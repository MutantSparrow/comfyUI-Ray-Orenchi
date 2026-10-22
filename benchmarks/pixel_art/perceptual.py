"""Pixel-art structure diagnostics and offline, blinded pairwise review.

These proxies are deliberately reported separately. They are not a calibrated
artistic-quality score; one-pixel highlights and intentional dithering are valid.
"""
import argparse
import base64
from itertools import combinations
import json
from pathlib import Path
import random

import numpy as np
from PIL import Image


def rgb(path):
    with Image.open(path) as source:
        return np.asarray(source.convert("RGB"), dtype=np.float32) / 255


def labels_and_clusters(image):
    colors, labels = np.unique(np.rint(np.clip(image, 0, 1) * 255).astype(np.uint8).reshape(-1, 3),
                               axis=0, return_inverse=True)
    h, w = image.shape[:2]
    labels = labels.reshape(h, w)
    parents = np.arange(h * w)
    def find(index):
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index
    for y in range(h):
        for x in range(w):
            index = y * w + x
            for yy, xx in ((y - 1, x), (y, x - 1)):
                if yy >= 0 and xx >= 0 and labels[y, x] == labels[yy, xx]:
                    parents[find(index)] = find(yy * w + xx)
    roots = np.array([find(index) for index in range(h * w)]).reshape(h, w)
    _, counts = np.unique(roots, return_counts=True)
    return colors.astype(np.float32) / 255, labels, roots, counts


def staircase_variation(roots):
    """Row-contour step jitter of the eight largest color clusters (lower is smoother)."""
    ids, areas = np.unique(roots, return_counts=True)
    changes = []
    for region in ids[np.argsort(areas)[-8:]]:
        ys, xs = np.where(roots == region)
        if len(ys) < 8:
            continue
        rows = np.unique(ys)
        for side in (min, max):
            positions = np.array([side(xs[ys == y]) for y in rows])
            contiguous = (np.diff(rows)[:-1] == 1) & (np.diff(rows)[1:] == 1)
            changes.extend(np.abs(np.diff(positions, n=2))[contiguous].tolist())
    return float(np.mean(changes)) if changes else None


def mask_metrics(reference, candidate):
    reference = np.asarray(reference) > .5
    candidate = np.asarray(candidate) > .5
    if reference.shape != candidate.shape:
        candidate = np.asarray(Image.fromarray(candidate).resize((reference.shape[1], reference.shape[0]), Image.Resampling.NEAREST))
    union = (reference | candidate).sum()
    return {"silhouette_iou": float((reference & candidate).sum() / union) if union else 1.0}


def diagnostics(image, source=None, reference_mask=None, candidate_mask=None):
    if image.ndim != 3 or image.shape[2] != 3 or min(image.shape[:2]) < 1:
        raise ValueError("Expected a nonempty RGB image.")
    palette, labels, roots, areas = labels_and_clusters(image)
    h, w = labels.shape
    padded = np.pad(labels, 1, mode="constant", constant_values=-1)
    same_neighbor = np.zeros((h, w), dtype=bool)
    for dy in range(3):
        for dx in range(3):
            if (dy, dx) != (1, 1):
                same_neighbor |= padded[dy:dy+h, dx:dx+w] == labels
    local = [len(np.unique(labels[y:y+8, x:x+8])) for y in range(0, h, 8) for x in range(0, w, 8)]
    checker = ((labels[:-1, :-1] == labels[1:, 1:]) &
               (labels[:-1, 1:] == labels[1:, :-1]) &
               (labels[:-1, :-1] != labels[:-1, 1:]))
    result = {
        "width": w, "height": h, "palette_colors": len(palette),
        "isolated_pixel_fraction": float((~same_neighbor).mean()),
        "tiny_cluster_pixel_fraction": float(areas[areas <= 2].sum() / labels.size),
        "cluster_count": len(areas), "median_cluster_area": float(np.median(areas)),
        "local_colors_mean_8x8": float(np.mean(local)),
        "local_colors_p90_8x8": float(np.percentile(local, 90)),
        "contour_step_variation": staircase_variation(roots),
        "checkerboard_fraction": float(checker.mean()) if checker.size else 0.0,
        "palette_ramp_chroma_step": None, "palette_ramp_gap_cv": None,
        "low_frequency_oklab_error": None, "silhouette_iou": None,
    }
    # Group approximate hue ramps, then inspect their sorted lightness steps.
    from ray_pixel_detector import oklab
    lab = oklab(palette)
    chroma = np.linalg.norm(lab[:, 1:], axis=1)
    hue = np.arctan2(lab[:, 2], lab[:, 1])
    groups = np.where(chroma < .035, -1, np.floor((hue + np.pi) * 8 / (2 * np.pi)).astype(int))
    steps, gaps = [], []
    for group in np.unique(groups):
        ramp = lab[groups == group]
        if len(ramp) >= 3:
            ordered = ramp[np.argsort(ramp[:, 0])]
            steps.extend(np.linalg.norm(np.diff(ordered[:, 1:], axis=0), axis=1).tolist())
            delta = np.diff(ordered[:, 0])
            if delta.mean() > 1e-8:
                gaps.append(float(delta.std() / delta.mean()))
    if steps:
        result["palette_ramp_chroma_step"] = float(np.mean(steps))
        result["palette_ramp_gap_cv"] = float(np.mean(gaps)) if gaps else None
    if source is not None:
        def tone(pixels):
            return np.asarray(Image.fromarray(np.rint(np.clip(pixels, 0, 1) * 255).astype(np.uint8))
                              .resize((max(1, w // 8), max(1, h // 8)), Image.Resampling.BOX), np.float32) / 255
        result["low_frequency_oklab_error"] = float(np.linalg.norm(oklab(tone(image)) - oklab(tone(source)), axis=-1).mean())
    if reference_mask is not None and candidate_mask is not None:
        result.update(mask_metrics(reference_mask, candidate_mask))
    return result


def data_image(path):
    # Re-encode user-selected images so HTML never injects file text or metadata.
    import io
    with Image.open(path) as source:
        buffer = io.BytesIO()
        source.convert("RGB").save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def evaluate(manifest_path, output):
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    folder = manifest_path.parent
    report, pairs = [], []
    rng = random.Random(42)
    for case in manifest["cases"]:
        source_path = folder / case["source"]
        source = rgb(source_path)
        reference = rgb(folder / case["source_mask"])[..., 0] if case.get("source_mask") else None
        candidates = case["candidates"]
        for candidate in candidates:
            path = folder / candidate["image"]
            mask = rgb(folder / candidate["mask"])[..., 0] if candidate.get("mask") else None
            report.append({"case": case["id"], "method": candidate["method"],
                           **diagnostics(rgb(path), source, reference, mask)})
        for a, b in combinations(candidates, 2):
            left, right = (a, b) if rng.randrange(2) else (b, a)
            pairs.append({"case": case["id"], "source": data_image(source_path),
                          "left": {"method": left["method"], "image": data_image(folder / left["image"])},
                          "right": {"method": right["method"], "image": data_image(folder / right["image"])}})
    rng.shuffle(pairs)
    output.mkdir(parents=True, exist_ok=True)
    (output / "diagnostics.json").write_text(json.dumps({"track": "conversion_structure_diagnostics", "results": report}, indent=2), encoding="utf-8")
    payload = json.dumps(pairs).replace("<", "\\u003c")
    html = (Path(__file__).with_name("pairwise.html").read_text(encoding="utf-8")
            .replace("/* PAIRS */ []", payload))
    (output / "pairwise.html").write_text(html, encoding="utf-8")
    return report, pairs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path, default=Path("perceptual-results"))
    args = parser.parse_args()
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    report, pairs = evaluate(args.manifest.resolve(), args.output.resolve())
    print(f"{len(report)} diagnostic rows and {len(pairs)} blinded pairs; human votes have not been supplied.")


if __name__ == "__main__":
    main()
