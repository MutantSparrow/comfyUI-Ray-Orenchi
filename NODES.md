# Node Documentation

All nodes live under the `Ray/*` category in the ComfyUI add-node menu.

---

## Ray's VFX: CRT (`RayCRT`)

**Purpose.** Image-space CRT display effect. Simulates phosphor mask (aperture / shadow / slot), scanline beam, halation + bloom, NTSC chroma bleed, barrel curvature, vignette, and reflection gloss. Multiple SOTA-inspired presets covering classic monitors and gaming consoles.

**Category:** `Ray/CRT📺`

| Pin | Type | Notes |
|-----|------|-------|
| **Input** `image` | IMAGE | Source frame(s). BHWC accepted. |
| **Control** `preset` | enum | `trinitron_aperture`, `pvm_shadow`, `consumer_slot`, `composite_ntsc`, `arcade_royale`, `lottes_fast`, `mattias_stylised`, `royale_kurozumi`, `guest_advanced`, `cyberlab_pixels`, `newpixie_framed`, `gtu_composite`, `hyllian_glow`, `super_famicom`, `megadrive`, `ps1`, `ps2`, `nintendo_ds`, `gameboy_advance`, `psp` |
| **Control** `curvature` | bool | Lottes barrel warp (out-of-bounds becomes black bezel). |
| **Control** `intensity` | float 0–1 | Master mix vs untouched input. |
| **Control** `scanline_strength` | float 0–2 | Scales preset scan depth. |
| **Control** `mask_strength` | float 0–2 | Scales preset mask depth + brightness compensation. |
| **Output** `crt_image` | IMAGE | Same H/W/B as input. |

---

## Ray's VFX: Offset Print (`RayOffsetPrint`)

**Purpose.** Image-space CMYK / duotone offset print simulation. Per-plate halftone screen at SWOP angles, plate misregistration, dot gain, ink bleed, paper substrate (tint + grain + texture), optional sepia / vignette / posterize.

**Category:** `Ray/CRT📺`

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
| **Output** `print_image` | IMAGE | Same H/W/B as input. |

---

## Ray's VFX: Pixel Art (`RayPixelArtDetector`)

**Purpose.** Pixel-art conversion: downscale (manual or auto pixel-size detection), optional dithering, palette reduction (kmeans Lab / kmeans RGB / quantize / OkLab hue ramps), solid-background isolation, optional silhouette outline, plus a hue-sorted palette preview.

**Category:** `Ray/PixelArt🕹️`

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

## 🎛️ Ray's Analog Series: Knob (`RayKnob`)

**Purpose.** Analog-style float knob widget. Drag rotates the knob; outputs both an `INT` and a `FLOAT` so it plugs into either side directly.

**Category:** `Ray/Knob🎛️`

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

---

## 🔘 Ray's Analog Series: Switch (`RaySwitch`)

**Purpose.** Boolean toggle widget. Trivial — exists so workflows pick up the analog-series visual style.

**Category:** `Ray/Switch🔘`

| Pin | Type | Notes |
|-----|------|-------|
| **Control** `state` | bool | Toggle. |
| **Output** `bool` | BOOLEAN | Mirror of `state`. |

---

## Ray's LM: Ollama + Clip Chat (`RayOllamaChat`)

**Purpose.** Inline chat node with two backends:
- **Ollama** — talks to a local Ollama server; supports image and audio attachments.
- **CLIP** — drives the text encoder of a ComfyUI-loaded CLIP model directly, no external server. Vision-language CLIPs are rejected.

The chat UI is rendered inside the node; conversation history is stored on the node so workflows reload chats after restart.

**Category:** `Ray/LLM💬`

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

## Ray's LM: LM Prompt Iterator (`RayPromptIterator`)

**Purpose.** Image-prompt judge + rewriter via Ollama. Given the original prompt and (optionally) the rendered image, returns a confidence score `[0, 1]` for how well the image matches the prompt and a revised prompt aimed at fixing visible mismatches. System prompt loaded from `iterator_sysprompt.txt` (overridable by editing that file).

**Category:** `Ray/LLM💬`

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

## Ray's Web: PromptDexter Scraper (`RayPromptDexter`)

**Purpose.** Fetches a random prompt + matching image from [promptdexter.com](https://promptdexter.com/). Discovery is **sitemap-driven**, so picks reach deep content (not just homepage top row). Seed-deterministic — freeze the seed for reproducible output. Maintains a per-node 20-entry LRU cache so consecutive runs avoid recent repeats; with a frozen seed, the cache forces a deterministic skip to the next seed-shuffled candidate. When a prompt page has no associated image, the IMAGE output falls back to a 1×1 black tensor so downstream nodes never break.

**Category:** `Ray/Web🌐`

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
