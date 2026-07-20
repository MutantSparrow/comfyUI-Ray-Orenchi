// _common.js — Ray's Orenchi shared web utilities.
//
// One place for everything the per-node JS files used to reinvent:
//   TWO_PI                       — Math.PI * 2 constant.
//   getRadialBrushedURL()        — cached radial brushed-metal texture.
//   RAY_PALETTE                  — bucket color palette (see UI.md).
//   applyBucketTint(node, key)   — assign bg/edge color for a bucket.
//   shiftTint(hex, degrees)      — hue-rotate a base hex color (mode tints).
//   setWidgetHidden(n, w, hide)  — v2-frontend-safe hide/show for a widget.
//   mountDymoLabel(node, opts)   — Dymo embossed label (knob + switch).
//
// See UI.md for the canon these helpers implement.

export const TWO_PI = Math.PI * 2;

// ---------------------------------------------------------------------------
// Radial brushed-metal texture (knob + switch)
// ---------------------------------------------------------------------------

let _radialBrushedURL = null;

export function getRadialBrushedURL(palette = ["#f5f5f5", "#c8c8c8", "#7a7a7a"]) {
    if (_radialBrushedURL) return _radialBrushedURL;
    const SZ = 256, R = 128;
    const c = document.createElement("canvas");
    c.width = SZ; c.height = SZ;
    const x = c.getContext("2d");
    const g = x.createRadialGradient(R - 40, R - 50, 0, R, R, R);
    g.addColorStop(0, palette[0]);
    g.addColorStop(0.55, palette[1]);
    g.addColorStop(1, palette[2]);
    x.fillStyle = g;
    x.beginPath(); x.arc(R, R, R, 0, TWO_PI); x.fill();
    x.save();
    x.beginPath(); x.arc(R, R, R, 0, TWO_PI); x.clip();
    for (let i = 0; i < 800; i++) {
        const a = Math.random() * TWO_PI;
        const rs = R * (0.05 + Math.random() * 0.05);
        const re = R * (0.95 + Math.random() * 0.05);
        const alpha = 0.05 + Math.random() * 0.06;
        x.strokeStyle = Math.random() > 0.5 ? `rgba(255,255,255,${alpha})` : `rgba(0,0,0,${alpha * 0.7})`;
        x.lineWidth = 0.4 + Math.random() * 0.5;
        x.beginPath();
        x.moveTo(R + Math.cos(a) * rs, R + Math.sin(a) * rs);
        x.lineTo(R + Math.cos(a) * re, R + Math.sin(a) * re);
        x.stroke();
    }
    x.restore();
    _radialBrushedURL = c.toDataURL();
    return _radialBrushedURL;
}

// ---------------------------------------------------------------------------
// Palette + tint helpers
// ---------------------------------------------------------------------------

export const RAY_PALETTE = {
    VFX:     { bg: "#2a1f3a", edge: "#8a3ac8" },  // violet
    Analog:  { bg: "#000000", edge: "#000000" },  // black — knob / switch
    Prompts: { bg: "#1f3a2a", edge: "#3aa867" },  // green
    LLM:     { bg: "#1f2a4a", edge: "#3a73c8" },  // blue
};

export function applyBucketTint(node, bucketKey) {
    const pair = RAY_PALETTE[bucketKey];
    if (!pair || !node) return;
    node.bgcolor = pair.bg;
    node.color = pair.edge;
}

// Convert #rrggbb -> [r,g,b] 0-255.
function _hexToRgb(hex) {
    const m = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex || "");
    if (!m) return [0, 0, 0];
    return [parseInt(m[1], 16), parseInt(m[2], 16), parseInt(m[3], 16)];
}

function _rgbToHex(r, g, b) {
    const clamp = v => Math.max(0, Math.min(255, Math.round(v)));
    const h = v => clamp(v).toString(16).padStart(2, "0");
    return `#${h(r)}${h(g)}${h(b)}`;
}

function _rgbToHsl(r, g, b) {
    r /= 255; g /= 255; b /= 255;
    const mx = Math.max(r, g, b), mn = Math.min(r, g, b);
    const l = (mx + mn) / 2;
    let h = 0, s = 0;
    if (mx !== mn) {
        const d = mx - mn;
        s = l > 0.5 ? d / (2 - mx - mn) : d / (mx + mn);
        switch (mx) {
            case r: h = (g - b) / d + (g < b ? 6 : 0); break;
            case g: h = (b - r) / d + 2; break;
            case b: h = (r - g) / d + 4; break;
        }
        h *= 60;
    }
    return [h, s, l];
}

function _hslToRgb(h, s, l) {
    h = ((h % 360) + 360) % 360;
    const c = (1 - Math.abs(2 * l - 1)) * s;
    const x = c * (1 - Math.abs(((h / 60) % 2) - 1));
    const m = l - c / 2;
    let r = 0, g = 0, b = 0;
    if (h < 60)       [r, g, b] = [c, x, 0];
    else if (h < 120) [r, g, b] = [x, c, 0];
    else if (h < 180) [r, g, b] = [0, c, x];
    else if (h < 240) [r, g, b] = [0, x, c];
    else if (h < 300) [r, g, b] = [x, 0, c];
    else              [r, g, b] = [c, 0, x];
    return [(r + m) * 255, (g + m) * 255, (b + m) * 255];
}

// Rotate `hex` by `degrees` hue; preserve saturation + lightness.
export function shiftTint(hex, degrees = 0) {
    const [r0, g0, b0] = _hexToRgb(hex);
    const [h, s, l] = _rgbToHsl(r0, g0, b0);
    const [r1, g1, b1] = _hslToRgb(h + degrees, s, l);
    return _rgbToHex(r1, g1, b1);
}

// ---------------------------------------------------------------------------
// Widget hide / show (v2 frontend compat)
// ---------------------------------------------------------------------------
//
// V2 renders widgets whose `type === "converted-widget"` as pins only. Legacy
// still respects an explicit `hidden` flag. We stash the original type under
// a single property so any node can round-trip repeatedly.

const _HIDDEN_TYPE = "converted-widget";
const _ORIG_KEY = "_rayOrigType";
const _ORIG_COMPUTE = "_rayOrigCompute";

export function setWidgetHidden(node, widget, hidden) {
    if (!widget) return;
    if (hidden) {
        if (widget[_ORIG_KEY] === undefined) widget[_ORIG_KEY] = widget.type;
        if (widget[_ORIG_COMPUTE] === undefined && typeof widget.computeSize === "function") {
            widget[_ORIG_COMPUTE] = widget.computeSize;
        }
        widget.type = _HIDDEN_TYPE;
        widget.hidden = true;
        widget.computeSize = () => [0, -4];
    } else {
        if (widget[_ORIG_KEY] !== undefined) {
            widget.type = widget[_ORIG_KEY];
            delete widget[_ORIG_KEY];
        }
        widget.hidden = false;
        if (widget[_ORIG_COMPUTE] !== undefined) {
            widget.computeSize = widget[_ORIG_COMPUTE];
            delete widget[_ORIG_COMPUTE];
        } else if (widget.computeSize && widget.computeSize.toString().includes("[0, -4]")) {
            delete widget.computeSize;
        }
    }
    if (node && typeof node.setDirtyCanvas === "function") {
        node.setDirtyCanvas(true, true);
    }
}

export function findWidget(node, name) {
    if (!node || !Array.isArray(node.widgets)) return null;
    return node.widgets.find(w => w.name === name) || null;
}

// Inline preview panel was removed — nodes rely on their IMAGE output
// wired to a downstream Preview Image / Save Image node instead. See
// commit history for the deleted mountRayPreview / autowireRayPreview
// / send_preview implementation if you need to reintroduce something.

// ---------------------------------------------------------------------------
// Dymo embossed label
// ---------------------------------------------------------------------------
//
// A little strip of black plastic tape with raised white letters. Click to
// edit the caption; text persists per-node via `node.properties.ray_label`.
// Sized to sit above the analog control widget on knobs + switches.
//
// Visual model:
//   - Black tape with rounded corners and subtle drop shadow.
//   - Left/right punched holes (mounting-tab dots).
//   - Text: bold sans, uppercase, generous tracking, with a two-layer
//     shadow (dark underneath, light offset on top-left) to fake emboss.
//   - Focus outline switches from a hidden state to a soft yellow when
//     the tape is being edited.

const DYMO_STYLE_ID = "ray-dymo-styles";

function _injectDymoStylesOnce() {
    if (document.getElementById(DYMO_STYLE_ID)) return;
    const tag = document.createElement("style");
    tag.id = DYMO_STYLE_ID;
    tag.textContent = `
.ray-dymo {
    position: relative;
    display: flex; align-items: center; justify-content: center;
    width: 100%;
    min-height: 22px;
    margin: 4px 0 2px;
    padding: 4px 22px;
    box-sizing: border-box;
    background: linear-gradient(180deg, #1c1c1c 0%, #0a0a0a 50%, #050505 100%);
    /* Vintage sticky-label band — sharp square corners. */
    border-radius: 0;
    box-shadow:
        inset 0 1px 0 rgba(255,255,255,0.12),
        inset 0 -1px 0 rgba(0,0,0,0.7),
        0 1px 2px rgba(0,0,0,0.75);
    cursor: text;
    user-select: none;
    overflow: hidden;
}
.ray-dymo::before,
.ray-dymo::after {
    content: "";
    position: absolute;
    top: 50%;
    width: 4px; height: 4px;
    border-radius: 50%;
    background: radial-gradient(circle at 30% 30%, rgba(0,0,0,0.9), rgba(0,0,0,0.6));
    box-shadow: 0 0 1px rgba(255,255,255,0.15);
    transform: translateY(-50%);
}
.ray-dymo::before { left: 8px; }
.ray-dymo::after  { right: 8px; }
.ray-dymo-text {
    color: #f2f2f2;
    font: 700 11px/1 "Helvetica Neue", "Arial Narrow", sans-serif;
    text-transform: uppercase;
    letter-spacing: 0.18em;
    text-shadow:
         0 -1px 0 rgba(0,0,0,0.9),
         0  1px 0 rgba(255,255,255,0.18),
        -1px 0px 0 rgba(0,0,0,0.65);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    width: 100%;
    text-align: center;
    outline: none;
    caret-color: #f5c04a;
    min-height: 12px;
}
.ray-dymo-text:empty::before {
    content: attr(data-placeholder);
    color: #6a6a6a;
    letter-spacing: 0.18em;
    font-style: normal;
}
.ray-dymo[data-editing="1"] {
    box-shadow:
        inset 0 1px 0 rgba(255,255,255,0.18),
        inset 0 -1px 0 rgba(0,0,0,0.7),
        0 0 0 1px rgba(245,192,74,0.55),
        0 0 4px rgba(245,192,74,0.35);
}
`;
    document.head.appendChild(tag);
}

const _DYMO_KEY = "_rayDymo";

/**
 * Mount an embossed Dymo-style label on `node`. Returns a state object with
 *   { root, setText(text), getText() }
 * The label text is stored on `node.properties.ray_label` (serialized with
 * the workflow).
 */
export function mountDymoLabel(node, {
    placeholder = "LABEL",
    maxLength = 24,
} = {}) {
    if (!node) return null;
    if (node[_DYMO_KEY]) return node[_DYMO_KEY];
    _injectDymoStylesOnce();

    node.properties = node.properties || {};
    if (typeof node.properties.ray_label !== "string") {
        node.properties.ray_label = "";
    }

    const root = document.createElement("div");
    root.className = "ray-dymo";

    const text = document.createElement("div");
    text.className = "ray-dymo-text";
    text.dataset.placeholder = placeholder;
    text.contentEditable = "false";
    text.spellcheck = false;
    text.textContent = node.properties.ray_label || "";
    root.appendChild(text);

    const finishEdit = (commit) => {
        text.contentEditable = "false";
        root.dataset.editing = "";
        if (commit) {
            let v = (text.textContent || "").replace(/\s+/g, " ").trim();
            if (v.length > maxLength) v = v.slice(0, maxLength);
            text.textContent = v;
            node.properties.ray_label = v;
        } else {
            text.textContent = node.properties.ray_label || "";
        }
        node.setDirtyCanvas?.(true, true);
    };

    const beginEdit = () => {
        text.contentEditable = "true";
        root.dataset.editing = "1";
        text.focus();
        // Select all so a single keystroke replaces the old label.
        const range = document.createRange();
        range.selectNodeContents(text);
        const sel = window.getSelection?.();
        if (sel) { sel.removeAllRanges(); sel.addRange(range); }
    };

    root.addEventListener("dblclick", (e) => {
        e.preventDefault(); e.stopPropagation();
        beginEdit();
    });
    root.addEventListener("click", (e) => e.stopPropagation());
    root.addEventListener("pointerdown", (e) => e.stopPropagation());
    root.addEventListener("mousedown",   (e) => e.stopPropagation());
    root.addEventListener("wheel",       (e) => e.stopPropagation(), { passive: true });
    root.addEventListener("contextmenu", (e) => e.stopPropagation());

    text.addEventListener("keydown", (e) => {
        if (e.key === "Enter") { e.preventDefault(); text.blur(); return; }
        if (e.key === "Escape") { e.preventDefault(); finishEdit(false); text.blur(); return; }
        if (text.textContent && text.textContent.length >= maxLength &&
            e.key.length === 1 && !e.metaKey && !e.ctrlKey) {
            e.preventDefault();
        }
    });
    text.addEventListener("blur", () => finishEdit(true));
    text.addEventListener("paste", (e) => {
        e.preventDefault();
        const raw = (e.clipboardData || window.clipboardData)?.getData?.("text") || "";
        const clean = raw.replace(/\s+/g, " ").slice(0, maxLength);
        document.execCommand?.("insertText", false, clean);
    });

    const state = {
        root, text,
        setText(v) {
            const s = String(v || "").slice(0, maxLength);
            text.textContent = s;
            node.properties.ray_label = s;
            node.setDirtyCanvas?.(true, true);
        },
        getText() { return node.properties.ray_label || ""; },
        beginEdit,
    };
    node[_DYMO_KEY] = state;
    return state;
}
