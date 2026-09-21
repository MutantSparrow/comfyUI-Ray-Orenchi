# comfyUI-Ray-Orenchi

A collection of 19 ComfyUI custom nodes for image effects, pixel-art conversion,
native local vision-language inference, prompt workflows, metadata, and compact
analog controls. Nodes appear under the `👑 Ray` category in four groups:
`✨ VFX`, `🎛️ Analog`, `📝 Prompts`, and `💬 LLM`.

## Highlights

- **Fast Qwen3-VL Infer** reuses an existing native Qwen3-VL `CLIP` object and
  checkpoint. It does not convert to GGUF, start a server, or load a second model
  copy. It retains ComfyUI loading, FP8-scaled weights, offloading, vision
  preprocessing, sampling, and ComfyKitchen decode support where available.
- **Pixel Art** repairs enlarged pixel grids or converts illustrations and photos
  while preserving the exact source aspect ratio. It includes perceptual and
  color-family palettes, highlight protection, restrained ramp-aware dithering,
  optional outlines, supplied palettes, and a labeled six-method comparison grid.
- **Folder Captioner** and **TXT Folder** support local batch workflows with
  aligned list outputs, stable ordering, ranges, and actionable errors.

## Nodes

| Node | Group | Purpose |
|---|---|---|
| Ray Save Image | VFX | Save either or both image inputs as PNGs, or preview them with a draggable comparison divider |
| Ray's VFX: CRT | VFX | CRT display simulation with phosphor masks, scanlines, halation, NTSC bleed, and barrel distortion |
| Ray's VFX: Offset Print | VFX | CMYK or duotone halftone printing with paper simulation |
| Ray's VFX: Pixel Art | VFX | Pixel-grid repair and illustration abstraction with palette reduction, selective dithering, outlines, native-size output, and comparison preview |
| Ray's VFX: Film Stock | VFX | Film response, grain, halation, and optional LUT/XMP assets |
| Ray's VFX: VHS / Tape | VFX | YUV tape degradation, tracking faults, dropouts, noise, and OSD |
| Ray's Analog: Knob | Analog | Float control with min/max, spin, and clamp behavior |
| Ray's Analog: Switch | Analog | Boolean toggle control |
| Ray's LLM: Fast Qwen3-VL Infer | LLM | Fast image-to-text generation through an already loaded native Qwen3-VL CLIP, with no duplicate model |
| Ray's LLM: Folder Captioner | LLM | Caption a sorted local image range with a full GPU VLM and return aligned text, image, and path lists |
| Ray's LLM: Ollama Chat | LLM | Ollama or ComfyUI CLIP chat with image and audio attachments |
| Ray's LLM: Prompt Iterator | LLM | Score image/prompt agreement and propose a revised prompt through Ollama |
| Ray's LLM: Prompt Library | LLM | Store and browse prompts in a local SQLite library with tags and source filters |
| Ray's Prompts: TXT Folder | Prompts | Read complete UTF-8 text prompts alphabetically and emit matching Save Image prefixes |
| Ray's Prompts: PromptDexter Scraper | Prompts | Retrieve a random prompt and image from PromptDexter |
| Ray's Prompts: CivitAI Gallery Scraper | Prompts | Retrieve prompt/image metadata from the CivitAI API with SFW/NSFW selection |
| Ray's Prompts: Folder Image Scraper | Prompts | Select a local image and extract its generation prompt |
| Ray's Prompts: Prompt Fetcher | Prompts | Unified local, PromptDexter, and CivitAI prompt source |
| Ray's Prompts: Metadata Inspector | Prompts | Read generation metadata or embed supplied metadata into an image |

Detailed references are linked in the documentation section below.

## Install

Clone the pack into `ComfyUI/custom_nodes`:

```shell
cd ComfyUI/custom_nodes
git clone https://github.com/MutantSparrow/comfyUI-Ray-Orenchi.git
cd comfyUI-Ray-Orenchi
pip install -r requirements.txt
```

Use the Python environment that launches ComfyUI when installing requirements.
Restart ComfyUI and refresh the browser after installing or updating the pack.

Core dependencies include PyTorch, NumPy, Pillow, scikit-learn, SciPy, OpenCV,
aiohttp, Requests, Beautiful Soup, and the Ollama Python client. ComfyUI already
provides several of these in common installations; `requirements.txt` is the
authoritative list.

## Native Qwen3-VL inference

For **Fast Qwen3-VL Infer**, load a full native Qwen3-VL 4B or 8B checkpoint with
ComfyUI's standard `CLIPLoader` using the Qwen Image-compatible model type
(`qwen_image`, or `krea2` for the shared 4B/Krea workflow). Connect the resulting
`CLIP`, an `IMAGE`, and a plain prompt to the node. The same CLIP output can branch
to Qwen Image/Krea conditioning and VLM inference.

`fast` mode enables the optimized request-local decode path; `native` is an A/B
baseline. Temperature, top-p, top-k, seed, thinking, repetition/presence penalties,
stop-check interval, and an optional repeated-phrase guard are exposed. Image
batches form one multi-image conversation rather than independent captions.

The optimization keeps one model copy and request-local KV/graph buffers. It does
not use Transformers, llama.cpp, vLLM, or a model conversion. Acceleration depends
on the installed ComfyUI/ComfyKitchen capabilities and GPU. See
[FAST_VLM.md](FAST_VLM.md) for architecture, measurements, constraints, and exact
validation, and [FAST_VLM_RELIABILITY.md](FAST_VLM_RELIABILITY.md) for prompt
attachment and repetition safeguards.

**Folder Captioner** instead selects and loads a full generative checkpoint from
ComfyUI's `text_encoders` list, then processes a bounded alphabetical image range.
It requires a GPU and holds selected output images in RAM until downstream nodes
release them; use `start_index` and `limit` for large folders.

## Pixel Art

**Pixel Art** returns two images:

- `image`: the actual pixel-resolution result, preserving the exact source aspect
  ratio without cropping or stretching.
- `preview`: a nearest-neighbor view at the original input size, or a labeled grid
  containing the exact current output plus all six palette methods when
  **color grid** is enabled.

Use `repair_pixel_art` for enlarged or damaged pixel art and `illustration_photo`
for region abstraction. Palette methods include `color_families`, `kmeans_lab`,
`quantize_simple`, `kmeans_rgb`, `oklab_source`, and `ramps_oklab`.
`color_families` prioritizes distinct hue/lightness groups at very small palette
budgets; other methods offer different tradeoffs between clean clusters, source
colors, and shading. Supplied palette images remain supported.

**Palette mapping** independently controls how pixels choose from either a
generated or supplied palette: automatic, original near-black-aware OkLab,
standard OkLab, CIE Lab, RGB, or color-family matching. It changes assignment
without adding colors to the palette.

Dithering is restricted to coherent ramps where palette mixing improves lost
tone; flat fills, strong edges, and noisy texture are protected. The full workflow,
recommended settings, limitations, engine attribution, and benchmark methodology
are documented in [PIXEL_ART.md](PIXEL_ART.md) and
[benchmarks/pixel_art/README.md](benchmarks/pixel_art/README.md).

## Ray Save Image

Connect `image_1` and optionally `image_2`. The second input enables a draggable
left/right comparison; images keep their aspect ratios, with letterboxing when
needed. Batch arrows step through pairs; a single image can be compared against
every image in the other batch.

The **Save Image** button group selects **None**, **1** (default), **2**, or **Both**.
The selection takes effect when the workflow executes. None creates temporary
previews only. Both saves every connected input image, with unique filenames to
avoid overwrites. Files are PNGs at their input resolution, including alpha.

**Browse…** opens a folder picker for the computer running ComfyUI. The arrow next
to it recalls the last three successfully used save folders, stored locally in
that browser. You can also type an absolute destination or a path relative to
ComfyUI's output directory; a blank path uses the output directory. A new typed
folder is created on save.

Right-click the node and toggle **Save without metadata** to omit prompt/workflow
metadata. ComfyUI's global metadata-disable setting is also respected. The save
selector and metadata choice are serialized with the workflow. The custom
controls use shared Legacy/Nodes 2.0 DOM-widget support; frontends without DOM
widgets retain the standard save-selection and metadata inputs.

Right-click **Ray Save Image → Open image location in Explorer** to open the
folder from its latest successful save. The option becomes available after a
save in the current session and stays tied to that folder if you edit the next
destination or run preview-only. Explorer opens on the Windows ComfyUI host.

## Analog controls

**Knob** outputs both a raw float and a quantized integer; **Switch** outputs a
boolean. Both provide vintage studio hardware faces, editable tape labels, and
compact mode, which hides unlinked setup widgets while preserving connections
and saved values. The controls support Legacy and Nodes 2.0 frontends.

Choose a theme from the right-click menu: ten knob themes include rotary dials,
a chickenhead, and a linear fader; nine switch themes include rockers, levers,
sliders, and an illuminated key. The original twelve themes have refreshed
metal, Bakelite, and indicator artwork with their existing style IDs preserved.

Drag a knob, hold Shift for fine adjustment, or enter an exact value in its
readout. Arrow keys adjust values and Home/End reach the configured limits.
Click a switch or focus it and press Space/Enter. Double-click the tape label
(or focus it and press Enter) to rename it. Refresh the ComfyUI frontend after
updating to load the new artwork.

## Ollama and network-backed nodes

- Install and run [Ollama](https://ollama.com/) for **Ollama Chat** in Ollama mode
  and **Prompt Iterator**, then select a locally installed model in the node.
- **PromptDexter**, **CivitAI**, and the corresponding **Prompt Fetcher** modes
  require network access. CivitAI can optionally read a local `civitai.secret`
  file for authenticated access; secret files are ignored by Git.
- Ollama Chat's CLIP mode uses an already loaded compatible ComfyUI CLIP and does
  not require Ollama.

## Documentation

- [NODES.md](NODES.md) — node-by-node inputs, outputs, and behavior
- [PIXEL_ART.md](PIXEL_ART.md) — Pixel Art workflow, algorithms, and limits
- [FAST_VLM.md](FAST_VLM.md) — Fast Qwen3-VL implementation and measurements
- [FAST_VLM_RELIABILITY.md](FAST_VLM_RELIABILITY.md) — attachment and repetition handling
- [UI.md](UI.md) — shared frontend and node UI conventions

## Compatibility

The pack supports ComfyUI's legacy and v2 frontends through shared helpers in
`web/_common.js`. Registered class names remain stable so existing workflows keep
loading. The Fast Qwen3-VL path follows native ComfyUI internals and is therefore
more sensitive to upstream decoder changes than ordinary image nodes; consult its
validation notes when updating ComfyUI.

## License

The node pack is licensed under Apache License 2.0; see [LICENSE](LICENSE).
The vendored Pixel Art Fixer grid detector is MIT-licensed and retains its own
[license](ray_pixel_fixer/LICENSE) and [notice](ray_pixel_fixer/NOTICE.md).
