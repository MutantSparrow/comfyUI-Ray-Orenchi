const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");
let extension;
const file = process.argv[2] || path.join(__dirname, "..", "web", "ray_vhs.js");
const source = fs.readFileSync(file, "utf8").replace(/^import .*;\r?\n/gm, "").replace(/^export /gm, "");
vm.runInNewContext(source, {app: {registerExtension: x => extension = x}});
const migrate = data => extension.beforeConfigureGraph(data);
const head = ["Worn EP", -1, -1, -1, -1, -1, -1];

// An old workflow: PLAY in the top right, then a REC, a date and a date with time.
const play = {type: "RayVHS", widgets_values: [...head, "▶ PLAY", "TR", "", 42, "randomize"],
              inputs: [{name: "image", link: 3}, {name: "osd_mode", link: null}, {name: "osd_corner", link: null}]};
migrate({nodes: [play]});
assert.deepEqual(Array.from(play.widgets_values), [...head, 0, "▶ PLAY", "TR", "Off", "TR", "", "White", 42, "randomize"]);
assert.deepEqual(play.inputs.map(i => i.name), ["image"]);

const rec = {type: "RayVHS", widgets_values: [...head, "● REC", "BL", "", 1, "fixed"]};
migrate({nodes: [rec]});
assert.deepEqual(Array.from(rec.widgets_values.slice(7)), [0, "● REC", "BL", "Off", "BL", "", "White", 1, "fixed"]);

const date = {type: "RayVHS", widgets_values: [...head, "Date", "BR", "1987 06 05", 7, "fixed"]};
migrate({nodes: [date]});
assert.deepEqual(Array.from(date.widgets_values.slice(7)), [0, "Off", "BR", "Date", "BR", "1987 06 05", "White", 7, "fixed"]);

const both = {type: "RayVHS", widgets_values: [...head, "Date+Time", "TL", "", 7, "fixed"]};
migrate({nodes: [both]});
assert.deepEqual(Array.from(both.widgets_values.slice(7, 11)), [0, "Off", "TL", "Date+Time"]);

const off = {type: "RayVHS", widgets_values: [...head, "Off", "BL", "", 0, "fixed"]};
migrate({nodes: [off]});
assert.deepEqual(Array.from(off.widgets_values.slice(7, 11)), [0, "Off", "BL", "Off"]);

// A linked old input is kept, and running the migration again changes nothing.
const linked = {type: "RayVHS", widgets_values: [...head, "Off", "BL", "", 0, "fixed"], inputs: [{name: "osd_mode", link: 9}]};
migrate({nodes: [linked]});
assert.equal(linked.inputs.length, 1);
const saved = JSON.stringify([play, rec, date, both, off]);
migrate({nodes: [play, rec, date, both, off]});
assert.equal(JSON.stringify([play, rec, date, both, off]), saved);

// Subgraphs migrate too, and other nodes are left alone.
const inner = {type: "RayVHS", widgets_values: [...head, "● REC", "TL", "", 5, "fixed"]};
const other = {type: "RayCRT", widgets_values: [...head, "● REC", "TL", "", 5, "fixed"]};
const before = JSON.stringify(other);
migrate({nodes: [other], definitions: {subgraphs: [{nodes: [inner]}]}});
assert.equal(inner.widgets_values[8], "● REC");
assert.equal(JSON.stringify(other), before);

// A node with no saved values, and an odd corner, never throw.
migrate({nodes: [{type: "RayVHS"}, {type: "RayVHS", widgets_values: []}]});
const odd = {type: "RayVHS", widgets_values: [...head, "Date", undefined, undefined]};
migrate({nodes: [odd]});
assert.equal(odd.widgets_values[9], "BL");
console.log("vhs migration ok");
