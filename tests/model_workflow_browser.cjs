/* Use an isolated ComfyUI instance; no real inference models are loaded. */
const assert=require('node:assert/strict');
const {chromium}=require('playwright');
const base=process.argv[2]||'http://127.0.0.1:8191';
(async()=>{
 const browser=await chromium.launch({headless:true});let current;
 try {
  for(const nodes2 of [true,false]) {
   const page=current=await browser.newPage({viewport:{width:1900,height:1500}});page.setDefaultTimeout(20000);
   const errors=[];page.on('pageerror',e=>errors.push(e.message));
   await page.route(/\/(?:api\/)?models\/diffusion_models$/,r=>r.fulfill({json:['MOSS/Alpha.safetensors','MOSS/Alpha changed.safetensors']}));
   await page.route(/\/(?:api\/)?models\/checkpoints$/,r=>r.fulfill({json:['Family/Beta.safetensors']}));
   await page.goto(base);await page.waitForFunction(()=>!!globalThis.LiteGraph?.registered_node_types?.RayModelMerge);
   await page.evaluate(async enabled=>{const{app}=await import('/scripts/app.js');await app.ui.settings.setSettingValue('Comfy.VueNodes.Enabled',enabled);},nodes2);
   await page.reload();await page.waitForFunction(()=>!!globalThis.LiteGraph?.registered_node_types?.RayModelMerge);
   await page.waitForTimeout(2000);await page.keyboard.press('Escape');
   await page.evaluate(async()=>{
    const{app}=await import('/scripts/app.js');app.graph.clear();
    for(const[key,type,x]of[['a','RayModelLoadAs',100],['b','RayModelLoadAs',680],['merge','RayModelMerge',1260]]){
     const node=LiteGraph.createNode(type);app.graph.add(node);node.pos=[x,150];window[key]=node;
    }
    window.a.connect(3,window.merge,window.merge.inputs.findIndex(i=>i.name==='data_a'));
    window.b.connect(3,window.merge,window.merge.inputs.findIndex(i=>i.name==='data_b'));
    app.canvas.ds.scale=.9;app.canvas.ds.offset=[0,0];app.canvas.setDirty(true,true);
   });
   const pick=page.getByRole('combobox',{name:'Model',exact:true});await pick.first().waitFor();
   const choose=async(index,query,item)=>{await pick.nth(index).click();await page.getByRole('textbox',{name:'Filter Model',exact:true}).fill(query);await page.getByRole('menuitem',{name:item,exact:true}).click();};
   await choose(0,'Alpha.safetensors','Diffusion models/MOSS/Alpha.safetensors');
   await choose(1,'Beta','Checkpoints/Family/Beta.safetensors');
   const preview=page.getByLabel('Merge name',{exact:true});
   await page.waitForFunction(()=>window.merge._rayMergeName.name.includes('A-Alpha_B-Beta_LERP_50-50_bf16'));
   const first=await preview.textContent();
   await choose(0,'changed','Diffusion models/MOSS/Alpha changed.safetensors');
   await page.waitForFunction(()=>window.merge._rayMergeName.name.includes('A-Alpha_changed_'));
   assert.notEqual(await preview.textContent(),first);
   await page.evaluate(()=>{const w=window.merge.widgets.find(w=>w.name==='weight_a');w.value=.25;w.callback?.(.25);});
   await page.waitForFunction(()=>window.merge._rayMergeName.name.includes('_25-75_'));
   assert.equal(await page.getByRole('button',{name:'Copy report',exact:true}).count(),0);
   assert.equal(await page.getByRole('switch',{name:'Load result',exact:true}).count(),0);
   const ports=await page.evaluate(()=>window.merge.outputs.map(o=>o.name));assert.equal(ports[6],'merge_name');
   assert.equal(await page.evaluate(()=>window.merge.inputs.find(i=>i.name==='block_weights')?.type),'STRING');
   assert.equal(await page.locator('textarea').count(),0,'Block weights no longer occupies a text editor');
   // A connected text node changes the settings part of the live name.
   const beforeBlock=await preview.textContent();
   await page.evaluate(async()=>{
    const{app}=await import('/scripts/app.js');
    class PickerString extends LiteGraph.LGraphNode{constructor(){super('Text');this.addOutput('text','STRING');this.addWidget('text','value','{"x":0.7}',()=>{});}}
    LiteGraph.registerNodeType('ModelWorkflowTextFixture',PickerString);
    const text=LiteGraph.createNode('ModelWorkflowTextFixture');app.graph.add(text);text.pos=[100,1100];
    text.connect(0,window.merge,window.merge.inputs.findIndex(i=>i.name==='block_weights'));window.block=text;
   });
   await page.waitForFunction(before=>window.merge._rayMergeName.name!==before,beforeBlock);
   const prompt=await page.evaluate(async()=>{const{app}=await import('/scripts/app.js');return app.graphToPrompt();});
   const id=await page.evaluate(()=>String(window.merge.id));
   assert.ok(Array.isArray(prompt.output[id].inputs.block_weights),'Block weights is queued as a STRING connection');
   assert.ok(!('load_result'in prompt.output[id].inputs));
   // Reload an old schema without shifting paths, ratios, precision or fast mode.
   await page.evaluate(async()=>{
    const{app}=await import('/scripts/app.js');window.merge.disconnectInput(window.merge.inputs.findIndex(i=>i.name==='block_weights'));
    const graph=app.graph.serialize();
    const a=graph.nodes.find(n=>String(n.id)===String(window.a.id)),merge=graph.nodes.find(n=>String(n.id)===String(window.merge.id));
    delete a.properties.ray_model_tools_schema;delete merge.properties.ray_model_tools_schema;
    merge.inputs=merge.inputs.filter(i=>i.name!=='block_weights');merge.inputs.push({name:'load_result',type:'BOOLEAN',link:null});
    a.widgets_values=['diffusion_models: MOSS/Alpha.safetensors','fp16','diffusion',false,'',false];
    merge.widgets_values=['Breadcrumbs',.6,'fp32','all','pad',12,'fixed',.3,2,.2,.05,false,'','','','{"x":0.8}',true];
    merge.outputs=merge.outputs.slice(0,6);
    await app.loadGraphData(graph);window.a=app.graph._nodes.find(n=>String(n.id)===String(a.id));window.merge=app.graph._nodes.find(n=>String(n.id)===String(merge.id));
   });
   const migrated=await page.evaluate(()=>Object.fromEntries(window.merge.widgets.filter(w=>w.serialize!==false).map(w=>[w.name,w.value])));
   assert.equal(migrated.weight_a,.6);assert.equal(migrated.weight_format,'fp32');assert.equal(migrated.density,.3);
   assert.equal(migrated.block_weights,'{"x":0.8}');assert.equal(migrated.fast_merge,true);
   assert.equal(await page.getByRole('dialog',{name:'Fast merge',exact:true}).count(),0);
   assert.equal(await page.evaluate(()=>window.merge.outputs[6]?.name),'merge_name');
   assert.equal(await page.evaluate(()=>window.merge.inputs.find(i=>i.name==='block_weights')?.type),'STRING');
   assert.equal(await page.evaluate(()=>window.merge.inputs.some(i=>i.name==='load_result')),false);
   assert.equal(await page.evaluate(()=>window.a.widgets.find(w=>w.name==='loader').value),'diffusion');
   assert.equal(await page.evaluate(()=>window.a.widgets.find(w=>w.name==='load_components').value),false);
   const unlinked=await page.evaluate(async()=>{const{app}=await import('/scripts/app.js');return app.graphToPrompt();});
   const restoredId=await page.evaluate(()=>String(window.merge.id));assert.equal(unlinked.output[restoredId].inputs.block_weights,'{"x":0.8}');
   await page.evaluate(async()=>{
    const{app}=await import('/scripts/app.js');const graph=app.graph.serialize(),old=graph.nodes.find(n=>String(n.id)===String(window.merge.id));
    delete old.properties.ray_model_tools_schema;
    old.widgets_values=['LERP',.4,'bf16','diffusion','forbid',0,'fixed',.5,1,.1,.01,false,'','','','{}'];
    await app.loadGraphData(graph);window.merge=app.graph._nodes.find(n=>String(n.id)===String(old.id));
   });
   assert.equal(await page.evaluate(()=>window.merge.widgets.find(w=>w.name==='weight_a').value),.4);
   assert.equal(await page.evaluate(()=>window.merge.widgets.find(w=>w.name==='fast_merge').value),false);
   assert.deepEqual(errors,[]);
   console.log(`${nodes2?'Nodes 2.0':'Legacy'}: source dropdown, live upstream names, block STRING connection, removed controls, output stability and old workflow migration passed`);
   await page.close();
  }
 }catch(error){if(current)await current.screenshot({path:require('node:path').join(process.env.TEMP,'model-workflow-failure.png')});throw error;}
 finally{await browser.close();}
})().catch(error=>{console.error(error.stack);process.exitCode=1});
