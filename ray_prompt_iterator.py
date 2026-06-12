import json
import os
import pathlib
import re

try:
    import ollama
except ImportError:
    ollama = None

try:
    from .ray_ollama_chat import tensor_to_b64_pngs
except ImportError:
    from ray_ollama_chat import tensor_to_b64_pngs

_SYSPROMPT_PATH = pathlib.Path(__file__).parent / "iterator_sysprompt.txt"

_DEFAULT_SYSPROMPT = (
    "You are an expert prompt engineer for image generation models.\n"
    "Score how well the image matches the prompt (0.0-1.0). Subtract for malformed anatomy "
    "(extra limbs/fingers, distorted faces) unless prompted. Then output an improved prompt.\n"
    'Output strict JSON only: {"confidence": <float 0.0-1.0>, "new_prompt": "<string>"}'
)


def _load_sysprompt() -> str:
    try:
        return _SYSPROMPT_PATH.read_text(encoding="utf-8").strip()
    except Exception:
        return _DEFAULT_SYSPROMPT


def _parse_response(raw: str, fallback_prompt: str):
    """Extract {confidence, new_prompt} from model output. Tolerant to fenced/wrapped JSON."""
    text = (raw or "").strip()
    # Strip ```json fences if present
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    # Find first {...} block
    m = re.search(r"\{.*\}", text, flags=re.DOTALL)
    candidate = m.group(0) if m else text
    try:
        data = json.loads(candidate)
        conf = float(data.get("confidence", 0.0))
        conf = max(0.0, min(1.0, conf))
        new_prompt = str(data.get("new_prompt", "")).strip() or fallback_prompt
        return conf, new_prompt
    except Exception:
        return 0.0, text or fallback_prompt


class RayPromptIterator:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "server_url":     ("STRING",  {"default": "http://localhost:11434"}),
                "model":          ("STRING",  {"default": ""}),
                "keep_alive":     ("STRING",  {"default": "5m"}),
                "temperature":    ("FLOAT",   {"default": 0.8, "min": 0.0, "max": 2.0, "step": 0.05}),
                "seed":           ("INT",     {"default": -1, "min": -1, "max": 2**31 - 1}),
                "copy_to_clipboard":("BOOLEAN",{"default": False}),
                "original_prompt":("STRING",  {"forceInput": True}),
            },
            "optional": {
                "image":           ("IMAGE",),
                "changes_required":("STRING",  {"forceInput": True}),
            },
            "hidden": {
                "node_id": "UNIQUE_ID",
            },
        }

    RETURN_TYPES = ("STRING", "FLOAT", "IMAGE",)
    RETURN_NAMES = ("new_prompt", "confidence", "image",)
    FUNCTION = "process"
    CATEGORY = "Ray/LLM💬"

    def process(self, server_url, model, keep_alive, temperature, seed, copy_to_clipboard,
                original_prompt, image=None, changes_required=None, node_id=None):
        if ollama is None:
            raise RuntimeError("ollama package not installed")
        if not model:
            raise ValueError("No model selected")

        sysprompt = _load_sysprompt()

        user_message = original_prompt or ""
        if changes_required and changes_required.strip():
            user_message += f"\n\nAdditional instruction: {changes_required.strip()}"

        user_msg: dict = {"role": "user", "content": user_message}
        if image is not None:
            b64_list = tensor_to_b64_pngs(image)
            if b64_list:
                user_msg["images"] = [b64_list[0]]

        messages = [
            {"role": "system", "content": sysprompt},
            user_msg,
        ]

        options: dict = {"temperature": temperature}
        if seed != -1:
            options["seed"] = seed

        client = ollama.Client(host=server_url)
        resp = client.chat(
            model=model,
            messages=messages,
            stream=False,
            keep_alive=keep_alive,
            options=options,
        )

        content = resp["message"]["content"] if isinstance(resp, dict) else resp.message.content
        confidence, new_prompt = _parse_response(content, fallback_prompt=original_prompt or "")
        return {
            "ui": {
                "ray_new_prompt":    [new_prompt],
                "ray_confidence":    [confidence],
                "copy_to_clipboard": [bool(copy_to_clipboard)],
            },
            "result": (new_prompt, confidence, image,),
        }
