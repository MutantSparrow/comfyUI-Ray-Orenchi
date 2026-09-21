import { app, nodeClass } from '/scripts/app.js';
import '/extensions/ray/ray_knob.js';
import '/extensions/ray/ray_switch.js';
import { KNOB_STYLES } from '/extensions/ray/knob_styles.js';
import { SWITCH_STYLES } from '/extensions/ray/switch_styles.js';
import { quantizeInt, boundValue } from '/extensions/ray/ray_knob.js';

const messages = [];
let passes = 0;
function check(condition, message) {
    if (!condition) throw Error(message);
    passes++; messages.push('PASS ' + message);
}
const widget = (node,name) => node.widgets.find(w => w.name === name);
const make = (kind,accessor=false,dom=true) => {
    const Type = nodeClass(kind,accessor,dom);
    const extension = app.extensions.find(e => e.name === (kind==='knob'?'Ray.Knob':'Ray.Switch'));
    extension.beforeRegisterNodeDef(Type,{name:kind==='knob'?'RayKnob':'RaySwitch'});
    const node = new Type(); node.onNodeCreated(); return node;
};
try {
    for (const accessor of [false,true]) {
        const knob = make('knob',accessor);
        const control = knob._rayAnalog;
        document.body.append(control.element);
        const values = knob.widgets.slice(0,6).map(w=>w.value);
        const slots = knob.outputs;
        knob.properties.compact = true; control.applyCompact();
        check(knob.outputs === slots && knob.outputs.length===2,'Compact preserves actual output slots');
        check(knob.title.includes('Knob'),'Compact preserves saved title');
        check(knob.widgets.slice(0,5).every(w=>w.hidden),'Compact hides numeric configuration');
        knob.properties.compact=false; control.applyCompact();
        check(knob.widgets.slice(0,5).every(w=>!w.hidden && ['number','toggle'].includes(w.type)),'Expand restores native types');
        check(JSON.stringify(values)===JSON.stringify(knob.widgets.slice(0,6).map(w=>w.value)),'Presentation preserves serialized input order and values');
        const value = widget(knob,'knob_value');
        widget(knob,'clamp').value = 2.5;
        check(quantizeInt(knob,6)===5 && quantizeInt(knob,-6)===-7,'Fractional quantization matches Python INT truncation');
        widget(knob,'allow_negative').value=false;
        widget(knob,'max_value').value=-1;
        check(boundValue(knob,-9)===0,'Inverted nonnegative bounds match backend');
        widget(knob,'allow_negative').value=true; widget(knob,'max_value').value=100;
        control.host.dispatchEvent(new KeyboardEvent('keydown',{key:'ArrowUp',bubbles:true,cancelable:true}));
        check(Math.abs(value.value-.2)<1e-9 && knob.callbacks===1,'Keyboard updates backing widget and callback exactly once');
        control.host.dispatchEvent(new KeyboardEvent('keydown',{key:'End',bubbles:true,cancelable:true}));
        check(value.value===100,'End reaches upper bound');
        control.host.dispatchEvent(new KeyboardEvent('keydown',{key:'Home',bubbles:true,cancelable:true}));
        check(value.value===-100,'Home reaches lower bound');
        const input=control.readout.querySelector('input');
        input.value='12.75'; input.dispatchEvent(new Event('change',{bubbles:true}));
        check(value.value===12.75,'Exact value entry');
        input.value='invalid'; input.dispatchEvent(new Event('change',{bubbles:true}));
        check(value.value===12.75 && input.value==='12.75','Invalid text cannot corrupt output');
        knob.inputs=[{name:'knob_value',link:23}]; knob.onConnectionsChange();
        control.host.dispatchEvent(new KeyboardEvent('keydown',{key:'End',cancelable:true}));
        check(value.value===12.75 && input.disabled,'Linked input disables local value editing');
        knob.inputs=[]; knob.onConnectionsChange();
        for (const key of Object.keys(KNOB_STYLES)) {
            knob.properties.style=key; control.render();
            check(!!control.host.querySelector('svg'),`Knob style ${key} renders`);
        }
        check(knob.graph.before===knob.graph.after,'Value edits balance history transactions');
        knob.onRemoved(); control.element.remove();

        const toggle=make('switch',accessor), ui=toggle._rayAnalog;
        document.body.append(ui.element);
        ui.host.dispatchEvent(new PointerEvent('pointerdown',{button:0,bubbles:true}));
        ui.host.dispatchEvent(new MouseEvent('mousedown',{button:0,bubbles:true}));
        check(widget(toggle,'state').value===false,'Pointer and compatibility mouse events do not double-toggle');
        ui.host.click();
        check(widget(toggle,'state').value===true && toggle.callbacks===1,'One click toggles once and calls native callback');
        ui.dymo.root.dispatchEvent(new PointerEvent('pointerdown',{button:0,bubbles:true}));
        ui.dymo.root.click();
        check(widget(toggle,'state').value===true,'Label clicks do not activate switch');
        ui.dymo.beginEdit(); ui.dymo.text.textContent='BUS A';
        ui.dymo.text.dispatchEvent(new FocusEvent('blur'));
        check(toggle.properties.ray_label==='BUS A','Label commit persists');
        ui.dymo.beginEdit(); ui.dymo.text.textContent='CANCEL';
        ui.dymo.text.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true,cancelable:true}));
        check(toggle.properties.ray_label==='BUS A','Escape cancels label edit');
        toggle.inputs=[{name:'state',link:1}]; toggle.onConnectionsChange(); ui.host.click();
        check(widget(toggle,'state').value===true,'Externally wired switch cannot change local output');
        for (const key of Object.keys(SWITCH_STYLES)) {
            toggle.properties.style=key; ui.render();
            check(!!ui.host.querySelector('svg'),`Switch style ${key} renders`);
        }
        toggle.onRemoved(); ui.element.remove();
    }
    for (const kind of ['knob','switch']) {
        const node=make(kind,false,false);
        check(node.widgets.every(w=>!w.hidden),'Native fallback stays usable without DOM widget support');
    }
    const old={nodes:[{type:'RayKnob',properties:{compact:true,ray_label:'GAIN'},title:'',outputs:[],widgets_values:[-100,100,20,0,true,17]},
        {type:'RaySwitch',properties:{compact:true},outputs:[]}]};
    for(const extension of app.extensions) extension.beforeConfigureGraph(old);
    check(old.nodes[0].outputs.length===2 && old.nodes[1].outputs.length===1,'Repair outputs lost by historical compact saves');
    check(old.nodes[0].widgets_values[5]===17 && old.nodes[0].properties.ray_label==='GAIN','Migration preserves values and label');
    const first=JSON.stringify(old);
    for(const extension of app.extensions) extension.beforeConfigureGraph(old);
    check(first===JSON.stringify(old),'Migration is idempotent');
    const linked={nodes:[{type:'RaySwitch',outputs:[{name:'bool',type:'BOOLEAN',links:[77]}]}]};
    for(const extension of app.extensions) extension.beforeConfigureGraph(linked);
    check(linked.nodes[0].outputs[0].links[0]===77,'Migration preserves live links');

    for (const [kind,styles] of [['knob',KNOB_STYLES],['switch',SWITCH_STYLES]]) {
        for (const [key,style] of Object.entries(styles)) {
            const node=make(kind); node.properties.style=key; node.properties.ray_label=kind==='knob'?'CHANNEL GAIN':'SIGNAL ROUTE';
            node._rayAnalog.dymo.setText(node.properties.ray_label);
            if(kind==='knob')widget(node,'knob_value').value=20; else widget(node,'state').value=true;
            node._rayAnalog.render();
            const card=document.createElement('section');card.className='card';
            const heading=document.createElement('header');heading.textContent=style.label;
            card.append(heading,node._rayAnalog.element);document.querySelector('#gallery').append(card);
        }
    }
    check([...document.querySelectorAll('svg *')].every(el =>
        [...el.attributes].every(attr => [...attr.value.matchAll(/url\(#([^)]+)\)/g)]
            .every(match => document.getElementById(match[1])))),
        'All mounted SVG material references resolve, including masks and strokes');
    const ids=[...document.querySelectorAll('svg [id]')].map(el=>el.id);
    check(new Set(ids).size===ids.length,'All simultaneously mounted SVG resource IDs are unique');
    check([...document.querySelectorAll('svg [fill^="url(#"]')].every(el=>document.getElementById(el.getAttribute('fill').slice(5,-1))), 'SVG gradient references resolve');
    document.querySelector('#results').textContent=`${passes} checks passed\n`+messages.join('\n');
    document.querySelector('summary').textContent=`Regression results — ${passes} checks passed`;
} catch(error) {
    document.querySelector('#results').textContent=messages.join('\n')+'\nFAIL '+error.stack;
    document.querySelector('details').open=true;
    document.querySelector('summary').textContent='Regression failed';
}
