# Ray's VFX: Pixel Art

Two input families share one node and the same two IMAGE outputs:

- **repair_pixel_art**: recover enlarged or damaged pixel-like art using grid
  detection and region voting. The final colors come from the source, not from
  the temporary palette used to identify regions.
- **illustration_photo**: use local iterative superpixel assignments to abstract
  features into a smaller image. This is an image-processing approximation;
  it does not redraw anatomy, understand objects or replace a pixel artist.

`image` is the actual pixel-resolution result. `preview` is that result enlarged
with nearest-neighbor sampling to the input dimensions. Save the first output
as PNG for editing; the second is for inspection.

## Starting settings

For existing pixel-like art: choose repair_pixel_art, auto_pixel_size, grid_snap,
32 colors, source palette style, no dither and no outline. If automatic sizing
is wrong, switch to manual_resize and choose the intended longest side.

For illustrations/photos: choose illustration_photo, manual_resize, grid_snap,
64 or 128 pixels, 16–32 colors, distinct palette style and no dither. Inspect
at native resolution before adding effects. At tiny resolutions, a crop made
upstream may communicate a subject better than converting an entire scene.
This node itself never crops.

Nearest and area sampling remain explicit alternatives in both input families.
Selecting either bypasses structural reconstruction. Dither, palette and outline
controls still apply. Irrelevant widgets are hidden using the pack's shared UI
helper; their values are preserved in the saved workflow.

## Exact aspect ratio

All output dimensions are integer multiples of the original reduced width:height
ratio. For example, 1024×768 can become 128×96. A 1001×667 image has no smaller
integer resolution with exactly its ratio, so its dimensions remain unchanged.
Requested sizes are rounded to the nearest feasible size, never silently
stretched or cropped. The console logs detected sizes and adjustments.

`pixel_size` requests source pixels per output pixel. `auto_pixel_size` uses
fractional-grid detection in repair mode and target_resolution in illustration
mode, where an underlying pixel lattice is not assumed. Batch auto sizing uses
one shared median size so tensors stack correctly. Clean one-pixel detail is
conservatively protected from automatic downscaling. This can retain more pixels
than desired; manual size remains the reliable override.

The preview always has the original dimensions. Noninteger enlargement can
produce preview blocks differing by a screen pixel; the low-resolution output
is the authoritative uniform grid.

## Palette and reconstruction

### Very small palettes: color_families

New nodes offer `color_families` first. Existing workflows retain their selected
method; select this explicitly when comparing an older saved workflow.

This method allocates a base entry to distinct hue/lightness families and supported
neutral/dark groups before allocating extra shading entries. Hue normalization
helps group different saturations of a color. Lightness still separates families
such as light skin and dark leather that can have similar hues. Ordinary Lab and
OkLab distances are perceptual distances, but minimizing their aggregate error
does not guarantee retaining material color identity at eight colors.

Pixel assignment combines OkLab distance with a hue-family penalty, instead of
constructing a family palette then immediately losing its identities to ordinary
nearest assignment. Dither pairs must also remain close in family hue. Supplied
palettes use the existing assignment behavior and remain exact.

`palette_allocation`, `palette_style` and `ramp_levels` do not apply to this method
and are hidden. Highlight protection uses remaining budget after family coverage;
at eight colors it may have no spare slot. This intentionally prioritizes main
color families over tiny glints. Try 12–16 colors when both are important.

This is a heuristic, not semantic recognition: it cannot guarantee that every
material shares one label, especially when materials have identical colors or
illumination strongly changes their hue. It also cannot retain more distinct
families than the requested color count. The six-material test and the elf review
exercise the actual eight-color case rather than extrapolating from 32 colors.

Repair uses a globally even lattice. A temporary perceptual palette separates
regions for a center-weighted vote. Original colors within the winning region
are pooled with stronger center weighting and impulse rejection. Median filtering
is used only for structural analysis when source cells are sufficiently large.
This avoids averaging unrelated regions or independently bending every grid cut.

Illustration abstraction uses bounded local superpixel movement, color and
position costs, source-edge weighting and optional palette-guided assignments.
It preserves the canvas but can change which small features occupy output pixels.
It is inspired by the general approach in Gerstner et al.'s
[Pixelated Image Abstraction](https://gfx.cs.princeton.edu/pubs/Gerstner_2012_PIA/),
not an implementation or reproduction of that paper's results.

Other palette methods are `kmeans_lab`, `quantize_simple`, `kmeans_rgb`,
`oklab_source` and `ramps_oklab`. Lab/RGB restore the original cluster-mean choices;
simple restores RGB buckets followed by clustering when necessary. OkLab source
uses actual source representatives. Ramps group chroma and divide each family
into weighted lightness bands. Unlike the original ramp implementation, all
methods respect max_colors even when it is not divisible by ramp_levels.

`palette_allocation=area_preserving` favors spatially coherent fills and reserves
separated, well-supported color anchors. Busy texture receives less fitting weight;
it cannot claim as many shades merely by containing many unique colors. This is
a local spatial heuristic, not recognition of skin, hair or materials. Choose
`frequency` for ordinary frequency weighting (simple retains its original
unweighted bucket fit). Try simple + area_preserving when you prefer firmer color
grouping; Lab + area_preserving is the general default.

`protect_highlights` restores explicit highlight slots, within the color budget.
`highlight_threshold` uses original CIE Lab lightness units (default 90). Neutral
metal glints and warm highlights are separated when at least eight colors are
available. A full source-color histogram avoids randomly missing rare glints.
Protection uses the reconstructed image: a feature lost during downsampling
cannot be recovered by palette fitting. Use nearest or a larger output when
reconstruction removes important tiny details.

`source` keeps fitted shades; `distinct` merges near-duplicate ordinary shades,
but preserves reserved highlights. In undithered illustration mode, distinct also
consolidates weak isolated shades. max_colors is a ceiling, not a requirement.

Connect a clean palette image to impose its colors. Up to 256 distinct colors
are preserved exactly, regardless of max_colors or reduce_palette. Images with
more colors are treated as palette references and reduced to max_colors. Supplied
palettes bypass distinct-style changes. Palette fitting is shared across a batch;
this helps color consistency but does not guarantee animation stability.

## Dither and outline

Dithering now requires a coherent directional source ramp, visible quantization
error and a useful palette-pair mixture. Flat fields, slight random noise,
strong boundaries and texture do not qualify just because colors vary. Ordered
patterns test mixtures in linear light; serpentine diffusion stays within an
eligible pair and does not propagate across protected boundaries. Unrelated
chroma pairs are rejected. Both are deliberately conservative: on artwork already
built from flat clusters they may do almost nothing. Leave dither off initially.
The test suite also checks that genuine coarse-quantized ramps improve in local
average tone, rather than merely checking that dithering changes pixels.


Dithering defaults to none. Ordered palette mixing or serpentine diffusion is
restricted using local gradients and texture: flat fills, strong boundaries and
busy texture are protected. Strength controls the amount. Flat colors between
palette entries deliberately map to one entry rather than becoming speckled.
Existing source dithering is not globally stripped.

silhouette adds a dark one-pixel inner contour. selective chooses colored contour
shades from nearby interior colors, using their brightness ordering instead of
inventing a light direction. It can soften black borders when suitable palette
colors exist. Neither mode expands the silhouette or paints an external halo.

Without a mask, outlining needs a recognizable solid backdrop at the image
border. Optional foreground_mask enables complex backgrounds: **1 means subject,
0 means background**. ComfyUI Load Image alpha masks generally need inversion.
Provide one HW/BHW mask or one per image; the mask is resized with nearest sampling.
The node outputs RGB, as before; it does not output transparency.

## Artistic guidance

[Derek Yu's basics](https://www.derekyu.com/makegames/pixelart.html) and
[common mistakes](https://www.derekyu.com/makegames/pixelart2.html) informed these
choices: prioritize readable groups of color, avoid redundant shades and excessive
texture, and let outlining follow existing form. The node preserves source shading
rather than manufacturing concentric shadow bands. Selective outlining is optional.

Line rhythm, convincing volume and character design still need visual judgment.
There is no universal jaggy-removal or limb-thickening pass: either can destroy
intentional details. Deliberate internal antialiasing is compatible with pixel art;
the node does not equate every intermediate color with an error. Examine the
result at native size and in grayscale, not only as a large preview.

## Engine and dependencies

Automatic grid detection vendors the MIT-licensed
[Pixel Art Fixer](https://github.com/Retro-Diffusion/pixel-art-fixer) detector.
Attribution, revision and the bounded-memory modification are in
ray_pixel_fixer/NOTICE.md and LICENSE. It uses NumPy, SciPy and OpenCV locally;
there is no model, server or runtime network request. Analysis is capped at
1.5 million pixels; reconstruction retains the complete original image. Very
fine grids in larger images may need manual sizing.

## Updating and validation

Restart ComfyUI and refresh the frontend. The node ID and two output slots stay
unchanged. Saved visual workflows from the original node and first rewrite
migrate on load. The original swatch-sheet output is now the source-size preview.
Re-export old API workflows after visual migration; links to removed original
advanced controls require review.

Tests cover sizing, fractional grids, clean reconstruction, random noise, spatial
tie-breaking, palettes, gradients, masks, high-contrast details, repeatability,
both historical widget layouts and conditional controls. The separate benchmark
compares automatic sizing and known-resolution reconstruction; its small fixture
set is development evidence, **not proof of state of the art**. See the benchmark
report and reproduction instructions for exact scope and limitations.

## Color grid preview

Enable **color grid**, immediately below highlight_threshold, to replace preview
with a labeled 3-column, 2-row comparison of all six palette methods. The main
image output is unchanged. Each tile runs the method with the same resolved
resolution, seed, and effect settings. Comparison tiles always generate palettes
using max_colors, even when reduce_palette is off or palette_image is connected;
those controls still apply normally to the main output.

Tiles use integer nearest-neighbor enlargement, targeting at most 512 pixels on
their longest side unless the native pixel output is already larger. Small tiles
are centered under their labels without stretching. A batch produces one grid
per input image. Grid mode takes longer because it evaluates all methods; off
restores the original-dimension nearest-neighbor preview.
