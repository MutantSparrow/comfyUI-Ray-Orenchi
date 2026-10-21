import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
const source=await readFile(new URL('../web/folders_filters.js',import.meta.url),'utf8');
const {options,nsfwScore,analysisScore,matchesAnalysis}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));

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
console.log('NSFW filter regression checks passed');
