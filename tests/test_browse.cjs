// Unit test of web/browse_common.js against a stubbed ComfyUI: node tests/test_browse.cjs
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");

const file = process.argv[2] || path.join(__dirname, "..", "web", "browse_common.js");
const source = fs.readFileSync(file, "utf8").replace(/^import .*;\r?\n/gm, "").replace(/^export /gm, "");

const toasts = [], requests = [];
let reply = () => ({ ok: true, status: 200, json: async () => ({ ok: true, cancelled: true }) });
const context = {
    console: { warn() {}, log() {} },
    app: { canvas: {}, extensionManager: { toast: { add: t => toasts.push(t) } } },
    api: { fetchApi: async (url, options) => { requests.push({ url, body: JSON.parse(options.body), options }); return reply(); } },
};
vm.createContext(context);
vm.runInContext(source + "\nthis.browsePath = browsePath; this.browseInto = browseInto; this.IMAGE_FILTERS = IMAGE_FILTERS;", context);
const { browsePath, browseInto, IMAGE_FILTERS } = context;

function makeNode(widgets = ["folder", "recurse", "limit"], inputs = []) {
    const node = {
        widgets: widgets.map(name => ({ name, value: name === "folder" ? "C:/start" : 1, callback(v) { this.seen = v; } })),
        inputs, history: [], dirty: 0,
        graph: { before: 0, after: 0, beforeChange() { this.before++; }, afterChange() { this.after++; } },
        addWidget(type, name, value, callback, options) { const w = { type, name, value, callback, options }; this.widgets.push(w); return w; },
        setDirtyCanvas() { this.dirty++; },
    };
    return node;
}
const answer = body => { reply = () => ({ ok: true, status: 200, json: async () => body }); };
const failWith = (status, body) => { reply = () => ({ ok: false, status, json: async () => body }); };

(async () => {
    // ---- browsePath ----
    answer({ ok: true, path: "D:/Pictures" });
    assert.equal(await browsePath("folder", "C:/x", { title: "T", filters: IMAGE_FILTERS }), "D:/Pictures");
    assert.equal(requests.at(-1).url, "/ray/browse");
    assert.equal(JSON.stringify(requests.at(-1).body), JSON.stringify({ kind: "folder", initial: "C:/x", title: "T", filters: IMAGE_FILTERS }));
    assert.equal(requests.at(-1).options.method, "POST");
    assert.equal(requests.at(-1).options.headers["Content-Type"], "application/json");
    answer({ ok: true, cancelled: true });
    assert.equal(await browsePath("file", null), null);
    assert.equal(requests.at(-1).body.initial, "");
    failWith(403, { ok: false, error: "Browse only works when ComfyUI runs on this computer. Type the path instead." });
    await assert.rejects(browsePath("folder", ""), /runs on this computer/);
    failWith(500, null);
    reply = () => ({ ok: false, status: 500, json: async () => { throw new Error("not json"); } });
    await assert.rejects(browsePath("folder", ""), /could not be opened \(500\)/);
    api_down: {
        const real = context.api.fetchApi;
        context.api.fetchApi = async () => { throw new TypeError("Failed to fetch"); };
        await assert.rejects(browsePath("folder", ""), /Could not reach ComfyUI/);
        context.api.fetchApi = real;
    }
    answer({ ok: true });
    assert.equal(await browsePath("folder", ""), null);

    // browseInto writes the chosen path into a widget, the way typing it would
    assert.equal(await browseInto(makeNode(["nothing"]), "folder"), false);
    answer({ ok: true, path: "G:/y" });
    const plain = makeNode();
    assert.equal(await browseInto(plain, "folder", { kind: "folder" }), true);
    assert.equal(plain.widgets[0].value, "G:/y");

    // a missing toast service falls back to the console instead of throwing
    context.app.extensionManager = undefined;
    failWith(500, { ok: false, error: "boom" });
    assert.equal(await browseInto(makeNode(), "folder"), false);

    console.log("browse helper ok");
})().catch(error => { console.error(error); process.exit(1); });
