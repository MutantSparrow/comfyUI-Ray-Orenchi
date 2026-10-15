import { app, nodeClass } from '/scripts/app.js';
import '/extensions/ray/ray_knob.js';
import '/extensions/ray/ray_switch.js';
import '/extensions/ray/ray_button_deck.js';
import '/extensions/ray/ray_fader_bank.js';
import { DECK_STYLES, gridShape } from '/extensions/ray/deck_styles.js';
import { parseEntries } from '/extensions/ray/ray_button_deck.js';
import { migrateClipInput } from '/extensions/ray/ray_vlm_folder.js';
import { KNOB_STYLES } from '/extensions/ray/knob_styles.js';
import { SWITCH_STYLES } from '/extensions/ray/switch_styles.js';
import { quantizeInt, boundValue } from '/extensions/ray/ray_knob.js';
import { isMuted, setMuted, createBank, VOICE_TABLES } from '/extensions/ray/analog_audio.js';
import { isWheelOn, setWheelOn, wheelUnits } from '/extensions/ray/analog_common.js';
import { clampCount, clampLevel, syncOutputs } from '/extensions/ray/ray_fader_bank.js';
import { FADER_STYLES } from '/extensions/ray/fader_styles.js';
import { THEMES, VOICE_CLASSES, FAMILIES, familyOf, MATERIALS } from '/extensions/ray/analog_themes.js';
import { KNOBS, SLIDERS, SWITCHES, GENERATED_KNOBS, GENERATED_SLIDERS, GENERATED_SWITCHES } from '/extensions/ray/analog_hardware.js';
import { knobVoice, switchVoice } from '/extensions/ray/analog_audio.js';

const messages = [];
let passes = 0;
function check(condition, message) {
    if (!condition) throw Error(message);
    passes++; messages.push('PASS ' + message);
}
const widget = (node,name) => node.widgets.find(w => w.name === name);
const make = (kind,accessor=false,dom=true) => {
    const Type = nodeClass(kind,accessor,dom);
    const extension = app.extensions.find(e => e.name === {knob:'Ray.Knob',switch:'Ray.Switch',deck:'Ray.ButtonDeck',fader:'Ray.FaderBank'}[kind]);
    extension.beforeRegisterNodeDef(Type,{name:{knob:'RayKnob',switch:'RaySwitch',deck:'RayButtonDeck',fader:'RayFaderBank'}[kind]});
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
        check([...picker.querySelectorAll('.ray-style-heading')].map(h=>h.textContent).join()==='Console,Broadcast,Mastering,Rack','Style picker groups the styles by family');
        check([...picker.querySelectorAll('.ray-style-kind')].every(tag=>tag.textContent==='slider') && picker.querySelectorAll('.ray-style-kind').length===8,'Slider faces are tagged in the Control picker');
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
    {
        // Button deck: grid rule, exclusive pressed state, keyboard, entries popout, styles, sound.
        const shapes={1:[1,1],2:[2,1],3:[2,2],4:[2,2],5:[3,2],6:[3,2],7:[3,3],9:[3,3],10:[4,3],12:[4,3],13:[4,4]};
        for (const [n,[cols,rows]] of Object.entries(shapes)) { const g=gridShape(Number(n)); check(g.cols===cols && g.rows===rows,`${n} buttons arrange as ${cols} x ${rows}`); }
        check(JSON.stringify(parseEntries('  a \r\n\r\nb\na\n c'))==='["a","b","c"]','Entries: one per line, trimmed, blanks and repeats dropped');
        for (const accessor of [false,true]) {
            const deck=make('deck',accessor), ui=deck._rayAnalog; document.body.append(ui.element);
            const entriesW=widget(deck,'entries'), selectedW=widget(deck,'selected');
            check(entriesW.hidden===true,'The raw entries box is hidden');
            const editW=deck.widgets.find(w=>w.name==='✎ Edit entries…');
            check(!!editW && editW.type==='button','An Edit entries button widget sits above the deck');
            entriesW.value='Alpha\nBeta\nGamma\nDelta\nEpsilon'; ui.render();
            const buttons=()=>[...ui.host.querySelectorAll('.ray-deck-button')];
            const lit=()=>buttons().filter(b=>b.getAttribute('aria-checked')==='true').map(b=>b.title);
            check(buttons().length===5 && ui.host.style.getPropertyValue('--deck-cols')==='3','Five entries make five buttons in three columns');
            check(JSON.stringify(lit())==='["Alpha"]','With nothing stored the first button is the lit one');
            buttons()[2].click();
            check(selectedW.value==='Gamma' && JSON.stringify(lit())==='["Gamma"]' && deck.callbacks===1,'Pressing a button stores its text and lights only that button');
            buttons()[2].click();
            check(deck.callbacks===1,'Pressing the lit button again changes nothing');
            buttons()[4].click(); buttons()[1].click();
            check(JSON.stringify(lit())==='["Beta"]' && buttons().filter(b=>b.dataset.state==='on').length===1,'Only one button is ever pressed');
            const pressed=buttons().find(b=>b.dataset.state==='on');
            check([...pressed.querySelectorAll('[data-on-only]')].every(el=>el.style.display!=='none') && [...pressed.querySelectorAll('[data-off-only]')].every(el=>el.style.display==='none'),'The pressed button shows its lit layers');
            const unlit=buttons().find(b=>b.dataset.state==='off');
            check([...unlit.querySelectorAll('[data-on-only]')].every(el=>el.style.display==='none') && [...unlit.querySelectorAll('[data-off-only]')].every(el=>el.style.display!=='none'),'Released buttons hide their lit layers');
            buttons()[1].dispatchEvent(new KeyboardEvent('keydown',{key:'ArrowRight',bubbles:true,cancelable:true}));
            check(selectedW.value==='Gamma' && document.activeElement===buttons()[2],'Arrow keys move the pressed button and focus');
            buttons()[2].dispatchEvent(new KeyboardEvent('keydown',{key:'End',bubbles:true,cancelable:true}));
            check(selectedW.value==='Epsilon','End presses the last button');
            selectedW.value='removed'; ui.render();
            check(JSON.stringify(lit())==='["Alpha"]','A stored value missing from the list falls back to the first button');
            check(ui.element.querySelector('.ray-analog-readout').textContent.includes('Alpha'),'The readout shows the output value');
            deck.inputs=[{name:'selected',link:5}]; deck.onConnectionsChange(); selectedW.value='Beta'; ui.render(); buttons()[3].click();
            check(selectedW.value==='Beta','A wired selected input cannot be changed from the deck');
            deck.inputs=[]; deck.onConnectionsChange();
            for (const key of Object.keys(DECK_STYLES)) {
                deck.properties.style=key; selectedW.value='Beta'; ui.render();
                const style=DECK_STYLES[key];
                check(buttons().length===5 && buttons().every(b=>!!b.querySelector('svg')) && JSON.stringify(lit())==='["Beta"]',`Deck style ${key} draws five buttons with one lit`);
                if (style.legend==='tape') check([...ui.host.querySelectorAll('.ray-deck-sticker')].map(s=>s.textContent).join()==='Alpha,Beta,Gamma,Delta,Epsilon',`Deck style ${key} puts each entry on a Dymo sticker`);
                else check([...buttons()[1].querySelectorAll('[data-label]')].every(t=>t.textContent==='Beta'),`Deck style ${key} cuts each entry into its button`);
            }
            deck.properties.compact=true; ui.applyCompact();
            check(editW.hidden===true,'Compact mode hides the Edit entries button');
            deck.properties.compact=false; ui.applyCompact();
            check(editW.hidden===false && entriesW.hidden===true,'Expanding restores the button and keeps the raw entries box hidden');
            ui.openEditor(); await new Promise(r=>setTimeout(r,30));
            const dialog=document.querySelector('.ray-deck-editor'), area=dialog.querySelector('textarea');
            check(area.value===entriesW.value,'The popout starts with the current entries');
            area.value='One\nTwo\n\nTwo\nThree\nFour'; area.dispatchEvent(new Event('input'));
            check(/4 buttons · 2 × 2 grid · 1 repeated or extra line ignored/.test(dialog.querySelector('.ray-deck-editor-info').textContent),'The popout previews the button count and grid');
            [...dialog.querySelectorAll('button')].find(b=>b.textContent==='Apply').click();
            await new Promise(r=>setTimeout(r,30));
            check(entriesW.value==='One\nTwo\nThree\nFour' && buttons().length===4 && !document.querySelector('.ray-deck-editor'),'Applying stores normalized entries, rebuilds the deck and closes');
            ui.openEditor(); await new Promise(r=>setTimeout(r,30));
            const second=document.querySelector('.ray-deck-editor textarea'); second.value='Discarded'; second.dispatchEvent(new Event('input'));
            [...document.querySelectorAll('.ray-deck-editor button')].find(b=>b.textContent==='Cancel').click();
            await new Promise(r=>setTimeout(r,30));
            check(entriesW.value==='One\nTwo\nThree\nFour' && !document.querySelector('.ray-deck-editor'),'Cancel leaves the entries alone');
            ui.openEditor(); await new Promise(r=>setTimeout(r,30));
            const third=document.querySelector('.ray-deck-editor textarea'); third.value='  \n '; third.dispatchEvent(new Event('input'));
            check([...document.querySelectorAll('.ray-deck-editor button')].find(b=>b.textContent==='Apply').disabled,'An empty list cannot be applied');
            document.querySelector('.ray-deck-editor').close();
            const items=[]; deck.getExtraMenuOptions({},items);
            check(items.some(o=>o.content==='Edit entries…') && items.some(o=>/^Deck Style…$/.test(o.content)),'Right-click offers Edit entries… and Deck Style…');
            deck.onRemoved(); ui.element.remove();
        }
        const octx=new OfflineAudioContext(1,22050,44100), bank=createBank(octx,octx.destination);
        for (const [key,style] of Object.entries(DECK_STYLES)) {
            check(bank.voices.decks.includes(style.sound),`Deck style ${key} has a sound`);
            const o=new OfflineAudioContext(1,22050,44100), b=createBank(o,o.destination); b.deck(style.sound,true,0);
            const peak=(await o.startRendering()).getChannelData(0).reduce((m,x)=>Math.max(m,Math.abs(x)),0);
            check(peak>0.05 && peak<1,`Deck sound ${style.sound} is audible and does not clip`);
        }
        for (const [key,style] of Object.entries(DECK_STYLES)) {
            const deck=make('deck'); deck.properties.style=key; const ui=deck._rayAnalog;
            widget(deck,'entries').value='Mic 1\nMic 2\nLine In\nPhono\nAux Return Long Name'; widget(deck,'selected').value='Line In'; ui.render();
            const card=document.createElement('section');card.className='card';card.style.gridColumn='span 2';
            const heading=document.createElement('header');heading.textContent=style.label;
            card.append(heading,ui.element);document.querySelector('#gallery').append(card);
        }
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
        // Every knob face sweeps min..max over 270 degrees, from 7:30 to 4:30.
        const node=make('knob'), ui=node._rayAnalog; document.body.append(ui.element);
        const value=widget(node,'knob_value');
        const angleAt=(style,v)=>{ node.properties.style=style; value.value=v; ui.render();
            return Number(/rotate\(([-\d.]+)\)/.exec(ui.host.querySelector('[data-rotate]')?.getAttribute('transform')||'')?.[1]); };
        for (const [key,style] of Object.entries(KNOB_STYLES)) {
            if (style.kind==='slider') continue;
            check(angleAt(key,-100)===-135 && angleAt(key,100)===135,`Knob ${key} sweeps 270 degrees from min to max`);
        }
        widget(node,'min_value').value=0; widget(node,'max_value').value=1;
        check(angleAt('console_rotary',.5)===0,'A 0..1 range centres the dial at 0.5');
        node.properties.style='dark_studio_led'; value.value=1; ui.render();
        const arc=ui.host.querySelector('[data-arc]');
        check(arc.getAttribute('stroke-dasharray')==='75.00 100' && arc.getAttribute('transform')==='rotate(135)','LED ring arc starts at 7:30 and covers the 270 degree sweep');
        node.onRemoved(); ui.element.remove();
    }
    {
        // Folder Captioner: the clip_name dropdown became a CLIP socket.
        const widgets=()=>['qwen3vl_8b_fp8.safetensors','C:/imgs',false,0,-1,'Describe',1024,.25,40,.9,.05,1.05,7,'randomize',false];
        const graph={nodes:[
            {id:2,type:'CLIPLoader',outputs:[{name:'CLIP',links:[4,9]}]},
            {id:3,type:'RayVLMFolder',inputs:[{name:'clip_name',widget:{name:'clip_name'},link:4},{name:'folder',widget:{name:'folder'},link:null},{name:'user_prompt',widget:{name:'user_prompt'},link:9}],widgets_values:widgets()},
            {id:5,type:'RayVLMFolder',inputs:[{name:'clip_name',widget:{name:'clip_name'},link:null},{name:'folder',widget:{name:'folder'},link:null}],widgets_values:widgets()},
            {id:6,type:'RayVLMFolder',inputs:[],widgets_values:['C:/other',false]}],
            links:[[4,2,0,3,0,'COMBO'],[9,2,0,3,2,'STRING']]};
        migrateClipInput(graph);
        const [linked,plain,untouched]=graph.nodes.slice(1);
        check(plain.widgets_values.length===14 && plain.widgets_values[0]==='C:/imgs' && plain.widgets_values[12]==='randomize','Captioner migration drops the saved model name and keeps every other value in place');
        check(plain.inputs[0].name==='clip' && plain.inputs[0].type==='CLIP' && plain.inputs[0].link===null && plain.inputs.length===2 && plain.inputs[1].name==='folder','The old dropdown slot becomes the CLIP socket in the same position');
        check(linked.inputs[0].name==='clip' && linked.inputs[0].link===null && graph.links.length===1 && graph.links[0][0]===9 && graph.links[0][4]===2,'A link into the old dropdown is dropped and other links keep their slots');
        check(JSON.stringify(graph.nodes[0].outputs[0].links)==='[9]','The dropped link is removed from its source output');
        check(JSON.stringify(untouched.widgets_values)==='["C:/other",false]','Workflows already using the CLIP socket are left alone');
        const again=JSON.stringify(graph); migrateClipInput(graph);
        check(again===JSON.stringify(graph),'Captioner migration is idempotent');
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
    // ---- one style list for every control -----------------------------------------------------------
    {
        const ids = Object.keys(THEMES);
        const lists = { Control: KNOB_STYLES, Switch: SWITCH_STYLES, 'Button Deck': DECK_STYLES, 'Fader Bank': FADER_STYLES };
        check(ids.length === 31 && new Set(ids.map(id => THEMES[id].label)).size === 31, 'There are 31 distinct styles');
        check(ids.every(id => FAMILIES.includes(familyOf(THEMES[id].label))), 'Every style belongs to a family');
        for (const [name, list] of Object.entries(lists)) {
            check(Object.keys(list).length === 31 && ids.every(id => Object.hasOwn(list, id)), `${name} offers all 31 styles`);
            check(ids.every(id => list[id].label === THEMES[id].label && list[id].panel === THEMES[id].panel), `${name} uses the shared names and panels`);
        }
        check(ids.every(id => Object.hasOwn(MATERIALS, THEMES[id].body) && Object.hasOwn(MATERIALS, THEMES[id].trim) && Object.hasOwn(VOICE_CLASSES, THEMES[id].voice)),
            'Every style names real materials and a real sound class');

        // The hand-drawn faces are untouched; only the missing ones are generated.
        check(Object.entries(KNOBS).every(([id, face]) => KNOB_STYLES[id] === face) && Object.entries(SLIDERS).every(([id, face]) => KNOB_STYLES[id] === face),
            'The hand-drawn knob and slider faces are used as drawn');
        check(Object.entries(SWITCHES).every(([id, face]) => SWITCH_STYLES[id] === face), 'The hand-drawn switch faces are used as drawn');
        check(Object.keys(GENERATED_KNOBS).length === 14 && Object.keys(GENERATED_SLIDERS).length === 3 && Object.keys(GENERATED_SWITCHES).length === 22,
            'The Control gains 17 generated faces and the Switch 22');
        check(['console_black', 'studio_silver', 'vintage_cream'].every(id => FADER_STYLES[id].label.includes(' · ')), 'The fader looks have family names');

        for (const [id, face] of Object.entries(GENERATED_KNOBS))
            check(/data-rotate/.test(face.svg) && /data-arc/.test(face.svg) && !face.kind, `Generated knob ${id} turns and lights its ring`);
        for (const [id, face] of Object.entries(GENERATED_SLIDERS))
            check(/data-slide/.test(face.svg) && /data-fill/.test(face.svg) && face.kind === 'slider', `Generated slider ${id} slides and fills`);
        for (const [id, face] of Object.entries(GENERATED_SWITCHES))
            check(/data-toggle/.test(face.svg) && /data-on-only/.test(face.svg) && /data-off-only/.test(face.svg), `Generated switch ${id} toggles and lights`);
        for (const [id, face] of Object.entries(DECK_STYLES)) {
            const cutout = face.legend === 'cutout';
            check(/data-toggle/.test(face.svg) && /data-on-only/.test(face.svg) && (cutout ? Array.isArray(face.box) && /data-label/.test(face.svg) : !face.box),
                `Deck button ${id} has its hooks (${face.legend})`);
        }

        // Every style makes a sound on every control.
        const audio = new OfflineAudioContext(1, 4410, 44100), voices = createBank(audio, audio.destination).voices;
        check(ids.every(id => voices.ticks.includes(knobVoice(id, false)) && voices.ticks.includes(knobVoice(id, true))), 'Every style has a knob and slider tick voice');
        check(ids.every(id => voices.presses.includes(switchVoice(id))), 'Every style has a switch press voice');
        check(Object.entries(DECK_STYLES).every(([id, face]) => voices.decks.includes(face.sound)), 'Every style has a deck press voice');
        check(ids.every(id => ['fader', 'plastic', 'pan'].includes(knobVoice(id, true)) || THEMES[id].native === 'slider'), 'A style worn by a slider takes a scraping voice');

        // And every style renders on every control.
        const knob = make('knob'), face = knob._rayAnalog; document.body.append(face.element);
        for (const id of ids) {
            knob.properties.style = id; face.render();
            const svg = face.host.querySelector('svg');
            check(!!svg && (KNOB_STYLES[id].kind === 'slider' ? !!svg.querySelector('[data-slide]') : !!svg.querySelector('[data-rotate]')) && face.element.dataset.panel === THEMES[id].panel,
                `Control renders ${id}`);
        }
        knob.onRemoved(); face.element.remove();
        const toggle = make('switch'), sw = toggle._rayAnalog; document.body.append(sw.element);
        for (const id of ids) {
            toggle.properties.style = id; sw.render();
            check(!!sw.host.querySelector('svg [data-toggle]') && sw.element.dataset.panel === THEMES[id].panel, `Switch renders ${id}`);
        }
        toggle.onRemoved(); sw.element.remove();
        const deck = make('deck'), buttons = deck._rayAnalog; document.body.append(buttons.element);
        for (const id of ids) {
            deck.properties.style = id; buttons.render();
            check(buttons.element.querySelectorAll('.ray-deck-button svg [data-toggle]').length === 3 && buttons.element.dataset.panel === THEMES[id].panel, `Button Deck renders ${id}`);
        }
        deck.onRemoved(); buttons.element.remove();
        const bank = make('fader'), faders = bank._rayAnalog; document.body.append(faders.element);
        for (const id of ids) {
            bank.properties.style = id; faders.render();
            check(faders.element.dataset.style === id && faders.element.dataset.panel === THEMES[id].panel, `Fader Bank renders ${id}`);
        }
        bank.onRemoved(); faders.element.remove();
    }
    // ---- mouse wheel ------------------------------------------------------------------------------
    {
        const spin = (el, deltaY, init = {}) => {
            const event = new WheelEvent('wheel', { deltaY, bubbles: true, cancelable: true, ...init });
            el.dispatchEvent(event);
            return event;
        };
        const idle = () => new Promise(resolve => setTimeout(resolve, 450));
        check(!isWheelOn(), 'Mouse wheel control starts off');
        check(wheelUnits({ deltaY: -100, deltaX: 0, deltaMode: 0 }) === 1 && wheelUnits({ deltaY: 3, deltaX: 0, deltaMode: 1 }) < -0.9
            && wheelUnits({ deltaY: 0, deltaX: 100, deltaMode: 0 }) === -1, 'Wheel deltas become notches: up is positive, lines and horizontal deltas count');

        const knob = make('knob'), face = knob._rayAnalog;
        document.body.append(face.element);
        const value = widget(knob, 'knob_value');
        let event = spin(face.element, -100);
        check(!event.defaultPrevented && value.value === 0, 'Scrolling does nothing to the control while the preference is off');

        setWheelOn(true);
        check(isWheelOn() && localStorage.getItem('ray.analog.wheel.v1') === '1', 'The wheel preference persists in the browser');
        event = spin(face.element, -100);
        check(event.defaultPrevented && Math.abs(value.value - 4) < 1e-9, 'A notch up moves a knob 2% of its range and blocks the canvas zoom');
        spin(face.element, 100);
        check(Math.abs(value.value) < 1e-9, 'A notch down moves it back');
        spin(face.element, -100, { shiftKey: true });
        check(Math.abs(value.value - .4) < 1e-9, 'Shift makes wheel steps ten times finer');
        spin(face.element, -100, { ctrlKey: true });
        check(Math.abs(value.value - .4) < 1e-9 && !spin(face.element, -100, { metaKey: true }).defaultPrevented, 'Ctrl / Cmd + wheel is left to the canvas zoom');
        for (let i = 0; i < 80; i++) spin(face.element, -100);
        check(value.value === 100, 'The wheel stops at the maximum');
        for (let i = 0; i < 120; i++) spin(face.element, 100);
        check(value.value === -100, 'and at the minimum');
        widget(knob, 'min_value').value = 0; widget(knob, 'max_value').value = 1; value.value = 0;
        for (let i = 0; i < 5; i++) spin(face.element, -100);
        check(Math.abs(value.value - .1) < 1e-12, 'Steps follow the range, so 0 to 1 is controllable and carries no float noise');
        await idle();
        check(knob.graph.before === knob.graph.after, 'A burst of wheel steps is one balanced undo step');
        spin(face.element, -100); spin(face.element, -100);
        await idle();
        check(knob.graph.before === knob.graph.after && knob.graph.before > 0, 'Bursts after a pause are balanced as well');
        knob.inputs = [{ name: 'knob_value', link: 4 }]; knob.onConnectionsChange();
        const before = value.value;
        event = spin(face.element, -100);
        check(!event.defaultPrevented && value.value === before, 'A linked control ignores the wheel and lets the canvas zoom');
        knob.inputs = []; knob.onConnectionsChange();
        knob.onRemoved(); face.element.remove();

        const toggle = make('switch'), ui = toggle._rayAnalog;
        document.body.append(ui.element);
        const state = widget(toggle, 'state');
        event = spin(ui.element, 100);
        check(event.defaultPrevented && state.value === false, 'Wheel down leaves an off switch off');
        spin(ui.element, -100);
        check(state.value === true, 'Wheel up switches on');
        spin(ui.element, -100);
        check(state.value === true, 'Another notch up leaves it on');
        spin(ui.element, 100);
        check(state.value === false, 'Wheel down switches off');
        ui.element.remove(); toggle.onRemoved();

        const deck = make('deck'), buttons = deck._rayAnalog;
        document.body.append(buttons.element);
        widget(deck, 'entries').value = 'A\nB\nC'; widget(deck, 'selected').value = 'A'; buttons.render();
        const selected = widget(deck, 'selected');
        spin(buttons.element, 100);
        check(selected.value === 'B', 'Wheel down presses the next button');
        spin(buttons.element, 100); spin(buttons.element, 100);
        event = spin(buttons.element, 100);
        check(selected.value === 'C' && event.defaultPrevented, 'The deck stops at the last button and still keeps the wheel');
        spin(buttons.element, -100);
        check(selected.value === 'B', 'Wheel up presses the previous button');
        widget(deck, 'selected').value = 'gone'; buttons.render();
        spin(buttons.element, 100);
        check(selected.value === 'B', 'From a missing stored value the deck steps from the first button');
        buttons.element.remove(); deck.onRemoved();

        const elsewhere = document.createElement('div'); document.body.append(elsewhere);
        check(!spin(elsewhere, -100).defaultPrevented, 'Scrolling anywhere else is untouched');
        elsewhere.remove();
        setWheelOn(false);
        check(!isWheelOn() && localStorage.getItem('ray.analog.wheel.v1') === '0', 'The preference turns off again');
    }
    // ---- fader bank -------------------------------------------------------------------------------
    {
        check(clampCount(0) === 2 && clampCount(99) === 10 && clampCount('x') === 4 && clampCount(5.9) === 5, 'Fader count clamps to 2..10');
        check(clampLevel(-1) === 0 && clampLevel(3) === 1 && clampLevel(NaN) === .5 && clampLevel('.25') === .25, 'Fader levels clamp to 0..1');
        const bank = make('fader'), ui = bank._rayAnalog;
        document.body.append(ui.element);
        const strips = () => [...ui.element.querySelectorAll('.ray-fader-strip')];
        const level = i => widget(bank, `fader_${i}`).value;
        const names = () => bank.outputs.map(o => o.name).join(',');
        check(strips().length === 4 && names() === 'values,fader_1,fader_2,fader_3,fader_4', 'A new bank has four faders and only their outputs');
        check(bank.size[0] >= 28 + 4 * 38, 'The node is wide enough for its faders');
        check(widget(bank, 'fader_1').hidden && widget(bank, 'fader_10').hidden && !widget(bank, 'faders').hidden, 'The raw fader widgets are hidden and the count stays editable');
        check(strips().every(el => el.getAttribute('role') === 'slider' && el.getAttribute('aria-valuenow') === '0.5'), 'Each fader is a slider at the middle');

        widget(bank, 'faders').value = 7; widget(bank, 'faders').callback();
        check(strips().length === 7 && names() === 'values,fader_1,fader_2,fader_3,fader_4,fader_5,fader_6,fader_7', 'Raising the count adds faders and their outputs');
        check(bank.size[0] >= 28 + 7 * 38, 'and widens the node to fit');
        widget(bank, 'faders').value = 2; widget(bank, 'faders').callback();
        check(strips().length === 2 && names() === 'values,fader_1,fader_2', 'Lowering the count removes the extra faders and outputs');
        widget(bank, 'faders').value = 10; widget(bank, 'faders').callback();
        check(strips().length === 10 && bank.outputs.length === 11, 'Ten faders show every output');
        widget(bank, 'faders').value = 99; widget(bank, 'faders').callback();
        check(strips().length === 10, 'A count above ten is held at ten');
        widget(bank, 'faders').value = 3; widget(bank, 'faders').callback();
        check(strips().length === 3 && bank.outputs.length === 4, 'Back down to three');

        const first = strips()[0];
        first.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowUp', bubbles: true, cancelable: true }));
        check(Math.abs(level(1) - .51) < 1e-9 && first.getAttribute('aria-valuenow') === '0.51', 'ArrowUp raises a fader by 0.01');
        first.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown', shiftKey: true, bubbles: true, cancelable: true }));
        check(Math.abs(level(1) - .509) < 1e-9, 'Shift makes keyboard steps ten times finer');
        first.dispatchEvent(new KeyboardEvent('keydown', { key: 'End', bubbles: true, cancelable: true }));
        check(level(1) === 1, 'End sends a fader to 1');
        first.dispatchEvent(new KeyboardEvent('keydown', { key: 'Home', bubbles: true, cancelable: true }));
        check(level(1) === 0 && level(2) === .5, 'Home sends it to 0 and leaves the others alone');
        first.dispatchEvent(new KeyboardEvent('keydown', { key: 'PageUp', bubbles: true, cancelable: true }));
        check(Math.abs(level(1) - .1) < 1e-9, 'PageUp moves a tenth');
        check(ui.element.querySelector('.ray-analog-readout').textContent === 'F1  0.10', 'The readout shows the last fader touched');

        // Drag, with pointer capture stubbed because the events are synthetic.
        const capture = Element.prototype.setPointerCapture, release = Element.prototype.releasePointerCapture;
        Element.prototype.setPointerCapture = () => {}; Element.prototype.releasePointerCapture = () => {};
        const second = strips()[1], track = second.querySelector('.ray-fader-track');
        const rect = track.getBoundingClientRect(), travel = rect.height - 18;
        const at = fraction => rect.bottom - 9 - fraction * travel;
        const pointer = (el, type, y, init = {}) => el.dispatchEvent(new PointerEvent(type, { pointerId: 7, button: 0, clientX: rect.left + 5, clientY: y, bubbles: true, cancelable: true, isPrimary: true, ...init }));
        check(rect.height > 80 && travel > 50, 'The fader track has room to travel');
        pointer(second, 'pointerdown', at(.8));
        check(Math.abs(level(2) - .8) < .01, 'Clicking the track jumps the cap to the pointer');
        pointer(second, 'pointermove', at(.8) - travel * .1);
        check(Math.abs(level(2) - .9) < .01, 'Dragging up raises the fader by the distance moved');
        pointer(second, 'pointermove', at(.8) - travel * .1 + travel * .1, { shiftKey: true });
        check(Math.abs(level(2) - .895) < .01, 'Shift slows the drag twenty times');
        pointer(second, 'pointermove', at(2));
        check(level(2) === 1, 'Dragging past the top stops at 1');
        pointer(second, 'pointerup', at(2));
        pointer(second, 'pointermove', at(0));
        check(level(2) === 1, 'Moving after release changes nothing');
        check(bank.graph.before === bank.graph.after && bank.graph.before > 0, 'A drag is one balanced undo step');
        pointer(second, 'pointerdown', at(.5));
        const cap = second.querySelector('.ray-fader-cap').getBoundingClientRect();
        pointer(second, 'pointerup', at(.5));
        pointer(second, 'pointerdown', cap.top + cap.height / 2);
        check(Math.abs(level(2) - .5) < .01, 'Grabbing the cap itself does not make it jump');
        pointer(second, 'pointerup', at(.5));
        Element.prototype.setPointerCapture = capture; Element.prototype.releasePointerCapture = release;

        bank.inputs = [{ name: 'fader_3', link: 8 }]; bank.onConnectionsChange();
        const third = strips()[2], held = level(3);
        third.dispatchEvent(new KeyboardEvent('keydown', { key: 'End', bubbles: true, cancelable: true }));
        check(level(3) === held && third.getAttribute('aria-disabled') === 'true' && /EXTERNAL/.test(ui.element.querySelector('.ray-analog-hint').textContent), 'A linked fader ignores local edits and says so');
        bank.inputs = []; bank.onConnectionsChange();

        // Mouse wheel works on the fader under the pointer only.
        const spin = (el, deltaY, init = {}) => { const e = new WheelEvent('wheel', { deltaY, bubbles: true, cancelable: true, ...init }); el.dispatchEvent(e); return e; };
        const idle = () => new Promise(resolve => setTimeout(resolve, 450));
        const before = [level(1), level(2), level(3)];
        check(!spin(strips()[0], -100).defaultPrevented && level(1) === before[0], 'The wheel does nothing to a fader while the preference is off');
        setWheelOn(true);
        const event = spin(strips()[0].querySelector('.ray-fader-track'), -100);
        check(event.defaultPrevented && Math.abs(level(1) - (before[0] + .02)) < 1e-9 && level(2) === before[1], 'A notch up raises only the fader under the pointer by 2%');
        spin(strips()[1], 100, { shiftKey: true });
        check(Math.abs(level(2) - (before[1] - .002)) < 1e-9, 'Shift makes the wheel ten times finer');
        check(!spin(ui.element.querySelector('.ray-analog-readout'), -100).defaultPrevented, 'The wheel over the readout is left to the canvas');
        for (let i = 0; i < 80; i++) spin(strips()[0], -100);
        check(level(1) === 1, 'The wheel stops at 1');
        await idle();
        check(bank.graph.before === bank.graph.after, 'Wheel bursts are balanced undo steps');
        setWheelOn(false);

        const labels = Object.values(FADER_STYLES);
        check(labels.length === 31 && labels.every(style => style.label && style.panel && style.capTop && style.capBottom), 'The fader bank has all 31 styles');
        for (const key of Object.keys(FADER_STYLES)) {
            bank.properties.style = key; ui.render();
            check(ui.element.dataset.style === key && ui.element.dataset.panel === FADER_STYLES[key].panel, `Fader style ${key} applies`);
        }
        bank.properties.style = 'nonsense'; ui.render();
        check(ui.element.dataset.style === 'console_black', 'An unknown style falls back to the default');

        const plain = make('fader', false, false);
        check(plain._rayAnalog === undefined && plain.outputs.length === 11, 'Without DOM widgets the native widgets and every output stay');
        bank.onRemoved(); ui.element.remove();
    }
    document.querySelector('#results').textContent=`${passes} checks passed\n`+messages.join('\n');
    document.querySelector('summary').textContent=`Regression results — ${passes} checks passed`;
} catch(error) {
    document.querySelector('#results').textContent=messages.join('\n')+'\nFAIL '+error.stack;
    document.querySelector('details').open=true;
    document.querySelector('summary').textContent='Regression failed';
}
