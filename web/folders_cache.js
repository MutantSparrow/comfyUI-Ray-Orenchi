// File identity includes folder, relative filename, mtime and size. Analysis survives
// workflow/browser reloads without retaining full images or rerunning the model.
let database;
function open() {
    database ||= new Promise(resolve=>{
        if(!globalThis.indexedDB){resolve(null);return;}
        const request=indexedDB.open("ray-folders-analysis-v1",1);
        request.onupgradeneeded=()=>request.result.createObjectStore("analysis");
        request.onsuccess=()=>resolve(request.result);
        request.onerror=()=>resolve(null);
        request.onblocked=()=>resolve(null);
    });
    return database;
}
export async function cachedAnalysis(key) {
    try {
        const db=await open();if(!db)return null;
        return await new Promise(resolve=>{const request=db.transaction("analysis").objectStore("analysis").get(key);request.onsuccess=()=>resolve(request.result||null);request.onerror=()=>resolve(null);});
    }catch{return null;}
}
export async function storeAnalysis(key,value) {
    try {
        const db=await open();if(!db)return;
        const transaction=db.transaction("analysis","readwrite");
        transaction.objectStore("analysis").put(value,key);
        transaction.onerror=()=>{};
    }catch{/* Full or disabled browser storage should not stop browsing. */}
}
