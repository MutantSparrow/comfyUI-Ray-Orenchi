import { installPanel } from "./ray_panel.js";
import { app } from "../../scripts/app.js";
import {
    applyBucketTint,
    setWidgetHidden as commonSetHidden,
    findWidget as getWidget,
} from "./_common.js";

const NODE_NAME = "RayPromptFetcher";

const MODE_LOCAL = "Local Folder";
const MODE_DEXTER = "PromptDexter";
const MODE_CIVITAI = "CivitAI";

const MODE_RED = "Red (NSFW)";
const NSFW_KEY = "ray.civitai.nsfwWarning.dismissed.v1";

// ---------------------------------------------------------------------------
// One-time warning for CivitAI Red. Dismissed once, it never shows again in this browser.
// ---------------------------------------------------------------------------

let lastPointer = [0, 0];
if (typeof window !== "undefined") {
    lastPointer = [window.innerWidth / 2, window.innerHeight / 3];
    window.addEventListener("pointerdown", event => { lastPointer = [event.clientX, event.clientY]; }, true);
}

export function nsfwWarningDismissed() {
    try { return localStorage.getItem(NSFW_KEY) === "1"; } catch { return false; }
}

function nsfwStyles() {
    if (document.getElementById("ray-nsfw-style")) return;
    const style = document.createElement("style");
    style.id = "ray-nsfw-style";
    style.textContent = `
.ray-nsfw { position:fixed; z-index:100000; box-sizing:border-box; width:290px; max-width:calc(100vw - 16px); padding:10px 12px 12px;
    background:#1b1c1f; color:#e6e6e6; border:1px solid #6b5a2a; border-radius:8px; box-shadow:0 10px 30px #000a; font:12px/1.4 system-ui,sans-serif; }
.ray-nsfw-title { display:flex; align-items:center; gap:8px; margin:0 0 6px; font:600 13px system-ui; color:#f2c65a; }
.ray-nsfw-title span { flex:1; }
.ray-nsfw p { margin:0 0 10px; color:#cfcfcf; }
.ray-nsfw button { padding:5px 10px; border:1px solid #4a4c52; border-radius:5px; background:#33363c; color:#fff; font:inherit; cursor:pointer; }
.ray-nsfw button:hover { background:#3d4148; }
.ray-nsfw .ray-nsfw-close { padding:0 6px; border:0; background:transparent; color:#9a9a9a; font-size:15px; line-height:1; }
.ray-nsfw .ray-nsfw-close:hover { color:#fff; background:transparent; }
.ray-nsfw button:focus-visible { outline:2px solid #185d89; outline-offset:2px; }
`;
    document.head.appendChild(style);
}

export function showNsfwWarning() {
    if (nsfwWarningDismissed() || document.querySelector(".ray-nsfw")) return null;
    nsfwStyles();
    const box = document.createElement("div");
    box.className = "ray-nsfw";
    box.setAttribute("role", "alertdialog");
    box.setAttribute("aria-labelledby", "ray-nsfw-title");
    const title = document.createElement("div");
    title.className = "ray-nsfw-title";
    const text = document.createElement("span");
    text.id = "ray-nsfw-title";
    text.textContent = "⚠️ NSFW content";
    const close = document.createElement("button");
    close.type = "button"; close.className = "ray-nsfw-close"; close.textContent = "×"; close.setAttribute("aria-label", "Dismiss");
    title.append(text, close);
    const body = document.createElement("p");
    body.textContent = "CivitAI Red includes adult (NSFW) images and prompts. Blue (SFW) keeps to safe content.";
    const ok = document.createElement("button");
    ok.type = "button"; ok.textContent = "Got it";
    box.append(title, body, ok);
    const stop = new AbortController();
    const dismiss = () => {
        try { localStorage.setItem(NSFW_KEY, "1"); } catch { /* shown again next time */ }
        stop.abort(); box.remove();
    };
    ok.addEventListener("click", dismiss);
    close.addEventListener("click", dismiss);
    box.addEventListener("keydown", event => { event.stopPropagation(); if (event.key === "Escape") { event.preventDefault(); dismiss(); } });
    window.addEventListener("keydown", event => { if (event.key === "Escape") dismiss(); }, { capture: true, signal: stop.signal });
    document.body.append(box);
    const rect = box.getBoundingClientRect(), margin = 8;
    box.style.left = `${Math.max(margin, Math.min(lastPointer[0] + 12, window.innerWidth - rect.width - margin))}px`;
    box.style.top = `${Math.max(margin, Math.min(lastPointer[1] + 12, window.innerHeight - rect.height - margin))}px`;
    ok.focus({ preventScroll: true });
    return box;
}

function warnIfRed(node) {
    if (getWidget(node, "scraper_mode")?.value === MODE_CIVITAI && getWidget(node, "civitai__mode")?.value === MODE_RED) showNsfwWarning();
}

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
        // stay visible. In the panel this decides which rows show.
        const owned = prefixes.some((p) => w.name?.startsWith(p));
        if (owned) commonSetHidden(node, w, !w.name.startsWith(keep));
    }
    applyModeStyling(node, mode);
    updateRefreshControls(node, mode);
    if (node._rayPanel) node._rayPanel.schedule();
    else if (typeof node.computeSize === "function") {
        const sz = node.computeSize();
        if (Array.isArray(node.size)) node.size[1] = sz[1];
        node.setSize?.([Array.isArray(node.size) ? node.size[0] : sz[0], sz[1]]);
    }
    node.setDirtyCanvas?.(true, true);
}

function applyModeStyling(node) {
    // Black in every mode, like every Ray node.
    applyBucketTint(node, "Tools");
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

// ---------------------------------------------------------------------------
// Refresh button + status line (PromptDexter sitemap, CivitAI cache)
// ---------------------------------------------------------------------------

async function postRefresh(url) {
    try {
        const r = await fetch(url, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({}),
        });
        return await r.json();
    } catch (e) {
        return { ok: false, error: String(e) };
    }
}

function setStatus(node, text, clearAfterMs = 0) {
    const el = node._rayScraperStatus;
    if (!el) return;
    el.textContent = text;
    node._rayPanel?.schedule();
    if (clearAfterMs) {
        setTimeout(() => {
            if (el.textContent === text) el.textContent = node._rayStatusDefault || "";
            node._rayPanel?.schedule();
        }, clearAfterMs);
    }
}

async function refreshSource(node) {
    const mode = getWidget(node, "scraper_mode")?.value;
    if (mode === MODE_DEXTER) {
        const category = getWidget(node, "dexter__category");
        const previous = category?.value;
        setStatus(node, "refreshing…");
        const res = await postRefresh("/ray_promptdexter/refresh");
        if (res.ok) {
            updateDexterCategoryWidget(node, res.categories || [], res.any || "(any)");
            if (previous && (res.categories || []).includes(previous) && category) category.value = previous;
            setStatus(node, `ok — ${res.prompt_url_count || 0} prompts, ${(res.categories || []).length} categories`, 3000);
        } else {
            setStatus(node, `refresh failed: ${res.error || "unknown"}`);
        }
    } else if (mode === MODE_CIVITAI) {
        setStatus(node, "clearing…");
        const res = await postRefresh("/ray_civitai/refresh");
        setStatus(node, res.ok ? "cache cleared — next run repages" : `refresh failed: ${res.error || "unknown"}`, 3000);
    }
    node.setDirtyCanvas?.(true, true);
}

function updateRefreshControls(node, mode) {
    // The CivitAI token note only applies to CivitAI mode.
    node._rayStatusDefault = mode === MODE_CIVITAI ? (node._rayCivitNote || "") : "";
    setStatus(node, node._rayStatusDefault);
}

// The panel: one source at a time, with refresh icons on the rows they belong to and a status line under them.
function scraperPanel(node) {
    const status = document.createElement("div");
    status.className = "rp-status";
    status.setAttribute("aria-live", "polite");
    node._rayScraperStatus = status;
    const mode = () => getWidget(node, "scraper_mode")?.value;
    const refresh = title => [{ icon: "refresh", title, onClick: () => refreshSource(node) }];
    return { sections: [
        { fields: [
            { name: "scraper_mode", label: "Source", kind: "segment", labels: { [MODE_LOCAL]: "Local", [MODE_DEXTER]: "PromptDexter", [MODE_CIVITAI]: "CivitAI" } },
            "seed",
        ] },
        { fields: [
            { name: "local__folder", label: "Folder of images", browse: { kind: "folder", title: "Choose a folder of images" } },
            { name: "local__recurse_subfolders", label: "Include subfolders" },
            { name: "local__skip_no_prompt", label: "Skip images without prompts" },
            { name: "local__prompt_best_try", label: "One prompt per image" },
            { name: "local__refresh_listing", label: "Re-scan the folder" },
        ] },
        { fields: [
            { name: "dexter__category", label: "Category", actions: refresh("Refresh the PromptDexter sitemap") },
            { name: "dexter__clear_cache", label: "Forget recent picks" },
            { name: "dexter__timeout", label: "Timeout (s)" },
        ] },
        { fields: [
            { name: "civitai__mode", label: "Rating", kind: "segment", labels: { "Blue (SFW)": "Blue · SFW", "Red (NSFW)": "Red · NSFW" } },
            { name: "civitai__base_model", label: "Base model", actions: refresh("Clear the CivitAI cache so the next run fetches again") },
            { name: "civitai__period", label: "Period" },
            { name: "civitai__sort", label: "Sort" },
            { name: "civitai__username", label: "Uploader", placeholder: "Anyone" },
            { name: "civitai__timeout", label: "Timeout (s)" },
        ] },
        { fields: [{ custom: () => status, when: () => !!status.textContent && [MODE_DEXTER, MODE_CIVITAI].includes(mode()) }] },
    ] };
}

async function checkCivitToken(node) {
    try {
        const r = await fetch("/ray_civitai/base_models");
        const opts = await r.json();
        if (opts && opts.has_token === false) {
            node._rayCivitNote = `no ${opts.token_file || "civitai.secret"} — public access only`;
            updateRefreshControls(node, getWidget(node, "scraper_mode")?.value);
        }
    } catch { /* offline or route missing: no note */ }
}

async function bootstrap(node) {
    const modeW = getWidget(node, "scraper_mode");
    if (!modeW) return;
    const spec = scraperPanel(node);
    if (typeof node.addDOMWidget === "function") queueMicrotask(() => installPanel(node, spec));
    checkCivitToken(node);

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
        warnIfRed(node);
        return r;
    };
    const ratingW = getWidget(node, "civitai__mode");
    if (ratingW) {
        const prior = ratingW.callback;
        ratingW.callback = function () {
            const r = prior?.apply(this, arguments);
            warnIfRed(node);
            return r;
        };
    }
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
