import { app } from "../../scripts/app.js";
import { applyBucketTint, setWidgetHidden } from "./_common.js";
import { installPanel, openPanelSettings, iconButton, linkChip, linkOf, registerLinkTargets } from "./ray_panel.js";
import { createModelPicker } from "./model_picker.js";

const LOADER_ID = "RayQueuedModelLoader";
const PLACEHOLDER = "Select a diffusion model…";

const widget = (node, name) => node.widgets?.find(item => item.name === name);
const element = (tag, className, text) => {
    const item = document.createElement(tag);
    if (className) item.className = className;
    if (text !== undefined) item.textContent = text;
    return item;
};

function installLoader(node, definition) {
    if (node._rayQueuedLoader) { node._rayQueuedLoader.refresh(); return; }
    applyBucketTint(node, "Tools");
    const first = widget(node, "model_name"), rest = widget(node, "queued_models");
    setWidgetHidden(node, first, true); setWidgetHidden(node, rest, true);
    setWidgetHidden(node, widget(node, "spectrum_enabled"), true);
    const root = element("div", "rql-models"), list = element("div");
    const status = element("div", "rp-status"); status.setAttribute("role", "status");
    const spectrumStatus = element("div", "rp-status");
    const add = iconButton("plus", "Add model", () => write([...read(), ""]));
    const options = iconButton("settings", "Loader options", () => openPanelSettings(node, { sections: [
        { title: "Spectrum", fields: [{ name: "spectrum_enabled", label: "Enable Spectrum" }, { custom: () => {
            const note = element("div", "rp-status", "Automatically selects the installed Spectrum adapter for each model. Forecasting can change generated results. MOSS, MiniMax H3 and SDXL/Anima use dedicated adapters; other supported families use general Spectrum. Check the node status after running.");
            note.setAttribute("role", "note"); return note;
        } }] },
    ] }, "Queued Model Loader options"));
    for (const container of [root, list]) Object.assign(container.style, { display: "flex", flexDirection: "column", gap: "6px" });
    let signature = "", unregister = () => {}, pickers = [];
    const read = () => {
        let extra;
        try { extra = JSON.parse(rest.value || "[]"); } catch { extra = []; }
        return [first.value === PLACEHOLDER ? "" : String(first.value ?? ""), ...(Array.isArray(extra) ? extra : [])];
    };
    function write(models) {
        if (!models.length) models = [""];
        node.graph?.beforeChange?.();
        try {
            first.value = models[0]; rest.value = JSON.stringify(models.slice(1)); status.textContent = "";
            node._raySpectrumReport = null;
            first.callback?.(first.value); rest.callback?.(rest.value);
        } finally { node.graph?.afterChange?.(); }
        signature = ""; refresh(); node._rayPanel?.schedule(); node.setDirtyCanvas?.(true, true);
    }
    function refresh() {
        const count = read().length;
        status.textContent = count > 1 ? `${count} models · one workflow execution` : "";
        spectrumStatus.textContent = widget(node, "spectrum_enabled")?.value
            ? node._raySpectrumReport?.message || "Spectrum: Auto" : "";
        const linked = !!linkOf(node, "model_name"); add.disabled = linked;
        const next = JSON.stringify([first.value, rest.value, linked]);
        if (next === signature) return;
        signature = next; unregister(); pickers.forEach(picker => picker.destroy()); pickers = []; list.replaceChildren();
        const models = read(); let firstRow;
        for (const [index, model] of models.entries()) {
            const row = element("div", "rp-row rp-full"), label = element("label", "rp-label", `Model ${index + 1}`);
            const control = element("div", "rp-control");
            const picker = createModelPicker({ group: "diffusion_models", label: `Model ${index + 1}`, value: model,
                placeholder: PLACEHOLDER, disabled: () => index === 0 && !!linkOf(node, "model_name"),
                onSelect: selected => { const models = read();
                    if (index < models.length && models[index] === model) { models[index] = selected; write(models); }
                } });
            pickers.push(picker); const source = picker.element;
            source.id = `ray-model-${crypto.randomUUID()}`; label.htmlFor = source.id;
            const remove = iconButton("remove", `Remove model ${index + 1}`, () => {
                const models = read(); models.splice(index, 1); write(models);
            });
            remove.disabled = linked || (models.length === 1 && !model);
            control.append(source, remove);
            if (index === 0) {
                const chip = linkChip(node, "model_name", refresh); control.prepend(chip.element); chip.update();
                source.hidden = linked; firstRow = row;
            }
            row.append(label, control); list.append(row);
        }
        if (firstRow) unregister = registerLinkTargets(node, [{ name: "model_name", element: firstRow }], refresh);
        node._rayPanel?.schedule();
    }
    root.append(list, spectrumStatus, status);
    const panel = installPanel(node, { minWidth: 480, skip: ["model_name", "queued_models", "spectrum_enabled"],
        headerActions: [add, options],
        sections: [{ title: "Models", fields: [{ custom: () => root, update: refresh }] }] });
    const observer = new ResizeObserver(() => panel.schedule()); observer.observe(root);
    const removed = node.onRemoved;
    node.onRemoved = function () { observer.disconnect(); unregister(); pickers.forEach(picker => picker.destroy()); return removed?.apply(this, arguments); };
    node._rayQueuedLoader = { refresh, status }; refresh();
}

app.registerExtension({
    name: "Ray.QueuedModelLoader",
    beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== LOADER_ID) return;
        const created = nodeType.prototype.onNodeCreated, configured = nodeType.prototype.onConfigure,
            executed = nodeType.prototype.onExecuted;
        nodeType.prototype.onExecuted = function (message) {
            const result = executed?.apply(this, arguments);
            const reports = message?.queued_model_loader;
            if (reports?.length) {
                const attached = reports.filter(item => item.state === "attached").length;
                this._raySpectrumReport = { message: reports.length === 1 ? reports[0].message
                    : `Spectrum: ${attached} attached, ${reports.length - attached} native fallback`, reports };
                this._rayQueuedLoader?.refresh();
            }
            return result;
        };
        nodeType.prototype.onNodeCreated = function () {
            const result = created?.apply(this, arguments); installLoader(this, nodeData); return result;
        };
        nodeType.prototype.onConfigure = function () {
            const result = configured?.apply(this, arguments); installLoader(this, nodeData); return result;
        };
    },
});
