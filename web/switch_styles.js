// switch_styles.js — Ray's Switch style registry (SVG + CSS sidecar)
// Each style entry:  { label, svg, css }
//   svg : string injected as innerHTML of the switch host.
//          Must contain a single <svg> root with viewBox = "-70 -70 140 140".
//   css : string of CSS rules. Scope your selectors under .rs--<key> to avoid collisions.
//
// Magic data-attributes the runtime understands:
//   data-toggle           → element whose transform attribute is set per state.
//                            Provide data-on-transform="..." and data-off-transform="..."
//                            (any valid SVG transform — rotate(deg), translate(x,y), etc).
//   data-on-only          → element only displayed when state == true.
//   data-off-only         → element only displayed when state == false.
//   data-readout          → textContent set to "ON"/"OFF" (optional override).
//
// To add a style: append an entry to SWITCH_STYLES below. No edits to ray_switch.js.

import { TWO_PI, getRadialBrushedURL } from "./_common.js";

// ─────────────────────────── style: chrome_rocker ───────────────────────────
const chromeRocker = (() => ({
    label: "Chrome Rocker",
    svg: `
<svg viewBox="-70 -70 140 140" class="rs--chrome_rocker" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="cr-bezel" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%"  stop-color="#3a3a3a"/>
      <stop offset="20%" stop-color="#a8a8a8"/>
      <stop offset="50%" stop-color="#f0f0f0"/>
      <stop offset="80%" stop-color="#a8a8a8"/>
      <stop offset="100%" stop-color="#3a3a3a"/>
    </linearGradient>
    <linearGradient id="cr-rocker" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%"  stop-color="#1a1a1a"/>
      <stop offset="50%" stop-color="#3e3e3e"/>
      <stop offset="100%" stop-color="#0d0d0d"/>
    </linearGradient>
    <radialGradient id="cr-led-on" cx="50%" cy="50%" r="50%">
      <stop offset="0%"  stop-color="#fff8b0"/>
      <stop offset="35%" stop-color="#ff3424"/>
      <stop offset="100%" stop-color="#560a05"/>
    </radialGradient>
    <radialGradient id="cr-shadow" cx="50%" cy="50%" r="50%">
      <stop offset="0%"  stop-color="rgba(0,0,0,0.55)"/>
      <stop offset="100%" stop-color="rgba(0,0,0,0)"/>
    </radialGradient>
  </defs>
  <ellipse cx="0" cy="58" rx="44" ry="8" fill="url(#cr-shadow)"/>
  <rect x="-32" y="-58" width="64" height="116" rx="6" fill="url(#cr-bezel)"/>
  <rect x="-32" y="-58" width="64" height="116" rx="6" fill="none" stroke="rgba(0,0,0,0.55)" stroke-width="0.7"/>
  <rect x="-24" y="-48" width="48" height="96" rx="3" fill="#0e0e0e"/>
  <!-- Physical rocker: LED sits above the top. Pressing the LED end DOWN
       (top edge goes toward viewer) turns ON, so ON=positive rotate. Also
       swap the top/bottom shading so the "depressed" edge takes the dark. -->
  <g data-toggle data-on-transform="rotate(8)" data-off-transform="rotate(-8)">
    <rect x="-20" y="-44" width="40" height="88" rx="3" fill="url(#cr-rocker)"/>
    <rect x="-18" y="-42" width="36" height="6"  fill="rgba(255,255,255,0.14)"/>
    <rect x="-18" y="36"  width="36" height="6"  fill="rgba(0,0,0,0.45)"/>
    <line x1="-14" y1="0" x2="14" y2="0" stroke="rgba(255,255,255,0.10)" stroke-width="0.6"/>
  </g>
  <circle data-on-only  cx="0" cy="-50" r="3.5" fill="url(#cr-led-on)" style="filter: drop-shadow(0 0 4px #ff3624);"/>
  <circle data-off-only cx="0" cy="-50" r="3.5" fill="#3a0a07" stroke="rgba(0,0,0,0.6)" stroke-width="0.5"/>
</svg>`,
    css: ``,
}))();

// ─────────────────────────── style: dark_studio_dome ───────────────────────────
const darkStudioDome = (() => ({
    label: "Dark Studio Dome",
    svg: `
<svg viewBox="-70 -70 140 140" class="rs--dark_studio_dome" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <radialGradient id="dsd-body" cx="35%" cy="30%" r="65%">
      <stop offset="0%"  stop-color="#2a2a2a"/>
      <stop offset="55%" stop-color="#161616"/>
      <stop offset="100%" stop-color="#070707"/>
    </radialGradient>
    <radialGradient id="dsd-dome-off" cx="35%" cy="30%" r="65%">
      <stop offset="0%"  stop-color="#3c3c3c"/>
      <stop offset="55%" stop-color="#202020"/>
      <stop offset="100%" stop-color="#0a0a0a"/>
    </radialGradient>
    <radialGradient id="dsd-dome-on" cx="35%" cy="30%" r="65%">
      <stop offset="0%"  stop-color="#d8fbff"/>
      <stop offset="40%" stop-color="#5fe6ff"/>
      <stop offset="100%" stop-color="#0a3a48"/>
    </radialGradient>
    <radialGradient id="dsd-shadow" cx="50%" cy="50%" r="50%">
      <stop offset="0%"  stop-color="rgba(0,0,0,0.45)"/>
      <stop offset="100%" stop-color="rgba(0,0,0,0)"/>
    </radialGradient>
  </defs>
  <ellipse cx="0" cy="11" rx="58" ry="18" fill="url(#dsd-shadow)"/>
  <circle cx="0" cy="0" r="50" fill="url(#dsd-body)"/>
  <circle cx="0" cy="0" r="49.4" fill="none" stroke="rgba(255,255,255,0.18)" stroke-width="1.2"/>
  <circle data-on-only cx="0" cy="0" r="42" fill="none" stroke="#5fe6ff" stroke-width="2"
          style="filter: drop-shadow(0 0 4px #5fe6ff) drop-shadow(0 0 10px rgba(95,230,255,0.6));"/>
  <g data-toggle data-on-transform="translate(0,1.2)" data-off-transform="translate(0,0)">
    <circle cx="0" cy="0" r="34" fill="url(#dsd-dome-off)" data-off-only/>
    <circle cx="0" cy="0" r="34" fill="url(#dsd-dome-on)"  data-on-only
            style="filter: drop-shadow(0 0 6px rgba(95,230,255,0.7));"/>
    <ellipse cx="0" cy="-14" rx="22" ry="11" fill="rgba(255,255,255,0.18)"/>
  </g>
</svg>`,
    css: ``,
}))();

// ─────────────────────────── style: bakelite_flip ───────────────────────────
const bakeliteFlip = (() => ({
    label: "Bakelite Flip",
    svg: `
<svg viewBox="-70 -70 140 140" class="rs--bakelite_flip" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <radialGradient id="bf-plate" cx="50%" cy="40%" r="70%">
      <stop offset="0%"  stop-color="#6b3f24"/>
      <stop offset="55%" stop-color="#3d2113"/>
      <stop offset="100%" stop-color="#1a0a04"/>
    </radialGradient>
    <radialGradient id="bf-well" cx="50%" cy="50%" r="50%">
      <stop offset="0%"  stop-color="#0a0a0a"/>
      <stop offset="80%" stop-color="#1a0a05"/>
      <stop offset="100%" stop-color="#2a1108"/>
    </radialGradient>
    <linearGradient id="bf-lever" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%"  stop-color="#5a5a5a"/>
      <stop offset="40%" stop-color="#cfcfcf"/>
      <stop offset="60%" stop-color="#f4f4f4"/>
      <stop offset="100%" stop-color="#5a5a5a"/>
    </linearGradient>
    <radialGradient id="bf-tip" cx="35%" cy="30%" r="70%">
      <stop offset="0%"  stop-color="#f0f0f0"/>
      <stop offset="60%" stop-color="#a8a8a8"/>
      <stop offset="100%" stop-color="#3a3a3a"/>
    </radialGradient>
    <radialGradient id="bf-shadow" cx="50%" cy="50%" r="50%">
      <stop offset="0%"  stop-color="rgba(0,0,0,0.55)"/>
      <stop offset="100%" stop-color="rgba(0,0,0,0)"/>
    </radialGradient>
  </defs>
  <ellipse cx="0" cy="60" rx="48" ry="9" fill="url(#bf-shadow)"/>
  <rect x="-38" y="-58" width="76" height="116" rx="5" fill="url(#bf-plate)"/>
  <rect x="-38" y="-58" width="76" height="116" rx="5" fill="none" stroke="rgba(0,0,0,0.7)" stroke-width="0.8"/>
  <text x="0" y="-30" text-anchor="middle" font-family="ui-monospace,monospace" font-size="9" font-weight="700" fill="rgba(255,220,180,0.65)">ON</text>
  <text x="0" y="44"  text-anchor="middle" font-family="ui-monospace,monospace" font-size="9" font-weight="700" fill="rgba(255,220,180,0.65)">OFF</text>
  <circle cx="0" cy="0" r="14" fill="url(#bf-well)"/>
  <circle cx="0" cy="0" r="14" fill="none" stroke="rgba(0,0,0,0.85)" stroke-width="1"/>
  <circle cx="0" cy="0" r="13.2" fill="none" stroke="rgba(255,220,180,0.18)" stroke-width="0.6"/>
  <!-- Physical bat-handle: ON=up, OFF=down. Lever pivots around origin;
       OFF rotates 180° so the tip (drawn at y=-46) ends up at y=+46. -->
  <g data-toggle data-on-transform="rotate(0)" data-off-transform="rotate(180)">
    <rect x="-3" y="-44" width="6" height="44" fill="url(#bf-lever)" rx="1.5"/>
    <ellipse cx="0" cy="-46" rx="7" ry="5.5" fill="url(#bf-tip)" style="filter: drop-shadow(0 1px 2px rgba(0,0,0,0.65));"/>
    <ellipse cx="-1.5" cy="-47.5" rx="2.5" ry="1.6" fill="rgba(255,255,255,0.45)"/>
  </g>
</svg>`,
    css: ``,
}))();

// ─────────────────────────── style: silver_paddle ───────────────────────────
const silverPaddle = (() => {
    const radialURL = getRadialBrushedURL();
    return {
        label: "Silver Paddle",
        svg: `
<svg viewBox="-70 -70 140 140" class="rs--silver_paddle" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="sp-bezel" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%"  stop-color="#7a7a7a"/>
      <stop offset="20%" stop-color="#cfcfcf"/>
      <stop offset="50%" stop-color="#f4f4f4"/>
      <stop offset="80%" stop-color="#a8a8a8"/>
      <stop offset="100%" stop-color="#5a5a5a"/>
    </linearGradient>
    <linearGradient id="sp-paddle" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%"  stop-color="#3a3a3a"/>
      <stop offset="50%" stop-color="#1a1a1a"/>
      <stop offset="100%" stop-color="#0a0a0a"/>
    </linearGradient>
    <radialGradient id="sp-shadow" cx="50%" cy="50%" r="50%">
      <stop offset="0%"  stop-color="rgba(0,0,0,0.45)"/>
      <stop offset="100%" stop-color="rgba(0,0,0,0)"/>
    </radialGradient>
  </defs>
  <ellipse cx="0" cy="35" rx="58" ry="10" fill="url(#sp-shadow)"/>
  <rect x="-58" y="-30" width="116" height="60" rx="10" fill="url(#sp-bezel)"/>
  <rect x="-58" y="-30" width="116" height="60" rx="10" fill="none" stroke="rgba(0,0,0,0.55)" stroke-width="0.8"/>
  <rect x="-50" y="-22" width="100" height="44" rx="4" fill="#0e0e0e"/>
  <image href="${radialURL}" x="-50" y="-22" width="100" height="44" preserveAspectRatio="xMidYMid slice" opacity="0.18"/>
  <!-- Labels sit outside the paddle's ±28 translation range so the paddle
       never covers the lit indicator. Bases stay dim, overlays glow when
       their state is active. -->
  <text x="-44" y="3" text-anchor="middle" font-family="ui-monospace,monospace" font-size="10" font-weight="700"
        fill="rgba(220,220,220,0.35)">OFF</text>
  <text x="44" y="3"  text-anchor="middle" font-family="ui-monospace,monospace" font-size="10" font-weight="700"
        fill="rgba(220,220,220,0.35)">ON</text>
  <text x="-44" y="3" text-anchor="middle" font-family="ui-monospace,monospace" font-size="10" font-weight="700"
        fill="#ff3624" data-off-only style="filter: drop-shadow(0 0 4px #ff3624);">OFF</text>
  <text x="44" y="3"  text-anchor="middle" font-family="ui-monospace,monospace" font-size="10" font-weight="700"
        fill="#36ff5a" data-on-only style="filter: drop-shadow(0 0 4px #36ff5a);">ON</text>
  <!-- Physical paddle: points TO the active label. -->
  <g data-toggle data-on-transform="translate(28,0)" data-off-transform="translate(-28,0)">
    <rect x="-18" y="-18" width="36" height="36" rx="4" fill="url(#sp-paddle)" stroke="rgba(0,0,0,0.7)" stroke-width="0.8"/>
    <rect x="-15" y="-15" width="30" height="6" fill="rgba(255,255,255,0.18)"/>
    <line x1="-12" y1="-2" x2="12" y2="-2" stroke="rgba(255,255,255,0.10)" stroke-width="0.6"/>
    <line x1="-12" y1="2"  x2="12" y2="2"  stroke="rgba(0,0,0,0.45)" stroke-width="0.6"/>
  </g>
</svg>`,
        css: ``,
    };
})();

// ─────────────────────────── style: brass_slider ───────────────────────────
const brassSlider = (() => ({
    label: "Brass Slider",
    svg: `
<svg viewBox="-70 -70 140 140" class="rs--brass_slider" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="bs-plate" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%"  stop-color="#fde9a7"/>
      <stop offset="40%" stop-color="#d6a93a"/>
      <stop offset="80%" stop-color="#7c5410"/>
      <stop offset="100%" stop-color="#4a3208"/>
    </linearGradient>
    <linearGradient id="bs-track" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%"  stop-color="#1a0c02"/>
      <stop offset="50%" stop-color="#2a1604"/>
      <stop offset="100%" stop-color="#1a0c02"/>
    </linearGradient>
    <linearGradient id="bs-thumb" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%"  stop-color="#fde9a7"/>
      <stop offset="35%" stop-color="#d6a93a"/>
      <stop offset="100%" stop-color="#553809"/>
    </linearGradient>
    <pattern id="bs-knurl" patternUnits="userSpaceOnUse" width="3" height="3">
      <line x1="0" y1="0" x2="0" y2="3" stroke="rgba(0,0,0,0.55)" stroke-width="1"/>
    </pattern>
    <radialGradient id="bs-shadow" cx="50%" cy="50%" r="50%">
      <stop offset="0%"  stop-color="rgba(0,0,0,0.5)"/>
      <stop offset="100%" stop-color="rgba(0,0,0,0)"/>
    </radialGradient>
  </defs>
  <ellipse cx="0" cy="32" rx="58" ry="8" fill="url(#bs-shadow)"/>
  <rect x="-58" y="-25" width="116" height="50" rx="4" fill="url(#bs-plate)"/>
  <rect x="-58" y="-25" width="116" height="50" rx="4" fill="none" stroke="rgba(0,0,0,0.6)" stroke-width="0.8"/>
  <rect x="-44" y="-9"  width="88"  height="18" rx="3" fill="url(#bs-track)"/>
  <rect x="-44" y="-9"  width="88"  height="18" rx="3" fill="none" stroke="rgba(0,0,0,0.7)" stroke-width="0.6"/>
  <!-- Labels moved outside slider thumb ±28 range so text stays visible. -->
  <text x="-38"  y="3"  text-anchor="middle" font-family="ui-monospace,monospace" font-size="9" font-weight="700" fill="rgba(255,210,120,0.45)">OFF</text>
  <text x="38"   y="3"  text-anchor="middle" font-family="ui-monospace,monospace" font-size="9" font-weight="700" fill="rgba(255,210,120,0.45)">ON</text>
  <g data-toggle data-on-transform="translate(28,0)" data-off-transform="translate(-28,0)">
    <rect x="-12" y="-13" width="24" height="26" rx="3" fill="url(#bs-thumb)"/>
    <rect x="-12" y="-13" width="24" height="26" rx="3" fill="url(#bs-knurl)" opacity="0.65"/>
    <rect x="-12" y="-13" width="24" height="26" rx="3" fill="none" stroke="rgba(0,0,0,0.6)" stroke-width="0.7"/>
    <rect x="-10" y="-11" width="20" height="3"  fill="rgba(255,255,255,0.35)"/>
  </g>
</svg>`,
    css: ``,
}))();

// ─────────────────────────── style: minimal_pill ───────────────────────────
const minimalPill = (() => ({
    label: "Minimal Pill",
    svg: `
<svg viewBox="-70 -70 140 140" class="rs--minimal_pill" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="mp-bg-off" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%"  stop-color="#3a3c40"/>
      <stop offset="100%" stop-color="#26282b"/>
    </linearGradient>
    <linearGradient id="mp-bg-on" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%"  stop-color="#36c46a"/>
      <stop offset="100%" stop-color="#1f8c48"/>
    </linearGradient>
    <radialGradient id="mp-thumb" cx="35%" cy="30%" r="65%">
      <stop offset="0%"  stop-color="#ffffff"/>
      <stop offset="55%" stop-color="#e6e6e6"/>
      <stop offset="100%" stop-color="#bdbdbd"/>
    </radialGradient>
    <radialGradient id="mp-shadow" cx="50%" cy="50%" r="50%">
      <stop offset="0%"  stop-color="rgba(0,0,0,0.35)"/>
      <stop offset="100%" stop-color="rgba(0,0,0,0)"/>
    </radialGradient>
  </defs>
  <ellipse cx="0" cy="32" rx="48" ry="6" fill="url(#mp-shadow)"/>
  <rect data-off-only x="-50" y="-22" width="100" height="44" rx="22" fill="url(#mp-bg-off)"/>
  <rect data-on-only  x="-50" y="-22" width="100" height="44" rx="22" fill="url(#mp-bg-on)"
        style="filter: drop-shadow(0 0 6px rgba(54,196,106,0.5));"/>
  <rect x="-50" y="-22" width="100" height="44" rx="22" fill="none" stroke="rgba(0,0,0,0.45)" stroke-width="0.8"/>
  <g data-toggle data-on-transform="translate(26,0)" data-off-transform="translate(-26,0)">
    <circle cx="0" cy="0" r="17" fill="url(#mp-thumb)" style="filter: drop-shadow(0 2px 3px rgba(0,0,0,0.45));"/>
    <ellipse cx="-2" cy="-6" rx="9" ry="5" fill="rgba(255,255,255,0.35)"/>
  </g>
</svg>`,
    css: ``,
}))();

// ─────────────────────────── style: _template (copy this) ───────────────────────────
//
// HOW TO ADD A NEW SWITCH STYLE
// 1. Copy the IIFE block below.
// 2. Rename const (`myNewSwitch`) and registry key (`my_new_switch`).
// 3. Update `label` (shown in right-click menu).
// 4. Replace SVG body. Conventions:
//      - Root <svg viewBox="-70 -70 140 140"> with class "rs--<your_key>".
//      - Origin (0,0) is switch center.
//      - All <defs> ids prefixed unique short token (e.g. "mns-").
// 5. Mark interactive elements with magic data-attributes:
//      - data-toggle  : element whose transform attribute is set per state.
//                       Provide data-on-transform="..." and data-off-transform="..."
//      - data-on-only : visible only when state == true.
//      - data-off-only: visible only when state == false.
// 6. Add entry to SWITCH_STYLES registry.
//
// MINIMAL TEMPLATE — uncomment and customize:
//
// const myNewSwitch = (() => ({
//     label: "My New Switch",
//
//     svg: `
// <svg viewBox="-70 -70 140 140" class="rs--my_new_switch" xmlns="http://www.w3.org/2000/svg">
//   <defs>
//     <linearGradient id="mns-bg" x1="0" y1="0" x2="0" y2="1">
//       <stop offset="0%"  stop-color="#444"/>
//       <stop offset="100%" stop-color="#222"/>
//     </linearGradient>
//   </defs>
//
//   <!-- bezel -->
//   <rect x="-50" y="-20" width="100" height="40" rx="8" fill="url(#mns-bg)"/>
//
//   <!-- toggle thumb — JS sets transform to either translate(20,0) or translate(-20,0) -->
//   <g data-toggle data-on-transform="translate(20,0)" data-off-transform="translate(-20,0)">
//     <circle cx="0" cy="0" r="14" fill="#fff"/>
//   </g>
//
//   <!-- on-only highlight -->
//   <circle data-on-only  cx="0" cy="0" r="48" fill="none" stroke="#5fe6ff" stroke-width="2"/>
// </svg>`,
//
//     css: ``,
// }))();
//
// Then register below:
//   my_new_switch: myNewSwitch,
//

// ─────────────────────────── registry ───────────────────────────

export const SWITCH_STYLES = {
    chrome_rocker:     chromeRocker,
    dark_studio_dome:  darkStudioDome,
    bakelite_flip:     bakeliteFlip,
    silver_paddle:     silverPaddle,
    brass_slider:      brassSlider,
    minimal_pill:      minimalPill,
    // my_new_switch: myNewSwitch,
};

export const DEFAULT_SWITCH_STYLE = "chrome_rocker";

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
