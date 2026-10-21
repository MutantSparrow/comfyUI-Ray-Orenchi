export const DEFAULTS = {types:["image","video","audio"],sort:"name",descending:false,recursive:false,
    columns:4,colors:[],nsfw:"all",threshold:.6,include_sexy:true,nsfw_regions:true,best_prompt:true,prompt_format:"multiline"};
export const COLORS = ["neutral","h0","h30","h60","h90","h120","h150","h180","h210","h240","h270","h300","h330"];
export function options(value) {
    try { if (typeof value === "string") value = JSON.parse(value); } catch { value = {}; }
    const result = {...DEFAULTS,...(value && typeof value === "object" ? value : {})};
    result.columns = Math.max(2,Math.min(7,Math.round(Number(result.columns)||4)));
    result.threshold = Math.max(.01,Math.min(.99,Number(result.threshold)||.6));
    result.colors = Array.isArray(result.colors) ? result.colors.filter(c=>COLORS.includes(c)) : [];
    result.types = Array.isArray(result.types) ? result.types.filter(t=>["image","video","audio"].includes(t)) : [...DEFAULTS.types];
    return result;
}
const normalize = value => String(value||"").toLowerCase().normalize("NFKD").replace(/\p{M}/gu,"");
function distance(a,b) {
    let row = Array.from({length:b.length+1},(_,i)=>i);
    for (let i=0;i<a.length;i++) {
        const next=[i+1];
        for(let j=0;j<b.length;j++) next.push(Math.min(row[j+1]+1,next[j]+1,row[j]+(a[i]!==b[j])));
        row=next;
    }
    return row[b.length];
}
export function fuzzyMatch(name,query) {
    if(!String(query||"").trim())return true;
    name=normalize(name);
    const words=name.match(/[\p{L}\p{N}_]+/gu)||[];
    return normalize(query).split(/\s+/).filter(Boolean).every(term=>{
        if(name.includes(term)) return true;
        let at=0;
        for(const char of name) if(char===term[at]) at++;
        return at===term.length || (term.length>=3 && words.some(word=>distance(term,word)<=Math.max(1,Math.floor(term.length/4))));
    });
}
// Adapted from FastGallery's MIT-licensed, centre-weighted 32x32 color signature.
export function colorSignature(image) {
    const canvas=document.createElement("canvas");canvas.width=canvas.height=32;
    const ctx=canvas.getContext("2d",{willReadFrequently:true});
    ctx.drawImage(image,0,0,32,32);
    const data=ctx.getImageData(0,0,32,32).data;
    let r=0,g=0,b=0,total=0;
    for(let y=0;y<32;y++) for(let x=0;x<32;x++) {
        const weight=Math.exp(-((x-16)**2+(y-16)**2)/200),i=(y*32+x)*4;
        total+=weight;r+=data[i]*weight;g+=data[i+1]*weight;b+=data[i+2]*weight;
    }
    r/=total*255;g/=total*255;b/=total*255;
    const max=Math.max(r,g,b),min=Math.min(r,g,b),l=(max+min)/2,d=max-min;
    const s=d===0?0:d/(1-Math.abs(2*l-1));
    let h=d===0?0:max===r?((g-b)/d+(g<b?6:0))*60:max===g?((b-r)/d+2)*60:((r-g)/d+4)*60;
    return s<.15||l<.08||l>.92 ? "neutral" : "h"+(Math.floor(h/30)*30);
}
export function nsfwScore(predictions,includeSexy=true) {
    if(!Array.isArray(predictions)||predictions.length!==5)return NaN;
    const classes=new Set(["Drawing","Neutral","Porn","Hentai","Sexy"]);
    let total=0,score=0;
    for(const p of predictions) {
        if(!p||!classes.delete(p.className)||!Number.isFinite(p.probability)||p.probability<0||p.probability>1)return NaN;
        total+=p.probability;
        if(p.className==="Porn"||p.className==="Hentai"||(includeSexy&&p.className==="Sexy"))score+=p.probability;
    }
    return Math.abs(total-1)<.01?Math.min(1,score):NaN;
}
export function analysisScore(analysis,opts) {
    const score=nsfwScore(analysis?.predictions,opts.include_sexy);
    if(!Number.isFinite(score)||!opts.nsfw_regions)return score;
    const region=analysis?.region_scores?.[opts.include_sexy?"inclusive":"explicit"];
    return Number.isFinite(region)&&region>=0&&region<=1?Math.max(score,region):NaN;
}
export function matchesAnalysis(item,opts,analysis) {
    if(item.kind==="audio") return true;
    if(opts.colors.length && (!analysis || !opts.colors.includes(analysis.color))) return false;
    if(opts.nsfw!=="all") {
        const score=analysisScore(analysis,opts);
        if(!Number.isFinite(score))return false;
        const unsafe=score>=opts.threshold;
        if(opts.nsfw==="safe"?unsafe:!unsafe) return false;
    }
    return true;
}
export function promptText(info,opts) {
    let prompts=info.prompts||[];
    if(opts.best_prompt && prompts.length) prompts=[prompts.reduce((a,b)=>a.length>=b.length?a:b)];
    const text=prompts.join("\n\n");
    return opts.prompt_format==="single"?text.replace(/\s+/g," ").trim():text;
}
