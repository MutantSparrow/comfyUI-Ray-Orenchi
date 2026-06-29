import { app } from "../../scripts/app.js";

const NODE_NAME = "RayMetaInspect";

const MODE_INSPECT = "Inspect";
const MODE_EMBED = "Embed";

// Widgets visible per mode. The `path` widget is shared.
const MODE_VISIBLE = {
    [MODE_INSPECT]: new Set(["mode", "path"]),
    [MODE_EMBED]: new Set(["mode", "path", "metadata_json"]),
};

function getWidget(node, name) {
    return node.widgets?.find((w) => w.name === name);
}

function setWidgetHidden(widget, hidden) {
    if (!widget) return;
    if (hidden) {
        if (widget.__rmiOrigType === undefined) {
            widget.__rmiOrigType = widget.type;
            widget.__rmiOrigComputeSize = widget.computeSize;
        }
        widget.type = "hidden";
        widget.computeSize = () => [0, -4];
        widget.hidden = true;
    } else {
        if (widget.__rmiOrigType !== undefined) {
            widget.type = widget.__rmiOrigType;
            widget.computeSize = widget.__rmiOrigComputeSize;
            widget.__rmiOrigType = undefined;
            widget.__rmiOrigComputeSize = undefined;
        }
        widget.hidden = false;
    }
}

function applyMode(node, mode) {
    const keep = MODE_VISIBLE[mode] || MODE_VISIBLE[MODE_INSPECT];
    for (const w of node.widgets || []) {
        if (w.name === "ray_drop_zone" || w.name === "ray_preview") continue;
        setWidgetHidden(w, !keep.has(w.name));
    }
    // Drop zone + preview are Inspect-only.
    const inspect = mode === MODE_INSPECT;
    if (node._rmiDropZoneEl) node._rmiDropZoneEl.style.display = inspect ? "" : "none";
    if (node._rmiPreviewEl) node._rmiPreviewEl.style.display = inspect ? "" : "none";
    if (typeof node.computeSize === "function") {
        const sz = node.computeSize();
        if (Array.isArray(node.size)) node.size[1] = sz[1];
        node.setSize?.([Array.isArray(node.size) ? node.size[0] : sz[0], sz[1]]);
    }
    node.setDirtyCanvas?.(true, true);
}

/**
 * Build a /view URL for an uploaded image. ComfyUI's /api/view (or /view in
 * older builds) serves files from input/output/temp folders. The annotated
 * `name [input]` filename format is what /upload/image returns; we translate
 * it into the equivalent ?filename=&type=&subfolder= query.
 */
function buildViewURL(name, subfolder, type) {
    const params = new URLSearchParams({
        filename: name,
        type: type || "input",
        subfolder: subfolder || "",
        // Cache-bust so re-uploaded files re-render.
        t: String(performance.now() | 0),
    });
    return `/api/view?${params.toString()}`;
}

function setPreviewImage(node, url) {
    if (!node._rmiPreviewEl) return;
    if (url) {
        node._rmiPreviewEl.src = url;
        node._rmiPreviewEl.style.display = "block";
    } else {
        node._rmiPreviewEl.removeAttribute("src");
        node._rmiPreviewEl.style.display = "none";
    }
    node.setDirtyCanvas?.(true, true);
}

function injectPreview(node) {
    if (node._rmiPreviewEl) return node._rmiPreviewEl;
    const img = document.createElement("img");
    img.style.cssText =
        "max-width:100%;max-height:220px;display:none;margin:4px auto;" +
        "border-radius:3px;background:rgba(0,0,0,0.3);object-fit:contain;";
    img.alt = "preview";
    img.addEventListener("error", () => {
        img.style.display = "none";
    });

    if (typeof node.addDOMWidget === "function") {
        node.addDOMWidget("ray_preview", "RAY_META_PREVIEW", img, {
            serialize: false,
            hideOnZoom: false,
            getMinHeight: () => (img.style.display === "none" ? 0 : 90),
            getHeight: () => (img.style.display === "none" ? 0 : 220),
        });
    }
    node._rmiPreviewEl = img;
    return img;
}

function injectDropZone(node) {
    if (node._rmiDropZoneEl) return node._rmiDropZoneEl;
    const el = document.createElement("div");
    el.textContent = "drop image here";
    el.style.cssText =
        "padding:14px 6px;text-align:center;font-size:11px;color:#888;" +
        "border:1px dashed #555;border-radius:4px;margin:4px 2px;" +
        "background:rgba(0,0,0,0.2);transition:all 120ms ease;";
    const setIdle = () => {
        el.textContent = "drop image here";
        el.style.color = "#888";
        el.style.borderColor = "#555";
        el.style.background = "rgba(0,0,0,0.2)";
    };
    const setHover = () => {
        el.textContent = "release to upload";
        el.style.color = "#fff";
        el.style.borderColor = "#3aa867";
        el.style.background = "rgba(58,168,103,0.15)";
    };
    el.addEventListener("dragover", (e) => {
        e.preventDefault();
        e.stopPropagation();
        e.dataTransfer.dropEffect = "copy";
        setHover();
    });
    el.addEventListener("dragleave", (e) => {
        e.preventDefault();
        e.stopPropagation();
        setIdle();
    });
    el.addEventListener("drop", async (e) => {
        e.preventDefault();
        e.stopPropagation();
        setIdle();
        const file = e.dataTransfer.files?.[0];
        if (!file) return;
        el.textContent = `uploading ${file.name}…`;
        try {
            const fd = new FormData();
            fd.append("image", file, file.name);
            fd.append("overwrite", "true");
            const res = await fetch("/upload/image", { method: "POST", body: fd });
            const json = await res.json();
            if (!res.ok) throw new Error(json?.error || res.statusText);
            // ComfyUI's /upload/image returns {name, subfolder, type:"input"}.
            // We store the canonical annotated `name [input]` form on the
            // widget — the backend's _resolve_path() understands that shape
            // and routes via ComfyUI's folder_paths.get_input_directory().
            const sub = json.subfolder ? `${json.subfolder}/` : "";
            const folderType = json.type || "input";
            const annotated = `${sub}${json.name} [${folderType}]`;
            const pathW = getWidget(node, "path");
            if (pathW) {
                pathW.value = annotated;
                if (typeof pathW.callback === "function") {
                    try { pathW.callback(annotated); } catch {}
                }
            }
            setPreviewImage(node, buildViewURL(json.name, json.subfolder, folderType));
            el.textContent = `loaded: ${json.name}`;
            // Re-snap height so the preview slot is included.
            if (typeof node.computeSize === "function") {
                const sz = node.computeSize();
                if (Array.isArray(node.size)) node.size[1] = sz[1];
                node.setSize?.([Array.isArray(node.size) ? node.size[0] : sz[0], sz[1]]);
            }
            node.setDirtyCanvas?.(true, true);
            setTimeout(setIdle, 2500);
        } catch (err) {
            console.error("[RayMetaInspect] upload failed:", err);
            el.textContent = `upload failed: ${err.message || err}`;
            setTimeout(setIdle, 4000);
        }
    });

    if (typeof node.addDOMWidget === "function") {
        node.addDOMWidget("ray_drop_zone", "RAY_META_DROP", el, {
            serialize: false,
            hideOnZoom: false,
            getMinHeight: () => 40,
            getHeight: () => 40,
        });
    }
    node._rmiDropZoneEl = el;
    return el;
}

/**
 * Parse an annotated path string back into {name, subfolder, type} so the
 * preview survives a workflow reload. Accepts `<sub>/<name> [input]` and
 * `input/<sub>/<name>` shapes.
 */
const QUOTE_PAIRS = [
    ['"', '"'], ["'", "'"], ["«", "»"], ["“", "”"], ["‘", "’"], ["`", "`"],
];

function stripQuotes(s) {
    if (!s) return s;
    const t = s.trim();
    for (const [o, c] of QUOTE_PAIRS) {
        if (t.length >= 2 && t.startsWith(o) && t.endsWith(c)) {
            return t.slice(1, -1).trim();
        }
    }
    return t;
}

function parseRefPath(raw) {
    const s = stripQuotes(raw || "");
    if (!s) return null;
    const m = s.match(/^(.*)\s*\[(input|output|temp)\]\s*$/);
    if (m) {
        const body = m[1].trim().replace(/\\/g, "/");
        const parts = body.split("/");
        const name = parts.pop();
        const subfolder = parts.join("/");
        return { name, subfolder, type: m[2] };
    }
    const low = s.toLowerCase();
    for (const t of ["input", "output", "temp"]) {
        if (low.startsWith(`${t}/`) || low.startsWith(`${t}\\`)) {
            const rest = s.slice(t.length + 1).replace(/\\/g, "/");
            const parts = rest.split("/");
            const name = parts.pop();
            const subfolder = parts.join("/");
            return { name, subfolder, type: t };
        }
    }
    return null;
}

function maybeRestorePreview(node) {
    const w = getWidget(node, "path");
    const ref = parseRefPath(w?.value);
    if (ref) setPreviewImage(node, buildViewURL(ref.name, ref.subfolder, ref.type));
}

function wirePathStripper(node) {
    const pathW = getWidget(node, "path");
    if (!pathW) return;
    const orig = pathW.callback;
    pathW.callback = function (v) {
        const cleaned = stripQuotes(v);
        if (cleaned !== v) {
            pathW.value = cleaned;
        }
        const r = orig?.apply(this, [cleaned]);
        // Refresh the preview from the new path if it looks like one of the
        // input/output/temp routed forms.
        maybeRestorePreview(node);
        return r;
    };
}

function bootstrap(node) {
    injectDropZone(node);
    injectPreview(node);
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
                maybeRestorePreview(this);
            } catch (e) {
                console.error("[RayMetaInspect] onConfigure error:", e);
            }
            return r;
        };
    },
});
