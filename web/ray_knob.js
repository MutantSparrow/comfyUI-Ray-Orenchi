import { app } from "../../scripts/app.js";
import { KNOB_STYLES, DEFAULT_STYLE, getAllStyleCSS } from "./knob_styles.js";
import { findWidget, TWO_PI } from "./_common.js";
import { createPanel, changeValue, editNode, isLinked, mountControlSVG, registerAnalog } from "./analog_common.js";

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
    host.title = "Drag around the dial. Shift = fine adjustment. Arrow keys = step. Home / End = limits.";
    const input = document.createElement("input");
    input.className = "ray-analog-value";
    input.type = "text";
    input.inputMode = "decimal";
    input.setAttribute("aria-label", "Knob value");
    input.title = "Enter an exact value";
    readout.appendChild(input);
    const intReadout = document.createElement("span");
    intReadout.className = "ray-analog-int";
    readout.appendChild(intReadout);
    let currentStyle;
    let rotating = [], arc, slide;
    let drag = null;
    let lastText = "";
    const format = value => String(Number(value.toPrecision(8)));
    const disabled = () => isLinked(node, "knob_value") || !!widget.disabled || !!widget.computedDisabled;
    const render = () => {
        const key = Object.hasOwn(KNOB_STYLES, node.properties.style) ? node.properties.style : DEFAULT_STYLE;
        const style = KNOB_STYLES[key];
        if (key !== currentStyle) {
            mountControlSVG(host, style.svg);
            currentStyle = key;
            rotating = [...host.querySelectorAll("[data-rotate]")];
            arc = host.querySelector("[data-arc]");
            slide = host.querySelector("[data-slide]");
            element.dataset.panel = style.panel || "silver";
        }
        const [lo, hi] = bounds(node);
        const value = boundValue(node, widget.value);
        const fraction = hi > lo ? (value - lo) / (hi - lo) : 0;
        const turns = value / Math.max(.0001, number(node, "spin_value", 20));
        const angle = style.sweep ? -135 + fraction * 270 : (turns % 1) * 360;
        for (const el of rotating) el.setAttribute("transform", `rotate(${angle.toFixed(3)})`);
        if (arc) arc.setAttribute("stroke-dasharray", `${(((turns % 1) + 1) % 1 * 100).toFixed(2)} 100`);
        if (slide) slide.setAttribute("transform", `translate(0,${(43 - fraction * 86).toFixed(3)})`);
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
        hint.textContent = disabled() ? "EXTERNAL CONTROL" : `${format(lo)} … ${format(hi)}  /  SHIFT · FINE`;
    };
    ui.render = render;
    const setValue = (value, event) => {
        if (disabled()) return;
        changeValue(node, widget, boundValue(node, value), event);
        render();
    };
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
        const step = Math.max(.0001, number(node, "spin_value", 20) / 100) * (event.shiftKey ? .1 : 1);
        const increments = { ArrowUp: step, ArrowRight: step, ArrowDown: -step, ArrowLeft: -step, PageUp: step * 10, PageDown: -step * 10 };
        let value;
        if (event.key === "Home") value = lo;
        else if (event.key === "End") value = hi;
        else if (Object.hasOwn(increments, event.key)) value = boundValue(node, widget.value) + increments[event.key];
        else return;
        event.preventDefault();
        editNode(node, () => setValue(value, event));
    });
    const endDrag = event => {
        if (!drag || (event?.pointerId != null && event.pointerId !== drag.id)) return;
        const previous = drag;
        drag = null;
        element.dataset.dragging = "false";
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
        const rect = host.getBoundingClientRect();
        drag = { id: event.pointerId, x: rect.left + rect.width / 2, y: rect.top + rect.height / 2,
            lastX: event.clientX, lastY: event.clientY, height: rect.height, graph: node.graph };
        drag.graph?.beforeChange?.();
        host.setPointerCapture(event.pointerId);
        element.dataset.dragging = "true";
        window.addEventListener("blur", cancelDrag);
    });
    host.addEventListener("pointermove", event => {
        if (!drag || event.pointerId !== drag.id) return;
        event.preventDefault(); event.stopPropagation();
        if (!host.isConnected || disabled()) { cancelDrag(); return; }
        let delta;
        if (slide) {
            const [lo, hi] = bounds(node);
            delta = (drag.lastY - event.clientY) / Math.max(1, drag.height * 86 / 140) * (hi - lo);
        } else {
            const prev = Math.atan2(drag.lastY - drag.y, drag.lastX - drag.x);
            const next = Math.atan2(event.clientY - drag.y, event.clientX - drag.x);
            delta = Math.atan2(Math.sin(next - prev), Math.cos(next - prev)) / TWO_PI * number(node, "spin_value", 20);
            // Ignore the unstable angle close to the spindle.
            if (Math.hypot(event.clientX - drag.x, event.clientY - drag.y) < 8 ||
                Math.hypot(drag.lastX - drag.x, drag.lastY - drag.y) < 8) delta = 0;
        }
        drag.lastX = event.clientX; drag.lastY = event.clientY;
        setValue(boundValue(node, widget.value) + delta * (event.shiftKey ? .1 : 1), event);
    });
    for (const type of ["pointerup", "pointercancel", "lostpointercapture"]) host.addEventListener(type, endDrag);
    return ui;
}

registerAnalog(app, {
    kind: "knob", name: "RayKnob", title: "🎛️ Ray's Analog: Knob",
    styles: KNOB_STYLES, defaultStyle: DEFAULT_STYLE, valueName: "knob_value",
    configNames: ["min_value", "max_value", "spin_value", "clamp", "allow_negative"],
    outputs: [["int", "INT"], ["float", "FLOAT"]], build: buildKnob,
});
