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
ComfyUI workflow with several CLIPTextEncode nodes), every output is
emitted as a ComfyUI list — one entry per prompt — so downstream nodes
iterate over each prompt independently. The image and path entries are
broadcast (repeated) across every prompt in the batch.

Outputs (all OUTPUT_IS_LIST = True):
  STRING prompt_single     — each prompt collapsed to one line.
  STRING prompt_multiline  — each prompt with its newlines preserved.
  IMAGE  image             — BHWC float32 [0,1] tensor (same tensor reused).
  STRING image_path        — absolute path of the source file (repeated).
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

# Class-name substrings that mark a node as the *target* (a text encoder
# that we want to feed a prompt into). When such a node's text input is
# wired rather than literal we walk backwards through the graph.
_COMFY_ENCODER_HINTS = (
    "CLIPTextEncode",
    "BNK_CLIPTextEncodeAdvanced",
    "CLIPTextEncodeFlux",
    "CLIPTextEncodeSDXL",
    "smZ CLIPTextEncode",
    "AdvancedCLIPTextEncode",
)

# Class-name substrings that mark a node as a *source* of free-form
# prompt text (Show Text, Text Multiline, String literals, primitive
# nodes, concat / pipe nodes...). When we follow a link back, we try to
# pull the literal text out of one of these.
_COMFY_TEXT_SOURCE_HINTS = (
    "Text Multiline",
    "ShowText",
    "Show Text",
    "Show_text",
    "ShowAnything",
    "String Literal",
    "StringLiteral",
    "String Constant",
    "PrimitiveNode",
    "Text Concatenate",
    "TextConcatenate",
    "Text Concat",
    "Text Combine",
    "StringFunction",
    "easy showAnything",
    "easy textConcat",
    "DPRandomGenerator",
    "Text",
)
_COMFY_MAX_LINK_DEPTH = 8


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


def _is_link_ref(val) -> bool:
    """ComfyUI wires inputs as [source_node_id, output_slot]."""
    return (
        isinstance(val, (list, tuple))
        and len(val) == 2
        and isinstance(val[0], (str, int))
        and isinstance(val[1], int)
    )


def _resolve_text_from_node(
    node_id, graph: dict, visited: set, depth: int = 0
) -> str:
    """Pull a literal prompt string out of a node, recursing through wired
    text inputs (Show Text -> Text Multiline -> String Literal etc.).

    Returns an empty string if no literal text can be found within the
    depth cap, or if a cycle is detected.
    """
    if depth > _COMFY_MAX_LINK_DEPTH:
        return ""
    nid = str(node_id)
    if nid in visited:
        return ""
    visited = visited | {nid}

    node = graph.get(nid)
    if not isinstance(node, dict):
        return ""
    inputs = node.get("inputs") or {}
    if not isinstance(inputs, dict):
        return ""

    # First pass: any literal text in known prompt fields.
    for field in _COMFY_PROMPT_INPUT_FIELDS:
        val = inputs.get(field)
        if isinstance(val, str):
            stripped = val.strip()
            if len(stripped) >= 4:
                return stripped

    # Second pass: collect EVERY literal string input (covers
    # concat / pipe nodes whose fields are text_a, text_b, str_1...).
    literal_pieces: list = []
    for field, val in inputs.items():
        if isinstance(val, str):
            stripped = val.strip()
            if len(stripped) >= 4:
                literal_pieces.append((field, stripped))
    if literal_pieces:
        # Heuristically sort: keep declaration order, but join with spaces.
        return " ".join(text for _f, text in literal_pieces)

    # Third pass: follow wired links upstream.
    for field, val in inputs.items():
        if _is_link_ref(val):
            upstream = _resolve_text_from_node(val[0], graph, visited, depth + 1)
            if upstream:
                return upstream

    return ""


def _resolve_encoder_text(node: dict, graph: dict) -> str:
    """For a single text-encoder node, return its prompt text.

    If the `text`/`positive`/`prompt` input is a literal string, return
    it directly. If it's a wired link, walk back through ShowText /
    TextMultiline / StringLiteral / concat nodes until a literal is
    found.
    """
    inputs = node.get("inputs") or {}
    if not isinstance(inputs, dict):
        return ""
    # Try every field name we know an encoder might use, in priority order.
    for field in _COMFY_PROMPT_INPUT_FIELDS:
        if field not in inputs:
            continue
        val = inputs[field]
        if isinstance(val, str):
            stripped = val.strip()
            if len(stripped) >= 4:
                return stripped
        elif _is_link_ref(val):
            text = _resolve_text_from_node(val[0], graph, visited=set(), depth=0)
            if text:
                return text
    return ""


def _node_matches(class_type: str, hints: tuple) -> bool:
    return any(hint in class_type for hint in hints)


def _extract_prompts_from_comfy_graph(graph_obj) -> list:
    """Walk a ComfyUI prompt graph and return *all* plausible prompts.

    `graph_obj` is the value of either the `prompt` chunk (a node dict
    keyed by node id) or a workflow object with a nested `prompt` key.
    Two strategies in order:

    1. Find every text-encoder node (CLIPTextEncode and friends), pull
       the prompt out of its text input — literal or wired. This is the
       most accurate: it directly answers "what prompt fed the model?"

    2. If no encoders found, fall back to harvesting literal text from
       any node whose class_type smells like a text source — for graphs
       that ship without their encoders (rare, but happens with
       split-workflow uploads).
    """
    if isinstance(graph_obj, str):
        try:
            graph_obj = json.loads(graph_obj)
        except Exception:
            return []
    if not isinstance(graph_obj, dict):
        return []

    if "prompt" in graph_obj and isinstance(graph_obj["prompt"], dict):
        graph_obj = graph_obj["prompt"]

    # Build a sane node map. Skip top-level keys whose value isn't a node.
    graph: dict = {}
    for nid, node in graph_obj.items():
        if isinstance(node, dict) and "class_type" in node:
            graph[str(nid)] = node

    # --- Strategy 1: every text encoder contributes its resolved prompt.
    encoder_prompts: list = []
    for nid, node in graph.items():
        ct = node.get("class_type") or ""
        if not _node_matches(ct, _COMFY_ENCODER_HINTS):
            continue
        text = _resolve_encoder_text(node, graph)
        if text:
            encoder_prompts.append(text)

    if encoder_prompts:
        seen = set()
        out: list = []
        for t in encoder_prompts:
            if t not in seen:
                seen.add(t)
                out.append(t)
        return out

    # --- Strategy 2: harvest literal text from known source nodes.
    candidates: list = []  # (priority, length, text)
    all_hints = _COMFY_PROMPT_CLASS_HINTS
    for _nid, node in graph.items():
        ct = node.get("class_type") or ""
        inputs = node.get("inputs") or {}
        if not isinstance(inputs, dict):
            continue
        priority = next(
            (i for i, hint in enumerate(all_hints) if hint in ct), 999
        )
        if priority == 999 and not _node_matches(ct, _COMFY_TEXT_SOURCE_HINTS):
            continue
        if priority == 999:
            priority = len(all_hints)  # text-source fallback
        for field in _COMFY_PROMPT_INPUT_FIELDS:
            val = inputs.get(field)
            if isinstance(val, str):
                stripped = val.strip()
                if len(stripped) >= 8:
                    candidates.append((priority, len(stripped), stripped))
                    break

    candidates.sort(key=lambda c: (c[0], -c[1]))
    seen = set()
    out: list = []
    for _, _, text in candidates:
        if text not in seen:
            seen.add(text)
            out.append(text)
    return out


def _looks_like_comfy_graph(s) -> bool:
    """True if `s` is a ComfyUI graph (API or UI format) we can parse.

    Used to distinguish JustRayzist / flat-text `prompt` chunks from a
    serialized ComfyUI prompt object — the former are literal prompts,
    the latter need graph walking. Accepts both raw strings (parsed) and
    already-parsed dicts.
    """
    obj = s
    if isinstance(obj, str):
        st = obj.lstrip()
        if not st.startswith("{"):
            return False
        try:
            obj = json.loads(st)
        except Exception:
            return False
    if not isinstance(obj, dict):
        return False
    # API format: dict keyed by node id -> {class_type, inputs}
    if "prompt" in obj and isinstance(obj["prompt"], dict):
        return True
    for v in obj.values():
        if isinstance(v, dict) and "class_type" in v:
            return True
    # UI format: {nodes: [...], links: [...], ...}
    nodes = obj.get("nodes")
    if isinstance(nodes, list) and nodes:
        for n in nodes:
            if isinstance(n, dict) and "type" in n:
                return True
    return False


def _extract_prompts_from_ui_workflow(obj) -> list:
    """Walk a ComfyUI *UI* workflow (nodes/links array shape) and harvest
    plausible prompts from widgets_values.

    Strategy:
      1. Encoder nodes (CLIPTextEncode*): widgets_values is a list where
         the leading string entries are the prompt(s).
      2. Text source nodes (Show Text, Text Multiline, easy wildcards,
         easy showAnything): also store their text in widgets_values,
         sometimes nested one level deep ([["..."]] for showAnything).
    """
    if isinstance(obj, str):
        try:
            obj = json.loads(obj)
        except Exception:
            return []
    if not isinstance(obj, dict):
        return []
    nodes = obj.get("nodes")
    if not isinstance(nodes, list):
        return []

    out: list = []
    seen: set = set()

    def _push(text: str) -> None:
        t = (text or "").strip()
        if len(t) < 4 or t in seen:
            return
        seen.add(t)
        out.append(t)

    def _harvest(values, encoder: bool) -> None:
        if not isinstance(values, list):
            return
        for v in values:
            if isinstance(v, str):
                _push(v)
            elif isinstance(v, list):
                for inner in v:
                    if isinstance(inner, str):
                        _push(inner)
            # ints/floats: skip silently (seed, guidance, etc.)

    encoder_hits = []
    source_hits = []
    has_wired_encoder = False
    for n in nodes:
        if not isinstance(n, dict):
            continue
        ct = n.get("type") or ""
        if not isinstance(ct, str):
            continue
        wv = n.get("widgets_values")
        if _node_matches(ct, _COMFY_ENCODER_HINTS):
            encoder_hits.append(wv)
            # Encoder with no usable string in widgets_values = its prompt
            # came in over a wire, so we must walk source nodes too.
            if not _has_meaningful_string(wv):
                has_wired_encoder = True
        elif _node_matches(ct, _COMFY_TEXT_SOURCE_HINTS):
            source_hits.append(wv)

    for wv in encoder_hits:
        _harvest(wv, encoder=True)
    # Pull from source nodes when no encoder produced text OR at least one
    # encoder was wired (its real prompt lives in an upstream node).
    if not out or has_wired_encoder:
        for wv in source_hits:
            _harvest(wv, encoder=False)
    return out


def _has_meaningful_string(values) -> bool:
    """True if `values` (a widgets_values list) contains any string ≥4 chars."""
    if not isinstance(values, list):
        return False
    for v in values:
        if isinstance(v, str) and len(v.strip()) >= 4:
            return True
        if isinstance(v, list):
            for inner in v:
                if isinstance(inner, str) and len(inner.strip()) >= 4:
                    return True
    return False


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

    # 2. PNG `prompt` chunk. ComfyUI writes a serialized graph here, but
    # some pipelines (JustRayzist etc.) write the literal prompt as a flat
    # string. Detect the shape before dispatching.
    comfy_prompt = info.get("prompt")
    if comfy_prompt:
        if isinstance(comfy_prompt, str) and not _looks_like_comfy_graph(comfy_prompt):
            literal = comfy_prompt.strip()
            if literal:
                prompts.append(literal)
        else:
            prompts.extend(_extract_prompts_from_comfy_graph(comfy_prompt))

    # 3. PNG `workflow` chunk. Two shapes possible:
    #    - API format: {<node_id>: {class_type, inputs}} (same as `prompt`)
    #    - UI format:  {nodes: [...], links: [...], groups: [...]}
    # Route UI format through a dedicated walker — `_extract_prompts_from_comfy_graph`
    # expects API format and would otherwise return the whole graph as a literal.
    comfy_workflow = info.get("workflow")
    if comfy_workflow:
        parsed = comfy_workflow
        if isinstance(parsed, str):
            try:
                parsed = json.loads(parsed)
            except Exception:
                parsed = None
        if isinstance(parsed, dict):
            if isinstance(parsed.get("nodes"), list):
                prompts.extend(_extract_prompts_from_ui_workflow(parsed))
            else:
                prompts.extend(_extract_prompts_from_comfy_graph(parsed))
        elif isinstance(comfy_workflow, str) and _looks_like_comfy_graph(comfy_workflow):
            prompts.extend(_extract_prompts_from_comfy_graph(comfy_workflow))
        elif isinstance(comfy_workflow, str):
            literal = comfy_workflow.strip()
            if literal:
                prompts.append(literal)

    # 3b. Generic flat-string prompt chunks: JustRayzist and similar tools
    # write multiple plain-text keys like `prompt_effective`, `prompt_original`,
    # `prompt_wildcard_resolved`, etc. Collect every string-valued key whose
    # name contains "prompt" and isn't one we already handled or a flag.
    _consumed = {"parameters", "Parameters", "prompt", "workflow"}
    for key, val in info.items():
        if not isinstance(key, str) or key in _consumed:
            continue
        kl = key.lower()
        if "prompt" not in kl:
            continue
        # Skip booleans-as-strings and counters.
        if kl.endswith("_enhanced") or kl.endswith("_count") or kl.endswith("_json"):
            continue
        if not isinstance(val, str):
            continue
        stripped = val.strip()
        if len(stripped) < 8:
            continue
        if stripped.lower() in ("true", "false", "none", "null"):
            continue
        prompts.append(stripped)

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


def _coerce_bool(val) -> bool:
    """ComfyUI sometimes hands BOOLEAN widgets through as 'true' / 'false'
    strings — those would coerce truthy under bool(). Normalize first."""
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return bool(val)
    if isinstance(val, str):
        return val.strip().lower() in ("true", "1", "yes", "on")
    return bool(val)


def _enumerate_images(folder: pathlib.Path, recurse: bool) -> list:
    """List image file paths under `folder`. Sorted for deterministic seeding.

    Uses os.walk for recursion so symlinks and permission errors on a
    single subtree don't abort the whole scan.
    """
    if not folder.is_dir():
        return []
    out: list = []
    if recurse:
        for dirpath, _dirnames, filenames in os.walk(folder, followlinks=False):
            for name in filenames:
                if name.lower().endswith(_SUPPORTED_EXT):
                    out.append(os.path.join(dirpath, name))
    else:
        try:
            for entry in folder.iterdir():
                try:
                    if entry.is_file() and entry.suffix.lower() in _SUPPORTED_EXT:
                        out.append(str(entry))
                except OSError:
                    continue
        except OSError:
            return []
    out.sort()
    return out


def _file_list(folder: pathlib.Path, recurse: bool, refresh: bool = False) -> list:
    key = (str(folder.resolve()) if folder.exists() else str(folder), bool(recurse))
    if not refresh and key in _FILE_LIST_CACHE:
        return _FILE_LIST_CACHE[key]
    lst = _enumerate_images(folder, recurse)
    _FILE_LIST_CACHE[key] = lst
    print(
        f"[RayLocalScraper] scanned {folder} (recurse={recurse}) -> "
        f"{len(lst)} images"
    )
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
                "prompt_best_try": ("BOOLEAN", {"default": False}),
                "seed": ("INT", {"default": -1, "min": -1, "max": 2**31 - 1}),
            },
            "optional": {
                "refresh_listing": ("BOOLEAN", {"default": False}),
            },
            "hidden": {"node_id": "UNIQUE_ID"},
        }

    RETURN_TYPES = ("STRING", "STRING", "IMAGE", "STRING")
    RETURN_NAMES = ("prompt_single", "prompt_multiline", "image", "image_path")
    # ComfyUI batches list outputs: when an image carries multiple prompts,
    # each output is emitted as a parallel list so the workflow can iterate
    # over every prompt. The image/path entries are repeated per prompt so
    # downstream nodes see (prompt_i, image, path) tuples.
    OUTPUT_IS_LIST = (True, True, True, True)
    FUNCTION = "process"
    CATEGORY = "Ray/Prompts📝"

    @classmethod
    def IS_CHANGED(cls, *args, **kwargs):
        return float("nan")

    def process(
        self,
        folder,
        recurse_subfolders,
        skip_no_prompt,
        prompt_best_try,
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

        recurse = _coerce_bool(recurse_subfolders)
        refresh = _coerce_bool(refresh_listing)
        skip_no_prompt = _coerce_bool(skip_no_prompt)
        best_try = _coerce_bool(prompt_best_try)
        paths = _file_list(folder_p, recurse, refresh=refresh)
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

        image_tensor = _pil_to_tensor(pil_image)
        if image_tensor is None:
            image_tensor = _black_tensor()
        path_str = os.fspath(chosen_path)

        if not chosen_prompts:
            # No prompt found — emit a single empty entry so downstream
            # nodes still see a list of length 1 (matching the image + path).
            return ([""], [""], [image_tensor], [path_str])

        if best_try and len(chosen_prompts) > 1:
            # Collapse to a single best candidate. Heuristic: longest by
            # character count — usually the most descriptive / final prompt
            # after wildcard expansion and enhancement.
            chosen_prompts = [max(chosen_prompts, key=len)]

        prompt_multiline_list = list(chosen_prompts)
        prompt_single_list = [
            re.sub(r"\s+", " ", p).strip() for p in chosen_prompts
        ]
        # Parallel-broadcast the image + path across every prompt.
        n = len(chosen_prompts)
        image_list = [image_tensor] * n
        path_list = [path_str] * n

        return (prompt_single_list, prompt_multiline_list, image_list, path_list)
