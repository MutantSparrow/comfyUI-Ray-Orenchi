"""Ray's VFX: Pixel Art — ComfyUI custom node for pixel-art conversion.

Pipeline per image:
    1. Normalize input (BHWC float32 [0,1]; drop alpha; expand grayscale).
    2. Downscale: manual_resize | auto_downscale_loose | auto_downscale_strict
       | auto_pixel_size (edge-grid block detection + phase-aligned mean-pool).
    3. Solid-background isolation (3D RGB histogram → OkLab-tolerance mask).
    4. Optional dither (additive: bayer_2x2/4x4/8x8, blue_noise; coupled:
       riemersma error diffusion on Hilbert curve, knoll/yliluoma pattern).
    5. Selective dither: smooth-region mask (OkLab L* std/range/Sobel) so
       dither stays off subjects.
    6. Palette reduction: kmeans_lab | kmeans_rgb | quantize_simple |
       ramps_oklab (per-hue lightness ramps). Optional palette_image input
       extracts a fixed palette and snaps to {2}∪{4k}.
    7. BG mask override (single nearest-OkLab palette entry; no dither speckle).
    8. Optional silhouette outline (palette-rank step on Sobel edges).
    9. Hue-sorted palette preview grid.

Tensor convention (ComfyUI): IMAGE = BHWC float32 in [0,1].
"""

from __future__ import annotations

import warnings
from contextlib import contextmanager
from typing import Optional, Tuple

import numpy as np
import torch
import torch.nn.functional as F
from sklearn.cluster import MiniBatchKMeans
from sklearn.exceptions import ConvergenceWarning

try:
    from ._common import (
        SRGB_LINEAR_THRESHOLD,
        SRGB_GAMMA_OFFSET,
        SRGB_GAMMA_SLOPE,
        SRGB_GAMMA_EXPONENT,
        SRGB_LINEAR_SLOPE,
        SRGB_LINEAR_THRESHOLD_INV,
        normalize_image,
        srgb_to_linear as _torch_srgb_to_linear,
    )
except ImportError:
    from _common import (
        SRGB_LINEAR_THRESHOLD,
        SRGB_GAMMA_OFFSET,
        SRGB_GAMMA_SLOPE,
        SRGB_GAMMA_EXPONENT,
        SRGB_LINEAR_SLOPE,
        SRGB_LINEAR_THRESHOLD_INV,
        normalize_image,
        srgb_to_linear as _torch_srgb_to_linear,
    )


@contextmanager
def _suppress_kmeans_convergence():
    """Silence sklearn ConvergenceWarning only inside the wrapped block."""
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=ConvergenceWarning)
        yield


# --- Constants ---------------------------------------------------------------

# Bayer ordered-dither matrices, normalized to [0, 1).
BAYER_2X2 = np.array([[0, 2], [3, 1]], dtype=np.float32) / 4.0
BAYER_4X4 = (
    np.array(
        [[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]],
        dtype=np.float32,
    )
    / 16.0
)
BAYER_8X8 = (
    np.array(
        [
            [0, 32, 8, 40, 2, 34, 10, 42],
            [48, 16, 56, 24, 50, 18, 58, 26],
            [12, 44, 4, 36, 14, 46, 6, 38],
            [60, 28, 52, 20, 62, 30, 54, 22],
            [3, 35, 11, 43, 1, 33, 9, 41],
            [51, 19, 59, 27, 49, 17, 57, 25],
            [15, 47, 7, 39, 13, 45, 5, 37],
            [63, 31, 55, 23, 61, 29, 53, 21],
        ],
        dtype=np.float32,
    )
    / 64.0
)
# Dither amplitude in 0-255 space; +/- 10 around midpoint.
DITHER_AMPLITUDE = 20.0

# Blue-noise mask side. 32 is a good speed/quality tradeoff and tiles cleanly.
BLUE_NOISE_SIZE = 32
BLUE_NOISE_SEED = 42

# Riemersma error-diffusion parameters (Hilbert curve).
RIEMERSMA_HISTORY = 16
RIEMERSMA_DECAY_RATIO = 1.0 / 16.0  # oldest weight relative to newest

# Knoll/Yliluoma per-pixel chunk ceiling for the (chunk, palette, 3) inner array.
KNOLL_CHUNK_BYTES = 96 * 1024 * 1024

# Dither categories: pre-noise types inject noise before quantization;
# coupled types replace nearest-neighbor mapping with their own scheme.
PRE_NOISE_DITHERS = {"bayer_2x2", "bayer_4x4", "bayer_8x8", "blue_noise"}
COUPLED_DITHERS = {"riemersma", "knoll"}

# sRGB <-> XYZ (D65) and CIE Lab constants.
SRGB_TO_XYZ = np.array(
    [
        [0.4124564, 0.3575761, 0.1804375],
        [0.2126729, 0.7151522, 0.0721750],
        [0.0193339, 0.1191920, 0.9503041],
    ],
    dtype=np.float32,
)
D65_WHITEPOINT = np.array([0.95047, 1.00000, 1.08883], dtype=np.float32)

# OkLab (Björn Ottosson 2020): perceptually uniform, used for nearest-color
# matching and dither error diffusion. M1 = linear RGB → LMS, M2 = LMS' → Lab.
OKLAB_M1 = np.array(
    [
        [0.4122214708, 0.5363325363, 0.0514459929],
        [0.2119034982, 0.6806995451, 0.1073969566],
        [0.0883024619, 0.2817188376, 0.6299787005],
    ],
    dtype=np.float32,
)
OKLAB_M2 = np.array(
    [
        [0.2104542553,  0.7936177850, -0.0040720468],
        [1.9779984951, -2.4285922050,  0.4505937099],
        [0.0259040371,  0.7827717662, -0.8086757660],
    ],
    dtype=np.float32,
)
LAB_DELTA = 6.0 / 29.0
LAB_DELTA_CUBED = LAB_DELTA ** 3            # 0.008856
LAB_F_SLOPE = 1.0 / (3.0 * LAB_DELTA ** 2)  # 7.787
LAB_F_OFFSET = 4.0 / 29.0                   # 16/116

# Auto-downscale acceptance thresholds (mean abs reconstruction error).
AUTO_THRESHOLDS = {"loose": 0.05, "strict": 0.02}

# Mixel-aware auto downscale tuning.
EDGE_PERCENTILE = 85.0
MIN_EDGE_RUNS = 8
MIXEL_TOLERANCE = 1

# Solid-background isolation: a dominant near-uniform region is detected from a
# 3D RGB histogram and mapped to a single nearest-OkLab palette entry. Subject
# pixels are mapped/dithered normally; the background mask overrides the
# mapper output so noise / dither never speckles the BG.
BG_HIST_BINS = 16              # bins per channel — 16³ = 4096 buckets total
BG_DOMINANCE_THRESHOLD = 0.20  # top bucket must cover ≥ 20% of pixels to count
BG_OKLAB_TOLERANCE = 0.05      # OkLab distance from BG mean to belong to BG mask

# Quality-feature tuning (all features default OFF; user toggles in INPUT_TYPES).
DITHER_SMOOTH_THRESHOLD_DEFAULT = 0.04   # OkLab L* std cutoff for smooth-region detection
OUTLINE_STEPS_DEFAULT = 1                # palette-rank steps to darken on silhouette edges
RAMP_LEVELS_DEFAULT = 4                  # M (L* levels per hue/chroma cluster) for ramps_oklab

# MiniBatchKMeans tuning.
KMEANS_BATCH = 2048
KMEANS_N_INIT = 3

# Palette preview grid layout.
PALETTE_GRID_COLS = 10
PALETTE_SWATCH_SIZE = 64

# Nearest-neighbor mapping chunk (pixels per cdist call) to bound memory.
NN_MAP_CHUNK = 65536


# --- Color-space helpers -----------------------------------------------------


def rgb_to_lab(rgb_0_255: np.ndarray) -> np.ndarray:
    """Convert sRGB (0-255) to CIE Lab.

    Args:
        rgb_0_255: numpy array of shape (..., 3) with values in [0, 255].

    Returns:
        numpy array of shape (..., 3) with channels (L*, a*, b*).
    """
    arr = (rgb_0_255.astype(np.float32) / 255.0).copy()  # copy avoids mutating input
    mask = arr > SRGB_LINEAR_THRESHOLD
    arr[mask] = np.power(
        (arr[mask] + SRGB_GAMMA_OFFSET) / SRGB_GAMMA_SLOPE, SRGB_GAMMA_EXPONENT
    )
    arr[~mask] /= SRGB_LINEAR_SLOPE
    xyz = arr @ SRGB_TO_XYZ.T
    xyz /= D65_WHITEPOINT
    mask = xyz > LAB_DELTA_CUBED
    f_xyz = np.empty_like(xyz)
    f_xyz[mask] = np.power(xyz[mask], 1.0 / 3.0)
    f_xyz[~mask] = LAB_F_SLOPE * xyz[~mask] + LAB_F_OFFSET
    L = 116.0 * f_xyz[..., 1] - 16.0
    a = 500.0 * (f_xyz[..., 0] - f_xyz[..., 1])
    b = 200.0 * (f_xyz[..., 1] - f_xyz[..., 2])
    return np.stack([L, a, b], axis=-1)


def _srgb_to_linear_np(rgb_0_255: np.ndarray) -> np.ndarray:
    """sRGB (0-255) → linear-light RGB in [0, 1]. Standard piecewise gamma."""
    arr = (rgb_0_255.astype(np.float32) / 255.0).copy()
    mask = arr > SRGB_LINEAR_THRESHOLD
    arr[mask] = np.power(
        (arr[mask] + SRGB_GAMMA_OFFSET) / SRGB_GAMMA_SLOPE, SRGB_GAMMA_EXPONENT
    )
    arr[~mask] /= SRGB_LINEAR_SLOPE
    return arr


def _linear_to_oklab_np(lin_rgb: np.ndarray) -> np.ndarray:
    """Linear-light RGB → OkLab (CIELAB-shoulder variant).

    Pure cube-root OkLab amplifies tiny linear-RGB deltas in the near-black
    region, which makes noisy near-black source pixels (e.g. (20, 20, 25))
    score "closer" to dark-chroma palette entries than to a pure-black
    palette entry. We graft the CIELAB linear segment onto the cube-root for
    LMS values below LAB_DELTA_CUBED, then rescale L so black→0, white→1.
    a/b are unaffected (M2 rows 1 and 2 sum to 0).
    """
    lms = np.maximum(lin_rgb @ OKLAB_M1.T, 0.0)
    f_lms = np.where(
        lms > LAB_DELTA_CUBED,
        np.cbrt(lms),
        LAB_F_SLOPE * lms + LAB_F_OFFSET,
    )
    lab = f_lms @ OKLAB_M2.T
    lab[..., 0] = (lab[..., 0] - LAB_F_OFFSET) / (1.0 - LAB_F_OFFSET)
    return lab


def rgb_to_oklab(rgb_0_255: np.ndarray) -> np.ndarray:
    """Convert sRGB (0-255) to OkLab — perceptually uniform color space."""
    return _linear_to_oklab_np(_srgb_to_linear_np(rgb_0_255))


# Pre-compute inverse matrices once; ramp construction calls these in inner loops.
OKLAB_M1_INV = np.linalg.inv(OKLAB_M1.astype(np.float64)).astype(np.float32)
OKLAB_M2_INV = np.linalg.inv(OKLAB_M2.astype(np.float64)).astype(np.float32)


def _oklab_to_linear_np(lab: np.ndarray) -> np.ndarray:
    """OkLab (CIELAB-shoulder variant) → linear-light RGB. Inverse of `_linear_to_oklab_np`."""
    lab_raw = lab.copy()
    lab_raw[..., 0] = lab_raw[..., 0] * (1.0 - LAB_F_OFFSET) + LAB_F_OFFSET
    f_lms = lab_raw @ OKLAB_M2_INV.T
    # Forward used cbrt when lms > δ³, equivalently f_lms > δ.
    lms = np.where(
        f_lms > LAB_DELTA,
        f_lms ** 3,
        (f_lms - LAB_F_OFFSET) / LAB_F_SLOPE,
    )
    lin = lms @ OKLAB_M1_INV.T
    return np.clip(lin, 0.0, None)


def _linear_to_srgb_np(lin: np.ndarray) -> np.ndarray:
    """Linear-light RGB [0, 1] → sRGB [0, 1]. Inverse of `_srgb_to_linear_np` (sans 255 scale)."""
    lin = np.clip(lin, 0.0, 1.0)
    out = np.where(
        lin <= SRGB_LINEAR_THRESHOLD_INV,
        lin * SRGB_LINEAR_SLOPE,
        SRGB_GAMMA_SLOPE * np.power(np.maximum(lin, 0.0), 1.0 / SRGB_GAMMA_EXPONENT)
        - SRGB_GAMMA_OFFSET,
    )
    return out


def _oklab_to_rgb_255_np(lab: np.ndarray) -> np.ndarray:
    """OkLab → sRGB 0-255. Round-trip pair of `rgb_to_oklab`."""
    lin = _oklab_to_linear_np(lab)
    srgb = _linear_to_srgb_np(lin)
    return np.clip(srgb * 255.0, 0.0, 255.0).astype(np.float32)


def _torch_rgb_to_oklab(rgb_0_1: torch.Tensor) -> torch.Tensor:
    """sRGB [0, 1] → OkLab (CIELAB-shoulder variant) on the input tensor's device.

    Mirrors `_linear_to_oklab_np`: linear shoulder for LMS < LAB_DELTA_CUBED so
    near-black source pixels don't blow up perceptually and lose to dark-chroma
    palette entries. L is rescaled so black→0, white→1.
    """
    lin = _torch_srgb_to_linear(rgb_0_1.clamp(0.0, 1.0))
    M1 = torch.as_tensor(OKLAB_M1, dtype=rgb_0_1.dtype, device=rgb_0_1.device)
    lms = (lin @ M1.T).clamp_min(0.0)
    high = lms.pow(1.0 / 3.0)
    low = LAB_F_SLOPE * lms + LAB_F_OFFSET
    f_lms = torch.where(lms > LAB_DELTA_CUBED, high, low)
    M2 = torch.as_tensor(OKLAB_M2, dtype=rgb_0_1.dtype, device=rgb_0_1.device)
    lab = f_lms @ M2.T
    L = (lab[..., 0:1] - LAB_F_OFFSET) / (1.0 - LAB_F_OFFSET)
    return torch.cat([L, lab[..., 1:]], dim=-1)


# --- Tensor utilities --------------------------------------------------------


def _checkerboard_np(h: int, w: int, tile: int = 8,
                     c1: float = 0.85, c2: float = 0.65) -> np.ndarray:
    """Return an (h, w, 3) float32 checkerboard background in [0, 1]."""
    yy, xx = np.indices((h, w))
    pat = ((yy // tile) + (xx // tile)) % 2
    base = np.where(pat == 0, c1, c2).astype(np.float32)
    return np.stack([base, base, base], axis=-1)


# --- Blue-noise mask (Ulichney void-and-cluster) -----------------------------


def _build_blue_noise_mask(size: int = BLUE_NOISE_SIZE,
                           sigma: float = 1.5,
                           seed: int = BLUE_NOISE_SEED) -> np.ndarray:
    """Generate a blue-noise threshold mask via void-and-cluster (Ulichney 1993).

    Returns an (size, size) float32 array with values in (0, 1), tileable.
    Computed once at module load and cached.
    """
    rng = np.random.RandomState(seed)
    n = size * size

    # Toroidal Gaussian energy filter via FFT.
    yy, xx = np.indices((size, size))
    dy = np.minimum(yy, size - yy)
    dx = np.minimum(xx, size - xx)
    kernel = np.exp(-(dx ** 2 + dy ** 2) / (2.0 * sigma ** 2)).astype(np.float32)
    kernel_fft = np.fft.fft2(kernel)

    def energy(p: np.ndarray) -> np.ndarray:
        return np.real(np.fft.ifft2(np.fft.fft2(p.astype(np.float32)) * kernel_fft))

    initial_count = max(1, n // 10)
    pattern = np.zeros((size, size), dtype=bool)
    pattern.flat[rng.choice(n, size=initial_count, replace=False)] = True

    # Phase 0: redistribute initial pattern until tightest-cluster pixel
    # is also the largest void after removal (stable point).
    for _ in range(n):  # bounded iteration
        e = energy(pattern)
        ty, tx = np.unravel_index(
            np.argmax(np.where(pattern, e, -np.inf)), e.shape
        )
        pattern[ty, tx] = False
        e2 = energy(pattern)
        vy, vx = np.unravel_index(
            np.argmin(np.where(~pattern, e2, np.inf)), e2.shape
        )
        pattern[vy, vx] = True
        if (ty, tx) == (vy, vx):
            break

    initial = pattern.copy()
    rank = np.full((size, size), -1, dtype=np.int32)

    # Phase 1: from initial, iteratively remove tightest cluster, ranking down to 0.
    p = initial.copy()
    for r in range(initial_count - 1, -1, -1):
        e = energy(p)
        ty, tx = np.unravel_index(np.argmax(np.where(p, e, -np.inf)), e.shape)
        p[ty, tx] = False
        rank[ty, tx] = r

    # Phase 2: from initial, iteratively fill largest void up to n//2.
    p = initial.copy()
    for r in range(initial_count, n // 2):
        e = energy(p)
        vy, vx = np.unravel_index(np.argmin(np.where(~p, e, np.inf)), e.shape)
        p[vy, vx] = True
        rank[vy, vx] = r

    # Phase 3: invert and continue ranking remaining majority pixels up to n.
    inv = ~p
    for r in range(n // 2, n):
        e = energy(inv)
        ty, tx = np.unravel_index(np.argmax(np.where(inv, e, -np.inf)), e.shape)
        inv[ty, tx] = False
        rank[ty, tx] = r

    return ((rank.astype(np.float32) + 0.5) / n).astype(np.float32)


_BLUE_NOISE_MASK_CACHE: Optional[np.ndarray] = None


def get_blue_noise_mask() -> np.ndarray:
    """Lazy-cached blue-noise mask (BLUE_NOISE_SIZE x BLUE_NOISE_SIZE, float32 in (0,1))."""
    global _BLUE_NOISE_MASK_CACHE
    if _BLUE_NOISE_MASK_CACHE is None:
        _BLUE_NOISE_MASK_CACHE = _build_blue_noise_mask()
    return _BLUE_NOISE_MASK_CACHE


# --- Hilbert curve traversal -------------------------------------------------


def _hilbert_d2xy(n: int, d: int) -> Tuple[int, int]:
    """Map distance d along a Hilbert curve of order n (n a power of 2) to (x, y)."""
    x, y, t = 0, 0, d
    s = 1
    while s < n:
        rx = 1 & (t // 2)
        ry = 1 & (t ^ rx)
        if ry == 0:
            if rx == 1:
                x = s - 1 - x
                y = s - 1 - y
            x, y = y, x
        x += s * rx
        y += s * ry
        t //= 4
        s *= 2
    return x, y


def hilbert_order(h: int, w: int) -> np.ndarray:
    """Return (N, 2) int32 array of (y, x) coords in Hilbert order, clipped to (h, w)."""
    n = 1
    while n < max(h, w):
        n *= 2
    coords = []
    for d in range(n * n):
        x, y = _hilbert_d2xy(n, d)
        if y < h and x < w:
            coords.append((y, x))
    return np.array(coords, dtype=np.int32)


# --- Mixel-aware block-size detection ---------------------------------------


def _edge_run_lengths(gray: np.ndarray, axis: int, percentile: float) -> np.ndarray:
    """Distances between consecutive strong edges along the given axis.

    axis=1 yields runs corresponding to horizontal block widths (B_w);
    axis=0 yields runs corresponding to vertical block heights (B_h).
    Threshold is the requested percentile of |diff| over non-zero entries —
    flat regions (zero diffs) are excluded so a smooth/solid image yields no
    edges at all rather than a degenerate "all positions are edges" mask.
    """
    if axis == 1:
        diffs = np.abs(np.diff(gray, axis=1))
    else:
        diffs = np.abs(np.diff(gray, axis=0))
    if diffs.size == 0:
        return np.array([], dtype=np.int32)
    nz = diffs[diffs > 0]
    if nz.size == 0:
        return np.array([], dtype=np.int32)
    threshold = float(np.percentile(nz, percentile))
    if threshold <= 0:
        threshold = float(nz.min())
    edges = diffs >= threshold
    runs: list[np.ndarray] = []
    if axis == 1:
        for row in edges:
            idx = np.flatnonzero(row)
            if idx.size >= 2:
                runs.append(np.diff(idx))
    else:
        for c in range(edges.shape[1]):
            idx = np.flatnonzero(edges[:, c])
            if idx.size >= 2:
                runs.append(np.diff(idx))
    if not runs:
        return np.array([], dtype=np.int32)
    return np.concatenate(runs).astype(np.int32)


def _score_block_size(counts: np.ndarray, B: int, max_mult: int) -> int:
    """Sum histogram mass at every multiple of B with +/-MIXEL_TOLERANCE slack."""
    score = 0
    n = len(counts)
    for k in range(1, max_mult + 1):
        center = k * B
        for delta in range(-MIXEL_TOLERANCE, MIXEL_TOLERANCE + 1):
            idx = center + delta
            if 0 <= idx < n:
                score += int(counts[idx])
    return score


def _best_block_for_axis(runs: np.ndarray, max_block: int) -> Optional[int]:
    """Pick the block size whose multiples best explain the run-length histogram.

    Eligibility: raw mass at multiples >= MIN_EDGE_RUNS. Among eligible candidates,
    select the one with highest density (mass / max_mult) — this prefers the
    fundamental period over its divisors, which would otherwise tie on raw mass.
    """
    if runs.size < MIN_EDGE_RUNS:
        return None
    max_len = max_block + MIXEL_TOLERANCE + 1
    runs = runs[(runs >= 1) & (runs <= max_len)]
    if runs.size < MIN_EDGE_RUNS:
        return None
    counts = np.bincount(runs, minlength=max_len + 1)
    n = len(counts)
    best_b: Optional[int] = None
    best_density = 0.0
    for B in range(2, max_block + 1):
        max_mult = (n - 1) // B
        if max_mult < 1:
            continue
        # Reject candidates whose fundamental neighborhood [B-tol, B+tol]
        # peaks somewhere other than B — those are divisors/neighbors stealing
        # mass from the true period via the mixel tolerance window.
        fund_lo = max(0, B - MIXEL_TOLERANCE)
        fund_hi = min(n, B + MIXEL_TOLERANCE + 1)
        fund_window = counts[fund_lo:fund_hi]
        if fund_window.size == 0:
            continue
        if fund_lo + int(np.argmax(fund_window)) != B:
            continue
        raw = _score_block_size(counts, B, max_mult)
        if raw < MIN_EDGE_RUNS:
            continue
        density = raw / max_mult
        if density > best_density:
            best_density = density
            best_b = B
    return best_b


def detect_block_size(chw: torch.Tensor, max_block: int) -> Optional[Tuple[int, int]]:
    """Detect the native pixel block size (B_h, B_w) of an upscaled pixel-art image.

    Returns None when the image lacks a clear edge-grid signature (solid
    colors, smooth gradients, photographic content).
    """
    gray = chw.mean(dim=0).detach().cpu().numpy().astype(np.float32)
    runs_w = _edge_run_lengths(gray, axis=1, percentile=EDGE_PERCENTILE)
    runs_h = _edge_run_lengths(gray, axis=0, percentile=EDGE_PERCENTILE)
    bw = _best_block_for_axis(runs_w, max_block)
    bh = _best_block_for_axis(runs_h, max_block)
    if bw is None or bh is None:
        return None
    return (bh, bw)


def _find_grid_offset(gray: np.ndarray, block: int, axis: int) -> int:
    """Pick the offset in [0, block) that minimizes within-block intensity variance."""
    H, W = gray.shape
    best_off = 0
    min_var = float("inf")
    for off in range(block):
        if axis == 0:
            n = (H - off) // block
            if n < 2:
                continue
            cropped = gray[off : off + n * block, :]
            blocks = cropped.reshape(n, block, W)
            v = float(blocks.var(axis=1).sum())
        else:
            n = (W - off) // block
            if n < 2:
                continue
            cropped = gray[:, off : off + n * block]
            blocks = cropped.reshape(H, n, block)
            v = float(blocks.var(axis=2).sum())
        if v < min_var:
            min_var = v
            best_off = off
    return best_off


def _block_pool(chw: torch.Tensor, bh: int, bw: int, oy: int, ox: int) -> torch.Tensor:
    """Crop to a multiple of (bh, bw) starting at (oy, ox), then mean-pool blocks."""
    C, H, W = chw.shape
    out_h = (H - oy) // bh
    out_w = (W - ox) // bw
    if out_h < 1 or out_w < 1:
        return chw
    cropped = chw[:, oy : oy + out_h * bh, ox : ox + out_w * bw]
    return cropped.reshape(C, out_h, bh, out_w, bw).mean(dim=(2, 4)).contiguous()


# --- Palette image input -----------------------------------------------------


def _snap_palette_size(n: int) -> int:
    """Snap n to the nearest valid palette count: {2} ∪ {4, 8, 12, 16, ...}.

    n=1 or 2 → 2 (1-bit). Otherwise round-half-up to nearest multiple of 4
    (min 4). Round-half-up (not banker's) so halfway cases like 6 → 8 rather
    than 4, biasing toward more color fidelity.
    """
    if n <= 2:
        return 2
    snapped = ((n + 2) // 4) * 4
    return max(4, snapped)


def _unique_colors_from_palette_image(palette_bhwc: torch.Tensor) -> np.ndarray:
    """8-bit-quantized, deduplicated RGB colors from a palette IMAGE tensor."""
    flat = palette_bhwc.detach().cpu().numpy().reshape(-1, 3) * 255.0
    flat_u8 = np.clip(np.rint(flat), 0, 255).astype(np.uint8)
    return np.unique(flat_u8, axis=0).astype(np.float32)


def _cluster_palette_to_target(palette: np.ndarray, target: int,
                               seed: int = 0) -> np.ndarray:
    """Reduce palette (N, 3) float32 to exactly `target` rows via MiniBatchKMeans.

    No-op when len(palette) <= target.
    """
    if len(palette) <= target:
        return palette
    with _suppress_kmeans_convergence():
        kmeans = MiniBatchKMeans(
            n_clusters=target,
            batch_size=KMEANS_BATCH,
            n_init=KMEANS_N_INIT,
            random_state=seed,
        ).fit(palette)
    return np.clip(kmeans.cluster_centers_, 0.0, 255.0).astype(np.float32)


def _detect_solid_background(
    img_255_hwc: torch.Tensor,
) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
    """Detect a dominant near-uniform background via a 3D RGB histogram.

    A 16-bin-per-channel histogram is built over the (downscaled) image. If the
    top bucket holds at least BG_DOMINANCE_THRESHOLD of all pixels, its mean
    color is taken as the BG color and an OkLab-distance mask defines which
    pixels belong to the BG. Returns (bg_rgb_255 shape (3,), bg_mask_HW bool)
    or (None, None) when no dominant region is found.
    """
    arr = img_255_hwc.detach().cpu().numpy()
    H, W, _ = arr.shape
    flat = arr.reshape(-1, 3).astype(np.float32)
    n = flat.shape[0]
    if n == 0:
        return None, None

    bins = BG_HIST_BINS
    q = np.clip((flat / 256.0 * bins).astype(np.int32), 0, bins - 1)
    keys = q[:, 0] * bins * bins + q[:, 1] * bins + q[:, 2]
    counts = np.bincount(keys, minlength=bins ** 3)
    top_key = int(np.argmax(counts))
    top_count = int(counts[top_key])
    if top_count < BG_DOMINANCE_THRESHOLD * n:
        return None, None

    bg_mean = flat[keys == top_key].mean(axis=0)
    bg_oklab = rgb_to_oklab(bg_mean.reshape(1, 3))[0]
    flat_oklab = rgb_to_oklab(flat)
    d2 = np.sum((flat_oklab - bg_oklab) ** 2, axis=1)
    mask = (d2 < BG_OKLAB_TOLERANCE ** 2).reshape(H, W)
    return bg_mean.astype(np.float32), mask


def _sobel_grad(channel_1chw: torch.Tensor) -> torch.Tensor:
    """Sobel magnitude on a 1×1×H×W tensor; returns HW gradient magnitudes."""
    kx = torch.tensor(
        [[-1.0, 0.0, 1.0], [-2.0, 0.0, 2.0], [-1.0, 0.0, 1.0]],
        dtype=channel_1chw.dtype, device=channel_1chw.device,
    ).view(1, 1, 3, 3)
    ky = kx.transpose(2, 3)
    gx = F.conv2d(channel_1chw, kx, padding=1)
    gy = F.conv2d(channel_1chw, ky, padding=1)
    return (gx * gx + gy * gy).sqrt().squeeze(0).squeeze(0)


def _compute_smooth_mask(
    img_255_hwc: torch.Tensor, threshold: float
) -> torch.Tensor:
    """Boolean HW mask: True where pixels are in a smooth-gradient region.

    Combines three signals on the OkLab L* channel:
      • local 3×3 std-dev BELOW `threshold`  (region is locally flat)
      • local 3×3 range ABOVE `2*threshold`  (region has meaningful tonal change)
      • Sobel-magnitude BELOW the EDGE_PERCENTILE threshold (not a sharp edge)

    Returns a HW bool tensor; True = eligible for dithering. Subjects (sharp
    interior shading, strong silhouettes) get False so dither stays off them.
    """
    img = img_255_hwc.clamp(0.0, 255.0) / 255.0
    L = _torch_rgb_to_oklab(img)[..., 0]            # HW
    Lh = L.unsqueeze(0).unsqueeze(0)                # 1×1×H×W

    mean = F.avg_pool2d(Lh, 3, stride=1, padding=1)
    sqmean = F.avg_pool2d(Lh * Lh, 3, stride=1, padding=1)
    std = (sqmean - mean * mean).clamp_min(0.0).sqrt()

    lmax = F.max_pool2d(Lh, 3, stride=1, padding=1)
    lmin = -F.max_pool2d(-Lh, 3, stride=1, padding=1)
    rng = lmax - lmin

    grad = _sobel_grad(Lh)
    edge_thr = torch.quantile(grad.flatten(), EDGE_PERCENTILE / 100.0)
    edge = grad > edge_thr

    smooth = (
        (std.squeeze(0).squeeze(0) < threshold)
        & (rng.squeeze(0).squeeze(0) > 2.0 * threshold)
        & ~edge
    )
    return smooth


def _compute_outline_mask(
    img_255_hwc: torch.Tensor,
    bg_mask: Optional[np.ndarray],
) -> torch.Tensor:
    """Boolean HW mask: True where this pixel sits on the dark side of a strong source edge.

    Detection: Sobel magnitude on grayscale, threshold at EDGE_PERCENTILE. The
    "dark side" filter (gray < local mean) ensures only one side of each edge
    is darkened — preventing double-thickness outlines. BG mask is excluded so
    the background never gets outlined regardless of how strong its edges are.
    """
    img = img_255_hwc.clamp(0.0, 255.0) / 255.0
    gray = img.mean(dim=-1)                          # HW
    gh = gray.unsqueeze(0).unsqueeze(0)              # 1×1×H×W

    grad = _sobel_grad(gh)
    edge_thr = torch.quantile(grad.flatten(), EDGE_PERCENTILE / 100.0)
    edge = grad > edge_thr

    local_mean = F.avg_pool2d(gh, 3, stride=1, padding=1).squeeze(0).squeeze(0)
    dark_side = gray < local_mean

    mask = edge & dark_side
    if bg_mask is not None:
        bg_t = torch.from_numpy(bg_mask).to(device=mask.device)
        mask = mask & ~bg_t
    return mask


def _apply_outline(
    img_255: torch.Tensor,
    palette_np: np.ndarray,
    outline_mask: torch.Tensor,
    outline_steps: int,
) -> torch.Tensor:
    """Darken outline-mask pixels by N palette ranks in OkLab L*.

    Operates in palette-index space so output stays on-palette regardless of
    which palette is in use (k-means, ramps_oklab, palette image). For each
    edge pixel: find its current palette index → step to the rank that is
    `outline_steps` darker (clamped to the darkest entry).
    """
    n_palette = palette_np.shape[0]
    if n_palette <= 1 or outline_steps <= 0:
        return img_255
    if not bool(outline_mask.any()):
        return img_255

    palette_t = torch.from_numpy(palette_np).to(
        device=img_255.device, dtype=img_255.dtype
    )
    palette_oklab = _torch_rgb_to_oklab(palette_t / 255.0)
    L = palette_oklab[:, 0]
    order = torch.argsort(L)                              # ascending L*
    inv = torch.empty_like(order)
    inv[order] = torch.arange(n_palette, device=order.device)

    flat = img_255.reshape(-1, 3)
    flat_oklab = _torch_rgb_to_oklab(flat / 255.0)
    d2 = torch.cdist(flat_oklab, palette_oklab) ** 2
    nearest = torch.argmin(d2, dim=1)                     # HW (flattened)
    ranked = inv[nearest]
    darker_ranked = (ranked - outline_steps).clamp(min=0)
    new_idx = order[darker_ranked]

    H, W, _ = img_255.shape
    new_idx_hw = new_idx.view(H, W)
    out = img_255.clone()
    out[outline_mask] = palette_t[new_idx_hw[outline_mask]]
    return out


# --- Node --------------------------------------------------------------------


class RayPixelArtDetector:
    """ComfyUI node: pixel-art downscale + palette reduction with palette preview."""

    DESCRIPTION = (
        "Pixel-art conversion pipeline. Downscales (manual target size or "
        "auto pixel-size detection), reduces palette (kmeans-Lab, "
        "kmeans-RGB, quantize, or OkLab hue-ramps), optional dithering "
        "(Bayer 2/4/8, blue-noise, Riemersma, Knoll), silhouette outline, "
        "and highlight protection.\n\n"
        "Attach a `palette_image` to force a fixed palette — snaps to "
        "{2}∪{4·k} colors and bypasses source clustering. Emits both the "
        "reduced image and a hue-sorted palette swatch grid."
    )

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE", {"tooltip": "Source image."}),
                "mode": (
                    [
                        "manual_resize",
                        "auto_downscale_loose",
                        "auto_downscale_strict",
                        "auto_pixel_size",
                    ],
                    {"default": "manual_resize",
                     "tooltip": "How to size the pixel grid."},
                ),
                "target_resolution": ("INT", {"default": 128, "min": 32, "max": 2048, "step": 8,
                                              "tooltip": "Target longest side in manual mode."}),
                "max_downscale_factor": ("INT", {"default": 16, "min": 2, "max": 64,
                                                 "tooltip": "Cap for auto downscale modes."}),
                "reduce_palette": ("BOOLEAN", {"default": True,
                                                "tooltip": "Run palette reduction."}),
                "max_colors": ("INT", {"default": 32, "min": 2, "max": 256,
                                       "tooltip": "Palette-size target."}),
                "palette_strategy": (
                    ["kmeans_lab", "kmeans_rgb", "quantize_simple", "ramps_oklab"],
                    {"default": "kmeans_lab",
                     "tooltip": "Palette-reduction algorithm."},
                ),
                "ramp_levels": ([3, 4, 5], {"default": RAMP_LEVELS_DEFAULT,
                                             "tooltip": "L* levels per cluster (ramps_oklab)."}),
                "protect_highlights": ("BOOLEAN", {"default": True,
                                                    "tooltip": "Reserve a slot for near-white highlights."}),
                "highlight_threshold": ("INT", {"default": 90, "min": 50, "max": 100,
                                                 "tooltip": "L* cutoff for highlight protection."}),
                "dither": (
                    [
                        "none",
                        "bayer_2x2",
                        "bayer_4x4",
                        "bayer_8x8",
                        "blue_noise",
                        "riemersma",
                        "knoll",
                    ],
                    {"default": "none",
                     "tooltip": "Dither kernel."},
                ),
                "selective_dither": ("BOOLEAN", {"default": False,
                                                  "tooltip": "Restrict dither to non-smooth regions."}),
                "dither_smooth_threshold": (
                    "FLOAT",
                    {"default": DITHER_SMOOTH_THRESHOLD_DEFAULT,
                     "min": 0.0, "max": 0.30, "step": 0.005,
                     "tooltip": "OkLab L* std cutoff for smooth-region detection."},
                ),
                "silhouette_outline": ("BOOLEAN", {"default": False,
                                                    "tooltip": "Darken silhouette edges by N palette ranks."}),
                "outline_steps": (
                    "INT",
                    {"default": OUTLINE_STEPS_DEFAULT, "min": 1, "max": 3,
                     "tooltip": "Palette-rank steps for the outline."},
                ),
                "seed": ("INT", {
                    "default": -1, "min": -1, "max": 2**31 - 1,
                    "tooltip": "-1 for random; any >=0 value is reproducible.",
                }),
            },
            "optional": {
                "palette_image": ("IMAGE", {"tooltip": "Optional fixed palette source."}),
            },
        }

    RETURN_TYPES = ("IMAGE", "IMAGE")
    RETURN_NAMES = ("pixel_art", "palette_preview")
    OUTPUT_TOOLTIPS = (
        "Pixel-art reduced image at the chosen resolution.",
        "Hue-sorted swatch grid of the final palette.",
    )
    FUNCTION = "process"
    CATEGORY = "👑 Ray/✨ VFX"

    # --- Public entry point --------------------------------------------------

    def process(
        self,
        image: torch.Tensor,
        mode: str,
        target_resolution: int,
        max_downscale_factor: int,
        reduce_palette: bool,
        max_colors: int,
        palette_strategy: str,
        protect_highlights: bool,
        highlight_threshold: int,
        dither: str,
        seed: int = 0,
        palette_image: Optional[torch.Tensor] = None,
        ramp_levels: int = RAMP_LEVELS_DEFAULT,
        selective_dither: bool = False,
        dither_smooth_threshold: float = DITHER_SMOOTH_THRESHOLD_DEFAULT,
        silhouette_outline: bool = False,
        outline_steps: int = OUTLINE_STEPS_DEFAULT,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        image = normalize_image(image)
        device, dtype = image.device, image.dtype

        # Normalize seed sentinel (-1 = OS-random) into a valid sklearn
        # random_state before threading it through the palette pipeline.
        if seed is None or int(seed) < 0:
            import secrets
            seed = int(secrets.randbits(31))
        else:
            seed = int(seed)

        # Palette-image override: extract a fixed palette, snap to {2}∪{4k},
        # force reduce_palette True, and skip source-derived clustering.
        fixed_palette: Optional[np.ndarray] = None
        if palette_image is not None:
            palette_norm = normalize_image(palette_image)
            unique = _unique_colors_from_palette_image(palette_norm)
            target = _snap_palette_size(len(unique))
            fixed_palette = _cluster_palette_to_target(unique, target, seed=seed)
            reduce_palette = True
            max_colors = len(fixed_palette)

        pixel_results: list[torch.Tensor] = []
        palette_results: list[torch.Tensor] = []

        for hwc in image:
            chw = hwc.permute(2, 0, 1).contiguous()
            chw_down = self._downscale(chw, mode, target_resolution, max_downscale_factor)

            # Move to HWC in 0-255 space for palette work.
            img_255 = chw_down.permute(1, 2, 0).contiguous() * 255.0

            # Solid-BG detection happens on the clean downscaled image, before
            # pre-noise dither, so noise never affects the mask. Only meaningful
            # when palette reduction will run — otherwise the BG override has
            # no palette to snap to.
            bg_color: Optional[np.ndarray] = None
            bg_mask: Optional[np.ndarray] = None
            if reduce_palette:
                bg_color, bg_mask = _detect_solid_background(img_255)

            # Selective dithering mask: computed once on the clean image so
            # neither pre-noise nor coupled dither paths can pollute the mask.
            smooth_mask: Optional[torch.Tensor] = None
            if reduce_palette and selective_dither and dither != "none":
                smooth_mask = _compute_smooth_mask(img_255, dither_smooth_threshold)

            # Silhouette outline mask (Feature B): also captured on clean image.
            outline_mask: Optional[torch.Tensor] = None
            if reduce_palette and silhouette_outline:
                outline_mask = _compute_outline_mask(img_255, bg_mask)

            if dither in PRE_NOISE_DITHERS:
                img_255 = self._apply_pre_noise_dither(
                    img_255, dither, smooth_mask=smooth_mask
                )

            palette_np: Optional[np.ndarray] = None
            if reduce_palette:
                if fixed_palette is not None:
                    palette_np = fixed_palette
                else:
                    palette_np = self._compute_palette(
                        img_255,
                        palette_strategy,
                        max_colors,
                        protect_highlights,
                        highlight_threshold,
                        seed,
                        ramp_levels=ramp_levels,
                    )
                palette_np = np.clip(palette_np, 0.0, 255.0).astype(np.float32)

                if dither == "knoll":
                    if smooth_mask is not None:
                        flat_img = self._map_to_palette(img_255, palette_np)
                        dith_img = self._knoll_map(img_255, palette_np)
                        img_255 = torch.where(
                            smooth_mask.unsqueeze(-1), dith_img, flat_img
                        )
                    else:
                        img_255 = self._knoll_map(img_255, palette_np)
                elif dither == "riemersma":
                    if smooth_mask is not None:
                        flat_img = self._map_to_palette(img_255, palette_np)
                        dith_img = self._riemersma_map(img_255, palette_np)
                        img_255 = torch.where(
                            smooth_mask.unsqueeze(-1), dith_img, flat_img
                        )
                    else:
                        img_255 = self._riemersma_map(img_255, palette_np)
                else:
                    img_255 = self._map_to_palette(img_255, palette_np)

                # Override BG mask with the single perceptually-closest palette
                # entry. This guarantees: BG never speckles from dither, and
                # noisy near-uniform regions snap to one consistent color.
                if bg_color is not None and bg_mask is not None:
                    bg_oklab = rgb_to_oklab(bg_color.reshape(1, 3))[0]
                    pal_oklab = rgb_to_oklab(palette_np)
                    idx = int(np.argmin(np.sum((pal_oklab - bg_oklab) ** 2, axis=1)))
                    bg_pal_t = torch.from_numpy(palette_np[idx]).to(
                        device=img_255.device, dtype=img_255.dtype
                    )
                    mask_t = torch.from_numpy(bg_mask).to(device=img_255.device)
                    img_255[mask_t] = bg_pal_t

                # Silhouette outline pass — runs after BG override so the BG
                # itself is never outlined (outline_mask was already AND'ed
                # with ~bg_mask, but BG override could still introduce edges).
                if outline_mask is not None:
                    img_255 = _apply_outline(
                        img_255, palette_np, outline_mask, outline_steps
                    )

            pixel_results.append((img_255 / 255.0).clamp(0.0, 1.0).to(dtype=dtype, device=device))
            palette_results.append(self._render_palette_preview(palette_np))

        palette_results = self._unify_palette_grids(palette_results)
        return torch.stack(pixel_results), torch.stack(palette_results)

    # --- Downscaling ---------------------------------------------------------

    def _downscale(
        self,
        chw: torch.Tensor,
        mode: str,
        target_resolution: int,
        max_downscale_factor: int,
    ) -> torch.Tensor:
        """Pick a downscale strategy based on mode and run it."""
        _, H, W = chw.shape
        if mode == "manual_resize":
            scale = target_resolution / max(H, W)
            new_h = max(1, int(round(H * scale)))
            new_w = max(1, int(round(W * scale)))
            return F.interpolate(
                chw.unsqueeze(0), size=(new_h, new_w), mode="area"
            ).squeeze(0)

        if mode == "auto_pixel_size":
            result = self._auto_pixel_size_downscale(chw, max_downscale_factor)
            if result is not None:
                return result
            mode = "auto_downscale_strict"

        threshold = AUTO_THRESHOLDS["loose" if "loose" in mode else "strict"]
        best_factor = 1
        for k in range(int(max_downscale_factor), 1, -1):
            if k > min(H, W):
                continue
            if self._reconstruction_error(chw, k) < threshold:
                best_factor = k
                break
        if best_factor == 1:
            return chw
        return self._phase_aware_downscale(chw, best_factor)

    @staticmethod
    def _reconstruction_error(chw: torch.Tensor, factor: int) -> float:
        """Mean abs error of nearest-neighbor reconstruction at given factor."""
        _, H, W = chw.shape
        down = chw[:, ::factor, ::factor].unsqueeze(0)
        up = F.interpolate(down, size=(H, W), mode="nearest").squeeze(0)
        return torch.mean(torch.abs(chw - up)).item()

    @staticmethod
    def _phase_aware_downscale(chw: torch.Tensor, factor: int) -> torch.Tensor:
        """Pick the lowest-edge-energy phase among 4 stride offsets.

        Note: samples 4 of factor**2 possible offsets — a quarter-phase
        approximation. Sufficient in practice and bounded in cost.
        """
        offsets = [
            (0, 0),
            (factor // 2, factor // 2),
            (0, factor // 2),
            (factor // 2, 0),
        ]
        best_img: Optional[torch.Tensor] = None
        min_score = float("inf")
        for oy, ox in offsets:
            sliced = chw[:, oy::factor, ox::factor]
            if sliced.shape[1] < 2 or sliced.shape[2] < 2:
                continue
            edge = (
                torch.sum(torch.abs(sliced[:, :, :-1] - sliced[:, :, 1:]))
                + torch.sum(torch.abs(sliced[:, :-1, :] - sliced[:, 1:, :]))
            )
            score = edge.item() / (sliced.shape[1] * sliced.shape[2])
            if score < min_score:
                min_score = score
                best_img = sliced
        if best_img is None:
            return chw[:, ::factor, ::factor]
        return best_img.contiguous()

    @staticmethod
    def _auto_pixel_size_downscale(
        chw: torch.Tensor, max_downscale_factor: int
    ) -> Optional[torch.Tensor]:
        """Detect native pixel block from edge geometry, then phase-aligned mean-pool.

        Returns None when the image lacks a clear edge-grid signature; caller
        should fall back to an alternative downscale strategy.
        """
        detected = detect_block_size(chw, max_downscale_factor)
        if detected is None:
            return None
        bh, bw = detected
        gray = chw.mean(dim=0).detach().cpu().numpy().astype(np.float32)
        oy = _find_grid_offset(gray, bh, axis=0)
        ox = _find_grid_offset(gray, bw, axis=1)
        return _block_pool(chw, bh, bw, oy, ox)

    # --- Dither --------------------------------------------------------------

    @staticmethod
    def _apply_pre_noise_dither(
        img_255_hwc: torch.Tensor,
        kind: str,
        smooth_mask: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        """Apply a tileable threshold mask as additive noise in 0-255 space.

        Supports bayer_2x2, bayer_4x4, bayer_8x8, blue_noise. Stays on device.
        If `smooth_mask` (HW bool) is given, additive noise is zeroed outside
        the mask — pixels failing the smooth-region test see no dither.
        """
        if kind == "bayer_2x2":
            m_np = BAYER_2X2
        elif kind == "bayer_4x4":
            m_np = BAYER_4X4
        elif kind == "bayer_8x8":
            m_np = BAYER_8X8
        elif kind == "blue_noise":
            m_np = get_blue_noise_mask()
        else:
            return img_255_hwc
        m = torch.from_numpy(m_np).to(device=img_255_hwc.device, dtype=img_255_hwc.dtype)
        h, w, _ = img_255_hwc.shape
        rep_y = (h + m.shape[0] - 1) // m.shape[0]
        rep_x = (w + m.shape[1] - 1) // m.shape[1]
        tiled = m.repeat(rep_y, rep_x)[:h, :w]
        additive = (tiled.unsqueeze(-1) - 0.5) * DITHER_AMPLITUDE
        if smooth_mask is not None:
            additive = additive * smooth_mask.unsqueeze(-1).to(dtype=additive.dtype)
        return torch.clamp(img_255_hwc + additive, 0.0, 255.0)

    # --- Palette -------------------------------------------------------------

    def _compute_palette(
        self,
        img_255: torch.Tensor,
        strategy: str,
        max_colors: int,
        protect_highlights: bool,
        highlight_threshold: int,
        seed: int,
        ramp_levels: int = RAMP_LEVELS_DEFAULT,
    ) -> np.ndarray:
        """Cluster pixels into <= max_colors entries; return the palette only."""
        flat_rgb_np = img_255.detach().cpu().numpy().reshape(-1, 3)

        if strategy == "kmeans_lab":
            palette = self._kmeans_lab(
                flat_rgb_np, max_colors, protect_highlights, highlight_threshold, seed
            )
        elif strategy == "kmeans_rgb":
            k = max(1, min(max_colors, len(flat_rgb_np)))
            with _suppress_kmeans_convergence():
                kmeans = MiniBatchKMeans(
                    n_clusters=k,
                    batch_size=KMEANS_BATCH,
                    n_init=KMEANS_N_INIT,
                    random_state=seed,
                ).fit(flat_rgb_np)
            palette = kmeans.cluster_centers_.astype(np.float32)
        elif strategy == "ramps_oklab":
            palette = self._kmeans_ramps(flat_rgb_np, max_colors, ramp_levels, seed)
        else:  # quantize_simple
            palette = self._quantize_simple(flat_rgb_np, max_colors, seed)
        return palette

    @staticmethod
    def _kmeans_lab(
        flat_rgb_np: np.ndarray,
        max_colors: int,
        protect_highlights: bool,
        highlight_threshold: int,
        seed: int,
    ) -> np.ndarray:
        flat_lab = rgb_to_lab(flat_rgb_np)
        reserved: list[np.ndarray] = []
        training_lab, training_rgb, k_target = flat_lab, flat_rgb_np, max_colors

        if protect_highlights and k_target > 1:
            mask = flat_lab[:, 0] > highlight_threshold
            n_high = int(np.sum(mask))
            if n_high > 0:
                reserved.append(np.mean(flat_rgb_np[mask], axis=0))
                training_lab = flat_lab[~mask]
                training_rgb = flat_rgb_np[~mask]
                k_target -= 1
                if len(training_lab) == 0:
                    return np.array(reserved, dtype=np.float32)

        k = max(1, min(k_target, len(training_lab)))
        with _suppress_kmeans_convergence():
            kmeans = MiniBatchKMeans(
                n_clusters=k,
                batch_size=KMEANS_BATCH,
                n_init=KMEANS_N_INIT,
                random_state=seed,
            ).fit(training_lab)

        # Compute mean RGB for each non-empty cluster (drop empty ones rather
        # than injecting black).
        clusters_rgb: list[np.ndarray] = []
        for i in range(k):
            members = training_rgb[kmeans.labels_ == i]
            if len(members):
                clusters_rgb.append(members.mean(axis=0))

        if reserved and clusters_rgb:
            return np.vstack([np.array(reserved), np.array(clusters_rgb)]).astype(np.float32)
        if reserved:
            return np.array(reserved, dtype=np.float32)
        if clusters_rgb:
            return np.array(clusters_rgb, dtype=np.float32)
        # Degenerate fallback: image was entirely uniform.
        return flat_rgb_np[:1].astype(np.float32)

    @staticmethod
    def _kmeans_ramps(
        flat_rgb_np: np.ndarray,
        max_colors: int,
        ramp_levels: int,
        seed: int,
    ) -> np.ndarray:
        """Build a palette of K hue/chroma ramps × M lightness levels.

        Cluster on OkLab (a, b) only — chroma/hue. Within each cluster pick M
        L* values by even spacing across [5th pct, 95th pct] of the cluster's
        L*. Reconstruct RGB via inverse OkLab. Result palette has at most
        K * M rows where K = ceil(max_colors / M). Highlight reservation is
        implicit: the brightest L* in each ramp acts as that hue's highlight.
        """
        if len(flat_rgb_np) == 0:
            return flat_rgb_np[:1].astype(np.float32)
        M = max(2, int(ramp_levels))
        K_target = max(1, -(-int(max_colors) // M))  # ceil

        flat_oklab = rgb_to_oklab(flat_rgb_np.astype(np.float32))
        ab = flat_oklab[:, 1:3]
        K = max(1, min(K_target, len(ab)))
        with _suppress_kmeans_convergence():
            kmeans = MiniBatchKMeans(
                n_clusters=K,
                batch_size=KMEANS_BATCH,
                n_init=KMEANS_N_INIT,
                random_state=seed,
            ).fit(ab)

        entries: list[np.ndarray] = []
        for i in range(K):
            mask = kmeans.labels_ == i
            n_members = int(mask.sum())
            if n_members == 0:
                continue
            cluster_ab = kmeans.cluster_centers_[i]
            Ls = flat_oklab[mask, 0]
            lo = float(np.percentile(Ls, 5.0))
            hi = float(np.percentile(Ls, 95.0))
            if hi - lo < 1e-3:
                # Degenerate (near-uniform) cluster — emit the single mean tone.
                levels = np.array([float(Ls.mean())], dtype=np.float32)
            else:
                levels = np.linspace(lo, hi, M, dtype=np.float32)
            for L in levels:
                entries.append(np.array([L, cluster_ab[0], cluster_ab[1]], dtype=np.float32))

        if not entries:
            return flat_rgb_np[:1].astype(np.float32)
        lab_palette = np.stack(entries, axis=0)
        return _oklab_to_rgb_255_np(lab_palette)

    @staticmethod
    def _quantize_simple(flat_rgb_np: np.ndarray, max_colors: int, seed: int) -> np.ndarray:
        """Per-channel bucketing then collapse to <= max_colors total entries."""
        step = max(1, 255 // max_colors)
        bucketed = (flat_rgb_np // step) * step
        unique = np.unique(bucketed.reshape(-1, 3), axis=0)
        if len(unique) <= max_colors:
            return unique.astype(np.float32)
        with _suppress_kmeans_convergence():
            kmeans = MiniBatchKMeans(
                n_clusters=max_colors,
                batch_size=KMEANS_BATCH,
                n_init=KMEANS_N_INIT,
                random_state=seed,
            ).fit(unique.astype(np.float32))
        return kmeans.cluster_centers_.astype(np.float32)

    @staticmethod
    def _map_to_palette(img_255: torch.Tensor, palette_np: np.ndarray) -> torch.Tensor:
        """Map each pixel to its nearest palette color (OkLab distance)."""
        H, W, _ = img_255.shape
        palette_t = torch.from_numpy(palette_np).to(
            device=img_255.device, dtype=img_255.dtype
        )
        flat = img_255.reshape(-1, 3)
        if palette_t.shape[0] == 1:
            return palette_t.expand(H * W, 3).reshape(H, W, 3).clone()

        flat_oklab = _torch_rgb_to_oklab(flat / 255.0)
        palette_oklab = _torch_rgb_to_oklab(palette_t / 255.0)

        indices = torch.empty(flat.shape[0], dtype=torch.long, device=flat.device)
        for start in range(0, flat.shape[0], NN_MAP_CHUNK):
            end = min(start + NN_MAP_CHUNK, flat.shape[0])
            d = torch.cdist(
                flat_oklab[start:end].unsqueeze(0), palette_oklab.unsqueeze(0)
            ).squeeze(0)
            indices[start:end] = torch.argmin(d, dim=1)
        return palette_t[indices].reshape(H, W, 3)

    # --- Coupled dithers (replace nearest-neighbor mapping) -----------------

    @staticmethod
    def _riemersma_map(img_255: torch.Tensor, palette_np: np.ndarray) -> torch.Tensor:
        """Riemersma error-diffusion dither along a Hilbert space-filling curve.

        Error diffusion runs in OkLab so that perceptual error (not raw RGB
        delta) is what gets pushed forward; output remains in sRGB palette
        colors. The Hilbert traversal eliminates the scanline directional
        bias of Floyd-Steinberg.
        """
        H, W, _ = img_255.shape
        img_np = img_255.detach().cpu().numpy().astype(np.float32)
        palette = palette_np.astype(np.float32)
        img_oklab = rgb_to_oklab(img_np)
        palette_oklab = rgb_to_oklab(palette)
        out = np.zeros_like(img_np)

        history = RIEMERSMA_HISTORY
        # Weights: oldest = RIEMERSMA_DECAY_RATIO * newest.
        ratio = RIEMERSMA_DECAY_RATIO ** (1.0 / max(1, history - 1))
        weights = ratio ** np.arange(history - 1, -1, -1, dtype=np.float32)
        weights /= weights.sum()
        err_buf = np.zeros((history, 3), dtype=np.float32)

        order = hilbert_order(H, W)
        for y, x in order:
            target = img_oklab[y, x] + (err_buf * weights[:, None]).sum(0)
            d = np.sum((palette_oklab - target) ** 2, axis=1)
            idx = int(np.argmin(d))
            out[y, x] = palette[idx]
            err_buf = np.roll(err_buf, -1, axis=0)
            err_buf[-1] = img_oklab[y, x] - palette_oklab[idx]
        return torch.from_numpy(out).to(device=img_255.device, dtype=img_255.dtype)

    @staticmethod
    def _knoll_map(img_255: torch.Tensor, palette_np: np.ndarray,
                   matrix_size: int = 4) -> torch.Tensor:
        """Knoll/Yliluoma pattern dither (algorithm 2).

        For each pixel, greedily build a list of M = matrix_size**2 palette
        colors whose running average best approximates the target. Sort the
        list by luminance and select an entry by Bayer threshold at the
        pixel's position. Output uses only palette colors.

        Mixing math is in linear-light RGB (correct for additive subpixel
        averaging), and the distance metric is OkLab (perceptually uniform).
        """
        H, W, _ = img_255.shape
        img_np = img_255.detach().cpu().numpy().astype(np.float32)
        palette = palette_np.astype(np.float32)
        P = palette.shape[0]

        if matrix_size == 8:
            bayer_norm = BAYER_8X8
        elif matrix_size == 2:
            bayer_norm = BAYER_2X2
        else:
            matrix_size = 4
            bayer_norm = BAYER_4X4
        M = matrix_size * matrix_size
        bayer_idx_map = np.rint(bayer_norm * M).astype(np.int32)
        bayer_idx_map = np.clip(bayer_idx_map, 0, M - 1)

        flat = img_np.reshape(-1, 3)
        N = flat.shape[0]
        target_oklab = rgb_to_oklab(flat)                    # (N, 3)
        palette_lin = _srgb_to_linear_np(palette)            # (P, 3) in [0, 1]
        accum_lin = np.zeros((N, 3), dtype=np.float32)
        candidates = np.empty((N, M), dtype=np.int32)

        # Bound peak memory of (chunk, P, 3) array.
        chunk = max(1, KNOLL_CHUNK_BYTES // (P * 3 * 4))
        for i in range(M):
            divisor = float(i + 1)
            for start in range(0, N, chunk):
                end = min(start + chunk, N)
                avg_lin = (
                    accum_lin[start:end, None, :] + palette_lin[None, :, :]
                ) / divisor
                avg_oklab = _linear_to_oklab_np(avg_lin)
                d = ((avg_oklab - target_oklab[start:end, None, :]) ** 2).sum(-1)
                best = np.argmin(d, axis=1).astype(np.int32)
                candidates[start:end, i] = best
                accum_lin[start:end] += palette_lin[best]

        # Sort each pixel's M candidates by luminance.
        palette_lum = palette @ np.array([0.299, 0.587, 0.114], dtype=np.float32)
        cand_lum = palette_lum[candidates]
        sort_idx = np.argsort(cand_lum, axis=1)
        sorted_cands = np.take_along_axis(candidates, sort_idx, axis=1)

        # Threshold position per pixel from Bayer map.
        yy = (np.arange(H).reshape(-1, 1) % matrix_size)
        xx = (np.arange(W).reshape(1, -1) % matrix_size)
        bayer_at_pixel = bayer_idx_map[yy, xx].reshape(-1)
        chosen = sorted_cands[np.arange(N), bayer_at_pixel]
        out = palette[chosen].reshape(H, W, 3)
        return torch.from_numpy(out).to(device=img_255.device, dtype=img_255.dtype)

    # --- Palette preview rendering ------------------------------------------

    @staticmethod
    def _render_palette_preview(palette_np: Optional[np.ndarray]) -> torch.Tensor:
        """Render a hue-sorted swatch grid; pad missing cells with a checkerboard."""
        if palette_np is None or len(palette_np) == 0:
            blank = _checkerboard_np(PALETTE_SWATCH_SIZE, PALETTE_SWATCH_SIZE)
            return torch.from_numpy(blank)

        palette_lab = rgb_to_lab(palette_np)
        lums = palette_lab[:, 0]
        hues = np.arctan2(palette_lab[:, 2], palette_lab[:, 1])
        sort_idx = np.lexsort((-lums, hues))  # primary hue asc, secondary L desc
        sorted_palette = palette_np[sort_idx]

        n = len(sorted_palette)
        cols = min(PALETTE_GRID_COLS, n)
        rows = (n + cols - 1) // cols
        s = PALETTE_SWATCH_SIZE

        grid = _checkerboard_np(rows * s, cols * s)
        for idx, color in enumerate(sorted_palette):
            r, c = idx // cols, idx % cols
            grid[r * s : (r + 1) * s, c * s : (c + 1) * s] = (color / 255.0).astype(np.float32)
        return torch.from_numpy(np.clip(grid, 0.0, 1.0).astype(np.float32))

    @staticmethod
    def _unify_palette_grids(grids: list[torch.Tensor]) -> list[torch.Tensor]:
        """Pad all grid tensors to a common (H, W) so torch.stack succeeds."""
        if not grids:
            return grids
        max_h = max(g.shape[0] for g in grids)
        max_w = max(g.shape[1] for g in grids)
        out: list[torch.Tensor] = []
        for g in grids:
            h, w = g.shape[0], g.shape[1]
            if h == max_h and w == max_w:
                out.append(g)
                continue
            canvas_np = _checkerboard_np(max_h, max_w)
            canvas = torch.from_numpy(canvas_np).to(dtype=g.dtype, device=g.device)
            canvas[:h, :w] = g
            out.append(canvas)
        return out
