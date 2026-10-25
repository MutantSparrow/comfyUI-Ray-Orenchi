/* Read-only schema checks and isolated frontend checks for every registered node. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const {chromium} = require('playwright');
const base = process.argv[2] || 'http://127.0.0.1:8194';

(async () => {
    const browser = await chromium.launch({headless:true,
        ...(process.env.RAY_BROWSER_CHANNEL ? {channel:process.env.RAY_BROWSER_CHANNEL} : {})});
    const results = [];
    try {
        const page = await browser.newPage({viewport:{width:1800,height:2200}});
        const errors = [];
        page.on('pageerror', error => errors.push(error.message));
        const info = await (await page.request.get(base + '/object_info')).json();
        const nodes = Object.entries(info).filter(([id]) => id.startsWith('Ray'));
        const reference = fs.readFileSync(require('node:path').join(__dirname,'../NODE_REFERENCE.md'),'utf8');
        for (const [id, data] of nodes) {
            assert(data.description?.trim(), `${id}: missing description`);
            assert(reference.includes(`id="${id}"`), `${id}: missing reference section`);
            for (const group of ['required','optional']) for (const [name, spec] of Object.entries(data.input[group] || {})) {
                assert(spec[1]?.tooltip?.trim().length > 15, `${id}.${name}: missing or unhelpful tooltip`);
                assert.notEqual(spec[1].tooltip.trim(),name);
            }
            assert.equal(data.output_tooltips?.length || 0,data.output.length,`${id}: output help count`);
            for (const tip of data.output_tooltips || []) assert(tip.trim().length > 8,`${id}: missing output description`);
        }
        for (const modern of [true,false]) {
            await page.goto(base);
            await page.waitForFunction(() => !!globalThis.LiteGraph?.registered_node_types?.RayModelMetadata);
            await page.evaluate(async enabled => {
                const {app} = await import('/scripts/app.js'); app.graph.clear();
                await app.ui.settings.setSettingValue('Comfy.VueNodes.Enabled',enabled);
            },modern);
            await page.reload();
            await page.waitForFunction(() => !!globalThis.LiteGraph?.registered_node_types?.RayModelMetadata);
            await page.waitForTimeout(900);
            for (const [id] of nodes) {
                await page.evaluate(async id => {
                    const {app}=await import('/scripts/app.js'); app.graph.clear();
                    const node=LiteGraph.createNode(id); app.graph.add(node); node.pos=[240,160];
                    app.canvas.ds.scale=1; app.canvas.ds.offset=[0,0]; app.canvas.setDirty(true,true);
                    window.contractNode=node;
                },id);
                await page.waitForTimeout(220);
                const result=await page.evaluate(() => {
                    const node=window.contractNode;
                    const root=node._rayPanel?.root || node._rayFolders?.root || node._raySave?.root || node._rayAnalog?.element;
                    if (!root) throw Error('Missing node interface');
                    const visible=element=>element.getBoundingClientRect().height>0;
                    const failures=[];
                    for(const row of node._rayPanel?.rows || []) if(row.widget) {
                        const schema=node.constructor.nodeData.input;
                        const tip=(schema.required?.[row.name] || schema.optional?.[row.name])?.[1]?.tooltip;
                        if(!tip || row.element.title!==tip) failures.push(`Unbound tooltip: ${row.name}`);
                    }
                    for(const heading of [...root.querySelectorAll('.rp-title')].filter(visible)) {
                        const style=getComputedStyle(heading);
                        if(style.color!=='rgb(212, 58, 168)' || style.textTransform!=='uppercase')failures.push('Heading style');
                    }
                    for(const section of [...root.querySelectorAll('.rp-section')].filter(visible)) {
                        if(!section.querySelector(':scope > .rp-title, :scope > .rp-header > .rp-title'))failures.push('Untitled section');
                        const earlier=[...section.parentElement.children].slice(0,[...section.parentElement.children].indexOf(section))
                            .some(s=>s.matches('.rp-section:not([hidden])')&&visible(s));
                        if((parseFloat(getComputedStyle(section).borderTopWidth)>0)!==earlier)failures.push('Section divider');
                    }
                    const cogs=[...root.querySelectorAll('[data-icon="settings"]')].filter(visible);
                    if(cogs.length>1)failures.push('Duplicate settings action');
                    for(const cog of cogs) {
                        const r=cog.getBoundingClientRect(),header=cog.closest('.rp-header');
                        if(r.width!==30 || r.height!==30 || !header || cog.parentElement.lastElementChild!==cog)failures.push('Settings size/placement');
                    }
                    return {id:node.comfyClass,failures,rows:node._rayPanel?.rows.filter(r=>r.widget).length || 0,
                        headings:[...root.querySelectorAll('.rp-title')].filter(visible).map(e=>e.textContent)};
                });
                assert.deepEqual(result.failures,[],`${modern?'Nodes 2.0':'legacy'} ${id}`);
                results.push({renderer:modern?'Nodes 2.0':'legacy',...result});
            }
            console.log(`${modern?'Nodes 2.0':'legacy'}: all ${nodes.length} node interfaces passed.`);
        }

        // Custom popup controls also use the shared visual hierarchy and preserve Apply/Cancel.
        await page.evaluate(async () => {
            const {app}=await import('/scripts/app.js'); app.graph.clear();
            const node=LiteGraph.createNode('RayFolders'); app.graph.add(node); node.pos=[240,160];
            window.contractNode=node;
        });
        await page.getByRole('button',{name:'Folders settings',exact:true}).click();
        const popup=page.getByRole('dialog',{name:'Folders settings',exact:true});
        assert.equal(await popup.evaluate(e=>getComputedStyle(e).backgroundColor),'rgb(0, 0, 0)');
        assert.equal(await popup.locator('.rp-section').count(),4);
        for(const heading of await popup.locator('.rp-title').all())
            assert.equal(await heading.evaluate(e=>getComputedStyle(e).color),'rgb(212, 58, 168)');
        const recursive=popup.getByRole('switch',{name:'Include subfolders',exact:true});
        await recursive.click();
        assert.equal(await recursive.getAttribute('aria-checked'),'true');
        await popup.getByRole('button',{name:'Cancel',exact:true}).click();
        assert.equal(await page.evaluate(()=>JSON.parse(window.contractNode.widgets.find(w=>w.name==='settings_json').value).recursive),undefined);
        await page.getByRole('button',{name:'Folders settings',exact:true}).click();
        await popup.getByRole('switch',{name:'Include subfolders',exact:true}).click();
        await popup.getByRole('button',{name:'Apply',exact:true}).click();
        assert.equal(await page.evaluate(()=>JSON.parse(window.contractNode.widgets.find(w=>w.name==='settings_json').value).recursive),true);
        for(const [id,action,selector] of [
            ['RaySaveImage','Build filename','.ray-name'],
            ['RayButtonDeck','Edit the entries, one per line','.ray-deck-editor'],
        ]) {
            await page.evaluate(async id=>{const {app}=await import('/scripts/app.js');app.graph.clear();const n=LiteGraph.createNode(id);app.graph.add(n);n.pos=[240,160];},id);
            await page.getByRole('button',{name:action,exact:true}).click();
            const dialog=page.locator(selector);
            assert.equal(await dialog.evaluate(e=>getComputedStyle(e).backgroundColor),'rgb(0, 0, 0)');
            assert.equal(await dialog.locator('.rp-title').evaluate(e=>getComputedStyle(e).color),'rgb(212, 58, 168)');
            await page.keyboard.press('Escape');
        }
        // The curve editor uses the shared surface, controls, focus, and live state.
        const panelURL=await page.evaluate(()=>performance.getEntriesByType('resource')
            .find(entry=>new URL(entry.name).pathname.endsWith('/ray_panel.js'))?.name);
        await page.evaluate(async panelURL=>{
            const {app}=await import('/scripts/app.js');app.graph.clear();
            const node=LiteGraph.createNode('RayKnob');app.graph.add(node);window.contractNode=node;
            const {openCurveEditor}=await import(new URL('./analog_curve.js',panelURL));openCurveEditor(node);
        },panelURL);
        const curve=page.getByRole('dialog',{name:'Response curve',exact:true});
        assert.equal(await curve.evaluate(e=>getComputedStyle(e).backgroundColor),'rgb(0, 0, 0)');
        assert.equal(await curve.locator('.rp-title').evaluate(e=>getComputedStyle(e).color),'rgb(212, 58, 168)');
        await curve.getByRole('button',{name:'Curve',exact:true}).click();
        assert.equal(await page.evaluate(()=>window.contractNode.properties.response),'curve');
        const done=curve.getByRole('button',{name:'Done',exact:true});await done.focus();
        assert.equal(await done.evaluate(e=>getComputedStyle(e).outlineColor),'rgb(185, 164, 250)');
        await done.click();
        await page.evaluate(async panelURL=>{
            const {openCurveEditor}=await import(new URL('./analog_curve.js',panelURL));
            openCurveEditor(window.contractNode);const previous=window.contractNode._rayCurveEditor;
            openCurveEditor(window.contractNode);previous.close();
        },panelURL);
        assert.equal(await page.locator('.ray-curve-editor').count(),1);

        // Mode-dependent native dialogs and hidden fields agree with the writer.
        const dialogs=[];
        await page.route('**/ray/browse',async route=>{
            dialogs.push(route.request().postDataJSON());
            await route.fulfill({json:{ok:true,cancelled:true}});
        });
        await page.evaluate(async()=>{const {app}=await import('/scripts/app.js');app.graph.clear();
            const node=LiteGraph.createNode('RayMetaInspect');app.graph.add(node);node.pos=[240,160];window.contractNode=node;});
        assert.equal(await page.locator('.ray-curve-editor').count(),0);
        await page.getByRole('button',{name:'Choose an image',exact:true}).click();
        await page.waitForFunction(()=>!window.contractNode._rayPanel.rows.find(r=>r.name==='metadata_json').element.checkVisibility());
        assert.equal(dialogs.at(-1).kind,'file');
        await page.evaluate(()=>{const n=window.contractNode,w=n.widgets.find(w=>w.name==='mode');n._rayPanel.write(w,'Embed');});
        await page.getByRole('button',{name:'Save metadata PNG as',exact:true}).click();
        assert.equal(dialogs.at(-1).kind,'save');
        assert.deepEqual(dialogs.at(-1).filters,[['PNG image',['png']]]);
        assert.equal(await page.evaluate(()=>window.contractNode.widgets.find(w=>w.name==='path').value),'');
        assert.equal(await page.getByRole('switch',{name:'Overwrite',exact:true}).getAttribute('aria-checked'),'false');
        await page.unroute('**/ray/browse');

        // Typing inside a custom metadata editor cannot trigger canvas shortcuts.
        await page.evaluate(async()=>{const {app}=await import('/scripts/app.js');app.graph.clear();
            const node=LiteGraph.createNode('RayModelMetadata');app.graph.add(node);node.pos=[240,160];
            node._rayMetadataEditor.addField();window.contractNode=node;window.contractKeys=0;
            document.addEventListener('keydown',()=>window.contractKeys++);});
        await page.getByRole('textbox',{name:'Metadata key',exact:true}).fill('typed_key');
        await page.getByRole('textbox',{name:'Metadata key',exact:true}).press('Delete');
        assert.equal(await page.evaluate(()=>window.contractKeys),0);
        assert.equal(await page.evaluate(()=>JSON.parse(window.contractNode.widgets.find(w=>w.name==='editor_json').value).typed_key),'');
        let pendingPreview;
        const receivedPreview=new Promise(resolve=>{
            page.route('**/ray/model-tools/preview',route=>{pendingPreview=route;resolve();});
        });
        await page.evaluate(()=>{const n=window.contractNode;n._rayPanel.write(n.widgets.find(w=>w.name==='path'),'old-source.safetensors');});
        await page.getByRole('button',{name:'Load / Edit',exact:true}).click();
        await receivedPreview;
        await page.evaluate(()=>{const n=window.contractNode;n._rayPanel.write(n.widgets.find(w=>w.name==='path'),'new-source.safetensors');});
        await pendingPreview.fulfill({json:{metadata:{stale:'must not replace edits'},source:'old-source.safetensors'}});
        await page.waitForTimeout(200);
        assert.deepEqual(await page.evaluate(()=>JSON.parse(window.contractNode.widgets.find(w=>w.name==='editor_json').value)),{typed_key:''});
        await page.unroute('**/ray/model-tools/preview');
        assert.deepEqual(errors,[], 'Frontend errors');
        if(process.env.RAY_CONTRACT_RESULT)fs.writeFileSync(process.env.RAY_CONTRACT_RESULT,JSON.stringify({nodes:nodes.length,results,errors},null,2));
        console.log('Schema documentation, tooltip binding, shared popup styling, and settings transactions passed.');
    } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
