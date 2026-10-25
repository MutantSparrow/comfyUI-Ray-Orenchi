// Native sockets stay owned by the frontend. This helper changes only the
// supported legacy widget start and the width of our first content section.
// Nodes 2.0 currently stacks NodeSlots and NodeWidgets in separate flex rows;
// it has no equivalent widget-start hook, so that renderer uses stacked rows.

const finite = value => Number.isFinite(value);
const label = slot => String(slot.label || slot.localized_name || slot.name || "");

export function measureOutputLane(node, root, {
    minContentWidth = 260, gap = 8, measureText, vueNodes = globalThis.LiteGraph?.vueNodesMode,
} = {}) {
    const stacked = reason => ({ mode: "stacked", reason, reserve: 0, start: null, height: 0 });
    if (vueNodes) return stacked("native-renderer-stacks-slots");
    if (!node.graph || !root.isConnected || node.flags?.collapsed) return stacked("not-visible");
    if (!node.outputs?.length || typeof node.getOutputPos !== "function") return stacked("no-output-geometry");
    // Widget-backed, unlinked inputs have no independent row in this renderer.
    // Actual data inputs and linked widgets must keep their native column clear.
    if (node.inputs?.some((slot, index) => !slot.widget || node.isInputConnected?.(index) || slot.link != null))
        return stacked("native-input-column");
    const visible = (node.getLayoutWidgets?.() || node.widgets || []).filter(widget => !widget.hidden);
    if (visible.length && visible[0].element !== root && !visible[0].element?.contains(root))
        return stacked("earlier-native-widget");
    const style = getComputedStyle(root);
    const innerWidth = root.clientWidth - parseFloat(style.paddingLeft || 0) - parseFloat(style.paddingRight || 0);
    const points = node.outputs.map((slot, index) => ({ slot, point: node.getOutputPos(index) }));
    if (points.some(({point}) => !point || !finite(point[0]) || !finite(point[1])))
        return stacked("no-output-geometry");
    let measure = measureText;
    if (!measure) {
        const context = document.createElement("canvas").getContext("2d");
        if (!context || !node.innerFontStyle) return stacked("no-label-metrics");
        context.font = node.innerFontStyle;
        measure = text => context.measureText(text).width;
    }
    // Include the native socket interaction width as well as its label. This
    // deliberately leaves a little extra room in legacy's label-to-socket gap.
    const socketSize = slot => Math.max(slot.boundingRect?.[2] || 0,
        slot.boundingRect?.[3] || 0, globalThis.LiteGraph?.NODE_SLOT_HEIGHT || 0);
    const reserve = Math.ceil(Math.max(...points.map(({slot}) => measure(label(slot)) + socketSize(slot))) + gap);
    if (!finite(reserve) || !reserve) return stacked("no-label-metrics");
    if (innerWidth - reserve < minContentWidth) return stacked("content-lane-too-narrow");
    const top = Math.min(...points.map(({slot, point}) => point[1] - node.pos[1] - socketSize(slot) / 2));
    const bottom = Math.max(...points.map(({slot, point}) => point[1] - node.pos[1] + socketSize(slot) / 2));
    if (!finite(top) || !finite(bottom) || top < 0 || bottom <= top) return stacked("unsupported-output-geometry");
    return { mode: "shared", reason: "measured-native-output-lane", reserve,
        start: top, height: bottom - top, contentWidth: innerWidth - reserve };
}

export function installOutputLane(node, root, {
    head = () => [...root.children].find(child => !child.hidden), onChange = () => {}, ...options
} = {}) {
    const hadStart = Object.prototype.hasOwnProperty.call(node, "widgets_start_y");
    const originalStart = node.widgets_start_y;
    const oldBackground = root.style.background;
    let currentHead, headStyles, ownedStart, stopped = false, queued = false;
    let state = { mode: "stacked", reason: "not-measured", reserve: 0, start: null, height: 0 };
    function resetHead() {
        if (currentHead && headStyles) {
            currentHead.style.marginRight = headStyles.marginRight;
            currentHead.style.minHeight = headStyles.minHeight;
        }
        currentHead = headStyles = null;
    }
    function restoreStart() {
        // Another extension may have installed a later layout policy. Restore
        // only the start value this controller actually wrote and still owns.
        if (ownedStart !== undefined && node.widgets_start_y === ownedStart) {
            if (hadStart) node.widgets_start_y = originalStart;
            else delete node.widgets_start_y;
        }
        ownedStart = undefined;
    }
    function refresh() {
        if (stopped) return state;
        const next = measureOutputLane(node, root, options);
        const first = typeof head === "function" ? head() : head;
        if (!first) { next.mode = "stacked"; next.reason = "no-content-section"; }
        const changed = JSON.stringify(next) !== JSON.stringify(state) || (next.mode === "shared" && first !== currentHead);
        if (!changed) return state;
        resetHead();
        if (next.mode === "shared") {
            currentHead = first;
            headStyles = { marginRight: first.style.marginRight, minHeight: first.style.minHeight };
            first.style.marginRight = `${next.reserve}px`;
            first.style.minHeight = `${next.height}px`;
            root.style.background = "transparent";
            node.widgets_start_y = next.start;
            ownedStart = next.start;
        } else {
            root.style.background = oldBackground;
            restoreStart();
        }
        root.dataset.outputLane = next.mode;
        state = next;
        onChange(state);
        node.setDirtyCanvas?.(true, true);
        return state;
    }
    const schedule = () => {
        if (queued || stopped) return;
        queued = true;
        requestAnimationFrame(() => { queued = false; refresh(); });
    };
    const observer = new ResizeObserver(schedule);
    observer.observe(root);
    schedule();
    return { refresh, get state() { return state; }, destroy() {
        if (stopped) return;
        stopped = true; observer.disconnect(); resetHead(); restoreStart();
        root.style.background = oldBackground;
        delete root.dataset.outputLane;
    } };
}
