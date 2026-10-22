export function styles() {
    if(document.getElementById("ray-folders-style"))return;
    const style=document.createElement("style");style.id="ray-folders-style";
    style.textContent=`
.dom-widget:has(> .ray-folders){pointer-events:none!important}
.ray-folders{box-sizing:border-box;position:relative;width:100%;min-width:0;min-height:0;height:100%;contain:size layout;display:flex;flex-direction:column;gap:6px;padding:6px;color:#eee;font:12px system-ui;color-scheme:dark;overflow:hidden;pointer-events:none;border-radius:8px}
.rf-controls{display:flex;flex-direction:column;gap:6px;min-width:0;min-height:100px;padding-right:92px;flex-shrink:0}
.lg-node:has(.ray-folders) [data-testid^="node-body-"]{position:relative}
.lg-node:has(.ray-folders) [data-testid^="node-body-"]>:has(>div>.lg-slot--output){position:absolute;top:4px;left:0;right:0;z-index:2;pointer-events:none}
.lg-node:has(.ray-folders) .lg-slot{pointer-events:auto}
.ray-folders *,.rf-settings *{box-sizing:border-box}
.ray-folders button,.ray-folders input,.rf-backdrop button,.rf-backdrop select,.rf-backdrop input{font:inherit;color:inherit;color-scheme:dark}
.ray-folders button,.rf-backdrop button{background:#171717;border:1px solid #383838;border-radius:5px;cursor:pointer;pointer-events:auto}
.ray-folders button:hover,.rf-backdrop button:hover{background:#353535}
.ray-folders :focus-visible,.rf-backdrop :focus-visible{outline:2px solid #b9a4fa;outline-offset:1px}
.rf-row{display:flex;align-items:center;gap:6px;min-width:0;flex-shrink:0}
.rf-row label{font-size:11px;color:#a3a3a3;flex:0 0 42px}
.rf-row input{flex:1;min-width:0;width:100%;height:28px;padding:4px 9px;background:#141414;border:1px solid #3a3a3a;border-radius:5px;pointer-events:auto}
.rf-row input:disabled{opacity:.6}
.ray-folders .rf-icon{flex:0 0 30px;width:30px;height:28px;padding:5px;display:grid;place-items:center}
.rf-icon svg{width:16px;height:16px;fill:none;stroke:currentColor;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round}
.rf-status{min-height:15px;color:#999;font-size:11px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;flex-shrink:0}
.rf-spinner,.rf-status.rf-busy::before{display:inline-block;flex:0 0 auto;width:19px;height:19px;border:2px solid #ffffff26;border-top-color:#b9a4fa;border-radius:50%;animation:rf-spin .8s linear infinite}
.rf-status.rf-busy::before{content:"";width:10px;height:10px;margin-right:6px;vertical-align:-1px}
@keyframes rf-spin{to{transform:rotate(360deg)}}
@media(prefers-reduced-motion:reduce){.rf-spinner,.rf-status.rf-busy::before{animation:none}}
.rf-loading{position:absolute;inset:0;z-index:2;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:10px;background:#000d;color:#aaa;pointer-events:none}
.rf-loading[hidden]{display:none}
.ray-folders .rf-more{position:absolute;bottom:26px;left:50%;transform:translateX(-50%);z-index:3;padding:4px 14px;font-size:11px}
.rf-more[hidden]{display:none}
.rf-placeholder{position:absolute;inset:0 0 24px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:8px;padding:8px;background:#141414;color:#999;text-align:center;font-size:10px}
.rf-tile:disabled{opacity:1;cursor:progress}
.rf-tile[data-state=error]{cursor:default}
.rf-tile[data-state=error] .rf-spinner,.rf-tile[data-waiting=true] .rf-spinner,.rf-tile[data-state=ready] .rf-placeholder{display:none}
.rf-tile:not([data-state=ready]) img{visibility:hidden}
.rf-total{color:#777;font-size:10px;line-height:16px;text-align:right;flex-shrink:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.rf-viewport{position:relative;flex:1;min-width:0;min-height:100px;overflow-x:hidden;overflow-y:auto;scrollbar-gutter:stable;overscroll-behavior:contain;pointer-events:auto;scrollbar-width:thin}
.rf-grid{position:relative;width:100%}
.ray-folders .rf-tile{position:absolute;padding:0;border:1px solid #292929;overflow:hidden;text-align:left;border-radius:5px;background:#111;touch-action:pan-y}
.ray-folders .rf-tile[aria-pressed=true]{border:2px solid #b9a4fa;background:#26212d}
.rf-tile img{width:100%;aspect-ratio:1;object-fit:cover;display:block;background:#141414;pointer-events:none}
.rf-tile[data-kind=audio] img{object-fit:contain}
.rf-name{height:24px;padding:3px 5px;display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-size:10px}
.rf-kind{position:absolute;right:4px;top:4px;padding:2px 4px;background:#000b;border-radius:3px;color:#ddd;font-size:9px}
.rf-selected{position:absolute;left:4px;top:4px;padding:1px 4px;border-radius:8px;background:#b9a4fa;color:#111;font-size:10px}
.rf-backdrop{position:fixed;inset:0;z-index:100000;background:#0009;display:grid;place-items:center;color:#eee;font:12px system-ui}
.rf-prompt-picker{display:grid;grid-template-columns:repeat(var(--rf-prompt-columns),minmax(0,1fr));grid-template-rows:repeat(var(--rf-prompt-columns),minmax(0,1fr));gap:18px;width:min(90vw,86vh);height:min(90vw,86vh);pointer-events:none}
.rf-prompt-picker .rf-prompt-card{box-sizing:border-box;display:flex;flex-direction:column;align-items:stretch;justify-content:flex-start;min-width:0;min-height:0;padding:16px;border:1px solid #333;border-radius:4px;background:#000;color:#eee;text-align:left;white-space:pre-wrap;overflow-wrap:anywhere;overflow:auto;overscroll-behavior:contain;font:13px/1.5 system-ui;pointer-events:auto}
.rf-prompt-card>span{display:block;flex:0 0 auto;min-width:0}
.rf-prompt-picker .rf-prompt-card:hover{background:#000;border-color:#999}
.rf-prompt-picker .rf-prompt-card:focus-visible{outline:2px solid #b9a4fa;outline-offset:3px}
.rf-settings{box-sizing:border-box;width:min(430px,92vw);max-height:85vh;overflow:auto;background:#101010;border:1px solid #444;border-radius:10px;padding:18px;box-shadow:0 12px 50px #0009;color-scheme:dark}
.rf-settings h3{font-size:15px;margin:0 0 16px}.rf-settings p{color:#999;font-size:11px;line-height:1.5}
.rf-setting{display:flex;align-items:center;justify-content:space-between;gap:12px;margin:11px 0;min-height:24px}.rf-setting>span{flex:0 0 145px;color:#bbb}
.rf-setting select{max-width:190px;padding:4px;background:#181818;border:1px solid #444;border-radius:4px}
.rf-checks{display:flex;align-items:center;gap:8px;flex-wrap:wrap}.rf-checks label{display:flex;align-items:center;gap:3px}.rf-checks input[type=range]{width:125px}.rf-checks output{min-width:28px}
.rf-swatches{display:flex;flex-wrap:wrap;gap:5px}.rf-swatches button{width:20px;height:20px;padding:0;border-radius:50%;border:2px solid transparent}.rf-swatches button[aria-pressed=true]{border-color:#fff;box-shadow:0 0 0 1px #b9a4fa}
.rf-actions{display:flex;justify-content:flex-end;gap:8px;margin-top:16px}.rf-actions button{padding:6px 16px}
.rf-tooltip{position:fixed;z-index:100002;max-width:min(440px,80vw);max-height:45vh;overflow:hidden;pointer-events:none;white-space:pre-wrap;background:#111f;color:#ddd;border:1px solid #555;border-radius:6px;padding:9px 11px;box-shadow:0 4px 20px #0009;font:11px/1.5 system-ui}
.rf-viewer{width:75vw;height:75vh;display:flex;align-items:center;justify-content:center;background:#050505;border:1px solid #444;border-radius:8px;overflow:hidden}.rf-viewer img,.rf-viewer video{max-width:100%;max-height:100%;object-fit:contain}.rf-viewer audio{width:80%}
.rf-menu{position:fixed;z-index:100003;min-width:190px;padding:4px;background:#171717;color:#eee;border:1px solid #555;border-radius:6px;box-shadow:0 8px 24px #0009;font:12px system-ui}.rf-menu button{display:block;width:100%;padding:8px 12px;text-align:left;border:0;background:transparent;color:inherit;cursor:pointer}.rf-menu button:hover{background:#333}.rf-menu button:disabled{opacity:.4;cursor:default}
`;
    document.head.append(style);
}
