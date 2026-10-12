// Original SVG artwork inspired by recording consoles and rack equipment. Every face (knob, slider
// and switch) is built from the one material set in `defs`.
// Scale marks are relative (0–10); the numeric readout remains in workflow units.
const defs = `
<defs>
  <linearGradient id="rim" x1="0" y1="0" x2=".8" y2="1">
    <stop stop-color="#e3e1d7"/><stop offset=".22" stop-color="#8b908d"/>
    <stop offset=".47" stop-color="#333b3c"/><stop offset=".73" stop-color="#a1a4a0"/>
    <stop offset="1" stop-color="#383d3b"/>
  </linearGradient>
  <radialGradient id="rubber" cx=".32" cy=".2" r=".85">
    <stop stop-color="#41474a"/><stop offset=".55" stop-color="#252a2c"/>
    <stop offset="1" stop-color="#101517"/>
  </radialGradient>
  <linearGradient id="cap" x1="0" y1="0" x2=".75" y2="1">
    <stop stop-color="#9cabb0"/><stop offset=".38" stop-color="#687d87"/>
    <stop offset=".65" stop-color="#4f6570"/><stop offset="1" stop-color="#374b54"/>
  </linearGradient>
  <linearGradient id="ivory" x1="0" y1="0" x2=".5" y2="1">
    <stop stop-color="#f5eed7"/><stop offset=".5" stop-color="#d0c6aa"/>
    <stop offset="1" stop-color="#8d8169"/>
  </linearGradient>
  <radialGradient id="silver" cx=".32" cy=".25" r=".8">
    <stop stop-color="#eeeae0"/><stop offset=".42" stop-color="#b5b8b3"/>
    <stop offset=".72" stop-color="#818b89"/><stop offset="1" stop-color="#b9bcb4"/>
  </radialGradient>
  <linearGradient id="rocker" x1="0" y1="0" x2="0" y2="1">
    <stop stop-color="#53585a"/><stop offset=".12" stop-color="#353a3c"/>
    <stop offset=".7" stop-color="#181d20"/><stop offset="1" stop-color="#0b1012"/>
  </linearGradient>
  <linearGradient id="amber" x1="0" y1="0" x2="0" y2="1">
    <stop stop-color="#ffe3a1"/><stop offset=".35" stop-color="#dba551"/>
    <stop offset="1" stop-color="#8a571e"/>
  </linearGradient>
  <linearGradient id="cap-black-v" x1="0" y1="0" x2="0" y2="1">
    <stop stop-color="#656b6d"/><stop offset=".08" stop-color="#34393b"/>
    <stop offset=".55" stop-color="#171b1c"/><stop offset="1" stop-color="#0a0d0e"/>
  </linearGradient>
  <linearGradient id="cap-black-h" x1="0" y1="0" x2="1" y2="0">
    <stop stop-color="#5d6365"/><stop offset=".14" stop-color="#2f3436"/>
    <stop offset=".6" stop-color="#171b1c"/><stop offset="1" stop-color="#0a0d0e"/>
  </linearGradient>
  <linearGradient id="slot" x1="0" y1="0" x2="1" y2="1">
    <stop stop-color="#020404"/><stop offset="1" stop-color="#1b2124"/>
  </linearGradient>
  <linearGradient id="amber-bar" x1="0" y1="0" x2="0" y2="1">
    <stop stop-color="#ffd884"/><stop offset=".5" stop-color="#f0a43b"/>
    <stop offset="1" stop-color="#b8681c"/>
  </linearGradient>
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
  <linearGradient id="ivory-pale" x1="0" y1="0" x2=".5" y2="1">
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

const svg = (body, className) => `<svg viewBox="-70 -70 140 140" class="${className}" xmlns="http://www.w3.org/2000/svg">${defs}${body}</svg>`;
const shadow = `<ellipse cx="2" cy="6" rx="41" ry="42" fill="#000" opacity=".24"/>
    <circle r="40" fill="#101415" stroke="#c6c6b6" stroke-opacity=".2"/>`;

function scale(color = "#d0d2c2") {
    let marks = "";
    for (let i = 0; i <= 40; i++) {
        const angle = (-225 + i / 40 * 270) * Math.PI / 180;
        const major = i % 4 === 0;
        const r = major ? 47 : 50;
        marks += `<path d="M${(Math.cos(angle) * r).toFixed(2)} ${(Math.sin(angle) * r).toFixed(2)} L${(Math.cos(angle) * 54).toFixed(2)} ${(Math.sin(angle) * 54).toFixed(2)}" stroke="${color}" stroke-width="${major ? 1.2 : .65}"/>`;
        if (major && i % 8 === 0) {
            marks += `<text x="${(Math.cos(angle) * 62).toFixed(2)}" y="${(Math.sin(angle) * 62 + 2.5).toFixed(2)}" text-anchor="middle" fill="${color}" font-family="monospace" font-size="6.5">${i / 4}</text>`;
        }
    }
    return marks;
}

function flutes(count = 36) {
    let marks = "";
    for (let i = 0; i < count; i++) {
        marks += `<path d="M-1 -35 L-1 -30" stroke="#080c0d" stroke-width="1.8" transform="rotate(${i * 360 / count})"/>
            <path d="M.6 -35 L.6 -30" stroke="#929c9c" stroke-opacity=".16" stroke-width=".7" transform="rotate(${i * 360 / count})"/>`;
    }
    return marks;
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
const pointer = `<g data-rotate><g transform="rotate(-90)"><path d="M17 0H34" stroke="#0e1719" stroke-width="4"/>
    <path d="M18 -.2H34" stroke="#e8e4ca" stroke-width="2" stroke-linecap="round"/></g></g>`;

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

export const KNOBS = {
    console_rotary: {
        label: "Console · Blue Grey", panel: "charcoal",
        svg: svg(`${scale()}${shadow}
          <circle r="37" fill="url(#rim)"/><circle r="35" fill="url(#rubber)"/>
          ${flutes()}<circle r="27.5" fill="#0b1113"/>
          <circle cy="-.7" r="25.7" fill="url(#cap)" stroke="#adc0c6" stroke-opacity=".22"/>
          <circle r="23.5" fill="none" stroke="#0a1a21" stroke-opacity=".35" stroke-width=".5"/>
          <g data-rotate><path d="M0 -13 V-31" stroke="#111b20" stroke-width="4"/>
            <path d="M0 -14 V-31" stroke="#eee8ca" stroke-width="2.2" stroke-linecap="round"/></g>`, "rk--console_rotary"),
    },
    ivory_selector: {
        label: "Broadcast · Ivory", panel: "olive",
        svg: svg(`${scale("#292e28")}${shadow}<circle r="36" fill="url(#rubber)"/>
          <circle r="33" fill="none" stroke="#777c69" stroke-opacity=".4"/>
          <g data-rotate>
            <path d="M-12 26 Q-21 20 -18 2 L-6 -33 Q0 -41 6 -33 L18 2 Q21 20 12 26Z" fill="#101714" opacity=".5" transform="translate(1,2)"/>
            <path d="M-12 24 Q-20 18 -17 2 L-5 -32 Q0 -38 5 -32 L17 2 Q20 18 12 24Z" fill="url(#ivory)" stroke="#887f65"/>
            <path d="M-10 19 Q-14 15 -12 3 L-2 -27" fill="none" stroke="#fff6dc" stroke-opacity=".65"/>
            <path d="M0 -32 V-18" stroke="#30382f" stroke-width="2"/>
          </g>`, "rk--ivory_selector"),
    },
    precision_dial: {
        label: "Mastering · Aluminium", panel: "silver",
        svg: svg(`${scale("#303633")}${shadow}<circle r="37" fill="url(#rim)"/>
          <circle r="34" fill="url(#rubber)"/>${flutes(48)}
          <circle cy="-1" r="28" fill="url(#silver)" stroke="#d2d6cb" stroke-width=".7"/>
          ${[8, 12, 16, 20, 24, 26].map(r => `<circle cy="-1" r="${r}" fill="none" stroke="#57625d" stroke-opacity=".16" stroke-width=".3"/>`).join("")}
          <g data-rotate><path d="M0 -17 V-33" stroke="#293533" stroke-width="2.5"/>
          <circle cy="-22" r="1" fill="#e6b977"/></g>`, "rk--precision_dial"),
    },
    chrome_notched: {
        label: "Mastering · Chrome Notched", panel: "silver",
        svg: svg(`${scale("#303633")}${seat}
          <circle r="37" fill="url(#chrome)"/>${grips(24, 36)}
          <circle r="29" fill="#394944"/><circle cy="-.5" r="27.5" fill="url(#aluminium)"/>
          ${machining([8, 12, 16, 20, 24, 26])}${pointer}`, "rk--chrome_notched"),
    },
    dark_studio_led: {
        label: "Console · LED Ring", panel: "charcoal",
        svg: svg(`${scale()}${seat}
          <circle r="43" fill="none" stroke="#101b1e" stroke-width="3"/>
          <circle data-arc transform="rotate(135)" r="43" pathLength="100" fill="none" stroke="#91c9bd" stroke-width="1.8" stroke-dasharray="0 100"/>
          <circle r="36" fill="url(#chrome)"/><circle r="34.5" fill="url(#graphite)"/>
          ${grips(44, 34, "#11191b")}<circle r="28" fill="url(#graphite)" stroke="#657470" stroke-opacity=".35" stroke-width=".6"/>
          <circle r="25" fill="none" stroke="#0a171c" stroke-width=".6"/>
          <g data-rotate><g transform="rotate(-90)"><path d="M20 0H33" stroke="#a6d5c4" stroke-width="2.2" stroke-linecap="round"/></g></g>`, "rk--dark_studio_led"),
    },
    bakelite_chickenhead: {
        label: "Broadcast · Bakelite Chickenhead", panel: "olive",
        svg: svg(`${scale("#292e28")}${seat}
          <circle r="35" fill="url(#bakelite)"/><circle r="32" fill="none" stroke="#c4a880" stroke-opacity=".15"/>
          <g data-rotate><g transform="rotate(-90)">
            <path d="M-24 -11Q-28 0-24 11L-4 18Q7 20 17 9L36 3Q40 0 36-3L17-9Q7-20-4-18Z" fill="#060c0c" opacity=".35" transform="translate(1.5,2)"/>
            <path d="M-24 -11Q-28 0-24 11L-4 18Q7 20 17 9L36 3Q40 0 36-3L17-9Q7-20-4-18Z" fill="url(#bakelite)" stroke="#1c211c"/>
            <path d="M-22-9L-5-15Q6-17 15-8L32-2" fill="none" stroke="#cdb391" stroke-opacity=".4" stroke-width=".8"/>
            <path d="M13 0H34" stroke="#ded1ad" stroke-width="2" stroke-linecap="round"/>
            <circle cx="-12" r="3" fill="#231e18" stroke="#846b4e" stroke-width=".6"/>
            <path d="M-14 0H-10" stroke="#a39478" stroke-width=".7"/>
          </g></g>`, "rk--bakelite_chickenhead"),
    },
    silver_skirted: {
        label: "Mastering · Silver Skirted", panel: "silver",
        svg: svg(`${scale("#303633")}${seat}
          <circle r="38" fill="url(#chrome)"/><circle r="35" fill="url(#aluminium)"/>
          ${machining([30, 32, 34])}<circle r="27" fill="#253533"/>
          <circle r="25.5" fill="url(#chrome)"/><circle cy="-.7" r="23" fill="url(#aluminium)"/>
          ${machining([7, 11, 15, 19, 21])}
          <g data-rotate><g transform="rotate(-90)"><path d="M15 0H35" stroke="#34433c" stroke-width="2"/>
          <path d="M27-2V2" stroke="#e8e7d8" stroke-width=".6"/></g></g>`, "rk--silver_skirted"),
    },
    knurled_brass: {
        label: "Broadcast · Knurled Brass", panel: "olive",
        svg: svg(`${scale("#292e28")}${seat}
          <circle r="37" fill="url(#brass)"/>
          <rect x="-38" y="-38" width="76" height="76" fill="url(#knurl)" mask="url(#knurl-band)"/>
          <circle r="29" fill="#59563d"/><circle r="27.5" fill="url(#brass-face)"/>
          ${machining([9, 13, 17, 21, 25], "#64583b")}
          <g data-rotate><g transform="rotate(-90)"><circle cx="23" r="3.1" fill="#554a33"/>
          <circle cx="23" r="2.3" fill="#ae5942"/><circle cx="22.4" cy="-.6" r=".7" fill="#e8b88c"/>
          <path d="M29 0H34" stroke="#e6d1a0" stroke-width="1.4"/></g></g>`, "rk--knurled_brass"),
    },
    minimal_flat: {
        label: "Console · Minimal Flat", panel: "charcoal",
        svg: svg(`${scale()}${seat}
          <circle r="36" fill="#66736e"/><circle cy=".6" r="35" fill="url(#graphite)"/>
          <circle r="32" fill="none" stroke="#0d171a" stroke-opacity=".45" stroke-width=".5"/>
          <g data-rotate><g transform="rotate(-90)"><path d="M18 0H33" stroke="#e1e4cf" stroke-width="1.8" stroke-linecap="round"/></g></g>`, "rk--minimal_flat"),
    },
};

// Sliders share one geometry: the cap centre travels 86 units across the face (+/-43).
const travel = f => 43 - f * 86;

function ruler(axis, count, { near, far, longFar, color, width = .7, longEvery = 5 }) {
    return Array.from({ length: count + 1 }, (_, i) => {
        const long = i % longEvery === 0;
        const reach = long ? longFar : far;
        const w = long ? width * 1.5 : width;
        return axis === "x"
            ? `<path d="M${(-43 + i / count * 86).toFixed(2)} ${near} V${reach}" stroke="${color}" stroke-width="${w}"/>`
            : `<path d="M${near} ${travel(i / count).toFixed(2)} H${reach}" stroke="${color}" stroke-width="${w}"/>`;
    }).join("");
}

const grooves = (ys, x) => ys.map(y =>
    `<path d="M${-x} ${y} H${x}" stroke="#000" stroke-width="1"/><path d="M${-x} ${y + 1.1} H${x}" stroke="#868e8f" stroke-opacity=".28" stroke-width=".6"/>`).join("");

export const SLIDERS = {
    studio_fader: {
        label: "Console · Linear Fader", panel: "charcoal", kind: "slider",
        svg: svg(`
          <rect x="-6" y="-53" width="12" height="106" rx="6" fill="#414a49"/>
          <rect x="-3.5" y="-52" width="7" height="104" rx="3" fill="#0b1011"/>
          <path d="M-2 -48 V48" stroke="#000"/>
          ${Array.from({length: 11}, (_, i) => `<path d="M-32 ${43-i*8.6} H-17 M17 ${43-i*8.6} H${i%2 ? 25 : 32}" stroke="#aeb8ab" stroke-width=".8"/>
            ${i%2 ? "" : `<text x="-42" y="${46-i*8.6}" text-anchor="middle" font-size="7" font-family="monospace" fill="#c8cebd">${i}</text>`}`).join("")}
          <g data-slide>
            <rect x="-18" y="-9" width="39" height="27" rx="2" fill="#000" opacity=".35"/>
            <rect x="-19" y="-13" width="38" height="26" rx="2" fill="url(#ivory)" stroke="#7d7b6c"/>
            <path d="M-16 -9 H16 M-16 -6 H16 M-16 6 H16 M-16 9 H16" stroke="#8c8a7c" stroke-width=".7"/>
            <path d="M-19 0 H19" stroke="#323b36" stroke-width="2"/>
          </g>`, "rk--studio_fader"),
    },
    channel_fader: {
        label: "Console · Channel Fader", panel: "silver", kind: "slider",
        svg: svg(`
          ${[[1, "+10"], [.875, "+5"], [.75, "0"], [.6, "-5"], [.45, "-10"], [.3, "-20"], [.15, "-40"], [0, "∞"]].map(([f, t]) =>
            `<path d="M-23 ${travel(f).toFixed(2)} H-16" stroke="${f === .75 ? "#8a2f20" : "#2b312d"}" stroke-width="${f === .75 ? 1.5 : 1}"/>
             <text x="-26" y="${(travel(f) + 2).toFixed(2)}" text-anchor="end" fill="${f === .75 ? "#8a2f20" : "#2b312d"}" font-family="monospace" font-size="5.6">${t}</text>`).join("")}
          ${ruler("y", 20, { near: 16, far: 20, longFar: 23, color: "#3a413b" })}
          <rect x="-5.5" y="-50" width="11" height="100" rx="5.5" fill="#fff" opacity=".35"/>
          <rect x="-4.5" y="-50" width="9" height="100" rx="4.5" fill="#222a2b" opacity=".55"/>
          <rect x="-3" y="-49" width="6" height="98" rx="3" fill="url(#slot)"/>
          <g data-slide data-axis="y">
            <rect x="-12" y="-14" width="27" height="36" rx="3" fill="#000" opacity=".32"/>
            <rect x="-13.5" y="-18" width="27" height="36" rx="2.5" fill="url(#cap-black-v)" stroke="#000" stroke-opacity=".7"/>
            <path d="M-11.5 -16.2 H11.5" stroke="#aab1b1" stroke-opacity=".45"/>
            ${grooves([-12, -8.5, -5, 5.5, 9, 12.5], 11)}
            <path d="M-13 0 H13" stroke="#f1efe5" stroke-width="2.4"/>
          </g>`, "rk--channel_fader"),
    },
    led_ladder: {
        label: "Rack · LED Ladder", panel: "charcoal", kind: "slider",
        svg: svg(`
          ${Array.from({ length: 11 }, (_, i) => `<path d="M-38 ${travel(i / 10).toFixed(2)} H${i % 5 ? -34 : -31}" stroke="#aeb8ab" stroke-width="${i % 5 ? .7 : 1.1}"/>`).join("")}
          ${[0, 5, 10].map(n => `<text x="-41" y="${(travel(n / 10) + 2).toFixed(2)}" text-anchor="end" fill="#c8cebd" font-family="monospace" font-size="6">${n}</text>`).join("")}
          <rect x="-17" y="-49" width="6" height="98" rx="3" fill="#000" opacity=".4"/>
          <rect x="-16" y="-48" width="4" height="96" rx="2" fill="url(#slot)"/>
          <rect x="9" y="-52" width="26" height="104" rx="3" fill="#0a1011" stroke="#c6c6b6" stroke-opacity=".16"/>
          ${Array.from({ length: 12 }, (_, i) => {
            const y = 44 - i * 7.9, c = i < 7 ? "#58e07f" : i < 10 ? "#f4c24d" : "#ef5a48", t = (i / 12).toFixed(4);
            return `<rect data-led="${t}" data-on=".3" data-off="0" x="11.5" y="${(y - 5).toFixed(2)}" width="21" height="9" rx="3" fill="${c}"/>
              <rect data-led="${t}" data-on="1" data-off=".16" x="14" y="${(y - 3.2).toFixed(2)}" width="16" height="5.4" rx="1.4" fill="${c}"/>
              <rect data-led="${t}" data-on=".6" data-off="0" x="14.8" y="${(y - 2.6).toFixed(2)}" width="14.4" height="1.6" rx=".8" fill="#fff"/>`;
          }).join("")}
          <g data-slide data-axis="y"><g transform="translate(-14,0)">
            <rect x="-11" y="-6" width="24" height="17" rx="3" fill="#000" opacity=".4"/>
            <rect x="-12" y="-8.5" width="24" height="17" rx="2.5" fill="url(#rim)" stroke="#0b1011"/>
            <rect x="-9.5" y="-6" width="19" height="12" rx="1.5" fill="url(#cap-black-v)"/>
            <path d="M-12 0 H12" stroke="#ef5a48" stroke-width="1.6"/>
            <path d="M-9 -4.4 H9" stroke="#9aa3a3" stroke-opacity=".35" stroke-width=".6"/>
          </g></g>`, "rk--led_ladder"),
    },
    pan_slider: {
        label: "Broadcast · Pan Slider", panel: "olive", kind: "slider",
        svg: svg(`
          ${ruler("x", 20, { near: -26, far: -21, longFar: -18, color: "#2b312a" })}
          ${[[0, "L"], [.5, "C"], [1, "R"]].map(([f, t]) =>
            `<text x="${(-43 + f * 86).toFixed(2)}" y="-31" text-anchor="middle" fill="${f === .5 ? "#7d2c1c" : "#2b312a"}" font-family="monospace" font-size="7.5" font-weight="bold">${t}</text>`).join("")}
          <rect x="-50" y="-5.5" width="100" height="11" rx="5.5" fill="#fff" opacity=".28"/>
          <rect x="-49" y="-4.5" width="98" height="9" rx="4.5" fill="#303729" opacity=".5"/>
          <rect x="-48" y="-3" width="96" height="6" rx="3" fill="url(#slot)"/>
          <text x="0" y="40" text-anchor="middle" fill="#2b312a" font-family="monospace" font-size="6.5" letter-spacing="1.5">PAN</text>
          <g data-slide data-axis="x">
            <rect x="-6" y="-12" width="18" height="34" rx="3" fill="#000" opacity=".3"/>
            <rect x="-8.5" y="-16" width="17" height="32" rx="2.5" fill="url(#cap-black-h)" stroke="#000" stroke-opacity=".7"/>
            <path d="M-7 -14 H7" stroke="#b6bcb5" stroke-opacity=".4"/>
            ${[-5.5, -3.2, 3.2, 5.5].map(x => `<path d="M${x} -12 V12" stroke="#000" stroke-width=".9"/><path d="M${x + .9} -12 V12" stroke="#8d948f" stroke-opacity=".25" stroke-width=".5"/>`).join("")}
            <path d="M0 -15 V15" stroke="#f0ead2" stroke-width="2.2"/>
          </g>`, "rk--pan_slider"),
    },
    amber_slide: {
        label: "Rack · Amber Slide", panel: "charcoal", kind: "slider",
        svg: svg(`
          ${ruler("x", 20, { near: 15, far: 20, longFar: 24, color: "#aeb8ab" })}
          ${[0, 5, 10].map(n => `<text x="${(-43 + n / 10 * 86).toFixed(2)}" y="35" text-anchor="middle" fill="#c8cebd" font-family="monospace" font-size="6.5">${n}</text>`).join("")}
          <rect x="-52" y="-9" width="104" height="18" rx="4" fill="#000" opacity=".4"/>
          <rect x="-51" y="-10" width="102" height="18" rx="3.5" fill="#0a1011" stroke="#c6c6b6" stroke-opacity=".18"/>
          <rect x="-47" y="-4.5" width="94" height="9" rx="4.5" fill="url(#slot)"/>
          <g transform="translate(-43,0)"><g data-fill data-axis="x">
            <rect x="0" y="-5.5" width="86" height="11" rx="5.5" fill="#f0a43b" opacity=".22"/>
            <rect x="0" y="-3.1" width="86" height="6.2" rx="3.1" fill="url(#amber-bar)"/>
            <rect x="0" y="-2.4" width="86" height="1.5" rx=".75" fill="#fff" opacity=".45"/>
          </g></g>
          <g data-slide data-axis="x">
            <rect x="-7" y="-12" width="19" height="31" rx="3" fill="#000" opacity=".35"/>
            <rect x="-9.5" y="-16" width="19" height="31" rx="2.5" fill="url(#rim)" stroke="#0b1011"/>
            <rect x="-7" y="-13.5" width="14" height="26" rx="1.8" fill="url(#cap-black-h)"/>
            <path d="M0 -15 V15" stroke="#ffc05c" stroke-width="2"/>
            <path d="M-2.4 -13 V13" stroke="#fff" stroke-opacity=".14" stroke-width=".6"/>
          </g>`, "rk--amber_slide"),
    },
};

export const SWITCHES = {
    console_rocker: {
        label: "Rack · Power Rocker", panel: "charcoal",
        svg: svg(`
          <text x="0" y="-54" text-anchor="middle" fill="#c4cabb" font-family="monospace" font-size="7" letter-spacing="2">POWER</text>
          <rect x="-27" y="-43" width="57" height="90" rx="5" fill="#000" opacity=".3"/>
          <rect x="-29" y="-45" width="58" height="90" rx="4" fill="url(#rim)"/>
          <rect x="-26" y="-42" width="52" height="84" rx="3" fill="#080d0f"/>
          <g data-toggle data-on-transform="translate(0,1)" data-off-transform="translate(0,-1)">
            <rect x="-23" y="-38" width="46" height="76" rx="3" fill="url(#rocker)" stroke="#595e5c" stroke-width=".5"/>
            <path data-off-only d="M-20 -34 H20" stroke="#919990" stroke-width="2"/>
            <path data-on-only d="M-20 34 H20" stroke="#919990" stroke-width="2"/>
            <path d="M0 -26 V-16" stroke="#d7daca" stroke-width="1.8"/>
            <circle cy="23" r="5" fill="none" stroke="#929a90" stroke-width="1.4"/>
            <rect x="-10" y="-5" width="20" height="7" rx="2" fill="#140c05" stroke="#070c0c"/>
            <rect data-on-only x="-9" y="-4" width="18" height="5" rx="1" fill="url(#amber)"/>
            <rect data-off-only x="-9" y="-4" width="18" height="5" rx="1" fill="#5c4027"/>
          </g>`, "rs--console_rocker"),
    },
    broadcast_lever: {
        label: "Broadcast · Steel Lever", panel: "olive",
        svg: svg(`
          <text x="0" y="-52" text-anchor="middle" fill="#2a3028" font-family="monospace" font-size="8">ON</text>
          <text x="0" y="59" text-anchor="middle" fill="#2a3028" font-family="monospace" font-size="8">OFF</text>
          <ellipse cy="5" rx="26" ry="27" fill="#000" opacity=".2"/>
          <path d="M-12 -22 H12 L25 0 12 22 H-12 L-25 0Z" fill="url(#rim)" stroke="#5a625a"/>
          <circle r="17" fill="url(#silver)" stroke="#4d564e"/><circle r="12" fill="#121b19"/>
          <g data-toggle data-on-transform="rotate(0)" data-off-transform="rotate(180)">
            <path d="M-5 5 L-7 -33 Q0 -40 7 -33 L5 5 Q0 11 -5 5Z" fill="url(#rim)" stroke="#636b64" stroke-width=".7"/>
            <path d="M-3 1 L-4 -31" stroke="#f3f1d9" stroke-width="1.5"/>
            <ellipse cy="-32" rx="6" ry="3" fill="#c4cac0"/>
          </g>
          <circle data-on-only cx="28" cy="-47" r="2.5" fill="#a75127"/>`, "rs--broadcast_lever"),
    },
    illuminated_key: {
        label: "Console · Illuminated Key", panel: "charcoal",
        svg: svg(`
          <rect x="-33" y="-31" width="70" height="70" rx="4" fill="#000" opacity=".3"/>
          <rect x="-35" y="-35" width="70" height="70" rx="3" fill="url(#rim)"/>
          <rect x="-32" y="-32" width="64" height="64" rx="2" fill="#0a1011"/>
          <g data-toggle data-on-transform="translate(0,1.5)" data-off-transform="translate(0,-1)">
            <rect x="-28" y="-28" width="56" height="56" rx="2" fill="url(#ivory)" stroke="#9c9b85"/>
            <rect data-on-only x="-25" y="-25" width="50" height="50" rx="1" fill="url(#amber)"/>
            <rect data-off-only x="-25" y="-25" width="50" height="50" rx="1" fill="#b6b59d"/>
            <path d="M-22 -23 H22" stroke="#fff5d1" stroke-opacity=".5"/>
            <text data-readout x="0" y="3" text-anchor="middle" fill="#3a3728" font-family="monospace" font-size="10" letter-spacing="1.5">OFF</text>
          </g>`, "rs--illuminated_key"),
    },
    chrome_rocker: {
        label: "Rack · Chrome Rocker", panel: "silver",
        svg: svg(`
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
          </g>`, "rs--chrome_rocker"),
    },
    dark_studio_dome: {
        label: "Console · Dome Button", panel: "charcoal",
        svg: svg(`${seat}<circle r="36" fill="url(#chrome)"/>
          <circle r="34.5" fill="#132124"/><circle r="31" fill="none" stroke="#466663" stroke-width="1.4"/>
          <circle data-on-only r="31" fill="none" stroke="#93c6b1" stroke-width="1.4"/>
          <g data-toggle data-on-transform="translate(0,1.5)" data-off-transform="translate(0,-.7)">
            <circle r="28" fill="url(#graphite)" stroke="#586861" stroke-width=".6"/>
            <path d="M-18-18Q0-28 18-18" fill="none" stroke="#75817a" stroke-opacity=".45" stroke-width=".7"/>
            <path d="M-7-6A10 10 0 1 0 7-6M0-12V-2" fill="none" stroke="#b7c9b8" stroke-width="1.4" stroke-linecap="round"/>
          </g>${label(0, 57, "ENGAGE")}`, "rs--dark_studio_dome"),
    },
    bakelite_flip: {
        label: "Broadcast · Bakelite Flip", panel: "olive",
        svg: svg(`
          <rect x="-30" y="-54" width="62" height="110" rx="3" fill="#000" opacity=".2"/>
          <rect x="-31" y="-56" width="62" height="112" rx="3" fill="url(#bakelite)" stroke="#24291f"/>
          <rect x="-28" y="-53" width="56" height="106" rx="2" fill="none" stroke="#b5a27a" stroke-opacity=".2" stroke-width=".6"/>
          ${screw(0,-48,"url(#brass)")}${screw(0,48,"url(#brass)")}
          ${label(-19, -25, "ON", "#d8c6a0")}${label(-17, 29, "OFF", "#d8c6a0")}
          <path d="M-10-17H10L20 0 10 17H-10L-20 0Z" fill="url(#chrome)"/>
          <circle r="12" fill="#101816" stroke="#777f6e" stroke-width="1"/>
          <g data-toggle data-on-transform="rotate(0)" data-off-transform="rotate(180)">
            <path d="M-4 3L-3-27H3L4 3Z" fill="url(#chrome)"/>
            <rect x="-6" y="-37" width="12" height="20" rx="5" fill="url(#ivory-pale)" stroke="#756e59" stroke-width=".6"/>
            <path d="M-3-32V-22" stroke="#fff0ca" stroke-opacity=".55"/>
          </g>`, "rs--bakelite_flip"),
    },
    silver_paddle: {
        label: "Mastering · Silver Paddle", panel: "silver",
        svg: svg(`${slideLabels("#354339")}
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
          </g>`, "rs--silver_paddle"),
    },
    brass_slider: {
        label: "Broadcast · Brass Slide", panel: "olive",
        svg: svg(`${slideLabels("#3b4333")}
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
          </g>`, "rs--brass_slider"),
    },
    minimal_pill: {
        label: "Console · Minimal Pill", panel: "charcoal",
        svg: svg(`${slideLabels("#b9c5b3")}
          <rect x="-50" y="-20" width="102" height="44" rx="22" fill="#000" opacity=".2"/>
          <rect x="-51" y="-22" width="102" height="44" rx="22" fill="url(#chrome)"/>
          <rect x="-49" y="-20" width="98" height="40" rx="20" fill="#152124"/>
          <path data-on-only d="M-29-15H29A15 15 0 0 1 29 15H-29A15 15 0 0 1-29-15" fill="#50634c"/>
          <g data-toggle data-on-transform="translate(26,0)" data-off-transform="translate(-26,0)">
            <circle cx="1" cy="1.5" r="17.5" fill="#000" opacity=".35"/>
            <circle r="17" fill="url(#ivory-pale)" stroke="#838e7b" stroke-width=".65"/>
            <circle r="14.5" fill="none" stroke="#fcf4d5" stroke-opacity=".25" stroke-width=".6"/>
            <path d="M-3-6V6M0-7V7M3-6V6" stroke="#778776" stroke-opacity=".65" stroke-width=".8"/>
          </g>`, "rs--minimal_pill"),
    },
};

