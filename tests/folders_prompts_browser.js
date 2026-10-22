import {app} from '/scripts/app.js';
import {api} from '/scripts/api.js';
import {createGallery} from '/extensions/ray/folders_gallery.js';

let passes=0,gallery,prompts=[],copyFailure=false;
const copied=[],warnings=[];
const check=(condition,message)=>{if(!condition)throw new Error(message);passes++;document.querySelector('#results').textContent+='PASS '+message+'\n';};
async function until(predicate){const start=performance.now();while(!predicate()){if(performance.now()-start>10000)throw new Error('Timed out waiting for prompt picker');await new Promise(resolve=>setTimeout(resolve,20));}}
const originalFetch=api.fetchApi,clipboardDescriptor=Object.getOwnPropertyDescriptor(navigator,'clipboard');
app.extensionManager={toast:{add:message=>warnings.push(message.detail)}};
api.fetchApi=(url,options)=>url.startsWith('/ray/folders/metadata?')
    ?Promise.resolve(new Response(JSON.stringify({prompts,has_prompt:!!prompts.length,width:180,height:120,workflow:null})))
    :originalFetch(url,options);
Object.defineProperty(navigator,'clipboard',{configurable:true,value:{async writeText(text){if(copyFailure)throw new Error('Clipboard denied');copied.push(text);}}});
const examples=[
    'A red cat sitting in warm light. Soft shadows fall across the wooden floor beside an open window.',
    'An illustrated cat in a sunlit garden, surrounded by tall grasses and small yellow flowers.',
    'A quiet room at sunset. A small cat watches the light move across the wall.\nNatural colors, soft grain, detailed textures.',
    'A watercolor portrait of a cat resting beneath a leafy tree, with loose brushwork and a pale blue sky.',
    'A candid photograph of a cat exploring an old bookshop, warm interior light, shelves fading into the distance.',
    'A playful cat in a field of wildflowers on a bright spring morning, shallow depth of field and gentle motion.',
    'A charcoal drawing of a sleeping cat on folded linen, strong shapes, rich blacks and soft edges.',
];

try {
    const fixture=await fetch('/fixture').then(response=>response.json());
    async function mount(values,settings={}) {
        gallery?.destroy();gallery?.root.remove();prompts=values;
        const node={widgets:Object.entries({folder:fixture.folder,name_filter:'',selected_files:'{}',settings_json:JSON.stringify(settings)}).map(([name,value])=>({name,value})),inputs:[],graph:{beforeChange(){},afterChange(){}},setDirtyCanvas(){}};
        gallery=createGallery(node);document.querySelector('#gallery').append(gallery.root);
        await until(()=>gallery.root.querySelector('[data-file="cat.png"][data-state="ready"]'));
    }
    const tile=()=>gallery.root.querySelector('[data-file="cat.png"]');
    async function copyAction() {
        tile().dispatchEvent(new MouseEvent('contextmenu',{bubbles:true,cancelable:true,clientX:180,clientY:180}));
        await until(()=>document.querySelector('.rf-menu button:nth-child(2)')?.disabled===false);
        document.querySelector('.rf-menu button:nth-child(2)').click();
    }
    const picker=()=>document.querySelector('.rf-prompt-picker');
    const cards=()=>[...document.querySelectorAll('.rf-prompt-card')];
    const preview=Number(new URLSearchParams(location.search).get('preview'));
    if(preview) {
        await mount(examples.slice(0,preview));await copyAction();await until(picker);
        document.querySelector('#summary').textContent=preview+' prompt preview';
    } else {
        await mount(['A single\npositive prompt']);await copyAction();await until(()=>copied.length===1);
        check(!picker()&&copied[0]==='A single\npositive prompt','A single prompt copies directly without opening the picker');
        await mount([]);tile().dispatchEvent(new MouseEvent('contextmenu',{bubbles:true,clientX:180,clientY:180}));
        await until(()=>document.querySelector('.rf-menu'));
        check(document.querySelector('.rf-menu button:nth-child(2)').disabled,'Copy prompt stays disabled when no prompt exists');
        document.dispatchEvent(new PointerEvent('pointerdown',{bubbles:true}));

        await mount(examples.slice(0,3),{best_prompt:true});await copyAction();await until(picker);
        const style=getComputedStyle(picker());
        check(cards().length===3&&style.gridTemplateColumns.split(' ').length===2&&style.gridTemplateRows.split(' ').length===2,'Three prompts use a 2×2 grid despite best-match output being enabled');
        check(copied.length===1,'Opening a multi-prompt picker does not copy anything automatically');
        check(cards().map(card=>card.textContent).join('|')===examples.slice(0,3).join('|'),'Each card shows one complete prompt without labels or truncation');
        check(cards().every(card=>getComputedStyle(card).backgroundColor==='rgb(0, 0, 0)'),'Prompt cards use a plain black background');
        const a=cards()[0].getBoundingClientRect(),b=cards()[1].getBoundingClientRect();
        check(b.left-a.right>=16,'Cards have a clear gap to prevent adjacent-card misclicks');
        const outside=document.elementFromPoint((a.right+b.left)/2,a.top+10);
        check(outside.classList.contains('rf-backdrop'),'Gaps between cards are outside the actionable cards');outside.click();
        check(!picker()&&copied.length===1,'Clicking between cards dismisses the picker without copying');
        await copyAction();await until(picker);cards()[1].click();await until(()=>!picker());
        check(copied.at(-1)===examples[1],'Clicking a card copies only that prompt and closes the picker');
        check(document.activeElement===tile(),'Closing the picker restores focus to the image tile');

        await mount(examples);await copyAction();await until(picker);
        const grid=picker().getBoundingClientRect(),backdrop=document.querySelector('.rf-backdrop').getBoundingClientRect(),sevenStyle=getComputedStyle(picker()),last=cards()[6].getBoundingClientRect(),first=cards()[0].getBoundingClientRect();
        check(cards().length===7&&sevenStyle.gridTemplateColumns.split(' ').length===3&&sevenStyle.gridTemplateRows.split(' ').length===3,'Seven prompts use a 3×3 grid with only seven clickable cards');
        check(Math.abs(last.left-first.left)<1&&last.top>first.bottom,'The seventh prompt occupies the first slot of the last row');
        check(Math.abs(grid.width-grid.height)<1&&Math.abs(grid.left+grid.width/2-backdrop.width/2)<1&&Math.abs(grid.top+grid.height/2-backdrop.height/2)<1,'The square grid is centered in the ComfyUI viewport');
        cards()[6].focus();cards()[6].dispatchEvent(new KeyboardEvent('keydown',{key:'Tab',bubbles:true,cancelable:true}));
        check(document.activeElement===cards()[0],'Tab from the last card stays inside the picker');
        cards()[0].dispatchEvent(new KeyboardEvent('keydown',{key:'Tab',shiftKey:true,bubbles:true,cancelable:true}));
        check(document.activeElement===cards()[6],'Shift-Tab from the first card stays inside the picker');
        const empty=document.elementFromPoint(last.left+2*(last.width+18)+last.width/2,last.top+last.height/2);
        check(empty.classList.contains('rf-backdrop'),'Unused slots in the last grid row are not clickable prompt cards');
        const beforeDismiss=copied.length;empty.click();
        check(!picker()&&copied.length===beforeDismiss,'Clicking outside the grid dismisses without copying');
        await copyAction();await until(picker);document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}));
        check(!picker(),'Escape dismisses the prompt picker');
        await copyAction();await until(picker);copyFailure=true;cards()[0].click();await until(()=>warnings.length>0);
        check(!!picker()&&warnings.at(-1)==='Clipboard denied'&&!cards()[0].disabled,'Clipboard errors keep the picker open and allow retry');
        copyFailure=false;cards()[0].click();await until(()=>!picker());
        check(copied.at(-1)===examples[0],'Retrying a failed copy succeeds');
        await copyAction();await until(picker);gallery.destroy();
        check(!picker()&&!document.querySelector('.rf-backdrop'),'Removing the node closes its prompt picker and releases the overlay');

        await mount(['<img src=x onerror=alert(1)>',('A detailed description of a landscape.\n').repeat(300),'A final prompt']);await copyAction();await until(picker);
        check(!cards()[0].querySelector('img')&&cards()[0].textContent.includes('<img'),'Prompt metadata is rendered as plain text');
        check(cards()[1].scrollHeight>cards()[1].clientHeight&&getComputedStyle(cards()[1]).overflowY==='auto','Long prompts scroll inside their card and remain fully available');
        gallery.destroy();gallery.root.remove();
        document.querySelector('#summary').textContent=passes+' checks passed';
    }
} catch(error) {
    document.querySelector('#summary').textContent='Regression failed';document.querySelector('#results').textContent+=error.stack;document.querySelector('details').open=true;
} finally {
    api.fetchApi=originalFetch;
    if(clipboardDescriptor)Object.defineProperty(navigator,'clipboard',clipboardDescriptor);else delete navigator.clipboard;
}
