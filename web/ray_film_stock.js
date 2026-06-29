import { app } from "../../scripts/app.js";

const NODE_NAME = "RayFilmStock";
const FOLDER_WIDGET = "assets_folder";
const FILE_WIDGET = "asset_file";
const NONE = "(none)";

function getWidget(node, name) {
    return node.widgets?.find((w) => w.name === name);
}

async function fetchAssets(folder) {
    try {
        const url = `/ray_film_stock/list?folder=${encodeURIComponent(folder)}`;
        const r = await fetch(url);
        const j = await r.json();
        return Array.isArray(j.files) ? j.files : [];
    } catch {
        return [];
    }
}

/**
 * Update the asset_file dropdown's choice list with the supplied entries.
 * The widget is already a combo (declared as such in INPUT_TYPES so Vue and
 * LiteGraph both render a real dropdown). We only swap the values array and
 * preserve the current selection when still valid.
 *
 * When the folder contains both LUTs and XMPs the entries are pre-tagged
 * `[LUT] …` / `[XMP] …`; otherwise they're plain relative paths. Subfolder
 * paths are kept verbatim so the dropdown navigates by directory.
 */
function rebuildDropdown(node, files) {
    const w = getWidget(node, FILE_WIDGET);
    if (!w) return;
    const values = [NONE, ...files];
    const prev = w.value;
    w.options = w.options || {};
    w.options.values = values;
    w.value = values.includes(prev) ? prev : NONE;
    node.setDirtyCanvas?.(true, true);
}

async function refresh(node) {
    const folderW = getWidget(node, FOLDER_WIDGET);
    const folder = (folderW?.value || "").trim();
    if (!folder) {
        rebuildDropdown(node, []);
        return;
    }
    const files = await fetchAssets(folder);
    rebuildDropdown(node, files);
}

function wireFolderListener(node) {
    const folderW = getWidget(node, FOLDER_WIDGET);
    if (!folderW) return;
    const orig = folderW.callback;
    let debounceTimer = null;
    folderW.callback = function (v) {
        const r = orig?.apply(this, arguments);
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => refresh(node), 350);
        return r;
    };
}

function bootstrap(node) {
    wireFolderListener(node);
    refresh(node);
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
                refresh(this);
            } catch (e) {
                console.error("[RayFilmStock] onConfigure error:", e);
            }
            return r;
        };
    },
});
