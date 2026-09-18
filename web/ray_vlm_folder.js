import { app } from "../../scripts/app.js";
import { applyBucketTint } from "./_common.js";

app.registerExtension({
    name: "Ray.VLMFolder",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== "RayVLMFolder") return;
        const onCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function (...args) {
            const result = onCreated?.apply(this, args);
            applyBucketTint(this, "LLM");
            return result;
        };
        const onDraw = nodeType.prototype.onDrawBackground;
        nodeType.prototype.onDrawBackground = function (...args) {
            applyBucketTint(this, "LLM");
            return onDraw?.apply(this, args);
        };
    },
});
