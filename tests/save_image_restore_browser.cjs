/* Run against an isolated ComfyUI instance containing the pack. */
const assert = require('node:assert/strict');
const {chromium} = require('playwright');
const base = process.argv[2] || 'http://127.0.0.1:8197';

(async () => {
    const browser = await chromium.launch({headless: true,
        ...(process.env.RAY_BROWSER_CHANNEL ? {channel: process.env.RAY_BROWSER_CHANNEL} : {})});
    try {
        const page = await browser.newPage({viewport: {width: 1500, height: 1200}});
        page.setDefaultTimeout(15000);
        const errors = [];
        page.on('pageerror', error => errors.push(error.message));
        await page.goto(base);
        await page.waitForFunction(() => !!globalThis.LiteGraph?.registered_node_types?.RaySaveImage
            && !!globalThis.comfyAPI?.app?.app?.extensionManager?.workflow?.activeWorkflow);
        for (const modern of [true, false]) {
            await page.evaluate(async enabled => {
                const {app} = await import('/scripts/app.js');
                await app.ui.settings.setSettingValue('Comfy.VueNodes.Enabled', enabled);
            }, modern);
            await page.reload();
            await page.waitForFunction(() => !!globalThis.LiteGraph?.registered_node_types?.RaySaveImage
                && !!globalThis.comfyAPI?.app?.app?.extensionManager?.workflow?.activeWorkflow);
            await page.evaluate(async () => {
                const {app} = await import('/scripts/app.js');
                const {api} = await import('/scripts/api.js');
                app.graph.clear();
                const one = LiteGraph.createNode('EmptyImage');
                const two = LiteGraph.createNode('EmptyImage');
                const save = LiteGraph.createNode('RaySaveImage');
                for (const node of [one, two, save]) app.graph.add(node);
                for (const source of [one, two]) {
                    for (const [name, value] of Object.entries({width: 64, height: 64, batch_size: 2})) {
                        source.widgets.find(widget => widget.name === name).value = value;
                    }
                }
                two.widgets.find(widget => widget.name === 'color').value = 0x5588bb;
                save.widgets.find(widget => widget.name === 'filename_prefix').value = `preview_restore_${Date.now()}_{counter}`;
                save.widgets.find(widget => widget.name === 'directory').value = 'preview_restore_test';
                save.widgets.find(widget => widget.name === 'save_image').value = 'both';
                one.connect(0, save, save.inputs.findIndex(input => input.name === 'image_1'));
                two.connect(0, save, save.inputs.findIndex(input => input.name === 'image_2'));
                save.pos = [200, 150];
                app.canvas.ds.scale = 1;
                app.canvas.ds.offset = [0, 0];
                window.restoreSaveId = save.id;
                window.restoreWorkflow = app.extensionManager.workflow.activeWorkflow;
                // Deliver completion after switching tabs, independently of CPU speed.
                window.restoreEvents = [];
                window.restoreDispatch = api.dispatchCustomEvent;
                api.dispatchCustomEvent = function (type, detail) {
                    if (/^(executed|executing|execution_)/.test(type)) { window.restoreEvents.push({type, detail}); return true; }
                    return window.restoreDispatch.call(this, type, detail);
                };
                await app.queuePrompt(0, 1);
            });
            await page.waitForFunction(() => window.restoreEvents.some(event => event.detail.output?.ray_saved?.length === 4));
            // Switching recreates nodes; ComfyUI restores results separately from onExecuted.
            await page.evaluate(async () => {
                const {app} = await import('/scripts/app.js');
                const {api} = await import('/scripts/api.js');
                const other = app.extensionManager.workflow.createNewTemporary('Preview other tab.json', {
                    version: 0.4, nodes: [], links: [], groups: [], config: {}, extra: {},
                });
                await app.loadGraphData(JSON.parse(JSON.stringify(other.activeState)), true, true, other);
                if (app.graph.getNodeById(window.restoreSaveId)) throw Error('Other workflow must be empty');
                api.dispatchCustomEvent = window.restoreDispatch;
                for (const event of window.restoreEvents) api.dispatchCustomEvent(event.type, event.detail);
            });
            await page.waitForFunction(() => {
                const outputs = window.restoreWorkflow.changeTracker.nodeOutputs;
                return Object.values(outputs || {}).some(output => output.ray_saved?.length === 4);
            });
            await page.evaluate(async () => {
                const {app} = await import('/scripts/app.js');
                const workflow = window.restoreWorkflow;
                await app.loadGraphData(JSON.parse(JSON.stringify(workflow.activeState)), true, true, workflow);
            });
            await page.waitForFunction(() => {
                const node = globalThis.comfyAPI.app.app.graph.getNodeById(window.restoreSaveId);
                return node?._raySave?.root.querySelectorAll('img[src]').length === 2;
            }, undefined, {timeout: 5000});
            const result = await page.evaluate(async () => {
                const {app} = await import('/scripts/app.js');
                const node = app.graph.getNodeById(window.restoreSaveId);
                const root = node._raySave.root;
                await Promise.all([...root.querySelectorAll('img')].map(image => image.decode()));
                const menu = [];
                node.getExtraMenuOptions(app.canvas, menu);
                const initial = {
                    images: [...root.querySelectorAll('img')].map(image => image.naturalWidth),
                    status: root.querySelector('.ray-save-info .ray-save-status').textContent,
                    comparing: !root.querySelector('.ray-save-divider').hidden,
                    count: root.querySelector('.ray-save-nav .ray-save-status').textContent,
                    directory: node._raySavedDirectory,
                    locationEnabled: !menu.find(item => item.content === 'Open image location in Explorer').disabled,
                    widgets: node.widgets.filter(widget => !widget.element).map(widget => [widget.name, widget.value]),
                };
                root.querySelector('[aria-label="Next image pair"]').click();
                initial.nextCount = root.querySelector('.ray-save-nav .ray-save-status').textContent;
                return initial;
            });
            assert.deepEqual(result.images, [64, 64], 'Restored previews must decode');
            assert.equal(result.status, 'Saved 4 PNGs');
            assert.equal(result.comparing, true);
            assert.equal(result.count, '1 / 2');
            assert.equal(result.nextCount, '2 / 2');
            assert.equal(result.locationEnabled, true);
            assert.match(result.directory, /preview_restore_test$/);
            assert.equal(Object.fromEntries(result.widgets).save_image, 'both');
            // History loads the saved graph first, then assigns its output snapshot.
            await page.evaluate(async () => {
                const {app} = await import('/scripts/app.js');
                const {api} = await import('/scripts/api.js');
                const promptId = window.restoreEvents.find(event => event.type === 'executed').detail.prompt_id;
                const history = await (await api.fetchApi(`/history/${promptId}`)).json();
                const run = history[promptId];
                if (!run?.outputs) throw Error('Completed run must be in history');
                await app.loadGraphData(run.prompt[3].extra_pnginfo.workflow);
                const node = app.graph.getNodeById(window.restoreSaveId);
                if (!node._raySave.root.querySelector('.ray-save-empty').hidden) {
                    app.nodeOutputs = run.outputs;
                } else {
                    throw Error('History test must start with a new preview');
                }
                await Promise.all([...node._raySave.root.querySelectorAll('img')].map(image => image.decode()));
                if (node._raySave.root.querySelectorAll('img[src]').length !== 2) throw Error('History previews missing');
                const before = node._raySave.root.querySelector('img').src;
                // Other node outputs must not clear a completed preview.
                app.nodeOutputs = {missing: {images: []}};
                if (node._raySave.root.querySelector('img').src !== before) throw Error('Unrelated output cleared preview');
            });
            console.log(`${modern ? 'Nodes 2.0' : 'Legacy'}: background completion, tab/history restoration, images, comparison, batches, saved status and location passed`);
        }
        assert.deepEqual(errors, []);
    } finally {
        await browser.close();
    }
})().catch(error => {console.error(error); process.exitCode = 1;});
