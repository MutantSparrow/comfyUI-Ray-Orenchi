#!/usr/bin/env node
/** Capture real, unexecuted Nodes 2.0 nodes from an isolated ComfyUI server. */
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const {execFileSync} = require('node:child_process');
const {chromium} = require('playwright');

const repo = path.resolve(__dirname, '..');
const args = process.argv.slice(2);
function option(name, fallback) {
    const index = args.indexOf(name);
    return index < 0 ? fallback : args[index + 1];
}
const url = option('--url', 'http://127.0.0.1:8191');
const python = option('--python', 'python');
const browserChannel = option('--browser-channel', '');
const requested = option('--node', '').split(',').filter(Boolean);
const output = path.join(repo, 'screenshots');
const manifestPath = path.join(output, 'manifest.json');
const scale = 2;
const padding = 24;
const digest = data => crypto.createHash('sha256').update(data).digest('hex');
const registration = fs.readFileSync(path.join(repo, '__init__.py'), 'utf8');
const modules = Object.fromEntries([...registration.split('_NODE_MODULES = {')[1].split('\n}')[0]
    .matchAll(/"(Ray\w+)":\s*"([\w]+)"/g)].map(m => [m[1], m[2]]));

async function ready(page) {
    await page.waitForFunction(() => !!globalThis.comfyAPI?.app?.app?.graph, undefined, {timeout:90000});
    await page.waitForFunction(() => {
        if (typeof globalThis.LiteGraph?.registered_node_types?.RayModelMetadata !== 'function') {
            window.rayScreenshotReady = 0;
            return false;
        }
        window.rayScreenshotReady ||= performance.now();
        return performance.now() - window.rayScreenshotReady > 1200;
    }, undefined, {timeout:90000});
}

async function settle(page, selector) {
    let previous = '', stable = 0;
    for (let attempt = 0; attempt < 80; attempt++) {
        const box = await page.locator(selector).boundingBox();
        const current = JSON.stringify(box);
        stable = current === previous ? stable + 1 : 0;
        if (box && stable >= 8) return box;
        previous = current;
        await page.waitForTimeout(100);
    }
    throw Error(`Node layout did not settle: ${selector}`);
}

(async () => {
    const unknown = requested.filter(id => !modules[id]);
    if (unknown.length) throw Error(`Unknown nodes: ${unknown.join(', ')}`);
    const classes = requested.length ? requested : Object.keys(modules);
    const fingerprints = JSON.parse(execFileSync(python,
        [path.join(__dirname,'check_node_screenshots.py'),'--sources-json'],{encoding:'utf8'}));
    const browser = await chromium.launch({headless:true, ...(browserChannel ? {channel:browserChannel} : {})});
    try {
        const page = await browser.newPage({viewport:{width:1800,height:2000}, deviceScaleFactor:scale});
        const errors = [];
        page.on('pageerror', error => errors.push(error.message));
        await page.goto(url);
        await ready(page);
        await page.evaluate(async () => {
            const {app} = await import('/scripts/app.js');
            await app.ui.settings.setSettingValue('Comfy.VueNodes.Enabled', true);
        });
        await page.reload();
        await ready(page);
        await page.evaluate(async () => {
            const {app} = await import('/scripts/app.js');
            app.graph.clear();
            app.extensionManager?.toast?.removeAll?.();
            await document.fonts.ready;
        });
        await page.waitForTimeout(800);
        const info = await (await page.request.get(`${url.replace(/\/$/, '')}/object_info`)).json();
        const stats = await (await page.request.get(`${url.replace(/\/$/, '')}/system_stats`)).json();
        fs.mkdirSync(output, {recursive:true});
        const manifest = requested.length && fs.existsSync(manifestPath)
            ? JSON.parse(fs.readFileSync(manifestPath, 'utf8')) : {schema:1, nodes:{}};
        manifest.renderer = 'ComfyUI Nodes 2.0';
        manifest.device_scale_factor = scale;
        manifest.zoom = 1;
        manifest.padding_css_px = padding;
        manifest.comfyui_version = stats.system?.comfyui_version;
        manifest.frontend_version = stats.system?.comfy_package_versions
            ?.find(item => item.name === 'comfyui-frontend-package')?.installed;
        manifest.browser_version = browser.version();
        manifest.platform = process.platform;
        for (const classId of classes) {
            const definition = info[classId];
            const category = /^👑 Ray\/(\S+) (.+)$/.exec(definition?.category || '');
            if (!category || !definition.display_name.startsWith(`${category[1]} Ray's ${category[2]}: `))
                throw Error(`Inconsistent category or title: ${classId}`);
            const id = await page.evaluate(async classId => {
                const {app} = await import('/scripts/app.js');
                app.graph.clear();
                app.canvas.deselectAllNodes();
                const node = LiteGraph.createNode(classId);
                if (!node) throw Error(`Cannot instantiate ${classId}`);
                node.pos = [240,200];
                app.graph.add(node);
                window.rayScreenshotNode = node;
                app.canvas.ds.scale = 1;
                app.canvas.ds.offset = [0,0];
                app.canvas.setDirty(true,true);
                app.extensionManager?.toast?.removeAll?.();
                return String(node.id);
            }, classId);
            const selector = `.lg-node[data-node-id="${id}"]`;
            await page.waitForSelector(selector, {timeout:15000}); // Also proves Nodes 2.0 is active.
            let box = await settle(page, selector);
            // Widen only if necessary to reveal the complete registered title/port labels.
            // Widget values and node properties remain at their on-create defaults.
            for (let attempt = 0; attempt < 6; attempt++) {
                const extra = await page.locator(selector).evaluate(element => Math.max(0,
                    ...[...element.querySelectorAll('[data-testid="node-title"] .truncate, .lg-slot .truncate')]
                        .map(label => label.scrollWidth - label.clientWidth)));
                if (extra <= 1) break;
                await page.evaluate(extra => {
                    const node = window.rayScreenshotNode;
                    node.setSize([node.size[0] + extra + 24, node.size[1]]);
                }, extra);
                box = await settle(page, selector);
            }
            await page.setViewportSize({width:Math.max(1800,Math.ceil(box.width+600)),
                height:Math.max(1200,Math.ceil(box.y+box.height+180))});
            await page.mouse.move(100,110);
            box = await settle(page, selector);
            const details = await page.locator(selector).evaluate(element => {
                const node = window.rayScreenshotNode;
                const rect = element.getBoundingClientRect();
                const title = element.querySelector('[data-testid="node-title"]');
                const cut = [...element.querySelectorAll('[data-testid="node-title"] .truncate, .lg-slot .truncate')]
                    .filter(label => label.scrollWidth > label.clientWidth + 1).map(label => label.textContent);
                if (cut.length) throw Error(`Truncated title/ports: ${cut.join(', ')}`);
                for (const host of element.querySelectorAll('.rp-host')) {
                    const panel = host.querySelector('.rp');
                    if (panel && panel.getBoundingClientRect().bottom > host.getBoundingClientRect().bottom+2)
                        throw Error('Custom panel is clipped');
                }
                const headings = [...element.querySelectorAll('.rp-title')]
                    .filter(heading => heading.getBoundingClientRect().height > 0);
                if (!headings.length) throw Error('Missing section headings');
                for (const heading of headings) {
                    const style = getComputedStyle(heading);
                    if (!heading.textContent.trim() || style.textTransform !== 'uppercase' || style.color !== 'rgb(212, 58, 168)')
                        throw Error(`Inconsistent section heading: ${heading.textContent}`);
                }
                for (const section of element.querySelectorAll('.rp-section:not([hidden])')) {
                    if (!section.getBoundingClientRect().height) continue;
                    if (!section.querySelector(':scope > .rp-title, :scope > .rp-header > .rp-title')) throw Error('Untitled control section');
                    const preceding = [...section.parentElement.children].slice(0, [...section.parentElement.children].indexOf(section))
                        .some(sibling => sibling.matches('.rp-section:not([hidden])') && sibling.getBoundingClientRect().height > 0);
                    if ((parseFloat(getComputedStyle(section).borderTopWidth) > 0) !== preceding)
                        throw Error(`Inconsistent section separator: ${section.textContent.slice(0, 50)}`);
                }
                const settings = [...element.querySelectorAll('button[data-icon="settings"]')]
                    .filter(button => button.getBoundingClientRect().height > 0);
                if (settings.length > 1) throw Error('Duplicate settings entry points');
                for (const button of settings) {
                    const box = button.getBoundingClientRect();
                    const group = button.closest('.rp-header-actions');
                    const header = group?.closest('.rp-header');
                    const section = header?.parentElement;
                    const first = [...section?.parentElement?.children || []]
                        .find(item => item.matches('.rp-section:not([hidden])') && item.getBoundingClientRect().height > 0);
                    if (Math.abs(box.width-30) > .5 || Math.abs(box.height-30) > .5)
                        throw Error('Settings button must have a 30 by 30 CSS-pixel hit target');
                    if (!header || section !== first || group.lastElementChild !== button)
                        throw Error('Settings must be rightmost in the first visible section header');
                    if (Math.abs(box.right-header.getBoundingClientRect().right) > 1)
                        throw Error('Settings button is not aligned to the header right edge');
                    if (!button.title || !button.getAttribute('aria-label') || button.type !== 'button')
                        throw Error('Settings button is missing its accessible action label');
                }
                const visible = direction => [...element.querySelectorAll(`.lg-slot--${direction}`)]
                    .filter(slot => slot.getBoundingClientRect().height > 0)
                    .map(slot => slot.textContent.trim());
                return {title:title?.textContent.trim(), inputs:visible('input'), outputs:visible('output'),
                    sections:headings.map(heading => heading.textContent.trim()),
                    default_widgets:Object.fromEntries((node.widgets || []).filter(w => w.name && !w.element)
                        .map(w => [w.name,w.value]).filter(([,value]) => value !== undefined)),
                    width_css_px:rect.width, height_css_px:rect.height};
            });
            const clip = {x:Math.floor(box.x-padding),y:Math.floor(box.y-padding),
                width:Math.ceil(box.width+padding*2),height:Math.ceil(box.height+padding*2)};
            if (clip.x < 0 || clip.y < 0) throw Error(`Frame outside viewport: ${classId}`);
            const filename = `${classId}.png`;
            const bytes = await page.screenshot({path:path.join(output,filename),clip,animations:'disabled'});
            manifest.nodes[classId] = {file:filename, display_name:info[classId]?.display_name,
                ...details, source_fingerprint:fingerprints[classId],
                sha256:digest(bytes), captured_at:new Date().toISOString()};
            console.log(`${classId}: ${Math.round(clip.width*scale)} × ${Math.round(clip.height*scale)}, `+
                `${details.inputs.length} inputs / ${details.outputs.length} outputs`);
        }
        if (errors.length) throw Error(`Frontend errors: ${[...new Set(errors)].join('\n')}`);
        manifest.nodes = Object.fromEntries(Object.entries(manifest.nodes).sort(([a],[b])=>a.localeCompare(b)));
        fs.writeFileSync(manifestPath, JSON.stringify(manifest,null,2)+'\n');
        console.log(`Saved ${classes.length} real Nodes 2.0 screenshots to ${output}`);
    } finally { await browser.close(); }
})().catch(error => {console.error(error.stack);process.exitCode=1;});
