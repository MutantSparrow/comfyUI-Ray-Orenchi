// Button faces for the Analog Button Deck. Each face draws one button in a 100 x 100 box and uses the
// same state hooks as the switch faces: [data-toggle] moves with on/off transforms, [data-on-only] and
// [data-off-only] show a layer only when the button is pressed or released, and [data-label] receives
// the entry text. `legend: "cutout"` prints the text inside the button; `legend: "tape"` puts it on a
// Dymo sticker under the button. Style IDs stay stable for saved workflows.

const lin = (id, stops, [x1, y1, x2, y2] = [0, 0, 0, 1]) =>
    `<linearGradient id="${id}" x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}">${stops.map(([o, c]) => `<stop offset="${o}" stop-color="${c}"/>`).join("")}</linearGradient>`;
const rad = (id, stops, [cx, cy, r] = [.5, .5, .5]) =>
    `<radialGradient id="${id}" cx="${cx}" cy="${cy}" r="${r}">${stops.map(([o, c]) => `<stop offset="${o}" stop-color="${c}"/>`).join("")}</radialGradient>`;
const box = (cls, defs, body) =>
    `<svg viewBox="-50 -50 100 100" class="${cls}" xmlns="http://www.w3.org/2000/svg"><defs>${defs}</defs>${body}</svg>`;

// Machined steel bezel shared by several faces.
const STEEL = [[0, "#e3e1d7"], [.24, "#8b908d"], [.5, "#333b3c"], [.76, "#a1a4a0"], [1, "#383d3b"]];

const text = (state, fill, extra = "") =>
    `<text data-label data-${state}-only x="0" y="0" text-anchor="middle" dominant-baseline="central" fill="${fill}" font-family="ui-monospace,Consolas,monospace" font-weight="700" ${extra}></text>`;

export const DECK_STYLES = {
    amber_keys: {
        label: "Console · Amber Keys", panel: "charcoal", legend: "cutout", box: [54, 40, 15], sound: "key",
        svg: box("rd--amber_keys", [
            lin("bez", STEEL, [0, 0, .8, 1]), lin("cap", [[0, "#f5eed7"], [.5, "#d0c6aa"], [1, "#8d8169"]], [0, 0, .5, 1]),
            lin("lit", [[0, "#ffe3a1"], [.35, "#dba551"], [1, "#8a571e"]]), lin("dim", [[0, "#4a3d2a"], [1, "#241b11"]]),
        ].join(""), `
          <rect x="-43" y="-40" width="88" height="88" rx="6" fill="#000" opacity=".3"/>
          <rect x="-44" y="-44" width="88" height="88" rx="5" fill="url(#bez)"/>
          <rect x="-40" y="-40" width="80" height="80" rx="3" fill="#080c0d"/>
          <g data-toggle data-on-transform="translate(0,2.4)" data-off-transform="translate(0,-.6)">
            <rect x="-36" y="-36" width="72" height="72" rx="3" fill="url(#cap)" stroke="#9c9b85"/>
            <rect data-on-only x="-31" y="-31" width="62" height="62" rx="2" fill="url(#lit)"/>
            <rect data-on-only x="-31" y="-31" width="62" height="62" rx="2" fill="#fff0c0" opacity=".18"/>
            <rect data-off-only x="-31" y="-31" width="62" height="62" rx="2" fill="url(#dim)"/>
            <path d="M-29 -29.5H29" stroke="#fff5d1" stroke-opacity=".4"/>
            ${text("on", "#2b1a06")}${text("off", "#9b7a3f")}
          </g>`),
    },
    dome_lamps: {
        label: "Console · Lamp Domes", panel: "charcoal", legend: "cutout", box: [50, 38, 14], sound: "dome",
        svg: box("rd--dome_lamps", [
            lin("ring", STEEL, [0, 0, .8, 1]),
            rad("on", [[0, "#d7ffe9"], [.5, "#7fe3b5"], [1, "#2f9c72"]], [.45, .4, .65]),
            rad("off", [[0, "#25403d"], [1, "#0b1514"]], [.4, .35, .7]),
        ].join(""), `
          <ellipse cx="2" cy="5" rx="43" ry="43" fill="#000" opacity=".3"/>
          <circle data-on-only r="47" fill="#7fffc4" opacity=".16"/>
          <circle r="43" fill="url(#ring)"/><circle r="39" fill="#0b1011"/>
          <g data-toggle data-on-transform="translate(0,1.8)" data-off-transform="translate(0,-.6)">
            <circle data-off-only r="35" fill="url(#off)" stroke="#31504b"/>
            <circle data-on-only r="35" fill="url(#on)" stroke="#a8efcd"/>
            <path d="M-24 -19Q0 -37 24 -19" fill="none" stroke="#fff" stroke-opacity=".26" stroke-width="1.5" stroke-linecap="round"/>
            ${text("on", "#0b2a20")}${text("off", "#5f9a88")}
          </g>`),
    },
    bakelite_rounds: {
        label: "Broadcast · Bakelite Pushbuttons", panel: "olive", legend: "tape", sound: "bakelite",
        svg: box("rd--bakelite_rounds", [
            lin("ring", STEEL, [0, 0, .8, 1]),
            lin("bk", [[0, "#6a5246"], [.3, "#45322a"], [.72, "#2b201c"], [1, "#181716"]], [0, 0, .65, 1]),
            rad("lamp", [[0, "#ffd0b0"], [.5, "#e0653a"], [1, "#7a2410"]], [.4, .35, .65]),
        ].join(""), `
          <ellipse cx="2" cy="5" rx="43" ry="43" fill="#000" opacity=".28"/>
          <circle r="43" fill="url(#ring)"/><circle r="39" fill="#14100d"/>
          <g data-toggle data-on-transform="translate(0,2.2)" data-off-transform="translate(0,-.8)">
            <circle r="35" fill="url(#bk)" stroke="#1c211c"/>
            <circle r="32" fill="none" stroke="#c4a880" stroke-opacity=".18"/>
            <circle data-on-only r="25" fill="none" stroke="#ff7a3a" stroke-opacity=".32" stroke-width="7"/>
            <circle data-on-only r="25" fill="none" stroke="#ff9a68" stroke-width="2.6"/>
            <circle data-off-only r="25" fill="none" stroke="#3b2218" stroke-width="2.6"/>
            <circle r="21" fill="url(#bk)" stroke="#120d0b"/>
            <circle data-on-only r="8.5" fill="url(#lamp)"/>
            <circle data-off-only r="8.5" fill="#2a1710" stroke="#0c0605"/>
            <path d="M-19 -21Q0 -32 19 -21" fill="none" stroke="#e8d9bf" stroke-opacity=".3"/>
          </g>`),
    },
    chrome_squares: {
        label: "Mastering · Chrome Squares", panel: "silver", legend: "tape", sound: "chrome",
        svg: box("rd--chrome_squares", [
            lin("ring", STEEL, [0, 0, .85, 1]),
            rad("alu", [[0, "#eceae0"], [.45, "#b8bbb6"], [.8, "#8a9692"], [1, "#adb4ad"]], [.3, .25, .85]),
            lin("led", [[0, "#c9ffd8"], [.4, "#58e07f"], [1, "#1d8f46"]]),
        ].join(""), `
          <rect x="-43" y="-40" width="88" height="88" rx="8" fill="#000" opacity=".26"/>
          <rect x="-44" y="-44" width="88" height="88" rx="7" fill="url(#ring)"/>
          <rect x="-40" y="-40" width="80" height="80" rx="5" fill="#101a1b"/>
          <g data-toggle data-on-transform="translate(0,2.2)" data-off-transform="translate(0,-.8)">
            <rect x="-35" y="-35" width="70" height="70" rx="4" fill="url(#alu)" stroke="#63776d" stroke-width=".7"/>
            <rect data-on-only x="-35" y="-35" width="70" height="70" rx="4" fill="#000" opacity=".12"/>
            ${[4, 9, 14, 19, 24, 29].map(y => `<path d="M-29 ${y}H29" stroke="#627169" stroke-opacity=".5" stroke-width=".6"/>`).join("")}
            <rect x="-15" y="-29" width="30" height="10" rx="2" fill="#161810" stroke="#060e10"/>
            <rect data-on-only x="-19" y="-32" width="38" height="16" rx="5" fill="#6cff9a" opacity=".24"/>
            <rect data-on-only x="-13" y="-27.5" width="26" height="7" rx="1.4" fill="url(#led)"/>
            <rect data-off-only x="-13" y="-27.5" width="26" height="7" rx="1.4" fill="#1d3a26"/>
          </g>`),
    },
    tape_keys: {
        label: "Rack · Tape Deck Keys", panel: "olive", legend: "tape", sound: "tape",
        svg: box("rd--tape_keys", [
            lin("ring", STEEL, [0, 0, .8, 1]),
            lin("key", [[0, "#5b6163"], [.1, "#34393b"], [.6, "#1a1e1f"], [1, "#0c0f10"]]),
        ].join(""), `
          <rect x="-33" y="-45" width="68" height="96" rx="5" fill="#000" opacity=".28"/>
          <rect x="-33" y="-48" width="66" height="96" rx="4" fill="url(#ring)"/>
          <rect x="-29" y="-45" width="58" height="90" rx="3" fill="#050808"/>
          <rect data-on-only x="-27" y="-45" width="54" height="4" rx="1" fill="#ffb347"/>
          <rect data-on-only x="-27" y="-45" width="54" height="9" rx="2" fill="#ff9d2f" opacity=".3"/>
          <g data-toggle data-on-transform="translate(0,6)" data-off-transform="translate(0,-1)">
            <rect x="-26" y="-40" width="52" height="76" rx="3" fill="url(#key)" stroke="#000" stroke-opacity=".7"/>
            <rect data-on-only x="-26" y="-40" width="52" height="5" rx="1.5" fill="#ff6a4a"/>
            <rect data-off-only x="-26" y="-40" width="52" height="5" rx="1.5" fill="#7d3a2c"/>
            ${[-28, -23, -18, -13].map(y => `<path d="M-21 ${y}H21" stroke="#000" stroke-width="1.1"/><path d="M-21 ${y + 1.2}H21" stroke="#8f9a9c" stroke-opacity=".25" stroke-width=".6"/>`).join("")}
            <path d="M-23 -37.5H23" stroke="#c4cacb" stroke-opacity=".35"/>
          </g>
          <rect x="-29" y="36" width="58" height="12" rx="3" fill="url(#ring)"/>
          <rect x="-29" y="40" width="58" height="6" fill="#050808"/>`),
    },
};

export const DEFAULT_DECK_STYLE = "amber_keys";

// Scales the legend text to the cutout box: one line if it fits, two lines for multi-word text.
export function layoutLegend(el, textValue, [boxWidth, boxHeight, maxSize]) {
    const value = String(textValue ?? "");
    const widthPerChar = .62;
    const fit = (chars, lines) => Math.min(maxSize, boxWidth / (Math.max(1, chars) * widthPerChar), boxHeight / (lines * 1.15));
    let lines = [value], size = fit(value.length, 1);
    const words = value.split(/\s+/);
    if (size < maxSize * .7 && words.length > 1) {
        // Split at the most balanced space.
        let best = 0, bestGap = Infinity;
        for (let i = 1; i < words.length; i++) {
            const gap = Math.abs(words.slice(0, i).join(" ").length - words.slice(i).join(" ").length);
            if (gap < bestGap) { bestGap = gap; best = i; }
        }
        const pair = [words.slice(0, best).join(" "), words.slice(best).join(" ")];
        const twoLine = fit(Math.max(pair[0].length, pair[1].length), 2);
        if (twoLine > size) { lines = pair; size = twoLine; }
    }
    size = Math.max(4.5, size);
    const limit = Math.floor(boxWidth / (size * widthPerChar));
    lines = lines.map(line => line.length > limit ? `${line.slice(0, Math.max(1, limit - 1))}…` : line);
    el.setAttribute("font-size", size.toFixed(2));
    el.replaceChildren(...lines.map((line, i) => {
        const span = document.createElementNS("http://www.w3.org/2000/svg", "tspan");
        span.setAttribute("x", "0");
        span.setAttribute("dy", i === 0 ? (lines.length === 2 ? `${(-.58 * size).toFixed(2)}` : "0") : `${(1.16 * size).toFixed(2)}`);
        span.textContent = line;
        return span;
    }));
}

// Grid shape for n buttons: columns = ceil(sqrt(n)), so 2 -> 2x1, 3 and 4 -> 2x2, 5 and 6 -> 3x2, 7..9 -> 3x3.
export function gridShape(count) {
    const n = Math.max(1, count);
    const cols = Math.ceil(Math.sqrt(n));
    return { cols, rows: Math.ceil(n / cols) };
}

export function getDeckStyleCSS() {
    return `
.ray-deck-wrap .ray-analog-face {
    flex:1 1 0; width:100%; height:auto; max-width:none; min-height:0; padding:2px; border-radius:0;
    display:grid; gap:6px; cursor:default; touch-action:auto;
    grid-template-columns:repeat(var(--deck-cols,1),minmax(0,1fr));
    grid-auto-rows:minmax(0,1fr);
}
.ray-deck-cell { display:flex; flex-direction:column; align-items:center; gap:3px; min-width:0; min-height:0; }
.ray-deck-button {
    flex:1 1 0; min-height:0; width:100%; padding:0; border:0; border-radius:8px; background:transparent;
    cursor:pointer; outline:none; touch-action:none;
}
.ray-deck-button svg { display:block; width:100%; height:100%; overflow:visible; pointer-events:none; }
.ray-deck-button svg [data-toggle] { transition:transform .06s ease-out; }
.ray-deck-button:focus-visible { outline:2px solid #185d89; outline-offset:2px; }
.ray-deck-button:hover:not([aria-checked="true"]) svg { filter:brightness(1.07); }
.ray-deck-sticker {
    box-sizing:border-box; flex:0 0 auto; width:100%; max-width:100%; padding:3px 7px 2px;
    background:linear-gradient(180deg,#1c1c1c,#0a0a0a 50%,#050505); box-shadow:inset 0 1px 0 #ffffff1f, 0 1px 2px #000c;
    color:#f2f2f2; font:700 9px/1.1 "Helvetica Neue","Arial Narrow",sans-serif; letter-spacing:.14em;
    text-transform:uppercase; text-align:center; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;
    text-shadow:0 -1px 0 #000e, 0 1px 0 #ffffff2e; user-select:none;
}
.ray-deck-button[aria-checked="true"] + .ray-deck-sticker { color:#ffd98a; }
.ray-deck-readout { min-width:0; max-width:94%; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.ray-deck-empty { grid-column:1/-1; align-self:center; text-align:center; font:11px ui-monospace,monospace; opacity:.75; }
.ray-deck-editor {
    width:min(560px,92vw); max-height:84vh; padding:16px; border:1px solid #62616d; border-radius:10px;
    background:#24252b; color:#eee; font:13px system-ui,sans-serif;
}
.ray-deck-editor::backdrop { background:#0008; }
.ray-deck-editor * { box-sizing:border-box; }
.ray-deck-editor h3 { margin:0 0 4px; font-size:16px; }
.ray-deck-editor p { margin:0 0 10px; color:#b9b8c2; }
.ray-deck-editor textarea {
    display:block; width:100%; height:260px; padding:8px; resize:vertical; color:#eee; background:#14151a;
    border:1px solid #383840; border-radius:6px; font:13px/1.5 ui-monospace,Consolas,monospace; white-space:pre; overflow:auto;
}
.ray-deck-editor-info { min-height:18px; margin:8px 0; color:#c0bdc8; font-size:12px; }
.ray-deck-editor-actions { display:flex; justify-content:flex-end; gap:8px; }
.ray-deck-editor button {
    padding:5px 14px; color:inherit; background:#171717; border:1px solid #383838; border-radius:4px; font:inherit; cursor:pointer;
}
.ray-deck-editor button:hover { background:#454753; }
.ray-deck-editor button[data-primary] { background:#2c5f86; border-color:#3c7aa8; }
.ray-deck-editor :focus-visible { outline:2px solid #b9a4fa; outline-offset:2px; }
@media (prefers-reduced-motion:reduce) { .ray-deck-button svg [data-toggle] { transition:none; } }
`;
}
