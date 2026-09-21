// Original style IDs remain stable for saved workflows.
import { STUDIO_SWITCHES } from "./analog_hardware.js";
import { LEGACY_SWITCHES } from "./analog_legacy.js";

export const SWITCH_STYLES = { ...STUDIO_SWITCHES, ...LEGACY_SWITCHES };

export const DEFAULT_SWITCH_STYLE = "console_rocker";

export function listSwitchStyles() {
    return Object.keys(SWITCH_STYLES);
}

export function getAllSwitchStyleCSS() {
    const base = `
.rs-host { width:100%; height:100%; display:flex; align-items:center; justify-content:center; cursor:pointer; touch-action:none; user-select:none; }
.rs-host > svg { width:100%; height:100%; display:block; overflow:visible; pointer-events:none; }
.rs-host [data-toggle]   { will-change: transform; transition: transform 0.12s ease-out; }
.rs-host [data-on-only],
.rs-host [data-off-only] { transition: opacity 0.10s linear; }
`;
    let out = base;
    for (const v of Object.values(SWITCH_STYLES)) {
        if (v.css) out += "\n" + v.css;
    }
    return out;
}
