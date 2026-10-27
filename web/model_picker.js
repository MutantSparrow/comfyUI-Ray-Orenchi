import { api } from "../../scripts/api.js";

// Keep stored names unchanged: separators are normalized only for grouping/search.
const parts = name => name.replaceAll("\\", "/").split("/").filter(Boolean);
const compare = (a, b) => a.localeCompare(b, undefined, { numeric: true, sensitivity: "base" });
let activePicker;

export function modelMenuEntries(names, query = "", select = () => {}, displayName = name => name) {
    const files = [...new Set(names.filter(name => typeof name === "string" && name))];
    const terms = query.trim().toLocaleLowerCase().replaceAll("\\", "/").split(/\s+/).filter(Boolean);
    const leaf = (name, label) => ({ title: label, content: label, value: name, callback: () => select(name) });
    if (terms.length) return files.filter(name => terms.every(term => displayName(name).replaceAll("\\", "/").toLocaleLowerCase().includes(term)))
        .sort(compare).map(name => leaf(name, displayName(name)));
    const tree = { folders: new Map(), files: [] };
    for (const name of files) {
        const path = parts(displayName(name)), filename = path.pop();
        if (!filename) continue;
        let branch = tree;
        for (const folder of path) {
            if (!branch.folders.has(folder)) branch.folders.set(folder, { folders: new Map(), files: [] });
            branch = branch.folders.get(folder);
        }
        branch.files.push({ name, filename });
    }
    const entries = branch => [
        ...[...branch.folders].sort(([a], [b]) => compare(a, b)).map(([folder, child]) => ({
            title: folder, content: folder, has_submenu: true, submenu: { options: entries(child) },
        })),
        ...branch.files.sort((a, b) => compare(a.filename, b.filename)).map(({ name, filename }) => leaf(name, filename)),
    ];
    return entries(tree);
}

function styles() {
    if (document.getElementById("ray-model-picker-styles")) return;
    const style = document.createElement("style"); style.id = "ray-model-picker-styles";
    style.textContent = `
.rp .rp-model-picker {display:flex;align-items:center;gap:6px;text-align:left;padding-right:9px}
.rp .rp-model-picker[hidden] {display:none}
.rp-model-picker span {overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex:1;min-width:0}
.rp-model-picker::after {content:"";width:6px;height:6px;flex:none;border-right:1.5px solid currentColor;border-bottom:1.5px solid currentColor;transform:rotate(45deg);margin:0 2px 3px 4px}
.litegraph.litecontextmenu.ray-model-menu {min-width:260px;max-width:min(680px,calc(100vw - 24px));max-height:min(480px,calc(100vh - 24px));overflow:auto;z-index:10001}
.ray-model-menu .litemenu-entry {white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.ray-model-menu .comfy-context-menu-filter {position:sticky;top:0;box-sizing:border-box;width:100%;margin:0 0 4px;z-index:1}
.ray-model-menu .ray-model-active {background:#ccc!important;color:#000!important}
`;
    document.head.append(style);
}

/** A standard ComfyUI combo menu, with registered files grouped by their folders. */
export function createModelPicker({ group, label, value = "", placeholder, tooltip, onSelect, disabled = () => false, accept = () => true }) {
    styles();
    const element = document.createElement("button"), text = document.createElement("span");
    element.type = "button"; element.className = "rp-select rp-model-picker";
    element.setAttribute("role", "combobox"); element.setAttribute("aria-label", label);
    element.setAttribute("aria-haspopup", "menu"); element.setAttribute("aria-expanded", "false");
    element.append(text);
    let menu, request, destroyed = false, selected = value;
    const close = () => { request?.abort(); request = null; menu?.close(); menu = null; };
    const multiple = Array.isArray(group);
    const displayName = name => multiple ? name.replace(/^diffusion_models: /, "Diffusion models/").replace(/^checkpoints: /, "Checkpoints/") : name;
    const update = name => { selected = String(name ?? ""); text.textContent = displayName(selected) || placeholder;
        const help = tooltip || `Select ${group === "loras" ? "a LoRA" : multiple ? "a checkpoint or diffusion model" : "a diffusion model"}. Search includes every registered subfolder.`;
        element.title = selected ? `${help}\nSelected: ${selected}` : help; };
    update(value);

    async function open() {
        if (destroyed || disabled()) return;
        activePicker?.(); activePicker = close;
        const bounds = element.getBoundingClientRect();
        const event = new MouseEvent("click", { clientX: bounds.left + 10, clientY: bounds.bottom + 10 });
        const options = { className: "dark ray-model-menu", event, autoopen: true, scale: 1 };
        menu = new LiteGraph.ContextMenu([], options);
        const opened = menu, originalClose = opened.close.bind(opened), events = new AbortController();
        const ownedMenus = () => { const result = []; for (let item = opened; item; item = item.current_submenu) result.push(item); return result; };
        const decorate = () => { for (const item of ownedMenus()) {
            item.root.classList.add("dark", "ray-model-menu"); item.root.setAttribute("role", "menu"); item.root.tabIndex = -1;
            for (const entry of item.root.querySelectorAll(":scope > .litemenu-entry"))
                if (entry.value?.title) entry.setAttribute("aria-label", entry.value.title);
        } };
        const observer = new MutationObserver(decorate); observer.observe(document.body, { childList: true });
        opened.close = (...args) => {
            observer.disconnect(); events.abort();
            request?.abort(); request = null;
            if (menu === opened) menu = null;
            element.setAttribute("aria-expanded", "false");
            if (activePicker === close) activePicker = null;
            originalClose(...args);
        };
        element.setAttribute("aria-expanded", "true");
        opened.root.setAttribute("role", "menu"); opened.root.setAttribute("aria-label", `${label} models`);
        const filter = document.createElement("input"); filter.className = "comfy-context-menu-filter";
        filter.placeholder = "Filter all folders…"; filter.setAttribute("aria-label", `Filter ${label}`);
        opened.root.append(filter);
        let names = [];
        const active = new WeakMap();
        const choose = name => { if (!destroyed && !disabled()) { close(); onSelect(name); } };
        const items = (target = opened) => [...target.root.children].filter(item => item.matches(".litemenu-entry:not(.disabled)"));
        function highlight(index, target = opened) {
            const entries = items(target); if (!entries.length) return;
            const selectedIndex = (index + entries.length) % entries.length; active.set(target, selectedIndex);
            for (const [i, item] of entries.entries()) item.classList.toggle("ray-model-active", i === selectedIndex);
            entries[selectedIndex]?.scrollIntoView({ block: "nearest" });
        }
        function render(message) {
            opened.current_submenu?.close(event, true); opened.current_submenu = undefined; opened.lock = false;
            for (const item of [...opened.root.children]) if (item !== filter) item.remove();
            const entries = message ? [] : modelMenuEntries(names, filter.value, choose, displayName);
            if (!entries.length) opened.addItem(message || "No matching models", { disabled: true }, options);
            else for (const entry of entries) {
                const item = opened.addItem(entry.title, entry, options);
                item.setAttribute("aria-label", entry.title);
                if (entry.value) item.title = entry.value;
            }
            active.set(opened, -1);
            const index = entries.findIndex(entry => entry.value === selected);
            if (index >= 0) highlight(index);
            // The filter increases the native menu height after construction.
            const rect = opened.root.getBoundingClientRect();
            opened.root.style.top = `${Math.max(8, Math.min(bounds.bottom, innerHeight - rect.height - 8))}px`;
            opened.root.style.left = `${Math.max(8, Math.min(bounds.left, innerWidth - rect.width - 8))}px`;
        }
        filter.addEventListener("input", () => render());
        document.addEventListener("keydown", key => {
            const target = ownedMenus().find(item => item.root.contains(key.target));
            if (!target) return;
            key.stopPropagation();
            if (key.key === "Escape") { key.preventDefault(); close(); element.focus(); }
            else if (key.key === "ArrowDown" || key.key === "ArrowUp") {
                key.preventDefault(); const index = active.get(target) ?? -1;
                highlight(index < 0 ? (key.key === "ArrowDown" ? 0 : items(target).length - 1) : index + (key.key === "ArrowDown" ? 1 : -1), target);
            } else if (key.key === "Enter" || key.key === "ArrowRight") {
                key.preventDefault(); const entries = items(target), item = entries[Math.max(0, active.get(target) ?? 0)];
                if (key.key === "ArrowRight" && !item?.classList.contains("has_submenu")) return;
                item?.click();
                const child = target.current_submenu;
                if (child) {
                    decorate(); child.root.focus(); highlight(0, child);
                }
            } else if (key.key === "ArrowLeft" && target !== opened) {
                key.preventDefault(); const parent = target.parentMenu; target.close(event); parent?.root.focus();
            } else if (key.key === "Tab") {
                close();
            }
        }, { capture: true, signal: events.signal });
        opened.root.addEventListener("wheel", key => key.stopPropagation());
        render("Loading models…"); filter.focus();
        request = new AbortController();
        try {
            const available = (await Promise.all((multiple ? group : [group]).map(async folder => {
                const response = await api.fetchApi(`/models/${folder}`, { signal: request.signal });
                if (!response.ok) throw Error("Model list unavailable. Close and reopen to retry.");
                const files = await response.json();
                if (!Array.isArray(files)) throw Error("Invalid model list. Close and reopen to retry.");
                const supported = files.filter(name => typeof name === "string" && accept(name));
                return multiple ? supported.map(name => `${folder}: ${name}`) : supported;
            }))).flat();
            if (menu !== opened || destroyed) return;
            names = available; render(names.length ? undefined : "No models in this folder. Add models, then reopen.");
        } catch (error) {
            if (menu === opened && !destroyed && error.name !== "AbortError") render(error.message);
        } finally { if (menu === opened) request = null; }
    }
    element.addEventListener("click", open);
    element.addEventListener("keydown", event => {
        event.stopPropagation();
        if (event.key === "ArrowDown" || event.key === "ArrowUp") { event.preventDefault(); open(); }
    });
    for (const type of ["keyup", "keypress", "pointerdown"]) element.addEventListener(type, event => event.stopPropagation());
    return { element, update, destroy() { destroyed = true; close(); } };
}
