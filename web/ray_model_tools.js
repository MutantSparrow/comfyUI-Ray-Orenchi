import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";
import { installPanel, linkOf } from "./ray_panel.js";
import { applyBucketTint, setWidgetHidden } from "./_common.js";
import { browseInto, notify } from "./browse_common.js";
import { metadataRows, rowsToMetadata, mergeFields, filterTensors, parseMetadataJSON } from "./model_tools_ui.mjs";

const IDS = new Set(["RayModelLoadAs", "RayModelConvert", "RayModelSave", "RayModelMetadata", "RayModelMetadataSave",
    "RayModelMerge", "RayModelInspector", "RayModelCompare", "RayLoraBake", "RayLoraExtract"]);
const widget = (node, name) => node.widgets?.find(w => w.name === name);
const value = (node, name) => widget(node, name)?.value ?? "";
const el = (tag, text, className) => {
    const element = document.createElement(tag);
    if (text !== undefined) element.textContent = text;
    if (className) element.className = className;
    return element;
};
const button = (label, callback) => {
    const b = el("button", label); b.type = "button"; b.onclick = callback; return b;
};
function setValue(node, name, next) {
    const target = widget(node, name);
    if (!target) return;
    node.graph?.beforeChange?.();
    try { target.value = next; target.callback?.(next); }
    finally { node.graph?.afterChange?.(); }
    node.setDirtyCanvas?.(true, true);
}
function styles() {
    if (document.getElementById("ray-model-tools-style")) return;
    const style = el("style"); style.id = "ray-model-tools-style";
    style.textContent = `.rmt{display:flex;flex-direction:column;gap:7px;min-width:0;width:100%;pointer-events:auto}
    .rmt [hidden]{display:none!important}.rmt-toolbar{display:flex;align-items:center;gap:6px;flex-wrap:wrap}.rmt button{height:28px;padding:4px 9px}.rmt input,.rmt textarea,.rmt select{background:#141414;color:#eee;border:1px solid #3a3a3a;border-radius:5px;padding:4px 9px;font:12px system-ui;min-width:0}
    .rmt input{width:100%}.rmt textarea{width:100%;resize:vertical;min-height:54px;max-height:240px;font:11px monospace}.rmt pre{font:11px monospace;white-space:pre-wrap;word-break:break-word;margin:0;max-height:240px;overflow:auto}
    .rmt-scroll{max-height:330px;overflow:auto;scrollbar-width:thin}.rmt-table{width:100%;border-collapse:collapse;font:11px system-ui;table-layout:fixed}.rmt-table th{text-align:left;color:#aaa;position:sticky;top:0;background:#080808}.rmt-table th:first-child{width:64%}.rmt-table th:nth-child(2){width:23%}.rmt-table th:nth-child(3){width:13%}.rmt-table td,.rmt-table th{padding:5px;border-bottom:1px solid #272727;vertical-align:top;overflow-wrap:anywhere}
    .rmt-row{display:grid;grid-template-columns:minmax(95px,1fr) minmax(120px,1.5fr) 52px;gap:5px;padding-bottom:7px;border-bottom:1px solid #252525}.rmt-key{display:flex;flex-direction:column;gap:5px}.rmt-row details{font-size:10px;color:#aaa}.rmt-message{color:#aaa;font-size:11px;white-space:pre-wrap}.rmt-error{color:#ff9292}.rmt-raw{min-height:180px!important}`;
    document.head.append(style);
}

async function preview(node, action) {
    const response = await api.fetchApi("/ray/model-tools/preview", { method: "POST",
        headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action, path: value(node, "path"),
            path_a: value(node, "path_a"), path_b: value(node, "path_b"), components: value(node, "components") || "diffusion" }) });
    const data = await response.json();
    if (!response.ok || data.error) throw new Error(data.error || `Preview failed (${response.status}).`);
    return data;
}

function watchHeight(node, root) {
    const observer = new ResizeObserver(() => node._rayPanel?.schedule());
    observer.observe(root);
    const removed = node.onRemoved;
    node.onRemoved = function () { observer.disconnect(); return removed?.apply(this, arguments); };
}

export function createMetadataEditor(node) {
    const root = el("div", undefined, "rmt");
    const toolbar = el("div", undefined, "rmt-toolbar"), message = el("div", "Load a model or JSON file, or add fields below.", "rmt-message");
    const scroll = el("div", undefined, "rmt-scroll"), raw = el("textarea", undefined, "rmt-raw");
    raw.setAttribute("aria-label", "Raw metadata JSON"); raw.hidden = true;
    let rows = [], rawMode = false, request = 0, active = false;
    const fields = () => rows.map(r => ({ key: r.key.value, type: r.type.value, value: r.value.value }));
    const serialize = () => rawMode ? JSON.stringify(rowsToMetadata(metadataRows(parseMetadataJSON(raw.value)))) : JSON.stringify(rowsToMetadata(fields()));
    const commit = () => {
        active = true;
        try {
            setValue(node, "editor_json", serialize());
            message.textContent = `${rows.length} metadata fields. Changes are saved with the workflow.`;
            message.classList.remove("rmt-error");
        } catch (error) {
            // API queueing must fail too, even if it does not invoke serializeValue.
            setValue(node, "editor_json", "{ invalid metadata JSON");
            message.textContent = error.message; message.classList.add("rmt-error");
        }
    };
    const draw = object => {
        scroll.replaceChildren(); rows = [];
        for (const item of metadataRows(object)) {
            const row = el("div", undefined, "rmt-row"), keyBox = el("div", undefined, "rmt-key");
            const key = el("input"), type = el("select"), text = el("textarea"), valueBox = el("div");
            key.value = item.key; key.setAttribute("aria-label", "Metadata key");
            text.value = item.value; text.setAttribute("aria-label", `Value for ${item.key}`);
            for (const [v, label] of [["text", "Text"], ["json", "JSON value"]]) {
                const option = el("option", label); option.value = v; type.append(option);
            }
            type.value = item.type; type.setAttribute("aria-label", `Type for ${item.key}`);
            const record = { key, type, value: text };
            const details = el("details"), nested = el("pre");
            details.append(el("summary", "Expand JSON"), nested);
            const updateNested = () => {
                try { nested.textContent = JSON.stringify(JSON.parse(text.value), null, 2); details.hidden = false; }
                catch { details.hidden = true; }
            };
            const changed = () => { updateNested(); commit(); };
            key.oninput = changed; type.onchange = changed; text.oninput = changed;
            keyBox.append(key, type); valueBox.append(text, details);
            row.append(keyBox, valueBox, button("Delete", () => { rows = rows.filter(r => r !== record); row.remove(); commit(); }));
            rows.push(record); updateNested(); scroll.append(row);
        }
        raw.value = JSON.stringify(object, null, 2);
    };
    const hydrate = (object, source = "") => {
        rawMode = false; raw.hidden = true; scroll.hidden = false;
        draw(object); setValue(node, "editor_source", source); commit();
    };
    toolbar.append(button("Load / Edit", async () => {
        const ticket = ++request;
        try {
            if (!String(value(node, "path")).trim()) {
                hydrate(node._rayModelToolsReport?.metadata || {}, ""); return;
            }
            const data = await preview(node, "metadata");
            if (ticket === request) hydrate(data.metadata_json ? parseMetadataJSON(data.metadata_json) : data.metadata, data.source);
        } catch (error) { message.textContent = error.message; message.classList.add("rmt-error"); }
    }), button("Add field", () => {
        try {
            const object = JSON.parse(serialize()); let key = "new_field", i = 1;
            while (Object.hasOwn(object, key)) key = `new_field_${i++}`;
            Object.defineProperty(object, key, { value: "", enumerable: true, writable: true, configurable: true });
            hydrate(object, value(node, "editor_source"));
        } catch (error) { notify(error.message); }
    }), button("Table / JSON", () => {
        try {
            const object = JSON.parse(serialize());
            if (rawMode) draw(object); else raw.value = JSON.stringify(object, null, 2);
            rawMode = !rawMode; raw.hidden = !rawMode; scroll.hidden = rawMode; commit();
        } catch (error) { message.textContent = error.message; message.classList.add("rmt-error"); }
    }));
    raw.oninput = commit;
    const target = widget(node, "editor_json");
    if (target) target.serializeValue = async () => active ? serialize() : "";
    root.append(toolbar, message, scroll, raw);
    watchHeight(node, root);
    const reload = () => {
        active = !!String(value(node, "editor_json")).trim();
        try { draw(parseMetadataJSON(value(node, "editor_json") || "{}")); }
        catch (error) { message.textContent = error.message; message.classList.add("rmt-error"); }
    };
    reload();
    node._rayMetadataEditor = { root, hydrate, reload, serialize };
    return root;
}

export function createReport(node, id) {
    const root = el("div", undefined, "rmt"), toolbar = el("div", undefined, "rmt-toolbar");
    const summary = el("div", "Run the node to see its report.", "rmt-message");
    const content = el("div", undefined, "rmt-scroll");
    let report = null, query = "", page = 0;
    const search = el("input"); search.placeholder = "Filter tensors…"; search.setAttribute("aria-label", "Filter tensors"); search.hidden = true;
    const paging = el("div", undefined, "rmt-toolbar"), count = el("span", "", "rmt-message"); paging.hidden = true;
    const render = () => {
        content.replaceChildren();
        if (!report) return;
        if (Array.isArray(report.rows)) {
            const filtered = filterTensors(report.rows, query, page); page = filtered.page;
            count.textContent = `${filtered.total} shown · page ${page + 1}/${filtered.pages}`;
            previous.disabled = page === 0; next.disabled = page >= filtered.pages - 1;
            const table = el("table", undefined, "rmt-table"), head = el("thead"), tr = el("tr");
            for (const label of ["Tensor", "Shape", "Dtype"]) tr.append(el("th", label));
            head.append(tr); table.append(head);
            const body = el("tbody");
            for (const row of filtered.rows) {
                const tr = el("tr"); for (const cell of [row.name, `[${row.shape.join(", ")}]`, row.dtype]) tr.append(el("td", cell));
                body.append(tr);
            }
            table.append(body); content.append(table);
        } else content.append(el("pre", JSON.stringify(report, null, 2)));
    };
    const show = data => {
        report = data; node._rayModelToolsReport = data; page = 0;
        search.hidden = paging.hidden = !Array.isArray(data.rows);
        if (data.tensor_count !== undefined) {
            summary.textContent = `${data.architecture?.name || "Unknown architecture"} · ${data.tensor_count.toLocaleString()} tensors · ${(data.tensor_bytes / 1e9).toFixed(2)} GB\n${data.architecture?.note || ""}${data.rows_truncated ? `\n${data.rows_truncated} additional rows omitted; increase max_rows on the node.` : ""}`;
        } else if (data.common !== undefined) {
            summary.textContent = `${data.structurally_compatible ? "Structure matches" : "Structure differs"} · ${data.common} shared tensors · ${data.shape_mismatches?.length || 0} shape differences`;
        } else summary.textContent = data.saved_path ? `Saved: ${data.saved_path}` : `${data.operation || "Operation"} complete`;
        summary.classList.remove("rmt-error"); render();
    };
    if (["RayModelInspector", "RayModelCompare"].includes(id)) toolbar.append(button("Preview files", async () => {
        try { show(await preview(node, id === "RayModelInspector" ? "inspect" : "compare")); }
        catch (error) { summary.textContent = error.message; summary.classList.add("rmt-error"); }
    }));
    toolbar.append(button("Copy report", async () => {
        try { await navigator.clipboard.writeText(JSON.stringify(report || {}, null, 2)); }
        catch (error) { notify(error.message); }
    }));
    search.oninput = () => { query = search.value; page = 0; render(); };
    const previous = button("‹", () => { page--; render(); }), next = button("›", () => { page++; render(); });
    previous.title = "Previous tensor page"; next.title = "Next tensor page";
    previous.setAttribute("aria-label", previous.title); next.setAttribute("aria-label", next.title);
    paging.append(previous, count, next);
    root.append(toolbar, summary, search, paging, content);
    watchHeight(node, root);
    node._rayModelToolsView = { show, root };
    return root;
}

const SECTIONS = {
    RayModelLoadAs: [
        ["Source", "model_name", "path"],
        ["Loading", "weight_format", "loader", "load_components"],
    ],
    RayModelConvert: [
        ["Source", "path"], ["Conversion", "weight_format", "components"], ["Output", "load_result"],
    ],
    RayModelSave: [
        ["Source", "path"], ["Metadata", "metadata_mode", "metadata_json"],
        ["Output", "filename_prefix", "output_path", "overwrite"],
    ],
    RayModelMetadata: [["Source", "path"]],
    RayModelMetadataSave: [
        ["Output", "mode", "filename_prefix", "output_path", "overwrite"],
        ["Source model", "source_model_path"], ["Metadata", "metadata_json"],
    ],
    RayModelMerge: [
        ["Merge", "strategy", "weight_a", "components", "mismatch"],
        ["Algorithm", "density", "lambda", "top_trim", "bottom_trim", "seed"],
        ["Block weights", "block_weights"], ["Output", "weight_format", "load_result"],
    ],
    RayModelInspector: [["Source", "path"], ["Inspection", "max_rows"]],
    RayModelCompare: [["Sources", "path_a", "path_b"], ["Comparison", "components"]],
    RayLoraBake: [
        ["Source", "path"], ["LoRA", "lora_name", "lora_path", "strength_model", "strength_clip"],
        ["Output", "weight_format", "load_result"],
    ],
    RayLoraExtract: [
        ["Sources", "finetuned_path", "base_path"],
        ["Extraction", "rank", "alpha", "components", "include_embeddings"],
        ["Output", "weight_format", "filename_prefix", "output_path"],
    ],
};
const LABELS = {
    model_name: "Model file", lora_name: "LoRA", lora_path: "LoRA file",
    strength_model: "Model strength", strength_clip: "CLIP strength", metadata_json: "Metadata (JSON)",
    path: "Model file", path_a: "Model A file", path_b: "Model B file", base_path: "Base model file",
    finetuned_path: "Fine-tuned model file", source_model_path: "Source model file", output_path: "Output file",
};
const MODEL_FILTERS = [["Safetensors", ["safetensors"]]];
const INSPECT_FILTERS = [["Model files", ["safetensors", "gguf"]]];
const METADATA_FILTERS = [["Models / metadata", ["safetensors", "json"]]];
const outputExtension = (node, id) => id === "RayModelMetadataSave" && value(node, "mode") === "json_sidecar" ? "json" : "safetensors";

function normalizeLoadSource(node) {
    const source = widget(node, "model_name"), legacy = widget(node, "path");
    if (!source) return;
    const input = node.inputs?.find(input => input.name === "model_name" || input.widget?.name === "model_name");
    if (input?.type === "COMBO") input.type = "STRING";
    if (legacy?.value && !linkOf(node, "path")) {
        if (!linkOf(node, "model_name")) source.value = legacy.value;
        legacy.value = "";
    }
    if (source.value === "Select a file or use path…") source.value = "";
}

export function installModelTools(node, id) {
    if (id === "RayModelLoadAs") normalizeLoadSource(node);
    if (node._rayModelTools) return;
    node._rayModelTools = true; styles(); applyBucketTint(node, "Tools");
    const hidden = id === "RayModelMetadata" ? ["editor_json", "editor_source"]
        : id === "RayModelMerge" ? ["path_a", "path_b", "base_path"] : [];
    for (const name of hidden) if (widget(node, name)) setWidgetHidden(node, widget(node, name), true);
    const native = (node.widgets || []).filter(w => w.type !== "button" && w.name !== "control_after_generate" && !hidden.includes(w.name));
    const fields = native.map(w => {
        const field = { name: w.name, label: LABELS[w.name], full: /path|model_name|block_weights|metadata_json/.test(w.name) };
        if (/^(model_name|path|path_a|path_b|base_path|finetuned_path|lora_path|source_model_path)$/.test(w.name)) {
            const metadata = id === "RayModelMetadata";
            if (metadata) field.label = "Model / metadata file";
            field.browse = { kind: "file", title: `Choose ${field.label.toLowerCase()}`,
                filters: metadata ? METADATA_FILTERS : id === "RayModelInspector" ? INSPECT_FILTERS : MODEL_FILTERS };
            field.placeholder = metadata ? "Model file, folder or metadata JSON" : "Model file or folder";
            if (w.name === "lora_path") field.placeholder = "Path to a LoRA file";
            else if (w.name === "source_model_path") field.placeholder = "Path to a model file";
            else field.actions = [{ icon: "folder", title: "Choose a model folder",
                onClick: () => browseInto(node, w.name, { kind: "folder", title: "Choose a model folder" }) }];
        }
        if (id === "RayModelLoadAs" && ["model_name", "path"].includes(w.name)) {
            field.when = n => {
                normalizeLoadSource(n);
                return !!linkOf(n, "path") === (w.name === "path");
            };
        }
        if (w.name === "output_path") {
            field.browse = n => ({ kind: "save", title: "Choose output file",
                filters: [[outputExtension(n, id) === "json" ? "Metadata JSON" : "Safetensors", [outputExtension(n, id)]]] });
            field.placeholder = "Automatic filename in the output folder";
        }
        if (id === "RayModelMerge" && ["density", "lambda", "top_trim", "bottom_trim", "seed"].includes(w.name)) {
            field.when = n => mergeFields(String(value(n, "strategy")))[w.name];
        }
        if (id === "RayModelMetadataSave" && w.name === "source_model_path") field.when = n => value(n, "mode") === "model_copy";
        return field;
    });
    const custom = () => id === "RayModelMetadata" ? createMetadataEditor(node) : createReport(node, id);
    const byName = new Map(fields.map(field => [field.name, field]));
    const sections = SECTIONS[id].map(([title, ...names]) => ({
        title, fields: names.map(name => byName.get(name)).filter(Boolean),
    }));
    sections.push({ title: id === "RayModelMetadata" ? "Metadata" : "Report", fields: [{ custom }] });
    installPanel(node, { skip: hidden, minWidth: 470, sections });
}

app.registerExtension({
    name: "Ray.ModelTools",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (!IDS.has(nodeData.name)) return;
        const created = nodeType.prototype.onNodeCreated, configured = nodeType.prototype.onConfigure,
            executed = nodeType.prototype.onExecuted;
        nodeType.prototype.onNodeCreated = function () {
            const result = created?.apply(this, arguments); installModelTools(this, nodeData.name); return result;
        };
        nodeType.prototype.onConfigure = function () {
            const result = configured?.apply(this, arguments); installModelTools(this, nodeData.name);
            this._rayMetadataEditor?.reload(); return result;
        };
        nodeType.prototype.onExecuted = function (message) {
            const result = executed?.apply(this, arguments), report = message?.model_tools?.[0];
            if (report) {
                this._rayModelToolsReport = report;
                this._rayModelToolsView?.show(report);
                if (nodeData.name === "RayModelMetadata" && !value(this, "editor_json")) {
                    try { this._rayMetadataEditor?.hydrate(report.metadata_json ? parseMetadataJSON(report.metadata_json) : report.metadata || {}, value(this, "path")); }
                    catch (error) { notify(error.message); }
                }
            }
            return result;
        };
    },
});
