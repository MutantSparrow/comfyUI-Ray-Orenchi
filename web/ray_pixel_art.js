import { app } from "../../scripts/app.js";
import { applyBucketTint, setWidgetHidden } from "./_common.js";

function refresh(node) {
    const widget = (name) => node.widgets?.find((w) => w.name === name);
    const value = (name) => widget(name)?.value;
    const show = (name, visible) => {
        const w = widget(name);
        if (w && Boolean(w.hidden) !== !visible) setWidgetHidden(node, w, !visible);
    };
    const paletteConnected = node.inputs?.some((i) => i.name === "palette_image" && i.link != null);
    const grid = Boolean(value("color_grid"));
    show("pixel_size", value("mode") === "pixel_size");
    show("target_resolution", value("mode") !== "pixel_size");
    show("max_colors", value("reduce_palette") || paletteConnected || grid);
    const families = value("palette_strategy") === "color_families" && !grid;
    const generated = (value("reduce_palette") && !paletteConnected) || grid;
    show("palette_style", generated && !families);
    show("palette_strategy", generated);
    show("palette_allocation", generated && !families);
    show("protect_highlights", generated);
    show("highlight_threshold", generated && value("protect_highlights"));
    show("ramp_levels", generated && (value("palette_strategy") === "ramps_oklab" || grid));
    show("dither", value("reduce_palette") || paletteConnected || grid);
    show("dither_strength", (value("reduce_palette") || paletteConnected || grid) && value("dither") !== "none");
}

app.registerExtension({
    name: "Ray.PixelArt",
    beforeConfigureGraph(graph) {
        for (const node of graph.nodes || []) {
            if (node.type !== "RayPixelArtDetector") continue;
            let v = node.widgets_values;
            if (!Array.isArray(v)) continue;
            let restored = ["kmeans_lab", true, 90, 4, "area_preserving"];
            if (v.length >= 15 && !["repair_pixel_art", "illustration_photo"].includes(v[0])) {
                const mode = v[0] === "manual_resize" ? "manual_resize" : "auto_pixel_size";
                const dither = v[9] === "none" ? "none" : v[9] === "riemersma" ? "error_diffusion" : "ordered";
                const old = v;
                restored = [["kmeans_lab", "kmeans_rgb", "ramps_oklab", "quantize_simple"].includes(old[5]) ? old[5] : "kmeans_lab", old[7], old[8], old[6], "area_preserving"];
                v = [mode, old[1], 8, "grid_snap", old[3], old[4], dither,
                     .7, old[12] ? "silhouette" : "none", old[14]];
                if (old.length > 15) v.push(old[15]);
            }
            // The first revision had ten controls; retain them by name/order.
            if (["manual_resize", "auto_pixel_size", "pixel_size"].includes(v[0])) {
                v = ["repair_pixel_art", ...v.slice(0, 6), "source", ...v.slice(6)];
            }
            // Revision 2 had 12 controls plus an optional seed behavior widget.
            // Insert the restored controls before seed, retaining its behavior.
            if (["repair_pixel_art", "illustration_photo"].includes(v[0]) && v.length <= 13) {
                v = [...v.slice(0, 11), ...restored, ...v.slice(11)];
            }
            // Previous schema had numeric ramp_levels immediately after threshold.
            if (["repair_pixel_art", "illustration_photo"].includes(v[0]) && typeof v[14] === "number") {
                v = [...v.slice(0, 14), false, ...v.slice(14)];
            }
            node.widgets_values = v;
            if (node.outputs?.[0]) node.outputs[0].name = "image";
            if (node.outputs?.[1]) node.outputs[1].name = "preview";
        }
    },
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== "RayPixelArtDetector") return;
        const created = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const result = created?.apply(this, arguments);
            applyBucketTint(this, "VFX");
            for (const w of this.widgets || []) {
                if (w.name === "color_grid") w.label = "color grid";
                if (!["mode", "reduce_palette", "dither", "palette_strategy", "protect_highlights", "color_grid"].includes(w.name)) continue;
                const callback = w.callback;
                w.callback = (...args) => {
                    const r = callback?.apply(w, args);
                    refresh(this);
                    return r;
                };
            }
            refresh(this);
            return result;
        };
        for (const hook of ["onConfigure", "onConnectionsChange"]) {
            const original = nodeType.prototype[hook];
            nodeType.prototype[hook] = function () {
                const result = original?.apply(this, arguments);
                refresh(this);
                return result;
            };
        }
        const draw = nodeType.prototype.onDrawBackground;
        nodeType.prototype.onDrawBackground = function () {
            applyBucketTint(this, "VFX");
            return draw?.apply(this, arguments);
        };
    },
});
