import { app } from "../../scripts/app.js";
import { applyBucketTint, setWidgetHidden } from "./_common.js";
import { installPanel, iconButton, linkChip, linkOf, registerLinkTargets } from "./ray_panel.js";
import { createModelPicker } from "./model_picker.js";

const ID = "RayLoraQKVLoader", PLACEHOLDER = "Select a LoRA…";
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
    const root = el("div", "rlq-loras"), list = el("div");
    for (const item of [root, list]) Object.assign(item.style, { display: "flex", flexDirection: "column", gap: "6px" });
    const controls = el("div", "rp-control");
    const add = iconButton("plus", "Add LoRA", () => write([...read(), { name: "", strength: 1 }]));
    const extraChip = linkChip(node, "additional_loras", () => refresh());
    controls.append(extraChip.element);
    const status = el("div", "rp-status"); status.setAttribute("role", "status");
    let signature = "", unregister = () => {}, scrub = null, pickers = [];
    const controlId = `ray-loras-${crypto.randomUUID()}`;

    function read() {
        let extra;
        try { extra = JSON.parse(rest.value || "[]"); } catch { extra = []; }
        return [{ name: first.value === PLACEHOLDER ? "" : String(first.value ?? ""), strength: Number(strength.value) },
            ...(Array.isArray(extra) ? extra : [])];
    }
    function write(rows, { history = true, render = true } = {}) {
        if (!rows.length) rows = [{ name: "", strength: 1 }];
        if (history) node.graph?.beforeChange?.();
        try {
            first.value = rows[0].name || "";
            strength.value = rows[0].strength;
            rest.value = JSON.stringify(rows.slice(1));
            for (const item of [first, strength, rest]) item.callback?.(item.value);
        } finally { if (history) node.graph?.afterChange?.(); }
        signature = ""; status.textContent = "";
        if (render) refresh();
        node.setDirtyCanvas?.(true, true);
    }
    function refresh() {
        const sourceLinked = !!linkOf(node, "lora_name"), strengthLinked = !!linkOf(node, "strength"), extraLinked = !!linkOf(node, "additional_loras");
        const next = JSON.stringify([first.value, strength.value, rest.value, sourceLinked, strengthLinked, extraLinked]);
        add.disabled = extraLinked; extraChip.update();
        // Keep the captured input mounted throughout a drag, including panel updates.
        if (next === signature || scrub) return;
        signature = next; unregister(); pickers.forEach(picker => picker.destroy()); pickers = []; list.replaceChildren();
        const rows = read(), targets = [];
        for (const [index, value] of rows.entries()) {
            if (index && extraLinked) break;
            const row = el("div", "rp-row rp-full"), label = el("label", "rp-label", `LoRA ${index + 1}`);
            const control = el("div", "rp-control");
            const picker = createModelPicker({ group: "loras", label: `LoRA ${index + 1}`, value: value.name,
                placeholder: PLACEHOLDER,
                disabled: () => !!linkOf(node, index === 0 ? "lora_name" : "additional_loras"),
                onSelect: selected => { const rows = read();
                    if (rows[index]?.name === value.name) { rows[index].name = selected; write(rows); }
                } });
            pickers.push(picker); const source = picker.element;
            source.id = `${controlId}-${index}`; label.htmlFor = source.id;
            const remove = iconButton("remove", `Remove LoRA ${index + 1}`, () => {
                const rows = read(); rows.splice(index, 1); write(rows);
            });
            remove.disabled = extraLinked || (index === 0 && (sourceLinked || strengthLinked)) || (rows.length === 1 && !value.name);
            control.append(source, remove); row.append(label, control); list.append(row);
            const strengthRow = el("div", "rp-row rp-full"), strengthLabel = el("label", "rp-label", "Strength");
            const strengthControl = el("div", "rp-control"), number = el("div", "rp-number"), amount = el("input", "rp-input");
            amount.type = "number"; amount.min = "-100"; amount.max = "100"; amount.step = "0.01"; amount.value = value.strength;
            amount.setAttribute("aria-label", `LoRA ${index + 1} strength`);
            amount.id = `${controlId}-strength-${index}`; strengthLabel.htmlFor = amount.id;
            const commit = candidate => {
                const parsed = Number(candidate);
                if (candidate === "" || !Number.isFinite(parsed) || Math.abs(parsed) > 100) {
                    amount.value = read()[index].strength; return;
                }
                const rows = read(); rows[index].strength = Math.round(parsed * 100) / 100; write(rows);
            };
            amount.onchange = () => commit(amount.value);
            amount.style.touchAction = "none";
            amount.title = "Drag left or right to adjust; click to type. Hold Shift for finer adjustment.";
            amount.addEventListener("pointerdown", event => {
                if (event.button !== 0 || document.activeElement === amount) return;
                event.preventDefault(); event.stopPropagation();
                scrub = { id: event.pointerId, x: event.clientX, start: read()[index].strength, moved: false };
                amount.setPointerCapture(event.pointerId);
            });
            amount.addEventListener("pointermove", event => {
                if (!scrub || event.pointerId !== scrub.id) return;
                event.stopPropagation();
                const dx = event.clientX - scrub.x;
                if (!scrub.moved && Math.abs(dx) < 3) return;
                if (!scrub.moved) { scrub.moved = true; node.graph?.beforeChange?.(); }
                const pixelsPerStep = event.shiftKey ? 60 : 6;
                const next = Math.max(-100, Math.min(100, Math.round((scrub.start + Math.round(dx / pixelsPerStep) * .01) * 100) / 100));
                const rows = read();
                if (rows[index].strength !== next) {
                    rows[index].strength = next;
                    write(rows, { history: false, render: false });
                    amount.value = next;
                }
            });
            const stopScrub = event => {
                if (!scrub || event.pointerId !== scrub.id) return;
                const { moved } = scrub; scrub = null;
                if (amount.hasPointerCapture(event.pointerId)) amount.releasePointerCapture(event.pointerId);
                if (moved) { node.graph?.afterChange?.(); refresh(); }
                else if (event.type === "pointerup") { amount.focus(); amount.select(); }
            };
            for (const type of ["pointerup", "pointercancel", "lostpointercapture"]) amount.addEventListener(type, stopScrub);
            const minus = iconButton("minus", `Decrease LoRA ${index + 1} strength`, () => commit(Math.max(-100, value.strength - .01)));
            const plus = iconButton("plus", `Increase LoRA ${index + 1} strength`, () => commit(Math.min(100, value.strength + .01)));
            number.append(minus, amount, plus); strengthControl.append(number); strengthRow.append(strengthLabel, strengthControl); list.append(strengthRow);
            for (const field of [source, amount]) for (const type of ["keydown", "keyup", "keypress"])
                field.addEventListener(type, event => event.stopPropagation());
            if (index === 0) {
                const sourceChip = linkChip(node, "lora_name", refresh), strengthChip = linkChip(node, "strength", refresh);
                control.prepend(sourceChip.element); sourceChip.update();
                strengthControl.prepend(strengthChip.element); strengthChip.update();
                source.hidden = sourceLinked; number.style.display = strengthLinked ? "none" : "flex";
                targets.push({ name: "lora_name", element: row }, { name: "strength", element: strengthRow });
            }
        }
        targets.push({ name: "additional_loras", element: controls });
        unregister = registerLinkTargets(node, targets, refresh);
        node._rayPanel?.schedule();
    }
    root.append(list, controls, status);
    const panel = installPanel(node, { minWidth: 480, skip: ["lora_name", "strength", "additional_loras"],
        headerActions: [add],
        sections: [{ title: "LoRAs", fields: [{ custom: () => root, update: refresh }] }] });
    const observer = new ResizeObserver(() => panel.schedule()); observer.observe(root);
    const removed = node.onRemoved;
    node.onRemoved = function () {
        if (scrub?.moved) node.graph?.afterChange?.();
        scrub = null;
        observer.disconnect(); unregister(); pickers.forEach(picker => picker.destroy()); return removed?.apply(this, arguments);
    };
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
