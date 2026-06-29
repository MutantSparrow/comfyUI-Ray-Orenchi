"""Ray's VFX: Film Stock — analytical film emulation with optional LUT override.

Per-frame:
  1. Normalize input → BHWC float32 [0,1].
  2. sRGB → linear.
  3. Exposure (±stops) in linear — preset + widget + XMP folded.
  4. Per-channel tone curve (S-curve, shadow/midtone/highlight per stock + XMP).
  5. Halation: red-channel blur added back to highlights (CineStill signature).
  6. Saturation pull (slide/cinema/B&W + XMP) in linear.
  7. Grain in linear (gaussian, mass+size per stock + XMP + global multiplier).
  8. Linear → sRGB.
  9. (Optional) `.cube` LUT applied after sRGB (industry convention).
 10. (Optional) XMP-driven post-crop vignette.
 11. Intensity-mix vs untouched input.

Optional inputs:
  • `lut_path`  — `.cube` 3D LUT applied after the analytical curves.
  • `xmp_path`  — Photoshop Camera Raw / Lightroom XMP sidecar. Reads the
                  `crs:*` namespace (Exposure2012, Contrast2012, Highlights2012,
                  Shadows2012, Temperature, Tint, Vibrance, Saturation,
                  GrainAmount/Size, PostCropVignetteAmount/Midpoint, etc.) and
                  folds those develop settings into the pipeline as deltas on
                  top of the chosen film stock.

Tensor convention preserved (BHWC float32 [0,1]). Same input/output shape.
"""

from __future__ import annotations

import io
import math
import pathlib
import re
from dataclasses import dataclass
from typing import Optional, Tuple

import torch
import torch.nn.functional as F

try:
    from ._common import normalize_image, srgb_to_linear, linear_to_srgb
except ImportError:
    from _common import normalize_image, srgb_to_linear, linear_to_srgb


# ---------------------------------------------------------------------------
# Stock parameter table
# ---------------------------------------------------------------------------


@dataclass
class FilmStockParams:
    label: str
    family: str            # 'negative' / 'cinema' / 'bw' / 'slide'
    iso: int
    # Tone curve: target black, midtone (50% input → output), white roll-off
    black_lift: float       # add to shadows in linear
    contrast: float         # S-curve strength (1.0 = linear, >1 punchier)
    highlight_roll: float   # 0..1 — how much highlights compress
    # Per-channel exposure offsets (R, G, B) in linear stops — pushes cast
    cast_rgb: Tuple[float, float, float]
    saturation: float       # >1 = more saturated; 0 = B&W
    # Grain
    grain_mass: float       # luma std multiplier
    grain_chroma: float     # chroma noise relative to luma
    grain_size: float       # blur sigma applied to noise (>0 = chunkier grain)
    # Halation
    halation_amount: float  # 0..1
    halation_sigma: float   # gaussian sigma in pixels
    halation_tint: Tuple[float, float, float]


# Cast values are tiny linear multipliers (e.g. 0.02 = +2% red push).
STOCKS = {
    # --- color negative classics
    "Kodak Portra 400": FilmStockParams(
        "Kodak Portra 400", "negative", 400,
        black_lift=0.012, contrast=0.95, highlight_roll=0.35,
        cast_rgb=(0.02, 0.005, -0.01), saturation=0.92,
        grain_mass=0.012, grain_chroma=0.4, grain_size=0.6,
        halation_amount=0.08, halation_sigma=2.0, halation_tint=(1.0, 0.6, 0.45),
    ),
    "Kodak Ektar 100": FilmStockParams(
        "Kodak Ektar 100", "negative", 100,
        black_lift=0.004, contrast=1.10, highlight_roll=0.25,
        cast_rgb=(0.015, 0.0, -0.005), saturation=1.18,
        grain_mass=0.005, grain_chroma=0.3, grain_size=0.4,
        halation_amount=0.05, halation_sigma=1.5, halation_tint=(1.0, 0.55, 0.4),
    ),
    "Fuji Pro 400H": FilmStockParams(
        "Fuji Pro 400H", "negative", 400,
        black_lift=0.014, contrast=0.92, highlight_roll=0.40,
        cast_rgb=(-0.005, 0.012, 0.018), saturation=0.88,
        grain_mass=0.011, grain_chroma=0.35, grain_size=0.55,
        halation_amount=0.06, halation_sigma=1.8, halation_tint=(1.0, 0.65, 0.5),
    ),
    "Fuji Superia 400": FilmStockParams(
        "Fuji Superia 400", "negative", 400,
        black_lift=0.010, contrast=1.05, highlight_roll=0.30,
        cast_rgb=(0.0, 0.018, 0.012), saturation=1.05,
        grain_mass=0.014, grain_chroma=0.45, grain_size=0.65,
        halation_amount=0.07, halation_sigma=1.8, halation_tint=(1.0, 0.62, 0.48),
    ),
    # --- cinema
    "CineStill 800T": FilmStockParams(
        "CineStill 800T", "cinema", 800,
        black_lift=0.018, contrast=1.0, highlight_roll=0.30,
        cast_rgb=(-0.015, -0.005, 0.025), saturation=0.95,
        grain_mass=0.020, grain_chroma=0.50, grain_size=0.80,
        halation_amount=0.45, halation_sigma=3.5, halation_tint=(1.0, 0.35, 0.20),
    ),
    "CineStill 50D": FilmStockParams(
        "CineStill 50D", "cinema", 50,
        black_lift=0.005, contrast=1.05, highlight_roll=0.25,
        cast_rgb=(0.005, 0.005, 0.005), saturation=1.0,
        grain_mass=0.004, grain_chroma=0.25, grain_size=0.35,
        halation_amount=0.25, halation_sigma=2.5, halation_tint=(1.0, 0.45, 0.30),
    ),
    "Kodak Vision3 500T": FilmStockParams(
        "Kodak Vision3 500T", "cinema", 500,
        black_lift=0.012, contrast=0.95, highlight_roll=0.40,
        cast_rgb=(-0.01, 0.0, 0.018), saturation=0.96,
        grain_mass=0.011, grain_chroma=0.4, grain_size=0.55,
        halation_amount=0.10, halation_sigma=2.2, halation_tint=(1.0, 0.55, 0.40),
    ),
    "Fuji Eterna 500T": FilmStockParams(
        "Fuji Eterna 500T", "cinema", 500,
        black_lift=0.014, contrast=0.85, highlight_roll=0.45,
        cast_rgb=(-0.012, 0.005, 0.022), saturation=0.80,
        grain_mass=0.010, grain_chroma=0.4, grain_size=0.55,
        halation_amount=0.09, halation_sigma=2.0, halation_tint=(1.0, 0.6, 0.5),
    ),
    # --- B&W
    "Kodak Tri-X 400": FilmStockParams(
        "Kodak Tri-X 400", "bw", 400,
        black_lift=0.008, contrast=1.12, highlight_roll=0.20,
        cast_rgb=(0.0, 0.0, 0.0), saturation=0.0,
        grain_mass=0.022, grain_chroma=0.0, grain_size=0.65,
        halation_amount=0.0, halation_sigma=0.0, halation_tint=(1.0, 1.0, 1.0),
    ),
    "Ilford HP5+": FilmStockParams(
        "Ilford HP5+", "bw", 400,
        black_lift=0.012, contrast=1.05, highlight_roll=0.25,
        cast_rgb=(0.0, 0.0, 0.0), saturation=0.0,
        grain_mass=0.020, grain_chroma=0.0, grain_size=0.65,
        halation_amount=0.0, halation_sigma=0.0, halation_tint=(1.0, 1.0, 1.0),
    ),
    "Ilford Delta 3200": FilmStockParams(
        "Ilford Delta 3200", "bw", 3200,
        black_lift=0.020, contrast=1.0, highlight_roll=0.30,
        cast_rgb=(0.0, 0.0, 0.0), saturation=0.0,
        grain_mass=0.045, grain_chroma=0.0, grain_size=0.95,
        halation_amount=0.0, halation_sigma=0.0, halation_tint=(1.0, 1.0, 1.0),
    ),
    "Kodak T-Max 100": FilmStockParams(
        "Kodak T-Max 100", "bw", 100,
        black_lift=0.005, contrast=1.15, highlight_roll=0.18,
        cast_rgb=(0.0, 0.0, 0.0), saturation=0.0,
        grain_mass=0.007, grain_chroma=0.0, grain_size=0.40,
        halation_amount=0.0, halation_sigma=0.0, halation_tint=(1.0, 1.0, 1.0),
    ),
    # --- slide / reversal
    "Fuji Velvia 50": FilmStockParams(
        "Fuji Velvia 50", "slide", 50,
        black_lift=0.002, contrast=1.25, highlight_roll=0.18,
        cast_rgb=(0.01, 0.018, 0.005), saturation=1.40,
        grain_mass=0.003, grain_chroma=0.2, grain_size=0.30,
        halation_amount=0.02, halation_sigma=1.2, halation_tint=(1.0, 0.5, 0.4),
    ),
    "Fuji Provia 100F": FilmStockParams(
        "Fuji Provia 100F", "slide", 100,
        black_lift=0.004, contrast=1.15, highlight_roll=0.22,
        cast_rgb=(0.005, 0.008, 0.005), saturation=1.18,
        grain_mass=0.005, grain_chroma=0.25, grain_size=0.40,
        halation_amount=0.03, halation_sigma=1.3, halation_tint=(1.0, 0.55, 0.4),
    ),
    "Kodak Ektachrome E100": FilmStockParams(
        "Kodak Ektachrome E100", "slide", 100,
        black_lift=0.003, contrast=1.18, highlight_roll=0.20,
        cast_rgb=(0.008, 0.005, -0.005), saturation=1.20,
        grain_mass=0.005, grain_chroma=0.25, grain_size=0.40,
        halation_amount=0.03, halation_sigma=1.3, halation_tint=(1.0, 0.55, 0.4),
    ),
    "Custom": FilmStockParams(
        "Custom", "negative", 200,
        black_lift=0.008, contrast=1.0, highlight_roll=0.30,
        cast_rgb=(0.0, 0.0, 0.0), saturation=1.0,
        grain_mass=0.010, grain_chroma=0.3, grain_size=0.5,
        halation_amount=0.0, halation_sigma=2.0, halation_tint=(1.0, 0.55, 0.40),
    ),
    # `None` is a true bypass — no curves, grain, halation, cast, or saturation.
    # Use it when you want a LUT or XMP to be the *sole* color treatment and
    # not have the analytical stock layer on top.
    "None": FilmStockParams(
        "None", "passthrough", 100,
        black_lift=0.0, contrast=1.0, highlight_roll=0.0,
        cast_rgb=(0.0, 0.0, 0.0), saturation=1.0,
        grain_mass=0.0, grain_chroma=0.0, grain_size=0.0,
        halation_amount=0.0, halation_sigma=0.0, halation_tint=(1.0, 1.0, 1.0),
    ),
}
STOCK_NAMES = list(STOCKS.keys())


# ---------------------------------------------------------------------------
# XMP sidecar parsing (Adobe Camera Raw / Lightroom)
# ---------------------------------------------------------------------------


# Adobe stores raw-develop settings under the `crs:` namespace. Some keys live
# as XML attributes on rdf:Description, others as child elements. Sliders are
# stringified floats; deprecated 2003 versions of Exposure/Contrast/etc. live
# alongside the 2012 versions — prefer the newer one when both present.
_CRS_KEYS = (
    "Exposure2012", "Exposure",
    "Contrast2012", "Contrast",
    "Highlights2012", "Highlights",
    "Shadows2012", "Shadows",
    "Whites2012", "Whites",
    "Blacks2012", "Blacks",
    "Temperature", "Tint",
    "Saturation", "Vibrance",
    "Clarity2012", "Clarity",
    "GrainAmount", "GrainSize",
    "PostCropVignetteAmount", "PostCropVignetteMidpoint",
    "PostCropVignetteFeather", "PostCropVignetteRoundness",
    "PostCropVignetteStyle",
    "WhiteBalance",
)


def parse_xmp_settings(text: str) -> dict:
    """Extract Adobe Camera Raw / Lightroom develop settings from an XMP file.

    Returns a flat {key: float} dict containing every recognized `crs:` slider.
    Missing keys are simply absent. Tolerates both attribute-style
    (`crs:Exposure2012="0.50"`) and element-style (`<crs:Exposure2012>0.50</crs:Exposure2012>`)
    representations — Lightroom mixes them across versions.
    """
    out: dict = {}
    if not isinstance(text, str):
        return out
    for key in _CRS_KEYS:
        # Attribute form: crs:Key="value"
        m = re.search(
            rf'crs:{re.escape(key)}\s*=\s*"([^"]*)"', text
        )
        # Element form: <crs:Key>value</crs:Key>
        if not m:
            m = re.search(
                rf"<crs:{re.escape(key)}>\s*([^<]+?)\s*</crs:{re.escape(key)}>",
                text,
            )
        if not m:
            continue
        raw = m.group(1).strip()
        try:
            out[key] = float(raw)
        except ValueError:
            out[key] = raw  # keep string for non-numeric fields (WhiteBalance)
    return out


def _xmp_pick(settings: dict, *keys, default: float = 0.0) -> float:
    """Return the first numeric value present among `keys` (priority order)."""
    for k in keys:
        v = settings.get(k)
        if isinstance(v, (int, float)):
            return float(v)
    return default


def _kelvin_to_rgb_mul(temp_k: float) -> Tuple[float, float, float]:
    """Approximate per-channel multipliers for a target color temperature.

    `temp_k` is the *target* (camera-side WB) on a typical 2000K..50000K scale.
    Reference is daylight ~6500K (multipliers = 1,1,1). Below 6500 = warmer
    output (boost R); above = cooler (boost B). The math here is a simplified
    Planckian curve fit good to ~5% over 3000..10000K — enough for stylistic
    grading, not colorimetric.
    """
    t = max(1000.0, min(40000.0, float(temp_k))) / 100.0
    # Tanner Helland's piecewise approximation
    if t <= 66.0:
        r = 255.0
        g = 99.4708025861 * math.log(t) - 161.1195681661
    else:
        r = 329.698727446 * ((t - 60.0) ** -0.1332047592)
        g = 288.1221695283 * ((t - 60.0) ** -0.0755148492)
    if t >= 66.0:
        b = 255.0
    elif t <= 19.0:
        b = 0.0
    else:
        b = 138.5177312231 * math.log(t - 10.0) - 305.0447927307
    r = max(0.0, min(255.0, r)) / 255.0
    g = max(0.0, min(255.0, g)) / 255.0
    b = max(0.0, min(255.0, b)) / 255.0
    # Normalize so daylight (~6500K) returns ~(1,1,1)
    daylight = (1.0, 0.97, 0.92)
    return (r / daylight[0], g / daylight[1], b / daylight[2])


# ---------------------------------------------------------------------------
# .cube LUT parser + apply
# ---------------------------------------------------------------------------


_CUBE_SIZE_RE = re.compile(r"^\s*LUT_3D_SIZE\s+(\d+)", re.IGNORECASE | re.MULTILINE)
_CUBE_DOMAIN_MIN_RE = re.compile(
    r"^\s*DOMAIN_MIN\s+([\d\.eE+\-]+)\s+([\d\.eE+\-]+)\s+([\d\.eE+\-]+)",
    re.IGNORECASE | re.MULTILINE,
)
_CUBE_DOMAIN_MAX_RE = re.compile(
    r"^\s*DOMAIN_MAX\s+([\d\.eE+\-]+)\s+([\d\.eE+\-]+)\s+([\d\.eE+\-]+)",
    re.IGNORECASE | re.MULTILINE,
)


def parse_cube_lut(text: str) -> dict:
    """Parse a `.cube` 3D LUT into {'size', 'domain_min', 'domain_max', 'data'(N,N,N,3)}.

    Raises ValueError on malformed input. Comments (`# ...`) and blank lines OK.
    """
    if not isinstance(text, str):
        raise ValueError("LUT input must be text")
    m = _CUBE_SIZE_RE.search(text)
    if not m:
        raise ValueError("LUT_3D_SIZE not found in .cube file")
    n = int(m.group(1))
    if n < 2 or n > 256:
        raise ValueError(f"LUT_3D_SIZE {n} out of range (2..256)")
    dmin = (0.0, 0.0, 0.0)
    dmax = (1.0, 1.0, 1.0)
    mm = _CUBE_DOMAIN_MIN_RE.search(text)
    if mm:
        dmin = tuple(float(x) for x in mm.groups())
    mm = _CUBE_DOMAIN_MAX_RE.search(text)
    if mm:
        dmax = tuple(float(x) for x in mm.groups())

    samples = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line[0].isalpha() or line.startswith("TITLE") or line.startswith('"'):
            continue
        parts = line.split()
        if len(parts) != 3:
            continue
        try:
            samples.append([float(parts[0]), float(parts[1]), float(parts[2])])
        except ValueError:
            continue
    if len(samples) != n * n * n:
        raise ValueError(f"LUT sample count {len(samples)} != {n}^3 = {n**3}")

    data = torch.tensor(samples, dtype=torch.float32).view(n, n, n, 3)
    return {"size": n, "domain_min": dmin, "domain_max": dmax, "data": data}


def apply_cube_lut(img_bhwc: torch.Tensor, lut: dict) -> torch.Tensor:
    """Trilinear-interpolate a 3D LUT over `img_bhwc` (BHWC float32 [0,1]).

    Axis bookkeeping (load-bearing — easy to swap by accident):

    `.cube` spec: data lines iterate with R fastest, then G, then B. Our
    `parse_cube_lut` reads them with `view(n, n, n, 3)` and Python's last-axis-
    fastest order, so the table is indexed as `data[b][g][r][channel]`.

    For F.grid_sample with a 5-D volume `(N, C, D, H, W)`:
      - axis D corresponds to the FIRST table index (B)
      - axis H corresponds to the SECOND table index (G)
      - axis W corresponds to the THIRD table index (R)
    Grid coords are `(x, y, z)` mapped to `(W, H, D)`, i.e. `(R, G, B)`.

    Therefore the grid built from the (R,G,B) input image is `norm` directly,
    NOT `norm[..., [2,1,0]]` — the previous swap inverted the cube and
    produced color shifts proportional to how non-symmetric the LUT was.
    """
    if not isinstance(lut, dict) or "data" not in lut:
        raise ValueError("invalid LUT")
    n = lut["size"]
    dmin = torch.tensor(lut["domain_min"], dtype=img_bhwc.dtype, device=img_bhwc.device)
    dmax = torch.tensor(lut["domain_max"], dtype=img_bhwc.dtype, device=img_bhwc.device)
    cube = lut["data"].to(device=img_bhwc.device, dtype=img_bhwc.dtype)

    norm = ((img_bhwc - dmin) / (dmax - dmin).clamp_min(1e-8)).clamp(0.0, 1.0)
    B = norm.shape[0]

    # cube: (B_dim, G_dim, R_dim, channel) → permute to (channel, D=B, H=G, W=R)
    vol = cube.permute(3, 0, 1, 2).unsqueeze(0)
    vol = vol.expand(B, -1, -1, -1, -1)
    # grid xyz = (R, G, B) — matches W, H, D respectively. No axis swap.
    grid = (norm * 2.0 - 1.0).unsqueeze(1)  # (B, 1, H, W, 3)
    sampled = F.grid_sample(
        vol, grid, mode="bilinear", padding_mode="border", align_corners=True
    )
    sampled = sampled.squeeze(2).permute(0, 2, 3, 1)
    return sampled.clamp(0.0, 1.0)


# ---------------------------------------------------------------------------
# Effect passes
# ---------------------------------------------------------------------------


def _gaussian_kernel_1d(sigma: float, device, dtype) -> torch.Tensor:
    radius = max(1, int(math.ceil(sigma * 3.0)))
    x = torch.arange(-radius, radius + 1, dtype=dtype, device=device)
    k = torch.exp(-(x * x) / (2.0 * sigma * sigma))
    return k / k.sum()


def _gaussian_blur_bchw(x: torch.Tensor, sigma: float) -> torch.Tensor:
    if sigma <= 0.0:
        return x
    k = _gaussian_kernel_1d(sigma, x.device, x.dtype)
    radius = k.numel() // 2
    C = x.shape[1]
    kh = k.view(1, 1, 1, -1).expand(C, 1, 1, -1)
    kv = k.view(1, 1, -1, 1).expand(C, 1, -1, 1)
    pad = (radius, radius, radius, radius)
    x = F.pad(x, pad, mode="reflect")
    x = F.conv2d(x, kh, groups=C)
    x = F.conv2d(x, kv, groups=C)
    return x


def _scurve(x: torch.Tensor, strength: float, highlight_roll: float) -> torch.Tensor:
    """Symmetric S-curve in linear with highlight roll-off.

    `strength` > 1.0 = more contrast. `highlight_roll` ∈ [0,1] compresses
    near-1.0 inputs so highlights don't clip. Both clamps and preserves [0,1].
    """
    x = x.clamp(0.0, 1.0)
    # S-curve via sigmoid recentering
    if abs(strength - 1.0) > 1e-4:
        k = strength * 6.0  # gentle scaling
        s = (1.0 / (1.0 + torch.exp(-k * (x - 0.5))))
        # rescale endpoints so [0,1] maps to [0,1]
        s_min = 1.0 / (1.0 + math.exp(k * 0.5))
        s_max = 1.0 / (1.0 + math.exp(-k * 0.5))
        s = (s - s_min) / (s_max - s_min)
        x = torch.where(torch.tensor(True, device=x.device), s, x)
    if highlight_roll > 0.0:
        # Reinhard-like roll for upper region
        knee = 1.0 - 0.4 * highlight_roll
        above = (x - knee).clamp_min(0.0)
        rolled = above / (1.0 + above)
        x = torch.where(x > knee, knee + rolled, x)
    return x.clamp(0.0, 1.0)


def _saturate(x_lin: torch.Tensor, factor: float) -> torch.Tensor:
    """Saturation pull in linear-light. factor=0 → grayscale, 1 → identity."""
    if abs(factor - 1.0) < 1e-4:
        return x_lin
    luma = (
        0.2126 * x_lin[..., 0:1]
        + 0.7152 * x_lin[..., 1:2]
        + 0.0722 * x_lin[..., 2:3]
    )
    return (luma + (x_lin - luma) * factor).clamp_min(0.0)


def _add_halation(
    x_lin_bchw: torch.Tensor,
    amount: float,
    sigma: float,
    tint: Tuple[float, float, float],
) -> torch.Tensor:
    if amount <= 0.0 or sigma <= 0.0:
        return x_lin_bchw
    # Highlight extraction (above 0.6 linear) → blur → tint → add.
    highlights = (x_lin_bchw - 0.6).clamp_min(0.0)
    glow = _gaussian_blur_bchw(highlights, sigma)
    tint_t = torch.tensor(tint, device=x_lin_bchw.device, dtype=x_lin_bchw.dtype).view(1, 3, 1, 1)
    return (x_lin_bchw + glow * tint_t * amount).clamp(0.0, 8.0)


def _add_grain(
    x_lin: torch.Tensor,
    mass: float,
    chroma_ratio: float,
    size: float,
    generator: Optional[torch.Generator] = None,
) -> torch.Tensor:
    if mass <= 0.0:
        return x_lin
    shape = x_lin.shape
    # Generate in BCHW for easy blur, then permute back.
    bchw = x_lin.permute(0, 3, 1, 2).contiguous()
    luma_noise = torch.randn(
        (bchw.shape[0], 1, bchw.shape[2], bchw.shape[3]),
        device=bchw.device, dtype=bchw.dtype, generator=generator,
    )
    if size > 0.0:
        luma_noise = _gaussian_blur_bchw(luma_noise, sigma=size)
        # Re-normalize to unit std after blur
        std = luma_noise.std() + 1e-8
        luma_noise = luma_noise / std
    grain = luma_noise.expand(-1, 3, -1, -1).clone() * mass
    if chroma_ratio > 0.0:
        chroma_noise = torch.randn(
            bchw.shape, device=bchw.device, dtype=bchw.dtype, generator=generator,
        )
        if size > 0.0:
            chroma_noise = _gaussian_blur_bchw(chroma_noise, sigma=size)
            std = chroma_noise.std() + 1e-8
            chroma_noise = chroma_noise / std
        grain = grain + chroma_noise * mass * chroma_ratio
    grained = (bchw + grain).clamp_min(0.0)
    return grained.permute(0, 2, 3, 1).contiguous()


# ---------------------------------------------------------------------------
# Top-level effect
# ---------------------------------------------------------------------------


def _post_crop_vignette(
    rgb_bhwc: torch.Tensor,
    amount: float,
    midpoint: float,
    feather: float,
) -> torch.Tensor:
    """Lightroom-style post-crop vignette. `amount` ∈ [-100,100] LR units."""
    if abs(amount) < 1e-3:
        return rgb_bhwc
    B, H, W, _ = rgb_bhwc.shape
    # Normalized centered radial coordinates
    ys = torch.linspace(-1.0, 1.0, H, device=rgb_bhwc.device, dtype=rgb_bhwc.dtype).view(1, H, 1)
    xs = torch.linspace(-1.0, 1.0, W, device=rgb_bhwc.device, dtype=rgb_bhwc.dtype).view(1, 1, W)
    radius = torch.sqrt(xs * xs + ys * ys)
    # midpoint LR slider 0..100 → start radius 0.5..1.0
    start = 0.5 + (max(0.0, min(100.0, midpoint)) / 100.0) * 0.5
    # feather LR slider 0..100 → falloff width 0.05..1.0
    width = 0.05 + (max(0.0, min(100.0, feather)) / 100.0) * 0.95
    mask = ((radius - start) / width).clamp(0.0, 1.0)
    factor = 1.0 - mask * (amount / 100.0)
    factor = factor.clamp(0.0, 2.0).unsqueeze(-1)
    return (rgb_bhwc * factor).clamp(0.0, 1.0)


def apply_film_stock(
    image: torch.Tensor,
    stock: FilmStockParams,
    intensity: float,
    grain_amount_mult: float,
    halation_amount_mult: float,
    expose_stops: float,
    lut: Optional[dict] = None,
    xmp_settings: Optional[dict] = None,
    seed: Optional[int] = None,
) -> torch.Tensor:
    image = normalize_image(image)
    original = image
    device, dtype = image.device, image.dtype

    xmp = xmp_settings or {}

    lin = srgb_to_linear(image)

    # 1. Exposure (preset stops + widget stops + XMP Exposure2012 stops)
    xmp_exposure = _xmp_pick(xmp, "Exposure2012", "Exposure")
    total_stops = float(expose_stops) + xmp_exposure
    if abs(total_stops) > 1e-6:
        lin = lin * (2.0 ** total_stops)

    # 2. Per-channel cast (stock cast + XMP WB via Kelvin temperature)
    cast = torch.tensor(stock.cast_rgb, device=device, dtype=dtype).view(1, 1, 1, 3)
    lin = (lin + cast).clamp_min(0.0)
    xmp_temp = xmp.get("Temperature")
    xmp_tint = xmp.get("Tint")
    # XMP Temperature is the *as-shot* target on the scene. We treat the LR
    # default of ~5500 as neutral and apply a normalized push so the slider
    # behaves perceptually like LR's mild WB tilt — NOT a full Planckian
    # remap (which would re-tint a fully-developed image dramatically).
    if isinstance(xmp_temp, (int, float)):
        r_mul, g_mul, b_mul = _kelvin_to_rgb_mul(xmp_temp)
        # Pull each channel ~30% of the way from neutral so the cast is
        # noticeable without overpowering the analytical stock layer.
        blend = 0.30
        r_mul = 1.0 + (r_mul - 1.0) * blend
        g_mul = 1.0 + (g_mul - 1.0) * blend
        b_mul = 1.0 + (b_mul - 1.0) * blend
        wb = torch.tensor([r_mul, g_mul, b_mul], device=device, dtype=dtype).view(1, 1, 1, 3)
        lin = lin * wb
    if isinstance(xmp_tint, (int, float)):
        # Tint slider ranges ~-150..+150. Positive = magenta (boost R+B), neg = green (boost G).
        # Keep deltas small — full slider ≈ ±4% per channel.
        t = max(-150.0, min(150.0, float(xmp_tint))) / 150.0
        tint_mul = torch.tensor(
            [1.0 + t * 0.04, 1.0 - t * 0.04, 1.0 + t * 0.02],
            device=device, dtype=dtype,
        ).view(1, 1, 1, 3)
        lin = lin * tint_mul

    # 3. Black lift (+XMP Shadows/Blacks)
    # LR Blacks slider is -100..+100; we treat it as a *shadow-only* lift so
    # +100 doesn't simply brighten the entire image.
    xmp_shadows = _xmp_pick(xmp, "Shadows2012", "Shadows") / 100.0
    xmp_blacks = _xmp_pick(xmp, "Blacks2012", "Blacks") / 100.0
    lin = lin + stock.black_lift
    if abs(xmp_blacks) > 1e-3:
        # Mask: pixels in linear < 0.1 get the full lift, falling off by 0.25.
        mask = (0.25 - lin).clamp(0.0, 0.25) / 0.25
        lin = lin + mask * (xmp_blacks * 0.03)
    if abs(xmp_shadows) > 1e-3:
        shadow_gamma = max(0.5, 1.0 - xmp_shadows * 0.25)
        # Cubic falloff window so the bend is local to shadow region.
        lift_mask = ((0.35 - lin).clamp(0.0, 0.35) / 0.35) ** 2
        shadow_bent = lin.clamp_min(0.0) ** shadow_gamma
        lin = lin + (shadow_bent - lin) * lift_mask

    # 4. S-curve + highlight roll (preset contrast × XMP contrast multiplier)
    xmp_contrast = _xmp_pick(xmp, "Contrast2012", "Contrast") / 100.0
    # XMP Contrast ±100 → stock contrast scaled by ±20%
    contrast_eff = stock.contrast * (1.0 + xmp_contrast * 0.20)
    xmp_highlights = _xmp_pick(xmp, "Highlights2012", "Highlights") / 100.0
    # Negative LR highlights = recover; positive = brighten. Apply as gentle
    # roll-off delta — full slider ±20% of the roll region.
    roll_eff = max(0.0, min(1.0, stock.highlight_roll + (-xmp_highlights) * 0.20))
    xmp_whites = _xmp_pick(xmp, "Whites2012", "Whites") / 100.0
    if abs(xmp_whites) > 1e-3:
        # Highlight-only gain, same mask shape as the shadow bend.
        white_mask = ((lin - 0.65).clamp(0.0, 0.35) / 0.35) ** 2
        lin = lin + white_mask * (xmp_whites * 0.10)
    lin = _scurve(lin, strength=contrast_eff, highlight_roll=roll_eff)

    # 5. Halation in linear (BCHW)
    lin_bchw = lin.permute(0, 3, 1, 2).contiguous()
    lin_bchw = _add_halation(
        lin_bchw,
        amount=stock.halation_amount * max(0.0, halation_amount_mult),
        sigma=stock.halation_sigma,
        tint=stock.halation_tint,
    )
    lin = lin_bchw.permute(0, 2, 3, 1).contiguous()

    # 6. Saturation (preset × XMP Saturation; XMP Vibrance pulls less-saturated pixels harder)
    # XMP Saturation ±100 → stock saturation scaled by ±50% (was ±100% before,
    # which made +100 produce double-saturated burns on already-saturated stocks).
    xmp_sat = _xmp_pick(xmp, "Saturation") / 100.0
    sat_eff = stock.saturation * (1.0 + xmp_sat * 0.5)
    lin = _saturate(lin, sat_eff)
    xmp_vibrance = _xmp_pick(xmp, "Vibrance") / 100.0
    if abs(xmp_vibrance) > 1e-3:
        # Use Rec.709 luma in linear space; clamp chroma to avoid negative
        # boost factors when channels exceed neutral.
        luma = 0.2126 * lin[..., 0:1] + 0.7152 * lin[..., 1:2] + 0.0722 * lin[..., 2:3]
        chroma = (lin - luma).abs().max(dim=-1, keepdim=True).values.clamp(0.0, 1.0)
        # Half the magnitude of Saturation, weighted toward low-chroma pixels.
        boost = (1.0 - chroma) * xmp_vibrance * 0.5
        lin = (luma + (lin - luma) * (1.0 + boost)).clamp_min(0.0)

    # 7. Grain (preset + XMP GrainAmount slider folds in on top)
    generator = None
    if seed is not None and seed >= 0:
        try:
            generator = torch.Generator(device=device).manual_seed(int(seed))
        except (RuntimeError, TypeError):
            generator = None
    xmp_grain_amount = _xmp_pick(xmp, "GrainAmount") / 100.0
    xmp_grain_size = _xmp_pick(xmp, "GrainSize") / 100.0
    # XMP GrainAmount is 0..100; treat as additive ~0..0.02 of luma std
    grain_mass_eff = stock.grain_mass * max(0.0, grain_amount_mult) + max(0.0, xmp_grain_amount) * 0.02
    grain_size_eff = max(0.0, stock.grain_size + max(0.0, xmp_grain_size) * 0.4)
    lin = _add_grain(
        lin,
        mass=grain_mass_eff,
        chroma_ratio=stock.grain_chroma,
        size=grain_size_eff,
        generator=generator,
    )

    # 8. Back to sRGB
    rgb = linear_to_srgb(lin.clamp(0.0, 4.0))

    # 9. Optional LUT (post-sRGB by convention)
    if lut is not None:
        rgb = apply_cube_lut(rgb, lut)

    # 10. Post-crop vignette (XMP-driven, applied after LUT)
    xmp_vig_amount = _xmp_pick(xmp, "PostCropVignetteAmount")
    xmp_vig_mid = _xmp_pick(xmp, "PostCropVignetteMidpoint", default=50.0)
    xmp_vig_feather = _xmp_pick(xmp, "PostCropVignetteFeather", default=50.0)
    if abs(xmp_vig_amount) > 1e-3:
        rgb = _post_crop_vignette(rgb, xmp_vig_amount, xmp_vig_mid, xmp_vig_feather)

    # 11. Intensity mix
    intensity = max(0.0, min(1.0, float(intensity)))
    if intensity < 1.0:
        rgb = original * (1.0 - intensity) + rgb * intensity

    return rgb.clamp(0.0, 1.0).to(dtype=dtype, device=device)


# ---------------------------------------------------------------------------
# Node class
# ---------------------------------------------------------------------------


_LUT_EXTS = (".cube", ".3dl")
_XMP_EXTS = (".xmp",)
_ALL_EXTS = _LUT_EXTS + _XMP_EXTS

NONE_CHOICE = "(none)"


def _kind_for(ext: str) -> Optional[str]:
    e = ext.lower()
    if e in _LUT_EXTS:
        return "lut"
    if e in _XMP_EXTS:
        return "xmp"
    return None


def list_assets(folder: str) -> list:
    """Enumerate `.cube`/`.3dl`/`.xmp` under `folder` recursively, organized by
    path and type.

    Returns a sorted list of display strings. When the folder contains *both*
    LUT and XMP files, entries are prefixed with `[LUT]` / `[XMP]` so the
    dropdown can group by type. When only one kind exists, the prefix is
    dropped to keep entries short. Subfolder paths are preserved in the entry
    so the user navigates by path (e.g. `[LUT] cinema/portra.cube`).

    The display strings are reversible via `_resolve_chosen` — they encode
    enough to find the file again on the server side.
    """
    out: list = []
    if not folder:
        return out
    base = pathlib.Path(folder).expanduser()
    if not base.is_dir():
        return out

    luts: list = []
    xmps: list = []
    try:
        for p in base.rglob("*"):
            try:
                if not p.is_file():
                    continue
                kind = _kind_for(p.suffix)
                if kind is None:
                    continue
                rel = p.relative_to(base).as_posix()
                (luts if kind == "lut" else xmps).append(rel)
            except OSError:
                continue
    except OSError:
        return out

    luts.sort()
    xmps.sort()
    mixed = bool(luts) and bool(xmps)
    if mixed:
        out.extend(f"[LUT] {r}" for r in luts)
        out.extend(f"[XMP] {r}" for r in xmps)
    else:
        out.extend(luts)
        out.extend(xmps)
    return out


# Back-compat shim — kept so external callers / older tests still work.
def list_files(folder: str, exts: Tuple[str, ...]) -> list:
    """Legacy: list files matching `exts`. New code should call `list_assets`."""
    out: list = []
    if not folder:
        return out
    base = pathlib.Path(folder).expanduser()
    if not base.is_dir():
        return out
    lower = tuple(e.lower() for e in exts)
    try:
        for p in base.rglob("*"):
            try:
                if p.is_file() and p.suffix.lower() in lower:
                    out.append(p.relative_to(base).as_posix())
            except OSError:
                continue
    except OSError:
        return out
    out.sort()
    return out


def _strip_kind_tag(choice: str) -> str:
    """Remove a leading `[LUT] ` / `[XMP] ` tag if present."""
    c = (choice or "").strip()
    if c.startswith("[LUT] "):
        return c[len("[LUT] "):]
    if c.startswith("[XMP] "):
        return c[len("[XMP] "):]
    return c


def _resolve_chosen(folder: str, choice: str) -> Optional[pathlib.Path]:
    """Resolve a (folder, dropdown-choice) pair to a concrete file path.

    Accepts:
      - `(none)` or empty → None
      - A tagged entry like `[LUT] cinema/portra.cube` → strips tag, resolves under folder
      - An untagged relative path → resolves under folder
      - An absolute path the user typed directly
    Returns None when nothing usable matches.
    """
    c = (choice or "").strip()
    if not c or c == NONE_CHOICE:
        return None
    c = _strip_kind_tag(c)
    p = pathlib.Path(c).expanduser()
    if p.is_absolute() and p.is_file():
        return p
    if folder:
        base = pathlib.Path(folder).expanduser()
        candidate = base / c
        if candidate.is_file():
            return candidate
    if p.is_file():
        return p
    return None


class RayFilmStock:
    """Film stock emulation with analytical curves, optional .cube LUT, and
    optional Photoshop / Lightroom XMP develop-setting overlay."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "preset": (STOCK_NAMES, {"default": "Kodak Portra 400"}),
                "intensity": ("FLOAT", {
                    "default": 1.0, "min": 0.0, "max": 1.0, "step": 0.01,
                }),
                "grain_amount": ("FLOAT", {
                    "default": 1.0, "min": 0.0, "max": 4.0, "step": 0.05,
                }),
                "halation_amount": ("FLOAT", {
                    "default": 1.0, "min": 0.0, "max": 4.0, "step": 0.05,
                }),
                "expose_stops": ("FLOAT", {
                    "default": 0.0, "min": -4.0, "max": 4.0, "step": 0.05,
                }),
                "seed": ("INT", {"default": -1, "min": -1, "max": 2**31 - 1}),
            },
            "optional": {
                "assets_folder": ("STRING", {
                    "default": "", "multiline": False,
                    "placeholder": "folder with .cube / .3dl / .xmp (recursed)",
                }),
                # Declared as a COMBO (list of choices) so both LiteGraph and
                # the Vue frontend render a real dropdown. The companion JS
                # repopulates `.options.values` live whenever assets_folder
                # changes. Default list seeded with the (none) sentinel so the
                # widget is interactive even before a folder is set.
                "asset_file": ([NONE_CHOICE], {"default": NONE_CHOICE}),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "process"
    CATEGORY = "Ray/Film📷"

    @classmethod
    def VALIDATE_INPUTS(cls, asset_file=None, **kwargs):
        """Accept any asset_file value — its allowed set is server-discovered
        from `assets_folder` at runtime via the companion JS, so the static
        combo list is just a UI seed, not a source of truth."""
        return True

    def process(
        self,
        image,
        preset,
        intensity,
        grain_amount,
        halation_amount,
        expose_stops,
        seed,
        assets_folder="",
        asset_file=NONE_CHOICE,
    ):
        stock = STOCKS.get(preset)
        if stock is None:
            raise ValueError(f"unknown preset: {preset!r}")

        lut = None
        xmp_settings = None
        chosen_path = _resolve_chosen(assets_folder, asset_file)
        if chosen_path is not None:
            kind = _kind_for(chosen_path.suffix)
            text = chosen_path.read_text(encoding="utf-8", errors="replace")
            if kind == "lut":
                lut = parse_cube_lut(text)
            elif kind == "xmp":
                xmp_settings = parse_xmp_settings(text)
            else:
                raise ValueError(
                    f"asset_file extension not recognized: {chosen_path.suffix!r}"
                )

        out = apply_film_stock(
            image=image,
            stock=stock,
            intensity=intensity,
            grain_amount_mult=grain_amount,
            halation_amount_mult=halation_amount,
            expose_stops=expose_stops,
            lut=lut,
            xmp_settings=xmp_settings,
            seed=int(seed),
        )
        return (out,)
