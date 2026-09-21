import {app, nodeClass} from '/scripts/app.js';
import '/extensions/ray/ray_save_image.js';
let passes = 0;
const check = (value, message) => { if (!value) throw new Error(message); passes++; document.querySelector('#results').textContent += `PASS ${message}\n`; };
try {
    for (const accessor of [false, true]) {
        const Node = nodeClass('knob', accessor);
        for (const extension of app.extensions) await extension.beforeRegisterNodeDef?.(Node, {name:'RaySaveImage'});
        const node = new Node();
        const template = node.widgets[0];
        node.widgets = Object.entries({save_image:'1',directory:'',filename_prefix:'Ray',save_without_metadata:false}).map(([name, value]) => {
            const w = Object.create(Object.getPrototypeOf(template));
            Object.assign(w,{name,value,type:typeof value === 'boolean'?'toggle':'combo',options:{},callback(){}}); return w;
        });
        node.onNodeCreated();
        const find = name => node.widgets.find(w => w.name === name);
        const root = node._raySave.root;
        const card = document.createElement('section'); card.className='card';
        card.append(document.createElement('h2'), root); card.firstChild.textContent = accessor ? 'Prototype-backed widgets / Nodes 2.0' : 'Plain widgets / Legacy';
        document.querySelector('#gallery').append(card);
        check(find('save_image').value === '1', 'Default saves input 1');
        const range = root.querySelector('input[type=range]');
        range.value='3';range.dispatchEvent(new Event('input'));
        check(find('save_image').value === 'both', 'Slider writes native serialized value');
        const menu=[];node.getExtraMenuOptions(null,menu); menu[0].callback();
        check(find('save_without_metadata').value === true, 'Context toggle writes native metadata input');
        const msg={ray_images_1:[{filename:'first.png',type:'temp'}],ray_images_2:[{filename:'second.png',type:'temp'}],ray_saved:[]};
        node.onExecuted(msg);
        check(!root.querySelector('.ray-save-divider').hidden, 'Two images enable comparison');
        const stage=root.querySelector('[role=slider]');
        stage.dispatchEvent(new KeyboardEvent('keydown',{key:'End',bubbles:true}));
        check(stage.getAttribute('aria-valuenow') === '100', 'Divider reaches full image 1');
        stage.dispatchEvent(new KeyboardEvent('keydown',{key:'Home',bubbles:true}));
        check(stage.getAttribute('aria-valuenow') === '0', 'Divider reaches full image 2');
        node.onExecuted({...msg,ray_images_2:[]});
        check(root.querySelector('.ray-save-divider').hidden, 'Single input hides comparison');
        const historyKey='ray.saveImage.paths.v1', oldHistory=localStorage.getItem(historyKey);
        try {
            for(const path of ['A','B','C','D','B']) node.onExecuted({...msg,ray_directory:[path],ray_saved:['fixture.png']});
            check(JSON.stringify(JSON.parse(localStorage.getItem(historyKey))) === JSON.stringify(['B','D','C']), 'History retains three unique destinations, most recent first');
            const recent=root.querySelector('select');recent.value='D';recent.dispatchEvent(new Event('change'));
            check(find('directory').value === 'D', 'History selection writes destination widget');
        } finally { if(oldHistory===null)localStorage.removeItem(historyKey);else localStorage.setItem(historyKey,oldHistory); }
        node.onExecuted({...msg,ray_images_1:[...msg.ray_images_1,...msg.ray_images_1],ray_images_2:[...msg.ray_images_2,...msg.ray_images_2,...msg.ray_images_2]});
        root.querySelector('[aria-label="Next image pair"]').click();root.querySelector('[aria-label="Next image pair"]').click();
        check(root.querySelector('.ray-save-overlay').hidden && !root.querySelector('.ray-save-stage > img').hidden, 'Unpaired second image remains visible');
        find('save_image').value='none';node.onConfigure();
        check(range.value === '0', 'Workflow restore synchronizes selector');
        node.inputs=[{name:'save_image',link:1}];node.onConnectionsChange();
        check(range.disabled,'Linked selection disables local slider');
        node.inputs=[];node.onConnectionsChange();
        node.onExecuted({...msg,ray_images_2:[...msg.ray_images_2,...msg.ray_images_2]});
        root.querySelector('[aria-label="Next image pair"]').click();
        check(!root.querySelector('.ray-save-divider').hidden, 'Singleton first image pairs with second batch');
        stage.dispatchEvent(new KeyboardEvent('keydown',{key:'ArrowRight',bubbles:true}));
        // Return gallery to the useful half-way view.
        for(let i=0;i<24;i++) stage.dispatchEvent(new KeyboardEvent('keydown',{key:'ArrowRight',bubbles:true}));
    }
    document.querySelector('#summary').textContent=`${passes} checks passed`;
} catch(e) { document.querySelector('#summary').textContent='Regression failed';document.querySelector('#results').textContent+=e.stack;document.querySelector('details').open=true; }
