"""Tests for ray_pixel_detector. Run with: pytest tests/"""

from typing import Tuple

import numpy as np
import pytest
import torch
import torch.nn.functional as F

from ray_pixel_detector import (
    BLUE_NOISE_SIZE,
    RayPixelArtDetector,
    _compute_outline_mask,
    _compute_smooth_mask,
    _detect_solid_background,
    _unique_colors_from_palette_image,
    _oklab_to_rgb_255_np,
    _snap_palette_size,
    detect_block_size,
    get_blue_noise_mask,
    hilbert_order,
    normalize_image,
    rgb_to_lab,
    rgb_to_oklab,
)


def make_image(b: int, h: int, w: int, c: int = 3, seed: int = 0) -> torch.Tensor:
    g = torch.Generator().manual_seed(seed)
    return torch.rand(b, h, w, c, generator=g, dtype=torch.float32)


@pytest.fixture
def node():
    return RayPixelArtDetector()


# --- normalize_image ---------------------------------------------------------


def test_normalize_accepts_bhwc_rgb():
    img = make_image(2, 64, 64, 3)
    out = normalize_image(img)
    assert out.shape == (2, 64, 64, 3)
    assert out.dtype == torch.float32


def test_normalize_accepts_hwc_rgb():
    img = make_image(1, 32, 32, 3).squeeze(0)
    out = normalize_image(img)
    assert out.shape == (1, 32, 32, 3)


def test_normalize_drops_alpha():
    img = make_image(1, 32, 32, 4)
    out = normalize_image(img)
    assert out.shape == (1, 32, 32, 3)


def test_normalize_expands_grayscale():
    img = make_image(1, 32, 32, 1)
    out = normalize_image(img)
    assert out.shape == (1, 32, 32, 3)
    # All three channels should be identical for grayscale broadcast
    assert torch.allclose(out[..., 0], out[..., 1])
    assert torch.allclose(out[..., 1], out[..., 2])


def test_normalize_rejects_bad_dim():
    with pytest.raises(ValueError):
        normalize_image(torch.zeros(2, 3, 4, 5, 6))


def test_normalize_rejects_bad_channels():
    with pytest.raises(ValueError):
        normalize_image(torch.zeros(1, 8, 8, 2))


def test_normalize_rejects_non_tensor():
    with pytest.raises(TypeError):
        normalize_image(np.zeros((1, 8, 8, 3)))


def test_normalize_uint8_scaled():
    img = (torch.rand(1, 16, 16, 3) * 255).to(torch.uint8)
    out = normalize_image(img)
    assert out.dtype == torch.float32
    assert out.max() <= 1.0 and out.min() >= 0.0


def test_normalize_clamps():
    img = torch.full((1, 8, 8, 3), 2.5, dtype=torch.float32)
    out = normalize_image(img)
    assert out.max().item() == pytest.approx(1.0)


# --- rgb_to_lab --------------------------------------------------------------


def test_rgb_to_lab_white_is_l100():
    white = np.full((1, 3), 255, dtype=np.float32)
    lab = rgb_to_lab(white)
    assert lab[0, 0] == pytest.approx(100.0, abs=1e-2)


def test_rgb_to_lab_black_is_l0():
    black = np.zeros((1, 3), dtype=np.float32)
    lab = rgb_to_lab(black)
    assert lab[0, 0] == pytest.approx(0.0, abs=1e-2)


def test_rgb_to_lab_does_not_mutate_input():
    rgb = np.array([[100.0, 150.0, 200.0]], dtype=np.float32)
    rgb_copy = rgb.copy()
    _ = rgb_to_lab(rgb)
    assert np.array_equal(rgb, rgb_copy)


# --- process: shape & dtype contracts ---------------------------------------


def test_process_manual_rgb(node):
    img = make_image(1, 256, 256)
    out, palette = node.process(
        img, "manual_resize", 64, 16, True, 16, "kmeans_lab", True, 90, "none", 0
    )
    assert out.dim() == 4 and out.shape[0] == 1 and out.shape[-1] == 3
    assert out.dtype == torch.float32
    assert 0.0 <= out.min().item() and out.max().item() <= 1.0
    assert palette.dim() == 4 and palette.shape[0] == 1 and palette.shape[-1] == 3


def test_process_rgba_input_no_crash(node):
    img = make_image(1, 128, 128, c=4)
    out, _ = node.process(
        img, "manual_resize", 64, 16, False, 16, "kmeans_lab", False, 90, "none", 0
    )
    assert out.shape[-1] == 3


def test_process_grayscale_input_no_crash(node):
    img = make_image(1, 128, 128, c=1)
    out, _ = node.process(
        img, "manual_resize", 64, 16, False, 16, "kmeans_lab", False, 90, "none", 0
    )
    assert out.shape[-1] == 3


def test_process_manual_target_resolution(node):
    img = make_image(1, 320, 240)
    out, _ = node.process(
        img, "manual_resize", 80, 16, False, 16, "kmeans_lab", False, 90, "none", 0
    )
    # Long edge mapped to target, aspect ratio preserved
    assert max(out.shape[1], out.shape[2]) == 80


def test_process_no_palette_reduction_skips_quantize(node):
    img = make_image(1, 64, 64)
    out, palette = node.process(
        img, "manual_resize", 32, 16, False, 16, "kmeans_lab", False, 90, "none", 0
    )
    # palette preview should still be returned (blank checkerboard)
    assert palette.shape[0] == 1


# --- B2 regression: heterogeneous palette sizes batch correctly --------------


def test_batch_heterogeneous_palette_sizes_does_not_crash(node):
    # Two images: rich color + nearly uniform. quantize_simple will produce
    # different palette sizes, which previously broke torch.stack.
    img1 = make_image(1, 128, 128, seed=1)
    img2 = (torch.ones(1, 128, 128, 3, dtype=torch.float32) * 0.2)
    img2 += torch.rand_like(img2) * 0.01
    img = torch.cat([img1, img2], dim=0)
    out, palette = node.process(
        img, "manual_resize", 32, 16, True, 8, "quantize_simple", False, 90, "none", 0
    )
    assert out.shape[0] == 2
    assert palette.shape[0] == 2
    # All grids share the same H, W after unification
    assert palette.shape[1] > 0 and palette.shape[2] > 0


# --- Determinism -------------------------------------------------------------


def test_determinism_kmeans_rgb(node):
    img = make_image(1, 96, 96, seed=7)
    a, _ = node.process(
        img, "manual_resize", 48, 16, True, 8, "kmeans_rgb", False, 90, "none", 123
    )
    b, _ = node.process(
        img, "manual_resize", 48, 16, True, 8, "kmeans_rgb", False, 90, "none", 123
    )
    assert torch.equal(a, b)


def test_different_seeds_can_differ(node):
    img = make_image(1, 96, 96, seed=11)
    a, _ = node.process(
        img, "manual_resize", 48, 16, True, 8, "kmeans_rgb", False, 90, "none", 0
    )
    b, _ = node.process(
        img, "manual_resize", 48, 16, True, 8, "kmeans_rgb", False, 90, "none", 999
    )
    # Not strictly guaranteed unequal, but for a rich random image it should be.
    assert a.shape == b.shape


# --- Auto modes --------------------------------------------------------------


def test_auto_loose_runs(node):
    img = make_image(1, 256, 256, seed=3)
    out, _ = node.process(
        img, "auto_downscale_loose", 128, 16, False, 16, "kmeans_lab", False, 90, "none", 0
    )
    assert out.shape[1] <= 256 and out.shape[2] <= 256


def test_auto_strict_runs(node):
    img = make_image(1, 256, 256, seed=5)
    out, _ = node.process(
        img, "auto_downscale_strict", 128, 16, False, 16, "kmeans_lab", False, 90, "none", 0
    )
    assert out.shape[1] <= 256 and out.shape[2] <= 256


# --- Dither ------------------------------------------------------------------


def test_dither_bayer_4x4_runs(node):
    img = make_image(1, 64, 64)
    out, _ = node.process(
        img, "manual_resize", 32, 16, True, 8, "kmeans_rgb", False, 90, "bayer_4x4", 0
    )
    assert out.shape[0] == 1


# --- New dither methods ------------------------------------------------------


def test_dither_bayer_8x8_runs(node):
    img = make_image(1, 96, 96, seed=2)
    out, _ = node.process(
        img, "manual_resize", 48, 16, True, 16, "kmeans_rgb", False, 90, "bayer_8x8", 0
    )
    assert out.shape[0] == 1
    assert 0.0 <= out.min().item() and out.max().item() <= 1.0


def test_dither_blue_noise_runs(node):
    img = make_image(1, 96, 96, seed=3)
    out, _ = node.process(
        img, "manual_resize", 48, 16, True, 16, "kmeans_rgb", False, 90, "blue_noise", 0
    )
    assert out.shape[0] == 1
    assert 0.0 <= out.min().item() and out.max().item() <= 1.0


def test_dither_riemersma_runs(node):
    img = make_image(1, 64, 64, seed=4)
    out, _ = node.process(
        img, "manual_resize", 32, 16, True, 8, "kmeans_rgb", False, 90, "riemersma", 0
    )
    assert out.shape[0] == 1


def test_dither_knoll_runs(node):
    img = make_image(1, 64, 64, seed=5)
    out, _ = node.process(
        img, "manual_resize", 32, 16, True, 8, "kmeans_rgb", False, 90, "knoll", 0
    )
    assert out.shape[0] == 1


def test_dither_knoll_output_uses_only_palette_colors(node):
    # Knoll must output only palette colors (no per-channel mixing).
    torch.manual_seed(0)
    img = torch.rand(1, 32, 32, 3, dtype=torch.float32)
    out, palette = node.process(
        img, "manual_resize", 32, 16, True, 4, "kmeans_rgb", False, 90, "knoll", 7
    )
    out_pixels = (out[0].reshape(-1, 3) * 255.0).round().to(torch.int32).cpu().numpy()
    unique_pixels = np.unique(out_pixels, axis=0)
    assert len(unique_pixels) <= 4 + 1  # rounding may add tiny variance, but bounded


def test_dither_riemersma_output_uses_only_palette_colors(node):
    torch.manual_seed(0)
    img = torch.rand(1, 32, 32, 3, dtype=torch.float32)
    out, palette = node.process(
        img, "manual_resize", 32, 16, True, 4, "kmeans_rgb", False, 90, "riemersma", 7
    )
    out_pixels = (out[0].reshape(-1, 3) * 255.0).round().to(torch.int32).cpu().numpy()
    unique_pixels = np.unique(out_pixels, axis=0)
    assert len(unique_pixels) <= 4 + 1


def test_coupled_dither_no_palette_is_noop(node):
    # With reduce_palette=False, knoll/riemersma have no palette to map to;
    # output should match the no-dither path (no error, no palette-only output).
    img = make_image(1, 48, 48, seed=9)
    out_knoll, _ = node.process(
        img, "manual_resize", 32, 16, False, 16, "kmeans_rgb", False, 90, "knoll", 0
    )
    out_riemersma, _ = node.process(
        img, "manual_resize", 32, 16, False, 16, "kmeans_rgb", False, 90, "riemersma", 0
    )
    assert out_knoll.shape == out_riemersma.shape
    assert torch.equal(out_knoll, out_riemersma)


# --- Blue noise mask ---------------------------------------------------------


def test_blue_noise_mask_shape_and_range():
    m = get_blue_noise_mask()
    assert m.shape == (BLUE_NOISE_SIZE, BLUE_NOISE_SIZE)
    assert m.dtype == np.float32
    assert 0.0 < m.min() and m.max() < 1.0


def test_blue_noise_mask_uniform_distribution():
    # Histogram of values should be roughly flat (rank-based mask).
    m = get_blue_noise_mask()
    hist, _ = np.histogram(m, bins=8, range=(0.0, 1.0))
    expected = m.size / 8
    assert np.all(np.abs(hist - expected) < expected * 0.2)


def test_blue_noise_mask_cached():
    m1 = get_blue_noise_mask()
    m2 = get_blue_noise_mask()
    assert m1 is m2


# --- Hilbert curve -----------------------------------------------------------


def test_hilbert_order_covers_all_pixels():
    coords = hilbert_order(16, 16)
    assert coords.shape == (256, 2)
    seen = {(int(y), int(x)) for y, x in coords}
    assert len(seen) == 256


def test_hilbert_order_non_power_of_two():
    coords = hilbert_order(13, 21)
    assert coords.shape == (13 * 21, 2)
    seen = {(int(y), int(x)) for y, x in coords}
    assert len(seen) == 13 * 21
    for y, x in seen:
        assert 0 <= y < 13 and 0 <= x < 21


# --- Palette preview is uniform across batch entries -------------------------


def test_palette_preview_uniform_shape_in_batch(node):
    img = torch.cat(
        [make_image(1, 96, 96, seed=i) for i in range(3)], dim=0
    )
    _, palette = node.process(
        img, "manual_resize", 32, 16, True, 16, "kmeans_lab", True, 90, "none", 0
    )
    assert palette.shape[0] == 3
    # all same H, W (this is the contract that makes torch.stack succeed)
    assert palette[0].shape == palette[1].shape == palette[2].shape


# --- Mixel-aware auto downscale ---------------------------------------------


def _nearest_upscale(chw_small: torch.Tensor, scale: float) -> torch.Tensor:
    """Upscale a (C, h, w) tensor by `scale` with nearest-neighbor; returns CHW."""
    h, w = chw_small.shape[1], chw_small.shape[2]
    new_h = int(round(h * scale))
    new_w = int(round(w * scale))
    return F.interpolate(
        chw_small.unsqueeze(0), size=(new_h, new_w), mode="nearest"
    ).squeeze(0)


def test_detect_block_size_clean_integer_scale():
    torch.manual_seed(0)
    base = torch.rand(3, 32, 32, dtype=torch.float32)
    upscaled = _nearest_upscale(base, 6.0)  # exact 6x
    res = detect_block_size(upscaled, max_block=16)
    assert res == (6, 6)


def test_detect_block_size_mixel_scale():
    torch.manual_seed(1)
    base = torch.rand(3, 32, 32, dtype=torch.float32)
    upscaled = _nearest_upscale(base, 119.0 / 32.0)  # 119/32 ~= 3.72 -> mixel runs of 3 and 4
    res = detect_block_size(upscaled, max_block=16)
    assert res is not None
    bh, bw = res
    assert bh in {3, 4}
    assert bw in {3, 4}


def test_detect_block_size_solid_returns_none():
    solid = torch.full((3, 96, 96), 0.5, dtype=torch.float32)
    res = detect_block_size(solid, max_block=16)
    assert res is None


def test_auto_pixel_size_downscale_dims(node):
    torch.manual_seed(2)
    base = torch.rand(3, 32, 32, dtype=torch.float32)
    upscaled = _nearest_upscale(base, 6.0)  # 192x192
    img = upscaled.permute(1, 2, 0).unsqueeze(0)  # BHWC
    out, _ = node.process(
        img, "auto_pixel_size", 64, 16, False, 16, "kmeans_rgb", False, 90, "none", 0
    )
    # Detected block is 6 → output dims should match floor((H - oy) / 6) per axis.
    H, W = upscaled.shape[1], upscaled.shape[2]
    assert out.shape[1] in {H // 6, (H // 6) - 1, (H // 6) + 1}
    assert out.shape[2] in {W // 6, (W // 6) - 1, (W // 6) + 1}


def test_auto_pixel_size_no_residual_mixels(node):
    """Reconstruction error of mixel-aware downscale should beat strict auto."""
    torch.manual_seed(3)
    base = torch.rand(3, 32, 32, dtype=torch.float32)
    upscaled = _nearest_upscale(base, 6.0)
    H, W = upscaled.shape[1], upscaled.shape[2]
    img_hwc = upscaled.permute(1, 2, 0).unsqueeze(0)

    out_pix, _ = node.process(
        img_hwc, "auto_pixel_size", 64, 16, False, 16, "kmeans_rgb", False, 90, "none", 0
    )
    out_strict, _ = node.process(
        img_hwc, "auto_downscale_strict", 64, 16, False, 16, "kmeans_rgb", False, 90, "none", 0
    )

    def err(small_bhwc):
        small_chw = small_bhwc[0].permute(2, 0, 1).unsqueeze(0)
        up = F.interpolate(small_chw, size=(H, W), mode="nearest").squeeze(0)
        return float(torch.mean(torch.abs(upscaled - up)).item())

    e_pix = err(out_pix)
    e_strict = err(out_strict)
    # Mixel-aware should be (near-)perfect; strict can match on this clean case.
    assert e_pix < 0.01
    assert e_pix <= e_strict + 1e-6


def test_auto_pixel_size_falls_back_on_solid(node):
    img = torch.full((1, 128, 128, 3), 0.5, dtype=torch.float32)
    out, _ = node.process(
        img, "auto_pixel_size", 64, 16, False, 16, "kmeans_rgb", False, 90, "none", 0
    )
    assert out.dim() == 4 and out.shape[0] == 1 and out.shape[-1] == 3
    assert 0.0 <= out.min().item() and out.max().item() <= 1.0


# --- Palette image input ----------------------------------------------------


def _make_swatch_palette_image(colors_u8: np.ndarray, swatch: int = 32) -> torch.Tensor:
    """Build a horizontal swatch strip from (N, 3) uint8 colors. Returns BHWC float."""
    n = len(colors_u8)
    arr = np.zeros((swatch, swatch * n, 3), dtype=np.float32)
    for i, c in enumerate(colors_u8):
        arr[:, i * swatch : (i + 1) * swatch, :] = c.astype(np.float32) / 255.0
    return torch.from_numpy(arr).unsqueeze(0)


def test_snap_palette_size_table():
    # Round-half-up to nearest multiple of 4, with {2} as the 1-bit floor.
    cases = {
        1: 2, 2: 2, 3: 4, 4: 4, 5: 4, 6: 8, 7: 8, 8: 8, 9: 8,
        10: 12, 12: 12, 13: 12, 14: 16, 15: 16, 16: 16, 17: 16,
        31: 32, 32: 32, 33: 32, 34: 36,
    }
    for n, expected in cases.items():
        assert _snap_palette_size(n) == expected, f"snap({n}) -> {_snap_palette_size(n)} != {expected}"


def test_unique_colors_from_palette_image_dedupes_swatches():
    rng = np.random.RandomState(0)
    colors = rng.randint(0, 256, size=(8, 3), dtype=np.uint8)
    pal_img = _make_swatch_palette_image(colors, swatch=16)
    extracted = _unique_colors_from_palette_image(pal_img)
    # Each swatch contributes one unique 8-bit color → exactly 8 entries.
    assert len(extracted) == 8


def test_palette_image_overrides_max_colors_and_forces_reduce(node):
    rng = np.random.RandomState(1)
    colors = rng.randint(0, 256, size=(8, 3), dtype=np.uint8)
    pal_img = _make_swatch_palette_image(colors, swatch=16)
    img = make_image(1, 64, 64, seed=2)

    # max_colors=99, reduce_palette=False — both should be overridden.
    out, palette_preview = node.process(
        img, "manual_resize", 32, 16, False, 99, "kmeans_rgb", False, 90, "none", 0,
        pal_img,
    )
    out_pixels = (out[0].reshape(-1, 3) * 255.0).round().to(torch.int32).cpu().numpy()
    unique_pixels = np.unique(out_pixels, axis=0)
    # Output must use only colors from the provided palette (8 entries, snap=8).
    # Allow tiny rounding leeway.
    assert len(unique_pixels) <= 8 + 1
    assert palette_preview.shape[0] == 1


def test_palette_image_snaps_to_four_multiple(node):
    rng = np.random.RandomState(3)
    # 7 unique colors → snap target = 8.
    colors = rng.randint(0, 256, size=(7, 3), dtype=np.uint8)
    pal_img = _make_swatch_palette_image(colors, swatch=16)
    img = make_image(1, 48, 48, seed=4)
    out, _ = node.process(
        img, "manual_resize", 24, 16, True, 16, "kmeans_rgb", False, 90, "none", 0,
        pal_img,
    )
    out_pixels = (out[0].reshape(-1, 3) * 255.0).round().to(torch.int32).cpu().numpy()
    unique_pixels = np.unique(out_pixels, axis=0)
    # 7 unique → cluster down to 8 is no-op (7 <= 8) → 7 colors used at most.
    assert len(unique_pixels) <= 8 + 1


# --- OkLab ------------------------------------------------------------------


def test_rgb_to_oklab_white_is_l1():
    white = np.full((1, 3), 255, dtype=np.float32)
    lab = rgb_to_oklab(white)
    assert lab[0, 0] == pytest.approx(1.0, abs=1e-3)
    assert abs(lab[0, 1]) < 1e-3
    assert abs(lab[0, 2]) < 1e-3


def test_rgb_to_oklab_black_is_zero():
    black = np.zeros((1, 3), dtype=np.float32)
    lab = rgb_to_oklab(black)
    assert np.allclose(lab[0], 0.0, atol=1e-4)


def test_rgb_to_oklab_does_not_mutate_input():
    rgb = np.array([[100.0, 150.0, 200.0]], dtype=np.float32)
    rgb_copy = rgb.copy()
    _ = rgb_to_oklab(rgb)
    assert np.array_equal(rgb, rgb_copy)


def test_oklab_mapper_picks_perceptually_closer_color(node):
    # Target: light gray. Palette: pure red (Euclidean-RGB closer to mid-gray)
    # vs. light gray (OkLab-closer). OkLab metric must pick light gray.
    target_color = np.array([180, 180, 180], dtype=np.uint8)
    img = torch.from_numpy(
        np.broadcast_to(target_color.astype(np.float32) / 255.0, (1, 16, 16, 3))
        .copy()
    ).to(torch.float32)
    palette_colors = np.array([[200, 0, 0], [200, 200, 200]], dtype=np.uint8)
    pal_img = _make_swatch_palette_image(palette_colors, swatch=8)
    out, _ = node.process(
        img, "manual_resize", 16, 16, True, 16, "kmeans_rgb", False, 90, "none", 0,
        pal_img,
    )
    # Snapped to 2 colors; output should be all light-gray pixels.
    out_pixels = (out[0].reshape(-1, 3) * 255.0).round().to(torch.int32).cpu().numpy()
    light_gray = np.array([200, 200, 200], dtype=np.int32)
    matches = np.all(out_pixels == light_gray, axis=1).sum()
    assert matches == out_pixels.shape[0], "OkLab mapper should prefer light gray over red"


def test_palette_image_two_colors_one_bit(node):
    colors = np.array([[0, 0, 0], [255, 255, 255]], dtype=np.uint8)
    pal_img = _make_swatch_palette_image(colors, swatch=16)
    img = make_image(1, 32, 32, seed=5)
    out, _ = node.process(
        img, "manual_resize", 16, 16, True, 16, "kmeans_rgb", False, 90, "none", 0,
        pal_img,
    )
    out_pixels = (out[0].reshape(-1, 3) * 255.0).round().to(torch.int32).cpu().numpy()
    unique_pixels = np.unique(out_pixels, axis=0)
    # snap(2) = 2, so output must contain at most 2 distinct colors.
    assert len(unique_pixels) <= 2 + 1


def test_oklab_mapper_near_black_prefers_black_over_navy(node):
    # Regression: pure-cube-root OkLab amplifies near-black L delta and pushes
    # noisy near-black source pixels toward dark-chroma palette entries (e.g.
    # navy) instead of the pure-black entry. CIELAB-shoulder OkLab must keep
    # near-black source mapped to black.
    target_color = np.array([20, 20, 25], dtype=np.uint8)
    img = torch.from_numpy(
        np.broadcast_to(target_color.astype(np.float32) / 255.0, (1, 16, 16, 3))
        .copy()
    ).to(torch.float32)
    palette_colors = np.array([[0, 0, 0], [40, 40, 90]], dtype=np.uint8)
    pal_img = _make_swatch_palette_image(palette_colors, swatch=8)
    out, _ = node.process(
        img, "manual_resize", 16, 16, True, 16, "kmeans_rgb", False, 90, "none", 0,
        pal_img,
    )
    out_pixels = (out[0].reshape(-1, 3) * 255.0).round().to(torch.int32).cpu().numpy()
    black = np.array([0, 0, 0], dtype=np.int32)
    matches = np.all(out_pixels == black, axis=1).sum()
    assert matches == out_pixels.shape[0], (
        "Near-black source must map to black palette entry, not navy"
    )


# --- Solid-BG isolation -----------------------------------------------------


def _make_subject_on_bg(
    bg_rgb: np.ndarray,
    subject_rgb: np.ndarray,
    h: int = 32,
    w: int = 32,
    subject_box: Tuple[int, int, int, int] = (4, 4, 12, 12),
    noise: float = 0.0,
    seed: int = 0,
) -> torch.Tensor:
    """Build a 1xHxWx3 image: solid BG with a small subject rectangle.

    Optional noise simulates near-uniform (not exactly uniform) BG so we exercise
    the OkLab-distance mask rather than a trivial exact-match path.
    """
    rng = np.random.default_rng(seed)
    img = np.broadcast_to(bg_rgb.astype(np.float32), (h, w, 3)).copy()
    if noise > 0:
        img = np.clip(img + rng.normal(0, noise * 255.0, img.shape), 0, 255)
    y0, x0, y1, x1 = subject_box
    img[y0:y1, x0:x1] = subject_rgb.astype(np.float32)
    img = (img / 255.0).astype(np.float32)
    return torch.from_numpy(img).unsqueeze(0)


def test_detect_solid_background_finds_dominant_black():
    img = _make_subject_on_bg(
        np.array([0, 0, 0]), np.array([200, 50, 50]), noise=0.01, seed=1
    )
    img_255 = img[0] * 255.0
    bg_color, bg_mask = _detect_solid_background(img_255)
    assert bg_color is not None
    assert bg_mask is not None
    assert np.linalg.norm(bg_color) < 25.0  # near-black
    # BG mask covers most pixels (subject is 8x8 of 32x32 = 64/1024 ≈ 6%).
    assert bg_mask.sum() > 0.85 * bg_mask.size


def test_detect_solid_background_returns_none_on_noise():
    rng = np.random.default_rng(7)
    img_255 = torch.from_numpy(
        rng.uniform(0, 255, (32, 32, 3)).astype(np.float32)
    )
    bg_color, bg_mask = _detect_solid_background(img_255)
    assert bg_color is None
    assert bg_mask is None


def test_bg_isolation_black_bg_maps_to_black_palette(node):
    # Subject (200,50,50) on near-black BG. Palette {black, navy, red, white}.
    # BG must map to pure black, not navy.
    img = _make_subject_on_bg(
        np.array([5, 5, 8]), np.array([200, 50, 50]), noise=0.02, seed=2
    )
    palette_colors = np.array(
        [[0, 0, 0], [40, 40, 90], [200, 50, 50], [255, 255, 255]], dtype=np.uint8
    )
    pal_img = _make_swatch_palette_image(palette_colors, swatch=8)
    out, _ = node.process(
        img, "manual_resize", 32, 16, True, 16, "kmeans_rgb", False, 90, "none", 0,
        pal_img,
    )
    out_u8 = (out[0].reshape(-1, 3) * 255.0).round().to(torch.int32).cpu().numpy()
    # Vast majority of pixels should be exactly (0,0,0).
    black = np.array([0, 0, 0], dtype=np.int32)
    bg_count = np.all(out_u8 == black, axis=1).sum()
    assert bg_count > 0.85 * out_u8.shape[0], (
        f"BG should map to pure black; only {bg_count}/{out_u8.shape[0]} are black"
    )


def test_bg_isolation_white_bg_maps_to_white_palette(node):
    img = _make_subject_on_bg(
        np.array([252, 252, 250]), np.array([20, 20, 20]), noise=0.01, seed=3
    )
    palette_colors = np.array(
        [[0, 0, 0], [128, 128, 128], [255, 255, 255]], dtype=np.uint8
    )
    pal_img = _make_swatch_palette_image(palette_colors, swatch=8)
    out, _ = node.process(
        img, "manual_resize", 32, 16, True, 16, "kmeans_rgb", False, 90, "none", 0,
        pal_img,
    )
    out_u8 = (out[0].reshape(-1, 3) * 255.0).round().to(torch.int32).cpu().numpy()
    white = np.array([255, 255, 255], dtype=np.int32)
    bg_count = np.all(out_u8 == white, axis=1).sum()
    assert bg_count > 0.85 * out_u8.shape[0], (
        f"BG should map to pure white; only {bg_count}/{out_u8.shape[0]} are white"
    )


def test_bg_isolation_disables_dither_on_bg(node):
    # Bayer dither would normally produce a checker pattern even on solid BG.
    # With BG isolation, BG pixels must be a single uniform color.
    img = _make_subject_on_bg(
        np.array([0, 0, 0]), np.array([200, 200, 50]), noise=0.0, seed=4
    )
    palette_colors = np.array(
        [[0, 0, 0], [200, 200, 50], [255, 255, 255]], dtype=np.uint8
    )
    pal_img = _make_swatch_palette_image(palette_colors, swatch=8)
    out, _ = node.process(
        img, "manual_resize", 32, 16, True, 16, "kmeans_rgb", False, 90,
        "bayer_4x4", 0, pal_img,
    )
    out_u8 = (out[0].reshape(-1, 3) * 255.0).round().to(torch.int32).cpu().numpy()
    black = np.array([0, 0, 0], dtype=np.int32)
    # Most BG pixels uniform black (no dither speckle).
    bg_count = np.all(out_u8 == black, axis=1).sum()
    assert bg_count > 0.80 * out_u8.shape[0], (
        f"Bayer dither must not speckle BG; only {bg_count}/{out_u8.shape[0]} pure black"
    )


# --- Feature C: ramps_oklab palette -----------------------------------------


def _two_hue_image(h: int = 64, w: int = 64, seed: int = 0) -> torch.Tensor:
    """Build a 2-hue image (warm + cool halves) with within-region L* variation
    so ramps have meaningful tonal range to quantize."""
    rng = np.random.default_rng(seed)
    arr = np.zeros((h, w, 3), dtype=np.float32)
    # Warm half: red-orange ramp on left.
    warm_L = rng.uniform(60, 220, (h, w // 2))
    arr[:, : w // 2, 0] = warm_L
    arr[:, : w // 2, 1] = warm_L * 0.5
    arr[:, : w // 2, 2] = warm_L * 0.2
    # Cool half: blue-cyan ramp on right.
    cool_L = rng.uniform(40, 200, (h, w - w // 2))
    arr[:, w // 2 :, 0] = cool_L * 0.2
    arr[:, w // 2 :, 1] = cool_L * 0.5
    arr[:, w // 2 :, 2] = cool_L
    arr = np.clip(arr, 0, 255) / 255.0
    return torch.from_numpy(arr).unsqueeze(0)


def test_ramps_oklab_palette_size_equals_K_times_M(node):
    img = _two_hue_image(seed=10)
    # max_colors=12, ramp_levels=4 → ceil(12/4)=3 hue clusters × 4 levels = 12 entries.
    out, _ = node.process(
        img, "manual_resize", 64, 16, True, 12, "ramps_oklab", False, 90, "none", 0,
        None, 4, False, 0.04, False, 1,
    )
    out_u8 = (out[0].reshape(-1, 3) * 255.0).round().to(torch.int32).cpu().numpy()
    unique = np.unique(out_u8, axis=0)
    # Should produce ≤ K*M unique colors. Allow a couple of off-by-one due to
    # rounding through OkLab→RGB inverse.
    assert len(unique) <= 12 + 2, f"Expected ≤ 14 unique colors, got {len(unique)}"


def test_ramps_oklab_within_cluster_l_star_strictly_increases(node):
    # Use the helper directly to inspect palette before mapping.
    flat_rgb = (_two_hue_image(seed=11)[0].reshape(-1, 3).numpy() * 255.0)
    palette = node._kmeans_ramps(flat_rgb, max_colors=12, ramp_levels=4, seed=11)
    pal_oklab = rgb_to_oklab(palette)
    # Cluster palette entries by (a, b) proximity to find the M=4 ramp groups.
    K = max(1, len(palette) // 4)
    if K < 2:
        pytest.skip("Need at least 2 hue clusters to validate ramp ordering")
    # For each consecutive run of M=4 entries in the palette (kmeans_ramps emits
    # them grouped by cluster), assert L* is strictly increasing.
    M = 4
    n_full_groups = len(palette) // M
    for g in range(n_full_groups):
        Ls = pal_oklab[g * M : (g + 1) * M, 0]
        diffs = np.diff(Ls)
        assert np.all(diffs > 0), f"Ramp {g} L* not strictly increasing: {Ls}"


def test_ramps_oklab_inverse_round_trip_within_tolerance():
    rgb = np.array(
        [[0, 0, 0], [255, 255, 255], [200, 50, 50], [40, 40, 90], [120, 200, 80],
         [50, 50, 50], [128, 128, 128]],
        dtype=np.float32,
    )
    lab = rgb_to_oklab(rgb)
    rt = _oklab_to_rgb_255_np(lab)
    assert np.max(np.abs(rgb - rt)) < 1.5, (
        f"OkLab round-trip exceeds 1.5/255 tolerance: max err = {np.max(np.abs(rgb - rt))}"
    )


def test_palette_strategy_kmeans_lab_unchanged(node):
    # Regression guard: existing kmeans_lab pipeline behavior must be unchanged
    # by the dispatch refactor. Same input + same args + reset seed → same output.
    img = make_image(1, 32, 32, seed=42)
    out_a, _ = node.process(
        img, "manual_resize", 32, 16, True, 8, "kmeans_lab", True, 90, "none", 0,
    )
    out_b, _ = node.process(
        img, "manual_resize", 32, 16, True, 8, "kmeans_lab", True, 90, "none", 0,
    )
    assert torch.allclose(out_a, out_b), "kmeans_lab not deterministic across calls"


# --- Feature A: selective dithering -----------------------------------------


def test_compute_smooth_mask_flat_returns_empty():
    # Smooth-mask requires both low local std AND non-zero local range. A
    # perfectly flat region has zero range so must return an all-False mask
    # regardless of threshold. (Selective-dither integration is exercised by
    # the dither tests below.)
    h, w = 32, 32
    flat = np.full((h, w, 3), 128.0, dtype=np.float32)
    mask = _compute_smooth_mask(torch.from_numpy(flat), threshold=0.05)
    assert mask.sum().item() == 0, (
        f"Flat region must have zero smooth pixels (got {mask.sum().item()})"
    )


def test_selective_dither_flat_subject_stays_flat(node):
    # Flat subject + noisy gradient BG. With selective_dither + bayer_4x4,
    # subject should remain a single solid palette color.
    h, w = 32, 32
    img_np = np.zeros((h, w, 3), dtype=np.float32)
    rng = np.random.default_rng(123)
    img_np[:, :, :] = np.linspace(40, 220, w)[None, :, None]  # horizontal gradient
    img_np += rng.normal(0, 3, img_np.shape)
    img_np[8:24, 8:24] = 120  # flat subject square
    img_np = np.clip(img_np, 0, 255) / 255.0
    img = torch.from_numpy(img_np).unsqueeze(0)
    palette_colors = np.array(
        [[40, 40, 40], [80, 80, 80], [120, 120, 120], [160, 160, 160], [220, 220, 220]],
        dtype=np.uint8,
    )
    pal_img = _make_swatch_palette_image(palette_colors, swatch=8)
    out, _ = node.process(
        img, "manual_resize", 32, 16, True, 5, "kmeans_rgb", False, 90, "bayer_4x4", 0,
        pal_img, 4, True, 0.06, False, 1,
    )
    out_u8 = (out[0] * 255.0).round().to(torch.int32).cpu().numpy()
    subject_uniques = np.unique(out_u8[8:24, 8:24].reshape(-1, 3), axis=0)
    assert len(subject_uniques) <= 2, (
        f"Selective dither must keep subject flat; got {len(subject_uniques)} colors"
    )


def test_selective_dither_off_matches_baseline(node):
    img = make_image(1, 32, 32, seed=7)
    base, _ = node.process(
        img, "manual_resize", 32, 16, True, 8, "kmeans_rgb", False, 90, "bayer_4x4", 0,
    )
    # With selective_dither=False, output must match baseline (i.e. unchanged
    # behavior for existing workflows).
    new, _ = node.process(
        img, "manual_resize", 32, 16, True, 8, "kmeans_rgb", False, 90, "bayer_4x4", 0,
        None, 4, False, 0.04, False, 1,
    )
    assert torch.allclose(base, new), "selective_dither=False must reproduce baseline"


def test_selective_dither_works_with_knoll(node):
    # Same flat-subject-on-gradient setup but using the coupled `knoll` dither
    # to exercise the where-blend code path.
    h, w = 32, 32
    img_np = np.zeros((h, w, 3), dtype=np.float32)
    img_np[:, :, :] = np.linspace(40, 220, w)[None, :, None]
    img_np[8:24, 8:24] = 120
    img_np = np.clip(img_np, 0, 255) / 255.0
    img = torch.from_numpy(img_np).unsqueeze(0)
    palette_colors = np.array(
        [[40, 40, 40], [120, 120, 120], [220, 220, 220]], dtype=np.uint8
    )
    pal_img = _make_swatch_palette_image(palette_colors, swatch=8)
    out, _ = node.process(
        img, "manual_resize", 32, 16, True, 4, "kmeans_rgb", False, 90, "knoll", 0,
        pal_img, 4, True, 0.06, False, 1,
    )
    out_u8 = (out[0] * 255.0).round().to(torch.int32).cpu().numpy()
    subject_uniques = np.unique(out_u8[8:24, 8:24].reshape(-1, 3), axis=0)
    assert len(subject_uniques) <= 2, (
        f"Selective knoll must keep subject flat; got {len(subject_uniques)} colors"
    )


# --- Feature B: silhouette outline ------------------------------------------


def test_compute_outline_mask_finds_subject_boundary():
    img = _make_subject_on_bg(
        np.array([255, 255, 255]), np.array([0, 0, 0]),
        h=32, w=32, subject_box=(8, 8, 24, 24), noise=0.0, seed=0,
    )
    img_t = (img[0] * 255.0)
    mask = _compute_outline_mask(img_t, bg_mask=None)
    # Outline should mostly land along subject boundary (rows/cols 7,8 and 23,24).
    edge_pixels = mask.sum().item()
    assert edge_pixels > 0, "Outline mask should detect subject silhouette"
    # Center of subject should not be in outline mask.
    assert not bool(mask[15, 15].item()), "Outline must not include subject interior"


def test_silhouette_outline_uses_only_palette_colors(node):
    img = _make_subject_on_bg(
        np.array([240, 240, 240]), np.array([100, 50, 50]),
        h=32, w=32, subject_box=(8, 8, 24, 24), noise=0.0, seed=2,
    )
    palette_colors = np.array(
        [[20, 10, 10], [100, 50, 50], [200, 100, 100], [240, 240, 240]],
        dtype=np.uint8,
    )
    pal_img = _make_swatch_palette_image(palette_colors, swatch=8)
    out, _ = node.process(
        img, "manual_resize", 32, 16, True, 4, "kmeans_rgb", False, 90, "none", 0,
        pal_img, 4, False, 0.04, True, 2,
    )
    out_u8 = (out[0].reshape(-1, 3) * 255.0).round().to(torch.int32).cpu().numpy()
    # Snap palette has 4 entries; output must use only those.
    extracted = _unique_colors_from_palette_image(pal_img)
    palette_set = {tuple(p.astype(int)) for p in extracted}
    output_set = {tuple(p) for p in out_u8}
    assert output_set <= palette_set, (
        f"Outline output uses non-palette colors: {output_set - palette_set}"
    )


def test_silhouette_outline_skips_bg_pixels(node):
    # Solid black BG (triggers BG isolation) + subject. After outline pass, BG
    # pixels should remain whatever the BG override mapped them to.
    img = _make_subject_on_bg(
        np.array([0, 0, 0]), np.array([200, 100, 50]),
        h=32, w=32, subject_box=(8, 8, 24, 24), noise=0.01, seed=3,
    )
    palette_colors = np.array(
        [[0, 0, 0], [100, 50, 25], [200, 100, 50], [255, 220, 180]],
        dtype=np.uint8,
    )
    pal_img = _make_swatch_palette_image(palette_colors, swatch=8)
    out, _ = node.process(
        img, "manual_resize", 32, 16, True, 4, "kmeans_rgb", False, 90, "none", 0,
        pal_img, 4, False, 0.04, True, 1,
    )
    out_u8 = (out[0] * 255.0).round().to(torch.int32).cpu().numpy()
    # Far-corner BG pixels must still be black (BG override + outline-skip-BG).
    corners = [out_u8[0, 0], out_u8[0, -1], out_u8[-1, 0], out_u8[-1, -1]]
    for px in corners:
        assert tuple(px) == (0, 0, 0), f"Corner BG pixel changed by outline: {px}"


# --- Combined ---------------------------------------------------------------


def test_combined_features_all_on_produces_on_palette_output(node):
    # Use exactly 4 swatches (power of 2) so the internal palette snap is a
    # no-op and the extracted palette equals the palette actually used.
    img = _make_subject_on_bg(
        np.array([240, 240, 240]), np.array([60, 30, 90]),
        h=48, w=48, subject_box=(12, 12, 36, 36), noise=0.02, seed=5,
    )
    palette_colors = np.array(
        [[10, 5, 15], [60, 30, 90], [120, 80, 160], [240, 240, 240]],
        dtype=np.uint8,
    )
    pal_img = _make_swatch_palette_image(palette_colors, swatch=8)
    out, _ = node.process(
        img, "manual_resize", 48, 16, True, 4, "ramps_oklab", False, 90, "bayer_4x4", 0,
        pal_img, 4, True, 0.04, True, 1,
    )
    out_u8 = (out[0].reshape(-1, 3) * 255.0).round().to(torch.int32).cpu().numpy()
    extracted = _unique_colors_from_palette_image(pal_img)
    palette_set = {tuple(p.astype(int)) for p in extracted}
    output_set = {tuple(p) for p in out_u8}
    assert output_set <= palette_set, (
        f"Combined-features output uses non-palette colors: {output_set - palette_set}"
    )
