import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

// Browse: the folder and file icons in the Ray panels. A web page is never told where a picked file lives, so
// the ComfyUI server shows the dialog (browse_routes.py) and the path it sends back goes into the widget.

export const IMAGE_FILTERS = [["Images", ["png", "jpg", "jpeg", "webp", "bmp", "tif", "tiff", "gif"]]];

export function notify(message) {
    const toast = app?.extensionManager?.toast;
    if (toast?.add) toast.add({ severity: "warn", summary: "Browse", detail: message, life: 6000 });
    else console.warn(`[Ray] ${message}`);
}

// Resolves to the chosen path, or null when the dialog was closed without choosing. Rejects with a message
// fit to show the user.
export async function browsePath(kind, initial, { title, filters } = {}) {
    let response;
    try {
        response = await api.fetchApi("/ray/browse", {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ kind, initial: initial ?? "", title, filters }),
        });
    } catch (error) {
        throw new Error("Could not reach ComfyUI to open the dialog.");
    }
    let data = {};
    try { data = await response.json(); } catch { /* an empty or non-JSON error body */ }
    if (!response.ok || data.ok === false) throw new Error(data.error || `The file dialog could not be opened (${response.status}).`);
    return data.cancelled ? null : (data.path || null);
}

const linked = (node, name) => !!node.inputs?.some(input => (input.widget?.name === name || input.name === name) && input.link != null);

// Chooses a path with the system dialog and writes it into `target` (a widget name), the way typing it would.
// Used by the button below and by Save Image's own toolbar.
export async function browseInto(node, targetName, { kind = "folder", title, filters } = {}) {
    const target = node.widgets?.find(w => w.name === targetName);
    if (!target) return false;
    if (linked(node, targetName)) { notify(`${targetName} is driven by a link, so there is nothing to browse.`); return false; }
    try {
        const picked = await browsePath(kind, String(target.value ?? ""), { title, filters });
        if (!picked) return false;
        const graph = node.graph;
        graph?.beforeChange?.();
        try {
            target.value = picked;
            target.callback?.(picked, app.canvas, node, undefined, undefined);
        } finally { graph?.afterChange?.(); }
        node.setDirtyCanvas?.(true, true);
        return true;
    } catch (error) {
        notify(error.message);
        return false;
    }
}
