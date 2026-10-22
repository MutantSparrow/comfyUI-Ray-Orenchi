import importlib.util
import json
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "benchmarks" / "pixel_art" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_cluster_and_noise_proxies_detect_speckle():
    metrics = load("perceptual")
    clean = np.zeros((16, 16, 3), np.float32)
    clean[4:12, 4:12] = 1
    noise = np.random.default_rng(1).random((16, 16, 3), dtype=np.float32)
    a, b = metrics.diagnostics(clean), metrics.diagnostics(noise)
    assert a["isolated_pixel_fraction"] == a["tiny_cluster_pixel_fraction"] == 0
    assert a["cluster_count"] == 2
    assert b["isolated_pixel_fraction"] > .9
    assert b["local_colors_mean_8x8"] > a["local_colors_mean_8x8"]
    assert a["silhouette_iou"] is None


def test_regular_dither_is_reported_separately_from_tone():
    metrics = load("perceptual")
    checker = np.repeat((np.indices((16, 16)).sum(0) % 2)[..., None], 3, axis=2).astype(np.float32)
    score = metrics.diagnostics(checker, np.full_like(checker, .5))
    assert score["checkerboard_fraction"] == 1
    assert score["low_frequency_oklab_error"] < .01
    assert "quality_score" not in score


def test_explicit_masks_and_different_resolutions():
    metrics = load("perceptual")
    mask = np.zeros((8, 8), np.float32)
    mask[2:6, 2:6] = 1
    assert metrics.mask_metrics(mask, mask[::2, ::2])["silhouette_iou"] == 1
    assert metrics.mask_metrics(mask, 1 - mask)["silhouette_iou"] == 0


def test_blinded_report_embeds_images_and_escapes_html(tmp_path):
    metrics = load("perceptual")
    for name, color in (("source", "gray"), ("a", "black"), ("b", "white")):
        Image.new("RGB", (8, 8), color).save(tmp_path / f"{name}.png")
    case = {"id": "</script><script>bad()</script>", "source": "source.png",
            "candidates": [{"method": "first", "image": "a.png"}, {"method": "second", "image": "b.png"}]}
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"cases": [case]}), encoding="utf-8")
    report, pairs = metrics.evaluate(manifest, tmp_path / "out")
    assert len(report) == 2 and len(pairs) == 1
    html = (tmp_path / "out" / "pairwise.html").read_text(encoding="utf-8")
    assert case["id"] not in html
    assert "data:image/png;base64," in html
    assert "human_conversion_pairwise" in html


def test_human_votes_are_deduplicated_and_ties_retained(tmp_path):
    rank = load("rank_votes")
    base = {"track": "human_conversion_pairwise", "reviewer": "person-1", "votes": [
        {"case": "sample", "left": "a", "right": "b", "choice": "left"}]}
    one = tmp_path / "one.json"
    one.write_text(json.dumps(base))
    base["votes"][0]["choice"] = "tie"
    two = tmp_path / "two.json"
    two.write_text(json.dumps(base))
    result = rank.aggregate([one, two])
    assert result == [{"case": "sample", "a": "a", "b": "b", "a_wins": 0, "b_wins": 0, "ties": 1, "skips": 0}]
