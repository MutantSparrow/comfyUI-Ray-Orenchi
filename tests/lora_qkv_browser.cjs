/* Run against the isolated CPU server with the small model/adapter fixtures. */
const assert = require('node:assert/strict');
const path = require('node:path');
const {chromium} = require('playwright');
const base = process.argv[2] || 'http://127.0.0.1:8196';
const fixtures = process.argv[3];
if (!fixtures) throw Error('Pass the isolated fixture directory as the second argument.');
const first = path.join(fixtures, 'fused.safetensors'), second = path.join(fixtures, 'peft.safetensors');

(async () => {
    const browser = await chromium.launch({headless: true});
    let page;
    try {
        page = await browser.newPage({viewport: {width: 1500, height: 1200}});
        const errors = [];
        page.on('pageerror', error => errors.push(error.message));
        await page.route(/\/(?:api\/)?models\/loras$/, route => route.fulfill({json: [first, second, path.join(fixtures, 'missing.safetensors')]}));
        await page.goto(base);
        await page.waitForFunction(() => !!globalThis.comfyAPI?.app?.app?.graph);
        await page.evaluate(async () => {
            const {app} = await import('/scripts/app.js');
            await app.ui.settings.setSettingValue('Comfy.VueNodes.Enabled', true);
        });
        await page.reload();
        await page.waitForFunction(() => !!globalThis.LiteGraph?.registered_node_types?.LoraQKVProbeCheck);
        await page.waitForTimeout(1500);
        await page.evaluate(async () => {
            const {app} = await import('/scripts/app.js');
            app.graph.clear();
            window.loader = LiteGraph.createNode('RayLoraQKVLoader');
            window.loader.pos = [240, 150]; app.graph.add(window.loader);
            app.canvas.ds.scale = 1; app.canvas.ds.offset = [0, 0]; app.canvas.setDirty(true, true);
        });
        const source = index => page.getByRole('combobox', {name: `LoRA ${index}`, exact: true});
        const amount = index => page.getByRole('spinbutton', {name: `LoRA ${index} strength`, exact: true});
        const edit = async (locator, value) => {
            if (await locator.getAttribute('role') === 'combobox') {
                const label = await locator.getAttribute('aria-label');
                await locator.click(); await page.getByRole('textbox', {name: `Filter ${label}`, exact: true}).fill(value);
                await page.getByRole('menuitem', {name: value, exact: true}).click();
            } else { await locator.fill(value); await locator.press('Tab'); }
        };
        await source(1).waitFor();
        await edit(source(1), first); await edit(amount(1), '0.5');
        await page.getByRole('button', {name: 'Add LoRA', exact: true}).click();
        await edit(source(2), second); await edit(amount(2), '-0.25');
        assert.equal(await amount(1).inputValue(), '0.5');
        assert.equal(await amount(2).inputValue(), '-0.25');
        const drag = async (index, dx, {shift = false, live} = {}) => {
            await amount(index).evaluate(input => input.blur());
            const bounds = await amount(index).boundingBox();
            const x = bounds.x + bounds.width / 2, y = bounds.y + bounds.height / 2;
            await page.mouse.move(x, y);
            if (shift) await page.keyboard.down('Shift');
            await page.mouse.down(); await page.mouse.move(x + dx, y, {steps: 8});
            if (live !== undefined) assert.equal(await page.evaluate(index => {
                const node = window.loader;
                return index === 1 ? node.widgets.find(item => item.name === 'strength').value
                    : JSON.parse(node.widgets.find(item => item.name === 'additional_loras').value)[index - 2].strength;
            }, index), live, 'Dragging must update the queued value before release');
            await page.mouse.up();
            if (shift) await page.keyboard.up('Shift');
        };
        await page.evaluate(async () => {
            const {app} = await import('/scripts/app.js');
            window.dragChanges = {before: 0, after: 0};
            for (const name of ['beforeChange', 'afterChange']) {
                const original = app.graph[name];
                app.graph[name] = function () {
                    window.dragChanges[name === 'beforeChange' ? 'before' : 'after']++;
                    return original?.apply(this, arguments);
                };
            }
        });
        await drag(1, 120, {live: .7});
        assert.equal(await amount(1).inputValue(), '0.7');
        assert.equal(await amount(2).inputValue(), '-0.25', 'Scrubbing one row must preserve other strengths');
        assert.deepEqual(await page.evaluate(() => window.dragChanges), {before: 1, after: 1}, 'A drag must form one graph change');
        await drag(1, -120); assert.equal(await amount(1).inputValue(), '0.5');
        await drag(2, -120, {live: -.45}); assert.equal(await amount(2).inputValue(), '-0.45');
        await drag(2, 120); assert.equal(await amount(2).inputValue(), '-0.25');
        await drag(1, 120, {shift: true, live: .52}); assert.equal(await amount(1).inputValue(), '0.52');
        await page.getByRole('button', {name: 'Increase LoRA 1 strength', exact: true}).click();
        assert.equal(await amount(1).inputValue(), '0.53', 'Buttons must continue from the fine drag value');
        await edit(amount(1), '99.99'); await drag(1, 120); assert.equal(await amount(1).inputValue(), '100');
        await edit(amount(1), '-99.99'); await drag(1, -120); assert.equal(await amount(1).inputValue(), '-100');
        await amount(1).click(); await edit(amount(1), '0.5');
        await page.getByRole('button', {name: 'Remove LoRA 1', exact: true}).click();
        assert.equal(await source(1).textContent(), second, 'Removing first must promote the complete second row');
        assert.equal(await amount(1).inputValue(), '-0.25');
        await edit(source(1), first); await edit(amount(1), '0.5');
        await page.getByRole('button', {name: 'Add LoRA', exact: true}).click();
        await edit(source(2), second); await edit(amount(2), '-0.25');
        await page.getByRole('button', {name: 'Add LoRA', exact: true}).click();
        await edit(source(3), path.join(fixtures, 'missing.safetensors')); await edit(amount(3), '0');
        await source(1).click(); await page.getByRole('textbox', {name: 'Filter LoRA 1', exact: true}).waitFor();
        await page.keyboard.press('Escape');
        assert.equal(await source(1).textContent(), first, 'Picker cancellation preserves the selection');
        const saved = await page.evaluate(async () => {
            const {app} = await import('/scripts/app.js'); return app.graph.serialize();
        });
        const savedLoader = saved.nodes.find(node => node.type === 'RayLoraQKVLoader');
        assert.equal(savedLoader.widgets_values[0], first);
        assert.equal(savedLoader.widgets_values[1], .5);
        assert.deepEqual(JSON.parse(savedLoader.widgets_values[2]), [{name: second, strength: -.25}, {name: path.join(fixtures, 'missing.safetensors'), strength: 0}]);
        await page.evaluate(async saved => {
            const {app} = await import('/scripts/app.js'); await app.loadGraphData(saved);
            window.loader = app.graph._nodes.find(node => node.type === 'RayLoraQKVLoader');
        }, saved);
        assert.equal(await source(2).textContent(), second);
        assert.equal(await amount(2).inputValue(), '-0.25');
        await page.evaluate(async first => {
            const {app} = await import('/scripts/app.js');
            const upstream = LiteGraph.createNode('LoraQKVProbeString'); app.graph.add(upstream);
            upstream.widgets.find(widget => widget.name === 'value').value = first;
            let slot = window.loader.inputs.findIndex(input => input.name === 'lora_name');
            if (slot < 0) { window.loader.addInput('lora_name', 'STRING', {widget: {name: 'lora_name'}}); slot = window.loader.inputs.length - 1; }
            upstream.connect(0, window.loader, slot); window.upstream = upstream;
            window.loader._rayLoraQKV.refresh();
        }, first);
        assert.equal(await page.getByRole('button', {name: 'Remove LoRA 1', exact: true}).isDisabled(), true);
        assert.equal(await source(1).isVisible(), false);
        const prompt = await page.evaluate(async () => {
            const {app} = await import('/scripts/app.js');
            const model = LiteGraph.createNode('LoraQKVProbeModel'); model.pos = [20, 80]; app.graph.add(model);
            const output = LiteGraph.createNode('LoraQKVProbeCheck'); output.pos = [850, 150]; app.graph.add(output);
            model.connect(0, window.loader, window.loader.inputs.findIndex(input => input.name === 'model'));
            window.loader.connect(0, output, 0); window.probe = output;
            return app.graphToPrompt();
        });
        const loaderId = await page.evaluate(() => String(window.loader.id));
        const probeId = await page.evaluate(() => String(window.probe.id));
        assert(Array.isArray(prompt.output[loaderId].inputs.lora_name), 'The linked filename must be serialized as a link');
        const submitted = await page.evaluate(async prompt => {
            const {api} = await import('/scripts/api.js'); return api.queuePrompt(0, prompt);
        }, prompt);
        assert(submitted.prompt_id);
        const completed = await page.waitForFunction(async id => {
            const history = await (await fetch('/history/' + id)).json();
            return history[id]?.status?.completed ? history[id] : false;
        }, submitted.prompt_id);
        const job = await completed.jsonValue();
        assert.equal(job.status.status_str, 'success', JSON.stringify(job.status));
        const report = job.outputs[probeId].probe[0];
        assert.deepEqual(Object.values(report.sums), [0, 16, 16]);
        assert.deepEqual(Object.values(report.counts), [2, 1, 1]);
        assert.equal(job.outputs[loaderId].lora_qkv[0].split, 1);
        assert.equal(job.outputs[loaderId].lora_qkv[2].skipped, true);
        await page.waitForFunction(() => window.loader._rayLoraQKV.status.textContent.includes('QKV split'));
        const status = await page.locator('.rlq-loras [role=status]').textContent();
        assert.match(status, /3 weights loaded.*1 QKV split/);
        assert.match(status, /skipped \(strength 0\)/);
        // Unlink using the shared control and ensure the dropdown becomes available again.
        await page.locator('.rlq-loras .rp-link').filter({hasText: 'LoraQKVProbeString'}).getByRole('button').click();
        assert.equal(await source(1).isVisible(), true);
        assert.equal(await source(1).isEnabled(), true);
        assert.deepEqual(errors, []);
        console.log('Nodes 2.0 browser and execution checks passed: horizontal strength dragging, fine adjustment, live values, bounds, grouped graph changes, direct entry, add/remove, independent strengths, picker cancellation, serialization, linked filename, exact native patch values, repair status and zero-strength skip.');
    } catch (error) {
        if (page) {
            console.error(await page.evaluate(() => ({
                node: window.loader?.type, panel: !!window.loader?._rayLoraQKV,
                text: document.body.innerText.slice(-3000),
            })));
            await page.screenshot({path: path.join(fixtures, 'browser-failure.png')});
        }
        throw error;
    } finally { await browser.close(); }
})().catch(error => { console.error(error.stack); process.exitCode = 1; });
