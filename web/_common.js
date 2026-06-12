// _common.js — Ray's Orenchi shared web utilities.
//
// Exports:
//   TWO_PI                 — Math.PI * 2 constant.
//   getRadialBrushedURL()  — cached canvas-rendered radial brushed-metal texture
//                            used by knob and switch styles.

export const TWO_PI = Math.PI * 2;

let _radialBrushedURL = null;

export function getRadialBrushedURL(palette = ["#f5f5f5", "#c8c8c8", "#7a7a7a"]) {
    if (_radialBrushedURL) return _radialBrushedURL;
    const SZ = 256, R = 128;
    const c = document.createElement("canvas");
    c.width = SZ; c.height = SZ;
    const x = c.getContext("2d");
    const g = x.createRadialGradient(R - 40, R - 50, 0, R, R, R);
    g.addColorStop(0, palette[0]);
    g.addColorStop(0.55, palette[1]);
    g.addColorStop(1, palette[2]);
    x.fillStyle = g;
    x.beginPath(); x.arc(R, R, R, 0, TWO_PI); x.fill();
    x.save();
    x.beginPath(); x.arc(R, R, R, 0, TWO_PI); x.clip();
    for (let i = 0; i < 800; i++) {
        const a = Math.random() * TWO_PI;
        const rs = R * (0.05 + Math.random() * 0.05);
        const re = R * (0.95 + Math.random() * 0.05);
        const alpha = 0.05 + Math.random() * 0.06;
        x.strokeStyle = Math.random() > 0.5 ? `rgba(255,255,255,${alpha})` : `rgba(0,0,0,${alpha * 0.7})`;
        x.lineWidth = 0.4 + Math.random() * 0.5;
        x.beginPath();
        x.moveTo(R + Math.cos(a) * rs, R + Math.sin(a) * rs);
        x.lineTo(R + Math.cos(a) * re, R + Math.sin(a) * re);
        x.stroke();
    }
    x.restore();
    _radialBrushedURL = c.toDataURL();
    return _radialBrushedURL;
}
