// Synthesized hardware feedback for the Analog controls (knobs, sliders, switches).
// Everything is generated with Web Audio at play time: short noise bursts, pitch-dropping
// tones and high-Q resonators stand in for plastic, bakelite, steel and brass. No sample files.
//
// The mute preference is a listener setting, so it lives in localStorage rather than the workflow.

import { THEMES, voiceFor } from "./analog_themes.js";

const PREF_KEY = "ray.analog.muted.v1";
const KNOB_DETENTS = 40;       // one click per printed scale mark (per sweep, or per turn on endless knobs)
const SLIDER_DETENTS = 40;     // fine ticks along a slider's travel
const MIN_TICK_GAP_MS = 11;

// Loudness trims measured from offline renders so every voice peaks at a comparable level.
const TICK_LEVEL = { rubber: .65, bakelite: 1.3, alu: .8, brass: 1.3, fader: 3, plastic: 3.5, pan: 3 };
const PRESS_LEVEL = { key: 1.7, paddle: 2.4 };
const DECK_LEVEL = { key: 1.8, chrome: 2.7 };

function readMuted() {
    try { return localStorage.getItem(PREF_KEY) === "1"; } catch { return false; }
}
let muted = readMuted();
const liveSlides = new Set();

export const isMuted = () => muted;
export function setMuted(value) {
    muted = !!value;
    try { localStorage.setItem(PREF_KEY, muted ? "1" : "0"); } catch { /* preference stays in memory */ }
    if (muted) for (const slide of [...liveSlides]) slide.stop();
}

// ---------------------------------------------------------------------------
// Voice tables: which sound each visual style makes
// ---------------------------------------------------------------------------

const KNOB_VOICE = {
    console_rotary: "rubber", dark_studio_led: "rubber", minimal_flat: "rubber",
    ivory_selector: "bakelite", bakelite_chickenhead: "bakelite",
    precision_dial: "alu", chrome_notched: "alu", silver_skirted: "alu",
    knurled_brass: "brass",
    studio_fader: "fader", channel_fader: "fader",
    led_ladder: "plastic", amber_slide: "plastic", pan_slider: "pan",
};
const SWITCH_VOICE = {
    console_rocker: "rocker", chrome_rocker: "rocker",
    broadcast_lever: "lever",
    illuminated_key: "key",
    bakelite_flip: "bakelite",
    silver_paddle: "paddle",
    brass_slider: "slider",
    minimal_pill: "pill",
    dark_studio_dome: "dome",
};
// Styles drawn for another kind of control sound like their sound class does on this one.
for (const [id, theme] of Object.entries(THEMES)) {
    if (!(id in KNOB_VOICE)) KNOB_VOICE[id] = voiceFor(id, theme.native === "fader" ? "slider" : "knob");
    if (!(id in SWITCH_VOICE)) SWITCH_VOICE[id] = voiceFor(id, "switch");
}
export const VOICE_TABLES = { knob: KNOB_VOICE, switch: SWITCH_VOICE };
// A slider (including the fader bank, which can wear any style) needs a voice that scrapes; a knob style
// used on a slider takes its class's slider voice.
export const knobVoice = (key, slider) => {
    const own = KNOB_VOICE[key];
    if (!slider) return own || voiceFor(key, "knob") || "rubber";
    return own && SLIDE[own] ? own : (voiceFor(key, "slider") || "fader");
};
export const switchVoice = key => SWITCH_VOICE[key] || voiceFor(key, "switch") || "rocker";

// Continuous scrape under a dragged slider cap: [centre Hz, Q, level, speed that reaches full level].
const SLIDE = {
    fader:   { f: 1100, q: .9,  gain: .11, vmax: 1.6 },
    plastic: { f: 2300, q: 1.1, gain: .08, vmax: 1.6 },
    pan:     { f: 1500, q: 1,   gain: .1,  vmax: 1.6 },
};

// ---------------------------------------------------------------------------
// Synthesis
// ---------------------------------------------------------------------------

// `ctx` may be a live AudioContext or an OfflineAudioContext (the tests render voices offline).
export function createBank(ctx, dest) {
    const rate = ctx.sampleRate;
    const noise = ctx.createBuffer(1, rate * 2, rate);
    const data = noise.getChannelData(0);
    for (let i = 0; i < data.length; i++) data[i] = Math.random() * 2 - 1;
    let out = dest;
    // Run one voice through a trim gain so differently built voices sit at a similar loudness.
    function withLevel(level, fn) {
        if (level === 1) return fn();
        const previous = out, trim = ctx.createGain();
        trim.gain.value = level; trim.connect(previous); out = trim;
        try { fn(); } finally { out = previous; }
        setTimeout(() => trim.disconnect(), 1000);
    }
    const jitter = (spread = .06) => 1 + (Math.random() - .5) * 2 * spread;
    const when = t => t ?? ctx.currentTime;

    function envelope(g, t, peak, attack, decay) {
        g.gain.setValueAtTime(.0001, t);
        g.gain.exponentialRampToValueAtTime(Math.max(.0002, peak), t + attack);
        g.gain.exponentialRampToValueAtTime(.0001, t + attack + decay);
    }

    // Filtered noise burst: the "tk" of plastic and metal contacts.
    function burst(t, { f = 2000, q = 1, type = "bandpass", dur = .01, gain = .3, attack = .0004 }) {
        const src = ctx.createBufferSource(); src.buffer = noise;
        const filter = ctx.createBiquadFilter(); filter.type = type; filter.frequency.value = f; filter.Q.value = q;
        const g = ctx.createGain(); envelope(g, t, gain, attack, dur);
        src.connect(filter).connect(g).connect(out);
        src.start(t, Math.random() * 1.5); src.stop(t + attack + dur + .03);
    }

    // Pitch-dropping sine or triangle: the body of a thunk.
    function tone(t, { f0 = 200, f1 = f0, dur = .05, gain = .3, type = "sine", attack = .0008 }) {
        const osc = ctx.createOscillator(); osc.type = type;
        osc.frequency.setValueAtTime(f0, t);
        osc.frequency.exponentialRampToValueAtTime(Math.max(20, f1), t + dur);
        const g = ctx.createGain(); envelope(g, t, gain, attack, dur);
        osc.connect(g).connect(out);
        osc.start(t); osc.stop(t + attack + dur + .03);
    }

    // A 1.5 ms noise knock exciting a high-Q filter: metal or hard plastic ringing after impact.
    function ring(t, { f = 3000, q = 25, dur = .06, gain = .3 }) {
        const src = ctx.createBufferSource(); src.buffer = noise;
        const knock = ctx.createGain();
        knock.gain.setValueAtTime(1, t); knock.gain.setTargetAtTime(0, t + .0012, .0005);
        const filter = ctx.createBiquadFilter(); filter.type = "bandpass"; filter.frequency.value = f; filter.Q.value = q;
        const g = ctx.createGain();
        g.gain.setValueAtTime(gain * 9, t); g.gain.exponentialRampToValueAtTime(.0001, t + dur);
        src.connect(knock).connect(filter).connect(g).connect(out);
        src.start(t, Math.random() * 1.5); src.stop(t + dur + .03);
    }

    // ---- knob detent ticks -------------------------------------------------
    const ticks = {
        rubber(t, v) {            // soft rubber-skirted pot detent
            const r = jitter();
            tone(t, { f0: 210 * r, f1: 95, dur: .018, gain: .36 * v });
            burst(t, { f: 1500 * r, q: 1.1, dur: .007, gain: .2 * v });
        },
        bakelite(t, v) {          // hard selector: click-clack
            const r = jitter();
            burst(t, { f: 2300 * r, q: 2.5, dur: .006, gain: .3 * v });
            ring(t + .001, { f: 1050 * r, q: 14, dur: .04, gain: .14 * v });
            tone(t, { f0: 330 * r, f1: 160, dur: .02, gain: .14 * v });
        },
        alu(t, v) {               // fine machined ratchet
            const r = jitter();
            burst(t, { f: 4300 * r, q: .7, type: "highpass", dur: .003, gain: .24 * v });
            tone(t, { f0: 3200 * r, f1: 2200, dur: .007, gain: .09 * v });
            ring(t, { f: 5200 * r, q: 30, dur: .022, gain: .05 * v });
        },
        brass(t, v) {             // knurled brass: a dull "tink"
            const r = jitter();
            burst(t, { f: 3000 * r, q: 2, dur: .004, gain: .22 * v });
            ring(t, { f: 2100 * r, q: 18, dur: .06, gain: .1 * v });
            tone(t, { f0: 800 * r, f1: 500, dur: .012, gain: .1 * v });
        },
        fader(t, v) {             // fader cap crossing a fine contact: whisper of a tick
            burst(t, { f: 3200 * jitter(), q: 1.6, dur: .0025, gain: .07 * v });
        },
        plastic(t, v) {
            burst(t, { f: 3800 * jitter(), q: 1.4, dur: .0025, gain: .06 * v });
        },
        pan(t, v) {
            burst(t, { f: 2700 * jitter(), q: 1.6, dur: .003, gain: .07 * v });
        },
    };

    // ---- end stops: the dial or cap hits its limit -----------------------
    const stops = {
        knob(t) {
            tone(t, { f0: 130, f1: 68, dur: .06, gain: .42, type: "triangle" });
            burst(t, { f: 700, q: .8, type: "lowpass", dur: .02, gain: .3 });
        },
        slider(t) {
            tone(t, { f0: 96, f1: 48, dur: .1, gain: .5, type: "triangle" });
            burst(t, { f: 520, q: .7, type: "lowpass", dur: .035, gain: .4 });
            ring(t + .002, { f: 1700, q: 10, dur: .05, gain: .06 });
        },
    };

    // ---- switch presses, shaped by each style's hardware ----------------
    // `on` is the state being switched to; "off" lands lower and softer.
    const presses = {
        rocker(t, on) {           // rack power rocker: thump, plastic clack, rocker hits its stop
            const p = on ? 1 : .88, v = on ? 1 : .82;
            tone(t, { f0: 150 * p, f1: 70 * p, dur: .06, gain: .5 * v, type: "triangle" });
            burst(t + .003, { f: 2400 * p, q: 1.5, dur: .008, gain: .42 * v });
            burst(t + (on ? .012 : .009), { f: 3200 * p, q: 2, dur: .006, gain: .24 * v });
            ring(t + .004, { f: 900 * p, q: 8, dur: .05, gain: .1 * v });
        },
        lever(t, on) {            // steel toggle: sharp strike, ring, a spring still singing
            const p = on ? 1 : .9;
            burst(t, { f: 3600, q: .7, type: "highpass", dur: .003, gain: .4 });
            ring(t, { f: 3300 * p, q: 40, dur: .1, gain: .18 });
            ring(t, { f: 5200 * p, q: 60, dur: .07, gain: .09 });
            tone(t, { f0: 230 * p, f1: 110, dur: .04, gain: on ? .36 : .46, type: "triangle" });
            ring(t + .016, { f: 1150 * p, q: 25, dur: .17, gain: .06 });
        },
        key(t, on) {              // illuminated console key: clean push, latch on the way down
            const p = on ? 1 : .86;
            burst(t, { f: 1900 * p, q: 2, dur: .005, gain: .38 });
            tone(t, { f0: 620 * p, f1: 300, dur: .02, gain: .2 });
            ring(t + .001, { f: 2600 * p, q: 20, dur: .03, gain: .07 });
            burst(t + .07, { f: 2600 * p, q: 2, dur: .004, gain: on ? .2 : .1 });
        },
        bakelite(t, on) {         // heavy bakelite flip: dull clunk with a bright lever tinkle
            const p = on ? 1 : .86;
            tone(t, { f0: 330 * p, f1: 120 * p, dur: .045, gain: .5, type: "triangle" });
            burst(t, { f: 1200 * p, q: 1.2, dur: .009, gain: .3 });
            ring(t + .001, { f: 1500 * p, q: 8, dur: .035, gain: .1 });
            ring(t + .006, { f: 2900 * p, q: 30, dur: .06, gain: .06 });
        },
        paddle(t, on) {           // light plastic paddle: tick-tack
            const p = on ? 1 : .88;
            burst(t, { f: 3400 * p, q: 2, dur: .004, gain: .34 });
            tone(t, { f0: 900 * p, f1: 500, dur: .012, gain: .14 });
            burst(t + .014, { f: 2600 * p, q: 2, dur: .005, gain: .28 });
        },
        slider(t, on) {           // brass slider: a short scrape ending in a detent click
            const p = on ? 1 : .88;
            burst(t, { f: 1800 * p, q: 1, dur: .055, gain: .12, attack: .03 });
            tone(t + .05, { f0: 700 * p, f1: 400, dur: .014, gain: .3 });
            ring(t + .05, { f: 2400 * p, q: 20, dur: .03, gain: .08 });
            burst(t + .05, { f: 2000 * p, q: 1.6, dur: .005, gain: .22 });
        },
        pill(t, on) {             // minimal pill: a soft tap
            const p = on ? 1 : .85;
            tone(t, { f0: 520 * p, f1: 260 * p, dur: .028, gain: .36 });
            burst(t, { f: 1200 * p, q: .8, type: "lowpass", dur: .009, gain: .2 });
        },
        dome(t, on) {             // dark dome: hollow thock and a membrane click
            const p = on ? 1 : .88;
            tone(t, { f0: 270 * p, f1: 140 * p, dur: .05, gain: .5, type: "triangle" });
            burst(t, { f: 1700 * p, q: 3, dur: .006, gain: .34 });
            ring(t + .002, { f: 700 * p, q: 10, dur: .045, gain: .1 });
        },
    };

    // ---- button deck: an interlocked bank. The pressed button latches (down) and the one that was
    // latched pops back out (up), a beat later and softer. ----------------------------------------
    const decks = {
        key: {                     // console amber key: clean push, latch
            down(t) {
                burst(t, { f: 1900, q: 2, dur: .005, gain: .38 });
                tone(t, { f0: 620, f1: 300, dur: .02, gain: .2 });
                ring(t + .001, { f: 2600, q: 20, dur: .03, gain: .07 });
            },
            up(t) { burst(t, { f: 2600, q: 2, dur: .004, gain: .14 }); tone(t, { f0: 380, f1: 260, dur: .012, gain: .06 }); },
        },
        dome: {                    // lamp dome: hollow thock, membrane click
            down(t) {
                tone(t, { f0: 270, f1: 140, dur: .05, gain: .5, type: "triangle" });
                burst(t, { f: 1700, q: 3, dur: .006, gain: .34 });
                ring(t + .002, { f: 700, q: 10, dur: .045, gain: .1 });
            },
            up(t) { tone(t, { f0: 330, f1: 200, dur: .015, gain: .1 }); burst(t, { f: 1500, q: 2, dur: .004, gain: .1 }); },
        },
        bakelite: {                // bakelite pushbutton: dull clunk
            down(t) {
                tone(t, { f0: 300, f1: 110, dur: .05, gain: .5, type: "triangle" });
                burst(t, { f: 1100, q: 1.2, dur: .01, gain: .3 });
                ring(t + .001, { f: 1500, q: 8, dur: .035, gain: .1 });
            },
            up(t) { tone(t, { f0: 220, f1: 150, dur: .025, gain: .16 }); burst(t, { f: 900, q: 1.2, dur: .006, gain: .12 }); },
        },
        chrome: {                  // chrome square: bright double tick
            down(t) {
                burst(t, { f: 3400, q: 2, dur: .004, gain: .34 });
                tone(t, { f0: 900, f1: 500, dur: .012, gain: .14 });
                burst(t + .012, { f: 2600, q: 2, dur: .005, gain: .26 });
            },
            up(t) { burst(t, { f: 2800, q: 2, dur: .003, gain: .1 }); },
        },
        tape: {                    // tape-deck key: heavy ka-chunk, then the latch lets go
            down(t) {
                tone(t, { f0: 120, f1: 55, dur: .09, gain: .55, type: "triangle" });
                burst(t, { f: 800, q: .8, type: "lowpass", dur: .02, gain: .35 });
                ring(t + .012, { f: 2000, q: 15, dur: .06, gain: .08 });
            },
            up(t) { ring(t, { f: 1800, q: 12, dur: .05, gain: .06 }); tone(t, { f0: 90, f1: 70, dur: .03, gain: .15 }); },
        },
    };

    // ---- slider scrape: filtered noise that follows drag speed ----------
    function slide(profile) {
        const src = ctx.createBufferSource(); src.buffer = noise; src.loop = true;
        const filter = ctx.createBiquadFilter(); filter.type = "bandpass"; filter.frequency.value = profile.f; filter.Q.value = profile.q;
        const g = ctx.createGain(); g.gain.value = 0;
        src.connect(filter).connect(g).connect(out);
        src.start(0, Math.random() * 1.5);
        let idle = 0;
        const controller = {
            dead: false,
            move(speed) {
                if (controller.dead) return;
                const x = Math.min(1, speed / profile.vmax), now = ctx.currentTime;
                g.gain.setTargetAtTime(profile.gain * Math.pow(x, .7), now, .03);
                filter.frequency.setTargetAtTime(profile.f * (.8 + .8 * x), now, .04);
                clearTimeout(idle);
                idle = setTimeout(controller.stop, 110);
            },
            stop() {
                if (controller.dead) return;
                controller.dead = true; clearTimeout(idle); liveSlides.delete(controller);
                g.gain.setTargetAtTime(0, ctx.currentTime, .025);
                setTimeout(() => { try { src.stop(); src.disconnect(); } catch { /* already stopped */ } }, 200);
            },
        };
        liveSlides.add(controller);
        return controller;
    }

    return {
        tick: (voice, velocity = 1, t) => withLevel(TICK_LEVEL[voice] ?? 1, () => (ticks[voice] || ticks.rubber)(when(t), velocity)),
        stop: (kind, t) => (stops[kind] || stops.knob)(when(t)),
        press: (voice, on, t) => withLevel(PRESS_LEVEL[voice] ?? 1, () => (presses[voice] || presses.rocker)(when(t), !!on)),
        deck(sound, hadPrevious, t) {
            const voice = decks[sound] || decks.key, at = when(t);
            withLevel(DECK_LEVEL[sound] ?? 1, () => {
                voice.down(at);
                if (hadPrevious) voice.up(at + .045);
            });
        },
        slide: voice => slide(SLIDE[voice] || SLIDE.fader),
        voices: { ticks: Object.keys(ticks), presses: Object.keys(presses), stops: Object.keys(stops), decks: Object.keys(decks) },
    };
}

// ---------------------------------------------------------------------------
// Live engine
// ---------------------------------------------------------------------------

let ctx = null, bank = null;
function audio() {
    if (muted) return null;
    if (!bank) {
        const Context = globalThis.AudioContext || globalThis.webkitAudioContext;
        if (!Context) return null;
        try {
            ctx = new Context({ latencyHint: "interactive" });
            const master = ctx.createGain(); master.gain.value = .85;
            const limiter = ctx.createDynamicsCompressor();
            limiter.threshold.value = -14; limiter.knee.value = 10; limiter.ratio.value = 6;
            limiter.attack.value = .002; limiter.release.value = .09;
            master.connect(limiter).connect(ctx.destination);
            bank = createBank(ctx, master);
        } catch { ctx = bank = null; return null; }
    }
    if (ctx.state !== "running") ctx.resume?.().catch(() => { /* needs a user gesture; the next one retries */ });
    return bank;
}

export function playSwitch(styleKey, on) {
    audio()?.press(switchVoice(styleKey), on);
}

// `sound` is a deck style's sound name; `hadPrevious` adds the release of the button that popped out.
export function playDeck(sound, hadPrevious) {
    audio()?.deck(sound, hadPrevious);
}

// One controller per Knob node. The UI reports every user-driven value change as a move between
// dial positions (0..1 along a sweep, turns on an endless knob); the controller turns that into
// detent ticks, slider scrape and end-stop thuds.
export function createKnobFeel(styleKey, isSlider) {
    let lastAt = 0, lastTick = 0, atStop = false, scrape = null;
    return {
        move(from, to, { stop = false } = {}) {
            const sound = audio();
            if (!sound) return;
            const slider = isSlider(), voice = knobVoice(styleKey(), slider);
            const now = performance.now(), dt = Math.max(1, now - lastAt);
            lastAt = now;
            const speed = Math.abs(to - from) / dt * 1000;
            const velocity = Math.max(.5, Math.min(1.2, .5 + Math.min(speed, 2.5) * .28));
            if (slider && SLIDE[voice]) {
                if (!scrape || scrape.dead) scrape = sound.slide(voice);
                scrape.move(speed);
            }
            const n = slider ? SLIDER_DETENTS : KNOB_DETENTS;
            const crossed = Math.abs(Math.floor(to * n) - Math.floor(from * n));
            if (crossed && now - lastTick >= MIN_TICK_GAP_MS) {
                lastTick = now;
                sound.tick(voice, velocity);
                if (crossed > 2 && !slider) sound.tick(voice, velocity * .7, ctx.currentTime + .007);
            }
            if (voice === "pan" && (from - .5) * (to - .5) < 0) {
                sound.press("pill", true);   // centre detent: a small decisive tap
            }
            if (stop && !atStop) sound.stop(slider ? "slider" : "knob");
            atStop = stop;
        },
        end() {
            scrape?.stop();
            scrape = null;
            atStop = false;
        },
    };
}
