// knob_styles.js — Ray's Knob style registry (SVG + CSS sidecar)
// Each style entry:  { label, svg, css }
//   svg : string injected as innerHTML of the knob wrapper.
//          Must contain a single <svg> root with viewBox = "-70 -70 140 140".
//   css : string of CSS rules. Scope your selectors under .rk--<key> so styles don't collide.
//
// Magic data-attributes the runtime understands:
//   data-rotate         → element's transform is set to rotate(<angle>deg) on drag.
//   data-arc            → element is treated as an LED arc; stroke-dasharray set from value frac.
//                         Element MUST be a <circle> with stroke + pathLength="100".
//                         Optional: data-arc-direction="cw"|"ccw" (default cw).
//   data-readout        → textContent set to "<float>  →  <int>" each render.
//
// To add a style: append an entry to KNOB_STYLES below. No edits required to ray_knob.js.

import { TWO_PI, getRadialBrushedURL } from "./_common.js";

// ─────────────────────────── helpers (SVG fragment builders) ───────────────────────────

function tickRing(count, r, len, color, width, startAngle = -Math.PI / 2) {
    let s = "";
    for (let i = 0; i < count; i++) {
        const a = startAngle + (i / count) * TWO_PI;
        const x1 = Math.cos(a) * r,         y1 = Math.sin(a) * r;
        const x2 = Math.cos(a) * (r + len), y2 = Math.sin(a) * (r + len);
        s += `<line x1="${x1.toFixed(2)}" y1="${y1.toFixed(2)}" x2="${x2.toFixed(2)}" y2="${y2.toFixed(2)}" stroke="${color}" stroke-width="${width}" stroke-linecap="round"/>`;
    }
    return s;
}

function dotRing(count, r, dotR, color, startAngle = -Math.PI / 2) {
    let s = "";
    for (let i = 0; i < count; i++) {
        const a = startAngle + (i / count) * TWO_PI;
        const x = Math.cos(a) * r, y = Math.sin(a) * r;
        s += `<circle cx="${x.toFixed(2)}" cy="${y.toFixed(2)}" r="${dotR}" fill="${color}"/>`;
    }
    return s;
}

function notchWedges(count, outerR, innerR, halfAngle, fill) {
    let d = "";
    for (let i = 0; i < count; i++) {
        const a = (i / count) * TWO_PI - Math.PI / 2;
        const x1 = Math.cos(a - halfAngle) * outerR, y1 = Math.sin(a - halfAngle) * outerR;
        const x2 = Math.cos(a + halfAngle) * outerR, y2 = Math.sin(a + halfAngle) * outerR;
        const x3 = Math.cos(a + halfAngle) * innerR, y3 = Math.sin(a + halfAngle) * innerR;
        const x4 = Math.cos(a - halfAngle) * innerR, y4 = Math.sin(a - halfAngle) * innerR;
        d += `M${x1.toFixed(2)},${y1.toFixed(2)} A${outerR},${outerR} 0 0 1 ${x2.toFixed(2)},${y2.toFixed(2)} L${x3.toFixed(2)},${y3.toFixed(2)} A${innerR},${innerR} 0 0 0 ${x4.toFixed(2)},${y4.toFixed(2)} Z `;
    }
    return `<path d="${d}" fill="${fill}"/>`;
}

function scallopedPath(lobes, baseR, amp, segs = 240) {
    let d = "";
    for (let i = 0; i <= segs; i++) {
        const a = (i / segs) * TWO_PI - Math.PI / 2;
        const rad = baseR + Math.cos(a * lobes) * amp;
        const x = Math.cos(a) * rad, y = Math.sin(a) * rad;
        d += (i === 0 ? "M" : "L") + x.toFixed(2) + "," + y.toFixed(2) + " ";
    }
    return d + "Z";
}

// ─────────────────────────── pre-baked textures (canvas → data URL) ───────────────────────────

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

// ─────────────────────────── shared SVG defs ───────────────────────────
// These are unique-per-style to avoid id collisions when multiple styles are inspected at once.
// (Each style declares its own <defs> with style-prefixed ids.)

// ─────────────────────────── style: chrome_notched ───────────────────────────
const chromeNotched = (() => {
    const ticks = tickRing(12, 60, 6, "#222", 1.6);
    const notches = notchWedges(16, 47, 38, 0.075, "rgba(0,0,0,0.7)");
    const radialURL = getRadialBrushedURL();
    return {
        label: "Chrome Notched",
        svg: `
<svg viewBox="-70 -70 140 140" class="rk--chrome_notched" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <radialGradient id="cn-shadow" cx="50%" cy="50%" r="50%">
      <stop offset="0%"  stop-color="rgba(0,0,0,0.55)"/>
      <stop offset="100%" stop-color="rgba(0,0,0,0)"/>
    </radialGradient>
    <linearGradient id="cn-cyl" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%"  stop-color="#2c2c2c"/>
      <stop offset="12%" stop-color="#6a6a6a"/>
      <stop offset="32%" stop-color="#cdcdcd"/>
      <stop offset="50%" stop-color="#f4f4f4"/>
      <stop offset="68%" stop-color="#cdcdcd"/>
      <stop offset="88%" stop-color="#6a6a6a"/>
      <stop offset="100%" stop-color="#2c2c2c"/>
    </linearGradient>
  </defs>
  <ellipse class="rk-shadow" cx="0" cy="11" rx="62" ry="20" fill="url(#cn-shadow)"/>
  <circle  class="rk-rim"   cx="0" cy="0" r="50" fill="url(#cn-cyl)"/>
  <circle  class="rk-bevel" cx="0" cy="0" r="46" fill="none" stroke="rgba(0,0,0,0.5)" stroke-width="1"/>
  ${notches}
  <circle class="rk-inner-clip-host" cx="0" cy="0" r="33" fill="#bdbdbd"/>
  <image class="rk-inner-tex" href="${radialURL}" x="-33" y="-33" width="66" height="66" clip-path="circle(33px at 33px 33px)" preserveAspectRatio="xMidYMid slice"/>
  <circle cx="0" cy="0" r="33" fill="none" stroke="rgba(0,0,0,0.45)" stroke-width="0.8"/>
  <ellipse cx="0" cy="-15" rx="26" ry="12" fill="rgba(255,255,255,0.18)"/>
  <line data-rotate class="rk-pointer" x1="3" y1="0" x2="30" y2="0" stroke="#fafafa" stroke-width="2.6" stroke-linecap="round" style="filter: drop-shadow(0 0 1px rgba(0,0,0,0.5));"/>
  ${ticks}
</svg>`,
        css: ``,
    };
})();

// ─────────────────────────── style: dark_studio_led ───────────────────────────
const darkStudioLED = (() => {
    const dots = dotRing(20, 61, 1.5, "#1a1a1a");
    return {
        label: "Dark Studio LED",
        svg: `
<svg viewBox="-70 -70 140 140" class="rk--dark_studio_led" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <radialGradient id="dsl-shadow" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="rgba(0,0,0,0.45)"/>
      <stop offset="100%" stop-color="rgba(0,0,0,0)"/>
    </radialGradient>
    <radialGradient id="dsl-body" cx="35%" cy="30%" r="65%">
      <stop offset="0%"  stop-color="#2a2a2a"/>
      <stop offset="55%" stop-color="#161616"/>
      <stop offset="100%" stop-color="#070707"/>
    </radialGradient>
    <filter id="dsl-glow" x="-30%" y="-30%" width="160%" height="160%">
      <feGaussianBlur stdDeviation="1.4"/>
    </filter>
  </defs>
  <ellipse cx="0" cy="11" rx="58" ry="18" fill="url(#dsl-shadow)"/>
  ${dots}
  <circle cx="0" cy="0" r="50" fill="url(#dsl-body)"/>
  <circle cx="0" cy="0" r="49.4" fill="none" stroke="rgba(255,255,255,0.18)" stroke-width="1.2"/>
  <ellipse cx="0" cy="-22" rx="32" ry="16" fill="rgba(255,255,255,0.10)"/>

  <!-- LED arc: full circle, stroke-dasharray driven by JS via [data-arc] -->
  <circle data-arc cx="0" cy="0" r="52" pathLength="100"
          fill="none" stroke="#5fe6ff" stroke-width="2" stroke-linecap="round"
          stroke-dasharray="0 100" stroke-dashoffset="0"
          transform="rotate(-90)"
          style="filter: drop-shadow(0 0 3px #5fe6ff) drop-shadow(0 0 6px rgba(95,230,255,0.6));"/>

  <!-- pointer triangle near disc edge -->
  <g data-rotate>
    <polygon points="46,0 30,-1.6 30,1.6" fill="#e8e8e8" style="filter: drop-shadow(0 0 1px rgba(0,0,0,0.6));"/>
  </g>
</svg>`,
        css: ``,
    };
})();

// ─────────────────────────── style: bakelite_chickenhead ───────────────────────────
const bakeliteChickenhead = (() => {
    const lobes = scallopedPath(12, 45, 5);
    return {
        label: "Bakelite Chickenhead",
        svg: `
<svg viewBox="-70 -70 140 140" class="rk--bakelite_chickenhead" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <radialGradient id="bk-shadow" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="rgba(0,0,0,0.55)"/>
      <stop offset="100%" stop-color="rgba(0,0,0,0)"/>
    </radialGradient>
    <radialGradient id="bk-body" cx="38%" cy="30%" r="70%">
      <stop offset="0%"  stop-color="#6b3f24"/>
      <stop offset="45%" stop-color="#3d2113"/>
      <stop offset="85%" stop-color="#241008"/>
      <stop offset="100%" stop-color="#160803"/>
    </radialGradient>
    <radialGradient id="bk-dome" cx="35%" cy="30%" r="65%">
      <stop offset="0%"  stop-color="#7a4a2d"/>
      <stop offset="55%" stop-color="#46251a"/>
      <stop offset="100%" stop-color="#2a1108"/>
    </radialGradient>
    <radialGradient id="bk-spec" cx="30%" cy="25%" r="50%">
      <stop offset="0%"  stop-color="rgba(255,220,180,0.55)"/>
      <stop offset="100%" stop-color="rgba(255,220,180,0)"/>
    </radialGradient>
    <linearGradient id="bk-needle" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%"  stop-color="#c9bfa6"/>
      <stop offset="50%" stop-color="#f0e8cf"/>
      <stop offset="100%" stop-color="#d8cfb4"/>
    </linearGradient>
  </defs>
  <ellipse cx="0" cy="11" rx="60" ry="18" fill="url(#bk-shadow)"/>
  <path d="${lobes}" fill="url(#bk-body)"/>
  <circle cx="0" cy="0" r="31" fill="url(#bk-dome)"/>
  <circle cx="0" cy="0" r="31" fill="url(#bk-spec)"/>
  <g data-rotate>
    <path d="M52,0 Q28,-5 2.5,-2.5 L2.5,2.5 Q28,5 52,0 Z" fill="url(#bk-needle)" style="filter: drop-shadow(0 1px 1.5px rgba(0,0,0,0.55));"/>
  </g>
  <text x="-65" y="38" font-family="ui-monospace,monospace" font-size="10" font-weight="700" fill="#3a3a3a" text-anchor="middle">L</text>
  <text x="65"  y="38" font-family="ui-monospace,monospace" font-size="10" font-weight="700" fill="#3a3a3a" text-anchor="middle">R</text>
</svg>`,
        css: ``,
    };
})();

// ─────────────────────────── style: silver_skirted ───────────────────────────
const silverSkirted = (() => {
    const ticks = tickRing(12, 58, 5, "#2a2a2a", 1.4);
    return {
        label: "Silver Skirted",
        svg: `
<svg viewBox="-70 -70 140 140" class="rk--silver_skirted" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <radialGradient id="ss-shadow" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="rgba(0,0,0,0.45)"/>
      <stop offset="100%" stop-color="rgba(0,0,0,0)"/>
    </radialGradient>
    <linearGradient id="ss-skirt" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%"  stop-color="#7a7a7a"/>
      <stop offset="20%" stop-color="#b5b5b5"/>
      <stop offset="50%" stop-color="#e8e8e8"/>
      <stop offset="80%" stop-color="#b5b5b5"/>
      <stop offset="100%" stop-color="#6e6e6e"/>
    </linearGradient>
    <radialGradient id="ss-cap" cx="35%" cy="30%" r="65%">
      <stop offset="0%"  stop-color="#f6f6f6"/>
      <stop offset="55%" stop-color="#cfcfcf"/>
      <stop offset="100%" stop-color="#888888"/>
    </radialGradient>
  </defs>
  <ellipse cx="0" cy="11" rx="60" ry="18" fill="url(#ss-shadow)"/>
  <circle cx="0" cy="0" r="50" fill="url(#ss-skirt)"/>
  <circle cx="0" cy="0" r="34" fill="none" stroke="rgba(0,0,0,0.55)" stroke-width="1.4"/>
  <circle cx="0" cy="0" r="32.5" fill="none" stroke="rgba(255,255,255,0.35)" stroke-width="0.8"/>
  <circle cx="0" cy="0" r="33" fill="url(#ss-cap)"/>
  <ellipse cx="0" cy="-14" rx="22" ry="11" fill="rgba(255,255,255,0.25)"/>
  <g data-rotate>
    <rect x="6" y="-0.9" width="22" height="1.8" fill="#202020"/>
  </g>
  ${ticks}
</svg>`,
        css: ``,
    };
})();

// ─────────────────────────── style: knurled_brass ───────────────────────────
const knurledBrass = (() => {
    const dots = dotRing(24, 61, 1.8, "#202020");
    return {
        label: "Knurled Brass",
        svg: `
<svg viewBox="-70 -70 140 140" class="rk--knurled_brass" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <radialGradient id="kb-shadow" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="rgba(0,0,0,0.55)"/>
      <stop offset="100%" stop-color="rgba(0,0,0,0)"/>
    </radialGradient>
    <linearGradient id="kb-knurl" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%"  stop-color="#5a3f12"/>
      <stop offset="30%" stop-color="#a8801f"/>
      <stop offset="55%" stop-color="#d4a936"/>
      <stop offset="80%" stop-color="#a8801f"/>
      <stop offset="100%" stop-color="#5a3f12"/>
    </linearGradient>
    <radialGradient id="kb-top" cx="38%" cy="30%" r="65%">
      <stop offset="0%"  stop-color="#fde9a7"/>
      <stop offset="45%" stop-color="#d6a93a"/>
      <stop offset="85%" stop-color="#7c5410"/>
      <stop offset="100%" stop-color="#553809"/>
    </radialGradient>
    <pattern id="kb-knurl-x1" patternUnits="userSpaceOnUse" width="3" height="3" patternTransform="rotate(45)">
      <line x1="0" y1="0" x2="0" y2="3" stroke="rgba(0,0,0,0.55)" stroke-width="1"/>
    </pattern>
    <pattern id="kb-knurl-x2" patternUnits="userSpaceOnUse" width="3" height="3" patternTransform="rotate(-45)">
      <line x1="0" y1="0" x2="0" y2="3" stroke="rgba(0,0,0,0.4)" stroke-width="1"/>
    </pattern>
    <mask id="kb-band-mask">
      <rect x="-70" y="-70" width="140" height="140" fill="black"/>
      <circle cx="0" cy="0" r="50" fill="white"/>
      <circle cx="0" cy="0" r="42" fill="black"/>
    </mask>
  </defs>
  <ellipse cx="0" cy="11" rx="60" ry="18" fill="url(#kb-shadow)"/>
  ${dots}
  <circle cx="0" cy="0" r="50" fill="url(#kb-knurl)"/>
  <rect x="-50" y="-50" width="100" height="100" fill="url(#kb-knurl-x1)" mask="url(#kb-band-mask)"/>
  <rect x="-50" y="-50" width="100" height="100" fill="url(#kb-knurl-x2)" mask="url(#kb-band-mask)"/>
  <circle cx="0" cy="0" r="42" fill="url(#kb-top)"/>
  <circle cx="0" cy="0" r="42" fill="none" stroke="rgba(0,0,0,0.45)" stroke-width="0.9"/>
  <ellipse cx="0" cy="-19" rx="28" ry="14" fill="rgba(255,255,255,0.25)"/>
  <g data-rotate>
    <circle cx="35" cy="0" r="2.6" fill="#d8261c" style="filter: drop-shadow(0 0 1px rgba(0,0,0,0.7));"/>
    <circle cx="34.4" cy="-0.6" r="0.9" fill="rgba(255,255,255,0.55)"/>
  </g>
</svg>`,
        css: ``,
    };
})();

// ─────────────────────────── style: minimal_flat ───────────────────────────
const minimalFlat = (() => {
    const ticks = tickRing(12, 58, 4, "rgba(170,175,180,0.55)", 1.2);
    return {
        label: "Minimal Flat",
        svg: `
<svg viewBox="-70 -70 140 140" class="rk--minimal_flat" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <radialGradient id="mf-shadow" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="rgba(0,0,0,0.25)"/>
      <stop offset="100%" stop-color="rgba(0,0,0,0)"/>
    </radialGradient>
    <linearGradient id="mf-body" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%"  stop-color="#3a3c40"/>
      <stop offset="50%" stop-color="#2e3034"/>
      <stop offset="100%" stop-color="#26282b"/>
    </linearGradient>
  </defs>
  <ellipse cx="0" cy="9" rx="55" ry="14" fill="url(#mf-shadow)"/>
  <circle cx="0" cy="0" r="50" fill="url(#mf-body)"/>
  <circle cx="0" cy="0" r="49.5" fill="none" stroke="rgba(255,255,255,0.06)" stroke-width="1"/>
  <line data-rotate x1="9" y1="0" x2="43" y2="0" stroke="#cfd2d6" stroke-width="1.8" stroke-linecap="round"/>
  ${ticks}
</svg>`,
        css: ``,
    };
})();

// ─────────────────────────── style: _template (copy this) ───────────────────────────
//
// HOW TO ADD A NEW KNOB STYLE
// 1. Copy the IIFE block below.
// 2. Rename the const (`myNewKnob`) and the registry key (`my_new_knob`).
// 3. Update `label` (shown in right-click menu).
// 4. Replace the SVG body with your design. Keep these conventions:
//      - Root <svg viewBox="-70 -70 140 140"> (knob radius ≤ 50, margin for ticks/shadow).
//      - Root class "rk--<your_key>" so any per-style CSS scopes cleanly.
//      - Coordinate origin (0,0) is the knob center.
//      - All <defs> ids must be prefixed with a unique short token (e.g. "mn-")
//        so they don't collide with other styles' ids.
// 5. Mark interactive elements with magic data-attributes:
//      - data-rotate  : element rotates around (0,0) per current value.
//                       Use SVG attribute transform — JS sets it via setAttribute.
//                       Wrap multi-element pointers in <g data-rotate>...</g>.
//      - data-arc     : <circle> whose stroke-dasharray is driven by revolution fraction.
//                       Must have pathLength="100", a stroke, and stroke-dasharray="0 100"
//                       as starting value. Add transform="rotate(-90)" so 0% sits at top.
//      - data-readout : (optional) textContent set to "<float>  →  <int>" each render.
//                       If absent, the wrapper's own readout div is used instead.
// 6. Optional `css` string: any per-style CSS rules. Scope under .rk--<your_key>.
// 7. Add the entry to KNOB_STYLES registry below. That's it — no ray_knob.js edits.
//
// MINIMAL TEMPLATE — uncomment and customize:
//
// const myNewKnob = (() => {
//     // pre-compute static SVG fragments outside the template string for cleanliness
//     const ticks = tickRing(/*count*/ 12, /*r*/ 58, /*len*/ 5, /*color*/ "#222", /*width*/ 1.4);
//     // const dots = dotRing(20, 60, 1.5, "#1a1a1a");
//     // const wedges = notchWedges(16, 47, 38, 0.075, "rgba(0,0,0,0.7)");
//     // const lobes  = scallopedPath(12, 45, 5);  // returns a path "d" string
//
//     return {
//         label: "My New Knob",  // shown in right-click "Knob Style" submenu
//
//         svg: `
// <svg viewBox="-70 -70 140 140" class="rk--my_new_knob" xmlns="http://www.w3.org/2000/svg">
//   <defs>
//     <!-- Prefix every id with a unique tag, e.g. "mn-" for my_new_knob -->
//     <radialGradient id="mn-body" cx="40%" cy="30%" r="65%">
//       <stop offset="0%"   stop-color="#888"/>
//       <stop offset="100%" stop-color="#222"/>
//     </radialGradient>
//   </defs>
//
//   <!-- soft drop shadow -->
//   <ellipse cx="0" cy="10" rx="58" ry="16" fill="rgba(0,0,0,0.45)"/>
//
//   <!-- knob body -->
//   <circle cx="0" cy="0" r="50" fill="url(#mn-body)"/>
//
//   <!-- pointer line — rotated by JS around (0,0) -->
//   <g data-rotate>
//     <line x1="10" y1="0" x2="44" y2="0" stroke="#fafafa" stroke-width="2" stroke-linecap="round"/>
//   </g>
//
//   <!-- optional progress arc — JS sets stroke-dasharray to "<frac*100> 100" -->
//   <!--
//   <circle data-arc cx="0" cy="0" r="52" pathLength="100"
//           fill="none" stroke="#5fe6ff" stroke-width="2" stroke-linecap="round"
//           stroke-dasharray="0 100" transform="rotate(-90)"/>
//   -->
//
//   <!-- ticks built by helper -->
//   ${"${ticks}"}
// </svg>`,
//
//         css: `
// /* per-style overrides scoped to .rk--my_new_knob — usually empty */
// `,
//     };
// })();
//
// Then register below:
//
//   my_new_knob: myNewKnob,
//

// ─────────────────────────── registry ───────────────────────────

export const KNOB_STYLES = {
    chrome_notched:       chromeNotched,
    dark_studio_led:      darkStudioLED,
    bakelite_chickenhead: bakeliteChickenhead,
    silver_skirted:       silverSkirted,
    knurled_brass:        knurledBrass,
    minimal_flat:         minimalFlat,
    // my_new_knob:       myNewKnob,
};

export const DEFAULT_STYLE = "chrome_notched";

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
