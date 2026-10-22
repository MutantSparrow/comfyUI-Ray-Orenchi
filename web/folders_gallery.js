import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";
import { ICONS, ensurePanelStyles, linkChip, registerLinkTargets } from "./ray_panel.js";
import { browseInto, notify } from "./browse_common.js";
import { options, searchFilenames, colorSignature, matchesAnalysis, analysisScore, nsfwScore, promptText } from "./folders_filters.js";
import { settingsPopup } from "./folders_settings.js";
import { styles } from "./folders.css.js";
import { cachedAnalysis, storeAnalysis } from "./folders_cache.js";
import { createThumbnailCache } from "./folders_thumbnails.js";

const DRAG_TYPE="application/x-ray-folders";
const COG='<svg viewBox="0 0 24 24"><path d="m10 3-1 3-3 1-3 3 2 2-1 3 3 3 3-1 2 2 3-1 1-3 3-1 1-3-2-2 1-3-3-3-3 1z"/><circle cx="12" cy="12" r="3"/></svg>';
const element=(tag,cls,text)=>{const el=document.createElement(tag);if(cls)el.className=cls;if(text!==undefined)el.textContent=text;return el;};
const widget=(node,name)=>node.widgets?.find(w=>w.name===name);
const linked=(node,name)=>node.inputs?.some(i=>(i.widget?.name===name||i.name===name)&&i.link!=null);
function change(node,name,value) {
    const target=widget(node,name);if(!target||target.value===value)return;
    node.graph?.beforeChange?.();
    try {target.value=value;target.callback?.(value);} finally {node.graph?.afterChange?.();}
    node.setDirtyCanvas?.(true,true);
}
async function request(url,data,signal) {
    const response=await api.fetchApi(url,data===undefined?{signal}:{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(data),signal});
    const result=await response.json();
    if(!response.ok)throw new Error(result.error||"The folder request failed.");
    return result;
}
function mediaURL(root,item,endpoint="media") {
    return api.apiURL(`/ray/folders/${endpoint}?${new URLSearchParams({root,file:item.id,v:item.revision})}`);
}
function closeOnEscape(close,signal) {
    document.addEventListener("keydown",e=>{if(e.key==="Escape"){e.stopPropagation();close();}},{capture:true,signal});
}

export function createGallery(node) {
    styles();ensurePanelStyles();
    const lifecycle=new AbortController();
    let scanRequest,folder="",rootToken="",items=[],visible=[],opts=options(widget(node,"settings_json")?.value);
    let selected=new Set(),resolved=null,lastNative="",lastScan="",dead=false,scanSerial=0,analysisSerial=0,counts={},message="Choose a folder to browse.";
    let tooltip,timer,hovered,hoverInfo,shift=false,viewerClose,menuClose,popupClose,promptClose,deleteClose,debounce,resizeFrame,filterFrame;
    let reading=false,hydrating=false,pendingCount=0,scrolling=false,scrollTimer;
    let searchRequest,searchTimer,searchSerial=0,searchQuery="",searchHideNoPrompt=false,searching=false,searchChecked=0,searchError="",searchStage="names";
    let textMatches=new Set(),searchPending=new Set();
    const meta=new Map(),analysis=new Map(),tiles=new Map();
    const thumbnails=createThumbnailCache(),jobs=new Map(),unavailable=new Map();let allowed=new Set();
    const cacheKey=item=>folder+"\0"+item.id+":"+item.revision;
    const root=element("div","ray-folders"),controls=element("div","rf-controls"),folderRow=element("div","rf-row"),filterRow=element("div","rf-row");
    const path=element("input"),filter=element("input");
    path.type=filter.type="text";path.spellcheck=filter.spellcheck=false;
    path.setAttribute("aria-label","Folder");path.placeholder="Choose a folder…";
    filter.setAttribute("aria-label","Filename or prompt filter");filter.placeholder="Fuzzy filename or prompt filter…";
    const browse=element("button","rf-icon");browse.type="button";browse.innerHTML=ICONS.folder;browse.title="Browse folder";browse.setAttribute("aria-label",browse.title);
    const refresh=element("button","rf-icon");refresh.type="button";refresh.innerHTML=ICONS.refresh;refresh.title="Refresh folder";refresh.setAttribute("aria-label",refresh.title);
    const cog=element("button","rf-icon");cog.type="button";cog.innerHTML=COG;cog.title="Folders settings";cog.setAttribute("aria-label",cog.title);
    const folderChip=linkChip(node,"folder",()=>sync()),filterChip=linkChip(node,"name_filter",()=>sync());
    folderRow.append(element("label","","Folder"),path,folderChip.element,browse,refresh);
    filterRow.append(element("label","","Filter"),filter,filterChip.element,cog);
    const status=element("div","rf-status","Choose a folder to browse."),viewport=element("div","rf-viewport"),grid=element("div","rf-grid");
    const total=element("div","rf-total","0 images");
    status.setAttribute("aria-live","polite");viewport.setAttribute("aria-label","Folder media");viewport.tabIndex=0;
    const loading=element("div","rf-loading"),loadingText=element("span","","Reading folder…");
    loading.append(element("span","rf-spinner"),loadingText);loading.hidden=true;
    const more=element("button","rf-more","Load more");more.type="button";more.hidden=true;
    more.title="Check the next visible files without scanning the whole folder";more.onclick=()=>render();
    controls.append(folderRow,filterRow,status);viewport.append(grid,loading);root.append(controls,viewport,more,total);
    const unregister=registerLinkTargets(node,[{name:"folder",element:folderRow},{name:"name_filter",element:filterRow}],()=>sync());

    function readSelection() {
        try {
            const value=JSON.parse(widget(node,"selected_files")?.value||"{}");
            selected=value.folder===folder?new Set(value.files||[]):new Set();
        } catch {selected=new Set();}
    }
    function storeSelection() {
        const files=selected.size?items.filter(i=>selected.has(i.id)&&matchesText(i)&&matchesAnalysis(i,opts,analysis.get(cacheKey(i)))).map(i=>i.id):[];
        change(node,"selected_files",JSON.stringify({folder,files}));
    }
    function currentFolder() {return linked(node,"folder")?(resolved?.folder||""):String(widget(node,"folder")?.value||"");}
    function currentFilter() {return linked(node,"name_filter")?(resolved?.name_filter||""):String(widget(node,"name_filter")?.value||"");}
    function matchesText(item) {return (!searchQuery&&(!opts.hide_no_prompt||item.kind!=="image"))||textMatches.has(item.id);}
    function cancelSearch() {++searchSerial;clearTimeout(searchTimer);searchRequest?.abort();searching=false;}
    function prepareSearch() {
        cancelSearch();searchQuery=currentFilter().trim();searchError="";searchChecked=0;searchStage="names";
        searchHideNoPrompt=opts.hide_no_prompt;
        textMatches=new Set();searchPending=new Set();
        if(!searchQuery&&!searchHideNoPrompt)return;
        searchPending=new Set(items.map(item=>item.id));
        if(!searchPending.size||!rootToken)return;
        searching=true;
        const serial=searchSerial,query=searchQuery,hideNoPrompt=searchHideNoPrompt,token=rootToken,listing=items;
        searchRequest=new AbortController();const signal=searchRequest.signal;
        searchTimer=setTimeout(()=>searchFiles(serial,query,hideNoPrompt,token,listing,signal),220);
    }
    async function searchFiles(serial,query,hideNoPrompt,token,listing,signal) {
        let lastPaint=0;
        try {
            const names=await searchFilenames(listing,query,signal,checked=>{
                if(!dead&&serial===searchSerial){searchChecked=checked;updateStatus();}
            });
            if(dead||serial!==searchSerial)return;
            const nameMatches=new Set(names.matches),files=[];textMatches=new Set();
            for(const item of listing) {
                if(nameMatches.has(item.id)&&(!hideNoPrompt||item.kind!=="image"))textMatches.add(item.id);
                else files.push(item.id);
            }
            searchPending=new Set(files);
            searchChecked=textMatches.size;searchStage="prompts";
            applyFilters();
            for(let offset=0;offset<files.length;offset+=128) {
                const batch=files.slice(offset,offset+128);
                const result=await request("/ray/folders/search",{root:token,files:batch,query,hide_no_prompt:hideNoPrompt},signal);
                if(dead||serial!==searchSerial)return;
                for(const id of result.matches)textMatches.add(id);
                for(const id of batch)searchPending.delete(id);
                searchChecked+=batch.length;
                if(performance.now()-lastPaint>120||offset+batch.length===files.length) {
                    const firstResults=!visible.length;
                    applyFilters(!!opts.colors.length||opts.nsfw!=="all");if(firstResults&&visible.length)render();
                    lastPaint=performance.now();
                }
            }
        } catch(error) {
            if(dead||serial!==searchSerial||error.name==="AbortError")return;
            searchError="Prompt filtering incomplete · refresh to retry";status.title=error.message;
        } finally {
            if(!dead&&serial===searchSerial){searching=false;applyFilters(true);updateStatus();}
        }
    }
    function pending(item) {
        if(item.kind==="audio"||unavailable.has(cacheKey(item)))return false;
        const info=analysis.get(cacheKey(item));
        return !!((opts.colors.length&&!info?.color)||(opts.nsfw!=="all"&&!Number.isFinite(analysisScore(info,opts))));
    }
    function removeTile(tile) {const image=tile.querySelector("img");image.onerror=null;image.removeAttribute("src");tile.remove();}
    function resetTiles() {
        ++analysisSerial;
        allowed.clear();
        for(const job of jobs.values())job.abort.abort();
        for(const tile of tiles.values())removeTile(tile);tiles.clear();
    }
    function showLoading() {
        reading=true;loading.hidden=false;more.hidden=true;loadingText.textContent="Reading folder…";status.textContent="Reading folder…";
        status.classList.add("rf-busy");viewport.setAttribute("aria-busy","true");
    }
    function updateStatus() {
        if(reading)return;
        status.textContent=message||`${visible.length-pendingCount} / ${items.length} files · ${selected.size} selected`;
        if(!message&&(opts.colors.length||opts.nsfw!=="all"))status.textContent+=` · ${analysis.size} analyzed${pendingCount?` · ${pendingCount} pending · scroll to check more`:""}`;
        if(!message&&unavailable.size)status.textContent+=` · ${unavailable.size} unavailable`;
        if(!message&&searching)status.textContent+=` · ${searchStage} ${searchChecked.toLocaleString()} / ${items.length.toLocaleString()} checked`;
        if(!message&&searchError)status.textContent+=` · ${searchError}`;
        const busy=reading||hydrating||jobs.size>0;
        status.classList.toggle("rf-busy",busy||searching);viewport.setAttribute("aria-busy",String(busy||searching));
        loading.hidden=!hydrating;
        loadingText.textContent="Checking saved selections…";
        more.hidden=busy||![...tiles.values()].some(tile=>tile.dataset.waiting==="true");
    }
    function sync(force=false) {
        if(dead)return;
        opts=options(widget(node,"settings_json")?.value);
        const controlledFolder=linked(node,"folder"),controlledFilter=linked(node,"name_filter");
        path.disabled=browse.disabled=!!controlledFolder;filter.disabled=!!controlledFilter;
        folderChip.update();filterChip.update();
        // Keep the resolved value visible when a graph input supplies the path/search.
        if(document.activeElement!==path)path.value=currentFolder();
        if(document.activeElement!==filter)filter.value=currentFilter();
        const native=JSON.stringify([currentFolder(),currentFilter(),opts]);
        const scanKey=JSON.stringify([currentFolder(),opts.types,opts.sort,opts.descending,opts.recursive]);
        const nativeChanged=native!==lastNative;lastNative=native;
        if(force||scanKey!==lastScan){lastScan=scanKey;scanRequest?.abort();++scanSerial;cancelSearch();resetTiles();showLoading();clearTimeout(debounce);debounce=setTimeout(load,force?0:180);}
        else if(nativeChanged){if(currentFilter().trim()!==searchQuery||opts.hide_no_prompt!==searchHideNoPrompt)prepareSearch();resetTiles();applyFilters();}
    }
    async function load() {
        const value=currentFolder().trim();
        scanRequest?.abort();const serial=++scanSerial;resetTiles();
        hideTooltip();reading=false;hydrating=false;loading.hidden=true;unavailable.clear();
        if(!value){folder="";rootToken="";items=[];counts={};selected.clear();thumbnails.clear();analysis.clear();message=linked(node,"folder")?"Run the workflow to resolve the folder input.":"Choose a folder to browse.";applyFilters();return;}
        scanRequest=new AbortController();showLoading();
        try {
            const data=await request("/ray/folders/scan",{folder:value,settings:opts},scanRequest.signal);
            if(dead||serial!==scanSerial)return;
            if(folder!==data.folder){thumbnails.clear();analysis.clear();meta.clear();viewport.scrollTop=0;}
            folder=data.folder;rootToken=data.root;items=data.items;counts=data.counts||{};readSelection();reading=false;message="";
            if(data.warnings?.length)status.title=data.warnings.join("\n");
            const existing=new Set(items.map(i=>i.id));selected=new Set([...selected].filter(id=>existing.has(id)));
            hydrating=!!selected.size&&(!!opts.colors.length||opts.nsfw!=="all");
            prepareSearch();storeSelection();applyFilters();
            if(hydrating) {
                await Promise.all([...selected].map(async id=>{
                    const item=items.find(i=>i.id===id);if(!item)return;
                    const key=cacheKey(item),info=analysis.get(key)||await cachedAnalysis("nsfwjs-4.4.0-mid-regions-v1:"+key);
                    if(!dead&&serial===scanSerial&&info)analysis.set(key,info);
                }));
                if(dead||serial!==scanSerial)return;
                hydrating=false;applyFilters();
            }
        } catch(error) {if(error.name!=="AbortError"&&!dead&&serial===scanSerial){reading=hydrating=false;loading.hidden=true;items=[];counts={};selected.clear();message="Folder unavailable · check the path or drive, then refresh.";storeSelection();applyFilters();status.title=error.message;}}
    }
    function applyFilters(fromAnalysis=false) {
        visible=[];pendingCount=0;const available=new Set();
        for(const item of items) {
            if(!matchesText(item))continue;
            const waiting=pending(item);
            if(waiting||matchesAnalysis(item,opts,analysis.get(cacheKey(item)))) {
                visible.push(item);if(waiting)pendingCount++;else available.add(item.id);
            }
        }
        // A file hidden by an active filter must not silently remain in the output selection.
        for(const id of selected)if(!available.has(id)){
            const item=items.find(i=>i.id===id);
            if(!item||(!searchPending.has(id)&&(!pending(item)||!matchesText(item))))selected.delete(id);
        }
        // Pending/unclassified media is not eligible for workflow output while a visual filter is active.
        storeSelection();
        render(!fromAnalysis);updateStatus();
        const count=(type,label)=>`${Number(counts[type]||0).toLocaleString()} ${label}${counts[type]===1?"":"s"}`;
        total.textContent=`${count("image","image")} · ${count("video","video")} · ${count("audio","audio file")}`;
    }
    function scheduleFilter() {
        if(filterFrame||dead)return;
        filterFrame=setTimeout(()=>{filterFrame=null;if(!dead)applyFilters(true);},120);
    }
    function pump() {
        if(dead||reading||hydrating||scrolling)return;
        const limit=opts.colors.length||opts.nsfw!=="all"?2:4;
        const queued=[...tiles.values()].filter(tile=>tile.dataset.state==="queued"&&tile.dataset.waiting!=="true");
        queued.sort((a,b)=>Math.abs(Number(a.dataset.top)-viewport.scrollTop)-Math.abs(Number(b.dataset.top)-viewport.scrollTop));
        for(const tile of queued) {
            if(jobs.size>=limit)break;
            const item=visible[Number(tile.dataset.index)],key=item&&cacheKey(item);
            if(!item||jobs.has(key))continue;
            const job={abort:new AbortController(),serial:analysisSerial};jobs.set(key,job);
            tile.dataset.state="loading";tile.setAttribute("aria-busy","true");
            loadTile(tile,item,key,job).finally(()=>{if(jobs.get(key)===job)jobs.delete(key);if(!dead){pump();updateStatus();}});
        }
        updateStatus();
    }
    async function loadTile(tile,item,key,job) {
        const settings=opts,signal=job.abort.signal;
        const active=()=>!dead&&!signal.aborted&&job.serial===analysisSerial&&tiles.get(item.id)===tile;
        try {
            if(item.kind!=="audio"&&(settings.colors.length||settings.nsfw!=="all")) {
                const previous=analysis.get(key),info=previous||await cachedAnalysis("nsfwjs-4.4.0-mid-regions-v1:"+key);
                if(!active())return;
                if(info){analysis.set(key,info);if(!previous)scheduleFilter();}
                if(!pending(item)&&!matchesAnalysis(item,settings,info)){tile.dataset.state="filtered";scheduleFilter();return;}
            }
            const preview=await thumbnails.load(key,mediaURL(rootToken,item,"thumbnail"),signal);
            if(!active())return;
            if(pending(item)) {
                tile.querySelector(".rf-placeholder-label").textContent="Checking…";
                let result=analysis.get(key)||{};
                if(!result.color)result={...result,color:colorSignature(preview.image)};
                if(settings.nsfw!=="all") {
                    const classifier=await import("./folders_nsfw.js");
                    if(!active())return;
                    if(!Number.isFinite(nsfwScore(result.predictions)))result.predictions=await classifier.classify(preview.image);
                    if(!active())return;
                    if(settings.nsfw_regions&&!Number.isFinite(analysisScore(result,settings)))result.region_scores=await classifier.classifyRegions(preview.image);
                }
                if(!active())return;
                analysis.set(key,result);storeAnalysis("nsfwjs-4.4.0-mid-regions-v1:"+key,result);scheduleFilter();
            }
            if(!matchesAnalysis(item,settings,analysis.get(key))){tile.dataset.state="filtered";scheduleFilter();return;}
            const image=tile.querySelector("img");preview.image.alt="";preview.image.draggable=false;
            preview.image.onerror=image.onerror;image.onerror=null;image.replaceWith(preview.image);
            tile.dataset.state="ready";tile.disabled=false;tile.draggable=item.kind==="image";
            tile.setAttribute("aria-busy","false");
        } catch(error) {
            if(!active()||error.name==="AbortError")return;
            unavailable.set(key,error.message);tile.dataset.state="error";tile.setAttribute("aria-busy","false");
            tile.title=error.message;tile.querySelector(".rf-placeholder-label").textContent="Unavailable · refresh to retry";
            tile.querySelector(".rf-kind").textContent="UNAVAILABLE";
            if(selected.delete(item.id))storeSelection();scheduleFilter();
        }
    }
    function render(grant=true) {
        const width=viewport.clientWidth;if(!width||reading)return;
        const columns=opts.columns,gap=6,tileWidth=(width-gap*(columns-1))/columns,rowHeight=tileWidth+30;
        const count=Math.ceil(visible.length/columns);grid.style.height=count*rowHeight+"px";
        const first=Math.max(0,Math.floor(viewport.scrollTop/rowHeight)-2)*columns;
        const last=Math.min(visible.length,(Math.ceil((viewport.scrollTop+viewport.clientHeight)/rowHeight)+2)*columns);
        if(!grant)lastScroll=viewport.scrollTop;
        const wanted=new Set(visible.slice(first,last).map(i=>i.id));
        for(const [id,tile] of tiles)if(!wanted.has(id)){removeTile(tile);tiles.delete(id);}
        const keys=new Set(visible.slice(first,last).map(cacheKey));
        if(grant)allowed=keys;
        for(const [key,job] of jobs)if(!keys.has(key))job.abort.abort();
        thumbnails.setWindow(keys);
        for(let i=first;i<last;i++) {
            const item=visible[i];let tile=tiles.get(item.id);
            if(!tile){tile=makeTile(item);tiles.set(item.id,tile);grid.append(tile);}
            tile.dataset.index=i;tile.dataset.top=Math.floor(i/columns)*rowHeight;
            const waiting=tile.dataset.state==="queued"&&!allowed.has(cacheKey(item));
            tile.dataset.waiting=String(waiting);
            if(tile.dataset.state==="queued")tile.querySelector(".rf-placeholder-label").textContent=waiting?"Scroll or load more":pending(item)?"Checking…":"Loading…";
            Object.assign(tile.style,{width:tileWidth+"px",height:(rowHeight-gap)+"px",left:(i%columns)*(tileWidth+gap)+"px",top:Math.floor(i/columns)*rowHeight+"px"});
            tile.setAttribute("aria-pressed",String(selected.has(item.id)));
            tile.querySelector(".rf-selected").hidden=!selected.has(item.id);
        }
        pump();
    }
    function makeTile(item) {
        const tile=element("button","rf-tile");tile.type="button";tile.dataset.kind=item.kind;tile.dataset.file=item.id;tile.setAttribute("aria-label",item.name);tile.draggable=false;tile.disabled=true;tile.dataset.state="queued";
        tile.setAttribute("aria-busy","true");
        const img=element("img");img.alt="";img.draggable=false;img.decoding="async";
        img.onerror=()=>{
            tile.dataset.state="error";tile.disabled=true;tile.draggable=false;tile.setAttribute("aria-busy","false");tile.title="File unavailable or preview unsupported: "+item.name;
            tile.querySelector(".rf-placeholder-label").textContent="Unavailable · refresh to retry";
            tile.querySelector(".rf-kind").textContent="UNAVAILABLE";
            if(selected.delete(item.id)){storeSelection();render();updateStatus();}
        };
        const kind=element("span","rf-kind",item.kind==="video"?"▶ VIDEO":item.kind==="audio"?"♫ AUDIO":"IMAGE");
        const placeholder=element("span","rf-placeholder");placeholder.append(element("span","rf-spinner"),element("span","rf-placeholder-label",pending(item)?"Checking…":"Loading…"));
        tile.append(img,placeholder,element("span","rf-name",item.name),kind,element("span","rf-selected","✓"));
        if(unavailable.has(cacheKey(item))){tile.dataset.state="error";placeholder.querySelector(".rf-placeholder-label").textContent="Unavailable · refresh to retry";kind.textContent="UNAVAILABLE";tile.setAttribute("aria-busy","false");}
        tile.onclick=e=>{
            if(tile.dataset.state!=="ready")return;
            if(!e.ctrlKey&&!e.metaKey){const only=selected.size===1&&selected.has(item.id);selected.clear();if(!only)selected.add(item.id);}
            else if(selected.has(item.id))selected.delete(item.id);else selected.add(item.id);
            storeSelection();render();updateStatus();
        };
        tile.ondblclick=e=>{e.preventDefault();if(tile.dataset.state==="ready")showViewer(item);};
        tile.oncontextmenu=e=>{e.preventDefault();e.stopPropagation();if(tile.dataset.state==="ready")showMenu(item,e);};
        tile.onpointerenter=e=>{if(tile.dataset.state!=="ready")return;hovered=item;hoverInfo=null;clearTimeout(timer);const at={clientX:e.clientX,clientY:e.clientY};timer=setTimeout(()=>showTooltip(item,at),400);};
        tile.onpointerleave=()=>hideTooltip();
        tile.ondragstart=e=>{if(tile.dataset.state!=="ready"){e.preventDefault();return;}hideTooltip();e.dataTransfer.setData(DRAG_TYPE,JSON.stringify({root:rootToken,item}));e.dataTransfer.effectAllowed="copy";};
        return tile;
    }
    async function details(item) {
        const key=cacheKey(item);
        if(meta.size>256)meta.delete(meta.keys().next().value);
        if(!meta.has(key))meta.set(key,request(`/ray/folders/metadata?${new URLSearchParams({root:rootToken,file:item.id})}`,undefined,lifecycle.signal).catch(error=>{meta.delete(key);throw error;}));
        return meta.get(key);
    }
    function hideTooltip() {clearTimeout(timer);hovered=null;hoverInfo=null;tooltip?.remove();tooltip=null;}
    async function showTooltip(item,event) {
        if(dead||hovered!==item)return;
        tooltip=element("div","rf-tooltip",item.name+"\nReading metadata…");document.body.append(tooltip);
        Object.assign(tooltip.style,{left:Math.min(event.clientX+12,window.innerWidth-460)+"px",top:Math.min(event.clientY+12,window.innerHeight-220)+"px"});
        try {const info=await details(item);if(hovered!==item||!tooltip)return;hoverInfo=info;updateTooltip();}
        catch(error){if(tooltip)tooltip.textContent=item.name+"\n"+error.message;}
    }
    function updateTooltip() {
        if(!tooltip||!hoverInfo||!hovered)return;
        const info=hoverInfo;
        const score=analysisScore(analysis.get(cacheKey(hovered)),opts);
        const scoreText=opts.nsfw!=="all"&&Number.isFinite(score)?`\nNSFW score: ${(score*100).toFixed(1)}% · threshold: ${Math.round(opts.threshold*100)}%`:"";
        tooltip.textContent=shift?(promptText(info,opts)||"No prompt found."):
            `${hovered.name}\n${new Date(hovered.modified*1000).toLocaleString()}\n${info.width?`${info.width} × ${info.height}`:info.duration?`${info.duration.toFixed(1)} seconds`:"Audio"}\nPrompt: ${info.has_prompt?"Yes":"No"}${scoreText}\nHold Shift to see the prompt`;
        const bounds=tooltip.getBoundingClientRect();
        tooltip.style.left=Math.max(8,Math.min(bounds.left,window.innerWidth-bounds.width-8))+"px";
        tooltip.style.top=Math.max(8,Math.min(bounds.top,window.innerHeight-bounds.height-8))+"px";
    }
    function showViewer(item) {
        hideTooltip();viewerClose?.();
        const abort=new AbortController(),backdrop=element("div","rf-backdrop"),box=element("div","rf-viewer");
        const media=element(item.kind==="image"?"img":item.kind);media.src=mediaURL(rootToken,item);media.alt=item.name;
        media.onerror=()=>box.replaceChildren(element("p","","File unavailable. It may have been moved, removed, or its drive disconnected."));
        if(item.kind!=="image"){media.controls=true;media.autoplay=true;media.onclick=e=>e.stopPropagation();}
        box.append(media);backdrop.append(box);document.body.append(backdrop);
        const close=()=>{abort.abort();media.onerror=null;if(media.pause)media.pause();media.removeAttribute("src");media.load?.();backdrop.remove();viewerClose=null;};
        viewerClose=close;backdrop.onclick=close;closeOnEscape(close,abort.signal);
    }
    async function copyPrompt(item) {
        const info=await details(item);if(dead)return;
        const prompts=[...new Set((info.prompts||[]).filter(text=>typeof text==="string"&&text.trim()))]
            .map(text=>promptText({prompts:[text]},opts));
        if(prompts.length===1){await navigator.clipboard.writeText(prompts[0]);return;}
        if(!prompts.length)return;
        promptClose?.();hideTooltip();
        const abort=new AbortController(),backdrop=element("div","rf-backdrop"),picker=element("div","rf-prompt-picker");
        const previous=tiles.get(item.id)||document.activeElement;
        const close=()=>{
            abort.abort();backdrop.remove();if(promptClose===close)promptClose=null;
            if(!dead&&previous?.isConnected)previous.focus?.({preventScroll:true});
        };
        promptClose=close;
        picker.setAttribute("role","dialog");picker.setAttribute("aria-modal","true");picker.setAttribute("aria-label","Choose a prompt to copy");
        picker.style.setProperty("--rf-prompt-columns",Math.ceil(Math.sqrt(prompts.length)));
        const cards=prompts.map(text=>{
            const card=element("button","rf-prompt-card");card.type="button";card.append(element("span","",text));
            card.onclick=async event=>{
                event.stopPropagation();card.disabled=true;
                try {await navigator.clipboard.writeText(text);close();}
                catch(error){if(backdrop.isConnected)notify(error.message);}
                finally{card.disabled=false;}
            };
            picker.append(card);return card;
        });
        backdrop.onclick=close;
        backdrop.onkeydown=event=>{
            event.stopPropagation();
            if(event.key!=="Tab")return;
            const first=cards[0],last=cards[cards.length-1];
            if(event.shiftKey&&document.activeElement===first){event.preventDefault();last.focus();}
            else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus();}
        };
        backdrop.onkeyup=event=>event.stopPropagation();
        backdrop.append(picker);document.body.append(backdrop);closeOnEscape(close,abort.signal);
        cards[0].focus({preventScroll:true});
    }
    function confirmDelete(item) {
        deleteClose?.();hideTooltip();
        const token=rootToken,sourceFolder=folder,key=cacheKey(item),abort=new AbortController();
        const backdrop=element("div","rf-backdrop"),panel=element("section","rf-delete-dialog"),error=element("p","rf-delete-error");
        panel.setAttribute("role","dialog");panel.setAttribute("aria-modal","true");panel.setAttribute("aria-label","Delete asset?");
        panel.append(element("h3","","Delete asset?"),element("p","rf-delete-name",item.id),element("p","","Move this asset to the Recycle Bin / Trash. You can restore it there."),error);
        error.setAttribute("role","alert");error.hidden=true;
        const actions=element("div","rf-actions"),cancel=element("button","","Cancel"),remove=element("button","rf-danger","Delete asset");
        cancel.type=remove.type="button";
        let busy=false;
        const previous=tiles.get(item.id)||document.activeElement;
        const close=(force=false)=>{
            if(busy&&!force)return;
            abort.abort();backdrop.remove();if(deleteClose===destroy)deleteClose=null;
            if(!dead&&previous?.isConnected)previous.focus?.({preventScroll:true});
        };
        const destroy=()=>close(true);deleteClose=destroy;
        cancel.onclick=()=>close();backdrop.onclick=event=>{if(event.target===backdrop)close();};
        closeOnEscape(()=>close(),abort.signal);
        backdrop.onkeydown=event=>{
            event.stopPropagation();
            if(event.key==="Tab"){
                const buttons=[cancel,remove].filter(button=>!button.disabled);
                if(!buttons.length){event.preventDefault();return;}
                if(event.shiftKey&&document.activeElement===buttons[0]){event.preventDefault();buttons.at(-1).focus();}
                else if(!event.shiftKey&&document.activeElement===buttons.at(-1)){event.preventDefault();buttons[0].focus();}
            }
        };
        backdrop.onkeyup=event=>event.stopPropagation();
        remove.onclick=async()=>{
            if(busy||dead)return;
            busy=true;cancel.disabled=remove.disabled=true;remove.textContent="Deleting…";error.hidden=true;
            try {
                if(folder!==sourceFolder||rootToken!==token)throw new Error("The folder changed. Close this dialog and refresh before deleting.");
                await request("/ray/folders/delete",{root:token,file:item.id,revision:item.revision},lifecycle.signal);
                close(true);if(dead||folder!==sourceFolder)return;
                if(rootToken!==token){sync(true);return;}
                selected.delete(item.id);items=items.filter(value=>value.id!==item.id);
                counts[item.kind]=Math.max(0,(counts[item.kind]||0)-1);textMatches.delete(item.id);searchPending.delete(item.id);
                resetTiles();thumbnails.remove(key);meta.delete(key);analysis.delete(key);unavailable.delete(key);
                viewerClose?.();promptClose?.();applyFilters();viewport.focus({preventScroll:true});
            } catch(failure) {
                if(!dead&&backdrop.isConnected){error.textContent="Could not delete asset. "+failure.message;error.hidden=false;}
            } finally {busy=false;cancel.disabled=remove.disabled=false;remove.textContent="Delete asset";}
        };
        actions.append(cancel,remove);panel.append(actions);backdrop.append(panel);document.body.append(backdrop);cancel.focus();
    }
    async function showMenu(item,event) {
        hideTooltip();menuClose?.();
        const abort=new AbortController(),menu=element("div","rf-menu");
        const close=()=>{abort.abort();menu.remove();menuClose=null;};menuClose=close;
        const actions=[
            ["Copy image",async()=>{
                const data=await fetch(mediaURL(rootToken,item)).then(r=>r.blob());
                const bitmap=await createImageBitmap(data),canvas=document.createElement("canvas");canvas.width=bitmap.width;canvas.height=bitmap.height;
                canvas.getContext("2d").drawImage(bitmap,0,0);bitmap.close();
                const png=await new Promise(resolve=>canvas.toBlob(resolve,"image/png"));
                await navigator.clipboard.write([new ClipboardItem({"image/png":png})]);
            },item.kind!=="image"],
            ["Copy prompt",()=>copyPrompt(item),true],
            ["Copy ComfyUI workflow",async()=>navigator.clipboard.writeText(JSON.stringify((await details(item)).workflow,null,2)),true],
        ];
        actions.push(["Delete asset",()=>confirmDelete(item),false,"rf-danger"]);
        const buttons=actions.map(([label,action,disabled,cls])=>{
            const button=element("button",cls,label);button.disabled=disabled;
            button.onclick=async()=>{close();try{await action();}catch(error){notify(error.message);}};menu.append(button);return button;
        });
        document.body.append(menu);
        Object.assign(menu.style,{left:Math.max(8,Math.min(event.clientX,window.innerWidth-menu.offsetWidth-8))+"px",top:Math.max(8,Math.min(event.clientY,window.innerHeight-menu.offsetHeight-8))+"px"});
        document.addEventListener("pointerdown",e=>{if(!menu.contains(e.target))close();},{capture:true,signal:abort.signal});closeOnEscape(close,abort.signal);
        try {const info=await details(item);if(menu.isConnected){buttons[1].disabled=!info.has_prompt;buttons[2].disabled=!info.workflow;}}catch{}
    }
    browse.onclick=async()=>{if(await browseInto(node,"folder",{title:"Choose a media folder"})){resolved=null;sync(true);}};
    refresh.onclick=()=>sync(true);
    cog.onclick=()=>{popupClose?.();popupClose=settingsPopup(opts,value=>{change(node,"settings_json",JSON.stringify(value));sync(true);},cog);};
    path.onchange=()=>{change(node,"folder",path.value);resolved=null;sync(true);};
    filter.oninput=()=>{change(node,"name_filter",filter.value);sync();};
    root.addEventListener("keydown",e=>{e.stopPropagation();if(e.key==="Escape")hideTooltip();});
    root.addEventListener("keyup",e=>e.stopPropagation());
    let space=false;
    window.addEventListener("keydown",e=>{if(e.code==="Space")space=true;if(e.key==="Shift"){shift=true;updateTooltip();}},{capture:true,signal:lifecycle.signal});
    window.addEventListener("keyup",e=>{if(e.code==="Space")space=false;if(e.key==="Shift"){shift=false;updateTooltip();}},{capture:true,signal:lifecycle.signal});
    window.addEventListener("blur",()=>{space=shift=false;hideTooltip();},{signal:lifecycle.signal});
    root.addEventListener("pointerdown",e=>{if(e.button===0&&!space)e.stopPropagation();});
    // Nodes 2.0 forwards wheel events during ancestor capture, before a widget's
    // own handler runs. Claim only this viewport's plain scrolling at the window.
    window.addEventListener("wheel",e=>{
        if(e.ctrlKey||e.metaKey||space||!e.composedPath().includes(viewport))return;
        e.preventDefault();e.stopPropagation();
        const unit=e.deltaMode===1?16:e.deltaMode===2?viewport.clientHeight:1;
        viewport.scrollTop+=e.deltaY*unit;
    },{capture:true,passive:false,signal:lifecycle.signal});
    let lastScroll=0;
    viewport.addEventListener("scroll",()=>{
        if(viewport.scrollTop===lastScroll)return;
        hideTooltip();lastScroll=viewport.scrollTop;scrolling=true;
        clearTimeout(scrollTimer);scrollTimer=setTimeout(()=>{scrolling=false;pump();},80);
        render();
    });
    let viewportWidth=-1,viewportHeight=-1;
    const observer=new ResizeObserver(()=>{
        const width=viewport.clientWidth,height=viewport.clientHeight;
        if(width===viewportWidth&&height===viewportHeight)return;
        viewportWidth=width;viewportHeight=height;
        cancelAnimationFrame(resizeFrame);resizeFrame=requestAnimationFrame(()=>render());
    });observer.observe(viewport);
    const poll=setInterval(()=>{if(root.isConnected)sync();},400);
    queueMicrotask(()=>sync(true));
    return {root,sync,refresh:()=>sync(true),
        executed(data){resolved=data;sync(true);if(data.error)status.title=data.error;},
        destroy(){dead=true;scanRequest?.abort();cancelSearch();resetTiles();thumbnails.clear();lifecycle.abort();observer.disconnect();cancelAnimationFrame(resizeFrame);clearTimeout(filterFrame);clearTimeout(scrollTimer);clearInterval(poll);clearTimeout(debounce);hideTooltip();viewerClose?.();menuClose?.();popupClose?.();promptClose?.();deleteClose?.();unregister();},
    };
}

// Only intercept our gallery drags. Standard ComfyUI file drops continue through its native handlers.
if(typeof document!=="undefined") {
    document.addEventListener("dragover",event=>{if([...event.dataTransfer.types].includes(DRAG_TYPE)){event.preventDefault();event.dataTransfer.dropEffect="copy";}},true);
    document.addEventListener("drop",event=>{
        const value=event.dataTransfer?.getData(DRAG_TYPE);if(!value)return;
        event.preventDefault();event.stopImmediatePropagation();
        let payload;try{payload=JSON.parse(value);}catch{return;}
        const canvas=app.canvas,point=canvas.convertEventToCanvasOffset(event);
        const graph=canvas.graph||app.graph,target=graph.getNodeOnPos?.(point[0],point[1],canvas.visible_nodes);
        (async()=>{
            const response=await fetch(mediaURL(payload.root,payload.item));if(!response.ok)throw new Error("The image could not be read.");
            const blob=await response.blob(),data=new FormData();data.append("image",blob,payload.item.name);data.append("type","input");data.append("overwrite","false");
            const uploaded=await api.fetchApi("/upload/image",{method:"POST",body:data});const file=await uploaded.json();
            if(!uploaded.ok)throw new Error(file.error||"The image could not be imported.");
            graph.beforeChange?.();
            try {
                const loader=target?.type==="LoadImage"?target:globalThis.LiteGraph.createNode("LoadImage");
                if(loader!==target){loader.pos=point;graph.add(loader);}
                const name=file.subfolder?file.subfolder+"/"+file.name:file.name;
                const input=widget(loader,"image");if(!input)throw new Error("The Load Image node has no image input.");
                const values=input.options?.values;if(Array.isArray(values)&&!values.includes(name))values.push(name);
                input.value=name;input.callback?.(name);
                const image=new Image();image.onload=()=>{loader.imgs=[image];loader.setSizeForImage?.();loader.setDirtyCanvas?.(true,true);};
                image.src=api.apiURL(`/view?${new URLSearchParams({filename:file.name,subfolder:file.subfolder||"",type:"input"})}`);
                loader.images=[{filename:file.name,subfolder:file.subfolder||"",type:"input"}];
                loader.setDirtyCanvas?.(true,true);
            }finally{graph.afterChange?.();}
        })().catch(error=>notify(error.message));
    },true);
}
