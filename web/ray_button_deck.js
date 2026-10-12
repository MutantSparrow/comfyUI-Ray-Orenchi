import { app } from "../../scripts/app.js";
import { findWidget, setWidgetHidden } from "./_common.js";
import { createPanel, changeValue, editNode, isLinked, mountControlSVG, registerAnalog } from "./analog_common.js";
import { DECK_STYLES, DEFAULT_DECK_STYLE, getDeckStyleCSS, gridShape, layoutLegend } from "./deck_styles.js";
import { playDeck } from "./analog_audio.js";

const MAX_ENTRIES = 64;
const CELL = 54, STICKER = 20, GAP = 6, CHROME = 96;   // px: button, Dymo sticker, grid gap, panel chrome

// One entry per line: trimmed, blank lines dropped, repeats ignored, order kept. Matches the Python node.
export function parseEntries(text) {
    const seen = new Set(), entries = [];
    for (const raw of String(text ?? "").split(/\r\n|\r|\n/)) {
        const line = raw.trim();
        if (line && !seen.has(line)) { seen.add(line); entries.push(line); }
    }
    return entries.slice(0, MAX_ENTRIES);
}

function element(tag, className, text) {
    const el = document.createElement(tag);
    if (className) el.className = className;
    if (text !== undefined) el.textContent = text;
    return el;
}

function buildDeck(node, widget) {
    const ui = createPanel(node, "deck", getDeckStyleCSS());
    const { element: panel, host, readout, hint } = ui;
    const entriesWidget = findWidget(node, "entries");
    setWidgetHidden(node, entriesWidget, true);   // edited through the popout, never as a raw text box
    host.setAttribute("role", "radiogroup");
    host.setAttribute("aria-label", "Button deck");
    const readoutText = element("span", "ray-deck-readout");
    readout.append(readoutText);

    let signature = "", cells = [], lastRaw = null, items = [];
    const styleKey = () => Object.hasOwn(DECK_STYLES, node.properties.style) ? node.properties.style : DEFAULT_DECK_STYLE;
    const disabled = () => isLinked(node, "selected") || isLinked(node, "entries") || !!widget.disabled || !!widget.computedDisabled;
    // The entry shown pressed: the stored one, or the first when it is missing (the node does the same).
    const shownEntry = () => {
        const stored = String(widget.value ?? "").trim();
        return items.includes(stored) ? stored : (items[0] ?? "");
    };

    function setPressed(cell, on) {
        if (cell.on === on) return;
        cell.on = on;
        cell.button.setAttribute("aria-checked", String(on));
        cell.button.dataset.state = on ? "on" : "off";
        for (const el of cell.toggles) {
            const transform = on ? el.dataset.onTransform : el.dataset.offTransform;
            if (transform) el.setAttribute("transform", transform);
        }
        for (const el of cell.onOnly) el.style.display = on ? "" : "none";
        for (const el of cell.offOnly) el.style.display = on ? "none" : "";
    }

    function press(text, event) {
        if (disabled()) return;
        if (text === String(widget.value ?? "").trim()) return;
        const shown = shownEntry();
        editNode(node, () => changeValue(node, widget, text, event));
        if (text !== shown) playDeck(DECK_STYLES[styleKey()].sound, !!shown);
        ui.render();
    }

    function navigate(event, index) {
        const last = cells.length - 1;
        const target = { ArrowRight: index + 1, ArrowDown: index + 1, ArrowLeft: index - 1, ArrowUp: index - 1, Home: 0, End: last }[event.key];
        if (target === undefined) return;
        event.preventDefault();
        const next = cells[(target + cells.length) % cells.length];
        press(next.text, event);
        next.button.focus();
    }

    function rebuild(key, list) {
        const style = DECK_STYLES[key];
        host.replaceChildren();
        host.style.setProperty("--deck-cols", String(gridShape(list.length).cols));
        panel.dataset.panel = style.panel || "silver";
        cells = [];
        if (!list.length) host.append(element("div", "ray-deck-empty", "NO ENTRIES — USE EDIT ENTRIES…"));
        list.forEach((text, index) => {
            const cell = element("div", "ray-deck-cell");
            const button = element("button", "ray-deck-button");
            button.type = "button";
            button.setAttribute("role", "radio");
            button.setAttribute("aria-label", text);
            button.title = text;
            mountControlSVG(button, style.svg);
            for (const label of button.querySelectorAll("[data-label]")) layoutLegend(label, text, style.box);
            const state = {
                text, button, on: null,
                toggles: [...button.querySelectorAll("[data-toggle]")],
                onOnly: [...button.querySelectorAll("[data-on-only]")],
                offOnly: [...button.querySelectorAll("[data-off-only]")],
            };
            button.addEventListener("click", event => press(text, event));
            button.addEventListener("keydown", event => navigate(event, index));
            cell.append(button);
            if (style.legend === "tape") {
                const sticker = element("div", "ray-deck-sticker", text);
                sticker.title = text;
                cell.append(sticker);
            }
            host.append(cell);
            cells.push(state);
        });
    }

    ui.render = () => {
        const key = styleKey();
        const raw = String(entriesWidget?.value ?? "");
        if (raw !== lastRaw) { lastRaw = raw; items = parseEntries(raw); }
        const sig = `${key}\u0000${items.join("\u0001")}`;
        if (sig !== signature) { signature = sig; rebuild(key, items); }
        const current = shownEntry();
        cells.forEach((cell, i) => {
            const on = cell.text === current;
            setPressed(cell, on);
            cell.button.tabIndex = on ? 0 : -1;
        });
        if (!cells.some(cell => cell.button.tabIndex === 0) && cells[0]) cells[0].button.tabIndex = 0;
        readout.dataset.state = current ? "on" : "off";
        readoutText.textContent = current ? `▶ ${current}` : "NO ENTRIES";
        readout.title = current;
        host.setAttribute("aria-disabled", String(disabled()));
        hint.textContent = disabled() ? "EXTERNAL CONTROL"
            : `${items.length} BUTTON${items.length === 1 ? "" : "S"}  /  CLICK · ARROWS`;
    };

    // Panel chrome plus one row of button (and sticker) per grid row.
    ui.minHeight = () => {
        const style = DECK_STYLES[styleKey()], { rows } = gridShape(items.length);
        return CHROME + rows * (CELL + (style.legend === "tape" ? STICKER : 0)) + (rows - 1) * GAP + 4;
    };
    ui.fitNode = () => {
        const size = node.computeSize?.();
        if (!size) return;
        node.setSize?.([Math.max(node.size?.[0] || 0, size[0]), Math.max(node.size?.[1] || 0, size[1])]);
        node.setDirtyCanvas?.(true, true);
    };

    // ---- entries popout ---------------------------------------------------
    ui.openEditor = () => {
        node._rayDeckEditor?.remove();
        node._rayDeckEditor?.close();
        const dialog = element("dialog", "ray-deck-editor");
        const area = element("textarea");
        area.value = String(entriesWidget?.value ?? "");
        area.spellcheck = false;
        area.setAttribute("aria-label", "Entries, one per line");
        const info = element("div", "ray-deck-editor-info");
        info.setAttribute("aria-live", "polite");
        const cancel = element("button", "", "Cancel"), apply = element("button", "", "Apply");
        // Remove the dialog right away; the browser's close event (Escape) only fires a tick later.
        const dismiss = () => { dialog.close(); dialog.remove(); if (node._rayDeckEditor === dialog) node._rayDeckEditor = null; };
        cancel.type = apply.type = "button";
        apply.dataset.primary = "";
        const refresh = () => {
            const list = parseEntries(area.value);
            const lines = area.value.split(/\r\n|\r|\n/).filter(line => line.trim()).length;
            const { cols, rows } = gridShape(list.length);
            info.textContent = list.length
                ? `${list.length} button${list.length === 1 ? "" : "s"} · ${cols} × ${rows} grid${lines > list.length ? ` · ${lines - list.length} repeated or extra line${lines - list.length === 1 ? "" : "s"} ignored` : ""}`
                : "Add at least one entry.";
            apply.disabled = !list.length;
        };
        const commit = () => {
            const list = parseEntries(area.value);
            if (!list.length) return;
            editNode(node, () => changeValue(node, entriesWidget, list.join("\n")));
            ui.render();
            ui.fitNode();
            dismiss();
        };
        area.addEventListener("input", refresh);
        cancel.addEventListener("click", dismiss);
        apply.addEventListener("click", commit);
        // Keep typing away from the canvas shortcuts; Ctrl/Cmd+Enter applies, Escape cancels.
        dialog.addEventListener("keydown", event => {
            event.stopPropagation();
            if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) { event.preventDefault(); commit(); }
        });
        dialog.addEventListener("close", () => { dialog.remove(); if (node._rayDeckEditor === dialog) node._rayDeckEditor = null; node.setDirtyCanvas?.(true, true); });
        dialog.append(
            element("h3", "", "Button deck entries"),
            element("p", "", "One value per line. Each line becomes a button, and the pressed button's text is the output. Blank and repeated lines are ignored."),
            area, info,
        );
        const actions = element("div", "ray-deck-editor-actions");
        actions.append(cancel, apply);
        dialog.append(actions);
        node._rayDeckEditor = dialog;
        document.body.append(dialog);
        dialog.showModal();
        refresh();
        area.focus();
        area.setSelectionRange(area.value.length, area.value.length);
    };

    const edit = node.addWidget?.("button", "✎ Edit entries…", null, () => ui.openEditor());
    if (edit) edit.serialize = false;
    ui.compactWidgets = () => (edit ? [edit] : []);
    ui.cancelDrag = () => { node._rayDeckEditor?.close(); node._rayDeckEditor?.remove(); node._rayDeckEditor = null; };
    // Initial size: room for the rows this deck needs.
    queueMicrotask(() => { ui.render(); ui.fitNode(); });
    return ui;
}

registerAnalog(app, {
    kind: "deck", name: "RayButtonDeck", title: "🎛️ Ray's Analog: Button Deck",
    extensionName: "Ray.ButtonDeck", menuName: "Deck",
    styles: DECK_STYLES, defaultStyle: DEFAULT_DECK_STYLE, valueName: "selected",
    outputs: [["value", "STRING"]], build: buildDeck,
    heights: ui => ({ min: ui.minHeight(), max: undefined }),
    menuItems: node => [{ content: "Edit entries…", callback: () => node._rayAnalog?.openEditor() }],
});
