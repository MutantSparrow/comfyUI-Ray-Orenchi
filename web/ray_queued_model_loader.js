import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";
import { applyBucketTint, setWidgetHidden } from "./_common.js";
import { installPanel, openPanelSettings, iconButton, linkChip, linkOf, registerLinkTargets } from "./ray_panel.js";
import { browsePath, notify } from "./browse_common.js";
import { PLACEHOLDER, planSweep, submitSweep } from "./queued_model_loader.mjs";

const LOADER_ID = "RayQueuedModelLoader";

const outputTypes = new Set();
let modelNames;
const availableModels = () => modelNames ||= api.fetchApi("/models/diffusion_models")
    .then(response => response.ok ? response.json() : []).catch(() => []);
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
    const root = element("div", "rql-models"), list = element("div"), choices = element("datalist");
    choices.id = `ray-queued-models-${crypto.randomUUID()}`;
    availableModels().then(names => {
        for (const name of names) {
            const option = element("option"); option.value = name; choices.append(option);
        }
    });
    const status = element("div", "rp-status"); status.setAttribute("role", "status");
    const controls = element("div", "rp-control");
    const spectrumStatus = element("div", "rp-status");
    const add = iconButton("plus", "Add model", () => write([...read(), ""]));
    const options = iconButton("edit", "Loader options", () => openPanelSettings(node, { sections: [
        { title: "Spectrum", fields: [{ name: "spectrum_enabled", label: "Enable Spectrum" }, { custom: () => {
            const note = element("div", "rp-status", "Automatically selects the installed Spectrum adapter for each model. Forecasting can change generated results. MOSS, MiniMax H3 and SDXL/Anima use dedicated adapters; other supported families use general Spectrum. Check the node status after running.");
            note.setAttribute("role", "note"); return note;
        } }] },
    ] }, "Queued Model Loader options"));
    options.style.marginLeft = "auto"; controls.append(add, options);
    for (const container of [root, list]) Object.assign(container.style, { display: "flex", flexDirection: "column", gap: "6px" });
    let signature = "", unregister = () => {};
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
            first.callback?.(first.value); rest.callback?.(rest.value);
        } finally { node.graph?.afterChange?.(); }
        signature = ""; refresh(); node._rayPanel?.schedule(); node.setDirtyCanvas?.(true, true);
    }
    function refresh() {
        spectrumStatus.textContent = widget(node, "spectrum_enabled")?.value
            ? node._raySpectrumReport?.message || "Spectrum: Auto" : "";
        const linked = !!linkOf(node, "model_name"); add.disabled = linked;
        const next = JSON.stringify([first.value, rest.value, linked]);
        if (next === signature) return;
        signature = next; unregister(); list.replaceChildren();
        const models = read(); let firstRow;
        for (const [index, model] of models.entries()) {
            const row = element("div", "rp-row rp-full"), label = element("label", "rp-label", `Model ${index + 1}`);
            const control = element("div", "rp-control"), source = element("input", "rp-input");
            source.value = model; source.placeholder = "Select a diffusion model…";
            source.setAttribute("list", choices.id); source.setAttribute("aria-label", `Model ${index + 1}`);
            source.id = `${choices.id}-${index}`; label.htmlFor = source.id;
            source.title = model || "Choose a registered diffusion model or browse to a file";
            source.onchange = () => { const models = read(); models[index] = source.value; write(models); };
            for (const type of ["keydown", "keyup", "keypress"]) source.addEventListener(type, event => event.stopPropagation());
            const browse = iconButton("file", `Choose model ${index + 1} file`, async () => {
                try {
                    const selected = await browsePath("file", source.value, { title: "Choose diffusion model",
                        filters: [["Diffusion models", ["safetensors", "sft", "ckpt", "pt", "pt2", "pth", "bin", "pkl"]]] });
                    if (selected) {
                        const models = read();
                        if (index < models.length && models[index] === model) { models[index] = selected; write(models); }
                    }
                } catch (error) { notify(error.message); }
            });
            const remove = iconButton("minus", `Remove model ${index + 1}`, () => {
                const models = read(); models.splice(index, 1); write(models);
            });
            remove.innerHTML = '<svg viewBox="0 0 24 24"><path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13M10 10v7M14 10v7"/></svg>';
            remove.disabled = linked || (models.length === 1 && !model);
            control.append(source, browse, remove);
            if (index === 0) {
                const chip = linkChip(node, "model_name", refresh); control.prepend(chip.element); chip.update();
                source.hidden = linked; browse.disabled = linked; firstRow = row;
            }
            row.append(label, control); list.append(row);
        }
        if (firstRow) unregister = registerLinkTargets(node, [{ name: "model_name", element: firstRow }], refresh);
        node._rayPanel?.schedule();
    }
    root.append(choices, list, controls, spectrumStatus, status);
    const panel = installPanel(node, { minWidth: 480, skip: ["model_name", "queued_models", "spectrum_enabled"],
        sections: [{ title: "Models", fields: [{ custom: () => root, update: refresh }] }] });
    const observer = new ResizeObserver(() => panel.schedule()); observer.observe(root);
    const removed = node.onRemoved;
    node.onRemoved = function () { observer.disconnect(); unregister(); return removed?.apply(this, arguments); };
    node._rayQueuedLoader = { refresh, status }; refresh();
}

app.registerExtension({
    name: "Ray.QueuedModelLoader",
    setup() {
        const original = api.queuePrompt;
        api.queuePrompt = async function (number, prompt, options) {
            const graph = app.rootGraph || app.graph;
            const widgetNames = Object.fromEntries((graph?._nodes || []).map(node => [String(node.id),
                (node.widgets || []).filter(item => item.serialize !== false && item.options?.serialize !== false).map(item => item.name)]));
            const plan = planSweep(prompt, { outputTypes, widgetNames, partialExecutionTargets: options?.partialExecutionTargets });
            if (!plan) return original.apply(this, arguments);
            const response = await api.fetchApi("/ray/queued-model-loader/validate", { method: "POST",
                headers: { "Content-Type": "application/json" }, body: JSON.stringify({ models: plan.models }) });
            const data = await response.json();
            if (!response.ok || data.error) throw Error(data.error || "The selected models could not be validated.");
            const node = app.rootGraph?.getNodeById(plan.id) || app.graph?.getNodeById(plan.id);
            const status = node?._rayQueuedLoader?.status;
            try {
                return await submitSweep(plan, number, options, (...args) => original.apply(this, args), (count, total) => {
                    if (status) status.textContent = `Queued ${count} / ${total} models`;
                });
            } catch (error) { if (status) status.textContent = error.message; throw error; }
        };
    },
    beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.output_node) outputTypes.add(nodeData.name);
        if (nodeData.name !== LOADER_ID) return;
        const created = nodeType.prototype.onNodeCreated, configured = nodeType.prototype.onConfigure,
            executed = nodeType.prototype.onExecuted;
        nodeType.prototype.onExecuted = function (message) {
            const result = executed?.apply(this, arguments);
            if (message?.queued_model_loader?.[0]) {
                this._raySpectrumReport = message.queued_model_loader[0]; this._rayQueuedLoader?.refresh();
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
