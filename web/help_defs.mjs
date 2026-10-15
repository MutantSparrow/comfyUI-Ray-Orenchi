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
        summary: "Repairs enlarged or damaged pixel art, or abstracts an illustration or photo into pixel art, keeping the exact source aspect ratio.",
        sections: [{
            heading: "Notes",
            bullets: [
                "Use `repair_pixel_art` for existing pixel grids and `illustration_photo` for region abstraction.",
                "`palette_strategy` builds the palette; `palette_mapping` assigns pixels to it. A connected `palette_image` overrides generated palettes (up to 256 exact colors).",
                "Dithering is limited to smooth ramps; flat fills, texture and strong edges are protected. Start with `none`.",
                "Exact aspect ratio can limit feasible sizes (for example 1001×667 cannot shrink exactly).",
            ],
        }],
    },

    RayFilmStock: {
        summary: "Emulates film stocks (Portra, HP5+, Cinestill, Velvia and more) with an analytical tone curve and color response, plus grain and halation. Optional LUT or XMP files can be layered on top.",
        sections: [{
            heading: "Notes",
            bullets: [
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
                "Right-click → Control Style picks from the 31 shared styles (nine knobs and five sliders are hand-drawn, the rest are generated to match); Compact mode hides unlinked setup widgets; Edit label… renames the tape label (or double-click it).",
                "Knobs, sliders and switches make hardware sounds, voiced to each style. Right-click → Mute sound turns them off for every analog control; the choice is remembered in this browser.",
                "Right-click → Mouse wheel control lets the scroll wheel drive the dial or slider while the pointer is over the node: 2% of the range per notch, a tenth of that with Shift. Ctrl + wheel still zooms. It is off by default and shared by every analog control.",
                "Style, compact mode and label are saved with the workflow.",
            ],
        }],
    },

    RayButtonDeck: {
        summary: "A bank of analog push buttons that replaces a dropdown. Each line you enter becomes a button, and the pressed button's text is the output.",
        sections: [{
            heading: "Notes",
            bullets: [
                "Click ✎ Edit entries… (or right-click → Edit entries…) and type one value per line. Apply with the button or Ctrl+Enter.",
                "The buttons form a near-square grid: 2 entries make 2×1, 3 or 4 make 2×2, 5 or 6 make 3×2, and so on. Exactly one button is pressed and lit.",
                "Arrow keys, Home and End move the selection. Blank and repeated lines are ignored, and the selection follows its value if you reorder the list.",
                "Right-click → Deck Style… picks from the 31 shared styles. Some print the text inside the button, others use a Dymo sticker below it; each has its own sound. Mute sound silences all analog controls.",
                "With Mouse wheel control on (right-click), scrolling over the node presses the next button (wheel down) or the previous one (wheel up), stopping at the ends.",
            ],
        }],
    },

    RayFaderBank: {
        summary: "A bank of 2 to 10 analog faders. Each fader is a vertical slider that outputs a float from 0 to 1.",
        sections: [{
            heading: "Notes",
            bullets: [
                "Set `faders` (2–10). The node shows one output per fader (`fader_1`…) and hides the rest; `values` is every active fader as a list, in order.",
                "Drag a fader, click its track to jump the cap there, or focus one and use Arrow keys (0.01, Shift for 0.001), PageUp/PageDown (0.1), Home and End. Shift slows a drag 20×.",
                "With Mouse wheel control on (right-click), scrolling over a fader moves just that one: 2% per notch, a tenth of that with Shift.",
                "Lowering `faders` removes the extra outputs and any links on them. A fader fed by a link is locked and says so.",
                "Right-click → Fader Style… picks from the 31 shared styles; Compact mode hides the `faders` widget; Edit label… renames the tape label; Mute sound silences all analog controls.",
            ],
        }],
    },

    RaySwitch: {
        summary: "An analog-style toggle switch that outputs a boolean.",
        sections: [{
            heading: "Notes",
            bullets: [
                "Click the face, or focus it and press Space/Enter.",
                "Right-click → Switch Style picks from the 31 shared styles (rockers, levers, sliders and keys are hand-drawn, the rest are generated to match); Compact mode hides setup widgets; Edit label… renames the tape label.",
                "Each face clicks, clacks or thunks like its hardware. Right-click → Mute sound silences all analog controls.",
                "With Mouse wheel control on (right-click), scrolling over the node switches it on (wheel up) or off (wheel down).",
            ],
        }],
    },

    // ── 💬 LLM ─────────────────────────────────────────────────────────
    RayVLMFolder: {
        summary: "Captions every image in a folder range with a local vision-language model on the GPU, returning aligned lists of captions, images and source paths.",
        sections: [{
            heading: "Notes",
            bullets: [
                "Connect a full generative VLM `CLIP` (such as Qwen3-VL from `CLIPLoader`, type `qwen_image`) to `clip`; text-only encoders cannot caption.",
                "Files are sorted by relative path. Use `start_index` and `limit` to process large folders in chunks; output images are held in RAM.",
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
                "See FAST_VLM.md for measurements and constraints.",
            ],
        }],
    },

    // ── 🔧 Tools ─────────────────────────────────────────────────────
    RaySaveImage: {
        summary: "Saves one or both image inputs as PNGs, or just previews them, with a draggable left/right comparison when two images are connected.",
        sections: [{
            heading: "Notes",
            bullets: [
                "The Save Image buttons choose None, 1, 2 or Both; saving happens when the workflow runs. None only previews.",
                "With two images connected, drag the ‹ › handle to compare them. The preview is otherwise click-through, so right-click, middle-drag and the wheel still reach the canvas.",
                "The picture fills the node: resize the node to enlarge it. Image sizes and the save status sit on the picture, and with several images the arrows at the bottom right step through the pairs.",
                "Browse… picks a folder on the ComfyUI host; the arrow recalls the last three save folders.",
                "Right-click → Save without metadata omits workflow data; Open image location in Explorer opens the last save folder (Windows host).",
                "Files are 8-bit PNGs at input resolution, alpha included, with unique names.",
            ],
        }],
    },

    RayTextFolder: {
        summary: "Reads each UTF-8 `.txt` file in a folder as one complete prompt, in alphabetical order, and outputs a matching filename prefix for saving.",
        sections: [{
            heading: "Notes",
            bullets: [
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
                "Widgets are prefixed by source: `local__`, `dexter__` and `civitai__`. Hidden widgets keep their values.",
                "Every mode produces the same four outputs; `image_path` is empty for the web sources.",
                "Local Folder mode reads A1111/Forge `parameters`, ComfyUI `prompt` / `workflow` graphs, other prompt-like PNG keys, EXIF comments and `<image>.txt` sidecars. When an image holds several prompts, each is emitted as a separate list entry.",
                "A seed of `-1` picks randomly and avoids recent repeats; any value ≥ 0 reproduces the same image or page every run.",
                "CivitAI can use an optional `civitai.secret` token file in the node pack folder for more content; without it only public images are reachable.",
                "PromptDexter mode has a **refresh sitemap** button and CivitAI mode a **clear cache** button; the status line under them also notes when no `civitai.secret` is present.",
                "Local Folder mode returns positive prompts only; text encoders that feed only a sampler's negative input are skipped.",
            ],
        }],
    },

    RayMetaInspect: {
        summary: "Reads generation metadata (prompts, seed, steps, sampler, model, LoRAs, size) from an image file, or embeds supplied metadata into an image.",
        sections: [{
            heading: "Notes",
            bullets: [
                "Inspect parses A1111 `parameters`, ComfyUI graphs, EXIF comments and sidecar text.",
                "Embed writes the connected image with `metadata_json` to `path`, then re-reads the file to verify it.",
                "In Inspect, connect a Load Image node to `image` and it reads that file's metadata (a connected image wins over `path`). Generated images have no file, so use `path` for those.",
            ],
        }],
    },
};
