// help.mjs — Ray's Orenchi node help popup + registry.
//
// ComfyUI's built-in Info tab is plain-text and cramped. This module lets us
// register a rich, themed help card per node and expose a ? button in the
// node's selection toolbar (the floating bar above a selected node) via
// ComfyUI's getSelectionToolboxCommands hook.
//
// Public API:
//   registerNodeHelp(comfyClass, helpDef)
//   getNodeHelp(comfyClass)
//   openHelpPopup(helpDef)
//   closeHelpPopup()
//   injectHelpCSS()
//
// helpDef shape:
//   {
//     title:    "Ray's VFX: CRT",          // optional; node display name wins
//     summary:  "Brief description of what the node does.",
//     details:  { intensity: "Longer text overriding the Python tooltip." },
//     sections: [                           // optional notes after the reference
//       { heading: "Notes", bullets: ["Right-click menu …"] },
//       { heading: "Modes", defs: [ ["Term", "meaning"], ... ] },
//       { heading: "About", body: "Paragraphs.\n\nBlank line = new paragraph." },
//     ],
//     footer: "Optional tip line at the bottom.",
//   }
//
// openHelpPopup(helpDef, nodeData) renders: summary, then Inputs (sockets),
// Widgets and Outputs generated from the node definition (types, choices,
// defaults, ranges and Python tooltips), then the authored sections.

import { app } from "../../scripts/app.js";

const CSS_ID = "ray-help-css";
// Magenta highlight — deliberately distinct from other node packs' oranges.
const BRAND = "#d43aa8";

// ── Per-node help registry ─────────────────────────────────────────────
const _nodeHelp = new Map();
export function registerNodeHelp(comfyClass, helpDef) {
    if (comfyClass && helpDef) _nodeHelp.set(comfyClass, helpDef);
}
export function getNodeHelp(comfyClass) {
    return comfyClass ? _nodeHelp.get(comfyClass) || null : null;
}

// ── CSS ────────────────────────────────────────────────────────────────
const CSS = `
.ray-help-backdrop {
    position: fixed; inset: 0; background: rgba(0,0,0,0.5);
    display: flex; align-items: center; justify-content: center;
    z-index: 10000; font-family: inherit; -webkit-font-smoothing: antialiased;
}
.ray-help-card {
    background: #1d1d1d; border: 1px solid #333; border-radius: 8px;
    width: min(840px, 94vw); max-height: 82vh; display: flex; flex-direction: column;
    box-shadow: 0 14px 52px rgba(0,0,0,0.6); overflow: hidden; color: #cfcfcf;
    animation: ray-help-in 0.14s ease;
}
@keyframes ray-help-in {
    from { opacity: 0; transform: translateY(10px) scale(0.985); }
    to   { opacity: 1; transform: none; }
}
.ray-help-header {
    display: flex; align-items: center; gap: 10px;
    padding: 13px 14px 13px 16px; border-bottom: 1px solid #2c2c2c; flex: none;
}
.ray-help-h-icon {
    width: 20px; height: 20px; flex: none; border-radius: 50%;
    background: ${BRAND}; display: inline-flex; align-items: center; justify-content: center;
    color: #fff; font-weight: 800; font-size: 13px; font-family: sans-serif;
}
.ray-help-h-title { flex: 1; font-size: 15px; font-weight: 600; color: #fff; line-height: 1.2; }
.ray-help-close {
    flex: none; width: 26px; height: 26px; border-radius: 4px; border: none;
    background: rgba(255,255,255,0.05); color: #aaa; cursor: pointer;
    font-size: 15px; line-height: 1; display: flex; align-items: center; justify-content: center;
    transition: background 0.12s, color 0.12s;
}
.ray-help-close:hover { background: ${BRAND}; color: #fff; }
.ray-help-body { padding: 14px 16px 16px 16px; overflow-y: auto; font-size: 12.5px; line-height: 1.55; }
.ray-help-section { margin-bottom: 15px; }
.ray-help-section:last-child { margin-bottom: 0; }
.ray-help-h {
    margin: 0 0 6px 0; font-size: 11px; font-weight: 700; color: ${BRAND};
    text-transform: uppercase; letter-spacing: 0.5px;
}
.ray-help-p { margin: 0 0 6px 0; white-space: pre-wrap; color: #cfcfcf; }
.ray-help-p:last-child { margin-bottom: 0; }
.ray-help-ul { margin: 0; padding-left: 18px; }
.ray-help-ul li { margin: 0 0 4px 0; }
.ray-help-defs { display: grid; grid-template-columns: auto 1fr; gap: 5px 14px; align-items: baseline; }
.ray-help-defs dt { color: #fff; font-weight: 600; white-space: nowrap; }
.ray-help-defs dd { margin: 0; color: #bcbcbc; white-space: pre-line; }
.ray-help code {
    background: rgba(255,255,255,0.08); border-radius: 3px; padding: 1px 5px;
    font-family: monospace; font-size: 11.5px; color: #ffd2c4;
}
.ray-help-tip {
    margin-top: 4px; padding: 8px 11px; background: rgba(200,100,50,0.10);
    border-left: 2px solid ${BRAND}; border-radius: 3px; color: #ddd; font-size: 12px;
}
`;

export function injectHelpCSS() {
    if (document.getElementById(CSS_ID)) return;
    const el = document.createElement("style");
    el.id = CSS_ID;
    el.textContent = CSS;
    document.head.appendChild(el);
}

// ── Formatting ─────────────────────────────────────────────────────────
function fmt(s) {
    const esc = String(s == null ? "" : s)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");
    return esc.replace(/`([^`]+)`/g, (_m, code) => `<code>${code}</code>`);
}

function buildSection(section) {
    const sec = document.createElement("div");
    sec.className = "ray-help-section";

    if (section.heading) {
        const h = document.createElement("div");
        h.className = "ray-help-h";
        h.textContent = section.heading;
        sec.appendChild(h);
    }

    if (section.body) {
        for (const para of String(section.body).split(/\n\s*\n/)) {
            const p = document.createElement("p");
            p.className = "ray-help-p";
            p.innerHTML = fmt(para);
            sec.appendChild(p);
        }
    }

    if (Array.isArray(section.bullets) && section.bullets.length) {
        const ul = document.createElement("ul");
        ul.className = "ray-help-ul";
        for (const item of section.bullets) {
            const li = document.createElement("li");
            li.innerHTML = fmt(item);
            ul.appendChild(li);
        }
        sec.appendChild(ul);
    }

    if (Array.isArray(section.defs) && section.defs.length) {
        const dl = document.createElement("dl");
        dl.className = "ray-help-defs";
        for (const entry of section.defs) {
            const [term, desc] = Array.isArray(entry) ? entry : [entry, ""];
            const dt = document.createElement("dt");
            dt.innerHTML = fmt(term);
            const dd = document.createElement("dd");
            dd.innerHTML = fmt(desc);
            dl.appendChild(dt);
            dl.appendChild(dd);
        }
        sec.appendChild(dl);
    }

    return sec;
}

// ── Reference generated from the node definition ───────────────────────
const WIDGET_TYPES = new Set(["INT", "FLOAT", "STRING", "BOOLEAN", "COMBO"]);
const MAX_CHOICES = 12;

function fmtNumber(v) {
    return typeof v === "number" && !Number.isInteger(v) ? String(+v.toFixed(4)) : String(v);
}

function choicesOf(type, opts) {
    if (Array.isArray(type)) return type;
    if (type === "COMBO" && Array.isArray(opts.options)) return opts.options;
    return null;
}

function widgetMeta(type, opts, choices) {
    const parts = [];
    if (choices) {
        const shown = choices.slice(0, MAX_CHOICES).map((c) => `\`${c}\``).join(", ");
        const more = choices.length > MAX_CHOICES ? ` (+${choices.length - MAX_CHOICES} more)` : "";
        parts.push(`Choices: ${shown}${more}`);
    }
    if (type === "INT" || type === "FLOAT") {
        if (opts.min !== undefined && opts.max !== undefined) {
            parts.push(`Range ${fmtNumber(opts.min)} – ${fmtNumber(opts.max)}`);
        }
    }
    if (opts.default !== undefined && opts.default !== "") {
        const d = type === "BOOLEAN" ? (opts.default ? "on" : "off") : fmtNumber(opts.default);
        if (String(d).length <= 60) parts.push(`Default \`${d}\``);
    }
    return parts.join(" · ");
}

function orderedInputs(nodeData) {
    const input = nodeData?.input || {};
    const order = nodeData?.input_order || {};
    const out = [];
    for (const group of ["required", "optional"]) {
        const specs = input[group] || {};
        const names = Array.isArray(order[group]) ? order[group] : Object.keys(specs);
        for (const name of names) {
            if (specs[name]) out.push({ name, spec: specs[name], optional: group === "optional" });
        }
    }
    return out;
}

export function buildReferenceSections(nodeData, details = {}) {
    if (!nodeData) return [];
    const sockets = [];
    const widgets = [];
    for (const { name, spec, optional } of orderedInputs(nodeData)) {
        const [type, opts = {}] = Array.isArray(spec) ? spec : [spec];
        const choices = choicesOf(type, opts);
        const typeName = choices ? "COMBO" : String(type);
        const isWidget = (choices || WIDGET_TYPES.has(typeName)) && !opts.forceInput;
        const desc = details[name] || opts.tooltip || "";
        const tag = optional ? " (optional)" : "";
        if (isWidget) {
            const meta = widgetMeta(typeName, opts, choices);
            widgets.push([`\`${name}\``, [desc, meta].filter(Boolean).join("\n")]);
        } else {
            sockets.push([`\`${name}\` · ${typeName}${tag}`, desc]);
        }
    }
    const outputs = [];
    const types = nodeData.output || [];
    const names = nodeData.output_name || [];
    const tips = nodeData.output_tooltips || [];
    const lists = nodeData.output_is_list || [];
    types.forEach((type, i) => {
        const name = names[i] || String(type).toLowerCase();
        const list = lists[i] ? " list" : "";
        outputs.push([`\`${name}\` · ${type}${list}`, details[`output:${name}`] || tips[i] || ""]);
    });
    const sections = [];
    sections.push({ heading: "Inputs", defs: sockets.length ? sockets : [["—", "No input sockets; configure the node with its widgets."]] });
    if (widgets.length) sections.push({ heading: "Widgets", defs: widgets });
    sections.push({ heading: "Outputs", defs: outputs.length ? outputs : [["—", "No output sockets; this is an output node."]] });
    return sections;
}

// ── Popup ──────────────────────────────────────────────────────────────
let _openCleanup = null;

export function closeHelpPopup() {
    if (_openCleanup) _openCleanup();
}

// Universal safety net: close any open help panel when the workflow changes
// so a leftover panel can't swallow Escape app-wide.
let _graphHookInstalled = false;
function ensureGraphCloseHook() {
    if (_graphHookInstalled) return;
    if (!app || typeof app.loadGraphData !== "function") return;
    _graphHookInstalled = true;
    const orig = app.loadGraphData.bind(app);
    app.loadGraphData = function (...args) {
        closeHelpPopup();
        return orig(...args);
    };
}

export function openHelpPopup(helpDef, nodeData = null) {
    helpDef = helpDef || {};
    injectHelpCSS();
    ensureGraphCloseHook();
    closeHelpPopup();

    const backdrop = document.createElement("div");
    backdrop.className = "ray-help-backdrop";

    const card = document.createElement("div");
    card.className = "ray-help-card ray-help";
    backdrop.appendChild(card);

    // header
    const header = document.createElement("div");
    header.className = "ray-help-header";
    const icon = document.createElement("span");
    icon.className = "ray-help-h-icon";
    icon.textContent = "?";
    const title = document.createElement("div");
    title.className = "ray-help-h-title";
    title.textContent = nodeData?.display_name || helpDef.title || "Help";
    const close = document.createElement("button");
    close.className = "ray-help-close";
    close.type = "button";
    close.textContent = "✕";
    close.title = "Close (Esc)";
    header.appendChild(icon);
    header.appendChild(title);
    header.appendChild(close);
    card.appendChild(header);

    // body
    const body = document.createElement("div");
    body.className = "ray-help-body";
    const summary = helpDef.summary || helpDef.tagline || nodeData?.description;
    if (summary) {
        const tag = document.createElement("p");
        tag.className = "ray-help-p";
        tag.style.color = "#e6e6e6"; tag.style.marginBottom = "14px";
        tag.innerHTML = fmt(summary);
        body.appendChild(tag);
    }
    const sections = [
        ...buildReferenceSections(nodeData, helpDef.details),
        ...(Array.isArray(helpDef.sections) ? helpDef.sections : []),
    ];
    for (const section of sections) {
        try {
            body.appendChild(buildSection(section));
        } catch (e) {
            console.warn("Ray help: skipped a malformed section", e);
        }
    }
    if (helpDef.footer) {
        const tip = document.createElement("div");
        tip.className = "ray-help-tip";
        tip.innerHTML = fmt(helpDef.footer);
        body.appendChild(tip);
    }
    card.appendChild(body);

    // close wiring
    let mouseDownOnBackdrop = false;
    const cleanup = () => {
        document.removeEventListener("keydown", onKey, true);
        backdrop.remove();
        if (_openCleanup === cleanup) _openCleanup = null;
    };
    _openCleanup = cleanup;

    const onKey = (e) => {
        if (e.key === "Escape") {
            e.stopPropagation();
            e.preventDefault();
            cleanup();
        }
    };
    document.addEventListener("keydown", onKey, true);

    close.addEventListener("click", (e) => { e.stopPropagation(); cleanup(); });
    backdrop.addEventListener("mousedown", (e) => { mouseDownOnBackdrop = e.target === backdrop; });
    backdrop.addEventListener("click", (e) => {
        if (e.target === backdrop && mouseDownOnBackdrop) cleanup();
        mouseDownOnBackdrop = false;
    });
    card.addEventListener("mousedown", (e) => e.stopPropagation());

    document.body.appendChild(backdrop);
    return cleanup;
}

// ── Fallback: turn a plain DESCRIPTION string into a minimal helpDef ───
// So a node that hasn't authored a full sections spec still gets *something*.
export function descToHelpDef(title, descStr) {
    if (!descStr) return null;
    const paragraphs = String(descStr).split(/\n\s*\n/);
    return {
        title: title || "Help",
        tagline: paragraphs.length > 1 ? paragraphs[0] : "",
        sections: [
            {
                heading: "About",
                body: paragraphs.length > 1 ? paragraphs.slice(1).join("\n\n") : paragraphs[0],
            },
        ],
    };
}
