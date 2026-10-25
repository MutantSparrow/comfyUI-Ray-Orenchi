import {app,nodeClass} from '/scripts/app.js';
import {api} from '/scripts/api.js';
import '/extensions/ray/ray_folders.js';

let passes=0;
const check=(value,message)=>{if(!value)throw new Error(message);passes++;document.querySelector('#results').textContent+='PASS '+message+'\n';};
const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
async function until(predicate){const start=performance.now();while(!predicate()){if(performance.now()-start>10000)throw new Error('Timed out waiting for gallery');await pause(30);}}
const emit=(type,detail)=>api.dispatchEvent(new CustomEvent(type,{detail}));
try {
    const {folder}=await fetch('/fixture').then(r=>r.json());
    const Node=nodeClass('knob');
    for(const extension of app.extensions)await extension.beforeRegisterNodeDef?.(Node,{name:'RayFolders'});
    const nodes=[];
    function create(linked=false){
        const node=new Node();node.id=100+nodes.length;
        node.widgets=Object.entries({folder,name_filter:'',selected_files:'{}',settings_json:'{}'}).map(([name,value])=>({name,value,type:'text',options:{},callback(){}}));
        node.inputs=linked?[{name:'folder',link:1},{name:'name_filter',link:2}]:[];
        node.onNodeCreated();
        const host=document.createElement('div');host.className='gallery';host.append(node._rayFolders.root);document.querySelector('#galleries').append(host);
        nodes.push(node);return node;
    }
    const linked=create(true),cached=create(),removed=create();
    const root=node=>node._rayFolders.root;
    const count=(node,n)=>root(node).querySelector('.rf-total').textContent.startsWith(n+' image');
    await until(()=>count(cached,82)&&count(removed,82)&&root(linked).querySelector('.rf-status').textContent==='Run the workflow to resolve the folder input.');
    let scans=0;
    const fetchApi=api.fetchApi;
    api.fetchApi=(url,options)=>{if(url==='/ray/folders/scan')scans++;return fetchApi(url,options);};

    emit('execution_start',{prompt_id:'first'});
    linked.onExecuted({ray_folders:[{folder,name_filter:'returned'}]});
    emit('executing','save-image');
    emit('status',{exec_info:{queue_remaining:0}});
    removed.onRemoved();
    await pause(650);
    check(scans===0,'Folders execution, polling and queue status do not rescan before output nodes finish');
    check(root(linked).querySelector('[aria-label="Folder"]').value==='','Linked folder resolution waits for completion instead of triggering an early poll scan');
    await fetch('/fixture/recover',{method:'POST'});
    emit('execution_success',{prompt_id:'first'});
    await pause(450);
    check(scans===0&&!count(cached,83),'An output saved later in the workflow is not scanned before the terminal completion event');
    emit('executing',null);
    await until(()=>count(linked,83)&&count(cached,83));
    check(scans===2,'Workflow completion refreshes every live gallery once and releases removed-node listeners');
    check(root(linked).querySelector('[aria-label="Folder"]').value===folder&&root(linked).querySelector('[aria-label="Filename or prompt filter"]').value==='returned','Completion applies linked folder and filter values');
    await until(()=>root(linked).querySelector('[data-file="returned.png"]'));
    check(root(linked).querySelectorAll('.rf-tile').length===1,'The newly generated image is visible with the resolved search filter');

    const before=scans;
    emit('execution_start',{prompt_id:'cached'});
    emit('execution_cached',{prompt_id:'cached',nodes:[String(cached.id),String(linked.id)]});
    await fetch('/fixture/delete',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
    await pause(450);
    check(scans===before&&count(cached,83),'Cached executions keep the current gallery while downstream work runs');
    emit('executing',null);
    await until(()=>count(cached,82)&&count(linked,82));
    check(scans===before+2,'Cached or disconnected galleries also update at workflow completion');

    const beforeManual=scans;
    root(cached).querySelector('[aria-label="Refresh folder"]').click();
    await until(()=>scans===beforeManual+1&&count(cached,82));
    check(scans===beforeManual+1,'Manual refresh still scans immediately');
    for(const node of [linked,cached])node.onRemoved();
    const afterRemoval=scans;
    emit('execution_start',{prompt_id:'removed'});emit('executing',null);
    await pause(450);
    check(scans===afterRemoval,'Removing all galleries releases workflow refresh listeners');
    document.querySelector('#summary').textContent=passes+' checks passed';
} catch(error){document.querySelector('#summary').textContent='Regression failed';document.querySelector('#results').textContent+='FAIL '+error.stack;console.error(error);}
