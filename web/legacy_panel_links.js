// The canvas arranges hidden native widgets at stale/overlapping coordinates. Keep their
// sockets and hit tests aligned with the DOM controls that replace them. Nodes 2.0 owns
// its own slot layout and must keep using the frontend's positions.
export function installLegacyLinkLayout(node, rows, canvas) {
    const positions = new Map();
    const hooks = [];
    const legacy = () => !globalThis.LiteGraph?.vueNodesMode && !node.flags?.collapsed;
    function restore(input, saved) {
        if (input.pos !== saved.ours) return;
        if (saved.previous === undefined) delete input.pos;
        else input.pos = saved.previous;
    }
    function geometry(row) {
        if (!row.name || row.element.hidden || !row.element.isConnected) return null;
        const widget = node.widgets?.find(w => w.element?.contains(row.element));
        const top = widget?.y ?? widget?.last_y;
        if (!Number.isFinite(top) || !widget.element.offsetWidth) return null;
        const host = widget.element.getBoundingClientRect();
        const scale = host.width / widget.element.offsetWidth;
        const rect = row.element.getBoundingClientRect();
        if (!(scale > 0) || !rect.width || !rect.height) return null;
        // Use the control's centre, especially for a textarea with a label above it.
        const control = (row.anchor || row.element.querySelector('.rp-control') || row.element).getBoundingClientRect();
        const margin = widget.margin ?? widget.options?.margin ?? 10;
        const y = top + margin;
        return {
            left: margin + (rect.left - host.left) / scale,
            right: margin + (rect.right - host.left) / scale,
            top: y + (rect.top - host.top) / scale,
            bottom: y + (rect.bottom - host.top) / scale,
            centre: y + (control.top + control.height / 2 - host.top) / scale,
        };
    }
    function sync() {
        const active = new Set();
        if (legacy()) for (const row of rows) {
            const at = node.inputs?.findIndex(i => i.widget?.name === row.name || (i.widget && i.name === row.name)) ?? -1;
            const box = at >= 0 ? geometry(row) : null;
            if (!box) continue;
            const input = node.inputs[at];
            const concrete = node._concreteInputs?.[at] || input;
            const x = (globalThis.LiteGraph?.NODE_SLOT_HEIGHT ?? 20) / 2;
            for (const slot of new Set([input, concrete])) {
                let saved = positions.get(slot);
                if (!saved || slot.pos !== saved.ours) saved = { previous: slot.pos };
                saved.ours = [x, box.centre];
                slot.pos = saved.ours;
                positions.set(slot, saved);
                active.add(slot);
            }
            node._measureSlot?.(concrete, at, true);
        }
        for (const [input, saved] of positions) if (!active.has(input)) {
            restore(input, saved);
            positions.delete(input);
        }
    }
    function hook(name, wrap) {
        const own = Object.getOwnPropertyDescriptor(node, name);
        const prior = node[name];
        const installed = wrap(prior);
        node[name] = installed;
        hooks.push(() => {
            if (node[name] !== installed) return;
            if (own) Object.defineProperty(node, name, own);
            else delete node[name];
        });
    }
    hook('arrange', prior => function (...args) {
        const result = prior?.apply(this, args);
        sync();
        return result;
    });
    // Re-measure after DOM reflow, including changes to labels, linked chips and node width.
    hook('onDrawForeground', prior => function (...args) {
        sync();
        return prior?.apply(this, args);
    });
    hook('getWidgetOnPos', prior => function (x, y, ...args) {
        const connector = canvas()?.linkConnector;
        if (legacy() && connector?.isConnecting && connector.state?.connectingTo === 'input') {
            sync();
            for (const row of rows) {
                const box = geometry(row);
                if (box && x - node.pos[0] >= box.left && x - node.pos[0] <= box.right
                    && y - node.pos[1] >= box.top && y - node.pos[1] <= box.bottom) {
                    const widget = node.widgets?.find(w => w.name === row.name);
                    if (widget && node.inputs?.some(i => i.widget?.name === row.name)) return widget;
                }
            }
        }
        return prior?.call(this, x, y, ...args);
    });
    return () => {
        for (const [input, saved] of positions) restore(input, saved);
        positions.clear();
        for (const restoreHook of hooks.reverse()) restoreHook();
    };
}
