// Keep a small session cache across scrolling and folder refreshes. The server also
// caches generated JPEGs by file revision; no full-resolution media is retained here.
export function createThumbnailCache() {
    const entries=new Map();let bytes=0,pinned=new Set();
    function trim() {
        for(const [key,entry] of entries) {
            if(entries.size<=128&&bytes<=24*1024*1024)break;
            if(pinned.has(key))continue;
            URL.revokeObjectURL(entry.url);entries.delete(key);bytes-=entry.bytes;
        }
    }
    return {
        setWindow(keys){pinned=new Set(keys);trim();},
        async load(key,url,signal) {
            let entry=entries.get(key),created=false;
            if(entry){entries.delete(key);entries.set(key,entry);}
            else {
                const response=await fetch(url,{signal});
                if(!response.ok)throw new Error("File unavailable or preview unsupported. Refresh to retry.");
                const blob=await response.blob();
                if(signal.aborted)throw new DOMException("Preview canceled","AbortError");
                entry={url:URL.createObjectURL(blob),bytes:blob.size};created=true;
            }
            const image=new Image();image.decoding="async";
            let rejectCanceled;
            const canceled=new Promise((resolve,reject)=>{rejectCanceled=reject;});
            const cancel=()=>{image.removeAttribute("src");rejectCanceled(new DOMException("Preview canceled","AbortError"));};
            signal.addEventListener("abort",cancel,{once:true});
            try {
                if(signal.aborted)throw new DOMException("Preview canceled","AbortError");
                image.src=entry.url;await Promise.race([image.decode(),canceled]);
                if(signal.aborted)throw new DOMException("Preview canceled","AbortError");
                if(created){entries.set(key,entry);bytes+=entry.bytes;trim();}
                return {url:entry.url,image};
            } catch(error) {
                if(!created&&!signal.aborted&&entries.get(key)===entry){entries.delete(key);bytes-=entry.bytes;URL.revokeObjectURL(entry.url);}
                if(created)URL.revokeObjectURL(entry.url);
                throw error;
            }
            finally {signal.removeEventListener("abort",cancel);}
        },
        remove(key){const entry=entries.get(key);if(entry){URL.revokeObjectURL(entry.url);entries.delete(key);bytes-=entry.bytes;}pinned.delete(key);},
        clear(){for(const entry of entries.values())URL.revokeObjectURL(entry.url);entries.clear();bytes=0;},
    };
}
