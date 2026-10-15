// ray_bucket_tints.js — auto-tint any Ray-Orenchi node that doesn't already
// have a dedicated JS extension. Keeps the fleet visually consistent without
// forcing a new JS file per plain VFX node.
//
// Nodes with their own JS already call applyBucketTint themselves; this
// extension only kicks in when a class name is registered in RAY_BUCKET and
// hasn't been touched yet.

import { app } from "../../scripts/app.js";
import { applyBucketTint, isLegacyBodyColor } from "./_common.js";

const RAY_BUCKET = {
    // VFX
    RayCRT: "VFX",
    RayOffsetPrint: "VFX",
    RayPixelArtDetector: "VFX",
    RayFilmStock: "VFX",
    RayVHS: "VFX",
    // Analog is black by convention; the knob/switch JS already sets that.
    // Tools
    RayPromptFetcher: "Tools",
    RayMetaInspect: "Tools",
    // LLM
};

app.registerExtension({
    name: "Ray.BucketTints",
    // Workflows saved before the black-body palette restore a tinted body over
    // the new one. Blacken those; keep the saved title color and any body the
    // user colored by hand.
    loadedGraphNode(node) {
        if (node?.comfyClass?.startsWith("Ray") && isLegacyBodyColor(node.bgcolor)) {
            node.bgcolor = "#000000";
        }
    },
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
