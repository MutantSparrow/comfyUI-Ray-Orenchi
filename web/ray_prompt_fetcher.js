import { app } from "../../scripts/app.js";
import {
    applyBucketTint,
    shiftTint,
    RAY_PALETTE,
    setWidgetHidden as commonSetHidden,
    findWidget as getWidget,
    autowireRayPreview,
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

// Widgets that always stay visible regardless of mode.
const ALWAYS_VISIBLE = new Set(["scraper_mode", "seed"]);

function applyMode(node, mode) {
    const keep = MODE_PREFIX[mode] || MODE_PREFIX[MODE_LOCAL];
    for (const w of node.widgets || []) {
        if (ALWAYS_VISIBLE.has(w.name)) {
            commonSetHidden(node, w, false);
            continue;
        }
        // Never hide our own DOM widgets (preview, status).
        if (w.type === "RAY_PREVIEW") { continue; }
        const hide = !w.name?.startsWith(keep);
        commonSetHidden(node, w, hide);
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
    // Prompts bucket base tint, hue-shifted per mode.
    applyBucketTint(node, "Prompts");
    if (mode === MODE_DEXTER) {
        node.bgcolor = shiftTint(RAY_PALETTE.Prompts.bg, 90);
        node.color = shiftTint(RAY_PALETTE.Prompts.edge, 90);
    } else if (mode === MODE_CIVITAI) {
        node.bgcolor = shiftTint(RAY_PALETTE.Prompts.bg, -90);
        node.color = shiftTint(RAY_PALETTE.Prompts.edge, -90);
    }
    // MODE_LOCAL keeps the canonical Prompts tint.
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

    autowireRayPreview(node, { height: 200, label: "fetcher preview" });

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
