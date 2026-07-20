# Node Documentation

All nodes live under `👑 Ray/` in the ComfyUI add-node menu, split across
four bucket sub-categories:

- `👑 Ray/✨ VFX` — image-space effects (CRT, Offset Print, PixelArt, FilmStock, VHS).
- `👑 Ray/🎛️ Analog` — analog-style UI widgets (Knob, Switch).
- `👑 Ray/📝 Prompts` — scrapers, hub fetcher, metadata inspector.
- `👑 Ray/💬 LLM` — chat, prompt iterator, prompt library.

See [UI.md](UI.md) for the pack's UI/UX canon (naming, category, color,
widget, and web-layer rules).

Every node is tinted by its bucket. Mode-tinted nodes (`RayCivitAI`,
`RayPromptFetcher`, `RayPromptLibrary`) hue-shift their bucket color rather
than pick a bespoke one.

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

**Purpose.** Pixel-art conversion: downscale (manual or auto pixel-size detection), optional dithering, palette reduction (kmeans Lab / kmeans RGB / quantize / OkLab hue ramps), solid-background isolation, optional silhouette outline, plus a hue-sorted palette preview.

**Category:** `👑 Ray/✨ VFX`

| Pin | Type | Notes |
|-----|------|-------|
| **Input** `image` | IMAGE | Source. |
| **Input** `palette_image` (optional) | IMAGE | Fixed palette source. Snaps palette size to {2}∪{4·k}; bypasses source-derived clustering. |
| **Control** `mode` | enum | `manual_resize`, `auto_downscale_loose`, `auto_downscale_strict`, `auto_pixel_size` |
| **Control** `target_resolution` | int 32–2048 | Target longest side (manual_resize). |
| **Control** `max_downscale_factor` | int 2–64 | Cap for auto modes. |
| **Control** `reduce_palette` | bool | Run palette reduction. |
| **Control** `max_colors` | int 2–256 | Palette size target. |
| **Control** `palette_strategy` | enum | `kmeans_lab`, `kmeans_rgb`, `quantize_simple`, `ramps_oklab` |
| **Control** `ramp_levels` | enum 3/4/5 | L\* levels per hue/chroma cluster (`ramps_oklab`). |
| **Control** `protect_highlights` | bool | Reserve a slot for near-white highlights. |
| **Control** `highlight_threshold` | int 50–100 | L\* cutoff for highlight protection. |
| **Control** `dither` | enum | `none`, `bayer_2x2`, `bayer_4x4`, `bayer_8x8`, `blue_noise`, `riemersma`, `knoll` |
| **Control** `selective_dither` | bool | Restrict dither to non-smooth regions. |
| **Control** `dither_smooth_threshold` | float 0–0.30 | OkLab L\* std cutoff for smooth-region detection. |
| **Control** `silhouette_outline` | bool | Darken silhouette edges by N palette ranks. |
| **Control** `outline_steps` | int 1–3 | Palette-rank steps for the outline. |
| **Control** `seed` | int | RNG seed (affects kmeans, blue noise). |
| **Output** `pixel_art` | IMAGE | Reduced image. |
| **Output** `palette_preview` | IMAGE | Hue-sorted swatch grid. |

---

## 🎛️ Ray's Analog: Knob (`RayKnob`)

**Purpose.** Analog-style float knob widget. Drag rotates the knob face; outputs both an `INT` (quantized by `clamp`) and a raw `FLOAT` so it plugs into either side without a converter.

**Category:** `👑 Ray/🎛️ Analog`

| Pin | Type | Notes |
|-----|------|-------|
| **Control** `min_value` | float | Range minimum. |
| **Control** `max_value` | float | Range maximum. |
| **Control** `spin_value` | float 10–100 | Drag sensitivity (px per full sweep). |
| **Control** `clamp` | float ≥0 | Quantization step for the INT output (`0` → truncate). |
| **Control** `allow_negative` | bool | Whether `min_value` may go below 0. |
| **Control** `knob_value` | float | Current value (driven by the widget). |
| **Output** `int` | INT | Quantized via `clamp`. |
| **Output** `float` | FLOAT | Raw clamped float in `[min, max]`. |

**Right-click menu.** Style picker (brushed-metal, black-plastic, bakelite, brass, and more), **Compact mode** (hides the min/max/spin/clamp/allow_negative config widgets and blanks the node title so the node reads as a bare analog appliance — brushed panel, Dymo label, knob face and readout stay), **Edit label…** (Dymo tape above the face). Double-clicking the Dymo tape also enters edit mode. Style, compact flag, and label text persist with the workflow.

---

## 🎛️ Ray's Analog: Switch (`RaySwitch`)

**Purpose.** Boolean toggle widget. Six physical styles, each with correct on/off geometry (Chrome Rocker press-LED-down = ON; Bakelite Flip bat-handle up = ON; Silver Paddle points to the lit label; Brass Slider slides toward the lit label).

**Category:** `👑 Ray/🎛️ Analog`

| Pin | Type | Notes |
|-----|------|-------|
| **Control** `state` | bool | Toggle. |
| **Output** `bool` | BOOLEAN | Mirror of `state`. |

**Right-click menu.** Style picker (Chrome Rocker, Bakelite Flip, Silver Paddle, Brass Slider, Minimal Pill, Dark Studio Dome), **Compact mode** (blanks the node title so the node reads as a bare analog appliance — brushed panel, Dymo label, switch face and readout stay), **Edit label…** (Dymo tape). Double-clicking the Dymo tape also enters edit mode. Style, compact flag, and label text persist with the workflow.

---

## 💬 Ray's LLM: Ollama Chat (`RayOllamaChat`)

**Purpose.** Inline chat node with two backends:
- **Ollama** — talks to a local Ollama server; supports image and audio attachments.
- **CLIP** — drives the text encoder of a ComfyUI-loaded CLIP model directly, no external server. Vision-language CLIPs are rejected.

The chat UI is rendered inside the node; conversation history is stored on the node so workflows reload chats after restart.

**Category:** `👑 Ray/💬 LLM`

| Pin | Type | Notes |
|-----|------|-------|
| **Input** `system_prompt` (optional) | STRING (forced) | System message. |
| **Input** `user_prompt` (optional) | STRING (forced) | One-shot user message (alternative to chatbox). |
| **Input** `image` (optional) | IMAGE | Attached when `attach_image` is on. |
| **Input** `audio` (optional) | AUDIO | Attached as base64 WAV when `attach_audio` is on. |
| **Input** `clip` (optional) | CLIP | Required for `inference_mode = clip`. |
| **Control** `inference_mode` | enum | `ollama` or `clip`. |
| **Control** `server_url` | string | Ollama server URL. |
| **Control** `model` | string | Ollama model name (or hint for CLIP mode). |
| **Control** `keep_alive` | string | Ollama keep-alive (e.g. `5m`). |
| **Control** `temperature` | float 0–2 | Sampling temperature. |
| **Control** `seed` | int | `-1` for random. |
| **Control** `think` | bool | Toggle Ollama "thinking" mode where supported. |
| **Control** `max_new_tokens` | int 1–4096 | CLIP-mode generation cap. |
| **Control** `top_p` | float 0–1 | CLIP-mode nucleus sampling. |
| **Control** `repetition_penalty` | float 1–2 | CLIP-mode repetition penalty. |
| **Control** `attach_image` | bool | Attach the IMAGE input to the next user turn. |
| **Control** `attach_audio` | bool | Attach the AUDIO input to the next user turn. |
| **Control** `chat_history` | string (multiline) | JSON-encoded turn list maintained by the widget. |
| **Control** `last_message` / `pending_user_prompt` | string | Wire-state for the chat UI; usually left alone. |
| **Output** `last_message` | STRING | Last assistant reply. |

---

## 💬 Ray's LLM: Prompt Iterator (`RayPromptIterator`)

**Purpose.** Image-prompt judge + rewriter via Ollama. Given the original prompt and (optionally) the rendered image, returns a confidence score `[0, 1]` for how well the image matches the prompt and a revised prompt aimed at fixing visible mismatches. System prompt loaded from `iterator_sysprompt.txt` (overridable by editing that file).

**Category:** `👑 Ray/💬 LLM`

| Pin | Type | Notes |
|-----|------|-------|
| **Input** `original_prompt` | STRING (forced) | Original generation prompt. |
| **Input** `image` (optional) | IMAGE | Generated image to score against the prompt. |
| **Input** `changes_required` (optional) | STRING (forced) | Free-form user guidance for the rewrite. |
| **Control** `server_url` | string | Ollama server URL. |
| **Control** `model` | string | Vision-capable Ollama model recommended when an image is attached. |
| **Control** `keep_alive` | string | Ollama keep-alive. |
| **Control** `temperature` | float 0–2 | Sampling temperature. |
| **Control** `seed` | int | `-1` for random. |
| **Control** `copy_to_clipboard` | bool | Tells the frontend to copy `new_prompt` to the clipboard on execute. |
| **Output** `new_prompt` | STRING | Revised prompt. |
| **Output** `confidence` | FLOAT | Image-vs-prompt match score `[0, 1]`. |
| **Output** `image` | IMAGE | Pass-through of the input image (so it stays on the wire). |

---

## 📝 Ray's Prompts: PromptDexter Scraper (`RayPromptDexter`)

**Purpose.** Fetches a random prompt + matching image from [promptdexter.com](https://promptdexter.com/). Discovery is **sitemap-driven**, so picks reach deep content (not just homepage top row). Seed-deterministic — freeze the seed for reproducible output. Maintains a per-node 20-entry LRU cache so consecutive runs avoid recent repeats; with a frozen seed, the cache forces a deterministic skip to the next seed-shuffled candidate. When a prompt page has no associated image, the IMAGE output falls back to a 1×1 black tensor so downstream nodes never break.

**Category:** `👑 Ray/📝 Prompts`

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

## 📝 Ray's Prompts: CivitAI Gallery Scraper (`RayCivitAI`)

**Purpose.** Fetches a random gallery image + its prompt from [civitai.com](https://civitai.com/) via the public REST API (`GET /api/v1/images`). Items with a usable prompt are kept — either the direct `meta.prompt` field, or, when missing, the text salvaged from a ComfyUI workflow blob embedded in `meta.comfy` (CLIPTextEncode / Text Multiline nodes etc.). Items with no extractable prompt are skipped. Seed-deterministic, per-node 20-entry LRU to avoid consecutive repeats, page cache keyed by (mode, period, sort, base_model, username). 1×1 black tensor fallback if an image fails to download.

**Access strategy.** REST API (not scraping, not MCP). Public endpoint, no key required for read access. Higher-tier content unlocks if a token file is present at `civitai.secret` inside the node-pack directory — never hard-coded. The legacy `nsfw` filter is bypassed in favour of `browsingLevel` (bitmask: PG=1, PG13=2, R=4, X=8, XXX=16), which the API documents as taking precedence. Blue = `PG | PG13` = `3`; Red = all levels OR'd = `31`.

**Category:** `👑 Ray/📝 Prompts`

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

## 📝 Ray's Prompts: Folder Image Scraper (`RayLocalScraper`)

**Purpose.** Picks a random image from a local folder and extracts any generation prompt found in its metadata. Functional sibling to the PromptDexter and CivitAI scrapers, but read off disk instead of HTTP. Seed-deterministic; per-node 20-entry LRU avoids consecutive repeats; folder listing cached until `refresh_listing` is set or the cache is cleared.

**Prompt sources, in priority order:**
1. PNG `parameters` text chunk (Automatic1111 / Forge; JSON blob variants also parsed).
2. PNG `prompt` text chunk (ComfyUI serialized prompt graph, JSON; flat-literal fallback for JustRayzist-style writers).
3. PNG `workflow` text chunk — API format or UI (`nodes[]`/`links[]`) format.
4. Any other `info[]` key whose name looks prompt-shaped (`prompt_*`, `positive*`, `caption`, `description`, `comment`, `sui_image_params`, `invokeai_metadata`, `novelai_metadata`, `dream`…). JSON values are walked recursively for nested `prompt` / `positive` keys.
5. EXIF text tags: UserComment (37510), ImageDescription (270), XPComment (40092), XPSubject / XPTitle / XPKeywords.
6. `<image>.txt` sidecar file in the same directory.

For ComfyUI graphs, the extractor first locates every text-encoder node (`CLIPTextEncode` / `CLIPTextEncodeFlux` / `CLIPTextEncodeSDXL` / `BNK_CLIPTextEncodeAdvanced` / `T5TextEncode` / `ImpactWildcardEncode` etc.). Each encoder contributes one prompt: if its `text` input is a literal string the literal is used; if it's wired to another node, the link is followed back through `ShowText` → `Text Multiline` → `String Literal` → `Text Concatenate` → primitive nodes (up to 8 hops, cycles detected) until a literal is found. Multiple text inputs on a concat-style node are joined with spaces.

Every candidate is passed through a path-rejection filter that drops strings that look like filesystem paths (drive letters, backslash runs, bare `.safetensors` / `.ckpt` filenames), so random `C:\loras\foo.safetensors`-style fields don't leak through as prompts.

If the image carries multiple positive prompts (e.g. a ComfyUI workflow with several `CLIPTextEncode` nodes), every output is emitted as a ComfyUI **list** — one entry per prompt — so downstream nodes iterate once per prompt. The `image` and `image_path` outputs are broadcast (repeated) across each prompt entry so each iteration sees a matching `(prompt, image, path)` triple. Single-prompt images still return lists of length 1; if no prompt is found and `skip_no_prompt` is off, the output is a single-entry list with an empty string in both prompt slots.

**Category:** `👑 Ray/📝 Prompts`

| Pin | Type | Notes |
|-----|------|-------|
| **Control** `folder` | string | Absolute path to a folder of images. Required; raises if blank or missing. |
| **Control** `recurse_subfolders` | bool | When on, walks every subdirectory under `folder`. Off by default. |
| **Control** `skip_no_prompt` | bool | When on, skip images whose metadata yields no prompt and pick the next one from the seed-shuffled pool (capped at 50 attempts). |
| **Control** `prompt_best_try` | bool | Collapse each image to its single best (longest) prompt AND skip a pick when the best-try text matches the last one emitted from this node. Advances until a new prompt is found or the pool runs out. |
| **Control** `seed` | int | `-1` for OS-random (non-deterministic). Any `≥0` value is reproducible. |
| **Control** `refresh_listing` (optional) | bool | Force a re-scan of the folder before picking. Off by default so repeated runs are cheap. |
| **Output** `prompt_single` | STRING (list) | One entry per prompt found, each whitespace-collapsed to a single line. |
| **Output** `prompt_multiline` | STRING (list) | One entry per prompt found, newlines preserved. |
| **Output** `image` | IMAGE (list) | Image tensor (BHWC float32 [0,1]), repeated across every prompt entry. |
| **Output** `image_path` | STRING (list) | Absolute path of the chosen file, repeated across every prompt entry. |

**Inline preview.** After each execute the node renders the picked image inside itself — no downstream Preview Image required.

Supported file extensions: `.png`, `.jpg`, `.jpeg`, `.webp`, `.bmp`, `.tiff`, `.tif`.

---

## 📝 Ray's Prompts: Prompt Fetcher (`RayPromptFetcher`)

**Purpose.** One node, three prompt sources. A `scraper_mode` dropdown picks between `Local Folder`, `PromptDexter`, and `CivitAI`; the frontend hides widgets that don't belong to the active mode. Outputs are harmonized to the local-scraper shape `(prompt_single, prompt_multiline, image, image_path)` so any mode is drop-in compatible with downstream wiring.

**Category:** `👑 Ray/📝 Prompts`

| Pin | Type | Notes |
|-----|------|-------|
| **Control** `scraper_mode` | enum | `Local Folder` / `PromptDexter` / `CivitAI`. Drives which widget group is shown and which backend runs. |
| **Control** `seed` | int | `-1` for random; any `≥0` value is reproducible. Shared across modes. |
| **Local** `local__folder` | string | Absolute path to a folder of images. |
| **Local** `local__recurse_subfolders` | bool | Walk every subdirectory. |
| **Local** `local__skip_no_prompt` | bool | Skip images whose metadata yields no prompt. |
| **Local** `local__prompt_best_try` | bool | Collapse to single best prompt + skip repeats of the last one. |
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

Node tint hue-shifts by active mode. Inline preview widget renders the emitted image.

---

## 📝 Ray's Prompts: Metadata Inspector (`RayMetaInspect`)

**Purpose.** Read or write image generation metadata. Two modes:

- `Inspect` — parses every known chunk (A1111 `parameters`, ComfyUI `prompt` / `workflow` graph, EXIF UserComment, sidecar text) and exposes the extracted fields as separate STRING outputs plus the raw JSON blob.
- `Embed` — writes an IMAGE tensor + `metadata_json` dict back to disk at `path`, then re-parses the file for round-trip verification.

Drag an image into the inline drop-zone to prefill `path` and preview it in-node.

**Category:** `👑 Ray/📝 Prompts`

| Pin | Type | Notes |
|-----|------|-------|
| **Control** `mode` | enum | `Inspect` / `Embed`. |
| **Control** `path` | string | Source file (Inspect) or destination file (Embed). |
| **Input** `image` (optional) | IMAGE | Embed mode: tensor to write. |
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

**Purpose.** Videotape degradation modeled in YUV space: chroma blur, head-switching band, tracking wobble, dropouts, hiss, Y/C separation — plus an OSD overlay that mimics a classic VCR readout.

Each slider defaults to `-1.0` (meaning "use the preset value") and `0..1` overrides that channel.

**Category:** `👑 Ray/✨ VFX`

| Pin | Type | Notes |
|-----|------|-------|
| **Input** `image` | IMAGE | Source frame(s). |
| **Control** `preset` | enum | Tape / speed preset (baseline for the sliders below). |
| **Control** `chroma_blur` | float ±1 | Chroma blur strength. |
| **Control** `head_switch` | float ±1 | Head-switching band at the frame bottom. |
| **Control** `tracking_jitter` | float ±1 | Horizontal tracking wobble. |
| **Control** `dropout_rate` | float ±1 | Bright dropout streaks. |
| **Control** `hiss` | float ±1 | Luma noise / analog hiss. |
| **Control** `yc_separation` | float ±1 | Y/C separation artifact strength. |
| **Control** `osd_mode` | enum | `Off` / `▶ PLAY` / `● REC` / `Date` / `Date+Time`. |
| **Control** `osd_corner` | enum | `TL` / `TR` / `BL` / `BR`. |
| **Control** `osd_date` | string | `YYYY MM DD`; blank stamps today's date. |
| **Control** `seed` | int | `-1` for random; any `≥0` value is reproducible. |
| **Output** `image` | IMAGE | Tape-degraded image with the OSD overlay applied. |

---

## 💬 Ray's LLM: Prompt Library (`RayPromptLibrary`)

**Purpose.** Local SQLite prompt library. Two modes on the same node — `Save` writes `prompt_in` to the DB with source, tags, image path, and model; `Browse` serves rows from an inline searchable table. Node tint hue-shifts between the two modes.

**Category:** `👑 Ray/💬 LLM`

| Pin | Type | Notes |
|-----|------|-------|
| **Control** `mode` | enum | `Save` / `Browse`. Legacy `Fetch` from older workflows migrates to `Browse`. |
| **Control** `prompt_in` | string (multiline) | Save mode: prompt text to store. Passed through on the outputs regardless of mode. |
| **Control** `seed` | int | `-1` for random. |
| **Save** `save__source` | string | Label attached to this row (`manual` / `local` / `dexter` / `civitai` / `ollama` / free-form). |
| **Save** `save__tags` | string | Comma-separated tags. |
| **Save** `save__image_path` | string | Optional path to the image this prompt produced. |
| **Save** `save__model` | string | Optional model / checkpoint that produced the row. |
| **Browse** `browse__selected_id` | int | DB row id selected in the panel. |
| **Browse** `browse__last_query` | string | Managed by the panel. |
| **Output** `prompt_single` | STRING (list) | Single-line prompt. |
| **Output** `prompt_multiline` | STRING (list) | Prompt with newlines preserved. |
| **Output** `image` | IMAGE (list) | Image stored with the selected row. |
| **Output** `image_path` | STRING (list) | Path to the associated image on disk, if any. |

**Browse panel.** Full-text search, tag + source filters, and multiple sort orders (most recent, longest, similarity by embedding). Click a row to select — the node then serves that row on every subsequent run. Inline preview widget renders the emitted image.
