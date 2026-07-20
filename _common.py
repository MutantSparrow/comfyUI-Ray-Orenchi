"""Shared color-space + UI utilities for Ray's Orenchi nodes.

Hosts the sRGB piecewise gamma constants, ComfyUI tensor normalization, and
torch-side sRGB↔linear conversions. Both ray_crt.py and ray_pixel_detector.py
import from here so the constants and helpers exist exactly once.

Also hosts the `send_preview` helper that scraper/library nodes call at the
end of `process()` to update their inline preview widget.

Tensor convention (ComfyUI): IMAGE = BHWC float32 in [0, 1].
"""

from __future__ import annotations

import os
import pathlib
import time

import torch


# --- sRGB piecewise gamma constants ------------------------------------------

SRGB_LINEAR_THRESHOLD = 0.04045
SRGB_GAMMA_OFFSET = 0.055
SRGB_GAMMA_SLOPE = 1.055
SRGB_GAMMA_EXPONENT = 2.4
SRGB_LINEAR_SLOPE = 12.92
SRGB_LINEAR_THRESHOLD_INV = SRGB_LINEAR_THRESHOLD / SRGB_LINEAR_SLOPE


# --- Tensor utilities --------------------------------------------------------


def normalize_image(image: torch.Tensor) -> torch.Tensor:
    """Normalize a ComfyUI IMAGE tensor to BHWC float32 in [0, 1] with C=3.

    Accepts BHWC or HWC, with C in {1, 3, 4}. RGBA inputs drop alpha; grayscale
    is broadcast to RGB. Integer dtypes are scaled from 0-255 into [0, 1].
    """
    if not isinstance(image, torch.Tensor):
        raise TypeError(f"Expected torch.Tensor, got {type(image).__name__}")
    if image.dim() == 3:
        image = image.unsqueeze(0)
    if image.dim() != 4:
        raise ValueError(
            f"Expected 3D or 4D tensor, got {image.dim()}D shape={tuple(image.shape)}"
        )
    c = image.shape[-1]
    if c == 4:
        image = image[..., :3]
    elif c == 1:
        image = image.expand(*image.shape[:-1], 3).contiguous()
    elif c != 3:
        raise ValueError(f"Expected 1, 3, or 4 channels in last dim, got {c}")
    if image.dtype in (torch.uint8, torch.int8, torch.int16, torch.int32, torch.int64):
        image = image.to(dtype=torch.float32) / 255.0
    else:
        image = image.to(dtype=torch.float32)
    return image.clamp(0.0, 1.0)


# --- Color space (torch) -----------------------------------------------------


def srgb_to_linear(t: torch.Tensor) -> torch.Tensor:
    """sRGB [0, 1] → linear-light RGB on the input tensor's device."""
    high = ((t + SRGB_GAMMA_OFFSET) / SRGB_GAMMA_SLOPE).clamp_min(0.0).pow(SRGB_GAMMA_EXPONENT)
    low = t / SRGB_LINEAR_SLOPE
    return torch.where(t > SRGB_LINEAR_THRESHOLD, high, low)


def linear_to_srgb(t: torch.Tensor) -> torch.Tensor:
    """Linear-light RGB [0, 1] → sRGB [0, 1]. Inverse of `srgb_to_linear`."""
    t = t.clamp(0.0, 1.0)
    return torch.where(
        t <= SRGB_LINEAR_THRESHOLD_INV,
        t * SRGB_LINEAR_SLOPE,
        SRGB_GAMMA_SLOPE * t.clamp_min(0.0).pow(1.0 / SRGB_GAMMA_EXPONENT) - SRGB_GAMMA_OFFSET,
    )


# --- YUV (BT.601) ------------------------------------------------------------
# Used by analog-video nodes (VHS, NTSC) where chroma subsampling and head-
# switching artifacts are most natural to model in Y/U/V.

BT601_RGB_TO_YUV = (
    (0.299, 0.587, 0.114),
    (-0.14713, -0.28886, 0.436),
    (0.615, -0.51499, -0.10001),
)
BT601_YUV_TO_RGB = (
    (1.0, 0.0, 1.13983),
    (1.0, -0.39465, -0.58060),
    (1.0, 2.03211, 0.0),
)


def rgb_to_yuv(t: torch.Tensor) -> torch.Tensor:
    """BHWC sRGB-encoded RGB [0,1] → BHWC YUV (Y in [0,1], U,V in [-0.5,0.5])."""
    m = torch.tensor(BT601_RGB_TO_YUV, dtype=t.dtype, device=t.device)
    return torch.einsum("...c,kc->...k", t, m)


def yuv_to_rgb(t: torch.Tensor) -> torch.Tensor:
    """BHWC YUV → BHWC RGB [0,1] (sRGB-encoded; clamped)."""
    m = torch.tensor(BT601_YUV_TO_RGB, dtype=t.dtype, device=t.device)
    return torch.einsum("...c,kc->...k", t, m).clamp(0.0, 1.0)


# ---------------------------------------------------------------------------
# UI preview channel
# ---------------------------------------------------------------------------


def _server_send(event: str, payload: dict) -> None:
    """Push `payload` to the frontend under `event`. No-op if PromptServer
    isn't available (e.g. under pytest without a running ComfyUI)."""
    try:
        from server import PromptServer  # type: ignore
    except Exception:
        return
    try:
        PromptServer.instance.send_sync(event, payload)
    except Exception:
        pass


def _persist_preview_from_disk(abs_path: pathlib.Path) -> dict:
    """Copy an on-disk image into ComfyUI's temp output dir so `/api/view` can
    serve it, and return a payload the frontend can consume.

    Falls back to `{"type": "abs", "filename": str(path)}` if the temp dir
    isn't reachable — the frontend then decides what to do (typically nothing,
    since browsers can't read file:// paths from a served page).
    """
    try:
        import folder_paths  # type: ignore
    except Exception:
        return {"type": "abs", "filename": str(abs_path)}

    src = pathlib.Path(abs_path)
    if not src.is_file():
        return {"type": "abs", "filename": str(abs_path)}

    try:
        temp_dir = pathlib.Path(folder_paths.get_temp_directory())
        temp_dir.mkdir(parents=True, exist_ok=True)
        # Deterministic-ish filename so we don't fill the temp dir with copies.
        stamp = int(time.time() * 1000) & 0xFFFFFF
        stem = src.stem[:40] or "preview"
        ext = src.suffix.lower() or ".png"
        out_name = f"ray_{stem}_{stamp}{ext}"
        out_path = temp_dir / out_name
        with open(src, "rb") as fh_in, open(out_path, "wb") as fh_out:
            fh_out.write(fh_in.read())
        return {
            "filename": out_name,
            "subfolder": "",
            "type": "temp",
            "rand": stamp,
        }
    except OSError:
        return {"type": "abs", "filename": str(abs_path)}


def send_preview(node_id, image_ref) -> None:
    """Dispatch a `ray-preview` event to the frontend for `node_id`.

    `image_ref` is one of:
      • str starting with http(s):// — used as an external URL verbatim.
      • str / pathlib.Path — an absolute on-disk path; copied into ComfyUI's
        temp dir and served via `/api/view`.
      • dict with keys {filename, subfolder, type[, rand]} or {"url": ...} —
        passed through verbatim.
    """
    if node_id is None:
        return

    payload: dict
    if isinstance(image_ref, dict):
        payload = dict(image_ref)
    elif isinstance(image_ref, str) and image_ref.lower().startswith(("http://", "https://")):
        payload = {"url": image_ref}
    elif isinstance(image_ref, (str, os.PathLike)):
        payload = _persist_preview_from_disk(pathlib.Path(image_ref))
    else:
        return

    payload["node_id"] = str(node_id)
    _server_send("ray-preview", payload)
