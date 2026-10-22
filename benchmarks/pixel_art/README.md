# Pixel Art evaluation

Two separate tracks answer different questions. No combined artistic-quality score is reported.

## Reconstruction

`benchmark.py` retains the existing fixture-based evaluation of damaged or enlarged
pixel art: exact output dimensions, aligned OKLab error and edge F1. These measure
recovery of a known original. They do not establish how native-looking an illustration
or photograph conversion is. Existing `results.json` files are reconstruction results.
Run `prepare_references.py` first when external reconstruction converters are needed;
it is an explicit setup step and is not part of the node runtime or normal CI.

## Conversion and human review

```shell
python benchmarks/pixel_art/prepare_perceptual.py --output perceptual-corpus
python benchmarks/pixel_art/perceptual.py perceptual-corpus/manifest.json --output perceptual-results
```

The starter corpus has six deterministic synthetic illustration cases, deliberately
labeled `synthetic_demonstration` and `human_ranked: false`. It compares Ray abstraction
with nearest and area sampling followed by Pillow palette quantization. These baselines
are reproducible, but do not substitute for comparisons against competing converters.

For a real reference set, curate 12–20 licensed illustrations/photos spanning portraits,
small objects, textured scenes, flat illustrations, difficult diagonals and gradients.
Record provenance/licensing alongside each case and retain failed cases. Use
`--sources <directory>` instead of the synthetic corpus. Match target size and palette
budget across converters. Add their pre-generated PNGs with
`--competitor converter-name=<directory>`; filenames must match the generated case IDs.
No external tool or model is downloaded automatically.

Open the resulting `pairwise.html` locally. It embeds the selected images, randomizes
A/B ordering with a fixed seed, hides method names, and supports wins, ties, skips and
notes. Enter a reviewer label and export votes. Repeated votes by the same reviewer
for the same case/method pair replace earlier votes when aggregated:

```shell
python benchmarks/pixel_art/rank_votes.py reviewer-a.json reviewer-b.json
```

Human review must supply the rankings; generated fixtures or proxy metrics must never
be presented as human judgments. Collect independent votes before revealing methods.
Report each pair's wins/ties/skips and inspect disagreement, rather than selecting a
winner from a small overall average. Keep the reviewed manifest and exported votes
together to form a reproducible human-ranked reference set.

`diagnostics.json` reports isolated pixels, tiny connected clusters, cluster sizes,
local 8×8 color counts, row-contour step variation, approximate hue-ramp chroma/gap
consistency, checkerboard coverage and low-frequency source-tone error. Intentional
highlights, texture and dithering can increase these values; none is a universal
pass/fail threshold. Checkerboard coverage is a regular-dither proxy, not a measure
of whether the dithering is artistically appropriate.

Silhouette IoU is computed only when a case has `source_mask` and the candidate has
`mask` (white foreground/black background files, paths relative to the manifest).
It remains null otherwise: the evaluator does not guess the subject from a photograph.
