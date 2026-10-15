// Deliberately tests both POJO widgets and widgets with prototype value accessors.
// Actual ComfyUI renderer integration still requires the live smoke test.
export const app = { extensions: [], registerExtension(extension) { this.extensions.push(extension); } };
class StoredWidget {
    constructor(data) { Object.assign(this, data); }
    get value() { return this._value; }
    set value(value) { this._value = value; }
}
export function nodeClass(kind, accessor = false, dom = true) {
    return class Node {
        constructor() {
            this.title = kind === 'knob' ? "🎛️ Ray's Analog: Knob" : kind === 'deck' ? "🎛️ Ray's Analog: Button Deck" : kind === 'fader' ? "🎛️ Ray's Analog: Fader Bank" : "🎛️ Ray's Analog: Switch";
            this.widgets = Object.entries(kind === 'knob' ? {
                min_value:-100,max_value:100,clamp:0,allow_negative:true,knob_value:0,
            } : kind === 'deck' ? {entries:"Alpha\nBeta\nGamma",selected:""} : kind === 'fader' ? {
                faders:4,...Object.fromEntries(Array.from({length:10},(_,i)=>[`fader_${i+1}`,.5])),
            } : {state:false}).map(([name,value]) => {
                const data = { name, value, type:typeof value === 'boolean' ? 'toggle' : typeof value === 'string' ? 'text' : 'number', options:{},
                    callback: () => { this.callbacks++; } };
                return accessor ? new StoredWidget(data) : data;
            });
            this.callbacks = 0;
            this.inputs = [];
            this.outputs = (kind === 'knob' ? [['int','INT'],['float','FLOAT']] : kind === 'deck' ? [['value','STRING']]
                : kind === 'fader' ? [['values','FLOAT'],...Array.from({length:10},(_,i)=>[`fader_${i+1}`,'FLOAT'])] : [['bool','BOOLEAN']])
                .map(([name,type]) => ({name,type,links:null}));
            this.size = [230,260]; this.flags = {}; this.properties = {};
            this.graph = { before:0, after:0, beforeChange(){this.before++;}, afterChange(){this.after++;}, change(){} };
            if (!dom) this.addDOMWidget = undefined;
        }
        addProperty(name, value) { this.properties[name] = value; }
        addOutput(name, type) { this.outputs.push({name,type,links:null}); }
        removeOutput(slot) { this.outputs.splice(slot, 1); }
        addDOMWidget(name,type,element,options) {
            const widget = {name,type,element,options}; this.widgets.push(widget); return widget;
        }
        addWidget(type,name,value,callback) {
            const widget = {name,type,value,callback,options:{}}; this.widgets.push(widget); return widget;
        }
        computeSize() { return [230,260]; }
        setSize(value) { this.size = value; }
        setDirtyCanvas() {}
    };
}
