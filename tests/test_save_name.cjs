// The browser half of the Save Image filename builder: node tests/test_save_name.cjs
// Runs the cases shared with the Python implementation (tests/filename_cases.json), so the live preview and the
// server cannot disagree about a name.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");

const file = process.argv[2] || path.join(__dirname, "..", "web", "save_name.js");
const source = fs.readFileSync(file, "utf8").replace(/^import .*;\r?\n/gm, "").replace(/^export /gm, "");
const context = { app: { canvas: {} }, console, document: undefined, window: undefined };
vm.createContext(context);
vm.runInContext(source + "\nthis.api = { parseTemplate, renderStem, cleanText, cleanValue, finishStem, listWidgets, resolveWidgetTokens, installNameBuilder, TemplateError, DEFAULT_TEMPLATE };", context);
const api = context.api;

const cases = JSON.parse(fs.readFileSync(path.join(__dirname, "filename_cases.json"), "utf8"));
const c = cases.context;
const [date, time] = c.now.split("T");
const [y, mo, d] = date.split("-").map(Number), [h, mi, s] = time.split(":").map(Number);
const ctx = { now: new Date(y, mo - 1, d, h, mi, s), index: c.index, input: c.input, hash: c.hash, widgets: (node, name) => c.widgets[`${node}.${name}`] ?? null };

// ---- the shared cases ----
let count = 0;
for (const [template, expected] of cases.render) {
    const got = api.renderStem(api.parseTemplate(template), ctx, c.counter);
    assert.equal(got, expected, `render ${JSON.stringify(template.slice(0, 40))}`);
    count++;
}
for (const template of cases.errors) {
    assert.throws(() => api.parseTemplate(template), error => error.name === "TemplateError", `should reject ${template}`);
    count++;
}

// ---- details ----
assert.match(api.renderStem(api.parseTemplate("{timestamp}"), ctx), /^\d{9,11}$/);
assert.equal(api.renderStem(api.parseTemplate("{timestamp}"), ctx), String(Math.floor(ctx.now.getTime() / 1000)));
const random = new Set(Array.from({ length: 20 }, () => api.renderStem(api.parseTemplate("{hash:10}"), { ...ctx, hash: undefined })));
assert.equal(random.size, 20);
assert.ok([...random].every(n => /^[0-9a-f]{10}$/.test(n)));
assert.equal(api.DEFAULT_TEMPLATE, "Ray_{date}_{counter}");
assert.equal(api.renderStem(api.parseTemplate(api.DEFAULT_TEMPLATE), ctx, 3), "Ray_2026-10-16_0003");
assert.equal(api.cleanValue("x".repeat(100)).length, 60);
assert.equal(api.cleanValue("🎨".repeat(100)).length, 120, "limits count characters, not UTF-16 units");
assert.equal(api.renderStem(api.parseTemplate("🎨".repeat(300)), ctx).length, 360);

// ---- the workflow's widgets ----
const widget = (name, value, extra = {}) => ({ name, value, type: typeof value === "number" ? "number" : "text", ...extra });
const nodes = [
    { id: 12, title: "KSampler", widgets: [widget("seed", 42), widget("steps", 20), widget("sampler", "euler")] },
    { id: 7, type: "CLIPTextEncode", widgets: [widget("text", "a cat / a dog?")] },
    { id: 3, title: "Control", widgets: [widget("knob_value", 7.5, { hidden: true }), widget("knob_ui", "", { element: {} }), widget("go", null, { type: "button" }), widget("quiet", "x", { serialize: false })] },
    { id: 4, title: "Browse", widgets: [widget("folder", "C:/x"), widget("📂 Browse", null, { type: "button", isRayBrowse: true })] },
    { id: 9, title: "Empty", widgets: [] },
    { id: 10, title: "Object", widgets: [widget("blob", { a: 1 })] },
];
const save = { id: 20, title: "Save", widgets: [widget("directory", "C:/out"), widget("filename_prefix", "T")] };
const graph = { _nodes: [...nodes, save], getNodeById(id) { return [...nodes, save].find(n => String(n.id) === String(id)) || null; } };
const listed = api.listWidgets(graph, save);
assert.equal(listed.map(n => n.id).join(), "3,4,7,12,20", "sorted by id; empty and object-only nodes are dropped");
assert.deepEqual(listed.find(n => n.id === "3").widgets.map(w => w.name), ["knob_value"], "buttons, DOM faces and unsaved widgets are not offered, but hidden real widgets are");
assert.deepEqual(listed.find(n => n.id === "4").widgets.map(w => w.name), ["folder"]);
assert.deepEqual(listed.find(n => n.id === "20").widgets.map(w => w.name), ["directory"], "the prefix itself is not offered to itself");
assert.equal(listed.find(n => n.id === "7").title, "CLIPTextEncode", "falls back to the node type");

const resolve = template => api.resolveWidgetTokens(template, graph);
assert.equal(resolve("s{widget:12.seed}_{widget:12.sampler}"), "s42_euler");
assert.equal(resolve("{widget:7.text}"), "a_cat_a_dog");
assert.equal(resolve("{widget:7.text|5}"), "a_cat");
assert.equal(resolve("{widget:3.knob_value}"), "7.5", "a hidden widget still has its value");
assert.equal(resolve("{widget:99.seed}-{widget:12.nothing}"), "{widget:99.seed}-{widget:12.nothing}", "unknown targets are left for the server");
assert.equal(resolve("{widget:3.knob_ui}{widget:3.go}"), "{widget:3.knob_ui}{widget:3.go}", "faces and buttons are not values");
assert.equal(resolve("{date}_{counter}_{hash:6}"), "{date}_{counter}_{hash:6}", "other tokens are left to the server");
assert.equal(resolve("no tokens"), "no tokens");
assert.equal(resolve(null), "null");
graph._nodes.push({ id: "12:5", title: "Inside", widgets: [widget("seed", 5)] });
nodes.push(graph._nodes.at(-1));
assert.equal(resolve("{widget:12:5.seed}"), "5", "ids of nodes inside groups contain a colon");
nodes[1].widgets[0].value = "{hash}/../x";
assert.equal(resolve("{widget:7.text}"), "hash_.._x", "a value can never carry a token or a path into the name");

// ---- the button ----
const prefix = widget("filename_prefix", "Ray_{widget:12.seed}");
const host = {
    widgets: [widget("directory", ""), prefix, widget("other", 1)], graph,
    addWidget(type, name, value, callback, options) { const w = { type, name, value, callback, options }; this.widgets.push(w); return w; },
};
const button = api.installNameBuilder(host);
assert.equal(host.widgets.map(w => w.name).join("|"), "directory|filename_prefix|🏷 Build filename…|other", "directly under the prefix");
assert.equal(button.serialize, false);
assert.equal(button.options.serialize, false);
assert.equal(api.installNameBuilder(host), null, "never installed twice");
assert.equal(host.widgets.length, 4);
assert.equal(typeof prefix.serializeValue, "function");
assert.equal(api.installNameBuilder({ widgets: [], addWidget() {} }), null);
assert.equal(api.installNameBuilder({ widgets: [prefix] }), null, "needs a node that can add widgets");

(async () => {
    assert.equal(await prefix.serializeValue(), "Ray_42", "the API prompt gets the value on screen");
    assert.equal(prefix.value, "Ray_{widget:12.seed}", "while the saved workflow keeps the template");
    nodes[0].widgets[0].value = 777;
    assert.equal(await prefix.serializeValue(), "Ray_777", "and it follows the widget");
    console.log(`save name ok (${count} shared cases)`);
})().catch(error => { console.error(error); process.exit(1); });
