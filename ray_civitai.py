"""Ray's Web: CivitAI Gallery Scraper.

Fetches a random gallery image + its prompt from civitai.com.
Uses the public REST API (`GET /api/v1/images`) — no scraping required.

Mode toggle:
  • Blue (SFW)  → browsingLevel=1   (PG only)
  • Red  (NSFW) → browsingLevel=28  (R | X | XXX)

The `browsingLevel` bitmask takes precedence over the legacy `nsfw`
parameter; values: PG=1, PG13=2, R=4, X=8, XXX=16.

Only images with a usable `meta.prompt` field are kept; ones without are
skipped. Per-node 20-entry LRU avoids consecutive repeats. Seed-deterministic.

API token (optional) is read from `civitai.secret` placed next to this
file inside the node-pack directory. The public endpoint works without a
token; supplying one unlocks higher-tier content access tied to the
account. The secret file is gitignored — never commit it.

Outputs: (STRING prompt_single, STRING prompt_multiline, IMAGE image).
"""

from __future__ import annotations

import io
import json
import pathlib
import random
import re
import time
import urllib.parse
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


_API_BASE = "https://civitai.com/api/v1"
_IMAGES_URL = f"{_API_BASE}/images"
_USER_AGENT = (
    "comfyUI-Ray-Orenchi/CivitAINode "
    "(+https://github.com/Thingamajic/comfyUI-Ray-Orenchi)"
)
_PACK_DIR = pathlib.Path(__file__).resolve().parent
_TOKEN_FILE = _PACK_DIR / "civitai.secret"

MODE_BLUE = "Blue (SFW)"
MODE_RED = "Red (NSFW)"
MODES = [MODE_BLUE, MODE_RED]

BROWSING_LEVEL_BLUE = 1            # PG
BROWSING_LEVEL_RED = 4 | 8 | 16    # R | X | XXX = 28

PERIODS = ["AllTime", "Year", "Month", "Week", "Day"]
SORTS = ["Random", "Most Reactions", "Most Comments", "Newest"]

BASE_MODELS_DEFAULT = "Any"
# Sampled live from /api/v1/images across periods; CivitAI returns whatever
# uploaders tag their work with, so new architectures keep appearing —
# refresh periodically.
BASE_MODELS = [
    BASE_MODELS_DEFAULT,
    "SD 1.5",
    "SDXL 1.0",
    "Pony",
    "Illustrious",
    "NoobAI",
    "Anima",
    "Flux.1 D",
    "Flux.1 S",
    "Flux.2 Klein 9B",
    "SD 3.5",
    "Chroma",
    "HiDream",
    "Krea 2",
    "Qwen",
    "OpenAI",
    "Nano Banana",
    "Grok",
    "Seedream",
    "Z-Image Base",
    "Z-Image Turbo",
    "Wan Video",
    "Wan Video 14B t2v",
    "LTXV 2.3",
]

_PAGE_CACHE: dict = {}
_RECENT_BY_NODE: dict = {}

_CACHE_MAX = 20
_RETRY_SLEEP = 0.5
_MAX_PAGES_PER_MODE = 6
_PAGE_LIMIT = 100


def _read_token() -> str:
    try:
        if _TOKEN_FILE.is_file():
            return _TOKEN_FILE.read_text(encoding="utf-8").strip()
    except OSError as e:
        print(f"[RayCivitAI] could not read {_TOKEN_FILE.name}: {e}")
    return ""


def has_token() -> bool:
    return bool(_read_token())


def _auth_header() -> dict:
    tok = _read_token()
    return {"Authorization": f"Bearer {tok}"} if tok else {}


def _headers() -> dict:
    h = {
        "User-Agent": _USER_AGENT,
        "Accept": "application/json,image/*,*/*",
    }
    h.update(_auth_header())
    return h


def _http_get(url: str, timeout: int, retries: int = 1) -> "requests.Response":
    if requests is None:
        raise RuntimeError("requests package not installed — `pip install requests`")
    last_exc = None
    for attempt in range(retries + 1):
        try:
            resp = requests.get(url, headers=_headers(), timeout=timeout)
            resp.raise_for_status()
            return resp
        except Exception as e:
            last_exc = e
            if attempt < retries:
                time.sleep(_RETRY_SLEEP)
    raise RuntimeError(f"GET {url} failed after {retries + 1} tries: {last_exc}")


def _mode_to_browsing_level(mode: str) -> int:
    """Bitmask for civitai browsingLevel: PG=1, PG13=2, R=4, X=8, XXX=16."""
    if mode == MODE_RED:
        return BROWSING_LEVEL_RED
    return BROWSING_LEVEL_BLUE


def _build_query(
    browsing_level: int,
    period: str,
    sort: str,
    base_model: str,
    cursor: Optional[str],
    limit: int,
    username: str = "",
) -> str:
    params = {
        "limit": str(limit),
        "browsingLevel": str(browsing_level),
        "period": period,
        "sort": sort,
        "withMeta": "true",
    }
    if cursor:
        params["cursor"] = cursor
    if base_model and base_model != BASE_MODELS_DEFAULT:
        params["baseModels"] = base_model
    if username:
        params["username"] = username
    return urllib.parse.urlencode(params)


def _fetch_page(
    browsing_level: int,
    period: str,
    sort: str,
    base_model: str,
    cursor: Optional[str],
    timeout: int,
    username: str = "",
) -> Tuple[list, Optional[str]]:
    qs = _build_query(
        browsing_level, period, sort, base_model, cursor, _PAGE_LIMIT, username
    )
    url = f"{_IMAGES_URL}?{qs}"
    resp = _http_get(url, timeout=timeout, retries=1)
    try:
        data = resp.json()
    except Exception as e:
        raise RuntimeError(f"CivitAI API returned non-JSON: {e}")
    items = data.get("items") or []
    next_cursor = (data.get("metadata") or {}).get("nextCursor")
    return items, next_cursor


# Node class_type heuristics for extracting a prompt out of a ComfyUI
# workflow JSON. Order matters — explicit "positive" wins over generic
# text-multiline nodes.
_COMFY_PROMPT_CLASS_HINTS = (
    "CLIPTextEncode",
    "BNK_CLIPTextEncodeAdvanced",
    "CLIPTextEncodeFlux",
    "CLIPTextEncodeSDXL",
    "Text Multiline",
    "Text Concatenate",
    "ShowText",
    "String Literal",
)


def _extract_prompt_from_comfy(meta: dict) -> str:
    """Salvage the positive prompt from a ComfyUI workflow blob.

    Civitai sometimes ships full workflows in `meta.comfy` (JSON string) and
    leaves `meta.prompt` empty — typical for uploads from ComfyUI's native
    image-saver. Walk `prompt` node graph, pull the longest plausibly-textual
    `inputs.text` (or `string`/`positive`/`prompt`) from a node whose
    class_type smells like a text encoder / text widget.
    """
    raw = meta.get("comfy")
    if not raw:
        return ""
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            return ""
    if not isinstance(raw, dict):
        return ""
    prompt_graph = raw.get("prompt") or {}
    if not isinstance(prompt_graph, dict):
        return ""

    candidates: list = []  # list of (priority, length, text)
    for _nid, node in prompt_graph.items():
        if not isinstance(node, dict):
            continue
        ct = node.get("class_type") or ""
        inputs = node.get("inputs") or {}
        if not isinstance(inputs, dict):
            continue
        # Score by class_type match position; "CLIPTextEncode" first.
        priority = next(
            (i for i, hint in enumerate(_COMFY_PROMPT_CLASS_HINTS) if hint in ct),
            999,
        )
        if priority == 999:
            continue
        # Try several common input field names.
        for field in ("text", "string", "positive", "prompt", "Text"):
            val = inputs.get(field)
            if isinstance(val, str):
                stripped = val.strip()
                if len(stripped) >= 12:
                    candidates.append((priority, len(stripped), stripped))
    if not candidates:
        return ""
    # Lowest priority value (best class match) first; ties broken by length.
    candidates.sort(key=lambda c: (c[0], -c[1]))
    return candidates[0][2]


def _extract_prompt(item: dict) -> str:
    """Return the best available prompt string for a civitai image item.

    Tries `meta.prompt` first, then falls back to a ComfyUI workflow blob.
    """
    meta = item.get("meta") or {}
    if not isinstance(meta, dict):
        return ""
    direct = (meta.get("prompt") or "").strip()
    if direct:
        return direct
    return _extract_prompt_from_comfy(meta)


def _filter_with_prompt(items: list) -> list:
    out = []
    for it in items:
        prompt = _extract_prompt(it)
        url = it.get("url") or ""
        if prompt and url:
            out.append({
                "id": it.get("id"),
                "url": url,
                "prompt": prompt,
                "nsfwLevel": it.get("nsfwLevel"),
                "baseModel": it.get("baseModel"),
                "username": it.get("username"),
            })
    return out


def _load_pool(
    mode: str,
    period: str,
    sort: str,
    base_model: str,
    timeout: int,
    username: str = "",
    force_refresh: bool = False,
) -> list:
    """Page through the API building a pool of prompted images. Cached by key.

    When `username` is set we force `period=AllTime`: per-user feeds rarely
    have enough recent activity to fill a `Week`/`Day` window, and the API
    returns zero results in that case instead of the full author archive.
    """
    if username and period != "AllTime":
        print(
            f"[RayCivitAI] username={username!r} set — overriding period "
            f"{period!r} -> 'AllTime' (per-user feeds need full history)."
        )
        period = "AllTime"

    key = (mode, period, sort, base_model, username)
    if not force_refresh and key in _PAGE_CACHE:
        return _PAGE_CACHE[key]

    pool: list = []
    seen_ids = set()
    browsing_level = _mode_to_browsing_level(mode)

    cursor: Optional[str] = None
    for _ in range(_MAX_PAGES_PER_MODE):
        items, next_cursor = _fetch_page(
            browsing_level, period, sort, base_model, cursor, timeout, username
        )
        kept = _filter_with_prompt(items)
        for k in kept:
            if k["id"] in seen_ids:
                continue
            seen_ids.add(k["id"])
            pool.append(k)
        if not next_cursor or not items:
            break
        cursor = next_cursor

    if not pool:
        user_part = f", username={username}" if username else ""
        raise RuntimeError(
            f"CivitAI returned no images with prompts for mode={mode}, "
            f"period={period}, sort={sort}, baseModel={base_model}{user_part}"
        )

    _PAGE_CACHE[key] = pool
    return pool


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
        print(f"[RayCivitAI] image fetch failed: {e}")
        return _black_tensor()


def _select_item(pool: list, recent: deque, rng, deterministic: bool) -> dict:
    if not pool:
        raise RuntimeError("pool is empty")
    if deterministic:
        indices = list(range(len(pool)))
        rng.shuffle(indices)
        for i in indices:
            if pool[i]["id"] not in recent:
                return pool[i]
        return pool[indices[0]]
    for _ in range(50):
        pick = rng.choice(pool)
        if pick["id"] not in recent:
            return pick
    return rng.choice(pool)


def _build_outputs(prompt_multiline: str, image_url: Optional[str], timeout: int):
    prompt_single = re.sub(r"\s+", " ", prompt_multiline).strip()
    image_tensor = _fetch_image_tensor(image_url, timeout)
    return prompt_single, prompt_multiline, image_tensor


def clear_cache():
    _PAGE_CACHE.clear()
    _RECENT_BY_NODE.clear()


class RayCivitAI:
    """Fetch a random prompt + gallery image from civitai.com, seed-deterministic."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "seed": ("INT", {"default": -1, "min": -1, "max": 2**31 - 1}),
                "mode": (MODES, {"default": MODE_BLUE}),
                "base_model": (BASE_MODELS, {"default": BASE_MODELS_DEFAULT}),
                "period": (PERIODS, {"default": "Week"}),
                "sort": (SORTS, {"default": "Random"}),
                "username": ("STRING", {"default": "", "multiline": False,
                                         "placeholder": "civitai username (optional)"}),
            },
            "optional": {
                "timeout": ("INT", {"default": 15, "min": 2, "max": 60, "step": 1}),
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
        mode,
        base_model,
        period,
        sort,
        username="",
        timeout=15,
        node_id=None,
    ):
        node_key = str(node_id) if node_id is not None else "_default"
        username = (username or "").strip()

        pool = _load_pool(
            mode=mode,
            period=period,
            sort=sort,
            base_model=base_model,
            timeout=int(timeout),
            username=username,
        )

        seed_int = int(seed)
        if seed_int < 0:
            rng = random.SystemRandom()
            deterministic = False
        else:
            rng = random.Random(seed_int)
            deterministic = True

        recent = _RECENT_BY_NODE.setdefault(node_key, deque(maxlen=_CACHE_MAX))
        chosen = _select_item(pool, recent, rng, deterministic)
        recent.append(chosen["id"])

        prompt_multiline = chosen["prompt"]
        image_url = chosen["url"]
        prompt_single, prompt_multiline, image_tensor = _build_outputs(
            prompt_multiline, image_url, int(timeout)
        )
        return (prompt_single, prompt_multiline, image_tensor)
