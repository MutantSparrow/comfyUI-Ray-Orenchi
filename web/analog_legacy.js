// Original theme IDs and control axes are preserved. All art is local SVG.
const materials = `<defs>
  <linearGradient id="chrome" x1="0" y1="0" x2=".85" y2="1">
    <stop stop-color="#eaede7"/><stop offset=".19" stop-color="#a7afad"/>
    <stop offset=".4" stop-color="#424e51"/><stop offset=".61" stop-color="#c0c6bf"/>
    <stop offset=".83" stop-color="#727e7c"/><stop offset="1" stop-color="#303b3e"/>
  </linearGradient>
  <radialGradient id="aluminium" cx=".3" cy=".23" r=".85">
    <stop stop-color="#e4e7de"/><stop offset=".42" stop-color="#b5bdb7"/>
    <stop offset=".8" stop-color="#8a9692"/><stop offset="1" stop-color="#a9b1aa"/>
  </radialGradient>
  <radialGradient id="graphite" cx=".3" cy=".2" r=".9">
    <stop stop-color="#414a4c"/><stop offset=".5" stop-color="#242c2f"/>
    <stop offset="1" stop-color="#10191c"/>
  </radialGradient>
  <linearGradient id="bakelite" x1="0" y1="0" x2=".65" y2="1">
    <stop stop-color="#685145"/><stop offset=".3" stop-color="#45322a"/>
    <stop offset=".72" stop-color="#2b201c"/><stop offset="1" stop-color="#181716"/>
  </linearGradient>
  <linearGradient id="brass" x1="0" y1="0" x2=".75" y2="1">
    <stop stop-color="#d3c299"/><stop offset=".24" stop-color="#b6a06f"/>
    <stop offset=".5" stop-color="#8b784e"/><stop offset=".72" stop-color="#baa879"/>
    <stop offset="1" stop-color="#665b3e"/>
  </linearGradient>
  <radialGradient id="brass-face" cx=".3" cy=".22" r=".85">
    <stop stop-color="#ddd0a6"/><stop offset=".5" stop-color="#b6a475"/>
    <stop offset="1" stop-color="#887749"/>
  </radialGradient>
  <linearGradient id="ivory" x1="0" y1="0" x2=".5" y2="1">
    <stop stop-color="#eee8d1"/><stop offset=".5" stop-color="#c9c5af"/>
    <stop offset="1" stop-color="#858877"/>
  </linearGradient>
  <linearGradient id="red-lens" x1="0" y1="0" x2="0" y2="1">
    <stop stop-color="#f9b38e"/><stop offset=".3" stop-color="#c36b49"/>
    <stop offset="1" stop-color="#723422"/>
  </linearGradient>
  <pattern id="knurl" patternUnits="userSpaceOnUse" width="4" height="4">
    <path d="M0 0L4 4M4 0L0 4" stroke="#373c30" stroke-opacity=".45" stroke-width=".65"/>
    <path d="M1 0L4 3" stroke="#ede0b4" stroke-opacity=".3" stroke-width=".45"/>
  </pattern>
  <mask id="knurl-band" maskUnits="userSpaceOnUse" x="-40" y="-40" width="80" height="80">
    <circle r="37" fill="white"/><circle r="29" fill="black"/>
  </mask>
</defs>`;

function face(key, body, kind = "rk") {
    return `<svg viewBox="-70 -70 140 140" class="${kind}--${key}" xmlns="http://www.w3.org/2000/svg">${materials}${body}</svg>`;
}

// Full-turn marks retain the original knob revolution behavior (zero at right).
function ticks(color = "#c4cbbd", count = 40) {
    return Array.from({ length: count }, (_, i) =>
        `<path d="M${i % 5 === 0 ? 46 : 50} 0H54" stroke="${color}" stroke-width="${i % 5 === 0 ? 1.2 : .6}" transform="rotate(${i * 360 / count})"/>`).join("");
}

function machining(radii, color = "#3f5049") {
    return radii.map(r => `<circle r="${r}" fill="none" stroke="${color}" stroke-width=".35" stroke-opacity=".2"/>`).join("");
}

function grips(count, radius, color = "#10191b") {
    return Array.from({ length: count }, (_, i) =>
        `<path d="M${radius - 5} -.8H${radius}" stroke="${color}" stroke-width="1.6" transform="rotate(${i * 360 / count})"/>
         <path d="M${radius - 5} .8H${radius}" stroke="#eef0dc" stroke-opacity=".22" stroke-width=".55" transform="rotate(${i * 360 / count})"/>`).join("");
}

const seat = `<ellipse cx="1.5" cy="4" rx="40" ry="41" fill="#000" opacity=".22"/>
    <circle r="39" fill="#192124" stroke="#8d9990" stroke-opacity=".25"/>`;
const index = `<g data-rotate><path d="M17 0H34" stroke="#0e1719" stroke-width="4"/>
    <path d="M18 -.2H34" stroke="#e8e4ca" stroke-width="2" stroke-linecap="round"/></g>`;

export const LEGACY_KNOBS = {
    chrome_notched: {
        label: "Chrome Notched", panel: "silver",
        svg: face("chrome_notched", `${ticks("#34413c")}${seat}
          <circle r="37" fill="url(#chrome)"/>${grips(24, 36)}
          <circle r="29" fill="#394944"/><circle cy="-.5" r="27.5" fill="url(#aluminium)"/>
          ${machining([8, 12, 16, 20, 24, 26])}${index}`),
    },
    dark_studio_led: {
        label: "Dark Studio LED", panel: "charcoal",
        svg: face("dark_studio_led", `${ticks("#81958e")}${seat}
          <circle r="43" fill="none" stroke="#101b1e" stroke-width="3"/>
          <circle data-arc r="43" pathLength="100" fill="none" stroke="#91c9bd" stroke-width="1.8" stroke-dasharray="0 100"/>
          <circle r="36" fill="url(#chrome)"/><circle r="34.5" fill="url(#graphite)"/>
          ${grips(44, 34, "#11191b")}<circle r="28" fill="url(#graphite)" stroke="#657470" stroke-opacity=".35" stroke-width=".6"/>
          <circle r="25" fill="none" stroke="#0a171c" stroke-width=".6"/>
          <g data-rotate><path d="M20 0H33" stroke="#a6d5c4" stroke-width="2.2" stroke-linecap="round"/></g>`),
    },
    bakelite_chickenhead: {
        label: "Bakelite Chickenhead", panel: "olive",
        svg: face("bakelite_chickenhead", `${ticks("#3e4535", 32)}${seat}
          <circle r="35" fill="url(#bakelite)"/><circle r="32" fill="none" stroke="#c4a880" stroke-opacity=".15"/>
          <g data-rotate>
            <path d="M-24 -11Q-28 0-24 11L-4 18Q7 20 17 9L36 3Q40 0 36-3L17-9Q7-20-4-18Z" fill="#060c0c" opacity=".35" transform="translate(1.5,2)"/>
            <path d="M-24 -11Q-28 0-24 11L-4 18Q7 20 17 9L36 3Q40 0 36-3L17-9Q7-20-4-18Z" fill="url(#bakelite)" stroke="#1c211c"/>
            <path d="M-22-9L-5-15Q6-17 15-8L32-2" fill="none" stroke="#cdb391" stroke-opacity=".4" stroke-width=".8"/>
            <path d="M13 0H34" stroke="#ded1ad" stroke-width="2" stroke-linecap="round"/>
            <circle cx="-12" r="3" fill="#231e18" stroke="#846b4e" stroke-width=".6"/>
            <path d="M-14 0H-10" stroke="#a39478" stroke-width=".7"/>
          </g>`),
    },
    silver_skirted: {
        label: "Silver Skirted", panel: "silver",
        svg: face("silver_skirted", `${ticks("#3f4b42", 32)}${seat}
          <circle r="38" fill="url(#chrome)"/><circle r="35" fill="url(#aluminium)"/>
          ${machining([30, 32, 34])}<circle r="27" fill="#253533"/>
          <circle r="25.5" fill="url(#chrome)"/><circle cy="-.7" r="23" fill="url(#aluminium)"/>
          ${machining([7, 11, 15, 19, 21])}
          <g data-rotate><path d="M15 0H35" stroke="#34433c" stroke-width="2"/>
          <path d="M27-2V2" stroke="#e8e7d8" stroke-width=".6"/></g>`),
    },
    knurled_brass: {
        label: "Knurled Brass", panel: "olive",
        svg: face("knurled_brass", `${ticks("#3e4535")}${seat}
          <circle r="37" fill="url(#brass)"/>
          <rect x="-38" y="-38" width="76" height="76" fill="url(#knurl)" mask="url(#knurl-band)"/>
          <circle r="29" fill="#59563d"/><circle r="27.5" fill="url(#brass-face)"/>
          ${machining([9, 13, 17, 21, 25], "#64583b")}
          <g data-rotate><circle cx="23" r="3.1" fill="#554a33"/>
          <circle cx="23" r="2.3" fill="#ae5942"/><circle cx="22.4" cy="-.6" r=".7" fill="#e8b88c"/>
          <path d="M29 0H34" stroke="#e6d1a0" stroke-width="1.4"/></g>`),
    },
    minimal_flat: {
        label: "Minimal Flat", panel: "charcoal",
        svg: face("minimal_flat", `${ticks("#abb9ad", 24)}${seat}
          <circle r="36" fill="#66736e"/><circle cy=".6" r="35" fill="url(#graphite)"/>
          <circle r="32" fill="none" stroke="#0d171a" stroke-opacity=".45" stroke-width=".5"/>
          <g data-rotate><path d="M18 0H33" stroke="#e1e4cf" stroke-width="1.8" stroke-linecap="round"/></g>`),
    },
};

function screw(x, y, color = "url(#chrome)") {
    return `<g transform="translate(${x},${y})"><circle cy=".6" r="2.8" fill="#000" opacity=".35"/>
      <circle r="2.3" fill="${color}" stroke="#2d3933" stroke-width=".4"/>
      <path d="M-1.4 .7L1.4-.7" stroke="#313b34" stroke-width=".7"/></g>`;
}

function label(x, y, text, color = "#cad0bd", state = "") {
    return `<text ${state ? `data-${state}-only` : ""} x="${x}" y="${y}" text-anchor="middle" font-family="monospace" font-size="7" letter-spacing="1" fill="${color}">${text}</text>`;
}

function slideLabels(color) {
    return `${label(-28, -32, "OFF", color)}${label(28, -32, "ON", color)}
      <circle cx="-28" cy="28" r="2" fill="#1d2925"/><circle cx="28" cy="28" r="2" fill="#1d2925"/>
      <circle data-off-only cx="-28" cy="28" r="1.3" fill="#c99064"/>
      <circle data-on-only cx="28" cy="28" r="1.3" fill="#9dbb81"/>`;
}

export const LEGACY_SWITCHES = {
    chrome_rocker: {
        label: "Chrome Rocker", panel: "silver",
        svg: face("chrome_rocker", `
          <rect x="-29" y="-46" width="60" height="98" rx="4" fill="#000" opacity=".22"/>
          <rect x="-30" y="-49" width="60" height="98" rx="3" fill="url(#chrome)"/>
          <rect x="-26" y="-45" width="52" height="90" rx="2" fill="#111c1d"/>
          ${screw(0,-55)}${screw(0,55)}
          <g data-toggle data-on-transform="translate(0,1)" data-off-transform="translate(0,-1)">
            <rect x="-23" y="-40" width="46" height="80" rx="2" fill="url(#graphite)" stroke="#4f5c57" stroke-width=".6"/>
            <path data-off-only d="M-20-36H20" stroke="#98a49a" stroke-width="2"/>
            <path data-on-only d="M-20 36H20" stroke="#98a49a" stroke-width="2"/>
            <path data-on-only d="M-21-38H21" stroke="#050d10" stroke-width="3"/>
            <path data-off-only d="M-21 38H21" stroke="#050d10" stroke-width="3"/>
            <rect x="-11" y="-26" width="22" height="8" rx="1" fill="#161810" stroke="#060e10"/>
            <rect data-on-only x="-10" y="-25" width="20" height="6" rx=".8" fill="url(#red-lens)"/>
            <rect data-off-only x="-10" y="-25" width="20" height="6" rx=".8" fill="#5c3b2d"/>
            <path d="M0-10V-3" stroke="#d5d8c5" stroke-width="1.4"/>
            <circle cy="23" r="4" fill="none" stroke="#9ca798" stroke-width="1.2"/>
            <path d="M-18 10H18" stroke="#141e21" stroke-width=".6"/>
          </g>`, "rs"),
    },
    dark_studio_dome: {
        label: "Dark Studio Dome", panel: "charcoal",
        svg: face("dark_studio_dome", `${seat}<circle r="36" fill="url(#chrome)"/>
          <circle r="34.5" fill="#132124"/><circle r="31" fill="none" stroke="#466663" stroke-width="1.4"/>
          <circle data-on-only r="31" fill="none" stroke="#93c6b1" stroke-width="1.4"/>
          <g data-toggle data-on-transform="translate(0,1.5)" data-off-transform="translate(0,-.7)">
            <circle r="28" fill="url(#graphite)" stroke="#586861" stroke-width=".6"/>
            <path d="M-18-18Q0-28 18-18" fill="none" stroke="#75817a" stroke-opacity=".45" stroke-width=".7"/>
            <path d="M-7-6A10 10 0 1 0 7-6M0-12V-2" fill="none" stroke="#b7c9b8" stroke-width="1.4" stroke-linecap="round"/>
          </g>${label(0, 57, "ENGAGE")}`, "rs"),
    },
    bakelite_flip: {
        label: "Bakelite Flip", panel: "olive",
        svg: face("bakelite_flip", `
          <rect x="-30" y="-54" width="62" height="110" rx="3" fill="#000" opacity=".2"/>
          <rect x="-31" y="-56" width="62" height="112" rx="3" fill="url(#bakelite)" stroke="#24291f"/>
          <rect x="-28" y="-53" width="56" height="106" rx="2" fill="none" stroke="#b5a27a" stroke-opacity=".2" stroke-width=".6"/>
          ${screw(0,-48,"url(#brass)")}${screw(0,48,"url(#brass)")}
          ${label(-19, -25, "ON", "#d8c6a0")}${label(-17, 29, "OFF", "#d8c6a0")}
          <path d="M-10-17H10L20 0 10 17H-10L-20 0Z" fill="url(#chrome)"/>
          <circle r="12" fill="#101816" stroke="#777f6e" stroke-width="1"/>
          <g data-toggle data-on-transform="rotate(0)" data-off-transform="rotate(180)">
            <path d="M-4 3L-3-27H3L4 3Z" fill="url(#chrome)"/>
            <rect x="-6" y="-37" width="12" height="20" rx="5" fill="url(#ivory)" stroke="#756e59" stroke-width=".6"/>
            <path d="M-3-32V-22" stroke="#fff0ca" stroke-opacity=".55"/>
          </g>`, "rs"),
    },
    silver_paddle: {
        label: "Silver Paddle", panel: "silver",
        svg: face("silver_paddle", `${slideLabels("#354339")}
          <rect x="-52" y="-21" width="108" height="47" rx="3" fill="#000" opacity=".2"/>
          <rect x="-54" y="-23" width="108" height="46" rx="3" fill="url(#chrome)"/>
          <rect x="-49" y="-18" width="98" height="36" rx="2" fill="#122021"/>
          <path d="M-43 0H43" stroke="#586962" stroke-width="1"/>
          ${screw(-60,0)}${screw(60,0)}
          <g data-toggle data-on-transform="translate(28,0)" data-off-transform="translate(-28,0)">
            <rect x="-15" y="-14" width="34" height="33" rx="2" fill="#000" opacity=".4"/>
            <rect x="-16" y="-16" width="32" height="32" rx="2" fill="url(#aluminium)" stroke="#63776d" stroke-width=".7"/>
            <path d="M-12-12H12M-12-8H12M-12 8H12M-12 12H12" stroke="#627169" stroke-width=".6"/>
            <path d="M-14 0H14" stroke="#293d34" stroke-width="2"/>
          </g>`, "rs"),
    },
    brass_slider: {
        label: "Brass Slider", panel: "olive",
        svg: face("brass_slider", `${slideLabels("#3b4333")}
          <rect x="-55" y="-22" width="112" height="48" rx="2" fill="#000" opacity=".2"/>
          <rect x="-56" y="-24" width="112" height="48" rx="2" fill="url(#brass)" stroke="#626142" stroke-width=".7"/>
          <rect x="-43" y="-9" width="86" height="18" rx="3" fill="#18251c" stroke="#8a875e" stroke-width=".6"/>
          <path d="M-40-6H40" stroke="#0b160f" stroke-width="1.5"/>
          ${screw(-49,0,"url(#brass)")}${screw(49,0,"url(#brass)")}
          <g data-toggle data-on-transform="translate(28,0)" data-off-transform="translate(-28,0)">
            <rect x="-11" y="-13" width="26" height="32" rx="1" fill="#000" opacity=".25"/>
            <rect x="-12" y="-15" width="24" height="30" rx="1.5" fill="url(#brass-face)" stroke="#64623f" stroke-width=".7"/>
            <rect x="-10" y="-12" width="20" height="24" rx="1" fill="url(#knurl)"/>
            <path d="M0-12V12" stroke="#e4d3a3" stroke-width="1.3"/>
          </g>`, "rs"),
    },
    minimal_pill: {
        label: "Minimal Pill", panel: "charcoal",
        svg: face("minimal_pill", `${slideLabels("#b9c5b3")}
          <rect x="-50" y="-20" width="102" height="44" rx="22" fill="#000" opacity=".2"/>
          <rect x="-51" y="-22" width="102" height="44" rx="22" fill="url(#chrome)"/>
          <rect x="-49" y="-20" width="98" height="40" rx="20" fill="#152124"/>
          <path data-on-only d="M-29-15H29A15 15 0 0 1 29 15H-29A15 15 0 0 1-29-15" fill="#50634c"/>
          <g data-toggle data-on-transform="translate(26,0)" data-off-transform="translate(-26,0)">
            <circle cx="1" cy="1.5" r="17.5" fill="#000" opacity=".35"/>
            <circle r="17" fill="url(#ivory)" stroke="#838e7b" stroke-width=".65"/>
            <circle r="14.5" fill="none" stroke="#fcf4d5" stroke-opacity=".25" stroke-width=".6"/>
            <path d="M-3-6V6M0-7V7M3-6V6" stroke="#778776" stroke-opacity=".65" stroke-width=".8"/>
          </g>`, "rs"),
    },
};
