import { app } from "../../scripts/app.js";
import { KNOB_STYLES, DEFAULT_STYLE, getAllStyleCSS } from "./knob_styles.js";
import { findWidget } from "./_common.js";
import { createPanel, changeValue, editNode, isLinked, mountControlSVG, registerAnalog, wheelEdit } from "./analog_common.js";
import { createKnobFeel } from "./analog_audio.js";
import { responseOf } from "./analog_curve.js";

// Shift slows any drag to this fraction of normal speed.
const FINE = .05;
const SWEEP_DEGREES = 270;

function number(node, name, fallback) {
    const value = Number(findWidget(node, name)?.value);
    return Number.isFinite(value) ? value : fallback;
}

export function bounds(node) {
    const min = number(node, "min_value", -100);
    const lo = findWidget(node, "allow_negative")?.value === false ? Math.max(0, min) : min;
    return [lo, Math.max(lo, number(node, "max_value", 100))];
}

export function boundValue(node, raw) {
    const [lo, hi] = bounds(node);
    const value = Number(raw);
    return Math.max(lo, Math.min(hi, Number.isFinite(value) ? value : 0));
}

export function quantizeInt(node, value) {
    const step = number(node, "clamp", 0);
    return Math.trunc(step > 0 ? Math.floor(value / step) * step : value);
}

function buildKnob(node, widget) {
    const ui = createPanel(node, "knob", getAllStyleCSS());
    const { element, host, readout, hint } = ui;
    host.setAttribute("role", "slider");
    host.title = "Drag the dial or slider. Click a slider track to jump. Shift = fine adjustment. Arrow keys = step. Home / End = limits.";
    const input = document.createElement("input");
    input.className = "ray-analog-value";
    input.type = "text";
    input.inputMode = "decimal";
    input.setAttribute("aria-label", "Control value");
    input.title = "Enter an exact value";
    readout.appendChild(input);
    const intReadout = document.createElement("span");
    intReadout.className = "ray-analog-int";
    readout.appendChild(intReadout);
    let currentStyle;
    let rotating = [], arc, slide, fills = [], leds = [];
    let drag = null;
    const feel = createKnobFeel(() => node.properties.style, () => !!slide);
    let lastText = "";
    const format = value => String(Number(value.toPrecision(8)));
    const disabled = () => isLinked(node, "knob_value") || !!widget.disabled || !!widget.computedDisabled;
    const slideAxis = () => slide?.dataset.axis === "x" ? "x" : "y";
    // Slider travel is 86 of the face's 140 SVG units, centred. Convert the pointer to 0..1 along it.
    const faceMetrics = () => {
        const rect = host.getBoundingClientRect();
        return { rect, unit: Math.max(1, Math.min(rect.width, rect.height) / 140) };
    };
    const pointerFraction = event => {
        const { rect, unit } = faceMetrics();
        return slideAxis() === "x"
            ? ((event.clientX - (rect.left + rect.width / 2)) / unit + 43) / 86
            : (43 - (event.clientY - (rect.top + rect.height / 2)) / unit) / 86;
    };
    // Where a value sits on the dial, 0..1 from min to max, through the control's response curve.
    const position = value => {
        const [lo, hi] = bounds(node);
        return hi > lo ? responseOf(node).inverse((value - lo) / (hi - lo)) : 0;
    };
    // The value at a dial position, and a value moved along the dial by `delta` of its travel.
    const valueAt = pos => {
        const [lo, hi] = bounds(node);
        const fraction = responseOf(node).forward(pos);
        return fraction >= 1 ? hi : lo + fraction * (hi - lo);
    };
    const nudged = (value, delta) => valueAt(position(value) + delta);
    const render = () => {
        const key = Object.hasOwn(KNOB_STYLES, node.properties.style) ? node.properties.style : DEFAULT_STYLE;
        const style = KNOB_STYLES[key];
        if (key !== currentStyle) {
            mountControlSVG(host, style.svg);
            currentStyle = key;
            rotating = [...host.querySelectorAll("[data-rotate]")];
            arc = host.querySelector("[data-arc]");
            slide = host.querySelector("[data-slide]");
            fills = [...host.querySelectorAll("[data-fill]")];
            leds = [...host.querySelectorAll("[data-led]")].map(el => ({
                el, at: Number(el.dataset.led), on: el.dataset.on ?? "1", off: el.dataset.off ?? ".18",
            }));
            element.dataset.panel = style.panel || "silver";
            element.dataset.control = slide ? "slider" : "knob";
        }
        const [lo, hi] = bounds(node);
        const value = boundValue(node, widget.value);
        const fraction = position(value);
        const angle = -SWEEP_DEGREES / 2 + fraction * SWEEP_DEGREES;
        for (const el of rotating) el.setAttribute("transform", `rotate(${angle.toFixed(3)})`);
        // The arc ring is drawn starting at 7:30; its path length is 100 for a full circle.
        if (arc) arc.setAttribute("stroke-dasharray", `${(fraction * SWEEP_DEGREES / 3.6).toFixed(2)} 100`);
        if (slide) {
            const across = -43 + fraction * 86;
            slide.setAttribute("transform", slideAxis() === "x"
                ? `translate(${across.toFixed(3)},0)` : `translate(0,${(-across).toFixed(3)})`);
        }
        for (const el of fills) {
            el.setAttribute("transform", el.dataset.axis === "y" ? `scale(1,${fraction.toFixed(4)})` : `scale(${fraction.toFixed(4)},1)`);
        }
        for (const led of leds) led.el.style.opacity = fraction > led.at ? led.on : led.off;
        const text = format(value);
        if (document.activeElement !== input && input.value !== text) input.value = text;
        const integerText = `INT ${quantizeInt(node, value)}`;
        if (lastText !== integerText) { intReadout.textContent = integerText; lastText = integerText; }
        host.setAttribute("aria-label", node.properties.ray_label || "Analog knob");
        host.setAttribute("aria-valuemin", String(lo));
        host.setAttribute("aria-valuemax", String(hi));
        host.setAttribute("aria-valuenow", String(value));
        host.setAttribute("aria-valuetext", `${text}; ${integerText}`);
        host.setAttribute("aria-disabled", String(disabled()));
        input.disabled = disabled();
        hint.textContent = disabled() ? "EXTERNAL CONTROL"
            : `${format(lo)} … ${format(hi)}  /  ${responseOf(node).linear ? "" : "CURVE  /  "}SHIFT · FINE`;
    };
    ui.render = render;
    const setValue = (value, event) => {
        if (disabled()) return;
        const before = boundValue(node, widget.value);
        changeValue(node, widget, boundValue(node, value), event);
        const after = boundValue(node, widget.value);
        if (after !== before) {
            const [lo, hi] = bounds(node);
            feel.move(position(before), position(after), { stop: after === lo || after === hi });
        }
        render();
    };
    // Mouse wheel: 2% of the dial per notch, a tenth of that with Shift.
    ui.wheel = (units, event) => {
        if (disabled()) return false;
        const step = units * .02 * (event.shiftKey ? .1 : 1);
        wheelEdit(node, () => setValue(Number(nudged(boundValue(node, widget.value), step).toPrecision(10)), event), feel.end);
        return true;
    };
    ui.curveInfo = () => ({
        title: `Response curve · ${node.properties.ray_label || "Control"}`,
        range: () => bounds(node), format, changed: () => ui.render(),
    });
    input.addEventListener("change", event => {
        const value = input.value.trim() === "" ? NaN : Number(input.value);
        if (Number.isFinite(value)) editNode(node, () => setValue(value, event));
        input.value = format(boundValue(node, widget.value));
    });
    input.addEventListener("keydown", event => {
        if (event.key === "Enter") { event.preventDefault(); input.blur(); }
        if (event.key === "Escape") {
            event.preventDefault(); input.value = format(boundValue(node, widget.value)); input.blur();
        }
    });
    host.addEventListener("keydown", event => {
        const [lo, hi] = bounds(node);
        const step = 1 / 200 * (event.shiftKey ? .1 : 1);
        const increments = { ArrowUp: step, ArrowRight: step, ArrowDown: -step, ArrowLeft: -step, PageUp: step * 10, PageDown: -step * 10 };
        let value;
        if (event.key === "Home") value = lo;
        else if (event.key === "End") value = hi;
        else if (Object.hasOwn(increments, event.key)) value = nudged(boundValue(node, widget.value), increments[event.key]);
        else return;
        event.preventDefault();
        editNode(node, () => setValue(value, event));
    });
    const endDrag = event => {
        if (!drag || (event?.pointerId != null && event.pointerId !== drag.id)) return;
        const previous = drag;
        drag = null;
        element.dataset.dragging = "false";
        feel.end();
        if (host.hasPointerCapture?.(previous.id)) host.releasePointerCapture(previous.id);
        window.removeEventListener("blur", cancelDrag);
        previous.graph?.afterChange?.();
    };
    const cancelDrag = () => endDrag();
    ui.cancelDrag = cancelDrag;
    host.addEventListener("pointerdown", event => {
        if (event.button !== 0 || event.isPrimary === false || disabled() || drag) return;
        event.preventDefault(); event.stopPropagation();
        host.focus({ preventScroll: true });
        const { rect, unit } = faceMetrics();
        drag = { id: event.pointerId, x: rect.left + rect.width / 2, y: rect.top + rect.height / 2,
            lastX: event.clientX, lastY: event.clientY, unit, graph: node.graph };
        drag.graph?.beforeChange?.();
        host.setPointerCapture(event.pointerId);
        element.dataset.dragging = "true";
        window.addEventListener("blur", cancelDrag);
        // Clicking the track outside the cap jumps there; grabbing the cap drags it without a jump.
        if (slide) {
            const target = pointerFraction(event);
            const current = position(boundValue(node, widget.value));
            if (Math.abs(target - current) > .17) setValue(valueAt(Math.max(0, Math.min(1, target))), event);
        }
    });
    host.addEventListener("pointermove", event => {
        if (!drag || event.pointerId !== drag.id) return;
        event.preventDefault(); event.stopPropagation();
        if (!host.isConnected || disabled()) { cancelDrag(); return; }
        let delta;
        if (slide) {
            const moved = slideAxis() === "x" ? event.clientX - drag.lastX : drag.lastY - event.clientY;
            delta = moved / (drag.unit * 86);
        } else {
            const prev = Math.atan2(drag.lastY - drag.y, drag.lastX - drag.x);
            const next = Math.atan2(event.clientY - drag.y, event.clientX - drag.x);
            // The dial follows the pointer: a full sweep of the dial covers min to max.
            delta = Math.atan2(Math.sin(next - prev), Math.cos(next - prev)) / (SWEEP_DEGREES * Math.PI / 180);
            // Ignore the unstable angle close to the spindle.
            if (Math.hypot(event.clientX - drag.x, event.clientY - drag.y) < 8 ||
                Math.hypot(drag.lastX - drag.x, drag.lastY - drag.y) < 8) delta = 0;
        }
        drag.lastX = event.clientX; drag.lastY = event.clientY;
        setValue(nudged(boundValue(node, widget.value), delta * (event.shiftKey ? FINE : 1)), event);
    });
    for (const type of ["pointerup", "pointercancel", "lostpointercapture"]) host.addEventListener(type, endDrag);
    return ui;
}

// Older workflows saved a spin_value widget between max_value and clamp. Drop its saved value and
// input slot, shifting links into the later slots, so nothing lands in the wrong widget. The old layout is
// recognised by shape, not length: allow_negative, a boolean, sat fifth ([min, max, spin, clamp, allow,
// value]), while now the fifth value is the number the knob holds. (The face's own widget adds a sixth,
// empty value to every current save, so six values alone does not mean an old workflow.)
export function removeSpinValue(data) {
    const links = Array.isArray(data?.links) ? data.links : [];
    const read = (link, index, key) => Array.isArray(link) ? link[index] : link?.[key];
    for (const node of data?.nodes || []) {
        if (node?.type !== "RayKnob") continue;
        const values = node.widgets_values;
        if (Array.isArray(values) && values.length >= 6 && typeof values[4] === "boolean") values.splice(2, 1);
        const at = Array.isArray(node.inputs) ? node.inputs.findIndex(input => input?.name === "spin_value") : -1;
        if (at < 0) continue;
        node.inputs.splice(at, 1);
        for (const link of [...links]) {
            if (read(link, 3, "target_id") !== node.id) continue;
            const slot = read(link, 4, "target_slot");
            if (slot > at) {
                if (Array.isArray(link)) link[4] = slot - 1; else link.target_slot = slot - 1;
            } else if (slot === at) {
                const id = read(link, 0, "id"), origin = read(link, 1, "origin_id");
                links.splice(links.indexOf(link), 1);
                for (const source of data.nodes) {
                    if (source.id !== origin) continue;
                    for (const output of source.outputs || []) {
                        if (Array.isArray(output.links)) output.links = output.links.filter(l => l !== id);
                    }
                }
            }
        }
    }
    for (const subgraph of data?.definitions?.subgraphs || []) removeSpinValue(subgraph);
}

registerAnalog(app, {
    kind: "knob", name: "RayKnob", title: "🎛️ Ray's Analog: Control (Knob / Slider)",
    styles: KNOB_STYLES, defaultStyle: DEFAULT_STYLE, valueName: "knob_value",
    configNames: ["min_value", "max_value", "clamp", "allow_negative"],
    outputs: [["int", "INT"], ["float", "FLOAT"]], build: buildKnob, migrate: removeSpinValue, curve: true, compactWidth: 180,
    panel: () => ({ skip: ["knob_value"], sections: [{ title: "Range", fields: [
        { name: "min_value", label: "Min" }, { name: "max_value", label: "Max" },
        { name: "clamp", label: "INT step" }, { name: "allow_negative", label: "Allow negative" },
    ] }] }),
});
