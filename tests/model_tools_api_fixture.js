export const browseFixture = { requests: [], path: 'C:\\models\\chosen.safetensors', cancelled: false, error: null };
export const api = { async fetchApi(url, options) {
    const body = JSON.parse(options.body);
    if (url === '/ray/browse') {
        browseFixture.requests.push(body);
        return {ok:!browseFixture.error, async json() { return {ok:!browseFixture.error,
            path:browseFixture.path, cancelled:browseFixture.cancelled, error:browseFixture.error}; }};
    }
    const metadata = {title:'Example model',literal:'001',nested:'{ "tags": ["a", "b"], "v": 1 }',unicode:'日本語'};
    const report = body.action === 'metadata' ? {metadata, source:'C:\\models\\example.safetensors'} : {
        architecture:{name:'SDXL',note:'Architecture does not establish checkpoint identity.'},tensor_count:250,
        tensor_bytes:6450000000,rows_truncated:0,dtypes:{BF16:250},metadata,
        rows:Array.from({length:250},(_,i)=>({name:`diffusion_model.block.${i}.weight`,shape:[320,320],dtype:'BF16'}))};
    return {ok:true,async json(){return report;}};
} };
