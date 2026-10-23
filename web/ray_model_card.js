import { app } from "../../scripts/app.js";
import { applyBucketTint, setWidgetHidden } from "./_common.js";
import { installPanel, openPanelSettings } from "./ray_panel.js";
import { openNameBuilder, resolveWidgetTokens, displayWidgetValue, renderDisplayName } from "./save_name.js";
import { notify } from "./browse_common.js";

const SECONDARY = ["image_width", "image_height", "card_width", "preview_width",
    "guidance_mode", "guidance", "max_images", "memory_limit_mb"];
const find = (node, name) => node.widgets?.find(w => w.name === name);

function openCardNameBuilder(node) {
    return openNameBuilder(node, { widgetName: "card_name", title: "Build card name", label: "Card name",
        defaultTemplate: "", fileTokens: false, separator: " ",
        note: "Spaces are preserved. Model loader widget values omit folders and file extensions. Blank uses MODEL CARD; a config =title takes precedence.",
        preview: (parts, context) => renderDisplayName(parts, context) || "MODEL CARD" });
}

export function openModelCardSettings(node) {
    return openPanelSettings(node, { sections: [
        { title: "Source generations", fields: ["image_width", "image_height"] },
        { title: "Model card", fields: ["card_width", "preview_width"] },
        { title: "Conditioning", fields: ["guidance_mode", { name: "guidance", when: n => find(n, "guidance_mode")?.value !== "disabled" }] },
        { title: "Run safeguards", fields: ["max_images", { name: "memory_limit_mb", label: "Output budget (MiB)" }] },
    ] }, "Model Card settings");
}

export function installModelCard(node, defaultConfig) {
    if (node._rayModelCard) return;
    node._rayModelCard = true;
    applyBucketTint(node, "Tools");
    const name = find(node, "card_name");
    if (name) name.serializeValue = async () => resolveWidgetTokens(name.value ?? "", node.graph, displayWidgetValue);
    const seed = find(node, "seed"), mode = find(node, "seed_mode");
    const control = seed?.linkedWidgets?.find(w => w.name === "control_after_generate") || find(node, "control_after_generate");
    if (mode && control) {
        control.value = mode.value;
        mode.serializeValue = async () => control.value;
        const callback = control.callback;
        control.callback = function (value) { mode.value = value; return callback?.apply(this, arguments); };
        setWidgetHidden(node, mode, true);
    }
    const copy = async () => {
        try {
            await navigator.clipboard.writeText(defaultConfig);
            const toast = app.extensionManager?.toast;
            if (toast?.add) toast.add({ severity: "success", summary: "Model Card", detail: "Default config copied", life: 2500 });
            const button = node._rayPanel?.root.querySelector('[data-action="copy-config"]');
            if (button) { button.textContent = "Copied"; setTimeout(() => { if (button.isConnected) button.textContent = "Copy Config"; }, 2000); }
        } catch (error) { notify(`Could not copy the default config: ${error.message}`); }
    };
    if (typeof node.addDOMWidget !== "function") {
        node.addWidget("button", "{ } Build card name", null, () => openCardNameBuilder(node), { serialize: false });
        node.addWidget("button", "Copy Config", null, copy, { serialize: false });
        node.addWidget("button", "Settings", null, () => openModelCardSettings(node), { serialize: false });
        return;
    }
    for (const name of SECONDARY) {
        const widget = find(node, name);
        if (widget) setWidgetHidden(node, widget, true);
    }
    installPanel(node, { skip: [...SECONDARY, ...(control ? ["seed_mode"] : [])], minWidth: 340, sections: [
        { fields: [{ name: "card_name", label: "Card name", full: true, placeholder: "MODEL CARD",
            actions: [{ label: "{ }", title: "Build card name", onClick: () => openCardNameBuilder(node) }] }] },
        { fields: ["seed", ...(!control ? ["seed_mode"] : []), "steps", { name: "cfg", label: "CFG" },
            { name: "sampler_name", label: "Sampler" }, "scheduler", "denoise"] },
        { fields: [{ custom() {
            const row = document.createElement("div"); row.className = "rp-control";
            for (const [text, action, callback] of [["Copy Config", "copy-config", copy], ["Settings", "settings", () => openModelCardSettings(node)]]) {
                const button = document.createElement("button"); button.type = "button";
                button.textContent = text; button.dataset.action = action;
                Object.assign(button.style, { flex: "1", height: "28px" });
                button.onclick = callback; row.append(button);
            }
            return row;
        } }] },
    ] });
}

app.registerExtension({
    name: "Ray.ModelCard",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== "RayModelCard") return;
        const defaultConfig = nodeData.input?.optional?.config?.[1]?.default;
        const created = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const result = created?.apply(this, arguments);
            installModelCard(this, defaultConfig);
            return result;
        };
        const configure = nodeType.prototype.onConfigure;
        nodeType.prototype.onConfigure = function () {
            const result = configure?.apply(this, arguments);
            // Keep links from workflows saved before the card-name field replaced the Settings selector.
            for (const input of this.inputs || []) {
                if (input.name === "model_name_source") input.name = "card_name";
                if (input.widget?.name === "model_name_source") input.widget.name = "card_name";
            }
            this._rayPanel?.schedule();
            return result;
        };
        const removed = nodeType.prototype.onRemoved;
        nodeType.prototype.onRemoved = function () {
            this._rayNameBuilder?.close();
            return removed?.apply(this, arguments);
        };
    },
});
