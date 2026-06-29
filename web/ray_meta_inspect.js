import { app } from "../../scripts/app.js";

const NODE_NAME = "RayMetaInspect";

const MODE_INSPECT = "Inspect";
const MODE_EMBED = "Embed";

// Widgets visible by mode. The `path` widget is shared.
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
        if (w.name === "ray_drop_zone") continue;
        setWidgetHidden(w, !keep.has(w.name));
    }
    // Drop zone is Inspect-only.
    if (node._rmiDropZoneEl) {
        node._rmiDropZoneEl.style.display = mode === MODE_INSPECT ? "" : "none";
    }
    if (typeof node.computeSize === "function") {
        const sz = node.computeSize();
        if (Array.isArray(node.size)) node.size[1] = sz[1];
        node.setSize?.([Array.isArray(node.size) ? node.size[0] : sz[0], sz[1]]);
    }
    node.setDirtyCanvas?.(true, true);
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
            // ComfyUI's /upload/image returns {name, subfolder, type}
            // Resolve to a viewable URL the server can later read by name —
            // here we set the *display* path. Users with absolute-path workflows
            // can still type a path manually.
            const sub = json.subfolder ? `${json.subfolder}/` : "";
            const inputDir = "input/";  // ComfyUI default upload dir
            const pathW = getWidget(node, "path");
            if (pathW) {
                // Convention: ComfyUI saves into <comfy>/input/<subfolder>/<name>.
                // Most users want the absolute path. Try a sane reconstruction.
                pathW.value = `${inputDir}${sub}${json.name}`;
                node.setDirtyCanvas?.(true, true);
                el.textContent = `loaded: ${json.name}`;
            } else {
                el.textContent = "path widget missing";
            }
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

function bootstrap(node) {
    injectDropZone(node);
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
