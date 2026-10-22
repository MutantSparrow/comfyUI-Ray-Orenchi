"""Prepare a small synthetic conversion corpus, or use a curated source folder.

Add external converters with --competitor name=directory; each directory should
contain <case-id>.png at the same target resolution/palette budget.
"""
import argparse
import json
from pathlib import Path
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from ray_pixel_detector import RayPixelArtDetector, approximate_size


def demo_sources(folder):
    folder.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(12)
    for index, name in enumerate(("flat_shapes", "diagonal_contours", "soft_shading", "busy_texture", "small_accents", "smooth_ramps")):
        y, x = np.indices((240, 320))
        ramp = np.stack((.15 + .5 * x / 320, .2 + .4 * y / 240, .45 + .1 * x / 320), axis=-1)
        if name == "busy_texture":
            ramp = np.clip(ramp + rng.normal(0, .04, ramp.shape), 0, 1)
        image = Image.fromarray(np.rint(ramp * 255).astype(np.uint8))
        draw = ImageDraw.Draw(image)
        draw.polygon([(30, 200), (125, 25 + index * 5), (190, 195)], fill="#d5a046")
        draw.ellipse((185, 65, 285, 165), fill="#76baa8")
        if name == "small_accents":
            for px, py in ((50, 60), (140, 160), (230, 110)):
                draw.ellipse((px, py, px + 6, py + 6), fill="white")
        if name == "diagonal_contours":
            for offset in range(0, 80, 12):
                draw.line((25 + offset, 220, 135 + offset, 25), fill="#202235", width=3)
        if name == "soft_shading":
            image = image.filter(ImageFilter.GaussianBlur(12))
        if name == "flat_shapes":
            image.paste("#262b3a", (0, 0, 320, 30))
        image.save(folder / f"{name}.png")
    return sorted(folder.glob("*.png"))


def prepare(output, sources=None, competitors=(), resolution=96, colors=16):
    output.mkdir(parents=True, exist_ok=True)
    originals = demo_sources(output / "sources") if sources is None else sorted(
        path for path in sources.iterdir() if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"})
    cases = []
    for index, path in enumerate(originals):
        case_id = path.stem if sources is None else f"{index:03}-{path.stem}"
        with Image.open(path) as source:
            image = source.convert("RGB")
        copied = output / "sources" / f"{case_id}.png"
        copied.parent.mkdir(exist_ok=True)
        image.save(copied)
        pixels = np.asarray(image, dtype=np.float32) / 255
        h, w = approximate_size(image.height, image.width, resolution)
        candidates = []
        for method in ("nearest_quantized", "area_quantized", "ray_abstraction"):
            if method == "ray_abstraction":
                result, _ = RayPixelArtDetector().process(torch.from_numpy(pixels)[None],
                    input_kind="illustration_photo", target_resolution=resolution, max_colors=colors,
                    palette_strategy="color_families", seed=42)
                converted = Image.fromarray(np.rint(np.clip(result[0].numpy(), 0, 1) * 255).astype(np.uint8))
            else:
                converted = image.resize((w, h), Image.Resampling.NEAREST if method.startswith("nearest") else Image.Resampling.BOX)
                converted = converted.quantize(colors=colors).convert("RGB")
            target = output / f"{case_id}-{method}.png"
            converted.save(target)
            candidates.append({"method": method, "image": target.name})
        for name, folder in competitors:
            external = folder / f"{case_id}.png"
            if not external.is_file():
                raise FileNotFoundError(f"Missing competitor output: {external}")
            target = output / f"{case_id}-external-{len(candidates)}.png"
            with Image.open(external) as candidate:
                candidate.convert("RGB").save(target)
            candidates.append({"method": name, "image": target.name})
        cases.append({"id": case_id, "kind": "synthetic_demonstration" if sources is None else "curated_source",
                      "source": copied.relative_to(output).as_posix(), "candidates": candidates})
    manifest = {"schema": 1, "target_long_edge": resolution, "palette_budget": colors,
                "human_ranked": False, "cases": cases}
    destination = output / "manifest.json"
    destination.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return destination


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("perceptual-corpus"))
    parser.add_argument("--sources", type=Path)
    parser.add_argument("--competitor", action="append", default=[], metavar="NAME=DIRECTORY")
    parser.add_argument("--resolution", type=int, default=96)
    parser.add_argument("--colors", type=int, default=16)
    args = parser.parse_args()
    competitors = [(name, Path(folder)) for name, folder in (value.split("=", 1) for value in args.competitor)]
    print(prepare(args.output.resolve(), args.sources, competitors, args.resolution, args.colors))
