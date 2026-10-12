// ray_help_toolbar.js — Ray's Orenchi help ? button in ComfyUI's node
// selection toolbar.
//
// ComfyUI calls `getSelectionToolboxCommands(item)` on every extension to
// collect command IDs to render on the toolbar above a selected node. We
// answer with a single "Ray.ShowHelp" command whenever the selected node
// has help registered.
//
// Each Ray node registers its help at beforeRegisterNodeDef time — see
// ./help_defs.mjs for the actual per-class content.

import { app } from "../../scripts/app.js";
import { openHelpPopup, getNodeHelp, registerNodeHelp } from "./help.mjs";
import { RAY_HELP_DEFS } from "./help_defs.mjs";

const CMD_ID = "Ray.ShowHelp";
const ICON_CLASS = "ray-help-toolbar-icon";
const CSS_ID = "ray-help-toolbar-css";
// Magenta — matches web/help.mjs.
const BRAND = "#d43aa8";

function injectIconCSS() {
    if (document.getElementById(CSS_ID)) return;
    const el = document.createElement("style");
    el.id = CSS_ID;
    el.textContent = `
        .${ICON_CLASS} {
            display: inline-flex; align-items: center; justify-content: center;
            width: 16px; height: 16px; border-radius: 50%;
            background: ${BRAND};
            color: #fff; font-weight: 800; font-size: 11px; font-family: sans-serif;
            line-height: 1;
        }
        .${ICON_CLASS}::before { content: "?"; }
    `;
    document.head.appendChild(el);
}

// Node definitions (object_info) by class; the popup builds its input,
// widget and output reference from these.
const _nodeData = new Map();

// First selected Ray node with registered help (or null).
function selectedHelp() {
    const c = app.canvas;
    if (!c) return null;
    const nodes = [];
    if (c.selected_nodes) nodes.push(...Object.values(c.selected_nodes));
    if (c.selectedItems) {
        for (const it of c.selectedItems) if (it && it.comfyClass) nodes.push(it);
    }
    for (const n of nodes) {
        const cls = n && n.comfyClass;
        const help = getNodeHelp(cls);
        if (help) return { help, nodeData: _nodeData.get(cls) || null };
    }
    return null;
}

// Register every predefined help def up front.
for (const [cls, def] of Object.entries(RAY_HELP_DEFS)) {
    registerNodeHelp(cls, def);
}

app.registerExtension({
    name: "Ray.HelpToolbar",
    commands: [
        {
            id: CMD_ID,
            label: "Help",
            icon: ICON_CLASS,
            function: () => {
                const sel = selectedHelp();
                if (sel) openHelpPopup(sel.help, sel.nodeData);
            },
        },
    ],
    // Show the ? command only when the selected node has help registered.
    getSelectionToolboxCommands(item) {
        if (!item || !item.comfyClass) return [];
        if (getNodeHelp(item.comfyClass)) return [CMD_ID];
        return [];
    },
    // Keep every Ray node's definition. A class without an authored help def
    // still gets one: its DESCRIPTION as the summary plus the generated
    // input/widget/output reference.
    async beforeRegisterNodeDef(nodeType, nodeData) {
        const name = nodeData?.name;
        if (!name || !name.startsWith("Ray")) return;
        _nodeData.set(name, nodeData);
        if (!getNodeHelp(name)) registerNodeHelp(name, {});
    },
    setup() {
        injectIconCSS();
    },
});
