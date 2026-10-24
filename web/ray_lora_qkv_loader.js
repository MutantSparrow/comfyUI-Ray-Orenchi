import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";
import { applyBucketTint, setWidgetHidden } from "./_common.js";
import { installPanel, iconButton, linkChip, linkOf, registerLinkTargets } from "./ray_panel.js";
import { browsePath, notify } from "./browse_common.js";

const ID = "RayLoraQKVLoader", PLACEHOLDER = "Select a LoRA…";
let loraNames;
const availableLoras = () => loraNames ||= api.fetchApi("/models/loras")
    .then(response => response.ok ? response.json() : []).catch(() => []);
const widget = (node, name) => node.widgets?.find(item => item.name === name);
const el = (tag, className, text) => {
    const item = document.createElement(tag);
    if (className) item.className = className;
    if (text !== undefined) item.textContent = text;
    return item;
};

function installLoader(node, definition) {
    if (node._rayLoraQKV) { node._rayLoraQKV.refresh(); return; }
    applyBucketTint(node, "Tools");
    const first = widget(node, "lora_name"), strength = widget(node, "strength"), rest = widget(node, "additional_loras");
    for (const item of [first, strength, rest]) setWidgetHidden(node, item, true);
    const root = el("div", "rlq-loras"), list = el("div"), choices = el("datalist");
    choices.id = `ray-loras-${crypto.randomUUID()}`;
    availableLoras().then(names => {
        for (const name of names) {
            const option = el("option"); option.value = name; choices.append(option);
        }
    });
    for (const item of [root, list]) Object.assign(item.style, { display: "flex", flexDirection: "column", gap: "6px" });
    const controls = el("div", "rp-control");
    const add = iconButton("plus", "Add LoRA", () => write([...read(), { name: "", strength: 1 }]));
    const extraChip = linkChip(node, "additional_loras", () => refresh());
    controls.append(add, extraChip.element);
    const status = el("div", "rp-status"); status.setAttribute("role", "status");
    let signature = "", unregister = () => {};

    function read() {
        let extra;
        try { extra = JSON.parse(rest.value || "[]"); } catch { extra = []; }
        return [{ name: first.value === PLACEHOLDER ? "" : String(first.value ?? ""), strength: Number(strength.value) },
            ...(Array.isArray(extra) ? extra : [])];
    }
    function write(rows) {
        if (!rows.length) rows = [{ name: "", strength: 1 }];
        node.graph?.beforeChange?.();
        try {
            first.value = rows[0].name || "";
            strength.value = rows[0].strength;
            rest.value = JSON.stringify(rows.slice(1));
            for (const item of [first, strength, rest]) item.callback?.(item.value);
        } finally { node.graph?.afterChange?.(); }
        signature = ""; status.textContent = ""; refresh(); node.setDirtyCanvas?.(true, true);
    }
    function refresh() {
        const sourceLinked = !!linkOf(node, "lora_name"), strengthLinked = !!linkOf(node, "strength"), extraLinked = !!linkOf(node, "additional_loras");
        const next = JSON.stringify([first.value, strength.value, rest.value, sourceLinked, strengthLinked, extraLinked]);
        add.disabled = extraLinked; extraChip.update();
        if (next === signature) return;
        signature = next; unregister(); list.replaceChildren();
        const rows = read(), targets = [];
        for (const [index, value] of rows.entries()) {
            if (index && extraLinked) break;
            const row = el("div", "rp-row rp-full"), label = el("label", "rp-label", `LoRA ${index + 1}`);
            const control = el("div", "rp-control"), source = el("input", "rp-input");
            source.value = value.name; source.placeholder = PLACEHOLDER;
            source.setAttribute("list", choices.id); source.setAttribute("aria-label", `LoRA ${index + 1}`);
            source.id = `${choices.id}-${index}`; label.htmlFor = source.id;
            source.title = value.name || "Choose a registered LoRA or browse to a file";
            source.onchange = () => { const rows = read(); rows[index].name = source.value; write(rows); };
            const browse = iconButton("file", `Choose LoRA ${index + 1} file`, async () => {
                try {
                    const selected = await browsePath("file", source.value, { title: "Choose LoRA",
                        filters: [["LoRA adapters", ["safetensors", "ckpt", "pt", "pth", "bin"]]] });
                    if (selected) {
                        const rows = read();
                        if (rows[index]?.name === value.name && !(index === 0 && linkOf(node, "lora_name")) && !linkOf(node, "additional_loras")) {
                            rows[index].name = selected; write(rows);
                        }
                    }
                } catch (error) { notify(error.message); }
            });
            const remove = iconButton("minus", `Remove LoRA ${index + 1}`, () => {
                const rows = read(); rows.splice(index, 1); write(rows);
            });
            remove.innerHTML = '<svg viewBox="0 0 24 24"><path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13M10 10v7M14 10v7"/></svg>';
            remove.disabled = extraLinked || (index === 0 && (sourceLinked || strengthLinked)) || (rows.length === 1 && !value.name);
            control.append(source, browse, remove); row.append(label, control); list.append(row);
            const strengthRow = el("div", "rp-row rp-full"), strengthLabel = el("label", "rp-label", "Strength");
            const strengthControl = el("div", "rp-control"), number = el("div", "rp-number"), amount = el("input", "rp-input");
            amount.type = "number"; amount.min = "-100"; amount.max = "100"; amount.step = "0.01"; amount.value = value.strength;
            amount.setAttribute("aria-label", `LoRA ${index + 1} strength`);
            amount.id = `${choices.id}-strength-${index}`; strengthLabel.htmlFor = amount.id;
            const commit = candidate => {
                const parsed = Number(candidate);
                if (candidate === "" || !Number.isFinite(parsed) || Math.abs(parsed) > 100) {
                    amount.value = read()[index].strength; return;
                }
                const rows = read(); rows[index].strength = Math.round(parsed * 100) / 100; write(rows);
            };
            amount.onchange = () => commit(amount.value);
            const minus = iconButton("minus", `Decrease LoRA ${index + 1} strength`, () => commit(Math.max(-100, value.strength - .01)));
            const plus = iconButton("plus", `Increase LoRA ${index + 1} strength`, () => commit(Math.min(100, value.strength + .01)));
            number.append(minus, amount, plus); strengthControl.append(number); strengthRow.append(strengthLabel, strengthControl); list.append(strengthRow);
            for (const field of [source, amount]) for (const type of ["keydown", "keyup", "keypress"])
                field.addEventListener(type, event => event.stopPropagation());
            if (index === 0) {
                const sourceChip = linkChip(node, "lora_name", refresh), strengthChip = linkChip(node, "strength", refresh);
                control.prepend(sourceChip.element); sourceChip.update();
                strengthControl.prepend(strengthChip.element); strengthChip.update();
                source.hidden = sourceLinked; browse.disabled = sourceLinked; number.style.display = strengthLinked ? "none" : "flex";
                targets.push({ name: "lora_name", element: row }, { name: "strength", element: strengthRow });
            }
        }
        targets.push({ name: "additional_loras", element: controls });
        unregister = registerLinkTargets(node, targets, refresh);
        node._rayPanel?.schedule();
    }
    root.append(choices, list, controls, status);
    const panel = installPanel(node, { minWidth: 480, skip: ["lora_name", "strength", "additional_loras"],
        sections: [{ title: "LoRAs", fields: [{ custom: () => root, update: refresh }] }] });
    const observer = new ResizeObserver(() => panel.schedule()); observer.observe(root);
    const removed = node.onRemoved;
    node.onRemoved = function () { observer.disconnect(); unregister(); return removed?.apply(this, arguments); };
    node._rayLoraQKV = { refresh, status }; refresh();
}

app.registerExtension({
    name: "Ray.LoraQKVLoader",
    beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== ID) return;
        const created = nodeType.prototype.onNodeCreated, configured = nodeType.prototype.onConfigure, executed = nodeType.prototype.onExecuted;
        nodeType.prototype.onNodeCreated = function () {
            const result = created?.apply(this, arguments); installLoader(this, nodeData); return result;
        };
        nodeType.prototype.onConfigure = function () {
            const result = configured?.apply(this, arguments); installLoader(this, nodeData); return result;
        };
        nodeType.prototype.onExecuted = function (message) {
            const result = executed?.apply(this, arguments);
            const status = this._rayLoraQKV?.status;
            if (status && message?.lora_qkv) status.textContent = message.lora_qkv.map((row, index) => {
                if (row.skipped) return `LoRA ${index + 1}: skipped (strength 0)`;
                const fixes = [row.aliases ? `${row.aliases} names matched` : "", row.split ? `${row.split} QKV split` : "", row.sliced ? `${row.sliced} Q/K/V mapped` : ""].filter(Boolean);
                return `LoRA ${index + 1}: ${row.loaded} weights loaded${fixes.length ? " · " + fixes.join(", ") : ""}${row.warnings?.length ? " · " + row.warnings.join(" ") : ""}`;
            }).join("\n") || "No LoRAs selected";
            if (status) status.style.whiteSpace = "pre-line";
            this._rayPanel?.schedule(); return result;
        };
    },
});
