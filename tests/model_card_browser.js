import {app,nodeClass} from '/scripts/app.js';
import '/extensions/ray/ray_model_card.js';

let passes=0;
const check=(value,message)=>{if(!value)throw new Error(message);passes++;document.querySelector('#results').textContent+=`PASS ${message}\n`;};
const defaults={seed:100,seed_mode:'fixed',steps:20,cfg:7,sampler_name:'euler',scheduler:'normal',denoise:1,
    image_width:1024,image_height:1024,card_width:3000,preview_width:1000,card_name:'',guidance_mode:'auto',guidance:3.5,max_images:256,memory_limit_mb:4096};
const options={seed_mode:['fixed','increment','decrement','randomize'],sampler_name:['euler','dpmpp_2m'],scheduler:['normal','simple'],guidance_mode:['auto','set','disabled']};
const canonical='+A\nCaption::positive|negative\n';
let copied='';
let nextId=200;
Object.defineProperty(navigator,'clipboard',{configurable:true,value:{async writeText(value){copied=value;}}});
try {
    for(const accessor of [false,true]) {
        const Node=nodeClass('knob',accessor);
        for(const extension of app.extensions)await extension.beforeRegisterNodeDef?.(Node,{name:'RayModelCard',input:{optional:{config:['STRING',{default:canonical}]}}});
        const make=()=>{
            const node=new Node();node.id=nextId++;
            const proto=Object.getPrototypeOf(node.widgets[0]);
            node.widgets=Object.entries(defaults).map(([name,value])=>Object.assign(Object.create(proto),{name,value,
                type:options[name]?'combo':typeof value==='number'?'number':'text',options:options[name]?{values:options[name]}:{min:0,max:32768,step:10,round:['cfg','guidance'].includes(name) ? .1 : name==='denoise' ? .01 : 1},callback(){}}));
            if(accessor)node.isWidgetVisible=()=>true;
            const seed=node.widgets.find(w=>w.name==='seed');
            const control=Object.assign(Object.create(proto),{name:'control_after_generate',value:'fixed',type:'combo',options:{values:options.seed_mode},serialize:false});
            node.widgets.push(control);seed.linkedWidgets=[control];
            const loader={id:12,title:'Load Diffusion Model',widgets:[{name:'unet_name',type:'combo',value:'models/Flux Dev.v1.safetensors'}]};
            const checkpoint={id:13,title:'Checkpoint Loader',widgets:[{name:'ckpt_name',type:'combo',value:'My SDXL.safetensors'}]};
            node.graph._nodes=[loader,checkpoint,node];node.graph.getNodeById=id=>node.graph._nodes.find(n=>String(n.id)===String(id));
            node.onNodeCreated();return node;
        };
        const node=make(),find=name=>node.widgets.find(w=>w.name===name);
        const box=document.createElement('div');box.className='card';box.append(node._rayPanel.root);document.querySelector('#gallery').append(box);
        check(node.color==='#000000'&&node.bgcolor==='#000000','Ray black node identity');
        check(node._rayPanel.rows.filter(r=>r.name).map(r=>r.name).join(',')==='card_name,seed,steps,cfg,sampler_name,scheduler,denoise','Card name above compact generation controls');
        check(find('image_width').hidden&&find('card_name').hidden,'Native widgets stay hidden behind panel editors');
        const nameRow=node._rayPanel.rows.find(r=>r.name==='card_name');
        const nameInput=nameRow.element.querySelector('input');
        nameInput.focus();nameInput.value='My card / v1.2';nameInput.dispatchEvent(new Event('input',{bubbles:true}));nameInput.blur();
        check(find('card_name').value==='My card / v1.2','Card name field edits its native serialized STRING widget');
        check(nameRow.element.classList.contains('rp-full')&&nameRow.element.querySelector('[aria-label="Build card name"]').textContent==='{ }','Save Image style full-width field and builder button');
        nameRow.element.querySelector('[aria-label="Build card name"]').click();
        let builder=document.querySelector('[role="dialog"][aria-label="Build card name"]');
        check(!!builder&&builder.querySelector('.ray-name-preview').textContent==='My card / v1.2','Shared builder previews display text with spaces and no extension');
        let editor=builder.querySelector('#ray-name-input');
        editor.value='';editor.dispatchEvent(new Event('input'));
        [...builder.querySelectorAll('button')].find(b=>b.textContent==='Widget value…').click();
        builder.querySelector('[title="{widget:12.unet_name}"]').click();
        check(find('card_name').value==='{widget:12.unet_name}','Shared widget picker inserts into Card name');
        check(builder.querySelector('.ray-name-preview').textContent==='Flux Dev.v1','Preview strips loader path and extension while preserving spaces');
        check(await find('card_name').serializeValue()==='Flux Dev.v1','Queue resolves model name without filename sanitization');
        check(find('card_name').value==='{widget:12.unet_name}','Queue preserves the stored name template');
        editor.value='Benchmark {widget:12.unet_name} - {date}';editor.dispatchEvent(new Event('input'));
        check(/^Benchmark Flux Dev.v1 - \d{4}-\d{2}-\d{2}$/.test(builder.querySelector('.ray-name-preview').textContent),'Mixed text, model widget and date tokens preview together');
        check(await find('card_name').serializeValue()==='Benchmark Flux Dev.v1 - {date}','Queue resolves widget values and leaves date evaluation to the server');
        editor.value='{widget:13.ckpt_name}';editor.dispatchEvent(new Event('input'));
        check(builder.querySelector('.ray-name-preview').textContent==='My SDXL','Checkpoint widgets also preview');
        check(![...builder.querySelectorAll('button')].some(b=>['Counter','Index','Input'].includes(b.textContent)),'Builder offers tokens that apply to card titles');
        builder.querySelector('.ray-name-done').click();
        check(!document.querySelector('.ray-name'),'Done closes shared builder');
        node.config='connected custom config';node._rayPanel.root.querySelector('[data-action="copy-config"]').click();await Promise.resolve();
        check(copied===canonical,'Copy Config copies canonical default, regardless of connected text');
        check(node._rayPanel.root.querySelector('[data-action="copy-config"]').textContent==='Copied','Immediate copy feedback');
        const mode=node._rayPanel.root.querySelector('[data-mode="fixed"]');mode.click();
        check(find('control_after_generate').value==='increment'&&await find('seed_mode').serializeValue()==='increment','Native seed control supplies per-image mode');
        node._rayPanel.root.querySelector('[aria-label="Model Card settings"]').click();
        let dialog=document.querySelector('dialog[open]');
        check(!!dialog&&dialog.getAttribute('aria-label')==='Model Card settings','Settings opens shared Ray panel dialog');
        let settings=node._raySettingsPanel;
        check(settings.rows.filter(r=>!r.element.hidden).length===8&&!settings.rows.some(r=>r.name==='card_name'||r.name==='model_name_source'),'Settings keeps secondary controls and removes the old name selector');
        const width=settings.rows.find(r=>r.name==='image_width').element.querySelector('input');width.value='768';width.dispatchEvent(new Event('change',{bubbles:true}));
        check(find('image_width').value===768,'Settings edits native serialized width');
        find('card_name').value='Benchmark {widget:12.unet_name}';
        const saved=Object.fromEntries(node.widgets.filter(w=>w.name in defaults||w.name==='control_after_generate').map(w=>[w.name,w.value]));
        node._raySettingsClose();check(!document.querySelector('dialog'),'Settings dialog is removed on close');
        for(let i=0;i<3;i++){node._rayPanel.root.querySelector('[aria-label="Model Card settings"]').click();check(!node._raySettingsPanel.rows[0].element.hidden,'Reopened Settings remains usable');node._raySettingsClose();}
        const restored=make();for(const widget of restored.widgets)if(widget.name in saved)widget.value=saved[widget.name];restored.onConfigure();
        const source=restored.widgets.find(w=>w.name==='card_name');
        check(source.value==='Benchmark {widget:12.unet_name}'&&await source.serializeValue()==='Benchmark Flux Dev.v1','Card name template survives workflow reload');
        check(await restored.widgets.find(w=>w.name==='seed_mode').serializeValue()==='increment','Seed mode survives workflow reload');
        restored.graph._nodes=restored.graph._nodes.filter(n=>n.id!==12);
        check(await source.serializeValue()==='Benchmark {widget:12.unet_name}','Missing model widget is left for server fallback');
        restored.inputs=[{name:'model_name_source',widget:{name:'model_name_source'},type:'STRING',link:5}];
        restored.onConfigure();
        check(restored.inputs[0].name==='card_name'&&restored.inputs[0].widget.name==='card_name','Existing model-name input connections migrate on workflow reload');
        restored._rayPanel.refresh();
        const linkedRow=restored._rayPanel.rows.find(r=>r.name==='card_name');
        check(linkedRow.element.querySelector('input').hidden&&linkedRow.element.querySelector('[aria-label="Build card name"]').disabled,'Connected Card name uses the link instead of editable text');
        nameRow.element.querySelector('[aria-label="Build card name"]').click();
        check(!!document.querySelector('.ray-name'),'Builder reopens');
        restored.onRemoved();node.onRemoved();
        check(!node._raySettingsPanel&&!document.querySelector('.ray-name'),'Node removal cleans up Settings and name builder');
    }
    document.querySelector('#summary').textContent=`${passes} checks passed`;
} catch(error) {document.querySelector('#summary').textContent='Regression failed';document.querySelector('#results').textContent+=error.stack;}
