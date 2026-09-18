import { app } from "../../scripts/app.js";
import { applyBucketTint } from "./_common.js";

app.registerExtension({
    name: "Ray.TextFolder",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== "RayTextFolder") return;
        const onCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function (...args) {
            const result = onCreated?.apply(this, args);
            applyBucketTint(this, "Prompts");
            return result;
        };
        const onDraw = nodeType.prototype.onDrawBackground;
        nodeType.prototype.onDrawBackground = function (...args) {
            applyBucketTint(this, "Prompts");
            return onDraw?.apply(this, args);
        };
    },
});
