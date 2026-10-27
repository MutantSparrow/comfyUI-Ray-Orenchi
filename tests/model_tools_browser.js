import {app,nodeClass} from '/scripts/app.js';
import {browseFixture} from '/scripts/api.js';
import '/extensions/ray/ray_model_tools.js';

let passes=0;
const check=(value,message)=>{if(!value)throw new Error(message);passes++;document.querySelector('#results').textContent+=`PASS ${message}\n`;};
const tick=()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
let id=1000;
async function make(kind,defaults,options={},accessor=false,input={}) {
    const Node=nodeClass('knob',accessor);
    for(const extension of app.extensions)await extension.beforeRegisterNodeDef?.(Node,{name:kind,input});
    const node=new Node();node.id=id++;
    node.addInput=(name,type,options={})=>node.inputs.push({name,type,...options});
    node.removeInput=slot=>node.inputs.splice(slot,1);
    const proto=Object.getPrototypeOf(node.widgets[0]);
    node.widgets=Object.entries(defaults).map(([name,value])=>Object.assign(Object.create(proto),{name,value,
        type:options[name]?'combo':typeof value==='number'?'number':typeof value==='boolean'?'toggle':'text',
        options:options[name]?{values:options[name]}:{min:0,max:name==='max_rows'?100000:1,step:1,round:name==='seed'||name==='max_rows'?1:.01},callback(){}}));
    const seed=node.widgets.find(w=>w.name==='seed');
    if(seed){const control=Object.assign(Object.create(proto),{name:'control_after_generate',value:'fixed',type:'combo',options:{values:['fixed','increment','randomize']},serialize:false});node.widgets.push(control);seed.linkedWidgets=[control];}
    if(accessor)node.isWidgetVisible=()=>true;
    node.graph._nodes=[node];node.graph.getNodeById=()=>node;
    node.onNodeCreated();
    const card=document.createElement('div');card.className='card';card.innerHTML=`<h2>${kind}</h2>`;
    card.append(node._rayPanel.root);document.querySelector('#gallery').append(card);
    await tick();return node;
}
try {
    for(const accessor of [false,true]) {
        const loader=await make('RayModelLoadAs',{model_name:'',weight_format:'auto',loader:'auto',load_components:true,path:''},
            {weight_format:['auto','fp16'],loader:['auto','checkpoint','diffusion']},accessor);
        const loadWidget=name=>loader.widgets.find(w=>w.name===name),loadRow=name=>loader._rayPanel.rows.find(r=>r.name===name);
        const modelPicker=loader._rayPanel.root.querySelector('[role="combobox"][aria-label="Model"]');
        check(modelPicker&&!loadRow('model_name')&&!loadRow('path'),
            'Load Model As uses one shared searchable model picker without duplicate legacy path rows');
        check(!loadRow('loader').element.hidden&&!loadRow('load_components').element.hidden,
            'Native inference loading retains its loader controls');
        loadWidget('path').value='C:\\models\\saved-source.safetensors';loader.onConfigure();loader._rayPanel.refresh();
        check(loadWidget('model_name').value==='C:\\models\\saved-source.safetensors'&&loadWidget('path').value==='',
            'Saved legacy paths restore into the single source picker');
        loader.inputs.push({name:'path',widget:{name:'path'},type:'STRING',link:1});
        loader.graph.links={1:{origin_id:999,origin_slot:0}};loader._rayPanel.refresh();
        check(modelPicker.hidden&&loader._rayPanel.root.querySelector('.rp-link:not([hidden])'),
            'An existing linked path retains its connection and hides the model picker');
        loader.inputs[0].link=null;loader._rayPanel.refresh();
        check(!modelPicker.hidden,'Unlinking restores the shared model picker');
        loader.onRemoved();
        const defaults={path:'C:\\models\\example.safetensors',editor_json:'',editor_source:''};
        const node=await make('RayModelMetadata',defaults,{},accessor), find=name=>node.widgets.find(w=>w.name===name);
        const fileRow=node._rayPanel.rows.find(r=>r.name==='path').element;
        const browse=fileRow.querySelector('button[data-icon="file"]');
        check(browse?.querySelector('svg')&&getComputedStyle(browse).width==='32px'&&getComputedStyle(browse).height==='28px',
            'Model source uses the pack file icon and compact button dimensions');
        browseFixture.cancelled=true;browse.click();await tick();
        check(find('path').value===defaults.path,'Cancelling a model browse preserves the source');
        browseFixture.cancelled=false;browse.click();await tick();
        check(find('path').value===browseFixture.path&&browseFixture.requests.at(-1).kind==='file'&&
            browseFixture.requests.at(-1).filters[0][1].includes('json'),'Metadata browse accepts both models and JSON');
        check(!fileRow.querySelector('[aria-label="Choose a model folder"]'),
            'Metadata sources offer one file picker without an extra folder button');
        find('path').value=defaults.path;node._rayPanel.refresh();
        check(await find('editor_json').serializeValue()==='', 'Unopened editor does not replace source metadata with an empty object');
        node._rayMetadataEditor.root.querySelector('button').click();await tick();
        check(node._rayMetadataEditor.root.querySelectorAll('.rmt-row').length===4,'Load populates four editable rows');
        check(JSON.parse(await find('editor_json').serializeValue()).nested==='{ "tags": ["a", "b"], "v": 1 }','JSON strings retain exact whitespace');
        check(JSON.parse(find('editor_json').value).literal==='001','Numeric-looking strings remain text');
        const rows=node._rayMetadataEditor.root.querySelectorAll('.rmt-row');
        const title=rows[0].querySelector('textarea');title.value='Edited model';title.dispatchEvent(new Event('input',{bubbles:true}));
        check(JSON.parse(find('editor_json').value).title==='Edited model','Table edits update the queued widget');
        const saved=Object.fromEntries(node.widgets.filter(w=>w.name in defaults).map(w=>[w.name,w.value]));
        const restored=await make('RayModelMetadata',defaults,{},accessor);
        for(const widget of restored.widgets)if(widget.name in saved)widget.value=saved[widget.name];
        restored.onConfigure();
        check(JSON.parse(await restored.widgets.find(w=>w.name==='editor_json').serializeValue()).title==='Edited model','Metadata edits survive workflow restoration');
        const duplicate=rows[1].querySelector('input');duplicate.value='title';duplicate.dispatchEvent(new Event('input',{bubbles:true}));
        let failed=false;try{await find('editor_json').serializeValue();}catch{failed=true;}
        check(failed,'Duplicate metadata keys prevent queue serialization');
        duplicate.value='literal';duplicate.dispatchEvent(new Event('input',{bubbles:true}));
        const toggle=[...node._rayMetadataEditor.root.querySelectorAll('button')].find(b=>b.textContent==='Table / JSON');toggle.click();
        const raw=node._rayMetadataEditor.root.querySelector('.rmt-raw');raw.value='{invalid';raw.dispatchEvent(new Event('input',{bubbles:true}));
        failed=false;try{await find('editor_json').serializeValue();}catch{failed=true;}
        check(failed&&find('editor_json').value.startsWith('{ invalid'),'Invalid raw JSON blocks both browser and API queues');
        raw.value=JSON.stringify({title:'Edited model',nested:{x:[1,true,null]}});raw.dispatchEvent(new Event('input',{bubbles:true}));toggle.click();
        check(JSON.parse(await find('editor_json').serializeValue()).nested.x[1]===true,'Typed nested JSON survives table/raw switching');
        node.onRemoved();restored.onRemoved();
        for (const [kind,names] of [
            ['RayModelConvert',['path']],
            ['RayModelMetadataSave',['source_model_path']], ['RayModelInspector',['path']],
            ['RayModelCompare',['path_a','path_b']], ['RayLoraBake',['lora_name']],
            ['RayLoraExtract',['finetuned_path','base_path']],
        ]) {
            const defaults=Object.fromEntries(names.map(name=>[name,'']));
            if(kind==='RayModelMetadataSave')defaults.mode='model_copy';
            const picker=await make(kind,defaults,{},accessor);
            for(const name of names) {
                const source=picker._rayPanel.rows.find(r=>r.name===name).element;
                const buttons=[...source.querySelectorAll('button')].filter(button=>!button.closest('.rp-link'));
                check(buttons.length===1&&buttons[0].dataset.icon==='file'&&buttons[0].getAttribute('aria-label').startsWith('Choose '),
                    `${kind}.${name} has one file browse button`);
                buttons[0].click();await tick();
                const request=browseFixture.requests.at(-1);
                check(request.kind==='file'&&request.filters[0][1].includes('safetensors')&&
                    picker.widgets.find(w=>w.name===name).value===browseFixture.path,
                    `${kind}.${name} selects a safetensors file directly`);
            }
            picker.onRemoved();
        }
        const baker=await make('RayLoraBake',{path:'C:\\models\\older-base.safetensors',lora_name:'loras: old.safetensors',lora_path:''},{},accessor);
        const bakeWidget=name=>baker.widgets.find(w=>w.name===name),bakeRow=name=>baker._rayPanel.rows.find(r=>r.name===name);
        check(!bakeRow('path')&&
            ![...baker._rayPanel.root.querySelectorAll('.rp-title')].some(title=>title.textContent==='Source')&&
            bakeWidget('path').value==='C:\\models\\older-base.safetensors',
            'LoRA Bake uses its model inputs without a duplicate Source section and preserves saved base paths');
        check(!bakeRow('lora_name').element.hidden&&bakeRow('lora_path').element.hidden&&
            !bakeRow('lora_name').element.querySelector('select')&&bakeWidget('lora_name').value==='loras: old.safetensors',
            'LoRA Bake restores a legacy dropdown selection in its single file picker');
        bakeWidget('lora_path').value='C:\\models\\saved-lora.safetensors';baker.onConfigure();baker._rayPanel.refresh();
        check(bakeWidget('lora_name').value==='C:\\models\\saved-lora.safetensors'&&bakeWidget('lora_path').value==='',
            'LoRA Bake restores a legacy file path into the single picker');
        baker.inputs.push({name:'lora_path',widget:{name:'lora_path'},type:'STRING',link:1});
        baker.graph.links={1:{origin_id:999,origin_slot:0}};baker._rayPanel.refresh();
        check(bakeRow('lora_name').element.hidden&&!bakeRow('lora_path').element.hidden,
            'LoRA Bake preserves an existing linked adapter path without showing duplicate controls');
        baker.onRemoved();
        const precision=await make('RayModelMerge',{strategy:'LERP',weight_format:'bf16'},
            {strategy:['LERP','SLERP'],weight_format:['bf16','fp32']},accessor,
            {required:{weight_format:[['bf16','fp32'],{tooltip:'Storage format for merged weights.'}]}});
        const precisionRow=precision._rayPanel.rows.find(r=>r.name==='weight_format').element;
        check(precisionRow.title==='Storage format for merged weights.'&&precisionRow.querySelector('label').title===precisionRow.title,
            'Backend tooltip text reaches the whole custom widget row and its label');
        check(!precision.widgets.some(w=>w.name==='fast_merge')&&!document.querySelector('dialog'),
            'Model Merge has no retired merge toggle or confirmation popup');
        precision.onRemoved();
    }
    const inspector=await make('RayModelInspector',{path:'example.safetensors',max_rows:5000});
    check(inspector._rayModelToolsView.root.closest('.rp-section').querySelector('.rp-title').textContent==='Inspection'&&
        inspector._rayModelToolsView.root.querySelector('.rmt-message').hidden,
        'Inspector keeps its preview tools in Inspection without an empty report placeholder');
    inspector._rayModelToolsView.root.querySelector('button').click();await tick();
    check(inspector._rayModelToolsView.root.querySelectorAll('tbody tr').length===100,'Inspector pages its tensor table');
    const previous=inspector._rayModelToolsView.root.querySelector('[aria-label="Previous tensor page"]');
    const next=inspector._rayModelToolsView.root.querySelector('[aria-label="Next tensor page"]');
    check(previous.disabled&&!next.disabled,'Tensor navigation disables Previous on its first page');
    next.click();next.click();
    check(!previous.disabled&&next.disabled&&inspector._rayModelToolsView.root.querySelectorAll('tbody tr').length===50,
        'Tensor navigation reaches the last page and disables Next');
    const search=inspector._rayModelToolsView.root.querySelector('input');search.value='block.249.';search.dispatchEvent(new Event('input',{bubbles:true}));
    check(inspector._rayModelToolsView.root.querySelectorAll('tbody tr').length===1,'Inspector filter finds a tensor beyond the first page');
    search.value='';search.dispatchEvent(new Event('input',{bubbles:true}));
    const merger=await make('RayModelMerge',{strategy:'LERP',weight_a:.5,density:.5,lambda:1,top_trim:.1,bottom_trim:.01,seed:0,
        path_a:'C:\\models\\older-a.safetensors',path_b:'C:\\models\\older-b.safetensors',base_path:''},
        {strategy:['LERP','DARE-TIES','DELLA','Breadcrumbs']});
    const row=name=>merger._rayPanel.rows.find(r=>r.name===name);
    check(!row('fast_merge')&&!merger._raySettingsPanel,
        'Model Merge has no retired toggle or confirmation popup');
    check(!merger._rayPanel.rows.some(r=>['path_a','path_b','base_path'].includes(r.name))&&
        ![...merger._rayPanel.root.querySelectorAll('.rp-title')].some(title=>title.textContent==='Sources'),
        'Model Merge uses its model inputs without a duplicate Sources section');
    check(merger.widgets.find(w=>w.name==='path_a').value==='C:\\models\\older-a.safetensors'&&
        merger.widgets.find(w=>w.name==='path_b').value==='C:\\models\\older-b.safetensors',
        'Removing source controls preserves paths in older saved workflows');
    check(row('density').element.hidden&&row('lambda').element.hidden&&row('seed').element.hidden,'LERP hides unrelated controls');
    const algorithm=row('density').element.closest('.rp-section');
    check(algorithm.hidden,'LERP hides its empty algorithm section');
    const strategy=merger.widgets.find(w=>w.name==='strategy');strategy.value='DELLA';merger._rayPanel.refresh();
    check(!row('density').element.hidden&&!row('lambda').element.hidden&&!row('seed').element.hidden&&row('top_trim').element.hidden,'DELLA shows density, lambda and seed');
    check(!algorithm.hidden,'DELLA restores its algorithm section');
    strategy.value='Breadcrumbs';merger._rayPanel.refresh();
    check(!row('top_trim').element.hidden&&!row('bottom_trim').element.hidden&&row('density').element.hidden,'Breadcrumbs shows trim controls');
    const saver=await make('RayModelMetadataSave',{mode:'json_sidecar',source_model_path:'',metadata_json:'{}',filename_prefix:'metadata',output_path:'',overwrite:false},
        {mode:['json_sidecar','model_copy']});
    const source=saver._rayPanel.rows.find(r=>r.name==='source_model_path').element.closest('.rp-section');
    check(source.hidden,'JSON sidecars hide the unused source model section');
    saver.widgets.find(w=>w.name==='mode').value='model_copy';saver._rayPanel.refresh();
    check(!source.hidden,'Model copies expose the source model without dropping metadata or output controls');
    check(!source.querySelector('[aria-label="Choose a model folder"]'),'Metadata copies offer a single source file');
    const output=saver._rayPanel.rows.find(r=>r.name==='output_path');
    const chooseOutput=output.element.querySelector('button[data-icon="file"]');
    chooseOutput.click();await tick();
    check(browseFixture.requests.at(-1).kind==='save'&&browseFixture.requests.at(-1).filters[0][1][0]==='safetensors'&&
        saver.widgets.find(w=>w.name==='output_path').value===browseFixture.path,'Model copy uses a Save As picker for safetensors');
    saver.widgets.find(w=>w.name==='mode').value='json_sidecar';saver._rayPanel.refresh();
    browseFixture.path='C:\\models\\metadata.json';chooseOutput.click();await tick();
    check(browseFixture.requests.at(-1).filters[0][1][0]==='json'&&saver.widgets.find(w=>w.name==='output_path').value===browseFixture.path,
        'Save As switches to JSON when the metadata mode changes');
    const input={name:'output_path',widget:{name:'output_path'},link:1};
    saver.inputs.push(input);saver.graph.links={1:{origin_id:999,origin_slot:0}};saver._rayPanel.refresh();
    const requestsBefore=browseFixture.requests.length;chooseOutput.click();await tick();
    check(chooseOutput.closest('.rp-control').hidden||!chooseOutput.getBoundingClientRect().height,
        'Linked output paths hide the editable picker');
    check(browseFixture.requests.length===requestsBefore,'A linked output cannot open a save dialog or change its value');
    saver.inputs=[];saver._rayPanel.refresh();
    // Keep one usable editor visible for manual inspection/screenshots.
    const editor=await make('RayModelMetadata',{path:'C:\\models\\example.safetensors',editor_json:'',editor_source:''});
    editor._rayMetadataEditor.root.querySelector('button').click();await tick();
    window.modelToolsFixture={editor,inspector,merger,saver};
    document.querySelector('#summary').textContent=`${passes} checks passed`;
} catch(error) {document.querySelector('#summary').textContent='Regression failed';document.querySelector('#results').textContent+=error.stack;}
