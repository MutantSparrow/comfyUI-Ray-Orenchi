// ray_local_scraper.js — inline preview + Prompts bucket tint.
//
// The Python side dispatches `ray-preview` with a filename/subfolder/type
// payload after every execute (folder scraper copies the chosen file into
// ComfyUI's temp dir so `/api/view` can serve it). The autowire helper
// picks that up and swaps the <img> src.

import { app } from "../../scripts/app.js";
import { applyBucketTint, autowireRayPreview } from "./_common.js";

const NODE_NAME = "RayLocalScraper";

function bootstrap(node) {
    applyBucketTint(node, "Prompts");
    autowireRayPreview(node, { height: 200, label: "folder scraper preview" });
}

app.registerExtension({
    name: "Ray.LocalScraper",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== NODE_NAME) return;
        const orig = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const r = orig?.apply(this, arguments);
            try { bootstrap(this); }
            catch (e) { console.error("[RayLocalScraper] bootstrap:", e); }
            return r;
        };
    },
});
