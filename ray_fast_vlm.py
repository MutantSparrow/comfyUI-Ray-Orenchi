"""Qwen3-VL generation using the supplied Comfy CLIP and native decode kernels."""
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


def image_tokens(clip, image, prompt, thinking):
    images = [image[i:i + 1, ..., :3] for i in range(image.shape[0])]
    # Instruct's official template ends at assistant\n, without an invented
    # completed reasoning block. Preserve native behavior for Thinking models.
    if thinking:
        tokens = clip.tokenize(prompt, images=images, thinking=True)
    else:
        vision = "<|vision_start|><|image_pad|><|vision_end|>" * len(images)
        chat = "<|im_start|>user\n" + vision + prompt + "<|im_end|>\n<|im_start|>assistant\n"
        tokens = clip.tokenize(chat, images=images, skip_template=True)
    count = sum(isinstance(t[0], dict) and t[0].get("type") == "image"
                for batches in tokens.values() for batch in batches for t in batch)
    if count != len(images):
        raise ValueError(f"VLM tokenizer attached {count} of {len(images)} images. Generation stopped to avoid a text-only answer.")
    logging.info("[FastVLM] Attached %d image(s)", count)
    return tokens


def decode_step(model, embeds, position_ids, cache, state):
    """Native blocks with request-local, stable graph input addresses.

    Llama2_.forward allocates new x/frequency tensors on each call. Their
    addresses can change after capture, but native replay checks weight
    signatures only. Keep these three small inputs alive for this request.
    """
    x, frequencies = state
    x.copy_(embeds)
    computed = model.compute_freqs_cis(position_ids, x.device)
    for target, source in zip(frequencies, computed):
        target.copy_(source)
    queue = prefetch.make_prefetch_queue(list(model.layers), x.device, {"prefetch_dynamic_vbars": True})
    for layer, kv in zip(model.layers, cache):
        kv.prepare(1)
        def core():
            result, _ = layer(x=x, attention_mask=None, freqs_cis=frequencies,
                              optimized_attention=None, past_key_value=kv)
            x.copy_(result)
        prefetch.prefetch_queue_pop(queue, x.device, layer, x.dtype, core=core,
                                   enable_graph=True, malloc_scope="block")
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
        state = (torch.empty((1, 1, embeds.shape[-1]), device=device, dtype=dtype),
                 tuple(t.clone() for t in self.model.compute_freqs_cis(next_position, device)))
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
                    None, embeds=embeds, attention_mask=None, past_key_values=cache,
                    position_ids=position_ids, **extra)
            logits = self.logits(x)[:, -1]
            if repetition_penalty != 1.0 or presence_penalty:
                if seen is None:
                    seen = torch.zeros_like(logits, dtype=torch.bool)
                logits = penalize_seen(logits, seen, repetition_penalty, presence_penalty)
            token = self.sample_token(logits, temperature, top_k, top_p, min_p,
                                     1.0, [], generator, do_sample=do_sample)
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
                    logging.info("[FastVLM] End of answer after %d tokens (limit %d)", len(generated), max_length)
                    progress.update_absolute(len(generated))
                    return generated
                cut = repeated_tail_start(generated) if repeat_guard else None
                if cut is not None:
                    logging.warning("[FastVLM] Stopped a repeating token loop after %d tokens; retained %d", len(generated), cut)
                    progress.update_absolute(cut)
                    return generated[:cut]
            progress.update_absolute(len(generated))
    logging.info("[FastVLM] Reached maximum of %d tokens", max_length)
    return generated


def qwen3vl_model(clip):
    stage = clip.cond_stage_model
    name = getattr(stage, "clip", None)
    encoder = getattr(stage, name, None) if isinstance(name, str) else None
    transformer = getattr(encoder, "transformer", None)
    detected = (f"{type(transformer).__module__}.{type(transformer).__name__} "
                f"(encoder={name!r}, model_type={getattr(transformer, 'model_type', None)!r})")
    if not isinstance(transformer, Qwen3VL):
        raise ValueError(
            f"Fast Qwen3-VL received {detected}, not a native Qwen3-VL model. "
            "In the connected CLIPLoader select Qwen/qwen3vl_8b_fp8_scaled.safetensors "
            "(or the full 4B equivalent), with type=qwen_image. The loader type alone "
            "does not turn Qwen2.5-VL or text-only Qwen3 weights into Qwen3-VL.")
    if transformer.model_type == "qwen3vl_32b":
        raise ValueError(
            f"Fast Qwen3-VL received {detected}. ComfyUI's native 32B MiniMax-H3 "
            "variant is truncated for conditioning, not supported for text generation. "
            "Connect a full Qwen3-VL 4B or 8B checkpoint.")
    return name, transformer


def prepare_clip(clip, sync_interval=8, repeat_guard=True):
    """Clone patcher metadata only. The tokenizer, model and all weights are shared."""
    name, transformer = qwen3vl_model(clip)
    stage = clip.cond_stage_model
    device = clip.patcher.load_device
    fixed = device.type == "cuda" and comfy_kitchen.flash_attention_decode_is_available(device)
    patched = clip.clone()
    prefix = name + ".transformer."
    patched.patcher.add_object_patch(prefix + "model.fixed_kv", fixed)
    # Let the native allocator own graph capture, invalidation and offloading.
    graphs = fixed and clip.is_dynamic() and prefetch.malloc_graph_enabled(device)
    patched.patcher.add_object_patch(prefix + "model.graph_dynamic_vbar_blocks", graphs)
    patched.patcher.add_object_patch(prefix + "model.prefetch_dynamic_vbars", graphs)
    if graphs:
        # Read the original patcher view, not a previous FastVLM clone's patch.
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
    patched.patcher.add_object_patch(prefix + "generate", MethodType(partial(fast_generate, sync_interval=sync_interval, repeat_guard=repeat_guard), transformer))
    logging.info("[FastVLM] Kitchen decode: %s; native graph eligible: %s", fixed, graphs)
    return patched


class RayFastQwen3VL:
    DESCRIPTION = "Generate text from images with the existing native Qwen3-VL CLIP. Shares model weights and preserves ComfyUI offloading."
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "clip": ("CLIP",),
            "image": ("IMAGE",),
            "prompt": ("STRING", {"default": "Describe this image in detail.", "multiline": True}),
            "max_tokens": ("INT", {"default": 256, "min": 1, "max": 8192}),
            "temperature": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 2.0, "step": 0.01}),
            "top_p": ("FLOAT", {"default": 0.9, "min": 0.01, "max": 1.0, "step": 0.01}),
            "top_k": ("INT", {"default": 40, "min": 0, "max": 1000}),
            "seed": ("INT", {"default": 42, "min": 0, "max": 2**63 - 1}),
        }, "optional": {
            "mode": (["fast", "native"], {"default": "fast"}),
            "sync_interval": ("INT", {"default": 8, "min": 1, "max": 32,
                "tooltip": "Check stop tokens every N steps. May compute up to N-1 extra tokens, which are discarded. Use 1 for immediate stop."}),
            "thinking": ("BOOLEAN", {"default": False}),
            "repetition_penalty": ("FLOAT", {"default": 1.0, "min": 1.0, "max": 2.0, "step": 0.01}),
            "presence_penalty": ("FLOAT", {"default": 1.5, "min": 0.0, "max": 2.0, "step": 0.1,
                "tooltip": "Discourage reusing generated tokens. Qwen recommends 1.5 for Instruct; use 0 for Thinking models."}),
            "repeat_guard": ("BOOLEAN", {"default": True, "tooltip": "Fast mode: stop if an identical 8–256-token phrase repeats three times. Retain its first copy."}),
        }}
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("text",)
    FUNCTION = "infer"
    CATEGORY = "👑 Ray/💬 LLM"

    def infer(self, clip, image, prompt, max_tokens=256, temperature=0.0,
              top_p=0.9, top_k=40, seed=42, mode="fast", sync_interval=8, thinking=False,
              repetition_penalty=1.0, presence_penalty=1.5, repeat_guard=True):
        if not 1 <= sync_interval <= 32 or not 1 <= max_tokens <= 8192:
            raise ValueError("Use sync_interval 1–32 and max_tokens 1–8192.")
        if image.ndim != 4 or image.shape[-1] < 3 or image.shape[0] < 1:
            raise ValueError("Connect a ComfyUI IMAGE tensor (batch, height, width, RGB).")
        if prompt.startswith("<|im_start|>"):
            raise ValueError("Enter a plain prompt; the native tokenizer adds the image chat template.")
        if mode == "fast":
            native = prepare_clip(clip, sync_interval, repeat_guard)
        else:
            qwen3vl_model(clip)
            native = clip
        tokens = image_tokens(native, image, prompt, thinking)
        ids = native.generate(tokens, do_sample=temperature > 0, max_length=max_tokens,
                              temperature=temperature or 1.0, top_k=top_k, top_p=top_p,
                              min_p=0.0, repetition_penalty=repetition_penalty,
                              presence_penalty=presence_penalty, seed=seed)
        return (native.decode(ids),)
