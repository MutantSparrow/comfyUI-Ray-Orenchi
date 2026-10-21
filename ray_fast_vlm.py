"""Generic Qwen text generation with a fast Qwen3-VL decode path."""
import logging
from functools import partial
from types import MethodType

import torch
import comfy_kitchen
import comfy.model_management as mm
import comfy.model_prefetch as prefetch
from comfy.text_encoders.qwen3vl import Qwen3VL
from comfy.utils import ProgressBar


def repeated_tail_start(tokens):
    """Keep the first copy when an 8–256 token phrase repeats three times."""
    size = len(tokens)
    for period in range(8, min(256, size // 3) + 1):
        if tokens[-period:] == tokens[-2 * period:-period] == tokens[-3 * period:-2 * period]:
            return size - 2 * period
    return None



def penalize_seen(logits, seen, repetition_penalty, presence_penalty):
    if repetition_penalty != 1.0:
        adjusted = torch.where(logits < 0, logits * repetition_penalty, logits / repetition_penalty)
        logits = torch.where(seen, adjusted, logits)
    if presence_penalty:
        logits = logits - seen.to(logits.dtype) * presence_penalty
    return logits



def input_tokens(clip, transformer, image, prompt, thinking):
    """Tokenize a Qwen request, using images only for supported VL models."""
    is_qwen3vl = isinstance(transformer, Qwen3VL)

    # Non-VL Qwen encoders own their prompt formatting. Passing `thinking`
    # through lets Qwen3/Qwen3.5 tokenizers select their native chat template
    # when they support it. An attached image is deliberately ignored.
    if not is_qwen3vl:
        if image is not None:
            logging.info(
                "[FastQwen] Ignoring image input for text-only model %s",
                type(transformer).__name__,
            )
        return clip.tokenize(prompt, thinking=thinking)

    # Qwen3-VL keeps the behavior of the original node. Instruct's official
    # template ends at assistant\n without inventing a completed reasoning
    # block; Thinking models are delegated to the tokenizer's native template.
    if image is None:
        if thinking:
            return clip.tokenize(prompt, thinking=True)
        chat = "<|im_start|>user\n" + prompt + "<|im_end|>\n<|im_start|>assistant\n"
        return clip.tokenize(chat, skip_template=True)

    images = [image[i:i + 1, ..., :3] for i in range(image.shape[0])]
    if thinking:
        tokens = clip.tokenize(prompt, images=images, thinking=True)
    else:
        vision = "<|vision_start|><|image_pad|><|vision_end|>" * len(images)
        chat = "<|im_start|>user\n" + vision + prompt + "<|im_end|>\n<|im_start|>assistant\n"
        tokens = clip.tokenize(chat, images=images, skip_template=True)

    count = sum(
        isinstance(t[0], dict) and t[0].get("type") == "image"
        for batches in tokens.values()
        for batch in batches
        for t in batch
    )
    if count != len(images):
        raise ValueError(
            f"Qwen VL tokenizer attached {count} of {len(images)} images. "
            "Generation stopped to avoid an accidental text-only answer."
        )
    logging.info("[FastQwen] Attached %d image(s)", count)
    return tokens


def decode_step(model, embeds, position_ids, cache, state):
    """Native blocks with request-local, stable graph input addresses.

    Llama2_.forward allocates new x/frequency tensors on each call. Their
    addresses can change after capture, but native replay checks weight
    signatures only. Keep these three small inputs alive for this request.

    Newer ComfyUI releases share the FixedKV position/seqlen tensors between
    all transformer layers. Older releases allocate them per layer. Detect the
    layout at runtime so the shared counters are prepared once per token while
    keeping compatibility with older per-layer caches.
    """
    x, frequencies = state
    x.copy_(embeds)
    computed = model.compute_freqs_cis(position_ids, x.device)
    for target, source in zip(frequencies, computed):
        target.copy_(source)

    queue = prefetch.make_prefetch_queue(
        list(model.layers), x.device, {"prefetch_dynamic_vbars": True}
    )

    shared_kv_state = (
        len(cache) > 1
        and getattr(cache[0], "position", None) is not None
        and getattr(cache[0], "seqlen", None) is not None
        and getattr(cache[1], "position", None) is cache[0].position
        and getattr(cache[1], "seqlen", None) is cache[0].seqlen
    )

    for i, (layer, kv) in enumerate(zip(model.layers, cache)):
        # ComfyUI >= Oct 17 2026: plain FixedKV caches share GPU counters.
        # Preparing every layer would advance seqlen once per transformer block
        # and eventually send flash-attention beyond the valid cache range.
        if not shared_kv_state or i == 0:
            kv.prepare(1)

        def core():
            result, _ = layer(
                x=x,
                attention_mask=None,
                freqs_cis=frequencies,
                optimized_attention=None,
                past_key_value=kv,
            )
            x.copy_(result)

        prefetch.prefetch_queue_pop(
            queue,
            x.device,
            layer,
            x.dtype,
            core=core,
            enable_graph=True,
            malloc_scope="block",
        )
        # The Python-side cache index remains per-layer even when the GPU
        # position/seqlen tensors are shared, so each layer still advances.
        kv.advance(1)

    prefetch.prefetch_queue_pop(queue, x.device, None, malloc_scope="block")
    return model.norm(x) if model.norm is not None else x



def fast_generate(self, *args, **kwargs):
    request_buffers = []
    try:
        return _generate_tokens(self, *args, _request_buffers=request_buffers, **kwargs)
    finally:
        # Graphs reference request-local KV and activation buffers. Release them
        # before another call or another CLIP consumer can reuse this model.
        if self.model.graph_dynamic_vbar_blocks:
            prefetch.cleanup_prefetch_queues()



def _generate_tokens(self, embeds=None, do_sample=True, max_length=256,
                  temperature=1.0, top_k=50, top_p=0.9, min_p=0.0,
                  repetition_penalty=1.0, seed=42, presence_penalty=0.0,
                  position_ids=None, visual_pos_masks=None, deepstack_embeds=None,
                  *, sync_interval=8, repeat_guard=True, _request_buffers):
    """Keep sampling on device; check EOS in bounded chunks, returning the first EOS."""
    device = embeds.device
    dtype = torch.bfloat16 if mm.should_use_bf16(device) else torch.float32
    embeds = embeds.to(dtype)
    if embeds.ndim == 2:
        embeds = embeds.unsqueeze(0)
    if embeds.shape[0] != 1:
        raise ValueError("Fast Qwen3-VL Infer supports one conversation per call.")
    cache = self.init_kv_cache(1, embeds.shape[1] + max_length, device, dtype)
    _request_buffers.append(cache)
    generator = torch.Generator(device=device).manual_seed(seed) if do_sample else None
    output = torch.empty((max_length,), dtype=torch.long, device=device)
    decode_token = torch.empty((1, 1), dtype=torch.long, device=device)
    # MRoPE decode follows the image-aware maximum, not the KV cache length.
    next_position = (position_ids[:, -1].max() + 1).reshape(1, 1) if position_ids is not None else None
    compiled = self.model.graph_dynamic_vbar_blocks and prefetch.malloc_graph_enabled(device)
    if compiled:
        if next_position is None:
            next_position = torch.full((1, 1), embeds.shape[1], device=device, dtype=torch.long)
        state = (
            torch.empty((1, 1, embeds.shape[-1]), device=device, dtype=dtype),
            tuple(t.clone() for t in self.model.compute_freqs_cis(next_position, device)),
        )
        _request_buffers.append(state)
    stop_tokens = set(self.model.config.stop_tokens)
    progress = ProgressBar(max_length)
    generated = []
    checked = 0
    seen = None
    for step in range(max_length):
        mm.throw_exception_if_processing_interrupted()
        graph_active = step > 0 and compiled
        if graph_active:
            prefetch.malloc_graph_begin(device)
        try:
            if step > 0:
                embeds = self.model.embed_tokens(decode_token).to(dtype)
                position_ids = next_position
            extra = {}
            if step == 0 and deepstack_embeds is not None:
                extra = dict(deepstack_embeds=deepstack_embeds, visual_pos_masks=visual_pos_masks)
            if step > 0 and compiled:
                x = decode_step(self.model, embeds, position_ids, cache, state)
            else:
                x, _, cache = self.model.forward(
                    None,
                    embeds=embeds,
                    attention_mask=None,
                    past_key_values=cache,
                    position_ids=position_ids,
                    **extra,
                )
            logits = self.logits(x)[:, -1]
            if repetition_penalty != 1.0 or presence_penalty:
                if seen is None:
                    seen = torch.zeros_like(logits, dtype=torch.bool)
                logits = penalize_seen(logits, seen, repetition_penalty, presence_penalty)
            token = self.sample_token(
                logits, temperature, top_k, top_p, min_p,
                1.0, [], generator, do_sample=do_sample
            )
            if seen is not None:
                seen.scatter_(1, token, True)
            decode_token.copy_(token)
            output[step:step + 1].copy_(token.reshape(-1))
            del token, logits, x, embeds, position_ids
        finally:
            if graph_active:
                prefetch.malloc_graph_end()
        if step > 0 and next_position is not None:
            next_position.add_(1)
        if (step + 1) % sync_interval == 0 or step + 1 == max_length:
            chunk = output[checked:step + 1].tolist()
            checked = step + 1
            for token_id in chunk:
                generated.append(token_id)
                if token_id in stop_tokens:
                    logging.info(
                        "[FastVLM] End of answer after %d tokens (limit %d)",
                        len(generated), max_length
                    )
                    progress.update_absolute(len(generated))
                    return generated
                cut = repeated_tail_start(generated) if repeat_guard else None
                if cut is not None:
                    logging.warning(
                        "[FastVLM] Stopped a repeating token loop after %d tokens; retained %d",
                        len(generated), cut
                    )
                    progress.update_absolute(cut)
                    return generated[:cut]
            progress.update_absolute(len(generated))
    logging.info("[FastVLM] Reached maximum of %d tokens", max_length)
    return generated



def qwen_model(clip):
    """Locate a generative Qwen transformer inside a ComfyUI CLIP object.

    Keep detection intentionally conservative: the connected encoder must
    identify itself as Qwen by model type, class name or module path and expose
    a callable generation method. This admits native Qwen3, Qwen3.5 and
    Qwen3-VL wrappers without treating unrelated Llama-family encoders as Qwen.
    """
    stage = clip.cond_stage_model

    candidates = []
    preferred_name = getattr(stage, "clip", None)
    if isinstance(preferred_name, str):
        encoder = getattr(stage, preferred_name, None)
        if encoder is not None:
            candidates.append((preferred_name, encoder))

    # Some compound text-encoder wrappers do not expose the preferred encoder
    # in the same way. Fall back to scanning direct children for transformers.
    for name, encoder in vars(stage).items():
        if any(name == existing[0] for existing in candidates):
            continue
        if getattr(encoder, "transformer", None) is not None:
            candidates.append((name, encoder))

    detected = []
    for name, encoder in candidates:
        transformer = getattr(encoder, "transformer", None)
        if transformer is None:
            continue

        model_type = str(getattr(transformer, "model_type", "") or "")
        identity = (
            f"{type(transformer).__module__}.{type(transformer).__name__} "
            f"(encoder={name!r}, model_type={model_type!r})"
        )
        detected.append(identity)

        qwen_identity = " ".join((
            model_type,
            type(transformer).__name__,
            type(transformer).__module__,
            name,
        )).lower()
        if "qwen" not in qwen_identity:
            continue
        if not callable(getattr(transformer, "generate", None)):
            continue

        # ComfyUI's MiniMax-H3 Qwen3-VL 32B encoder is intentionally truncated
        # for conditioning and cannot produce normal LM output.
        if isinstance(transformer, Qwen3VL) and model_type == "qwen3vl_32b":
            raise ValueError(
                "The connected Qwen3-VL 32B MiniMax-H3 encoder is truncated for "
                "conditioning and does not support text generation. Connect a full "
                "generative Qwen checkpoint instead."
            )

        return name, encoder, transformer

    details = "; ".join(detected) if detected else "no transformer-bearing encoder found"
    raise ValueError(
        "Ray's Fast Qwen Infer needs a ComfyUI-native generative Qwen text encoder. "
        f"Detected: {details}."
    )


def prepare_qwen3vl_fast(clip, name, transformer, sync_interval=8, repeat_guard=True):
    """Patch only Qwen3-VL with Ray's chunk-synchronised fast decode path."""
    if not isinstance(transformer, Qwen3VL):
        return clip

    device = clip.patcher.load_device
    fixed = device.type == "cuda" and comfy_kitchen.flash_attention_decode_is_available(device)
    patched = clip.clone()
    prefix = name + ".transformer."
    patched.patcher.add_object_patch(prefix + "model.fixed_kv", fixed)

    # Let ComfyUI's allocator own graph capture, invalidation and offloading.
    graphs = fixed and clip.is_dynamic() and prefetch.malloc_graph_enabled(device)
    patched.patcher.add_object_patch(prefix + "model.graph_dynamic_vbar_blocks", graphs)
    patched.patcher.add_object_patch(prefix + "model.prefetch_dynamic_vbars", graphs)
    if graphs:
        # Read the original patcher view, not a previous FastQwen clone's patch.
        try:
            original_units = clip.patcher.get_model_object("get_dynamic_vram__units")
        except AttributeError:
            original_units = None
        if original_units is not None and not callable(original_units):
            original_units = None

        def units():
            first, last = original_units() if original_units else ([], [])
            return list(first) + list(transformer.model.layers), list(last)

        patched.patcher.add_object_patch("get_dynamic_vram__units", units)

    patched.patcher.add_object_patch(
        prefix + "generate",
        MethodType(
            partial(
                fast_generate,
                sync_interval=sync_interval,
                repeat_guard=repeat_guard,
            ),
            transformer,
        ),
    )
    logging.info(
        "[FastQwen] %s: kitchen decode=%s; native graph eligible=%s",
        getattr(transformer, "model_type", type(transformer).__name__),
        fixed,
        graphs,
    )
    return patched


class RayFastQwen3VL:
    # Registered class ID intentionally stays RayFastQwen3VL so existing
    # workflows continue to load. The node itself now accepts generic Qwen.
    DESCRIPTION = (
        "Generate text with ComfyUI-native Qwen models. Qwen3-VL supports optional "
        "images and Ray's fast decode path; text-only Qwen models ignore image input "
        "and use their native ComfyUI generator."
    )

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "clip": (
                    "CLIP",
                    {
                        "tooltip": (
                            "ComfyUI-native generative Qwen text encoder: Qwen3, "
                            "Qwen3.5, Qwen3-VL, or another compatible Qwen wrapper."
                        )
                    },
                ),
                "prompt": (
                    "STRING",
                    {
                        "default": "Describe this image in detail.",
                        "multiline": True,
                        "tooltip": (
                            "Prompt for the Qwen model. The connected tokenizer owns "
                            "the appropriate Qwen chat template."
                        ),
                    },
                ),
                "max_tokens": (
                    "INT",
                    {
                        "default": 256,
                        "min": 1,
                        "max": 8192,
                        "tooltip": "Maximum generated tokens. Reaching the cap truncates the answer.",
                    },
                ),
                "temperature": (
                    "FLOAT",
                    {
                        "default": 0.0,
                        "min": 0.0,
                        "max": 2.0,
                        "step": 0.01,
                        "tooltip": "Sampling randomness. 0 is greedy decoding; higher values vary the wording.",
                    },
                ),
                "top_p": (
                    "FLOAT",
                    {
                        "default": 0.9,
                        "min": 0.01,
                        "max": 1.0,
                        "step": 0.01,
                        "tooltip": "Nucleus sampling threshold. Ignored by greedy decoding.",
                    },
                ),
                "top_k": (
                    "INT",
                    {
                        "default": 40,
                        "min": 0,
                        "max": 1000,
                        "tooltip": "Top-k sampling limit. 0 disables it. Ignored by greedy decoding.",
                    },
                ),
                "seed": (
                    "INT",
                    {
                        "default": 42,
                        "min": 0,
                        "max": 2**63 - 1,
                        "tooltip": "Sampling seed when temperature is above 0.",
                    },
                ),
            },
            "optional": {
                "image": (
                    "IMAGE",
                    {
                        "tooltip": (
                            "Optional image or image batch for Qwen3-VL. If the connected "
                            "Qwen model is text-only, this input is ignored."
                        )
                    },
                ),
                "mode": (
                    ["fast", "native"],
                    {
                        "default": "fast",
                        "tooltip": (
                            "fast: use Ray's optimized path when the model is a compatible "
                            "Qwen3-VL; otherwise automatically use native ComfyUI generation. "
                            "native: always use the model's stock ComfyUI generator."
                        ),
                    },
                ),
                "sync_interval": (
                    "INT",
                    {
                        "default": 8,
                        "min": 1,
                        "max": 32,
                        "tooltip": (
                            "Qwen3-VL fast mode only: check stop tokens every N steps. "
                            "May compute up to N-1 extra tokens which are discarded."
                        ),
                    },
                ),
                "thinking": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "tooltip": (
                            "Pass the model's thinking-mode request through its tokenizer. "
                            "Effect depends on the connected Qwen tokenizer/checkpoint."
                        ),
                    },
                ),
                "repetition_penalty": (
                    "FLOAT",
                    {
                        "default": 1.0,
                        "min": 1.0,
                        "max": 2.0,
                        "step": 0.01,
                        "tooltip": "Scale down scores of tokens already generated. 1 disables it.",
                    },
                ),
                "presence_penalty": (
                    "FLOAT",
                    {
                        "default": 1.5,
                        "min": 0.0,
                        "max": 2.0,
                        "step": 0.1,
                        "tooltip": "Discourage reusing generated tokens. Set 0 to disable.",
                    },
                ),
                "repeat_guard": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "tooltip": (
                            "Qwen3-VL fast mode only: stop if an identical 8–256-token "
                            "phrase repeats three times."
                        ),
                    },
                ),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("text",)
    OUTPUT_TOOLTIPS = ("Decoded answer from the connected Qwen model.",)
    FUNCTION = "infer"
    CATEGORY = "👑 Ray/💬 LLM"

    def infer(self, clip, prompt, max_tokens=256, temperature=0.0,
              top_p=0.9, top_k=40, seed=42, image=None, mode="fast",
              sync_interval=8, thinking=False, repetition_penalty=1.0,
              presence_penalty=1.5, repeat_guard=True):
        if not 1 <= sync_interval <= 32 or not 1 <= max_tokens <= 8192:
            raise ValueError("Use sync_interval 1–32 and max_tokens 1–8192.")

        name, encoder, transformer = qwen_model(clip)
        is_qwen3vl = isinstance(transformer, Qwen3VL)

        if is_qwen3vl and image is not None:
            if image.ndim != 4 or image.shape[-1] < 3 or image.shape[0] < 1:
                raise ValueError(
                    "Connect a valid ComfyUI IMAGE tensor (batch, height, width, RGB), "
                    "or leave image disconnected."
                )

        if is_qwen3vl and prompt.startswith("<|im_start|>"):
            raise ValueError(
                "Enter a plain prompt for Qwen3-VL; the node adds its chat template."
            )

        # Only Qwen3-VL currently uses Ray's manual decode loop. Other Qwen
        # families retain their architecture-specific native cache/decode code.
        use_ray_fast = mode == "fast" and is_qwen3vl
        if use_ray_fast:
            native = prepare_qwen3vl_fast(
                clip, name, transformer, sync_interval, repeat_guard
            )
        else:
            native = clip
            if mode == "fast":
                logging.info(
                    "[FastQwen] %s is not on the Ray fast-path allowlist; using native ComfyUI generation.",
                    getattr(transformer, "model_type", type(transformer).__name__),
                )

        # Re-resolve the transformer on the patched clone for tokenization
        # decisions. The underlying tokenizer/model weights remain shared.
        if use_ray_fast:
            _, _, token_transformer = qwen_model(native)
        else:
            token_transformer = transformer

        tokens = input_tokens(native, token_transformer, image, prompt, thinking)
        ids = native.generate(
            tokens,
            do_sample=temperature > 0,
            max_length=max_tokens,
            temperature=temperature or 1.0,
            top_k=top_k,
            top_p=top_p,
            min_p=0.0,
            repetition_penalty=repetition_penalty,
            presence_penalty=presence_penalty,
            seed=seed,
        )
        return (native.decode(ids),)
