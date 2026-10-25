/* Refresh the example from the registered nodes on an isolated server. */
const fs=require('node:fs'),path=require('node:path');
const{chromium}=require('playwright');
(async()=>{const browser=await chromium.launch({headless:true});try{
 const page=await browser.newPage();await page.goto(process.argv[2]||'http://127.0.0.1:8191');
 await page.waitForFunction(()=>!!globalThis.LiteGraph?.registered_node_types?.RayModelMerge);await page.waitForTimeout(1800);
 const graph=await page.evaluate(async()=>{
  const{app}=await import('/scripts/app.js');app.graph.clear();
  const make=(type,x,y)=>{const n=LiteGraph.createNode(type);app.graph.add(n);n.pos=[x,y];return n;};
  const a=make('RayModelLoadAs',40,80),b=make('RayModelLoadAs',40,680),merge=make('RayModelMerge',620,80),save=make('RayModelSave',1780,80),metadata=make('RayModelMetadata',1200,680);
  a.connect(3,merge,merge.inputs.findIndex(i=>i.name==='data_a'));b.connect(3,merge,merge.inputs.findIndex(i=>i.name==='data_b'));
  merge.connect(3,save,save.inputs.findIndex(i=>i.name==='model_data'));
  if(!save.inputs.some(i=>i.name==='filename_prefix'))save.addInput('filename_prefix','STRING',{widget:{name:'filename_prefix'}});
  merge.connect(6,save,save.inputs.findIndex(i=>i.name==='filename_prefix'));
  metadata.widgets.find(w=>w.name==='editor_json').value='{"author":"Ray","method":"LERP","ratio":"50/50"}';
  metadata._rayMetadataEditor.reload();metadata.connect(0,save,save.inputs.findIndex(i=>i.name==='metadata'));
  await new Promise(r=>setTimeout(r,700));return app.graph.serialize();
 });
 fs.writeFileSync(path.join(__dirname,'../examples/model_tools_merge.json'),JSON.stringify(graph,null,2)+'\n');
 console.log('Example updated: data-only loaders, 50/50 LERP, automatic merge_name wired to Save Model');
}finally{await browser.close();}})().catch(error=>{console.error(error);process.exitCode=1});
