import { app, nodeClass } from '/scripts/app.js';
import '/extensions/ray/ray_knob.js';
import '/extensions/ray/ray_switch.js';
import { KNOB_STYLES } from '/extensions/ray/knob_styles.js';
import { SWITCH_STYLES } from '/extensions/ray/switch_styles.js';
import { quantizeInt, boundValue } from '/extensions/ray/ray_knob.js';
import { isMuted, setMuted, createBank, VOICE_TABLES } from '/extensions/ray/analog_audio.js';

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
        const values = knob.widgets.slice(0,5).map(w=>w.value);
        const slots = knob.outputs;
        knob.properties.compact = true; control.applyCompact();
        check(knob.outputs === slots && knob.outputs.length===2,'Compact preserves actual output slots');
        check(knob.title.includes('Knob'),'Compact preserves saved title');
        check(knob.widgets.slice(0,4).every(w=>w.hidden),'Compact hides numeric configuration');
        knob.properties.compact=false; control.applyCompact();
        check(knob.widgets.slice(0,4).every(w=>!w.hidden && ['number','toggle'].includes(w.type)),'Expand restores native types');
        check(JSON.stringify(values)===JSON.stringify(knob.widgets.slice(0,5).map(w=>w.value)),'Presentation preserves serialized input order and values');
        const value = widget(knob,'knob_value');
        widget(knob,'clamp').value = 2.5;
        check(quantizeInt(knob,6)===5 && quantizeInt(knob,-6)===-7,'Fractional quantization matches Python INT truncation');
        widget(knob,'allow_negative').value=false;
        widget(knob,'max_value').value=-1;
        check(boundValue(knob,-9)===0,'Inverted nonnegative bounds match backend');
        widget(knob,'allow_negative').value=true; widget(knob,'max_value').value=100;
        control.host.dispatchEvent(new KeyboardEvent('keydown',{key:'ArrowUp',bubbles:true,cancelable:true}));
        check(Math.abs(value.value-1)<1e-9 && knob.callbacks===1,'Keyboard steps 1/200 of the range and calls the callback exactly once');
        control.host.dispatchEvent(new KeyboardEvent('keydown',{key:'ArrowDown',shiftKey:true,bubbles:true,cancelable:true}));
        check(Math.abs(value.value-.9)<1e-9,'Shift slows keyboard steps tenfold');
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
    {
        // Sliders: horizontal and vertical travel, LED ladder and fill indicators.
        const node=make('knob'), ui=node._rayAnalog; document.body.append(ui.element);
        const value=widget(node,'knob_value'), slideOf=()=>ui.host.querySelector('[data-slide]');
        const setAt=(style,v)=>{ node.properties.style=style; value.value=v; ui.render(); };
        setAt('pan_slider',-100); check(slideOf().getAttribute('transform')==='translate(-43.000,0)','Horizontal slider sits at the left end');
        setAt('pan_slider',100); check(slideOf().getAttribute('transform')==='translate(43.000,0)','Horizontal slider sits at the right end');
        setAt('channel_fader',100); check(slideOf().getAttribute('transform')==='translate(0,-43.000)','Vertical slider sits at the top');
        setAt('channel_fader',-100); check(slideOf().getAttribute('transform')==='translate(0,43.000)','Vertical slider sits at the bottom');
        check(ui.element.dataset.control==='slider','Slider styles are flagged as sliders');
        setAt('console_rotary',0); check(ui.element.dataset.control==='knob','Knob styles are flagged as knobs');
        const lit=()=>[...ui.host.querySelectorAll('[data-led][data-on="1"]')].filter(el=>el.style.opacity==='1').length;
        setAt('led_ladder',-100); check(lit()===0,'LED ladder is dark at minimum');
        setAt('led_ladder',100); check(lit()===12,'LED ladder is fully lit at maximum');
        setAt('led_ladder',0); check(lit()===6,'LED ladder lights half its segments at mid range');
        const fill=()=>ui.host.querySelector('[data-fill]').getAttribute('transform');
        setAt('amber_slide',-100); check(fill()==='scale(0.0000,1)','Amber bar is empty at minimum');
        setAt('amber_slide',100); check(fill()==='scale(1.0000,1)','Amber bar is full at maximum');
        node.onRemoved(); ui.element.remove();
    }
    {
        // Sound: the mute option, the persisted preference, and a voice for every style.
        setMuted(false);
        const node=make('knob'), toggle=make('switch');
        for (const n of [node,toggle]) {
            const options=[]; n.getExtraMenuOptions({},options);
            const item=options.find(o=>/sound/i.test(o.content||''));
            check(!!item && /Mute/.test(item.content),'Right-click menu offers Mute sound');
            item.callback();
            check(isMuted() && localStorage.getItem('ray.analog.muted.v1')==='1','Mute persists as a listener preference');
            const again=[]; n.getExtraMenuOptions({},again);
            check(/Unmute/.test(again.find(o=>/sound/i.test(o.content||'')).content),'Menu offers Unmute while muted');
            setMuted(false);
        }
        // The style choice is a plain menu entry that opens a floating picker, never a nested submenu.
        const styleMenu=[]; node.getExtraMenuOptions({},styleMenu);
        const styleItem=styleMenu.find(o=>/Style…$/.test(o.content));
        check(!!styleItem && !styleItem.has_submenu && !styleItem.submenu,'Style is a plain menu entry, not a nested submenu');
        styleItem.callback(); await new Promise(r=>setTimeout(r,20));
        const picker=document.querySelector('.ray-style-picker');
        check(!!picker && picker.getBoundingClientRect().left>=0 && picker.getBoundingClientRect().right<=innerWidth && picker.getBoundingClientRect().bottom<=innerHeight,'Style picker opens fully inside the window');
        check([...picker.querySelectorAll('.ray-style-heading')].map(h=>h.textContent).join()==='Knobs,Sliders','Style picker groups knobs and sliders');
        check(picker.querySelectorAll('.ray-style-item').length===Object.keys(KNOB_STYLES).length,'Style picker lists every style');
        check(picker.scrollWidth<=picker.clientWidth,'Style picker never scrolls sideways');
        const target=[...picker.querySelectorAll('.ray-style-item')].find(b=>/Channel Fader/.test(b.textContent));
        target.click();
        check(node.properties.style==='channel_fader' && !document.querySelector('.ray-style-picker'),'Choosing a style applies it and closes the picker');
        node.properties.style='console_rotary';
        styleItem.callback(); await new Promise(r=>setTimeout(r,20));
        document.querySelector('.ray-style-picker').dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}));
        check(!document.querySelector('.ray-style-picker') && node.properties.style==='console_rotary','Escape closes the picker without changing the style');
        const octx=new OfflineAudioContext(1,22050,44100);
        const bank=createBank(octx,octx.destination);
        for (const [kind,styles] of [['knob',KNOB_STYLES],['switch',SWITCH_STYLES]]) {
            for (const key of Object.keys(styles)) check(Object.hasOwn(VOICE_TABLES[kind],key),`${kind} style ${key} has a sound voice`);
        }
        for (const voice of new Set(Object.values(VOICE_TABLES.switch))) check(bank.voices.presses.includes(voice),`Switch voice ${voice} exists`);
        for (const voice of new Set(Object.values(VOICE_TABLES.knob))) check(bank.voices.ticks.includes(voice),`Knob voice ${voice} exists`);
        for (const voice of bank.voices.presses) { const o=new OfflineAudioContext(1,22050,44100); const b=createBank(o,o.destination); b.press(voice,true,0); b.press(voice,false,0.1);
            const peak=(await o.startRendering()).getChannelData(0).reduce((m,x)=>Math.max(m,Math.abs(x)),0);
            check(peak>0.05 && peak<1,`Switch voice ${voice} is audible and does not clip`); }
        for (const voice of bank.voices.ticks) { const o=new OfflineAudioContext(1,22050,44100); const b=createBank(o,o.destination); b.tick(voice,1,0);
            const peak=(await o.startRendering()).getChannelData(0).reduce((m,x)=>Math.max(m,Math.abs(x)),0);
            check(peak>0.02 && peak<1,`Tick voice ${voice} is audible and does not clip`); }
        node.onRemoved(); toggle.onRemoved();
    }
    for (const kind of ['knob','switch']) {
        const node=make(kind,false,false);
        check(node.widgets.every(w=>!w.hidden),'Native fallback stays usable without DOM widget support');
    }
    const old={nodes:[{type:'RayKnob',properties:{compact:true,ray_label:'GAIN'},title:'',outputs:[],widgets_values:[-100,100,20,0,true,17]},
        {type:'RaySwitch',properties:{compact:true},outputs:[]}]};
    for(const extension of app.extensions) extension.beforeConfigureGraph(old);
    check(old.nodes[0].outputs.length===2 && old.nodes[1].outputs.length===1,'Repair outputs lost by historical compact saves');
    check(JSON.stringify(old.nodes[0].widgets_values)==='[-100,100,0,true,17]' && old.nodes[0].properties.ray_label==='GAIN','Migration drops the saved spin value and keeps the rest and the label');
    const first=JSON.stringify(old);
    for(const extension of app.extensions) extension.beforeConfigureGraph(old);
    check(first===JSON.stringify(old),'Migration is idempotent');
    {
        // A saved Control with a spin_value input slot, wired on both sides of it.
        const graph={nodes:[
            {id:1,type:'Primitive',outputs:[{name:'out',links:[9,10]}]},
            {id:5,type:'RayKnob',inputs:[{name:'min_value',link:null},{name:'max_value',link:null},{name:'spin_value',link:9},
                {name:'clamp',link:null},{name:'allow_negative',link:null},{name:'knob_value',link:10}],widgets_values:[0,1,20,0,true,.5]}],
            links:[[9,1,0,5,2,'FLOAT'],[10,1,0,5,5,'FLOAT']]};
        for(const extension of app.extensions) extension.beforeConfigureGraph(graph);
        check(graph.nodes[1].inputs.length===5 && !graph.nodes[1].inputs.some(i=>i.name==='spin_value'),'Migration removes the spin_value input slot');
        check(graph.links.length===1 && graph.links[0][4]===4,'Links into later slots shift down and the spin_value link is dropped');
        check(JSON.stringify(graph.nodes[0].outputs[0].links)==='[10]','The dropped link is removed from its source output');
        check(JSON.stringify(graph.nodes[1].widgets_values)==='[0,1,0,true,0.5]','Saved 0..1 range and value survive the migration');
        const again=JSON.stringify(graph);
        for(const extension of app.extensions) extension.beforeConfigureGraph(graph);
        check(again===JSON.stringify(graph),'Spin migration is idempotent');
    }
    {
        // Every knob face sweeps min..max over 270 degrees; legacy faces start at 7:30 like the studio ones.
        const node=make('knob'), ui=node._rayAnalog; document.body.append(ui.element);
        const value=widget(node,'knob_value');
        const angleAt=(style,v)=>{ node.properties.style=style; value.value=v; ui.render();
            return Number(/rotate\(([-\d.]+)\)/.exec(ui.host.querySelector('[data-rotate]')?.getAttribute('transform')||'')?.[1]); };
        for (const [key,style] of Object.entries(KNOB_STYLES)) {
            if (style.kind==='slider') continue;
            const zero=style.zero ?? -135;
            check(angleAt(key,-100)===zero && angleAt(key,100)===zero+270,`Knob ${key} sweeps 270 degrees from min to max`);
        }
        widget(node,'min_value').value=0; widget(node,'max_value').value=1;
        check(angleAt('console_rotary',.5)===0,'A 0..1 range centres the dial at 0.5');
        node.properties.style='dark_studio_led'; value.value=1; ui.render();
        const arc=ui.host.querySelector('[data-arc]');
        check(arc.getAttribute('stroke-dasharray')==='75.00 100' && arc.getAttribute('stroke-dashoffset')==='-37.5','LED arc covers the 270 degree sweep');
        node.onRemoved(); ui.element.remove();
    }
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
