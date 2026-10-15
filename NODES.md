# Node Documentation

All nodes live under `👑 Ray/` in the ComfyUI add-node menu, split across
four bucket sub-categories:

- `👑 Ray/✨ VFX` — image-space effects (CRT, Offset Print, PixelArt, FilmStock, VHS).
- `👑 Ray/🎛️ Analog` — analog-style UI widgets (Control: knob / slider, Switch, Button Deck).
- `👑 Ray/🔧 Tools` — scrapers, prompt scraper, metadata inspector, TXT folder, Save Image.
- `👑 Ray/💬 LLM` — local vision-language inference and folder captioning.

Every node has a black body and a header colored by its bucket. Mode-tinted
nodes (`RayCivitAI`, `RayPromptFetcher`) hue-shift their
header color rather than pick a bespoke one.

---

## ✨ Ray's VFX: CRT (`RayCRT`)

**Purpose.** Image-space CRT display effect. Simulates phosphor mask (aperture / shadow / slot), scanline beam, halation + bloom, NTSC chroma bleed, barrel curvature, vignette, and reflection gloss. Multiple SOTA-inspired presets covering classic monitors and gaming consoles.

**Category:** `👑 Ray/✨ VFX`

| Pin | Type | Notes |
|-----|------|-------|
| **Input** `image` | IMAGE | Source frame(s). BHWC accepted. |
| **Control** `preset` | enum | `trinitron_aperture`, `pvm_shadow`, `consumer_slot`, `composite_ntsc`, `arcade_royale`, `lottes_fast`, `mattias_stylised`, `royale_kurozumi`, `guest_advanced`, `cyberlab_pixels`, `newpixie_framed`, `gtu_composite`, `hyllian_glow`, `super_famicom`, `megadrive`, `ps1`, `ps2`, `nintendo_ds`, `gameboy_advance`, `psp` |
| **Control** `curvature` | bool | Lottes barrel warp (out-of-bounds becomes black bezel). |
| **Control** `intensity` | float 0–1 | Master mix vs untouched input. |
| **Control** `scanline_strength` | float 0–2 | Scales preset scan depth. |
| **Control** `mask_strength` | float 0–2 | Scales preset mask depth + brightness compensation. |
| **Output** `image` | IMAGE | Same H/W/B as input. Legacy workflows may show this pin as `crt_image`; the tensor is unchanged. |

---

## ✨ Ray's VFX: Offset Print (`RayOffsetPrint`)

**Purpose.** Image-space CMYK / duotone offset print simulation. Per-plate halftone screen at SWOP angles, plate misregistration, dot gain, ink bleed, paper substrate (tint + grain + texture), optional sepia / vignette / posterize.

**Category:** `👑 Ray/✨ VFX`

| Pin | Type | Notes |
|-----|------|-------|
| **Input** `image` | IMAGE | Source frame(s). |
| **Control** `preset` | enum | `old_newspaper`, `modern_newspaper`, `comic_book`, `chromolithography`, `inkjet`, `pulp_magazine`, `risograph`, `silk_screen`, `xerox`, `glossy_magazine` |
| **Control** `intensity` | float 0–1 | Master mix vs untouched input. |
| **Control** `ink_strength` | float 0–2 | Per-plate ink density multiplier. |
| **Control** `screen_strength` | float 0–1.5 | Halftone screen depth. |
| **Control** `paper_strength` | float 0–2 | Paper grain + texture amount. |
| **Control** `scale` | float 0–4 | Halftone screen pitch scale. |
| **Control** `paper_color` | string | Paper substrate hex color (e.g. `#fffaf0`). |
| **Control** `paper_color_mix` | float 0–1 | Blend toward `paper_color` over the preset paper tint. |
| **Output** `image` | IMAGE | Same H/W/B as input. Legacy workflows may show this pin as `print_image`; the tensor is unchanged. |

---

## ✨ Ray's VFX: Pixel Art (`RayPixelArtDetector`)

**Purpose.** Repair an existing pixel grid or abstract illustrations/photos into readable regions. Preserve exact aspect ratio, fit perceptual palettes and optionally add restrained dithering or colored outlines.

**Category:** `👑 Ray/✨ VFX`

| Pin / control | Notes |
|---|---|
| `image` | Source image or batch. |
| `input_kind` | `repair_pixel_art` or `illustration_photo`. |
| `mode` | `manual_resize`, `auto_pixel_size`, `pixel_size`. Illustration auto uses target_resolution. |
| `target_resolution`, `pixel_size` | Desired longest side or source pixels per output pixel; exact-aspect dimensions only. |
| `sampling` | `grid_snap` structural processing, `nearest` sampling, `area` averaging. |
| `reduce_palette`, `max_colors` | Fit a generated palette within its color budget. |
| `palette_style` | `source` shading or `distinct` colors; distinct also consolidates weak isolated shades in undithered illustrations. |
| `palette_strategy` | Build a generated palette with color_families, Lab/RGB clustering, simple quantization, OkLab source colors, or ramps. |
| `palette_mapping` | Choose assignment independently: auto, legacy_oklab, oklab, lab, rgb, or color_families. Applies to supplied palettes too. |
| `palette_image` (optional) | Preserve up to 256 exact swatch colors; larger references are reduced to max_colors. Overrides generated palette settings. |
| `dither`, `dither_strength` | `none`, `ordered`, `error_diffusion`; protect flat fills, strong edges and busy texture. |
| `outline` | `none`, dark `silhouette`, or shading-guided colored `selective`. |
| `foreground_mask` (optional) | One means subject, zero means background; enables outlines on complex backgrounds. |
| `seed` | -1 for random; nonnegative values reproduce palette/reconstruction choices. |
| Output `image` | Actual pixel-resolution result. |
| Output `preview` | Nearest-neighbor preview at input dimensions. |

Grid detection uses the attributed MIT-licensed Pixel Art Fixer detector locally. No model or server is required. Irrelevant controls are hidden.

---

## 🎛️ Ray's Analog: Control (`RayKnob`)

**Purpose.** Analog-style float control, either a rotary knob or a slider, themed after studio hardware. Drag rotates a knob face or moves a slider cap; outputs both an `INT` (quantized by `clamp`) and a raw `FLOAT` so it plugs into either side without a converter. The node keeps its original `RayKnob` ID, so existing workflows load unchanged.

**Category:** `👑 Ray/🎛️ Analog`

| Pin | Type | Notes |
|-----|------|-------|
| **Control** `min_value` | float | Range minimum. |
| **Control** `max_value` | float | Range maximum. |
| **Control** `clamp` | float ≥0 | Quantization step for the INT output (`0` → truncate). |
| **Control** `allow_negative` | bool | Whether `min_value` may go below 0. |
| **Control** `knob_value` | float | Current value (driven by the widget). |
| **Output** `int` | INT | Quantized via `clamp`. |
| **Output** `float` | FLOAT | Raw clamped float in `[min, max]`. |

**Faces.** Nine knobs and five sliders, all drawn from one material set with the same 0–10 scale and 270° sweep. Knobs: console blue grey, broadcast ivory, mastering aluminium, mastering chrome notched, console LED ring, broadcast bakelite chickenhead, mastering silver skirted, broadcast knurled brass and console minimal flat. Sliders: console linear fader, console channel fader with a dB scale, rack LED ladder, broadcast pan slider and rack amber slide. The pan slider and amber slide are horizontal; the others are vertical.

**Dragging.** Every knob sweeps 270° from `min_value` to `max_value`, and the dial follows the pointer around its centre, so a 0–1 range is as controllable as 0–1000. Hold **Shift** for 20× finer movement. Arrow keys step 1/200 of the range (Shift: 1/2000), PageUp/PageDown step ten times that, and Home/End jump to the limits. Older workflows that saved a `spin_value` setting are migrated on load; that setting no longer exists.

**Sliders.** Drag the cap, or click the track to jump the cap there. The LED ladder lights segments as the value rises and the amber slide fills behind its cap.

**Sound.** Knobs click through detents that match their printed scale, sliders scrape and tick as they move and thud at the end stops, and the pan slider taps at its centre. Switches voice each face: a thump and clack for the rack rocker, a ringing strike and spring for the steel lever, a push-and-latch for the illuminated key, a clunk for the bakelite flip, a tick-tack for the paddle, a scrape and detent for the brass slider, a soft tap for the pill and a hollow thock for the dome. The sounds are synthesized with Web Audio in `web/analog_audio.js`; there are no audio files. **Mute sound** in the right-click menu (on both the Control and the Switch) silences every analog control and is remembered per browser.

**Right-click menu.** **Control Style…** opens a floating picker (knobs and sliders under separate headings; arrow keys, Enter and Escape work) rather than a nested submenu, so it stays on screen in both the legacy canvas and Nodes 2.0. **Mute sound** is next to it. **Compact mode** hides only unlinked setup controls while preserving real slots and workflow data. **Edit label…** changes the Dymo tape above the face; double-click or Enter also edits it. Drag around a rotary control or along a slider, use Shift for fine movement, or use Arrow/Home/End keys. Exact values can be entered in the readout. Style, compact flag, and label text persist with the workflow.

---

## 🎛️ Ray's Analog: Switch (`RaySwitch`)

**Purpose.** Boolean toggle widget with nine studio-hardware themes. Rockers and illuminated keys show their active state; lever handles point up for ON, and horizontal paddles/sliders move toward the ON label.

**Category:** `👑 Ray/🎛️ Analog`

| Pin | Type | Notes |
|-----|------|-------|
| **Control** `state` | bool | Toggle. |
| **Output** `bool` | BOOLEAN | Mirror of `state`. |

**Right-click menu.** **Switch Style…** opens a picker with nine faces: rack power rocker, broadcast steel lever, console illuminated key, rack chrome rocker, console dome button, broadcast bakelite flip, mastering silver paddle, broadcast brass slide and console minimal pill. **Mute sound** is shared with the Control. Every face has its own click, clack or thunk. **Compact mode** hides only unlinked setup controls and keeps the real output slot available. Click the face, or focus it and press Space/Enter. **Edit label…** changes the Dymo tape above the face; double-click or Enter also edits it. Style, compact flag, and label text persist with the workflow. The controls remain usable in both Legacy and Nodes 2.0 frontends.

---

## 🎛️ Ray's Analog: Button Deck (`RayButtonDeck`)

**Purpose.** A bank of analog push buttons that replaces a dropdown. Enter one value per line; each line becomes a button, and the pressed button's text comes out as a `STRING`. Styled after retro console hardware, in the same family as the Control and Switch.

**Category:** `👑 Ray/🎛️ Analog`

| Pin | Type | Notes |
|-----|------|-------|
| **Control** `entries` | multiline string | One value per line. Blank lines and repeated lines are ignored; up to 64 entries. Edited through the **✎ Edit entries…** popout, so the raw text box stays hidden. |
| **Control** `selected` | string | The pressed button's text, driven by the deck. If it isn't in the list the first entry is used. |
| **Output** `value` | STRING | The pressed button's text, exactly as typed. |

**Layout.** The buttons form a near-square grid with `ceil(sqrt(n))` columns: 1 → 1×1, 2 → 2×1, 3 and 4 → 2×2, 5 and 6 → 3×2, 7 to 9 → 3×3, 10 to 12 → 4×3, and so on (columns × rows). The node grows to fit the rows it needs, and the buttons scale with the node.

**Pressing.** The bank is interlocked like a radio-preset panel: exactly one button is pressed down and lit, and every other button stays raised and unlit. Pressing a button releases the previous one; pressing the lit one changes nothing. Arrow keys, Home and End move the selection, and Space or Enter presses the focused button. The selection follows the value, so reordering the entries keeps the same button pressed. If the pressed value is deleted, the first entry takes over (the same rule the node applies when it runs). A deck with no entries raises an error when it runs.

**Edit entries…** opens a popout with a text box (one value per line) and a live count of buttons and grid size. **Apply** (or Ctrl+Enter) saves the normalized list; **Cancel** (or Escape) discards the changes.

**Styles.** Five faces; each has its own sound and either prints the text inside the button or puts it on a Dymo sticker below:

| Style | Look | Text | Sound |
|-------|------|------|-------|
| Console · Amber Keys | Ivory keycaps with a backlit amber window | Cut into the key | Clean push and latch |
| Console · Lamp Domes | Chrome-ringed glass domes that glow green | Cut into the lens | Hollow thock |
| Broadcast · Bakelite Pushbuttons | Brown bakelite buttons with an orange lamp ring | Dymo sticker | Dull clunk |
| Mastering · Chrome Squares | Brushed-aluminium keys with a green LED | Dymo sticker | Bright double tick |
| Rack · Tape Deck Keys | Tall rubber keys that sink and light a slot | Dymo sticker | Heavy ka-chunk |

Pressing a button plays its latch sound, followed by a softer release as the previously pressed button pops out. **Mute sound** in the right-click menu silences every analog control.

**Right-click menu.** **Deck Style…** (the picker used by the other analog nodes), **Edit entries…**, **Compact mode**, **Edit label…** (the Dymo tape above the deck) and **Mute sound**. Style, compact flag and label persist with the workflow.

---

## 🔧 Ray's Tools: PromptDexter Scraper (`RayPromptDexter`)

**Purpose.** Fetches a random prompt + matching image from [promptdexter.com](https://promptdexter.com/). Discovery is **sitemap-driven**, so picks reach deep content (not just homepage top row). Seed-deterministic — freeze the seed for reproducible output. Maintains a per-node 20-entry LRU cache so consecutive runs avoid recent repeats; with a frozen seed, the cache forces a deterministic skip to the next seed-shuffled candidate. When a prompt page has no associated image, the IMAGE output falls back to a 1×1 black tensor so downstream nodes never break.

**Category:** `👑 Ray/🔧 Tools`

| Pin | Type | Notes |
|-----|------|-------|
| **Control** `seed` | int | `-1` for random (true OS randomness, ignores cache deterministically). Any `≥0` value is reproducible. |
| **Control** `category` | dropdown | `(any)` or any category slug discovered from the sitemap (e.g. `anime`, `people`, `cyberpunk`). Selecting a slug restricts picks to that category page's listed prompts. |
| **Control** `clear_cache` | bool | Drop this node's 20-entry deque before selection. |
| **Button** `🔄 refresh sitemap` | — | Click to re-fetch `/sitemap.xml` and reload the category list now. Triggered on click, not on workflow run. Sitemap is otherwise cached for the Python process lifetime. |
| **Control** `timeout` (optional) | int 2–60 | HTTP timeout per request, in seconds. |
| **Output** `prompt_single` | STRING | Whitespace-collapsed single-line prompt. |
| **Output** `prompt_multiline` | STRING | Original prompt with newlines preserved. |
| **Output** `image` | IMAGE | Matching image as BHWC float32 [0,1]. 1×1 black tensor if the page has no image or fetch fails. |

---

## 🔧 Ray's Tools: CivitAI Gallery Scraper (`RayCivitAI`)

**Purpose.** Fetches a random gallery image + its prompt from [civitai.com](https://civitai.com/) via the public REST API (`GET /api/v1/images`). Items with a usable prompt are kept — either the direct `meta.prompt` field, or, when missing, the text salvaged from a ComfyUI workflow blob embedded in `meta.comfy` (CLIPTextEncode / Text Multiline nodes etc.). Items with no extractable prompt are skipped. Seed-deterministic, per-node 20-entry LRU to avoid consecutive repeats, page cache keyed by (mode, period, sort, base_model, username). 1×1 black tensor fallback if an image fails to download.

**Access strategy.** REST API (not scraping, not MCP). Public endpoint, no key required for read access. Higher-tier content unlocks if a token file is present at `civitai.secret` inside the node-pack directory — never hard-coded. The legacy `nsfw` filter is bypassed in favour of `browsingLevel` (bitmask: PG=1, PG13=2, R=4, X=8, XXX=16), which the API documents as taking precedence. Blue = `PG | PG13` = `3`; Red = all levels OR'd = `31`.

**Category:** `👑 Ray/🔧 Tools`

| Pin | Type | Notes |
|-----|------|-------|
| **Control** `seed` | int | `-1` for random (true OS randomness). Any `≥0` value is reproducible. |
| **Control** `mode` | dropdown | `Blue (SFW)` → `browsingLevel=3` (PG \| PG13). `Red (NSFW)` → `browsingLevel=31` (all levels). JS extension tints the node header to match. |
| **Control** `base_model` | dropdown | `Any` or a specific base model (`SDXL 1.0`, `Pony`, `Illustrious`, `Flux.1 D`, `Flux.2 Klein 9B`, `Chroma`, `Qwen`, `Krea 2`, `Z-Image Turbo`, `Wan Video`, etc.). Passed to the API as `baseModels`. List is sampled live from the gallery — CivitAI surfaces new architectures as uploaders tag them, so the list is refreshed periodically. |
| **Control** `period` | dropdown | `AllTime` / `Year` / `Month` / `Week` / `Day` — window for metric-based sorts. |
| **Control** `sort` | dropdown | `Random` / `Most Reactions` / `Most Comments` / `Newest`. |
| **Control** `username` | string | Optional. Restrict the pool to images posted by a specific CivitAI user (e.g. `VISITOR01`). Leave blank for any user. Passed to the API as `username`. When set, `period` is automatically overridden to `AllTime` so small per-user archives don't drop to zero hits inside a `Week`/`Day` window. |
| **Button** `🔄 clear cache` | — | Click to clear both the process-wide page cache and this node's 20-entry recent-pick deque; next workflow run repages from the API. Triggered on click, not on workflow run. |
| **Control** `timeout` (optional) | int 2–60 | HTTP timeout per request, in seconds. |
| **Output** `prompt_single` | STRING | Whitespace-collapsed single-line prompt. |
| **Output** `prompt_multiline` | STRING | Original prompt with newlines preserved. |
| **Output** `image` | IMAGE | Gallery image as BHWC float32 [0,1]. 1×1 black tensor on fetch failure. |

**API token.** Optional. Create `civitai.secret` inside the `comfyUI-Ray-Orenchi/` node-pack directory and paste the token as its only contents (trailing whitespace/newlines are trimmed). The token is read fresh on each request — no caching, no persistence beyond the file itself. `civitai.secret` and `*.secret` are listed in `.gitignore`; do not commit them.

---

## 🔧 Ray's Tools: Folder Image Scraper (`RayLocalScraper`)

**Purpose.** Picks a random image from a local folder and extracts any generation prompt found in its metadata. Functional sibling to the PromptDexter and CivitAI scrapers, but read off disk instead of HTTP. Seed-deterministic; per-node 20-entry LRU avoids consecutive repeats; folder listing cached until `refresh_listing` is set or the cache is cleared.

**Prompt sources, in priority order:**
1. PNG `parameters` text chunk (Automatic1111 / Forge; JSON blob variants also parsed).
2. PNG `prompt` text chunk (ComfyUI serialized prompt graph, JSON; flat-literal fallback for JustRayzist-style writers).
3. PNG `workflow` text chunk — API format or UI (`nodes[]`/`links[]`) format.
4. Any other `info[]` key whose name looks prompt-shaped (`prompt_*`, `positive*`, `caption`, `description`, `comment`, `sui_image_params`, `invokeai_metadata`, `novelai_metadata`, `dream`…). JSON values are walked recursively for nested `prompt` / `positive` keys.
5. EXIF text tags: UserComment (37510), ImageDescription (270), XPComment (40092), XPSubject / XPTitle / XPKeywords.
6. `<image>.txt` sidecar file in the same directory.

For ComfyUI graphs, the extractor first locates every text-encoder node (`CLIPTextEncode` / `CLIPTextEncodeFlux` / `CLIPTextEncodeSDXL` / `BNK_CLIPTextEncodeAdvanced` / `T5TextEncode` / `ImpactWildcardEncode` etc.). Each encoder contributes one prompt: if its `text` input is a literal string the literal is used; if it's wired to another node, the link is followed back through `ShowText` → `Text Multiline` → `String Literal` → `Text Concatenate` → primitive nodes (up to 8 hops, cycles detected) until a literal is found. Multiple text inputs on a concat-style node are joined with spaces. Encoders that only feed a sampler's `negative` input (`KSampler`, `CFGGuider`, ControlNet apply nodes and the like) are skipped, so only positive prompts come back; an encoder shared by both sides is kept. Graphs with no positive/negative sampler wiring keep every encoder. This applies to both the API `prompt` chunk and the UI `workflow` chunk.

Every candidate is passed through a path-rejection filter that drops strings that look like filesystem paths (drive letters, backslash runs, bare `.safetensors` / `.ckpt` filenames), so random `C:\loras\foo.safetensors`-style fields don't leak through as prompts.

If the image carries multiple positive prompts (e.g. a ComfyUI workflow with several `CLIPTextEncode` nodes), every output is emitted as a ComfyUI **list** — one entry per prompt — so downstream nodes iterate once per prompt. The `image` and `image_path` outputs are broadcast (repeated) across each prompt entry so each iteration sees a matching `(prompt, image, path)` triple. Single-prompt images still return lists of length 1; if no prompt is found and `skip_no_prompt` is off, the output is a single-entry list with an empty string in both prompt slots.

**Category:** `👑 Ray/🔧 Tools`

| Pin | Type | Notes |
|-----|------|-------|
| **Control** `folder` | string | Absolute path to a folder of images. Required; raises if blank or missing. |
| **Control** `recurse_subfolders` | bool | When on, walks every subdirectory under `folder`. Off by default. |
| **Control** `skip_no_prompt` | bool | When on, skip images whose metadata yields no prompt and pick the next one from the seed-shuffled pool (capped at 50 attempts). |
| **Control** `prompt_best_try` | bool | Two behaviors. **Collapse** — always applies: reduce each image's prompt set to its single longest prompt. **Skip repeats** — random-mode only (`seed = -1`): if the collapsed prompt is anywhere in this node's recent-best deque (last 20 emits) advance to the next image. Locked seeds serve the collapsed prompt for the seeded pick every run regardless of history. |
| **Control** `seed` | int | `-1` for OS-random (non-deterministic). Any `≥0` value is reproducible. |
| **Control** `refresh_listing` (optional) | bool | Force a re-scan of the folder before picking. Off by default so repeated runs are cheap. |
| **Output** `prompt_single` | STRING (list) | One entry per prompt found, each whitespace-collapsed to a single line. |
| **Output** `prompt_multiline` | STRING (list) | One entry per prompt found, newlines preserved. |
| **Output** `image` | IMAGE (list) | Image tensor (BHWC float32 [0,1]), repeated across every prompt entry. |
| **Output** `image_path` | STRING (list) | Absolute path of the chosen file, repeated across every prompt entry. |

Supported file extensions: `.png`, `.jpg`, `.jpeg`, `.webp`, `.bmp`, `.tiff`, `.tif`.

---

## 🔧 Ray's Tools: Prompt Scraper (`RayPromptFetcher`)

**Purpose.** One node, three prompt sources. A `scraper_mode` dropdown picks between `Local Folder`, `PromptDexter`, and `CivitAI`; the frontend hides widgets that don't belong to the active mode. Outputs are harmonized to the local-scraper shape `(prompt_single, prompt_multiline, image, image_path)` so any mode is drop-in compatible with downstream wiring.

**Category:** `👑 Ray/🔧 Tools`

| Pin | Type | Notes |
|-----|------|-------|
| **Control** `scraper_mode` | enum | `Local Folder` / `PromptDexter` / `CivitAI`. Drives which widget group is shown and which backend runs. |
| **Control** `seed` | int | `-1` for random; any `≥0` value is reproducible. Shared across modes. |
| **Local** `local__folder` | string | Absolute path to a folder of images. |
| **Local** `local__recurse_subfolders` | bool | Walk every subdirectory. |
| **Local** `local__skip_no_prompt` | bool | Skip images whose metadata yields no prompt. |
| **Local** `local__prompt_best_try` | bool | Collapse to single longest prompt (always). Skip repeats via recent-best deque in random mode only. |
| **Local** `local__refresh_listing` (optional) | bool | Force a re-scan of the folder. |
| **Dexter** `dexter__category` | dropdown | Sitemap category slug, or `(any)`. |
| **Dexter** `dexter__clear_cache` | bool | Drop the recent-pick deque. |
| **Dexter** `dexter__timeout` (optional) | int 2–60 | HTTP timeout per request. |
| **CivitAI** `civitai__mode` | enum | `Blue (SFW)` / `Red (NSFW)`. |
| **CivitAI** `civitai__base_model` | dropdown | Restrict picks to a base model. |
| **CivitAI** `civitai__period` | enum | Time window. |
| **CivitAI** `civitai__sort` | enum | Gallery sort. |
| **CivitAI** `civitai__username` | string | Restrict to one uploader (optional). |
| **CivitAI** `civitai__timeout` (optional) | int 2–60 | HTTP timeout per request. |
| **Output** `prompt_single` | STRING (list) | Single-line prompt. |
| **Output** `prompt_multiline` | STRING (list) | Prompt with newlines preserved. |
| **Output** `image` | IMAGE (list) | Result image. |
| **Output** `image_path` | STRING (list) | Absolute path for Local mode; empty for web modes. |

**Refresh button.** In `PromptDexter` mode the node shows **🔄 refresh sitemap**, which re-reads PromptDexter's sitemap and updates the category list (a status line reports the prompt and category counts). In `CivitAI` mode it shows **🔄 clear cache**, which makes the next run page the gallery again; the status line also notes when no `civitai.secret` file is present and only public access is available. Local Folder mode hides both.

Node tint hue-shifts by active mode.

---

## 🔧 Ray's Tools: Metadata Inspector (`RayMetaInspect`)

**Purpose.** Read or write image generation metadata. Two modes:

- `Inspect` — parses every known chunk (A1111 `parameters`, ComfyUI `prompt` / `workflow` graph, EXIF UserComment, sidecar text) and exposes the extracted fields as separate STRING outputs plus the raw JSON blob.
- `Embed` — writes an IMAGE tensor + `metadata_json` dict back to disk at `path`, then re-parses the file for round-trip verification.

In `Inspect`, connect a **Load Image** node to `image` and the node reads the metadata of the file it loaded: the connection is traced upstream, through nodes that only transform the image (resize, crop and similar), to the file's name. A connected image wins over `path`. An image that was generated rather than loaded has no file, so enter a `path` instead.

**Category:** `👑 Ray/🔧 Tools`

| Pin | Type | Notes |
|-----|------|-------|
| **Control** `mode` | enum | `Inspect` / `Embed`. |
| **Control** `path` | string | Inspect: source file, used when no image is connected (absolute, `input/...` or `name [input]`). Embed: destination file. |
| **Input** `image` (optional) | IMAGE | Inspect: connect a Load Image node to read that file's metadata. Embed: tensor to write. |
| **Control** `metadata_json` (optional) | string (multiline) | Embed mode: JSON dict of metadata fields to attach. Visible only in Embed mode. |
| **Output** `prompt_positive` | STRING | Positive prompt extracted from the file. |
| **Output** `prompt_negative` | STRING | Negative prompt extracted from the file. |
| **Output** `seed` | STRING | Seed if present. |
| **Output** `steps` | STRING | Sampler step count if present. |
| **Output** `cfg` | STRING | CFG scale if present. |
| **Output** `sampler` | STRING | Sampler name if present. |
| **Output** `model` | STRING | Model / checkpoint reference if present. |
| **Output** `loras_json` | STRING | LoRAs referenced in the metadata, encoded as JSON. |
| **Output** `width` | STRING | Image width in pixels. |
| **Output** `height` | STRING | Image height in pixels. |
| **Output** `raw_metadata_json` | STRING | Full raw metadata JSON — for debugging or downstream tools. |
| **Output** `image` | IMAGE | Source image tensor. |

---

## ✨ Ray's VFX: Film Stock (`RayFilmStock`)

**Purpose.** Analytical film-stock emulation. Applies a per-stock tonal curve + color response, optional grain and halation, and (optionally) layers a real graded look from a `.cube` / `.3dl` LUT or Photoshop / Lightroom `.xmp` develop-setting file.

**Category:** `👑 Ray/✨ VFX`

| Pin | Type | Notes |
|-----|------|-------|
| **Input** `image` | IMAGE | Source frame(s). |
| **Control** `preset` | enum | Film stock name (Kodak Portra 400, Ilford HP5+, Cinestill, Fujifilm Velvia, …). |
| **Control** `intensity` | float 0–1 | Master mix vs untouched input. |
| **Control** `grain_amount` | float 0–4 | Grain strength (0 = off). |
| **Control** `halation_amount` | float 0–4 | Halation bloom strength (0 = off). |
| **Control** `expose_stops` | float ±4 | Exposure compensation before the tonal curve. |
| **Control** `seed` | int | `-1` for random; any `≥0` value is reproducible. |
| **Control** `assets_folder` (optional) | string | Folder recursed for `.cube` / `.3dl` LUTs and `.xmp` develop presets. |
| **Control** `asset_file` (optional) | dropdown | LUT / XMP file to overlay on top of the analytical curve. Repopulated live by the frontend when `assets_folder` changes. |
| **Output** `image` | IMAGE | Emulated film-stock image. |

---

## ✨ Ray's VFX: VHS / Tape (`RayVHS`)

**Purpose.** Videotape degradation modeled as a signal chain in YUV space, plus a VCR or camcorder on-screen display (OSD) that is burned into the picture rather than laid over it. The stages follow the path a tape signal takes: soft luma with deck sharpening halos, low-bandwidth colour that smears and lags behind the picture, cross-colour rainbows around fine detail, smooth line-level time-base wobble with tracking bands and a bent top edge, the torn head-switching band at the bottom, streaky tape noise, and dropouts.

**OSD.** The status readout (PLAY / REC / PAUSE / STOP) and the date / time stamp can be shown together, each in its own corner, in white, yellow or green. Lines that share a corner stack, status above stamp. The text is composited before the tape stages, so it goes through the same luma softening, colour bleed and lag, line wobble, noise and dropouts as the picture, the way a camcorder's burned-in stamp behaves. On top of that the character generator adds a dark outline with a smeared drop shadow, a little line jitter of its own and a faint shimmer along the glyph edges. The margins keep it inside the safe area and clear of the head-switch band.

**Fade.** `effect_fade` alpha-blends the result with the source: `0` is the full effect, `1` is the untouched picture. At any fade the OSD keeps its text, with its analog imperfections fading out along with everything else.

Every effect is sized relative to the picture, not in pixels, so a preset looks the same on a small frame and on a 4K one. A fixed `seed` always gives the same tape, and changing one slider never reshuffles another effect's noise.

Each slider defaults to `-1.0` (meaning "use the preset value") and `0..1` overrides that one effect. Setting every slider to `0` leaves only the preset's softness, colour and levels; the picture is otherwise clean.

**Presets.** Each preset is a tape and deck: it sets the softness, deck sharpening halos, colour handling, levels and the starting value of every slider.

| Preset | What it models |
|--------|----------------|
| Pristine SP | A well-kept standard-play tape on a good deck: soft, slightly lifted blacks, colour smeared a little, hardly any faults. |
| S-VHS | Higher-resolution luma and separated colour (no rainbow artifacts), very stable. |
| Worn EP | A rewatched extended-play tape (the default): soft, noisy, colour lagging, tracking wander, dropouts and a visible head-switch tear. |
| Gen-3 dub | A copy of a copy: very soft, washed-out and hue-drifted colour, strong halos, heavy noise and dropouts. |
| VHS-C camcorder | A compact-cassette camcorder: punchy saturated colour, crunchy highlights, strong sharpening, little tape damage. |
| Hi8 | 8 mm tape: sharper than VHS with good colour and few faults. |
| Rental tape | A shop rental played to death: many dropouts, tracking trouble and a bent top edge. |
| Off-air LP | A long-play recording from broadcast TV: soft, with strong cross-colour rainbows and colour lag. |
| Chewed tape | Damaged tape: tracking bands full of snow, a badly torn bottom edge, constant dropouts. |
| Custom | A neutral middle setting to start your own look from. |

**Category:** `👑 Ray/✨ VFX`

| Pin | Type | Notes |
|-----|------|-------|
| **Input** `image` | IMAGE | Source frame(s). |
| **Control** `preset` | enum | Tape and deck (baseline for the sliders below). |
| **Control** `chroma_blur` | float ±1 | Colour bandwidth loss: how far chroma smears and lags the picture. |
| **Control** `head_switch` | float ±1 | The skewed, noisy band at the bottom of the frame. |
| **Control** `tracking_jitter` | float ±1 | Line wobble and tracking bands (with snow). |
| **Control** `dropout_rate` | float ±1 | Dropout streaks, short bright or dark lines with a soft tail. |
| **Control** `hiss` | float ±1 | Tape noise in brightness and colour, streaky along the scanline. |
| **Control** `yc_separation` | float ±1 | Cross-colour rainbows and dot crawl around fine detail. |
| **Control** `effect_fade` | float 0..1 | Blend back toward the source. `0` (default) is the full effect, `1` the untouched picture. |
| **Control** `osd_status` | enum | `Off` / `▶ PLAY` / `● REC` / `❚❚ PAUSE` / `■ STOP`, drawn in a built-in VCR pixel font. |
| **Control** `osd_status_corner` | enum | `TL` / `TR` / `BL` / `BR` (default `TL`). |
| **Control** `osd_stamp` | enum | `Off` / `Date` / `Time` / `Date+Time`; shows together with the status line. |
| **Control** `osd_stamp_corner` | enum | `TL` / `TR` / `BL` / `BR` (default `BR`). Shares a corner with the status line by stacking. |
| **Control** `osd_date` | string | `YYYY MM DD`; blank stamps today's date. |
| **Control** `osd_color` | enum | `White` / `Yellow` / `Green`. |
| **Control** `seed` | int | `-1` for random; any `≥0` value is reproducible. |
| **Output** `image` | IMAGE | Tape-degraded image with the OSD burned in. |

---

## 🔧 Ray's Tools: TXT Folder (`RayTextFolder`)

**Category:** `👑 Ray/🔧 Tools`

Read UTF-8 .txt files from one folder, alphabetically by filename; subfolders
are excluded. Each non-empty file is one prompt, including its paragraphs
and whitespace. A UTF-8 BOM is removed. Files are re-read on every execution.

| Control / output | Behavior |
|---|---|
| `directory` | Folder containing prompt files |
| `start_index` | Zero-based starting file in alphabetical order |
| `limit` | Maximum files examined; -1 means all remaining files |
| `output_prefix` | Save Image prefix; the source filename stem is appended |
| `prompt` | List of complete, unchanged prompts |
| `filename_prefix` | Equally sized list of matching output prefixes |

Empty files are skipped, but still count toward start_index and limit.
No usable prompts produces an actionable error instead of a blank generation.
Read/decode failures stop execution before any prompt list is emitted.

Connect `prompt` to RayKrea2Sampler's text input and `filename_prefix` to
Save Image's filename_prefix input. Connect the sampler image to Save Image.
ComfyUI maps the paired lists automatically; no extra loop is needed.
Keep the sampler batch size at 1 for one image per file. Save Image adds its
normal counter suffix. Use limit 3 for a small test, then -1 for the folder.

## 💬 Ray's LLM: Folder Captioner (`RayVLMFolder`)

**Category:** `👑 Ray/💬 LLM`

Connect a full vision-language `CLIP` (for example Qwen3-VL from a
`CLIPLoader` with type `qwen_image`, the same setup as Fast Qwen3-VL) and caption
each selected image independently on GPU. The node
uses native `CLIP.tokenize/generate/decode` with the image template enabled,
and preserves the supplied instruction and decoded answer. It does not write
sidecars, resize source images, or add a conversation history.

| Control | Behavior |
|---|---|
| `clip` (input) | Full generative VLM CLIP, e.g. Qwen3-VL from `CLIPLoader`; an ordinary text-only CLIP is unsuitable |
| `folder`, `recurse_subfolders` | Source folder and optional recursive scan |
| `start_index`, `limit` | Zero-based alphabetical relative-path range; -1 means all remaining files |
| `user_prompt` | Multiline instruction used independently for each image |
| `max_length` | Maximum generated tokens per image |
| `temperature` | Sampling temperature; 0 selects greedy decoding |
| `top_k`, `top_p`, `min_p` | Native token sampling filters |
| `repetition_penalty` | Native repetition penalty; 1 is neutral |
| `seed` | -1 selects a random seed per image; a fixed seed is reused per image for repeatability |
| `thinking` | Requests model-supported thinking; any decoded reasoning is retained in text |

Outputs `text`, `image`, and `image_path` are aligned lists. Each image is
a separate RGB tensor with EXIF orientation applied, so mixed sizes work.
Connect an output to a display, save, or downstream processing node to run.

Supported formats: JPEG, PNG, WebP, BMP, TIFF, GIF. Animated/multipage files use
their first frame. HEIC is not included. Folder contents are rescanned each run.
Unreadable files, absent vision tokens, CPU fallback, and empty answers stop the
run with an error rather than emitting misleading captions. No files are modified.

All outputs become available after the selected range finishes. Full-resolution
images accumulate in RAM; use a small `limit` and advance `start_index` for
large folders. ComfyUI manages model offloading; CPU staging is allowed, but
the inference device must be a GPU. The checkpoint must fit the available resources.


## 🔧 Ray's Tools: Save Image (`RaySaveImage`)

**Category:** `👑 Ray/🔧 Tools`. Output node; no output sockets.

| Input | Purpose |
|---|---|
| `image_1` | Required IMAGE batch. |
| `image_2` | Optional IMAGE batch; enables comparison. |
| `save_image` | `none`, `1` (default), `2`, or `both`; presented as compact segmented buttons. |
| `directory` | Blank for ComfyUI output, relative to output, or an absolute destination. Browse lists folders on the ComfyUI host. |
| `filename_prefix` | Filename-only prefix; input number, batch index, and a unique ID are appended. |
| `save_without_metadata` | Right-click toggle; removes prompt/workflow PNG text metadata. Defaults to false. |

Saving happens on execution. Selecting 2 without image_2 gives an actionable
error; Both with only image_1 saves that input. Preview-only mode writes only to
ComfyUI's temporary folder. All saved images retain resolution and alpha. The
comparison fits each image without stretching; a singleton repeats across the
other batch, and unequal non-singleton batches show unpaired trailing images.
Drag the divider or focus it and use Left/Right/Home/End. Folder history holds
three successful destinations per browser, independently of workflow values.

Right-click **Ray's Tools: Save Image → Open image location in Explorer** to
open the folder from its latest successful save. The option becomes available
after a save in the current session and stays tied to that folder if you edit
the next destination or run preview-only. Explorer opens on the Windows ComfyUI host.
