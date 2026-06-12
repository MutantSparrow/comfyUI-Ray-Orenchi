"""Tests for ray_crt. Run with: pytest tests/"""

import pytest
import torch

from ray_crt import (
    PRESET_NAMES,
    PRESETS,
    RayCRT,
    _ntsc_bleed,
    normalize_image,
)


def make_image(b: int, h: int, w: int, c: int = 3, seed: int = 0) -> torch.Tensor:
    g = torch.Generator().manual_seed(seed)
    return torch.rand(b, h, w, c, generator=g, dtype=torch.float32)


@pytest.fixture
def node():
    return RayCRT()


# --- normalize_image (mirrors HiPix coverage) -------------------------------


def test_normalize_accepts_bhwc_rgb():
    out = normalize_image(make_image(2, 64, 64, 3))
    assert out.shape == (2, 64, 64, 3)
    assert out.dtype == torch.float32


def test_normalize_accepts_hwc_rgb():
    out = normalize_image(make_image(1, 32, 32, 3).squeeze(0))
    assert out.shape == (1, 32, 32, 3)


def test_normalize_drops_alpha():
    out = normalize_image(make_image(1, 32, 32, 4))
    assert out.shape == (1, 32, 32, 3)


def test_normalize_expands_grayscale():
    out = normalize_image(make_image(1, 32, 32, 1))
    assert out.shape == (1, 32, 32, 3)
    assert torch.allclose(out[..., 0], out[..., 1])
    assert torch.allclose(out[..., 1], out[..., 2])


def test_normalize_rejects_bad_channels():
    with pytest.raises(ValueError):
        normalize_image(torch.zeros(1, 8, 8, 2))


# --- Shape preservation across all presets ----------------------------------


@pytest.mark.parametrize("preset", PRESET_NAMES)
@pytest.mark.parametrize("curvature", [False, True])
def test_shape_preservation(node, preset, curvature):
    img = make_image(1, 64, 64, 3)
    (out,) = node.process(
        image=img, preset=preset, curvature=curvature,
        intensity=1.0, scanline_strength=1.0, mask_strength=1.0,
    )
    assert out.shape == img.shape
    assert out.dtype == torch.float32
    assert float(out.min()) >= 0.0
    assert float(out.max()) <= 1.0


# --- Determinism ------------------------------------------------------------


def test_determinism(node):
    img = make_image(1, 64, 64, 3, seed=7)
    kwargs = dict(
        preset="lottes_fast", curvature=True,
        intensity=1.0, scanline_strength=1.0, mask_strength=1.0,
    )
    (a,) = node.process(image=img, **kwargs)
    (b,) = node.process(image=img, **kwargs)
    assert torch.equal(a, b)


# --- Intensity mix ----------------------------------------------------------


def test_intensity_zero_returns_input(node):
    img = make_image(1, 64, 64, 3, seed=11)
    (out,) = node.process(
        image=img, preset="arcade_royale", curvature=True,
        intensity=0.0, scanline_strength=1.0, mask_strength=1.0,
    )
    assert torch.allclose(out, img, atol=1e-5)


def test_zero_strengths_curvature_off_closer_to_input(node):
    """mask=0, scan=0, curvature=False should leave halation/bloom/vignette
    only — output stays much closer to input than full effect does."""
    img = make_image(1, 64, 64, 3, seed=3)
    common = dict(preset="trinitron_aperture", curvature=False, intensity=1.0)
    (full,) = node.process(image=img, scanline_strength=1.0, mask_strength=1.0, **common)
    (clean,) = node.process(image=img, scanline_strength=0.0, mask_strength=0.0, **common)
    full_diff = float((full - img).abs().mean())
    clean_diff = float((clean - img).abs().mean())
    assert clean_diff < full_diff


# --- Curvature toggle changes corner pixels ---------------------------------


def test_curvature_changes_corners(node):
    img = torch.full((1, 64, 64, 3), 0.7, dtype=torch.float32)
    common = dict(
        image=img, preset="lottes_fast", intensity=1.0,
        scanline_strength=0.0, mask_strength=0.0,
    )
    (off,) = node.process(curvature=False, **common)
    (on,) = node.process(curvature=True, **common)
    # Corner blocks (8x8) should differ — warp pulls bright interior outward
    # and out-of-bounds pixels go black per padding_mode='zeros'.
    diff_corner = (off[:, :8, :8, :] - on[:, :8, :8, :]).abs().max()
    assert float(diff_corner) > 0.0


# --- Channel handling -------------------------------------------------------


def test_grayscale_input(node):
    img = make_image(1, 64, 64, 1)
    (out,) = node.process(
        image=img, preset="pvm_shadow", curvature=False,
        intensity=1.0, scanline_strength=1.0, mask_strength=1.0,
    )
    assert out.shape == (1, 64, 64, 3)


def test_rgba_input(node):
    img = make_image(1, 64, 64, 4)
    (out,) = node.process(
        image=img, preset="pvm_shadow", curvature=False,
        intensity=1.0, scanline_strength=1.0, mask_strength=1.0,
    )
    assert out.shape == (1, 64, 64, 3)


# --- Batch ------------------------------------------------------------------


def test_batch_independent_processing(node):
    img = make_image(3, 64, 64, 3, seed=21)
    (out,) = node.process(
        image=img, preset="trinitron_aperture", curvature=True,
        intensity=1.0, scanline_strength=1.0, mask_strength=1.0,
    )
    assert out.shape == (3, 64, 64, 3)
    # Different inputs → different outputs per batch element.
    assert not torch.equal(out[0], out[1])
    assert not torch.equal(out[1], out[2])


# --- NTSC chroma bleed ------------------------------------------------------


def test_ntsc_preset_smooths_chroma_horizontally():
    """High-frequency chroma input (alternating R/B cols) should have its
    I-channel adjacent-pixel diff drop after `_ntsc_bleed` runs."""
    h, w = 16, 32
    img = torch.zeros(1, 3, h, w, dtype=torch.float32)
    img[:, 0, :, 0::2] = 1.0   # R on even cols
    img[:, 2, :, 1::2] = 1.0   # B on odd cols
    out = _ntsc_bleed(img)

    rgb_to_yiq = torch.tensor(
        [[0.299, 0.587, 0.114], [0.596, -0.274, -0.322], [0.211, -0.523, 0.312]],
        dtype=torch.float32,
    )
    in_yiq = torch.einsum('ij,bjhw->bihw', rgb_to_yiq, img)
    out_yiq = torch.einsum('ij,bjhw->bihw', rgb_to_yiq, out)
    in_diff = (in_yiq[:, 1, :, 1:] - in_yiq[:, 1, :, :-1]).abs().mean()
    out_diff = (out_yiq[:, 1, :, 1:] - out_yiq[:, 1, :, :-1]).abs().mean()
    assert float(out_diff) < float(in_diff)


# --- Edge sizes -------------------------------------------------------------


@pytest.mark.parametrize("size", [(1, 1), (8, 8), (33, 47), (128, 64)])
def test_arbitrary_sizes(node, size):
    h, w = size
    img = make_image(1, h, w, 3)
    (out,) = node.process(
        image=img, preset="composite_ntsc", curvature=True,
        intensity=1.0, scanline_strength=1.0, mask_strength=1.0,
    )
    assert out.shape == (1, h, w, 3)


# --- Sanity: PRESETS table well-formed --------------------------------------


def test_all_presets_have_required_keys():
    required = {
        "mask_type", "mask_pitch", "mask_depth",
        "scan_depth", "scan_pitch", "beam_mod",
        "halation", "halation_sigma", "halation_tint",
        "bloom", "bloom_sigma",
        "ntsc", "vignette", "reflection", "brightness_compensation",
    }
    for name, cfg in PRESETS.items():
        missing = required - set(cfg.keys())
        assert not missing, f"preset {name!r} missing keys: {missing}"
        assert cfg["mask_type"] in {"aperture", "shadow", "slot"}
        if "tint" in cfg:
            assert len(cfg["tint"]) == 3
        if "saturation" in cfg:
            assert isinstance(cfg["saturation"], (int, float))


# --- GBA preset desaturates -------------------------------------------------


def test_gba_desaturates(node):
    """gameboy_advance preset (saturation=0.65) reduces YIQ chroma magnitude."""
    h, w = 32, 32
    img = torch.zeros(1, h, w, 3, dtype=torch.float32)
    img[:, :, : w // 3, 0] = 1.0          # saturated red strip
    img[:, :, w // 3 : 2 * w // 3, 1] = 1.0  # saturated green strip
    img[:, :, 2 * w // 3 :, 2] = 1.0      # saturated blue strip

    (out,) = node.process(
        image=img, preset="gameboy_advance", curvature=False,
        intensity=1.0, scanline_strength=0.0, mask_strength=0.0,
    )

    rgb_to_yiq = torch.tensor(
        [[0.299, 0.587, 0.114], [0.596, -0.274, -0.322], [0.211, -0.523, 0.312]],
        dtype=torch.float32,
    )
    in_bchw = img.permute(0, 3, 1, 2)
    out_bchw = out.permute(0, 3, 1, 2)
    in_yiq = torch.einsum('ij,bjhw->bihw', rgb_to_yiq, in_bchw)
    out_yiq = torch.einsum('ij,bjhw->bihw', rgb_to_yiq, out_bchw)
    in_chroma = (in_yiq[:, 1].abs() + in_yiq[:, 2].abs()).mean()
    out_chroma = (out_yiq[:, 1].abs() + out_yiq[:, 2].abs()).mean()
    assert float(out_chroma) < float(in_chroma) * 0.85


# --- Console-flavored preset roster sanity ----------------------------------


CONSOLE_PRESETS = [
    "super_famicom", "megadrive", "ps1", "ps2",
    "nintendo_ds", "gameboy_advance", "psp",
]


@pytest.mark.parametrize("preset", CONSOLE_PRESETS)
def test_console_preset_runs(node, preset):
    img = make_image(1, 48, 48, 3)
    (out,) = node.process(
        image=img, preset=preset, curvature=False,
        intensity=1.0, scanline_strength=1.0, mask_strength=1.0,
    )
    assert out.shape == img.shape
    assert float(out.min()) >= 0.0 and float(out.max()) <= 1.0


def test_handheld_presets_have_no_scanlines(node):
    """LCD-flavored presets (scan_depth=0) should not produce row-banding."""
    img = torch.full((1, 64, 64, 3), 0.5, dtype=torch.float32)
    for preset in ("nintendo_ds", "gameboy_advance", "psp"):
        (out,) = node.process(
            image=img, preset=preset, curvature=False,
            intensity=1.0, scanline_strength=1.0, mask_strength=1.0,
        )
        # Row means: if scanlines were applied, adjacent rows would alternate
        # significantly. Without scans, row-mean diff should stay small.
        row_means = out[0].mean(dim=(1, 2))  # H
        diffs = (row_means[1:] - row_means[:-1]).abs()
        assert float(diffs.max()) < 0.05, (
            f"{preset}: unexpected row banding (max diff {float(diffs.max()):.4f})"
        )
