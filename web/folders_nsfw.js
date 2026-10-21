import {nsfwScore} from "./folders_filters.js";

let modelPromise;
export async function classify(image) {
    modelPromise ||= import("./vendor/nsfw/nsfw.mjs").then(module=>module.loadModel()).catch(error=>{modelPromise=null;throw error;});
    const model=await modelPromise;
    const predictions=await model.classify(image,5);
    if(!Number.isFinite(nsfwScore(predictions)))throw new Error("The NSFW model returned invalid scores. Refresh to retry.");
    return predictions;
}

export async function classifyRegions(image) {
    const width=image.naturalWidth||image.width,height=image.naturalHeight||image.height;
    if(!width||!height)throw new Error("The image could not be decoded for NSFW analysis.");
    const canvas=document.createElement("canvas");canvas.width=canvas.height=224;
    const ctx=canvas.getContext("2d"),side=Math.min(width,height)*.7;
    const scores={explicit:0,inclusive:0};
    try {
        // Overlapping crops retain detail that the full image loses at the model's 224px input.
        for(const [x,y] of [[0,0],[1,0],[.5,.5],[0,1],[1,1]]) {
            ctx.drawImage(image,(width-side)*x,(height-side)*y,side,side,0,0,224,224);
            const predictions=await classify(canvas);
            scores.explicit=Math.max(scores.explicit,nsfwScore(predictions,false));
            scores.inclusive=Math.max(scores.inclusive,nsfwScore(predictions,true));
        }
        return scores;
    } finally {canvas.width=canvas.height=1;}
}
