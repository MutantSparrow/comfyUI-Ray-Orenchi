import { app } from "../../scripts/app.js";
import {
    applyBucketTint,
    shiftTint,
    RAY_PALETTE,
    setWidgetHidden as commonSetHidden,
    findWidget as getWidget,
} from "./_common.js";

const NODE_NAME = "RayPromptLibrary";

const MODE_SAVE = "Save";
const MODE_BROWSE = "Browse";
const MODE_LEGACY_FETCH = "Fetch";

const MODE_PREFIX = {
    [MODE_SAVE]: "save__",
    [MODE_BROWSE]: "browse__",
};
const ALWAYS_VISIBLE = new Set(["mode", "prompt_in", "seed"]);
// Hidden state widgets — mounted in the widget list for serialization,
// never shown in the panel (the DOM widget drives them).
const NEVER_VISIBLE = new Set(["browse__selected_id", "browse__last_query"]);

const SORT_OPTIONS = [
    ["most_recent", "Most recent"],
    ["oldest", "Oldest"],
    ["longest", "Longest"],
    ["shortest", "Shortest"],
    ["source", "Source (A→Z)"],
    ["similarity", "Similarity (embed)"],
];

function setWidgetHidden(widget, hidden) {
    // node isn't available in every call site here; commonSetHidden's
    // second arg is the widget itself, and it handles null-node gracefully.
    commonSetHidden(null, widget, hidden);
}

function normalizeMode(v) {
    if (v === MODE_LEGACY_FETCH) return MODE_BROWSE;
    if (v === MODE_SAVE || v === MODE_BROWSE) return v;
    return MODE_BROWSE;
}

function applyMode(node, mode) {
    const m = normalizeMode(mode);
    const keep = MODE_PREFIX[m] || MODE_PREFIX[MODE_BROWSE];
    for (const w of node.widgets || []) {
        if (ALWAYS_VISIBLE.has(w.name)) {
            setWidgetHidden(w, false);
            continue;
        }
        if (w.name === "ray_pl_status" || w.name === "ray_pl_panel") continue;
        if (NEVER_VISIBLE.has(w.name)) {
            setWidgetHidden(w, true);
            continue;
        }
        setWidgetHidden(w, !w.name?.startsWith(keep));
    }
    if (node._rplPanelEl) {
        node._rplPanelEl.style.display = (m === MODE_BROWSE) ? "" : "none";
    }
    applyModeStyling(node, m);
    if (typeof node.computeSize === "function") {
        const sz = node.computeSize();
        if (Array.isArray(node.size)) node.size[1] = sz[1];
        node.setSize?.([Array.isArray(node.size) ? node.size[0] : sz[0], sz[1]]);
    }
    node.setDirtyCanvas?.(true, true);
}

function applyModeStyling(node, mode) {
    // LLM bucket base tint; Save mode gets a warm hue shift.
    applyBucketTint(node, "LLM");
    if (mode === MODE_SAVE) {
        node.bgcolor = shiftTint(RAY_PALETTE.LLM.bg, 150);
        node.color = shiftTint(RAY_PALETTE.LLM.edge, 150);
    }
}

async function fetchJSON(url) {
    try {
        const r = await fetch(url);
        return await r.json();
    } catch (e) {
        return { error: String(e) };
    }
}

async function fetchStats() {
    return await fetchJSON("/ray_prompt_library/stats");
}

async function fetchSources() {
    const j = await fetchJSON("/ray_prompt_library/sources");
    return Array.isArray(j.sources) ? j.sources : [];
}

async function searchRows({ q, source, tag, sort, limit, offset }) {
    const params = new URLSearchParams();
    if (q) params.set("q", q);
    if (source) params.set("source", source);
    if (tag) params.set("tag", tag);
    if (sort) params.set("sort", sort);
    if (limit != null) params.set("limit", String(limit));
    if (offset != null) params.set("offset", String(offset));
    return await fetchJSON(`/ray_prompt_library/search?${params}`);
}

function injectStatusWidget(node) {
    if (node._rplStatusEl) return node._rplStatusEl;
    const el = document.createElement("div");
    el.style.cssText =
        "padding:2px 6px;font-size:10px;color:#aaa;min-height:14px;";
    el.textContent = "";
    if (typeof node.addDOMWidget === "function") {
        node.addDOMWidget("ray_pl_status", "RAY_PL_STATUS", el, {
            serialize: false,
            hideOnZoom: false,
            getMinHeight: () => 18,
            getHeight: () => 18,
        });
    }
    node._rplStatusEl = el;
    return el;
}

async function refreshStatus(node, statusEl) {
    const s = await fetchStats();
    if (s.error) {
        statusEl.textContent = `library: ${s.error}`;
        return;
    }
    const emb = s.embeddings_available ? "embed-on" : "embed-off";
    statusEl.textContent =
        `${s.total ?? 0} prompts · ${(s.sources ?? []).length} sources · ${emb}`;
}

function fmtCreated(ts) {
    if (!ts) return "";
    // sqlite CURRENT_TIMESTAMP returns "YYYY-MM-DD HH:MM:SS" (UTC-ish).
    const s = String(ts).replace("T", " ").replace("Z", "");
    return s.slice(0, 16);
}

function esc(s) {
    return String(s ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
}

function buildPanelDOM() {
    const wrap = document.createElement("div");
    wrap.className = "ray-pl-panel";
    wrap.style.cssText = [
        "display:flex", "flex-direction:column", "gap:4px",
        "padding:4px 6px", "font-family:system-ui,sans-serif",
        "font-size:11px", "color:#ddd",
        "background:#141a1a", "border:1px solid #2a4444",
        "border-radius:4px", "min-height:280px", "overflow:hidden",
    ].join(";");

    const controls = document.createElement("div");
    controls.style.cssText = "display:grid;grid-template-columns:1fr 1fr;gap:4px;";
    const search = document.createElement("input");
    search.type = "text";
    search.placeholder = "search prompt text…";
    search.className = "ray-pl-search";
    const tag = document.createElement("input");
    tag.type = "text";
    tag.placeholder = "tag substring";
    tag.className = "ray-pl-tag";
    const source = document.createElement("select");
    source.className = "ray-pl-source";
    const sort = document.createElement("select");
    sort.className = "ray-pl-sort";
    for (const [val, label] of SORT_OPTIONS) {
        const o = document.createElement("option");
        o.value = val;
        o.textContent = label;
        sort.appendChild(o);
    }
    const inputCss = [
        "background:#0d1414", "color:#ddd",
        "border:1px solid #345", "border-radius:3px",
        "padding:2px 4px", "font:inherit",
    ].join(";");
    for (const el of [search, tag, source, sort]) el.style.cssText = inputCss;
    controls.appendChild(search);
    controls.appendChild(tag);
    controls.appendChild(source);
    controls.appendChild(sort);
    wrap.appendChild(controls);

    const meta = document.createElement("div");
    meta.className = "ray-pl-meta";
    meta.style.cssText =
        "display:flex;justify-content:space-between;font-size:10px;color:#7ac;";
    meta.innerHTML = `<span class="ray-pl-count">…</span>
        <span class="ray-pl-selected">no row selected</span>`;
    wrap.appendChild(meta);

    const tableWrap = document.createElement("div");
    tableWrap.style.cssText =
        "flex:1;min-height:180px;max-height:400px;overflow:auto;" +
        "border:1px solid #2a4444;border-radius:3px;background:#0a1010;";
    const table = document.createElement("table");
    table.className = "ray-pl-table";
    table.style.cssText =
        "width:100%;border-collapse:collapse;font-family:ui-monospace,monospace;" +
        "font-size:10px;color:#cde;";
    const thead = document.createElement("thead");
    thead.innerHTML = `
        <tr style="position:sticky;top:0;background:#152020;">
            <th data-sort="none"          style="text-align:left;padding:3px 4px;border-bottom:1px solid #345;cursor:default;">Prompt</th>
            <th data-sort="source"        style="text-align:left;padding:3px 4px;border-bottom:1px solid #345;cursor:pointer;">Source</th>
            <th data-sort="none"          style="text-align:left;padding:3px 4px;border-bottom:1px solid #345;">Tags</th>
            <th data-sort="length"        style="text-align:right;padding:3px 4px;border-bottom:1px solid #345;cursor:pointer;">Len</th>
            <th data-sort="created"       style="text-align:left;padding:3px 4px;border-bottom:1px solid #345;cursor:pointer;">Created</th>
            <th data-sort="none"          style="text-align:left;padding:3px 4px;border-bottom:1px solid #345;">Model</th>
            <th data-sort="none"          style="text-align:right;padding:3px 4px;border-bottom:1px solid #345;">Seed</th>
        </tr>`;
    const tbody = document.createElement("tbody");
    tbody.className = "ray-pl-tbody";
    table.appendChild(thead);
    table.appendChild(tbody);
    tableWrap.appendChild(table);
    wrap.appendChild(tableWrap);

    const clearBtn = document.createElement("button");
    clearBtn.textContent = "Clear selection";
    clearBtn.className = "ray-pl-clear";
    clearBtn.style.cssText =
        "align-self:flex-end;padding:2px 8px;background:#231818;color:#fcc;" +
        "border:1px solid #533;border-radius:3px;cursor:pointer;font:inherit;";
    wrap.appendChild(clearBtn);

    return { wrap, search, tag, source, sort, tbody, meta, thead, clearBtn };
}

function renderRows(tbody, rows, selectedId) {
    tbody.textContent = "";
    if (!rows || rows.length === 0) {
        const tr = document.createElement("tr");
        tr.innerHTML =
            `<td colspan="7" style="padding:12px;text-align:center;color:#678;">no rows</td>`;
        tbody.appendChild(tr);
        return;
    }
    for (const r of rows) {
        const tr = document.createElement("tr");
        tr.dataset.id = String(r.id);
        const active = (r.id === selectedId);
        tr.style.cssText =
            `background:${active ? "#264040" : "transparent"};cursor:pointer;`;
        const full = r.prompt || "";
        const preview = r.prompt_preview || full;
        tr.innerHTML = `
            <td title="${esc(full)}" style="padding:2px 4px;max-width:340px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${esc(preview)}</td>
            <td style="padding:2px 4px;color:#8bd;">${esc(r.source || "")}</td>
            <td style="padding:2px 4px;color:#ab8;">${esc(r.tags || "")}</td>
            <td style="padding:2px 4px;text-align:right;color:#89a;">${r.length ?? 0}</td>
            <td style="padding:2px 4px;color:#789;">${esc(fmtCreated(r.created_at))}</td>
            <td style="padding:2px 4px;color:#a9c;">${esc(r.model || "")}</td>
            <td style="padding:2px 4px;text-align:right;color:#789;">${r.seed ?? ""}</td>
        `;
        tr.addEventListener("mouseenter", () => {
            if (!active) tr.style.background = "#1a2828";
        });
        tr.addEventListener("mouseleave", () => {
            if (!active) tr.style.background = "transparent";
        });
        tbody.appendChild(tr);
    }
}

function debounce(fn, ms) {
    let h;
    return function (...a) {
        clearTimeout(h);
        h = setTimeout(() => fn.apply(this, a), ms);
    };
}

function injectBrowsePanel(node) {
    if (node._rplPanelEl) return;
    const dom = buildPanelDOM();
    node._rplPanelEl = dom.wrap;
    node._rplPanelDOM = dom;
    if (typeof node.addDOMWidget === "function") {
        node.addDOMWidget("ray_pl_panel", "RAY_PL_PANEL", dom.wrap, {
            serialize: false,
            hideOnZoom: false,
            getMinHeight: () => 320,
            getHeight: () => 320,
        });
    }

    const idWidget = getWidget(node, "browse__selected_id");
    const queryWidget = getWidget(node, "browse__last_query");

    function selectRow(rowId) {
        const rid = (rowId == null || rowId < 0) ? -1 : Number(rowId);
        if (idWidget) idWidget.value = rid;
        const rows = node._rplLastRows || [];
        const row = rows.find((r) => r.id === rid);
        if (rid < 0) {
            dom.meta.querySelector(".ray-pl-selected").textContent = "no row selected";
        } else {
            const preview = row?.prompt_preview || row?.prompt || `id=${rid}`;
            dom.meta.querySelector(".ray-pl-selected").textContent =
                `selected: ${preview.slice(0, 60)}`;
        }
        // Re-render rows so the highlight tracks.
        renderRows(dom.tbody, rows, rid);
        node.setDirtyCanvas?.(true, true);
        app.graph.change?.();
    }

    async function refresh() {
        const q = dom.search.value.trim();
        const tag = dom.tag.value.trim();
        const source = dom.source.value;
        const sort = dom.sort.value;
        if (queryWidget) queryWidget.value = q;
        const res = await searchRows({
            q, source, tag, sort, limit: 200, offset: 0,
        });
        if (res.error) {
            dom.meta.querySelector(".ray-pl-count").textContent =
                `error: ${res.error}`;
            return;
        }
        node._rplLastRows = res.rows || [];
        dom.meta.querySelector(".ray-pl-count").textContent =
            `${res.rows?.length ?? 0} / ${res.total ?? 0} (${res.used || ""})`;
        const currentSel = idWidget ? Number(idWidget.value) : -1;
        renderRows(dom.tbody, node._rplLastRows, currentSel);
    }

    node._rplRefresh = refresh;

    dom.search.addEventListener("input", debounce(refresh, 200));
    dom.tag.addEventListener("input", debounce(refresh, 200));
    dom.source.addEventListener("change", refresh);
    dom.sort.addEventListener("change", refresh);

    dom.tbody.addEventListener("click", (e) => {
        const tr = e.target?.closest?.("tr[data-id]");
        if (!tr) return;
        selectRow(Number(tr.dataset.id));
    });

    dom.thead.addEventListener("click", (e) => {
        const th = e.target?.closest?.("th[data-sort]");
        if (!th || th.dataset.sort === "none") return;
        const key = th.dataset.sort;
        const map = {
            source: "source",
            length: "longest",
            created: "most_recent",
        };
        const target = map[key];
        if (target) {
            dom.sort.value = target;
            refresh();
        }
    });

    dom.clearBtn.addEventListener("click", () => selectRow(-1));

    // Populate sources dropdown async.
    fetchSources().then((srcs) => {
        dom.source.innerHTML = "";
        const any = document.createElement("option");
        any.value = "";
        any.textContent = "any source";
        dom.source.appendChild(any);
        for (const s of srcs) {
            const o = document.createElement("option");
            o.value = s;
            o.textContent = s;
            dom.source.appendChild(o);
        }
    });

    // Restore any persisted search text.
    if (queryWidget?.value) dom.search.value = String(queryWidget.value);

    // Initial rows.
    refresh();
}

function bootstrap(node) {
    const statusEl = injectStatusWidget(node);
    refreshStatus(node, statusEl);
    injectBrowsePanel(node);

    const modeW = getWidget(node, "mode");
    if (!modeW) return;
    // Migrate legacy Fetch value.
    if (modeW.value === MODE_LEGACY_FETCH) modeW.value = MODE_BROWSE;
    applyMode(node, modeW.value);
    const orig = modeW.callback;
    modeW.callback = function (v) {
        const r = orig?.apply(this, arguments);
        applyMode(node, v);
        return r;
    };
}

app.registerExtension({
    name: "Ray.PromptLibrary",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== NODE_NAME) return;
        const origCreate = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const r = origCreate?.apply(this, arguments);
            try {
                bootstrap(this);
            } catch (e) {
                console.error("[RayPromptLibrary] bootstrap error:", e);
            }
            return r;
        };
        const origConf = nodeType.prototype.onConfigure;
        nodeType.prototype.onConfigure = function () {
            const r = origConf?.apply(this, arguments);
            try {
                const modeW = getWidget(this, "mode");
                if (modeW) {
                    if (modeW.value === MODE_LEGACY_FETCH) modeW.value = MODE_BROWSE;
                    applyMode(this, modeW.value);
                }
                // Re-refresh the table so persisted selection re-highlights.
                if (typeof this._rplRefresh === "function") {
                    this._rplRefresh();
                }
            } catch (e) {
                console.error("[RayPromptLibrary] onConfigure error:", e);
            }
            return r;
        };
    },
});
