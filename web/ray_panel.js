import { app } from "../../scripts/app.js";
import { setWidgetHidden } from "./_common.js";
import { installLegacyLinkLayout } from "./legacy_panel_links.js";
import { browsePath, notify } from "./browse_common.js";

// The Ray panel: every Ray node draws its controls in one black, compact panel, in the style of Save Image
// (see UI.md for the design rules). The node's native widgets stay the source of truth (values, saving,
// queueing, links); they are hidden and the panel edits them. A layout (`spec`) names the rows; any widget
// it does not mention is still shown, at the end, so nothing can go missing.
//
// Every row is also a link target: drag a link from another node onto a row and it connects to that input.
// A linked row shows where its value comes from, with a button to unlink it.

export const ICONS = {
    folder: '<svg viewBox="0 0 24 24"><path d="M3 6.5h6l2 2h10v10H3z"/></svg>',
    file: '<svg viewBox="0 0 24 24"><path d="M6 3h8l4 4v14H6z"/><path d="M14 3v4h4"/></svg>',
    refresh: '<svg viewBox="0 0 24 24"><path d="M19 8a7.5 7.5 0 1 0 1.2 6"/><path d="M19.5 3.5V8H15"/></svg>',
    edit: '<svg viewBox="0 0 24 24"><path d="M4 20h4L19 9l-4-4L4 16z"/><path d="M13.5 6.5l4 4"/></svg>',
    unlink: '<svg viewBox="0 0 24 24"><path d="M6 6l12 12M18 6L6 18"/></svg>',
    minus: '<svg viewBox="0 0 24 24"><path d="M6 12h12"/></svg>',
    plus: '<svg viewBox="0 0 24 24"><path d="M6 12h12M12 6v12"/></svg>',
    randomize: '<svg viewBox="0 0 24 24"><rect x="4" y="4" width="16" height="16" rx="3"/><circle cx="9" cy="9" r=".6"/><circle cx="15" cy="15" r=".6"/><circle cx="15" cy="9" r=".6"/><circle cx="9" cy="15" r=".6"/></svg>',
    fixed: '<svg viewBox="0 0 24 24"><rect x="5" y="11" width="14" height="9" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/></svg>',
    increment: '<svg viewBox="0 0 24 24"><path d="M12 19V5M6 11l6-6 6 6"/></svg>',
    decrement: '<svg viewBox="0 0 24 24"><path d="M12 5v14M6 13l6 6 6-6"/></svg>',
    link: '<svg viewBox="0 0 24 24"><path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1"/><path d="M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/></svg>',
};
const SEED_MODES = { fixed: "Keep this seed after each run", increment: "Add 1 after each run", decrement: "Subtract 1 after each run", randomize: "New random seed after each run" };
const MODE_PREFIX = /^(local|dexter|civitai)__/;

const el = (tag, className, text) => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
};
export function iconButton(icon, title, onClick, { label } = {}) {
    const b = el("button", "rp-icon");
    b.type = "button";
    b.title = title;
    b.setAttribute("aria-label", title);
    if (label) b.textContent = label; else b.innerHTML = ICONS[icon] || "";
    b.addEventListener("click", event => { event.stopPropagation(); onClick(event); });
    return b;
}

// How an option reads: the layout's label, or a snake_case value written out ("error_diffusion" -> "Error diffusion").
export function optionLabel(v, field) {
    if (field?.labels && Object.hasOwn(field.labels, v)) return field.labels[v];
    const s = String(v);
    return /^[a-z][a-z0-9]*(_[a-z0-9]+)*$/.test(s) ? (s.charAt(0).toUpperCase() + s.slice(1)).replace(/_/g, " ") : s;
}

export function humanize(name) {
    const text = String(name).replace(MODE_PREFIX, "").replace(/_/g, " ").trim();
    return text.charAt(0).toUpperCase() + text.slice(1);
}

export const PANEL_CSS = `
.dom-widget:has(> .rp-host) {pointer-events:none !important}
.rp-host {width:100%;height:100%;overflow:hidden;pointer-events:none}
.rp {box-sizing:border-box;width:100%;padding:6px 6px 8px;display:flex;flex-direction:column;gap:6px;background:#000;color:#eee;font:12px system-ui,sans-serif;color-scheme:dark;pointer-events:none;border-radius:8px}
.rp * {box-sizing:border-box}
.rp[hidden], .rp-row[hidden], .rp-section[hidden] {display:none !important}
.rp-section {display:flex;flex-direction:column;gap:6px;min-width:0}
.rp-section:not([hidden]) ~ .rp-section:not([hidden]) {border-top:1px solid #2b2b2b;padding-top:8px}
.rp-title {font:600 10px system-ui,sans-serif;letter-spacing:.08em;text-transform:uppercase;color:#d43aa8}
.rp-row {display:grid;grid-template-columns:minmax(64px,34%) minmax(0,1fr);gap:8px;align-items:center;min-height:28px;border-radius:5px;position:relative}
.rp-row.rp-full {grid-template-columns:minmax(0,1fr);gap:4px}
.rp-row.rp-bool {grid-template-columns:minmax(0,1fr) auto}
.rp-label {font-size:11px;color:#a3a3a3;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.rp-control {display:flex;gap:6px;align-items:center;min-width:0;pointer-events:auto}
.rp-input, .rp-select, .rp-textarea {flex:1 1 0;width:auto;min-width:0;height:28px;padding:4px 9px;background:#141414;color:#eee;border:1px solid #3a3a3a;border-radius:5px;font:12px system-ui,sans-serif}
.rp-input::placeholder, .rp-textarea::placeholder {color:#6f6f6f}
.rp-textarea {height:auto;min-height:64px;padding:6px 9px;line-height:1.4;resize:none;font-family:system-ui,sans-serif}
.rp-select {appearance:none;-webkit-appearance:none;padding-right:26px;cursor:pointer;
  background-image:linear-gradient(45deg,transparent 50%,#9a9a9a 50%),linear-gradient(135deg,#9a9a9a 50%,transparent 50%);
  background-position:calc(100% - 13px) 12px,calc(100% - 9px) 12px;background-size:4px 4px;background-repeat:no-repeat}
.rp-select option {background:#141414;color:#eee}
.rp :is(.rp-input,.rp-select,.rp-textarea):disabled {opacity:.55}
.rp :focus-visible {outline:2px solid #b9a4fa;outline-offset:1px}
.rp button {font:inherit;color:inherit;background:#171717;border:1px solid #383838;border-radius:5px;cursor:pointer}
.rp button:hover:not(:disabled) {background:#454753}
.rp button:disabled {opacity:.4;cursor:default}
.rp .rp-icon {flex:0 0 auto;width:32px;height:28px;padding:0;display:grid;place-items:center;font:600 13px ui-monospace,monospace}
.rp-icon svg {width:16px;height:16px;fill:none;stroke:currentColor;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round}
.rp-seg {display:flex;flex:0 1 auto;min-width:0;border:1px solid #444;border-radius:5px;overflow:hidden}
.rp .rp-seg button {flex:1 1 auto;min-width:0;height:26px;padding:3px 8px;font-size:12px;background:transparent;border:0;border-radius:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.rp .rp-seg button + button {border-left:1px solid #2f2f2f}
.rp .rp-seg button[aria-pressed=true], .rp .rp-seg button[aria-pressed=true]:hover {background:#e2e2e2;color:#111}
.rp-number {display:flex;flex:1 1 0;min-width:0;height:28px;border:1px solid #3a3a3a;border-radius:5px;background:#141414;overflow:hidden}
.rp-number .rp-input {border:0;border-radius:0;background:transparent;text-align:center;padding:4px 2px;cursor:ew-resize}
.rp-number .rp-input:focus {cursor:text}
.rp .rp-number button {flex:0 0 24px;height:100%;padding:0;border:0;border-radius:0;background:transparent;color:#9a9a9a;display:grid;place-items:center}
.rp .rp-number button:hover:not(:disabled) {background:#2a2a2a;color:#eee}
.rp-number button svg {width:12px;height:12px;fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round}
.rp-slider {display:flex;flex:1 1 0;min-width:0;gap:8px;align-items:center}
.rp-track {position:relative;flex:1 1 0;min-width:40px;height:28px;cursor:pointer;touch-action:none}
.rp-track::before {content:"";position:absolute;left:0;right:0;top:13px;height:3px;border-radius:2px;background:#2c2c2c}
.rp-fill {position:absolute;left:0;top:13px;height:3px;border-radius:2px;background:#d6d6d6}
.rp-thumb {position:absolute;top:8px;width:13px;height:13px;margin-left:-6.5px;border-radius:50%;background:#eee;box-shadow:0 0 0 3px #000}
.rp-slider .rp-input {flex:0 0 58px;text-align:right;padding:4px 7px}
.rp .rp-toggle {position:relative;flex:0 0 auto;width:34px;height:18px;padding:0;border-radius:9px;background:#2a2a2a;border:1px solid #444}
.rp .rp-toggle::after {content:"";position:absolute;top:2px;left:2px;width:12px;height:12px;border-radius:50%;background:#8a8a8a;transition:left .12s}
.rp .rp-toggle[aria-checked=true] {background:#e2e2e2;border-color:#e2e2e2}
.rp .rp-toggle[aria-checked=true]::after {left:18px;background:#111}
.rp .rp-toggle:hover:not(:disabled) {background:#3a3a3a}
.rp .rp-toggle[aria-checked=true]:hover:not(:disabled) {background:#fff}
.rp-link .rp-unlink {width:22px;height:22px;border:0;background:transparent;color:#9a9a9a;display:grid;place-items:center;padding:0;border-radius:4px;cursor:pointer}
.rp-link .rp-unlink:hover {background:#2a2a2a;color:#eee}
.rp-link {display:flex;flex:1 1 0;min-width:0;align-items:center;gap:6px;height:28px;padding:0 4px 0 9px;border:1px dashed #4a4a4a;border-radius:5px;color:#bdbdbd;font-size:11px}
.rp-link span {flex:1 1 0;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.rp-link svg {width:13px;height:13px;flex:0 0 auto;fill:none;stroke:currentColor;stroke-width:1.8;stroke-linecap:round}
.rp .rp-link button {width:22px;height:22px;border:0;background:transparent;color:#9a9a9a;display:grid;place-items:center;padding:0}
.rp-swatch {flex:0 0 32px;width:32px;height:28px;padding:2px;border:1px solid #3a3a3a;border-radius:5px;background:#141414;cursor:pointer}
.rp-swatch::-webkit-color-swatch-wrapper {padding:0}
.rp-swatch::-webkit-color-swatch {border:0;border-radius:3px}
.rp-summary {flex:1 1 0;min-width:0;color:#d0d0d0;font-size:12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.rp-status {font-size:11px;color:#9a9a9a;min-height:14px;overflow-wrap:anywhere}
.rp-status:empty {display:none}
.rp-row[data-drop=ok] {box-shadow:0 0 0 1px #6b5a2a}
.rp-row[data-drop=over] {box-shadow:0 0 0 2px #e5b567;background:#1c1a14}
`;

export function ensurePanelStyles() { injectStyles(); }

// A "From <node> · <output>" chip with an unlink button, for interfaces that lay out their own fields.
export function linkChip(node, name, changed) {
    const box = el("div", "rp-link");
    box.innerHTML = ICONS.link;
    const text = el("span");
    const unlink = el("button", "rp-unlink");
    unlink.type = "button"; unlink.title = "Unlink this input"; unlink.setAttribute("aria-label", unlink.title);
    unlink.innerHTML = ICONS.unlink;
    unlink.addEventListener("click", event => {
        event.stopPropagation();
        const info = linkOf(node, name);
        if (!info) return;
        node.graph?.beforeChange?.();
        try { node.disconnectInput(info.slot); } finally { node.graph?.afterChange?.(); }
        changed?.();
    });
    box.append(text, unlink);
    return {
        element: box,
        update() {
            const info = linkOf(node, name);
            box.style.display = info ? "flex" : "none";
            if (info) text.textContent = `From ${info.origin?.title || info.origin?.type || "a link"}${info.output ? ` · ${info.output}` : ""}`;
            return !!info;
        },
    };
}

// Lets an interface with its own layout take dropped links: `rows` are [{ name, element }].
export function registerLinkTargets(node, rows, refresh) {
    const target = { node, rows: rows.map(r => ({ ...r, element: r.element })), refresh };
    const restoreLayout = installLegacyLinkLayout(node, target.rows, () => app.canvas);
    livePanels.add(target);
    return () => { restoreLayout(); livePanels.delete(target); };
}

function injectStyles() {
    if (document.getElementById("ray-panel-style")) return;
    const style = el("style");
    style.id = "ray-panel-style";
    style.textContent = PANEL_CSS;
    document.head.append(style);
}

// ---------------------------------------------------------------------------
// Links: a row is a drop target for a link dragged towards an input
// ---------------------------------------------------------------------------

const livePanels = new Set();
const inputIndex = (node, name) => node.inputs?.findIndex(input => input.widget?.name === name || (input.name === name && input.widget)) ?? -1;
export function linkOf(node, name) {
    const at = inputIndex(node, name);
    const id = at >= 0 ? node.inputs[at].link : null;
    if (id == null) return null;
    const link = node.graph?.links?.get?.(id) ?? node.graph?.links?.[id];
    const origin = link ? node.graph.getNodeById?.(link.origin_id) : null;
    return { slot: at, origin, output: origin?.outputs?.[link?.origin_slot]?.name };
}
const insideRect = (element, event) => {
    if (!element?.isConnected) return false;
    const r = element.getBoundingClientRect();
    return r.width > 0 && event.clientX >= r.left && event.clientX <= r.right && event.clientY >= r.top && event.clientY <= r.bottom;
};
let hovered = null;
function dropTargets(event) {
    const lc = app?.canvas?.linkConnector;
    const active = !!lc?.isConnecting && lc.state?.connectingTo === "input";
    hovered = null;
    for (const panel of livePanels) {
        for (const row of panel.rows) {
            if (!row.name || row.element.hidden) { row.element.removeAttribute("data-drop"); continue; }
            const at = active ? inputIndex(panel.node, row.name) : -1;
            const ok = at >= 0 && lc.renderLinks.some(link => link.canConnectToInput?.(panel.node, panel.node.inputs[at]));
            if (!ok) { row.element.removeAttribute("data-drop"); continue; }
            const over = event && insideRect(row.element, event);
            row.element.dataset.drop = over ? "over" : "ok";
            if (over) hovered = { panel, row, at };
        }
    }
}
if (typeof window !== "undefined") {
    window.addEventListener("pointermove", event => { if (livePanels.size) dropTargets(event); }, true);
    window.addEventListener("pointerup", event => {
        if (!livePanels.size) return;
        dropTargets(event);
        const lc = app?.canvas?.linkConnector, target = hovered;
        for (const panel of livePanels) for (const row of panel.rows) row.element.removeAttribute("data-drop");
        hovered = null;
        if (!target || !lc?.isConnecting) return;
        const { panel, at } = target, input = panel.node.inputs[at];
        const links = lc.renderLinks.filter(link => link.canConnectToInput?.(panel.node, input));
        if (!links.length) return;
        panel.node.graph?.beforeChange?.();
        try { for (const link of links) link.connectToInput(panel.node, input, lc.events); }
        finally { panel.node.graph?.afterChange?.(); }
        lc.reset();
        app.canvas.setDirty?.(true, true);
        panel.refresh();
    }, true);
}

// ---------------------------------------------------------------------------
// Controls
// ---------------------------------------------------------------------------

const stepOf = widget => Number(widget.options?.step2 ?? widget.options?.round ?? 1) || 1;
const precisionOf = widget => Number.isFinite(widget.options?.precision) ? widget.options.precision : (stepOf(widget) < 1 ? 2 : 0);
function clampNumber(widget, value) {
    const { min, max } = widget.options || {};
    let v = Number(value);
    if (!Number.isFinite(v)) return null;
    const step = stepOf(widget), digits = precisionOf(widget);
    if (step > 0) v = Math.round(v / step) * step;
    if (Number.isFinite(min)) v = Math.max(min, v);
    if (Number.isFinite(max)) v = Math.min(max, v);
    return Number(v.toFixed(digits));
}
const formatNumber = (widget, value) => {
    const v = Number(value);
    return Number.isFinite(v) ? v.toFixed(precisionOf(widget)) : String(value ?? "");
};
const valuesOf = widget => {
    const values = widget.options?.values;
    const list = typeof values === "function" ? values(widget) : values;
    return Array.isArray(list) ? list : [];
};

// Typing in the panel belongs to the panel, never to canvas shortcuts.
function isolateKeys(element) {
    for (const type of ["keydown", "keyup", "keypress"]) element.addEventListener(type, event => event.stopPropagation());
}

export function installPanel(node, spec = {}) {
    injectStyles();
    const panelKey = spec.settings ? "_raySettingsPanel" : "_rayPanel";
    if (node[panelKey]) return node[panelKey];
    // ComfyUI stretches the element it is given to the height it reserves, so the panel content sits in a host
    // and is measured on its own; measuring the stretched element would feed its height back into itself.
    const host = el("div", "rp-host");
    const root = el("div", "rp");
    host.append(root);
    const rows = [];
    const panel = { node, root, rows, refresh, schedule, fit, destroy, widgetEl: null };
    const mentioned = new Set([...(spec.skip || []), "control_after_generate"]);

    // ---- editing a native widget ----------------------------------------------------------------------
    let editing = false;
    const begin = () => { if (!editing) { node.graph?.beforeChange?.(); editing = true; } };
    const end = () => { if (editing) { editing = false; node.graph?.afterChange?.(); } };
    function write(widget, value, { history = true } = {}) {
        if (!widget || Object.is(widget.value, value)) return;
        if (history && !editing) node.graph?.beforeChange?.();
        try {
            widget.value = value;
            widget.callback?.(value, app.canvas, node, undefined, undefined);
        } finally { if (history && !editing) node.graph?.afterChange?.(); }
        node.setDirtyCanvas?.(true, true);
        schedule();
    }
    panel.write = write;

    // ---- one row per field ---------------------------------------------------------------------------
    function makeRow(field) {
        if (field.custom) {
            const content = field.custom(panel);
            const own = content.classList?.contains("rp-row");
            const row = { custom: true, when: field.when, element: own ? content : el("div", "rp-row rp-full") };
            if (!own) row.element.append(content);
            row.update = field.update || (() => {});
            return row;
        }
        const widget = node.widgets?.find(w => w.name === field.name);
        if (!widget) return null;
        mentioned.add(widget.name);
        const kind = field.kind || detectKind(widget, field);
        const full = field.full ?? (["textarea", "path"].includes(kind) && field.labelAbove !== false);
        const row = { name: widget.name, widget, when: field.when, kind, element: el("div", `rp-row${full ? " rp-full" : ""}${kind === "toggle" ? " rp-bool" : ""}`) };
        const label = el("label", "rp-label", field.label || humanize(widget.name));
        label.title = widget.tooltip || widget.options?.tooltip || widget.name;
        const control = el("div", "rp-control");
        row.element.append(label, control);
        const linkBox = el("div", "rp-link");
        linkBox.innerHTML = ICONS.link;
        const linkText = el("span");
        const unlink = iconButton("unlink", "Unlink this input", () => {
            const info = linkOf(node, widget.name);
            if (!info) return;
            node.graph?.beforeChange?.();
            try { node.disconnectInput(info.slot); } finally { node.graph?.afterChange?.(); }
            schedule();
        });
        linkBox.append(linkText, unlink);
        const editor = buildControl(kind, widget, field, row);
        control.append(editor.element, linkBox, ...(field.actions || []).map(action => {
            const b = iconButton(action.icon, action.title, () => action.onClick(panel), { label: action.label });
            row.actions = [...(row.actions || []), b];
            return b;
        }));
        if (editor.focusable) label.htmlFor = editor.focusable.id = `rp-${node.id}-${widget.name}`.replace(/[^\w-]/g, "_");
        row.update = () => {
            const info = linkOf(node, widget.name);
            editor.element.hidden = !!info;
            editor.element.style.display = info ? "none" : "";
            linkBox.hidden = !info;
            linkBox.style.display = info ? "flex" : "none";
            for (const b of row.actions || []) b.disabled = !!info;
            if (info) linkText.textContent = `From ${info.origin?.title || info.origin?.type || "a link"}${info.output ? ` · ${info.output}` : ""}`;
            else editor.update();
        };
        return row;
    }

    function detectKind(widget, field) {
        const type = widget._rayOrigType || widget.type;
        if (field.browse) return "path";
        if (type === "toggle") return "toggle";
        if (type === "customtext") return "textarea";
        if (type === "combo") {
            const values = valuesOf(widget);
            return values.length >= 2 && values.length <= 4 && values.every(v => String(v).length <= 9) ? "segment" : "select";
        }
        if (type === "number") {
            if ((widget.linkedWidgets || []).some(w => w.name === "control_after_generate")) return "seed";
            const { min, max } = widget.options || {};
            return Number.isFinite(min) && Number.isFinite(max) && max - min <= 10 && precisionOf(widget) > 0 ? "slider" : "number";
        }
        return "text";
    }

    function textInput(widget, field, multiline = false) {
        const input = el(multiline ? "textarea" : "input", multiline ? "rp-textarea" : "rp-input");
        if (!multiline) input.type = "text";
        else input.rows = field.rows || 4;
        input.spellcheck = !!multiline;
        input.autocomplete = "off";
        if (field.placeholder) input.placeholder = field.placeholder;
        isolateKeys(input);
        input.addEventListener("focus", begin);
        input.addEventListener("input", () => write(widget, input.value, { history: false }));
        input.addEventListener("blur", end);
        if (!multiline) input.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === "Escape") { e.preventDefault(); input.blur(); } });
        return input;
    }

    function numberInput(widget, onCommit) {
        const input = el("input", "rp-input");
        input.type = "text"; input.inputMode = "decimal"; input.autocomplete = "off";
        isolateKeys(input);
        const commit = () => {
            const v = clampNumber(widget, input.value);
            if (v === null) { input.value = formatNumber(widget, widget.value); return; }
            onCommit(v);
            input.value = formatNumber(widget, widget.value);
        };
        input.addEventListener("change", commit);
        input.addEventListener("keydown", e => {
            if (e.key === "Enter") { e.preventDefault(); commit(); input.blur(); }
            else if (e.key === "Escape") { e.preventDefault(); input.value = formatNumber(widget, widget.value); input.blur(); }
            else if (e.key === "ArrowUp" || e.key === "ArrowDown") {
                e.preventDefault();
                const step = stepOf(widget) * (e.shiftKey ? 10 : 1) * (e.key === "ArrowUp" ? 1 : -1);
                const v = clampNumber(widget, Number(widget.value) + step);
                if (v !== null) { onCommit(v); input.value = formatNumber(widget, v); }
            }
        });
        // Drag sideways on the number to scrub it; a click without moving types.
        let scrub = null;
        input.addEventListener("pointerdown", e => {
            if (document.activeElement === input || e.button !== 0) return;
            e.preventDefault();
            scrub = { id: e.pointerId, x: e.clientX, start: Number(widget.value) || 0, moved: false };
            try { input.setPointerCapture(e.pointerId); } catch { /* the pointer is gone */ }
        });
        input.addEventListener("pointermove", e => {
            if (!scrub || e.pointerId !== scrub.id) return;
            const dx = e.clientX - scrub.x;
            if (!scrub.moved && Math.abs(dx) < 3) return;
            if (!scrub.moved) { scrub.moved = true; node.graph?.beforeChange?.(); }
            const v = clampNumber(widget, scrub.start + Math.round(dx / 6) * stepOf(widget) * (e.shiftKey ? 0.1 : 1));
            if (v !== null) { write(widget, v, { history: false }); input.value = formatNumber(widget, v); }
        });
        const stop = e => {
            if (!scrub || (e.pointerId != null && e.pointerId !== scrub.id)) return;
            const moved = scrub.moved;
            scrub = null;
            if (moved) node.graph?.afterChange?.();
            else { input.focus(); input.select(); }
        };
        for (const type of ["pointerup", "pointercancel"]) input.addEventListener(type, stop);
        return input;
    }

    function buildControl(kind, widget, field, row) {
        if (kind === "toggle") {
            const button = el("button", "rp-toggle");
            button.type = "button"; button.setAttribute("role", "switch");
            button.addEventListener("click", () => write(widget, !widget.value));
            return { element: button, focusable: button, update() { button.setAttribute("aria-checked", String(!!widget.value)); } };
        }
        if (kind === "segment") {
            const group = el("div", "rp-seg");
            group.setAttribute("role", "group");
            let signature = "";
            return { element: group, update() {
                const values = valuesOf(widget), sig = values.join("\u0001");
                if (sig !== signature) {
                    signature = sig;
                    group.replaceChildren(...values.map(v => {
                        const b = el("button", "", optionLabel(v, field));
                        b.type = "button"; b.title = String(v);
                        b.addEventListener("click", () => write(widget, v));
                        return b;
                    }));
                }
                [...group.children].forEach((b, i) => b.setAttribute("aria-pressed", String(values[i] === widget.value)));
            } };
        }
        if (kind === "select") {
            const select = el("select", "rp-select");
            isolateKeys(select);
            let signature = "";
            select.addEventListener("change", () => {
                const values = valuesOf(widget);
                write(widget, values[select.selectedIndex] ?? select.value);
            });
            return { element: select, focusable: select, update() {
                const values = valuesOf(widget), sig = values.join("\u0001");
                if (sig !== signature) {
                    signature = sig;
                    select.replaceChildren(...values.map(v => { const o = el("option", "", optionLabel(v, field)); o.value = String(v); return o; }));
                }
                const at = values.findIndex(v => v === widget.value || String(v) === String(widget.value));
                if (at >= 0) select.selectedIndex = at;
                select.title = String(widget.value ?? "");
            } };
        }
        if (kind === "color") {
            const wrap = el("div", "rp-control");
            wrap.style.flex = "1 1 0";
            const swatch = el("input", "rp-swatch");
            swatch.type = "color";
            swatch.title = "Pick a color";
            const input = textInput(widget, { placeholder: "#rrggbb", ...field });
            swatch.addEventListener("focus", begin);
            swatch.addEventListener("input", () => write(widget, swatch.value, { history: false }));
            swatch.addEventListener("change", end);
            swatch.addEventListener("blur", end);
            wrap.append(swatch, input);
            return { element: wrap, focusable: input, update() {
                const text = String(widget.value ?? "");
                if (document.activeElement !== input) input.value = text;
                if (/^#[0-9a-f]{6}$/i.test(text) && document.activeElement !== swatch) swatch.value = text.toLowerCase();
            } };
        }
        if (kind === "textarea") {
            const area = textInput(widget, field, true);
            return { element: area, focusable: area, update() { if (document.activeElement !== area) area.value = String(widget.value ?? ""); } };
        }
        if (kind === "path") {
            const wrap = el("div", "rp-control");
            wrap.style.flex = "1 1 0";
            const input = textInput(widget, { placeholder: field.placeholder ?? (field.browse?.kind === "file" ? "Path to a file" : "Path to a folder"), ...field });
            const { kind: pick = "folder", title, filters } = field.browse || {};
            const browse = iconButton(pick === "file" ? "file" : "folder", pick === "file" ? "Choose a file" : "Choose a folder", async () => {
                try {
                    const picked = await browsePath(pick, String(widget.value ?? ""), { title, filters });
                    if (picked) write(widget, picked);
                } catch (error) { notify(error.message); }
            });
            wrap.append(input, browse);
            return { element: wrap, focusable: input, update() { if (document.activeElement !== input) input.value = String(widget.value ?? ""); } };
        }
        if (kind === "slider") {
            const wrap = el("div", "rp-slider"), track = el("div", "rp-track"), fill = el("div", "rp-fill"), thumb = el("div", "rp-thumb");
            track.append(fill, thumb);
            track.setAttribute("role", "slider");
            track.tabIndex = 0;
            const input = numberInput(widget, v => write(widget, v));
            const { min, max } = widget.options;
            const fraction = () => (Number(widget.value) - min) / (max - min || 1);
            const fromEvent = e => { const r = track.getBoundingClientRect(); return min + Math.max(0, Math.min(1, (e.clientX - r.left) / (r.width || 1))) * (max - min); };
            let drag = null;
            track.addEventListener("pointerdown", e => {
                if (e.button !== 0) return;
                e.preventDefault(); e.stopPropagation();
                drag = e.pointerId;
                try { track.setPointerCapture(e.pointerId); } catch { /* gone */ }
                node.graph?.beforeChange?.();
                const v = clampNumber(widget, fromEvent(e));
                if (v !== null) write(widget, v, { history: false });
            });
            track.addEventListener("pointermove", e => {
                if (drag !== e.pointerId) return;
                const v = clampNumber(widget, fromEvent(e));
                if (v !== null) write(widget, v, { history: false });
            });
            const stop = e => { if (drag === null || (e.pointerId != null && e.pointerId !== drag)) return; drag = null; node.graph?.afterChange?.(); };
            for (const type of ["pointerup", "pointercancel"]) track.addEventListener(type, stop);
            isolateKeys(track);
            track.addEventListener("keydown", e => {
                const delta = { ArrowRight: 1, ArrowUp: 1, ArrowLeft: -1, ArrowDown: -1 }[e.key];
                if (!delta && e.key !== "Home" && e.key !== "End") return;
                e.preventDefault();
                const target = e.key === "Home" ? min : e.key === "End" ? max : Number(widget.value) + delta * stepOf(widget) * (e.shiftKey ? 10 : 1);
                const v = clampNumber(widget, target);
                if (v !== null) write(widget, v);
            });
            wrap.append(track, input);
            return { element: wrap, focusable: input, update() {
                const f = Math.max(0, Math.min(1, fraction()));
                fill.style.width = `${f * 100}%`;
                thumb.style.left = `${f * 100}%`;
                track.setAttribute("aria-valuenow", String(widget.value));
                track.setAttribute("aria-valuemin", String(min)); track.setAttribute("aria-valuemax", String(max));
                if (document.activeElement !== input) input.value = formatNumber(widget, widget.value);
            } };
        }
        if (kind === "number" || kind === "seed") {
            const wrap = el("div", "rp-control");
            wrap.style.flex = "1 1 0";
            const box = el("div", "rp-number");
            const input = numberInput(widget, v => write(widget, v));
            const nudge = sign => {
                const v = clampNumber(widget, Number(widget.value) + sign * stepOf(widget));
                if (v !== null) write(widget, v);
            };
            const minus = el("button"); minus.type = "button"; minus.innerHTML = ICONS.minus; minus.setAttribute("aria-label", "Decrease"); minus.tabIndex = -1;
            const plus = el("button"); plus.type = "button"; plus.innerHTML = ICONS.plus; plus.setAttribute("aria-label", "Increase"); plus.tabIndex = -1;
            minus.addEventListener("click", e => { e.stopPropagation(); nudge(-1); });
            plus.addEventListener("click", e => { e.stopPropagation(); nudge(1); });
            box.append(minus, input, plus);
            wrap.append(box);
            let after = null;
            const control = (widget.linkedWidgets || []).find(w => w.name === "control_after_generate");
            if (kind === "seed" && control) {
                after = iconButton("randomize", "", () => {
                    const values = valuesOf(control);
                    const next = values[(values.indexOf(control.value) + 1) % values.length];
                    write(control, next);
                });
                wrap.append(after);
            }
            return { element: wrap, focusable: input, update() {
                if (document.activeElement !== input) input.value = formatNumber(widget, widget.value);
                if (after) {
                    const mode = control.value;
                    after.innerHTML = ICONS[mode] || ICONS.randomize;
                    after.title = SEED_MODES[mode] || String(mode);
                    after.setAttribute("aria-label", after.title);
                    after.dataset.mode = mode;
                }
            } };
        }
        const input = textInput(widget, field);
        return { element: input, focusable: input, update() { if (document.activeElement !== input) input.value = String(widget.value ?? ""); } };
    }

    // ---- sections ----------------------------------------------------------------------------------------
    const sections = [];
    function addSection(section) {
        const box = el("div", "rp-section");
        box.append(el("div", "rp-title", section.title || "Settings"));
        const own = [];
        for (const field of section.fields || []) {
            const row = makeRow(typeof field === "string" ? { name: field } : field);
            if (!row) continue;
            own.push(row); rows.push(row);
            box.append(row.element);
        }
        sections.push({ box, rows: own, when: section.when });
        root.append(box);
    }
    for (const section of spec.sections || []) addSection(section);
    // Anything the layout forgot is still editable, at the end.
    const rest = (spec.settings ? [] : node.widgets || []).filter(w => !mentioned.has(w.name) && w.serialize !== false && w.type !== "button"
        && !(w.element && w.type !== "customtext") && !String(w.type).startsWith("RAY_") && w.options?.serialize !== false);
    if (rest.length) addSection({ title: "Additional settings", fields: rest.map(w => w.name) });

    // Hide the native widgets the panel now draws. Code that hides them by mode still decides whether the
    // row shows (setWidgetHidden records it as widget.rayLogicHidden).
    for (const row of rows) {
        if (!row.widget) continue;
        const hiddenNow = !!row.widget.hidden;
        setWidgetHidden(node, row.widget, true);
        row.widget.rayLogicHidden = spec.settings ? false : hiddenNow;
        row.widget.rayPanel = panel;
        for (const linked of row.widget.linkedWidgets || []) { setWidgetHidden(node, linked, true); linked.rayPanel = panel; linked.rayLogicHidden = true; }
    }

    // ---- refresh -------------------------------------------------------------------------------------------
    let queued = false, lastHeight = 0;
    function schedule() {
        if (queued) return;
        queued = true;
        requestAnimationFrame(() => { queued = false; refresh(); });
    }
    function refresh() {
        for (const section of sections) {
            let any = false;
            for (const row of section.rows) {
                const visible = (!row.when || row.when(node)) && !(row.widget && row.widget.rayLogicHidden);
                row.element.hidden = !visible;
                if (visible) { any = true; row.update(); }
            }
            section.box.hidden = !any || (section.when && !section.when(node));
        }
        const empty = sections.every(s => s.box.hidden);
        root.hidden = empty;
        host.hidden = empty;
        if (panel.domWidget && Boolean(panel.domWidget.hidden) !== empty) setWidgetHidden(node, panel.domWidget, empty);
        fit();
    }
    function height() {
        if (root.hidden) return 0;
        const measured = root.isConnected ? root.offsetHeight : 0;
        if (measured) return measured;
        return 14 + rows.filter(r => !r.element.hidden).reduce((h, r) => h + (r.kind === "textarea" ? 92 : r.element.classList.contains("rp-full") ? 52 : 34), 0)
            + sections.filter(s => !s.box.hidden).length * 18;
    }
    panel.height = height;
    const minWidth = spec.minWidth || 340;
    function fit() {
        if (spec.settings) return;
        const h = height();
        // node.size is a typed array, not an Array.
        const hasSize = node.size && node.size.length >= 2;
        const narrow = hasSize && h > 0 && node.size[0] < minWidth;
        if (Math.abs(h - lastHeight) < 1 && !narrow) return;
        lastHeight = h;
        // A panel mounted in a face the user sizes (the analog controls) never shrinks the node: it only makes
        // sure the node is tall enough. The face takes whatever height the panel gives up.
        if (spec.mount) {
            if (hasSize) node.setSize?.([Math.max(node.size[0], h > 0 ? minWidth : 0), Math.max(node.size[1], node.computeSize?.()[1] || 0)]);
        } else {
            const size = node.computeSize?.();
            if (size && hasSize) node.setSize?.([Math.max(node.size[0], size[0], minWidth), size[1]]);
        }
        node.setDirtyCanvas?.(true, true);
    }
    // Values also change from outside (control after generate, other extensions, a loaded workflow).
    const timer = setInterval(() => { if (root.isConnected) refresh(); }, 400);
    function destroy() {
        clearInterval(timer); unregister();
        if (spec.settings) for (const row of rows) if (row.widget?.rayPanel === panel) delete row.widget.rayPanel;
    }

    root.addEventListener("pointerdown", e => { if (e.button === 0 && e.target !== root) e.stopPropagation(); });
    // The legacy canvas insets a DOM widget by its margin on each side; keep it small and count it.
    const MARGIN = 4;
    const outer = () => { const h = height(); return h ? h + 2 * MARGIN : 0; };
    const widgetOptions = { serialize: false, hideOnZoom: false, margin: MARGIN, getMinHeight: outer, getMaxHeight: outer, getHeight: outer };
    // Mounted inside another interface (the analog controls), the panel takes no DOM widget of its own.
    if (spec.mount) { host.style.height = "auto"; host.style.flex = "0 0 auto"; spec.mount.prepend(host); }
    const domWidget = spec.mount ? null : node.addDOMWidget?.("ray_panel", "RAY_PANEL", host, widgetOptions);
    if (domWidget) {
        domWidget.serialize = false;
        panel.domWidget = domWidget;
        // The panel goes first, above any face or preview the node draws itself.
        const list = node.widgets;
        list.splice(list.indexOf(domWidget), 1);
        let at = spec.before ? list.findIndex(w => w.name === spec.before) : -1;
        if (at < 0) at = list.findIndex(w => w.element && w.type !== "customtext");
        list.splice(at < 0 ? list.length : at, 0, domWidget);
    }
    node[panelKey] = panel;
    const unregister = spec.settings ? () => {} : registerLinkTargets(node, rows, refresh);
    if (!spec.settings) {
        const removed = node.onRemoved;
        node.onRemoved = function () { destroy(); return removed?.apply(this, arguments); };
    }
    refresh();
    requestAnimationFrame(() => { lastHeight = -1; refresh(); });
    return panel;
}

// Secondary settings reuse the same native-widget editors as the graph panel.
export function openPanelSettings(node, spec, title = "Ray settings") {
    node._raySettingsClose?.();
    const dialog = document.createElement("dialog");
    dialog.className = "rp-dialog";
    dialog.setAttribute("aria-label", title);
    Object.assign(dialog.style, { width: "440px", maxWidth: "calc(100vw - 24px)", maxHeight: "85vh",
        overflow: "auto", padding: "10px", background: "#000", color: "#eee", border: "1px solid #383838", borderRadius: "8px" });
    const heading = el("h3", "rp-title", title);
    const mount = el("div");
    dialog.append(heading, mount);
    document.body.append(dialog);
    const panel = installPanel(node, { ...spec, mount, settings: true });
    const done = el("button", "rp-input", "Done");
    done.type = "button";
    dialog.append(done);
    let closed = false;
    const close = () => {
        if (closed) return;
        closed = true;
        panel.destroy();
        delete node._raySettingsPanel;
        delete node._raySettingsClose;
        dialog.close();
        dialog.remove();
    };
    done.onclick = close;
    dialog.addEventListener("cancel", event => { event.preventDefault(); close(); });
    dialog.addEventListener("click", event => { if (event.target === dialog) close(); });
    for (const type of ["keydown", "keyup", "keypress"]) dialog.addEventListener(type, event => event.stopPropagation());
    if (!node._raySettingsLifecycle) {
        node._raySettingsLifecycle = true;
        const removed = node.onRemoved;
        node.onRemoved = function () { this._raySettingsClose?.(); return removed?.apply(this, arguments); };
    }
    node._raySettingsClose = close;
    dialog.showModal();
    done.focus();
    return { dialog, panel, close };
}
