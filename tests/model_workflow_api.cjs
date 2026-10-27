/* Run against an isolated CPU server with Alpha/Beta safetensors fixtures. */
const assert=require('node:assert/strict');
const base=process.argv[2]||'http://127.0.0.1:8191';
const request=async(route,body)=>{
 const response=await fetch(base+route,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
 const result=await response.json();assert.ok(response.ok,JSON.stringify(result));return result;
};
(async()=>{
const info=await request('/object_info');
const classes=['RayModelLoadAs','RayModelConvert','RayModelMerge','RayLoraBake'];
for(const id of classes)assert.ok(!('load_result'in(info[id].input.required||{}))&&!('load_result'in(info[id].input.optional||{})));
assert.equal(info.RayModelMerge.output_name[6],'merge_name');
const models=await request('/models/diffusion_models'),checkpoints=await request('/models/checkpoints');
const a=models.find(name=>name.endsWith('Alpha.safetensors')),b=checkpoints.find(name=>name.endsWith('Beta.safetensors'));
assert.ok(a&&b,'Create only the disposable Alpha/Beta test fixtures in this isolated server');
const graph={
 '1':{class_type:'RayModelLoadAs',inputs:{model_name:'diffusion_models: '+a,weight_format:'auto',loader:'auto',load_components:true}},
 '2':{class_type:'RayModelLoadAs',inputs:{model_name:'checkpoints: '+b,weight_format:'preserve',loader:'auto',load_components:true}},
 '3':{class_type:'RayModelMerge',inputs:{strategy:'LERP',weight_a:.5,weight_format:'fp32',components:'diffusion',mismatch:'forbid',
  seed:0,density:.5,lambda:1,top_trim:.1,bottom_trim:.01,block_weights:'{"diffusion_model.proj":0.25}',data_a:['1',3],data_b:['2',3]}},
 '4':{class_type:'RayModelSave',inputs:{model_data:['3',3],filename_prefix:['3',6],output_folder:'model_tools',metadata_mode:'merge',metadata:['5',0],overwrite:false}},
 '5':{class_type:'RayModelMetadata',inputs:{path:'',editor_json:'{"author":"Ray"}',editor_source:''}},
};
const submitted=await request('/prompt',{prompt:graph,client_id:'model-workflow-check'});assert.ok(submitted.prompt_id);
let job;
for(let n=0;n<80;n++){
 const history=await request('/history/'+submitted.prompt_id);job=history[submitted.prompt_id];
 if(job?.status?.completed)break;await new Promise(resolve=>setTimeout(resolve,250));
}
assert.equal(job?.status?.status_str,'success',JSON.stringify(job?.status));
const reports=job.outputs['3'].model_tools[0],name=reports.merge_name;
assert.match(name,/^A-Alpha_B-Beta_LERP_50-50_fp32_[a-f0-9]{8}_\d{8}-\d{6}$/);
assert.equal(job.outputs['1'].model_tools[0].loaded,false);assert.equal(job.outputs['2'].model_tools[0].loaded,false);
const saved=job.outputs['4'].model_tools[0].saved_path;assert.equal(saved.split(/[\\/]/).at(-1),name+'.safetensors');
console.log(JSON.stringify({saved_path:saved,merge_name:name,model_a_loaded:false,model_b_loaded:false}));
})().catch(error=>{console.error(error.stack);process.exitCode=1});
