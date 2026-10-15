import { THEMES, MARK, SLOT, materialColors } from "./analog_themes.js";

// Fader bank looks: the cap colours, the stripe across it, the slot and the scale marks. The first three are
// drawn for the bank; every other style is built from its description in analog_themes.js.
const NATIVE_FADERS = {
    console_black: {
        label: "Console · Black Faders", panel: "charcoal",
        capTop: "#a2a7ab", capBottom: "#464a4e", stripe: "#f4f4f0", slot: "#06090a", tick: "#a7b1a6",
    },
    studio_silver: {
        label: "Mastering · Silver Faders", panel: "silver",
        capTop: "#383c40", capBottom: "#101213", stripe: "#ffffff", slot: "#2b2f32", tick: "#3a3f43",
    },
    vintage_cream: {
        label: "Broadcast · Cream Faders", panel: "olive",
        capTop: "#f4eed8", capBottom: "#c4ba94", stripe: "#b3261e", slot: "#2a2f24", tick: "#46503c",
    },
};

const generated = Object.fromEntries(Object.entries(THEMES).filter(([id]) => !(id in NATIVE_FADERS)).map(([id, t]) => {
    const { hi, lo } = materialColors(t.body);
    return [id, { label: t.label, panel: t.panel, capTop: hi, capBottom: lo, stripe: t.accent, slot: SLOT[t.panel], tick: MARK[t.panel] }];
}));
export const FADER_STYLES = { ...NATIVE_FADERS, ...generated };
export const DEFAULT_FADER_STYLE = "console_black";

export function getFaderStyleCSS() {
    const palettes = Object.entries(FADER_STYLES).map(([key, s]) => `
.ray-fader-wrap[data-style="${key}"] {
    --cap-top:${s.capTop}; --cap-bottom:${s.capBottom}; --stripe:${s.stripe}; --slot:${s.slot}; --tick:${s.tick};
}`).join("");
    return `${palettes}
.ray-fader-wrap .ray-analog-face {
    display:flex; flex:1 1 150px; width:100%; height:auto; max-width:none; min-height:110px; padding:2px 0;
    gap:3px; justify-content:center; align-items:stretch; border-radius:0; cursor:default; touch-action:auto;
}
.ray-fader-strip {
    position:relative; flex:1 1 0; min-width:20px; max-width:46px; display:flex; flex-direction:column;
    align-items:center; outline:none; cursor:ns-resize; touch-action:none;
}
.ray-fader-track { position:relative; flex:1 1 auto; width:100%; min-height:80px; }
.ray-fader-scale {
    position:absolute; left:0; right:0; top:9px; bottom:9px; border-bottom:1px solid var(--tick);
    background:repeating-linear-gradient(to bottom, var(--tick) 0 1px, transparent 1px 10%);
    opacity:.55; pointer-events:none;
    -webkit-mask:linear-gradient(to right,#000 0 24%,transparent 24% 76%,#000 76%);
    mask:linear-gradient(to right,#000 0 24%,transparent 24% 76%,#000 76%);
}
.ray-fader-slot {
    position:absolute; left:50%; top:9px; bottom:9px; width:5px; margin-left:-2.5px; border-radius:3px;
    background:var(--slot); box-shadow:inset 0 1px 3px #000c, 0 1px 0 #ffffff30; pointer-events:none;
}
.ray-fader-cap {
    position:absolute; left:50%; width:min(28px,92%); height:18px; transform:translateX(-50%);
    bottom:calc(var(--v,0) * (100% - 18px)); border-radius:3px; pointer-events:none;
    background:linear-gradient(to bottom, var(--cap-top), var(--cap-bottom));
    box-shadow:0 2px 3px #0009, inset 0 1px 0 #ffffff55, inset 0 -1px 0 #0006;
}
.ray-fader-cap::after {
    content:""; position:absolute; left:3px; right:3px; top:50%; height:2px; margin-top:-1px;
    background:var(--stripe); border-radius:1px; box-shadow:0 0 0 1px #0004;
}
.ray-fader-num { margin-top:3px; font:9px/1 ui-monospace,monospace; opacity:.8; pointer-events:none; }
.ray-fader-strip[data-active="true"] .ray-fader-cap { filter:brightness(1.15); }
.ray-fader-strip:focus-visible .ray-fader-cap { outline:2px solid #185d89; outline-offset:2px; }
.ray-fader-strip[aria-disabled="true"] { opacity:.5; cursor:not-allowed; }
`;
}
