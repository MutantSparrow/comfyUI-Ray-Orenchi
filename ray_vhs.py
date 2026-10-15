"""Ray's VFX: VHS / Tape — analog video degradation.

A signal-chain simulation in YUV (BT.601). Every effect is sized relative to the picture rather than in
pixels, so a preset looks the same on a 480-pixel frame and on a 4K one. The stages follow the path a tape
signal takes:

  1. Levels: contrast, lifted blacks, soft-clipped highlights, colour phase error and saturation
  2. Luma bandwidth: VHS luma is soft (about 240 lines); the deck then adds "peaking" halos at edges
  3. Chroma: colour-under bandwidth (a few dozen samples across), a trail to the right and a small delay
  4. Cross-colour: luma detail near the NTSC subcarrier leaking into colour (rainbows, dot crawl)
  5. Time base: smooth per-line wobble, flagging at the top, tracking bands and the head-switch tear
  6. Tape noise: streaky luma noise and colour noise, snow in tracking bands and head-switch lines
  7. Dropouts: short bright streaks with soft tails
  8. YUV -> RGB, then an optional blend back toward the source (effect_fade)

The on-screen display (a status line and a date / time line, in a built-in pixel font) is not laid over the
finished picture. It is burned in before stage 1, so it goes through the same tape: it softens, its colour
bleeds and lags, it wobbles with the picture and the noise and dropouts land on it too. On top of that it
gets what a character generator adds on the way to the screen: a smeared shadow, a little independent line
jitter and a shimmer along its edges.

Output preserves BHWC float32 [0,1] shape. Every random draw comes from a seeded generator, so a fixed
seed always gives the same tape, and changing one control never reshuffles another effect's noise.
"""

from __future__ import annotations

import datetime
import unicodedata
import math
import secrets
from dataclasses import dataclass, replace
from typing import Optional

import numpy as np
import torch
import torch.nn.functional as F

try:
    from ._common import normalize_image, rgb_to_yuv, yuv_to_rgb
except ImportError:
    from _common import normalize_image, rgb_to_yuv, yuv_to_rgb


# ---------------------------------------------------------------------------
# Preset table
# ---------------------------------------------------------------------------


@dataclass
class VHSParams:
    label: str
    chroma_blur: float        # 0..1: how far chroma bandwidth drops (160 down to 22 samples across)
    head_switch: float        # 0..1: the torn band at the bottom of the frame
    tracking_jitter: float    # 0..1: line wobble and tracking bands
    dropout_rate: float       # 0..1: how many dropout streaks
    hiss: float               # 0..1: tape noise
    yc_separation: float      # 0..1: cross-colour rainbows and dot crawl
    # Tape and deck character. Each preset sets these; they are not sliders. The defaults change nothing.
    luma_res: float = 0.0     # horizontal luma resolution, samples across the picture (0 = no limit)
    vres: float = 0.0         # vertical luma resolution, lines (0 = no limit)
    ringing: float = 0.0      # 0..1 deck sharpening, halos around edges
    chroma_shift: float = 0.0  # chroma delay to the right, in VHS samples (320 across the picture)
    chroma_noise: float = 0.0  # 0..1 colour noise
    saturation: float = 1.0
    contrast: float = 1.0
    black_lift: float = 0.0   # raised blacks, 0..0.1
    hue_shift: float = 0.0    # colour phase error, degrees
    flagging: float = 0.0     # 0..1 skew at the top of the frame


# NTSC VHS: luma about 240 TVL (~320 samples across), colour-under chroma about 40 samples across.
# The six slider fields are tuned against that physics; the rest describe the tape and deck.
PRESETS = {
    "Pristine SP": VHSParams(
        "Pristine SP", chroma_blur=0.55, head_switch=0.10, tracking_jitter=0.06,
        dropout_rate=0.03, hiss=0.14, yc_separation=0.22,
        luma_res=330, vres=420, ringing=0.35, chroma_shift=0.8, chroma_noise=0.15,
        saturation=0.95, contrast=0.98, black_lift=0.02, hue_shift=0.0, flagging=0.0,
    ),
    "S-VHS": VHSParams(
        "S-VHS", chroma_blur=0.34, head_switch=0.08, tracking_jitter=0.04,
        dropout_rate=0.02, hiss=0.08, yc_separation=0.04,
        luma_res=470, vres=450, ringing=0.30, chroma_shift=0.4, chroma_noise=0.10,
        saturation=1.0, contrast=1.0, black_lift=0.01, hue_shift=0.0, flagging=0.0,
    ),
    "Worn EP": VHSParams(
        "Worn EP", chroma_blur=0.70, head_switch=0.35, tracking_jitter=0.30,
        dropout_rate=0.22, hiss=0.38, yc_separation=0.40,
        luma_res=250, vres=360, ringing=0.45, chroma_shift=1.4, chroma_noise=0.35,
        saturation=0.88, contrast=0.92, black_lift=0.035, hue_shift=2.5, flagging=0.15,
    ),
    "Gen-3 dub": VHSParams(
        "Gen-3 dub", chroma_blur=0.86, head_switch=0.45, tracking_jitter=0.45,
        dropout_rate=0.40, hiss=0.55, yc_separation=0.55,
        luma_res=205, vres=320, ringing=0.60, chroma_shift=2.0, chroma_noise=0.55,
        saturation=0.78, contrast=0.88, black_lift=0.05, hue_shift=-4.0, flagging=0.30,
    ),
    "VHS-C camcorder": VHSParams(
        "VHS-C camcorder", chroma_blur=0.62, head_switch=0.12, tracking_jitter=0.16,
        dropout_rate=0.10, hiss=0.30, yc_separation=0.28,
        luma_res=275, vres=380, ringing=0.55, chroma_shift=1.0, chroma_noise=0.30,
        saturation=1.10, contrast=1.07, black_lift=0.0, hue_shift=3.0, flagging=0.0,
    ),
    "Hi8": VHSParams(
        "Hi8", chroma_blur=0.40, head_switch=0.08, tracking_jitter=0.08,
        dropout_rate=0.05, hiss=0.16, yc_separation=0.10,
        luma_res=420, vres=440, ringing=0.30, chroma_shift=0.5, chroma_noise=0.20,
        saturation=1.03, contrast=1.0, black_lift=0.01, hue_shift=0.0, flagging=0.0,
    ),
    "Rental tape": VHSParams(
        "Rental tape", chroma_blur=0.66, head_switch=0.30, tracking_jitter=0.42,
        dropout_rate=0.50, hiss=0.36, yc_separation=0.34,
        luma_res=270, vres=370, ringing=0.42, chroma_shift=1.2, chroma_noise=0.30,
        saturation=0.90, contrast=0.95, black_lift=0.03, hue_shift=-2.0, flagging=0.28,
    ),
    "Off-air LP": VHSParams(
        "Off-air LP", chroma_blur=0.74, head_switch=0.22, tracking_jitter=0.22,
        dropout_rate=0.14, hiss=0.34, yc_separation=0.62,
        luma_res=265, vres=370, ringing=0.50, chroma_shift=1.5, chroma_noise=0.40,
        saturation=0.92, contrast=1.0, black_lift=0.025, hue_shift=4.0, flagging=0.08,
    ),
    "Chewed tape": VHSParams(
        "Chewed tape", chroma_blur=0.82, head_switch=0.78, tracking_jitter=0.85,
        dropout_rate=0.85, hiss=0.70, yc_separation=0.50,
        luma_res=225, vres=330, ringing=0.50, chroma_shift=2.2, chroma_noise=0.60,
        saturation=0.80, contrast=0.90, black_lift=0.045, hue_shift=-5.0, flagging=0.70,
    ),
    "Custom": VHSParams(
        "Custom", chroma_blur=0.5, head_switch=0.3, tracking_jitter=0.2,
        dropout_rate=0.1, hiss=0.15, yc_separation=0.3,
        luma_res=300, vres=400, ringing=0.30, chroma_shift=1.0, chroma_noise=0.20,
        saturation=0.95, contrast=0.98, black_lift=0.02, hue_shift=0.0, flagging=0.0,
    ),
}
PRESET_NAMES = list(PRESETS.keys())

OSD_STATUS = ["Off", "▶ PLAY", "● REC", "❚❚ PAUSE", "■ STOP"]
OSD_STAMP = ["Off", "Date", "Time", "Date+Time"]
OSD_CORNERS = ["TL", "TR", "BL", "BR"]
# The phosphor colours of VCR and camcorder character generators.
OSD_COLORS = {
    "White": (0.96, 0.96, 0.92),
    "Yellow": (1.00, 0.86, 0.04),
    "Green": (0.18, 1.00, 0.32),
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _stage_generator(seed: int, stage: int) -> torch.Generator:
    """A CPU generator private to one effect, so toggling a control never reshuffles another's noise."""
    gen = torch.Generator(device="cpu")
    gen.manual_seed((int(seed) * 1000003 + stage * 7919) % (2**63 - 1))
    return gen


def _rand(gen: torch.Generator) -> float:
    return float(torch.rand(1, generator=gen).item())


def _kernel(sigma: float, device, dtype) -> torch.Tensor:
    radius = max(1, int(math.ceil(sigma * 3.0)))
    x = torch.arange(-radius, radius + 1, dtype=dtype, device=device)
    k = torch.exp(-(x * x) / (2.0 * sigma * sigma))
    return k / k.sum()


def _blur(x: torch.Tensor, sx: float = 0.0, sy: float = 0.0) -> torch.Tensor:
    """Separable gaussian blur on a BCHW tensor; sigmas are in pixels."""
    C = x.shape[1]
    if sx > 0.05:
        k = _kernel(sx, x.device, x.dtype)
        r = k.numel() // 2
        x = F.conv2d(F.pad(x, (r, r, 0, 0), mode="replicate"), k.view(1, 1, 1, -1).expand(C, 1, 1, -1), groups=C)
    if sy > 0.05:
        k = _kernel(sy, x.device, x.dtype)
        r = k.numel() // 2
        x = F.conv2d(F.pad(x, (0, 0, r, r), mode="replicate"), k.view(1, 1, -1, 1).expand(C, 1, -1, 1), groups=C)
    return x


def _trail(x: torch.Tensor, tau: float) -> torch.Tensor:
    """One-sided exponential smear to the right: colour that lags behind the picture it belongs to."""
    if tau <= 0.05:
        return x
    C = x.shape[1]
    r = max(2, int(math.ceil(tau * 5.0)))
    k = torch.exp(-torch.arange(0, r + 1, dtype=x.dtype, device=x.device) / tau)
    k = (k / k.sum()).flip(0)
    return F.conv2d(F.pad(x, (r, 0, 0, 0), mode="replicate"), k.view(1, 1, 1, -1).expand(C, 1, 1, -1), groups=C)


def _shift_h(x: torch.Tensor, dx: float) -> torch.Tensor:
    """Shift right by a fractional number of pixels (replicating the edge)."""
    if abs(dx) < 0.02:
        return x
    W = x.shape[-1]

    def step(s: int) -> torch.Tensor:
        if s == 0:
            return x
        if s > 0:
            return F.pad(x, (s, 0, 0, 0), mode="replicate")[..., :W]
        return F.pad(x, (0, -s, 0, 0), mode="replicate")[..., -s:]

    n = math.floor(dx)
    f = dx - n
    return step(n) * (1.0 - f) + step(n + 1) * f


def _displace_rows(x: torch.Tensor, offsets: torch.Tensor) -> torch.Tensor:
    """Move each row of a BCHW tensor sideways by `offsets` (B, H) pixels, positive = right, sub-pixel."""
    B, _, H, W = x.shape
    xs = torch.linspace(-1.0, 1.0, W, device=x.device, dtype=x.dtype).view(1, 1, W)
    ys = torch.linspace(-1.0, 1.0, H, device=x.device, dtype=x.dtype).view(1, H, 1).expand(B, H, W)
    gx = xs - 2.0 * offsets.to(x.device, x.dtype).view(B, H, 1) / max(W - 1, 1)
    grid = torch.stack([gx.expand(B, H, W), ys], dim=-1)
    return F.grid_sample(x, grid, mode="bilinear", padding_mode="border", align_corners=True)


def _smooth1d(n: int, sigma: float, gen: torch.Generator) -> torch.Tensor:
    """Unit-variance noise along a line of `n` samples, correlated over about `sigma` samples."""
    noise = torch.randn(n, generator=gen)
    if sigma > 0.05 and n > 1:
        k = _kernel(sigma, noise.device, noise.dtype)
        r = k.numel() // 2
        noise = F.conv1d(F.pad(noise.view(1, 1, -1), (r, r), mode="replicate"), k.view(1, 1, -1)).view(-1)
        noise = noise / float(noise.std(unbiased=False).clamp_min(1e-6))
    return noise


def _streaky_noise(shape, sigma_x: float, sigma_y: float, gen: torch.Generator) -> torch.Tensor:
    """Noise that is soft along the scanline and varies in strength from line to line: tape noise."""
    B, C, H, W = shape
    noise = _blur(torch.randn(shape, generator=gen), sigma_x, sigma_y)
    noise = noise / noise.std(unbiased=False).clamp_min(1e-6)
    gain = torch.stack([(1.0 + 0.35 * _smooth1d(H, 0.8, gen)).clamp(0.35, 1.8) for _ in range(B)])
    return noise * gain.view(B, 1, H, 1)


# ---------------------------------------------------------------------------
# Signal-chain stages
# ---------------------------------------------------------------------------


def _levels(y: torch.Tensor, uv: torch.Tensor, p: VHSParams):
    """Contrast, lifted blacks and soft-clipped highlights on luma; hue error and saturation on colour."""
    if p.contrast != 1.0 or p.black_lift != 0.0:
        y = (y - 0.5) * p.contrast + 0.5
        y = p.black_lift + y * (1.0 - p.black_lift)
        knee = 0.82
        y = torch.where(y > knee, knee + (1.0 - knee) * torch.tanh((y - knee) / (1.0 - knee)), y)
    if p.hue_shift:
        a = math.radians(p.hue_shift)
        c, s = math.cos(a), math.sin(a)
        uv = torch.cat([uv[:, 0:1] * c - uv[:, 1:2] * s, uv[:, 0:1] * s + uv[:, 1:2] * c], dim=1)
    return y, uv * p.saturation


def _luma_bandwidth(y: torch.Tensor, p: VHSParams) -> torch.Tensor:
    """Soften luma to the tape's resolution, then add the deck's peaking halos."""
    H, W = y.shape[-2:]
    sx = max(0.0, 0.5 * (W / p.luma_res - 1.0)) if p.luma_res > 0 else 0.0
    sy = max(0.0, 0.5 * (H / p.vres - 1.0)) if p.vres > 0 else 0.0
    y = _blur(y, sx, sy)
    if p.ringing > 0:
        radius = max(0.8, 1.2 * W / 320.0)
        y = y + p.ringing * 1.1 * (y - _blur(y, radius, 0.0))
    return y


def _chroma_bandwidth(uv: torch.Tensor, severity: float, shift: float) -> torch.Tensor:
    """Colour-under chroma: only a few dozen samples across, smeared and lagging to the right."""
    H, W = uv.shape[-2:]
    u, v = W / 320.0, H / 480.0
    if severity > 0:
        samples = 160.0 * (22.0 / 160.0) ** severity
        sx = max(0.0, 0.65 * (W / samples - 1.0))
        sy = (0.35 + 1.1 * severity) * v * 0.9
        smooth = _blur(uv, sx, sy)
        uv = smooth * (1.0 - 0.35 * severity) + _trail(smooth, max(0.0, 0.6 * sx)) * (0.35 * severity)
    return _shift_h(uv, shift * u)


def _cross_colour(y: torch.Tensor, uv: torch.Tensor, strength: float) -> torch.Tensor:
    """Luma detail near the colour subcarrier bleeding into chroma, with NTSC's line-to-line phase flip."""
    if strength <= 0:
        return uv
    H, W = y.shape[-2:]
    period = max(2.0, W / 227.5)
    detail = y - _blur(y, period * 0.42, 0.0)
    xs = torch.arange(W, device=y.device, dtype=y.dtype).view(1, 1, 1, W)
    ys = torch.arange(H, device=y.device, dtype=y.dtype).view(1, 1, H, 1)
    phase = 2.0 * math.pi * xs / period + math.pi * ys
    bleed = detail * 0.55 * strength
    return uv + torch.cat([bleed * torch.cos(phase), bleed * torch.sin(phase)], dim=1)


def _time_base(H: int, W: int, jitter: float, flagging: float, gen: torch.Generator):
    """Per-line sideways offsets in pixels (H,), plus a 0..1 mask of tracking bands (H,).

    Real time-base error is smooth: neighbouring lines move together, whole stretches of picture sway, and
    the top of the frame bends when the tape tension is off. It is not a handful of random torn lines."""
    u = W / 320.0
    offsets = torch.zeros(H)
    bands = torch.zeros(H)
    ys = torch.arange(H, dtype=torch.float32)
    if jitter > 0:
        offsets += _smooth1d(H, 0.7 + 0.5 * (H / 480.0) ** 0.5, gen) * (0.04 + 1.5 * jitter) * u
        period = (30.0 + 140.0 * _rand(gen)) * (H / 480.0)
        offsets += torch.sin(2 * math.pi * ys / period + 6.28 * _rand(gen)) * (0.06 + 2.6 * jitter) * u * 0.55
        expected = 1.8 * jitter ** 1.2
        count = min(3, int(expected) + (1 if _rand(gen) < expected - int(expected) else 0))
        for _ in range(count):
            centre = (0.1 + 0.82 * _rand(gen)) * H
            half = H * (0.02 + 0.07 * _rand(gen)) * (0.7 + 0.6 * jitter)
            window = (0.5 * (1.0 + torch.cos(math.pi * ((ys - centre) / half).clamp(-1, 1)))).clamp(0, 1)
            wavelength = half * (0.8 + 0.8 * _rand(gen))
            swing = (0.5 + 0.7 * torch.sin(2 * math.pi * (ys - centre) / wavelength + 6.28 * _rand(gen)))
            sign = 1.0 if _rand(gen) < 0.5 else -1.0
            offsets += sign * (3.0 + 9.0 * jitter) * u * window * swing
            bands = torch.maximum(bands, window)
    if flagging > 0:
        sign = 1.0 if _rand(gen) < 0.5 else -1.0
        offsets += sign * flagging * 7.0 * u * torch.exp(-ys / (0.05 * H)) * (0.7 + 0.3 * math.cos(6.28 * _rand(gen)))
    return offsets, bands


def _head_switch(H: int, W: int, severity: float, gen: torch.Generator):
    """Offsets (H,) and a 0..1 noise mask (H,) for the torn lines at the bottom of the frame.

    The video heads swap near the bottom of the picture, and those lines are skewed progressively sideways
    and garbled with noise, always the same way within a frame."""
    offsets = torch.zeros(H)
    noise = torch.zeros(H)
    if severity <= 0:
        return offsets, noise
    u = W / 320.0
    band = max(3, int(round(H * (0.016 + 0.040 * severity))))
    t = ((torch.arange(H, dtype=torch.float32) - (H - band)) / band).clamp(0.0, 1.0)
    sign = 1.0 if _rand(gen) < 0.5 else -1.0
    offsets = sign * severity * 30.0 * u * t ** 1.7 * (1.0 + 0.10 * _smooth1d(H, 1.0, gen))
    ramp = ((t - 0.35) / 0.65).clamp(0.0, 1.0)
    noise = ramp * ramp * (3.0 - 2.0 * ramp) * min(1.0, 0.4 + severity)
    return offsets, noise


def _dropout_layer(H: int, W: int, rate: float, last_row: int, gen: torch.Generator):
    """(mask, level): where dropout streaks land (0..1) and the luma they drive the line to."""
    mask = torch.zeros(H, W)
    level = torch.ones(H, W)
    if rate <= 0 or last_row < 2:
        return mask, level
    u, v = W / 320.0, H / 480.0
    expected = rate * 26.0 * v
    count = int(expected) + (1 if _rand(gen) < expected - int(expected) else 0)
    xs = torch.arange(W, dtype=torch.float32)
    for _ in range(count):
        row = int(_rand(gen) * (last_row - 1))
        lines = max(1, int(round(v * (1.0 + _rand(gen)))))
        length = float(np.clip(math.exp(math.log(16.0) + 0.6 * float(torch.randn(1, generator=gen))), 4.0, 90.0)) * u
        start = _rand(gen) * W
        into = xs - start
        profile = torch.where(into < length * 0.6, torch.ones(W), torch.exp(-(into - length * 0.6) / (length * 0.2 + 1e-6)))
        profile = torch.where(into < 0, torch.zeros(W), profile).clamp(0, 1)
        kind = _rand(gen)
        target = 1.12 if kind < 0.8 else 0.02
        for r in range(row, min(H, row + lines)):
            stronger = profile > mask[r]
            mask[r] = torch.where(stronger, profile, mask[r])
            level[r] = torch.where(stronger, torch.full((W,), target), level[r])
    return mask, level


# ---------------------------------------------------------------------------
# OSD overlay
# ---------------------------------------------------------------------------


# 5 x 7 pixel glyphs in the style of a VCR's on-screen-display character generator. Rows are joined with
# "|"; X is a lit cell. Drawn as blocks so the OSD looks the same on every machine and needs no font file.
_OSD_GLYPHS = {
    "A": ".XXX.|X...X|X...X|XXXXX|X...X|X...X|X...X",
    "B": "XXXX.|X...X|X...X|XXXX.|X...X|X...X|XXXX.",
    "C": ".XXX.|X...X|X....|X....|X....|X...X|.XXX.",
    "D": "XXXX.|X...X|X...X|X...X|X...X|X...X|XXXX.",
    "E": "XXXXX|X....|X....|XXXX.|X....|X....|XXXXX",
    "F": "XXXXX|X....|X....|XXXX.|X....|X....|X....",
    "G": ".XXX.|X...X|X....|X.XXX|X...X|X...X|.XXXX",
    "H": "X...X|X...X|X...X|XXXXX|X...X|X...X|X...X",
    "I": ".XXX.|..X..|..X..|..X..|..X..|..X..|.XXX.",
    "J": "..XXX|...X.|...X.|...X.|...X.|X..X.|.XX..",
    "K": "X...X|X..X.|X.X..|XX...|X.X..|X..X.|X...X",
    "L": "X....|X....|X....|X....|X....|X....|XXXXX",
    "M": "X...X|XX.XX|X.X.X|X.X.X|X...X|X...X|X...X",
    "N": "X...X|XX..X|X.X.X|X..XX|X...X|X...X|X...X",
    "O": ".XXX.|X...X|X...X|X...X|X...X|X...X|.XXX.",
    "P": "XXXX.|X...X|X...X|XXXX.|X....|X....|X....",
    "Q": ".XXX.|X...X|X...X|X...X|X.X.X|X..X.|.XX.X",
    "R": "XXXX.|X...X|X...X|XXXX.|X.X..|X..X.|X...X",
    "S": ".XXXX|X....|X....|.XXX.|....X|....X|XXXX.",
    "T": "XXXXX|..X..|..X..|..X..|..X..|..X..|..X..",
    "U": "X...X|X...X|X...X|X...X|X...X|X...X|.XXX.",
    "V": "X...X|X...X|X...X|X...X|X...X|.X.X.|..X..",
    "W": "X...X|X...X|X...X|X.X.X|X.X.X|XX.XX|X...X",
    "X": "X...X|X...X|.X.X.|..X..|.X.X.|X...X|X...X",
    "Y": "X...X|X...X|.X.X.|..X..|..X..|..X..|..X..",
    "Z": "XXXXX|....X|...X.|..X..|.X...|X....|XXXXX",
    "0": ".XXX.|X...X|X..XX|X.X.X|XX..X|X...X|.XXX.",
    "1": "..X..|.XX..|..X..|..X..|..X..|..X..|.XXX.",
    "2": ".XXX.|X...X|....X|...X.|..X..|.X...|XXXXX",
    "3": "XXXXX|...X.|..X..|...X.|....X|X...X|.XXX.",
    "4": "...X.|..XX.|.X.X.|X..X.|XXXXX|...X.|...X.",
    "5": "XXXXX|X....|XXXX.|....X|....X|X...X|.XXX.",
    "6": "..XX.|.X...|X....|XXXX.|X...X|X...X|.XXX.",
    "7": "XXXXX|....X|...X.|..X..|.X...|.X...|.X...",
    "8": ".XXX.|X...X|X...X|.XXX.|X...X|X...X|.XXX.",
    "9": ".XXX.|X...X|X...X|.XXXX|....X|...X.|.XX..",
    ":": ".....|..X..|..X..|.....|..X..|..X..|.....",
    ".": ".....|.....|.....|.....|.....|..X..|..X..",
    ",": ".....|.....|.....|.....|..X..|..X..|.X...",
    "-": ".....|.....|.....|XXXXX|.....|.....|.....",
    "_": ".....|.....|.....|.....|.....|.....|XXXXX",
    "+": ".....|..X..|..X..|XXXXX|..X..|..X..|.....",
    "/": "....X|....X|...X.|..X..|.X...|X....|X....",
    "'": "..X..|..X..|.X...|.....|.....|.....|.....",
    "!": "..X..|..X..|..X..|..X..|..X..|.....|..X..",
    "?": ".XXX.|X...X|....X|...X.|..X..|.....|..X..",
    "(": "...X.|..X..|.X...|.X...|.X...|..X..|...X.",
    ")": ".X...|..X..|...X.|...X.|...X.|..X..|.X...",
    "%": "XX..X|XX..X|...X.|..X..|.X...|X..XX|X..XX",
}
# Status symbols on the same 5 x 7 grid.
_OSD_ICONS = {
    "play": "X....|XX...|XXX..|XXXX.|XXX..|XX...|X....",
    "rec": ".....|.XXX.|XXXXX|XXXXX|XXXXX|.XXX.|.....",
    "pause": "XX.XX|XX.XX|XX.XX|XX.XX|XX.XX|XX.XX|XX.XX",
    "stop": ".....|XXXXX|XXXXX|XXXXX|XXXXX|XXXXX|.....",
}
_OSD_ADVANCE = 6      # cells per character (5 wide plus a 1 cell gap)
_OSD_SPACE = 4        # cells a space advances
_OSD_ICON_GAP = 2     # cells between an icon and the text
_OSD_LINE_GAP = 3     # cells between lines stacked in one corner


def _osd_icon(mode: str):
    """Symbol drawn before the OSD text, as part of the pixel font."""
    return {"▶ PLAY": "play", "● REC": "rec", "❚❚ PAUSE": "pause", "■ STOP": "stop"}.get(mode)


def _osd_text(mode: str, custom_date: str = "") -> str:
    fixed = {"▶ PLAY": "PLAY", "● REC": "REC", "❚❚ PAUSE": "PAUSE", "■ STOP": "STOP"}
    if mode in fixed:
        return fixed[mode]
    if mode in ("Date", "Time", "Date+Time"):
        try:
            now = datetime.datetime.now()
            parts = []
            if mode in ("Date", "Date+Time"):
                parts.append((custom_date or "").strip() or now.strftime("%Y %m %d"))
            if mode in ("Time", "Date+Time"):
                parts.append(now.strftime("%H:%M"))
            return "  ".join(parts)
        except Exception:
            return ""
    return ""


def osd_lines(status: str = "Off", status_corner: str = "TL", stamp: str = "Off",
              stamp_corner: str = "BR", custom_date: str = ""):
    """(text, icon, corner) for each OSD line that is switched on, status first."""
    lines = []
    for mode, corner in ((status, status_corner), (stamp, stamp_corner)):
        if mode and mode != "Off":
            text = _osd_text(mode, custom_date)
            if text:
                lines.append((text, _osd_icon(mode), corner))
    return lines


def _osd_glyph(char: str):
    """The 7 rows for `char`: uppercase, accents stripped, anything unknown shown as "?"."""
    char = char.upper()
    if char not in _OSD_GLYPHS:
        base = unicodedata.normalize("NFKD", char)[:1].upper()
        char = base if base in _OSD_GLYPHS else "?"
    return _OSD_GLYPHS[char].split("|")


def _osd_cells(text: str, icon=None):
    """Lit (column, row) cells for one line of OSD, and the line's width in cells."""
    cells, col = [], 0
    if icon in _OSD_ICONS:
        for y, row in enumerate(_OSD_ICONS[icon].split("|")):
            cells += [(col + x, y) for x, c in enumerate(row) if c == "X"]
        col += 5 + _OSD_ICON_GAP
    for char in text.strip():
        if char.isspace():
            col += _OSD_SPACE
            continue
        for y, row in enumerate(_osd_glyph(char)):
            cells += [(col + x, y) for x, c in enumerate(row) if c == "X"]
        col += _OSD_ADVANCE
    return cells, max(0, col - (_OSD_ADVANCE - 5))


def _osd_scale(H: int) -> int:
    """Pixels per font cell; the text is about 4% of the picture height."""
    return max(1, int(round(H * 0.0057)))


def _osd_fill(H: int, W: int, lines) -> torch.Tensor:
    """(1, 1, H, W) 0/1 mask of the lit pixels. Lines sharing a corner stack in the order given; lines in
    the right-hand corners are right-aligned. The margins keep text inside the safe area and clear of the
    head-switch band."""
    fill = np.zeros((H, W), dtype=np.float32)
    scale = _osd_scale(H)
    pad_x, pad_y = max(4, int(W * 0.045)), max(4, int(H * 0.07))
    by_corner = {}
    for text, icon, corner in lines:
        text = str(text or "").strip()
        if text:
            by_corner.setdefault(corner if corner in OSD_CORNERS else "BL", []).append(_osd_cells(text, icon))
    for corner, rows in by_corner.items():
        block = (len(rows) * 7 + (len(rows) - 1) * _OSD_LINE_GAP) * scale
        y = pad_y if corner[0] == "T" else H - block - pad_y
        for cells, cols in rows:
            x0 = pad_x if corner[1] == "L" else W - cols * scale - pad_x
            for cx, cy in cells:
                px, py = x0 + cx * scale, y + cy * scale
                if px >= 0 and py >= 0:
                    fill[py:py + scale, px:px + scale] = 1.0
            y += (7 + _OSD_LINE_GAP) * scale
    return torch.from_numpy(fill).view(1, 1, H, W)


def _burn_in_osd(rgb_bhwc: torch.Tensor, lines, color: str, amount: float, seed: int) -> torch.Tensor:
    """Composite the OSD into the picture the way a character generator does: coloured text on a black
    outline and a smeared drop shadow. `amount` (0..1) scales the analog imperfections (independent line
    jitter and shimmering edges); the tape chain that follows does the softening and colour bleed."""
    B, H, W, _ = rgb_bhwc.shape
    fill = _osd_fill(H, W, lines)
    if float(fill.max()) <= 0:
        return rgb_bhwc
    scale = _osd_scale(H)
    u = W / 320.0
    edge = max(1, scale // 3)
    shadow = max(1, scale // 2)
    outline = F.max_pool2d(fill, 2 * edge + 1, 1, edge)
    drop = F.pad(outline, (shadow, 0, shadow, 0))[..., :H, :W]
    drop = _blur(_trail(drop, 1.4 * scale), 0.5 * scale, 0.4 * scale).clamp(0, 1)

    gen = _stage_generator(seed, 8)
    if amount > 0:
        # The character generator is not locked perfectly to the picture: its lines drift a little.
        sway = (_smooth1d(H, 0.9, gen) * (0.25 * amount * u)).view(1, H)
        layers = _displace_rows(torch.cat([fill, outline, drop], dim=1), sway)
        fill, outline, drop = layers[:, 0:1], layers[:, 1:2], layers[:, 2:3]
        # Shimmer along the glyph edges, soft along the line like the rest of the signal noise.
        rim = F.max_pool2d(fill, 3, 1, 1) + F.max_pool2d(-fill, 3, 1, 1)
        shimmer = _blur(torch.randn(fill.shape, generator=gen), 0.7, 0.0)
        fill = (fill + rim * shimmer * (0.30 * amount)).clamp(0, 1)

    fill, outline, drop = (t.to(rgb_bhwc.device).permute(0, 2, 3, 1) for t in (fill, outline, drop))
    colour = torch.tensor(OSD_COLORS.get(color, OSD_COLORS["White"]), device=rgb_bhwc.device, dtype=rgb_bhwc.dtype)
    out = rgb_bhwc * (1.0 - 0.7 * drop)
    out = out * (1.0 - outline)
    return out * (1.0 - fill) + colour * fill


# ---------------------------------------------------------------------------
# Top-level
# ---------------------------------------------------------------------------


def apply_vhs(
    image: torch.Tensor,
    preset: VHSParams,
    overrides: Optional[VHSParams] = None,
    osd=None,
    osd_color: str = "White",
    effect_fade: float = 0.0,
    seed: Optional[int] = None,
) -> torch.Tensor:
    """`osd` is a list of (text, icon, corner) from `osd_lines`; `effect_fade` (0..1) blends the result back
    toward the source, which keeps its OSD."""
    image = normalize_image(image)
    device, dtype = image.device, image.dtype

    p = overrides or preset
    base = int(seed) if seed is not None and seed >= 0 else secrets.randbelow(2**31)
    fade = min(1.0, max(0.0, float(effect_fade)))

    # The OSD is part of the picture the tape sees, not something drawn over the result.
    if osd:
        image = _burn_in_osd(image, osd, osd_color, 1.0 - fade, base)
    source = image

    x = rgb_to_yuv(image).permute(0, 3, 1, 2).contiguous().float()
    B, _, H, W = x.shape
    u, v = W / 320.0, H / 480.0
    y, uv = _levels(x[:, :1], x[:, 1:], p)
    y = _luma_bandwidth(y, p)
    uv = _chroma_bandwidth(uv, p.chroma_blur, p.chroma_shift)
    uv = _cross_colour(y, uv, p.yc_separation)
    x = torch.cat([y, uv], dim=1)

    # Time base: line wobble, flagging, tracking bands and the head-switch tear move as one displacement,
    # so every line is resampled exactly once.
    offsets = torch.zeros(B, H)
    bands = torch.zeros(B, H)
    head_noise = torch.zeros(B, H)
    for b in range(B):
        wobble, band = _time_base(H, W, p.tracking_jitter, p.flagging, _stage_generator(base + b, 1))
        tear, garble = _head_switch(H, W, p.head_switch, _stage_generator(base + b, 2))
        offsets[b], bands[b], head_noise[b] = wobble + tear, band, garble
    if float(offsets.abs().max()) > 0.01:
        x = _displace_rows(x, offsets)
    y, uv = x[:, :1], x[:, 1:]
    rows = lambda t: t.to(device).view(B, 1, H, 1)

    # Tape noise: soft along the line and uneven from line to line, not clean digital grain.
    if p.hiss > 0:
        y = y + _streaky_noise(y.shape, 0.5 * u + 0.3, 0.0, _stage_generator(base, 3)).to(device) * (p.hiss * 0.075)
        if p.chroma_noise > 0:
            colour = _streaky_noise(uv.shape, 2.2 * u + 0.5, 0.6 * v, _stage_generator(base, 4)).to(device)
            uv = uv + colour * (p.chroma_noise * p.hiss * 0.07)
    # Snow and colour loss inside tracking bands, and garbling in the head-switch lines.
    if float(bands.max()) > 0:
        snow = _streaky_noise(y.shape, 1.4 * u + 0.5, 0.0, _stage_generator(base, 5)).to(device)
        y = y + rows(bands) * (snow * (0.22 + 0.35 * p.tracking_jitter) + 0.04)
        uv = uv * (1.0 - 0.75 * rows(bands))
    if float(head_noise.max()) > 0:
        garble = _streaky_noise(y.shape, 1.1 * u + 0.4, 0.0, _stage_generator(base, 6)).to(device)
        y = y + rows(head_noise) * garble * (0.18 + 0.30 * p.head_switch)
        uv = uv * (1.0 - 0.6 * rows(head_noise))

    # Dropouts: short streaks that drive the line to white (mostly) or black, with a soft tail.
    if p.dropout_rate > 0:
        last_row = H - max(3, int(round(H * (0.016 + 0.040 * p.head_switch)))) if p.head_switch > 0 else H
        for b in range(B):
            mask, level = _dropout_layer(H, W, p.dropout_rate, last_row, _stage_generator(base + b, 7))
            if float(mask.max()) <= 0:
                continue
            mask = _blur(mask.view(1, 1, H, W), 0.35 * u + 0.2, 0.4 * v).view(H, W).clamp(0, 1).to(device)
            level = level.to(device)
            y[b, 0] = y[b, 0] * (1.0 - mask) + level * mask
            uv[b] = uv[b] * (1.0 - 0.9 * mask)

    yuv = torch.cat([y.clamp(-0.1, 1.25), uv.clamp(-0.6, 0.6)], dim=1).permute(0, 2, 3, 1).contiguous()
    rgb = yuv_to_rgb(yuv).clamp(0.0, 1.0)
    if fade > 0:
        rgb = rgb * (1.0 - fade) + source.clamp(0.0, 1.0) * fade

    return rgb.to(dtype=dtype, device=device)


# ---------------------------------------------------------------------------
# Node class
# ---------------------------------------------------------------------------


class RayVHS:
    """VHS / tape degradation in YUV space with OSD overlays."""

    DESCRIPTION = (
        "Videotape degradation modeled as a signal chain in YUV space: soft luma with deck "
        "sharpening halos, low-bandwidth chroma that smears and lags, cross-colour rainbows, "
        "line-level time-base wobble, tracking bands, a head-switching tear, streaky tape noise "
        "and dropouts. Effects scale with the picture, so presets look the same at any size.\n\n"
        "The preset sets the tape and deck character (softness, halos, colour, levels). Each "
        "slider defaults to -1 (use the preset value) and 0..1 overrides that one effect.\n\n"
        "effect_fade blends the result back toward the source: 0 is the full effect, 1 is the "
        "untouched picture.\n\n"
        "The on-screen display has a status line (PLAY / REC / PAUSE / STOP) and a date / time line, "
        "each in its own corner, in white, yellow or green. It is burned into the picture before the "
        "tape, so it softens, bleeds and wobbles with it. Leave osd_date blank to stamp today's date."
    )

    @classmethod
    def INPUT_TYPES(cls):
        _override = "-1 uses the preset value; 0..1 overrides."
        return {
            "required": {
                "image": ("IMAGE", {"tooltip": "Source image."}),
                "preset": (PRESET_NAMES, {
                    "default": "Worn EP",
                    "tooltip": "Tape and deck: sets softness, halos, colour, levels and the starting value of every slider below.",
                }),
                "chroma_blur": ("FLOAT", {
                    "default": -1.0, "min": -1.0, "max": 1.0, "step": 0.05,
                    "tooltip": f"Colour bandwidth loss: how far chroma smears and lags. {_override}",
                }),
                "head_switch": ("FLOAT", {
                    "default": -1.0, "min": -1.0, "max": 1.0, "step": 0.05,
                    "tooltip": f"The torn, noisy band at the bottom of the frame. {_override}",
                }),
                "tracking_jitter": ("FLOAT", {
                    "default": -1.0, "min": -1.0, "max": 1.0, "step": 0.05,
                    "tooltip": f"Line wobble and tracking bands. {_override}",
                }),
                "dropout_rate": ("FLOAT", {
                    "default": -1.0, "min": -1.0, "max": 1.0, "step": 0.05,
                    "tooltip": f"Dropout streaks (short bright or dark lines). {_override}",
                }),
                "hiss": ("FLOAT", {
                    "default": -1.0, "min": -1.0, "max": 1.0, "step": 0.05,
                    "tooltip": f"Tape noise in luma and colour. {_override}",
                }),
                "yc_separation": ("FLOAT", {
                    "default": -1.0, "min": -1.0, "max": 1.0, "step": 0.05,
                    "tooltip": f"Cross-colour rainbows and dot crawl around fine detail. {_override}",
                }),
                "effect_fade": ("FLOAT", {
                    "default": 0.0, "min": 0.0, "max": 1.0, "step": 0.05,
                    "tooltip": "Blend the result back toward the source image. 0 = full effect, 1 = untouched picture.",
                }),
                "osd_status": (OSD_STATUS, {
                    "default": "Off",
                    "tooltip": "Deck status readout: Off / ▶ PLAY / ● REC / ❚❚ PAUSE / ■ STOP.",
                }),
                "osd_status_corner": (OSD_CORNERS, {
                    "default": "TL",
                    "tooltip": "Corner for the status readout (TL=top-left, TR=top-right, BL=bottom-left, BR=bottom-right).",
                }),
                "osd_stamp": (OSD_STAMP, {
                    "default": "Off",
                    "tooltip": "Date and time stamp: Off / Date / Time / Date+Time. Shown together with the status readout.",
                }),
                "osd_stamp_corner": (OSD_CORNERS, {
                    "default": "BR",
                    "tooltip": "Corner for the date / time stamp. Lines sharing a corner stack, status above stamp.",
                }),
                "osd_date": ("STRING", {
                    "default": "",
                    "placeholder": "YYYY MM DD (blank = today)",
                    "tooltip": "Date text for the stamp. Leave blank to use today's date.",
                }),
                "osd_color": (list(OSD_COLORS), {
                    "default": "White",
                    "tooltip": "OSD colour: White, Yellow or Green.",
                }),
                "seed": ("INT", {
                    "default": -1, "min": -1, "max": 2**31 - 1,
                    "tooltip": "-1 for random; any >=0 value is reproducible.",
                }),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    OUTPUT_TOOLTIPS = ("Tape-degraded image with the OSD burned in.",)
    FUNCTION = "process"
    CATEGORY = "👑 Ray/✨ VFX"

    def process(
        self,
        image,
        preset,
        chroma_blur,
        head_switch,
        tracking_jitter,
        dropout_rate,
        hiss,
        yc_separation,
        effect_fade,
        osd_status,
        osd_status_corner,
        osd_stamp,
        osd_stamp_corner,
        osd_date,
        osd_color,
        seed,
    ):
        base = PRESETS.get(preset)
        if base is None:
            raise ValueError(f"unknown preset: {preset!r}")

        # Override any control whose slider is >= 0. -1 = "use preset value".
        def _mix(slider, preset_val):
            return float(slider) if slider >= 0.0 else preset_val

        overrides = replace(
            base,
            chroma_blur=_mix(chroma_blur, base.chroma_blur),
            head_switch=_mix(head_switch, base.head_switch),
            tracking_jitter=_mix(tracking_jitter, base.tracking_jitter),
            dropout_rate=_mix(dropout_rate, base.dropout_rate),
            hiss=_mix(hiss, base.hiss),
            yc_separation=_mix(yc_separation, base.yc_separation),
        )

        out = apply_vhs(
            image=image,
            preset=base,
            overrides=overrides,
            osd=osd_lines(osd_status, osd_status_corner, osd_stamp, osd_stamp_corner, osd_date or ""),
            osd_color=osd_color,
            effect_fade=effect_fade,
            seed=int(seed),
        )
        return (out,)
