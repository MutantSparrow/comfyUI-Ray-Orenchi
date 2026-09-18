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
    RayVLMFolder: {
        title: "Ray's LLM: Folder Captioner",
        tagline: "Caption each image in a folder with a local vision-language model on GPU.",
        sections: [
            {
                heading: "Model and folder widgets",
                defs: [
                    ["`clip_name`", "Select a full generative vision-language checkpoint from ComfyUI's text_encoders model list, such as Qwen3-VL. Ordinary text-only CLIP encoders cannot caption images. The node loads the model once per run and keeps its image template enabled."],
                    ["`folder`", "Enter the source image folder. Files are sorted alphabetically by their path relative to this folder, not by modification time. The folder is scanned again on every run."],
                    ["`recurse_subfolders`", "Off: inspect only the chosen folder. On: also include images in nested folders, in the same relative-path ordering."],
                    ["`start_index`", "Zero-based position in the sorted image list. 0 starts at the first image; 10 skips the first ten. Applied before limit."],
                    ["`limit`", "Maximum number of images to caption after start_index. -1 means all remaining images. 0 or a range beyond the last image produces a no-images error. Use a small positive limit for a test."],
                    ["`user_prompt`", "Write the instruction sent independently with each image. Paragraphs are preserved. There is no conversation history between images. Use plain instructions; do not add manual chat-template or image-token markers."],
                ],
            },
            {
                heading: "Inference widgets",
                defs: [
                    ["`max_length`", "Maximum generated tokens per image, not characters or words. Default: 1024. The model can finish earlier; reaching this cap may truncate an answer. Thinking, when supported, can use part of this budget."],
                    ["`temperature`", "Controls sampling randomness. Lower positive values favor predictable answers; higher values allow more variation. Default: 0.25. Set 0 for greedy decoding, which chooses the most likely token instead of sampling."],
                    ["`top_k`", "Restricts sampling to the k most likely next tokens. Default: 40. Set 0 to disable this filter. Smaller values narrow the choices."],
                    ["`top_p`", "Restricts sampling to the smallest set of likely tokens whose combined probability reaches this threshold. Default: 0.9. Set 1 to keep the full probability range before other filters."],
                    ["`min_p`", "Drops tokens whose probability is below this fraction of the most likely token's probability. Default: 0.05. Set 0 to disable. Higher values exclude more unlikely choices."],
                    ["`repetition_penalty`", "Adjusts the scores of already generated tokens. Default: 1.05. 1 leaves scores unchanged; values above 1 discourage repetition, while values between 0 and 1 favor it. Excessive penalties can distort wording."],
                    ["`seed`", "-1 chooses a new random seed for each image. A value of 0 or greater reuses that seed for every image, helping repeat runs with the same model and settings. It does not reuse captions: each image is encoded separately. Greedy decoding does not sample from the seed."],
                    ["`thinking`", "Requests the model's thinking mode when supported. It does not add that capability to models without it. Decoded reasoning, if the model emits any, remains in the text output; it is not stripped."],
                ],
                body: "top_k, top_p and min_p apply together during sampling. At temperature 0, these sampling filters do not control greedy token selection.",
            },
            {
                heading: "Output sockets",
                defs: [
                    ["`text` · STRING list", "One decoded VLM answer per image, preserving its plain text and line breaks. This is the answer, not the input instruction. Connect it to a text display, a text saver, or a downstream prompt input."],
                    ["`image` · IMAGE list", "The source image examined for each answer, converted to RGB with EXIF orientation applied. Each file is a separate one-image tensor, so different image sizes are supported. Source resolution is preserved in this output. Connect it to Preview Image or other image nodes."],
                    ["`image_path` · STRING list", "The absolute source file path, including filename and extension, for each image. This is not a sidecar path or a generated output filename. Use it to identify the source or build a save path downstream."],
                ],
                body: "All three lists have the same length and ordering: text[0], image[0] and image_path[0] describe the same file. ComfyUI maps list entries into downstream nodes automatically. Outputs become available when the selected range completes, not as a live stream. Connect at least one output to an output/display node to execute this node. No sidecars or source files are written.",
            },
            {
                heading: "Formats, GPU and batch size",
                body: "Supported files: JPEG, PNG, WebP, BMP, TIFF and GIF. Animated or multipage files use their first frame. HEIC is not included.\n\nInference requires a GPU. ComfyUI may stage/offload weights in CPU memory, but the execution device stays on the GPU; CPU fallback causes an error. Unreadable images, missing image tokens or empty answers also stop the run.\n\nFull-resolution output images accumulate in RAM. For large folders, use a bounded limit and advance start_index. For example, start_index 0 and limit 20 examines the first 20 images; start_index 20 and limit 20 examines the next 20.",
            },
        ],
    },
    RayTextFolder: {
        title: "Ray's Prompts: TXT Folder",
        tagline: "One complete prompt and matching save prefix per text file.",
        sections: [
            { heading: "Connect", body: "Connect prompt to the sampler text input, filename_prefix to Save Image, and the sampler image to Save Image. Lists are paired automatically. Keep image batch size at 1." },
            { heading: "Range", body: "Files are alphabetical, without subfolders. start_index is zero-based; limit -1 reads all remaining files. Empty files count toward the range but are skipped." },
            { heading: "Text and saving", body: "UTF-8 text is passed through without rewriting or splitting paragraphs. output_prefix receives each source filename stem. Save Image adds its usual counter. Files refresh each run." },
            { heading: "Test", body: "Set limit to 3 for a small run, then -1 for the whole folder. If no non-empty files remain, execution stops with an error." },
        ],
    },

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
        tagline: "Repair a pixel grid or abstract an illustration while keeping its exact aspect ratio.",
        sections: [
            { heading: "Choose the source", body: "Use repair_pixel_art for enlarged or damaged pixel-like images. Use illustration_photo for local region abstraction. grid_snap enables that processing; nearest and area remain direct sampling alternatives." },
            { heading: "Size and preview", body: "image is the actual pixel-resolution result; preview is its nearest-neighbor enlargement to input dimensions. Exact aspect ratio can limit feasible sizes: 1001×667 cannot shrink exactly. In illustration mode, auto uses target_resolution." },
            { heading: "Palette", body: "For 8-color palettes, try color_families: preserve distinct hue/lightness groups and neutrals before buying extra shades, and retain hue identity during assignment. Highlights use spare slots. This is a color heuristic, not semantic recognition. Other choices are Lab, simple RGB buckets, RGB, OkLab source colors or chroma/lightness ramps. area_preserving favors broad coherent color areas over busy texture; frequency gives ordinary fitting. Highlight protection reserves neutral and warm bright colors within the budget. Threshold uses CIE Lab lightness, default 90. Supplied palettes remain exact up to 256 colors and override generated-palette controls." },
            { heading: "Dither", body: "Start with none. Ordered and error diffusion are restricted to coherent ramps where palette mixing improves lost tone. Flat fills, noisy texture and strong boundaries are protected. Increasing strength does not force dithering into protected regions." },
            { heading: "Outlines", body: "silhouette gives a dark inner contour; selective chooses colored outlines using nearby shading. Connect foreground_mask for complex backgrounds: 1 is subject, 0 is background. Invert Load Image alpha masks first. No outside halo is added." },
            { heading: "Artistic limits", body: "Readable forms and deliberate color clusters matter more than an indiscriminate effect stack. This node does not redesign characters or invent lighting. Inspect at native size; thin details and purposeful internal antialiasing are not automatically mistakes." },
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
