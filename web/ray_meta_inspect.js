import { app } from "../../scripts/app.js";
import {
    applyBucketTint,
    setWidgetHidden as commonSetHidden,
    findWidget as getWidget,
} from "./_common.js";

const NODE_NAME = "RayMetaInspect";

const MODE_INSPECT = "Inspect";
const MODE_EMBED = "Embed";

// Widgets visible per mode. The `path` widget is shared.
const MODE_VISIBLE = {
    [MODE_INSPECT]: new Set(["mode", "path"]),
    [MODE_EMBED]: new Set(["mode", "path", "metadata_json"]),
};

function setWidgetHidden(widget, hidden) {
    commonSetHidden(null, widget, hidden);
}

function applyMode(node, mode) {
    const keep = MODE_VISIBLE[mode] || MODE_VISIBLE[MODE_INSPECT];
    for (const w of node.widgets || []) setWidgetHidden(w, !keep.has(w.ownerName || w.name));
    if (typeof node.computeSize === "function") {
        const sz = node.computeSize();
        if (Array.isArray(node.size)) node.size[1] = sz[1];
        node.setSize?.([Array.isArray(node.size) ? node.size[0] : sz[0], sz[1]]);
    }
    node.setDirtyCanvas?.(true, true);
}

// A copied path may arrive wrapped in quotes (Explorer's "Copy as path" adds them).
const QUOTE_PAIRS = [
    ['"', '"'], ["'", "'"], ["«", "»"], ["“", "”"], ["‘", "’"], ["`", "`"],
];

export function stripQuotes(s) {
    if (!s) return s;
    const t = s.trim();
    for (const [o, c] of QUOTE_PAIRS) {
        if (t.length >= 2 && t.startsWith(o) && t.endsWith(c)) {
            return t.slice(1, -1).trim();
        }
    }
    return t;
}

function wirePathStripper(node) {
    const pathW = getWidget(node, "path");
    if (!pathW) return;
    const orig = pathW.callback;
    pathW.callback = function (v) {
        const cleaned = stripQuotes(v);
        if (cleaned !== v) pathW.value = cleaned;
        return orig?.apply(this, [cleaned]);
    };
}

function bootstrap(node) {
    applyBucketTint(node, "Tools");
    wirePathStripper(node);
    const modeW = getWidget(node, "mode");
    if (!modeW) return;
    applyMode(node, modeW.value);
    const orig = modeW.callback;
    modeW.callback = function (v) {
        const r = orig?.apply(this, arguments);
        applyMode(node, v);
        return r;
    };
}

app.registerExtension({
    name: "Ray.MetaInspect",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== NODE_NAME) return;
        const orig = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const r = orig?.apply(this, arguments);
            try {
                bootstrap(this);
            } catch (e) {
                console.error("[RayMetaInspect] bootstrap error:", e);
            }
            return r;
        };
        const origConf = nodeType.prototype.onConfigure;
        nodeType.prototype.onConfigure = function () {
            const r = origConf?.apply(this, arguments);
            try {
                const modeW = getWidget(this, "mode");
                if (modeW) applyMode(this, modeW.value);
            } catch (e) {
                console.error("[RayMetaInspect] onConfigure error:", e);
            }
            return r;
        };
    },
});
