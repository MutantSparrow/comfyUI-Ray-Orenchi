// Response curves for the analog controls. A control can map its dial or fader position to its value through
// a curve instead of a straight line, like the taper of a potentiometer: a log taper gives fine control at the
// low end, an S-curve at both ends. The value the control stores and outputs is always the real value; the
// curve only decides how far along the dial that value sits, so saved values and the Python nodes are unchanged.
//
// A curve is a list of [x, y] points from (0, 0) to (1, 1): x is the position along the dial, y the fraction of
// the range. Points only ever move up and to the right, so the curve is a one-to-one map, and a smooth monotone
// curve is drawn through them.

export const POINT_LIMIT = 16;
export const MIN_GAP = 0.01;       // closest two points may sit on the x axis
const TABLE = 512;

import { ensurePanelStyles } from "./ray_panel.js";

const clamp01 = v => Math.max(0, Math.min(1, v));
const round = v => Math.round(v * 10000) / 10000;

// Typical pot tapers and a few useful shapes, sampled into points.
const sample = (fn, n = 8) => Array.from({ length: n + 1 }, (_, i) => [round(i / n), round(clamp01(fn(i / n)))]);
const AUDIO_K = 4.6;            // about 9% of the range at the middle of the dial, like an audio-taper pot
const audio = x => (Math.exp(AUDIO_K * x) - 1) / (Math.exp(AUDIO_K) - 1);
export const PRESETS = [
    { name: "Linear", linear: true, points: [[0, 0], [1, 1]] },
    { name: "Audio (log)", points: sample(audio) },
    { name: "Reverse audio", points: sample(x => 1 - audio(1 - x)) },
    { name: "Fine low end", points: sample(x => x ** 3) },
    { name: "Fine high end", points: sample(x => 1 - (1 - x) ** 3) },
    { name: "S-curve", points: sample(x => x * x * (3 - 2 * x)) },
    { name: "Fine centre", points: sample(x => 4 * (x - .5) ** 3 + .5) },
];
export const DEFAULT_CURVE = PRESETS[1].points;

// Valid points from anything: sorted, inside 0..1, ends pinned to (0,0) and (1,1), never going back down,
// no two closer than MIN_GAP, at most POINT_LIMIT. Returns null when `points` is not a list at all.
export function normalizePoints(points) {
    if (!Array.isArray(points)) return null;
    const inner = points
        .map(p => Array.isArray(p) ? [Number(p[0]), Number(p[1])] : [NaN, NaN])
        .filter(([x, y]) => Number.isFinite(x) && Number.isFinite(y))
        .map(([x, y]) => [clamp01(x), clamp01(y)])
        .filter(([x]) => x > MIN_GAP / 2 && x < 1 - MIN_GAP / 2)
        .sort((a, b) => a[0] - b[0]);
    const out = [[0, 0]];
    for (const [x, y] of inner) {
        const [px, py] = out[out.length - 1];
        if (x - px < MIN_GAP || out.length >= POINT_LIMIT - 1) continue;
        out.push([round(x), round(Math.max(y, py))]);
    }
    out.push([1, 1]);
    return out;
}

// Smooth monotone curve (Fritsch-Carlson cubic Hermite) through the points, sampled into a table so mapping
// either way is a lookup. `forward` takes a position to a fraction of the range; `inverse` goes back.
export function compile(points) {
    const pts = normalizePoints(points) || PRESETS[0].points;
    const n = pts.length;
    const dx = [], slope = [];
    for (let i = 0; i < n - 1; i++) {
        dx.push(pts[i + 1][0] - pts[i][0]);
        slope.push((pts[i + 1][1] - pts[i][1]) / dx[i]);
    }
    const tangent = new Array(n);
    tangent[0] = slope[0]; tangent[n - 1] = slope[n - 2];
    for (let i = 1; i < n - 1; i++) tangent[i] = slope[i - 1] * slope[i] <= 0 ? 0 : (slope[i - 1] + slope[i]) / 2;
    for (let i = 0; i < n - 1; i++) {
        if (slope[i] === 0) { tangent[i] = 0; tangent[i + 1] = 0; continue; }
        const a = tangent[i] / slope[i], b = tangent[i + 1] / slope[i], s = a * a + b * b;
        if (s > 9) { const k = 3 / Math.sqrt(s); tangent[i] = k * a * slope[i]; tangent[i + 1] = k * b * slope[i]; }
    }
    const table = new Float64Array(TABLE + 1);
    let seg = 0, floor = 0;
    for (let j = 0; j <= TABLE; j++) {
        const x = j / TABLE;
        while (seg < n - 2 && x > pts[seg + 1][0]) seg++;
        const h = dx[seg], u = (x - pts[seg][0]) / h, u2 = u * u, u3 = u2 * u;
        const y = (2 * u3 - 3 * u2 + 1) * pts[seg][1] + (u3 - 2 * u2 + u) * h * tangent[seg]
            + (-2 * u3 + 3 * u2) * pts[seg + 1][1] + (u3 - u2) * h * tangent[seg + 1];
        floor = Math.max(floor, clamp01(y));
        table[j] = floor;
    }
    table[0] = 0; table[TABLE] = 1;
    const forward = x => {
        const at = clamp01(x) * TABLE, i = Math.min(TABLE - 1, Math.floor(at));
        return table[i] + (table[i + 1] - table[i]) * (at - i);
    };
    const inverse = y => {
        if (y <= 0) return 0;
        if (y >= 1) return 1;
        let lo = 0, hi = TABLE;
        while (hi - lo > 1) { const mid = (lo + hi) >> 1; if (table[mid] < y) lo = mid; else hi = mid; }
        const span = table[hi] - table[lo];
        return (lo + (span > 0 ? (y - table[lo]) / span : 0)) / TABLE;
    };
    return { linear: false, points: pts, forward, inverse };
}

export const IDENTITY = { linear: true, points: PRESETS[0].points, forward: clamp01, inverse: clamp01 };

// The curve a node uses right now: a straight line unless its `response` property is "curve".
const compiled = new WeakMap();
export function curvePoints(node) {
    return normalizePoints(node.properties?.curve) || DEFAULT_CURVE;
}
export function responseOf(node) {
    if (node.properties?.response !== "curve") return IDENTITY;
    const key = JSON.stringify(node.properties.curve ?? null);
    const hit = compiled.get(node);
    if (hit?.key === key) return hit.response;
    const response = compile(curvePoints(node));
    compiled.set(node, { key, response });
    return response;
}

// The preset these points match, or "Custom".
export function presetName(points) {
    const key = JSON.stringify(normalizePoints(points));
    return PRESETS.find(p => !p.linear && JSON.stringify(normalizePoints(p.points)) === key)?.name || "Custom";
}

// ---------------------------------------------------------------------------
// Editor
// ---------------------------------------------------------------------------

const SIZE = 244, PAD = 18;
let lastPointer = [0, 0];
let savedPosition = null;      // where the editor was last left, so it reopens there
if (typeof window !== "undefined") {
    lastPointer = [window.innerWidth / 2, window.innerHeight / 3];
    window.addEventListener("pointerdown", event => { lastPointer = [event.clientX, event.clientY]; }, true);
}

function injectStyles() {
    ensurePanelStyles();
    if (document.getElementById("ray-curve-editor-style")) return;
    const style = document.createElement("style");
    style.id = "ray-curve-editor-style";
    style.textContent = `
.ray-curve-editor {
    position:fixed; z-index:100000; box-sizing:border-box; width:${SIZE + 24}px; padding:10px 12px 12px;
    box-shadow:0 10px 30px #000a; line-height:1.35;
}
.ray-curve-title {
    margin:-10px -12px 10px; padding:8px 12px; border-bottom:1px solid #2c2f35; border-radius:8px 8px 0 0;
    cursor:move; user-select:none; touch-action:none;
}
.ray-curve-title::before { content:"⠿"; margin-right:7px; letter-spacing:0; opacity:.7; }
.ray-curve-row { display:flex; gap:6px; align-items:center; margin-bottom:8px; }
.ray-curve-row > * { flex:1 1 0; min-width:0; }
.ray-curve-presets { display:grid; grid-template-columns:1fr 1fr; gap:4px; margin-bottom:8px; }
.ray-curve-presets button {
    padding:4px;
    white-space:nowrap; overflow:hidden; text-overflow:ellipsis;
}
.ray-curve-presets button[aria-pressed="true"] { background:#e2e2e2; border-color:#e2e2e2; color:#111; font-weight:600; }
.ray-curve-editor canvas { display:block; width:${SIZE}px; height:${SIZE}px; border-radius:4px; background:#101214; touch-action:none; outline:none; cursor:crosshair; }
.ray-curve-editor canvas:focus-visible { outline:2px solid #b9a4fa; outline-offset:2px; }
.ray-curve-info { min-height:2.7em; margin:7px 0 8px; font:11px/1.35 ui-monospace,monospace; color:#b9bdc4; }
.ray-curve-hint { margin:0 0 8px; font-size:10px; color:#8d9096; }
.ray-curve-done { width:100%; }
`;
    document.head.appendChild(style);
}

// `info()` returns { title, range: [lo, hi], format(value) }; `changed()` redraws the control after any edit.
let activeEditor;
export function openCurveEditor(node, { title = "Response curve", range = () => [0, 1], format = v => String(+Number(v).toPrecision(4)), changed = () => {} } = {}) {
    injectStyles();
    activeEditor?.close();
    const panel = document.createElement("div");
    panel.className = "ray-curve-editor rp-surface";
    panel.setAttribute("role", "dialog");
    panel.setAttribute("aria-label", "Response curve");
    const heading = Object.assign(document.createElement("p"), { className: "ray-curve-title rp-title", textContent: title, title: "Drag to move" });

    const modeRow = document.createElement("div");
    modeRow.className = "ray-curve-row";
    const mode = document.createElement("div");
    mode.className = "ray-curve-mode rp-seg";
    mode.setAttribute("role", "group");
    mode.setAttribute("aria-label", "Response");
    const linearButton = Object.assign(document.createElement("button"), { type: "button", textContent: "Linear" });
    const curveButton = Object.assign(document.createElement("button"), { type: "button", textContent: "Curve" });
    linearButton.title = "Map the control position evenly onto its output range";
    curveButton.title = "Use the editable response curve to map the control position onto its output range";
    mode.append(linearButton, curveButton);
    modeRow.append(mode);
    // Plain buttons, not a drop-down: a native list is drawn by the browser outside the page, and opening it
    // takes focus from the window.
    const presets = document.createElement("div");
    presets.className = "ray-curve-presets";
    presets.setAttribute("role", "group");
    presets.setAttribute("aria-label", "Presets");
    const presetButtons = PRESETS.slice(1).map(p => Object.assign(document.createElement("button"), { type: "button", textContent: p.name }));
    for (const button of presetButtons) button.title = `Apply the ${button.textContent} response curve`;
    presets.append(...presetButtons);

    const canvas = document.createElement("canvas");
    const ratio = Math.max(1, window.devicePixelRatio || 1);
    canvas.width = Math.round(SIZE * ratio); canvas.height = Math.round(SIZE * ratio);
    canvas.tabIndex = 0;
    canvas.setAttribute("role", "application");
    canvas.setAttribute("aria-label", "Curve: drag points, arrow keys move the selected point, Delete removes it");
    const info = Object.assign(document.createElement("div"), { className: "ray-curve-info" });
    info.setAttribute("aria-live", "polite");
    const hint = Object.assign(document.createElement("p"), { className: "ray-curve-hint",
        textContent: "Click to add a point · drag to shape · double-click or Delete removes · [ ] pick a point" });
    const done = Object.assign(document.createElement("button"), { type: "button", className: "ray-curve-done", textContent: "Done" });
    done.title = "Close the editor; response changes are already saved with the workflow";
    panel.append(heading, modeRow, presets, canvas, info, hint, done);
    document.body.append(panel);

    // ---- state -------------------------------------------------------------------------------------
    let points = curvePoints(node).map(p => [...p]);
    let selected = null, dragging = null, hover = null;
    const graph = node.graph;
    const isCurve = () => node.properties.response === "curve";
    const current = () => (isCurve() ? compile(points) : IDENTITY);
    const edit = fn => { graph?.beforeChange?.(); try { fn(); } finally { graph?.afterChange?.(); } };
    const store = () => { node.properties.curve = points.map(([x, y]) => [round(x), round(y)]); };
    const refresh = () => { changed(); node.setDirtyCanvas?.(true, true); draw(); sync(); };

    function sync() {
        linearButton.setAttribute("aria-pressed", String(!isCurve()));
        curveButton.setAttribute("aria-pressed", String(isCurve()));
        const name = isCurve() ? presetName(points) : null;
        for (const button of presetButtons) button.setAttribute("aria-pressed", String(button.textContent === name));
        canvas.style.opacity = isCurve() ? "1" : ".55";
        describe(hover);
    }

    // ---- geometry ----------------------------------------------------------------------------------
    const toPx = (x, y) => [PAD + x * (SIZE - 2 * PAD), SIZE - PAD - y * (SIZE - 2 * PAD)];
    const fromPx = (px, py) => [clamp01((px - PAD) / (SIZE - 2 * PAD)), clamp01((SIZE - PAD - py) / (SIZE - 2 * PAD))];
    const local = event => { const r = canvas.getBoundingClientRect(); return [(event.clientX - r.left) * SIZE / r.width, (event.clientY - r.top) * SIZE / r.height]; };
    const hit = (px, py) => {
        let best = -1, bestDistance = 11;
        points.forEach(([x, y], i) => { const [qx, qy] = toPx(x, y); const d = Math.hypot(qx - px, qy - py); if (d < bestDistance) { best = i; bestDistance = d; } });
        return best;
    };

    function draw() {
        const g = canvas.getContext("2d");
        g.setTransform(ratio, 0, 0, ratio, 0, 0);
        g.clearRect(0, 0, SIZE, SIZE);
        g.lineWidth = 1;
        g.strokeStyle = "#2a2e33";
        for (let i = 0; i <= 4; i++) {
            const [ax, ay] = toPx(i / 4, 0), [bx, by] = toPx(i / 4, 1), [cx, cy] = toPx(0, i / 4), [dx, dy] = toPx(1, i / 4);
            g.beginPath(); g.moveTo(ax, ay); g.lineTo(bx, by); g.moveTo(cx, cy); g.lineTo(dx, dy); g.stroke();
        }
        g.setLineDash([4, 4]); g.strokeStyle = "#4a4f57";
        g.beginPath(); g.moveTo(...toPx(0, 0)); g.lineTo(...toPx(1, 1)); g.stroke(); g.setLineDash([]);
        const response = compile(points), live = isCurve();
        g.strokeStyle = live ? "#e5b567" : "#6b6f77"; g.lineWidth = 2;
        g.beginPath();
        for (let i = 0; i <= 160; i++) { const x = i / 160, [px, py] = toPx(x, response.forward(x)); if (i) g.lineTo(px, py); else g.moveTo(px, py); }
        g.stroke();
        points.forEach(([x, y], i) => {
            const [px, py] = toPx(x, y), end = i === 0 || i === points.length - 1;
            g.fillStyle = i === selected ? "#ffffff" : live ? "#f3d9a4" : "#8a8e96";
            g.strokeStyle = "#101214"; g.lineWidth = 1.5;
            g.beginPath();
            if (end) g.rect(px - 4, py - 4, 8, 8); else g.arc(px, py, i === selected ? 5.5 : 4.5, 0, Math.PI * 2);
            g.fill(); g.stroke();
        });
        g.fillStyle = "#8d9096"; g.font = "9px ui-monospace,monospace";
        g.textAlign = "center"; g.fillText("dial position", SIZE / 2, SIZE - 4);
        g.save(); g.translate(8, SIZE / 2); g.rotate(-Math.PI / 2); g.fillText("value", 0, 0); g.restore();
    }

    // Four significant digits fit the panel however the control itself formats its value.
    const shown = value => format(Number(Number(value).toPrecision(4)));
    function describe(x) {
        const [lo, hi] = range();
        const response = current();
        if (x == null) {
            const mid = response.forward(.5);
            info.textContent = isCurve()
                ? `Dial middle gives ${shown(lo + mid * (hi - lo))} (${Math.round(mid * 100)}% of the range)`
                : "Straight line: the dial maps evenly onto the range.";
            return;
        }
        const y = response.forward(x);
        info.textContent = `Dial ${Math.round(x * 100)}% → ${shown(lo + y * (hi - lo))} (${Math.round(y * 100)}% of the range)`;
    }

    // ---- editing -----------------------------------------------------------------------------------
    function movePoint(i, x, y) {
        if (i <= 0 || i >= points.length - 1) return;
        const lowX = points[i - 1][0] + MIN_GAP, highX = points[i + 1][0] - MIN_GAP;
        points[i] = [Math.max(lowX, Math.min(highX, x)), Math.max(points[i - 1][1], Math.min(points[i + 1][1], y))];
        store();
    }
    function addPoint(x, y) {
        if (points.length >= POINT_LIMIT) return null;
        const at = points.findIndex(([px]) => px > x);
        if (at <= 0 || points[at][0] - x < MIN_GAP || x - points[at - 1][0] < MIN_GAP) return null;
        points.splice(at, 0, [x, Math.max(points[at - 1][1], Math.min(points[at][1], y))]);
        store();
        return at;
    }
    function removePoint(i) {
        if (i <= 0 || i >= points.length - 1) return;
        points.splice(i, 1);
        selected = null;
        store();
    }
    function useCurve() {
        if (!isCurve()) { node.properties.response = "curve"; }
        store();
    }

    canvas.addEventListener("pointerdown", event => {
        if (event.button !== 0) return;
        event.preventDefault();
        canvas.focus({ preventScroll: true });
        const [px, py] = local(event);
        let i = hit(px, py);
        graph?.beforeChange?.();
        if (i < 0) {
            const [x, y] = fromPx(px, py);
            useCurve();
            i = addPoint(x, y) ?? -1;
        } else useCurve();
        selected = i >= 0 ? i : null;
        dragging = i > 0 && i < points.length - 1 ? { id: event.pointerId, i } : null;
        if (dragging) canvas.setPointerCapture?.(event.pointerId);
        refresh();
        if (!dragging) { graph?.afterChange?.(); }
    });
    canvas.addEventListener("pointermove", event => {
        const [px, py] = local(event);
        const [x, y] = fromPx(px, py);
        hover = x;
        if (dragging && event.pointerId === dragging.id) { movePoint(dragging.i, x, y); refresh(); describe(points[dragging.i][0]); return; }
        describe(x);
    });
    const endDrag = event => {
        if (!dragging || (event?.pointerId != null && event.pointerId !== dragging.id)) return;
        dragging = null;
        graph?.afterChange?.();
    };
    for (const type of ["pointerup", "pointercancel", "lostpointercapture"]) canvas.addEventListener(type, endDrag);
    canvas.addEventListener("pointerleave", () => { hover = null; describe(null); });
    canvas.addEventListener("dblclick", event => {
        const i = hit(...local(event));
        if (i > 0 && i < points.length - 1) edit(() => { removePoint(i); }), refresh();
    });
    canvas.addEventListener("keydown", event => {
        const inner = points.length - 2;
        if (event.key === "[" || event.key === "]") {
            event.preventDefault();
            const from = selected ?? (event.key === "]" ? 0 : points.length - 1);
            selected = Math.max(1, Math.min(inner, from + (event.key === "]" ? 1 : -1)));
            draw(); return;
        }
        if (selected == null || selected <= 0 || selected >= points.length - 1) return;
        const step = event.shiftKey ? .001 : .01;
        const moves = { ArrowLeft: [-step, 0], ArrowRight: [step, 0], ArrowUp: [0, step], ArrowDown: [0, -step] };
        if (event.key === "Delete" || event.key === "Backspace") {
            event.preventDefault(); edit(() => { useCurve(); removePoint(selected); }); refresh();
        } else if (moves[event.key]) {
            event.preventDefault();
            const [dx, dy] = moves[event.key];
            edit(() => { useCurve(); movePoint(selected, points[selected][0] + dx, points[selected][1] + dy); });
            refresh();
        }
    });

    linearButton.addEventListener("click", () => { edit(() => { node.properties.response = "linear"; }); refresh(); });
    curveButton.addEventListener("click", () => { edit(() => { useCurve(); }); refresh(); });
    presetButtons.forEach(button => button.addEventListener("click", () => {
        const chosen = PRESETS.find(p => p.name === button.textContent);
        if (!chosen) return;
        edit(() => { points = chosen.points.map(p => [...p]); selected = null; useCurve(); });
        refresh();
    }));

    // ---- closing and placing -----------------------------------------------------------------------
    const stop = new AbortController();
    function close() {
        endDrag(); stop.abort(); panel.remove();
        if (node._rayCurveEditor?.panel === panel) node._rayCurveEditor = null;
        if (activeEditor?.panel === panel) activeEditor = null;
    }
    done.addEventListener("click", close);
    panel.addEventListener("keydown", event => event.stopPropagation());
    // Escape closes it wherever the keyboard focus is (after dragging the title bar it is no longer inside).
    window.addEventListener("keydown", event => { if (event.key === "Escape") { event.preventDefault(); event.stopPropagation(); close(); } }, { capture: true, signal: stop.signal });
    window.addEventListener("pointerdown", event => { if (!panel.contains(event.target)) close(); }, { capture: true, signal: stop.signal });
    const margin = 8;
    const place = (x, y) => {
        const box = panel.getBoundingClientRect();
        const left = Math.max(margin, Math.min(x, window.innerWidth - box.width - margin));
        const top = Math.max(margin, Math.min(y, window.innerHeight - box.height - margin));
        panel.style.left = `${left}px`; panel.style.top = `${top}px`;
        return [left, top];
    };
    const [startX, startY] = savedPosition || lastPointer;
    place(startX, startY);
    window.addEventListener("resize", () => place(panel.getBoundingClientRect().left, panel.getBoundingClientRect().top), { signal: stop.signal });

    // Drag the title bar to move the panel; it reopens wherever it was left.
    let moving = null;
    heading.addEventListener("pointerdown", event => {
        if (event.button !== 0) return;
        event.preventDefault();
        const box = panel.getBoundingClientRect();
        moving = { id: event.pointerId, dx: event.clientX - box.left, dy: event.clientY - box.top };
        try { heading.setPointerCapture(event.pointerId); } catch { /* the pointer is already gone */ }
    });
    heading.addEventListener("pointermove", event => {
        if (!moving || event.pointerId !== moving.id) return;
        savedPosition = place(event.clientX - moving.dx, event.clientY - moving.dy);
    });
    for (const type of ["pointerup", "pointercancel", "lostpointercapture"]) heading.addEventListener(type, () => { moving = null; });
    node._rayCurveEditor = activeEditor = { close, panel };
    draw(); sync();
    (isCurve() ? canvas : curveButton).focus({ preventScroll: true });
    return panel;
}
