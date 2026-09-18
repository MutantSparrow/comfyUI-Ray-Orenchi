// Benchmark adapter for Spritefusion's published browser engine. Only exposes
// its existing WASM initializer and process function; processing is unchanged.
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const root = __dirname;
const assets = path.join(root, '.references');
const source = fs.readFileSync(path.join(assets, 'snapper_worker.js'), 'utf8')
    .replace('let R=!1;self.onmessage', 'self.initialize=h;self.process=x;let R=!1;self.onmessage');
const self = {};
vm.runInNewContext(source, {self, TextDecoder, TextEncoder, Uint8Array,
    WebAssembly, URL, Response, Request, console, crypto: require('node:crypto').webcrypto});
(async () => {
    await self.initialize(fs.readFileSync(path.join(assets, 'snapper.wasm')));
    const jobs = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
    for (const job of jobs) {
        const start = performance.now();
        try {
            const out = self.process(fs.readFileSync(job.input), job.colors || 32, job.step ?? null, null);
            fs.writeFileSync(job.output, out);
            console.log(JSON.stringify({id:job.id, seconds:(performance.now()-start)/1000}));
        } catch (e) { console.log(JSON.stringify({id:job.id,error:String(e)})); }
    }
})();
