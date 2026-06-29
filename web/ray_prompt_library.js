import { app } from "../../scripts/app.js";

const NODE_NAME = "RayPromptLibrary";

const MODE_SAVE = "Save";
const MODE_FETCH = "Fetch";

const MODE_PREFIX = {
    [MODE_SAVE]: "save__",
    [MODE_FETCH]: "fetch__",
};
const ALWAYS_VISIBLE = new Set(["mode", "prompt_in", "seed"]);

function getWidget(node, name) {
    return node.widgets?.find((w) => w.name === name);
}

function setWidgetHidden(widget, hidden) {
    if (!widget) return;
    if (hidden) {
        if (widget.__rplOrigType === undefined) {
            widget.__rplOrigType = widget.type;
            widget.__rplOrigComputeSize = widget.computeSize;
        }
        widget.type = "hidden";
        widget.computeSize = () => [0, -4];
        widget.hidden = true;
    } else {
        if (widget.__rplOrigType !== undefined) {
            widget.type = widget.__rplOrigType;
            widget.computeSize = widget.__rplOrigComputeSize;
            widget.__rplOrigType = undefined;
            widget.__rplOrigComputeSize = undefined;
        }
        widget.hidden = false;
    }
}

function applyMode(node, mode) {
    const keep = MODE_PREFIX[mode] || MODE_PREFIX[MODE_FETCH];
    for (const w of node.widgets || []) {
        if (ALWAYS_VISIBLE.has(w.name)) {
            setWidgetHidden(w, false);
            continue;
        }
        if (w.name === "ray_pl_status") continue;
        setWidgetHidden(w, !w.name?.startsWith(keep));
    }
    applyModeStyling(node, mode);
    if (typeof node.computeSize === "function") {
        node.size[1] = node.computeSize()[1];
    }
    node.setDirtyCanvas?.(true, true);
}

function applyModeStyling(node, mode) {
    if (mode === MODE_SAVE) {
        node.bgcolor = "#3a3a1f";
        node.color = "#c8a83a";
    } else {
        node.bgcolor = "#1f3a3a";
        node.color = "#3ac8c8";
    }
}

async function fetchStats() {
    try {
        const r = await fetch("/ray_prompt_library/stats");
        return await r.json();
    } catch (e) {
        return { error: String(e) };
    }
}

function injectStatusWidget(node) {
    if (node._rplStatusEl) return node._rplStatusEl;
    const el = document.createElement("div");
    el.style.cssText =
        "padding:2px 6px;font-size:10px;color:#aaa;min-height:14px;";
    el.textContent = "";
    if (typeof node.addDOMWidget === "function") {
        node.addDOMWidget("ray_pl_status", "RAY_PL_STATUS", el, {
            serialize: false,
            hideOnZoom: false,
            getMinHeight: () => 18,
            getHeight: () => 18,
        });
    }
    node._rplStatusEl = el;
    return el;
}

async function refreshStatus(node, statusEl) {
    const s = await fetchStats();
    if (s.error) {
        statusEl.textContent = `library: ${s.error}`;
        return;
    }
    const emb = s.embeddings_available ? "embed-on" : "embed-off";
    statusEl.textContent = `${s.total ?? 0} prompts · ${(s.sources ?? []).length} sources · ${emb}`;
}

function bootstrap(node) {
    const statusEl = injectStatusWidget(node);
    refreshStatus(node, statusEl);

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
    name: "Ray.PromptLibrary",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== NODE_NAME) return;
        const origCreate = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const r = origCreate?.apply(this, arguments);
            try {
                bootstrap(this);
            } catch (e) {
                console.error("[RayPromptLibrary] bootstrap error:", e);
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
                console.error("[RayPromptLibrary] onConfigure error:", e);
            }
            return r;
        };
    },
});
