"""Ray's VFX: Film Stock — analytical film emulation with optional LUT override.

Per-frame:
  1. Normalize input → BHWC float32 [0,1].
  2. sRGB → linear.
  3. Exposure (±stops) in linear.
  4. Per-channel tone curve (S-curve, shadow/midtone/highlight per stock).
  5. Halation: red-channel blur added back to highlights (CineStill signature).
  6. Saturation pull (slide/cinema/B&W) in linear.
  7. Grain in linear (gaussian, mass+size per stock + global multiplier).
  8. Linear → sRGB.
  9. (Optional) `.cube` LUT applied after sRGB (industry convention).
 10. Intensity-mix vs untouched input.

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
}
STOCK_NAMES = list(STOCKS.keys())


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

    Uses torch.nn.functional.grid_sample on the LUT cube treated as a 3D
    volume. Output is clamped to [0,1].
    """
    if not isinstance(lut, dict) or "data" not in lut:
        raise ValueError("invalid LUT")
    n = lut["size"]
    dmin = torch.tensor(lut["domain_min"], dtype=img_bhwc.dtype, device=img_bhwc.device)
    dmax = torch.tensor(lut["domain_max"], dtype=img_bhwc.dtype, device=img_bhwc.device)
    cube = lut["data"].to(device=img_bhwc.device, dtype=img_bhwc.dtype)

    # Normalize input to [0,1] within domain
    norm = ((img_bhwc - dmin) / (dmax - dmin).clamp_min(1e-8)).clamp(0.0, 1.0)
    B, H, W, _ = norm.shape

    # grid_sample's 3D grid axes are (D=R, H=G, W=B) but conventional .cube
    # iteration in spec is "B fastest, then G, then R" — meaning data[r,g,b,:]
    # holds the LUT entry at coords (r,g,b). We treat the cube as volume
    # indexed in [D,H,W] = [R,G,B].
    # grid_sample expects volume shape (N, C, D, H, W) and grid (N, Dout, Hout, Wout, 3)
    # with last-dim = (x,y,z) in [-1, 1] mapping to (W, H, D).
    # Therefore for color (r,g,b), grid xyz = (b, g, r) mapped to [-1,1].
    vol = cube.permute(3, 0, 1, 2).unsqueeze(0)  # (1, 3, N, N, N) — (C,D,H,W)
    vol = vol.expand(B, -1, -1, -1, -1)
    # Build grid of shape (B, 1, H, W, 3) so output is (B, 3, 1, H, W) → squeeze.
    grid = norm[..., [2, 1, 0]] * 2.0 - 1.0  # (B,H,W,3) → xyz=(b,g,r)
    grid = grid.unsqueeze(1)  # (B,1,H,W,3)
    sampled = F.grid_sample(
        vol, grid, mode="bilinear", padding_mode="border", align_corners=True
    )
    # sampled: (B, 3, 1, H, W) → (B, H, W, 3)
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


def apply_film_stock(
    image: torch.Tensor,
    stock: FilmStockParams,
    intensity: float,
    grain_amount_mult: float,
    halation_amount_mult: float,
    expose_stops: float,
    lut: Optional[dict] = None,
    seed: Optional[int] = None,
) -> torch.Tensor:
    image = normalize_image(image)
    original = image
    device, dtype = image.device, image.dtype

    lin = srgb_to_linear(image)

    # 1. Exposure
    if abs(expose_stops) > 1e-6:
        lin = lin * (2.0 ** float(expose_stops))

    # 2. Per-channel cast
    cast = torch.tensor(stock.cast_rgb, device=device, dtype=dtype).view(1, 1, 1, 3)
    lin = (lin + cast).clamp_min(0.0)

    # 3. Black lift
    lin = lin + stock.black_lift

    # 4. S-curve + highlight roll, per channel
    lin = _scurve(lin, strength=stock.contrast, highlight_roll=stock.highlight_roll)

    # 5. Halation in linear (BCHW)
    lin_bchw = lin.permute(0, 3, 1, 2).contiguous()
    lin_bchw = _add_halation(
        lin_bchw,
        amount=stock.halation_amount * max(0.0, halation_amount_mult),
        sigma=stock.halation_sigma,
        tint=stock.halation_tint,
    )
    lin = lin_bchw.permute(0, 2, 3, 1).contiguous()

    # 6. Saturation
    lin = _saturate(lin, stock.saturation)

    # 7. Grain
    generator = None
    if seed is not None and seed >= 0:
        try:
            generator = torch.Generator(device=device).manual_seed(int(seed))
        except (RuntimeError, TypeError):
            generator = None
    lin = _add_grain(
        lin,
        mass=stock.grain_mass * max(0.0, grain_amount_mult),
        chroma_ratio=stock.grain_chroma,
        size=stock.grain_size,
        generator=generator,
    )

    # 8. Back to sRGB
    rgb = linear_to_srgb(lin.clamp(0.0, 4.0))

    # 9. Optional LUT (post-sRGB by convention)
    if lut is not None:
        rgb = apply_cube_lut(rgb, lut)

    # 10. Intensity mix
    intensity = max(0.0, min(1.0, float(intensity)))
    if intensity < 1.0:
        rgb = original * (1.0 - intensity) + rgb * intensity

    return rgb.clamp(0.0, 1.0).to(dtype=dtype, device=device)


# ---------------------------------------------------------------------------
# Node class
# ---------------------------------------------------------------------------


class RayFilmStock:
    """Film stock emulation with analytical curves and optional .cube LUT."""

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
                "lut_path": ("STRING", {
                    "default": "", "multiline": False,
                    "placeholder": "optional .cube LUT path (overrides curves)",
                }),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "process"
    CATEGORY = "Ray/Film📷"

    def process(
        self,
        image,
        preset,
        intensity,
        grain_amount,
        halation_amount,
        expose_stops,
        seed,
        lut_path="",
    ):
        stock = STOCKS.get(preset)
        if stock is None:
            raise ValueError(f"unknown preset: {preset!r}")
        lut = None
        if lut_path and lut_path.strip():
            p = pathlib.Path(lut_path.strip()).expanduser()
            if not p.is_file():
                raise FileNotFoundError(f"LUT not found: {p}")
            lut = parse_cube_lut(p.read_text(encoding="utf-8", errors="replace"))
        out = apply_film_stock(
            image=image,
            stock=stock,
            intensity=intensity,
            grain_amount_mult=grain_amount,
            halation_amount_mult=halation_amount,
            expose_stops=expose_stops,
            lut=lut,
            seed=int(seed),
        )
        return (out,)
