import { app } from "../../scripts/app.js";
import { applyBucketTint } from "./_common.js";

const MODEL_FILE = /\.(safetensors|gguf|ckpt|pt|pth|bin|sft)$/i;

// Older workflows saved a `clip_name` dropdown (its value and an input slot) where the node now has a
// CLIP socket. Drop the saved model name so the other values stay in their widgets, and replace the old
// slot with the CLIP socket in place so link slot numbers do not shift. A link that fed the old dropdown
// cannot feed a CLIP socket, so it is removed; connect a CLIPLoader instead.
export function migrateClipInput(data) {
    const links = Array.isArray(data?.links) ? data.links : [];
    const read = (link, index, key) => Array.isArray(link) ? link[index] : link?.[key];
    for (const node of data?.nodes || []) {
        if (node?.type !== "RayVLMFolder") continue;
        if (Array.isArray(node.widgets_values) && typeof node.widgets_values[0] === "string"
            && MODEL_FILE.test(node.widgets_values[0])) {
            node.widgets_values.splice(0, 1);
        }
        const at = Array.isArray(node.inputs) ? node.inputs.findIndex(input => input?.name === "clip_name") : -1;
        if (at < 0) continue;
        const old = node.inputs[at];
        node.inputs[at] = { name: "clip", type: "CLIP", link: null };
        if (old?.link == null) continue;
        const link = links.find(l => read(l, 0, "id") === old.link);
        if (!link) continue;
        links.splice(links.indexOf(link), 1);
        const origin = read(link, 1, "origin_id");
        for (const source of data.nodes) {
            if (source.id !== origin) continue;
            for (const output of source.outputs || []) {
                if (Array.isArray(output.links)) output.links = output.links.filter(id => id !== old.link);
            }
        }
    }
    for (const subgraph of data?.definitions?.subgraphs || []) migrateClipInput(subgraph);
}

app.registerExtension({
    name: "Ray.VLMFolder",
    beforeConfigureGraph(data) { migrateClipInput(data); },
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
