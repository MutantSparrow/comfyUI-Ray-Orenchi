/* Match browser-side name previews to Python execution output. */
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {execFileSync}=require('node:child_process');
const vm=require('node:vm');
(async()=>{
const root=path.resolve(__dirname,'..');
const cases=JSON.parse(fs.readFileSync(path.join(__dirname,'workflow_name_cases.json'),'utf8'));
const context={TextEncoder,console,app:{canvas:{}}};vm.createContext(context);
for(const file of ['save_name.js','model_merge_name.mjs'])vm.runInContext(fs.readFileSync(path.join(root,'web',file),'utf8').replace(/^import .*;\r?\n/gm,'').replace(/^export /gm,''),context);
vm.runInContext('this.mergeName=mergeName',context);const{mergeName}=context;
const script='import json,sys\nfrom datetime import datetime\nfrom model_workflow import merge_name\nprint(json.dumps([merge_name(**item,now=datetime(2026,10,24,20,30,40)) for item in json.load(sys.stdin)],ensure_ascii=False))';
const expected=JSON.parse(execFileSync(process.env.PYTHON||'python',['-c',script],{cwd:root,input:JSON.stringify(cases),encoding:'utf8',windowsHide:true}));
assert.deepEqual(cases.map(item=>mergeName({...item,now:new Date(2026,9,24,20,30,40)})),expected);
for(const item of cases){
 const name=mergeName({...item,now:new Date(2026,9,24,20,30,40)});
 for(const retired of [false,true])assert.equal(mergeName({...item,settings:{...item.settings,fast_merge:retired},now:new Date(2026,9,24,20,30,40)}),name);
}
console.log('Browser preview and execution names match across source paths, strategies, Unicode, quantization, ratios and block weights');
})().catch(error=>{console.error(error);process.exitCode=1});
