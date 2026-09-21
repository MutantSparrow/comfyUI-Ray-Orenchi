// Original style IDs remain stable for saved workflows. Artwork is shared by both renderers.
import { STUDIO_KNOBS } from "./analog_hardware.js";
import { LEGACY_KNOBS } from "./analog_legacy.js";

let _brushedNodeURL = null;
export function getBrushedAluminumURL() {
    if (_brushedNodeURL) return _brushedNodeURL;
    const c = document.createElement("canvas");
    c.width = 256; c.height = 256;
    const x = c.getContext("2d");
    const base = x.createLinearGradient(0, 0, 0, 256);
    base.addColorStop(0, "#c8c9cb");
    base.addColorStop(0.5, "#b6b8bb");
    base.addColorStop(1, "#9fa1a4");
    x.fillStyle = base; x.fillRect(0, 0, 256, 256);
    for (let i = 0; i < 1400; i++) {
        const y = Math.random() * 256;
        const len = 30 + Math.random() * 220;
        const xs = Math.random() * 256;
        const a = 0.04 + Math.random() * 0.10;
        x.strokeStyle = Math.random() > 0.5 ? `rgba(255,255,255,${a})` : `rgba(40,40,40,${a * 0.85})`;
        x.lineWidth = 0.4 + Math.random() * 0.6;
        x.beginPath();
        x.moveTo(xs, y);
        x.lineTo(xs + len, y + (Math.random() - 0.5) * 0.4);
        x.stroke();
    }
    const vg = x.createRadialGradient(128, 128, 30, 128, 128, 200);
    vg.addColorStop(0, "rgba(0,0,0,0)");
    vg.addColorStop(1, "rgba(0,0,0,0.10)");
    x.fillStyle = vg; x.fillRect(0, 0, 256, 256);
    _brushedNodeURL = c.toDataURL();
    return _brushedNodeURL;
}

export const KNOB_STYLES = { ...STUDIO_KNOBS, ...LEGACY_KNOBS };

export const DEFAULT_STYLE = "console_rotary";

export function listStyles() {
    return Object.keys(KNOB_STYLES);
}

// Concatenate all per-style CSS plus a small base block. ray_knob.js injects this once.
export function getAllStyleCSS() {
    const base = `
.rk-host { width:100%; height:100%; display:flex; align-items:center; justify-content:center; cursor:grab; touch-action:none; user-select:none; }
.rk-host:active { cursor:grabbing; }
.rk-host > svg { width:100%; height:100%; display:block; overflow:visible; pointer-events:none; }
.rk-host [data-rotate] { will-change: transform; }
.rk-host [data-arc]    { will-change: stroke-dasharray; }
`;
    let out = base;
    for (const v of Object.values(KNOB_STYLES)) {
        if (v.css) out += "\n" + v.css;
    }
    return out;
}
