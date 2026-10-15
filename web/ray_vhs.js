import { app } from "../../scripts/app.js";

const STATUS = { "▶ PLAY": "▶ PLAY", "● REC": "● REC" };
const STAMP = { "Date": "Date", "Date+Time": "Date+Time" };
const OLD_INPUTS = new Set(["osd_mode", "osd_corner"]);

// Older workflows saved one OSD line as `osd_mode`, `osd_corner`, `osd_date`. The node now has a status line
// and a date / time stamp with a corner each, a colour and an effect fade, so the saved values move to the
// matching widgets: a PLAY or REC mode becomes the status, a Date mode the stamp, and both take the old
// corner. A workflow already on the new layout has a number (the fade) where the old mode was, so it is
// left alone.
export function migrateVhsOsd(data) {
    for (const node of data?.nodes || []) {
        if (node?.type !== "RayVHS") continue;
        const values = node.widgets_values;
        if (!Array.isArray(values) || typeof values[7] !== "string") continue;
        const [mode, corner, date] = [values[7], values[8], values[9]];
        const where = typeof corner === "string" ? corner : "BL";
        values.splice(7, 3, 0, STATUS[mode] || "Off", where, STAMP[mode] || "Off", where, date ?? "", "White");
        if (Array.isArray(node.inputs)) {
            node.inputs = node.inputs.filter(input => !(OLD_INPUTS.has(input?.name) && input.link == null));
        }
    }
    for (const subgraph of data?.definitions?.subgraphs || []) migrateVhsOsd(subgraph);
}

app.registerExtension({
    name: "Ray.VHS",
    beforeConfigureGraph(data) { migrateVhsOsd(data); },
});
