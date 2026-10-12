import { app } from "../../scripts/app.js";
import {
    applyBucketTint,
    shiftTint,
    RAY_PALETTE,
    setWidgetHidden as commonSetHidden,
    findWidget as getWidget,
} from "./_common.js";

const NODE_NAME = "RayPromptFetcher";

const MODE_LOCAL = "Local Folder";
const MODE_DEXTER = "PromptDexter";
const MODE_CIVITAI = "CivitAI";

// Mode → widget-name prefix that should remain visible.
const MODE_PREFIX = {
    [MODE_LOCAL]: "local__",
    [MODE_DEXTER]: "dexter__",
    [MODE_CIVITAI]: "civitai__",
};

function applyMode(node, mode) {
    const keep = MODE_PREFIX[mode] || MODE_PREFIX[MODE_LOCAL];
    const prefixes = Object.values(MODE_PREFIX);
    for (const w of node.widgets || []) {
        // Only hide widgets owned by another mode. Shared widgets
        // (scraper_mode, seed, and the frontend's control_after_generate)
        // stay visible.
        const owned = prefixes.some((p) => w.name?.startsWith(p));
        commonSetHidden(node, w, owned && !w.name.startsWith(keep));
    }
    applyModeStyling(node, mode);
    if (typeof node.computeSize === "function") {
        const sz = node.computeSize();
        if (Array.isArray(node.size)) node.size[1] = sz[1];
        node.setSize?.([Array.isArray(node.size) ? node.size[0] : sz[0], sz[1]]);
    }
    node.setDirtyCanvas?.(true, true);
}

function applyModeStyling(node, mode) {
    // Tools bucket base tint, hue-shifted per mode.
    applyBucketTint(node, "Tools");
    if (mode === MODE_DEXTER) {
        node.bgcolor = shiftTint(RAY_PALETTE.Tools.bg, 90);
        node.color = shiftTint(RAY_PALETTE.Tools.edge, 90);
    } else if (mode === MODE_CIVITAI) {
        node.bgcolor = shiftTint(RAY_PALETTE.Tools.bg, -90);
        node.color = shiftTint(RAY_PALETTE.Tools.edge, -90);
    }
    // MODE_LOCAL keeps the canonical Tools tint.
}

// PromptDexter category list arrives async via /ray_promptdexter/categories.
async function fetchDexterCategories() {
    try {
        const r = await fetch("/ray_promptdexter/categories");
        const j = await r.json();
        return {
            categories: Array.isArray(j.categories) ? j.categories : [],
            any: j.any || "(any)",
        };
    } catch {
        return { categories: [], any: "(any)" };
    }
}

function updateDexterCategoryWidget(node, list, anyLabel) {
    const w = getWidget(node, "dexter__category");
    if (!w) return;
    const merged = [anyLabel, ...list.filter((c) => c && c !== anyLabel)];
    // Replace the whole options object so Vue's reactivity tracker notices.
    w.options = { ...(w.options || {}), values: merged };
    if (!merged.includes(w.value)) w.value = anyLabel;
    node.setDirtyCanvas?.(true, true);
}

async function bootstrap(node) {
    const modeW = getWidget(node, "scraper_mode");
    if (!modeW) return;

    // Populate Dexter categories asynchronously — same source the dedicated
    // node uses. INPUT_TYPES already seeded the dropdown, but the live list
    // can be richer than what was cached at registration.
    fetchDexterCategories().then(({ categories, any }) => {
        updateDexterCategoryWidget(node, categories, any);
    });

    applyMode(node, modeW.value);

    const orig = modeW.callback;
    modeW.callback = function (v) {
        const r = orig?.apply(this, arguments);
        applyMode(node, v);
        return r;
    };
}

app.registerExtension({
    name: "Ray.PromptFetcher",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== NODE_NAME) return;
        const orig = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const r = orig?.apply(this, arguments);
            try {
                bootstrap(this);
            } catch (e) {
                console.error("[RayPromptFetcher] bootstrap error:", e);
            }
            return r;
        };

        // After deserializing a saved workflow, widgets are restored but our
        // visibility state isn't — re-apply.
        const origConfigure = nodeType.prototype.onConfigure;
        nodeType.prototype.onConfigure = function () {
            const r = origConfigure?.apply(this, arguments);
            try {
                const modeW = getWidget(this, "scraper_mode");
                if (modeW) applyMode(this, modeW.value);
            } catch (e) {
                console.error("[RayPromptFetcher] onConfigure error:", e);
            }
            return r;
        };
    },
});
