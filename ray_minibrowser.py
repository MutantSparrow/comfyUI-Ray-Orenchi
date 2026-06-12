"""RayMiniBrowser node — nested mini-browser inside a ComfyUI node.

The node hosts a same-origin iframe served by `minibrowser_routes.py`. The
frontend ships the picked element's text and a batch of WebP rasterizations
back to a server-side cache keyed by node_id. On execute, this module
decodes every cached image and stacks them into the ComfyUI IMAGE batch
convention (BHWC float32 in [0, 1], all batch entries share H and W via
black-letterboxing).
"""

from __future__ import annotations

import base64
import io
import json

import numpy as np
from PIL import Image

try:
    import torch
except ImportError:  # pragma: no cover - torch is required at runtime
    torch = None


# Selection cache populated by POST /ray_minibrowser/select. Entries:
#   {"text": str, "images": list[str], "url": str, "ts": float}
SELECTION_CACHE: dict = {}
SELECTION_CACHE_MAX = 64


def _decode_one(b64: str):
    """Decode one base64 PNG/WebP into an HWC float32 [0,1] numpy array."""
    if not b64:
        return None
    try:
        raw = base64.b64decode(b64)
        with Image.open(io.BytesIO(raw)) as img:
            img = img.convert("RGB")
            return np.asarray(img, dtype=np.float32) / 255.0
    except Exception as e:
        print(f"[RayMiniBrowser] image decode error: {e}")
        return None


def _stack_letterbox(frames: list[np.ndarray]):
    """Pad each HWC frame onto a common (max H, max W) canvas with black.

    Returns BHWC float32 [0,1] tensor or None if torch unavailable.
    """
    if torch is None or not frames:
        return None
    max_h = max(f.shape[0] for f in frames)
    max_w = max(f.shape[1] for f in frames)
    out = np.zeros((len(frames), max_h, max_w, 3), dtype=np.float32)
    for i, f in enumerate(frames):
        h, w = f.shape[0], f.shape[1]
        out[i, :h, :w, :] = f
    return torch.from_numpy(out).contiguous().clamp(0.0, 1.0)


def _placeholder_tensor():
    if torch is None:
        return None
    return torch.zeros((1, 1, 1, 3), dtype=torch.float32)


def _images_from_pending(pending: str) -> list[str]:
    if not pending:
        return []
    try:
        parsed = json.loads(pending)
        if isinstance(parsed, list):
            return [str(x) for x in parsed if isinstance(x, str) and x]
    except Exception:
        pass
    # Back-compat with the early single-image field shape
    return [pending] if isinstance(pending, str) and pending else []


class RayMiniBrowser:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "url": ("STRING", {"default": "https://example.com"}),
                "pending_text": ("STRING", {"default": "", "multiline": True}),
                "pending_images_json": ("STRING", {"default": "[]", "multiline": True}),
            },
            "hidden": {"node_id": "UNIQUE_ID"},
        }

    RETURN_TYPES = ("STRING", "IMAGE")
    RETURN_NAMES = ("selected_text", "selected_images")
    FUNCTION = "process"
    CATEGORY = "Ray/UI🌐"

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("nan")

    def process(self, url, pending_text, pending_images_json, node_id=None):
        text = ""
        images_b64: list[str] = []
        final_url = url or ""

        entry = SELECTION_CACHE.get(str(node_id)) if node_id is not None else None
        if entry:
            text = entry.get("text") or ""
            images_b64 = list(entry.get("images") or [])
            final_url = entry.get("url") or final_url

        # Cold start (workflow loaded from disk before any in-session pick)
        if not text and not images_b64:
            text = pending_text or ""
            images_b64 = _images_from_pending(pending_images_json)

        decoded = [_decode_one(b) for b in images_b64]
        decoded = [d for d in decoded if d is not None]

        if decoded:
            tensor = _stack_letterbox(decoded)
        else:
            tensor = _placeholder_tensor()
        if tensor is None:
            tensor = _placeholder_tensor()

        return {
            "ui": {
                "ray_mb_url": [final_url],
                "ray_mb_text": [text],
                "ray_mb_image_count": [len(decoded)],
            },
            "result": (text, tensor),
        }
