import { app } from "../../scripts/app.js";
import { installPanel } from "./ray_panel.js";
import { IMAGE_FILTERS } from "./browse_common.js";

// The layout of every Ray node's panel (see ray_panel.js and UI.md). Nodes with their own interface code (the
// analog controls, Save Image, the Prompt Scraper) set up their panels themselves.

const value = (node, name) => node.widgets?.find(w => w.name === name)?.value;

export const PANEL_SPECS = {
    // ── VFX ────────────────────────────────────────────────────────────────
    RayCRT: { sections: [
        { fields: ["preset", "curvature"] },
        { title: "Strength", fields: ["intensity", { name: "scanline_strength", label: "Scanlines" }, { name: "mask_strength", label: "Mask" }] },
    ] },
    RayOffsetPrint: { sections: [
        { fields: ["preset", "intensity"] },
        { title: "Plates", fields: [{ name: "ink_strength", label: "Ink" }, { name: "screen_strength", label: "Screen" }, { name: "paper_strength", label: "Paper" }, { name: "scale", label: "Scale" }] },
        { title: "Paper", fields: [{ name: "paper_color", label: "Color", kind: "color" }, { name: "paper_color_mix", label: "Color mix" }] },
    ] },
    RayPixelArtDetector: { sections: [
        { fields: [
            { name: "input_kind", label: "Input", labels: { repair_pixel_art: "Repair pixel art", illustration_photo: "Illustration / photo" } },
            { name: "mode", labels: { manual_resize: "Target size", auto_pixel_size: "Detect grid", pixel_size: "Pixel size" } },
            { name: "target_resolution", label: "Target size" }, "pixel_size",
            { name: "sampling", labels: { grid_snap: "Grid snap", nearest: "Nearest", area: "Area" } },
            { name: "outline", labels: { none: "None", silhouette: "Silhouette", selective: "Selective" } },
        ] },
        { title: "Palette", fields: [
            { name: "reduce_palette", label: "Reduce palette" }, { name: "color_grid", label: "Color grid" },
            { name: "max_colors", label: "Colors" },
            { name: "palette_strategy", label: "Strategy", labels: { color_families: "Color families", kmeans_lab: "K-means Lab", quantize_simple: "Quantize", kmeans_rgb: "K-means RGB", oklab_source: "OKLab source", ramps_oklab: "OKLab ramps" } },
            { name: "palette_style", label: "Style", labels: { source: "Source", distinct: "Distinct" } },
            { name: "palette_allocation", label: "Allocation", labels: { area_preserving: "Area", frequency: "Frequency" } },
            { name: "palette_mapping", label: "Mapping", labels: { auto: "Auto", legacy_oklab: "Legacy OKLab", oklab: "OKLab", lab: "Lab", rgb: "RGB", color_families: "Color families" } },
            { name: "ramp_levels", label: "Ramp levels" },
            { name: "protect_highlights", label: "Protect highlights" }, { name: "highlight_threshold", label: "Highlight level" },
        ] },
        { title: "Dither", fields: [
            { name: "dither", labels: { none: "None", ordered: "Ordered", error_diffusion: "Diffusion" } },
            { name: "dither_strength", label: "Strength" },
        ] },
        { fields: ["seed"] },
    ] },
    RayFilmStock: { sections: [
        { fields: ["preset", "intensity", { name: "expose_stops", label: "Exposure" }] },
        { title: "Texture", fields: [{ name: "grain_amount", label: "Grain" }, { name: "halation_amount", label: "Halation" }, "seed"] },
        { title: "Look file", fields: [
            { name: "assets_folder", label: "LUT / XMP folder", browse: { kind: "folder", title: "Choose a folder of LUTs and XMP presets" }, placeholder: "Folder of .cube / .3dl / .xmp files" },
            { name: "asset_file", label: "File", kind: "select" },
        ] },
    ] },
    RayVHS: { sections: [
        { fields: ["preset", "effect_fade"] },
        { title: "Effects · -1 uses the preset", fields: ["chroma_blur", "head_switch", "tracking_jitter", "dropout_rate", "hiss", { name: "yc_separation", label: "Y/C separation" }] },
        { title: "On-screen display", fields: [
            { name: "osd_status", label: "Status" },
            { name: "osd_status_corner", label: "Status corner", when: n => value(n, "osd_status") !== "Off" },
            { name: "osd_stamp", label: "Stamp" },
            { name: "osd_stamp_corner", label: "Stamp corner", when: n => value(n, "osd_stamp") !== "Off" },
            { name: "osd_date", label: "Date", placeholder: "YYYY MM DD (blank = today)", when: n => ["Date", "Date+Time"].includes(value(n, "osd_stamp")) },
            { name: "osd_color", label: "Color", when: n => value(n, "osd_status") !== "Off" || value(n, "osd_stamp") !== "Off" },
        ] },
        { fields: ["seed"] },
    ] },

    // ── Tools ──────────────────────────────────────────────────────────────
    RayTextFolder: { sections: [
        { fields: [{ name: "directory", label: "Folder of .txt prompts", browse: { kind: "folder", title: "Choose a folder of .txt prompts" } }] },
        { fields: [{ name: "start_index", label: "Start at" }, { name: "limit", label: "Limit (-1 = all)" }, { name: "output_prefix", label: "Filename prefix" }] },
    ] },
    RayMetaInspect: { sections: [
        { fields: [
            "mode",
            { name: "path", label: "Image file", browse: { kind: "file", title: "Choose an image", filters: IMAGE_FILTERS }, placeholder: "Path to an image (or connect one)" },
            { name: "metadata_json", label: "Metadata to embed (JSON)", rows: 6 },
        ] },
    ] },

    // ── LLM ────────────────────────────────────────────────────────────────
    RayVLMFolder: { sections: [
        { fields: [
            { name: "folder", label: "Folder of images", browse: { kind: "folder", title: "Choose a folder of images" } },
            { name: "recurse_subfolders", label: "Include subfolders" },
            { name: "start_index", label: "Start at" }, { name: "limit", label: "Limit (-1 = all)" },
            { name: "user_prompt", label: "Prompt", rows: 4 },
        ] },
        { title: "Sampling", fields: [{ name: "max_length", label: "Max tokens" }, "temperature", { name: "top_k", label: "Top K" }, { name: "top_p", label: "Top P" }, { name: "min_p", label: "Min P" }, { name: "repetition_penalty", label: "Repeat penalty" }, "seed", "thinking"] },
    ] },
    RayFastQwen3VL: { sections: [
        { fields: [{ name: "prompt", rows: 5 }, { name: "max_tokens", label: "Max tokens" }] },
        { title: "Sampling", fields: ["temperature", { name: "top_p", label: "Top P" }, { name: "top_k", label: "Top K" }, "seed"] },
        { title: "Advanced", fields: ["mode", { name: "sync_interval", label: "Sync interval" }, "thinking", { name: "repetition_penalty", label: "Repeat penalty" }, { name: "presence_penalty", label: "Presence penalty" }, { name: "repeat_guard", label: "Repeat guard" }] },
    ] },
};

app.registerExtension({
    name: "Ray.Panels",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        const spec = PANEL_SPECS[nodeData.name];
        if (!spec) return;
        const created = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const result = created?.apply(this, arguments);
            // After the other extensions have set the node up (their hooks may add or hide widgets).
            if (typeof this.addDOMWidget === "function") queueMicrotask(() => installPanel(this, spec));
            return result;
        };
    },
});
