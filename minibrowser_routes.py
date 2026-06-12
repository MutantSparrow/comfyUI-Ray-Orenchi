"""HTTP routes backing the RayMiniBrowser node.

Two endpoints, both registered on ComfyUI's PromptServer:

* GET  /ray_minibrowser/proxy   — same-origin proxy that fetches the target
  URL, strips framing/CSP headers, and rewrites HTML/CSS so all subresource
  URLs route back through this proxy. A small bridge <script> is injected
  to forward link clicks and the picker payload back to the parent window.

* POST /ray_minibrowser/select  — the bridge posts the picker result here;
  it lands in SELECTION_CACHE keyed by node_id and is consumed by the
  RayMiniBrowser.process() call on the next workflow run.

Heavy SPAs and login-walled sites will partially break — this is best-effort
proxying, not a real browser. The aiohttp.ClientSession is module-level and
lazy; ComfyUI process lifetime cleans it up on restart.
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from urllib.parse import quote, urljoin, urlparse, urlsplit

import aiohttp
from aiohttp import web

try:
    from bs4 import BeautifulSoup
except ImportError:  # pragma: no cover
    BeautifulSoup = None

try:
    from server import PromptServer
except ImportError:
    PromptServer = None

from .ray_minibrowser import SELECTION_CACHE, SELECTION_CACHE_MAX


_session: aiohttp.ClientSession | None = None
# Mimic a real Chrome UA so sites with bot heuristics don't 403/blank.
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
_DEFAULT_HEADERS = {
    "User-Agent": _USER_AGENT,
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,image/apng,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    # No Accept-Encoding — let aiohttp negotiate and decode automatically.
}
_PROXY_PATH = "/ray_minibrowser/proxy"
_HEADERS_TO_DROP = {
    "x-frame-options",
    "frame-options",
    "content-security-policy",
    "content-security-policy-report-only",
    "strict-transport-security",
    "cross-origin-opener-policy",
    "cross-origin-embedder-policy",
    "cross-origin-resource-policy",
    "permissions-policy",
    "set-cookie",  # cookies live in our session jar, never the iframe
    "clear-site-data",
    "report-to",
    "nel",
    "expect-ct",
    "x-content-type-options",
    "referrer-policy",
}
_HOP_BY_HOP = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
    "content-length",
    "content-encoding",
}
_SKIP_URL_PREFIX = ("javascript:", "mailto:", "data:", "blob:", "#", "tel:")
_CSS_URL_RE = re.compile(r"""url\(\s*(['"]?)([^'")]+)\1\s*\)""")
_MAX_CSS_REWRITE_BYTES = 4 * 1024 * 1024


def _get_session() -> aiohttp.ClientSession:
    global _session
    if _session is None or _session.closed:
        # Per-session cookie jar: lets sites that gate on session cookies
        # (Cloudflare interstitials, consent flows) progress past the wall.
        # Disable SSL verification so self-signed/expired-cert hosts still
        # render; this is a UI feature inside ComfyUI, not a security tool.
        connector = aiohttp.TCPConnector(ssl=False, limit=32)
        jar = aiohttp.CookieJar(unsafe=True)
        _session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=25, connect=10),
            trust_env=True,
            headers=_DEFAULT_HEADERS,
            cookie_jar=jar,
            connector=connector,
            auto_decompress=True,
        )
    return _session


def _proxify(absolute_url: str) -> str:
    return f"{_PROXY_PATH}?url={quote(absolute_url, safe='')}"


def _error_html(target: str, message: str) -> str:
    safe_target = (target or "").replace("<", "&lt;").replace(">", "&gt;")
    safe_msg = (message or "").replace("<", "&lt;").replace(">", "&gt;")
    return f"""<!doctype html><html><head><meta charset="utf-8">
<title>RayMiniBrowser proxy error</title>
<style>
body{{background:#1e1f22;color:#d8d8da;font:13px/1.5 -apple-system,Segoe UI,Roboto,sans-serif;
     padding:24px;margin:0}}
h1{{font-size:14px;color:#e35b5b;margin:0 0 8px}}
code{{color:#9cdcfe;font:12px ui-monospace,Consolas,monospace;word-break:break-all}}
.box{{background:#15161a;border:1px solid #333;border-radius:6px;padding:12px;margin-top:12px}}
</style></head><body>
<h1>Could not load page</h1>
<div>The proxy could not fetch this URL.</div>
<div class="box"><div>URL</div><code>{safe_target}</code></div>
<div class="box"><div>Reason</div><code>{safe_msg}</code></div>
<div class="box">Possible causes: site blocks proxies/bots, requires login, hard CSP/SRI,
WebSocket-only content, or strict TLS. Try another URL.</div>
</body></html>"""


def _should_skip(val: str) -> bool:
    if not val:
        return True
    v = val.strip().lower()
    return any(v.startswith(p) for p in _SKIP_URL_PREFIX)


def _rewrite_css(css: str, base: str) -> str:
    def repl(m: re.Match) -> str:
        raw = m.group(2).strip()
        if _should_skip(raw):
            return m.group(0)
        absolute = urljoin(base, raw)
        return f"url({_proxify(absolute)})"

    return _CSS_URL_RE.sub(repl, css)


def _rewrite_srcset(srcset: str, base: str) -> str:
    out = []
    for chunk in srcset.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        parts = chunk.split(None, 1)
        url = parts[0]
        descriptor = f" {parts[1]}" if len(parts) > 1 else ""
        if _should_skip(url):
            out.append(chunk)
            continue
        out.append(_proxify(urljoin(base, url)) + descriptor)
    return ", ".join(out)


def _bridge_script() -> str:
    """JS injected into every proxied HTML page.

    Capture-phase click interception, picker overlay, fetch/XHR shim, and the
    parent <-> iframe message channel all live here. Kept as a single string
    literal so the HTML rewrite step is a one-liner append.

    The base URL of the *real* document is read from window.__rayRealBase,
    set by a tiny <script> block injected just before this one. Without that,
    relative URLs resolved by page JS against location.href (the proxy URL)
    point back at ComfyUI's origin and 404 every subresource.
    """
    return r"""
(function(){
  if (window.__rayBridgeInstalled) return;
  window.__rayBridgeInstalled = true;
  var PROXY = '/ray_minibrowser/proxy?url=';

  // Stash real parent before framebust neutralizer hides it.
  var REAL_PARENT = window.parent;
  function postUp(msg){ try { REAL_PARENT.postMessage(msg, '*'); } catch(_){} }

  // --- Framebust neutralizer: pages like google.com check window.top !== window.self
  // and either redirect or wipe the document. Make top look like self to the page. ---
  try {
    Object.defineProperty(window, 'top',    { get: function(){ return window.self; }, configurable: true });
    Object.defineProperty(window, 'parent', { get: function(){ return window.self; }, configurable: true });
    Object.defineProperty(window, 'frameElement', { get: function(){ return null; }, configurable: true });
  } catch(_){}

  // Ping parent so the URL bar can show the post-redirect URL (which may
  // differ from what we asked the proxy for).
  postUp({type:'rayLoaded', url: location.href, title: document.title || ''});

  // Reflect the *original* origin so relative URLs resolve to the real host
  // and not to ComfyUI's local origin (which would 404 every subresource).
  // Source-of-truth = window.__rayRealBase (set by injected <script> just
  // before this one), with <base href> + ?url= as last-resort fallbacks.
  function realDocumentBase(){
    if (typeof window.__rayRealBase === 'string' && window.__rayRealBase) {
      return window.__rayRealBase;
    }
    try {
      var b = document.querySelector && document.querySelector('base');
      if (b && b.href) return b.href;
    } catch(_){}
    try {
      var u = new URL(location.href);
      if (u.pathname === '/ray_minibrowser/proxy') {
        var inner = u.searchParams.get('url');
        if (inner) return inner;
      }
    } catch(_){}
    return location.href;
  }
  function unproxyUrl(u){
    try {
      var p = new URL(u, location.href);
      if (p.pathname === '/ray_minibrowser/proxy') {
        var inner = p.searchParams.get('url');
        if (inner) return inner;
      }
      return p.href;
    } catch(_){ return u; }
  }
  function absolute(u){ try { return new URL(u, realDocumentBase()).href; } catch(e){ return u; } }
  function shouldSkip(u){
    if (!u) return true;
    var s = String(u).trim().toLowerCase();
    return s.startsWith('javascript:') || s.startsWith('data:') || s.startsWith('blob:')
        || s.startsWith('mailto:') || s.startsWith('tel:') || s.startsWith('#')
        || s.startsWith('about:');
  }
  function viaProxy(u){
    var abs = absolute(u);
    // If somebody handed us a URL pointing at our own origin (likely because
    // base resolution failed earlier), unproxy + retry against the real base.
    try {
      var p = new URL(abs);
      if (p.origin === location.origin) {
        if (p.pathname === '/ray_minibrowser/proxy') {
          return abs; // already proxied
        }
        // Wrong origin — rewrite against real base
        var real = new URL(p.pathname + p.search + p.hash, realDocumentBase()).href;
        return PROXY + encodeURIComponent(real);
      }
    } catch(_){}
    return PROXY + encodeURIComponent(abs);
  }

  // --- Link click interception: bubble navigation up to parent ---
  document.addEventListener('click', function(e){
    if (window.__rayPickerOn) return; // picker handler manages clicks itself
    var a = e.target && e.target.closest && e.target.closest('a[href]');
    if (!a) return;
    var href = a.getAttribute('href');
    if (shouldSkip(href)) return;
    e.preventDefault();
    e.stopImmediatePropagation();
    // If the href is already a proxy URL (server-side HTML rewrite did its
    // job), pull the inner ?url= back out — don't double-resolve. Otherwise
    // resolve against the real base.
    var target;
    try {
      var u = new URL(href, location.href);
      if (u.origin === location.origin && u.pathname === '/ray_minibrowser/proxy') {
        target = u.searchParams.get('url') || href;
      } else {
        target = absolute(href);
      }
    } catch(_) {
      target = absolute(href);
    }
    postUp({type:'rayNavigated', url: target});
  }, true);

  // --- Form submit interception: GET forms (search bars) lose the proxy
  // ?url=... query when the browser rebuilds the query string from inputs.
  // Resolve to the original action, append form data, route through proxy. ---
  function realActionUrl(form){
    // form.action / formaction may be /ray_minibrowser/proxy?url=<orig> after
    // the server-side rewrite; pull <orig> back out.
    var raw = form.getAttribute('action') || location.href;
    try {
      var u = new URL(raw, location.href);
      if (u.pathname === '/ray_minibrowser/proxy') {
        var inner = u.searchParams.get('url');
        if (inner) return inner;
      }
      return u.href;
    } catch(_){ return raw; }
  }
  document.addEventListener('submit', function(e){
    if (window.__rayPickerOn) return;
    var form = e.target;
    if (!form || form.tagName !== 'FORM') return;
    var method = (form.method || 'get').toLowerCase();
    if (method !== 'get') return; // POST forms work — body is preserved
    e.preventDefault();
    e.stopImmediatePropagation();
    try {
      var actionAbs = realActionUrl(form);
      var fd = new FormData(form);
      var params = new URLSearchParams();
      fd.forEach(function(v, k){ params.append(k, typeof v === 'string' ? v : ''); });
      var qs = params.toString();
      var sep = actionAbs.indexOf('?') >= 0 ? '&' : '?';
      // If the original URL had a query, GET form spec says replace it; emulate.
      var base = actionAbs.split('#')[0].split('?')[0];
      var fullUrl = base + (qs ? ('?' + qs) : '');
      postUp({type:'rayNavigated', url: fullUrl});
    } catch(err){
      console.warn('[RayMiniBrowser] form submit intercept failed:', err);
    }
  }, true);

  // --- fetch / XHR shim for SPAs that build URLs at runtime ---
  function isProxied(u){
    try {
      if (!u) return false;
      var s = String(u);
      if (s.indexOf('/ray_minibrowser/') === 0) return true;
      if (s.indexOf('://') >= 0) {
        var p = new URL(s);
        return p.origin === location.origin && p.pathname === '/ray_minibrowser/proxy';
      }
    } catch(_){}
    return false;
  }
  try {
    var origFetch = window.fetch && window.fetch.bind(window);
    if (origFetch) {
      window.fetch = function(input, init){
        try {
          if (typeof input === 'string' && !shouldSkip(input) && !isProxied(input)) {
            input = viaProxy(input);
          } else if (input && input.url && !shouldSkip(input.url) && !isProxied(input.url)) {
            input = new Request(viaProxy(input.url), input);
          }
        } catch(_){}
        return origFetch(input, init);
      };
    }
  } catch(_){}
  try {
    var XO = XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open = function(method, url){
      try {
        if (typeof url === 'string' && !shouldSkip(url) && !isProxied(url)) {
          url = viaProxy(url);
        }
      } catch(_){}
      return XO.apply(this, [method, url].concat([].slice.call(arguments,2)));
    };
  } catch(_){}

  // --- location shim: page JS doing `location.href = '/foo'` or
  // `location.assign('/foo')` resolves against location.href (the proxy
  // URL on ComfyUI's origin), which would navigate the iframe to
  // ComfyUI itself. Reroute through proxy with viaProxy() instead. ---
  function rewriteNav(u){
    try {
      if (typeof u !== 'string') return u;
      if (shouldSkip(u) || isProxied(u)) return u;
      return viaProxy(u);
    } catch(_) { return u; }
  }
  try {
    var L = Location.prototype;
    if (L.assign) {
      var origAssign = L.assign;
      L.assign = function(u){ return origAssign.call(this, rewriteNav(u)); };
    }
    if (L.replace) {
      var origReplace = L.replace;
      L.replace = function(u){ return origReplace.call(this, rewriteNav(u)); };
    }
    var hrefDesc = Object.getOwnPropertyDescriptor(L, 'href');
    if (hrefDesc && hrefDesc.set) {
      var origHrefSet = hrefDesc.set;
      Object.defineProperty(L, 'href', {
        configurable: true,
        enumerable: hrefDesc.enumerable,
        get: hrefDesc.get,
        set: function(u){ return origHrefSet.call(this, rewriteNav(u)); },
      });
    }
  } catch(_){}
  // window.open() likewise — pop into parent so URL bar updates
  try {
    var origOpen = window.open && window.open.bind(window);
    if (origOpen) {
      window.open = function(u, name, feat){
        try {
          if (typeof u === 'string' && !shouldSkip(u) && !isProxied(u)) {
            postUp({type:'rayNavigated', url: absolute(u)});
            return null;
          }
        } catch(_){}
        return origOpen(u, name, feat);
      };
    }
  } catch(_){}
  // history.pushState / replaceState — keep URL bar synced + ensure paths
  // resolve correctly if the SPA later does location-based ops
  try {
    var H = history;
    var origPush = H.pushState && H.pushState.bind(H);
    var origRepl = H.replaceState && H.replaceState.bind(H);
    if (origPush) {
      H.pushState = function(s, t, u){
        var r = origPush(s, t, u);
        try { postUp({type:'rayLoaded', url: absolute(u || location.href), title: document.title || ''}); } catch(_){}
        return r;
      };
    }
    if (origRepl) {
      H.replaceState = function(s, t, u){
        var r = origRepl(s, t, u);
        try { postUp({type:'rayLoaded', url: absolute(u || location.href), title: document.title || ''}); } catch(_){}
        return r;
      };
    }
  } catch(_){}

  // --- sendBeacon shim (page-view trackers etc) ---
  try {
    if (navigator.sendBeacon) {
      var origBeacon = navigator.sendBeacon.bind(navigator);
      navigator.sendBeacon = function(url, data){
        try {
          if (typeof url === 'string' && !shouldSkip(url) && !isProxied(url)) {
            url = viaProxy(url);
          }
        } catch(_){}
        return origBeacon(url, data);
      };
    }
  } catch(_){}

  // --- Worker / SharedWorker shim — same-origin scripts only; cross-origin
  // workers fail by spec, so we route via proxy to keep them same-origin. ---
  try {
    if (window.Worker) {
      var OrigWorker = window.Worker;
      window.Worker = function(url, opts){
        try {
          if (typeof url === 'string' && !shouldSkip(url) && !isProxied(url)) {
            url = viaProxy(url);
          }
        } catch(_){}
        return new OrigWorker(url, opts);
      };
      window.Worker.prototype = OrigWorker.prototype;
    }
  } catch(_){}

  // --- DOM attribute shims: rewrite href/src/action/data set after parse.
  // Static HTML is already rewritten server-side; this catches dynamic JS
  // that sets img.src = '/foo.png', new Image().src = '...', script.src=...
  // Hook BOTH the property setter and setAttribute. ---
  function shouldRewriteAttr(tag, attr){
    tag = (tag || '').toUpperCase();
    if (attr === 'src') {
      return ['IMG','SCRIPT','IFRAME','SOURCE','VIDEO','AUDIO','TRACK','EMBED'].indexOf(tag) >= 0;
    }
    if (attr === 'href') {
      return ['A','LINK','AREA','IMAGE'].indexOf(tag) >= 0;
    }
    if (attr === 'action') return tag === 'FORM';
    if (attr === 'poster') return tag === 'VIDEO';
    if (attr === 'data')   return tag === 'OBJECT';
    if (attr === 'formaction') return ['BUTTON','INPUT'].indexOf(tag) >= 0;
    return false;
  }
  function maybeRewriteValue(value){
    try {
      var s = String(value);
      if (!s || shouldSkip(s) || isProxied(s)) return value;
      // <a href="#anchor"> stays anchor; only rewrite when there's a path.
      return viaProxy(s);
    } catch(_) { return value; }
  }
  function patchAttr(proto, attr){
    try {
      var d = Object.getOwnPropertyDescriptor(proto, attr);
      if (!d || !d.set) return;
      var origSet = d.set;
      var origGet = d.get;
      Object.defineProperty(proto, attr, {
        configurable: true,
        get: function(){ return origGet ? origGet.call(this) : undefined; },
        set: function(v){
          try {
            if (shouldRewriteAttr(this.tagName, attr)) {
              v = maybeRewriteValue(v);
            }
          } catch(_){}
          return origSet.call(this, v);
        }
      });
    } catch(_){}
  }
  patchAttr(HTMLImageElement.prototype,    'src');
  patchAttr(HTMLScriptElement.prototype,   'src');
  patchAttr(HTMLIFrameElement.prototype,   'src');
  patchAttr(HTMLSourceElement.prototype,   'src');
  patchAttr(HTMLMediaElement.prototype,    'src');
  patchAttr(HTMLTrackElement.prototype,    'src');
  patchAttr(HTMLEmbedElement.prototype,    'src');
  patchAttr(HTMLAnchorElement.prototype,   'href');
  patchAttr(HTMLLinkElement.prototype,     'href');
  patchAttr(HTMLAreaElement.prototype,     'href');
  patchAttr(HTMLFormElement.prototype,     'action');
  patchAttr(HTMLVideoElement.prototype,    'poster');
  if (window.HTMLObjectElement) patchAttr(HTMLObjectElement.prototype, 'data');

  try {
    var origSetAttr = Element.prototype.setAttribute;
    Element.prototype.setAttribute = function(name, value){
      try {
        var n = String(name).toLowerCase();
        if (n === 'src' || n === 'href' || n === 'action' || n === 'poster' || n === 'data' || n === 'formaction') {
          if (shouldRewriteAttr(this.tagName, n)) {
            value = maybeRewriteValue(value);
          }
        } else if (n === 'srcset' && this.tagName === 'IMG') {
          try {
            var parts = String(value).split(',').map(function(c){
              c = c.trim();
              if (!c) return c;
              var sp = c.split(/\s+/);
              var u = sp[0];
              if (!shouldSkip(u) && !isProxied(u)) sp[0] = viaProxy(u);
              return sp.join(' ');
            });
            value = parts.join(', ');
          } catch(_){}
        }
      } catch(_){}
      return origSetAttr.call(this, name, value);
    };
  } catch(_){}

  // --- MutationObserver: catch nodes added via innerHTML / document.write
  // / cloneNode etc — those bypass our property setter shims because the
  // attribute was set during HTML parse, not via property assignment. ---
  function fixNodeUrls(node){
    if (!node || node.nodeType !== 1) return;
    var tag = node.tagName;
    if (!tag) return;
    var ATTRS = ['src','href','action','poster','data','formaction'];
    for (var i = 0; i < ATTRS.length; i++) {
      var a = ATTRS[i];
      if (shouldRewriteAttr(tag, a) && node.hasAttribute && node.hasAttribute(a)) {
        var v = node.getAttribute(a);
        if (v && !shouldSkip(v) && !isProxied(v)) {
          try { node.setAttribute(a, viaProxy(v)); } catch(_){}
        }
      }
    }
    if (tag === 'IMG' && node.hasAttribute && node.hasAttribute('srcset')) {
      try { node.setAttribute('srcset', node.getAttribute('srcset')); } catch(_){}
    }
  }
  function walkAndFix(root){
    try {
      fixNodeUrls(root);
      if (root.querySelectorAll) {
        var all = root.querySelectorAll('*');
        for (var i = 0; i < all.length; i++) fixNodeUrls(all[i]);
      }
    } catch(_){}
  }
  try {
    var mo = new MutationObserver(function(muts){
      for (var i = 0; i < muts.length; i++) {
        var m = muts[i];
        if (m.type === 'childList') {
          for (var j = 0; j < m.addedNodes.length; j++) walkAndFix(m.addedNodes[j]);
        } else if (m.type === 'attributes') {
          fixNodeUrls(m.target);
        }
      }
    });
    var startObserver = function(){
      try {
        mo.observe(document.documentElement || document, {
          childList: true, subtree: true, attributes: true,
          attributeFilter: ['src','href','action','poster','data','formaction','srcset']
        });
      } catch(_){}
    };
    if (document.documentElement) startObserver();
    else document.addEventListener('DOMContentLoaded', startObserver);
  } catch(_){}

  // --- Picker overlay ---
  var overlay = null;
  function ensureOverlay(){
    if (overlay) return overlay;
    overlay = document.createElement('div');
    overlay.style.cssText = 'position:fixed;pointer-events:none;z-index:2147483647;'
      + 'border:2px solid #4ea0ff;background:rgba(78,160,255,0.18);'
      + 'box-shadow:0 0 0 1px rgba(0,0,0,0.4);transition:none;display:none;';
    (document.body || document.documentElement).appendChild(overlay);
    return overlay;
  }
  function hideOverlay(){ if (overlay) overlay.style.display='none'; }
  function moveOverlay(el){
    var r = el.getBoundingClientRect();
    var o = ensureOverlay();
    o.style.left = r.left + 'px';
    o.style.top = r.top + 'px';
    o.style.width = r.width + 'px';
    o.style.height = r.height + 'px';
    o.style.display = 'block';
  }

  var lastHover = null;
  function onMove(e){
    if (!window.__rayPickerOn) return;
    var el = document.elementFromPoint(e.clientX, e.clientY);
    if (!el || el === lastHover) return;
    lastHover = el;
    moveOverlay(el);
  }
  function onClickPick(e){
    if (!window.__rayPickerOn) return;
    var el = document.elementFromPoint(e.clientX, e.clientY);
    if (!el) return;
    e.preventDefault();
    e.stopImmediatePropagation();
    capture(el);
  }

  // --- Image rasterization (single media element) -----------------------
  // Always resolves within RASTER_TIMEOUT_MS; never hangs the picker.
  var RASTER_TIMEOUT_MS = 3500;
  var MAX_IMAGES = 64;

  function withTimeout(promise, ms){
    return new Promise(function(resolve){
      var done = false;
      var t = setTimeout(function(){ if (!done){ done = true; resolve(''); } }, ms);
      promise.then(function(v){ if (!done){ done = true; clearTimeout(t); resolve(v); } },
                   function(){ if (!done){ done = true; clearTimeout(t); resolve(''); } });
    });
  }
  function blobToB64(blob){
    return new Promise(function(resolve){
      if (!blob) { resolve(''); return; }
      var fr = new FileReader();
      fr.onload = function(){
        var s = String(fr.result || '');
        var i = s.indexOf(',');
        resolve(i >= 0 ? s.slice(i+1) : s);
      };
      fr.onerror = function(){ resolve(''); };
      try { fr.readAsDataURL(blob); } catch(_){ resolve(''); }
    });
  }
  function canvasToB64(canvas){
    return new Promise(function(resolve){
      try {
        canvas.toBlob(function(b){ blobToB64(b).then(resolve); }, 'image/webp', 0.85);
      } catch(_){ resolve(''); }
    });
  }
  function rasterizeMedia(el){
    return withTimeout(new Promise(function(resolve){
      try {
        var canvas, ctx;
        if (el.tagName === 'IMG') {
          if (!el.complete || !el.naturalWidth) { resolve(''); return; }
          canvas = document.createElement('canvas');
          canvas.width = el.naturalWidth; canvas.height = el.naturalHeight;
          ctx = canvas.getContext('2d');
          ctx.drawImage(el, 0, 0);
          return canvasToB64(canvas).then(resolve);
        }
        if (el.tagName === 'CANVAS') {
          return canvasToB64(el).then(resolve);
        }
        if (el.tagName === 'VIDEO' && el.videoWidth) {
          canvas = document.createElement('canvas');
          canvas.width = el.videoWidth; canvas.height = el.videoHeight;
          ctx = canvas.getContext('2d');
          ctx.drawImage(el, 0, 0);
          return canvasToB64(canvas).then(resolve);
        }
        if (el.tagName === 'svg' || el.tagName === 'SVG' || el.namespaceURI === 'http://www.w3.org/2000/svg') {
          var rect = el.getBoundingClientRect();
          var w = Math.max(1, Math.round(rect.width || el.getAttribute('width') || 64));
          var h = Math.max(1, Math.round(rect.height || el.getAttribute('height') || 64));
          var ser = new XMLSerializer().serializeToString(el);
          var blob = new Blob([ser], {type:'image/svg+xml;charset=utf-8'});
          var url = URL.createObjectURL(blob);
          var img = new Image();
          img.onload = function(){
            var c = document.createElement('canvas');
            c.width = w; c.height = h;
            c.getContext('2d').drawImage(img, 0, 0, w, h);
            URL.revokeObjectURL(url);
            canvasToB64(c).then(resolve);
          };
          img.onerror = function(){ URL.revokeObjectURL(url); resolve(''); };
          img.src = url;
          return;
        }
        resolve('');
      } catch(err) {
        console.warn('[RayMiniBrowser] rasterize failed:', err);
        resolve('');
      }
    }), RASTER_TIMEOUT_MS);
  }

  // --- Batch capture: clicked element + all descendants -----------------
  // Walks the subtree, collects every text node and every media element.
  function collectSubtree(root){
    var texts = [];
    var media = [];
    var seen = 0;
    var walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT, null, false);
    var node = root; // include the root
    function visit(n){
      if (n.nodeType === Node.TEXT_NODE) {
        var t = n.nodeValue;
        if (t && t.trim()) texts.push(t.trim());
        return;
      }
      if (n.nodeType !== Node.ELEMENT_NODE) return;
      var tag = n.tagName;
      if (tag === 'SCRIPT' || tag === 'STYLE' || tag === 'NOSCRIPT' || tag === 'TEMPLATE') return;
      // Include the element itself for media detection
      if (tag === 'IMG' || tag === 'CANVAS' || tag === 'VIDEO') {
        if (media.length < MAX_IMAGES) media.push(n);
      } else if (n.namespaceURI === 'http://www.w3.org/2000/svg' && tag.toLowerCase() === 'svg') {
        if (media.length < MAX_IMAGES) media.push(n);
      }
      // Pull text directly (preserves visual order well enough)
      if (tag !== 'IMG' && tag !== 'CANVAS' && tag !== 'VIDEO') {
        for (var c = n.firstChild; c; c = c.nextSibling) {
          if (++seen > 20000) return; // safety
          visit(c);
        }
      }
    }
    visit(root);
    return { texts: texts, media: media };
  }

  function capture(root){
    var collected = collectSubtree(root);
    var rootText = (root.innerText || root.textContent || '').trim();
    var joined = rootText || collected.texts.join('\n');
    if (joined.length > 262144) joined = joined.slice(0, 262144);

    var jobs = collected.media.map(function(el){ return rasterizeMedia(el); });
    Promise.all(jobs).then(function(b64s){
      var images = b64s.filter(function(s){ return s && s.length > 0; });
      postUp({
        type: 'raySelected',
        text: joined,
        images: images,
        url: location.href,
        rootTag: root.tagName,
        imageCount: images.length,
      });
    }, function(){
      postUp({
        type: 'raySelected',
        text: joined,
        images: [],
        url: location.href,
        rootTag: root.tagName,
        imageCount: 0,
      });
    });
  }

  document.addEventListener('mousemove', onMove, true);
  document.addEventListener('click', onClickPick, true);

  window.addEventListener('message', function(e){
    var d = e.data || {};
    if (d.type === 'rayPickerOn')  { window.__rayPickerOn = true; }
    if (d.type === 'rayPickerOff') { window.__rayPickerOn = false; lastHover = null; hideOverlay(); }
  });
})();
"""


def _rewrite_html(html: str, base: str) -> str:
    if BeautifulSoup is None:
        # Best-effort: at least append the bridge so picker still works.
        return html + f"<script>window.__rayRealBase={base!r};{_bridge_script()}</script>"

    soup = BeautifulSoup(html, "html.parser")

    # <head> + <base href=...> for relative resolution
    head = soup.head
    if head is None:
        head = soup.new_tag("head")
        if soup.html:
            soup.html.insert(0, head)
        else:
            soup.insert(0, head)
    parsed = urlsplit(base)
    base_dir = base.rsplit("/", 1)[0] + "/" if "/" in parsed.path else f"{parsed.scheme}://{parsed.netloc}/"
    base_tag = soup.new_tag("base", href=base_dir, target="_self")
    head.insert(0, base_tag)

    # Set __rayRealBase as the very first <script> in <head> so any inline
    # script that runs during parse can resolve URLs against the real origin.
    base_init = soup.new_tag("script")
    base_init.string = (
        f"window.__rayRealBase={json.dumps(base_dir)};"
        f"window.__rayOriginalUrl={json.dumps(base)};"
    )
    head.insert(1, base_init)

    # Strip CSP <meta> tags and meta-refresh redirects (latter would break
    # out of the iframe to the unproxied URL).
    for meta in soup.find_all("meta"):
        equiv = (meta.get("http-equiv") or "").lower()
        if equiv in {"content-security-policy", "x-frame-options", "refresh"}:
            meta.decompose()

    # Attribute rewrites. NOTE: <form action> is intentionally absolutized
    # but NOT proxified — the bridge intercepts submit and routes via
    # postMessage to keep query strings intact for GET search forms.
    for tag in soup.find_all(True):
        # Strip Subresource Integrity — content rewrite invalidates the hash.
        if tag.has_attr("integrity"):
            del tag["integrity"]
        if tag.has_attr("crossorigin"):
            del tag["crossorigin"]
        for attr in ("href", "src", "poster", "data-src", "data-href"):
            val = tag.get(attr)
            if isinstance(val, str) and not _should_skip(val):
                tag[attr] = _proxify(urljoin(base, val))
        if tag.name == "form":
            action_val = tag.get("action")
            if isinstance(action_val, str) and not _should_skip(action_val):
                tag["action"] = urljoin(base, action_val)
        srcset = tag.get("srcset")
        if isinstance(srcset, str) and srcset.strip():
            tag["srcset"] = _rewrite_srcset(srcset, base)
        style = tag.get("style")
        if isinstance(style, str) and "url(" in style:
            tag["style"] = _rewrite_css(style, base)

    # <style> blocks
    for style_tag in soup.find_all("style"):
        if style_tag.string:
            style_tag.string.replace_with(_rewrite_css(style_tag.string, base))

    # Inject bridge as the SECOND <script> in <head> (right after the
    # __rayRealBase init). This is critical: any inline <script> earlier in
    # the document would resolve relative URLs against location.href (the
    # proxy URL on ComfyUI's origin) before our shims patched fetch/XHR/
    # element setters — leading to subresources hitting :8188/foo instead
    # of being proxied. Installing in <head> means shims are live before
    # any page script runs.
    bridge = soup.new_tag("script")
    bridge.string = _bridge_script()
    head.insert(2, bridge)

    return str(soup)


def _filter_response_headers(headers) -> dict:
    out = {}
    for k, v in headers.items():
        kl = k.lower()
        if kl in _HEADERS_TO_DROP or kl in _HOP_BY_HOP:
            continue
        out[k] = v
    out["Access-Control-Allow-Origin"] = "*"
    return out


def _trim_cache():
    if len(SELECTION_CACHE) <= SELECTION_CACHE_MAX:
        return
    excess = len(SELECTION_CACHE) - SELECTION_CACHE_MAX
    by_age = sorted(SELECTION_CACHE.items(), key=lambda kv: kv[1].get("ts", 0.0))
    for k, _ in by_age[:excess]:
        SELECTION_CACHE.pop(k, None)


_FORWARD_REQUEST_HEADERS = (
    "accept",
    "accept-language",
    "content-type",
    "x-requested-with",
    "x-csrf-token",
    "x-xsrf-token",
)


async def _proxy_handle(request: "web.Request"):
    target = request.query.get("url", "")
    if not target:
        return web.Response(
            body=_error_html("", "missing url query parameter").encode("utf-8"),
            status=400,
            headers={"Content-Type": "text/html; charset=utf-8"},
        )
    parsed = urlparse(target)
    if parsed.scheme not in ("http", "https"):
        return web.Response(
            body=_error_html(target, "unsupported URL scheme").encode("utf-8"),
            status=400,
            headers={"Content-Type": "text/html; charset=utf-8"},
        )

    # Spoof Referer + Origin to the target's site so hotlink/CORS gates pass.
    forwarded_headers = {
        "Referer": f"{parsed.scheme}://{parsed.netloc}/",
        "Origin":  f"{parsed.scheme}://{parsed.netloc}",
    }
    for hk in _FORWARD_REQUEST_HEADERS:
        if hk in request.headers:
            forwarded_headers[hk.title()] = request.headers[hk]

    method = request.method.upper()
    body = None
    if method in ("POST", "PUT", "PATCH", "DELETE"):
        try:
            body = await request.read()
        except Exception:
            body = None

    try:
        session = _get_session()
        async with session.request(
            method,
            target,
            allow_redirects=True,
            headers=forwarded_headers,
            data=body,
        ) as upstream:
            ctype = upstream.headers.get("Content-Type", "")
            ctype_lower = ctype.lower()
            final_url = str(upstream.url)
            base_headers = _filter_response_headers(upstream.headers)
            base_headers["X-Ray-Final-Url"] = final_url

            if "text/html" in ctype_lower:
                raw = await upstream.read()
                decoded = raw.decode(upstream.charset or "utf-8", errors="replace")
                rewritten = _rewrite_html(decoded, final_url)
                encoded = rewritten.encode("utf-8")
                base_headers["Content-Type"] = "text/html; charset=utf-8"
                return web.Response(body=encoded, status=upstream.status, headers=base_headers)

            if "text/css" in ctype_lower:
                raw = await upstream.read()
                if len(raw) > _MAX_CSS_REWRITE_BYTES:
                    return web.Response(body=raw, status=upstream.status, headers=base_headers)
                decoded = raw.decode(upstream.charset or "utf-8", errors="replace")
                rewritten = _rewrite_css(decoded, final_url)
                encoded = rewritten.encode("utf-8")
                base_headers["Content-Type"] = ctype or "text/css; charset=utf-8"
                return web.Response(body=encoded, status=upstream.status, headers=base_headers)

            # Streamed pass-through for everything else
            resp = web.StreamResponse(status=upstream.status, headers=base_headers)
            await resp.prepare(request)
            async for chunk in upstream.content.iter_chunked(8192):
                try:
                    await resp.write(chunk)
                except (ConnectionResetError, ConnectionError, asyncio.CancelledError):
                    break
            try:
                await resp.write_eof()
            except Exception:
                pass
            return resp
    except aiohttp.ClientResponseError as e:
        return web.Response(
            body=_error_html(target, f"HTTP {e.status}: {e.message}").encode("utf-8"),
            status=502,
            headers={"Content-Type": "text/html; charset=utf-8"},
        )
    except asyncio.TimeoutError:
        return web.Response(
            body=_error_html(target, "upstream request timed out").encode("utf-8"),
            status=504,
            headers={"Content-Type": "text/html; charset=utf-8"},
        )
    except Exception as e:
        print(f"[RayMiniBrowser] proxy error {request.method} {target}: {e!r}")
        return web.Response(
            body=_error_html(target, f"{type(e).__name__}: {e}").encode("utf-8"),
            status=502,
            headers={"Content-Type": "text/html; charset=utf-8"},
        )


if PromptServer is not None:

    _routes = PromptServer.instance.routes
    # NOTE: aiohttp's GET route registration implicitly adds HEAD as well, so
    # registering HEAD explicitly here raises "method HEAD is already registered".
    for _method in ("GET", "POST", "PUT", "PATCH", "DELETE"):
        _routes.route(_method, "/ray_minibrowser/proxy")(_proxy_handle)

    @PromptServer.instance.routes.post("/ray_minibrowser/select")
    async def select(request: web.Request):
        try:
            body = await request.json()
        except Exception as e:
            return web.json_response({"error": f"bad json: {e}"}, status=400)
        nid = str(body.get("node_id", "")).strip()
        if not nid:
            return web.json_response({"error": "missing node_id"}, status=400)
        raw_images = body.get("images")
        images: list[str] = []
        if isinstance(raw_images, list):
            images = [str(x) for x in raw_images if isinstance(x, str) and x]
        # Back-compat: prior shape used a single image_webp_b64 field.
        if not images:
            single = body.get("image_webp_b64")
            if isinstance(single, str) and single:
                images = [single]
        SELECTION_CACHE[nid] = {
            "text": str(body.get("text", "")),
            "images": images,
            "url": str(body.get("url", "")),
            "ts": time.time(),
        }
        _trim_cache()
        return web.json_response({"ok": True, "image_count": len(images)})

    @PromptServer.instance.routes.options("/ray_minibrowser/proxy")
    async def proxy_options(request: web.Request):
        return web.Response(
            status=204,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, PUT, PATCH, DELETE, HEAD, OPTIONS",
                "Access-Control-Allow-Headers": "*",
            },
        )

    @PromptServer.instance.routes.options("/ray_minibrowser/select")
    async def select_options(request: web.Request):
        return web.Response(
            status=204,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type",
            },
        )
