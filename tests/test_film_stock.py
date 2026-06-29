"""Tests for ray_film_stock — film emulation + .cube LUT pipeline."""

import math
import pathlib

import pytest
import torch

import ray_film_stock as rfs


def _ramp(h=32, w=32):
    """Horizontal gradient 0→1, BHWC float32."""
    x = torch.linspace(0.0, 1.0, w).view(1, 1, w, 1)
    img = x.expand(1, h, w, 3).contiguous().clone()
    return img.float()


def _flat(h=8, w=8, v=0.5):
    return torch.full((1, h, w, 3), float(v), dtype=torch.float32)


def test_input_types_declares_required():
    it = rfs.RayFilmStock.INPUT_TYPES()
    assert "image" in it["required"]
    assert "preset" in it["required"]
    assert "lut_path" in it["optional"]


def test_stock_names_includes_all_families():
    names = rfs.STOCK_NAMES
    assert "Kodak Portra 400" in names
    assert "CineStill 800T" in names
    assert "Kodak Tri-X 400" in names
    assert "Fuji Velvia 50" in names
    assert "Custom" in names


def test_node_returns_image_tensor():
    img = _ramp()
    node = rfs.RayFilmStock()
    (out,) = node.process(
        image=img, preset="Kodak Portra 400",
        intensity=1.0, grain_amount=1.0, halation_amount=1.0,
        expose_stops=0.0, seed=42,
    )
    assert out.shape == img.shape
    assert out.dtype == torch.float32
    assert out.min().item() >= 0.0
    assert out.max().item() <= 1.0


def test_grain_adds_noise():
    img = _flat(64, 64, 0.5)
    node = rfs.RayFilmStock()
    (out,) = node.process(
        image=img, preset="Ilford Delta 3200",
        intensity=1.0, grain_amount=4.0, halation_amount=0.0,
        expose_stops=0.0, seed=1,
    )
    # Flat input should pick up measurable noise from heavy-grain stock
    assert out.std().item() > 0.005


def test_bw_stock_desaturates():
    img = _flat(16, 16, 0.5).clone()
    img[..., 0] = 0.8
    img[..., 2] = 0.2
    node = rfs.RayFilmStock()
    (out,) = node.process(
        image=img, preset="Kodak Tri-X 400",
        intensity=1.0, grain_amount=0.0, halation_amount=0.0,
        expose_stops=0.0, seed=0,
    )
    # All three channels should be similar after desaturation
    avg = out.mean(dim=(0, 1, 2))
    spread = float(avg.max() - avg.min())
    assert spread < 0.05, f"channels not desaturated, spread={spread}"


def test_halation_reddens_highlights():
    img = torch.zeros((1, 32, 32, 3), dtype=torch.float32)
    img[:, 12:20, 12:20, :] = 1.0  # bright square
    node = rfs.RayFilmStock()
    (no_hal,) = node.process(
        image=img, preset="CineStill 800T",
        intensity=1.0, grain_amount=0.0, halation_amount=0.0,
        expose_stops=0.0, seed=0,
    )
    (with_hal,) = node.process(
        image=img, preset="CineStill 800T",
        intensity=1.0, grain_amount=0.0, halation_amount=4.0,
        expose_stops=0.0, seed=0,
    )
    # Region adjacent to the highlight should pick up red glow
    border_no = no_hal[:, 8:12, 12:20, 0].mean().item()
    border_with = with_hal[:, 8:12, 12:20, 0].mean().item()
    assert border_with > border_no + 0.01


def test_intensity_zero_returns_near_input():
    img = _ramp()
    node = rfs.RayFilmStock()
    (out,) = node.process(
        image=img, preset="Kodak Portra 400",
        intensity=0.0, grain_amount=1.0, halation_amount=1.0,
        expose_stops=0.0, seed=42,
    )
    diff = (out - img).abs().mean().item()
    assert diff < 0.01


def test_expose_stops_brightens():
    img = _flat(16, 16, 0.3)
    node = rfs.RayFilmStock()
    (dim,) = node.process(
        image=img, preset="Custom",
        intensity=1.0, grain_amount=0.0, halation_amount=0.0,
        expose_stops=0.0, seed=0,
    )
    (bright,) = node.process(
        image=img, preset="Custom",
        intensity=1.0, grain_amount=0.0, halation_amount=0.0,
        expose_stops=2.0, seed=0,
    )
    assert bright.mean().item() > dim.mean().item() + 0.1


def test_seed_is_deterministic():
    img = _flat(16, 16, 0.5)
    node = rfs.RayFilmStock()
    (a,) = node.process(image=img, preset="Kodak Tri-X 400", intensity=1.0,
                        grain_amount=2.0, halation_amount=0.0,
                        expose_stops=0.0, seed=123)
    (b,) = node.process(image=img, preset="Kodak Tri-X 400", intensity=1.0,
                        grain_amount=2.0, halation_amount=0.0,
                        expose_stops=0.0, seed=123)
    assert torch.allclose(a, b)


# ----- .cube LUT parsing/apply ---------------------------------------------


def _identity_cube_text(n=4):
    """A trivial identity LUT — every (r,g,b) index maps to itself."""
    lines = [f"LUT_3D_SIZE {n}"]
    for b in range(n):
        for g in range(n):
            for r in range(n):
                rv = r / (n - 1)
                gv = g / (n - 1)
                bv = b / (n - 1)
                lines.append(f"{rv:.6f} {gv:.6f} {bv:.6f}")
    return "\n".join(lines)


def test_parse_cube_identity():
    text = _identity_cube_text(8)
    lut = rfs.parse_cube_lut(text)
    assert lut["size"] == 8
    assert lut["data"].shape == (8, 8, 8, 3)


def test_parse_cube_rejects_bad_input():
    with pytest.raises(ValueError):
        rfs.parse_cube_lut("not a lut")


def test_apply_identity_lut_is_close_to_input():
    img = _ramp(8, 8)
    lut = rfs.parse_cube_lut(_identity_cube_text(8))
    out = rfs.apply_cube_lut(img, lut)
    assert torch.allclose(out, img, atol=0.05)


def test_lut_path_in_node(tmp_path):
    p = tmp_path / "id.cube"
    p.write_text(_identity_cube_text(4))
    img = _flat(16, 16, 0.5)
    node = rfs.RayFilmStock()
    (out,) = node.process(
        image=img, preset="Custom",
        intensity=1.0, grain_amount=0.0, halation_amount=0.0,
        expose_stops=0.0, seed=0, lut_path=str(p),
    )
    # Identity LUT keeps mid-gray roughly mid-gray after the pipeline
    assert 0.3 < out.mean().item() < 0.7
