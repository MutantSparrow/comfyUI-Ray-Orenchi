import { app } from "../../scripts/app.js";
import { SWITCH_STYLES, DEFAULT_SWITCH_STYLE, getAllSwitchStyleCSS } from "./switch_styles.js";
import { createPanel, changeValue, createWheelSteps, editNode, isLinked, mountControlSVG, registerAnalog } from "./analog_common.js";
import { playSwitch } from "./analog_audio.js";

function buildSwitch(node, widget) {
    const ui = createPanel(node, "switch", getAllSwitchStyleCSS());
    const { element, host, readout, hint } = ui;
    host.setAttribute("role", "switch");
    host.title = "Click, Space or Enter to switch";
    let currentStyle;
    let toggles = [], onOnly = [], offOnly = [], labels = [];
    const disabled = () => isLinked(node, "state") || !!widget.disabled || !!widget.computedDisabled;
    ui.render = () => {
        const key = Object.hasOwn(SWITCH_STYLES, node.properties.style) ? node.properties.style : DEFAULT_SWITCH_STYLE;
        if (key !== currentStyle) {
            const style = SWITCH_STYLES[key];
            mountControlSVG(host, style.svg);
            currentStyle = key;
            toggles = [...host.querySelectorAll("[data-toggle]")];
            onOnly = [...host.querySelectorAll("[data-on-only]")];
            offOnly = [...host.querySelectorAll("[data-off-only]")];
            labels = [...host.querySelectorAll("[data-readout]")];
            element.dataset.panel = style.panel || "silver";
        }
        const state = !!widget.value;
        host.dataset.state = state ? "on" : "off";
        host.setAttribute("aria-checked", String(state));
        host.setAttribute("aria-label", node.properties.ray_label || "Analog switch");
        host.setAttribute("aria-disabled", String(disabled()));
        for (const el of toggles) {
            const transform = state ? el.dataset.onTransform : el.dataset.offTransform;
            if (transform) el.setAttribute("transform", transform);
        }
        for (const el of onOnly) el.style.display = state ? "" : "none";
        for (const el of offOnly) el.style.display = state ? "none" : "";
        for (const el of labels) el.textContent = state ? "ON" : "OFF";
        readout.dataset.state = state ? "on" : "off";
        readout.textContent = state ? "●  ON" : "○  OFF";
        hint.textContent = disabled() ? "EXTERNAL CONTROL" : "BOOLEAN  /  CLICK · SPACE · ENTER";
    };
    // A real button supplies keyboard activation and a single click after pointerup.
    host.addEventListener("click", event => {
        event.stopPropagation();
        if (disabled()) return;
        const next = !widget.value;
        editNode(node, () => changeValue(node, widget, next, event));
        playSwitch(node.properties.style, next);
        ui.render();
    });
    // Mouse wheel: up switches on, down switches off.
    const wheelSteps = createWheelSteps();
    ui.wheel = (units, event) => {
        if (disabled()) return false;
        const steps = wheelSteps(units);
        if (steps && (steps > 0) !== !!widget.value) {
            const next = steps > 0;
            editNode(node, () => changeValue(node, widget, next, event));
            playSwitch(node.properties.style, next);
            ui.render();
        }
        return true;
    };
    return ui;
}

registerAnalog(app, {
    kind: "switch", name: "RaySwitch", title: "🎛️ Ray's Analog: Switch",
    styles: SWITCH_STYLES, defaultStyle: DEFAULT_SWITCH_STYLE, valueName: "state",
    outputs: [["bool", "BOOLEAN"]], build: buildSwitch, compactWidth: 180,
});
