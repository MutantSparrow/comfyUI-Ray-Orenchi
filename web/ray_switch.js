import { app } from "../../scripts/app.js";
import { getBrushedAluminumURL } from "./knob_styles.js";
import {
    SWITCH_STYLES,
    DEFAULT_SWITCH_STYLE,
    listSwitchStyles,
    getAllSwitchStyleCSS,
} from "./switch_styles.js";
import { mountDymoLabel } from "./_common.js";

const STYLE_ID = "ray-switch-styles";

function styleList() {
    const ks = listSwitchStyles();
    return ks.length ? ks : [DEFAULT_SWITCH_STYLE];
}

// Single global capture-phase listener. Iterates all live .ray-switch-wrap elements
// at click time, hit-tests by bounding rect, dispatches to stashed _raySwitchOnDown.
// Survives V1↔V2 mode switches because nothing closes over a per-instance ref.
let _globalSwitchDispatcherInstalled = false;
function installGlobalSwitchDispatcher() {
    if (_globalSwitchDispatcherInstalled) return;
    _globalSwitchDispatcherInstalled = true;
    const handler = (e) => {
        if (e.button !== undefined && e.button !== 0) return;
        const wraps = document.querySelectorAll(".ray-switch-wrap");
        for (const w of wraps) {
            if (!w.isConnected || typeof w._raySwitchOnDown !== "function") continue;
            const r = w.getBoundingClientRect();
            if (r.width === 0 || r.height === 0) continue;
            if (e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom) continue;
            w._raySwitchOnDown(e);
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
    tag.textContent = getAllSwitchStyleCSS() + `
.ray-switch-wrap {
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
.ray-switch-wrap.rs-compact {
    background:transparent;
    box-shadow:none;
    padding:0;
}
.ray-switch-wrap .rs-host {
    width: 156px;
    height: 156px;
    max-width: 100%;
}
.ray-switch-wrap .rs-readout {
    color:#1a1a1a;
    font:11px ui-monospace, monospace;
    margin-top:4px;
    text-align:center;
    text-shadow:0 1px 0 rgba(255,255,255,0.45);
    line-height:1.1;
    letter-spacing:0.08em;
}
.ray-switch-wrap.rs-compact .rs-readout { display:none; }
.ray-switch-wrap.rs-compact .ray-dymo   { display:none; }`;
    document.head.appendChild(tag);
}

function buildSwitchElement(node, sw) {
    injectStylesOnce();

    const wrap = document.createElement("div");
    wrap.className = "ray-switch-wrap";

    // Dymo label above the switch face; hidden in compact mode via CSS.
    const dymo = mountDymoLabel(node, { placeholder: "LABEL" });
    if (dymo?.root) wrap.appendChild(dymo.root);

    const host = document.createElement("div");
    host.className = "rs-host";
    wrap.appendChild(host);

    const readout = document.createElement("div");
    readout.className = "rs-readout";
    wrap.appendChild(readout);

    const applyCompact = () => {
        const c = !!node.properties?.compact;
        wrap.classList.toggle("rs-compact", c);
    };
    applyCompact();
    node._raySwitchApplyCompact = applyCompact;

    let currentStyle = null;

    const swapStyle = (key) => {
        const entry = SWITCH_STYLES[key] || SWITCH_STYLES[DEFAULT_SWITCH_STYLE];
        host.innerHTML = entry.svg;
        currentStyle = key;
    };

    const render = () => {
        const styleKey = node.properties?.style || DEFAULT_SWITCH_STYLE;
        if (styleKey !== currentStyle) swapStyle(styleKey);

        const state = !!sw?.value;
        host.dataset.state = state ? "on" : "off";

        const tog = host.querySelector("[data-toggle]");
        if (tog) {
            const t = state ? tog.dataset.onTransform : tog.dataset.offTransform;
            if (t) tog.setAttribute("transform", t);
        }
        host.querySelectorAll("[data-on-only]").forEach(el  => { el.style.display = state ? "" : "none"; });
        host.querySelectorAll("[data-off-only]").forEach(el => { el.style.display = state ? "none" : ""; });

        const ro = host.querySelector("[data-readout]");
        const txt = state ? "ON" : "OFF";
        if (ro) ro.textContent = txt;
        readout.textContent = txt;
    };

    const onDown = (e) => {
        if (e.button !== undefined && e.button !== 0) return;
        if (sw) sw.value = !sw.value;
        render();
        node.setDirtyCanvas?.(true, true);
        e.preventDefault();
        e.stopPropagation();
    };

    wrap._raySwitchOnDown = onDown;

    wrap.addEventListener("wheel",       (e) => e.stopPropagation(), { passive: true });
    wrap.addEventListener("contextmenu", (e) => e.stopPropagation());
    installGlobalSwitchDispatcher();

    swapStyle(node.properties?.style || DEFAULT_SWITCH_STYLE);
    render();

    return { element: wrap, render };
}

app.registerExtension({
    name: "Ray.Switch",

    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        if (nodeData.name !== "RaySwitch") return;

        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const r = onNodeCreated?.apply(this, arguments);

            this.bgcolor = "#000000";
            this.color   = "#000000";

            this.properties = this.properties || {};
            const styles = styleList();
            if (!styles.includes(this.properties.style)) {
                this.properties.style = DEFAULT_SWITCH_STYLE;
            }
            if (typeof this.properties.compact !== "boolean") {
                this.properties.compact = false;
            }
            if (typeof this.properties.ray_label !== "string") {
                this.properties.ray_label = "";
            }
            if (typeof this.addProperty === "function") {
                this.addProperty("style", this.properties.style, "enum", { values: styles });
                this.addProperty("compact", this.properties.compact, "boolean");
                this.addProperty("ray_label", this.properties.ray_label, "string");
            }

            const sw = this.widgets?.find(w => w.name === "state");
            if (sw) {
                sw.type = "hidden";
                sw.computeSize = () => [0, -4];
                sw.hidden = true;
                sw.visible = false;
                sw.advanced = true;
                if (sw.options) sw.options.hidden = true;
            }

            const node = this;
            const { element, render } = buildSwitchElement(node, sw);

            if (typeof this.addDOMWidget === "function") {
                element.style.minHeight = "184px";
                this.addDOMWidget("switch_ui", "RAY_SWITCH", element, {
                    serialize: false,
                    hideOnZoom: false,
                    getMinHeight: () => 184,
                    getMaxHeight: () => 220,
                    getHeight: () => 184,
                });
            } else {
                console.warn("[RaySwitch] addDOMWidget unavailable — switch requires modern ComfyUI frontend.");
            }

            node._switchRender = render;

            this.size = this.computeSize ? this.computeSize() : this.size;
            requestAnimationFrame(render);
            return r;
        };

        const getExtraMenuOptions = nodeType.prototype.getExtraMenuOptions;
        nodeType.prototype.getExtraMenuOptions = function (canvas, options) {
            const node = this;
            const styles = styleList();
            const compact = !!node.properties?.compact;
            options.unshift(
                {
                    content: "Switch Style",
                    has_submenu: true,
                    submenu: {
                        options: styles.map(s => ({
                            content: (node.properties?.style === s ? "● " : "  ") + (SWITCH_STYLES[s]?.label || s),
                            callback: () => {
                                node.properties = node.properties || {};
                                node.properties.style = s;
                                node._switchRender?.();
                                node.setDirtyCanvas?.(true, true);
                            },
                        })),
                    },
                },
                {
                    content: (compact ? "● " : "  ") + "Compact mode",
                    callback: () => {
                        node.properties = node.properties || {};
                        node.properties.compact = !node.properties.compact;
                        node._raySwitchApplyCompact?.();
                        node.setDirtyCanvas?.(true, true);
                    },
                },
                {
                    content: "Edit label…",
                    callback: () => { node._rayDymo?.beginEdit?.(); },
                },
            );
            return getExtraMenuOptions?.apply(this, arguments);
        };

        const onPropertyChanged = nodeType.prototype.onPropertyChanged;
        nodeType.prototype.onPropertyChanged = function (name, value) {
            if (name === "style") {
                if (!styleList().includes(value)) {
                    this.properties.style = DEFAULT_SWITCH_STYLE;
                }
                this._switchRender?.();
                this.setDirtyCanvas?.(true, true);
            } else if (name === "compact") {
                this._raySwitchApplyCompact?.();
                this.setDirtyCanvas?.(true, true);
            }
            return onPropertyChanged?.apply(this, arguments);
        };

        const onConfigure = nodeType.prototype.onConfigure;
        nodeType.prototype.onConfigure = function () {
            const r = onConfigure?.apply(this, arguments);
            setTimeout(() => {
                if (this._rayDymo && typeof this.properties?.ray_label === "string") {
                    this._rayDymo.setText(this.properties.ray_label);
                }
                this._raySwitchApplyCompact?.();
                this._switchRender?.();
            }, 0);
            return r;
        };

        const onDrawBackground = nodeType.prototype.onDrawBackground;
        nodeType.prototype.onDrawBackground = function (ctx) {
            this.bgcolor = "#000000";
            this.color   = "#000000";
            return onDrawBackground?.apply(this, arguments);
        };
    },
});
