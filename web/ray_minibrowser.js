import { app } from "../../scripts/app.js";
import { injectStylesOnce } from "./minibrowser_styles.js";

const NODE_NAME = "RayMiniBrowser";
const HOME_URL = "https://example.com";

function getWidget(node, name) {
    return node.widgets?.find((w) => w.name === name);
}

function hideWidget(node, name) {
    const w = getWidget(node, name);
    if (!w) return;
    if (w._origType === undefined) w._origType = w.type;
    if (w._origComputeSize === undefined) w._origComputeSize = w.computeSize;
    if (w._origAdvanced === undefined) w._origAdvanced = w.advanced;
    w.type = "hidden";
    w.computeSize = () => [0, -4];
    w.hidden = true;
    w.visible = false;
    w.advanced = true;
    if (w.element) w.element.style.display = "none";
    if (w.options) w.options.hidden = true;
}

function safeNodeId(node) {
    const id = node.id;
    if (id == null || id === -1) return `tmp_${Date.now()}`;
    return String(id);
}

// Strip the proxy wrapper off any URL the bridge posts up. The HTML rewriter
// rewrote every <a href> to `/ray_minibrowser/proxy?url=<original>`, so when
// the iframe reports navigation/selection, location.href and anchor.href both
// resolve to the proxied form. Surface the underlying original URL instead.
function unproxy(u) {
    if (!u) return u;
    try {
        const parsed = new URL(u, window.location.origin);
        if (parsed.pathname === "/ray_minibrowser/proxy") {
            const inner = parsed.searchParams.get("url");
            if (inner) return inner;
        }
    } catch {}
    return u;
}

function buildBrowserUI(node) {
    injectStylesOnce();

    hideWidget(node, "pending_text");
    hideWidget(node, "pending_images_json");

    const wrap = document.createElement("div");
    wrap.className = "ray-mb-wrap";

    const toolbar = document.createElement("div");
    toolbar.className = "rmb-toolbar";

    const backBtn   = mkBtn("◀", "Back");
    const fwdBtn    = mkBtn("▶", "Forward");
    const reloadBtn = mkBtn("↻", "Reload");
    const homeBtn   = mkBtn("⌂", "Home");

    const urlBar = document.createElement("input");
    urlBar.className = "rmb-url";
    urlBar.type = "text";
    urlBar.spellcheck = false;
    urlBar.placeholder = "https://...";

    const goBtn     = mkBtn("→", "Go");
    const pickerBtn = mkBtn("🎯", "Toggle DOM picker");

    const status = document.createElement("span");
    status.className = "rmb-status";

    toolbar.append(backBtn, fwdBtn, reloadBtn, homeBtn, urlBar, goBtn, pickerBtn, status);

    const iframe = document.createElement("iframe");
    iframe.className = "rmb-frame";
    iframe.setAttribute("sandbox", "allow-scripts allow-forms allow-same-origin allow-popups");
    iframe.setAttribute("referrerpolicy", "no-referrer");

    wrap.append(toolbar, iframe);

    // Event isolation — keep ComfyUI canvas from grabbing wheel/keys
    wrap.addEventListener("wheel", (e) => e.stopPropagation(), { passive: true });
    wrap.addEventListener("contextmenu", (e) => e.stopPropagation());
    wrap.addEventListener("pointerdown", (e) => e.stopPropagation());
    wrap.addEventListener("mousedown", (e) => e.stopPropagation());
    urlBar.addEventListener("keydown", (e) => {
        e.stopPropagation();
        if (e.key === "Enter") {
            e.preventDefault();
            const v = urlBar.value.trim();
            if (v) loadUrl(normalizeUrl(v));
        } else if (e.key === "Escape") {
            urlBar.blur();
        }
    });
    urlBar.addEventListener("keyup", (e) => e.stopPropagation());

    // History state
    const historyStack = [];
    let historyIdx = -1;
    let pickerOn = false;

    function setStatus(msg, kind = "") {
        status.textContent = msg || "";
        status.className = "rmb-status" + (kind ? " " + kind : "");
        if (msg) {
            clearTimeout(setStatus._t);
            setStatus._t = setTimeout(() => {
                status.textContent = "";
                status.className = "rmb-status";
            }, 2500);
        }
    }

    function normalizeUrl(v) {
        if (/^[a-z]+:\/\//i.test(v)) return v;
        return "https://" + v;
    }

    function updateNavButtons() {
        backBtn.disabled = historyIdx <= 0;
        fwdBtn.disabled = historyIdx < 0 || historyIdx >= historyStack.length - 1;
    }

    function loadUrl(rawUrl, pushHistory = true) {
        if (!rawUrl) return;
        urlBar.value = rawUrl;
        const urlW = getWidget(node, "url");
        if (urlW) urlW.value = rawUrl;

        const proxied = "/ray_minibrowser/proxy?url="
            + encodeURIComponent(rawUrl)
            + "&node_id=" + encodeURIComponent(safeNodeId(node));
        iframe.src = proxied;

        if (pushHistory) {
            if (historyIdx < historyStack.length - 1) {
                historyStack.splice(historyIdx + 1);
            }
            // collapse repeats
            if (historyStack[historyStack.length - 1] !== rawUrl) {
                historyStack.push(rawUrl);
                historyIdx = historyStack.length - 1;
            }
        }
        if (!node.properties) node.properties = {};
        node.properties._rayMBUrl = rawUrl;
        updateNavButtons();
    }

    backBtn.addEventListener("click", () => {
        if (historyIdx > 0) {
            historyIdx--;
            loadUrl(historyStack[historyIdx], false);
        }
    });
    fwdBtn.addEventListener("click", () => {
        if (historyIdx < historyStack.length - 1) {
            historyIdx++;
            loadUrl(historyStack[historyIdx], false);
        }
    });
    reloadBtn.addEventListener("click", () => {
        if (historyIdx >= 0) loadUrl(historyStack[historyIdx], false);
    });
    homeBtn.addEventListener("click", () => loadUrl(HOME_URL));
    goBtn.addEventListener("click", () => {
        const v = urlBar.value.trim();
        if (v) loadUrl(normalizeUrl(v));
    });

    pickerBtn.addEventListener("click", () => {
        pickerOn = !pickerOn;
        pickerBtn.classList.toggle("armed", pickerOn);
        pickerBtn.title = pickerOn ? "Picker ARMED — click an element" : "Toggle DOM picker";
        try {
            iframe.contentWindow?.postMessage(
                { type: pickerOn ? "rayPickerOn" : "rayPickerOff" }, "*",
            );
        } catch {}
        setStatus(pickerOn ? "picker on" : "picker off");
    });

    // Listen for messages from the iframe bridge
    function onMessage(e) {
        if (e.source !== iframe.contentWindow) return;
        const d = e.data || {};
        if (d.type === "rayNavigated" && typeof d.url === "string") {
            loadUrl(unproxy(d.url));
        } else if (d.type === "raySelected") {
            handleSelected({ ...d, url: unproxy(d.url) });
        } else if (d.type === "rayLoaded") {
            const real = unproxy(d.url || "");
            if (real && real !== urlBar.value) {
                urlBar.value = real;
                const urlW = getWidget(node, "url");
                if (urlW) urlW.value = real;
            }
            setStatus(`loaded${d.title ? ": " + String(d.title).slice(0, 32) : ""}`, "ok");
        }
    }
    window.addEventListener("message", onMessage);

    // iframe-level diagnostics — fires when browser refuses the load entirely
    // (Enhanced Tracking Prevention, sandbox conflict, OS-level filter).
    iframe.addEventListener("load", () => {
        // Wait briefly to see if the bridge says rayLoaded; if not, the iframe
        // either rendered our error HTML, was nuked by the browser, or the
        // bridge failed to install (CSP we missed, charset issue).
        setTimeout(() => {
            try {
                if (iframe.contentDocument?.body?.innerText === "") {
                    setStatus("blank: browser blocked content?", "err");
                }
            } catch {
                setStatus("cross-origin (proxy bug)", "err");
            }
        }, 600);
    });
    iframe.addEventListener("error", () => setStatus("iframe error", "err"));

    function handleSelected(payload) {
        const text = String(payload.text || "");
        const images = Array.isArray(payload.images)
            ? payload.images.filter((s) => typeof s === "string" && s)
            : [];

        node._raySelectedText = text;
        node._raySelectedImages = images;

        const tW = getWidget(node, "pending_text");
        if (tW) tW.value = text;
        const iW = getWidget(node, "pending_images_json");
        const imagesJson = JSON.stringify(images);
        if (iW) iW.value = imagesJson;

        if (!node.properties) node.properties = {};
        node.properties._rayMBLastText = text.length > 4096 ? text.slice(0, 4096) : text;
        node.properties._rayMBLastImagesJson = imagesJson;

        // Auto-disarm picker after capture (parent + iframe)
        if (pickerOn) {
            pickerOn = false;
            pickerBtn.classList.remove("armed");
            pickerBtn.title = "Toggle DOM picker";
            try {
                iframe.contentWindow?.postMessage({ type: "rayPickerOff" }, "*");
            } catch {}
        }

        // Push to server-side cache so the next workflow run picks it up
        fetch("/ray_minibrowser/select", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                node_id: safeNodeId(node),
                text,
                images,
                url: payload.url || "",
            }),
        }).catch(() => {});

        const tag = (payload.rootTag || "").toLowerCase();
        const summary = `captured ${tag || "el"} · ${images.length} img · ${text.length} ch`;
        setStatus(summary, "ok");
        node.setDirtyCanvas?.(true, true);
    }

    function mkBtn(label, title) {
        const b = document.createElement("button");
        b.textContent = label;
        b.title = title;
        return b;
    }

    // Resize: track the wrap height into node.properties
    const ro = new ResizeObserver(() => {
        if (!node.properties) node.properties = {};
        node.properties._rayMBHeight = wrap.clientHeight || 480;
    });
    ro.observe(wrap);

    // Sync url widget edits from outside (e.g. user types into node widget directly)
    const urlW = getWidget(node, "url");
    if (urlW) {
        const origCallback = urlW.callback;
        urlW.callback = function (v) {
            const r = origCallback?.apply(this, arguments);
            const cur = historyStack[historyIdx];
            if (typeof v === "string" && v.trim() && v.trim() !== cur) {
                loadUrl(normalizeUrl(v.trim()));
            }
            return r;
        };
    }

    if (typeof node.addDOMWidget === "function") {
        wrap.style.minHeight = "320px";
        node.addDOMWidget("browser_ui", "RAY_MB", wrap, {
            serialize: false,
            hideOnZoom: false,
            getMinHeight: () => 360,
            getHeight: () => node.properties?._rayMBHeight || 480,
        });
    }

    // Initial load — defer so widgets are settled
    setTimeout(() => {
        const startUrl = node.properties?._rayMBUrl
            || getWidget(node, "url")?.value
            || HOME_URL;
        loadUrl(startUrl, true);
    }, 60);

    // Public hooks for extension lifecycle
    node._rayMBLoadUrl = (u) => loadUrl(u);
    node._rayMBOnConfigure = () => {
        const props = node.properties || {};
        if (props._rayMBLastText != null) {
            const tW = getWidget(node, "pending_text");
            if (tW) tW.value = props._rayMBLastText;
        }
        if (props._rayMBLastImagesJson != null) {
            const iW = getWidget(node, "pending_images_json");
            if (iW) iW.value = props._rayMBLastImagesJson;
        }
        const target = props._rayMBUrl || getWidget(node, "url")?.value || HOME_URL;
        loadUrl(target, true);
    };
    node._rayMBOnExecuted = (uiData) => {
        const url = uiData?.ray_mb_url?.[0];
        if (url && url !== urlBar.value) urlBar.value = url;
    };
}

app.registerExtension({
    name: "Ray.MiniBrowser",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== NODE_NAME) return;
        const orig = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const r = orig?.apply(this, arguments);
            try { buildBrowserUI(this); }
            catch (e) { console.error("[RayMiniBrowser] buildBrowserUI error:", e); }
            this.size = [560, 480];
            return r;
        };

        const onConfigure = nodeType.prototype.onConfigure;
        nodeType.prototype.onConfigure = function (info) {
            const r = onConfigure?.apply(this, arguments);
            setTimeout(() => {
                try { this._rayMBOnConfigure?.(); }
                catch (e) { console.warn("[RayMiniBrowser] onConfigure dispatch error:", e); }
            }, 60);
            return r;
        };

        const onExecuted = nodeType.prototype.onExecuted;
        nodeType.prototype.onExecuted = function (message) {
            const r = onExecuted?.apply(this, arguments);
            try { this._rayMBOnExecuted?.(message); }
            catch (e) { console.warn("[RayMiniBrowser] onExecuted dispatch error:", e); }
            return r;
        };
    },
});
