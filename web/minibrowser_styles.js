const STYLE_ID = "ray-minibrowser-styles";

const MB_CSS = `
.ray-mb-wrap {
    display: flex;
    flex-direction: column;
    width: 100%;
    height: 100%;
    min-height: 320px;
    background: #1e1f22;
    border-radius: 6px;
    overflow: hidden;
    color: #d8d8da;
    font: 12px/1.4 -apple-system, "Segoe UI", Roboto, sans-serif;
}
.rmb-toolbar {
    display: flex;
    flex-direction: row;
    gap: 4px;
    align-items: center;
    padding: 4px 6px;
    background: #2a2b2f;
    border-bottom: 1px solid #111;
    flex: 0 0 auto;
}
.rmb-toolbar button {
    appearance: none;
    background: #3a3b40;
    color: #d8d8da;
    border: 1px solid #1c1c1f;
    border-radius: 4px;
    width: 26px;
    height: 24px;
    padding: 0;
    font-size: 13px;
    cursor: pointer;
    transition: background 80ms;
}
.rmb-toolbar button:hover:not(:disabled) {
    background: #4a4b50;
}
.rmb-toolbar button:disabled {
    opacity: 0.4;
    cursor: default;
}
.rmb-toolbar button.armed {
    background: #c8443c;
    border-color: #7a1f1a;
    color: #fff;
}
.rmb-url {
    flex: 1 1 auto;
    min-width: 80px;
    height: 24px;
    background: #15161a;
    color: #e2e2e6;
    border: 1px solid #1c1c1f;
    border-radius: 4px;
    padding: 0 8px;
    font: 12px/1 ui-monospace, "Consolas", "Cascadia Code", monospace;
    outline: none;
}
.rmb-url:focus {
    border-color: #4ea0ff;
}
.rmb-status {
    color: #888;
    font-size: 11px;
    padding: 0 4px;
    white-space: nowrap;
    max-width: 140px;
    overflow: hidden;
    text-overflow: ellipsis;
}
.rmb-status.ok { color: #6ad26a; }
.rmb-status.err { color: #e35b5b; }
.rmb-frame {
    flex: 1 1 auto;
    width: 100%;
    height: 100%;
    border: 0;
    background: #fff;
    display: block;
}
`;

export function injectStylesOnce() {
    if (document.getElementById(STYLE_ID)) return;
    const tag = document.createElement("style");
    tag.id = STYLE_ID;
    tag.textContent = MB_CSS;
    document.head.appendChild(tag);
}
