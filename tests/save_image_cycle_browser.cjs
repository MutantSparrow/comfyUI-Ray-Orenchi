/* Run against an isolated ComfyUI instance containing the pack; no models required. */
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
        const ready = () => page.waitForFunction(() => !!globalThis.LiteGraph?.registered_node_types?.RaySaveImage
            && !!globalThis.comfyAPI?.app?.app?.extensionManager?.workflow?.activeWorkflow);
        await ready();
        for (const modern of [true, false]) {
            await page.evaluate(async enabled => {
                const {app} = await import('/scripts/app.js');
                await app.ui.settings.setSettingValue('Comfy.VueNodes.Enabled', enabled);
            }, modern);
            await page.reload();
            await ready();
            await page.evaluate(async () => {
                const {app} = await import('/scripts/app.js');
                app.graph.clear();
                const save = LiteGraph.createNode('RaySaveImage');
                app.graph.add(save);
                for (let number = 1; number <= 2; number++) {
                    const image = LiteGraph.createNode('EmptyImage');
                    app.graph.add(image);
                    image.pos = [-600, -600];
                    for (const [name, value] of Object.entries({width: 64, height: 64, batch_size: 4 - number, color: number * 0x334455})) {
                        image.widgets.find(widget => widget.name === name).value = value;
                    }
                    image.connect(0, save, save.inputs.findIndex(input => input.name === `image_${number}`));
                }
                save.widgets.find(widget => widget.name === 'save_image').value = 'none';
                save.widgets.find(widget => widget.name === 'filename_prefix').value = `cycle_${Date.now()}`;
                save.pos = [200, 150];
                app.canvas.ds.scale = 1;
                app.canvas.ds.offset = [0, 0];
                window.cycleSave = save;
                await app.queuePrompt(0, 1);
            });
            await page.waitForFunction(() => window.cycleSave._raySave.root.querySelector('.ray-save-nav .ray-save-status').textContent === '1 / 3');
            const stage = page.locator('.ray-save-stage');
            const count = () => page.locator('.ray-save-nav .ray-save-status').textContent();
            const clickPreview = async (right = false) => {
                const box = await stage.boundingBox();
                await page.mouse.click(box.x + box.width * (right ? .8 : .2), box.y + box.height * .3);
            };
            await clickPreview();
            assert.equal(await count(), '2 / 3', 'A single click advances exactly once');
            await clickPreview(true);
            assert.equal(await count(), '3 / 3 · Unpaired image');
            await clickPreview();
            assert.equal(await count(), '1 / 3', 'Last image wraps to the first');
            await page.evaluate(() => window.cycleSave.setSize([340, window.cycleSave.size[1]]));
            await page.waitForTimeout(100);
            await clickPreview();
            assert.equal(await count(), '2 / 3', 'Narrow preview still cycles');
            await page.getByRole('button', {name: 'Previous image pair', exact: true}).click();
            await page.getByRole('button', {name: 'Next image pair', exact: true}).click();
            assert.equal(await count(), '2 / 3', 'Arrow click must not also cycle the stage');
            await page.getByRole('button', {name: 'Previous image pair', exact: true}).click();
            assert.equal(await count(), '1 / 3');
            const slider = page.getByRole('slider', {name: 'Image comparison divider'});
            const handle = await slider.boundingBox();
            const box = await stage.boundingBox();
            await page.mouse.move(handle.x + handle.width / 2, handle.y + handle.height / 2);
            await page.mouse.down();
            await page.mouse.move(box.x + box.width * .7, handle.y + handle.height / 2, {steps: 8});
            await page.mouse.up();
            assert.equal(await count(), '1 / 3', 'Divider drag must not cycle images');
            assert(Number(await slider.getAttribute('aria-valuenow')) > 60, 'Divider still drags');
            await slider.click();
            assert.equal(await count(), '1 / 3', 'Divider click must not cycle images');
            await page.mouse.move(box.x + box.width * .2, box.y + box.height * .3);
            await page.mouse.down();
            await page.mouse.move(box.x + box.width * .3, box.y + box.height * .4, {steps: 5});
            await page.mouse.up();
            assert.equal(await count(), '1 / 3', 'Dragging the picture must not count as a click');
            // Exercise actual canvas pan/zoom over the preview, including DOM-widget forwarding.
            const canvasState = () => page.evaluate(() => {
                const ds = globalThis.comfyAPI.app.app.canvas.ds;
                return {scale: ds.scale, offset: [...ds.offset]};
            });
            for (const space of [true, false]) {
                await page.evaluate(() => globalThis.comfyAPI.app.app.canvas.canvas.focus());
                const before = await canvasState();
                const region = await stage.boundingBox();
                await page.mouse.move(region.x + region.width * .2, region.y + region.height * .3);
                if (space) await page.keyboard.down('Space');
                await page.mouse.down({button: space ? 'left' : 'middle'});
                await page.mouse.move(region.x + region.width * .2 + 30, region.y + region.height * .3 + 20, {steps: 5});
                await page.mouse.up({button: space ? 'left' : 'middle'});
                if (space) await page.keyboard.up('Space');
                await page.waitForTimeout(100);
                assert.notDeepEqual((await canvasState()).offset, before.offset, `${space ? 'Space' : 'Middle'}-drag pans the canvas`);
                assert.equal(await count(), '1 / 3', 'Panning must not cycle images');
            }
            const region = await stage.boundingBox();
            await page.mouse.move(region.x + region.width * .2, region.y + region.height * .3);
            const beforeWheel = await canvasState();
            await page.mouse.wheel(0, 100);
            await page.waitForTimeout(150);
            assert.notEqual((await canvasState()).scale, beforeWheel.scale, 'Wheel zooms the canvas');
            assert.equal(await count(), '1 / 3', 'Zooming must not cycle images');
            const menuRegion = await stage.boundingBox();
            await page.mouse.click(menuRegion.x + menuRegion.width * .2, menuRegion.y + menuRegion.height * .3, {button: 'right'});
            await page.getByText('Save without metadata', {exact: true}).waitFor();
            assert.equal(await count(), '1 / 3', 'Right-click must not cycle images');
            await page.keyboard.press('Escape');
            await page.evaluate(async () => {
                const {app} = await import('/scripts/app.js');
                window.cycleOutput = app.nodeOutputs[window.cycleSave.id];
                window.cycleSave.onExecuted({...window.cycleOutput, ray_images_1: [], ray_images_2: window.cycleOutput.ray_images_2});
                app.canvas.ds.scale = 1;
                app.canvas.ds.offset = [0, 0];
            });
            await clickPreview();
            assert.equal(await count(), '2 / 2 · Unpaired image', 'Second-input-only batch cycles');
            await clickPreview();
            assert.equal(await count(), '1 / 2 · Unpaired image');
            await page.evaluate(() => window.cycleSave.onExecuted({...window.cycleOutput,
                ray_images_1: window.cycleOutput.ray_images_1.slice(0, 1)}));
            const singleton = await stage.locator('.ray-save-overlay img').getAttribute('src');
            await clickPreview();
            assert.equal(await count(), '2 / 2');
            assert.equal(await stage.locator('.ray-save-overlay img').getAttribute('src'), singleton, 'Singleton stays paired with the other batch');
            await page.evaluate(() => window.cycleSave.onExecuted({...window.cycleOutput,
                ray_images_1: window.cycleOutput.ray_images_1.slice(0, 1), ray_images_2: []}));
            assert.equal(await stage.evaluate(element => element.classList.contains('ray-save-cycle')), false, 'Single images stay click-through');
            assert.equal(await count(), '1 / 1');
            await page.evaluate(() => window.cycleSave.onExecuted({ray_images_1: [], ray_images_2: [], ray_saved: []}));
            assert.equal(await stage.evaluate(element => element.classList.contains('ray-save-cycle')), false, 'Empty previews stay click-through');
            console.log(`${modern ? 'Nodes 2.0' : 'Legacy'}: click cycling, wraparound, input pairing, arrows, divider and canvas navigation passed`);
        }
        assert.deepEqual(errors, []);
    } finally {
        await browser.close();
    }
})().catch(error => {console.error(error); process.exitCode = 1;});
