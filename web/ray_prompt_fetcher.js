import { app } from "../../scripts/app.js";

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

function getWidget(node, name) {
    return node.widgets?.find((w) => w.name === name);
}

function setWidgetHidden(widget, hidden) {
    if (!widget) return;
    if (hidden) {
        if (widget.__rfOrigType === undefined) {
            widget.__rfOrigType = widget.type;
            widget.__rfOrigComputeSize = widget.computeSize;
        }
        widget.type = "hidden";
        widget.computeSize = () => [0, -4];
        widget.hidden = true;
    } else {
        if (widget.__rfOrigType !== undefined) {
            widget.type = widget.__rfOrigType;
            widget.computeSize = widget.__rfOrigComputeSize;
            widget.__rfOrigType = undefined;
            widget.__rfOrigComputeSize = undefined;
        }
        widget.hidden = false;
    }
}

function applyMode(node, mode) {
    const keep = MODE_PREFIX[mode] || MODE_PREFIX[MODE_LOCAL];
    for (const w of node.widgets || []) {
        if (ALWAYS_VISIBLE.has(w.name)) {
            setWidgetHidden(w, false);
            continue;
        }
        const hide = !w.name?.startsWith(keep);
        setWidgetHidden(w, hide);
    }
    applyModeStyling(node, mode);
    // Snap height. node.setSize is the v2-friendly path; node.size[1] is the
    // LiteGraph mutation path — set both so we cover frontends.
    if (typeof node.computeSize === "function") {
        const sz = node.computeSize();
        if (Array.isArray(node.size)) node.size[1] = sz[1];
        node.setSize?.([Array.isArray(node.size) ? node.size[0] : sz[0], sz[1]]);
    }
    node.setDirtyCanvas?.(true, true);
}

function applyModeStyling(node, mode) {
    let bg = "#2a2a3a";
    let edge = "#5a5a7a";
    if (mode === MODE_LOCAL) {
        bg = "#1f3a2a"; edge = "#3aa867";
    } else if (mode === MODE_DEXTER) {
        bg = "#1f2a4a"; edge = "#3a73c8";
    } else if (mode === MODE_CIVITAI) {
        bg = "#3a1f4a"; edge = "#a83aa8";
    }
    node.bgcolor = bg;
    node.color = edge;
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
    w.options = w.options || {};
    w.options.values = merged;
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
