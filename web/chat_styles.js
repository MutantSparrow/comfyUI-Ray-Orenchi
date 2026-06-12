export const STYLE_ID = "ray-ollama-chat-styles";

export const CHAT_CSS = `
.ray-chat-wrap {
    width: 100%;
    height: 100%;
    display: flex;
    flex-direction: column;
    box-sizing: border-box;
    background: #1e1f22;
    color: #e6e6e6;
    border-radius: 6px;
    overflow: hidden;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    font-size: 12px;
}
.rc-toolbar {
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 4px 6px;
    background: #2a2b2f;
    border-bottom: 1px solid #3a3b3f;
    flex: 0 0 auto;
}
.rc-toolbar .rc-model {
    flex: 1 1 auto;
    min-width: 60px;
    background: #1a1b1d;
    color: #e6e6e6;
    border: 1px solid #444;
    border-radius: 3px;
    padding: 3px 4px;
    font-size: 11px;
    cursor: pointer;
}
.rc-modelbox {
    flex: 1 1 auto;
    min-width: 80px;
    position: relative;
    background: #1a1b1d;
    color: #e6e6e6;
    border: 1px solid #444;
    border-radius: 3px;
    padding: 3px 6px;
    font-size: 11px;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 4px;
    user-select: none;
    overflow: visible;
}
.rc-modelbox:hover { border-color: #4488ff; }
.rc-modelbox .rc-modelname {
    flex: 1 1 auto;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    min-width: 0;
}
.rc-modelbox .rc-modeltags {
    flex: 0 0 auto;
    display: flex;
    gap: 3px;
    align-items: center;
}
.rc-modelbox .rc-modelarrow {
    flex: 0 0 auto;
    opacity: 0.6;
    margin-left: 2px;
    font-size: 10px;
}
.rc-modelmenu {
    position: absolute;
    top: 100%;
    left: 0;
    right: 0;
    max-height: 280px;
    overflow-y: auto;
    overflow-x: hidden;
    background: #2a2b2f;
    border: 1px solid #555;
    border-radius: 3px;
    z-index: 9999;
    margin-top: 2px;
    display: none;
    box-shadow: 0 4px 12px rgba(0,0,0,0.5);
    scrollbar-width: thin;
    scrollbar-color: #555 #2a2b2f;
}
.rc-modelmenu.open { display: block; }
.rc-modelmenu::-webkit-scrollbar { width: 8px; }
.rc-modelmenu::-webkit-scrollbar-thumb { background: #555; border-radius: 4px; }
.rc-modelitem {
    padding: 5px 8px;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 4px;
    font-size: 11px;
    border-bottom: 1px solid #333;
    color: #e6e6e6;
}
.rc-modelitem:last-child { border-bottom: none; }
.rc-modelitem:hover { background: #3a3b3f; }
.rc-modelitem.selected { background: rgba(45, 108, 223, 0.25); }
.rc-modelitem .rc-modelitemname {
    flex: 1 1 auto;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    min-width: 0;
}
.rc-modelitem .rc-modelparam {
    flex: 0 0 auto;
    color: #888;
    font-size: 10px;
    margin-right: 4px;
}
.rc-tag {
    display: inline-block;
    padding: 1px 5px;
    border-radius: 3px;
    font-size: 9px;
    font-weight: 600;
    line-height: 1.4;
    white-space: nowrap;
    flex: 0 0 auto;
}
.rc-tag-vision   { background: #2d6cdf; color: #fff; }
.rc-tag-tools    { background: #d97a2c; color: #fff; }
.rc-tag-thinking { background: #8e4ec6; color: #fff; }
.rc-tag-embed    { background: #555;    color: #ccc; }
.rc-tag-audio    { background: #d63384; color: #fff; }
.rc-tag-chat     { background: #2a9d4a; color: #fff; }
.rc-toolbar button {
    background: #3a3b3f;
    color: #e6e6e6;
    border: 1px solid #4a4b4f;
    border-radius: 3px;
    padding: 3px 7px;
    font-size: 12px;
    cursor: pointer;
    line-height: 1;
    flex: 0 0 auto;
}
.rc-toolbar button:hover { background: #4a4b4f; }
.rc-toolbar button:active { transform: translateY(1px); }
.rc-toolbar button.rc-attach.armed {
    background: #2d6cdf;
    border-color: #4488ff;
    box-shadow: 0 0 0 1px #4488ff inset;
}
.rc-toolbar button.rc-attach-audio.armed {
    background: #d63384;
    border-color: #f06aaa;
    box-shadow: 0 0 0 1px #f06aaa inset;
}
.rc-toolbar .rc-stop {
    background: #b34040;
    border-color: #d04040;
}
.rc-toolbar .rc-stop:hover { background: #d04040; }
.rc-toolbar .rc-execmode {
    font-size: 10px;
    padding: 3px 6px;
    background: #2a2b2f;
    border-color: #555;
    color: #aaa;
    white-space: nowrap;
}
.rc-toolbar .rc-execmode:hover { background: #3a3b3f; color: #e6e6e6; }
.rc-toolbar .rc-execmode.run-mode {
    background: #2a4a2a;
    border-color: #4a8a4a;
    color: #8ade8a;
}
.rc-toolbar .rc-execmode.run-mode:hover { background: #3a5a3a; }
.rc-toolbar .rc-status {
    font-size: 10px;
    color: #888;
    margin-left: auto;
    padding-left: 4px;
    white-space: nowrap;
}
.rc-history {
    flex: 1 1 auto;
    overflow-y: auto;
    overflow-x: hidden;
    padding: 8px;
    display: flex;
    flex-direction: column;
    gap: 6px;
    background: #1e1f22;
    scrollbar-width: thin;
    scrollbar-color: #555 #1e1f22;
}
.rc-history::-webkit-scrollbar { width: 8px; }
.rc-history::-webkit-scrollbar-track { background: #1e1f22; }
.rc-history::-webkit-scrollbar-thumb { background: #555; border-radius: 4px; }
.rc-history::-webkit-scrollbar-thumb:hover { background: #777; }
.rc-msg {
    position: relative;
    max-width: 92%;
    padding: 6px 9px;
    border-radius: 8px;
    word-wrap: break-word;
    overflow-wrap: anywhere;
    line-height: 1.4;
    white-space: pre-wrap;
    font-size: 12px;
}
.rc-copy {
    position: absolute;
    top: 3px;
    right: 3px;
    background: rgba(0, 0, 0, 0.45);
    color: #fff;
    border: none;
    border-radius: 3px;
    padding: 1px 5px;
    font-size: 10px;
    line-height: 1.2;
    cursor: pointer;
    opacity: 0;
    transition: opacity 0.12s, background 0.12s;
}
.rc-msg:hover > .rc-copy { opacity: 0.85; }
.rc-copy:hover { opacity: 1 !important; background: rgba(0, 0, 0, 0.75); }
.rc-copy.copied {
    background: #2a9d4a !important;
    opacity: 1 !important;
}
.rc-msg.user .rc-copy { background: rgba(255, 255, 255, 0.18); }
.rc-msg.user .rc-copy:hover { background: rgba(255, 255, 255, 0.32); }
.rc-msg.user {
    align-self: flex-end;
    background: #2d6cdf;
    color: #fff;
    border-bottom-right-radius: 2px;
}
.rc-msg.assistant {
    align-self: flex-start;
    background: #2f3034;
    color: #e6e6e6;
    border-bottom-left-radius: 2px;
}
.rc-msg.system {
    align-self: center;
    background: transparent;
    color: #888;
    font-style: italic;
    font-size: 10px;
    padding: 2px 6px;
}
.rc-msg .rc-img-pill {
    display: inline-block;
    background: rgba(0,0,0,0.3);
    padding: 1px 6px;
    border-radius: 8px;
    font-size: 10px;
    margin-bottom: 4px;
    opacity: 0.85;
}
.rc-msg .rc-audio-pill {
    display: inline-block;
    background: rgba(214, 51, 132, 0.45);
    padding: 1px 6px;
    border-radius: 8px;
    font-size: 10px;
    margin-bottom: 4px;
    margin-left: 4px;
    opacity: 0.9;
}
.rc-thinking-wrap {
    display: none;
    margin-bottom: 4px;
}
.rc-thinking-wrap.has-think { display: block; }
.rc-thinking-toggle {
    color: #b08adf;
    font-weight: 600;
    font-size: 9px;
    cursor: pointer;
    user-select: none;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
.rc-thinking-toggle:hover { color: #d6b6ff; }
.rc-thinking-body {
    font-size: 10px;
    color: #999;
    font-style: italic;
    border-left: 2px solid #8e4ec6;
    padding: 2px 0 2px 6px;
    margin-top: 2px;
    max-height: 100px;
    overflow-y: auto;
    white-space: pre-wrap;
    display: none;
}
.rc-thinking-wrap.expanded .rc-thinking-body { display: block; }
.rc-msg pre {
    background: #14151a;
    border: 1px solid #333;
    border-radius: 4px;
    padding: 6px 8px;
    margin: 4px 0;
    overflow-x: auto;
    font-family: ui-monospace, "Cascadia Code", Menlo, Consolas, monospace;
    font-size: 11px;
    white-space: pre;
}
.rc-msg code {
    font-family: ui-monospace, "Cascadia Code", Menlo, Consolas, monospace;
    font-size: 11px;
    background: #14151a;
    padding: 1px 4px;
    border-radius: 3px;
}
.rc-msg pre code { background: transparent; padding: 0; }
.rc-msg.streaming::after {
    content: "▍";
    animation: rc-blink 1s steps(2) infinite;
    margin-left: 1px;
    opacity: 0.7;
}
@keyframes rc-blink { 50% { opacity: 0; } }
.rc-composer {
    flex: 0 0 auto;
    display: flex;
    gap: 4px;
    padding: 6px;
    background: #2a2b2f;
    border-top: 1px solid #3a3b3f;
    align-items: flex-end;
}
.rc-input {
    flex: 1 1 auto;
    background: #1a1b1d;
    color: #e6e6e6;
    border: 1px solid #444;
    border-radius: 4px;
    padding: 5px 7px;
    font-size: 12px;
    font-family: inherit;
    resize: none;
    outline: none;
    min-height: 22px;
    max-height: 160px;
    line-height: 1.4;
}
.rc-input:focus { border-color: #4488ff; }
.rc-send {
    background: #2d6cdf;
    color: #fff;
    border: 1px solid #4488ff;
    border-radius: 4px;
    padding: 5px 12px;
    font-size: 14px;
    cursor: pointer;
    flex: 0 0 auto;
}
.rc-send:hover { background: #4488ff; }
.rc-send:disabled { background: #444; border-color: #555; color: #888; cursor: not-allowed; }
.rc-empty {
    color: #666;
    text-align: center;
    padding: 20px 8px;
    font-style: italic;
    font-size: 11px;
}
`;

export function injectStylesOnce() {
    if (document.getElementById(STYLE_ID)) return;
    const tag = document.createElement("style");
    tag.id = STYLE_ID;
    tag.textContent = CHAT_CSS;
    document.head.appendChild(tag);
}

function escapeHtml(s) {
    return String(s)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
}

export function renderMarkdown(text) {
    if (text == null) return "";
    let s = escapeHtml(text);
    // fenced code blocks ```lang\n...\n```
    s = s.replace(/```([a-zA-Z0-9_+-]*)\n([\s\S]*?)```/g, (_, lang, body) => {
        return `<pre><code>${body.replace(/\n$/, "")}</code></pre>`;
    });
    // unclosed fenced block at end (during streaming) — render rest as code
    const lastFence = s.lastIndexOf("```");
    if (lastFence !== -1 && (s.match(/```/g) || []).length % 2 === 1) {
        const before = s.slice(0, lastFence);
        const after = s.slice(lastFence + 3).replace(/^[a-zA-Z0-9_+-]*\n?/, "");
        s = before + `<pre><code>${after}</code></pre>`;
    }
    // inline code `...`
    s = s.replace(/`([^`\n]+)`/g, (_, c) => `<code>${c}</code>`);
    // bold **...**
    s = s.replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>");
    // line breaks (but not inside <pre>)
    const parts = s.split(/(<pre>[\s\S]*?<\/pre>)/);
    for (let i = 0; i < parts.length; i++) {
        if (!parts[i].startsWith("<pre>")) {
            parts[i] = parts[i].replace(/\n/g, "<br>");
        }
    }
    return parts.join("");
}
