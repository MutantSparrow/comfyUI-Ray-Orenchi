import { app } from "../../scripts/app.js";
import {
    applyBucketTint,
    findWidget as getWidget,
    autowireRayPreview,
} from "./_common.js";

const NODE_NAME = "RayPromptDexter";

async function fetchCategories(force = false) {
    const url = `/ray_promptdexter/categories${force ? "?force=1" : ""}`;
    try {
        const r = await fetch(url);
        const j = await r.json();
        return {
            categories: Array.isArray(j.categories) ? j.categories : [],
            any: j.any || "(any)",
            error: j.error || null,
        };
    } catch (e) {
        return { categories: [], any: "(any)", error: String(e) };
    }
}

async function postRefresh() {
    try {
        const r = await fetch("/ray_promptdexter/refresh", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({}),
        });
        return await r.json();
    } catch (e) {
        return { ok: false, error: String(e) };
    }
}

function updateCategoryWidget(node, list, anyLabel) {
    const w = getWidget(node, "category");
    if (!w) return;
    const merged = [anyLabel, ...list.filter((c) => c && c !== anyLabel)];
    // Replace the whole options object so Vue's reactivity tracker notices
    // the new array reference. LiteGraph reads .values per-draw, unaffected.
    w.options = { ...(w.options || {}), values: merged };
    if (!merged.includes(w.value)) {
        w.value = anyLabel;
    }
    node.setDirtyCanvas?.(true, true);
}

function injectRefreshButton(node, statusEl) {
    if (node._rayRefreshBtnAdded) return;
    node._rayRefreshBtnAdded = true;
    const btn = node.addWidget(
        "button",
        "🔄 refresh sitemap",
        null,
        async () => {
            const w = getWidget(node, "category");
            const prev = w?.value;
            statusEl.textContent = "refreshing…";
            const res = await postRefresh();
            if (res.ok) {
                updateCategoryWidget(node, res.categories || [], res.any || "(any)");
                if (prev && (res.categories || []).includes(prev)) {
                    const cw = getWidget(node, "category");
                    if (cw) cw.value = prev;
                }
                statusEl.textContent = `ok — ${res.prompt_url_count || 0} prompts, ${(res.categories || []).length} categories`;
                setTimeout(() => { if (statusEl.textContent.startsWith("ok")) statusEl.textContent = ""; }, 3000);
            } else {
                statusEl.textContent = `refresh failed: ${res.error || "unknown"}`;
            }
            node.setDirtyCanvas?.(true, true);
        },
        { serialize: false },
    );
    if (btn) btn.serialize = false;
}

function injectStatusWidget(node) {
    if (node._rayStatusEl) return node._rayStatusEl;
    const el = document.createElement("div");
    el.style.cssText = "padding:2px 6px;font-size:10px;color:#aaa;min-height:14px;";
    el.textContent = "";
    if (typeof node.addDOMWidget === "function") {
        node.addDOMWidget("pd_status", "RAY_PD_STATUS", el, {
            serialize: false,
            hideOnZoom: false,
            getMinHeight: () => 18,
            getHeight: () => 18,
        });
    }
    node._rayStatusEl = el;
    return el;
}

async function bootstrap(node) {
    applyBucketTint(node, "Prompts");
    const statusEl = injectStatusWidget(node);
    injectRefreshButton(node, statusEl);
    autowireRayPreview(node, { height: 200, label: "promptdexter preview" });

    statusEl.textContent = "loading categories…";
    const res = await fetchCategories(false);
    if (res.error) {
        statusEl.textContent = `categories: ${res.error}`;
    } else {
        statusEl.textContent = "";
    }
    updateCategoryWidget(node, res.categories, res.any);
}

app.registerExtension({
    name: "Ray.PromptDexter",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== NODE_NAME) return;
        const orig = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const r = orig?.apply(this, arguments);
            try {
                bootstrap(this);
            } catch (e) {
                console.error("[RayPromptDexter] bootstrap error:", e);
            }
            return r;
        };
    },
});
