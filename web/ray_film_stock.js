import { app } from "../../scripts/app.js";

const NODE_NAME = "RayFilmStock";

const KIND_BY_FILE = {
    lut_file: "lut",
    xmp_file: "xmp",
};
const FILE_TO_FOLDER = {
    lut_file: "lut_folder",
    xmp_file: "xmp_folder",
};
const NONE = "(none)";

function getWidget(node, name) {
    return node.widgets?.find((w) => w.name === name);
}

async function fetchList(kind, folder) {
    try {
        const url = `/ray_film_stock/list?kind=${encodeURIComponent(kind)}&folder=${encodeURIComponent(folder)}`;
        const r = await fetch(url);
        const j = await r.json();
        return Array.isArray(j.files) ? j.files : [];
    } catch {
        return [];
    }
}

/**
 * Convert a STRING widget into a combo dropdown of files plus a "(none)"
 * sentinel. Re-runs each time the corresponding folder changes.
 */
function rebuildAsDropdown(node, fileWidgetName, files) {
    const w = getWidget(node, fileWidgetName);
    if (!w) return;
    const values = [NONE, ...files];
    // Preserve current selection if still valid; else fall back to NONE.
    const prev = w.value;
    w.options = w.options || {};
    w.options.values = values;
    // Switch widget visual type to combo if it's currently a text input.
    // STRING widgets register as `text` by default; mutate `type` and add a
    // `callback` so LiteGraph + Vue both render a dropdown.
    if (w.type !== "combo") {
        w.__rfsOrigType = w.__rfsOrigType ?? w.type;
        w.type = "combo";
    }
    w.value = values.includes(prev) ? prev : NONE;
    node.setDirtyCanvas?.(true, true);
}

async function refreshDropdown(node, fileWidgetName) {
    const kind = KIND_BY_FILE[fileWidgetName];
    const folderW = getWidget(node, FILE_TO_FOLDER[fileWidgetName]);
    const folder = (folderW?.value || "").trim();
    if (!folder) {
        rebuildAsDropdown(node, fileWidgetName, []);
        return;
    }
    const files = await fetchList(kind, folder);
    rebuildAsDropdown(node, fileWidgetName, files);
}

function wireFolderToFile(node, folderName, fileName) {
    const folderW = getWidget(node, folderName);
    if (!folderW) return;
    const orig = folderW.callback;
    let debounceTimer = null;
    folderW.callback = function (v) {
        const r = orig?.apply(this, arguments);
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => refreshDropdown(node, fileName), 350);
        return r;
    };
}

function bootstrap(node) {
    wireFolderToFile(node, "lut_folder", "lut_file");
    wireFolderToFile(node, "xmp_folder", "xmp_file");
    // Initial population — covers workflows loaded from disk where the
    // folder text widget already has a value.
    refreshDropdown(node, "lut_file");
    refreshDropdown(node, "xmp_file");
}

app.registerExtension({
    name: "Ray.FilmStock",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== NODE_NAME) return;
        const origCreate = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const r = origCreate?.apply(this, arguments);
            try {
                bootstrap(this);
            } catch (e) {
                console.error("[RayFilmStock] bootstrap error:", e);
            }
            return r;
        };
        const origConf = nodeType.prototype.onConfigure;
        nodeType.prototype.onConfigure = function () {
            const r = origConf?.apply(this, arguments);
            try {
                refreshDropdown(this, "lut_file");
                refreshDropdown(this, "xmp_file");
            } catch (e) {
                console.error("[RayFilmStock] onConfigure error:", e);
            }
            return r;
        };
    },
});
