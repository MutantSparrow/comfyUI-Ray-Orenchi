/* Run against an isolated ComfyUI instance. No model execution is required. */
const assert = require('node:assert/strict');
const {chromium} = require('playwright');
const base = process.argv[2] || 'http://127.0.0.1:8191';
const names = ['root.safetensors', 'FamilyA/Version 2/Alpha.safetensors',
    'FamilyA/Version 2/Beta.safetensors', 'FamilyA/Version 3/Alpha.safetensors',
    'FamilyB\\Nested\\Gamma.safetensors', '日本語/Style.safetensors'];

(async () => {
    const browser = await chromium.launch({headless: true,
        ...(process.env.RAY_BROWSER_CHANNEL ? {channel:process.env.RAY_BROWSER_CHANNEL} : {})});
    let current;
    try {
        for (const nodes2 of [true, false]) {
            const page = await browser.newPage({viewport: {width: 1600, height: 1200}});
            current = page; page.setDefaultTimeout(15000);
            const errors = []; let dialogs = 0, modelRequests = 0;
            page.on('pageerror', error => errors.push(error.message));
            await page.route(/\/(?:api\/)?models\/(diffusion_models|loras)$/, route => {
                modelRequests++; return route.fulfill({json: names});
            });
            page.on('request', request => { if (request.url().includes('/ray/browse')) dialogs++; });
            await page.goto(base);
            await page.waitForFunction(() => !!globalThis.LiteGraph?.registered_node_types?.RayLoraQKVLoader);
            await page.evaluate(async enabled => {
                const {app} = await import('/scripts/app.js');
                await app.ui.settings.setSettingValue('Comfy.VueNodes.Enabled', enabled);
            }, nodes2);
            await page.reload();
            await page.waitForFunction(() => !!globalThis.LiteGraph?.registered_node_types?.RayLoraQKVLoader);
            await page.waitForTimeout(2200); await page.keyboard.press('Escape');
            await page.evaluate(async () => {
                const {app} = await import('/scripts/app.js'); app.graph.clear();
                for (const [id, type, x] of [['queued', 'RayQueuedModelLoader', 100], ['lora', 'RayLoraQKVLoader', 720]]) {
                    const node = LiteGraph.createNode(type); app.graph.add(node); node.pos = [x, 160]; window[id] = node;
                }
                app.canvas.ds.scale = 1; app.canvas.ds.offset = [0, 0]; app.canvas.setDirty(true, true);
            });
            const picker = label => page.getByRole('combobox', {name: label, exact: true});
            const search = label => page.getByRole('textbox', {name: `Filter ${label}`, exact: true});
            const select = async (label, name) => {
                await picker(label).click(); await search(label).fill(name);
                await page.getByRole('menuitem', {name, exact: true}).click();
                await search(label).waitFor({state: 'detached'});
                assert.equal(await picker(label).textContent(), name);
            };
            await picker('Model 1').waitFor();
            await page.waitForTimeout(400);
            assert.match(await picker('Model 1').getAttribute('title'),/Precision and supported quantization/);
            assert.equal(await page.getByRole('button', {name: /^Choose (model|LoRA).*file$/}).count(), 0);
            // Opening shows folders, rather than every descendant flattened into one list.
            await picker('Model 1').click();
            await page.getByRole('menuitem', {name: 'FamilyA', exact: true}).hover();
            await page.getByRole('menuitem', {name: 'Version 2', exact: true}).hover();
            await page.getByRole('menuitem', {name: 'Beta.safetensors', exact: true}).click();
            assert.equal(await picker('Model 1').textContent(), names[2]);
            // Folder names and filenames are both searchable, including unopened branches.
            await picker('Model 1').click(); await search('Model 1').fill('FAMILYB gamma');
            await page.getByRole('menuitem', {name: names[4], exact: true}).click();
            assert.equal(await picker('Model 1').textContent(), names[4], 'Preserve original separators in stored values');
            await page.getByRole('button', {name: 'Add model', exact: true}).click();
            await select('Model 2', names[1]);
            await picker('Model 2').click(); await search('Model 2').fill('absent model');
            await page.getByRole('menuitem', {name: 'No matching models', exact: true}).waitFor();
            await search('Model 2').fill('');
            await page.getByRole('menuitem', {name: 'FamilyA', exact: true}).waitFor();
            await page.keyboard.press('Escape'); assert.equal(await picker('Model 2').textContent(), names[1]);
            // The keyboard can navigate nested folders and select a file.
            await picker('Model 2').focus(); await page.keyboard.press('ArrowDown');
            await search('Model 2').waitFor(); await search('Model 2').press('ArrowDown');
            await page.keyboard.press('ArrowRight'); await page.keyboard.press('ArrowRight'); await page.keyboard.press('Enter');
            assert.equal(await picker('Model 2').textContent(), names[1]);
            await select('LoRA 1', names[5]);
            const strength = index => page.getByRole('spinbutton', {name: `LoRA ${index} strength`, exact: true});
            await strength(1).fill('0.5'); await strength(1).press('Tab');
            await page.getByRole('button', {name: 'Add LoRA', exact: true}).click();
            await select('LoRA 2', names[4]); await strength(2).fill('-0.25'); await strength(2).press('Tab');
            for(const index of [1,2]) {
                assert.match(await strength(index).getAttribute('title'),/Zero skips it; negative values reverse/);
                assert.match(await strength(index).getAttribute('title'),/Drag left or right/);
            }
            await page.getByRole('button', {name: 'Remove LoRA 1', exact: true}).click();
            assert.equal(await picker('LoRA 1').textContent(), names[4]); assert.equal(await strength(1).inputValue(), '-0.25');
            const saved = await page.evaluate(async () => {
                const {app} = await import('/scripts/app.js'); const saved = app.graph.serialize();
                await app.loadGraphData(saved); window.queued = app.graph._nodes.find(n => n.comfyClass === 'RayQueuedModelLoader');
                window.lora = app.graph._nodes.find(n => n.comfyClass === 'RayLoraQKVLoader'); return saved;
            });
            assert.equal(await picker('Model 1').textContent(), names[4]); assert.equal(await picker('LoRA 1').textContent(), names[4]);
            const queued = saved.nodes.find(n => n.type === 'RayQueuedModelLoader');
            assert.deepEqual(queued.widgets_values.slice(0, 2), [names[4], JSON.stringify([names[1]])]);
            // A name supplied by a connected STRING still takes precedence over the dropdown.
            await page.evaluate(async () => {
                const {app} = await import('/scripts/app.js');
                const node = window.queued;
                if (!node.inputs.some(i => i.name === 'model_name')) node.addInput('model_name', 'STRING', {widget: {name: 'model_name'}});
                const origin = new LiteGraph.LGraphNode('Model name'); origin.addOutput('name', 'STRING'); app.graph.add(origin);
                origin.connect(0, node, node.inputs.findIndex(i => i.name === 'model_name'));
                node._rayQueuedLoader.refresh();
            });
            assert.equal(await picker('Model 1').isVisible(), false);
            // Deleting a node with an open menu must remove the menu and abort its work.
            await picker('LoRA 1').click(); await search('LoRA 1').waitFor();
            await page.evaluate(async () => { const {app} = await import('/scripts/app.js'); app.graph.remove(window.lora); });
            await page.locator('.ray-model-menu').waitFor({state: 'detached'});
            assert.equal(dialogs, 0); assert.ok(modelRequests >= 8); assert.deepEqual(errors, []);
            console.log(`${nodes2 ? 'Nodes 2.0' : 'Legacy'}: folder tree, recursive filter, keyboard, stacks, serialization and teardown passed`);
            await page.close();
        }
    } catch (error) {
        console.error('Picker diagnostics:', await current?.locator('.litecontextmenu').allTextContents());
        await current?.screenshot({path: require('node:path').join(process.env.TEMP, 'loader-picker-failure.png')});
        throw error;
    } finally { await browser.close(); }
})().catch(error => {console.error(error.stack); process.exitCode = 1;});
