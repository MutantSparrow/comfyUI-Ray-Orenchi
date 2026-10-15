import { app } from "../../scripts/app.js";
import { findWidget, setWidgetHidden } from "./_common.js";
import { createPanel, changeValue, editNode, isLinked, registerAnalog, wheelEdit } from "./analog_common.js";
import { FADER_STYLES, DEFAULT_FADER_STYLE, getFaderStyleCSS } from "./fader_styles.js";
import { createKnobFeel } from "./analog_audio.js";
import { responseOf } from "./analog_curve.js";

const MIN_FADERS = 2, MAX_FADERS = 10, DEFAULT_FADERS = 4;   // in a row
const MAX_ROWS = 4, TOTAL_FADERS = MAX_FADERS * MAX_ROWS;
const ROW = 120;           // px of face height each row past the first adds
const FINE = .05;          // Shift slows a drag to this fraction
const CAP = 18;            // px: cap height; the cap travels the track minus this
const STRIP = 38;          // px of node width per fader

export function clampCount(value) {
    const count = Math.trunc(Number(value));
    return Number.isFinite(count) ? Math.max(MIN_FADERS, Math.min(MAX_FADERS, count)) : DEFAULT_FADERS;
}

export function clampRows(value) {
    const rows = Math.trunc(Number(value));
    return Number.isFinite(rows) ? Math.max(1, Math.min(MAX_ROWS, rows)) : 1;
}

export function clampLevel(value) {
    const level = Number(value);
    return Number.isFinite(level) ? Math.max(0, Math.min(1, level)) : .5;
}

function element(tag, className, text) {
    const el = document.createElement(tag);
    if (className) el.className = className;
    if (text !== undefined) el.textContent = text;
    return el;
}

// Output 0 is the list of every active fader; the others are one per fader. Only the first `count` of
// those are shown, so the slot numbers of the visible ones never change.
export function syncOutputs(node, count) {
    if (!Array.isArray(node.outputs) || typeof node.removeOutput !== "function" || typeof node.addOutput !== "function") return;
    while (node.outputs.length > count + 1) node.removeOutput(node.outputs.length - 1);
    while (node.outputs.length < count + 1) node.addOutput(`fader_${node.outputs.length}`, "FLOAT");
}

// Workflows saved before rows existed hold the count, ten faders and (in the real frontend) the face widget's
// empty value. `rows` and faders 11-40 were added after the first ten, so slot their defaults in where they now
// belong instead of letting the face's value land in `rows`.
export function addFaderRows(data) {
    for (const node of data?.nodes || []) {
        const values = node?.widgets_values;
        if (node?.type !== "RayFaderBank" || !Array.isArray(values)) continue;
        const old = values.length === MAX_FADERS + 1 || (values.length === MAX_FADERS + 2 && typeof values[MAX_FADERS + 1] !== "number");
        if (old) node.widgets_values = [...values.slice(0, MAX_FADERS + 1), 1, ...Array(TOTAL_FADERS - MAX_FADERS).fill(.5), ...values.slice(MAX_FADERS + 1)];
    }
    for (const subgraph of data?.definitions?.subgraphs || []) addFaderRows(subgraph);
}

function buildFaders(node, firstWidget) {
    const ui = createPanel(node, "fader", getFaderStyleCSS());
    const { element: panel, host, readout, hint } = ui;
    host.tabIndex = -1;
    host.setAttribute("role", "group");
    host.setAttribute("aria-label", "Fader bank");
    const countWidget = findWidget(node, "faders"), rowsWidget = findWidget(node, "rows");
    const widgets = [firstWidget];
    for (let i = 2; i <= TOTAL_FADERS; i++) {
        const w = findWidget(node, `fader_${i}`);
        if (w) { widgets.push(w); setWidgetHidden(node, w, true); }
    }
    const readoutText = element("span", "ray-fader-readout");
    readout.append(readoutText);
    const feel = createKnobFeel(() => node.properties.style, () => true);

    let strips = [], built = "", last = 0, drag = null;
    // Faders in a row, rows, and every fader: rows are filled in order, so fader 7 of a 6-wide bank opens row 2.
    const perRow = () => clampCount(countWidget?.value);
    const rows = () => clampRows(rowsWidget?.value);
    const count = () => Math.min(perRow() * rows(), widgets.length);
    const level = i => clampLevel(widgets[i]?.value);
    // Where a fader's cap sits on its track, 0..1, through the bank's response curve; and a fader moved along
    // its track by `delta` of the travel, as a value.
    const trackAt = i => responseOf(node).inverse(level(i));
    const nudged = (i, delta) => responseOf(node).forward(trackAt(i) + delta);
    const disabled = i => isLinked(node, `fader_${i + 1}`) || !!widgets[i]?.disabled || !!widgets[i]?.computedDisabled;
    const format = value => value.toFixed(2);

    function setLevel(i, value, event) {
        if (disabled(i)) return;
        const before = level(i), after = clampLevel(Number(value.toFixed(3)));
        if (after === before) return;
        changeValue(node, widgets[i], after, event);
        last = i;
        feel.move(before, after, { stop: after === 0 || after === 1 });
        ui.render();
    }

    function fractionAt(strip, event) {
        const rect = strip.track.getBoundingClientRect();
        const travel = Math.max(1, rect.height - CAP);
        return { fraction: (rect.bottom - CAP / 2 - event.clientY) / travel, travel };
    }

    function endDrag(event) {
        if (!drag || (event?.pointerId != null && event.pointerId !== drag.id)) return;
        const previous = drag;
        drag = null;
        previous.strip.el.dataset.active = "false";
        feel.end();
        if (previous.strip.el.hasPointerCapture?.(previous.id)) previous.strip.el.releasePointerCapture(previous.id);
        window.removeEventListener("blur", cancelDrag);
        previous.graph?.afterChange?.();
    }
    function cancelDrag() { endDrag(); }
    ui.cancelDrag = cancelDrag;

    function rebuild(n, width) {
        host.replaceChildren();
        strips = [];
        let line = null;
        for (let i = 0; i < n; i++) {
            if (i % width === 0) { line = element("div", "ray-fader-row"); host.append(line); }
            const el = element("div", "ray-fader-strip");
            el.tabIndex = 0;
            el.setAttribute("role", "slider");
            el.setAttribute("aria-orientation", "vertical");
            el.setAttribute("aria-valuemin", "0");
            el.setAttribute("aria-valuemax", "1");
            el.setAttribute("aria-label", `Fader ${i + 1}`);
            const track = element("div", "ray-fader-track");
            track.append(element("div", "ray-fader-scale"), element("div", "ray-fader-slot"), element("div", "ray-fader-cap"));
            el.append(track, element("div", "ray-fader-num", String(i + 1)));
            const strip = { el, track, cap: track.lastChild, at: null };
            el.addEventListener("pointerdown", event => {
                if (event.button !== 0 || event.isPrimary === false || disabled(i) || drag) return;
                event.preventDefault(); event.stopPropagation();
                el.focus({ preventScroll: true });
                last = i;
                drag = { id: event.pointerId, strip, i, lastY: event.clientY, graph: node.graph };
                drag.graph?.beforeChange?.();
                el.setPointerCapture(event.pointerId);
                el.dataset.active = "true";
                window.addEventListener("blur", cancelDrag);
                // Grabbing the cap drags it where it is; the track elsewhere jumps the cap to the pointer.
                const { fraction } = fractionAt(strip, event);
                if (Math.abs(fraction - trackAt(i)) > CAP / Math.max(1, strip.track.getBoundingClientRect().height - CAP) * .6) {
                    setLevel(i, responseOf(node).forward(fraction), event);
                }
                ui.render();
            });
            el.addEventListener("pointermove", event => {
                if (!drag || event.pointerId !== drag.id || drag.strip !== strip) return;
                event.preventDefault(); event.stopPropagation();
                if (!el.isConnected || disabled(i)) { cancelDrag(); return; }
                const { travel } = fractionAt(strip, event);
                const moved = (drag.lastY - event.clientY) / travel * (event.shiftKey ? FINE : 1);
                drag.lastY = event.clientY;
                setLevel(i, nudged(i, moved), event);
            });
            for (const type of ["pointerup", "pointercancel", "lostpointercapture"]) el.addEventListener(type, endDrag);
            el.addEventListener("keydown", event => {
                const fine = event.shiftKey ? .1 : 1;
                const steps = { ArrowUp: .01, ArrowRight: .01, ArrowDown: -.01, ArrowLeft: -.01, PageUp: .1, PageDown: -.1 };
                let value;
                if (event.key === "Home") value = 0;
                else if (event.key === "End") value = 1;
                else if (Object.hasOwn(steps, event.key)) value = nudged(i, steps[event.key] * fine);
                else return;
                event.preventDefault();
                editNode(node, () => setLevel(i, value, event));
            });
            el.addEventListener("focus", () => { last = i; ui.render(); });
            line.append(el);
            strips.push(strip);
        }
    }

    ui.render = () => {
        const n = count(), width = perRow(), shape = `${n}/${width}`;
        if (shape !== built) {
            const first = !built;
            built = shape;
            cancelDrag();
            rebuild(n, width);
            syncOutputs(node, n);
            // Grow the node to fit a wider row or an added row; never shrink what the user sized.
            const size = node.computeSize?.(), need = 28 + width * STRIP;
            const w = Math.max(node.size?.[0] || 0, need), h = Math.max(node.size?.[1] || 0, first ? 0 : size?.[1] || 0);
            if (w !== node.size?.[0] || h !== node.size?.[1]) node.setSize?.([w, h || 250]);
        } else if (node.outputs && node.outputs.length !== n + 1) {
            syncOutputs(node, n);
        }
        const key = Object.hasOwn(FADER_STYLES, node.properties.style) ? node.properties.style : DEFAULT_FADER_STYLE;
        panel.dataset.style = key;
        panel.dataset.panel = FADER_STYLES[key].panel || "silver";
        strips.forEach((strip, i) => {
            const value = level(i), track = trackAt(i);
            if (strip.at !== track || strip.value !== value) {
                strip.at = track; strip.value = value;
                strip.el.style.setProperty("--v", String(track));
                strip.el.setAttribute("aria-valuenow", String(value));
                strip.el.setAttribute("aria-valuetext", format(value));
                strip.el.title = `Fader ${i + 1}: ${format(value)}`;
            }
            strip.el.setAttribute("aria-disabled", String(disabled(i)));
        });
        const shown = Math.min(last, n - 1);
        readoutText.textContent = `F${shown + 1}  ${format(level(shown))}`;
        const any = strips.some((_, i) => disabled(i));
        hint.textContent = `${n} FADERS  /  0 … 1  /  ${responseOf(node).linear ? "" : "CURVE  /  "}${any ? "SOME EXTERNAL  /  " : ""}SHIFT · FINE`;
    };

    // Mouse wheel over a fader: 2% per notch, a tenth of that with Shift. Anywhere else the canvas keeps it.
    ui.wheel = (units, event) => {
        const at = strips.findIndex(strip => strip.el.contains(event.target));
        if (at < 0 || disabled(at)) return false;
        const step = units * .02 * (event.shiftKey ? .1 : 1);
        wheelEdit(node, () => setLevel(at, nudged(at, step), event), feel.end);
        return true;
    };

    ui.minHeight = () => 250 + (rows() - 1) * ROW;
    ui.compactMinWidth = () => 28 + perRow() * 24;

    ui.curveInfo = () => ({
        title: `Response curve · ${node.properties.ray_label || "Fader Bank"}`,
        range: () => [0, 1], format: value => value.toFixed(3), changed: () => ui.render(),
    });

    ui.render();
    return ui;
}

registerAnalog(app, {
    kind: "fader", name: "RayFaderBank", title: "🎛️ Ray's Analog: Fader Bank",
    extensionName: "Ray.FaderBank", menuName: "Fader",
    styles: FADER_STYLES, defaultStyle: DEFAULT_FADER_STYLE, valueName: "fader_1", configNames: ["faders", "rows"],
    panel: () => ({ skip: Array.from({ length: TOTAL_FADERS }, (_, i) => `fader_${i + 1}`), minWidth: 240, sections: [{ title: "Bank", fields: [
        { name: "faders", label: "Per row" }, { name: "rows", label: "Rows" },
    ] }] }),
    outputs: [["values", "FLOAT"], ...Array.from({ length: TOTAL_FADERS }, (_, i) => [`fader_${i + 1}`, "FLOAT"])],
    build: buildFaders, curve: true, migrate: addFaderRows,
    heights: ui => ({ min: ui.minHeight(), max: undefined }),
});
