import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";
import { findWidget, setWidgetHidden } from "./_common.js";
import { browsePath, notify } from "./browse_common.js";
import { installNameBuilder, openNameBuilder, resolveOnQueue } from "./save_name.js";
import { ensurePanelStyles, linkChip, registerLinkTargets } from "./ray_panel.js";

const modes = ["none", "1", "2", "both"];
const DEFAULT_PREFIX_HINT = "Ray_{date}_{counter}";
let fieldIds = 0;
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
.ray-save button,.ray-save select,.ray-save input,.ray-save-handle {pointer-events:auto}
.ray-save * {box-sizing:border-box}
.ray-save button,.ray-save select {font:inherit;color:inherit;background:#171717;border:1px solid #383838;border-radius:4px;padding:3px 6px;min-width:0}
.ray-save button:disabled {opacity:.4}
.ray-save button:hover:not(:disabled) {background:#454753}
.ray-save :focus-visible {outline:2px solid #b9a4fa;outline-offset:2px}
.ray-save-head {display:flex;flex-direction:column;gap:6px;padding:6px 6px 9px;border-bottom:1px solid #2b2b2b;flex-shrink:0}
.ray-save-label {font-size:11px;color:#a3a3a3}
.ray-save-row {display:flex;gap:6px;align-items:center;min-width:0;flex-wrap:wrap}
.ray-save-group {display:flex;gap:6px;align-items:center;flex:1 1 200px;min-width:0}
.ray-save-row.ray-save-fixed {flex-wrap:nowrap}
.ray-save-input {flex:1 1 0;width:auto;min-width:0;height:28px;padding:4px 9px;background:#141414;color:#eee;border:1px solid #3a3a3a;border-radius:5px;font:12px system-ui}
.ray-save-input::placeholder {color:#6f6f6f}
.ray-save-input:disabled {opacity:.55}
.ray-save button.ray-save-icon {flex:0 0 auto;width:32px;height:28px;padding:0;display:grid;place-items:center;font:600 13px ui-monospace,monospace}
.ray-save-icon svg {width:16px;height:16px;fill:none;stroke:currentColor;stroke-width:1.8;stroke-linejoin:round}
.ray-save-dir {font-size:11px;color:#a3a3a3;white-space:nowrap}
.ray-save-path {position:relative;flex:1 1 auto;min-width:90px;display:flex}
.ray-save-path .ray-save-input {padding-right:26px}
.ray-save-path select {position:absolute;right:1px;top:1px;bottom:1px;width:24px;padding:0;opacity:0;cursor:pointer}
.ray-save-chevron {position:absolute;right:1px;top:1px;bottom:1px;width:24px;display:grid;place-items:center;color:#9a9a9a;font-size:11px;pointer-events:none;border-left:1px solid #2c2c2c}
.ray-save-path select:disabled + .ray-save-chevron {opacity:.35}
.ray-save-stops {display:flex;flex-shrink:0;gap:0;border:1px solid #444;border-radius:5px;overflow:hidden}
.ray-save-stops button {flex:0 0 auto;height:26px;padding:3px 9px;font-size:12px;background:transparent;border:0;border-radius:0}
.ray-save-stops button + button {border-left:1px solid #2f2f2f}
.ray-save .ray-save-stops button[aria-pressed=true], .ray-save .ray-save-stops button[aria-pressed=true]:hover {background:#e2e2e2;color:#111}
.ray-save-stage {position:relative;flex:1 1 0;min-height:0;overflow:hidden;border-radius:5px;background:#000}
.ray-save-stage img {position:absolute;width:100%;height:100%;object-fit:contain;inset:0;pointer-events:none}
.ray-save-overlay {position:absolute;inset:0;pointer-events:none;background:#000}
.ray-save-divider {position:absolute;top:0;bottom:0;width:2px;background:#fff;box-shadow:0 0 2px #000;pointer-events:none}
.ray-save-handle {position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);background:#f5f3fa;color:#222;border-radius:12px;padding:8px 5px;white-space:nowrap;font:bold 13px system-ui;box-shadow:0 1px 5px #0008;cursor:ew-resize;touch-action:none}
.ray-save-empty {position:absolute;inset:0;display:flex;flex-direction:column;gap:12px;align-items:center;justify-content:center;color:#8c8c8c;text-align:center;padding:24px;pointer-events:none}
.ray-save-empty svg {width:52px;height:52px;fill:none;stroke:#5c5c5c;stroke-width:1.6;stroke-linejoin:round}
.ray-save-badge {position:absolute;top:8px;background:#111b;padding:3px 6px;border-radius:3px;pointer-events:none;font-size:10px}
.ray-save-info {position:absolute;left:6px;bottom:6px;max-width:calc(100% - 120px);display:flex;flex-direction:column;align-items:flex-start;gap:2px;pointer-events:none}
.ray-save-info > span {max-width:100%;padding:2px 5px;border-radius:3px;background:#000b;color:#ddd;font-size:10px;line-height:1.3;white-space:pre-line;overflow:hidden;text-overflow:ellipsis}
.ray-save-info > span:empty {display:none}
.ray-save-nav {position:absolute;right:6px;bottom:6px;display:flex;align-items:center;gap:3px;padding:2px;border-radius:5px;background:#000b;font-size:10px;color:#ddd}
.ray-save-nav button {padding:1px 6px}
`;
    document.head.append(css);
}

// A text field that edits a native widget: the whole edit is one undo step, and it shows when a link sets it.
function textField(node, name) {
    const input = element("input", "ray-save-input");
    input.type = "text"; input.spellcheck = false; input.autocomplete = "off";
    let editing = false;
    input.addEventListener("focus", () => { if (!editing) { node.graph?.beforeChange?.(); editing = true; } });
    input.addEventListener("input", () => {
        const widget = findWidget(node, name);
        if (!widget || linked(node, name)) return;
        widget.value = input.value; widget.callback?.(input.value);
        node.setDirtyCanvas?.(true, true);
    });
    input.addEventListener("blur", () => { if (editing) { editing = false; node.graph?.afterChange?.(); } });
    input.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === "Escape") { e.preventDefault(); input.blur(); } });
    return input;
}

// The folder button opens the system's own folder dialog (see browse_routes.py) and pastes the path.
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
    const root = element("div", "ray-save"), head = element("div", "ray-save-head");
    // Filename prefix, with { } opening the filename builder.
    const prefixLabel = element("label", "ray-save-label", "Filename prefix");
    const prefix = textField(node, "filename_prefix");
    prefix.id = `ray-save-prefix-${++fieldIds}`; prefixLabel.htmlFor = prefix.id;
    const tokens = button("{ }", () => openNameBuilder(node));
    tokens.className = "ray-save-icon"; tokens.title = "Build the filename from tokens: date, counter, hash, widget values…";
    tokens.setAttribute("aria-label", "Build filename");
    const prefixRow = element("div", "ray-save-row ray-save-fixed");
    // A linked field shows where its value comes from, with a button to unlink it.
    const prefixLink = linkChip(node, "filename_prefix", () => ui.sync());
    prefixRow.append(prefix, tokens, prefixLink.element);
    // Save choice, then the directory: folder dialog, path, and the last three save folders in a drop-down.
    const stops = element("div", "ray-save-stops");
    stops.setAttribute("role", "group"); stops.setAttribute("aria-label", "Save Image");
    modes.forEach(mode => stops.append(button(mode === "none" ? "None" : mode === "both" ? "Both" : mode, () => update(node, "save_image", mode))));
    const dirLabel = element("label", "ray-save-dir", "Directory");
    const browse = button("", () => browseFolder(node));
    browse.className = "ray-save-icon"; browse.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 6.5h6l2 2h10v10H3z"/></svg>';
    browse.title = "Choose the save folder"; browse.setAttribute("aria-label", "Choose the save folder");
    const directory = textField(node, "directory");
    directory.id = `ray-save-dir-${fieldIds}`; dirLabel.htmlFor = directory.id;
    const recent = element("select"); recent.title = "Last three save folders"; recent.setAttribute("aria-label", "Recent save folders");
    function recentOptions() {
        const paths = history();
        recent.replaceChildren(element("option", "", ""), ...paths.map(p => { const o = element("option", "", p); o.value = p; return o; }));
        recent.selectedIndex = 0;
        recent.title = paths.length ? "Last three save folders" : "No save folders yet";
    }
    recentOptions();
    recent.addEventListener("pointerdown", recentOptions);
    recent.onchange = () => { if (recent.selectedIndex > 0) update(node, "directory", recent.value); recent.selectedIndex = 0; };
    const path = element("div", "ray-save-path");
    path.append(directory, recent, element("span", "ray-save-chevron", "▾"));
    const group = element("div", "ray-save-group");
    const directoryLink = linkChip(node, "directory", () => ui.sync());
    group.append(dirLabel, browse, path, directoryLink.element);
    const row = element("div", "ray-save-row");
    row.append(stops, group);
    head.append(prefixLabel, prefixRow, row);
    const state = element("span", "ray-save-status");
    const stage = element("div", "ray-save-stage"), first = element("img"), second = element("img"), overlay = element("div", "ray-save-overlay");
    first.alt = "Image 1"; second.alt = "Image 2"; overlay.append(first);
    const divider = element("div", "ray-save-divider"), handle = element("span", "ray-save-handle", "‹ ›"), empty = element("div", "ray-save-empty");
    empty.innerHTML = '<svg viewBox="0 0 48 48" aria-hidden="true"><rect x="5" y="7" width="38" height="34" rx="3"/><circle cx="17" cy="17" r="3.5"/><path d="M5 35l11-11 9 9 6-6 12 12"/></svg>';
    empty.append(element("span", "", "Queue the workflow to preview images"));
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
        empty.hidden = !!(pair[0] || pair[1]); empty.style.display = empty.hidden ? "none" : "flex";
        batch.hidden = total <= 1; batch.style.display = batch.hidden ? "none" : "flex";
        count.textContent = `${index + 1} / ${total}${!comparing && arrays[1].length ? " · Unpaired image" : ""}`;
        previous.disabled = index === 0; next.disabled = index >= total - 1;
        position(fraction);
        updateSizes();
    }
    [first, second].forEach(img => img.addEventListener("error", () => { state.textContent = "Preview expired. Queue again to refresh."; }));
    root.append(head, stage);
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
        // Typing in a field belongs to the field, never to canvas shortcuts.
        if (e.target instanceof HTMLInputElement) { e.stopPropagation(); return; }
        if (e.ctrlKey || e.metaKey || e.altKey || e.code === "Space" || e.key === " ") return;
        if (e.defaultPrevented || ["Enter", "ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", "Home", "End"].includes(e.key)) e.stopPropagation();
    });
    const ui = {
        root,
        sync() {
            const mode = findWidget(node, "save_image")?.value || "1";
            [...stops.children].forEach((b, i) => { b.disabled = linked(node, "save_image"); b.setAttribute("aria-pressed", String(mode === modes[i])); });
            const prefixLinked = prefixLink.update(), directoryLinked = directoryLink.update();
            prefix.style.display = tokens.style.display = prefixLinked ? "none" : "";
            browse.style.display = path.style.display = directoryLinked ? "none" : "";
            for (const [input, name, hint] of [[prefix, "filename_prefix", DEFAULT_PREFIX_HINT], [directory, "directory", "/output"]]) {
                input.placeholder = hint;
                if (document.activeElement !== input) input.value = String(findWidget(node, name)?.value ?? "");
            }
            recent.disabled = !history().length;
        },
        executed(message) {
            arrays = [message.ray_images_1 || [], message.ray_images_2 || []]; index = 0;
            state.textContent = message.ray_saved?.length ? `Saved ${message.ray_saved.length} PNG${message.ray_saved.length === 1 ? "" : "s"}` : "Preview only · No files saved";
            state.title = (message.ray_saved || []).join("\n");
            if (message.ray_directory?.[0]) { remember(message.ray_directory[0]); recentOptions(); }
            show();
        },
        destroy() { navigation.abort(); unregister(); first.removeAttribute("src"); second.removeAttribute("src"); },
    };
    // Drag a link onto the prefix or the directory to connect it.
    ensurePanelStyles();
    const unregister = registerLinkTargets(node, [{ name: "filename_prefix", element: prefixRow }, { name: "directory", element: group }], () => ui.sync());
    show(); ui.sync(); return ui;
}

app.registerExtension({
    name: "Ray.SaveImage",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== "RaySaveImage") return;
        const proto = nodeType.prototype, created = proto.onNodeCreated;
        proto.onNodeCreated = function () {
            const result = created?.apply(this, arguments); this.color = this.bgcolor = "#000000";
            if (!this.addDOMWidget) { installNameBuilder(this); return result; }
            resolveOnQueue(this);
            this._raySave = build(this);
            for (const name of ["save_image", "save_without_metadata", "filename_prefix", "directory"]) setWidgetHidden(this, findWidget(this, name), true);
            this.addDOMWidget("ray_save_preview", "RAY_SAVE_IMAGE", this._raySave.root, {
                serialize: false, hideOnZoom: false, getMinHeight: () => 230, getHeight: () => 380,
            });
            this.setSize?.([Math.max(this.size?.[0] || 0, 420), Math.max(this.size?.[1] || 0, 480)]);
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
        proto.onRemoved = function () { this._raySave?.destroy(); this._rayNameBuilder?.close(); return removed?.apply(this, arguments); };
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
