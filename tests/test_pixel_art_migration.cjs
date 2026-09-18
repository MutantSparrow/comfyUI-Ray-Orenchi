const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");
let extension;
const file = process.argv[2] || path.join(__dirname, "..", "web", "ray_pixel_art.js");
const source = fs.readFileSync(file, "utf8").replace(/^import .*;\r?\n/gm, "");
vm.runInNewContext(source, {app: {registerExtension: x => extension = x}, applyBucketTint() {},
    setWidgetHidden(node,widget,hidden) {widget.hidden=hidden;}});
const values = ["auto_downscale_strict", 96, 16, true, 24, "ramps_oklab", 4,
                true, 90, "riemersma", false, .04, true, 2, 42, "fixed"];
const node = {type: "RayPixelArtDetector", widgets_values: values,
              outputs: [{name: "pixel_art", links: [1]}, {name: "palette_preview", links: [2]}]};
extension.beforeConfigureGraph({nodes: [node]});
assert.deepEqual(Array.from(node.widgets_values), ["repair_pixel_art", "auto_pixel_size", 96, 8, "grid_snap", true, 24,
                                                 "source", "error_diffusion", .7, "silhouette", "ramps_oklab", true, 90, false, 4, "area_preserving", "legacy_oklab", 42, "fixed"]);
assert.equal(node.outputs[1].name, "preview");
assert.deepEqual(node.outputs[1].links, [2]);
const migrated = JSON.stringify(node);
extension.beforeConfigureGraph({nodes: [node]});
assert.equal(JSON.stringify(node), migrated);
const previous = {type:"RayPixelArtDetector",widgets_values:["pixel_size",64,6,"nearest",false,16,"none",.5,"none",123,"fixed"]};
extension.beforeConfigureGraph({nodes:[previous]});
assert.deepEqual(Array.from(previous.widgets_values),["repair_pixel_art","pixel_size",64,6,"nearest",false,16,"source","none",.5,"none","kmeans_lab",true,90,false,4,"area_preserving","auto",123,"fixed"]);
const v2={type:"RayPixelArtDetector",widgets_values:["illustration_photo","manual_resize",128,8,"area",true,32,"distinct","ordered",.3,"none",19,"randomize"]};
extension.beforeConfigureGraph({nodes:[v2]});
assert.deepEqual(Array.from(v2.widgets_values),["illustration_photo","manual_resize",128,8,"area",true,32,"distinct","ordered",.3,"none","kmeans_lab",true,90,false,4,"area_preserving","auto",19,"randomize"]);
const saved=JSON.stringify(v2);
extension.beforeConfigureGraph({nodes:[v2]});
assert.equal(JSON.stringify(v2),saved);
const other = {type: "Other", widgets_values: values};
const recent={type:'RayPixelArtDetector',widgets_values:['repair_pixel_art','manual_resize',256,8,'nearest',true,8,'source','none',.7,'none','color_families',true,90,4,'frequency',42,'fixed']};
extension.beforeConfigureGraph({nodes:[recent]});
assert.equal(recent.widgets_values[14],false);
assert.deepEqual(Array.from(recent.widgets_values.slice(15)),[4,'frequency','auto',42,'fixed']);
recent.widgets_values[14]=true;
const gridSaved=JSON.stringify(recent);
extension.beforeConfigureGraph({nodes:[recent]});
assert.equal(JSON.stringify(recent),gridSaved);
const current={type:'RayPixelArtDetector',widgets_values:['repair_pixel_art','manual_resize',64,8,'area',true,32,'source','none',.7,'none','kmeans_lab',true,90,true,4,'area_preserving',6,'fixed']};
extension.beforeConfigureGraph({nodes:[current]});
assert.deepEqual(Array.from(current.widgets_values.slice(17)),['auto',6,'fixed']);
current.widgets_values[17]='lab';
const explicit=JSON.stringify(current);
extension.beforeConfigureGraph({nodes:[current]});
assert.equal(JSON.stringify(current),explicit);
extension.beforeConfigureGraph({nodes: [other]});
assert.equal(other.widgets_values, values);
function Node() {this.widgets=[
    ...["pixel_size","target_resolution","max_colors","palette_style","palette_allocation","palette_mapping","dither_strength","highlight_threshold","ramp_levels"].map(name=>({name})),
    {name:"palette_strategy",value:"kmeans_lab"},{name:"protect_highlights",value:true},
    {name:"mode",value:"manual_resize"},{name:"reduce_palette",value:true},{name:"dither",value:"none"}
];this.inputs=[];}
(async()=>{
    await extension.beforeRegisterNodeDef(Node,{name:"RayPixelArtDetector"});
    const instance=new Node();instance.onNodeCreated();
    const w=name=>instance.widgets.find(w=>w.name===name);
    assert.equal(w('pixel_size').hidden,true);
    assert.equal(w('dither_strength').hidden,true);
    assert.equal(w('ramp_levels').hidden,true);
    assert.equal(Boolean(w('palette_mapping').hidden),false);
    assert.equal(Boolean(w('highlight_threshold').hidden),false);
    w('palette_strategy').value='ramps_oklab';w('palette_strategy').callback();
    assert.equal(w('ramp_levels').hidden,false);
    w('palette_strategy').value='color_families';w('palette_strategy').callback();
    assert.equal(w('palette_style').hidden,true);
    assert.equal(w('palette_allocation').hidden,true);
    assert.equal(w('ramp_levels').hidden,true);
    w('palette_strategy').value='kmeans_lab';w('palette_strategy').callback();
    assert.equal(w('palette_style').hidden,false);
    assert.equal(w('palette_allocation').hidden,false);
    w('protect_highlights').value=false;w('protect_highlights').callback();
    assert.equal(w('highlight_threshold').hidden,true);
    w('mode').value='pixel_size';w('mode').callback();
    assert.equal(w('pixel_size').hidden,false);assert.equal(w('target_resolution').hidden,true);
    instance.inputs.push({name:'palette_image',link:7});instance.onConnectionsChange();
    assert.equal(Boolean(w('palette_mapping').hidden),false);
    assert.equal(w('palette_style').hidden,true);
    assert.equal(w('palette_strategy').hidden,true);
    assert.equal(w('ramp_levels').hidden,true);
    instance.inputs=[];w('reduce_palette').value=false;w('reduce_palette').callback();
    assert.equal(w('palette_mapping').hidden,true);
    console.log("Original/v1 migration, links, idempotence, other nodes and conditional controls passed.");
})();


