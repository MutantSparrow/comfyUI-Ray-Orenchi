"""Ray's Local: Folder Image Scraper.

Walks a local folder (optionally recursing into subfolders) and serves
images one at a time, attempting to extract any generation prompt found
in the image's metadata. Designed as a functional sibling to the
PromptDexter and CivitAI scrapers but for local files.

Prompt extraction sources, in priority order:
  1. PNG `parameters` chunk (Automatic1111 / Forge native format).
  2. PNG `prompt` chunk (ComfyUI's serialized prompt graph JSON).
  3. PNG `workflow` chunk (ComfyUI workflow JSON).
  4. JPEG/WEBP EXIF UserComment (A1111 also writes here).
  5. JPEG/WEBP `info['parameters']` (PIL surfaces it for some encoders).
  6. Sidecar `<image>.txt` in the same directory.

When multiple positive prompts are found inside a single image (e.g. a
ComfyUI workflow with several CLIPTextEncode nodes), they are batched
into the multiline output separated by `\\n---\\n`. The single-line
output is the first prompt collapsed to one line.

Outputs:
  STRING prompt_single     — first prompt, whitespace-collapsed.
  STRING prompt_multiline  — full prompt text, multi-prompt batched.
  IMAGE  image             — BHWC float32 [0,1] tensor of the image.
  STRING image_path        — absolute path of the source file.
"""

from __future__ import annotations

import json
import os
import pathlib
import random
import re
from collections import deque
from typing import Optional

import numpy as np
from PIL import Image

try:
    import torch
except ImportError:
    torch = None


_SUPPORTED_EXT = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".tif")

_FILE_LIST_CACHE: dict = {}   # key=(folder, recurse) -> sorted list[str]
_RECENT_BY_NODE: dict = {}
_CACHE_MAX = 20

# ComfyUI node classes whose `inputs.text` (or similar) typically holds a
# positive prompt. Order matters — explicit CLIPTextEncode wins.
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
_COMFY_PROMPT_INPUT_FIELDS = ("text", "string", "positive", "prompt", "Text")


# ---------------------------------------------------------------------------
# Prompt extractors
# ---------------------------------------------------------------------------


def _strip_a1111(blob: str) -> str:
    """Return only the positive portion of an A1111 parameters block."""
    if not isinstance(blob, str):
        return ""
    # A1111 format: "<positive>\nNegative prompt: <neg>\nSteps: ..."
    parts = re.split(r"\n(?:Negative prompt:|Steps:)", blob, maxsplit=1)
    return parts[0].strip()


def _extract_prompts_from_comfy_graph(graph_obj) -> list:
    """Walk a ComfyUI prompt graph dict and return *all* plausible prompts.

    `graph_obj` is the value of either the `prompt` chunk (a node dict
    keyed by node id) or a workflow object with `prompt` / `nodes` keys.
    Returns a list ordered by class_type priority (best first).
    """
    if isinstance(graph_obj, str):
        try:
            graph_obj = json.loads(graph_obj)
        except Exception:
            return []
    if not isinstance(graph_obj, dict):
        return []

    # Two shapes: {"prompt": {...}, "workflow": {...}} or {"<nid>": {...}}.
    if "prompt" in graph_obj and isinstance(graph_obj["prompt"], dict):
        graph_obj = graph_obj["prompt"]

    candidates: list = []  # (priority, length, text)
    for _nid, node in graph_obj.items():
        if not isinstance(node, dict):
            continue
        ct = node.get("class_type") or ""
        inputs = node.get("inputs") or {}
        if not isinstance(inputs, dict):
            continue
        priority = next(
            (i for i, hint in enumerate(_COMFY_PROMPT_CLASS_HINTS) if hint in ct),
            999,
        )
        if priority == 999:
            continue
        for field in _COMFY_PROMPT_INPUT_FIELDS:
            val = inputs.get(field)
            if isinstance(val, str):
                stripped = val.strip()
                if len(stripped) >= 8:
                    candidates.append((priority, len(stripped), stripped))
                    break

    # De-duplicate while preserving order and sorting by priority/length.
    candidates.sort(key=lambda c: (c[0], -c[1]))
    seen = set()
    out: list = []
    for _, _, text in candidates:
        if text not in seen:
            seen.add(text)
            out.append(text)
    return out


def _read_exif_user_comment(pil_image: Image.Image) -> str:
    """EXIF UserComment from a PIL image, decoded to plain text."""
    try:
        exif = pil_image.getexif()
    except Exception:
        return ""
    if not exif:
        return ""
    # 37510 = UserComment
    raw = exif.get(37510)
    if raw is None:
        return ""
    if isinstance(raw, bytes):
        # EXIF UserComment is prefixed with an 8-byte character-code header
        # ("ASCII\0\0\0", "UNICODE\0", "JIS\0\0\0\0\0").
        if raw.startswith(b"UNICODE\0"):
            try:
                return raw[8:].decode("utf-16-be").strip()
            except Exception:
                try:
                    return raw[8:].decode("utf-16-le").strip()
                except Exception:
                    return ""
        if raw.startswith(b"ASCII\0\0\0"):
            return raw[8:].decode("ascii", errors="replace").strip()
        return raw.decode("utf-8", errors="replace").strip()
    return str(raw).strip()


def _read_sidecar(image_path: pathlib.Path) -> str:
    sidecar = image_path.with_suffix(image_path.suffix + ".txt")
    if not sidecar.is_file():
        sidecar = image_path.with_suffix(".txt")
    if not sidecar.is_file():
        return ""
    try:
        return sidecar.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return ""


def extract_prompts(image_path: pathlib.Path, pil_image: Image.Image) -> list:
    """Return a list of positive prompts found in the image's metadata.

    May return an empty list when nothing is found. Order is best-effort:
    A1111 first, then ComfyUI graphs (each CLIPTextEncode contributes one
    entry), then EXIF/sidecar fallback.
    """
    info = pil_image.info or {}

    prompts: list = []

    # 1. A1111 parameters chunk (PNG iTXt or JPEG info).
    params_blob = info.get("parameters") or info.get("Parameters")
    if isinstance(params_blob, str) and params_blob.strip():
        positive = _strip_a1111(params_blob)
        if positive:
            prompts.append(positive)

    # 2. PNG `prompt` chunk = serialized ComfyUI prompt graph.
    comfy_prompt = info.get("prompt")
    if comfy_prompt:
        prompts.extend(_extract_prompts_from_comfy_graph(comfy_prompt))

    # 3. PNG `workflow` chunk = ComfyUI workflow (may include the prompt).
    comfy_workflow = info.get("workflow")
    if comfy_workflow:
        prompts.extend(_extract_prompts_from_comfy_graph(comfy_workflow))

    # 4. EXIF UserComment fallback.
    if not prompts:
        exif_text = _read_exif_user_comment(pil_image)
        if exif_text:
            # Some encoders embed A1111-style here; others store JSON.
            positive = _strip_a1111(exif_text)
            if positive:
                prompts.append(positive)

    # 5. Sidecar .txt file.
    if not prompts:
        sidecar = _read_sidecar(image_path)
        if sidecar:
            prompts.append(sidecar)

    # De-duplicate while preserving order.
    seen = set()
    deduped: list = []
    for p in prompts:
        s = (p or "").strip()
        if s and s not in seen:
            seen.add(s)
            deduped.append(s)
    return deduped


# ---------------------------------------------------------------------------
# Folder enumeration
# ---------------------------------------------------------------------------


def _enumerate_images(folder: pathlib.Path, recurse: bool) -> list:
    """List image file paths under `folder`. Sorted for deterministic seeding."""
    if not folder.is_dir():
        return []
    if recurse:
        it = folder.rglob("*")
    else:
        it = folder.iterdir()
    out = []
    for p in it:
        try:
            if p.is_file() and p.suffix.lower() in _SUPPORTED_EXT:
                out.append(str(p))
        except OSError:
            continue
    out.sort()
    return out


def _file_list(folder: pathlib.Path, recurse: bool, refresh: bool = False) -> list:
    key = (str(folder.resolve()) if folder.exists() else str(folder), recurse)
    if not refresh and key in _FILE_LIST_CACHE:
        return _FILE_LIST_CACHE[key]
    lst = _enumerate_images(folder, recurse)
    _FILE_LIST_CACHE[key] = lst
    return lst


def clear_cache():
    _FILE_LIST_CACHE.clear()
    _RECENT_BY_NODE.clear()


# ---------------------------------------------------------------------------
# Image -> tensor + outputs
# ---------------------------------------------------------------------------


def _black_tensor():
    if torch is None:
        return None
    return torch.zeros((1, 1, 1, 3), dtype=torch.float32)


def _pil_to_tensor(pil_image: Image.Image):
    if torch is None:
        return None
    arr = np.array(pil_image.convert("RGB")).astype(np.float32) / 255.0
    return torch.from_numpy(arr)[None, ...]


def _select_path(paths: list, recent: deque, rng, deterministic: bool) -> str:
    if not paths:
        raise RuntimeError("no images found in folder")
    if deterministic:
        indices = list(range(len(paths)))
        rng.shuffle(indices)
        for i in indices:
            if paths[i] not in recent:
                return paths[i]
        return paths[indices[0]]
    for _ in range(50):
        pick = rng.choice(paths)
        if pick not in recent:
            return pick
    return rng.choice(paths)


# ---------------------------------------------------------------------------
# Node class
# ---------------------------------------------------------------------------


class RayLocalScraper:
    """Pick a random image from a local folder and extract its prompts."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "folder": ("STRING", {
                    "default": "",
                    "multiline": False,
                    "placeholder": "absolute path to a folder of images",
                }),
                "recurse_subfolders": ("BOOLEAN", {"default": False}),
                "skip_no_prompt": ("BOOLEAN", {"default": False}),
                "seed": ("INT", {"default": -1, "min": -1, "max": 2**31 - 1}),
            },
            "optional": {
                "refresh_listing": ("BOOLEAN", {"default": False}),
            },
            "hidden": {"node_id": "UNIQUE_ID"},
        }

    RETURN_TYPES = ("STRING", "STRING", "IMAGE", "STRING")
    RETURN_NAMES = ("prompt_single", "prompt_multiline", "image", "image_path")
    FUNCTION = "process"
    CATEGORY = "Ray/Local📁"

    @classmethod
    def IS_CHANGED(cls, *args, **kwargs):
        return float("nan")

    def process(
        self,
        folder,
        recurse_subfolders,
        skip_no_prompt,
        seed,
        refresh_listing=False,
        node_id=None,
    ):
        node_key = str(node_id) if node_id is not None else "_default"
        folder = (folder or "").strip()
        if not folder:
            raise RuntimeError("folder path is empty")
        folder_p = pathlib.Path(folder).expanduser()
        if not folder_p.is_dir():
            raise RuntimeError(f"folder does not exist: {folder_p}")

        paths = _file_list(folder_p, bool(recurse_subfolders), refresh=bool(refresh_listing))
        if not paths:
            raise RuntimeError(f"no supported images in {folder_p}")

        seed_int = int(seed)
        if seed_int < 0:
            rng = random.SystemRandom()
            deterministic = False
        else:
            rng = random.Random(seed_int)
            deterministic = True

        recent = _RECENT_BY_NODE.setdefault(node_key, deque(maxlen=_CACHE_MAX))

        # When skip_no_prompt is on, we may need to try several picks
        # before finding one with extractable metadata. Cap attempts at
        # the pool size so we don't loop forever on a folder of raw images.
        attempts = 0
        max_attempts = min(len(paths), 50) if skip_no_prompt else 1
        chosen_path: Optional[str] = None
        chosen_prompts: list = []
        pil_image: Optional[Image.Image] = None

        candidates_tried: set = set()
        while attempts < max_attempts:
            attempts += 1
            try:
                pick = _select_path(paths, recent, rng, deterministic)
            except RuntimeError:
                break

            if pick in candidates_tried:
                # Same pick chosen again means the LRU forced a fallback;
                # bail rather than spin.
                break
            candidates_tried.add(pick)

            try:
                pil_image = Image.open(pick)
                pil_image.load()
            except Exception as e:
                print(f"[RayLocalScraper] cannot open {pick}: {e}")
                continue

            prompts = extract_prompts(pathlib.Path(pick), pil_image)
            if prompts or not skip_no_prompt:
                chosen_path = pick
                chosen_prompts = prompts
                break

            # Skip this one and mark as recent so we don't immediately
            # retry the same file.
            recent.append(pick)

        if chosen_path is None or pil_image is None:
            if skip_no_prompt:
                raise RuntimeError(
                    f"no images with extractable prompts in {folder_p} "
                    f"(tried {attempts})"
                )
            raise RuntimeError(f"could not open any image in {folder_p}")

        recent.append(chosen_path)

        if chosen_prompts:
            prompt_multiline = "\n---\n".join(chosen_prompts)
            prompt_single = re.sub(r"\s+", " ", chosen_prompts[0]).strip()
        else:
            prompt_multiline = ""
            prompt_single = ""

        image_tensor = _pil_to_tensor(pil_image)
        if image_tensor is None:
            image_tensor = _black_tensor()

        return (prompt_single, prompt_multiline, image_tensor, os.fspath(chosen_path))
