# Pixel Art development results — 2026-09-17

This is a 24-case **development set**, used during implementation, not an
independent held-out evaluation or evidence of SOTA. There are only three
procedural source artworks and eight conditions per artwork. Fairer sampling
and comparisons replace the earlier demonstration with noise deliberately
placed at nearest-sampling positions.

All runs below completed successfully against the pinned engines. Conditions,
versions, color-budget differences and reproduction steps are in README.md.

## Automatic sizing

| Method | Exact native size | Within one pixel | Exact source aspect ratio | Mean seconds |
|---|---:|---:|---:|---:|
| Ray, revised | 24/24 | 24/24 | 24/24 | 0.317 |
| Ray, previous rewrite | 13/24 | 13/24 | 24/24 | 0.137 |
| Pixel Art Fixer reference | 21/24 | 21/24 | 22/24 | 0.274 |
| Spritefusion browser engine | 0/24 | 4/24 | 1/24 | 0.025 |

Ray uses the vendored Pixel Art Fixer detector plus exact-aspect sizing and
conservative native-detail preservation; these are not independent detectors.
The earlier fallback-size leak was removed: Ray's auto fallback stays at 128,
whereas the originals' longest sides are 40, 48 and 64. The detector now uses
a fresh seeded worker so other OpenCV calls cannot alter its initialization.

## Reconstruction with the true resolution supplied

Lower OkLab error is better. This table includes clean/native cases; on clean,
correctly aligned inputs, nearest is already exact. Ray's advantage here is
mainly recovery from damage, not improvement over an exact original.

| Method | Mean OkLab error | Mean edge F1 | Correct size | Mean seconds |
|---|---:|---:|---:|---:|
| Nearest | 0.007055 | 0.907 | 24/24 | 0.023 |
| Area + 16-color palette | 0.010352 | 0.916 | 24/24 | 0.048 |
| Ray, previous rewrite | 0.006476 | 0.921 | 24/24 | 0.064 |
| Ray, revised | 0.004366 | 0.948 | 24/24 | 0.146 |
| Pixel Art Fixer two-stage pack | 0.006086 | 0.915 | 24/24 | 0.099 |
| Spritefusion with known cell size | 0.050314 | 0.556 | 1/24 | 0.025 |

Spritefusion often returns a different number of rows/columns even with a cell
size override. Its color/edge scores involve nearest resizing to the original
dimensions, so they combine reconstruction and grid-placement errors. This is
not sufficient to conclude that it makes worse-looking pixel art generally.

## Remaining limitations

- No human/artist preference study or broad real AI-image collection was used.
- Automatic detection remains heuristic; other art can fail, particularly weak
  or conflicting grids. Native-detail protection can be conservative.
- Photo/illustration examples were reviewed visually, not scored against an
  artist-created target. Readable facial features and pixel-line rhythm still
  need judgment; the node does not redesign a character or infer lighting.
- Full animation stability, transparency output and semantic segmentation are
  not implemented. Foreground masks guide outlines only.
- Exact aspect ratio can prevent downscaling coprime source dimensions.

## Tutorial-informed checks

Generated colors can be consolidated into distinct shades; restrained dither
protects fills and contours; colored outlines follow existing nearby shading.
Weak isolated shades can merge while high-contrast eyes, highlights and thin
strokes survive. No automatic limb thickening, blanket antialias removal, or
synthetic concentric shading was introduced. See PIXEL_ART.md for Derek Yu links
and the precise behavior of each option.

22 Python behavior tests and JavaScript tests for original/v1 workflow migration,
links, idempotence and conditional widgets passed. Runtime tests use the local
ComfyUI Python environment; the running UI needs a restart to load the update.
