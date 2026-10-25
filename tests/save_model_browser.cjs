/* Exercise Save Model on an isolated server, without loading inference weights. */
const assert=require('node:assert/strict');
const{chromium}=require('playwright');
const base=process.argv[2]||'http://127.0.0.1:8191';
(async()=>{const browser=await chromium.launch({headless:true});try{
 for(const nodes2 of [true,false]){
  const page=await browser.newPage({viewport:{width:1500,height:1200}});page.setDefaultTimeout(20000);
  const errors=[],requests=[];page.on('pageerror',e=>errors.push(e.message));let cancel=false;
  await page.route(/\/ray\/browse$/,async route=>{
   requests.push(route.request().postDataJSON());await route.fulfill({json:cancel?{cancelled:true}:{path:'D:/Merged café'}});
  });
  await page.goto(base);await page.waitForFunction(()=>!!globalThis.LiteGraph?.registered_node_types?.RayModelSave);
  await page.evaluate(async enabled=>{const{app}=await import('/scripts/app.js');await app.ui.settings.setSettingValue('Comfy.VueNodes.Enabled',enabled);},nodes2);
  await page.reload();await page.waitForFunction(()=>!!globalThis.LiteGraph?.registered_node_types?.RayModelSave);await page.waitForTimeout(1600);await page.keyboard.press('Escape');
  await page.evaluate(async()=>{
   const{app}=await import('/scripts/app.js');app.graph.clear();window.save=LiteGraph.createNode('RayModelSave');app.graph.add(window.save);window.save.pos=[160,100];
   app.canvas.ds.scale=1;app.canvas.ds.offset=[0,0];app.canvas.setDirty(true,true);
  });
  const browse=page.getByRole('button',{name:'Choose a folder',exact:true});await browse.waitFor();
  assert.equal(await page.getByRole('button',{name:'Choose output file',exact:true}).count(),0);
  assert.equal(await page.getByRole('button',{name:'Choose model file',exact:true}).count(),0);
  assert.equal(await page.locator('textarea:visible').count(),0);
  assert.deepEqual(await page.locator('.rp-title:visible').allTextContents(),['Output','Metadata','Report']);
  assert.deepEqual(await page.evaluate(()=>window.save.inputs.filter(i=>!i.widget).map(i=>i.name)),['model','clip','vae','model_data','metadata']);
  assert.deepEqual(await browse.evaluate(b=>[b.offsetWidth,b.offsetHeight,b.dataset.icon]),[32,28,'folder']);
  await browse.click();await page.waitForFunction(()=>window.save.widgets.find(w=>w.name==='output_folder').value==='D:/Merged café');
  assert.equal(requests.at(-1).kind,'folder');assert.equal(requests.at(-1).initial,'model_tools');
  const before=await page.evaluate(()=>JSON.stringify(window.save.serialize()));cancel=true;await browse.click();await page.waitForTimeout(300);
  assert.equal(await page.evaluate(()=>JSON.stringify(window.save.serialize())),before,'Cancel preserves values');
  // Old positional fields retain their values; an explicit filename becomes folder + prefix.
  await page.evaluate(async()=>{
   const{app}=await import('/scripts/app.js'),graph=app.graph.serialize(),old=graph.nodes[0];
   old.properties.ray_model_tools_schema=2;old.widgets_values=['ignored','replace',true,'{"author":"Ray"}','D:/Old source.safetensors','D:/Old folder/Merged.safetensors'];
   await app.loadGraphData(graph);window.save=app.graph._nodes[0];
  });
  let values=await page.evaluate(()=>Object.fromEntries(window.save.widgets.filter(w=>w.serialize!==false).map(w=>[w.name,w.value])));
  assert.equal(values.output_folder,'D:/Old folder/');assert.equal(values.filename_prefix,'Merged');assert.equal(values.overwrite,true);assert.equal(values.metadata_mode,'replace');
  assert.equal(values.metadata_json,'{"author":"Ray"}');assert.equal(values.path,'D:/Old source.safetensors');assert.equal(values.output_path,'');
  assert.equal(await page.locator('textarea:visible').count(),0);
  // A saved prefix containing a directory moves that directory into Output folder.
  await page.evaluate(async()=>{
   const{app}=await import('/scripts/app.js'),graph=app.graph.serialize(),old=graph.nodes[0];delete old.properties.ray_model_tools_schema;
   old.widgets_values=['model_tools/Legacy_Model','merge',false,'','',''];
   await app.loadGraphData(graph);window.save=app.graph._nodes[0];
  });
  values=await page.evaluate(()=>Object.fromEntries(window.save.widgets.filter(w=>w.serialize!==false).map(w=>[w.name,w.value])));
  assert.equal(values.output_folder,'model_tools/');assert.equal(values.filename_prefix,'Legacy_Model');
  // Folder and model-data links survive reload; a linked folder has no browse action.
  await page.evaluate(async()=>{
   const{app}=await import('/scripts/app.js');
   class SaveInputs extends LiteGraph.LGraphNode{constructor(){super('Save inputs');this.addOutput('folder','STRING');this.addOutput('data','RAY_MODEL_DATA');this.addOutput('metadata','RAY_MODEL_METADATA');}}
   LiteGraph.registerNodeType('SaveModelInputsFixture',SaveInputs);const source=LiteGraph.createNode('SaveModelInputsFixture');app.graph.add(source);source.pos=[20,780];
   window.save.addInput('output_folder','STRING',{widget:{name:'output_folder'}});
   source.connect(0,window.save,window.save.inputs.findIndex(i=>i.name==='output_folder'));source.connect(1,window.save,window.save.inputs.findIndex(i=>i.name==='model_data'));source.connect(2,window.save,window.save.inputs.findIndex(i=>i.name==='metadata'));
   const id=window.save.id;await app.loadGraphData(app.graph.serialize());window.save=app.graph._nodes.find(n=>n.id===id);
  });
  await page.waitForTimeout(500);assert.equal(await browse.isVisible(),false);
  const prompt=await page.evaluate(async()=>{const{app}=await import('/scripts/app.js');const p=await app.graphToPrompt();return p.output[String(window.save.id)].inputs;});
  assert.ok(Array.isArray(prompt.output_folder)&&Array.isArray(prompt.model_data)&&Array.isArray(prompt.metadata));
  assert.equal(prompt.filename_prefix,'Legacy_Model');
  await page.evaluate(async()=>{const{app}=await import('/scripts/app.js');await app.loadGraphData(app.graph.serialize());});
  assert.deepEqual(errors,[]);console.log(`${nodes2?'Nodes 2.0':'Legacy'}: folder picker, cancel, simplified controls, links, queueing and saved-workflow migration passed`);await page.close();
 }
}finally{await browser.close();}})().catch(error=>{console.error(error);process.exitCode=1});
