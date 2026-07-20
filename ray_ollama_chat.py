import base64
import io
import json
import re
import wave

import numpy as np
from PIL import Image

try:
    import torch
except ImportError:
    torch = None

try:
    import ollama
except ImportError:
    ollama = None


IMAGE_CACHE: dict = {}
AUDIO_CACHE: dict = {}


def _safe_get(obj, *path, default=None):
    """Walk a mixed dict/attr chain; return `default` if any link is missing."""
    for key in path:
        if obj is None:
            return default
        if isinstance(obj, dict):
            obj = obj.get(key)
        else:
            obj = getattr(obj, key, None)
    return default if obj is None else obj


def audio_to_b64_wav(audio_dict) -> str:
    if audio_dict is None:
        return ""
    waveform = audio_dict.get("waveform") if isinstance(audio_dict, dict) else getattr(audio_dict, "waveform", None)
    sr = audio_dict.get("sample_rate") if isinstance(audio_dict, dict) else getattr(audio_dict, "sample_rate", 16000)
    if waveform is None:
        return ""
    arr = waveform.detach().cpu().numpy() if hasattr(waveform, "detach") else np.asarray(waveform)
    if arr.ndim == 3:
        arr = arr[0]
    if arr.ndim == 1:
        arr = arr[None, :]
    # arr now [C, T]
    arr = np.clip(arr * 32767.0, -32768, 32767).astype(np.int16)
    channels, nframes = arr.shape
    interleaved = arr.T.reshape(-1)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(int(sr))
        wf.writeframes(interleaved.tobytes())
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def tensor_to_b64_pngs(image_tensor) -> list:
    if image_tensor is None:
        return []
    arr = image_tensor.detach().cpu().numpy() if hasattr(image_tensor, "detach") else np.asarray(image_tensor)
    if arr.ndim == 3:
        arr = arr[None, ...]
    out = []
    for i in range(arr.shape[0]):
        frame = arr[i]
        frame = np.clip(frame * 255.0, 0, 255).astype(np.uint8)
        pil = Image.fromarray(frame)
        buf = io.BytesIO()
        pil.save(buf, format="PNG")
        out.append(base64.b64encode(buf.getvalue()).decode("utf-8"))
    return out


# ---------------------------------------------------------------------------
# CLIP-embedded LLM path: extract text encoder from a ComfyUI CLIP and use it
# directly. Skips Ollama entirely. Supports ComfyUI-native (Gemma/Qwen via
# SPiece) and HuggingFace transformer text encoders. Vision-language models
# rejected with a clear error.
# ---------------------------------------------------------------------------

def _find_comfyui_components(clip):
    tok_wrapper = getattr(clip, "tokenizer", None)
    model_wrapper = getattr(clip, "cond_stage_model", None)
    if tok_wrapper is None or model_wrapper is None:
        return None, None
    name = getattr(tok_wrapper, "clip", None)
    if name is None:
        return None, None
    sd_tokenizer = getattr(tok_wrapper, name, None)
    if sd_tokenizer is None:
        return None, None
    spiece_wrapper = getattr(sd_tokenizer, "tokenizer", None)
    if spiece_wrapper is None:
        return None, None
    spiece = getattr(spiece_wrapper, "tokenizer", spiece_wrapper)
    if not (hasattr(spiece, "encode") and hasattr(spiece, "decode")):
        return None, None
    sd_clip_model = getattr(model_wrapper, name, None)
    if sd_clip_model is None:
        return None, None
    transformer = getattr(sd_clip_model, "transformer", None)
    if transformer is None or not hasattr(transformer, "get_input_embeddings"):
        return None, None
    if hasattr(transformer, "visual") or hasattr(transformer, "vision_model"):
        return None, None
    return spiece, transformer


def _find_hf_tokenizer(clip):
    attr_chains = (
        ("tokenizer",),
        ("cond_stage_model", "tokenizer"),
        ("cond_stage_model", "model", "tokenizer"),
    )
    inner_attrs = ("tokenizer", "_tokenizer", "hf_tokenizer")
    for chain in attr_chains:
        obj = clip
        for attr in chain:
            obj = getattr(obj, attr, None)
            if obj is None:
                break
        if obj is None:
            continue
        if callable(obj) and hasattr(obj, "decode"):
            return obj
        for inner in inner_attrs:
            candidate = getattr(obj, inner, None)
            if candidate is not None and callable(candidate) and hasattr(candidate, "decode"):
                return candidate
    return None


def _find_hf_text_encoder(clip):
    attr_chains = (
        ("cond_stage_model", "model"),
        ("cond_stage_model", "transformer"),
        ("cond_stage_model",),
        ("text_encoder",),
    )
    for chain in attr_chains:
        obj = clip
        for attr in chain:
            obj = getattr(obj, attr, None)
            if obj is None:
                break
        if obj is not None and hasattr(obj, "forward") and hasattr(obj, "generate"):
            return obj
    return None


def _check_vision_model(clip):
    model_wrapper = getattr(clip, "cond_stage_model", None)
    if model_wrapper is None:
        return
    name = getattr(model_wrapper, "clip", None)
    if name is None:
        return
    sd_clip_model = getattr(model_wrapper, name, None)
    if sd_clip_model is None:
        return
    transformer = getattr(sd_clip_model, "transformer", None)
    if transformer is not None and (hasattr(transformer, "visual") or hasattr(transformer, "vision_model")):
        raise ValueError(
            "This CLIP model is a Vision-Language model (e.g. Qwen 2.5 VL, "
            "Gemma 3 Vision). VL models are fine-tuned for image conditioning, "
            "not for text generation. Use a text-only LLM clip instead."
        )


def _sample_next_token(logits, generated, do_sample, temperature, top_p, repetition_penalty):
    if repetition_penalty > 1.0:
        unique_ids = torch.unique(generated[0]).to(logits.device)
        tok_logits = logits[0, unique_ids]
        adjusted = torch.where(
            tok_logits < 0,
            tok_logits * repetition_penalty,
            tok_logits / repetition_penalty,
        )
        logits[0, unique_ids] = adjusted
    if do_sample:
        temp = max(float(temperature), 1e-5)
        logits = logits / temp
        if top_p < 1.0:
            sorted_logits, sorted_indices = torch.sort(logits, descending=True, dim=-1)
            sorted_probs = torch.softmax(sorted_logits, dim=-1)
            cumulative = torch.cumsum(sorted_probs, dim=-1)
            remove = cumulative > top_p
            remove[..., 1:] = remove[..., :-1].clone()
            remove[..., 0] = False
            mask = torch.zeros_like(remove, dtype=torch.bool)
            mask.scatter_(-1, sorted_indices, remove)
            logits = logits.masked_fill(mask, float("-inf"))
        probs = torch.softmax(logits, dim=-1)
        return torch.multinomial(probs, num_samples=1)
    else:
        return logits.argmax(dim=-1, keepdim=True)


def _generate_comfyui(*, model, input_ids, max_new_tokens, stop_tokens=None,
                     do_sample=False, temperature=1.0, top_p=1.0, repetition_penalty=1.0):
    embed_weight = model.get_input_embeddings().weight
    generated = input_ids
    step = 0
    with torch.inference_mode():
        for step in range(max_new_tokens):
            result = model(generated)
            hidden = result[0] if isinstance(result, tuple) else result
            logits = torch.nn.functional.linear(hidden[:, -1:, :].float(), embed_weight.float())
            next_token = _sample_next_token(
                logits[:, 0, :] if logits.dim() == 3 else logits,
                generated, do_sample, temperature, top_p, repetition_penalty,
            )
            token_id = next_token.item()
            generated = torch.cat([generated, next_token.to(generated.device)], dim=-1)
            if stop_tokens and token_id in stop_tokens:
                break
    return generated


def _generate_hf(*, text_encoder, tokenizer, encoded, max_new_tokens, do_sample,
                temperature, top_p, repetition_penalty=1.0):
    generate_kwargs = {
        "max_new_tokens": max_new_tokens,
        "do_sample": do_sample,
        "temperature": temperature,
        "top_p": top_p,
        "repetition_penalty": repetition_penalty,
    }
    pad_token_id = getattr(tokenizer, "pad_token_id", None)
    eos_token_id = getattr(tokenizer, "eos_token_id", None)
    if pad_token_id is not None:
        generate_kwargs["pad_token_id"] = pad_token_id
    if eos_token_id is not None:
        generate_kwargs["eos_token_id"] = eos_token_id
    with torch.inference_mode():
        return text_encoder.generate(**encoded, **generate_kwargs)


def _extract_response(full_text: str, input_text: str) -> str:
    candidate = (
        full_text[len(input_text):].strip()
        if full_text.startswith(input_text)
        else full_text.strip()
    )
    candidate = re.sub(r"<think>.*?</think>\s*", "", candidate, flags=re.DOTALL).strip()
    for marker in ("Response:", "Rewritten prompt:", "Assistant:"):
        if marker in candidate:
            candidate = candidate.split(marker, 1)[-1].strip()
    candidate = " ".join(line.strip() for line in candidate.splitlines() if line.strip()) if candidate else ""
    return candidate


def _build_chat_text(system_prompt, history, user_prompt):
    parts = []
    if system_prompt and system_prompt.strip():
        parts.append(f"System: {system_prompt.strip()}")
    for m in history or []:
        if not isinstance(m, dict):
            continue
        role = m.get("role", "user").capitalize()
        content = m.get("content", "")
        if content:
            parts.append(f"{role}: {content}")
    parts.append(f"User: {user_prompt}")
    parts.append("Assistant:")
    return "\n\n".join(parts)


class RayOllamaChat:
    DESCRIPTION = (
        "Inline chat node with two backends. `ollama` talks to a local "
        "Ollama server (supports image + audio attachments per turn); "
        "`clip` drives the text encoder of a ComfyUI-loaded CLIP model "
        "directly, no external server. Vision-language CLIPs are "
        "rejected in CLIP mode.\n\n"
        "The chat UI is rendered inside the node. Conversation history "
        "and last message live on the node so workflows reload chats "
        "after restart. `think` toggles Ollama's thinking-mode where "
        "the model supports it."
    )

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "inference_mode": (["ollama", "clip"], {
                    "default": "ollama",
                    "tooltip": "ollama = local Ollama server. clip = ComfyUI CLIP text encoder.",
                }),
                "server_url":   ("STRING",  {"default": "http://localhost:11434",
                                              "tooltip": "Ollama server URL."}),
                "model":        ("STRING",  {"default": "",
                                              "tooltip": "Ollama model name (or hint for CLIP mode)."}),
                "keep_alive":   ("STRING",  {"default": "5m",
                                              "tooltip": "Ollama keep-alive window (e.g. 5m)."}),
                "temperature":  ("FLOAT",   {"default": 0.7, "min": 0.0, "max": 2.0, "step": 0.05,
                                              "tooltip": "Sampling temperature."}),
                "seed":         ("INT",     {"default": -1, "min": -1, "max": 2**31 - 1,
                                              "tooltip": "-1 for random; any >=0 value is reproducible."}),
                "think":        ("BOOLEAN", {"default": False,
                                              "tooltip": "Enable Ollama thinking mode where supported."}),
                "chat_history": ("STRING",  {"default": "[]", "multiline": True,
                                              "tooltip": "Hidden JSON-encoded chat log — managed by the widget."}),
                "last_message": ("STRING",  {"default": "",   "multiline": True,
                                              "tooltip": "Hidden — last assistant reply."}),
                "pending_user_prompt": ("STRING", {"default": "", "multiline": True,
                                                    "tooltip": "Hidden — user-typed message queued for the next turn."}),
                "attach_image": ("BOOLEAN", {"default": True,
                                              "tooltip": "Attach the IMAGE input on the next turn."}),
                "attach_audio": ("BOOLEAN", {"default": True,
                                              "tooltip": "Attach the AUDIO input on the next turn."}),
            },
            "optional": {
                "system_prompt": ("STRING", {"forceInput": True, "multiline": True,
                                              "tooltip": "System message override."}),
                "user_prompt":   ("STRING", {"forceInput": True, "multiline": True,
                                              "tooltip": "One-shot user message (alternative to typing)."}),
                "image":         ("IMAGE",  {"tooltip": "Image to attach when attach_image is on."}),
                "audio":         ("AUDIO",  {"tooltip": "Audio to attach when attach_audio is on."}),
                "clip":          ("CLIP",   {"tooltip": "Required for CLIP inference_mode."}),
                "max_new_tokens": ("INT",   {"default": 256, "min": 1, "max": 4096, "step": 1,
                                              "tooltip": "CLIP mode: generation cap."}),
                "top_p":          ("FLOAT", {"default": 0.92, "min": 0.0, "max": 1.0, "step": 0.01,
                                              "tooltip": "CLIP mode: nucleus sampling."}),
                "repetition_penalty": ("FLOAT", {"default": 1.08, "min": 1.0, "max": 2.0, "step": 0.01,
                                                  "tooltip": "CLIP mode: repetition penalty."}),
            },
            "hidden": {"node_id": "UNIQUE_ID"},
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("last_message",)
    OUTPUT_TOOLTIPS = ("Last assistant reply.",)
    FUNCTION = "process"
    CATEGORY = "👑 Ray/💬 LLM"

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("nan")

    def process(
        self,
        inference_mode,
        server_url,
        model,
        keep_alive,
        temperature,
        seed,
        think,
        chat_history,
        last_message,
        pending_user_prompt="",
        attach_image=True,
        attach_audio=True,
        system_prompt=None,
        user_prompt=None,
        image=None,
        audio=None,
        clip=None,
        max_new_tokens=256,
        top_p=0.92,
        repetition_penalty=1.08,
        node_id=None,
    ):
        # Run-mode entrypoint: chatbox text travels through pending_user_prompt
        if (not user_prompt or not user_prompt.strip()) and pending_user_prompt and pending_user_prompt.strip():
            user_prompt = pending_user_prompt

        if inference_mode == "ollama":
            if image is not None and attach_image and node_id is not None:
                try:
                    IMAGE_CACHE[str(node_id)] = tensor_to_b64_pngs(image)
                except Exception as e:
                    print(f"[RayOllamaChat] image cache error: {e}")
            if audio is not None and attach_audio and node_id is not None:
                try:
                    b64 = audio_to_b64_wav(audio)
                    AUDIO_CACHE[str(node_id)] = [b64] if b64 else []
                except Exception as e:
                    print(f"[RayOllamaChat] audio cache error: {e}")

        if not user_prompt or not user_prompt.strip():
            return (last_message or "",)

        if inference_mode == "clip":
            if clip is None:
                err = "[RayOllamaChat] CLIP mode selected but no clip input connected."
                print(err)
                return (err,)
            try:
                history = json.loads(chat_history) if chat_history else []
            except Exception:
                history = []
            clip_result = self._process_clip(
                clip=clip,
                system_prompt=system_prompt,
                history=history,
                user_prompt=user_prompt,
                seed=seed,
                temperature=temperature,
                top_p=top_p,
                repetition_penalty=repetition_penalty,
                max_new_tokens=max_new_tokens,
            )
            clip_content = clip_result[0] if isinstance(clip_result, tuple) else ""
            return {
                "ui": {
                    "ray_chat_user": [user_prompt],
                    "ray_chat_assistant": [clip_content],
                    "ray_chat_had_image": [False],
                    "ray_chat_had_audio": [False],
                },
                "result": (clip_content,),
            }

        if ollama is None:
            err = "[RayOllamaChat] ollama package not installed. pip install ollama"
            print(err)
            return (err,)

        try:
            history = json.loads(chat_history) if chat_history else []
        except Exception:
            history = []

        def _is_real_b64(s):
            return isinstance(s, str) and s and s != "__attached__"

        messages = []
        if system_prompt and system_prompt.strip():
            messages.append({"role": "system", "content": system_prompt})
        for m in history:
            if not (isinstance(m, dict) and "role" in m and "content" in m):
                continue
            msg = {"role": m["role"], "content": m["content"]}
            imgs = [s for s in (m.get("images") or []) if _is_real_b64(s)]
            if imgs:
                msg["images"] = imgs
            auds = [s for s in (m.get("audios") or []) if _is_real_b64(s)]
            if auds:
                msg["audios"] = auds
            messages.append(msg)

        # Run mode: JS already pushed the user msg into chat_history before queueing
        # (with an "__attached__" marker that gets stripped during history build).
        # Re-using that trailing user msg avoids sending Ollama two consecutive user
        # turns where only the second one carries the image — vision models drop the
        # image in that case. Send mode never hits this branch.
        if (messages and messages[-1].get("role") == "user"
                and messages[-1].get("content") == user_prompt):
            target_msg = messages[-1]
        else:
            target_msg = {"role": "user", "content": user_prompt}
            messages.append(target_msg)
        if image is not None and attach_image:
            try:
                imgs = tensor_to_b64_pngs(image)
                if imgs:
                    target_msg["images"] = imgs
            except Exception as e:
                print(f"[RayOllamaChat] image encode error: {e}")
        if audio is not None and attach_audio:
            try:
                b64 = audio_to_b64_wav(audio)
                if b64:
                    target_msg["audios"] = [b64]
            except Exception as e:
                print(f"[RayOllamaChat] audio encode error: {e}")

        options = {"temperature": float(temperature)}
        if int(seed) >= 0:
            options["seed"] = int(seed)

        try:
            client = ollama.Client(host=server_url)
            chat_kwargs = dict(
                model=model,
                messages=messages,
                stream=False,
                keep_alive=keep_alive or "5m",
                options=options,
            )
            if think:
                chat_kwargs["think"] = True
            try:
                resp = client.chat(**chat_kwargs)
            except TypeError:
                chat_kwargs.pop("think", None)
                resp = client.chat(**chat_kwargs)
            content = _safe_get(resp, "message", "content", default="")
        except Exception as e:
            err = f"[RayOllamaChat] ollama error: {e}"
            print(err)
            return (err,)

        had_image = bool(image is not None and attach_image and "images" in target_msg)
        had_audio = bool(audio is not None and attach_audio and "audios" in target_msg)
        return {
            "ui": {
                "ray_chat_user": [user_prompt],
                "ray_chat_assistant": [content],
                "ray_chat_had_image": [had_image],
                "ray_chat_had_audio": [had_audio],
            },
            "result": (content,),
        }

    # ------------------------------------------------------------------ #
    # CLIP-embedded LLM path
    # ------------------------------------------------------------------ #

    def _process_clip(self, *, clip, system_prompt, history, user_prompt,
                      seed, temperature, top_p, repetition_penalty, max_new_tokens):
        if torch is None:
            err = "[RayOllamaChat] torch not available — cannot use CLIP path"
            print(err)
            return (err,)

        try:
            seed_int = int(seed)
            if seed_int < 0:
                seed_int = 0
            torch.manual_seed(seed_int)
            if torch.cuda.is_available():
                torch.cuda.manual_seed_all(seed_int)

            _check_vision_model(clip)

            chat_input = _build_chat_text(system_prompt, history, user_prompt)
            do_sample = float(temperature) > 0.0

            spiece, comfyui_model = _find_comfyui_components(clip)
            if spiece is not None and comfyui_model is not None:
                return self._clip_comfyui(
                    clip=clip, spiece=spiece, model=comfyui_model,
                    chat_input=chat_input, do_sample=do_sample,
                    temperature=float(temperature), top_p=float(top_p),
                    repetition_penalty=float(repetition_penalty),
                    max_new_tokens=int(max_new_tokens),
                    fallback_text=user_prompt,
                )

            hf_tokenizer = _find_hf_tokenizer(clip)
            hf_encoder = _find_hf_text_encoder(clip)
            if hf_tokenizer is not None and hf_encoder is not None:
                return self._clip_hf(
                    tokenizer=hf_tokenizer, text_encoder=hf_encoder,
                    chat_input=chat_input, do_sample=do_sample,
                    temperature=float(temperature), top_p=float(top_p),
                    repetition_penalty=float(repetition_penalty),
                    max_new_tokens=int(max_new_tokens),
                    fallback_text=user_prompt,
                )

            err = ("[RayOllamaChat] No usable tokenizer/model in CLIP. "
                   "Need a CLIP whose text encoder is a transformer LLM "
                   "(Gemma/Llama/Qwen).")
            print(err)
            return (err,)
        except Exception as e:
            err = f"[RayOllamaChat] CLIP path error: {e}"
            print(err)
            return (err,)

    def _clip_comfyui(self, *, clip, spiece, model, chat_input, do_sample,
                      temperature, top_p, repetition_penalty, max_new_tokens, fallback_text):
        import comfy.model_management as model_management

        input_ids_list = spiece.encode(chat_input)
        input_ids = torch.tensor([input_ids_list], dtype=torch.long)

        model_management.load_models_gpu([clip.patcher], force_full_load=True)
        device = model_management.get_torch_device()
        model.to(device)
        input_ids = input_ids.to(device)

        saved_cast = {}
        for name, module in model.named_modules():
            if hasattr(module, "comfy_cast_weights"):
                saved_cast[name] = module.comfy_cast_weights
                module.comfy_cast_weights = False

        try:
            if hasattr(model, "generate"):
                embeds = model.get_input_embeddings()(input_ids)
                generated_ids = model.generate(
                    embeds=embeds,
                    do_sample=do_sample,
                    max_length=max_new_tokens,
                    temperature=temperature,
                    top_p=top_p,
                    repetition_penalty=repetition_penalty,
                    initial_tokens=input_ids_list,
                )
                full_text = spiece.decode(input_ids_list + generated_ids)
                input_text = spiece.decode(input_ids_list)
                result = _extract_response(full_text, input_text)
                if not result.strip():
                    result = fallback_text
                return (result[:4000],)

            stop_tokens = _safe_get(model, "model", "config", "stop_tokens")
            if not stop_tokens:
                eos_token_id = spiece.eos_id() if hasattr(spiece, "eos_id") else None
                if eos_token_id is not None and eos_token_id >= 0:
                    stop_tokens = [eos_token_id]

            output_ids = _generate_comfyui(
                model=model,
                input_ids=input_ids,
                max_new_tokens=max_new_tokens,
                stop_tokens=stop_tokens,
                do_sample=do_sample,
                temperature=temperature,
                top_p=top_p,
                repetition_penalty=repetition_penalty,
            )
        finally:
            for name, module in model.named_modules():
                if name in saved_cast:
                    module.comfy_cast_weights = saved_cast[name]

        full_text = spiece.decode(output_ids[0].tolist())
        input_text = spiece.decode(input_ids_list)
        result = _extract_response(full_text, input_text)
        if not result.strip():
            result = fallback_text
        return (result[:4000],)

    def _clip_hf(self, *, tokenizer, text_encoder, chat_input, do_sample,
                 temperature, top_p, repetition_penalty, max_new_tokens, fallback_text):
        encoded = tokenizer(chat_input, return_tensors="pt")
        try:
            device = next(text_encoder.parameters()).device
        except StopIteration:
            device = torch.device("cpu")
        encoded = {k: v.to(device) for k, v in encoded.items()}

        output_ids = _generate_hf(
            text_encoder=text_encoder,
            tokenizer=tokenizer,
            encoded=encoded,
            max_new_tokens=max_new_tokens,
            do_sample=do_sample,
            temperature=temperature,
            top_p=top_p,
            repetition_penalty=repetition_penalty,
        )

        full_text = tokenizer.decode(output_ids[0], skip_special_tokens=True)
        input_text = tokenizer.decode(encoded["input_ids"][0], skip_special_tokens=True)
        result = _extract_response(full_text, input_text)
        if not result.strip():
            result = fallback_text
        return (result[:4000],)
