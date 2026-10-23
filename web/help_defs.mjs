// help_defs.mjs — Ray's Orenchi help content.
//
// One entry per node class, consumed by help.mjs's openHelpPopup. Each card
// shows `summary`, then Inputs / Widgets / Outputs generated from the node
// definition (types, choices, defaults, ranges, Python tooltips), then the
// optional `sections` below.
//
// Keep `summary` to one or two sentences. Describe individual inputs through
// their Python `tooltip` (or `details` here when a tooltip would be too
// long). Use `sections` only for behavior that is not a single widget:
// right-click menus, modes, file formats, wiring tips. Inline `code` via
// backticks. A node without an entry still gets its DESCRIPTION as summary.

export const RAY_HELP_DEFS = {
    RayModelCard: {
        summary: "Connect MODEL, CLIP and VAE to generate a complete visual model benchmark. Outputs the full black card, a reduced preview, source images in card order, and a Markdown report as text.",
        sections: [{ heading: "Benchmark config", bullets: [
            "Leave config disconnected to run 66 images across eleven categories. Copy Config copies that exact editable template; paste it into a multiline string node and connect it to config.",
            "Start categories with +CATEGORY. Entries use caption::positive prompt|negative prompt; caption and negative are optional. Blank lines are ignored. There are no comments or global negative prompts.",
            "Escape delimiters with \\|, \\::, \\+, \\= and \\\\. Only a leading + or = has structural meaning. Errors include config line numbers and happen before sampling.",
            "Card name is an editable, connectable STRING field above the generation controls. Its { } button opens Save Image's name builder with a live preview, dates, times, hashes and widget values such as unet_name, ckpt_name or seed. Spaces are preserved; loader widget paths/extensions are removed.",
            "An optional =TITLE in the config overrides Card name. Blank names fall back to MODEL CARD. Name templates and existing widget selections survive workflow reload.",
        ] }, { heading: "Generation and layout", bullets: [
            "Categories run top to bottom, prompts left to right. The largest category sets the column count; shorter categories reserve empty cells. Captions wrap to two lines, then truncate with an ellipsis; the report keeps complete prompts.",
            "Fixed repeats the initial seed. Increment/decrement advance before each image: initial 100 produces 101, 102, 103 with increment. Seeds wrap at 64 bits. Randomize chooses each image seed independently; all actual seeds are reported. The native seed control also updates the starting seed between queued runs.",
            "Settings controls generation width/height, card width, maximum preview width, embedded guidance and run safeguards. Card height is automatic; preview is resized from the completed card.",
            "Use the supplied model's normal sampler/CFG settings. Auto guidance applies the Settings guidance value to models declaring an embedding. Set supplies it explicitly; Disabled keeps native conditioning. MODEL patches such as shift/renorm belong upstream. V1 benchmarks image generation.",
            "Source images remain in memory. The run count and estimated CPU output budget are checked before generation and can be raised in Settings. Model/VRAM memory is additional. A failed or interrupted run never emits a completed partial card.",
        ] }],
    },
    // ── ✨ VFX ─────────────────────────────────────────────────────────
    RayCRT: {
        summary: "Simulates a CRT display on an image: phosphor mask, scanlines, halation and bloom, NTSC chroma bleed, barrel curvature, vignette and glass reflection.",
        sections: [{
            heading: "Notes",
            bullets: [
                "Presets cover classic monitors (`trinitron_aperture`, `pvm_shadow`, `composite_ntsc`, …) and consoles (`super_famicom`, `megadrive`, `ps1`, `gameboy_advance`, …).",
                "`scanline_strength` and `mask_strength` scale the preset (0–2); `intensity` blends the result over the original.",
            ],
        }],
    },

    RayOffsetPrint: {
        summary: "Simulates CMYK or duotone halftone printing: per-plate screens at SWOP angles, misregistration, dot gain, ink bleed and a paper substrate.",
        sections: [{
            heading: "Notes",
            bullets: [
                "`paper_color` is a hex color (`#fffaf0` ivory, `#ffffff` pure white); `paper_color_mix` 0 keeps the preset paper, 1 fully overrides it.",
            ],
        }],
    },

    RayPixelArtDetector: {
        summary: "Repairs enlarged or damaged pixel art on its exact grid, or converts illustrations/photos at a requested size with rounded aspect preservation.",
        sections: [{
            heading: "Notes",
            bullets: [
                "Use `repair_pixel_art` for existing pixel grids and `illustration_photo` for region abstraction.",
                "`palette_strategy` builds the palette; `palette_mapping` assigns pixels to it. A connected `palette_image` overrides generated palettes (up to 256 exact colors).",
                "Dithering is limited to smooth ramps; flat fills, texture and strong edges are protected. Start with `none`.",
                "Repair preserves the exact aspect lattice, which can limit resizing. Illustration/photo fixes the long edge to the target and rounds the other dimension (1001×667 becomes 128×85 at target 128).",
            ],
        }],
    },

    RayFilmStock: {
        summary: "Emulates film stocks (Portra, HP5+, Cinestill, Velvia and more) with an analytical tone curve and color response, plus grain and halation. Optional LUT or XMP files can be layered on top.",
        sections: [{
            heading: "Notes",
            bullets: [
                "The folder icon next to **LUT / XMP folder** opens your system's folder dialog; the file list refreshes from the folder you pick.",
                "Point `assets_folder` at `.cube` / `.3dl` LUTs and `.xmp` develop files; `asset_file` refreshes live with what it finds.",
            ],
        }],
    },

    RayVHS: {
        summary: "Degrades an image like analog videotape, modeled as a signal chain: soft luma with sharpening halos, smeared and lagging colour, rainbows, line wobble, a torn head-switch band, tape noise and dropouts, with an optional VCR on-screen display that goes through the tape with the picture.",
        sections: [{
            heading: "Notes",
            bullets: [
                "The preset is a tape and deck: it sets softness, halos, colour and levels, and the starting value of every slider. Worn EP is the default; Chewed tape is the extreme.",
                "Effect sliders default to `-1`, which uses the preset value; `0`–`1` overrides that one effect. All sliders at `0` leaves only the preset's softness, colour and levels.",
                "Effects scale with the image, so a preset looks the same at any size. A fixed `seed` always gives the same tape.",
                "`effect_fade` blends the result back toward the source: `0` is the full effect (the default), `1` is the untouched picture. The OSD stays readable at any fade.",
                "The OSD has a status line (PLAY, REC, PAUSE, STOP) and a date / time stamp, each with its own corner, so REC and a date can show together. Lines sharing a corner stack. Pick White, Yellow or Green.",
                "The OSD is burned in before the tape, so it softens, bleeds colour, wobbles and picks up noise and dropouts with the picture, and it gets a smeared shadow and a little line jitter of its own. Leave `osd_date` blank to stamp today's date.",
            ],
        }],
    },

    // ── 🎛️ Analog ─────────────────────────────────────────────────────
    RayKnob: {
        summary: "An analog-style control, a rotary knob or a slider, that outputs a float and a quantized integer, so it can drive either kind of input without a converter.",
        sections: [{
            heading: "Notes",
            bullets: [
                "Drag the face: the dial sweeps 270° from min to max and Shift slows it 20×. Use Arrow/Home/End keys, or type an exact value in the readout. On a slider, click the track to jump the cap there.",
                "Right-click → Control Style picks from the 31 shared styles (nine knobs and five sliders are hand-drawn, the rest are generated to match); Compact mode shows the faceplate alone (no title, dots or panel): drag it by its frame, right-click it for the menu; Edit label… renames the tape label (or double-click it).",
                "Knobs, sliders and switches make hardware sounds, voiced to each style. Right-click → Mute sound turns them off for every analog control; the choice is remembered in this browser.",
                "Right-click → Mouse wheel control lets the scroll wheel drive the dial or slider while the pointer is over the node: 2% of the dial per notch, a tenth of that with Shift. Ctrl + wheel still zooms. It is off by default and shared by every analog control.",
                "Right-click → Curve response… bends how the dial maps to the value, like a pot taper: pick a preset (audio, reverse audio, fine low or high end, S-curve, fine centre) or drag points to draw your own. The value you set and the output stay real values; only where the dial points changes. Linear response turns it off and keeps the curve.",
                "Style, compact mode and label are saved with the workflow.",
            ],
        }],
    },

    RayButtonDeck: {
        summary: "A bank of analog push buttons that replaces a dropdown. Each line you enter becomes a button, and the pressed button's text is the output.",
        sections: [{
            heading: "Notes",
            bullets: [
                "Click the pencil next to **Entries** (or right-click → Edit entries…) and type one value per line. Apply with the button or Ctrl+Enter.",
                "Size the node however you like: the buttons take the grid that makes them biggest, a row in a wide node (1×4 becomes 4 across), 2×2 in a square one, a column in a tall one. Exactly one button is pressed and lit.",
                "Right-click → Compact mode shows the faceplate alone (no title, dots or panel); drag it by its frame and right-click it to switch back.",
                "Arrow keys, Home and End move the selection. Blank and repeated lines are ignored, and the selection follows its value if you reorder the list.",
                "Right-click → Deck Style… picks from the 31 shared styles. Some print the text inside the button, others use a Dymo sticker below it; each has its own sound. Mute sound silences all analog controls.",
                "With Mouse wheel control on (right-click), scrolling over the node presses the next button (wheel down) or the previous one (wheel up), stopping at the ends.",
            ],
        }],
    },

    RayFaderBank: {
        summary: "A bank of analog faders, 2 to 10 in a row and up to 4 rows. Each fader is a vertical slider that outputs a float from 0 to 1.",
        sections: [{
            heading: "Notes",
            bullets: [
                "Set `faders` (Per row, 2–10) and `rows` (1–4): 6 per row and 2 rows make 12. The node shows one output per fader (`fader_1`…, numbered row by row) and hides the rest; `values` is every active fader as a list, in order.",
                "Drag a fader, click its track to jump the cap there, or focus one and use Arrow keys (0.01, Shift for 0.001), PageUp/PageDown (0.1), Home and End. Shift slows a drag 20×.",
                "With Mouse wheel control on (right-click), scrolling over a fader moves just that one: 2% per notch, a tenth of that with Shift.",
                "Lowering `faders` or `rows` removes the extra outputs and any links on them. A fader fed by a link is locked and says so.",
                "Right-click → Curve response… gives every fader the same response curve (a pot taper such as audio log, or one you draw), so the low end can be finer than the top. The outputs stay real 0–1 values.",
                "Right-click → Fader Style… picks from the 31 shared styles; Compact mode shows the faceplate alone (no title, dots or panel); Edit label… renames the tape label; Mute sound silences all analog controls.",
            ],
        }],
    },

    RaySwitch: {
        summary: "An analog-style toggle switch that outputs a boolean.",
        sections: [{
            heading: "Notes",
            bullets: [
                "Click the face, or focus it and press Space/Enter.",
                "Right-click → Switch Style picks from the 31 shared styles (rockers, levers, sliders and keys are hand-drawn, the rest are generated to match); Compact mode shows the faceplate alone (no title, dots or panel); Edit label… renames the tape label.",
                "Each face clicks, clacks or thunks like its hardware. Right-click → Mute sound silences all analog controls.",
                "With Mouse wheel control on (right-click), scrolling over the node switches it on (wheel up) or off (wheel down).",
            ],
        }],
    },

    // ── 💬 LLM ─────────────────────────────────────────────────────────
    RayVLMFolder: {
        summary: "Captions every image in a folder range with a local vision-language model on the GPU, returning captions and paths with optional original-size images.",
        sections: [{
            heading: "Notes",
            bullets: [
                "The folder icon next to **Folder of images** opens your system's folder dialog and fills in the path. You can still type or paste one.",
                "Connect a full generative VLM `CLIP` (such as Qwen3-VL from `CLIPLoader`, type `qwen_image`) to `clip`; text-only encoders cannot caption.",
                "Files are sorted by relative path and captioned one at a time. `return_images` is off by default; enable it to decode the image output after all captioning finishes. Returned images still occupy RAM, so use `start_index` and `limit` to bound that output.",
                "`cleanup_every` releases transient objects and unused ComfyUI VRAM caches every N captions (default 16). Low-memory cleanup also runs when available CPU RAM or VRAM falls below 512 MiB.",
                "Supports JPEG, PNG, WebP, BMP, TIFF and GIF (first frame). Requires a GPU.",
            ],
        }],
    },

    RayFastQwen3VL: {
        summary: "Generates text from images using a Qwen3-VL CLIP that is already loaded, sharing its weights instead of loading a second model copy.",
        sections: [{
            heading: "Notes",
            bullets: [
                "Load a full Qwen3-VL 4B or 8B checkpoint with CLIPLoader (type `qwen_image`, or `krea2`). The same CLIP can also feed image conditioning.",
                "Penalty defaults are neutral: repetition 1.0, presence 0.0. Select the explicit anti_loop preset for presence 1.5, or set custom penalties. Saved custom penalty values remain effective.",
                "Fast Qwen3-VL initialization is validated for ComfyUI 0.42.x; incompatible private APIs use native generation. Other Qwen families also use their native generator.",
                "See FAST_VLM.md for measurements and constraints.",
            ],
        }],
    },

    // ── 🔧 Tools ─────────────────────────────────────────────────────
    RayFolders: {
        summary: "Browse local images, videos and audio. Select files to output native media lists, prompts and paths. The listing refreshes every run, even without connected outputs.",
        sections: [{heading: "Gallery", bullets: [
            "Click selects one file; Ctrl/Cmd-click toggles additional selections. Media retains original dimensions and sample rates.",
            "Folder and fuzzy filename filter accept STRING connections. The cog controls sorting, recursion, 2–7 columns, color/NSFW filters and prompt formatting.",
            "Hover for metadata; hold Shift for the prompt. Double-click opens the viewer. Right-click copies an image, prompt or embedded workflow.",
            "Drag an image to the canvas or an existing Load Image node. A copy is imported; the original stays in place.",
            "The bottom note shows total media counts. Missing files are dropped from selection; deleted folders or disconnected drives show an unavailable state. Refresh after reconnecting.",
        ]}, {heading: "List outputs", bullets: [
            "images, videos and audio contain only their respective media type. prompt and paths cover the whole mixed selection in gallery order.",
            "With nothing selected, media/prompt lists are empty and paths contains the folder path. All outputs may stay unconnected.",
            "NSFW classification runs locally on images and video posters, not every video frame. Audio is not visually classified.",
        ]}],
    },

    RaySaveImage: {
        summary: "Saves one or both image inputs as PNGs, or just previews them, with a draggable left/right comparison when two images are connected.",
        sections: [{
            heading: "Notes",
            bullets: [
                "The folder button next to **Directory** opens your system's folder dialog and pastes the path. A blank directory saves to ComfyUI's output folder; the ▾ in the field recalls the last three save folders.",
                "The Save Image buttons choose None, 1, 2 or Both; saving happens when the workflow runs. None only previews.",
                "With two images connected, drag the ‹ › handle to compare them. The preview is otherwise click-through, so right-click, middle-drag and the wheel still reach the canvas.",
                "The picture fills the node: resize the node to enlarge it. Image sizes and the save status sit on the picture, and with several images the arrows at the bottom right step through the pairs.",
                "The **{ }** button next to **Filename prefix** opens a panel to build the name from tokens: `{date}`, `{time}`, `{counter}`, `{index}`, `{input}`, `{hash}` and `{widget:ID.NAME}` (the value of any widget in the workflow). The file is saved as exactly `<name>.png`.",
                "Spaces and characters a filename cannot hold are replaced with `_`, and nothing is ever overwritten: `{counter}` moves on to the next free number, otherwise `-2`, `-3`… is added.",
                "Leave `metadata` unconnected to keep ComfyUI's default embedded metadata. Connect a STRING to replace it with that exact text in PNG `parameters`, including empty text.",
                "Right-click → Save without metadata omits all embedded metadata, including connected custom text; ComfyUI's global metadata-disable option does too. Open image location in Explorer opens the last save folder (Windows host).",
                "Files are 8-bit PNGs at input resolution, alpha included.",
            ],
        }],
    },

    RayTextFolder: {
        summary: "Reads each UTF-8 `.txt` file in a folder as one complete prompt, in alphabetical order, and outputs a matching filename prefix for saving.",
        sections: [{
            heading: "Notes",
            bullets: [
                "The folder icon next to the folder field opens your system's folder dialog and fills in the path. You can still type or paste one.",
                "Connect `prompt` to the text encoder and `filename_prefix` to Save Image; lists are paired automatically. Keep image batch size at 1.",
                "`start_index` is zero-based; `limit` -1 reads all remaining files. Empty files count toward the range but are skipped.",
            ],
        }],
    },

    RayPromptFetcher: {
        summary: "One node for three prompt sources: a local image folder, PromptDexter or CivitAI. `scraper_mode` picks the source and only that source's widgets are shown.",
        sections: [{
            heading: "Notes",
            bullets: [
                "In Local Folder mode, the folder icon next to **Folder of images** opens your system's folder dialog and fills in the path.",
                "Widgets are prefixed by source: `local__`, `dexter__` and `civitai__`. Hidden widgets keep their values.",
                "Every mode produces the same four outputs; `image_path` is empty for the web sources.",
                "Local Folder mode reads A1111/Forge `parameters`, ComfyUI `prompt` / `workflow` graphs, other prompt-like PNG keys, EXIF comments and `<image>.txt` sidecars. When an image holds several prompts, each is emitted as a separate list entry.",
                "A seed of `-1` picks randomly and avoids recent repeats; any value ≥ 0 reproduces the same image or page every run.",
                "CivitAI can use an optional `civitai.secret` token file in the node pack folder for more content; without it only public images are reachable.",
                "In PromptDexter mode the refresh icon next to **Category** re-reads the sitemap; in CivitAI mode the one next to **Base model** clears the cache. A status line reports the result and notes when no `civitai.secret` is present.",
                "Local Folder mode returns positive prompts only; text encoders that feed only a sampler's negative input are skipped.",
            ],
        }],
    },

    RayMetaInspect: {
        summary: "Reads generation metadata (prompts, seed, steps, sampler, model, LoRAs, size) from an image file, or embeds supplied metadata into an image.",
        sections: [{
            heading: "Notes",
            bullets: [
                "The file icon next to **Image file** opens your system's file dialog, filtered to images. You can still paste a path.",
                "Inspect parses A1111 `parameters`, ComfyUI graphs, EXIF comments and sidecar text.",
                "Embed writes the connected image with `metadata_json` to `path`, then re-reads the file to verify it.",
                "In Inspect, connect a Load Image node to `image` and it reads that file's metadata (a connected image wins over `path`). Generated images have no file, so use `path` for those.",
            ],
        }],
    },
};
