import { app } from "../../scripts/app.js";
import {
    KNOB_STYLES,
    DEFAULT_STYLE,
    listStyles,
    getBrushedAluminumURL,
    getAllStyleCSS,
} from "./knob_styles.js";
import { TWO_PI } from "./_common.js";

const STYLE_ID = "ray-knob-styles";

function wrapPi(a) {
    while (a >  Math.PI) a -= TWO_PI;
    while (a < -Math.PI) a += TWO_PI;
    return a;
}

function getPropFloat(node, name, fallback) {
    const w = node.widgets?.find(w => w.name === name);
    const v = w ? Number(w.value) : NaN;
    return Number.isFinite(v) ? v : fallback;
}

function getPropBool(node, name, fallback) {
    const w = node.widgets?.find(w => w.name === name);
    return w ? !!w.value : fallback;
}

function applyBounds(node, raw) {
    const minV = getPropFloat(node, "min_value", -100);
    const maxV = getPropFloat(node, "max_value",  100);
    const allowNeg = getPropBool(node, "allow_negative", true);
    let lo = allowNeg ? minV : Math.max(0, minV);
    let hi = maxV;
    if (hi < lo) hi = lo;
    return Math.max(lo, Math.min(hi, raw));
}

function quantizeInt(node, f) {
    const c = getPropFloat(node, "clamp", 0);
    if (c <= 0) return Math.trunc(f);
    return Math.floor(f / c) * c;
}

function styleList() {
    const ks = listStyles();
    return ks.length ? ks : [DEFAULT_STYLE];
}

// Single global pointerdown/mousedown capture-phase listener. Iterates all live
// .ray-knob-wrap elements at click time and dispatches to their stashed onDown.
// Robust to Vue/Legacy mode switches — no stale closures.
let _globalDispatcherInstalled = false;
function installGlobalKnobDispatcher() {
    if (_globalDispatcherInstalled) return;
    _globalDispatcherInstalled = true;
    const handler = (e) => {
        if (e.button !== undefined && e.button !== 0) return;
        const wraps = document.querySelectorAll(".ray-knob-wrap");
        // Diagnostic — remove once stable
        if (wraps.length === 0) {
            console.log("[RayKnob] click but no .ray-knob-wrap in DOM", { type: e.type });
        }
        for (const w of wraps) {
            if (!w.isConnected || typeof w._rayKnobOnDown !== "function") continue;
            const r = w.getBoundingClientRect();
            if (r.width === 0 || r.height === 0) {
                console.log("[RayKnob] wrap has zero size", { w: r.width, h: r.height, top: r.top, left: r.left });
                continue;
            }
            if (e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom) continue;
            console.log("[RayKnob] dispatch hit", { type: e.type, target: e.target?.tagName });
            w._rayKnobOnDown(e);
            return;
        }
    };
    document.addEventListener("pointerdown", handler, true);
    document.addEventListener("mousedown",   handler, true);
}

function injectStylesOnce() {
    if (document.getElementById(STYLE_ID)) return;
    const tag = document.createElement("style");
    tag.id = STYLE_ID;
    tag.textContent = getAllStyleCSS() + `
.ray-knob-wrap {
    width:100%;
    display:flex;
    flex-direction:column;
    align-items:center;
    justify-content:center;
    user-select:none;
    touch-action:none;
    border-radius:4px;
    background-color:#b6b8bb;
    background-image:url("${getBrushedAluminumURL()}");
    background-repeat:repeat;
    background-size:256px 256px;
    box-shadow:inset 0 1px 0 rgba(255,255,255,0.35), inset 0 -1px 0 rgba(0,0,0,0.35);
    padding:6px 6px 4px;
    box-sizing:border-box;
}
.ray-knob-wrap .rk-host {
    width: 156px;
    height: 156px;
    max-width: 100%;
}
.ray-knob-wrap .rk-readout {
    color:#1a1a1a;
    font:11px ui-monospace, monospace;
    margin-top:4px;
    text-align:center;
    text-shadow:0 1px 0 rgba(255,255,255,0.45);
    line-height:1.1;
}`;
    document.head.appendChild(tag);
}

function buildKnobElement(node, kvw) {
    injectStylesOnce();

    const wrap = document.createElement("div");
    wrap.className = "ray-knob-wrap";

    const host = document.createElement("div");
    host.className = "rk-host";
    wrap.appendChild(host);

    const readout = document.createElement("div");
    readout.className = "rk-readout";
    wrap.appendChild(readout);

    let currentStyle = null;
    let pointerEl = null;
    let arcEl = null;

    const swapStyle = (key) => {
        const entry = KNOB_STYLES[key] || KNOB_STYLES[DEFAULT_STYLE];
        host.innerHTML = entry.svg;
        currentStyle = key;
        pointerEl = host.querySelector("[data-rotate]");
        arcEl     = host.querySelector("[data-arc]");
    };

    const render = () => {
        const styleKey = node.properties?.style || DEFAULT_STYLE;
        if (styleKey !== currentStyle) swapStyle(styleKey);

        const kv = Number(kvw?.value) || 0;
        const sv = getPropFloat(node, "spin_value", 20);

        // pointer rotation: full revolution per spin_value
        const angleFrac = sv > 0 ? (kv / sv) : 0;
        const deg = angleFrac * 360;
        // SVG attribute transform rotates around (0,0) — the knob center in our viewBox.
        if (pointerEl) pointerEl.setAttribute("transform", `rotate(${deg.toFixed(3)})`);

        // arc fill: 0..100 of pathLength, fraction of current revolution
        if (arcEl) {
            const f = ((angleFrac % 1) + 1) % 1;
            arcEl.setAttribute("stroke-dasharray", `${(f * 100).toFixed(2)} 100`);
        }

        const f = applyBounds(node, kv);
        const i = quantizeInt(node, f);
        readout.textContent = `${f.toFixed(2)}  →  ${i}`;
    };

    let lastAngle = null;
    let activePointerId = null;

    const knobCenter = () => {
        const r = host.getBoundingClientRect();
        return { cx: r.left + r.width / 2, cy: r.top + r.height / 2 };
    };

    const onDocMove = (e) => {
        if (lastAngle === null) return;
        const { cx, cy } = knobCenter();
        const cur = Math.atan2(e.clientY - cy, e.clientX - cx);
        const delta = wrapPi(cur - lastAngle);
        lastAngle = cur;
        const sv = getPropFloat(node, "spin_value", 20);
        const raw = (Number(kvw.value) || 0) + (delta / TWO_PI) * sv;
        kvw.value = applyBounds(node, raw);
        render();
        e.preventDefault();
        e.stopPropagation();
    };
    const onDocUp = (e) => {
        if (lastAngle === null) return;
        lastAngle = null;
        activePointerId = null;
        wrap.style.cursor = "grab";
        document.removeEventListener("pointermove",  onDocMove, true);
        document.removeEventListener("pointerup",    onDocUp,   true);
        document.removeEventListener("pointercancel", onDocUp,  true);
        document.removeEventListener("mousemove",    onDocMoveMouse, true);
        document.removeEventListener("mouseup",      onDocUp, true);
    };
    // Mouse fallback in case pointer events are blocked upstream
    const onDocMoveMouse = (e) => {
        if (lastAngle === null) return;
        const { cx, cy } = knobCenter();
        const cur = Math.atan2(e.clientY - cy, e.clientX - cx);
        const delta = wrapPi(cur - lastAngle);
        lastAngle = cur;
        const sv = getPropFloat(node, "spin_value", 20);
        const raw = (Number(kvw.value) || 0) + (delta / TWO_PI) * sv;
        kvw.value = applyBounds(node, raw);
        render();
        e.preventDefault();
        e.stopPropagation();
    };

    const onDown = (e) => {
        if (e.button !== undefined && e.button !== 0) return;
        const { cx, cy } = knobCenter();
        console.log("[RayKnob] pointerdown fired", { type: e.type, x: e.clientX, y: e.clientY, cx, cy });
        lastAngle = Math.atan2(e.clientY - cy, e.clientX - cx);
        activePointerId = e.pointerId;
        wrap.style.cursor = "grabbing";
        document.addEventListener("pointermove",  onDocMove,      true);
        document.addEventListener("pointerup",    onDocUp,        true);
        document.addEventListener("pointercancel", onDocUp,       true);
        document.addEventListener("mousemove",    onDocMoveMouse, true);
        document.addEventListener("mouseup",      onDocUp,        true);
        e.preventDefault();
        e.stopPropagation();
    };

    // Stash the per-knob onDown on the wrap itself. A single global capture listener finds
    // any live .ray-knob-wrap whose rect contains the click and dispatches. This survives
    // Vue/Legacy mode switches because nothing closes over a stale wrap reference.
    wrap._rayKnobOnDown = onDown;

    wrap.addEventListener("wheel",        (e) => e.stopPropagation(), { passive: true });
    wrap.addEventListener("contextmenu",  (e) => e.stopPropagation());
    installGlobalKnobDispatcher();

    swapStyle(node.properties?.style || DEFAULT_STYLE);
    render();

    return { element: wrap, render };
}

app.registerExtension({
    name: "Ray.Knob",

    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        if (nodeData.name !== "RayKnob") return;

        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const r = onNodeCreated?.apply(this, arguments);

            // black node body — brushed aluminium lives only under the knob widget
            this.bgcolor = "#000000";
            this.color   = "#000000";

            this.properties = this.properties || {};
            const styles = styleList();
            if (!styles.includes(this.properties.style)) {
                this.properties.style = DEFAULT_STYLE;
            }
            if (typeof this.addProperty === "function") {
                this.addProperty("style", this.properties.style, "enum", { values: styles });
            }

            const kvw = this.widgets?.find(w => w.name === "knob_value");
            if (kvw) {
                kvw.type = "hidden";
                kvw.computeSize = () => [0, -4];
                kvw.hidden = true;
                kvw.visible = false;
                kvw.advanced = true;
                if (kvw.options) kvw.options.hidden = true;
            }

            const node = this;
            const { element, render } = buildKnobElement(node, kvw);

            if (typeof this.addDOMWidget === "function") {
                element.style.minHeight = "184px";
                this.addDOMWidget("knob_ui", "RAY_KNOB", element, {
                    serialize: false,
                    hideOnZoom: false,
                    getMinHeight: () => 184,
                    getMaxHeight: () => 220,
                    getHeight: () => 184,
                });
            } else {
                console.warn("[RayKnob] addDOMWidget unavailable — knob requires modern ComfyUI frontend.");
            }

            node._knobRender = render;

            for (const name of ["min_value", "max_value", "allow_negative", "clamp", "spin_value"]) {
                const w = this.widgets?.find(w => w.name === name);
                if (!w) continue;
                const orig = w.callback;
                w.callback = function (v) {
                    if (kvw) kvw.value = applyBounds(node, Number(kvw.value) || 0);
                    render();
                    node.setDirtyCanvas?.(true, true);
                    return orig?.apply(this, arguments);
                };
            }

            this.size = this.computeSize ? this.computeSize() : this.size;
            requestAnimationFrame(render);
            return r;
        };

        const getExtraMenuOptions = nodeType.prototype.getExtraMenuOptions;
        nodeType.prototype.getExtraMenuOptions = function (canvas, options) {
            const node = this;
            const styles = styleList();
            options.unshift({
                content: "Knob Style",
                has_submenu: true,
                submenu: {
                    options: styles.map(s => ({
                        content: (node.properties?.style === s ? "● " : "  ") + (KNOB_STYLES[s]?.label || s),
                        callback: () => {
                            node.properties = node.properties || {};
                            node.properties.style = s;
                            node._knobRender?.();
                            node.setDirtyCanvas?.(true, true);
                        },
                    })),
                },
            });
            return getExtraMenuOptions?.apply(this, arguments);
        };

        const onPropertyChanged = nodeType.prototype.onPropertyChanged;
        nodeType.prototype.onPropertyChanged = function (name, value) {
            if (name === "style") {
                if (!styleList().includes(value)) {
                    this.properties.style = DEFAULT_STYLE;
                }
                this._knobRender?.();
                this.setDirtyCanvas?.(true, true);
            }
            return onPropertyChanged?.apply(this, arguments);
        };

        // Node body stays black; brushed aluminium is rendered only inside the knob widget DOM.
        const onDrawBackground = nodeType.prototype.onDrawBackground;
        nodeType.prototype.onDrawBackground = function (ctx) {
            this.bgcolor = "#000000";
            this.color   = "#000000";
            return onDrawBackground?.apply(this, arguments);
        };
    },
});
