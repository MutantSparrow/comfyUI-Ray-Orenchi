/* Run against an isolated ComfyUI server containing the pack. */
const assert = require('node:assert/strict');
const {chromium} = require('playwright');
const base = process.argv[2] || 'http://127.0.0.1:8194';

(async () => {
    const browser = await chromium.launch({headless: true,
        ...(process.env.RAY_BROWSER_CHANNEL ? {channel: process.env.RAY_BROWSER_CHANNEL} : {})});
    try {
        const page = await browser.newPage({viewport: {width: 1500, height: 1200}});
        await page.goto(base);
        const ready = async () => {
            await page.waitForFunction(() => !!globalThis.LiteGraph?.registered_node_types?.RayFolders);
            await page.waitForTimeout(900);
            await page.keyboard.press('Escape');
        };
        await ready();
        for (const vue of [false, true]) {
            await page.evaluate(async enabled => {
                const {app} = await import('/scripts/app.js');
                await app.ui.settings.setSettingValue('Comfy.VueNodes.Enabled', enabled);
            }, vue);
            await page.reload(); await ready();
            const results = await page.evaluate(async vue => {
                const {app} = await import('/scripts/app.js');
                const extension = (await (await fetch('/extensions')).json()).find(path => path.endsWith('/output_lane.js'));
                const {installOutputLane} = await import(extension);
                app.graph.clear();
                app.canvas.ds.scale = 1; app.canvas.ds.offset = [0, 0];
                const delay = () => new Promise(resolve => setTimeout(resolve, 250));
                const results = [];
                for (const type of ['RayFolders', 'RayTextFolder']) {
                    const node = LiteGraph.createNode(type); node.pos = [250, 180]; app.graph.add(node);
                    await delay(); // Standard panels install after native widget construction.
                    const installed = node._rayPanel?.outputLane || node._rayFoldersOutputLane;
                    if (!installed) throw new Error(`${type}: production shared output-lane controller is missing`);
                    node.setSize([520, node.size[1]]); app.canvas.setDirty(true, true); await delay();
                    // Exercise the production controller first, then release it
                    // before a separate ownership/teardown geometry exercise.
                    installed.refresh();
                    const production = {...installed.state};
                    installed.destroy();
                    const root = node._rayFolders?.root || node._rayPanel.root;
                    const priorStart = {own:Object.prototype.hasOwnProperty.call(node,'widgets_start_y'),value:node.widgets_start_y};
                    const nativeBefore = node.outputs.map((slot, index) => ({name: slot.name, point: node.getOutputPos(index)}));
                    const lane = installOutputLane(node, root);
                    lane.refresh(); app.canvas.setDirty(true, true); await delay();
                    const wide = {...lane.state};
                    const first = [...root.children].find(child => !child.hidden);
                    const box = first.getBoundingClientRect();
                    const cog = root.querySelector('[data-icon="settings"]')?.getBoundingClientRect();
                    const labels = node.outputs.map((slot, index) => ({name: slot.name, point: node.getOutputPos(index)}));
                    const socket = node.getOutputPos(0);
                    const client = app.canvas.ds.convertCanvasToOffset(socket);
                    const canvasBox = app.canvas.canvas.getBoundingClientRect();
                    const hit = document.elementFromPoint(client[0] + canvasBox.left, client[1] + canvasBox.top);
                    const socketCovered = !!hit && root.contains(hit);
                    const lastSocket = node.getOutputPos(node.outputs.length - 1);
                    const lastClient = app.canvas.ds.convertCanvasToOffset(lastSocket);
                    const sharesVerticalSpace = box.top < lastClient[1] + canvasBox.top + LiteGraph.NODE_SLOT_HEIGHT / 2;
                    // Never force extra node width merely to enable row sharing.
                    node.setSize([340, node.size[1]]); app.canvas.setDirty(true, true); await delay(); lane.refresh();
                    const narrow = {...lane.state};
                    node.setSize([520, node.size[1]]);
                    const original = node.outputs[0].label;
                    node.outputs[0].label = 'An output label that must retain its whole native interaction area';
                    lane.refresh(); const longLabel = {...lane.state}; node.outputs[0].label = original;
                    // A connected/converted widget must retain its native input space.
                    const savedInputs = node.inputs;
                    node.inputs = [...savedInputs, {name: 'native_data', type: 'IMAGE', link: null}];
                    lane.refresh(); const input = {...lane.state}; node.inputs = savedInputs;
                    lane.destroy();
                    const restored = Object.prototype.hasOwnProperty.call(node, 'widgets_start_y')===priorStart.own
                        && node.widgets_start_y===priorStart.value
                        && !first.style.marginRight && !root.dataset.outputLane;
                    const external = installOutputLane(node, root);
                    external.refresh(); node.widgets_start_y = 137; external.destroy();
                    const externalPreserved = node.widgets_start_y === 137; delete node.widgets_start_y;
                    results.push({type, vue, production, wide, narrow, longLabel, input, socketCovered, sharesVerticalSpace, restored, externalPreserved,
                        portsUnchanged: JSON.stringify(nativeBefore) === JSON.stringify(labels),
                        cogFits: !cog || cog.right <= box.right + 1});
                    app.graph.remove(node);
                }
                return results;
            }, vue);
            for (const row of results) {
                assert.equal(row.wide.mode, vue ? 'stacked' : 'shared', `${row.type}: ${JSON.stringify(row.wide)}`);
                assert.equal(row.production.mode, vue ? 'stacked' : 'shared', `${row.type}: production integration`);
                assert.equal(row.narrow.mode, 'stacked', `${row.type}: narrow fallback`);
                assert.equal(row.longLabel.mode, 'stacked', `${row.type}: long-label fallback`);
                assert.equal(row.input.mode, 'stacked', `${row.type}: native-input fallback`);
                assert.equal(row.socketCovered, false, `${row.type}: widget must not intercept the output socket`);
                if (!vue) assert.equal(row.sharesVerticalSpace, true, `${row.type}: content must actually use the output column's vertical space`);
                assert.equal(row.portsUnchanged, true, `${row.type}: native ports must retain their coordinates`);
                assert.equal(row.cogFits, true, `${row.type}: settings must fit the content lane`);
                assert.equal(row.restored, true, `${row.type}: teardown restores owned styles and widget start`);
                assert.equal(row.externalPreserved, true, `${row.type}: teardown preserves a later external widget-start policy`);
            }
            console.log(`${vue ? 'Nodes 2.0 safe stacked fallback' : 'Legacy measured shared lane'}: ${results.length} nodes passed`);
        }
    } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
