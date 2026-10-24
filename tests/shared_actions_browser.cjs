/* Run against an isolated ComfyUI server containing the pack. */
const assert = require('node:assert/strict');
const {chromium} = require('playwright');
const base = process.argv[2] || 'http://127.0.0.1:8194';

(async () => {
    const browser = await chromium.launch({headless: true,
        ...(process.env.RAY_BROWSER_CHANNEL ? {channel: process.env.RAY_BROWSER_CHANNEL} : {})});
    try {
        const page = await browser.newPage({viewport: {width: 1500, height: 1200}});
        const errors = [];
        page.on('pageerror', error => errors.push(error.message));
        await page.goto(base);
        await page.waitForFunction(() => !!globalThis.comfyAPI?.app?.app?.graph
            && !!globalThis.LiteGraph?.registered_node_types?.RayLoraQKVLoader);
        await page.waitForTimeout(1500);
        await page.keyboard.press('Escape');
        const extensions = await (await page.request.get(base + '/extensions')).json();
        const moduleURL = await page.evaluate(() => performance.getEntriesByType('resource')
            .find(entry => new URL(entry.name).pathname.endsWith('/ray_panel.js'))?.name)
            || new URL(extensions.find(url => url.endsWith('/ray_panel.js')), base).href;
        assert.ok(moduleURL, 'Shared panel module must be loaded by the real pack');

        // Exercise the shared API outside an ordinary .rp panel, with gallery CSS present.
        await page.evaluate(async moduleURL => {
            const {createNodeHeader, iconButton} = await import(moduleURL);
            const {styles} = await import(new URL('./folders.css.js', moduleURL).href); styles();
            const fixture = document.createElement('div'); fixture.id = 'shared-action-fixture';
            fixture.className = 'ray-folders';
            Object.assign(fixture.style, {position: 'fixed', left: '20px', top: '80px',
                width: '340px', height: '90px', zIndex: '200000', background: '#000'});
            window.actionClicks = 0;
            const settings = iconButton('settings', 'Shared settings test', () => window.actionClicks++);
            const add = iconButton('plus', 'Shared Add test', () => {});
            const header = createNodeHeader('Items', [settings, add]);
            fixture.append(header.element); document.body.append(fixture);
            window.sharedActionFixture = {fixture, header};
        }, moduleURL);
        const settings = page.getByRole('button', {name: 'Shared settings test', exact: true});
        const measure = locator => locator.evaluate(button => ({
            width: button.offsetWidth, height: button.offsetHeight,
            glyph: [button.querySelector('svg').getBoundingClientRect().width,
                button.querySelector('svg').getBoundingClientRect().height],
            type: button.type, title: button.title, label: button.getAttribute('aria-label'),
        }));
        assert.deepEqual(await measure(settings), {width: 30, height: 30, glyph: [16, 16],
            type: 'button', title: 'Shared settings test', label: 'Shared settings test'});
        assert.deepEqual(await page.locator('#shared-action-fixture .rp-header-actions').evaluate(group =>
            [...group.children].map(button => button.dataset.icon)), ['plus', 'settings']);
        assert.deepEqual(await page.getByRole('button', {name: 'Shared Add test', exact: true})
            .evaluate(button => [button.offsetWidth, button.offsetHeight]), [32, 28]);
        await settings.hover();
        assert.equal(await settings.evaluate(button => getComputedStyle(button).backgroundColor), 'rgb(69, 71, 83)');
        await settings.focus(); await page.keyboard.press('Enter');
        assert.equal(await page.evaluate(() => window.actionClicks), 1, 'Keyboard activation uses the shared handler');
        assert.equal(await settings.evaluate(button => getComputedStyle(button).outlineWidth), '2px');
        assert.equal(await settings.evaluate(button => getComputedStyle(button).outlineColor), 'rgb(185, 164, 250)');
        await settings.evaluate(button => button.disabled = true);
        await settings.dispatchEvent('click');
        assert.equal(await page.evaluate(() => window.actionClicks), 1, 'Disabled actions cannot invoke their callback');
        assert.equal(await settings.evaluate(button => getComputedStyle(button).opacity), '0.4');
        const isolated = await settings.evaluate(button => {
            button.disabled = false;
            let keys = 0, pointers = 0;
            const key = () => keys++, pointer = () => pointers++;
            document.addEventListener('keydown', key); document.addEventListener('pointerdown', pointer);
            button.dispatchEvent(new KeyboardEvent('keydown', {key: 'x', bubbles: true}));
            button.dispatchEvent(new PointerEvent('pointerdown', {button: 0, bubbles: true}));
            document.removeEventListener('keydown', key); document.removeEventListener('pointerdown', pointer);
            return {keys, pointers};
        });
        assert.deepEqual(isolated, {keys: 0, pointers: 0}, 'Action gestures stay out of graph shortcuts and panning');
        await page.evaluate(() => { window.sharedActionFixture.header.destroy(); window.sharedActionFixture.fixture.remove(); });

        // A node action follows the first visible section and preserves focus between refreshes.
        const dynamic = await page.evaluate(async moduleURL => {
            const {installPanel} = await import(moduleURL);
            const mount = document.createElement('div'); document.body.append(mount);
            const node = {showFirst: true, isWidgetVisible: () => true,
                widgets: ['a', 'b'].map(name => ({name, type: 'text', value: name, options: {}}))};
            const panel = installPanel(node, {mount, settings: true,
                headerActions: [{icon: 'settings', title: 'Conditional settings', onClick() {}}],
                sections: [{title: 'First', when: node => node.showFirst, fields: ['a']},
                    {title: 'Second', actions: [{icon: 'plus', title: 'Add item', onClick() {}}], fields: ['b']}]});
            const cog = panel.root.querySelector('[data-icon="settings"]'); cog.focus();
            panel.refresh();
            const focus = document.activeElement === cog;
            node.showFirst = false; panel.refresh(); panel.refresh();
            const result = {focus, title: cog.closest('.rp-header').querySelector('.rp-title').textContent,
                icons: [...cog.parentElement.children].map(button => button.dataset.icon),
                cogs: panel.root.querySelectorAll('[data-icon="settings"]').length};
            panel.destroy(); result.headersAfterDestroy = mount.querySelectorAll('.rp-header').length;
            mount.remove(); return result;
        }, moduleURL);
        assert.deepEqual(dynamic, {focus: true, title: 'Second', icons: ['plus', 'settings'], cogs: 1, headersAfterDestroy: 0});

        // Metadata's section Add action keeps the existing parser/editor and workflow state.
        await page.evaluate(async () => {
            const {app} = await import('/scripts/app.js'); app.graph.clear();
            const node = LiteGraph.createNode('RayModelMetadata'); node.pos = [220, 120]; app.graph.add(node);
            app.canvas.ds.scale = 1; app.canvas.ds.offset = [0, 0]; app.canvas.setDirty(true, true);
            window.metadataActionNode = node;
        });
        const addField = page.getByRole('button', {name: 'Add field', exact: true});
        await addField.waitFor();
        assert.equal(await addField.evaluate(button => button.closest('.rp-header').querySelector('.rp-title').textContent), 'Metadata');
        await addField.click();
        const field = page.getByRole('textbox', {name: 'Value for new_field', exact: true});
        await field.fill('kept text'); await field.dispatchEvent('input');
        await addField.click();
        const values = () => page.evaluate(() => JSON.parse(window.metadataActionNode.widgets.find(widget => widget.name === 'editor_json').value));
        assert.deepEqual(await values(), {new_field: 'kept text', new_field_1: ''});
        await page.getByRole('button', {name: 'Table / JSON', exact: true}).click();
        assert.deepEqual(JSON.parse(await page.getByRole('textbox', {name: 'Raw metadata JSON', exact: true}).inputValue()), {new_field: 'kept text', new_field_1: ''});
        await addField.click();
        assert.deepEqual(await values(), {new_field: 'kept text', new_field_1: '', new_field_2: ''});
        const saved = await page.evaluate(async () => {
            const {app} = await import('/scripts/app.js'); return app.graph.serialize();
        });
        await page.evaluate(async saved => {
            const {app} = await import('/scripts/app.js'); await app.loadGraphData(saved);
            window.metadataActionNode = app.graph._nodes.find(node => node.type === 'RayModelMetadata');
        }, saved);
        await addField.waitFor();
        assert.equal(await addField.count(), 1, 'Metadata reload must keep one contextual Add action');
        assert.deepEqual(await values(), {new_field: 'kept text', new_field_1: '', new_field_2: ''});
        const removeField = page.getByRole('button', {name: 'Remove metadata field', exact: true});
        assert.equal(await removeField.count(), 3);
        await removeField.nth(1).click();
        assert.deepEqual(await values(), {new_field: 'kept text', new_field_2: ''});
        assert.deepEqual(errors, [], 'No frontend exceptions');
        console.log('Shared header and icon browser checks passed: gallery styles, size, glyph, order, keyboard, focus, disabled state, graph gesture isolation, conditional placement, refresh, teardown and metadata Add/table/JSON/workflow reload.');
    } finally { await browser.close(); }
})().catch(error => {console.error(error.stack); process.exitCode = 1;});
