// One list of looks for every analog control. Each of the 31 styles belongs to a family (Console,
// Broadcast, Mastering, Rack) and is described once, by its materials and colours. The hand-drawn face
// stays on the control it was drawn for (`native`); every other control gets a face built from the same
// description, so any style can be picked on any control. Style IDs stay stable for saved workflows.
//
// This file is data and small helpers only, so the face modules and the audio engine can all import it.

// Gradient stops for the materials the faces are made of (the same set analog_hardware.js defines).
export const MATERIALS = {
    rim: [[0, "#e3e1d7"], [.22, "#8b908d"], [.47, "#333b3c"], [.73, "#a1a4a0"], [1, "#383d3b"]],
    rubber: [[0, "#41474a"], [.55, "#252a2c"], [1, "#101517"]],
    cap: [[0, "#9cabb0"], [.38, "#687d87"], [.65, "#4f6570"], [1, "#374b54"]],
    ivory: [[0, "#f5eed7"], [.5, "#d0c6aa"], [1, "#8d8169"]],
    silver: [[0, "#eeeae0"], [.42, "#b5b8b3"], [.72, "#818b89"], [1, "#b9bcb4"]],
    rocker: [[0, "#53585a"], [.12, "#353a3c"], [.7, "#181d20"], [1, "#0b1012"]],
    graphite: [[0, "#414a4c"], [.5, "#242c2f"], [1, "#10191c"]],
    bakelite: [[0, "#685145"], [.3, "#45322a"], [.72, "#2b201c"], [1, "#181716"]],
    brass: [[0, "#d3c299"], [.24, "#b6a06f"], [.5, "#8b784e"], [.72, "#baa879"], [1, "#665b3e"]],
    "brass-face": [[0, "#ddd0a6"], [.5, "#b6a475"], [1, "#887749"]],
    aluminium: [[0, "#e4e7de"], [.42, "#b5bdb7"], [.8, "#8a9692"], [1, "#a9b1aa"]],
    chrome: [[0, "#eaede7"], [.19, "#a7afad"], [.4, "#424e51"], [.61, "#c0c6bf"], [.83, "#727e7c"], [1, "#303b3e"]],
    "ivory-pale": [[0, "#eee8d1"], [.5, "#c9c5af"], [1, "#858877"]],
};
// Materials that read as light, so edges and marks on them go dark.
const LIGHT = new Set(["ivory", "silver", "aluminium", "chrome", "brass", "brass-face", "ivory-pale"]);
export const isLight = material => LIGHT.has(material);

// Scale marks and printed text, by panel.
export const MARK = { charcoal: "#d0d2c2", silver: "#303633", olive: "#292e28" };
export const SLOT = { charcoal: "#06090a", silver: "#2b2f32", olive: "#2a2f24" };

// `voice` names a sound class; VOICE_CLASSES says which sound that class makes on each kind of control.
// body/trim: the main material and the bezel material. accent: the mark that shows the position.
// lamp: the colour it lights up in. legend: where a deck prints its text.
export const THEMES = {
    // ---- drawn as rotary knobs --------------------------------------------------------------------
    console_rotary: { label: "Console · Blue Grey", panel: "charcoal", native: "knob", body: "cap", trim: "rim", accent: "#eee8ca", lamp: "#8fd0d8", voice: "rubber" },
    ivory_selector: { label: "Broadcast · Ivory", panel: "olive", native: "knob", body: "ivory", trim: "rubber", accent: "#30382f", lamp: "#c9803a", voice: "bakelite" },
    precision_dial: { label: "Mastering · Aluminium", panel: "silver", native: "knob", body: "silver", trim: "rim", accent: "#293533", lamp: "#e6b977", voice: "alu" },
    chrome_notched: { label: "Mastering · Chrome Notched", panel: "silver", native: "knob", body: "aluminium", trim: "chrome", accent: "#293533", lamp: "#e6b977", voice: "alu" },
    dark_studio_led: { label: "Console · LED Ring", panel: "charcoal", native: "knob", body: "graphite", trim: "chrome", accent: "#a6d5c4", lamp: "#91c9bd", voice: "rubber" },
    bakelite_chickenhead: { label: "Broadcast · Bakelite Chickenhead", panel: "olive", native: "knob", body: "bakelite", trim: "bakelite", accent: "#ded1ad", lamp: "#e0653a", voice: "bakelite" },
    silver_skirted: { label: "Mastering · Silver Skirted", panel: "silver", native: "knob", body: "aluminium", trim: "chrome", accent: "#34433c", lamp: "#58e07f", voice: "alu" },
    knurled_brass: { label: "Broadcast · Knurled Brass", panel: "olive", native: "knob", body: "brass-face", trim: "brass", accent: "#554a33", lamp: "#ae5942", voice: "brass" },
    minimal_flat: { label: "Console · Minimal Flat", panel: "charcoal", native: "knob", body: "graphite", trim: "graphite", accent: "#e1e4cf", lamp: "#c9d6c0", voice: "rubber" },
    // ---- drawn as sliders -------------------------------------------------------------------------
    studio_fader: { label: "Console · Linear Fader", panel: "charcoal", native: "slider", body: "ivory", trim: "rim", accent: "#323b36", lamp: "#f0a43b", voice: "fader" },
    channel_fader: { label: "Console · Channel Fader", panel: "silver", native: "slider", body: "rocker", trim: "rim", accent: "#f1efe5", lamp: "#e0483a", voice: "fader" },
    led_ladder: { label: "Rack · LED Ladder", panel: "charcoal", native: "slider", body: "rocker", trim: "rim", accent: "#ef5a48", lamp: "#58e07f", voice: "plastic" },
    pan_slider: { label: "Broadcast · Pan Slider", panel: "olive", native: "slider", body: "rocker", trim: "rim", accent: "#f0ead2", lamp: "#d9a441", voice: "pan" },
    amber_slide: { label: "Rack · Amber Slide", panel: "charcoal", native: "slider", body: "rocker", trim: "rim", accent: "#ffc05c", lamp: "#f0a43b", voice: "plastic" },
    // ---- drawn as switches ------------------------------------------------------------------------
    console_rocker: { label: "Rack · Power Rocker", panel: "charcoal", native: "switch", body: "rocker", trim: "rim", accent: "#d7daca", lamp: "#dba551", voice: "rocker" },
    broadcast_lever: { label: "Broadcast · Steel Lever", panel: "olive", native: "switch", body: "rim", trim: "rim", accent: "#f3f1d9", lamp: "#c4663a", voice: "lever" },
    illuminated_key: { label: "Console · Illuminated Key", panel: "charcoal", native: "switch", body: "ivory", trim: "rim", accent: "#3a3728", lamp: "#dba551", voice: "key" },
    chrome_rocker: { label: "Rack · Chrome Rocker", panel: "silver", native: "switch", body: "graphite", trim: "chrome", accent: "#d5d8c5", lamp: "#d9704a", voice: "rocker" },
    dark_studio_dome: { label: "Console · Dome Button", panel: "charcoal", native: "switch", body: "graphite", trim: "chrome", accent: "#b7c9b8", lamp: "#93c6b1", voice: "dome" },
    bakelite_flip: { label: "Broadcast · Bakelite Flip", panel: "olive", native: "switch", body: "bakelite", trim: "chrome", accent: "#f1e4bd", lamp: "#d8b070", voice: "bakelite" },
    silver_paddle: { label: "Mastering · Silver Paddle", panel: "silver", native: "switch", body: "aluminium", trim: "chrome", accent: "#293d34", lamp: "#9dbb81", voice: "paddle" },
    brass_slider: { label: "Broadcast · Brass Slide", panel: "olive", native: "switch", body: "brass-face", trim: "brass", accent: "#3b3524", lamp: "#9dbb81", voice: "slider" },
    minimal_pill: { label: "Console · Minimal Pill", panel: "charcoal", native: "switch", body: "ivory-pale", trim: "chrome", accent: "#4f5d4c", lamp: "#7fa66f", voice: "pill" },
    // ---- drawn as deck buttons --------------------------------------------------------------------
    amber_keys: { label: "Console · Amber Keys", panel: "charcoal", native: "deck", body: "ivory", trim: "rim", accent: "#2b1a06", lamp: "#dba551", voice: "key", legend: "cutout" },
    dome_lamps: { label: "Console · Lamp Domes", panel: "charcoal", native: "deck", body: "graphite", trim: "rim", accent: "#a9e6cc", lamp: "#7fe3b5", voice: "dome", legend: "cutout" },
    bakelite_rounds: { label: "Broadcast · Bakelite Pushbuttons", panel: "olive", native: "deck", body: "bakelite", trim: "rim", accent: "#e8d9bf", lamp: "#ff7a3a", voice: "bakelite", legend: "tape" },
    chrome_squares: { label: "Mastering · Chrome Squares", panel: "silver", native: "deck", body: "aluminium", trim: "rim", accent: "#293d34", lamp: "#58e07f", voice: "chrome", legend: "tape" },
    tape_keys: { label: "Rack · Tape Deck Keys", panel: "olive", native: "deck", body: "rocker", trim: "rim", accent: "#c4cacb", lamp: "#ff9d2f", voice: "tape", legend: "tape" },
    // ---- drawn as fader-bank caps -----------------------------------------------------------------
    console_black: { label: "Console · Black Faders", panel: "charcoal", native: "fader", body: "cap", trim: "rim", accent: "#f4f4f0", lamp: "#8fd0d8", voice: "fader" },
    studio_silver: { label: "Mastering · Silver Faders", panel: "silver", native: "fader", body: "rocker", trim: "rim", accent: "#ffffff", lamp: "#58e07f", voice: "fader" },
    vintage_cream: { label: "Broadcast · Cream Faders", panel: "olive", native: "fader", body: "ivory-pale", trim: "brass", accent: "#b3261e", lamp: "#d9a441", voice: "fader" },
};

// The sound each class makes on each kind of control. The names are the voices analog_audio.js already has:
// knob/slider ticks, switch presses and deck presses.
export const VOICE_CLASSES = {
    rubber:   { knob: "rubber",   slider: "fader",   switch: "rocker", deck: "tape" },
    bakelite: { knob: "bakelite", slider: "pan",     switch: "bakelite", deck: "bakelite" },
    alu:      { knob: "alu",      slider: "fader",   switch: "paddle", deck: "chrome" },
    brass:    { knob: "brass",    slider: "pan",     switch: "slider", deck: "key" },
    fader:    { knob: "rubber",   slider: "fader",   switch: "rocker", deck: "tape" },
    plastic:  { knob: "rubber",   slider: "plastic", switch: "pill",   deck: "key" },
    pan:      { knob: "bakelite", slider: "pan",     switch: "lever",  deck: "bakelite" },
    rocker:   { knob: "rubber",   slider: "fader",   switch: "rocker", deck: "tape" },
    lever:    { knob: "alu",      slider: "fader",   switch: "lever",  deck: "chrome" },
    key:      { knob: "rubber",   slider: "fader",   switch: "key",    deck: "key" },
    paddle:   { knob: "alu",      slider: "fader",   switch: "paddle", deck: "chrome" },
    slider:   { knob: "brass",    slider: "pan",     switch: "slider", deck: "key" },
    pill:     { knob: "rubber",   slider: "plastic", switch: "pill",   deck: "dome" },
    dome:     { knob: "rubber",   slider: "plastic", switch: "dome",   deck: "dome" },
    chrome:   { knob: "alu",      slider: "fader",   switch: "paddle", deck: "chrome" },
    tape:     { knob: "rubber",   slider: "fader",   switch: "rocker", deck: "tape" },
};
export const voiceFor = (id, kind) => VOICE_CLASSES[THEMES[id]?.voice]?.[kind];

export const FAMILIES = ["Console", "Broadcast", "Mastering", "Rack"];
export const familyOf = label => String(label).split(" · ")[0];

// Style IDs whose native face is not `kind`, in a stable order: these are the ones a control builds.
export const themesNotNative = kinds => Object.entries(THEMES).filter(([, t]) => !kinds.includes(t.native));

// ---- colour helpers for the generated faces ----------------------------------------------------------

const clamp = v => Math.max(0, Math.min(255, Math.round(v)));
export function parseColor(hex) {
    const h = String(hex).replace("#", "");
    const full = h.length === 3 ? h.split("").map(c => c + c).join("") : h;
    return [parseInt(full.slice(0, 2), 16), parseInt(full.slice(2, 4), 16), parseInt(full.slice(4, 6), 16)];
}
export const toHex = ([r, g, b]) => `#${[r, g, b].map(v => clamp(v).toString(16).padStart(2, "0")).join("")}`;
// Blend `a` toward `b` by `t` (0..1).
export function mix(a, b, t) {
    const [x, y] = [parseColor(a), parseColor(b)];
    return toHex(x.map((v, i) => v + (y[i] - v) * t));
}
export const lighten = (hex, t) => mix(hex, "#ffffff", t);
export const darken = (hex, t) => mix(hex, "#000000", t);

// Representative colours of a material: its highlight, middle and shade.
export function materialColors(name) {
    const stops = MATERIALS[name] || MATERIALS.rim;
    return { hi: stops[0][1], mid: stops[Math.floor((stops.length - 1) / 2)][1], lo: stops[stops.length - 1][1] };
}
