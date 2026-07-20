import { app } from "../../scripts/app.js";
import { injectStylesOnce, renderMarkdown } from "./chat_styles.js";
import { applyBucketTint } from "./_common.js";

const NODE_NAME = "RayOllamaChat";

function getWidget(node, name) {
    return node.widgets?.find((w) => w.name === name);
}

// Vue Nodes 2.0 detection — multiple heuristics, any one is enough
function isVueNodes() {
    try {
        if (typeof window === "undefined") return false;
        // ComfyUI exposes Vue stores via window.comfyAPI in Nodes 2.0 builds
        if (window.comfyAPI?.domWidget?.isDOMWidget) return true;
        const settings = app?.ui?.settings;
        // Common setting keys across builds — kept loose since they shift between releases
        const candidates = [
            "Comfy.Node.UseVueNodes",
            "Comfy.UseVueNodes",
            "Comfy.VueNodes",
            "Comfy.Node.Renderer",
            "Comfy.NewNodes",
        ];
        for (const k of candidates) {
            const v = settings?.getSettingValue?.(k);
            if (v === true || v === "vue" || v === "v2") return true;
        }
    } catch {}
    return false;
}

function hideWidget(node, name) {
    const w = getWidget(node, name);
    if (!w) return;
    if (w._origType === undefined) w._origType = w.type;
    if (w._origComputeSize === undefined) w._origComputeSize = w.computeSize;
    if (w._origAdvanced === undefined) w._origAdvanced = w.advanced;
    // Legacy litegraph
    w.type = "hidden";
    w.computeSize = () => [0, -4];
    // Vue Nodes 2.0 + legacy shared
    w.hidden = true;
    w.visible = false;
    w.advanced = true;
    if (w.element) w.element.style.display = "none";
    // Vue may track an options bag
    if (w.options) w.options.hidden = true;
}

function showWidget(node, name) {
    const w = getWidget(node, name);
    if (!w) return;
    if (w._origType !== undefined) w.type = w._origType;
    if (w._origComputeSize !== undefined) {
        w.computeSize = w._origComputeSize;
    } else {
        delete w.computeSize;
    }
    if (w._origAdvanced !== undefined) {
        w.advanced = w._origAdvanced;
    } else {
        delete w.advanced;
    }
    w.hidden = false;
    w.visible = true;
    if (w.element) w.element.style.display = "";
    if (w.options) delete w.options.hidden;
}

// Widgets exclusive to ollama mode
const OLLAMA_ONLY_WIDGETS = ["server_url", "model", "keep_alive", "think"];
// Widgets exclusive to clip mode
const CLIP_ONLY_WIDGETS = ["max_new_tokens", "top_p", "repetition_penalty"];
// Input slot names exclusive to ollama mode
const OLLAMA_ONLY_INPUTS = ["image", "audio"];
// Input slot names exclusive to clip mode
const CLIP_ONLY_INPUTS = ["clip"];

function setInputVisible(node, inputName, visible) {
    if (!node.inputs) return;
    const idx = node.inputs.findIndex((i) => i.name === inputName);
    if (idx < 0) return;
    const inp = node.inputs[idx];
    inp._rayHidden = !visible;
    if (visible) {
        delete inp.hidden;
        delete inp._invisible;
    } else {
        inp.hidden = true;
        inp._invisible = true;
        // Disconnect any link if hiding
        if (inp.link != null) {
            try { node.graph?.removeLink(inp.link); } catch {}
        }
    }
    // Trigger Vue reactivity / litegraph redraw
    try { node.graph?.change?.(); } catch {}
}

function applyModeUI(node, mode, attachBtn, attachAudioBtn) {
    if (mode === "ollama") {
        for (const name of OLLAMA_ONLY_WIDGETS) showWidget(node, name);
        for (const name of CLIP_ONLY_WIDGETS) hideWidget(node, name);
        for (const name of OLLAMA_ONLY_INPUTS) setInputVisible(node, name, true);
        for (const name of CLIP_ONLY_INPUTS) setInputVisible(node, name, false);
        if (attachBtn) attachBtn.style.display = "";
        if (attachAudioBtn) attachAudioBtn.style.display = "";
    } else {
        // clip mode
        for (const name of OLLAMA_ONLY_WIDGETS) hideWidget(node, name);
        for (const name of CLIP_ONLY_WIDGETS) showWidget(node, name);
        for (const name of OLLAMA_ONLY_INPUTS) setInputVisible(node, name, false);
        for (const name of CLIP_ONLY_INPUTS) setInputVisible(node, name, true);
        if (attachBtn) attachBtn.style.display = "none";
        if (attachAudioBtn) attachAudioBtn.style.display = "none";
    }
    node.setDirtyCanvas?.(true, true);
}

function readUrl(node)   { return getWidget(node, "server_url")?.value || "http://localhost:11434"; }
function readModel(node) { return getWidget(node, "model")?.value || ""; }
function readKeepAlive(node) { return getWidget(node, "keep_alive")?.value || "5m"; }
function readTemperature(node) { return Number(getWidget(node, "temperature")?.value ?? 0.7); }
function readSeed(node) { return Number(getWidget(node, "seed")?.value ?? -1); }

function blobToBase64(blob) {
    return new Promise((res, rej) => {
        const fr = new FileReader();
        fr.onload = () => {
            const url = fr.result;
            const comma = String(url).indexOf(",");
            res(comma >= 0 ? String(url).slice(comma + 1) : String(url));
        };
        fr.onerror = rej;
        fr.readAsDataURL(blob);
    });
}

async function grabAudioFromUpstream(node) {
    const idx = node.inputs?.findIndex((i) => i.name === "audio");
    if (idx == null || idx < 0) return null;
    const link = node.inputs[idx].link;
    if (link == null) return null;
    const linkObj = node.graph?.links?.[link];
    if (!linkObj) return null;
    const src = node.graph.getNodeById(linkObj.origin_id);
    if (!src) return null;

    // LoadAudio / similar with `audio` widget holding a filename
    const audioWidget = src.widgets?.find((w) => w.name === "audio" || w.name === "audio_file");
    if (audioWidget && typeof audioWidget.value === "string" && audioWidget.value) {
        const val = audioWidget.value;
        let filename = val;
        let subfolder = "";
        let type = "input";
        const slash = val.lastIndexOf("/");
        if (slash >= 0) {
            subfolder = val.slice(0, slash);
            filename = val.slice(slash + 1);
        }
        const m = filename.match(/^\[(output|input|temp)\]\s+(.+)$/);
        if (m) { type = m[1]; filename = m[2]; }
        try {
            const params = new URLSearchParams({ filename, type, subfolder });
            const resp = await fetch(`/view?${params}`);
            if (!resp.ok) return null;
            const blob = await resp.blob();
            return await blobToBase64(blob);
        } catch (e) {
            console.warn("[RayOllamaChat] audio /view fetch failed:", e);
            return null;
        }
    }
    return null;
}

async function grabImageFromUpstream(node) {
    const idx = node.inputs?.findIndex((i) => i.name === "image");
    if (idx == null || idx < 0) return null;
    const link = node.inputs[idx].link;
    if (link == null) return null;
    const linkObj = node.graph?.links?.[link];
    if (!linkObj) return null;
    const src = node.graph.getNodeById(linkObj.origin_id);
    if (!src) return null;

    // LoadImage / similar nodes with `image` widget holding a filename
    const imgWidget = src.widgets?.find((w) => w.name === "image");
    if (imgWidget && typeof imgWidget.value === "string" && imgWidget.value) {
        const val = imgWidget.value;
        let filename = val;
        let subfolder = "";
        let type = "input";
        // some nodes prefix with subfolder/filename
        const slash = val.lastIndexOf("/");
        if (slash >= 0) {
            subfolder = val.slice(0, slash);
            filename = val.slice(slash + 1);
        }
        // pattern "[output] name" / "[input] name"
        const m = filename.match(/^\[(output|input|temp)\]\s+(.+)$/);
        if (m) { type = m[1]; filename = m[2]; }
        try {
            const params = new URLSearchParams({ filename, type, subfolder });
            const resp = await fetch(`/view?${params}`);
            if (!resp.ok) return null;
            const blob = await resp.blob();
            return await blobToBase64(blob);
        } catch (e) {
            console.warn("[RayOllamaChat] /view fetch failed:", e);
            return null;
        }
    }

    // Source has an imgs preview (LoadImage post-render also exposes node.imgs)
    if (Array.isArray(src.imgs) && src.imgs.length) {
        try {
            const im = src.imgs[0];
            const c = document.createElement("canvas");
            c.width = im.naturalWidth || im.width;
            c.height = im.naturalHeight || im.height;
            c.getContext("2d").drawImage(im, 0, 0);
            const dataUrl = c.toDataURL("image/png");
            const comma = dataUrl.indexOf(",");
            return comma >= 0 ? dataUrl.slice(comma + 1) : dataUrl;
        } catch (e) {
            console.warn("[RayOllamaChat] canvas snapshot failed:", e);
        }
    }
    return null;
}

function readSystemPromptInput(node) {
    const idx = node.inputs?.findIndex((i) => i.name === "system_prompt");
    if (idx == null || idx < 0) return "";
    const link = node.inputs[idx].link;
    if (link == null) return "";
    const linkObj = node.graph?.links?.[link];
    if (!linkObj) return "";
    const src = node.graph.getNodeById(linkObj.origin_id);
    const out = src?.widgets_values || src?.widgets;
    const w = src?.widgets?.find?.((w) => typeof w.value === "string");
    return w?.value || "";
}

function loadHistory(node) {
    try {
        const w = getWidget(node, "chat_history");
        if (!w?.value) return [];
        const arr = JSON.parse(w.value);
        return Array.isArray(arr) ? arr : [];
    } catch {
        return [];
    }
}

function saveHistory(node, arr) {
    const w = getWidget(node, "chat_history");
    if (w) w.value = JSON.stringify(arr);
}

function setLastMessage(node, text) {
    const w = getWidget(node, "last_message");
    if (w) w.value = text;
}

function buildChatUI(node) {
    injectStylesOnce();

    hideWidget(node, "chat_history");
    hideWidget(node, "last_message");
    hideWidget(node, "pending_user_prompt");
    hideWidget(node, "attach_image");
    hideWidget(node, "attach_audio");

    const wrap = document.createElement("div");
    wrap.className = "ray-chat-wrap";

    // toolbar
    const toolbar = document.createElement("div");
    toolbar.className = "rc-toolbar";

    const modelBox = document.createElement("div");
    modelBox.className = "rc-modelbox";
    modelBox.title = "Ollama model";
    const modelNameEl = document.createElement("span");
    modelNameEl.className = "rc-modelname";
    modelNameEl.textContent = "(no model)";
    const modelTagsEl = document.createElement("span");
    modelTagsEl.className = "rc-modeltags";
    const modelArrow = document.createElement("span");
    modelArrow.className = "rc-modelarrow";
    modelArrow.textContent = "▾";
    const modelMenu = document.createElement("div");
    modelMenu.className = "rc-modelmenu";
    modelBox.append(modelNameEl, modelTagsEl, modelArrow, modelMenu);

    const attachBtn = document.createElement("button");
    attachBtn.className = "rc-attach";
    attachBtn.textContent = "📎";
    attachBtn.title = "Attach connected image to next message";

    const attachAudioBtn = document.createElement("button");
    attachAudioBtn.className = "rc-attach rc-attach-audio";
    attachAudioBtn.textContent = "🎤";
    attachAudioBtn.title = "Attach connected audio to next message (run workflow once if upstream isn't a LoadAudio)";

    const clearBtn = document.createElement("button");
    clearBtn.className = "rc-clear";
    clearBtn.textContent = "🗑";
    clearBtn.title = "New chat (clears history)";

    const stopBtn = document.createElement("button");
    stopBtn.className = "rc-stop";
    stopBtn.textContent = "⏹";
    stopBtn.title = "Stop streaming";
    stopBtn.hidden = true;

    // Execution mode toggle: "send" = chat sends immediately, "run" = waits for ComfyUI queue
    const execModeBtn = document.createElement("button");
    execModeBtn.className = "rc-execmode";
    execModeBtn.title = "Execution mode: click to toggle between Send and Run mode";

    const status = document.createElement("span");
    status.className = "rc-status";
    status.textContent = "";

    toolbar.append(modelBox, attachBtn, attachAudioBtn, clearBtn, stopBtn, execModeBtn, status);

    // history pane
    const historyPane = document.createElement("div");
    historyPane.className = "rc-history";

    // composer
    const composer = document.createElement("div");
    composer.className = "rc-composer";
    const input = document.createElement("textarea");
    input.className = "rc-input";
    input.placeholder = "Message…  (Ctrl+Enter to send)";
    input.rows = 2;
    const sendBtn = document.createElement("button");
    sendBtn.className = "rc-send";
    sendBtn.textContent = "▶";
    sendBtn.title = "Send (Ctrl+Enter)";
    composer.append(input, sendBtn);

    wrap.append(toolbar, historyPane, composer);

    // event isolation — keep ComfyUI canvas from grabbing wheel/keys
    wrap.addEventListener("wheel", (e) => e.stopPropagation(), { passive: true });
    wrap.addEventListener("contextmenu", (e) => e.stopPropagation());
    wrap.addEventListener("pointerdown", (e) => e.stopPropagation());
    wrap.addEventListener("mousedown", (e) => e.stopPropagation());
    input.addEventListener("keydown", (e) => {
        e.stopPropagation();
        if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
            e.preventDefault();
            doSend();
        } else if (e.key === "Escape") {
            input.blur();
        }
    });
    input.addEventListener("keyup", (e) => e.stopPropagation());
    input.addEventListener("input", () => {
        if (getExecMode() === "run") syncRunModeWidgets();
    });

    // state
    let armedAttach = false;
    let armedAttachAudio = false;
    let abortController = null;
    let userScrolled = false;

    // Execution mode: "send" = chat sends on Send button, "run" = waits for ComfyUI queue
    // Persisted in a hidden widget value so it survives workflow save/load
    function getExecMode() {
        const w = getWidget(node, "chat_history");
        // stored as a separate key in node's properties to survive serialization
        return node._rayExecMode || "send";
    }
    function setExecMode(mode) {
        node._rayExecMode = mode;
        if (!node.properties) node.properties = {};
        node.properties._rayExecMode = mode;
        if (mode === "run") {
            execModeBtn.textContent = "⚙ run";
            execModeBtn.classList.add("run-mode");
            execModeBtn.title = "Execution mode: ON RUN — chat triggers on ComfyUI queue. Click to switch to Send mode.";
            input.placeholder = "Message… (queued on workflow run)";
        } else {
            execModeBtn.textContent = "▶ send";
            execModeBtn.classList.remove("run-mode");
            execModeBtn.title = "Execution mode: ON SEND — chat sends immediately. Click to switch to Run mode.";
            input.placeholder = "Message…  (Ctrl+Enter to send)";
        }
    }
    execModeBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        setExecMode(getExecMode() === "send" ? "run" : "send");
    });

    // Sticky attach state helpers (used by run mode to persist across workflow runs)
    function getStickyAttach() {
        return node._rayStickyAttach || false;
    }
    function getStickyAttachAudio() {
        return node._rayStickyAttachAudio || false;
    }
    function setStickyAttach(val) {
        node._rayStickyAttach = val;
        if (!node.properties) node.properties = {};
        node.properties._rayStickyAttach = val;
        armedAttach = val;
        attachBtn.classList.toggle("armed", val);
        attachBtn.title = val
            ? "Image WILL be attached to next message — click again to cancel"
            : "Attach connected image to next message";
        const w = getWidget(node, "attach_image");
        if (w) w.value = !!val;
    }
    function setStickyAttachAudio(val) {
        node._rayStickyAttachAudio = val;
        if (!node.properties) node.properties = {};
        node.properties._rayStickyAttachAudio = val;
        armedAttachAudio = val;
        attachAudioBtn.classList.toggle("armed", val);
        attachAudioBtn.title = val
            ? "Audio WILL be attached to next message — click again to cancel"
            : "Attach connected audio to next message";
        const w = getWidget(node, "attach_audio");
        if (w) w.value = !!val;
    }

    historyPane.addEventListener("scroll", () => {
        const atBottom = historyPane.scrollHeight - historyPane.scrollTop - historyPane.clientHeight < 30;
        userScrolled = !atBottom;
    });

    function autoScroll() {
        if (!userScrolled) historyPane.scrollTop = historyPane.scrollHeight;
    }

    function makeBubble(role, content, hasImage = false, hasAudio = false) {
        const div = document.createElement("div");
        div.className = `rc-msg ${role}`;
        div._raw = content || "";

        if (role !== "system") {
            const copyBtn = document.createElement("button");
            copyBtn.className = "rc-copy";
            copyBtn.textContent = "⧉";
            copyBtn.title = "Copy message";
            copyBtn.addEventListener("click", async (e) => {
                e.stopPropagation();
                e.preventDefault();
                const txt = div._raw || "";
                try {
                    if (navigator.clipboard?.writeText) {
                        await navigator.clipboard.writeText(txt);
                    } else {
                        const ta = document.createElement("textarea");
                        ta.value = txt;
                        ta.style.position = "fixed";
                        ta.style.opacity = "0";
                        document.body.appendChild(ta);
                        ta.select();
                        document.execCommand("copy");
                        document.body.removeChild(ta);
                    }
                    copyBtn.textContent = "✓";
                    copyBtn.classList.add("copied");
                    setTimeout(() => {
                        copyBtn.textContent = "⧉";
                        copyBtn.classList.remove("copied");
                    }, 900);
                } catch (err) {
                    console.warn("[RayOllamaChat] clipboard failed:", err);
                    copyBtn.textContent = "✗";
                    setTimeout(() => { copyBtn.textContent = "⧉"; }, 900);
                }
            });
            div.appendChild(copyBtn);
        }

        if (hasImage || hasAudio) {
            const pillRow = document.createElement("div");
            if (hasImage) {
                const p = document.createElement("span");
                p.className = "rc-img-pill";
                p.textContent = "🖼 image";
                pillRow.appendChild(p);
            }
            if (hasAudio) {
                const p = document.createElement("span");
                p.className = "rc-audio-pill";
                p.textContent = "🎤 audio";
                pillRow.appendChild(p);
            }
            div.appendChild(pillRow);
        }

        if (role === "assistant") {
            const thinkWrap = document.createElement("div");
            thinkWrap.className = "rc-thinking-wrap";
            const thinkToggle = document.createElement("span");
            thinkToggle.className = "rc-thinking-toggle";
            thinkToggle.textContent = "🧠 thinking ▸";
            const thinkBody = document.createElement("div");
            thinkBody.className = "rc-thinking-body";
            thinkToggle.addEventListener("click", (e) => {
                e.stopPropagation();
                const open = thinkWrap.classList.toggle("expanded");
                thinkToggle.textContent = open ? "🧠 thinking ▾" : "🧠 thinking ▸";
                div._thinkUserToggled = true;
            });
            thinkWrap.append(thinkToggle, thinkBody);
            div.appendChild(thinkWrap);
            div._thinkWrap = thinkWrap;
            div._thinkBody = thinkBody;
            div._thinkRaw = "";
        }

        const body = document.createElement("span");
        body.className = "rc-body";
        body.innerHTML = role === "assistant" ? renderMarkdown(content || "") : escapeText(content || "");
        div.appendChild(body);
        div._body = body;
        return div;
    }

    function escapeText(s) {
        const d = document.createElement("div");
        d.textContent = s;
        return d.innerHTML;
    }

    function renderHistory() {
        historyPane.innerHTML = "";
        const hist = loadHistory(node);
        if (!hist.length) {
            const empty = document.createElement("div");
            empty.className = "rc-empty";
            empty.textContent = "No messages yet. Type below to start chatting.";
            historyPane.appendChild(empty);
            return;
        }
        for (const m of hist) {
            historyPane.appendChild(makeBubble(
                m.role,
                m.content,
                !!(m.images && m.images.length),
                !!(m.audios && m.audios.length),
            ));
        }
        historyPane.scrollTop = historyPane.scrollHeight;
        userScrolled = false;
    }

    const TAG_DEFS = [
        { id: "vision",   match: (m) => m.capabilities?.includes("vision"),    cls: "rc-tag-vision",   text: "🖼 vision" },
        { id: "audio",    match: (m) => (m.families || []).some((f) => /audio|voxtral|whisper|qwen2[_-]?audio/i.test(f))
                                       || (m.capabilities || []).some((c) => /audio|speech/i.test(c)), cls: "rc-tag-audio", text: "🎵 audio" },
        { id: "tools",    match: (m) => m.capabilities?.includes("tools"),     cls: "rc-tag-tools",    text: "🔧 tools" },
        { id: "thinking", match: (m) => m.capabilities?.includes("thinking"),  cls: "rc-tag-thinking", text: "🧠 think" },
        { id: "embed",    match: (m) => m.capabilities?.includes("embedding"), cls: "rc-tag-embed",    text: "📊 embed" },
    ];

    function makeTagsForModel(m) {
        const out = [];
        if (!m) return out;
        for (const def of TAG_DEFS) {
            if (def.match(m)) {
                const span = document.createElement("span");
                span.className = "rc-tag " + def.cls;
                span.textContent = def.text;
                out.push(span);
            }
        }
        return out;
    }

    let modelData = [];

    function setSelectedModel(name) {
        const w = getWidget(node, "model");
        if (w) w.value = name || "";
        modelNameEl.textContent = name || "(no model)";
        modelTagsEl.innerHTML = "";
        const m = modelData.find((x) => x.name === name);
        for (const t of makeTagsForModel(m)) modelTagsEl.appendChild(t);
        modelMenu.querySelectorAll(".rc-modelitem").forEach((el) => {
            el.classList.toggle("selected", el.dataset.name === name);
        });
    }

    function rebuildModelMenu() {
        modelMenu.innerHTML = "";
        if (!modelData.length) {
            const empty = document.createElement("div");
            empty.className = "rc-modelitem";
            empty.style.color = "#888";
            empty.style.cursor = "default";
            empty.textContent = "(no models)";
            modelMenu.appendChild(empty);
            return;
        }
        for (const m of modelData) {
            const item = document.createElement("div");
            item.className = "rc-modelitem";
            item.dataset.name = m.name;
            const name = document.createElement("span");
            name.className = "rc-modelitemname";
            name.textContent = m.name;
            item.appendChild(name);
            if (m.parameter_size) {
                const ps = document.createElement("span");
                ps.className = "rc-modelparam";
                ps.textContent = m.parameter_size;
                item.appendChild(ps);
            }
            for (const t of makeTagsForModel(m)) item.appendChild(t);
            item.addEventListener("click", (e) => {
                e.stopPropagation();
                setSelectedModel(m.name);
                modelMenu.classList.remove("open");
            });
            modelMenu.appendChild(item);
        }
    }

    modelBox.addEventListener("click", (e) => {
        if (e.target.closest(".rc-modelmenu")) return;
        e.stopPropagation();
        const willOpen = !modelMenu.classList.contains("open");
        document.querySelectorAll(".rc-modelmenu.open").forEach((el) => el.classList.remove("open"));
        if (willOpen) modelMenu.classList.add("open");
    });
    document.addEventListener("click", (e) => {
        if (!modelBox.contains(e.target)) modelMenu.classList.remove("open");
    });

    async function refreshModels() {
        const url = readUrl(node);
        status.textContent = "loading models…";
        try {
            const r = await fetch(`/ray_ollama/models?url=${encodeURIComponent(url)}`);
            const j = await r.json();
            const list = j.models || [];
            modelData = list.map((m) =>
                typeof m === "string"
                    ? { name: m, capabilities: [], families: [], parameter_size: "" }
                    : m
            );
            rebuildModelMenu();
            const cur = readModel(node);
            if (cur && modelData.some((m) => m.name === cur)) {
                setSelectedModel(cur);
            } else if (modelData.length) {
                setSelectedModel(modelData[0].name);
            } else {
                modelNameEl.textContent = j.error ? `(error: ${j.error})` : "(no models)";
                modelTagsEl.innerHTML = "";
            }
            status.textContent = "";
        } catch (e) {
            status.textContent = `models: ${e.message || e}`;
        }
    }

    attachBtn.addEventListener("click", () => {
        const newVal = !armedAttach;
        if (getExecMode() === "run") {
            setStickyAttach(newVal);
        } else {
            armedAttach = newVal;
            attachBtn.classList.toggle("armed", armedAttach);
            attachBtn.title = armedAttach
                ? "Image WILL be attached to next message — click again to cancel"
                : "Attach connected image to next message";
        }
    });

    attachAudioBtn.addEventListener("click", () => {
        const newVal = !armedAttachAudio;
        if (getExecMode() === "run") {
            setStickyAttachAudio(newVal);
        } else {
            armedAttachAudio = newVal;
            attachAudioBtn.classList.toggle("armed", armedAttachAudio);
            attachAudioBtn.title = armedAttachAudio
                ? "Audio WILL be attached to next message — click again to cancel"
                : "Attach connected audio to next message";
        }
    });

    clearBtn.addEventListener("click", () => {
        saveHistory(node, []);
        setLastMessage(node, "");
        renderHistory();
        node.setDirtyCanvas?.(true, true);
    });

    stopBtn.addEventListener("click", async () => {
        try { abortController?.abort(); } catch {}
        try {
            await fetch("/ray_ollama/abort", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ node_id: String(node.id) }),
            });
        } catch {}
    });

    sendBtn.addEventListener("click", () => doSend());

    function syncRunModeWidgets() {
        const text = input.value;
        const pW = getWidget(node, "pending_user_prompt");
        if (pW) pW.value = text || "";
        const aiW = getWidget(node, "attach_image");
        if (aiW) aiW.value = !!getStickyAttach();
        const auW = getWidget(node, "attach_audio");
        if (auW) auW.value = !!getStickyAttachAudio();
    }

    async function doRunModeQueue() {
        const text = input.value.trim();
        if (!text) {
            status.textContent = "type a message first";
            setTimeout(() => { status.textContent = ""; }, 1500);
            return;
        }
        syncRunModeWidgets();

        // Push user msg to history immediately so chat shows it; assistant fills on execute
        const hist = loadHistory(node);
        hist.push({
            role: "user",
            content: text,
            images: getStickyAttach() ? ["__attached__"] : undefined,
            audios: getStickyAttachAudio() ? ["__attached__"] : undefined,
        });
        saveHistory(node, hist);
        const empty = historyPane.querySelector(".rc-empty");
        if (empty) empty.remove();
        historyPane.appendChild(makeBubble("user", text, getStickyAttach(), getStickyAttachAudio()));
        userScrolled = false;
        autoScroll();

        input.value = "";
        status.textContent = "queued — waiting for workflow run…";

        // Trigger ComfyUI queue
        try {
            if (app.queuePrompt) {
                await app.queuePrompt(0);
            } else {
                document.getElementById("queue-button")?.click();
            }
        } catch (e) {
            status.textContent = `queue failed: ${e.message || e}`;
        }
    }

    async function doSend() {
        if (getExecMode() === "run") {
            return doRunModeQueue();
        }
        const text = input.value.trim();
        if (!text) return;
        const model = readModel(node);
        if (!model) {
            status.textContent = "select a model";
            return;
        }

        const hist = loadHistory(node);
        hist.push({
            role: "user",
            content: text,
            images: armedAttach ? ["__attached__"] : undefined,
            audios: armedAttachAudio ? ["__attached__"] : undefined,
        });
        saveHistory(node, hist);

        // remove empty placeholder if first msg
        const empty = historyPane.querySelector(".rc-empty");
        if (empty) empty.remove();

        historyPane.appendChild(makeBubble("user", text, armedAttach, armedAttachAudio));
        const asstBubble = makeBubble("assistant", "");
        asstBubble.classList.add("streaming");
        const asstBody = asstBubble.querySelector(".rc-body");
        historyPane.appendChild(asstBubble);
        userScrolled = false;
        autoScroll();

        input.value = "";
        sendBtn.disabled = true;
        stopBtn.hidden = false;
        status.textContent = "streaming…";

        // build messages from history (skip the bookkeeping image marker; backend pulls real image)
        const sysPrompt = readSystemPromptInput(node);
        const messages = [];
        if (sysPrompt) messages.push({ role: "system", content: sysPrompt });
        for (const m of hist) {
            const obj = { role: m.role, content: m.content };
            messages.push(obj);
        }

        const options = { temperature: readTemperature(node) };
        const seed = readSeed(node);
        if (seed >= 0) options.seed = seed;

        const wasAttaching = armedAttach;
        const wasAttachingAudio = armedAttachAudio;
        // In send mode: reset arm state after send. In run mode: sticky (handled elsewhere).
        armedAttach = false;
        armedAttachAudio = false;
        attachBtn.classList.remove("armed");
        attachAudioBtn.classList.remove("armed");
        attachBtn.title = "Attach connected image to next message";
        attachAudioBtn.title = "Attach connected audio to next message";

        let attachedB64 = null;
        if (wasAttaching) {
            attachedB64 = await grabImageFromUpstream(node);
            if (!attachedB64) {
                status.textContent = "no upstream image — using cached (run queue once if blank)";
            }
        }
        let attachedAudioB64 = null;
        if (wasAttachingAudio) {
            attachedAudioB64 = await grabAudioFromUpstream(node);
            if (!attachedAudioB64) {
                status.textContent = "no upstream audio — using cached (run queue once if blank)";
            }
        }

        const thinkOn = !!getWidget(node, "think")?.value;

        let acc = "";
        abortController = new AbortController();

        try {
            const resp = await fetch("/ray_ollama/chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    server_url: readUrl(node),
                    model,
                    messages,
                    options,
                    keep_alive: readKeepAlive(node),
                    node_id: String(node.id),
                    attach_image_node_id: wasAttaching ? String(node.id) : null,
                    attached_image_b64: attachedB64,
                    attach_audio_node_id: wasAttachingAudio ? String(node.id) : null,
                    attached_audio_b64: attachedAudioB64,
                    think: thinkOn,
                }),
                signal: abortController.signal,
            });

            if (!resp.ok || !resp.body) {
                const errText = await resp.text().catch(() => "");
                throw new Error(`HTTP ${resp.status}: ${errText}`);
            }

            const reader = resp.body.getReader();
            const decoder = new TextDecoder();
            let buf = "";
            while (true) {
                const { value, done } = await reader.read();
                if (done) break;
                buf += decoder.decode(value, { stream: true });
                let idx;
                while ((idx = buf.indexOf("\n\n")) !== -1) {
                    const evt = buf.slice(0, idx).trim();
                    buf = buf.slice(idx + 2);
                    if (!evt.startsWith("data:")) continue;
                    const payload = evt.slice(5).trim();
                    if (!payload) continue;
                    let obj;
                    try { obj = JSON.parse(payload); } catch { continue; }
                    if (obj.error) {
                        acc += `\n[error: ${obj.error}]`;
                        asstBody.innerHTML = renderMarkdown(acc);
                        asstBubble._raw = acc;
                    } else if (obj.aborted) {
                        acc += "\n[aborted]";
                        asstBody.innerHTML = renderMarkdown(acc);
                        asstBubble._raw = acc;
                    } else if (obj.think) {
                        if (asstBubble._thinkWrap) {
                            asstBubble._thinkRaw = (asstBubble._thinkRaw || "") + obj.think;
                            asstBubble._thinkBody.textContent = asstBubble._thinkRaw;
                            asstBubble._thinkWrap.classList.add("has-think");
                            if (!asstBubble._thinkAutoExpanded) {
                                asstBubble._thinkWrap.classList.add("expanded");
                                asstBubble._thinkAutoExpanded = true;
                                const tog = asstBubble._thinkWrap.querySelector(".rc-thinking-toggle");
                                if (tog) tog.textContent = "🧠 thinking ▾";
                            }
                            autoScroll();
                        }
                    } else if (obj.chunk) {
                        acc += obj.chunk;
                        asstBody.innerHTML = renderMarkdown(acc);
                        asstBubble._raw = acc;
                        // collapse thinking once real content arrives
                        if (asstBubble._thinkWrap?.classList.contains("expanded") && !asstBubble._thinkUserToggled) {
                            asstBubble._thinkWrap.classList.remove("expanded");
                            const tog = asstBubble._thinkWrap.querySelector(".rc-thinking-toggle");
                            if (tog) tog.textContent = "🧠 thinking ▸";
                        }
                        autoScroll();
                    } else if (obj.done) {
                        if (obj.message?.content && !acc) {
                            acc = obj.message.content;
                            asstBubble._raw = acc;
                        }
                    }
                }
            }
        } catch (e) {
            if (e.name !== "AbortError") {
                acc += `\n[fetch error: ${e.message || e}]`;
                asstBody.innerHTML = renderMarkdown(acc);
            } else {
                acc += "\n[stopped]";
                asstBody.innerHTML = renderMarkdown(acc);
            }
            asstBubble._raw = acc;
        } finally {
            asstBubble.classList.remove("streaming");
            sendBtn.disabled = false;
            stopBtn.hidden = true;
            status.textContent = "";
            abortController = null;

            // persist
            const finalHist = loadHistory(node);
            const last = { role: "assistant", content: acc };
            finalHist.push(last);
            saveHistory(node, finalHist);
            setLastMessage(node, acc);
            node.setDirtyCanvas?.(true, true);
            autoScroll();
        }
    }

    // wire DOM widget — Vue Nodes 2.0 honors min height via getHeight/getMinHeight + element sizing
    if (typeof node.addDOMWidget === "function") {
        wrap.style.minHeight = "320px";
        const domWidget = node.addDOMWidget("chat_ui", "RAY_CHAT", wrap, {
            serialize: false,
            hideOnZoom: false,
            getMinHeight: () => 320,
            getHeight: () => 320,
        });
        // Vue Nodes 2.0 sometimes wraps the widget; ensure visible flags are set
        if (domWidget) {
            domWidget.computeSize = domWidget.computeSize || (() => [400, 320]);
        }
    }

    // initial render — defer slightly so widgets are settled
    setTimeout(() => {
        renderHistory();
        // Apply mode UI based on current inference_mode widget value
        const modeW = getWidget(node, "inference_mode");
        const initialMode = modeW?.value || "ollama";
        applyModeUI(node, initialMode, attachBtn, attachAudioBtn);
        if (initialMode === "ollama") refreshModels();
        // Restore exec mode and sticky attach state
        setExecMode(node._rayExecMode || "send");
        if (node._rayStickyAttach) setStickyAttach(true);
        if (node._rayStickyAttachAudio) setStickyAttachAudio(true);
    }, 50);

    // refresh models if URL changes
    const urlW = getWidget(node, "server_url");
    if (urlW) {
        const orig = urlW.callback;
        urlW.callback = function (v) {
            const r = orig?.apply(this, arguments);
            refreshModels();
            return r;
        };
    }

    // Wire inference_mode toggle
    const modeW = getWidget(node, "inference_mode");
    if (modeW) {
        const origCallback = modeW.callback;
        modeW.callback = function (v) {
            const r = origCallback?.apply(this, arguments);
            applyModeUI(node, v, attachBtn, attachAudioBtn);
            if (v === "ollama") refreshModels();
            return r;
        };
    }

    node._rayChatRender = renderHistory;
    node._rayApplyModeUI = () => {
        const w = getWidget(node, "inference_mode");
        applyModeUI(node, w?.value || "ollama", attachBtn, attachAudioBtn);
    };

    node._rayOnExecuted = (uiData) => {
        try {
            const asst = (uiData?.ray_chat_assistant?.[0]) ?? "";
            if (!asst) return;
            const finalHist = loadHistory(node);
            finalHist.push({ role: "assistant", content: asst });
            saveHistory(node, finalHist);
            setLastMessage(node, asst);
            // Clear pending so next interactive run doesn't re-send
            const pW = getWidget(node, "pending_user_prompt");
            if (pW) pW.value = "";
            renderHistory();
            status.textContent = "";
        } catch (e) {
            console.warn("[RayOllamaChat] onExecuted handler error:", e);
        }
    };
}

app.registerExtension({
    name: "Ray.OllamaChat",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== NODE_NAME) return;
        const orig = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const r = orig?.apply(this, arguments);
            try { buildChatUI(this); applyBucketTint(this, "LLM"); }
            catch (e) { console.error("[RayOllamaChat] buildChatUI error:", e); }
            this.size = [400, 480];
            return r;
        };

        const onConfigure = nodeType.prototype.onConfigure;
        nodeType.prototype.onConfigure = function (info) {
            const r = onConfigure?.apply(this, arguments);
            // litegraph merges info.properties → this.properties before onConfigure fires
            const props = this.properties || {};
            if (props._rayExecMode) this._rayExecMode = props._rayExecMode;
            if (props._rayStickyAttach != null) this._rayStickyAttach = props._rayStickyAttach;
            if (props._rayStickyAttachAudio != null) this._rayStickyAttachAudio = props._rayStickyAttachAudio;
            // re-render history and re-apply mode UI after workflow load
            setTimeout(() => {
                this._rayChatRender?.();
                this._rayApplyModeUI?.();
            }, 50);
            return r;
        };

        const onExecuted = nodeType.prototype.onExecuted;
        nodeType.prototype.onExecuted = function (message) {
            const r = onExecuted?.apply(this, arguments);
            try { this._rayOnExecuted?.(message); }
            catch (e) { console.warn("[RayOllamaChat] onExecuted dispatch error:", e); }
            return r;
        };
    },
});
