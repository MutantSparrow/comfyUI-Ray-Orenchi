// ray_bucket_tints.js — auto-tint any Ray-Orenchi node that doesn't already
// have a dedicated JS extension. Keeps the fleet visually consistent without
// forcing a new JS file per plain VFX node.
//
// Nodes with their own JS already call applyBucketTint themselves; this
// extension only kicks in when a class name is registered in RAY_BUCKET and
// hasn't been touched yet.

import { app } from "../../scripts/app.js";
import { applyBucketTint } from "./_common.js";

const RAY_BUCKET = {
    // VFX
    RayCRT: "VFX",
    RayOffsetPrint: "VFX",
    RayPixelArtDetector: "VFX",
    RayFilmStock: "VFX",
    RayVHS: "VFX",
    // Analog is black by convention; the knob/switch JS already sets that.
    // Prompts
    RayLocalScraper: "Prompts",
    RayPromptDexter: "Prompts",
    RayCivitAI: "Prompts",
    RayPromptFetcher: "Prompts",
    RayMetaInspect: "Prompts",
    // LLM
    RayOllamaChat: "LLM",
    RayPromptIterator: "LLM",
    RayPromptLibrary: "LLM",
};

app.registerExtension({
    name: "Ray.BucketTints",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        const bucket = RAY_BUCKET[nodeData?.name];
        if (!bucket) return;
        const orig = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const r = orig?.apply(this, arguments);
            // If a dedicated extension has already set our marker, skip.
            if (!this._rayBucketTinted) {
                try {
                    applyBucketTint(this, bucket);
                    this._rayBucketTinted = true;
                } catch (e) { /* non-fatal */ }
            }
            return r;
        };
    },
});
