import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";
import { applyBucketTint, findWidget, setWidgetHidden } from "./_common.js";

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
.ray-save {box-sizing:border-box;width:100%;height:100%;padding:8px;display:flex;flex-direction:column;gap:8px;background:#202126;color:#eee;font:12px system-ui;border-radius:8px;overflow:hidden}
.ray-save *, .ray-save-dialog * {box-sizing:border-box}
.ray-save button,.ray-save select,.ray-save-dialog button,.ray-save-dialog input,.ray-save-dialog select {font:inherit;color:inherit;background:#33353d;border:1px solid #51535e;border-radius:5px;padding:5px 8px;min-width:0}
.ray-save button:disabled {opacity:.4}
.ray-save button:hover:not(:disabled),.ray-save-dialog button:hover {background:#454753}
.ray-save :focus-visible,.ray-save-dialog :focus-visible {outline:2px solid #b9a4fa;outline-offset:2px}
.ray-save-toolbar {display:flex;gap:5px;align-items:center;flex-shrink:0}
.ray-save-toolbar label {margin-right:auto}
.ray-save-range {width:100%;accent-color:#b7a2ef;margin:0;cursor:pointer}
.ray-save-stops {display:flex;justify-content:space-between;gap:4px}
.ray-save-stops button {flex:1;padding:3px;font-size:11px;background:transparent;border-color:transparent}
.ray-save-stops button[aria-pressed=true] {background:#534570;border-color:#a48bce}
.ray-save-stage {position:relative;flex:1;min-height:140px;overflow:hidden;border-radius:5px;background:repeating-conic-gradient(#24252a 0% 25%,#2e3035 0% 50%) 50%/16px 16px;touch-action:none}
.ray-save-stage img {position:absolute;width:100%;height:100%;object-fit:contain;inset:0;pointer-events:none}
.ray-save-overlay {position:absolute;inset:0;pointer-events:none;background:repeating-conic-gradient(#24252a 0% 25%,#2e3035 0% 50%) 50%/16px 16px}
.ray-save-divider {position:absolute;top:0;bottom:0;width:2px;background:#fff;box-shadow:0 0 2px #000;pointer-events:none}
.ray-save-divider::after {content:'‹ ›';position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);background:#f5f3fa;color:#222;border-radius:12px;padding:6px 4px;white-space:nowrap;font:bold 13px system-ui;box-shadow:0 1px 5px #0008}
.ray-save-empty {position:absolute;inset:0;display:grid;place-items:center;color:#bbb;text-align:center;padding:24px;pointer-events:none}
.ray-save-badge {position:absolute;top:8px;background:#111b;padding:3px 6px;border-radius:3px;pointer-events:none;font-size:10px}
.ray-save-status {font-size:11px;color:#c0bdc8;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;min-height:15px}
.ray-save-dialog {width:min(620px,90vw);max-height:80vh;background:#24252b;color:#eee;border:1px solid #62616d;border-radius:10px;padding:16px;font:13px system-ui}
.ray-save-dialog::backdrop {background:#0008}
.ray-save-dialog h3 {margin:0 0 12px;font-size:16px}
.ray-save-dialog .ray-save-toolbar {margin-bottom:10px}
.ray-save-dialog input {flex:1;width:100%}
.ray-save-folders {display:flex;flex-direction:column;gap:4px;overflow:auto;height:260px;margin:10px 0}
.ray-save-folders button {text-align:left}
.ray-save-dialog .ray-save-error {min-height:18px;color:#ffb1aa;overflow-wrap:anywhere}
`;
    document.head.append(css);
}

function folderPicker(node) {
    const dialog = element("dialog", "ray-save-dialog");
    dialog.append(element("h3", "", "Choose save folder"));
    const row = element("div", "ray-save-toolbar"), path = element("input");
    path.setAttribute("aria-label", "Folder path");
    const list = element("div", "ray-save-folders"), error = element("div", "ray-save-error");
    const roots = element("select"); roots.setAttribute("aria-label", "Drive");
    const choose = button("Use this folder", () => {
        if (!current) return;
        update(node, "directory", current); dialog.close();
    });
    let current = "", parent = "", requestNumber = 0;
    const controller = new AbortController();
    async function load(value) {
        const request = ++requestNumber; error.textContent = "Loading…"; choose.disabled = true;
        try {
            const response = await api.fetchApi(`/ray/save-image/folders?${new URLSearchParams({path: value})}`, {signal: controller.signal});
            const data = await response.json();
            if (request !== requestNumber || !dialog.isConnected) return;
            if (!response.ok) throw new Error(data.error || "Cannot open folder.");
            current = data.path; parent = data.parent; path.value = current;
            roots.replaceChildren(...data.roots.map(root => { const o = element("option", "", root); o.value = root; return o; }));
            roots.value = data.roots.find(root => current.toLowerCase().startsWith(root.toLowerCase())) || data.roots[0];
            list.replaceChildren(...data.folders.map(folder => button(`▸ ${folder.name}`, () => load(folder.path))));
            error.textContent = data.folders.length ? "" : "No subfolders. You can choose this folder.";
            choose.disabled = false;
        } catch (e) { if (e.name !== "AbortError" && request === requestNumber) error.textContent = e.message; }
    }
    roots.onchange = () => load(roots.value);
    path.addEventListener("keydown", e => { if (e.key === "Enter") { e.preventDefault(); load(path.value); } });
    row.append(roots, button("↑", () => load(parent)), path, button("Open", () => load(path.value)));
    const footer = element("div", "ray-save-toolbar");
    footer.append(button("Cancel", () => dialog.close()), choose);
    dialog.append(row, list, error, footer);
    dialog.addEventListener("close", () => { controller.abort(); dialog.remove(); node._raySaveDialog = null; });
    dialog.addEventListener("keydown", e => e.stopPropagation());
    node._raySaveDialog?.close(); node._raySaveDialog = dialog;
    document.body.append(dialog); dialog.showModal(); load(findWidget(node, "directory")?.value || "");
}

function build(node) {
    styles();
    const root = element("div", "ray-save"), toolbar = element("div", "ray-save-toolbar");
    const browse = button("Browse…", () => folderPicker(node));
    const recent = element("select"); recent.title = "Last three save folders"; recent.setAttribute("aria-label", "Recent save folders");
    function recentOptions() {
        recent.replaceChildren(element("option", "", ""), ...history().map(p => { const o = element("option", "", p); o.value = p; return o; }));
        recent.selectedIndex = 0;
    }
    recent.style.maxWidth = "42px"; recentOptions();
    recent.addEventListener("pointerdown", recentOptions);
    recent.onchange = () => { if (recent.selectedIndex > 0) update(node, "directory", recent.value); recent.selectedIndex = 0; };
    const label = element("label", "", "Save Image"), state = element("span", "ray-save-status");
    toolbar.append(label, browse, recent);
    const range = element("input", "ray-save-range"); range.type = "range"; range.min = "0"; range.max = "3"; range.step = "1";
    range.setAttribute("aria-label", "Save Image"); range.oninput = () => update(node, "save_image", modes[Number(range.value)]);
    const stops = element("div", "ray-save-stops");
    modes.forEach(mode => stops.append(button(mode === "none" ? "None" : mode === "both" ? "Both" : mode, () => update(node, "save_image", mode))));
    const stage = element("div", "ray-save-stage"), first = element("img"), second = element("img"), overlay = element("div", "ray-save-overlay");
    first.alt = "Image 1"; second.alt = "Image 2"; overlay.append(first);
    const divider = element("div", "ray-save-divider"), empty = element("div", "ray-save-empty", "Queue the workflow to preview images");
    const left = element("span", "ray-save-badge", "1"), right = element("span", "ray-save-badge", "2");
    left.style.left = "8px"; right.style.right = "8px";
    stage.append(second, overlay, divider, left, right, empty);
    stage.tabIndex = 0; stage.setAttribute("role", "slider"); stage.setAttribute("aria-label", "Image comparison divider");
    stage.setAttribute("aria-valuemin", "0"); stage.setAttribute("aria-valuemax", "100");
    let fraction = .5, arrays = [[], []], index = 0, comparing = false, activePointer = null;
    const batch = element("div", "ray-save-toolbar"), count = element("span", "ray-save-status");
    const previous = button("‹", () => { index--; show(); }), next = button("›", () => { index++; show(); });
    previous.setAttribute("aria-label", "Previous image pair"); next.setAttribute("aria-label", "Next image pair");
    batch.append(previous, count, next);
    function position(value) {
        fraction = Math.max(0, Math.min(1, value));
        overlay.style.clipPath = comparing ? `inset(0 ${(1 - fraction) * 100}% 0 0)` : "none";
        divider.style.left = `${fraction * 100}%`;
        stage.setAttribute("aria-valuenow", String(Math.round(fraction * 100)));
    }
    function drag(e) {
        const rect = stage.getBoundingClientRect();
        if (rect.width) position((e.clientX - rect.left) / rect.width);
    }
    stage.onpointerdown = e => { if (!comparing || e.button !== 0) return; activePointer = e.pointerId; stage.setPointerCapture(e.pointerId); drag(e); e.preventDefault(); };
    stage.onpointermove = e => { if (activePointer === e.pointerId) drag(e); };
    stage.onpointerup = stage.onpointercancel = e => { if (stage.hasPointerCapture(e.pointerId)) stage.releasePointerCapture(e.pointerId); activePointer = null; };
    stage.onlostpointercapture = () => { activePointer = null; };
    stage.onkeydown = e => {
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
        stage.setAttribute("aria-disabled", String(!comparing)); stage.style.cursor = comparing ? "ew-resize" : "default";
        empty.hidden = !!(pair[0] || pair[1]); empty.style.display = empty.hidden ? "none" : "grid";
        batch.hidden = total <= 1; batch.style.display = batch.hidden ? "none" : "flex";
        count.textContent = `${index + 1} / ${total}${!comparing && arrays[1].length ? " · Unpaired image" : ""}`;
        previous.disabled = index === 0; next.disabled = index >= total - 1;
        position(fraction);
    }
    [first, second].forEach(img => img.addEventListener("error", () => { state.textContent = "Preview expired. Queue again to refresh."; }));
    root.append(toolbar, range, stops, stage, batch, state);
    for (const event of ["pointerdown", "mousedown", "click", "dblclick", "keydown", "keyup", "wheel"]) root.addEventListener(event, e => e.stopPropagation());
    const ui = {
        root,
        sync() {
            const mode = findWidget(node, "save_image")?.value || "1";
            range.value = String(Math.max(0, modes.indexOf(mode))); range.setAttribute("aria-valuetext", mode);
            range.disabled = linked(node, "save_image");
            [...stops.children].forEach((b, i) => { b.disabled = range.disabled; b.setAttribute("aria-pressed", String(mode === modes[i])); });
            browse.disabled = recent.disabled = linked(node, "directory");
        },
        executed(message) {
            arrays = [message.ray_images_1 || [], message.ray_images_2 || []]; index = 0;
            state.textContent = message.ray_saved?.length ? `Saved ${message.ray_saved.length} PNG${message.ray_saved.length === 1 ? "" : "s"}` : "Preview only · No files saved";
            state.title = (message.ray_saved || []).join("\n");
            if (message.ray_directory?.[0]) { remember(message.ray_directory[0]); recentOptions(); }
            show();
        },
        destroy() { node._raySaveDialog?.close(); first.removeAttribute("src"); second.removeAttribute("src"); },
    };
    show(); ui.sync(); return ui;
}

app.registerExtension({
    name: "Ray.SaveImage",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== "RaySaveImage") return;
        const proto = nodeType.prototype, created = proto.onNodeCreated;
        proto.onNodeCreated = function () {
            const result = created?.apply(this, arguments); applyBucketTint(this, "VFX");
            if (!this.addDOMWidget) return result;
            this._raySave = build(this);
            for (const name of ["save_image", "save_without_metadata"]) setWidgetHidden(this, findWidget(this, name), true);
            this.addDOMWidget("ray_save_preview", "RAY_SAVE_IMAGE", this._raySave.root, {
                serialize: false, hideOnZoom: false, getMinHeight: () => 330, getMaxHeight: () => 600, getHeight: () => 380,
            });
            this.setSize?.([Math.max(this.size?.[0] || 0, 350), Math.max(this.size?.[1] || 0, 490)]);
            return result;
        };
        for (const event of ["onConfigure", "onConnectionsChange"]) {
            const prior = proto[event];
            proto[event] = function () { const result = prior?.apply(this, arguments); this._raySave?.sync(); return result; };
        }
        const executed = proto.onExecuted;
        proto.onExecuted = function (message) { const result = executed?.apply(this, arguments); this._raySave?.executed(message); return result; };
        const removed = proto.onRemoved;
        proto.onRemoved = function () { this._raySave?.destroy(); return removed?.apply(this, arguments); };
        const menu = proto.getExtraMenuOptions;
        proto.getExtraMenuOptions = function (canvas, options) {
            const result = menu?.apply(this, arguments), widget = findWidget(this, "save_without_metadata");
            options.unshift({content: `${widget?.value ? "✓ " : ""}Save without metadata`, disabled: linked(this, "save_without_metadata"),
                callback: () => update(this, "save_without_metadata", !widget?.value)});
            return result;
        };
    },
});
