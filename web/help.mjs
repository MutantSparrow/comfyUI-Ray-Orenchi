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
//     title:   "Ray's VFX: CRT",
//     tagline: "Optional one-line summary.",
//     sections: [
//       { heading: "What it does", body: "One or more paragraphs.\n\nBlank line = new paragraph." },
//       { heading: "Key inputs",   bullets: ["`preset` — SOTA-inspired CRT model.", "`intensity` — master mix."] },
//       { heading: "Modes",        defs: [ ["Term", "meaning"], ... ] },
//     ],
//     footer: "Optional tip line at the bottom.",
//   }

import { app } from "../../scripts/app.js";

const CSS_ID = "ray-help-css";
const BRAND = "#c86432";

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
.ray-help-defs dd { margin: 0; color: #bcbcbc; }
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

export function openHelpPopup(helpDef) {
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
    title.textContent = helpDef.title || "Help";
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
    if (helpDef.tagline) {
        const tag = document.createElement("p");
        tag.className = "ray-help-p";
        tag.style.color = "#e6e6e6";
        tag.innerHTML = fmt(helpDef.tagline);
        body.appendChild(tag);
    }
    const sections = Array.isArray(helpDef.sections) ? helpDef.sections : [];
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
