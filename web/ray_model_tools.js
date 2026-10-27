import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";
import { installPanel, iconButton, linkChip, linkOf, registerLinkTargets, inputTooltip, outputTooltip } from "./ray_panel.js";
import { applyBucketTint, setWidgetHidden } from "./_common.js";
import { notify } from "./browse_common.js";
import { metadataRows, rowsToMetadata, mergeFields, filterTensors, parseMetadataJSON } from "./model_tools_ui.mjs";
import { createModelPicker } from "./model_picker.js";
import { mergeName, mergeSources, stringValue } from "./model_merge_name.mjs";

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
    const b = el("button", label); b.type = "button"; b.onclick = callback;
    b.title = ({"Load / Edit": "Read the selected file's metadata into the editor; it does not rewrite the file",
        "Table / JSON": "Switch between the field table and raw JSON while preserving values",
        "Copy report": "Copy the current operation report as JSON text",
        "Preview files": "Inspect the selected files without initializing an inference model"})[label] || label;
    return b;
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
    .rmt-row{display:grid;grid-template-columns:minmax(95px,1fr) minmax(120px,1.5fr) 32px;gap:5px;padding-bottom:7px;border-bottom:1px solid #252525}.rmt-key{display:flex;flex-direction:column;gap:5px}.rmt-row details{font-size:10px;color:#aaa}.rmt-message{color:#aaa;font-size:11px;white-space:pre-wrap}.rmt-error{color:#ff9292}.rmt-warning{color:#edbc78;font-size:12px;line-height:1.5;margin:0}.rmt-raw{min-height:180px!important}`;
    document.head.append(style);
}

const previewSignature = node => JSON.stringify([value(node,"path"),value(node,"path_a"),value(node,"path_b"),value(node,"components")]);
async function preview(node, action, signal) {
    const response = await api.fetchApi("/ray/model-tools/preview", { method: "POST",
        signal,
        headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action, path: value(node, "path"),
            path_a: value(node, "path_a"), path_b: value(node, "path_b"), components: value(node, "components") || "diffusion" }) });
    const data = await response.json();
    if (!response.ok || data.error) throw new Error(data.error || `Preview failed (${response.status}).`);
    return data;
}

function watchHeight(node, root, cleanup = () => {}) {
    const observer = new ResizeObserver(() => node._rayPanel?.schedule());
    observer.observe(root);
    const removed = node.onRemoved;
    node.onRemoved = function () { observer.disconnect(); cleanup(); return removed?.apply(this, arguments); };
}

export function createMetadataEditor(node) {
    const root = el("div", undefined, "rmt");
    const toolbar = el("div", undefined, "rmt-toolbar"), message = el("div", "Load a model or JSON file, or add fields below.", "rmt-message");
    const scroll = el("div", undefined, "rmt-scroll"), raw = el("textarea", undefined, "rmt-raw");
    raw.setAttribute("aria-label", "Raw metadata JSON"); raw.hidden = true;
    raw.title = "Edit a JSON object. Duplicate keys, malformed JSON, and unsafe integer edits are rejected before execution.";
    let rows = [], rawMode = false, request = 0, active = false, dead = false, controller;
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
            key.title = "Metadata field name. Each name must be unique.";
            text.value = item.value; text.setAttribute("aria-label", `Value for ${item.key}`);
            text.title = "Field value. Text is stored verbatim; JSON value parses numbers, booleans, arrays, and objects.";
            for (const [v, label] of [["text", "Text"], ["json", "JSON value"]]) {
                const option = el("option", label); option.value = v; type.append(option);
            }
            type.value = item.type; type.setAttribute("aria-label", `Type for ${item.key}`);
            type.title = "Choose literal text or a typed JSON value for this field.";
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
            row.append(keyBox, valueBox, iconButton("remove", "Remove metadata field", () => { rows = rows.filter(r => r !== record); row.remove(); commit(); }));
            rows.push(record); updateNested(); scroll.append(row);
        }
        raw.value = JSON.stringify(object, null, 2);
    };
    const hydrate = (object, source = "") => {
        rawMode = false; raw.hidden = true; scroll.hidden = false;
        draw(object); setValue(node, "editor_source", source); commit();
    };
    const addField = () => {
        try {
            const object = JSON.parse(serialize()); let key = "new_field", i = 1;
            while (Object.hasOwn(object, key)) key = `new_field_${i++}`;
            Object.defineProperty(object, key, { value: "", enumerable: true, writable: true, configurable: true });
            hydrate(object, value(node, "editor_source"));
        } catch (error) { notify(error.message); }
    };
    toolbar.append(button("Load / Edit", async () => {
        const ticket = ++request;
        const source = previewSignature(node);
        controller?.abort();controller=new AbortController();
        try {
            if (!String(value(node, "path")).trim()) {
                hydrate(node._rayModelToolsReport?.metadata || {}, ""); return;
            }
            const data = await preview(node, "metadata", controller.signal);
            if (!dead && ticket === request && source === previewSignature(node))
                hydrate(data.metadata_json ? parseMetadataJSON(data.metadata_json) : data.metadata, data.source);
        } catch (error) {
            if (!dead && ticket === request && source === previewSignature(node) && error.name !== "AbortError") {
                message.textContent = error.message; message.classList.add("rmt-error");
            }
        }
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
    watchHeight(node, root, () => {dead=true;request++;controller?.abort();});
    const reload = () => {
        active = !!String(value(node, "editor_json")).trim();
        try { draw(parseMetadataJSON(value(node, "editor_json") || "{}")); }
        catch (error) { message.textContent = error.message; message.classList.add("rmt-error"); }
    };
    reload();
    node._rayMetadataEditor = { root, hydrate, reload, serialize, addField };
    return root;
}

export function createInspectionView(node, id) {
    const root = el("div", undefined, "rmt"), toolbar = el("div", undefined, "rmt-toolbar");
    const summary = el("div", undefined, "rmt-message"); summary.hidden = true;
    const content = el("div", undefined, "rmt-scroll");
    let report = null, query = "", page = 0, request = 0, dead = false, controller;
    const search = el("input"); search.placeholder = "Filter tensors…"; search.setAttribute("aria-label", "Filter tensors"); search.hidden = true;
    search.title = "Filter the current tensor report by name. This changes the displayed rows, not the model.";
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
        summary.hidden = false;
        search.hidden = paging.hidden = !Array.isArray(data.rows);
        if (data.tensor_count !== undefined) {
            summary.textContent = `${data.architecture?.name || "Unknown architecture"} · ${data.tensor_count.toLocaleString()} tensors · ${(data.tensor_bytes / 1e9).toFixed(2)} GB\n${data.architecture?.note || ""}${data.rows_truncated ? `\n${data.rows_truncated} additional rows omitted; increase max_rows on the node.` : ""}`;
        } else if (data.common !== undefined) {
            summary.textContent = `${data.structurally_compatible ? "Structure matches" : "Structure differs"} · ${data.common} shared tensors · ${data.shape_mismatches?.length || 0} shape differences`;
        } else summary.textContent = data.saved_path ? `Saved: ${data.saved_path}` : `${data.operation || "Operation"} complete`;
        summary.classList.remove("rmt-error"); render();
    };
    toolbar.append(button("Preview files", async () => {
        const ticket=++request,source=previewSignature(node);
        controller?.abort();controller=new AbortController();
        try {
            const data=await preview(node, id === "RayModelInspector" ? "inspect" : "compare",controller.signal);
            if(!dead && ticket===request && source===previewSignature(node))show(data);
        } catch (error) {
            if(!dead && ticket===request && source===previewSignature(node) && error.name!=="AbortError") {
                summary.textContent = error.message; summary.hidden = false; summary.classList.add("rmt-error");
            }
        }
    }));
    search.oninput = () => { query = search.value; page = 0; render(); };
    const previous = button("‹", () => { page--; render(); }), next = button("›", () => { page++; render(); });
    previous.title = "Previous tensor page"; next.title = "Next tensor page";
    previous.setAttribute("aria-label", previous.title); next.setAttribute("aria-label", next.title);
    paging.append(previous, count, next);
    if (toolbar.childElementCount) root.append(toolbar);
    root.append(summary, search, paging, content);
    watchHeight(node, root, () => {dead=true;request++;controller?.abort();});
    node._rayModelToolsView = { show, root };
    return root;
}

const SECTIONS = {
    RayModelLoadAs: [
        ["Source", "model_name", "path"],
        ["Loading", "weight_format", "loader", "load_components"],
    ],
    RayModelConvert: [
        ["Source", "path"], ["Conversion", "weight_format", "components"],
    ],
    RayModelSave: [
        ["Output", "output_folder", "filename_prefix", "overwrite"], ["Metadata", "metadata_mode"],
    ],
    RayModelMetadata: [["Source", "path"]],
    RayModelMetadataSave: [
        ["Output", "mode", "filename_prefix", "output_path", "overwrite"],
        ["Source model", "source_model_path"], ["Metadata", "metadata_json"],
    ],
    RayModelMerge: [
        ["Merge", "strategy", "weight_a", "components", "mismatch"],
        ["Algorithm", "density", "lambda", "top_trim", "bottom_trim", "seed"],
        ["Output", "weight_format"],
    ],
    RayModelInspector: [["Source", "path"], ["Inspection", "max_rows"]],
    RayModelCompare: [["Sources", "path_a", "path_b"], ["Comparison", "components"]],
    RayLoraBake: [
        ["LoRA", "lora_name", "lora_path", "strength_model", "strength_clip"],
        ["Output", "weight_format"],
    ],
    RayLoraExtract: [
        ["Sources", "finetuned_path", "base_path"],
        ["Extraction", "rank", "alpha", "components", "include_embeddings"],
        ["Output", "weight_format", "filename_prefix", "output_path"],
    ],
};
const LABELS = {
    model_name: "Model file", lora_name: "LoRA file", lora_path: "LoRA file",
    strength_model: "Model strength", strength_clip: "CLIP strength", metadata_json: "Metadata (JSON)",
    path: "Model file", path_a: "Model A file", path_b: "Model B file", base_path: "Base model file",
    finetuned_path: "Fine-tuned model file", source_model_path: "Source model file", output_path: "Output file", output_folder: "Output folder",
};
const MODEL_FILTERS = [["Safetensors", ["safetensors"]]];
const INSPECT_FILTERS = [["Model files", ["safetensors", "gguf"]]];
const METADATA_FILTERS = [["Models / metadata", ["safetensors", "json"]]];
const outputExtension = (node, id) => id === "RayModelMetadataSave" && value(node, "mode") === "json_sidecar" ? "json" : "safetensors";

function normalizeSource(node, name, legacyName) {
    const source = widget(node, name), legacy = widget(node, legacyName);
    if (!source) return;
    const input = node.inputs?.find(input => input.name === name || input.widget?.name === name);
    if (input?.type === "COMBO") input.type = "STRING";
    if (legacy?.value && !linkOf(node, legacyName)) {
        if (!linkOf(node, name)) source.value = legacy.value;
        legacy.value = "";
    }
    if (source.value === "Select a file or use path…") source.value = "";
}

const OLD_WIDGETS = {
    RayModelLoadAs: ["model_name", "weight_format", "loader", "load_components", "path", "load_result"],
    RayModelConvert: ["weight_format", "components", "load_result", "path"],
    RayLoraBake: ["lora_name", "strength_model", "strength_clip", "weight_format", "load_result", "path", "lora_path"],
    RayModelMerge: ["strategy", "weight_a", "weight_format", "components", "mismatch", "seed", "control_after_generate",
        "density", "lambda", "top_trim", "bottom_trim", "load_result", "path_a", "path_b", "base_path", "block_weights", "fast_merge"],
};
function migrateWidgets(node, id, saved) {
    const names = OLD_WIDGETS[id], values = saved?.widgets_values;
    const earlierMerge = id === "RayModelMerge" && Array.isArray(values) && values.length === names.length - 1 && typeof values[11] === "boolean";
    if (names && !saved?.properties?.ray_model_tools_schema && Array.isArray(values) && (values.length === names.length || earlierMerge)) {
        for (const [index, name] of names.entries()) {
            const target = widget(node, name);
            if (target && index < values.length) target.value = values[index];
        }
    }
    if (id === "RayModelMerge" && saved?.properties?.ray_model_tools_schema === 2 && Array.isArray(values)) {
        // The retired toggle preceded the hidden block map in schema 2.
        const previous = [...names.slice(0, 11), "path_a", "path_b", "base_path", "fast_merge", "block_weights"];
        previous.forEach((name, index) => {
            const target = widget(node, name);
            if (target && index < values.length) target.value = values[index];
        });
    }
    if (id === "RayModelSave" && (saved?.properties?.ray_model_tools_schema || 0) < 3 && Array.isArray(values) && values.length === 6) {
        ["filename_prefix", "metadata_mode", "overwrite", "metadata_json", "path", "output_path"].forEach((name, index) => {
            const target = widget(node, name); if (target) target.value = values[index];
        });
        const linked = name => saved.inputs?.some(input => (input.name === name || input.widget?.name === name) && input.link != null);
        const split = text => { const normalized = String(text || "").replaceAll("\\", "/"); const index = normalized.lastIndexOf("/");
            return [index < 0 ? "" : normalized.slice(0, index + 1), normalized.slice(index + 1)]; };
        const explicit = widget(node, "output_path");
        if (explicit?.value && !linked("output_path")) {
            const [folder, file] = split(explicit.value.trim().replace(/^["']|["']$/g, ""));
            widget(node, "output_folder").value = folder;
            if (!linked("filename_prefix")) { widget(node, "filename_prefix").value = file.replace(/\.safetensors$/i, ""); explicit.value = ""; }
        } else if (!explicit?.value && !linked("output_path") && !linked("filename_prefix")) {
            const [folder, file] = split(widget(node, "filename_prefix").value);
            widget(node, "output_folder").value = folder; widget(node, "filename_prefix").value = file;
        }
    }
    node.properties ||= {}; node.properties.ray_model_tools_schema = ["RayModelSave", "RayModelMerge"].includes(id) ? 3 : 2;
}

function createLoadSource(node) {
    const root = el("div", undefined, "rp-row rp-full"), label = el("label", "Model", "rp-label"), control = el("div", undefined, "rp-control");
    const tooltip = inputTooltip(node, "model_name", "Choose a registered checkpoint or diffusion model. Search includes every subfolder.");
    root.title = label.title = tooltip;
    const picker = createModelPicker({ group: ["diffusion_models", "checkpoints"], label: "Model", value: value(node, "model_name"),
        tooltip,
        accept: name => name.toLowerCase().endsWith(".safetensors"),
        placeholder: "Select a model…", disabled: () => ["model_name", "path", "model_data"].some(name => linkOf(node, name)),
        onSelect: next => setValue(node, "model_name", next) });
    picker.element.id = `ray-model-source-${crypto.randomUUID()}`; label.htmlFor = picker.element.id;
    const chips = ["model_data", "path", "model_name"].map(name => linkChip(node, name, () => node._rayPanel?.schedule()));
    control.append(...chips.map(chip => chip.element), picker.element); root.append(label, control);
    const refresh = () => {
        normalizeSource(node, "model_name", "path"); picker.update(value(node, "model_name"));
        chips.forEach(chip => chip.update());
        picker.element.hidden = ["model_name", "path", "model_data"].some(name => !!linkOf(node, name));
    };
    const unregister = registerLinkTargets(node, [{name: "model_name", element: root}], refresh);
    const removed = node.onRemoved;
    node.onRemoved = function () { picker.destroy(); unregister(); return removed?.apply(this, arguments); };
    refresh(); return {root, refresh};
}

function createMergeName(node) {
    const root = el("div", undefined, "rmt"), label = el("label", "Merge name", "rp-label"), output = el("output", "", "rmt-message");
    root.title = label.title = output.title = outputTooltip(node, "merge_name", "Suggested merge filename containing source names, strategy, settings, and execution time. Connect merge_name to Save Model's filename_prefix.");
    output.setAttribute("aria-label", "Merge name"); output.style.overflowWrap = "anywhere"; output.style.whiteSpace = "normal";
    root.append(label, output);
    let signature = "";
    const state = node._rayMergeName = {name: "", show(name) { state.name = name; output.textContent = name; }};
    const refresh = () => {
        const sources = mergeSources(node), settings = Object.fromEntries(["components", "mismatch", "seed", "density", "lambda", "top_trim", "bottom_trim"]
            .map(name => [name, value(node, name)]));
        settings.block_weights = stringValue(node, "block_weights") || "{}";
        const args = {...sources, settings, strategy: value(node, "strategy"), weight_a: value(node, "weight_a"), weight_format: value(node, "weight_format")};
        const next = JSON.stringify(args);
        if (next === signature) return;
        signature = next;
        if (!sources.a || !sources.b) { state.name = ""; output.textContent = "Connect model A and B to build a merge name."; }
        else state.show(mergeName(args));
    };
    refresh(); return {root, refresh};
}

export function installModelTools(node, id, nodeData = null) {
    const sourceNames = id === "RayModelLoadAs" ? ["model_name", "path"]
        : id === "RayLoraBake" ? ["lora_name", "lora_path"] : null;
    if (sourceNames) normalizeSource(node, ...sourceNames);
    if (node._rayModelTools) return;
    node._rayModelTools = true; styles(); applyBucketTint(node, "Tools");
    node.properties ||= {}; node.properties.ray_model_tools_schema = ["RayModelSave", "RayModelMerge"].includes(id) ? 3 : 2;
    // Keep old saved per-layer ratios as a hidden native value behind the STRING socket.
    if (id === "RayModelMerge" && !widget(node, "block_weights")) node.addWidget("text", "block_weights", "{}", () => {});
    const hidden = id === "RayModelMetadata" ? ["editor_json", "editor_source"]
        : id === "RayModelMerge" ? ["path_a", "path_b", "base_path", "block_weights"]
        : id === "RayModelLoadAs" ? ["model_name", "path"]
        : id === "RayLoraBake" ? ["path"]
        : id === "RayModelSave" ? ["path", "metadata_json", "output_path"] : [];
    for (const name of hidden) if (widget(node, name)) setWidgetHidden(node, widget(node, name), true);
    const native = (node.widgets || []).filter(w => w.type !== "button" && w.name !== "control_after_generate" && !hidden.includes(w.name));
    const definitions = { ...nodeData?.input?.required, ...nodeData?.input?.optional };
    const fields = native.map(w => {
        const field = { name: w.name, label: LABELS[w.name], tooltip: definitions[w.name]?.[1]?.tooltip,
            full: /path|model_name|lora_name|block_weights|metadata_json|output_folder/.test(w.name) };
        if (/^(model_name|lora_name|path|path_a|path_b|base_path|finetuned_path|lora_path|source_model_path)$/.test(w.name)) {
            const metadata = id === "RayModelMetadata";
            if (metadata) field.label = "Model / metadata file";
            field.browse = { kind: "file", title: `Choose ${field.label.toLowerCase()}`,
                filters: metadata ? METADATA_FILTERS : id === "RayModelInspector" ? INSPECT_FILTERS : MODEL_FILTERS };
            field.placeholder = metadata ? "Path to a model or metadata JSON file" : "Path to a model file";
            if (["lora_name", "lora_path"].includes(w.name)) field.placeholder = "Path to a LoRA file";
        }
        if (sourceNames?.includes(w.name)) {
            field.when = n => {
                normalizeSource(n, ...sourceNames);
                return !!linkOf(n, sourceNames[1]) === (w.name === sourceNames[1]);
            };
        }
        if (w.name === "output_path") {
            field.browse = n => ({ kind: "save", title: "Choose output file",
                filters: [[outputExtension(n, id) === "json" ? "Metadata JSON" : "Safetensors", [outputExtension(n, id)]]] });
            field.placeholder = "Automatic filename in the output folder";
        }
        if (w.name === "output_folder") {
            field.browse = {kind: "folder", title: "Choose output folder"};
            field.placeholder = "ComfyUI output folder";
        }
        if (id === "RayModelMerge" && ["density", "lambda", "top_trim", "bottom_trim", "seed"].includes(w.name)) {
            field.when = n => mergeFields(String(value(n, "strategy")))[w.name];
        }
        if (id === "RayModelMetadataSave" && w.name === "source_model_path") field.when = n => value(n, "mode") === "model_copy";
        return field;
    });
    const byName = new Map(fields.map(field => [field.name, field]));
    const sections = SECTIONS[id].map(([title, ...names]) => ({
        title, fields: names.map(name => byName.get(name)).filter(Boolean),
    }));
    if (id === "RayModelLoadAs") {
        let source;
        sections[0].fields = [{custom: () => { source = createLoadSource(node); return source.root; }, update: () => source?.refresh()}];
    }
    if (id === "RayModelMerge") {
        let requirement;
        sections[0].fields.push({
            custom: () => { requirement = el("p", "", "rmt-warning rmt-base-required"); requirement.setAttribute("role", "status"); return requirement; },
            when: n => !linkOf(n, "strategy") && mergeFields(String(value(n, "strategy"))).base
                && !n.inputs?.some(input => ["base_model", "base_data"].includes(input.name) && input.link != null)
                && !linkOf(n, "base_path") && !String(value(n, "base_path")).trim(),
            update: () => { if (requirement) requirement.textContent = `${value(node, "strategy")} requires the compatible original training base. Connect it to base_model or base_data. For a two-model blend without a base, choose LERP or SLERP.`; },
        });
        let name;
        sections.find(section => section.title === "Output").fields.push({
            custom: () => { name = createMergeName(node); return name.root; }, update: () => name?.refresh(),
        });
    }
    if (id === "RayModelMetadata") sections.push({ title: "Metadata", fields: [{custom: () => createMetadataEditor(node)}],
        actions: [{icon: "plus", title: "Add field", onClick: () => node._rayMetadataEditor.addField()}] });
    if (["RayModelInspector", "RayModelCompare"].includes(id))
        sections.at(-1).fields.push({custom: () => createInspectionView(node, id)});
    installPanel(node, { skip: hidden, minWidth: 470, sections });
}

app.registerExtension({
    name: "Ray.ModelTools",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (!IDS.has(nodeData.name)) return;
        const created = nodeType.prototype.onNodeCreated, configured = nodeType.prototype.onConfigure,
            executed = nodeType.prototype.onExecuted;
        nodeType.prototype.onNodeCreated = function () {
            const result = created?.apply(this, arguments); installModelTools(this, nodeData.name, nodeData); return result;
        };
        nodeType.prototype.onConfigure = function (saved) {
            migrateWidgets(this, nodeData.name, saved);
            const result = configured?.apply(this, arguments); installModelTools(this, nodeData.name, nodeData);
            for (const name of ["load_result", ...(nodeData.name === "RayModelMerge" ? ["fast_merge"] : [])]) {
                const removedInput = this.inputs?.findIndex(input => input.name === name);
                if (removedInput >= 0) this.removeInput(removedInput);
            }
            if (nodeData.name === "RayModelMerge") {
                if (!this.inputs?.some(input => input.name === "block_weights")) this.addInput("block_weights", "STRING", {shape: 7});
                const blocks = this.inputs.find(input => input.name === "block_weights");
                delete blocks.widget; blocks.type = "STRING";
            }
            if (nodeData.name === "RayModelMerge" && !this.outputs?.some(output => output.name === "merge_name")) this.addOutput("merge_name", "STRING");
            this._rayMetadataEditor?.reload(); return result;
        };
        nodeType.prototype.onExecuted = function (message) {
            const result = executed?.apply(this, arguments), report = message?.model_tools?.[0];
            if (report) {
                this._rayModelToolsReport = report;
                this._rayModelToolsView?.show(report);
                if (report.merge_name) this._rayMergeName?.show(report.merge_name);
                if (nodeData.name === "RayModelMetadata" && !value(this, "editor_json")) {
                    try { this._rayMetadataEditor?.hydrate(report.metadata_json ? parseMetadataJSON(report.metadata_json) : report.metadata || {}, value(this, "path")); }
                    catch (error) { notify(error.message); }
                }
            }
            return result;
        };
    },
});
