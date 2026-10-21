// Usage: npm install --prefix <build-dir> --ignore-scripts nsfwjs@4.4.0 @tensorflow/tfjs@4.22.0 esbuild@0.28.2
//        node scripts/build_folders_nsfw.cjs <build-dir>
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {createRequire} = require('node:module');
const build = path.resolve(process.argv[2]);
const requireBuild = createRequire(path.join(build, 'package.json'));
const esbuild = requireBuild('esbuild');
const packageRoot = path.join(build,'node_modules','nsfwjs');
const destination = path.resolve(__dirname,'../web/vendor/nsfw');
fs.mkdirSync(path.join(destination,'model'),{recursive:true});
function exported(name) {
    const context = {module:{exports:{}},exports:{}};
    vm.runInNewContext(fs.readFileSync(path.join(packageRoot,'dist/models/mobilenet_v2_mid',name),'utf8'),context);
    return context.module.exports;
}
const model = exported('model.min.js');
fs.writeFileSync(path.join(destination,'model','model.json'),JSON.stringify(model));
for(const [index,file] of model.weightsManifest[0].paths.entries()) {
    const base64 = exported(`group1-shard${index+1}of2.min.js`);
    if(typeof base64!=='string')throw new Error('Unexpected NSFWJS weights export');
    fs.writeFileSync(path.join(destination,'model',file),Buffer.from(base64,'base64'));
}
fs.copyFileSync(path.join(packageRoot,'LICENSE'),path.join(destination,'LICENSE-NSFWJS'));
const tfLicense = path.join(build,'node_modules','@tensorflow','tfjs-core','LICENSE');
if(fs.existsSync(tfLicense))fs.copyFileSync(tfLicense,path.join(destination,'LICENSE-TENSORFLOW'));
if(!fs.existsSync(path.join(destination,'LICENSE-TENSORFLOW')))throw new Error('Keep the bundled TensorFlow license (tfjs-v4.22.0/LICENSE).');
esbuild.buildSync({
    stdin:{contents:`import * as tf from '@tensorflow/tfjs';
        import {load} from 'nsfwjs/core';
        export async function loadModel() {
            tf.enableProdMode();
            try {await tf.ready();} catch {await tf.setBackend('cpu');await tf.ready();}
            return load(new URL('./model/model.json',import.meta.url).href,{type:'graph',size:224});
        }`,resolveDir:build,sourcefile:'ray-folders-nsfw.js'},
    outfile:path.join(destination,'nsfw.mjs'),bundle:true,minify:true,format:'esm',platform:'browser',target:'es2022',legalComments:'eof',
});
console.log('Built offline NSFWJS MobileNet V2 Mid assets:',destination);
