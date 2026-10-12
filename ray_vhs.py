"""Ray's VFX: VHS / Tape — analog video degradation.

Multi-pass simulation in YUV (BT.601):
  1. RGB → YUV
  2. Chroma subsample (decimate UV horizontally) + chroma blur
  3. Y/C separation artifacts (optional): cross-color rainbow + dot crawl
  4. Head-switching noise band at bottom (horizontal jitter + noise)
  5. Tracking jitter: random per-row horizontal offsets
  6. Dropouts: scattered white streaks
  7. Tape hiss: gaussian noise on Y
  8. YUV → RGB
  9. (Optional) OSD overlay (camcorder-style date/time/PLAY/REC) drawn in a built-in 5x7 pixel font

Output preserves BHWC float32 [0,1] shape.
"""

from __future__ import annotations

import datetime
import unicodedata
import math
import random
from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image, ImageDraw

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
    chroma_blur: float        # 0..1 (severity)
    head_switch: float        # 0..1
    tracking_jitter: float    # 0..1
    dropout_rate: float       # 0..1 (probability mass)
    hiss: float               # 0..1
    yc_separation: float      # 0..1 (cross-color / dot-crawl mix)


PRESETS = {
    "Pristine SP": VHSParams(
        "Pristine SP", chroma_blur=0.2, head_switch=0.05, tracking_jitter=0.05,
        dropout_rate=0.02, hiss=0.05, yc_separation=0.10,
    ),
    "Worn EP": VHSParams(
        "Worn EP", chroma_blur=0.55, head_switch=0.35, tracking_jitter=0.25,
        dropout_rate=0.20, hiss=0.20, yc_separation=0.40,
    ),
    "Gen-3 dub": VHSParams(
        "Gen-3 dub", chroma_blur=0.75, head_switch=0.50, tracking_jitter=0.40,
        dropout_rate=0.35, hiss=0.35, yc_separation=0.55,
    ),
    "VHS-C camcorder": VHSParams(
        "VHS-C camcorder", chroma_blur=0.45, head_switch=0.20, tracking_jitter=0.15,
        dropout_rate=0.10, hiss=0.25, yc_separation=0.30,
    ),
    "Hi8": VHSParams(
        "Hi8", chroma_blur=0.30, head_switch=0.10, tracking_jitter=0.08,
        dropout_rate=0.05, hiss=0.12, yc_separation=0.15,
    ),
    "Custom": VHSParams(
        "Custom", chroma_blur=0.5, head_switch=0.3, tracking_jitter=0.2,
        dropout_rate=0.1, hiss=0.15, yc_separation=0.3,
    ),
}
PRESET_NAMES = list(PRESETS.keys())

OSD_MODES = ["Off", "▶ PLAY", "● REC", "Date", "Date+Time"]
OSD_CORNERS = ["TL", "TR", "BL", "BR"]


# ---------------------------------------------------------------------------
# Passes
# ---------------------------------------------------------------------------


def _gauss_kernel(sigma: float, device, dtype) -> torch.Tensor:
    radius = max(1, int(math.ceil(sigma * 3.0)))
    x = torch.arange(-radius, radius + 1, dtype=dtype, device=device)
    k = torch.exp(-(x * x) / (2.0 * sigma * sigma))
    return k / k.sum()


def _blur_h(x: torch.Tensor, sigma: float) -> torch.Tensor:
    """Horizontal-only gaussian blur on a BCHW tensor."""
    if sigma <= 0.0:
        return x
    k = _gauss_kernel(sigma, x.device, x.dtype)
    radius = k.numel() // 2
    C = x.shape[1]
    kh = k.view(1, 1, 1, -1).expand(C, 1, 1, -1)
    x = F.pad(x, (radius, radius, 0, 0), mode="reflect")
    return F.conv2d(x, kh, groups=C)


def _chroma_blur_subsample(yuv_bhwc: torch.Tensor, severity: float) -> torch.Tensor:
    """Simulate VHS 4:1:1 chroma subsample + bandwidth-limit horizontal blur."""
    if severity <= 0.0:
        return yuv_bhwc
    # BHWC → BCHW for conv2d
    bchw = yuv_bhwc.permute(0, 3, 1, 2).contiguous()
    y = bchw[:, 0:1]
    uv = bchw[:, 1:3]
    # Decimate UV horizontally (factor proportional to severity), then upsample.
    decim_factor = 1 + int(round(severity * 6))   # 1..7
    if decim_factor > 1:
        uv_small = F.avg_pool2d(uv, kernel_size=(1, decim_factor),
                                stride=(1, decim_factor))
        uv = F.interpolate(uv_small, size=(uv.shape[2], uv.shape[3]),
                           mode="bilinear", align_corners=False)
    # Additional horizontal gaussian smear on chroma
    uv = _blur_h(uv, sigma=1.0 + severity * 4.0)
    out = torch.cat([y, uv], dim=1)
    return out.permute(0, 2, 3, 1).contiguous()


def _yc_artifacts(yuv_bhwc: torch.Tensor, strength: float) -> torch.Tensor:
    """Approximate cross-color/dot-crawl: high-frequency luma bleeds into chroma."""
    if strength <= 0.0:
        return yuv_bhwc
    bchw = yuv_bhwc.permute(0, 3, 1, 2).contiguous()
    y = bchw[:, 0:1]
    # High-pass on Y: y - blurred_y
    hp = y - _blur_h(y, sigma=1.5)
    # Modulate by a horizontal carrier (cosine of pixel index) to fake the
    # color subcarrier — bleed into U + V at opposite phases.
    H, W = y.shape[2], y.shape[3]
    xs = torch.arange(W, device=y.device, dtype=y.dtype).view(1, 1, 1, W)
    carrier = torch.cos(xs * (math.pi / 2.0))   # alternates each pixel
    u_bleed = hp * carrier * (0.6 * strength)
    v_bleed = hp * torch.sin(xs * (math.pi / 2.0)) * (0.6 * strength)
    out = bchw.clone()
    out[:, 1:2] = out[:, 1:2] + u_bleed
    out[:, 2:3] = out[:, 2:3] + v_bleed
    return out.permute(0, 2, 3, 1).contiguous()


def _head_switch_noise(
    yuv_bhwc: torch.Tensor,
    severity: float,
    rng: random.Random,
) -> torch.Tensor:
    """Bottom 2-5% of frame gets horizontal offset + noise."""
    if severity <= 0.0:
        return yuv_bhwc
    B, H, W, C = yuv_bhwc.shape
    band_h = max(2, int(H * (0.02 + 0.03 * severity)))
    out = yuv_bhwc.clone()
    for b in range(B):
        for i in range(band_h):
            row_idx = H - band_h + i
            shift = int((1.0 - i / max(1, band_h - 1)) * severity * (W * 0.08))
            shift = rng.randint(-shift, shift) if shift > 0 else 0
            if shift != 0:
                out[b, row_idx] = torch.roll(out[b, row_idx], shifts=shift, dims=0)
            # luma noise on Y channel
            noise = (torch.rand(W, device=out.device, dtype=out.dtype) - 0.5) * severity * 0.6
            out[b, row_idx, :, 0] = (out[b, row_idx, :, 0] + noise).clamp(0.0, 1.5)
    return out


def _tracking_jitter(
    yuv_bhwc: torch.Tensor,
    severity: float,
    rng: random.Random,
) -> torch.Tensor:
    """Per-row horizontal pixel offset, sparse — tape tracking error."""
    if severity <= 0.0:
        return yuv_bhwc
    B, H, W, _ = yuv_bhwc.shape
    out = yuv_bhwc.clone()
    max_shift = int(severity * W * 0.04)
    if max_shift <= 0:
        return yuv_bhwc
    # Pick which rows jitter (about severity * 0.1 of them)
    jitter_count = int(H * severity * 0.15)
    for _ in range(jitter_count):
        b = rng.randrange(B)
        r = rng.randrange(H)
        shift = rng.randint(-max_shift, max_shift)
        if shift != 0:
            out[b, r] = torch.roll(out[b, r], shifts=shift, dims=0)
    return out


def _dropouts(
    yuv_bhwc: torch.Tensor,
    rate: float,
    rng: random.Random,
) -> torch.Tensor:
    """White horizontal streaks (Y boosted) at sparse random rows."""
    if rate <= 0.0:
        return yuv_bhwc
    B, H, W, _ = yuv_bhwc.shape
    out = yuv_bhwc.clone()
    count = int(B * H * rate * 0.02)
    for _ in range(count):
        b = rng.randrange(B)
        r = rng.randrange(H)
        x0 = rng.randrange(W)
        length = rng.randint(2, max(3, int(W * 0.05)))
        x1 = min(W, x0 + length)
        out[b, r, x0:x1, 0] = 1.2  # bright Y
        out[b, r, x0:x1, 1] = 0.0
        out[b, r, x0:x1, 2] = 0.0
    return out


def _hiss(
    yuv_bhwc: torch.Tensor,
    amount: float,
    generator: Optional[torch.Generator],
) -> torch.Tensor:
    if amount <= 0.0:
        return yuv_bhwc
    noise = torch.randn(
        yuv_bhwc.shape[:3] + (1,),
        device=yuv_bhwc.device, dtype=yuv_bhwc.dtype,
        generator=generator,
    )
    out = yuv_bhwc.clone()
    out[..., 0:1] = out[..., 0:1] + noise * amount * 0.05
    return out


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
# The PLAY triangle and REC dot, on the same 5 x 7 grid.
_OSD_ICONS = {
    "play": "X....|XX...|XXX..|XXXX.|XXX..|XX...|X....",
    "rec": ".....|.XXX.|XXXXX|XXXXX|XXXXX|.XXX.|.....",
}
_OSD_ADVANCE = 6      # cells per character (5 wide plus a 1 cell gap)
_OSD_SPACE = 4        # cells a space advances
_OSD_ICON_GAP = 2     # cells between an icon and the text


def _osd_icon(mode: str):
    """Symbol drawn before the OSD text, as part of the pixel font."""
    return {"▶ PLAY": "play", "● REC": "rec"}.get(mode)


def _osd_text(mode: str, custom_date: str) -> str:
    if mode == "▶ PLAY":
        return "PLAY"
    if mode == "● REC":
        return "REC"
    if mode in ("Date", "Date+Time"):
        try:
            if custom_date.strip():
                base = custom_date.strip()
            else:
                now = datetime.datetime.now()
                base = now.strftime("%Y %m %d")
            if mode == "Date+Time":
                now = datetime.datetime.now()
                base += "  " + now.strftime("%H:%M")
            return base
        except Exception:
            return ""
    return ""


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


def _draw_osd(
    rgb_bhwc: torch.Tensor,
    text: str,
    corner: str,
    icon: str = None,
) -> torch.Tensor:
    """Composite a VCR-style OSD line into the chosen corner: chunky 5 x 7 pixel characters in
    cream with a black outline and drop shadow, like a tape deck's character generator."""
    text = str(text or "").strip()
    if not text:
        return rgb_bhwc
    B, H, W, _ = rgb_bhwc.shape
    cells, cols = _osd_cells(text, icon)
    scale = max(1, int(round(H * 0.0057)))        # pixels per cell; the text is about 4% of the height
    edge = max(1, scale // 3)                     # outline thickness
    shadow = max(1, scale // 4)                   # drop-shadow offset
    tw, th = cols * scale, 7 * scale
    pad = max(4, int(H * 0.01)) + edge
    if corner == "TL":
        x0, y0 = pad, pad
    elif corner == "TR":
        x0, y0 = W - tw - pad, pad
    elif corner == "BR":
        x0, y0 = W - tw - pad, H - th - pad
    else:
        x0, y0 = pad, H - th - pad
    out_list = []
    for b in range(B):
        arr = (rgb_bhwc[b].cpu().numpy().clip(0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)
        pil = Image.fromarray(arr, mode="RGB")
        draw = ImageDraw.Draw(pil)
        for cx, cy in cells:                      # outline and shadow first, so they never cover a neighbour
            x, y = x0 + cx * scale, y0 + cy * scale
            draw.rectangle([x - edge + shadow, y - edge + shadow, x + scale - 1 + edge + shadow, y + scale - 1 + edge + shadow],
                           fill=(0, 0, 0))
            draw.rectangle([x - edge, y - edge, x + scale - 1 + edge, y + scale - 1 + edge], fill=(0, 0, 0))
        for cx, cy in cells:
            x, y = x0 + cx * scale, y0 + cy * scale
            draw.rectangle([x, y, x + scale - 1, y + scale - 1], fill=(255, 255, 240))
        out_arr = np.asarray(pil, dtype=np.float32) / 255.0
        out_list.append(torch.from_numpy(out_arr))
    return torch.stack(out_list, dim=0).to(rgb_bhwc.device).contiguous()


# ---------------------------------------------------------------------------
# Top-level
# ---------------------------------------------------------------------------


def apply_vhs(
    image: torch.Tensor,
    preset: VHSParams,
    overrides: Optional[VHSParams] = None,
    osd_mode: str = "Off",
    osd_corner: str = "BL",
    osd_date: str = "",
    seed: Optional[int] = None,
) -> torch.Tensor:
    image = normalize_image(image)
    device, dtype = image.device, image.dtype

    p = overrides or preset
    rng = random.Random(seed) if seed is not None and seed >= 0 else random.Random()
    generator = None
    if seed is not None and seed >= 0:
        try:
            generator = torch.Generator(device=device).manual_seed(int(seed))
        except (RuntimeError, TypeError):
            generator = None

    yuv = rgb_to_yuv(image)

    yuv = _chroma_blur_subsample(yuv, p.chroma_blur)
    yuv = _yc_artifacts(yuv, p.yc_separation)
    yuv = _head_switch_noise(yuv, p.head_switch, rng)
    yuv = _tracking_jitter(yuv, p.tracking_jitter, rng)
    yuv = _dropouts(yuv, p.dropout_rate, rng)
    yuv = _hiss(yuv, p.hiss, generator)

    rgb = yuv_to_rgb(yuv)

    if osd_mode and osd_mode != "Off":
        text = _osd_text(osd_mode, osd_date)
        rgb = _draw_osd(rgb, text, osd_corner, _osd_icon(osd_mode))

    return rgb.clamp(0.0, 1.0).to(dtype=dtype, device=device)


# ---------------------------------------------------------------------------
# Node class
# ---------------------------------------------------------------------------


class RayVHS:
    """VHS / tape degradation in YUV space with OSD overlays."""

    DESCRIPTION = (
        "Videotape degradation modeled in YUV space: chroma blur, head-"
        "switching band, tracking wobble, dropouts, hiss, and Y/C "
        "separation. Each slider defaults to -1 (use the preset value) "
        "and 0..1 overrides that channel.\n\n"
        "OSD overlay simulates the classic VCR readout: ▶ PLAY / ● REC / "
        "Date / Date+Time in any corner. Leave osd_date blank to stamp "
        "today's date."
    )

    @classmethod
    def INPUT_TYPES(cls):
        _override = "-1 uses the preset value; 0..1 overrides."
        return {
            "required": {
                "image": ("IMAGE", {"tooltip": "Source image."}),
                "preset": (PRESET_NAMES, {
                    "default": "Worn EP",
                    "tooltip": "Tape / speed preset (baseline for the sliders below).",
                }),
                "chroma_blur": ("FLOAT", {
                    "default": -1.0, "min": -1.0, "max": 1.0, "step": 0.05,
                    "tooltip": f"Chroma blur strength. {_override}",
                }),
                "head_switch": ("FLOAT", {
                    "default": -1.0, "min": -1.0, "max": 1.0, "step": 0.05,
                    "tooltip": f"Head-switching band at frame bottom. {_override}",
                }),
                "tracking_jitter": ("FLOAT", {
                    "default": -1.0, "min": -1.0, "max": 1.0, "step": 0.05,
                    "tooltip": f"Horizontal tracking wobble. {_override}",
                }),
                "dropout_rate": ("FLOAT", {
                    "default": -1.0, "min": -1.0, "max": 1.0, "step": 0.05,
                    "tooltip": f"Random dropouts (bright streaks). {_override}",
                }),
                "hiss": ("FLOAT", {
                    "default": -1.0, "min": -1.0, "max": 1.0, "step": 0.05,
                    "tooltip": f"Luma noise / analog hiss. {_override}",
                }),
                "yc_separation": ("FLOAT", {
                    "default": -1.0, "min": -1.0, "max": 1.0, "step": 0.05,
                    "tooltip": f"Y/C separation artifact strength. {_override}",
                }),
                "osd_mode": (OSD_MODES, {
                    "default": "Off",
                    "tooltip": "On-screen display overlay: Off / ▶ PLAY / ● REC / Date / Date+Time.",
                }),
                "osd_corner": (OSD_CORNERS, {
                    "default": "BL",
                    "tooltip": "Corner for the OSD (TL=top-left, TR=top-right, BL=bottom-left, BR=bottom-right).",
                }),
                "osd_date": ("STRING", {
                    "default": "",
                    "placeholder": "YYYY MM DD (blank = today)",
                    "tooltip": "OSD date. Leave blank to use today's date.",
                }),
                "seed": ("INT", {
                    "default": -1, "min": -1, "max": 2**31 - 1,
                    "tooltip": "-1 for random; any >=0 value is reproducible.",
                }),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    OUTPUT_TOOLTIPS = ("Tape-degraded image with the OSD overlay applied.",)
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
        osd_mode,
        osd_corner,
        osd_date,
        seed,
    ):
        base = PRESETS.get(preset)
        if base is None:
            raise ValueError(f"unknown preset: {preset!r}")

        # Override any control whose slider is >= 0. -1 = "use preset value".
        def _mix(slider, preset_val):
            return float(slider) if slider >= 0.0 else preset_val

        overrides = VHSParams(
            label=base.label,
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
            osd_mode=osd_mode,
            osd_corner=osd_corner,
            osd_date=osd_date or "",
            seed=int(seed),
        )
        return (out,)
