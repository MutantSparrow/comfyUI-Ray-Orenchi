import { app } from "../../scripts/app.js";
import {
    applyBucketTint,
    shiftTint,
    RAY_PALETTE,
    findWidget as getWidget,
    autowireRayPreview,
} from "./_common.js";

const NODE_NAME = "RayCivitAI";

async function postRefresh() {
    try {
        const r = await fetch("/ray_civitai/refresh", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({}),
        });
        return await r.json();
    } catch (e) {
        return { ok: false, error: String(e) };
    }
}

async function fetchOptions() {
    try {
        const r = await fetch("/ray_civitai/base_models");
        return await r.json();
    } catch {
        return null;
    }
}

function applyModeStyling(node, mode) {
    // Prompts bucket base tint; Red mode hue-shifts toward violet/red.
    applyBucketTint(node, "Prompts");
    if (mode && mode.toLowerCase().startsWith("red")) {
        node.bgcolor = shiftTint(RAY_PALETTE.Prompts.bg, -110);
        node.color = shiftTint(RAY_PALETTE.Prompts.edge, -110);
    }
    node.setDirtyCanvas?.(true, true);
}

function injectStatusWidget(node) {
    if (node._rayCivitStatusEl) return node._rayCivitStatusEl;
    const el = document.createElement("div");
    el.style.cssText = "padding:2px 6px;font-size:10px;color:#aaa;min-height:14px;";
    el.textContent = "";
    if (typeof node.addDOMWidget === "function") {
        node.addDOMWidget("civit_status", "RAY_CIVIT_STATUS", el, {
            serialize: false,
            hideOnZoom: false,
            getMinHeight: () => 18,
            getHeight: () => 18,
        });
    }
    node._rayCivitStatusEl = el;
    return el;
}

function injectRefreshButton(node, statusEl) {
    if (node._rayCivitRefreshAdded) return;
    node._rayCivitRefreshAdded = true;
    node.addWidget(
        "button",
        "🔄 clear cache",
        null,
        async () => {
            statusEl.textContent = "clearing…";
            const res = await postRefresh();
            statusEl.textContent = res.ok
                ? "cache cleared — next run repages"
                : `refresh failed: ${res.error || "unknown"}`;
            setTimeout(() => {
                if (statusEl.textContent.startsWith("cache")) statusEl.textContent = "";
            }, 3000);
            node.setDirtyCanvas?.(true, true);
        },
        { serialize: false },
    );
}

async function bootstrap(node) {
    const statusEl = injectStatusWidget(node);
    injectRefreshButton(node, statusEl);
    autowireRayPreview(node, { height: 200, label: "civitai preview" });

    const opts = await fetchOptions();
    if (opts && opts.has_token === false) {
        const f = opts.token_file || "civitai.secret";
        statusEl.textContent = `no ${f} — public access only`;
    }

    const modeW = getWidget(node, "mode");
    applyModeStyling(node, modeW?.value);
    if (modeW) {
        const orig = modeW.callback;
        modeW.callback = function (v) {
            const r = orig?.apply(this, arguments);
            applyModeStyling(node, v);
            return r;
        };
    }
}

app.registerExtension({
    name: "Ray.CivitAI",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== NODE_NAME) return;
        const orig = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const r = orig?.apply(this, arguments);
            try {
                bootstrap(this);
            } catch (e) {
                console.error("[RayCivitAI] bootstrap error:", e);
            }
            return r;
        };
    },
});
