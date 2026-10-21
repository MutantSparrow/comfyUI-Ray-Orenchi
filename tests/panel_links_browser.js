import { app, nodeClass } from '/scripts/app.js';
import '/extensions/ray/ray_save_image.js';
import { installPanel } from '/extensions/ray/ray_panel.js';
import { PANEL_SPECS } from '/extensions/ray/ray_panels.js';

let passes = 0;
const check = (condition, message) => {
    if (!condition) throw new Error(message);
    passes++;
    document.querySelector('#results').textContent += 'PASS ' + message + String.fromCharCode(10);
};
const near = (actual, expected, message) => check(Math.abs(actual - expected) < 1.1, message);
globalThis.LiteGraph = { vueNodesMode: false, NODE_SLOT_HEIGHT: 20 };
app.canvas = { linkConnector: { isConnecting: true, state: { connectingTo: 'input' }, renderLinks: [] }, setDirty() {} };

function legacyNode(names) {
    const Node = nodeClass('knob');
    const node = new Node();
    node.pos = [150, 220];
    node.widgets = Object.entries(names).map(([name, value]) => ({name, value,
        type: typeof value === 'boolean' ? 'toggle' : typeof value === 'number' ? 'number' : 'text',
        options: {}, callback() {}}));
    // Simulate the frontend's hidden-widget layout, where all sockets end up at y=10.
    node.inputs = [{name:'images', type:'IMAGE', link:null}, ...Object.keys(names).map(name => ({name, type:'STRING', widget:{name}, link:null}))];
    node._concreteInputs = node.inputs.map(i => ({...i}));
    node._measureSlot = (slot, at) => { slot.boundingRect = [node.pos[0] + slot.pos[0] - 10, node.pos[1] + slot.pos[1] - 10, 20, 20]; };
    node.arrange = () => {
        for (const [at, input] of node.inputs.entries()) if (input.widget) {
            input.pos = node._concreteInputs[at].pos = [10, 10];
            node._measureSlot(node._concreteInputs[at], at);
        }
        for (const widget of node.widgets) if (widget.element) widget.y = 64;
    };
    node.getWidgetOnPos = () => node.widgets.find(w => w.element);
    return node;
}
function mount(node, x, y, width) {
    const card = document.createElement('section');
    card.className = 'test-node';
    Object.assign(card.style, {left:x+'px', top:y+'px', width:width+'px', height:'1040px'});
    const widget = node.widgets.find(w => w.element);
    const margin = widget.margin ?? widget.options.margin ?? 10;
    node.arrange();
    Object.assign(widget.element.style, {left:margin+'px', top:(widget.y+margin)+'px', width:(width-2*margin)+'px', height:'900px'});
    card.append(widget.element);
    document.querySelector('#stage').append(card);
    node.arrange();
    return {card, widget};
}
function position(node, mounted, control) {
    const rect = control.getBoundingClientRect(), host = mounted.card.getBoundingClientRect();
    const scale = host.width / mounted.card.offsetWidth;
    // Borders surround the rendered node; coordinates inside the body start after the border.
    return [node.pos[0] + (rect.left + rect.width/2 - host.left)/scale - 1,
        node.pos[1] + (rect.top + rect.height/2 - host.top)/scale - 1];
}
function verify(node, mounted, name, control, message) {
    node.arrange();
    const point = position(node, mounted, control);
    const at = node.inputs.findIndex(i => i.widget?.name === name);
    near(node.pos[1] + node.inputs[at].pos[1], point[1], message + ': endpoint follows the visible field');
    near(node._concreteInputs[at].boundingRect[1] + 10, point[1], message + ': native hit box follows the endpoint');
    check(node.getWidgetOnPos(...point)?.name === name, message + ': canvas snapping selects ' + name);
}
try {
    const save = legacyNode({save_image:'1', directory:'', filename_prefix:'Ray', save_without_metadata:false});
    for (const extension of app.extensions) await extension.beforeRegisterNodeDef?.({prototype:save}, {name:'RaySaveImage'});
    save.onNodeCreated();
    const saveMount = mount(save, 0, 0, 420);
    const prefix = save._raySave.root.querySelector('input[id^="ray-save-prefix"]');
    const directory = save._raySave.root.querySelector('input[id^="ray-save-dir"]');
    verify(save, saveMount, 'directory', directory, 'Save Image folder');
    verify(save, saveMount, 'filename_prefix', prefix, 'Save Image prefix');
    const prefixY = save.inputs.find(i => i.name === 'filename_prefix').pos[1];
    const directoryY = save.inputs.find(i => i.name === 'directory').pos[1];
    check(directoryY - prefixY >= 28, 'Folder and prefix sockets do not overlap');
    check(!save.inputs[0].pos, 'Image input stays in its native position');

    const fast = legacyNode({prompt:'Describe the image.', max_tokens:256, temperature:0, top_p:.9, top_k:40, seed:42,
        mode:'fast', sync_interval:8, thinking:false, repetition_penalty:1, presence_penalty:1.5, repeat_guard:true});
    fast.widgets.find(w => w.name === 'prompt').type = 'customtext';
    installPanel(fast, PANEL_SPECS.RayFastQwen3VL);
    const fastMount = mount(fast, 460, 0, 380);
    const prompt = fast._rayPanel.root.querySelector('textarea');
    verify(fast, fastMount, 'prompt', prompt, 'Fast VLM multiline prompt');
    verify(fast, fastMount, 'max_tokens', fast._rayPanel.rows.find(r => r.name === 'max_tokens').element.querySelector('input'), 'Field after multiline prompt');

    for (const scale of [.5, 1.75]) {
        saveMount.card.style.transform = 'translate(37px, 21px) scale(' + scale + ')';
        verify(save, saveMount, 'directory', directory, 'Folder after pan/zoom ' + scale);
        fastMount.card.style.transform = 'scale(' + scale + ')';
        verify(fast, fastMount, 'prompt', prompt, 'Fast VLM after zoom ' + scale);
    }
    saveMount.card.style.transform = '';
    saveMount.card.style.width = '300px';
    saveMount.widget.element.style.width = '280px';
    verify(save, saveMount, 'directory', directory, 'Folder after width reflow');

    const folderInput = save.inputs.find(i => i.name === 'directory');
    folderInput.link = 7;
    save.graph.links = new Map([[7, {origin_id:4, origin_slot:0}]]);
    save.onConnectionsChange();
    verify(save, saveMount, 'directory', save._raySave.root.querySelector('.ray-save-group .rp-link'), 'Linked folder chip');
    folderInput.link = null;
    save.onConnectionsChange();
    verify(save, saveMount, 'directory', directory, 'Folder after unlinking');

    function dropOn(node, control, name) {
        let connected;
        const connector = app.canvas.linkConnector;
        connector.isConnecting = true;
        connector.renderLinks = [{canConnectToInput: () => true, connectToInput: (target, input) => { connected = {target, input}; }}];
        connector.reset = () => { connector.isConnecting = false; connector.renderLinks = []; };
        const rect = control.getBoundingClientRect();
        const event = {clientX:rect.left+rect.width/2, clientY:rect.top+rect.height/2, bubbles:true};
        window.dispatchEvent(new PointerEvent('pointermove', event));
        window.dispatchEvent(new PointerEvent('pointerup', event));
        check(connected?.target === node && connected.input.name === name, 'Dropping on the visible field connects to ' + name);
        check(!connector.isConnecting && node.graph.before === node.graph.after, 'Drop resets the connector with a balanced undo step');
        connector.isConnecting = true;
    }
    dropOn(save, directory, 'directory');
    dropOn(fast, prompt, 'prompt');

    // Native hover must receive the actual widget, not the DOM panel (which falls back to first STRING).
    const target = save.getWidgetOnPos(...position(save, saveMount, directory));
    const selected = save.inputs.find(i => i.widget?.name === target?.name) || save.inputs.find(i => i.type === 'STRING');
    check(selected.name === 'directory', 'Legacy fallback cannot redirect the folder drop to prefix');
    app.canvas.linkConnector.isConnecting = false;
    check(save.getWidgetOnPos(...position(save, saveMount, directory)) === saveMount.widget, 'Normal panel editing keeps the original hit test');
    app.canvas.linkConnector.isConnecting = true;

    globalThis.LiteGraph.vueNodesMode = true;
    save.arrange();
    check(save.inputs.filter(i => i.widget).every(i => i.pos[1] === 10), 'Nodes 2.0 keeps the frontend slot layout');
    check(save.getWidgetOnPos(...position(save, saveMount, directory)) === saveMount.widget, 'Nodes 2.0 keeps the frontend hit test');
    globalThis.LiteGraph.vueNodesMode = false;
    verify(save, saveMount, 'directory', directory, 'Returning to legacy mode');
    const hidden = fast._rayPanel.rows.find(r => r.name === 'prompt');
    hidden.widget.rayLogicHidden = true;
    fast._rayPanel.refresh();
    fast.arrange();
    check(fast.inputs.find(i => i.name === 'prompt').pos[1] === 10, 'Hidden rows release their custom socket positions');
    hidden.widget.rayLogicHidden = false;
    fast._rayPanel.refresh();
    verify(fast, fastMount, 'prompt', prompt, 'Showing a previously hidden field');
    save.onRemoved();
    fast.onRemoved();
    check(save.getWidgetOnPos(...position(save, saveMount, directory)) === saveMount.widget, 'Removing a panel restores native hooks');
    check(save.inputs.filter(i => i.widget).every(i => i.pos[1] === 10), 'Removing a panel restores native positions');
    document.querySelector('#summary').textContent = passes + ' checks passed';
} catch (error) {
    document.querySelector('#summary').textContent = 'Regression failed';
    document.querySelector('#results').textContent += error.stack;
}
