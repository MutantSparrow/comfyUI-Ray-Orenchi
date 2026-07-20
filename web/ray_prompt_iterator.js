import { app } from "../../scripts/app.js";
import { injectStylesOnce } from "./chat_styles.js";
import { applyBucketTint } from "./_common.js";

const NODE_NAME = "RayPromptIterator";

function getWidget(node, name) {
    return node.widgets?.find((w) => w.name === name);
}

function hideWidget(node, name) {
    const w = getWidget(node, name);
    if (!w) return;
    if (w._origType === undefined) w._origType = w.type;
    if (w._origComputeSize === undefined) w._origComputeSize = w.computeSize;
    w.type = "hidden";
    w.computeSize = () => [0, -4];
    w.hidden = true;
    w.visible = false;
    w.advanced = true;
    if (w.element) w.element.style.display = "none";
    if (w.options) w.options.hidden = true;
}

function readUrl(node)   { return getWidget(node, "server_url")?.value || "http://localhost:11434"; }
function readModel(node) { return getWidget(node, "model")?.value || ""; }

function buildPickerUI(node) {
    injectStylesOnce();
    hideWidget(node, "model");

    const wrap = document.createElement("div");
    wrap.style.cssText = "padding:4px 6px;display:flex;flex-direction:column;gap:4px;";

    // model picker row
    const modelBox = document.createElement("div");
    modelBox.className = "rc-modelbox";
    modelBox.title = "Ollama vision model";
    const modelNameEl = document.createElement("span");
    modelNameEl.className = "rc-modelname";
    modelNameEl.textContent = "(no model)";
    const modelTagsEl = document.createElement("span");
    modelTagsEl.className = "rc-modeltags";
    const modelArrow = document.createElement("span");
    modelArrow.className = "rc-modelarrow";
    modelArrow.textContent = "▾";
    const modelMenu = document.createElement("div");
    modelMenu.className = "rc-modelmenu";
    modelBox.append(modelNameEl, modelTagsEl, modelArrow, modelMenu);

    const statusEl = document.createElement("span");
    statusEl.style.cssText = "font-size:10px;color:#aaa;padding-left:4px;";

    // confidence display
    const confWrap = document.createElement("div");
    confWrap.style.cssText = "display:flex;align-items:center;gap:6px;padding:2px 4px;font-size:11px;";
    const confLabel = document.createElement("span");
    confLabel.textContent = "Confidence:";
    confLabel.style.cssText = "color:#bbb;";
    const confBarBg = document.createElement("div");
    confBarBg.style.cssText = "flex:1;height:10px;background:#222;border:1px solid #444;border-radius:3px;overflow:hidden;";
    const confBarFill = document.createElement("div");
    confBarFill.style.cssText = "height:100%;width:0%;background:#888;transition:width 200ms,background 200ms;";
    confBarBg.appendChild(confBarFill);
    const confValue = document.createElement("span");
    confValue.style.cssText = "color:#ddd;min-width:36px;text-align:right;font-variant-numeric:tabular-nums;";
    confValue.textContent = "—";
    confWrap.append(confLabel, confBarBg, confValue);

    function setConfidence(v, persist = true) {
        if (v == null || isNaN(v)) {
            confBarFill.style.width = "0%";
            confBarFill.style.background = "#888";
            confValue.textContent = "—";
            return;
        }
        const c = Math.max(0, Math.min(1, Number(v)));
        confBarFill.style.width = (c * 100).toFixed(1) + "%";
        const hue = Math.round(c * 120);
        confBarFill.style.background = `hsl(${hue}, 70%, 45%)`;
        confValue.textContent = c.toFixed(2);
        if (persist) {
            if (!node.properties) node.properties = {};
            node.properties._rayConfidence = c;
        }
    }

    node._raySetConfidence = setConfidence;

    // Restore last confidence after node is built
    setTimeout(() => {
        const saved = node.properties?._rayConfidence;
        if (typeof saved === "number") setConfidence(saved, false);
    }, 60);

    wrap.append(modelBox, statusEl, confWrap);

    wrap.addEventListener("wheel",       (e) => e.stopPropagation(), { passive: true });
    wrap.addEventListener("contextmenu", (e) => e.stopPropagation());
    wrap.addEventListener("pointerdown", (e) => e.stopPropagation());
    wrap.addEventListener("mousedown",   (e) => e.stopPropagation());

    let modelData = [];

    function setSelectedModel(name) {
        const w = getWidget(node, "model");
        if (w) w.value = name || "";
        modelNameEl.textContent = name || "(no model)";
        modelTagsEl.innerHTML = "";
        if (name) {
            const tag = document.createElement("span");
            tag.className = "rc-tag rc-tag-vision";
            tag.textContent = "🖼 vision";
            modelTagsEl.appendChild(tag);
        }
        modelMenu.querySelectorAll(".rc-modelitem").forEach((el) => {
            el.classList.toggle("selected", el.dataset.name === name);
        });
    }

    function rebuildModelMenu() {
        modelMenu.innerHTML = "";
        if (!modelData.length) {
            const empty = document.createElement("div");
            empty.className = "rc-modelitem";
            empty.style.cssText = "color:#888;cursor:default;";
            empty.textContent = "(no vision models found)";
            modelMenu.appendChild(empty);
            return;
        }
        for (const m of modelData) {
            const item = document.createElement("div");
            item.className = "rc-modelitem";
            item.dataset.name = m.name;
            const nameSpan = document.createElement("span");
            nameSpan.className = "rc-modelitemname";
            nameSpan.textContent = m.name;
            item.appendChild(nameSpan);
            if (m.parameter_size) {
                const ps = document.createElement("span");
                ps.className = "rc-modelparam";
                ps.textContent = m.parameter_size;
                item.appendChild(ps);
            }
            const tag = document.createElement("span");
            tag.className = "rc-tag rc-tag-vision";
            tag.textContent = "🖼 vision";
            item.appendChild(tag);
            item.addEventListener("click", (e) => {
                e.stopPropagation();
                setSelectedModel(m.name);
                modelMenu.classList.remove("open");
            });
            modelMenu.appendChild(item);
        }
    }

    modelBox.addEventListener("click", (e) => {
        if (e.target.closest(".rc-modelmenu")) return;
        e.stopPropagation();
        const willOpen = !modelMenu.classList.contains("open");
        document.querySelectorAll(".rc-modelmenu.open").forEach((el) => el.classList.remove("open"));
        if (willOpen) modelMenu.classList.add("open");
    });
    document.addEventListener("click", (e) => {
        if (!modelBox.contains(e.target)) modelMenu.classList.remove("open");
    });

    async function refreshModels() {
        const url = readUrl(node);
        statusEl.textContent = "loading models…";
        try {
            const r = await fetch(`/ray_ollama/models?url=${encodeURIComponent(url)}`);
            const j = await r.json();
            const all = (j.models || []).map((m) =>
                typeof m === "string"
                    ? { name: m, capabilities: [], families: [], parameter_size: "" }
                    : m
            );
            // vision-only filter
            modelData = all.filter((m) => m.capabilities?.includes("vision"));
            rebuildModelMenu();
            const cur = readModel(node);
            if (cur && modelData.some((m) => m.name === cur)) {
                setSelectedModel(cur);
            } else if (modelData.length) {
                setSelectedModel(modelData[0].name);
            } else {
                modelNameEl.textContent = j.error ? `(error: ${j.error})` : "(no vision models)";
                modelTagsEl.innerHTML = "";
            }
            statusEl.textContent = "";
        } catch (e) {
            statusEl.textContent = `error: ${e.message || e}`;
        }
    }

    if (typeof node.addDOMWidget === "function") {
        const dom = node.addDOMWidget("prompt_iter_ui", "RAY_PROMPT_ITER", wrap, {
            serialize: false,
            hideOnZoom: false,
            getMinHeight: () => 78,
            getHeight: () => 78,
        });
        // Move picker DOM widget to sit right below server_url
        try {
            const widgets = node.widgets || [];
            const urlIdx = widgets.findIndex((w) => w.name === "server_url");
            const domIdx = widgets.indexOf(dom);
            if (urlIdx !== -1 && domIdx !== -1 && domIdx !== urlIdx + 1) {
                widgets.splice(domIdx, 1);
                widgets.splice(urlIdx + 1, 0, dom);
            }
        } catch (e) {
            console.warn("[RayPromptIterator] reorder failed:", e);
        }
    }

    // initial load after widgets settle
    setTimeout(() => refreshModels(), 50);

    // refresh when server_url widget changes
    const urlW = getWidget(node, "server_url");
    if (urlW) {
        const orig = urlW.callback;
        urlW.callback = function (v) {
            const r = orig?.apply(this, arguments);
            refreshModels();
            return r;
        };
    }

    node._rayPromptIterRefresh = refreshModels;
}

app.registerExtension({
    name: "Ray.PromptIterator",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== NODE_NAME) return;
        const orig = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const r = orig?.apply(this, arguments);
            try { buildPickerUI(this); applyBucketTint(this, "LLM"); }
            catch (e) { console.error("[RayPromptIterator] buildPickerUI error:", e); }
            this.size = [380, 300];
            return r;
        };

        const onConfigure = nodeType.prototype.onConfigure;
        nodeType.prototype.onConfigure = function (info) {
            const r = onConfigure?.apply(this, arguments);
            setTimeout(() => this._rayPromptIterRefresh?.(), 50);
            return r;
        };

        const onExecuted = nodeType.prototype.onExecuted;
        nodeType.prototype.onExecuted = function (message) {
            const r = onExecuted?.apply(this, arguments);
            try {
                const txt = message?.ray_new_prompt?.[0];
                const flag = message?.copy_to_clipboard?.[0];
                const conf = message?.ray_confidence?.[0];
                if (conf != null) this._raySetConfidence?.(conf);
                if (flag && txt) {
                    if (navigator.clipboard?.writeText) {
                        navigator.clipboard.writeText(txt).catch((err) =>
                            console.warn("[RayPromptIterator] clipboard failed:", err)
                        );
                    } else {
                        const ta = document.createElement("textarea");
                        ta.value = txt;
                        ta.style.position = "fixed";
                        ta.style.opacity = "0";
                        document.body.appendChild(ta);
                        ta.select();
                        try { document.execCommand("copy"); } catch {}
                        document.body.removeChild(ta);
                    }
                }
            } catch (e) {
                console.warn("[RayPromptIterator] onExecuted error:", e);
            }
            return r;
        };
    },
});
