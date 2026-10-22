import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
const source=await readFile(new URL('../web/folders_filters.js',import.meta.url),'utf8');
const {options,nsfwScore,analysisScore,matchesAnalysis,fuzzyMatch,searchFilenames}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));

const predictions=(drawing,neutral,porn,hentai,sexy)=>[
    {className:'Drawing',probability:drawing},{className:'Neutral',probability:neutral},
    {className:'Porn',probability:porn},{className:'Hentai',probability:hentai},
    {className:'Sexy',probability:sexy},
];
const item={kind:'image'},base={predictions:predictions(.2,.77,.01,.01,.01)};
const opts=options({nsfw:'safe',threshold:.05});
assert.equal(opts.include_sexy,true);
assert.equal(opts.nsfw_regions,true);
assert.equal(options({threshold:.01}).threshold,.01);
assert.ok(Math.abs(nsfwScore(base.predictions)-.03)<1e-6);
assert.ok(Math.abs(nsfwScore(base.predictions,false)-.02)<1e-6);
assert.equal(matchesAnalysis(item,opts,base),false,'Pending region checks must not pass as safe');
const regional={...base,region_scores:{explicit:.36,inclusive:.4}};
assert.equal(analysisScore(regional,opts),.4);
assert.equal(matchesAnalysis(item,opts,regional),false,'Regional hit hides a file missed by its full thumbnail');
assert.equal(matchesAnalysis(item,{...opts,nsfw:'unsafe'},regional),true);
assert.equal(matchesAnalysis(item,{...opts,nsfw_regions:false},regional),true,'Fast mode uses the full thumbnail');
assert.equal(matchesAnalysis(item,{...opts,threshold:.4},regional),false,'Threshold comparison is inclusive');
const suggestive={predictions:predictions(.1,.1,.01,.01,.78),region_scores:{explicit:.01,inclusive:.1}};
assert.equal(matchesAnalysis(item,opts,suggestive),false,'Suggestive category participates in the combined score');
assert.equal(matchesAnalysis(item,{...opts,include_sexy:false},suggestive),true,'Explicit-only setting remains supported');
const safe={...base,region_scores:{explicit:.01,inclusive:.02}};
assert.equal(matchesAnalysis(item,opts,safe),true);
for(const invalid of [undefined,[],[{className:'Porn',probability:NaN}],predictions(.2,.2,.2,.2,2)]) {
    assert.equal(matchesAnalysis(item,{...opts,nsfw_regions:false},{predictions:invalid}),false,'Invalid model results must not pass as safe');
}
assert.equal(matchesAnalysis(item,opts,{...base,region_scores:{explicit:NaN,inclusive:NaN}}),false);
assert.equal(matchesAnalysis(item,{...opts,nsfw:'all'},undefined),true);
assert.equal(matchesAnalysis({kind:'audio'},opts,undefined),true);
for(const [name,query,expected] of [
    ['Red_Cat_01.png','red cat',true],['Red_Cat_01.png','rdct',true],['Cat portrait.png','catt',true],
    ['Bär im Wald.png','bar wld',true],['cat.png','zzzz',false],['cat.png','',true],['dog.png','cat',false],
    ['a'.repeat(200)+'.png','xyz',false],['00001.png','a very long prompt pasted into search',false],
])assert.equal(fuzzyMatch(name,query),expected,`${name} / ${query}`);
const many=Array.from({length:100000},(_,i)=>({id:String(i),name:`render_${i}_a_long_camera_description_and_model_name.png`}));
let ticks=0;const heartbeat=setInterval(()=>ticks++,0),controller=new AbortController();
try {
    const start=performance.now(),pending=searchFilenames(many,'mountain sunset',controller.signal);
    assert.ok(performance.now()-start<100,'Starting a six-figure filename search must yield promptly');
    const result=await pending;
    assert.equal(result.matches.length,0);assert.equal(result.remaining.length,100000);
    assert.ok(ticks>1,'Keyboard and paint timers must run during filename matching');
} finally {clearInterval(heartbeat);}
const canceled=new AbortController(),pending=searchFilenames(many,'portrait',canceled.signal);
setTimeout(()=>canceled.abort(),0);
await assert.rejects(pending,{name:'AbortError'},'Superseded queries must stop between small chunks');
console.log('Folder search responsiveness, cancellation, fuzzy matching and NSFW checks passed');
