# Pixel Art development benchmark

This is a small transparent development benchmark, not a SOTA leaderboard.
Three independently drawn procedural images have different native dimensions.
Eight conditions produce 24 inputs: native, integer enlargement, fractional
enlargement, bilinear enlargement, blur, JPEG, uniformly distributed Gaussian
noise, and uneven cell widths. There is no corruption targeted at the nearest
sampler's locations. The originals and noise seeds are reproducible.

Automatic sizing and known-resolution reconstruction are evaluated separately.
All automatic methods get their normal detector; Ray's fallback stays at 128,
not the answer. Known-resolution methods receive the same true target dimensions
or the corresponding source cell size. Spritefusion's override specifies cell
size, and its returned dimensions are left unchanged.

## Run

Use the same Python environment as ComfyUI, with the pack's requirements installed,
and Node.js available on PATH:

```text
python prepare_references.py
python benchmark.py
```

The setup command explicitly downloads reference source and Spritefusion's
published browser WASM engine to `.references`. Nothing is uploaded. Setup is
separate from the node, which never downloads or calls a server.

Pixel Art Fixer is pinned to `ef376e57e1c272633ca2dbf5f29ec3fcf6596465`.
Spritefusion is its published browser engine, pinned by SHA-256 in the setup
script, not an asserted match to the current Rust CLI. The adapter exposes the
existing initializer and process function; it does not modify processing.
Both are benchmark references, not installed runtime engines. The node vendors
only the attributed Pixel Art Fixer detector under the pack's ray_pixel_fixer.

`previous_pixel.py` freezes the first Ray rewrite as a historical baseline.
The script creates fixture PNGs, outputs and baseline_results.json. RESULTS.md
and results.json record the run accompanying this change.

## Reading the numbers

Exact size and dimensions within one pixel are direct grid measures. Color error
is mean Euclidean OkLab distance. For wrong-sized outputs only, nearest resizing
to the known original grid allows a secondary comparison; this is not a precise
alignment-aware restoration score. Edge F1 uses color differences above .04
between neighboring pixels, with no translation tolerance. These metrics do not
establish pleasant line rhythm, material rendering, character design or artistic
quality. Do not use the color/edge scores alone to rank differently sized outputs.

Repair color metrics disable Ray's output palette reduction. Spritefusion always
quantizes (32-color budget), and area16 uses a 16-color palette; originals have
fewer than 16 colors. This remaining algorithm difference is intentional and
must accompany comparisons. Color budgets are ceilings, not equal actual counts.

The public NASA astronaut photo and a smooth procedural illustration were also
reviewed visually, outside the scored repair set. Their conversions have no
pixel-art ground truth and were not scored as recovery. No artist study, broad
AI-image corpus, animation test or official pixel-bench suite was run.

Source attribution for the photo: NASA / Eileen Collins, distributed in
scikit-image v0.19.3 as skimage/data/astronaut.png. Reference source licenses are
retained by setup. Procedural fixtures are authored for this node pack.
