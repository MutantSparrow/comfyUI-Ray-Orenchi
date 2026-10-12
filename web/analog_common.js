import { applyBucketTint, findWidget, mountDymoLabel, setWidgetHidden } from "./_common.js";
import { getBrushedAluminumURL } from "./knob_styles.js";
import { isMuted, setMuted } from "./analog_audio.js";

let nextSvgId = 0;

// SVG fragment identifiers share the document namespace, even between nodes.
export function mountControlSVG(host, svg) {
    const prefix = `ray-analog-${++nextSvgId}-`;
    const ids = new Map([...svg.matchAll(/\bid="([^"]+)"/g)].map(m => [m[1], prefix + m[1]]));
    host.innerHTML = svg
        .replace(/\bid="([^"]+)"/g, (_, id) => `id="${ids.get(id)}"`)
        .replace(/url\(#([^)]+)\)/g, (_, id) => `url(#${ids.get(id) || id})`)
        .replace(/\bhref="#([^"]+)"/g, (_, id) => `href="#${ids.get(id) || id}"`);
    host.querySelector("svg")?.setAttribute("aria-hidden", "true");
}

export function changeValue(node, widget, value, event) {
    if (!widget || Object.is(widget.value, value)) return;
    widget.value = value;
    widget.callback?.(value, undefined, node, undefined, event);
    node.setDirtyCanvas?.(true, true);
}

export function editNode(node, action) {
    const graph = node.graph;
    graph?.beforeChange?.();
    try { action(); }
    finally {
        graph?.afterChange?.();
        node.setDirtyCanvas?.(true, true);
    }
}

function injectStyles() {
    if (document.getElementById("ray-analog-panel")) return;
    const style = document.createElement("style");
    style.id = "ray-analog-panel";
    style.textContent = `
.ray-analog-panel {
    width:100%; height:100%; min-width:0; box-sizing:border-box;
    display:flex; flex-direction:column; align-items:center; gap:4px;
    padding:10px 12px 8px; border:1px solid #74777b; border-radius:3px;
    position:relative;
    color:#1c2023; background:#b6b8bb url("${getBrushedAluminumURL()}") repeat;
    background-size:256px 256px;
    box-shadow:inset 0 1px 0 #ffffff80, inset 0 -1px 0 #00000040;
    user-select:none;
}
.ray-analog-panel[data-panel="charcoal"] {
    color:#c5cabb; border-color:#111b1d;
    background-color:#29383b;
    background-image:repeating-linear-gradient(0deg,#ffffff02 0px,#ffffff02 1px,transparent 1px,transparent 3px),linear-gradient(115deg,#344246,#253236);
    background-size:auto,100% 100%;
    box-shadow:inset 0 1px 0 #73817f55,inset 0 -1px 0 #0009;
}
.ray-analog-panel[data-panel="olive"] {
    color:#30382e; border-color:#767c67;
    background-image:repeating-linear-gradient(0deg,#00000002 0px,#00000002 1px,transparent 1px,transparent 3px),linear-gradient(115deg,#c6c8ad,#adb59a);
    background-size:auto,100% 100%;
}
.ray-analog-panel::before,.ray-analog-panel::after {
    content:""; position:absolute; bottom:6px; width:5px; height:5px; border-radius:50%;
    border:1px solid #151d1b88; background:linear-gradient(135deg,#b4b6a5 40%,#303b35 42%,#303b35 58%,#969d8e 60%);
    box-shadow:0 1px 1px #0005;
}
.ray-analog-panel::before { left:5px; }
.ray-analog-panel::after { right:5px; }
.ray-analog-panel .ray-dymo { flex-shrink:0; margin:0; }
.ray-style-picker {
    position:fixed; z-index:100000; box-sizing:border-box; min-width:230px; max-width:calc(100vw - 16px);
    max-height:min(72vh,520px); overflow-x:hidden; overflow-y:auto; padding:6px;
    background:#1b1c1f; color:#e6e6e6; border:1px solid #4a4c52; border-radius:8px;
    box-shadow:0 10px 30px #000a; font:13px/1.3 system-ui,sans-serif;
}
.ray-style-heading { margin:6px 8px 3px; font:600 10px system-ui; letter-spacing:.08em; text-transform:uppercase; color:#8d9096; }
.ray-style-item {
    display:flex; align-items:center; gap:8px; width:100%; padding:6px 8px; border:0; border-radius:5px;
    background:transparent; color:inherit; font:inherit; text-align:left; white-space:nowrap; cursor:pointer;
}
.ray-style-item:hover, .ray-style-item:focus-visible { background:#33363c; outline:none; }
.ray-style-item[aria-checked="true"] { color:#fff; }
.ray-style-swatch { flex:none; width:10px; height:10px; border-radius:3px; border:1px solid #0009; background:#b6b8bb; }
.ray-style-swatch[data-panel="charcoal"] { background:#34464a; }
.ray-style-swatch[data-panel="olive"] { background:#c6c8ad; }
.ray-style-mark { margin-left:auto; padding-left:12px; }
.ray-analog-panel .ray-analog-face {
    display:block; flex:0 0 140px; width:140px; height:140px; max-width:100%;
    padding:0; border:0; border-radius:8px; background:transparent;
    min-height:0; touch-action:none; cursor:pointer; outline:none;
}
.ray-analog-face svg { display:block; width:100%; height:100%; pointer-events:none; }
.ray-analog-face:focus-visible, .ray-analog-value:focus-visible {
    outline:2px solid #185d89; outline-offset:2px;
}
.ray-analog-face[aria-disabled="true"] { opacity:.55; cursor:not-allowed; }
.ray-analog-face:hover:not([aria-disabled="true"]) svg { filter:brightness(1.04); }
.ray-knob-wrap[data-dragging="true"] .ray-analog-face svg [data-slide],
.ray-knob-wrap[data-dragging="true"] .ray-analog-face svg [data-rotate] { filter:brightness(1.13); }
.ray-knob-wrap .ray-analog-face { cursor:grab; }
.ray-knob-wrap[data-dragging="true"] .ray-analog-face { cursor:grabbing; }
.ray-analog-readout {
    display:flex; align-items:center; justify-content:center; gap:8px;
    width:100%; min-height:26px; flex-shrink:0; box-sizing:border-box;
    border:1px solid #ffffff45; border-radius:4px; background:#151c20;
    color:#e6eacb; font:12px/1.4 ui-monospace,monospace;
    font-variant-numeric:tabular-nums; box-shadow:inset 0 1px 3px #0009;
}
.ray-analog-value {
    width:58%; min-width:0; padding:2px 4px; border:0; border-radius:2px;
    background:transparent; color:inherit; font:inherit; text-align:right;
}
.ray-analog-int { padding-right:5px; font-size:10px; opacity:.8; white-space:nowrap; }
.ray-analog-readout[data-state="on"] { color:#b7f5b2; }
.ray-analog-hint { font:9px/1.2 ui-monospace,monospace; opacity:.8; text-align:center; }
@media (prefers-reduced-motion:reduce) {
    .ray-analog-panel [data-toggle] { transition:none; }
}
`;
    document.head.appendChild(style);
}

// The style choice opens its own floating panel instead of a nested context-menu submenu: LiteGraph
// pushes submenus over their parent near the screen edge, and the Nodes 2.0 menu renders them inside
// its own scroll container, where they overflow sideways and become unreachable.
let lastPointer = [0, 0];
if (typeof window !== "undefined") {
    lastPointer = [window.innerWidth / 2, window.innerHeight / 3];
    window.addEventListener("pointerdown", event => { lastPointer = [event.clientX, event.clientY]; }, true);
}

export function openStylePicker(node, kind, styles) {
    document.querySelector(".ray-style-picker")?.remove();
    const picker = document.createElement("div");
    picker.className = "ray-style-picker";
    picker.setAttribute("role", "menu");
    picker.setAttribute("aria-label", `${kind === "knob" ? "Control" : "Switch"} style`);
    // Knob faces first, then sliders, each under a heading.
    const entries = Object.entries(styles).sort(([, a], [, b]) => (a.kind === "slider") - (b.kind === "slider"));
    const items = [];
    let group = null;
    for (const [key, style] of entries) {
        const heading = kind === "knob" ? (style.kind === "slider" ? "Sliders" : "Knobs") : null;
        if (heading && heading !== group) {
            const title = document.createElement("div");
            title.className = "ray-style-heading"; title.setAttribute("role", "presentation"); title.textContent = heading;
            picker.append(title);
        }
        group = heading;
        const current = node.properties.style === key;
        const item = document.createElement("button");
        item.type = "button"; item.className = "ray-style-item";
        item.setAttribute("role", "menuitemradio"); item.setAttribute("aria-checked", String(current));
        const swatch = document.createElement("span");
        swatch.className = "ray-style-swatch"; swatch.dataset.panel = style.panel || "silver";
        const label = document.createElement("span");
        label.textContent = style.label;
        item.append(swatch, label);
        if (current) {
            const mark = document.createElement("span");
            mark.className = "ray-style-mark"; mark.textContent = "●";
            item.append(mark);
        }
        item.addEventListener("click", () => {
            close();
            editNode(node, () => {
                node.properties.style = key;
                node._rayAnalog?.render();
            });
        });
        items.push(item);
        picker.append(item);
    }
    const stop = new AbortController();
    function close() { stop.abort(); picker.remove(); }
    document.body.append(picker);
    // Keep the whole panel inside the window; it scrolls vertically if it is taller than the space.
    const box = picker.getBoundingClientRect(), margin = 8;
    picker.style.left = `${Math.max(margin, Math.min(lastPointer[0], window.innerWidth - box.width - margin))}px`;
    picker.style.top = `${Math.max(margin, Math.min(lastPointer[1], window.innerHeight - box.height - margin))}px`;
    const signal = stop.signal;
    window.addEventListener("pointerdown", event => { if (!picker.contains(event.target)) close(); }, { capture: true, signal });
    window.addEventListener("resize", close, { signal });
    window.addEventListener("blur", close, { signal });
    picker.addEventListener("keydown", event => {
        event.stopPropagation();
        const at = items.indexOf(document.activeElement);
        const move = { ArrowDown: at + 1, ArrowUp: at - 1, Home: 0, End: items.length - 1 }[event.key];
        if (event.key === "Escape") { event.preventDefault(); close(); }
        else if (move !== undefined) { event.preventDefault(); items[(move + items.length) % items.length].focus(); }
    });
    (items.find(item => item.getAttribute("aria-checked") === "true") || items[0])?.focus({ preventScroll: false });
    return picker;
}

export function createPanel(node, kind, css) {
    injectStyles();
    const styleId = `ray-${kind}-styles`;
    if (!document.getElementById(styleId)) {
        const style = document.createElement("style");
        style.id = styleId;
        style.textContent = css;
        document.head.appendChild(style);
    }
    const element = document.createElement("div");
    element.className = `ray-analog-panel ray-${kind}-wrap`;
    const dymo = mountDymoLabel(node, { placeholder: kind.toUpperCase() });
    element.appendChild(dymo.root);
    const host = document.createElement(kind === "switch" ? "button" : "div");
    if (kind === "switch") host.type = "button";
    host.className = `ray-analog-face ${kind === "knob" ? "rk-host" : "rs-host"}`;
    host.tabIndex = 0;
    element.appendChild(host);
    const readout = document.createElement("div");
    readout.className = "ray-analog-readout";
    element.appendChild(readout);
    const hint = document.createElement("div");
    hint.className = "ray-analog-hint";
    element.appendChild(hint);
    // Stop graph shortcuts/drags only inside this control, never by screen rectangles.
    for (const type of ["pointerdown", "mousedown", "click", "dblclick", "keydown", "keyup"]) {
        element.addEventListener(type, event => event.stopPropagation());
    }
    return { element, host, readout, hint, dymo };
}

export function isLinked(node, name) {
    return node.inputs?.some(input => (input.widget?.name === name || input.name === name) && input.link != null) || false;
}

// Old compact workflows serialized empty output arrays and an empty title.
export function repairAnalogWorkflow(data, name, title, outputs) {
    for (const node of data?.nodes || []) {
        if (node.type !== name) continue;
        if (node.properties?.compact && !node.title) node.title = title;
        if (Array.isArray(node.outputs) && node.outputs.length === 0) {
            node.outputs = outputs.map(([slotName, type]) => ({ name: slotName, type, links: null }));
        }
    }
    for (const subgraph of data?.definitions?.subgraphs || []) {
        repairAnalogWorkflow(subgraph, name, title, outputs);
    }
}

export function registerAnalog(app, { kind, name, title, styles, defaultStyle, valueName, configNames = [], outputs, build, migrate }) {
    app.registerExtension({
        name: `Ray.${kind === "knob" ? "Knob" : "Switch"}`,
        beforeConfigureGraph(data) { repairAnalogWorkflow(data, name, title, outputs); migrate?.(data); },
        beforeRegisterNodeDef(nodeType, nodeData) {
            if (nodeData.name !== name) return;
            const proto = nodeType.prototype;
            const created = proto.onNodeCreated;
            proto.onNodeCreated = function () {
                const result = created?.apply(this, arguments);
                applyBucketTint(this, "Analog");
                this.properties ||= {};
                if (!Object.hasOwn(styles, this.properties.style)) this.properties.style = defaultStyle;
                if (typeof this.properties.compact !== "boolean") this.properties.compact = false;
                if (typeof this.properties.ray_label !== "string") this.properties.ray_label = "";
                this.addProperty?.("style", this.properties.style, "enum", { values: Object.keys(styles) });
                this.addProperty?.("compact", this.properties.compact, "boolean");
                this.addProperty?.("ray_label", this.properties.ray_label, "string");
                const widget = findWidget(this, valueName);
                // Very old frontends retain the usable native numeric/boolean widget.
                if (!widget || typeof this.addDOMWidget !== "function") return result;
                const ui = build(this, widget);
                this._rayAnalog = ui;
                setWidgetHidden(this, widget, true);
                this.addDOMWidget(`${kind}_ui`, `RAY_${kind.toUpperCase()}`, ui.element, {
                    serialize: false, hideOnZoom: false,
                    getMinHeight: () => 232, getMaxHeight: () => 232, getHeight: () => 232,
                    onDraw: () => ui.render(),
                });
                const titleDescriptor = Object.getOwnPropertyDescriptor(this, "title_mode");
                let compactApplied;
                ui.applyCompact = () => {
                    const compact = !!this.properties.compact;
                    if (compactApplied === compact) return;
                    compactApplied = compact;
                    for (const key of configNames) {
                        const config = findWidget(this, key);
                        if (config && !isLinked(this, key)) setWidgetHidden(this, config, compact);
                    }
                    // Keep slots and the actual title intact for serialization and Nodes 2.0.
                    if (compact) {
                        Object.defineProperty(this, "title_mode", {
                            configurable: true, get: () => window.LiteGraph?.NO_TITLE ?? 1,
                        });
                    } else if (titleDescriptor) {
                        Object.defineProperty(this, "title_mode", titleDescriptor);
                    } else {
                        delete this.title_mode;
                    }
                    if (this.flags) delete this.flags.no_title;
                    const size = this.computeSize?.();
                    if (size) this.setSize?.([Math.max(this.size?.[0] || 0, size[0]), size[1]]);
                    this.setDirtyCanvas?.(true, true);
                };
                for (const key of [valueName, ...configNames]) {
                    const w = findWidget(this, key);
                    if (!w) continue;
                    const callback = w.callback;
                    w.callback = function () {
                        const result = callback?.apply(this, arguments);
                        ui.render();
                        return result;
                    };
                }
                ui.applyCompact();
                ui.render();
                return result;
            };
            const configured = proto.onConfigure;
            proto.onConfigure = function () {
                const result = configured?.apply(this, arguments);
                if (!this.title && this.properties?.compact) this.title = title;
                this._rayAnalog?.dymo.setText(this.properties?.ray_label || "");
                this._rayAnalog?.applyCompact();
                this._rayAnalog?.render();
                return result;
            };
            const removed = proto.onRemoved;
            proto.onRemoved = function () {
                this._rayAnalog?.cancelDrag?.();
                return removed?.apply(this, arguments);
            };
            const propertyChanged = proto.onPropertyChanged;
            proto.onPropertyChanged = function (key, value) {
                const result = propertyChanged?.apply(this, arguments);
                if (result === false) return result;
                if (key === "style" && !Object.hasOwn(styles, value)) this.properties.style = defaultStyle;
                if (key === "compact") this._rayAnalog?.applyCompact();
                if (key === "ray_label") this._rayAnalog?.dymo.setText(value);
                this._rayAnalog?.render();
                return result;
            };
            const connectionsChanged = proto.onConnectionsChange;
            proto.onConnectionsChange = function () {
                const result = connectionsChanged?.apply(this, arguments);
                this._rayAnalog?.render();
                return result;
            };
            const menu = proto.getExtraMenuOptions;
            proto.getExtraMenuOptions = function (canvas, options) {
                const result = menu?.apply(this, arguments);
                options.unshift(
                    // Deferred so the context menu has finished closing before the picker takes focus.
                    { content: `${kind === "knob" ? "Control" : "Switch"} Style…`,
                        callback: () => setTimeout(() => openStylePicker(this, kind, styles), 0) },
                    { content: `${this.properties.compact ? "● " : ""}Compact mode`,
                        callback: () => editNode(this, () => {
                            this.properties.compact = !this.properties.compact;
                            this._rayAnalog?.applyCompact();
                        }) },
                    { content: "Edit label…", callback: () => this._rayDymo?.beginEdit() },
                    { content: isMuted() ? "🔈 Unmute sound" : "🔇 Mute sound", callback: () => setMuted(!isMuted()) },
                );
                return result;
            };
        },
    });
}
