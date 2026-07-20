// ray_local_scraper.js — Prompts bucket tint.

import { app } from "../../scripts/app.js";
import { applyBucketTint } from "./_common.js";

const NODE_NAME = "RayLocalScraper";

function bootstrap(node) {
    applyBucketTint(node, "Prompts");
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
