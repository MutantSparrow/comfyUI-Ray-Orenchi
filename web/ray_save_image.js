import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";
import { findWidget, setWidgetHidden } from "./_common.js";
import { browsePath, notify } from "./browse_common.js";
import { installNameBuilder } from "./save_name.js";

const modes = ["none", "1", "2", "both"];
const historyKey = "ray.saveImage.paths.v1";
function history() {
    try {
        const value = JSON.parse(localStorage.getItem(historyKey) || "[]");
        return Array.isArray(value) ? value.filter(p => typeof p === "string").slice(0, 3) : [];
    } catch { return []; }
}
function remember(path) {
    try { localStorage.setItem(historyKey, JSON.stringify([path, ...history().filter(p => p !== path)].slice(0, 3))); }
    catch { /* Saving remains available when browser storage is disabled. */ }
}
function element(tag, className, text) {
    const el = document.createElement(tag);
    if (className) el.className = className;
    if (text !== undefined) el.textContent = text;
    return el;
}
function button(text, action) {
    const el = element("button", "", text); el.type = "button";
    el.addEventListener("click", action); return el;
}
function linked(node, name) { return node.inputs?.some(i => i.name === name && i.link != null); }
function update(node, name, value) {
    const widget = findWidget(node, name);
    if (!widget || linked(node, name) || Object.is(widget.value, value)) return;
    node.graph?.beforeChange?.();
    try { widget.value = value; widget.callback?.(value); }
    finally { node.graph?.afterChange?.(); node.setDirtyCanvas?.(true, true); }
    node._raySave?.sync();
}

function styles() {
    if (document.getElementById("ray-save-style")) return;
    const css = element("style"); css.id = "ray-save-style";
    css.textContent = `
.dom-widget:has(> .ray-save) {pointer-events:none !important}
.ray-save {box-sizing:border-box;width:100%;height:100%;padding:2px;display:flex;flex-direction:column;gap:2px;background:#000;color:#eee;font:12px system-ui;border-radius:8px;overflow:hidden;pointer-events:none}
.ray-save button,.ray-save select,.ray-save-handle {pointer-events:auto}
.ray-save * {box-sizing:border-box}
.ray-save button,.ray-save select {font:inherit;color:inherit;background:#171717;border:1px solid #383838;border-radius:4px;padding:3px 6px;min-width:0}
.ray-save button:disabled {opacity:.4}
.ray-save button:hover:not(:disabled) {background:#454753}
.ray-save :focus-visible {outline:2px solid #b9a4fa;outline-offset:2px}
.ray-save-toolbar {display:flex;gap:5px;align-items:center;flex-shrink:0}
.ray-save-toolbar label {white-space:nowrap;font-size:11px}
.ray-save > .ray-save-toolbar {gap:4px}
.ray-save-stops {display:flex;flex-shrink:0;gap:0;margin-right:auto;border:1px solid #444;border-radius:4px;overflow:hidden}
.ray-save-stops button {flex:0 0 auto;padding:3px 6px;font-size:11px;background:transparent;border:0;border-radius:0}
.ray-save-stops button[aria-pressed=true] {background:#ddd;color:#111}
.ray-save-stage {position:relative;flex:1 1 0;min-height:0;overflow:hidden;border-radius:5px;background:#000}
.ray-save-stage img {position:absolute;width:100%;height:100%;object-fit:contain;inset:0;pointer-events:none}
.ray-save-overlay {position:absolute;inset:0;pointer-events:none;background:#000}
.ray-save-divider {position:absolute;top:0;bottom:0;width:2px;background:#fff;box-shadow:0 0 2px #000;pointer-events:none}
.ray-save-handle {position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);background:#f5f3fa;color:#222;border-radius:12px;padding:8px 5px;white-space:nowrap;font:bold 13px system-ui;box-shadow:0 1px 5px #0008;cursor:ew-resize;touch-action:none}
.ray-save-empty {position:absolute;inset:0;display:grid;place-items:center;color:#bbb;text-align:center;padding:24px;pointer-events:none}
.ray-save-badge {position:absolute;top:8px;background:#111b;padding:3px 6px;border-radius:3px;pointer-events:none;font-size:10px}
.ray-save-info {position:absolute;left:6px;bottom:6px;max-width:calc(100% - 120px);display:flex;flex-direction:column;align-items:flex-start;gap:2px;pointer-events:none}
.ray-save-info > span {max-width:100%;padding:2px 5px;border-radius:3px;background:#000b;color:#ddd;font-size:10px;line-height:1.3;white-space:pre-line;overflow:hidden;text-overflow:ellipsis}
.ray-save-info > span:empty {display:none}
.ray-save-nav {position:absolute;right:6px;bottom:6px;display:flex;align-items:center;gap:3px;padding:2px;border-radius:5px;background:#000b;font-size:10px;color:#ddd}
.ray-save-nav button {padding:1px 6px}
`;
    document.head.append(css);
}

// The Browse button opens the system's own folder dialog (see browse_routes.py).
async function browseFolder(node) {
    try {
        const picked = await browsePath("folder", findWidget(node, "directory")?.value || "", { title: "Choose the save folder" });
        if (picked) update(node, "directory", picked);
    } catch (error) { notify(error.message); }
}

function build(node) {
    styles();
    const navigation = new AbortController();
    let spaceHeld = false, panClick = false;
    window.addEventListener("keydown", e => { if (e.code === "Space" || e.key === " ") spaceHeld = true; }, {capture: true, signal: navigation.signal});
    window.addEventListener("keyup", e => { if (e.code === "Space" || e.key === " ") spaceHeld = false; }, {capture: true, signal: navigation.signal});
    window.addEventListener("blur", () => { spaceHeld = false; }, {signal: navigation.signal});
    const root = element("div", "ray-save"), toolbar = element("div", "ray-save-toolbar");
    const browse = button("Browse…", () => browseFolder(node));
    const recent = element("select"); recent.title = "Last three save folders"; recent.setAttribute("aria-label", "Recent save folders");
    function recentOptions() {
        recent.replaceChildren(element("option", "", ""), ...history().map(p => { const o = element("option", "", p); o.value = p; return o; }));
        recent.selectedIndex = 0;
    }
    recent.style.width = "25px"; recentOptions();
    recent.addEventListener("pointerdown", recentOptions);
    recent.onchange = () => { if (recent.selectedIndex > 0) update(node, "directory", recent.value); recent.selectedIndex = 0; };
    const state = element("span", "ray-save-status");
    const stops = element("div", "ray-save-stops");
    stops.setAttribute("role", "group"); stops.setAttribute("aria-label", "Save Image");
    modes.forEach(mode => stops.append(button(mode === "none" ? "None" : mode === "both" ? "Both" : mode, () => update(node, "save_image", mode))));
    toolbar.append(stops, browse, recent);
    const stage = element("div", "ray-save-stage"), first = element("img"), second = element("img"), overlay = element("div", "ray-save-overlay");
    first.alt = "Image 1"; second.alt = "Image 2"; overlay.append(first);
    const divider = element("div", "ray-save-divider"), handle = element("span", "ray-save-handle", "‹ ›"), empty = element("div", "ray-save-empty", "Queue the workflow to preview images");
    const left = element("span", "ray-save-badge", "1"), right = element("span", "ray-save-badge", "2");
    left.style.left = "8px"; right.style.right = "8px";
    divider.append(handle);
    handle.tabIndex = 0; handle.setAttribute("role", "slider"); handle.setAttribute("aria-label", "Image comparison divider");
    handle.setAttribute("aria-valuemin", "0"); handle.setAttribute("aria-valuemax", "100");
    let fraction = .5, arrays = [[], []], index = 0, comparing = false, activePointer = null;
    const batch = element("div", "ray-save-nav"), count = element("span", "ray-save-status");
    const info = element("div", "ray-save-info"), sizes = element("span", "ray-save-sizes");
    info.append(sizes, state);
    stage.append(second, overlay, divider, left, right, empty, info, batch);
    function updateSizes() {
        sizes.textContent = [first, second].flatMap((img, n) =>
            !img.hidden && img.complete && img.naturalWidth
                ? [`${arrays[1].length ? `${n + 1}: ` : ""}${img.naturalWidth} × ${img.naturalHeight}`] : []
        ).join("\n");
    }
    [first, second].forEach(img => img.addEventListener("load", updateSizes));
    const previous = button("‹", () => { index--; show(); }), next = button("›", () => { index++; show(); });
    previous.setAttribute("aria-label", "Previous image pair"); next.setAttribute("aria-label", "Next image pair");
    batch.append(previous, count, next);
    function position(value) {
        fraction = Math.max(0, Math.min(1, value));
        overlay.style.clipPath = comparing ? `inset(0 ${(1 - fraction) * 100}% 0 0)` : "none";
        divider.style.left = `${fraction * 100}%`;
        handle.setAttribute("aria-valuenow", String(Math.round(fraction * 100)));
    }
    function drag(e) {
        const rect = stage.getBoundingClientRect();
        if (rect.width) position((e.clientX - rect.left) / rect.width);
    }
    // Only the handle takes pointer input; the rest of the preview is
    // transparent to the mouse so the canvas keeps its menu, pan and zoom.
    handle.onpointerdown = e => { if (spaceHeld || !comparing || e.button !== 0) return; activePointer = e.pointerId; handle.setPointerCapture(e.pointerId); drag(e); e.preventDefault(); };
    handle.onpointermove = e => { if (activePointer === e.pointerId) drag(e); };
    handle.onpointerup = handle.onpointercancel = e => { if (handle.hasPointerCapture(e.pointerId)) handle.releasePointerCapture(e.pointerId); activePointer = null; };
    handle.onlostpointercapture = () => { activePointer = null; };
    handle.onkeydown = e => {
        if (!comparing) return;
        const values = {ArrowLeft: fraction - .02, ArrowRight: fraction + .02, Home: 0, End: 1};
        if (Object.hasOwn(values, e.key)) { e.preventDefault(); position(values[e.key]); }
    };
    function show() {
        const total = Math.max(arrays[0].length, arrays[1].length);
        index = Math.max(0, Math.min(index, total - 1));
        const pair = arrays.map(a => a.length === 1 ? a[0] : a[index]);
        comparing = !!(pair[0] && pair[1]);
        overlay.hidden = !pair[0];
        [first, second].forEach((img, n) => {
            img.hidden = !pair[n];
            if (pair[n]) img.src = api.apiURL(`/view?${new URLSearchParams(pair[n])}`);
            else img.removeAttribute("src");
        });
        divider.hidden = !comparing; left.hidden = !pair[0]; right.hidden = !pair[1];
        handle.setAttribute("aria-disabled", String(!comparing));
        empty.hidden = !!(pair[0] || pair[1]); empty.style.display = empty.hidden ? "none" : "grid";
        batch.hidden = total <= 1; batch.style.display = batch.hidden ? "none" : "flex";
        count.textContent = `${index + 1} / ${total}${!comparing && arrays[1].length ? " · Unpaired image" : ""}`;
        previous.disabled = index === 0; next.disabled = index >= total - 1;
        position(fraction);
        updateSizes();
    }
    [first, second].forEach(img => img.addEventListener("error", () => { state.textContent = "Preview expired. Queue again to refresh."; }));
    root.append(toolbar, stage);
    // Keep canvas navigation alive over DOM widgets. Only ordinary control
    // interactions belong to this panel; wheel, Space-pan and middle-pan bubble.
    root.addEventListener("pointerdown", e => { panClick = spaceHeld || e.button === 1; }, true);
    root.addEventListener("click", e => {
        if (panClick) { panClick = false; e.preventDefault(); e.stopImmediatePropagation(); }
    }, true);
    for (const event of ["pointerdown", "mousedown", "click", "dblclick"]) root.addEventListener(event, e => {
        if (!spaceHeld && e.button === 0) e.stopPropagation();
    });
    for (const event of ["keydown", "keyup"]) root.addEventListener(event, e => {
        if (e.ctrlKey || e.metaKey || e.altKey || e.code === "Space" || e.key === " ") return;
        if (e.defaultPrevented || ["Enter", "ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", "Home", "End"].includes(e.key)) e.stopPropagation();
    });
    const ui = {
        root,
        sync() {
            const mode = findWidget(node, "save_image")?.value || "1";
            [...stops.children].forEach((b, i) => { b.disabled = linked(node, "save_image"); b.setAttribute("aria-pressed", String(mode === modes[i])); });
            browse.disabled = recent.disabled = linked(node, "directory");
        },
        executed(message) {
            arrays = [message.ray_images_1 || [], message.ray_images_2 || []]; index = 0;
            state.textContent = message.ray_saved?.length ? `Saved ${message.ray_saved.length} PNG${message.ray_saved.length === 1 ? "" : "s"}` : "Preview only · No files saved";
            state.title = (message.ray_saved || []).join("\n");
            if (message.ray_directory?.[0]) { remember(message.ray_directory[0]); recentOptions(); }
            show();
        },
        destroy() { navigation.abort(); first.removeAttribute("src"); second.removeAttribute("src"); },
    };
    show(); ui.sync(); return ui;
}

app.registerExtension({
    name: "Ray.SaveImage",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== "RaySaveImage") return;
        const proto = nodeType.prototype, created = proto.onNodeCreated;
        proto.onNodeCreated = function () {
            const result = created?.apply(this, arguments); this.color = this.bgcolor = "#000000";
            installNameBuilder(this);
            if (!this.addDOMWidget) return result;
            this._raySave = build(this);
            for (const name of ["save_image", "save_without_metadata"]) setWidgetHidden(this, findWidget(this, name), true);
            this.addDOMWidget("ray_save_preview", "RAY_SAVE_IMAGE", this._raySave.root, {
                serialize: false, hideOnZoom: false, getMinHeight: () => 120, getHeight: () => 300,
            });
            this.setSize?.([Math.max(this.size?.[0] || 0, 320), Math.max(this.size?.[1] || 0, 400)]);
            return result;
        };
        for (const event of ["onConfigure", "onConnectionsChange"]) {
            const prior = proto[event];
            proto[event] = function () { const result = prior?.apply(this, arguments);
                if (event === "onConfigure" && this.bgcolor === "#2a1f3a" && this.color === "#8a3ac8") this.color = this.bgcolor = "#000000";
                this._raySave?.sync(); return result; };
        }
        const executed = proto.onExecuted;
        proto.onExecuted = function (message) {
            const result = executed?.apply(this, arguments);
            if (message.ray_saved?.length && message.ray_directory?.[0]) this._raySavedDirectory = message.ray_directory[0];
            this._raySave?.executed(message); return result;
        };
        const removed = proto.onRemoved;
        proto.onRemoved = function () { this._raySave?.destroy(); return removed?.apply(this, arguments); };
        const menu = proto.getExtraMenuOptions;
        proto.getExtraMenuOptions = function (canvas, options) {
            const result = menu?.apply(this, arguments), widget = findWidget(this, "save_without_metadata");
            options.unshift({content: `${widget?.value ? "✓ " : ""}Save without metadata`, disabled: linked(this, "save_without_metadata"),
                callback: () => update(this, "save_without_metadata", !widget?.value)},
            {content: "Open image location in Explorer", disabled: !this._raySavedDirectory,
                callback: async () => {
                    if (!this._raySavedDirectory) return;
                    try {
                        const response = await api.fetchApi("/ray/save-image/open-location", {
                            method: "POST", headers: {"Content-Type": "application/json"},
                            body: JSON.stringify({path: this._raySavedDirectory}),
                        });
                        const data = await response.json();
                        if (!response.ok) throw new Error(data.error || "Cannot open image location.");
                    } catch (error) { window.alert(error.message); }
                }});
            return result;
        };
    },
});
