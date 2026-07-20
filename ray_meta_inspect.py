"""Ray's Local: Metadata Inspector / Pasteboard.

Read any PNG/JPEG/WEBP and expose every known metadata chunk as separate
string outputs, OR write a tensor back to disk with metadata chunks embedded.

Two modes (toggled by the `mode` widget):
  • Inspect — read from `path`, parse, expose fields.
  • Embed   — take IMAGE + metadata_json + output_path, write a new PNG with
              chunks (parameters, prompt, JustRayzist-style flat keys),
              then re-parse so the same outputs are available downstream.

Inspect sources (priority for shared fields):
  1. PNG `parameters` chunk (A1111 / Forge format).
  2. PNG `prompt` chunk (ComfyUI prompt graph — API format).
  3. PNG `workflow` chunk (ComfyUI workflow — UI format with `nodes` array).
  4. EXIF UserComment (A1111 also writes here on JPEG/WEBP).
  5. JustRayzist-style flat string keys (prompt, prompt_effective, etc.).
  6. XMP packet (lightweight regex extraction).

Outputs:
  prompt_positive, prompt_negative, seed, steps, cfg, sampler, model,
  loras_json, width, height, raw_metadata_json, image
"""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import re
from typing import Optional

import numpy as np
from PIL import Image, PngImagePlugin

try:
    import torch
except ImportError:
    torch = None

# Optional: ComfyUI's path resolver. Lets the node accept the annotated
# "name [input]" / "name [output]" / "name [temp]" filename format that the
# /upload/image endpoint returns, plus plain relative `input/foo.png` paths
# when ComfyUI's CWD differs from this node-pack's CWD.
try:
    import folder_paths  # type: ignore[import-not-found]
except ImportError:
    folder_paths = None  # type: ignore[assignment]

try:
    from .ray_local_scraper import (
        _strip_a1111,
        _extract_prompts_from_comfy_graph,
        _extract_prompts_from_ui_workflow,
        _looks_like_comfy_graph,
        _read_exif_user_comment,
    )
except ImportError:
    from ray_local_scraper import (  # type: ignore[no-redef]
        _strip_a1111,
        _extract_prompts_from_comfy_graph,
        _extract_prompts_from_ui_workflow,
        _looks_like_comfy_graph,
        _read_exif_user_comment,
    )


MODE_INSPECT = "Inspect"
MODE_EMBED = "Embed"
MODES = [MODE_INSPECT, MODE_EMBED]


_ANNOTATED_RE = re.compile(r"^(.*)\s*\[(input|output|temp)\]\s*$")

# Pairs of quote characters that may wrap a copied path. Windows Explorer's
# "Copy as path" uses ASCII double quotes; some locales paste guillemets or
# curly quotes instead.
_QUOTE_PAIRS = (
    ('"', '"'),
    ("'", "'"),
    ("«", "»"),
    ("“", "”"),  # “ ”
    ("‘", "’"),  # ‘ ’
    ("`", "`"),
)


def _strip_path_quotes(s: str) -> str:
    """Strip one matched pair of surrounding quote characters, if present."""
    if not s:
        return s
    for opener, closer in _QUOTE_PAIRS:
        if len(s) >= 2 and s[0] == opener and s[-1] == closer:
            return s[1:-1].strip()
    return s


def _resolve_path(path_str: str) -> pathlib.Path:
    """Resolve a user-supplied path. Handles three shapes:

      1. An absolute path or a path that already exists relative to CWD.
      2. ComfyUI's annotated `name [input]` / `name [output]` / `name [temp]`
         filename format returned by the /upload/image endpoint.
      3. Plain `input/<name>` / `output/<name>` / `temp/<name>` relative paths,
         which we look up via `folder_paths` against ComfyUI's actual roots so
         the node works even when the process CWD differs from ComfyUI's.

    Returns the first candidate that resolves to an existing file. Falls back
    to the original `pathlib.Path(path_str)` so `inspect_file` can surface a
    clear "not a file" error if none worked.
    """
    raw = (path_str or "").strip()
    # Windows Explorer's "Copy as path" wraps the path with `"…"`. macOS and
    # some shells use guillemets / smart quotes. Strip a single matched pair
    # of any common quote characters so a literal paste resolves cleanly.
    raw = _strip_path_quotes(raw)
    if not raw:
        return pathlib.Path(raw)

    # 1. Direct
    direct = pathlib.Path(raw).expanduser()
    if direct.is_file():
        return direct

    # 2. Annotated "name [input]"
    m = _ANNOTATED_RE.match(raw)
    sub = ""
    name = None
    folder_type = None
    if m:
        name = m.group(1).strip()
        folder_type = m.group(2)
        # The "name" portion may itself contain a forward-slash subfolder.
        if "/" in name or "\\" in name:
            sub_path = pathlib.Path(name)
            sub = str(sub_path.parent)
            name = sub_path.name
    elif raw.lower().startswith(("input/", "input\\", "output/", "output\\",
                                  "temp/", "temp\\")):
        # 3. `input/<name>` style — strip the prefix and route via folder_paths.
        head = raw.split("/", 1)[0].split("\\", 1)[0].lower()
        rest = pathlib.Path(raw[len(head) + 1:])
        folder_type = head
        name = rest.name
        sub = str(rest.parent) if str(rest.parent) != "." else ""

    if folder_type and name and folder_paths is not None:
        try:
            if folder_type == "input":
                base = folder_paths.get_input_directory()
            elif folder_type == "output":
                base = folder_paths.get_output_directory()
            else:
                base = folder_paths.get_temp_directory()
        except Exception:
            base = None
        if base:
            candidate = pathlib.Path(base) / sub / name if sub else pathlib.Path(base) / name
            if candidate.is_file():
                return candidate

    return direct


_A1111_NEG_RE = re.compile(r"\nNegative prompt:\s*(.*?)(?=\n[A-Z][a-z]+ ?[A-Za-z]*:|$)", re.DOTALL)
_A1111_SCALAR_RE = re.compile(r"(?:^|[\n,])\s*([A-Z][A-Za-z][A-Za-z ]*?):\s*([^,\n]+)")
_XMP_TAG_RE = re.compile(r"<(?:dc|xmp|exif|Iptc4xmpCore):([\w]+)>\s*([^<]+)\s*</", re.IGNORECASE)


def _coerce_bool(val) -> bool:
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return bool(val)
    if isinstance(val, str):
        return val.strip().lower() in ("true", "1", "yes", "on")
    return bool(val)


def _empty_tensor():
    if torch is None:
        return None
    return torch.zeros((1, 1, 1, 3), dtype=torch.float32)


def _pil_to_tensor(pil_image: Image.Image):
    if torch is None:
        return None
    arr = np.array(pil_image.convert("RGB")).astype(np.float32) / 255.0
    return torch.from_numpy(arr)[None, ...]


def _tensor_to_pil(image_tensor) -> Image.Image:
    if torch is None or image_tensor is None:
        return Image.new("RGB", (1, 1), (0, 0, 0))
    t = image_tensor
    if hasattr(t, "dim") and t.dim() == 4:
        t = t[0]
    arr = (t.cpu().numpy().clip(0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)
    return Image.fromarray(arr, mode="RGB")


# ---------------------------------------------------------------------------
# Parse
# ---------------------------------------------------------------------------


def _parse_a1111(blob: str) -> dict:
    """Parse an A1111 `parameters` blob into a dict of positive/negative/scalars."""
    out = {"positive": "", "negative": "", "scalars": {}}
    if not isinstance(blob, str) or not blob:
        return out
    out["positive"] = _strip_a1111(blob)
    m = _A1111_NEG_RE.search(blob)
    if m:
        out["negative"] = m.group(1).strip()
    for key, val in _A1111_SCALAR_RE.findall(blob):
        out["scalars"][key.strip()] = val.strip()
    return out


def _parse_xmp(xmp_text: str) -> dict:
    out: dict = {}
    if not isinstance(xmp_text, str):
        return out
    for tag, val in _XMP_TAG_RE.findall(xmp_text):
        out[tag.lower()] = val.strip()
    return out


def _harvest_flat_prompt_keys(info: dict) -> list:
    """JustRayzist-style: collect string-valued `*prompt*` keys."""
    out = []
    consumed = {"parameters", "Parameters", "prompt", "workflow"}
    for key, val in (info or {}).items():
        if not isinstance(key, str) or key in consumed:
            continue
        kl = key.lower()
        if "prompt" not in kl:
            continue
        if kl.endswith("_enhanced") or kl.endswith("_count") or kl.endswith("_json"):
            continue
        if not isinstance(val, str):
            continue
        s = val.strip()
        if len(s) >= 8 and s.lower() not in ("true", "false", "none", "null"):
            out.append((key, s))
    return out


def inspect_file(path: pathlib.Path) -> dict:
    """Read every known metadata source from `path` and return a flat result dict."""
    result = {
        "prompt_positive": "",
        "prompt_negative": "",
        "seed": "",
        "steps": "",
        "cfg": "",
        "sampler": "",
        "model": "",
        "loras_json": "",
        "width": "",
        "height": "",
        "raw_metadata_json": "",
        "pil_image": None,
    }
    if not path.is_file():
        result["raw_metadata_json"] = json.dumps({"error": f"not a file: {path}"})
        return result

    try:
        pil = Image.open(path)
        pil.load()
    except Exception as e:
        result["raw_metadata_json"] = json.dumps({"error": f"open failed: {e}"})
        return result

    result["pil_image"] = pil
    result["width"] = str(pil.width)
    result["height"] = str(pil.height)
    info = pil.info or {}

    raw: dict = {"_source_file": str(path), "_info_keys": list(info.keys())}

    # A1111 parameters
    params = info.get("parameters") or info.get("Parameters")
    if isinstance(params, str) and params.strip():
        parsed = _parse_a1111(params)
        if parsed["positive"]:
            result["prompt_positive"] = parsed["positive"]
        if parsed["negative"]:
            result["prompt_negative"] = parsed["negative"]
        for k, v in parsed["scalars"].items():
            kl = k.lower()
            if kl == "seed":
                result["seed"] = v
            elif kl == "steps":
                result["steps"] = v
            elif kl in ("cfg scale", "cfg"):
                result["cfg"] = v
            elif kl == "sampler":
                result["sampler"] = v
            elif kl == "model":
                result["model"] = v
            elif kl == "model hash":
                result.setdefault("model", "")
                result["model"] = result["model"] or v
            elif "lora" in kl:
                result["loras_json"] = v
        raw["parameters"] = params

    # ComfyUI prompt chunk
    cprompt = info.get("prompt")
    if cprompt:
        raw["prompt_chunk"] = cprompt if len(str(cprompt)) < 200000 else "<truncated>"
        if isinstance(cprompt, str) and not _looks_like_comfy_graph(cprompt):
            if not result["prompt_positive"]:
                result["prompt_positive"] = cprompt.strip()
        else:
            prompts = _extract_prompts_from_comfy_graph(cprompt)
            if prompts and not result["prompt_positive"]:
                result["prompt_positive"] = prompts[0]

    # ComfyUI workflow chunk (UI format)
    wf = info.get("workflow")
    if wf:
        raw["workflow_chunk"] = "<workflow present>"
        parsed = wf
        if isinstance(parsed, str):
            try:
                parsed = json.loads(parsed)
            except Exception:
                parsed = None
        if isinstance(parsed, dict):
            if isinstance(parsed.get("nodes"), list):
                prompts = _extract_prompts_from_ui_workflow(parsed)
            else:
                prompts = _extract_prompts_from_comfy_graph(parsed)
            if prompts and not result["prompt_positive"]:
                result["prompt_positive"] = prompts[0]

    # EXIF UserComment
    exif_text = _read_exif_user_comment(pil)
    if exif_text:
        raw["exif_user_comment"] = exif_text[:2000]
        if not result["prompt_positive"]:
            parsed = _parse_a1111(exif_text)
            if parsed["positive"]:
                result["prompt_positive"] = parsed["positive"]
            if parsed["negative"] and not result["prompt_negative"]:
                result["prompt_negative"] = parsed["negative"]

    # Full EXIF dump
    try:
        exif = pil.getexif()
        if exif:
            raw["exif"] = {int(k): str(v)[:500] for k, v in dict(exif).items()}
    except Exception:
        pass

    # Flat JustRayzist-style fields
    flats = _harvest_flat_prompt_keys(info)
    if flats:
        raw["flat_prompts"] = {k: v[:200] for k, v in flats}
        if not result["prompt_positive"]:
            result["prompt_positive"] = max((v for _k, v in flats), key=len)

    # Scalar info keys (anything string/int/float)
    scalars = {}
    for k, v in info.items():
        if k in ("parameters", "prompt", "workflow"):
            continue
        if isinstance(v, (str, int, float, bool)):
            scalars[k] = v
    raw["scalars"] = scalars

    # XMP
    for key in ("XML:com.adobe.xmp", "xmp", "XMP"):
        x = info.get(key)
        if isinstance(x, (bytes, str)):
            xs = x.decode("utf-8", "replace") if isinstance(x, bytes) else x
            xmp = _parse_xmp(xs)
            if xmp:
                raw["xmp"] = xmp
                break

    # Fall back to scalar dict for missing fields
    for missing in ("seed", "steps", "cfg", "sampler", "model"):
        if not result[missing]:
            for sk, sv in scalars.items():
                if sk.lower() == missing:
                    result[missing] = str(sv)
                    break

    result["raw_metadata_json"] = json.dumps(raw, indent=2, default=str)
    return result


# ---------------------------------------------------------------------------
# Embed
# ---------------------------------------------------------------------------


def embed_file(
    pil_image: Image.Image,
    metadata: dict,
    output_path: pathlib.Path,
) -> None:
    """Write `pil_image` to `output_path` (PNG) with chunks from `metadata`.

    Recognized metadata keys:
      • parameters         → A1111-style flat string (priority)
      • positive/negative/seed/steps/cfg/sampler/model
        → assembled into A1111 `parameters` chunk if `parameters` not given
      • prompt             → ComfyUI prompt graph (object or JSON string)
      • workflow           → ComfyUI workflow (object or JSON string)
      • any other scalar   → embedded as a flat iTXt key (JustRayzist style)
    """
    if not isinstance(metadata, dict):
        metadata = {}

    pnginfo = PngImagePlugin.PngInfo()

    # A1111 parameters chunk
    params = metadata.get("parameters")
    if not params:
        pos = metadata.get("positive") or metadata.get("prompt_positive") or ""
        neg = metadata.get("negative") or metadata.get("prompt_negative") or ""
        scalars = []
        for k in ("Steps", "Sampler", "CFG scale", "Seed", "Model"):
            lower_k = k.lower().replace(" scale", "")
            for cand in (k, k.lower(), lower_k):
                if cand in metadata and metadata[cand] not in (None, ""):
                    scalars.append(f"{k}: {metadata[cand]}")
                    break
        if pos:
            params = pos
            if neg:
                params += f"\nNegative prompt: {neg}"
            if scalars:
                params += "\n" + ", ".join(scalars)
    if isinstance(params, str) and params.strip():
        pnginfo.add_text("parameters", params)

    # Comfy chunks
    for chunk_key in ("prompt", "workflow"):
        v = metadata.get(chunk_key)
        if v is None:
            continue
        if isinstance(v, (dict, list)):
            v = json.dumps(v)
        if isinstance(v, str) and v.strip():
            pnginfo.add_text(chunk_key, v)

    # Flat fields — every other scalar key gets written as-is so JustRayzist
    # / similar readers pick them up.
    consumed = {"parameters", "prompt", "workflow", "positive", "prompt_positive",
                "negative", "prompt_negative"}
    for k, v in metadata.items():
        if k in consumed:
            continue
        if v is None:
            continue
        sv = v if isinstance(v, str) else json.dumps(v)
        if isinstance(sv, str) and sv:
            try:
                pnginfo.add_text(k, sv)
            except Exception:
                continue

    tmp = output_path.with_suffix(output_path.suffix + ".tmp")
    pil_image.save(tmp, "PNG", pnginfo=pnginfo)
    os.replace(tmp, output_path)


# ---------------------------------------------------------------------------
# Node class
# ---------------------------------------------------------------------------


class RayMetaInspect:
    """Read or write image metadata. Inspect parses every known chunk; Embed
    writes a tensor + dict back to disk and re-parses for verification."""

    DESCRIPTION = (
        "Read or write image generation metadata.\n"
        "  • `Inspect` — parses every known chunk (A1111 parameters, "
        "ComfyUI prompt / workflow graph, EXIF UserComment, sidecar "
        "text) and exposes prompt_positive, prompt_negative, seed, "
        "steps, cfg, sampler, model, LoRAs, dimensions, and the raw "
        "JSON blob.\n"
        "  • `Embed`   — writes an IMAGE tensor + `metadata_json` dict "
        "back to disk at `path`, then re-parses the file for round-trip "
        "verification.\n\n"
        "Drag an image onto the inline drop-zone to prefill `path`."
    )

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "mode": (MODES, {
                    "default": MODE_INSPECT,
                    "tooltip": "Inspect reads metadata; Embed writes a tensor + JSON dict to disk.",
                }),
                "path": ("STRING", {
                    "default": "",
                    "multiline": False,
                    "placeholder": "Path to image (Inspect) or output path (Embed)",
                    "tooltip": "Source file (Inspect) or destination file (Embed).",
                }),
            },
            "optional": {
                "image": ("IMAGE", {"tooltip": "Embed mode: tensor to write."}),
                "metadata_json": ("STRING", {
                    "default": "",
                    "multiline": True,
                    "placeholder": "Embed mode: JSON dict of metadata fields",
                    "tooltip": "Embed mode: JSON dict of metadata fields to attach.",
                }),
            },
            "hidden": {"node_id": "UNIQUE_ID"},
        }

    RETURN_TYPES = (
        "STRING", "STRING", "STRING", "STRING", "STRING",
        "STRING", "STRING", "STRING", "STRING", "STRING",
        "STRING", "IMAGE",
    )
    RETURN_NAMES = (
        "prompt_positive", "prompt_negative", "seed", "steps", "cfg",
        "sampler", "model", "loras_json", "width", "height",
        "raw_metadata_json", "image",
    )
    OUTPUT_TOOLTIPS = (
        "Positive prompt extracted from the file's metadata.",
        "Negative prompt extracted from the file's metadata.",
        "Seed value if present.",
        "Sampler step count if present.",
        "CFG scale if present.",
        "Sampler name if present.",
        "Model / checkpoint reference if present.",
        "LoRAs referenced in the metadata, encoded as JSON.",
        "Image width in pixels.",
        "Image height in pixels.",
        "Full raw metadata as JSON — for debugging or downstream tools.",
        "Source image tensor.",
    )
    FUNCTION = "process"
    CATEGORY = "👑 Ray/📝 Prompts"

    @classmethod
    def IS_CHANGED(cls, *args, **kwargs):
        return float("nan")

    def process(self, mode, path, image=None, metadata_json="", node_id=None):
        mode = (mode or MODE_INSPECT).strip()
        path_str = (path or "").strip()

        if mode == MODE_EMBED:
            return self._do_embed(path_str, image, metadata_json)
        return self._do_inspect(path_str)

    # --- Inspect ----------------------------------------------------------

    def _do_inspect(self, path_str):
        if not path_str:
            return self._empty_outputs("path is empty")
        p = _resolve_path(path_str)
        r = inspect_file(p)
        tensor = _pil_to_tensor(r["pil_image"]) if r["pil_image"] is not None else _empty_tensor()
        return (
            r["prompt_positive"],
            r["prompt_negative"],
            r["seed"],
            r["steps"],
            r["cfg"],
            r["sampler"],
            r["model"],
            r["loras_json"],
            r["width"],
            r["height"],
            r["raw_metadata_json"],
            tensor,
        )

    # --- Embed ------------------------------------------------------------

    def _do_embed(self, path_str, image, metadata_json):
        if not path_str:
            return self._empty_outputs("output path is empty")
        if image is None:
            return self._empty_outputs("Embed mode requires an image input")
        try:
            meta = json.loads(metadata_json) if metadata_json.strip() else {}
        except json.JSONDecodeError as e:
            return self._empty_outputs(f"metadata_json invalid: {e}")
        if not isinstance(meta, dict):
            return self._empty_outputs("metadata_json must be a JSON object")

        out_path = pathlib.Path(path_str).expanduser()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        pil = _tensor_to_pil(image)
        embed_file(pil, meta, out_path)
        # Re-inspect so downstream sees the written-back metadata
        return self._do_inspect(str(out_path))

    @staticmethod
    def _empty_outputs(reason: str):
        err = json.dumps({"error": reason})
        return ("", "", "", "", "", "", "", "", "", "", err, _empty_tensor())
