// Original SVG artwork inspired by recording consoles and rack equipment.
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

export const STUDIO_KNOBS = {
    console_rotary: {
        label: "Console · Blue Grey", panel: "charcoal", sweep: true,
        svg: svg(`${scale()}${shadow}
          <circle r="37" fill="url(#rim)"/><circle r="35" fill="url(#rubber)"/>
          ${flutes()}<circle r="27.5" fill="#0b1113"/>
          <circle cy="-.7" r="25.7" fill="url(#cap)" stroke="#adc0c6" stroke-opacity=".22"/>
          <circle r="23.5" fill="none" stroke="#0a1a21" stroke-opacity=".35" stroke-width=".5"/>
          <g data-rotate><path d="M0 -13 V-31" stroke="#111b20" stroke-width="4"/>
            <path d="M0 -14 V-31" stroke="#eee8ca" stroke-width="2.2" stroke-linecap="round"/></g>`, "rk--console_rotary"),
    },
    ivory_selector: {
        label: "Broadcast · Ivory", panel: "olive", sweep: true,
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
        label: "Mastering · Aluminium", panel: "silver", sweep: true,
        svg: svg(`${scale("#303633")}${shadow}<circle r="37" fill="url(#rim)"/>
          <circle r="34" fill="url(#rubber)"/>${flutes(48)}
          <circle cy="-1" r="28" fill="url(#silver)" stroke="#d2d6cb" stroke-width=".7"/>
          ${[8, 12, 16, 20, 24, 26].map(r => `<circle cy="-1" r="${r}" fill="none" stroke="#57625d" stroke-opacity=".16" stroke-width=".3"/>`).join("")}
          <g data-rotate><path d="M0 -17 V-33" stroke="#293533" stroke-width="2.5"/>
          <circle cy="-22" r="1" fill="#e6b977"/></g>`, "rk--precision_dial"),
    },
    studio_fader: {
        label: "Console · Linear Fader", panel: "charcoal", sweep: true, kind: "slider",
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

const SLIDERS = {
    channel_fader: {
        label: "Console · Channel Fader", panel: "silver", sweep: true, kind: "slider",
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
        label: "Rack · LED Ladder", panel: "charcoal", sweep: true, kind: "slider",
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
        label: "Broadcast · Pan Slider", panel: "olive", sweep: true, kind: "slider",
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
        label: "Rack · Amber Slide", panel: "charcoal", sweep: true, kind: "slider",
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

export const STUDIO_SWITCHES = {
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
};

export const STUDIO_SLIDERS = SLIDERS;
