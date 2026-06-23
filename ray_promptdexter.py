"""Ray's Web: PromptDexter Scraper.

Fetches a random prompt + matching image from https://promptdexter.com/.
Seed-deterministic. 20-entry per-node LRU cache to avoid repeats.
Sitemap-driven discovery (handles sitemapindex recursion) so picks reach
deep content, not only the homepage top row.

Outputs: (STRING prompt_single, STRING prompt_multiline, IMAGE image).
"""

from __future__ import annotations

import io
import random
import re
import time
import urllib.parse
import xml.etree.ElementTree as ET
from collections import deque
from typing import Optional, Tuple

import numpy as np
from PIL import Image

try:
    import torch
except ImportError:
    torch = None

try:
    import requests
except ImportError:
    requests = None

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None


_SITE_BASE = "https://promptdexter.com"
_SITEMAP_URL = f"{_SITE_BASE}/sitemap.xml"
_USER_AGENT = (
    "comfyUI-Ray-Orenchi/PromptDexterNode "
    "(+https://github.com/Thingamajic/comfyUI-Ray-Orenchi)"
)
_HEADERS = {
    "User-Agent": _USER_AGENT,
    "Accept": "text/html,application/xml,application/xhtml+xml,*/*",
}

_SITEMAP_CACHE: Optional[list] = None
_RECENT_BY_NODE: dict = {}

_CACHE_MAX = 20
_RETRY_SLEEP = 0.5


def _http_get(url: str, timeout: int, retries: int = 1) -> "requests.Response":
    """GET with N retries (total tries = retries+1). Raises on terminal failure."""
    if requests is None:
        raise RuntimeError("requests package not installed — `pip install requests`")
    last_exc = None
    for attempt in range(retries + 1):
        try:
            resp = requests.get(url, headers=_HEADERS, timeout=timeout)
            resp.raise_for_status()
            return resp
        except Exception as e:
            last_exc = e
            if attempt < retries:
                time.sleep(_RETRY_SLEEP)
    raise RuntimeError(f"GET {url} failed after {retries + 1} tries: {last_exc}")


def _parse_sitemap_xml(content: bytes) -> Tuple[str, list]:
    """Return (root_tag_local, list_of_loc_strings). Strips namespace."""
    root = ET.fromstring(content)
    tag = root.tag.split("}", 1)[-1] if "}" in root.tag else root.tag
    locs = [el.text.strip() for el in root.findall(".//{*}loc") if el.text]
    return tag, locs


def _load_sitemap(force_refresh: bool, timeout: int) -> list:
    """Return cached pool of prompt URLs. Recurses into sitemapindex one level."""
    global _SITEMAP_CACHE
    if _SITEMAP_CACHE is not None and not force_refresh:
        return _SITEMAP_CACHE

    resp = _http_get(_SITEMAP_URL, timeout=timeout, retries=1)
    root_tag, locs = _parse_sitemap_xml(resp.content)

    if root_tag.lower() == "sitemapindex":
        all_urls = []
        for child_url in locs:
            child_resp = _http_get(child_url, timeout=timeout, retries=1)
            child_tag, child_locs = _parse_sitemap_xml(child_resp.content)
            if child_tag.lower() == "sitemapindex":
                raise RuntimeError(
                    f"Nested sitemapindex unsupported: {child_url}"
                )
            all_urls.extend(child_locs)
    elif root_tag.lower() == "urlset":
        all_urls = locs
    else:
        raise RuntimeError(
            f"Unexpected sitemap root <{root_tag}> at {_SITEMAP_URL}"
        )

    prompt_urls = []
    for u in all_urls:
        try:
            path = urllib.parse.urlsplit(u).path or ""
        except Exception:
            continue
        if path.startswith("/prompt/") and path != "/prompt/":
            prompt_urls.append(u)

    prompt_urls = list(dict.fromkeys(prompt_urls))
    if not prompt_urls:
        raise RuntimeError(
            "PromptDexter sitemap returned no /prompt URLs — site structure "
            "may have changed"
        )

    _SITEMAP_CACHE = prompt_urls
    return _SITEMAP_CACHE


def _normalize_text(s: Optional[str]) -> str:
    return (s or "").strip().lower()


def _extract_prompt_text(soup) -> Optional[str]:
    # 1. Heading "Prompt" → next sibling block
    for tag_name in ("h1", "h2", "h3"):
        for h in soup.find_all(tag_name):
            if _normalize_text(h.get_text()) == "prompt":
                sib = h.find_next_sibling()
                if sib is not None:
                    text = sib.get_text("\n", strip=True)
                    if text:
                        return text
                # Fallback: parent's text minus the heading
                parent = h.parent
                if parent is not None:
                    text = parent.get_text("\n", strip=True)
                    if text:
                        text = re.sub(r"^prompt\s*", "", text, flags=re.IGNORECASE)
                        if text.strip():
                            return text.strip()

    # 2. data-attribute markup
    el = soup.select_one("section[data-prompt], div[data-prompt]")
    if el is not None:
        text = el.get_text("\n", strip=True)
        if text:
            return text

    # 3. og:description
    meta = soup.find("meta", attrs={"property": "og:description"})
    if meta and meta.get("content"):
        return meta["content"].strip()

    # 4. Longest <p> >40 chars in main/article
    container = soup.find("main") or soup.find("article") or soup
    candidates = [p.get_text("\n", strip=True) for p in container.find_all("p")]
    candidates = [c for c in candidates if c and len(c) > 40]
    if candidates:
        return max(candidates, key=len)

    return None


def _extract_image_url(soup) -> Optional[str]:
    img = soup.select_one('img[src*="/images/explore/"]')
    if img is not None and img.get("src"):
        return urllib.parse.urljoin(_SITE_BASE, img["src"])

    meta = soup.find("meta", attrs={"property": "og:image"})
    if meta and meta.get("content"):
        return urllib.parse.urljoin(_SITE_BASE, meta["content"].strip())

    container = soup.find("main") or soup.find("article")
    if container is not None:
        first = container.find("img")
        if first is not None and first.get("src"):
            return urllib.parse.urljoin(_SITE_BASE, first["src"])

    return None


def _fetch_prompt_page(url: str, timeout: int) -> Tuple[str, Optional[str]]:
    if BeautifulSoup is None:
        raise RuntimeError("beautifulsoup4 not installed — `pip install beautifulsoup4`")
    resp = _http_get(url, timeout=timeout, retries=1)
    soup = BeautifulSoup(resp.text, "html.parser")
    text = _extract_prompt_text(soup)
    if not text:
        raise RuntimeError(f"Could not parse prompt text from {url}")
    image_url = _extract_image_url(soup)
    return text, image_url


def _black_tensor():
    if torch is None:
        return None
    return torch.zeros((1, 1, 1, 3), dtype=torch.float32)


def _fetch_image_tensor(image_url: Optional[str], timeout: int):
    if image_url is None or torch is None:
        return _black_tensor()
    try:
        resp = _http_get(image_url, timeout=timeout, retries=1)
        pil = Image.open(io.BytesIO(resp.content)).convert("RGB")
        arr = np.array(pil).astype(np.float32) / 255.0
        return torch.from_numpy(arr)[None, ...]
    except Exception as e:
        print(f"[RayPromptDexter] image fetch failed: {e}")
        return _black_tensor()


def _select_url(urls: list, recent: deque, rng, deterministic: bool) -> str:
    if not urls:
        raise RuntimeError("URL pool is empty")
    if deterministic:
        indices = list(range(len(urls)))
        rng.shuffle(indices)
        for i in indices:
            if urls[i] not in recent:
                return urls[i]
        return urls[indices[0]]
    for _ in range(50):
        pick = rng.choice(urls)
        if pick not in recent:
            return pick
    return rng.choice(urls)


def _build_outputs(prompt_multiline: str, image_url: Optional[str], timeout: int):
    prompt_single = re.sub(r"\s+", " ", prompt_multiline).strip()
    image_tensor = _fetch_image_tensor(image_url, timeout)
    return prompt_single, prompt_multiline, image_tensor


class RayPromptDexter:
    """Fetch a random prompt + image from promptdexter.com, seed-deterministic."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "seed": ("INT", {"default": -1, "min": -1, "max": 2**31 - 1}),
                "force_refresh_sitemap": ("BOOLEAN", {"default": False}),
                "clear_cache": ("BOOLEAN", {"default": False}),
            },
            "optional": {
                "category_filter": ("STRING", {"default": ""}),
                "timeout": ("INT", {"default": 10, "min": 2, "max": 60, "step": 1}),
            },
            "hidden": {"node_id": "UNIQUE_ID"},
        }

    RETURN_TYPES = ("STRING", "STRING", "IMAGE")
    RETURN_NAMES = ("prompt_single", "prompt_multiline", "image")
    FUNCTION = "process"
    CATEGORY = "Ray/Web🌐"

    @classmethod
    def IS_CHANGED(cls, *args, **kwargs):
        return float("nan")

    def process(
        self,
        seed,
        force_refresh_sitemap,
        clear_cache,
        category_filter="",
        timeout=10,
        node_id=None,
    ):
        node_key = str(node_id) if node_id is not None else "_default"

        if clear_cache:
            _RECENT_BY_NODE.pop(node_key, None)

        urls = _load_sitemap(bool(force_refresh_sitemap), int(timeout))

        cf = (category_filter or "").strip().lower()
        if cf:
            urls = [u for u in urls if cf in u.lower()]
            if not urls:
                raise RuntimeError(
                    f"category_filter '{category_filter}' matched no /prompt URLs"
                )

        seed_int = int(seed)
        if seed_int < 0:
            rng = random.SystemRandom()
            deterministic = False
        else:
            rng = random.Random(seed_int)
            deterministic = True

        recent = _RECENT_BY_NODE.setdefault(node_key, deque(maxlen=_CACHE_MAX))
        chosen_url = _select_url(urls, recent, rng, deterministic)
        recent.append(chosen_url)

        prompt_multiline, image_url = _fetch_prompt_page(chosen_url, int(timeout))
        prompt_single, prompt_multiline, image_tensor = _build_outputs(
            prompt_multiline, image_url, int(timeout)
        )
        return (prompt_single, prompt_multiline, image_tensor)
