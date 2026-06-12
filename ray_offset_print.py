"""Ray's Offset Print VFX — ComfyUI custom node.

Image-space simulation of CMYK offset / halftone print processes. Per frame:
    1. Normalize input → BHWC float32 [0, 1]; permute to BCHW.
    2. sRGB → linear; pre-process contrast/saturation per preset.
    3. RGB → CMYK plate separation (with optional UCR).
    4. Per plate: misregister shift, halftone screen at preset angle/LPI,
       ink density modulation, optional dot-gain blur.
    5. Composite plates onto paper substrate (tint + grain + texture).
    6. Linear → sRGB.
    7. Optional sepia tone, vignette, posterize, ink bleed.
    8. Master intensity mix vs untouched input.
    9. Permute back to BHWC, clamp, return.

Output tensor preserves input H, W, B exactly.

Tensor convention (ComfyUI): IMAGE = BHWC float32 in [0, 1].
"""

from __future__ import annotations

import math
from typing import Tuple

import torch
import torch.nn.functional as F

try:
    from ._common import normalize_image, srgb_to_linear, linear_to_srgb
except ImportError:
    from _common import normalize_image, srgb_to_linear, linear_to_srgb


# --- Constants ---------------------------------------------------------------

# Standard SWOP screen angles (deg) per CMYK plate.
SWOP_ANGLES = {"C": 15.0, "M": 75.0, "Y": 0.0, "K": 45.0}
DEG = math.pi / 180.0


# --- Preset table ------------------------------------------------------------

# Each preset declares the print process recipe.
# mode: "cmyk_halftone" | "duotone" | "monochrome" | "spot_color" | "posterize"
# screen_lpi_px: halftone dot period in pixels (smaller = finer screen)
# misreg: max plate registration offset in pixels (per plate, signed)
# ink_density: per-plate ink darkness multiplier (CMYK = 4-tuple)
# paper_tint: RGB substrate color (multiplies background)
# paper_grain: per-pixel monochrome noise amount
# paper_texture: low-freq mottled noise amount
# dot_gain: gaussian sigma applied to plates pre-screen (mid-tone fattening)
# ink_bleed: post-composite gaussian sigma simulating wet-ink absorption
# contrast / saturation: pre-screen color grade
# vignette: corner darkening strength
# sepia: 0..1 mix into sepia-toned monochrome
# screen_softness: halftone dot edge softness (higher = softer dot edges)
# ucr: under-color removal 0..1 (how much K is pulled out of CMY)
# duotone_inks: for duotone/monochrome modes, two RGB inks (shadow, highlight)

PRESETS = {
    "old_newspaper": {
        "mode": "duotone",
        "screen_lpi_px": 6.0,
        "misreg": 0.0,
        "ink_density": (0.0, 0.0, 0.0, 0.95),
        "paper_tint": (0.92, 0.86, 0.70),
        "paper_grain": 0.10,
        "paper_texture": 0.20,
        "dot_gain": 0.6,
        "ink_bleed": 0.7,
        "contrast": 1.20,
        "saturation": 0.0,
        "vignette": 0.20,
        "sepia": 0.0,
        "screen_softness": 0.20,
        "ucr": 1.0,
        "duotone_inks": ((0.10, 0.08, 0.06), (0.92, 0.86, 0.70)),
    },
    "modern_newspaper": {
        "mode": "cmyk_halftone",
        "screen_lpi_px": 5.0,
        "misreg": 1.5,
        "ink_density": (0.85, 0.85, 0.80, 0.95),
        "paper_tint": (0.95, 0.93, 0.88),
        "paper_grain": 0.05,
        "paper_texture": 0.10,
        "dot_gain": 0.4,
        "ink_bleed": 0.4,
        "contrast": 1.05,
        "saturation": 0.85,
        "vignette": 0.10,
        "sepia": 0.0,
        "screen_softness": 0.18,
        "ucr": 0.85,
    },
    "comic_book": {
        "mode": "cmyk_halftone",
        "screen_lpi_px": 9.0,
        "misreg": 2.5,
        "ink_density": (1.0, 1.0, 1.0, 1.0),
        "paper_tint": (0.97, 0.94, 0.84),
        "paper_grain": 0.03,
        "paper_texture": 0.08,
        "dot_gain": 0.3,
        "ink_bleed": 0.2,
        "contrast": 1.15,
        "saturation": 1.25,
        "vignette": 0.12,
        "sepia": 0.0,
        "screen_softness": 0.10,
        "ucr": 0.85,
    },
    "chromolithography": {
        "mode": "chromolitho",
        "screen_lpi_px": 0.0,
        "misreg": 1.2,
        "ink_density": (1.0, 1.0, 1.0, 1.0),
        "paper_tint": (0.94, 0.89, 0.76),
        "paper_grain": 0.03,
        "paper_texture": 0.15,
        "dot_gain": 0.0,
        "ink_bleed": 0.4,
        "contrast": 1.10,
        "saturation": 1.30,
        "vignette": 0.20,
        "sepia": 0.0,
        "screen_softness": 0.0,
        "ucr": 1.0,
        # Mineral pigment palette (sRGB). Quantization snaps every pixel to
        # nearest palette swatch; each swatch becomes a "stone" plate.
        "stone_palette_srgb": (
            (0.05, 0.04, 0.05),  # bone black
            (0.55, 0.10, 0.12),  # vermillion red
            (0.78, 0.20, 0.22),  # crimson lake
            (0.95, 0.78, 0.20),  # chrome yellow
            (0.92, 0.62, 0.18),  # ochre
            (0.55, 0.30, 0.10),  # burnt sienna
            (0.18, 0.45, 0.22),  # leaf green
            (0.55, 0.78, 0.42),  # pale green
            (0.10, 0.22, 0.55),  # prussian blue
            (0.30, 0.45, 0.78),  # ultramarine
            (0.92, 0.86, 0.68),  # cream highlight
            (0.50, 0.30, 0.50),  # mauve / aniline
        ),
        "stipple_amount": 0.18,    # crayon/stipple texture inside color regions
        "stipple_freq_px": 1.5,    # high-freq noise scale
        "edge_softness_px": 0.8,   # mask edge softness
    },
    "inkjet": {
        "mode": "inkjet",
        "screen_lpi_px": 0.0,      # NO halftone — droplets sub-pixel
        "misreg": 0.0,
        "ink_density": (1.0, 1.0, 1.0, 1.0),
        "paper_tint": (0.99, 0.99, 0.99),
        "paper_grain": 0.01,
        "paper_texture": 0.015,
        "dot_gain": 0.0,
        "ink_bleed": 0.0,
        "contrast": 1.02,
        "saturation": 0.97,        # consumer ink gamut compression
        "vignette": 0.0,
        "sepia": 0.0,
        "screen_softness": 0.0,
        "ucr": 0.65,
        "channel_noise": 0.012,    # per-channel random fluctuation
        "banding_amount": 0.025,   # horizontal head-pass streaks
        "banding_period_px": 18.0, # head pass band height
        "banding_irregularity": 0.4,  # variance in band amplitude
        "wicking_sigma_px": 0.35,  # ink wicking into paper fiber
        "gamut_compress": 0.10,    # cyan/magenta crosstalk → slight muddy mids
    },
    "pulp_magazine": {
        "mode": "cmyk_halftone",
        "screen_lpi_px": 7.5,
        "misreg": 3.0,
        "ink_density": (0.80, 0.80, 0.75, 0.90),
        "paper_tint": (0.88, 0.80, 0.62),
        "paper_grain": 0.10,
        "paper_texture": 0.22,
        "dot_gain": 0.7,
        "ink_bleed": 0.6,
        "contrast": 0.95,
        "saturation": 0.85,
        "vignette": 0.25,
        "sepia": 0.0,
        "screen_softness": 0.22,
        "ucr": 0.80,
    },
    "risograph": {
        "mode": "spot_color",
        "screen_lpi_px": 8.0,
        "misreg": 4.0,
        "ink_density": (0.90, 0.0, 0.0, 0.95),
        "paper_tint": (0.96, 0.94, 0.88),
        "paper_grain": 0.08,
        "paper_texture": 0.10,
        "dot_gain": 0.5,
        "ink_bleed": 0.3,
        "contrast": 1.15,
        "saturation": 0.0,
        "vignette": 0.12,
        "sepia": 0.0,
        "screen_softness": 0.18,
        "ucr": 1.0,
        "spot_inks": ((0.95, 0.20, 0.30), (0.10, 0.20, 0.55)),
    },
    "silk_screen": {
        "mode": "posterize",
        "screen_lpi_px": 0.0,
        "misreg": 3.5,
        "ink_density": (0.95, 0.95, 0.95, 1.0),
        "paper_tint": (0.97, 0.96, 0.93),
        "paper_grain": 0.04,
        "paper_texture": 0.08,
        "dot_gain": 0.0,
        "ink_bleed": 0.4,
        "contrast": 1.10,
        "saturation": 1.20,
        "vignette": 0.10,
        "sepia": 0.0,
        "screen_softness": 0.0,
        "ucr": 0.90,
        "posterize_levels": 4,
    },
    "xerox": {
        "mode": "monochrome",
        "screen_lpi_px": 4.0,
        "misreg": 0.5,
        "ink_density": (0.0, 0.0, 0.0, 1.0),
        "paper_tint": (0.96, 0.96, 0.96),
        "paper_grain": 0.18,
        "paper_texture": 0.06,
        "dot_gain": 0.5,
        "ink_bleed": 0.3,
        "contrast": 1.45,
        "saturation": 0.0,
        "vignette": 0.05,
        "sepia": 0.0,
        "screen_softness": 0.10,
        "ucr": 1.0,
        "duotone_inks": ((0.05, 0.05, 0.05), (0.96, 0.96, 0.96)),
        "scratch_noise": 0.04,
    },
    "glossy_magazine": {
        "mode": "cmyk_halftone",
        "screen_lpi_px": 3.5,
        "misreg": 0.5,
        "ink_density": (0.95, 0.95, 0.95, 1.0),
        "paper_tint": (0.99, 0.99, 0.99),
        "paper_grain": 0.02,
        "paper_texture": 0.04,
        "dot_gain": 0.25,
        "ink_bleed": 0.15,
        "contrast": 1.10,
        "saturation": 1.10,
        "vignette": 0.05,
        "sepia": 0.0,
        "screen_softness": 0.12,
        "ucr": 0.85,
    },
}

PRESET_NAMES = list(PRESETS.keys())


# --- Helpers ----------------------------------------------------------------


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


def _shift(img: torch.Tensor, dx: float, dy: float) -> torch.Tensor:
    """Sub-pixel shift via grid_sample (zero-padding outside)."""
    if abs(dx) < 1e-4 and abs(dy) < 1e-4:
        return img
    B, C, H, W = img.shape
    yy, xx = torch.meshgrid(
        torch.linspace(-1.0, 1.0, H, device=img.device, dtype=img.dtype),
        torch.linspace(-1.0, 1.0, W, device=img.device, dtype=img.dtype),
        indexing='ij',
    )
    nx = xx - 2.0 * dx / max(1, W - 1)
    ny = yy - 2.0 * dy / max(1, H - 1)
    grid = torch.stack([nx, ny], dim=-1).unsqueeze(0).expand(B, -1, -1, -1)
    return F.grid_sample(img, grid, mode='bilinear', padding_mode='border',
                         align_corners=True)


def _color_grade_srgb(img_srgb: torch.Tensor, contrast: float, saturation: float) -> torch.Tensor:
    """Apply contrast (around 0.5 sRGB midpoint) and saturation in sRGB space.

    Grading in sRGB matches perceptual expectations: contrast 1.2 at sRGB-0.5
    is the perceived midtone; linear-light contrast at 0.5 sits at perceived
    ~0.73 (much brighter than midtone) and biases shadows.
    """
    if contrast != 1.0:
        img_srgb = ((img_srgb - 0.5) * contrast + 0.5).clamp(0.0, 1.0)
    if saturation != 1.0:
        luma = (
            0.2126 * img_srgb[:, 0:1] + 0.7152 * img_srgb[:, 1:2] + 0.0722 * img_srgb[:, 2:3]
        )
        img_srgb = (luma + saturation * (img_srgb - luma)).clamp(0.0, 1.0)
    return img_srgb


def _rgb_to_cmyk(rgb: torch.Tensor, ucr: float) -> torch.Tensor:
    """Convert linear RGB BCHW [0,1] to CMYK BCHW [0,1].

    GCR-style separation:
        C' = 1-R, M' = 1-G, Y' = 1-B
        K  = min(C', M', Y') * ucr
        C  = C' - K, M = M' - K, Y = Y' - K
    ucr=1.0 → maximum black extraction (true black = full K, no CMY).
    ucr=0.0 → no K plate; black built from CMY composite.
    Pure-black input (0,0,0) at ucr=1.0 → K=1, CMY=0 → solid black plate.
    """
    R, G, B = rgb[:, 0:1], rgb[:, 1:2], rgb[:, 2:3]
    Cp = 1.0 - R
    Mp = 1.0 - G
    Yp = 1.0 - B
    K = torch.minimum(torch.minimum(Cp, Mp), Yp) * ucr
    C = (Cp - K).clamp(0.0, 1.0)
    M = (Mp - K).clamp(0.0, 1.0)
    Y = (Yp - K).clamp(0.0, 1.0)
    return torch.cat([C, M, Y, K.clamp(0.0, 1.0)], dim=1)


def _halftone_screen(plate: torch.Tensor, lpi_px: float, angle_rad: float,
                     softness: float) -> torch.Tensor:
    """Convert continuous-tone plate (B,1,H,W) to halftone dot coverage (B,1,H,W).

    Spot function: clustered-dot from cos(2π x'/p) + cos(2π y'/p) where
    (x', y') is the screen-rotated coordinate. Threshold against this
    screen value yields a binary dot pattern; sigmoid softening anti-aliases
    the dot edges to avoid moiré at sub-pixel scales.

    lpi_px <= 0 disables screening (continuous-tone passthrough).
    """
    if lpi_px <= 0.0:
        return plate
    B, _, H, W = plate.shape
    yy, xx = torch.meshgrid(
        torch.arange(H, device=plate.device, dtype=plate.dtype),
        torch.arange(W, device=plate.device, dtype=plate.dtype),
        indexing='ij',
    )
    cs, sn = math.cos(angle_rad), math.sin(angle_rad)
    xr = xx * cs - yy * sn
    yr = xx * sn + yy * cs
    # Screen value 0..1 (cos+cos in [-2,2] → /4 + 0.5 → [0,1]).
    s = (torch.cos(2.0 * math.pi * xr / lpi_px) +
         torch.cos(2.0 * math.pi * yr / lpi_px)) * 0.25 + 0.5
    s = s.view(1, 1, H, W)
    # Sharper threshold = harder dots; sharpness scales inversely with softness.
    sharpness = max(2.0, 16.0 * (1.0 - softness))
    return torch.sigmoid((plate - s) * sharpness)


def _grain(B: int, H: int, W: int, channels: int, amount: float,
           device: torch.device, dtype: torch.dtype) -> torch.Tensor:
    """High-frequency monochrome noise broadcast over channels."""
    if amount <= 0.0:
        return torch.zeros(B, channels, H, W, device=device, dtype=dtype)
    g = (torch.rand(B, 1, H, W, device=device, dtype=dtype) - 0.5) * 2.0
    return (g * amount).expand(B, channels, H, W)


def _texture(B: int, H: int, W: int, amount: float,
             device: torch.device, dtype: torch.dtype) -> torch.Tensor:
    """Low-frequency mottled paper texture (single-channel)."""
    if amount <= 0.0:
        return torch.zeros(B, 1, H, W, device=device, dtype=dtype)
    # Coarse noise: downsample, then upsample with bilinear.
    sh, sw = max(8, H // 32), max(8, W // 32)
    coarse = torch.rand(B, 1, sh, sw, device=device, dtype=dtype) - 0.5
    up = F.interpolate(coarse, size=(H, W), mode='bilinear', align_corners=True)
    return up * amount


def _radial_vignette(h: int, w: int, strength: float,
                     device: torch.device, dtype: torch.dtype) -> torch.Tensor:
    """Smoothstep corner darkening. Returns (1, 1, H, W) multiplier."""
    if strength <= 0.0:
        return torch.ones(1, 1, h, w, device=device, dtype=dtype)
    yy = torch.linspace(-1.0, 1.0, h, device=device, dtype=dtype).view(h, 1)
    xx = torch.linspace(-1.0, 1.0, w, device=device, dtype=dtype).view(1, w)
    r = (xx * xx + yy * yy).sqrt()
    t = ((r - 0.6) / 0.4).clamp(0.0, 1.0)
    return (1.0 - strength * (t * t)).view(1, 1, h, w)


def _sepia(img: torch.Tensor, amount: float) -> torch.Tensor:
    """Mix into a sepia-toned monochrome image. amount 0..1."""
    if amount <= 0.0:
        return img
    luma = (
        0.2126 * img[:, 0:1] + 0.7152 * img[:, 1:2] + 0.0722 * img[:, 2:3]
    )
    sep = torch.cat([
        luma * 1.00,
        luma * 0.85,
        luma * 0.65,
    ], dim=1).clamp(0.0, 1.0)
    return img * (1.0 - amount) + sep * amount


def _posterize(img: torch.Tensor, levels: int) -> torch.Tensor:
    """Reduce per-channel tonal levels."""
    if levels <= 1:
        return img
    return torch.round(img * (levels - 1)) / (levels - 1)


# --- Plate compositing ------------------------------------------------------


# Process-ink transmittances in linear-light (canonical CMYK, eye-matched to
# SWOP-ish primaries). T_ink is the per-channel light fraction passing through
# a fully-inked area. Cyan absorbs red → low R transmit; etc.
# These values are LINEAR-LIGHT (not sRGB-display).
INK_T = {
    "C": (0.10, 0.62, 0.85),  # cyan: blocks red, passes G/B
    "M": (0.85, 0.10, 0.50),  # magenta: blocks green, passes R/B
    "Y": (0.95, 0.92, 0.08),  # yellow: blocks blue, passes R/G
    "K": (0.02, 0.02, 0.02),  # black: blocks all
}


def _composite_cmyk(C: torch.Tensor, M: torch.Tensor, Y: torch.Tensor, K: torch.Tensor,
                    paper_rgb: torch.Tensor, ink_density: tuple,
                    ink_t_override: tuple | None = None) -> torch.Tensor:
    """Composite CMYK plates onto a paper substrate via Beer-Lambert subtractive.

    Each plate has dot coverage 0..1. Ink behaves as a transparent absorber:
    transmitted light = paper × T_C^c × T_M^m × T_Y^y × T_K^k where (c,m,y,k)
    are coverages (scaled by ink_density). On overlap, transmittances multiply
    correctly (C+M overlap → blue, C+Y → green, full CMY → near-black).

    Critically: paper color modulates ink output. Yellow paper × cyan ink →
    green-ish (yellow paper passes R+G, cyan ink passes G+B → only G survives).
    Black paper → no ink visible (no light to absorb). White paper → pure ink.

    ink_t_override: optional 4-tuple of (R,G,B) linear-light transmittances for
    (C, M, Y, K) plates. If None, uses canonical INK_T table.

    paper_rgb: (B, 3, H, W) substrate in linear-light [0, 1].
    """
    cd, md, yd, kd = ink_density
    device, dtype = C.device, C.dtype
    eps = 1e-6
    if ink_t_override is None:
        T_C, T_M, T_Y, T_K = INK_T["C"], INK_T["M"], INK_T["Y"], INK_T["K"]
    else:
        T_C, T_M, T_Y, T_K = ink_t_override
    c = (C * cd).clamp(0.0, 1.0)
    m = (M * md).clamp(0.0, 1.0)
    y = (Y * yd).clamp(0.0, 1.0)
    k = (K * kd).clamp(0.0, 1.0)
    log_TC = torch.log(torch.tensor(T_C, device=device, dtype=dtype).clamp_min(eps)).view(1, 3, 1, 1)
    log_TM = torch.log(torch.tensor(T_M, device=device, dtype=dtype).clamp_min(eps)).view(1, 3, 1, 1)
    log_TY = torch.log(torch.tensor(T_Y, device=device, dtype=dtype).clamp_min(eps)).view(1, 3, 1, 1)
    log_TK = torch.log(torch.tensor(T_K, device=device, dtype=dtype).clamp_min(eps)).view(1, 3, 1, 1)
    log_atten = c * log_TC + m * log_TM + y * log_TY + k * log_TK
    out = paper_rgb * torch.exp(log_atten)
    return out.clamp(0.0, 1.0)


def _palette_quantize(rgb_lin: torch.Tensor, palette_lin: torch.Tensor,
                      edge_softness_px: float) -> torch.Tensor:
    """Snap each pixel to nearest palette color in linear-light. Returns
    (B, N_colors, H, W) one-hot membership, optionally edge-softened.

    palette_lin: (N, 3) tensor of linear-light palette colors.
    """
    B, _, H, W = rgb_lin.shape
    N = palette_lin.shape[0]
    # Distance from each pixel to each palette color: (B, N, H, W).
    px = rgb_lin.unsqueeze(1)                                   # (B,1,3,H,W)
    pal = palette_lin.view(1, N, 3, 1, 1)                       # (1,N,3,1,1)
    diff = px - pal
    dist2 = (diff * diff).sum(dim=2)                            # (B,N,H,W)
    # Hard one-hot.
    idx = dist2.argmin(dim=1, keepdim=True)                     # (B,1,H,W)
    onehot = torch.zeros(B, N, H, W, device=rgb_lin.device, dtype=rgb_lin.dtype)
    onehot.scatter_(1, idx, 1.0)
    # Soften region edges (mimics hand-painted plate boundaries).
    if edge_softness_px > 0.0:
        onehot = _gaussian_blur(onehot, edge_softness_px)
        # Renormalize so columns sum to 1.
        onehot = onehot / onehot.sum(dim=1, keepdim=True).clamp_min(1e-6)
    return onehot


def _composite_duotone(plate: torch.Tensor, paper_rgb: torch.Tensor,
                       ink_lin_rgb: tuple, density: float) -> torch.Tensor:
    """Composite a single ink plate via Beer-Lambert.

    Treats the ink color (in linear-light) as a transmittance the inked region
    converges to as coverage→1. Where coverage=0 paper passes through; where
    coverage=1, output = paper × ink_transmittance / paper if paper>ink, else
    output ≈ ink. Practical implementation: lerp paper → (paper × ink_t) which
    matches print intuition and behaves on any paper color.
    """
    eps = 1e-6
    ink_t = torch.tensor(ink_lin_rgb, device=plate.device, dtype=plate.dtype).view(1, 3, 1, 1).clamp_min(eps)
    cov = (plate * density).clamp(0.0, 1.0)
    # Beer-Lambert: out = paper * ink_t^cov.
    log_atten = cov * torch.log(ink_t)
    return (paper_rgb * torch.exp(log_atten)).clamp(0.0, 1.0)


def _composite_spot(plates: list, paper_rgb: torch.Tensor,
                    inks_lin_rgb: tuple, densities: tuple) -> torch.Tensor:
    """Composite N spot-color plates via Beer-Lambert (multiplicative inks)."""
    eps = 1e-6
    log_atten = torch.zeros_like(paper_rgb)
    for plate, ink, dens in zip(plates, inks_lin_rgb, densities):
        ink_t = torch.tensor(ink, device=plate.device, dtype=plate.dtype).view(1, 3, 1, 1).clamp_min(eps)
        cov = (plate * dens).clamp(0.0, 1.0)
        log_atten = log_atten + cov * torch.log(ink_t)
    return (paper_rgb * torch.exp(log_atten)).clamp(0.0, 1.0)


def _composite_chromolitho(plates: list, paper_rgb: torch.Tensor,
                           inks_lin_rgb: tuple, densities: tuple) -> torch.Tensor:
    """Composite N stone-printed plates via Beer-Lambert.

    Same physics as _composite_spot, but plates here are continuous-tone
    (no halftone screen) — chromolithography used solid ink areas with
    stippled stone work, not regular dot screens.
    """
    return _composite_spot(plates, paper_rgb, inks_lin_rgb, densities)


# --- Print pipeline ---------------------------------------------------------


def _parse_hex_color(s: str) -> Tuple[float, float, float]:
    """Parse #RGB / #RRGGBB into linear-light 0..1 tuple. Falls back to white."""
    if not isinstance(s, str):
        return (1.0, 1.0, 1.0)
    t = s.strip().lstrip("#")
    if len(t) == 3:
        t = "".join(ch * 2 for ch in t)
    if len(t) != 6:
        return (1.0, 1.0, 1.0)
    try:
        r = int(t[0:2], 16) / 255.0
        g = int(t[2:4], 16) / 255.0
        b = int(t[4:6], 16) / 255.0
    except ValueError:
        return (1.0, 1.0, 1.0)
    return (r, g, b)


def _apply_offset_print(
    img_srgb_bchw: torch.Tensor,
    cfg: dict,
    intensity: float,
    ink_strength: float,
    screen_strength: float,
    paper_strength: float,
    scale: float,
    paper_color_lin: Tuple[float, float, float],
    paper_color_mix: float,
) -> torch.Tensor:
    """Apply the full offset-print effect to a BCHW sRGB-space tensor."""
    original = img_srgb_bchw
    B, _, H, W = img_srgb_bchw.shape
    device, dtype = img_srgb_bchw.device, img_srgb_bchw.dtype

    # 1. Pre-screen color grade in sRGB (perceptual midpoint at 0.5).
    graded_srgb = _color_grade_srgb(img_srgb_bchw, float(cfg["contrast"]), float(cfg["saturation"]))

    # 2. Optional posterize in sRGB BEFORE going linear.
    mode = cfg["mode"]
    if "posterize_levels" in cfg and mode in ("posterize",):
        graded_srgb = _posterize(graded_srgb, int(cfg["posterize_levels"]))

    # 3. sRGB → linear for plate separation and Beer-Lambert composite.
    lin = srgb_to_linear(graded_srgb)
    s = max(0.0, float(scale))
    # Scale multiplies all spatial features: dot pitch, misregister, dot-gain,
    # ink-bleed sigmas. scale=0 collapses screen LPI / misreg / blurs to zero
    # (continuous-tone, perfect registration). scale>1 enlarges print artifacts.
    misreg = float(cfg["misreg"]) * s
    softness = float(cfg["screen_softness"])
    base_lpi = float(cfg["screen_lpi_px"])
    eff_lpi = base_lpi * s if (screen_strength > 0.0 and s > 0.0) else 0.0
    eff_softness = max(0.0, min(1.0, softness + (1.0 - screen_strength) * 0.6))
    dot_gain_sigma = float(cfg["dot_gain"]) * s

    # 4. Build paper substrate. Preset paper_tint values are sRGB-eyeball
    # values; convert to linear-light here so the Beer-Lambert composite
    # works in the right space. user paper_color is already linear-light.
    preset_tint_srgb = torch.tensor(cfg["paper_tint"], device=device, dtype=dtype).view(1, 3, 1, 1)
    preset_tint = srgb_to_linear(preset_tint_srgb)
    user_tint = torch.tensor(paper_color_lin, device=device, dtype=dtype).view(1, 3, 1, 1)
    mix = max(0.0, min(1.0, float(paper_color_mix)))
    paper_tint = preset_tint * (1.0 - mix) + user_tint * mix
    paper_grain_amt = float(cfg["paper_grain"]) * float(paper_strength)
    paper_tex_amt   = float(cfg["paper_texture"]) * float(paper_strength)
    paper_rgb = paper_tint.expand(B, 3, H, W).clone()
    if paper_tex_amt > 0.0:
        tex = _texture(B, H, W, paper_tex_amt, device, dtype)
        paper_rgb = (paper_rgb + tex.expand(B, 3, H, W)).clamp(0.0, 1.0)
    if paper_grain_amt > 0.0:
        gr = _grain(B, H, W, 3, paper_grain_amt, device, dtype)
        paper_rgb = (paper_rgb + gr).clamp(0.0, 1.0)
    # Optional foxing (old_book): warm splotches.
    if "foxing" in cfg and float(cfg["foxing"]) > 0.0:
        fox_amt = float(cfg["foxing"]) * float(paper_strength)
        fox = (_texture(B, H, W, 1.0, device, dtype) + 0.5).clamp(0.0, 1.0)
        fox = (fox - 0.55).clamp_min(0.0) * 2.0
        warm_srgb = torch.tensor((0.78, 0.55, 0.30), device=device, dtype=dtype).view(1, 3, 1, 1)
        warm = srgb_to_linear(warm_srgb)
        paper_rgb = (paper_rgb * (1.0 - fox * fox_amt) + warm * fox * fox_amt).clamp(0.0, 1.0)

    # 4. Mode-specific plate generation + compositing.
    if mode == "cmyk_halftone":
        cmyk = _rgb_to_cmyk(lin, float(cfg["ucr"]))
        plates = []
        names = ["C", "M", "Y", "K"]
        for i, name in enumerate(names):
            plate = cmyk[:, i:i+1]
            if dot_gain_sigma > 0.0:
                plate = _gaussian_blur(plate, dot_gain_sigma)
            ang = SWOP_ANGLES[name] * DEG
            dx = math.cos(ang) * misreg * (1.0 if i % 2 == 0 else -1.0)
            dy = math.sin(ang) * misreg * (1.0 if i < 2 else -1.0)
            plate = _shift(plate, dx, dy)
            plate = _halftone_screen(plate, eff_lpi, ang, eff_softness)
            plates.append(plate)
        density = tuple(d * float(ink_strength) for d in cfg["ink_density"])
        out_lin = _composite_cmyk(plates[0], plates[1], plates[2], plates[3],
                                  paper_rgb, density)

    elif mode == "inkjet":
        # Inkjet at viewing scale: photographic-quality output, NOT visible
        # halftone. Sub-pixel droplets at 600+ dpi; user sees a near-identity
        # transform with subtle defects:
        #   • slight ink wicking (gaussian blur, fraction of a pixel)
        #   • per-channel droplet randomness (channel_noise)
        #   • horizontal head-pass banding (irregular sine streaks)
        #   • mild gamut compression (consumer-ink crosstalk on rich colors)
        #   • CMYK separation + UCR for plausible black-density behavior
        #   • subtractive composite onto bright paper
        # No screen, no posterize, no misregister.
        wick = float(cfg.get("wicking_sigma_px", 0.0)) * (1.0 + 0.5 * (s - 1.0))
        wick = max(0.0, wick)
        if wick > 0.0:
            lin_wet = _gaussian_blur(lin, wick)
        else:
            lin_wet = lin
        cmyk = _rgb_to_cmyk(lin_wet, float(cfg["ucr"]))
        # Per-channel noise: emulates random droplet placement variance.
        ch_noise = float(cfg.get("channel_noise", 0.0)) * float(ink_strength)
        if ch_noise > 0.0:
            n = (torch.rand_like(cmyk) - 0.5) * 2.0 * ch_noise
            cmyk = (cmyk + n).clamp(0.0, 1.0)
        density = tuple(d * float(ink_strength) for d in cfg["ink_density"])
        out_lin = _composite_cmyk(cmyk[:, 0:1], cmyk[:, 1:2], cmyk[:, 2:3], cmyk[:, 3:4],
                                  paper_rgb, density)
        # Gamut compression: consumer inks can't reach deep saturated cyan/mag;
        # pull saturated regions slightly toward neutral.
        gc = float(cfg.get("gamut_compress", 0.0))
        if gc > 0.0:
            luma = (0.2126 * out_lin[:, 0:1] + 0.7152 * out_lin[:, 1:2] + 0.0722 * out_lin[:, 2:3])
            out_lin = (out_lin * (1.0 - gc) + luma * gc).clamp(0.0, 1.0)
        # Horizontal head-pass banding: low-amp, low-freq, with irregular envelope.
        band_amt = float(cfg.get("banding_amount", 0.0)) * float(ink_strength)
        if band_amt > 0.0:
            period = max(2.0, float(cfg.get("banding_period_px", 18.0))) * max(1.0, s)
            irreg = float(cfg.get("banding_irregularity", 0.0))
            yy = torch.arange(H, device=device, dtype=dtype).view(1, 1, H, 1)
            band = torch.sin(2.0 * math.pi * yy / period)
            if irreg > 0.0:
                # Irregular per-pass amplitude: random scaling per band period.
                n_bands = max(1, int(H / period) + 2)
                amp = 1.0 - irreg + irreg * torch.rand(n_bands, device=device, dtype=dtype)
                amp = amp.repeat_interleave(int(period) + 1)[:H].view(1, 1, H, 1)
                band = band * amp
            out_lin = (out_lin * (1.0 + band_amt * band * 0.5)).clamp(0.0, 1.0)

    elif mode == "chromolitho":
        # True chromolithography: image quantized to a fixed mineral pigment
        # palette (each color = one limestone plate). Each plate prints as
        # solid color in its region. Plates misregister slightly (1-2 px) at
        # boundaries, producing the hallmark color halos. Inside each color
        # region, light stipple/crayon texture from the lithographic stone.
        palette_srgb = cfg["stone_palette_srgb"]
        palette_lin = torch.tensor(palette_srgb, device=device, dtype=dtype)
        palette_lin = srgb_to_linear(palette_lin)               # (N, 3)
        edge_soft = float(cfg.get("edge_softness_px", 0.8))
        masks = _palette_quantize(lin, palette_lin, edge_soft)  # (B, N, H, W)
        # Per-stone misregister: deterministic angle per plate.
        N = palette_lin.shape[0]
        plates = []
        for i in range(N):
            mask = masks[:, i:i+1]
            # Plate-specific random-but-deterministic offset direction.
            ang = (i * 137.5) * DEG  # golden-angle spread
            dx = math.cos(ang) * misreg
            dy = math.sin(ang) * misreg
            mask = _shift(mask, dx, dy)
            plates.append(mask)
        # Stipple texture: per-pixel high-freq noise modulating ink coverage
        # only inside printed regions (not on bare paper).
        stipple_amt = float(cfg.get("stipple_amount", 0.0)) * float(ink_strength)
        stipple_freq = max(1.0, float(cfg.get("stipple_freq_px", 1.5)))
        if stipple_amt > 0.0:
            sh = max(1, int(H / stipple_freq))
            sw = max(1, int(W / stipple_freq))
            noise_lo = torch.rand(B, 1, sh, sw, device=device, dtype=dtype)
            noise = F.interpolate(noise_lo, size=(H, W), mode='bilinear', align_corners=True)
            stipple_mod = (1.0 - stipple_amt) + stipple_amt * noise
            for i in range(N):
                plates[i] = plates[i] * stipple_mod
        # Composite via Beer-Lambert. Each plate prints its own pigment.
        ink_density_scaled = float(cfg["ink_density"][3]) * float(ink_strength)
        densities = tuple(ink_density_scaled for _ in range(N))
        palette_lin_tup = tuple(tuple(float(c) for c in row) for row in palette_lin.tolist())
        out_lin = _composite_chromolitho(plates, paper_rgb, palette_lin_tup, densities)

    elif mode in ("duotone", "monochrome"):
        # Use luma plate; treat as K-equivalent.
        luma = (
            0.2126 * lin[:, 0:1] + 0.7152 * lin[:, 1:2] + 0.0722 * lin[:, 2:3]
        )
        plate = (1.0 - luma).clamp(0.0, 1.0)  # darkness coverage
        if dot_gain_sigma > 0.0:
            plate = _gaussian_blur(plate, dot_gain_sigma)
        plate = _shift(plate, misreg * 0.5, misreg * 0.5)
        plate = _halftone_screen(plate, eff_lpi, SWOP_ANGLES["K"] * DEG, eff_softness)
        ink_shadow_srgb, _ = cfg.get("duotone_inks", ((0.05, 0.05, 0.05), (1.0, 1.0, 1.0)))
        ink_shadow_lin = tuple(
            float(c) for c in srgb_to_linear(
                torch.tensor(ink_shadow_srgb, dtype=torch.float32)
            ).tolist()
        )
        out_lin = _composite_duotone(plate, paper_rgb, ink_shadow_lin,
                                     float(cfg["ink_density"][3]) * float(ink_strength))

    elif mode == "spot_color":
        # Generate two plates from chroma channels: warm vs cool.
        R, G, Bc = lin[:, 0:1], lin[:, 1:2], lin[:, 2:3]
        warm_plate = ((R - (G + Bc) * 0.5).clamp(0.0, 1.0) +
                      (1.0 - (0.2126 * R + 0.7152 * G + 0.0722 * Bc)) * 0.4).clamp(0.0, 1.0)
        cool_plate = ((Bc - (R + G) * 0.5).clamp(0.0, 1.0) +
                      (1.0 - (0.2126 * R + 0.7152 * G + 0.0722 * Bc)) * 0.3).clamp(0.0, 1.0)
        plates = []
        for idx, p in enumerate((warm_plate, cool_plate)):
            if dot_gain_sigma > 0.0:
                p = _gaussian_blur(p, dot_gain_sigma)
            ang = SWOP_ANGLES["M"] * DEG if idx == 0 else SWOP_ANGLES["C"] * DEG
            dx = math.cos(ang) * misreg * (1.0 if idx == 0 else -1.0)
            dy = math.sin(ang) * misreg * (1.0 if idx == 0 else -1.0)
            p = _shift(p, dx, dy)
            p = _halftone_screen(p, eff_lpi, ang, eff_softness)
            plates.append(p)
        inks_srgb = cfg.get("spot_inks", ((0.95, 0.20, 0.30), (0.10, 0.20, 0.55)))
        inks_lin = tuple(
            tuple(float(c) for c in srgb_to_linear(
                torch.tensor(ink, dtype=torch.float32)
            ).tolist())
            for ink in inks_srgb
        )
        densities = (float(cfg["ink_density"][0]) * float(ink_strength),
                     float(cfg["ink_density"][3]) * float(ink_strength))
        out_lin = _composite_spot(plates, paper_rgb, inks_lin, densities)

    elif mode == "posterize":
        cmyk = _rgb_to_cmyk(lin, float(cfg["ucr"]))
        # Posterized solid plates (no halftone), with misregister between layers.
        plates = []
        names = ["C", "M", "Y", "K"]
        for i, name in enumerate(names):
            plate = cmyk[:, i:i+1]
            ang = SWOP_ANGLES[name] * DEG
            dx = math.cos(ang) * misreg * (1.0 if i % 2 == 0 else -1.0)
            dy = math.sin(ang) * misreg * (1.0 if i < 2 else -1.0)
            plate = _shift(plate, dx, dy)
            plates.append(plate)
        density = tuple(d * float(ink_strength) for d in cfg["ink_density"])
        out_lin = _composite_cmyk(plates[0], plates[1], plates[2], plates[3],
                                  paper_rgb, density)

    else:
        raise ValueError(f"Unknown mode: {mode}")

    # 5. Ink bleed (post-composite blur).
    bleed = float(cfg["ink_bleed"]) * s
    if bleed > 0.0:
        out_lin = _gaussian_blur(out_lin, bleed)

    # 6. Linear → sRGB.
    out_srgb = linear_to_srgb(out_lin)

    # 7. Sepia tone.
    sepia_amt = float(cfg["sepia"])
    if sepia_amt > 0.0:
        out_srgb = _sepia(out_srgb, sepia_amt)

    # 8. Vignette.
    vig = float(cfg["vignette"])
    if vig > 0.0:
        out_srgb = out_srgb * _radial_vignette(H, W, vig, device, dtype)

    # 9. Optional scratch noise (xerox).
    if "scratch_noise" in cfg and float(cfg["scratch_noise"]) > 0.0:
        scr_amt = float(cfg["scratch_noise"]) * float(paper_strength)
        scratches = (torch.rand(B, 1, H, W, device=device, dtype=dtype) > (1.0 - scr_amt)).to(dtype)
        out_srgb = (out_srgb - scratches.expand(B, 3, H, W)).clamp(0.0, 1.0)

    out_srgb = out_srgb.clamp(0.0, 1.0)

    # 10. Master intensity mix vs untouched original.
    if intensity >= 1.0:
        return out_srgb
    if intensity <= 0.0:
        return original
    return original * (1.0 - intensity) + out_srgb * intensity


# --- Node --------------------------------------------------------------------


class RayOffsetPrint:
    """ComfyUI node: image-space offset-print VFX with print-process presets."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "preset": (PRESET_NAMES, {"default": PRESET_NAMES[0]}),
                "intensity": (
                    "FLOAT",
                    {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.01},
                ),
                "ink_strength": (
                    "FLOAT",
                    {"default": 1.0, "min": 0.0, "max": 2.0, "step": 0.05},
                ),
                "screen_strength": (
                    "FLOAT",
                    {"default": 1.0, "min": 0.0, "max": 1.5, "step": 0.05},
                ),
                "paper_strength": (
                    "FLOAT",
                    {"default": 1.0, "min": 0.0, "max": 2.0, "step": 0.05},
                ),
                "scale": (
                    "FLOAT",
                    {"default": 1.0, "min": 0.0, "max": 4.0, "step": 0.05},
                ),
                "paper_color": (
                    "STRING",
                    {"default": "#ffffff"},
                ),
                "paper_color_mix": (
                    "FLOAT",
                    {"default": 0.0, "min": 0.0, "max": 1.0, "step": 0.01},
                ),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("print_image",)
    FUNCTION = "process"
    CATEGORY = "Ray/CRT📺"

    def process(
        self,
        image: torch.Tensor,
        preset: str,
        intensity: float,
        ink_strength: float,
        screen_strength: float,
        paper_strength: float,
        scale: float,
        paper_color: str,
        paper_color_mix: float,
    ) -> Tuple[torch.Tensor]:
        image = normalize_image(image)
        device, dtype = image.device, image.dtype

        if preset not in PRESETS:
            raise ValueError(
                f"Unknown preset '{preset}'. Choose from {PRESET_NAMES}."
            )
        cfg = PRESETS[preset]

        bchw = image.permute(0, 3, 1, 2).contiguous()
        # Parse user paper color from hex sRGB → linear-light tuple for blending
        # with the preset's paper_tint (which is already linear-light).
        rgb_srgb = _parse_hex_color(paper_color)
        rgb_lin = tuple(
            float(c)
            for c in srgb_to_linear(
                torch.tensor(rgb_srgb, dtype=torch.float32)
            ).tolist()
        )
        out_bchw = _apply_offset_print(
            bchw, cfg,
            intensity=float(intensity),
            ink_strength=float(ink_strength),
            screen_strength=float(screen_strength),
            paper_strength=float(paper_strength),
            scale=float(scale),
            paper_color_lin=rgb_lin,
            paper_color_mix=float(paper_color_mix),
        )
        out_bhwc = out_bchw.permute(0, 2, 3, 1).contiguous().clamp(0.0, 1.0)
        return (out_bhwc.to(dtype=dtype, device=device),)
