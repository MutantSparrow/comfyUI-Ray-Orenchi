"""Tests for ray_vhs — preset dispatch + per-effect controls + OSD."""

import pytest
import torch

import ray_vhs as rv


_NO_OSD = dict(effect_fade=0.0, osd_status="Off", osd_status_corner="TL", osd_stamp="Off",
               osd_stamp_corner="BR", osd_date="", osd_color="White")


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
              "dropout_rate", "hiss", "yc_separation", "effect_fade", "osd_status",
              "osd_status_corner", "osd_stamp", "osd_stamp_corner", "osd_date", "osd_color", "seed"):
        assert k in req, f"missing widget: {k}"
    assert "osd_mode" not in req and "osd_corner" not in req
    # The fade starts at 0 (the full effect), not at the sliders' -1 "use the preset" sentinel.
    fade = req["effect_fade"][1]
    assert fade["default"] == 0.0 and fade["min"] == 0.0 and fade["max"] == 1.0
    assert rv.OSD_COLORS.keys() == {"White", "Yellow", "Green"}
    assert req["osd_color"][0] == ["White", "Yellow", "Green"]


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
        **_NO_OSD, seed=42,
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
    # Heavy chroma blur flattens the colour channels. (RGB saturation is the wrong measure: the checker's
    # brightness still alternates, which can raise max-min even when the colour has been averaged away.)
    from _common import rgb_to_yuv
    sa = rgb_to_yuv(a)[..., 1:].std().item()
    sb = rgb_to_yuv(b)[..., 1:].std().item()
    assert sb < sa * 0.6, f"chroma blur didn't flatten the colour channels: {sa} → {sb}"


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
        **_NO_OSD, seed=0,
    )
    (with_osd,) = node.process(
        image=img, preset="Pristine SP",
        chroma_blur=0.0, head_switch=0.0, tracking_jitter=0.0,
        dropout_rate=0.0, hiss=0.0, yc_separation=0.0,
        **{**_NO_OSD, "osd_status": "▶ PLAY", "osd_status_corner": "BL"}, seed=0,
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
        **_NO_OSD, seed=999,
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
        **_NO_OSD, seed=0,
    )
    (dirty,) = node.process(
        image=img, preset="Gen-3 dub",
        chroma_blur=-1.0, head_switch=-1.0, tracking_jitter=-1.0,
        dropout_rate=-1.0, hiss=-1.0, yc_separation=-1.0,
        **_NO_OSD, seed=0,
    )
    # Override-all-to-zero should be visibly cleaner than the preset
    assert (clean - img).abs().mean().item() < (dirty - img).abs().mean().item()


def test_common_yuv_round_trip():
    from _common import rgb_to_yuv, yuv_to_rgb
    img = torch.rand((1, 16, 16, 3))
    rt = yuv_to_rgb(rgb_to_yuv(img))
    assert torch.allclose(img, rt, atol=1e-4)


def _lit(img):
    """(rows, cols) of pixels bright enough to be OSD text."""
    return (img[0].max(dim=-1).values > 0.8).nonzero(as_tuple=True)


def _burn(img, lines, color="White"):
    """The OSD exactly as the character generator draws it, before any tape or analog wobble."""
    return rv._burn_in_osd(img, lines, color, 0.0, 0)


def test_osd_needs_no_system_font_glyphs():
    # Consolas and Courier New have no ▶, which used to print a missing-glyph box. The OSD is drawn from a
    # built-in pixel font, so its text is plain ASCII and the symbols are icons.
    for mode in rv.OSD_STATUS + rv.OSD_STAMP:
        assert rv._osd_text(mode, "").isascii(), mode
    assert rv._osd_icon("▶ PLAY") == "play" and rv._osd_icon("● REC") == "rec"
    assert rv._osd_icon("❚❚ PAUSE") == "pause" and rv._osd_icon("■ STOP") == "stop"
    assert rv._osd_icon("Date") is None and rv._osd_icon("Off") is None


def test_pixel_font_covers_everything_the_osd_can_show():
    for char in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789:.,-_+/'!?()%":
        rows = rv._OSD_GLYPHS[char].split("|")
        assert len(rows) == 7 and all(len(row) == 5 for row in rows), char
        assert any("X" in row for row in rows), char
    for icon, bitmap in rv._OSD_ICONS.items():
        rows = bitmap.split("|")
        assert len(rows) == 7 and all(len(row) == 5 for row in rows), icon
    # Lowercase, accents and unknown characters never raise and never print a missing-glyph box.
    assert rv._osd_glyph("a") == rv._osd_glyph("A")
    assert rv._osd_glyph("É") == rv._osd_glyph("E")
    assert rv._osd_glyph("☃") == rv._osd_glyph("?")


def test_osd_lines_follow_the_switches():
    assert rv.osd_lines() == []
    only_stamp = rv.osd_lines("Off", "TL", "Time", "BR")
    assert [line[2] for line in only_stamp] == ["BR"] and ":" in only_stamp[0][0]
    both = rv.osd_lines("● REC", "TL", "Date", "BR", "1987 06 05")
    assert [(t, i, c) for t, i, c in both] == [("REC", "rec", "TL"), ("1987 06 05", None, "BR")]
    assert rv.osd_lines("Off", "TL", "Date", "BR", "")[0][0].replace(" ", "").isdigit()
    # A custom date is only for the Date stamp; Time ignores it.
    assert "1987" not in rv.osd_lines("Off", "TL", "Time", "BR", "1987 06 05")[0][0]


def test_two_osd_lines_show_at_once_in_their_own_corners():
    img = _flat(h=128, w=256, color=(0.0, 0.0, 0.0))
    rows, cols = _lit(_burn(img, rv.osd_lines("● REC", "TL", "Date+Time", "BR")))
    top_left = (rows < 64) & (cols < 128)
    bottom_right = (rows >= 64) & (cols >= 128)
    assert top_left.sum() > 20 and bottom_right.sum() > 20
    assert not ((rows < 64) & (cols >= 128)).any() and not ((rows >= 64) & (cols < 128)).any()


def test_lines_sharing_a_corner_stack_status_above_stamp():
    img = _flat(h=256, w=512, color=(0.0, 0.0, 0.0))
    one = _lit(_burn(img, rv.osd_lines("▶ PLAY", "BL", "Off", "BL")))[0]
    two = _lit(_burn(img, rv.osd_lines("▶ PLAY", "BL", "Date", "BL")))[0]
    assert two.max() == one.max() or two.max() >= one.max()           # the block still ends at the margin
    assert two.min() < one.min()                                       # and grows upward
    assert (two.max() - two.min()) > 2 * (one.max() - one.min())


def test_osd_colours():
    img = _flat(h=128, w=256, color=(0.0, 0.0, 0.0))
    lines = rv.osd_lines("▶ PLAY", "TL", "Off", "BR")

    def lit_mean(color):
        out = _burn(img, lines, color)
        mask = out[0].max(dim=-1).values > 0.8
        return out[0][mask].mean(dim=0)

    white, yellow, green = lit_mean("White"), lit_mean("Yellow"), lit_mean("Green")
    assert white.min() > 0.85
    assert yellow[0] > 0.9 and yellow[1] > 0.7 and yellow[2] < 0.2
    assert green[1] > 0.9 and green[0] < 0.4 and green[2] < 0.5
    assert torch.equal(_burn(img, lines, "nonsense"), _burn(img, lines, "White"))


def test_osd_stays_inside_every_corner():
    img = _flat(h=128, w=256, color=(0.0, 0.0, 0.0))
    for corner, left, top in (("TL", True, True), ("TR", False, True), ("BL", True, False), ("BR", False, False)):
        rows, cols = _lit(_burn(img, [("REC", "rec", corner)]))
        assert rows.min() >= 0 and rows.max() < 128 and cols.min() >= 0 and cols.max() < 256, corner
        assert (cols.float().mean() < 128) == left and (rows.float().mean() < 64) == top, corner


def test_bottom_osd_stays_clear_of_the_head_switch_band():
    img = _flat(h=480, w=640, color=(0.0, 0.0, 0.0))
    rows, _ = _lit(_burn(img, [("REC", "rec", "BL")]))
    assert rows.max() < 480 - int(480 * (0.016 + 0.040)) - 4


def test_osd_icon_sits_left_of_the_text_and_pushes_it_right():
    img = _flat(h=128, w=256, color=(0.0, 0.0, 0.0))
    _, plain_cols = _lit(_burn(img, [("PLAY", None, "BL")]))
    for icon in ("play", "rec", "pause", "stop"):
        _, cols = _lit(_burn(img, [("PLAY", icon, "BL")]))
        assert cols.min() == plain_cols.min()                   # the icon starts where the text used to
        assert cols.max() > plain_cols.max(), icon              # and the text moved right to make room


def test_osd_scales_with_the_image():
    small = _lit(_burn(_flat(h=128, w=256, color=(0, 0, 0)), [("PLAY", "play", "BL")]))[0]
    big = _lit(_burn(_flat(h=1024, w=2048, color=(0, 0, 0)), [("PLAY", "play", "BL")]))[0]
    assert (big.max() - big.min()) > 4 * (small.max() - small.min())


def test_osd_has_a_dark_outline_and_a_smeared_shadow_on_bright_pictures():
    img = _flat(h=256, w=512, color=(0.8, 0.8, 0.8))
    out = _burn(img, [("REC", "rec", "TL")])
    darkened = (out[0].max(dim=-1).values < 0.7).nonzero(as_tuple=True)
    lit_rows, lit_cols = _lit(out)
    assert len(darkened[0]) > len(lit_rows) * 0.5                            # outline plus shadow around the text
    assert darkened[1].max() > lit_cols.max()                                 # the shadow trails past the glyphs


def test_osd_goes_through_the_tape_instead_of_sitting_on_top():
    img = _flat(h=240, w=640, color=(0.0, 0.0, 0.0))
    lines = rv.osd_lines("● REC", "TL", "Off", "BR")
    p = replace_params(rv.PRESETS["Worn EP"], head_switch=0.0, tracking_jitter=0.0, dropout_rate=0.0, hiss=0.0)
    crisp = _burn(img, lines, "Yellow")
    taped = rv.apply_vhs(img, p, p, osd=lines, osd_color="Yellow", seed=3)
    assert (taped[0].max(dim=-1).values > 0.95).sum() < (crisp[0].max(dim=-1).values > 0.95).sum()   # softened
    # Colour bleeds past the glyphs: pixels the crisp OSD left black pick up chroma.
    outside = crisp[0].max(dim=-1).values == 0
    bleed = rv.rgb_to_yuv(taped)[0, ..., 1:].abs().amax(dim=-1)
    assert (bleed[outside] > 0.02).sum() > 50
    # A different seed gives the OSD its own jitter; the same seed repeats it exactly.
    again = rv.apply_vhs(img, p, p, osd=lines, osd_color="Yellow", seed=3)
    other = rv.apply_vhs(img, p, p, osd=lines, osd_color="Yellow", seed=4)
    assert torch.equal(taped, again) and not torch.equal(taped, other)


def replace_params(p, **changes):
    from dataclasses import replace
    return replace(p, **changes)


def test_effect_fade_blends_back_toward_the_source():
    img = torch.rand((1, 64, 96, 3))
    p = rv.PRESETS["Gen-3 dub"]
    full = rv.apply_vhs(img, p, p, seed=1, effect_fade=0.0)
    half = rv.apply_vhs(img, p, p, seed=1, effect_fade=0.5)
    none = rv.apply_vhs(img, p, p, seed=1, effect_fade=1.0)
    assert torch.allclose(none, img, atol=1e-6)
    assert torch.allclose(half, 0.5 * full + 0.5 * img, atol=1e-5)
    assert torch.equal(full, rv.apply_vhs(img, p, p, seed=1))        # 0 is the default and changes nothing
    # Out-of-range values are clamped rather than extrapolating.
    assert torch.equal(rv.apply_vhs(img, p, p, seed=1, effect_fade=7.0), none)
    assert torch.equal(rv.apply_vhs(img, p, p, seed=1, effect_fade=-3.0), full)


def test_effect_fade_keeps_a_crisp_osd():
    img = _flat(h=128, w=256, color=(0.0, 0.0, 0.0))
    p = rv.PRESETS["Chewed tape"]
    lines = rv.osd_lines("● REC", "TL", "Date", "BR")
    out = rv.apply_vhs(img, p, p, osd=lines, osd_color="Green", seed=2, effect_fade=1.0)
    assert torch.equal(out, _burn(img, lines, "Green"))
    through_node, = rv.RayVHS().process(
        image=img, preset="Chewed tape", chroma_blur=-1.0, head_switch=-1.0, tracking_jitter=-1.0,
        dropout_rate=-1.0, hiss=-1.0, yc_separation=-1.0,
        **{**_NO_OSD, "effect_fade": 1.0, "osd_status": "● REC", "osd_color": "Green"}, seed=2)
    assert through_node.shape == img.shape and (through_node[0].max(dim=-1).values > 0.8).any()


# ---------------------------------------------------------------------------
# Signal chain and presets
# ---------------------------------------------------------------------------

from dataclasses import replace  # noqa: E402


def _only(preset, **kw):
    """The preset's tape and deck character with every slider effect switched off, then `kw` applied."""
    sliders = dict(chroma_blur=0.0, head_switch=0.0, tracking_jitter=0.0, dropout_rate=0.0, hiss=0.0, yc_separation=0.0)
    return replace(preset, **{**sliders, **kw})


def _edge(h, w, left, right):
    img = torch.zeros((1, h, w, 3))
    img[:, :, : w // 2] = torch.tensor(left)
    img[:, :, w // 2:] = torch.tensor(right)
    return img


def _transition(row, lo=0.1, hi=0.9):
    """Width, as a fraction of the row, over which `row` goes from `lo` to `hi` of its range."""
    row = row - row.min()
    row = row / row.max().clamp_min(1e-6)
    return ((row > lo) & (row < hi)).sum().item() / row.numel()


def test_all_presets_exist_and_are_in_range():
    expected = ["Pristine SP", "S-VHS", "Worn EP", "Gen-3 dub", "VHS-C camcorder", "Hi8",
                "Rental tape", "Off-air LP", "Chewed tape", "Custom"]
    assert rv.PRESET_NAMES == expected
    for name, p in rv.PRESETS.items():
        assert p.label == name
        for field in ("chroma_blur", "head_switch", "tracking_jitter", "dropout_rate", "hiss", "yc_separation", "chroma_noise", "ringing"):
            assert 0.0 <= getattr(p, field) <= 1.0, (name, field)
        assert 150 <= p.luma_res <= 600 and p.vres > 0, name


def test_neutral_settings_leave_the_image_untouched():
    # Saturated red/green exceed the tape's normal V clamp. A neutral node
    # should bypass the tape transform, rather than clip these rare pixels.
    img = torch.tensor([[[[1., 0., 0.], [0., 1., 0.], [0., 0., 1.], [.12, .45, .78]]]])
    p = rv.VHSParams("neutral", 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    out = rv.apply_vhs(img, p, p, seed=1)
    torch.testing.assert_close(out, img, atol=0, rtol=0)


def test_every_preset_runs_through_the_node_and_stays_in_range():
    img = torch.rand((2, 48, 64, 3))
    for name in rv.PRESET_NAMES:
        (out,) = rv.RayVHS().process(
            image=img, preset=name, chroma_blur=-1.0, head_switch=-1.0, tracking_jitter=-1.0,
            dropout_rate=-1.0, hiss=-1.0, yc_separation=-1.0,
            **{**_NO_OSD, "osd_status": "▶ PLAY", "osd_stamp": "Date+Time"}, seed=11)
        assert out.shape == img.shape and out.min() >= 0.0 and out.max() <= 1.0, name


def test_tiny_images_and_extreme_sliders_do_not_crash():
    worst = rv.PRESETS["Chewed tape"]
    for shape in ((1, 1, 1, 3), (1, 2, 3, 3), (1, 8, 8, 3), (3, 5, 200, 3)):
        out = rv.apply_vhs(torch.rand(shape), worst, worst, seed=2, osd=rv.osd_lines("● REC", "TL", "Date+Time", "BR"))
        assert out.shape == shape and torch.isfinite(out).all()


def test_effects_are_sized_to_the_picture_not_to_pixels():
    # The same preset must smear colour and soften edges by the same fraction of the width at any size.
    colour = _only(rv.PRESETS["Worn EP"], chroma_blur=0.7)
    luma = _only(rv.PRESETS["Worn EP"], ringing=0.0)   # halos overshoot the edge and would skew the measurement
    widths = []
    for w in (320, 1280):
        h = w // 4
        chroma_row = rv.rgb_to_yuv(rv.apply_vhs(_edge(h, w, (0.9, 0.1, 0.1), (0.1, 0.1, 0.9)), colour, colour, seed=0))[0, h // 2, :, 2]
        luma_row = rv.apply_vhs(_edge(h, w, (0.05, 0.05, 0.05), (0.95, 0.95, 0.95)), luma, luma, seed=0)[0, h // 2, :, 0]
        widths.append((_transition(chroma_row), _transition(luma_row)))
    (c_small, l_small), (c_big, l_big) = widths
    assert abs(c_big - c_small) / c_small < 0.3, f"chroma smear {c_small:.3f} vs {c_big:.3f} of the width"
    assert abs(l_big - l_small) < 0.02, f"luma softness {l_small:.3f} vs {l_big:.3f} of the width"
    assert c_big > 0.03, "chroma should be smeared over several percent of the width"


def test_colour_is_far_softer_than_luma_and_lags_to_the_right():
    p = _only(rv.PRESETS["Pristine SP"], chroma_blur=0.55)
    h, w = 80, 640
    out = rv.rgb_to_yuv(rv.apply_vhs(_edge(h, w, (0.1, 0.1, 0.1), (0.9, 0.2, 0.2)), p, p, seed=0))[0, h // 2]
    chroma_w, luma_w = _transition(out[:, 1]), _transition(out[:, 0])
    assert chroma_w > 3 * luma_w, f"chroma {chroma_w:.3f} vs luma {luma_w:.3f}"

    def middle(row):
        scaled = (row - row.min()) / (row.max() - row.min())
        return ((scaled > 0.5).nonzero()[0].item())

    assert middle(out[:, 1].abs()) > middle(out[:, 0]), "colour should change after the brightness does"


def test_better_tapes_are_softer_than_worse_ones():
    edge = _edge(96, 640, (0.05, 0.05, 0.05), (0.95, 0.95, 0.95))
    soft = {}
    for name in ("S-VHS", "Hi8", "Pristine SP", "Worn EP", "Gen-3 dub"):
        p = _only(rv.PRESETS[name], ringing=0.0)
        soft[name] = _transition(rv.apply_vhs(edge, p, p, seed=0)[0, 48, :, 0])
    assert soft["S-VHS"] <= soft["Hi8"] <= soft["Pristine SP"] <= soft["Worn EP"] <= soft["Gen-3 dub"], soft
    assert soft["Gen-3 dub"] > soft["S-VHS"] * 1.5, soft


def test_presets_get_progressively_worse():
    torch.manual_seed(0)
    h, w = 120, 320
    yy, xx = torch.meshgrid(torch.linspace(0, 1, h), torch.linspace(0, 1, w), indexing="ij")
    img = torch.stack([0.2 + 0.6 * xx, 0.3 + 0.4 * yy, 0.7 - 0.5 * xx * yy], dim=-1).unsqueeze(0)
    img[:, 30:90, 60:90] = torch.tensor([0.9, 0.2, 0.2])
    img[:, 30:90, 200:230] = torch.tensor([0.1, 0.8, 0.3])
    distortion = {}
    for name in ("S-VHS", "Pristine SP", "Worn EP", "Gen-3 dub", "Chewed tape"):
        p = rv.PRESETS[name]
        distortion[name] = (rv.apply_vhs(img, p, p, seed=4) - img).abs().mean().item()
    order = list(distortion.values())
    assert order == sorted(order), distortion


def test_noise_streams_are_independent_so_one_control_does_not_reshuffle_another():
    img = _flat(h=120, w=160, color=(0.4, 0.5, 0.6))
    base = _only(rv.PRESETS["Worn EP"], hiss=0.5)
    with_tear = replace(base, head_switch=1.0)
    a = rv.apply_vhs(img, base, base, seed=9)
    b = rv.apply_vhs(img, with_tear, with_tear, seed=9)
    band = max(3, int(round(120 * (0.016 + 0.040 * 1.0))))
    assert torch.equal(a[:, : 120 - band - 2], b[:, : 120 - band - 2]), "tape noise above the tear changed"
    assert not torch.equal(a[:, -band:], b[:, -band:])


def test_seeds_reproduce_and_differ_and_batch_frames_are_not_copies():
    img = _flat(h=64, w=96).repeat(2, 1, 1, 1)
    p = rv.PRESETS["Gen-3 dub"]
    a = rv.apply_vhs(img, p, p, seed=21)
    assert torch.equal(a, rv.apply_vhs(img, p, p, seed=21))
    assert not torch.equal(a, rv.apply_vhs(img, p, p, seed=22))
    assert not torch.equal(a[0], a[1])


def test_time_base_error_is_smooth_not_random_rows():
    gen = torch.Generator().manual_seed(3)
    offsets, _bands = rv._time_base(480, 640, 0.5, 0.0, gen)
    neighbour_step = (offsets[1:] - offsets[:-1]).abs().mean().item()
    shuffled = offsets[torch.randperm(480, generator=torch.Generator().manual_seed(1))]
    assert neighbour_step < 0.8 * (shuffled[1:] - shuffled[:-1]).abs().mean().item()
    assert offsets.abs().max() > 0.5


def test_tracking_bands_appear_only_when_the_tape_is_unstable():
    calm = sum(float(rv._time_base(480, 640, 0.02, 0.0, torch.Generator().manual_seed(s))[1].max()) for s in range(30))
    rough = sum(float(rv._time_base(480, 640, 0.9, 0.0, torch.Generator().manual_seed(s))[1].max()) for s in range(30))
    assert calm < 2.0 and rough > 20.0, (calm, rough)


def test_head_switch_skews_progressively_toward_the_bottom():
    H, W = 480, 640
    offsets, noise = rv._head_switch(H, W, 1.0, torch.Generator().manual_seed(2))
    band = max(3, int(round(H * (0.016 + 0.040))))
    assert torch.count_nonzero(offsets[: H - band]) == 0 and torch.count_nonzero(noise[: H - band]) == 0
    inside = offsets[H - band:].abs()
    third = band // 3
    assert inside[:third].mean() < inside[third: 2 * third].mean() < inside[2 * third:].mean()
    assert inside.max() > 0.04 * W, "a full head-switch should pull the bottom lines sideways by several percent"
    assert noise[-1] > 0.9 and noise[H - band] == 0


def test_dropouts_scale_with_rate_and_picture_size():
    def area(rate, h, w, seeds=12):
        return sum(float(rv._dropout_layer(h, w, rate, h, torch.Generator().manual_seed(s))[0].sum()) for s in range(seeds))

    assert area(0.0, 240, 320) == 0
    assert area(0.8, 240, 320) > 3 * area(0.1, 240, 320)
    # Twice the width and height: streaks are longer and thicker and there are more of them.
    assert area(0.4, 480, 640) > 3 * area(0.4, 240, 320)
    mask, level = rv._dropout_layer(240, 320, 0.8, 240, torch.Generator().manual_seed(0))
    assert float(mask.max()) <= 1.0 and float(level.max()) <= 1.15 and float(level.min()) >= 0.0


def test_dropouts_never_land_in_the_head_switch_lines():
    mask, _ = rv._dropout_layer(300, 400, 1.0, 280, torch.Generator().manual_seed(5))
    assert float(mask[280:].sum()) == 0


def test_hiss_is_streaky_along_the_scanline_not_per_pixel_grain():
    shape = (1, 1, 96, 320)
    noise = rv._streaky_noise(shape, 3.0, 0.0, torch.Generator().manual_seed(1))[0, 0]
    along = torch.corrcoef(torch.stack([noise[:, :-1].reshape(-1), noise[:, 1:].reshape(-1)]))[0, 1]
    down = torch.corrcoef(torch.stack([noise[:-1].reshape(-1), noise[1:].reshape(-1)]))[0, 1]
    assert along > 0.6 and abs(down) < 0.2, (float(along), float(down))
