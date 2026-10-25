import { COLORS } from "./folders_filters.js";
import { ensurePanelStyles, toggleButton } from "./ray_panel.js";

export function settingsPopup(current,commit,anchor) {
    ensurePanelStyles();
    const backdrop=document.createElement("div");backdrop.className="rf-backdrop";
    const panel=document.createElement("section");panel.className="rf-settings rp-surface";
    panel.setAttribute("role","dialog");panel.setAttribute("aria-label","Folders settings");
    const title=document.createElement("h3");title.className="rp-title";title.textContent="Folders settings";panel.append(title);
    const opts=structuredClone(current);
    let section;
    function addSection(title) {
        section=document.createElement("div");section.className="rp-section";
        const heading=document.createElement("div");heading.className="rp-title";heading.textContent=title;
        section.append(heading);panel.append(section);
    }
    const tips={
        Media:"Choose which media types appear in the gallery and its outputs.",
        "Sort by":"Sort the current listing by filename, modification time, or file size.",
        descending:"Reverse the selected sort order.",recursive:"Include supported files in nested folders.",
        "Thumbnails per row":"Number of thumbnails across the gallery, from two to seven. Changing it keeps the node width unchanged.",
        "Color · none means all":"Keep media matching any selected dominant color. No selected colors means every color is allowed.",
        "NSFW filter":"Show all content, hide content above the score threshold, or show only that content. Classification can make mistakes.",
        "NSFW score threshold":"Score cutoff for content filtering. Lower values classify more files as NSFW; this is not a guarantee of content safety.",
        include_sexy:"Include the classifier's suggestive-content category when calculating the NSFW score.",
        nsfw_regions:"Analyze overlapping crops as well as the full thumbnail. Slower and stricter; cached analysis is reused.",
        hide_no_prompt:"Hide images with no usable embedded or sidecar prompt. Refresh after adding metadata or reconnecting a drive.",
        best_prompt:"Use the best matching prompt candidate instead of combining every available prompt.",
        "Prompt format":"Choose single-line or multiline text for the prompt output; this does not rewrite source files.",
    };
    function field(label,input) {
        const row=document.createElement("label");row.className="rf-setting";
        input.title ||= tips[label] || label;
        const text=document.createElement("span");text.textContent=label;row.append(text,input);section.append(row);return input;
    }
    function check(label,key) {
        const input=toggleButton(tips[key] || label,opts[key],value=>opts[key]=value);
        input.setAttribute("aria-label",label);field(label,input);
    }
    function select(label,key,values) {
        const input=document.createElement("select");
        for(const [value,text] of values) {const option=document.createElement("option");option.value=value;option.textContent=text;input.append(option);}
        input.value=opts[key];input.onchange=()=>opts[key]=input.value;field(label,input);
    }
    const types=document.createElement("div");types.className="rf-checks";
    for(const type of ["image","video","audio"]) {
        const label=document.createElement("label"),input=document.createElement("input");input.type="checkbox";input.checked=opts.types.includes(type);
        input.onchange=()=>opts.types=input.checked?[...opts.types,type]:opts.types.filter(t=>t!==type);
        label.append(input,document.createTextNode(type.charAt(0).toUpperCase()+type.slice(1)));types.append(label);
    }
    addSection("Browsing");field("Media",types);
    select("Sort by","sort",[["name","Name"],["date","Date modified"],["size","File size"]]);
    check("Descending order","descending");check("Include subfolders","recursive");
    const columns=document.createElement("input");columns.type="range";columns.min=2;columns.max=7;columns.step=1;columns.value=opts.columns;
    columns.title=tips["Thumbnails per row"];columns.setAttribute("aria-label","Thumbnails per row");
    const amount=document.createElement("output");amount.textContent=opts.columns;
    const slider=document.createElement("div");slider.className="rf-checks";slider.append(columns,amount);
    columns.oninput=()=>{opts.columns=Number(columns.value);amount.textContent=opts.columns;};field("Thumbnails per row",slider);
    const colors=document.createElement("div");colors.className="rf-swatches";
    addSection("Color");
    const names=["Neutral","Red","Orange","Yellow","Lime","Green","Mint","Cyan","Azure","Blue","Violet","Magenta","Pink"];
    COLORS.forEach((color,i)=>{
        const b=document.createElement("button");b.type="button";b.title=`Filter by ${names[i].toLowerCase()}; multiple colors may be selected`;b.setAttribute("aria-label",names[i]);
        b.style.background=color==="neutral"?"#808080":`hsl(${color.slice(1)},65%,52%)`;
        b.setAttribute("aria-pressed",String(opts.colors.includes(color)));
        b.onclick=()=>{opts.colors=opts.colors.includes(color)?opts.colors.filter(c=>c!==color):[...opts.colors,color];b.setAttribute("aria-pressed",String(opts.colors.includes(color)));};colors.append(b);
    });field("Color · none means all",colors);
    addSection("Content filter");
    select("NSFW filter","nsfw",[["all","Off · show all"],["safe","Hide NSFW"],["unsafe","NSFW only"]]);
    const threshold=document.createElement("input");threshold.type="range";threshold.min=.01;threshold.max=.99;threshold.step=.01;threshold.value=opts.threshold;
    threshold.title=tips["NSFW score threshold"];threshold.setAttribute("aria-label","NSFW score threshold");
    const confidence=document.createElement("output");confidence.textContent=Math.round(opts.threshold*100)+"%";
    const sensitivity=document.createElement("div");sensitivity.className="rf-checks";sensitivity.append(threshold,confidence);
    threshold.oninput=()=>{opts.threshold=Number(threshold.value);confidence.textContent=Math.round(opts.threshold*100)+"%";};field("NSFW score threshold",sensitivity);
    check("Include suggestive content (‘Sexy’)","include_sexy");
    check("Check image regions · slower, stricter","nsfw_regions");
    const nsfwNote=document.createElement("p");nsfwNote.textContent="Lower thresholds hide more files and can hide safe images too. Region checks analyze the full thumbnail plus five overlapping crops; their highest NSFW score is used. The model can still miss content. Changes take effect after Apply.";section.append(nsfwNote);
    const note=document.createElement("p");note.textContent="Color and NSFW filters analyze images and video posters locally. Audio is controlled by the media filter. Results are cached; changing the threshold does not rerun the model.";section.append(note);
    addSection("Prompts");
    check("Hide images without prompts","hide_no_prompt");
    check("Best matching prompt only","best_prompt");
    select("Prompt format","prompt_format",[["single","Single line"],["multiline","Multiline"]]);
    const actions=document.createElement("div");actions.className="rf-actions";
    const cancel=document.createElement("button"),apply=document.createElement("button");cancel.type=apply.type="button";cancel.textContent="Cancel";apply.textContent="Apply";
    cancel.title="Close without applying these changes";apply.title="Apply these gallery settings and refresh the listing";
    const close=()=>{document.removeEventListener("keydown",escape);backdrop.remove();anchor?.focus();};
    const escape=e=>{if(e.key==="Escape")close();};document.addEventListener("keydown",escape);
    cancel.onclick=close;apply.onclick=()=>{commit(opts);close();};actions.append(cancel,apply);panel.append(actions);
    backdrop.onclick=e=>{if(e.target===backdrop)close();};panel.onkeydown=e=>e.stopPropagation();
    // Escape still closes when focus is inside the popup.
    panel.addEventListener("keydown",e=>{if(e.key==="Escape")close();});
    backdrop.append(panel);document.body.append(backdrop);apply.focus();return close;
}
