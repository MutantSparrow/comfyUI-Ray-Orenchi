"""Ray's Local: Folder Image Scraper.

Walks a local folder (optionally recursing into subfolders) and serves
images one at a time, attempting to extract any generation prompt found
in the image's metadata. Designed as a functional sibling to the
PromptDexter and CivitAI scrapers but for local files.

Prompt extraction sources, in priority order:
  1. PNG `parameters` chunk (Automatic1111 / Forge native format, or a
     JSON blob from SwarmUI / InvokeAI when the writer used that key).
  2. PNG `prompt` chunk (ComfyUI serialized graph, OR a flat literal
     string when written by JustRayzist / minimal ComfyUI plugins).
  3. PNG `workflow` chunk — API format (node dict) or UI format
     (nodes/links array).
  4. Every other `info[]` key whose name looks prompt-shaped
     (`prompt*`, `positive*`, `caption`, `description`, `comment`,
     `sui_image_params`, `invokeai_metadata`, `sd-metadata`,
     `novelai_metadata`, `dream`, `Software` on Fooocus, `title`,
     `notes`). Values may be plain text or JSON.
  5. EXIF: UserComment (37510), ImageDescription (270), XPComment
     (40092), XPSubject (40095), XPTitle (40091), XPKeywords (40094).
  6. Sidecar `<image>.txt` in the same directory.

Every candidate is passed through `_valid_prompt_candidate` which rejects
strings that look like filesystem paths (drive letters, backslash-heavy
strings with no spaces, tail-image-extension paths). This is what keeps
random ``C:\\loras\\foo.safetensors``-shaped fields from leaking through
as prompts.

When multiple positive prompts are found inside a single image, every
output is emitted as a ComfyUI list — one entry per prompt — so
downstream nodes iterate over each prompt independently.

`prompt_best_try` collapses to a single prompt per image (the longest
one, treated as the most descriptive final prompt). When on, the scraper
also remembers the last best-try prompt it emitted for this node and,
if the current pick would emit the same prompt again, advances to the
next image until a new best-try prompt is found or the pool runs out.

Outputs (all OUTPUT_IS_LIST = True):
  STRING prompt_single     — each prompt collapsed to one line.
  STRING prompt_multiline  — each prompt with its newlines preserved.
  IMAGE  image             — BHWC float32 [0,1] tensor.
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

_FILE_LIST_CACHE: dict = {}     # (folder, recurse) -> sorted list[str]
_RECENT_BY_NODE: dict = {}      # node_key -> deque of recently picked paths
_RECENT_BEST_BY_NODE: dict = {}   # node_key -> deque of recently emitted best-try prompts
_BEST_HISTORY_MAX = 20            # skip a pick if its best prompt is in the last N emits
_CACHE_MAX = 20

# ComfyUI class-name substrings that mark a node as a text encoder we
# want to feed a prompt into. If its text input is wired instead of a
# literal, we walk backwards through the graph.
_COMFY_ENCODER_HINTS = (
    "CLIPTextEncode",
    "BNK_CLIPTextEncodeAdvanced",
    "CLIPTextEncodeFlux",
    "CLIPTextEncodeSDXL",
    "smZ CLIPTextEncode",
    "AdvancedCLIPTextEncode",
    "CLIPTextEncodeSD3",
    "T5TextEncode",
    "ImpactWildcardEncode",
)

# Class-name substrings that mark a node as a *source* of free-form
# prompt text. Used both for backwards-walking wired encoders and as a
# fallback when a graph ships without any encoder.
_COMFY_TEXT_SOURCE_HINTS = (
    "Text Multiline",
    "TextMultiline",
    "ShowText",
    "Show Text",
    "Show_text",
    "ShowAnything",
    "String Literal",
    "StringLiteral",
    "String Constant",
    "String",
    "PrimitiveNode",
    "Text Concatenate",
    "TextConcatenate",
    "Text Concat",
    "TextConcat",
    "Text Combine",
    "TextCombine",
    "StringFunction",
    "easy showAnything",
    "easy textConcat",
    "easy positive",
    "DPRandomGenerator",
    "Wildcard",
    "PromptComposer",
    "Prompt",
    "Text",
    "Note",
    "MarkdownNote",
)

# Field names on a node's `inputs` dict that typically hold prompt text.
_COMFY_PROMPT_INPUT_FIELDS = (
    "text", "text_g", "text_l", "text_positive",
    "string", "String",
    "positive", "prompt", "Prompt", "Text",
    "populated_text", "wildcard_text",
    "value",
)

# Cap for how deep the graph walker chases wired links before giving up.
_COMFY_MAX_LINK_DEPTH = 8

# `info[]` key names (case-insensitive) that are likely to carry prompt
# text. Broad on purpose — the path/JSON filters downstream stop paths,
# software strings, and numeric flags from leaking through.
_INFO_KEY_HINTS = (
    "prompt", "positive", "caption", "description", "comment",
    "usercomment", "notes", "dream",
    "sd-metadata", "sui_image_params", "invokeai_metadata",
    "novelai_metadata", "fooocus", "params", "settings",
    "title",
)

# Info keys we always consume via a dedicated path — don't double-emit them
# in the generic sweep.
_INFO_KEY_CONSUMED = {"parameters", "Parameters", "prompt", "workflow"}


# ---------------------------------------------------------------------------
# Prompt validity / rejection heuristics
# ---------------------------------------------------------------------------


_PATH_START_RE = re.compile(
    r"""^\s*(?:
        [A-Za-z]:[\\/]         |    # windows drive: C:\ or C:/
        \\\\[^\\]+\\           |    # UNC \\server\share
        \.{1,2}[\\/]           |    # ./  ../
        ~[\\/]                 |    # ~/
        /[A-Za-z0-9._-]+/           # unix path root
    )""",
    re.VERBOSE,
)
_TRAILING_IMAGE_EXT_RE = re.compile(
    r"[\\/][^\\/]+\.(png|jpe?g|webp|bmp|tiff?|gif|mp4|mov|avi|"
    r"safetensors|pt|ckpt|json|txt)\b",
    re.IGNORECASE,
)
_MODEL_FILE_ONLY_RE = re.compile(
    r"^[\w.\-]+\.(safetensors|ckpt|pt|bin|onnx)$",
    re.IGNORECASE,
)


def _looks_like_path(s: str) -> bool:
    """True if `s` looks like a filesystem path rather than a prompt.

    Only rejects strings whose *entire content* reads as a path — a real
    prompt that merely references `embedding:embeddings/foo.pt` inside a
    longer text will still pass, because the separator density check is
    gated on the string having very few spaces.
    """
    if not s:
        return False
    if "\n" in s:
        # Real prompts often span lines; paths do not. A newline is a
        # strong signal we're looking at prose.
        return False

    stripped = s.strip()
    if not stripped:
        return False

    if _PATH_START_RE.match(stripped):
        return True

    # Model / weight filename all by itself: `something.safetensors`.
    if _MODEL_FILE_ONLY_RE.match(stripped):
        return True

    seps = stripped.count("\\") + stripped.count("/")
    spaces = stripped.count(" ")

    # Heavy separators, no whitespace: bare path.
    if seps >= 2 and spaces == 0:
        return True

    # Something like `models\stable-diffusion\foo.safetensors` — some
    # separators, only a couple of spaces, and an image/model ext tail.
    if seps >= 2 and spaces < 3 and _TRAILING_IMAGE_EXT_RE.search(stripped):
        return True

    return False


def _valid_prompt_candidate(s: str, min_len: int = 4) -> bool:
    """True if `s` is worth returning as a prompt candidate."""
    if not isinstance(s, str):
        return False
    stripped = s.strip()
    if len(stripped) < min_len:
        return False
    if stripped.lower() in ("true", "false", "none", "null", "nan"):
        return False
    # Pure numeric / boolean flag strings.
    if re.fullmatch(r"[-+]?\d+(\.\d+)?", stripped):
        return False
    if _looks_like_path(stripped):
        return False
    return True


def _clean_candidates(items) -> list:
    """De-duplicate and drop invalid entries while preserving order."""
    seen: set = set()
    out: list = []
    for it in items or []:
        s = (it or "").strip() if isinstance(it, str) else ""
        if not _valid_prompt_candidate(s):
            continue
        if s in seen:
            continue
        seen.add(s)
        out.append(s)
    return out


# ---------------------------------------------------------------------------
# Prompt extractors
# ---------------------------------------------------------------------------


def _strip_a1111(blob: str) -> str:
    """Return only the positive portion of an A1111 parameters block."""
    if not isinstance(blob, str):
        return ""
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


def _node_matches(class_type: str, hints: tuple) -> bool:
    if not isinstance(class_type, str):
        return False
    return any(hint in class_type for hint in hints)


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
            if _valid_prompt_candidate(stripped):
                return stripped

    # Second pass: collect every literal string input that passes the
    # prompt-candidate filter (covers concat / pipe nodes whose fields are
    # text_a, text_b, str_1...).
    literal_pieces: list = []
    for field, val in inputs.items():
        if isinstance(val, str):
            stripped = val.strip()
            if _valid_prompt_candidate(stripped):
                literal_pieces.append(stripped)
    if literal_pieces:
        return " ".join(literal_pieces)

    # Third pass: follow wired links upstream.
    for field, val in inputs.items():
        if _is_link_ref(val):
            upstream = _resolve_text_from_node(val[0], graph, visited, depth + 1)
            if upstream:
                return upstream

    return ""


def _resolve_encoder_text(node: dict, graph: dict) -> str:
    """For a single text-encoder node, return its prompt text.

    If a known prompt input is a literal string, return it directly. If
    it's a wired link, walk back through ShowText / TextMultiline /
    StringLiteral / concat nodes until a literal is found.
    """
    inputs = node.get("inputs") or {}
    if not isinstance(inputs, dict):
        return ""
    for field in _COMFY_PROMPT_INPUT_FIELDS:
        if field not in inputs:
            continue
        val = inputs[field]
        if isinstance(val, str):
            stripped = val.strip()
            if _valid_prompt_candidate(stripped):
                return stripped
        elif _is_link_ref(val):
            text = _resolve_text_from_node(val[0], graph, visited=set(), depth=0)
            if text:
                return text
    return ""


def _extract_prompts_from_comfy_graph(graph_obj) -> list:
    """Walk a ComfyUI prompt graph and return every plausible prompt.

    `graph_obj` is the value of either the `prompt` chunk (a node dict
    keyed by node id) or a workflow object with a nested `prompt` key.

    Strategy 1: every text encoder contributes its resolved prompt.
    Strategy 2 (fallback): harvest literal text from source nodes when
    no encoder produced anything usable.
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
        return _clean_candidates(encoder_prompts)

    # --- Strategy 2: harvest from source nodes.
    candidates: list = []  # (priority, length, text)
    for _nid, node in graph.items():
        ct = node.get("class_type") or ""
        inputs = node.get("inputs") or {}
        if not isinstance(inputs, dict):
            continue
        if not _node_matches(ct, _COMFY_TEXT_SOURCE_HINTS):
            continue
        priority = next(
            (i for i, hint in enumerate(_COMFY_TEXT_SOURCE_HINTS) if hint in ct),
            len(_COMFY_TEXT_SOURCE_HINTS),
        )
        for field in _COMFY_PROMPT_INPUT_FIELDS:
            val = inputs.get(field)
            if isinstance(val, str):
                stripped = val.strip()
                if _valid_prompt_candidate(stripped, min_len=8):
                    candidates.append((priority, len(stripped), stripped))
                    break

    candidates.sort(key=lambda c: (c[0], -c[1]))
    return _clean_candidates(text for _, _, text in candidates)


def _looks_like_comfy_graph(s) -> bool:
    """True if `s` is a ComfyUI graph (API or UI format) we can parse."""
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
    if "prompt" in obj and isinstance(obj["prompt"], dict):
        return True
    for v in obj.values():
        if isinstance(v, dict) and "class_type" in v:
            return True
    nodes = obj.get("nodes")
    if isinstance(nodes, list) and nodes:
        for n in nodes:
            if isinstance(n, dict) and "type" in n:
                return True
    return False


def _extract_prompts_from_ui_workflow(obj) -> list:
    """Walk a ComfyUI UI workflow (nodes/links array) and harvest prompts
    from `widgets_values`.
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
        if not _valid_prompt_candidate(t):
            return
        if t in seen:
            return
        seen.add(t)
        out.append(t)

    def _harvest(values) -> None:
        if not isinstance(values, list):
            return
        for v in values:
            if isinstance(v, str):
                _push(v)
            elif isinstance(v, list):
                for inner in v:
                    if isinstance(inner, str):
                        _push(inner)
                    elif isinstance(inner, dict):
                        # easy showAnything can wrap the string in a dict.
                        for iv in inner.values():
                            if isinstance(iv, str):
                                _push(iv)
            elif isinstance(v, dict):
                for iv in v.values():
                    if isinstance(iv, str):
                        _push(iv)

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
            if not _has_meaningful_string(wv):
                has_wired_encoder = True
        elif _node_matches(ct, _COMFY_TEXT_SOURCE_HINTS):
            source_hits.append(wv)

    for wv in encoder_hits:
        _harvest(wv)
    if not out or has_wired_encoder:
        for wv in source_hits:
            _harvest(wv)
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


# EXIF tag numbers we mine for prompt-shaped fields, in order.
_EXIF_TEXT_TAGS: tuple = (
    (37510, "UserComment"),
    (270,   "ImageDescription"),
    (40092, "XPComment"),
    (40095, "XPSubject"),
    (40091, "XPTitle"),
    (40094, "XPKeywords"),
)


def _decode_exif_bytes(raw: bytes, tag_id: int) -> str:
    """Decode a raw EXIF bytes value into a plain string."""
    if not isinstance(raw, bytes):
        return ""
    # UserComment uses an 8-byte character-code header.
    if tag_id == 37510:
        if raw.startswith(b"UNICODE\0"):
            try:
                return raw[8:].decode("utf-16-be", errors="replace").strip("\x00").strip()
            except Exception:
                try:
                    return raw[8:].decode("utf-16-le", errors="replace").strip("\x00").strip()
                except Exception:
                    return ""
        if raw.startswith(b"ASCII\0\0\0"):
            return raw[8:].decode("ascii", errors="replace").strip("\x00").strip()
        return raw.decode("utf-8", errors="replace").strip("\x00").strip()
    # XP* tags are Windows-style UTF-16LE, null-terminated.
    if tag_id in (40091, 40092, 40094, 40095):
        try:
            return raw.decode("utf-16-le", errors="replace").strip("\x00").strip()
        except Exception:
            pass
    return raw.decode("utf-8", errors="replace").strip("\x00").strip()


def _read_exif_user_comment(pil_image: Image.Image) -> str:
    """EXIF UserComment (tag 37510) from a PIL image, decoded to plain text."""
    try:
        exif = pil_image.getexif()
    except Exception:
        return ""
    if not exif:
        return ""
    raw = exif.get(37510)
    if raw is None:
        return ""
    if isinstance(raw, bytes):
        return _decode_exif_bytes(raw, 37510)
    return str(raw).strip()


def _read_exif_text_tags(pil_image: Image.Image) -> list:
    """Return every prompt-shaped string found in EXIF text tags."""
    try:
        exif = pil_image.getexif()
    except Exception:
        return []
    if not exif:
        return []
    out: list = []
    for tag_id, _name in _EXIF_TEXT_TAGS:
        raw = exif.get(tag_id)
        if raw is None:
            continue
        text = _decode_exif_bytes(raw, tag_id) if isinstance(raw, bytes) else str(raw).strip()
        if not text:
            continue
        # A1111 sometimes packs full parameters into UserComment.
        stripped = _strip_a1111(text) if "Negative prompt:" in text or "\nSteps:" in text else text
        out.append(stripped.strip())
    return out


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


def _walk_json_for_prompts(obj, depth: int = 0) -> list:
    """Recursively pull prompt-shaped strings out of a nested JSON object.

    Used for SwarmUI / InvokeAI / NovelAI metadata blobs, which store the
    positive prompt at some key like `prompt` or `sui_image_params.prompt`.
    """
    if depth > 6 or obj is None:
        return []
    out: list = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            kl = str(k).lower()
            # Explicit prompt-ish keys pull their values directly.
            if any(hint in kl for hint in ("prompt", "positive", "caption",
                                            "description", "text")):
                if isinstance(v, str) and _valid_prompt_candidate(v):
                    out.append(v.strip())
                elif isinstance(v, (dict, list)):
                    out.extend(_walk_json_for_prompts(v, depth + 1))
            elif isinstance(v, (dict, list)):
                out.extend(_walk_json_for_prompts(v, depth + 1))
    elif isinstance(obj, list):
        for v in obj:
            if isinstance(v, (dict, list)):
                out.extend(_walk_json_for_prompts(v, depth + 1))
            elif isinstance(v, str) and _valid_prompt_candidate(v):
                out.append(v.strip())
    return out


def _harvest_info_value(key: str, val) -> list:
    """Pull prompt candidates from a single `info[]` entry."""
    if not isinstance(key, str):
        return []
    kl = key.lower()
    if not any(hint in kl for hint in _INFO_KEY_HINTS):
        return []
    # Skip obvious flags / counters we don't want to smuggle in as prompts.
    if kl.endswith(("_enhanced", "_count", "_json", "_seed", "_steps",
                    "_cfg", "_size", "_flag", "_enabled")):
        return []

    if isinstance(val, str):
        stripped = val.strip()
        if not stripped:
            return []
        # JSON-looking string: try to parse and harvest inner prompt keys.
        if stripped[:1] in ("{", "[") and stripped[-1:] in ("}", "]"):
            try:
                parsed = json.loads(stripped)
            except Exception:
                parsed = None
            if parsed is not None:
                inner = _walk_json_for_prompts(parsed)
                if inner:
                    return inner
        # A1111-shaped blob under some non-`parameters` key.
        if "Negative prompt:" in stripped or "\nSteps:" in stripped:
            pos = _strip_a1111(stripped)
            return [pos] if pos else []
        return [stripped]
    if isinstance(val, (dict, list)):
        return _walk_json_for_prompts(val)
    return []


def extract_prompts(image_path: pathlib.Path, pil_image: Image.Image) -> list:
    """Return a list of positive prompts found in the image's metadata."""
    info = pil_image.info or {}

    prompts: list = []

    # 1. A1111 `parameters` (may also carry a JSON blob from SwarmUI /
    # InvokeAI when they piggyback on the same key).
    params_blob = info.get("parameters") or info.get("Parameters")
    if isinstance(params_blob, str) and params_blob.strip():
        stripped = params_blob.strip()
        if stripped[:1] in ("{", "[") and stripped[-1:] in ("}", "]"):
            try:
                parsed = json.loads(stripped)
                prompts.extend(_walk_json_for_prompts(parsed))
            except Exception:
                positive = _strip_a1111(stripped)
                if positive:
                    prompts.append(positive)
        else:
            positive = _strip_a1111(stripped)
            if positive:
                prompts.append(positive)

    # 2. PNG `prompt` chunk (graph or literal).
    comfy_prompt = info.get("prompt")
    if comfy_prompt:
        if isinstance(comfy_prompt, str) and not _looks_like_comfy_graph(comfy_prompt):
            literal = comfy_prompt.strip()
            if literal:
                prompts.append(literal)
        else:
            prompts.extend(_extract_prompts_from_comfy_graph(comfy_prompt))

    # 3. PNG `workflow` chunk (API or UI shape).
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

    # 4. Every other info[] key that looks prompt-shaped.
    for key, val in info.items():
        if not isinstance(key, str) or key in _INFO_KEY_CONSUMED:
            continue
        prompts.extend(_harvest_info_value(key, val))

    # 5. EXIF text tags (UserComment, ImageDescription, XP*).
    exif_texts = _read_exif_text_tags(pil_image)
    prompts.extend(exif_texts)

    # 6. Sidecar .txt file — only when nothing else survived the filter.
    cleaned = _clean_candidates(prompts)
    if not cleaned:
        sidecar = _read_sidecar(image_path)
        if sidecar:
            cleaned = _clean_candidates([sidecar])

    return cleaned


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
    """List image file paths under `folder`. Sorted for deterministic seeding."""
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
    _RECENT_BEST_BY_NODE.clear()


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


def _select_path(paths: list, recent: deque, rng, deterministic: bool,
                 excluded=None) -> str:
    """Pick one path from `paths`.

    Determinism contract:
    - When `deterministic` is True, the LRU `recent` queue is IGNORED —
      freezing the seed must produce the same pick every time this node
      runs, no matter what previous picks put into the queue. The seeded
      shuffle order is walked and the first entry NOT in `excluded` is
      returned. `excluded` is a per-call set the caller uses to advance
      within one process() invocation (best-try dedup, skip_no_prompt).
    - When `deterministic` is False (seed=-1), the `recent` LRU is used
      to avoid immediate consecutive repeats across runs.
    """
    if not paths:
        raise RuntimeError("no images found in folder")
    if excluded is None:
        excluded = set()
    if deterministic:
        indices = list(range(len(paths)))
        rng.shuffle(indices)
        for i in indices:
            if paths[i] not in excluded:
                return paths[i]
        return paths[indices[0]]
    for _ in range(50):
        pick = rng.choice(paths)
        if pick not in recent and pick not in excluded:
            return pick
    return rng.choice(paths)


# ---------------------------------------------------------------------------
# Node class
# ---------------------------------------------------------------------------


class RayLocalScraper:
    """Pick a random image from a local folder and extract its prompts."""

    DESCRIPTION = (
        "Random image from a local folder, with any generation prompt "
        "found in its metadata. Reads A1111 `parameters`, ComfyUI "
        "`prompt` / `workflow` graphs (walking wired ShowText / Text "
        "Multiline / String Literal chains up to 8 hops), JPEG/WEBP "
        "EXIF UserComment, and `<image>.txt` sidecars.\n\n"
        "Seed-deterministic with a 20-entry LRU to avoid consecutive "
        "repeats. `prompt_best_try` collapses each image to its single "
        "best prompt AND skips a pick if it repeats the previous best. "
        "Multi-prompt images emit one list entry per prompt across all "
        "outputs."
    )

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "folder": ("STRING", {
                    "default": "",
                    "multiline": False,
                    "placeholder": "Absolute path to a folder of images",
                    "tooltip": "Absolute path to a folder of images.",
                }),
                "recurse_subfolders": ("BOOLEAN", {
                    "default": False,
                    "tooltip": "Walk every subdirectory under folder.",
                }),
                "skip_no_prompt": ("BOOLEAN", {
                    "default": False,
                    "tooltip": "Skip images whose metadata yields no prompt.",
                }),
                "prompt_best_try": ("BOOLEAN", {
                    "default": False,
                    "tooltip": "Collapse to one prompt per image, and skip repeats of the last emit.",
                }),
                "seed": ("INT", {
                    "default": -1, "min": -1, "max": 2**31 - 1,
                    "tooltip": "-1 for random; any >=0 value is reproducible.",
                }),
            },
            "optional": {
                "refresh_listing": ("BOOLEAN", {
                    "default": False,
                    "tooltip": "Force a re-scan of the folder before selecting.",
                }),
            },
            "hidden": {"node_id": "UNIQUE_ID"},
        }

    RETURN_TYPES = ("STRING", "STRING", "IMAGE", "STRING")
    RETURN_NAMES = ("prompt_single", "prompt_multiline", "image", "image_path")
    OUTPUT_TOOLTIPS = (
        "Whitespace-collapsed single-line prompt (list, one per prompt found).",
        "Prompt with original newlines preserved (list).",
        "Image tensor, repeated across every prompt entry.",
        "Absolute path of the chosen file, repeated across every prompt entry.",
    )
    OUTPUT_IS_LIST = (True, True, True, True)
    FUNCTION = "process"
    CATEGORY = "👑 Ray/📝 Prompts"

    @classmethod
    def IS_CHANGED(cls, *args, **kwargs):
        return float("nan")

    def process(
        self,
        folder,
        recurse_subfolders,
        skip_no_prompt,
        seed,
        prompt_best_try=False,
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
        recent_best = _RECENT_BEST_BY_NODE.setdefault(
            node_key, deque(maxlen=_BEST_HISTORY_MAX)
        )

        # Loop enabled whenever we might need to keep looking:
        # - skip_no_prompt: keep trying until we find one with a prompt
        # - best_try:       keep trying while the best-try prompt is in the
        #                   recent-best deque (not just the very last one —
        #                   otherwise the node flip-flops A/B/A/B forever
        #                   when the pool only has two distinct prompts).
        need_loop = skip_no_prompt or best_try
        max_attempts = min(len(paths), 50) if need_loop else 1
        attempts = 0
        chosen_path: Optional[str] = None
        chosen_prompts: list = []
        pil_image: Optional[Image.Image] = None

        candidates_tried: set = set()
        while attempts < max_attempts:
            attempts += 1
            try:
                pick = _select_path(
                    paths, recent, rng, deterministic,
                    excluded=candidates_tried,
                )
            except RuntimeError:
                break

            if pick in candidates_tried:
                # Fallback repeat (pool exhausted) — bail rather than spin.
                break
            candidates_tried.add(pick)

            try:
                candidate_img = Image.open(pick)
                candidate_img.load()
            except Exception as e:
                print(f"[RayLocalScraper] cannot open {pick}: {e}")
                continue

            prompts = extract_prompts(pathlib.Path(pick), candidate_img)

            # No prompt case.
            if not prompts:
                if skip_no_prompt:
                    recent.append(pick)
                    continue
                chosen_path = pick
                chosen_prompts = prompts
                pil_image = candidate_img
                break

            # Best-try dedup: if the top prompt is anywhere in the last
            # N emits from this node, advance. Deque avoids the A/B/A/B
            # flip-flop that a single-slot "last emit" comparison caused.
            if best_try:
                best = max(prompts, key=len)
                if best and best in recent_best:
                    recent.append(pick)
                    continue
                chosen_path = pick
                chosen_prompts = [best]
                pil_image = candidate_img
                recent_best.append(best)
                break

            chosen_path = pick
            chosen_prompts = prompts
            pil_image = candidate_img
            break

        if chosen_path is None or pil_image is None:
            if skip_no_prompt and best_try:
                raise RuntimeError(
                    f"no image with a new best-try prompt in {folder_p} "
                    f"(tried {attempts})"
                )
            if skip_no_prompt:
                raise RuntimeError(
                    f"no images with extractable prompts in {folder_p} "
                    f"(tried {attempts})"
                )
            if best_try:
                raise RuntimeError(
                    f"no image with a new best-try prompt in {folder_p} "
                    f"(tried {attempts})"
                )
            raise RuntimeError(f"could not open any image in {folder_p}")

        recent.append(chosen_path)

        image_tensor = _pil_to_tensor(pil_image)
        if image_tensor is None:
            image_tensor = _black_tensor()
        path_str = os.fspath(chosen_path)

        try:
            from _common import send_preview
        except ImportError:
            try:
                from ._common import send_preview  # type: ignore
            except ImportError:
                send_preview = None  # type: ignore
        if send_preview is not None:
            send_preview(node_id, path_str)

        if not chosen_prompts:
            return ([""], [""], [image_tensor], [path_str])

        # `best_try` already collapsed above; keep the guard for the
        # (rare) path where prompts came from an unfiltered branch.
        if best_try and len(chosen_prompts) > 1:
            chosen_prompts = [max(chosen_prompts, key=len)]

        prompt_multiline_list = list(chosen_prompts)
        prompt_single_list = [
            re.sub(r"\s+", " ", p).strip() for p in chosen_prompts
        ]
        n = len(chosen_prompts)
        image_list = [image_tensor] * n
        path_list = [path_str] * n

        return (prompt_single_list, prompt_multiline_list, image_list, path_list)
