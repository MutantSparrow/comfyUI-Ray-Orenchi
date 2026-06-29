"""Tests for ray_vhs — preset dispatch + per-effect controls + OSD."""

import pytest
import torch

import ray_vhs as rv


def _flat(h=32, w=64, color=(0.5, 0.5, 0.5)):
    img = torch.zeros((1, h, w, 3), dtype=torch.float32)
    img[..., 0] = color[0]
    img[..., 1] = color[1]
    img[..., 2] = color[2]
    return img


def _checker(h=32, w=64):
    """High-frequency checkerboard — exercises chroma blur."""
    img = torch.zeros((1, h, w, 3), dtype=torch.float32)
    xs = torch.arange(w).view(1, 1, w, 1)
    ys = torch.arange(h).view(1, h, 1, 1)
    pattern = ((xs + ys) % 2).float()
    img[..., 0] = pattern.squeeze(-1)
    img[..., 1] = 1.0 - pattern.squeeze(-1)
    return img


def test_input_types_declares_required():
    it = rv.RayVHS.INPUT_TYPES()
    req = it["required"]
    for k in ("image", "preset", "chroma_blur", "head_switch", "tracking_jitter",
              "dropout_rate", "hiss", "yc_separation", "osd_mode", "osd_corner",
              "osd_date", "seed"):
        assert k in req, f"missing widget: {k}"


def test_presets_cover_v1_set():
    assert "Pristine SP" in rv.PRESETS
    assert "Worn EP" in rv.PRESETS
    assert "Gen-3 dub" in rv.PRESETS
    assert "VHS-C camcorder" in rv.PRESETS
    assert "Hi8" in rv.PRESETS
    assert "Custom" in rv.PRESETS


def test_node_returns_image_tensor():
    img = _flat()
    node = rv.RayVHS()
    (out,) = node.process(
        image=img, preset="Pristine SP",
        chroma_blur=-1.0, head_switch=-1.0, tracking_jitter=-1.0,
        dropout_rate=-1.0, hiss=-1.0, yc_separation=-1.0,
        osd_mode="Off", osd_corner="BL", osd_date="", seed=42,
    )
    assert out.shape == img.shape
    assert out.dtype == torch.float32
    assert out.min().item() >= 0.0
    assert out.max().item() <= 1.0


def test_chroma_blur_reduces_chroma_variance():
    img = _checker()
    base = rv.PRESETS["Custom"]
    no_blur = rv.VHSParams(**{**base.__dict__, "chroma_blur": 0.0,
                              "head_switch": 0.0, "tracking_jitter": 0.0,
                              "dropout_rate": 0.0, "hiss": 0.0, "yc_separation": 0.0})
    heavy = rv.VHSParams(**{**base.__dict__, "chroma_blur": 1.0,
                            "head_switch": 0.0, "tracking_jitter": 0.0,
                            "dropout_rate": 0.0, "hiss": 0.0, "yc_separation": 0.0})
    a = rv.apply_vhs(img, no_blur, no_blur, seed=0)
    b = rv.apply_vhs(img, heavy, heavy, seed=0)
    # Heavy chroma blur should reduce per-pixel saturation variance
    sa = (a.max(dim=-1).values - a.min(dim=-1).values).std().item()
    sb = (b.max(dim=-1).values - b.min(dim=-1).values).std().item()
    assert sb < sa, f"chroma blur didn't reduce saturation variance: {sa} → {sb}"


def test_head_switch_alters_bottom_rows():
    img = _checker(h=64, w=64)
    base = rv.PRESETS["Custom"]
    clean = rv.VHSParams(**{**base.__dict__, "chroma_blur": 0.0,
                            "head_switch": 0.0, "tracking_jitter": 0.0,
                            "dropout_rate": 0.0, "hiss": 0.0, "yc_separation": 0.0})
    sw = rv.VHSParams(**{**clean.__dict__, "head_switch": 1.0})
    a = rv.apply_vhs(img, clean, clean, seed=0)
    b = rv.apply_vhs(img, sw, sw, seed=0)
    top_diff = (a[:, :32] - b[:, :32]).abs().mean().item()
    bot_diff = (a[:, 56:] - b[:, 56:]).abs().mean().item()
    assert bot_diff > top_diff + 0.005


def test_osd_alters_chosen_corner():
    img = _flat(h=128, w=256, color=(0.3, 0.3, 0.3))
    node = rv.RayVHS()
    (no_osd,) = node.process(
        image=img, preset="Pristine SP",
        chroma_blur=0.0, head_switch=0.0, tracking_jitter=0.0,
        dropout_rate=0.0, hiss=0.0, yc_separation=0.0,
        osd_mode="Off", osd_corner="BL", osd_date="", seed=0,
    )
    (with_osd,) = node.process(
        image=img, preset="Pristine SP",
        chroma_blur=0.0, head_switch=0.0, tracking_jitter=0.0,
        dropout_rate=0.0, hiss=0.0, yc_separation=0.0,
        osd_mode="▶ PLAY", osd_corner="BL", osd_date="", seed=0,
    )
    bl_diff = (no_osd[:, -32:, :96] - with_osd[:, -32:, :96]).abs().mean().item()
    tr_diff = (no_osd[:, :32, -96:] - with_osd[:, :32, -96:]).abs().mean().item()
    assert bl_diff > tr_diff, f"OSD didn't land in bottom-left: bl={bl_diff} tr={tr_diff}"


def test_seed_is_deterministic():
    img = _flat()
    node = rv.RayVHS()
    kwargs = dict(
        image=img, preset="Worn EP",
        chroma_blur=-1.0, head_switch=-1.0, tracking_jitter=-1.0,
        dropout_rate=-1.0, hiss=-1.0, yc_separation=-1.0,
        osd_mode="Off", osd_corner="BL", osd_date="", seed=999,
    )
    (a,) = node.process(**kwargs)
    (b,) = node.process(**kwargs)
    assert torch.allclose(a, b)


def test_slider_overrides_preset():
    img = _flat()
    node = rv.RayVHS()
    (clean,) = node.process(
        image=img, preset="Gen-3 dub",
        chroma_blur=0.0, head_switch=0.0, tracking_jitter=0.0,
        dropout_rate=0.0, hiss=0.0, yc_separation=0.0,
        osd_mode="Off", osd_corner="BL", osd_date="", seed=0,
    )
    (dirty,) = node.process(
        image=img, preset="Gen-3 dub",
        chroma_blur=-1.0, head_switch=-1.0, tracking_jitter=-1.0,
        dropout_rate=-1.0, hiss=-1.0, yc_separation=-1.0,
        osd_mode="Off", osd_corner="BL", osd_date="", seed=0,
    )
    # Override-all-to-zero should be visibly cleaner than the preset
    assert (clean - img).abs().mean().item() < (dirty - img).abs().mean().item()


def test_common_yuv_round_trip():
    from _common import rgb_to_yuv, yuv_to_rgb
    img = torch.rand((1, 16, 16, 3))
    rt = yuv_to_rgb(rgb_to_yuv(img))
    assert torch.allclose(img, rt, atol=1e-4)
