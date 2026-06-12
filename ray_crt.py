"""Ray's VFX: CRT — ComfyUI custom node.

Image-space CRT display effect. Per frame:
    1. Normalize input → BHWC float32 [0, 1]; permute to BCHW.
    2. sRGB → linear.
    3. Brightness compensation (offsets phosphor-mask darkening).
    4. Halation + bloom (gaussian-blurred bright regions, optional red-orange tint).
    5. Phosphor mask (aperture grille / shadow / slot) multiply.
    6. Scanline curve multiply, with optional beam-width luminance modulation.
    7. NTSC chroma-bleed pass (composite_ntsc preset only).
    8. Linear → sRGB.
    9. Vignette multiply.
   10. If curvature: Lottes barrel warp via grid_sample (out-of-bounds = bezel).
   11. Optional reflection gloss (mattias_stylised).
   12. Master intensity mix vs untouched input.
   13. Permute back to BHWC, clamp, return.

Output tensor preserves input H, W, B exactly.

Tensor convention (ComfyUI): IMAGE = BHWC float32 in [0, 1].
"""

from __future__ import annotations

from typing import Tuple

import torch
import torch.nn.functional as F

try:
    from ._common import normalize_image, srgb_to_linear, linear_to_srgb
except ImportError:
    from _common import normalize_image, srgb_to_linear, linear_to_srgb


# --- Constants ---------------------------------------------------------------

# Lottes barrel-warp coefficients (canonical defaults). Larger → more curvature.
LOTTES_WARP_X = 1.0 / 32.0
LOTTES_WARP_Y = 1.0 / 24.0

# NTSC YIQ encode/decode matrices (FCC standard).
RGB_TO_YIQ = (
    (0.299, 0.587, 0.114),
    (0.596, -0.274, -0.322),
    (0.211, -0.523, 0.312),
)
YIQ_TO_RGB = (
    (1.0, 0.956, 0.621),
    (1.0, -0.272, -0.647),
    (1.0, -1.106, 1.703),
)
NTSC_LOWPASS_TAPS = 7  # horizontal box low-pass on I/Q channels


# --- Preset table ------------------------------------------------------------

# Each preset declares an ingredient mix. SOTA-inspired (libretro slang-shader
# space): trinitron ≈ crt-aperture/easymode, pvm ≈ easymode-halation,
# consumer ≈ crt-consumer, composite ≈ crt-hyllian-ntsc, royale ≈ crt-royale,
# lottes_fast ≈ crt-lottes, mattias ≈ crt-mattias/crt-pi.

PRESETS = {
    "trinitron_aperture": {
        "mask_type": "aperture", "mask_pitch": 3, "mask_depth": 0.40,
        "scan_depth": 0.55, "scan_pitch": 2, "beam_mod": 0.0,
        "halation": 0.15, "halation_sigma": 1.5, "halation_tint": (1.0, 0.60, 0.40),
        "bloom": 0.0, "bloom_sigma": 0.0,
        "ntsc": False,
        "vignette": 0.0, "reflection": 0.0,
        "brightness_compensation": 1.5,
    },
    "pvm_shadow": {
        "mask_type": "shadow", "mask_pitch": 4, "mask_depth": 0.45,
        "scan_depth": 0.50, "scan_pitch": 3, "beam_mod": 0.0,
        "halation": 0.25, "halation_sigma": 2.5, "halation_tint": (1.0, 0.50, 0.30),
        "bloom": 0.15, "bloom_sigma": 4.0,
        "ntsc": False,
        "vignette": 0.20, "reflection": 0.0,
        "brightness_compensation": 1.6,
    },
    "consumer_slot": {
        "mask_type": "slot", "mask_pitch": 4, "mask_depth": 0.50,
        "scan_depth": 0.60, "scan_pitch": 3, "beam_mod": 0.0,
        "halation": 0.30, "halation_sigma": 3.0, "halation_tint": (1.0, 0.55, 0.35),
        "bloom": 0.30, "bloom_sigma": 6.0,
        "ntsc": False,
        "vignette": 0.40, "reflection": 0.0,
        "brightness_compensation": 1.7,
    },
    "composite_ntsc": {
        "mask_type": "slot", "mask_pitch": 4, "mask_depth": 0.45,
        "scan_depth": 0.55, "scan_pitch": 3, "beam_mod": 0.0,
        "halation": 0.30, "halation_sigma": 3.0, "halation_tint": (1.0, 0.55, 0.40),
        "bloom": 0.35, "bloom_sigma": 7.0,
        "ntsc": True,
        "vignette": 0.45, "reflection": 0.0,
        "brightness_compensation": 1.7,
    },
    "arcade_royale": {
        "mask_type": "aperture", "mask_pitch": 3, "mask_depth": 0.50,
        "scan_depth": 0.65, "scan_pitch": 2, "beam_mod": 0.6,
        "halation": 0.40, "halation_sigma": 4.0, "halation_tint": (1.0, 0.45, 0.30),
        "bloom": 0.20, "bloom_sigma": 5.0,
        "ntsc": False,
        "vignette": 0.15, "reflection": 0.0,
        "brightness_compensation": 1.8,
    },
    "lottes_fast": {
        "mask_type": "aperture", "mask_pitch": 3, "mask_depth": 0.35,
        "scan_depth": 0.50, "scan_pitch": 2, "beam_mod": 0.5,
        "halation": 0.10, "halation_sigma": 1.5, "halation_tint": (1.0, 0.60, 0.50),
        "bloom": 0.0, "bloom_sigma": 0.0,
        "ntsc": False,
        "vignette": 0.30, "reflection": 0.0,
        "brightness_compensation": 1.5,
    },
    "mattias_stylised": {
        "mask_type": "slot", "mask_pitch": 5, "mask_depth": 0.40,
        "scan_depth": 0.45, "scan_pitch": 3, "beam_mod": 0.0,
        "halation": 0.50, "halation_sigma": 5.0, "halation_tint": (1.0, 0.55, 0.45),
        "bloom": 0.50, "bloom_sigma": 9.0,
        "ntsc": False,
        "vignette": 0.55, "reflection": 0.40,
        "brightness_compensation": 1.8,
    },
    "royale_kurozumi": {
        "mask_type": "shadow", "mask_pitch": 3, "mask_depth": 0.50,
        "scan_depth": 0.60, "scan_pitch": 2, "beam_mod": 0.0,
        "halation": 0.30, "halation_sigma": 2.5, "halation_tint": (1.0, 0.50, 0.35),
        "bloom": 0.10, "bloom_sigma": 3.0,
        "ntsc": False,
        "vignette": 0.15, "reflection": 0.0,
        "brightness_compensation": 1.7,
    },
    "guest_advanced": {
        "mask_type": "slot", "mask_pitch": 4, "mask_depth": 0.45,
        "scan_depth": 0.55, "scan_pitch": 3, "beam_mod": 0.3,
        "halation": 0.30, "halation_sigma": 3.0, "halation_tint": (1.0, 0.50, 0.35),
        "bloom": 0.20, "bloom_sigma": 5.0,
        "ntsc": True,
        "vignette": 0.25, "reflection": 0.0,
        "brightness_compensation": 1.7,
    },
    "cyberlab_pixels": {
        "mask_type": "aperture", "mask_pitch": 3, "mask_depth": 0.45,
        "scan_depth": 0.70, "scan_pitch": 2, "beam_mod": 0.0,
        "halation": 0.0, "halation_sigma": 0.0, "halation_tint": (1.0, 1.0, 1.0),
        "bloom": 0.0, "bloom_sigma": 0.0,
        "ntsc": False,
        "vignette": 0.0, "reflection": 0.0,
        "brightness_compensation": 1.6,
        "saturation": 1.10,
    },
    "newpixie_framed": {
        "mask_type": "slot", "mask_pitch": 4, "mask_depth": 0.40,
        "scan_depth": 0.40, "scan_pitch": 3, "beam_mod": 0.0,
        "halation": 0.20, "halation_sigma": 2.0, "halation_tint": (1.0, 0.60, 0.45),
        "bloom": 0.20, "bloom_sigma": 4.0,
        "ntsc": False,
        "vignette": 0.70, "reflection": 0.0,
        "brightness_compensation": 1.5,
    },
    "gtu_composite": {
        "mask_type": "aperture", "mask_pitch": 3, "mask_depth": 0.0,
        "scan_depth": 0.40, "scan_pitch": 3, "beam_mod": 0.0,
        "halation": 0.10, "halation_sigma": 1.5, "halation_tint": (1.0, 0.65, 0.50),
        "bloom": 0.0, "bloom_sigma": 0.0,
        "ntsc": True,
        "vignette": 0.20, "reflection": 0.0,
        "brightness_compensation": 1.0,
    },
    "hyllian_glow": {
        "mask_type": "aperture", "mask_pitch": 3, "mask_depth": 0.50,
        "scan_depth": 0.50, "scan_pitch": 2, "beam_mod": 0.0,
        "halation": 0.25, "halation_sigma": 2.5, "halation_tint": (1.0, 0.60, 0.50),
        "bloom": 0.0, "bloom_sigma": 0.0,
        "ntsc": False,
        "vignette": 0.10, "reflection": 0.0,
        "brightness_compensation": 1.6,
    },
    "super_famicom": {
        "mask_type": "slot", "mask_pitch": 4, "mask_depth": 0.45,
        "scan_depth": 0.50, "scan_pitch": 3, "beam_mod": 0.0,
        "halation": 0.20, "halation_sigma": 2.5, "halation_tint": (1.0, 0.55, 0.40),
        "bloom": 0.15, "bloom_sigma": 4.0,
        "ntsc": True,
        "vignette": 0.30, "reflection": 0.0,
        "brightness_compensation": 1.65,
        "tint": (1.04, 1.0, 0.96),
    },
    "megadrive": {
        "mask_type": "slot", "mask_pitch": 4, "mask_depth": 0.45,
        "scan_depth": 0.55, "scan_pitch": 3, "beam_mod": 0.0,
        "halation": 0.25, "halation_sigma": 3.0, "halation_tint": (1.0, 0.55, 0.40),
        "bloom": 0.20, "bloom_sigma": 5.0,
        "ntsc": True,
        "vignette": 0.35, "reflection": 0.0,
        "brightness_compensation": 1.70,
        "tint": (1.03, 1.0, 0.95),
    },
    "ps1": {
        "mask_type": "slot", "mask_pitch": 4, "mask_depth": 0.50,
        "scan_depth": 0.60, "scan_pitch": 3, "beam_mod": 0.0,
        "halation": 0.30, "halation_sigma": 3.5, "halation_tint": (1.0, 0.55, 0.40),
        "bloom": 0.30, "bloom_sigma": 6.0,
        "ntsc": True,
        "vignette": 0.40, "reflection": 0.0,
        "brightness_compensation": 1.70,
        "tint": (1.04, 1.0, 0.95),
    },
    "ps2": {
        "mask_type": "slot", "mask_pitch": 3, "mask_depth": 0.40,
        "scan_depth": 0.50, "scan_pitch": 3, "beam_mod": 0.0,
        "halation": 0.20, "halation_sigma": 2.5, "halation_tint": (1.0, 0.55, 0.40),
        "bloom": 0.15, "bloom_sigma": 4.0,
        "ntsc": False,
        "vignette": 0.25, "reflection": 0.0,
        "brightness_compensation": 1.60,
        "tint": (1.02, 1.0, 0.98),
    },
    "nintendo_ds": {
        "mask_type": "slot", "mask_pitch": 3, "mask_depth": 0.20,
        "scan_depth": 0.0, "scan_pitch": 1, "beam_mod": 0.0,
        "halation": 0.0, "halation_sigma": 0.0, "halation_tint": (1.0, 1.0, 1.0),
        "bloom": 0.05, "bloom_sigma": 1.5,
        "ntsc": False,
        "vignette": 0.0, "reflection": 0.0,
        "brightness_compensation": 1.10,
    },
    "gameboy_advance": {
        "mask_type": "slot", "mask_pitch": 3, "mask_depth": 0.25,
        "scan_depth": 0.0, "scan_pitch": 1, "beam_mod": 0.0,
        "halation": 0.0, "halation_sigma": 0.0, "halation_tint": (1.0, 1.0, 1.0),
        "bloom": 0.0, "bloom_sigma": 0.0,
        "ntsc": False,
        "vignette": 0.05, "reflection": 0.0,
        "brightness_compensation": 1.0,
        "tint": (0.95, 1.0, 0.85),
        "saturation": 0.65,
    },
    "psp": {
        "mask_type": "slot", "mask_pitch": 3, "mask_depth": 0.15,
        "scan_depth": 0.0, "scan_pitch": 1, "beam_mod": 0.0,
        "halation": 0.0, "halation_sigma": 0.0, "halation_tint": (1.0, 1.0, 1.0),
        "bloom": 0.10, "bloom_sigma": 2.0,
        "ntsc": False,
        "vignette": 0.05, "reflection": 0.0,
        "brightness_compensation": 1.10,
        "saturation": 1.15,
    },
}

PRESET_NAMES = list(PRESETS.keys())


# --- Phosphor mask generators -----------------------------------------------


def _aperture_mask(h: int, w: int, pitch: int, depth: float,
                   device: torch.device, dtype: torch.dtype) -> torch.Tensor:
    """Vertical RGB stripe mask. Returns (1, 3, 1, W) — broadcasts over H.

    Each color stripe is `pitch // 3` columns wide, repeating R G B horizontally.
    Mask values: stripe color = 1.0, others = 1.0 - depth.
    """
    pitch = max(3, int(pitch))
    third = max(1, pitch // 3)
    pattern = torch.full((3, pitch), 1.0 - depth, device=device, dtype=dtype)
    pattern[0, 0:third] = 1.0
    pattern[1, third:2 * third] = 1.0
    pattern[2, 2 * third:pitch] = 1.0
    rep = (w + pitch - 1) // pitch
    tiled = pattern.repeat(1, rep)[:, :w]                      # (3, W)
    return tiled.view(1, 3, 1, w).contiguous()


def _slot_mask(h: int, w: int, pitch: int, depth: float,
               device: torch.device, dtype: torch.dtype) -> torch.Tensor:
    """Slot mask: aperture stripes with row-alternating half-pitch x-shift.

    Returns (1, 3, H, W). Even row-blocks of `pitch` rows use the base
    pattern; odd row-blocks use a half-pitch-shifted pattern.
    """
    pitch = max(3, int(pitch))
    third = max(1, pitch // 3)
    pattern = torch.full((3, pitch), 1.0 - depth, device=device, dtype=dtype)
    pattern[0, 0:third] = 1.0
    pattern[1, third:2 * third] = 1.0
    pattern[2, 2 * third:pitch] = 1.0
    pattern_shift = torch.roll(pattern, shifts=pitch // 2, dims=1)
    rep_x = (w + pitch - 1) // pitch
    even = pattern.repeat(1, rep_x)[:, :w]                     # (3, W)
    odd = pattern_shift.repeat(1, rep_x)[:, :w]                # (3, W)
    row_phase = torch.arange(h, device=device) // pitch
    parity = (row_phase % 2).bool()                            # (H,)
    even_b = even.view(3, 1, w).expand(3, h, w)
    odd_b = odd.view(3, 1, w).expand(3, h, w)
    out = torch.where(parity.view(1, h, 1), odd_b, even_b)
    return out.unsqueeze(0).contiguous()                       # (1, 3, H, W)


def _shadow_mask(h: int, w: int, pitch: int, depth: float,
                 device: torch.device, dtype: torch.dtype) -> torch.Tensor:
    """Shadow mask: triad-style. Smaller-cell slot-like pattern.

    Uses pitch//2 horizontally (finer triads) with row-alternation every
    pitch//2 rows, half-pitch x-shift. Returns (1, 3, H, W).
    """
    base_pitch = max(3, int(pitch))
    sub_pitch = max(3, base_pitch // 2 + (base_pitch % 2))    # 2 → 3, 4 → 3, 5 → 4
    return _slot_mask(h, w, sub_pitch, depth, device, dtype)


def _build_mask(mask_type: str, h: int, w: int, pitch: int, depth: float,
                device: torch.device, dtype: torch.dtype) -> torch.Tensor:
    if mask_type == "aperture":
        return _aperture_mask(h, w, pitch, depth, device, dtype).expand(1, 3, h, w)
    if mask_type == "slot":
        return _slot_mask(h, w, pitch, depth, device, dtype)
    if mask_type == "shadow":
        return _shadow_mask(h, w, pitch, depth, device, dtype)
    raise ValueError(f"Unknown mask_type: {mask_type}")


# --- Scanline curve ---------------------------------------------------------


def _scanline_curve(h: int, pitch: int, depth: float,
                    device: torch.device, dtype: torch.dtype) -> torch.Tensor:
    """1D vertical scanline brightness curve. Returns (H,).

    Beam centered between rows: `phase = ((y % pitch) / pitch - 0.5) * 2` is the
    signed normalized distance from beam center; gaussian falloff with sigma=0.5.
    Curve range: peak = 1.0, troughs = 1.0 - depth.
    """
    pitch = max(1, int(pitch))
    y = torch.arange(h, device=device, dtype=dtype)
    phase = ((y % pitch) / pitch - 0.5) * 2.0
    sigma = 0.5
    beam = torch.exp(-(phase * phase) / (2.0 * sigma * sigma))
    beam = (beam - beam.min()) / (beam.max() - beam.min() + 1e-8)  # normalize 0..1
    return 1.0 - depth * (1.0 - beam)


def _apply_scanlines(img_lin: torch.Tensor, curve: torch.Tensor,
                     beam_mod: float) -> torch.Tensor:
    """Multiply scanline curve onto image; optionally widen beam in bright pixels.

    Lottes-style beam-width modulation: bright pixels (high luminance) have
    their scan dip filled in proportional to `beam_mod`, simulating the wider
    beam at higher signal levels.
    """
    H = img_lin.shape[-2]
    curve_b = curve.view(1, 1, H, 1)                           # broadcasts over B,C,W
    if beam_mod <= 0.0:
        return img_lin * curve_b
    luma = (
        0.2126 * img_lin[:, 0:1] + 0.7152 * img_lin[:, 1:2] + 0.0722 * img_lin[:, 2:3]
    ).clamp(0.0, 1.0)
    modulated = curve_b + (1.0 - curve_b) * luma * beam_mod
    return img_lin * modulated.clamp(0.0, 1.0)


# --- Gaussian blur (separable) ----------------------------------------------


def _gaussian_blur(img: torch.Tensor, sigma: float) -> torch.Tensor:
    """Separable gaussian blur on BCHW tensor. No-op when sigma <= 0."""
    if sigma <= 0.0:
        return img
    radius = max(1, int(round(sigma * 3.0)))
    kernel_size = 2 * radius + 1
    x = torch.arange(kernel_size, device=img.device, dtype=img.dtype) - radius
    k = torch.exp(-(x * x) / (2.0 * sigma * sigma))
    k = k / k.sum()
    C = img.shape[1]
    kx = k.view(1, 1, 1, kernel_size).expand(C, 1, 1, kernel_size).contiguous()
    ky = k.view(1, 1, kernel_size, 1).expand(C, 1, kernel_size, 1).contiguous()
    img = F.conv2d(img, kx, padding=(0, radius), groups=C)
    img = F.conv2d(img, ky, padding=(radius, 0), groups=C)
    return img


# --- NTSC chroma bleed -------------------------------------------------------


def _ntsc_bleed(img_lin: torch.Tensor) -> torch.Tensor:
    """Composite-NTSC-style horizontal chroma low-pass (RGB→YIQ→RGB).

    Y channel passes through unchanged; I and Q (chroma) are box-low-passed
    horizontally with a 7-tap kernel. Approximates limited chroma bandwidth
    and color smearing of analog NTSC composite. Done in linear-light to keep
    the pipeline simple — visual effect (chroma blur) is preserved.
    """
    device, dtype = img_lin.device, img_lin.dtype
    rgb_to_yiq = torch.tensor(RGB_TO_YIQ, device=device, dtype=dtype)
    yiq_to_rgb = torch.tensor(YIQ_TO_RGB, device=device, dtype=dtype)
    yiq = torch.einsum('ij,bjhw->bihw', rgb_to_yiq, img_lin)
    taps = NTSC_LOWPASS_TAPS
    k = torch.full((1, 1, 1, taps), 1.0 / taps, device=device, dtype=dtype)
    I = F.conv2d(yiq[:, 1:2], k, padding=(0, taps // 2))
    Q = F.conv2d(yiq[:, 2:3], k, padding=(0, taps // 2))
    yiq = torch.cat([yiq[:, 0:1], I, Q], dim=1)
    rgb = torch.einsum('ij,bjhw->bihw', yiq_to_rgb, yiq)
    return rgb


# --- Vignette / reflection / warp -------------------------------------------


def _radial_vignette(h: int, w: int, strength: float,
                     device: torch.device, dtype: torch.dtype) -> torch.Tensor:
    """Smoothstep corner darkening. Returns (1, 1, H, W) multiplier."""
    if strength <= 0.0:
        return torch.ones(1, 1, h, w, device=device, dtype=dtype)
    yy = torch.linspace(-1.0, 1.0, h, device=device, dtype=dtype).view(h, 1)
    xx = torch.linspace(-1.0, 1.0, w, device=device, dtype=dtype).view(1, w)
    r = (xx * xx + yy * yy).sqrt()
    t = ((r - 0.6) / 0.4).clamp(0.0, 1.0)
    v = 1.0 - strength * (t * t)
    return v.view(1, 1, h, w)


def _reflection_gloss(h: int, w: int, strength: float,
                      device: torch.device, dtype: torch.dtype) -> torch.Tensor:
    """Soft diagonal highlight in the upper-left corner. Returns (1, 1, H, W)."""
    if strength <= 0.0:
        return torch.zeros(1, 1, h, w, device=device, dtype=dtype)
    yy = torch.linspace(0.0, 1.0, h, device=device, dtype=dtype).view(h, 1)
    xx = torch.linspace(0.0, 1.0, w, device=device, dtype=dtype).view(1, w)
    diag = (1.0 - xx) * (1.0 - yy)
    return (strength * diag.pow(2.0)).view(1, 1, h, w)


def _color_grade(img_srgb: torch.Tensor, tint: tuple, saturation: float) -> torch.Tensor:
    """Per-channel tint multiply + saturation scale around per-pixel luma.

    Used by console-flavored presets to push warm/cool/desaturated palette
    without retuning halation. No-op when tint == (1,1,1) and saturation == 1.0.
    """
    if tint != (1.0, 1.0, 1.0):
        t = torch.tensor(tint, device=img_srgb.device, dtype=img_srgb.dtype).view(1, 3, 1, 1)
        img_srgb = img_srgb * t
    if saturation != 1.0:
        luma = (
            0.2126 * img_srgb[:, 0:1] + 0.7152 * img_srgb[:, 1:2] + 0.0722 * img_srgb[:, 2:3]
        )
        img_srgb = luma + saturation * (img_srgb - luma)
    return img_srgb


def _lottes_warp(img: torch.Tensor, warp_x: float, warp_y: float) -> torch.Tensor:
    """Lottes barrel warp via grid_sample. Out-of-bounds → 0 (black bezel).

    img: (B, C, H, W). Output has identical shape.
    """
    B, C, H, W = img.shape
    yy, xx = torch.meshgrid(
        torch.linspace(-1.0, 1.0, H, device=img.device, dtype=img.dtype),
        torch.linspace(-1.0, 1.0, W, device=img.device, dtype=img.dtype),
        indexing='ij',
    )
    nx = xx * (1.0 + (yy * yy) * warp_x)
    ny = yy * (1.0 + (xx * xx) * warp_y)
    grid = torch.stack([nx, ny], dim=-1).unsqueeze(0).expand(B, -1, -1, -1)
    return F.grid_sample(img, grid, mode='bilinear', padding_mode='zeros',
                         align_corners=True)


# --- CRT pipeline ------------------------------------------------------------


def _apply_crt(
    img_srgb_bchw: torch.Tensor,
    cfg: dict,
    curvature: bool,
    intensity: float,
    scanline_strength: float,
    mask_strength: float,
) -> torch.Tensor:
    """Apply the full CRT effect to a BCHW sRGB-space tensor; return BCHW sRGB."""
    original = img_srgb_bchw
    B, C, H, W = img_srgb_bchw.shape
    device, dtype = img_srgb_bchw.device, img_srgb_bchw.dtype

    # Effective per-call strengths.
    eff_mask_depth = float(cfg["mask_depth"]) * float(mask_strength)
    eff_scan_depth = float(cfg["scan_depth"]) * float(scanline_strength)
    # Brightness compensation scales with mask_strength so mask=0 leaves luminance alone.
    eff_brightness = 1.0 + (float(cfg["brightness_compensation"]) - 1.0) * float(mask_strength)

    # 1. sRGB → linear; pre-multiply for mask compensation.
    lin = srgb_to_linear(img_srgb_bchw)
    lin_amp = lin * eff_brightness

    # 2. Halation + bloom from PRE-mask linear image (the "beam").
    halation = float(cfg["halation"])
    halation_sigma = float(cfg["halation_sigma"])
    if halation > 0.0 and halation_sigma > 0.0:
        halo_blur = _gaussian_blur(lin_amp, halation_sigma)
        tint = torch.tensor(cfg["halation_tint"], device=device, dtype=dtype).view(1, 3, 1, 1)
        halo = halo_blur * tint * halation
    else:
        halo = torch.zeros_like(lin_amp)
    bloom = float(cfg["bloom"])
    bloom_sigma = float(cfg["bloom_sigma"])
    if bloom > 0.0 and bloom_sigma > 0.0:
        bloom_glow = _gaussian_blur(lin_amp, bloom_sigma) * bloom
    else:
        bloom_glow = torch.zeros_like(lin_amp)

    # 3. Phosphor mask multiply.
    if eff_mask_depth > 0.0:
        mask = _build_mask(
            cfg["mask_type"], H, W, int(cfg["mask_pitch"]),
            eff_mask_depth, device, dtype,
        )
        masked = lin_amp * mask
    else:
        masked = lin_amp

    # 4. Scanline multiply with optional beam-width modulation.
    if eff_scan_depth > 0.0:
        curve = _scanline_curve(H, int(cfg["scan_pitch"]), eff_scan_depth, device, dtype)
        masked = _apply_scanlines(masked, curve, float(cfg["beam_mod"]))

    # 5. Composite halation/bloom on top.
    out_lin = masked + halo + bloom_glow

    # 6. NTSC chroma bleed (only when preset enables it).
    if cfg.get("ntsc", False):
        out_lin = _ntsc_bleed(out_lin)

    # 7. Linear → sRGB.
    out_srgb = linear_to_srgb(out_lin)

    # 7b. Color grade (tint + saturation) — used by console-flavored presets.
    tint = cfg.get("tint", (1.0, 1.0, 1.0))
    saturation = float(cfg.get("saturation", 1.0))
    out_srgb = _color_grade(out_srgb, tint, saturation)

    # 8. Vignette.
    vignette = float(cfg["vignette"])
    if vignette > 0.0:
        out_srgb = out_srgb * _radial_vignette(H, W, vignette, device, dtype)

    # 9. Curvature (Lottes warp + black bezel from out-of-bounds).
    if curvature:
        out_srgb = _lottes_warp(out_srgb, LOTTES_WARP_X, LOTTES_WARP_Y)

    # 10. Reflection gloss.
    reflection = float(cfg["reflection"])
    if reflection > 0.0:
        out_srgb = out_srgb + _reflection_gloss(H, W, reflection, device, dtype)

    out_srgb = out_srgb.clamp(0.0, 1.0)

    # 11. Master intensity mix vs untouched original.
    if intensity >= 1.0:
        return out_srgb
    if intensity <= 0.0:
        return original
    return original * (1.0 - intensity) + out_srgb * intensity


# --- Node --------------------------------------------------------------------


class RayCRT:
    """ComfyUI node: image-space CRT display effect with SOTA-inspired presets."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "preset": (PRESET_NAMES, {"default": PRESET_NAMES[0]}),
                "curvature": ("BOOLEAN", {"default": True}),
                "intensity": (
                    "FLOAT",
                    {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.01},
                ),
                "scanline_strength": (
                    "FLOAT",
                    {"default": 1.0, "min": 0.0, "max": 2.0, "step": 0.05},
                ),
                "mask_strength": (
                    "FLOAT",
                    {"default": 1.0, "min": 0.0, "max": 2.0, "step": 0.05},
                ),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("crt_image",)
    FUNCTION = "process"
    CATEGORY = "Ray/CRT📺"

    def process(
        self,
        image: torch.Tensor,
        preset: str,
        curvature: bool,
        intensity: float,
        scanline_strength: float,
        mask_strength: float,
    ) -> Tuple[torch.Tensor]:
        image = normalize_image(image)
        device, dtype = image.device, image.dtype

        if preset not in PRESETS:
            raise ValueError(
                f"Unknown preset '{preset}'. Choose from {PRESET_NAMES}."
            )
        cfg = PRESETS[preset]

        # BHWC → BCHW for conv/grid-sample work.
        bchw = image.permute(0, 3, 1, 2).contiguous()
        out_bchw = _apply_crt(
            bchw, cfg,
            curvature=bool(curvature),
            intensity=float(intensity),
            scanline_strength=float(scanline_strength),
            mask_strength=float(mask_strength),
        )
        out_bhwc = out_bchw.permute(0, 2, 3, 1).contiguous().clamp(0.0, 1.0)
        return (out_bhwc.to(dtype=dtype, device=device),)
