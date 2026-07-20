// help_defs.mjs — Ray's Orenchi rich help definitions.
//
// One entry per node class. Each entry is a helpDef consumed by help.mjs's
// openHelpPopup. See help.mjs for the shape.
//
// Keep entries terse but structured: `tagline` for the one-liner, a small
// number of sections (About / Key controls / Modes / Tips), inline `code`
// via backticks. When you add a new node, append its entry here and the
// selection-toolbar ? button lights up for free.

export const RAY_HELP_DEFS = {

    // ── ✨ VFX ─────────────────────────────────────────────────────────
    RayCRT: {
        title: "Ray's VFX: CRT",
        tagline: "Image-space CRT display effect with SOTA-inspired presets.",
        sections: [
            {
                heading: "About",
                body: "Simulates phosphor mask (aperture / shadow / slot), scanline beam, halation + bloom, NTSC chroma bleed, barrel curvature, vignette, and reflection gloss.",
            },
            {
                heading: "Presets",
                body: "Classic monitors: `trinitron_aperture`, `pvm_shadow`, `consumer_slot`, `composite_ntsc`, `royale_kurozumi`, `guest_advanced`, `hyllian_glow`.\n\nConsoles: `super_famicom`, `megadrive`, `ps1`, `ps2`, `nintendo_ds`, `gameboy_advance`, `psp`.",
            },
            {
                heading: "Master mix",
                defs: [
                    ["`intensity`", "Blends the CRT output back over the untouched input (0..1)."],
                    ["`scanline_strength`", "Scales the preset's scan-line depth (0..2)."],
                    ["`mask_strength`", "Scales the preset's phosphor-mask depth (0..2)."],
                    ["`curvature`", "Toggles the Lottes barrel warp (bezel = black)."],
                ],
            },
        ],
    },

    RayOffsetPrint: {
        title: "Ray's VFX: Offset Print",
        tagline: "CMYK / duotone halftone print simulation with paper substrate.",
        sections: [
            {
                heading: "About",
                body: "Per-plate halftone screens at SWOP angles, plate misregistration, dot gain, ink bleed, paper substrate (tint + grain + texture), optional sepia / vignette / posterize.",
            },
            {
                heading: "Presets",
                body: "`old_newspaper`, `modern_newspaper`, `comic_book`, `chromolithography`, `inkjet`, `pulp_magazine`, `risograph`, `silk_screen`, `xerox`, `glossy_magazine`.",
            },
            {
                heading: "Paper color",
                body: "`paper_color` is a hex substrate color (`#fffaf0` = ivory, `#ffffff` = pure). `paper_color_mix` blends it over the preset's own paper tint (0 = preset, 1 = full override).",
            },
        ],
    },

    RayPixelArtDetector: {
        title: "Ray's VFX: Pixel Art",
        tagline: "Pixel-art downscale + palette reduction with palette preview.",
        sections: [
            {
                heading: "About",
                body: "Downscales (manual target size or auto pixel-size detection), reduces palette (kmeans-Lab, kmeans-RGB, quantize, or OkLab hue-ramps), optional dithering, silhouette outline, and highlight protection.",
            },
            {
                heading: "Fixed palette",
                body: "Attach `palette_image` to force a fixed palette — snaps to {2}∪{4·k} colors and bypasses source clustering.",
            },
            {
                heading: "Dither kernels",
                bullets: [
                    "`bayer_2x2` / `bayer_4x4` / `bayer_8x8` — deterministic screen patterns.",
                    "`blue_noise` — perceptually smooth stochastic dither.",
                    "`riemersma` — Hilbert-curve error-diffusion.",
                    "`knoll` — pattern dither on kmeans centroids.",
                ],
            },
        ],
    },

    RayFilmStock: {
        title: "Ray's VFX: Film Stock",
        tagline: "Analytical film stock emulation, optional .cube LUT + XMP overlay.",
        sections: [
            {
                heading: "About",
                body: "Applies a per-stock tonal curve + color response (Kodak Portra 400, Ilford HP5+, Cinestill, Fujifilm Velvia, and more), plus optional grain and halation.",
            },
            {
                heading: "Assets folder",
                body: "Point `assets_folder` at a directory of `.cube` / `.3dl` LUTs and `.xmp` develop-setting files. The `asset_file` dropdown repopulates live and layers the chosen file on top of the analytical baseline.",
            },
            {
                heading: "Controls",
                defs: [
                    ["`intensity`", "Master mix vs untouched input."],
                    ["`grain_amount`", "Grain strength (0 = off)."],
                    ["`halation_amount`", "Halation bloom (0 = off)."],
                    ["`expose_stops`", "Exposure compensation in stops before the tonal curve."],
                ],
            },
        ],
    },

    RayVHS: {
        title: "Ray's VFX: VHS / Tape",
        tagline: "Analog videotape degradation modeled in YUV space with OSD overlay.",
        sections: [
            {
                heading: "About",
                body: "Simulates chroma blur, head-switching band, tracking wobble, dropouts, hiss, and Y/C separation. Each slider defaults to `-1.0` (use the preset value); `0..1` overrides that channel.",
            },
            {
                heading: "OSD",
                defs: [
                    ["`osd_mode`", "`Off` / `▶ PLAY` / `● REC` / `Date` / `Date+Time`."],
                    ["`osd_corner`", "`TL` / `TR` / `BL` / `BR`."],
                    ["`osd_date`", "`YYYY MM DD` — leave blank to stamp today's date."],
                ],
            },
        ],
    },

    // ── 🎛️ Analog ─────────────────────────────────────────────────────
    RayKnob: {
        title: "Ray's Analog: Knob",
        tagline: "Analog-style float knob. Drag rotates the face; emits INT and FLOAT.",
        sections: [
            {
                heading: "Outputs",
                body: "Both an INT (quantized by `clamp`) and a raw FLOAT are emitted, so you can plug the knob into either side without a converter.",
            },
            {
                heading: "Controls",
                defs: [
                    ["`min_value` / `max_value`", "Range endpoints."],
                    ["`spin_value`", "Drag sensitivity in px per full sweep."],
                    ["`clamp`", "Quantization step for the INT output. `0` truncates."],
                    ["`allow_negative`", "Lets `min_value` go below 0."],
                ],
            },
            {
                heading: "Right-click menu",
                bullets: [
                    "**Knob Style** — brushed-metal, black-plastic, bakelite, brass, and more.",
                    "**Compact mode** — strips everything except the brushed panel + Dymo + knob face + readout. Title bar, config widgets, and unwired pins are all hidden.",
                    "**Edit label…** — Dymo tape above the face (double-click also enters edit).",
                ],
            },
            { heading: "Persistence", body: "Style, compact flag, and label all serialize with the workflow." },
        ],
    },

    RaySwitch: {
        title: "Ray's Analog: Switch",
        tagline: "Analog-style boolean toggle with six physical styles.",
        sections: [
            {
                heading: "Physical styles",
                bullets: [
                    "`chrome_rocker` — press the LED end DOWN to turn ON.",
                    "`bakelite_flip` — bat-handle: UP = ON, DOWN = OFF.",
                    "`silver_paddle` — paddle slides TOWARD the lit label.",
                    "`brass_slider` — slider slides TOWARD the lit label.",
                    "`minimal_pill` — clean iOS-style toggle.",
                    "`dark_studio_dome` — dome-button with glow ring.",
                ],
            },
            {
                heading: "Right-click menu",
                bullets: [
                    "**Switch Style** — pick a style.",
                    "**Compact mode** — strips everything except the brushed panel + Dymo + switch face + readout. Title bar and unwired pins are hidden.",
                    "**Edit label…** — Dymo tape (double-click also enters edit).",
                ],
            },
        ],
    },

    // ── 💬 LLM ─────────────────────────────────────────────────────────
    RayOllamaChat: {
        title: "Ray's LLM: Ollama Chat",
        tagline: "Inline chat node with Ollama and CLIP text-encoder backends.",
        sections: [
            {
                heading: "Two backends",
                defs: [
                    ["`ollama`", "Talks to a local Ollama server. Supports image + audio attachments per turn."],
                    ["`clip`", "Drives the text encoder of a ComfyUI-loaded CLIP model directly, no external server. Vision-language CLIPs are rejected in this mode."],
                ],
            },
            {
                heading: "Attachments",
                body: "`attach_image` and `attach_audio` decide whether the wired IMAGE / AUDIO input rides with the next user turn. History and last message live on the node so workflows reload chats after restart.",
            },
            {
                heading: "Sampling",
                bullets: [
                    "`temperature` — 0..2.",
                    "`seed` — `-1` for random.",
                    "`think` — toggles Ollama's thinking-mode where supported.",
                    "CLIP mode: `max_new_tokens`, `top_p`, `repetition_penalty`.",
                ],
            },
        ],
    },

    RayPromptIterator: {
        title: "Ray's LLM: Prompt Iterator",
        tagline: "Image-prompt judge + rewriter via Ollama.",
        sections: [
            {
                heading: "About",
                body: "Given the original prompt and (optionally) the rendered image, returns a `confidence` score `[0,1]` for how well the image matches the prompt, and a `new_prompt` aimed at closing the gap.",
            },
            {
                heading: "Loop",
                body: "Wire `new_prompt` back into your CLIP text encoder to iterate. `copy_to_clipboard` also mirrors the revised prompt to the OS clipboard on execute.",
            },
            { heading: "System prompt", body: "Loaded from `iterator_sysprompt.txt` next to the node code — edit that file to customize the judge." },
        ],
    },

    RayPromptLibrary: {
        title: "Ray's LLM: Prompt Library",
        tagline: "Local SQLite prompt library. Save + Browse in one node.",
        sections: [
            {
                heading: "Modes",
                defs: [
                    ["`Save`", "Writes `prompt_in` to the DB with source, tags, image path, and model."],
                    ["`Browse`", "Inline searchable table; pick a row and its prompt + image path flow onto the outputs."],
                ],
            },
            {
                heading: "Browse panel",
                body: "Full-text search, tag + source filters, and multiple sort orders (most recent, longest, similarity by embedding). Click a row to select — the node then serves that row on every subsequent run.",
            },
        ],
    },

    // ── 📝 Prompts ─────────────────────────────────────────────────────
    RayPromptDexter: {
        title: "Ray's Prompts: PromptDexter Scraper",
        tagline: "Random prompt + image from promptdexter.com. Seed-deterministic.",
        sections: [
            {
                heading: "Discovery",
                body: "Sitemap-driven — picks reach deep content, not just the homepage top row. The `🔄 refresh sitemap` button re-fetches the category list live.",
            },
            {
                heading: "Seed",
                body: "`seed = -1` picks a fresh OS-random URL each run. Any `>= 0` value is reproducible: the same seed on the same node returns the same URL every time.",
            },
        ],
    },

    RayCivitAI: {
        title: "Ray's Prompts: CivitAI Gallery Scraper",
        tagline: "Random prompt + gallery image from civitai.com via the REST API.",
        sections: [
            {
                heading: "Content level",
                body: "Blue (SFW) = browsingLevel `PG | PG13`. Red = all levels OR'd together. The node hue-shifts its tint to match the mode.",
            },
            {
                heading: "Filters",
                bullets: [
                    "`base_model` — restrict picks to one architecture.",
                    "`period` — time window for metric-based sorts.",
                    "`sort` — `Random` / `Most Reactions` / `Most Comments` / `Newest`.",
                    "`username` — restrict to one uploader. Forces `period=AllTime`.",
                ],
            },
            {
                heading: "Only usable items",
                body: "Only items with an extractable prompt are kept — either `meta.prompt` directly, or text salvaged from a ComfyUI workflow blob in `meta.comfy`.",
            },
            {
                heading: "API token",
                body: "Higher-tier content unlocks if a `civitai.secret` token file is present next to the node code. Gitignored.",
            },
        ],
    },

    RayLocalScraper: {
        title: "Ray's Prompts: Folder Image Scraper",
        tagline: "Random image + extracted prompt from a local folder.",
        sections: [
            {
                heading: "Prompt sources",
                bullets: [
                    "PNG `parameters` — A1111 / Forge (JSON blob variants also parsed).",
                    "PNG `prompt` — ComfyUI graph (walking wired ShowText / Text Multiline / String Literal chains up to 8 hops).",
                    "PNG `workflow` — API or UI (nodes/links) format.",
                    "Info keys — `caption` / `description` / `comment` / `sui_image_params` / `invokeai_metadata` / `novelai_metadata` / `dream`.",
                    "EXIF — UserComment, ImageDescription, XPComment, XPSubject, XPTitle, XPKeywords.",
                    "`<image>.txt` sidecar.",
                ],
            },
            {
                heading: "Best-try mode",
                body: "`prompt_best_try` collapses each image to its single best (longest) prompt AND skips a pick when the best-try text matches the last one emitted from this node. Advances until a new prompt is found or the pool runs out.",
            },
            {
                heading: "Seed",
                body: "`seed = -1` is OS-random. Any `>= 0` value is reproducible: same seed, same pick every run.",
            },
        ],
    },

    RayPromptFetcher: {
        title: "Ray's Prompts: Prompt Fetcher",
        tagline: "One node, three prompt sources.",
        sections: [
            {
                heading: "Modes",
                defs: [
                    ["`Local Folder`", "Wraps RayLocalScraper — random image + extracted prompt from disk."],
                    ["`PromptDexter`", "Wraps RayPromptDexter — random prompt + image scraped from promptdexter.com."],
                    ["`CivitAI`", "Wraps RayCivitAI — random prompt + gallery image via CivitAI's REST API."],
                ],
            },
            {
                heading: "Output shape",
                body: "Outputs are harmonized to `(prompt_single, prompt_multiline, image, image_path)` so any mode is drop-in compatible with downstream wiring. `image_path` is empty for web modes.",
            },
            { heading: "Widget partitioning", body: "The frontend hides widgets that don't belong to the active mode, keyed off the `local__` / `dexter__` / `civitai__` name prefix." },
        ],
    },

    RayMetaInspect: {
        title: "Ray's Prompts: Metadata Inspector",
        tagline: "Read or write image generation metadata.",
        sections: [
            {
                heading: "Modes",
                defs: [
                    ["`Inspect`", "Parses every known chunk (A1111 `parameters`, ComfyUI `prompt` / `workflow` graph, EXIF UserComment, sidecar text) and exposes prompt_positive, prompt_negative, seed, steps, cfg, sampler, model, LoRAs, dimensions, and the raw JSON blob."],
                    ["`Embed`", "Writes an IMAGE tensor + `metadata_json` dict back to disk at `path`, then re-parses the file for round-trip verification."],
                ],
            },
            { heading: "Drop zone", body: "Drag an image into the inline drop-zone to prefill `path` and preview it in-node." },
        ],
    },
};
