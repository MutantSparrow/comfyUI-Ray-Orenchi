import { app } from "../../scripts/app.js";
import { ensurePanelStyles } from "./ray_panel.js";

// Filename builder for Save Image: the pure rules below mirror filename_template.py character for character
// (tests/filename_cases.json runs against both), and the popup lets you assemble a prefix from tokens.

export const DEFAULT_TEMPLATE = "Ray_{date}_{counter}";
const FALLBACK_STEM = "Ray";
const MAX_STEM = 180;
const VALUE_LIMIT = 60;
const NAMES = ["date", "time", "datetime", "timestamp", "counter", "index", "input", "hash", "widget"];
// Keep these two classes identical to ILLEGAL and SPACE in filename_template.py.
const ILLEGAL = /[<>:"/\\|?*\x00-\x1f\x7f-\x9f]/g;
const SPACE = new RegExp("[ \\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff]+", "g");
const RESERVED = new Set(["CON", "PRN", "AUX", "NUL", ...Array.from({ length: 9 }, (_, i) => `COM${i + 1}`), ...Array.from({ length: 9 }, (_, i) => `LPT${i + 1}`)]);

export class TemplateError extends Error {
    constructor(message) { super(message); this.name = "TemplateError"; }
}

const cut = (text, length) => Array.from(text).slice(0, length).join("");
const trimSet = (text, chars, start = true, end = true) => {
    let from = 0, to = text.length;
    while (start && from < to && chars.includes(text[from])) from++;
    while (end && to > from && chars.includes(text[to - 1])) to--;
    return text.slice(from, to);
};

function number(text, name, low, high, fallback) {
    if (text === "") return fallback;
    if (!/^\d{1,3}$/.test(text) || Number(text) < low || Number(text) > high) throw new TemplateError(`{${name}:${text}} needs a number from ${low} to ${high}.`);
    return Number(text);
}

function token(body) {
    const bar = body.indexOf("|");
    const base = bar < 0 ? body : body.slice(0, bar), limit = bar < 0 ? null : body.slice(bar + 1);
    const colon = base.indexOf(":");
    const name = (colon < 0 ? base : base.slice(0, colon)).trim().toLowerCase();
    const arg = colon < 0 ? "" : base.slice(colon + 1);
    if (!NAMES.includes(name)) throw new TemplateError(`Unknown filename token {${body}}. Tokens: ${NAMES.map(n => `{${n}}`).join(", ")}.`);
    if (limit !== null && name !== "widget") throw new TemplateError(`{${name}} does not take a |length.`);
    if (["date", "time", "datetime", "timestamp", "input"].includes(name)) {
        if (arg) throw new TemplateError(`{${name}} takes no options.`);
        return ["token", name, {}];
    }
    if (name === "counter") return ["token", name, { width: number(arg.trim(), name, 1, 12, 4) }];
    if (name === "index") return ["token", name, { width: number(arg.trim(), name, 1, 12, 1) }];
    if (name === "hash") return ["token", name, { length: number(arg.trim(), name, 4, 32, 8) }];
    const target = arg.trim(), dot = target.lastIndexOf(".");
    const node = dot < 0 ? "" : target.slice(0, dot), widget = dot < 0 ? "" : target.slice(dot + 1);
    if (!node || !widget || /[\s{}|]/.test(node + widget)) throw new TemplateError("{widget:...} needs a node id and a widget name, like {widget:12.seed}.");
    return ["token", name, { node, widget, limit: limit === null ? VALUE_LIMIT : number(limit.trim(), "widget|", 1, 200, VALUE_LIMIT) }];
}

const plain = text => {
    if (/[{}]/.test(text)) throw new TemplateError("A { or } is not part of a token. Write tokens like {date} or {counter:4}.");
    return text;
};

// ["text", string] and ["token", name, options] parts, or a TemplateError.
export function parseTemplate(template) {
    template = String(template);
    const parts = [], pattern = /\{([^{}]*)\}/g;
    let position = 0, match;
    while ((match = pattern.exec(template))) {
        parts.push(["text", plain(template.slice(position, match.index))], token(match[1]));
        position = match.index + match[0].length;
    }
    parts.push(["text", plain(template.slice(position))]);
    if (parts.filter(p => p[0] === "token" && p[1] === "counter").length > 1) throw new TemplateError("Use {counter} only once.");
    return parts.filter(p => !(p[0] === "text" && p[1] === ""));
}

export const cleanText = text => String(text).normalize("NFC").replace(ILLEGAL, "_").replace(SPACE, "_");

function valueText(value) {
    if (value === null || value === undefined) return "";
    if (typeof value === "boolean") return value ? "true" : "false";
    return String(value);
}

export function cleanValue(value, limit = VALUE_LIMIT) {
    let text = valueText(value).normalize("NFC").replace(/[{}]/g, "_").replace(ILLEGAL, "_").replace(SPACE, "_");
    text = trimSet(text.replace(/_{2,}/g, "_"), "_-. ");
    return trimSet(cut(text, limit), "_-. ", false, true);
}

export function finishStem(stem) {
    stem = trimSet(cut(trimSet(stem, ". ", true, false), MAX_STEM), ". ", false, true);
    if (RESERVED.has(stem.split(".")[0].toUpperCase())) stem = `_${stem}`;
    return stem || FALLBACK_STEM;
}

const two = n => String(n).padStart(2, "0");
function randomHex(length) {
    const bytes = new Uint8Array(16);
    if (globalThis.crypto?.getRandomValues) globalThis.crypto.getRandomValues(bytes);
    else for (let i = 0; i < bytes.length; i++) bytes[i] = Math.floor(Math.random() * 256);
    return Array.from(bytes, b => b.toString(16).padStart(2, "0")).join("").slice(0, length);
}

function piece(part, ctx) {
    const [, name, options] = part, d = ctx.now;
    const date = `${d.getFullYear()}-${two(d.getMonth() + 1)}-${two(d.getDate())}`, time = `${two(d.getHours())}-${two(d.getMinutes())}-${two(d.getSeconds())}`;
    switch (name) {
        case "date": return date;
        case "time": return time;
        case "datetime": return `${date}T${time}`;
        case "timestamp": return String(Math.floor(d.getTime() / 1000));
        case "input": return String(ctx.input ?? 1);
        case "index": return String(ctx.index ?? 1).padStart(options.width, "0");
        case "hash": return (ctx.hash || randomHex(32)).slice(0, options.length);
        case "widget": return cleanValue(ctx.widgets ? ctx.widgets(options.node, options.widget) : null, options.limit);
        default: throw new TemplateError(`{${name}} cannot be used here.`);
    }
}

// The finished stem for one image. `counter` fills {counter}.
export function renderStem(parts, ctx, counter = 0) {
    return finishStem(parts.map(part => {
        if (part[0] === "text") return cleanText(part[1]);
        if (part[1] === "counter") return String(counter || 0).padStart(part[2].width, "0");
        return piece(part, ctx);
    }).join(""));
}

// ---------------------------------------------------------------------------
// Widgets of the workflow
// ---------------------------------------------------------------------------

const nodeById = (graph, id) => graph?.getNodeById?.(/^\d+$/.test(id) ? Number(id) : id) || graph?.getNodeById?.(id) || null;
const usable = w => w && w.serialize !== false && w.type !== "button" && !w.element && !w.isRayBrowse && !/_ui$|_preview$/.test(w.name || "");

// Every widget a filename can use, grouped by node: [{ id, title, widgets: [{ name, value }] }].
export function listWidgets(graph, skip) {
    return (graph?._nodes || []).map(node => ({
        id: String(node.id), title: node.title || node.type || `Node ${node.id}`,
        widgets: (node.widgets || []).filter(w => usable(w) && !(node === skip && w.name === "filename_prefix"))
            .filter(w => w.value === null || ["string", "number", "boolean"].includes(typeof w.value))
            .map(w => ({ name: w.name, value: w.value })),
    })).filter(n => n.widgets.length).sort((a, b) => Number(a.id) - Number(b.id) || a.id.localeCompare(b.id));
}

export function widgetValue(graph, id, name) {
    const widget = nodeById(graph, id)?.widgets?.find(w => w.name === name);
    return usable(widget) ? widget.value : null;
}

// Shared by Save Image's name builder and Model Card's card name.
export function createWidgetPicker(graph, skip, selected) {
    injectStyles();
    const picker = el("div", "ray-name-widgets");
    const filter = el("input");
    filter.type = "text"; filter.placeholder = "Filter nodes and widgets…";
    filter.setAttribute("aria-label", "Filter widgets");
    const list = el("div", "ray-name-list");
    function render() {
        list.replaceChildren();
        const query = filter.value.trim().toLowerCase();
        for (const group of listWidgets(graph, skip).filter(g => String(g.id) !== String(skip?.id))) {
            const widgets = group.widgets.filter(w => !query || `${group.title} ${group.id} ${w.name} ${w.value}`.toLowerCase().includes(query));
            if (!widgets.length) continue;
            list.append(el("h4", "", `${group.title} · #${group.id}`));
            for (const widget of widgets) {
                const button = el("button"); button.type = "button";
                button.append(el("span", "", widget.name), el("span", "", valueText(widget.value).slice(0, 80)));
                button.title = `{widget:${group.id}.${widget.name}}`;
                button.onclick = () => selected(button.title);
                list.append(button);
            }
        }
        if (!list.children.length) list.append(el("div", "ray-name-empty", "No widgets match."));
    }
    filter.addEventListener("input", render);
    picker.append(filter, list);
    render();
    return picker;
}

export function displayWidgetValue(value, limit = VALUE_LIMIT) {
    let text = valueText(value).normalize("NFC").replace(/[{}]/g, "_")
        .replace(/[\p{Cc}\p{Cf}]/gu, "").replace(/\s+/gu, " ").trim();
    if (/\.(safetensors|ckpt|pt|pth|bin|gguf)$/i.test(text)) {
        text = text.replace(/\\/g, "/").split("/").pop().replace(/\.[^.]+$/, "");
    }
    return cut(text, limit);
}

export function renderDisplayName(parts, ctx) {
    const text = parts.map(part => {
        if (part[0] === "text") return part[1];
        if (part[1] === "widget") return displayWidgetValue(ctx.widgets?.(part[2].node, part[2].widget), part[2].limit);
        if (["date", "time", "datetime", "timestamp", "hash"].includes(part[1])) return piece(part, ctx);
        throw new TemplateError(`{${part[1]}} is only available for filenames.`);
    }).join("");
    return cut(text.normalize("NFC").replace(/[\p{Cc}\p{Cf}]/gu, "").replace(/\s+/gu, " ").trim(), 512);
}

// Replaces {widget:ID.NAME} with the widget's current value before the prompt is sent, so the value is the one on
// screen even when the widget is fed by a link. Anything that cannot be found is left for the server to try.
export function resolveWidgetTokens(template, graph, formatValue = cleanValue) {
    return String(template).replace(/\{widget:([^.{}|\s]+)\.([^.{}|\s]+)(?:\|(\d+))?\}/gi, (whole, id, name, limit) => {
        const node = nodeById(graph, id);
        const widget = node?.widgets?.find(w => w.name === name);
        return usable(widget) ? formatValue(widget.value, limit ? Math.min(200, Math.max(1, Number(limit))) : VALUE_LIMIT) : whole;
    });
}

// ---------------------------------------------------------------------------
// The popup
// ---------------------------------------------------------------------------

const linked = (node, name) => !!node.inputs?.some(input => (input.widget?.name === name || input.name === name) && input.link != null);
let savedPosition = null;
let lastPointer = [0, 0];
if (typeof window !== "undefined") {
    lastPointer = [window.innerWidth / 2, window.innerHeight / 3];
    window.addEventListener("pointerdown", event => { lastPointer = [event.clientX, event.clientY]; }, true);
}

function injectStyles() {
    ensurePanelStyles();
    if (document.getElementById("ray-name-style")) return;
    const style = document.createElement("style");
    style.id = "ray-name-style";
    style.textContent = `
.ray-name { position:fixed; z-index:100000; box-sizing:border-box; width:380px; max-width:calc(100vw - 16px); padding:10px 12px 12px;
    box-shadow:0 10px 30px #000a; line-height:1.35; }
.ray-name * { box-sizing:border-box; }
.ray-name-title { margin:-10px -12px 10px; padding:8px 12px; border-bottom:1px solid #2c2f35; border-radius:8px 8px 0 0; cursor:move; user-select:none; touch-action:none; }
.ray-name-title::before { content:"⠿"; margin-right:7px; letter-spacing:0; opacity:.7; }
.ray-name label { display:block; margin:0 0 4px; font-size:10px; letter-spacing:.06em; text-transform:uppercase; color:#8d9096; }
.ray-name input[type=text] { width:100%; font-family:ui-monospace,monospace; }
.ray-name-chips { display:flex; flex-wrap:wrap; gap:5px; margin:8px 0; }
.ray-name-with { display:inline-flex; align-items:stretch; }
.ray-name-with button { border-radius:5px 0 0 5px; border-right:0; }
.ray-name-with input[type=number] { width:44px; padding:0 4px; border-radius:0 5px 5px 0; }
.ray-name-preview { margin:8px 0 4px; padding:8px; border-radius:5px; background:#101214; font:12px ui-monospace,monospace; color:#ddd; overflow-wrap:anywhere; min-height:2.6em; }
.ray-name-preview[data-error="true"] { color:#ffb1aa; }
.ray-name-note { margin:0 0 8px; font-size:10px; color:#8d9096; }
.ray-name-widgets { margin:6px 0; border:1px solid #33363c; border-radius:5px; background:#15171a; pointer-events:auto; }
.ray-name-widgets input[type=text] { border:0; border-bottom:1px solid #33363c; border-radius:5px 5px 0 0; }
.ray-name-list { max-height:190px; overflow-y:auto; padding:2px; }
.ray-name-list h4 { margin:6px 6px 2px; font:600 10px system-ui; letter-spacing:.06em; text-transform:uppercase; color:#d43aa8; }
.ray-name-list button { display:flex; width:100%; gap:8px; justify-content:space-between; border:0; background:transparent; text-align:left; padding:4px 6px; }
.ray-name-list button span:last-child { color:#8d9096; font-family:ui-monospace,monospace; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; max-width:55%; }
.ray-name-empty { padding:10px; color:#8d9096; }
.ray-name-done { width:100%; }
`;
    document.head.appendChild(style);
}

const el = (tag, className, text) => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
};

export function openNameBuilder(node, options = {}) {
    injectStyles();
    node._rayNameBuilder?.close();
    const widgetName = options.widgetName || "filename_prefix";
    const widget = node.widgets?.find(w => w.name === widgetName);
    if (!widget) return null;
    const graph = node.graph;
    const panel = el("div", "ray-name rp-surface");
    panel.setAttribute("role", "dialog");
    panel.setAttribute("aria-label", options.title || "Build filename");
    const title = el("div", "ray-name-title rp-title", options.title || "Build filename");
    title.title = "Drag to move";
    const label = el("label", "", options.label || "File name (saved as name.png)");
    const input = el("input");
    input.type = "text"; input.spellcheck = false; input.autocomplete = "off";
    input.value = String(widget.value ?? "");
    input.title = options.note || "Filename stem with optional date, counter, and workflow-widget tokens; the preview shows the result";
    input.id = "ray-name-input"; label.htmlFor = input.id;
    const chips = el("div", "ray-name-chips");
    const preview = el("div", "ray-name-preview");
    preview.setAttribute("aria-live", "polite");
    const note = el("p", "ray-name-note", options.note || "Spaces and characters a filename cannot hold become _. Nothing is overwritten: {counter} continues from the files in the folder, and otherwise -2, -3… is added.");
    const done = el("button", "ray-name-done", "Done");
    done.type = "button";
    done.title = "Close the builder; changes are already saved with the workflow";
    const picker = el("div", "ray-name-widgets");
    picker.hidden = true;
    panel.append(title, label, input, chips, picker, preview, note, done);
    document.body.append(panel);

    const editable = !linked(node, widgetName);
    if (!editable) { input.disabled = true; note.textContent = `${widgetName} is driven by a link, so it cannot be edited here.`; }

    let counting = false;
    const begin = () => { if (!counting) { graph?.beforeChange?.(); counting = true; } };
    function setTemplate(value) {
        if (!editable) return;
        begin();
        widget.value = value;
        widget.callback?.(value, app.canvas, node, undefined, undefined);
        node.setDirtyCanvas?.(true, true);
        node._raySave?.sync?.();
        node._rayPanel?.schedule?.();
        showPreview();
    }
    function showPreview() {
        const text = input.value.trim() || (options.defaultTemplate ?? DEFAULT_TEMPLATE);
        try {
            const parts = parseTemplate(text);
            const lookup = (id, name) => widgetValue(graph, id, name);
            const context = { now: new Date(), index: 1, input: 1, widgets: lookup };
            preview.textContent = options.preview ? options.preview(parts, context) : `${renderStem(parts, context, 1)}.png`;
            preview.dataset.error = "false";
        } catch (error) {
            preview.textContent = error.message;
            preview.dataset.error = "true";
        }
    }
    function insert(text) {
        if (!editable) return;
        const start = input.selectionStart ?? input.value.length, end = input.selectionEnd ?? start;
        const before = input.value.slice(0, start), after = input.value.slice(end);
        const glue = before && !/[_\-\s]$/.test(before) ? (options.separator ?? "_") : "";
        input.value = before + glue + text + after;
        const caret = (before + glue + text).length;
        input.setSelectionRange(caret, caret);
        input.focus();
        setTemplate(input.value);
    }
    const chip = (text, value, tip) => { const b = el("button", "", text); b.type = "button"; b.title = tip; b.addEventListener("click", () => insert(value)); return b; };
    const withDigits = (text, name, min, max, fallback, tip) => {
        const wrap = el("span", "ray-name-with"), digits = el("input");
        digits.type = "number"; digits.min = String(min); digits.max = String(max); digits.value = String(fallback);
        digits.setAttribute("aria-label", `${text} digits`); digits.title = `Number of ${text.toLowerCase()} digits, from ${min} to ${max}`;
        const b = el("button", "", text); b.type = "button"; b.title = tip;
        b.addEventListener("click", () => {
            const n = Math.min(max, Math.max(min, Math.trunc(Number(digits.value)) || fallback));
            insert(`{${name}:${n}}`);
        });
        wrap.append(b, digits);
        return wrap;
    };
    const widgetsButton = el("button", "", "Widget value…");
    widgetsButton.type = "button"; widgetsButton.title = "Use the value of a widget on any node of this workflow";
    chips.append(
        chip("Date", "{date}", "ISO date: 2026-10-16"), chip("Time", "{time}", "14-32-05 (colons are not allowed in filenames)"),
        chip("Date + time", "{datetime}", "2026-10-16T14-32-05"),
        ...(options.fileTokens === false ? [] : [
            withDigits("Counter", "counter", 1, 12, 4, "The next unused number in the folder, zero-padded to this many digits"),
            chip("Index", "{index}", "Position of the image in its batch, from 1"), chip("Input", "{input}", "1 or 2: which image input the file came from"),
        ]),
        withDigits("Hash", "hash", 4, 32, 8, "Random hex characters, so two names can never clash"),
        widgetsButton,
    );

    widgetsButton.addEventListener("click", () => {
        if (!picker.hidden) { picker.hidden = true; return; }
        const shared = createWidgetPicker(graph, node, token => { picker.hidden = true; insert(token); });
        picker.replaceChildren(shared);
        picker.hidden = false;
        shared.querySelector("input").focus();
    });
    input.addEventListener("input", () => setTemplate(input.value));
    input.addEventListener("keydown", event => { event.stopPropagation(); if (event.key === "Enter") { event.preventDefault(); close(); } });

    // ---- closing, placing, dragging ----------------------------------------------------------------
    const stop = new AbortController();
    function close() {
        if (counting) { graph?.afterChange?.(); counting = false; }
        stop.abort(); panel.remove();
        if (node._rayNameBuilder?.panel === panel) node._rayNameBuilder = null;
    }
    done.addEventListener("click", close);
    panel.addEventListener("keydown", event => event.stopPropagation());
    // Escape closes it wherever the keyboard focus is (after dragging the title bar it is no longer inside).
    window.addEventListener("keydown", event => { if (event.key === "Escape") { event.preventDefault(); event.stopPropagation(); close(); } }, { capture: true, signal: stop.signal });
    window.addEventListener("pointerdown", event => { if (!panel.contains(event.target)) close(); }, { capture: true, signal: stop.signal });
    const margin = 8;
    const place = (x, y) => {
        const box = panel.getBoundingClientRect();
        const left = Math.max(margin, Math.min(x, window.innerWidth - box.width - margin)), top = Math.max(margin, Math.min(y, window.innerHeight - box.height - margin));
        panel.style.left = `${left}px`; panel.style.top = `${top}px`;
        return [left, top];
    };
    place(...(savedPosition || lastPointer));
    window.addEventListener("resize", () => place(panel.getBoundingClientRect().left, panel.getBoundingClientRect().top), { signal: stop.signal });
    let moving = null;
    title.addEventListener("pointerdown", event => {
        if (event.button !== 0) return;
        event.preventDefault();
        const box = panel.getBoundingClientRect();
        moving = { id: event.pointerId, dx: event.clientX - box.left, dy: event.clientY - box.top };
        try { title.setPointerCapture(event.pointerId); } catch { /* the pointer is already gone */ }
    });
    title.addEventListener("pointermove", event => { if (moving && event.pointerId === moving.id) savedPosition = place(event.clientX - moving.dx, event.clientY - moving.dy); });
    for (const type of ["pointerup", "pointercancel", "lostpointercapture"]) title.addEventListener(type, () => { moving = null; });

    node._rayNameBuilder = { close, panel };
    showPreview();
    input.focus({ preventScroll: true });
    input.setSelectionRange(input.value.length, input.value.length);
    return panel;
}

// Widget tokens are filled in from the live workflow whenever a prompt is queued; the saved workflow keeps the
// template you typed.
export function resolveOnQueue(node) {
    const target = node.widgets?.find(w => w.name === "filename_prefix");
    if (!target) return false;
    target.serializeValue = async () => resolveWidgetTokens(target.value ?? "", node.graph);
    return true;
}

// For frontends without DOM widgets: "🏷 Build filename…" directly under the native prefix widget.
export function installNameBuilder(node) {
    const widgets = node.widgets;
    const target = widgets?.find(w => w.name === "filename_prefix");
    if (!target || typeof node.addWidget !== "function" || widgets.some(w => w.isRayName)) return null;
    resolveOnQueue(node);
    const button = node.addWidget("button", "🏷 Build filename…", null, () => openNameBuilder(node), { serialize: false });
    if (!button) return null;
    button.serialize = false;
    button.isRayName = true;
    widgets.splice(widgets.indexOf(button), 1);
    widgets.splice(widgets.indexOf(target) + 1, 0, button);
    return button;
}
