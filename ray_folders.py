"""Ray - Folders: local media listing, previews, metadata and native ComfyUI lists."""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import tempfile
import threading
import unicodedata
from collections import OrderedDict
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageOps

try:
    from .ray_local_scraper import extract_prompts, _harvest_info_value, _clean_candidates
except ImportError:
    from ray_local_scraper import extract_prompts, _harvest_info_value, _clean_candidates

EXTENSIONS = {
    "image": {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff", ".avif"},
    "video": {".mp4", ".webm", ".mov", ".mkv", ".avi", ".m4v", ".mpeg", ".mpg"},
    "audio": {".wav", ".mp3", ".flac", ".ogg", ".m4a", ".aac", ".opus", ".aiff", ".wma"},
}
DEFAULTS = {"types": ["image", "video", "audio"], "sort": "name", "descending": False,
            "recursive": False, "columns": 4, "colors": [], "nsfw": "all", "threshold": .6,
            "include_sexy": True, "nsfw_regions": True, "best_prompt": True, "prompt_format": "multiline"}
_META = OrderedDict()
_LOCK = threading.RLock()
_LOG = logging.getLogger(__name__)
MEDIA_ERRORS = (OSError, ValueError, IndexError, StopIteration, Image.DecompressionBombError)


def settings(value=None):
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (ValueError, TypeError):
            value = {}
    value = value if isinstance(value, dict) else {}
    result = {**DEFAULTS, **{k: v for k, v in value.items() if k in DEFAULTS}}
    result["types"] = [t for t in result["types"] if isinstance(t, str) and t in EXTENSIONS] if isinstance(result["types"], list) else list(DEFAULTS["types"])
    result["sort"] = result["sort"] if result["sort"] in ("name", "date", "size") else "name"
    result["prompt_format"] = "single" if result["prompt_format"] == "single" else "multiline"
    result["recursive"] = result["recursive"] is True
    result["descending"] = result["descending"] is True
    result["best_prompt"] = result["best_prompt"] is not False
    return result


def folder_path(value):
    text = str(value or "").strip().strip('"')
    path = Path(text).expanduser()
    if not text or not path.is_absolute():
        raise ValueError("Choose an absolute folder path.")
    path = path.resolve(strict=True)
    if not path.is_dir():
        raise ValueError("The selected path is not a folder.")
    return path


def media_kind(path):
    return next((kind for kind, exts in EXTENSIONS.items() if Path(path).suffix.lower() in exts), None)


def resolve_media(root, relative, recursive=True):
    root = folder_path(root)
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise ValueError("Expected a media path relative to the selected folder.")
    path = (root / relative).resolve(strict=True)
    if not path.is_relative_to(root) or (not recursive and path.parent != root):
        raise ValueError("The media file is outside the selected folder.")
    if not path.is_file() or not media_kind(path):
        raise ValueError("This is not a supported media file.")
    return path


def _normalize(text):
    return "".join(c for c in unicodedata.normalize("NFKD", str(text).lower()) if not unicodedata.combining(c))


def fuzzy_match(name, query):
    """AND-match words, allowing subsequences and small spelling mistakes."""
    if not str(query or "").strip():
        return True
    name = _normalize(name)
    words = re.findall(r"\w+", name)
    for term in _normalize(query).split():
        if term in name:
            continue
        iterator = iter(name)
        if all(any(c == n for n in iterator) for c in term):
            continue
        limit = max(1, len(term) // 4)
        if len(term) < 3 or not any(_distance(term, word) <= limit for word in words):
            return False
    return True


def _distance(a, b):
    row = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        updated = [i]
        for j, cb in enumerate(b, 1):
            updated.append(min(row[j] + 1, updated[-1] + 1, row[j - 1] + (ca != cb)))
        row = updated
    return row[-1]


def scan(folder, options=None, name_filter=""):
    root = folder_path(folder)
    opts = settings(options)
    files, errors = [], []
    counts = {"image": 0, "video": 0, "audio": 0}
    for directory, dirs, names in os.walk(root, followlinks=False, onerror=errors.append):
        dirs[:] = sorted(d for d in dirs if not (Path(directory) / d).is_symlink()
                         and not getattr(Path(directory) / d, "is_junction", lambda: False)()) if opts["recursive"] else []
        for name in names:
            path = Path(directory) / name
            kind = media_kind(path)
            if not kind:
                continue
            try:
                if not path.resolve().is_relative_to(root):
                    continue
                stat = path.stat()
                counts[kind] += 1
                if kind not in opts["types"] or not fuzzy_match(name, name_filter):
                    continue
                relative = path.relative_to(root).as_posix()
                files.append({"id": relative, "name": name, "kind": kind, "size": stat.st_size,
                              "modified": stat.st_mtime, "revision": f"{stat.st_mtime_ns}-{stat.st_size}"})
            except OSError as error:
                errors.append(error)
                continue
    if not root.is_dir():
        raise OSError("The folder is no longer available. It may have been deleted or its drive disconnected.")
    if errors and not files and not any(counts.values()):
        raise OSError("The folder could not be read. Check the drive connection and folder permissions.")
    key = {"name": lambda f: (f["name"].lower(), f["id"]),
           "date": lambda f: (f["modified"], f["id"]), "size": lambda f: (f["size"], f["id"])}[opts["sort"]]
    files.sort(key=key, reverse=opts["descending"])
    return {"folder": str(root), "items": files, "name_filter": str(name_filter or ""), "counts": counts,
            "warnings": [f"{len(errors)} files or folders could not be read."] if errors else []}


def _stamp(path):
    stat = path.stat()
    sidecar = path.with_suffix(".txt")
    try:
        side = sidecar.stat()
        side_stamp = (side.st_mtime_ns, side.st_size)
    except OSError:
        side_stamp = None
    return (str(path), stat.st_mtime_ns, stat.st_size, side_stamp)


def _workflow(value):
    try:
        obj = json.loads(value) if isinstance(value, str) else value
        return obj if isinstance(obj, dict) and (isinstance(obj.get("nodes"), list) or any(isinstance(v, dict) and "class_type" in v for v in obj.values())) else None
    except (TypeError, ValueError):
        return None


def metadata(path):
    path = Path(path)
    key = _stamp(path)
    with _LOCK:
        if key in _META:
            _META.move_to_end(key)
            return dict(_META[key])
    result = {"width": None, "height": None, "duration": None, "prompts": [], "workflow": None}
    if media_kind(path) == "image":
        with Image.open(path) as image:
            result.update(width=image.width, height=image.height, prompts=extract_prompts(path, image),
                          workflow=_workflow(image.info.get("workflow")) or _workflow(image.info.get("prompt")))
    else:
        import av
        with av.open(str(path)) as container:
            if container.duration is not None:
                result["duration"] = float(container.duration / av.time_base)
            videos = container.streams.video
            if videos:
                result.update(width=videos[0].width, height=videos[0].height)
            candidates = []
            tags = dict(container.metadata)
            for stream in container.streams:
                tags.update(stream.metadata)
            for name, value in tags.items():
                candidates.extend(_harvest_info_value(name, value))
                if name.lower() in ("workflow", "prompt") and not result["workflow"]:
                    result["workflow"] = _workflow(value)
            result["prompts"] = _clean_candidates(candidates)
        if not result["prompts"]:
            sidecar = path.with_suffix(".txt")
            if sidecar.is_file():
                result["prompts"] = _clean_candidates([sidecar.read_text(encoding="utf-8-sig", errors="replace")])
    result["has_prompt"] = bool(result["prompts"])
    with _LOCK:
        _META[key] = dict(result)
        while len(_META) > 2048:
            _META.popitem(last=False)
    return result


def prompt_text(info, options=None):
    opts = settings(options)
    candidates = list(info.get("prompts") or [])
    if opts["best_prompt"] and candidates:
        candidates = [max(candidates, key=len)]
    text = "\n\n".join(candidates)
    return re.sub(r"\s+", " ", text).strip() if opts["prompt_format"] == "single" else text


def _cache_dir():
    try:
        import folder_paths
        base = folder_paths.get_temp_directory()
    except ImportError:
        base = tempfile.gettempdir()
    path = Path(base) / "ray_folders_thumbnails"
    path.mkdir(parents=True, exist_ok=True)
    return path


def thumbnail(path):
    path = Path(path)
    destination = _cache_dir() / (hashlib.sha256(repr(_stamp(path)).encode()).hexdigest() + ".jpg")
    if destination.exists():
        return destination
    kind = media_kind(path)
    if kind == "image":
        with Image.open(path) as source:
            image = ImageOps.exif_transpose(source).convert("RGB")
            image.thumbnail((384, 384))
    else:
        import av
        with av.open(str(path)) as container:
            if container.streams.video:
                stream = container.streams.video[0]
                frame = next(container.decode(stream), None)
                if frame is None:
                    raise ValueError("No video frame could be decoded.")
                image = frame.to_image().convert("RGB")
                image.thumbnail((384, 384))
            else:
                image = Image.new("RGB", (384, 256), "#141414")
                draw = ImageDraw.Draw(image)
                samples, count = [], 0
                stream = container.streams.audio[0]
                for frame in container.decode(stream):
                    values = frame.to_ndarray().astype(np.float32).reshape(-1)
                    samples.append(values)
                    count += len(values)
                    if count >= (stream.rate or 48000) * 8:
                        break
                if samples:
                    values = np.concatenate(samples)
                    values /= max(float(np.max(np.abs(values))), 1e-9)
                    for x, chunk in enumerate(np.array_split(values, 176)):
                        amplitude = min(90, float(np.max(np.abs(chunk))) * 90) if chunk.size else 0
                        draw.line((16 + x * 2, 128 - amplitude, 16 + x * 2, 128 + amplitude), fill="#cbbbf7")
                draw.text((16, 220), "AUDIO", fill="#aaa")
    # Each writer uses its own temporary file; concurrent requests never expose partial JPEGs.
    fd, temporary = tempfile.mkstemp(suffix=".jpg", dir=destination.parent)
    os.close(fd)
    try:
        image.save(temporary, "JPEG", quality=85)
        os.replace(temporary, destination)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return destination


def _selected(value, root):
    try:
        value = json.loads(value) if isinstance(value, str) else value
    except (TypeError, ValueError):
        return set()
    if not isinstance(value, dict) or not isinstance(value.get("files"), list):
        return set()
    try:
        if folder_path(value.get("folder")) != root:
            return set()
    except (ValueError, OSError):
        return set()
    return {s for s in value["files"] if isinstance(s, str)}


class RayFolders:
    DESCRIPTION = "Browse local images, videos and audio. Select files to emit native media lists, matching prompts and paths. Refreshes on every run, including with no outputs connected."

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "folder": ("STRING", {"default": "", "tooltip": "Browse or connect an absolute folder path."}),
            "name_filter": ("STRING", {"default": "", "tooltip": "Fuzzy filename search; words are matched together."}),
        }, "optional": {
            "selected_files": ("STRING", {"default": "{}"}),
            "settings_json": ("STRING", {"default": "{}"}),
        }, "hidden": {"node_id": "UNIQUE_ID"}}

    RETURN_TYPES = ("IMAGE", "VIDEO", "AUDIO", "STRING", "STRING")
    RETURN_NAMES = ("images", "videos", "audio", "prompt", "paths")
    OUTPUT_IS_LIST = (True, True, True, True, True)
    OUTPUT_TOOLTIPS = ("Selected images at original dimensions.", "Selected native ComfyUI videos.",
                       "Selected audio at original sample rates.", "One prompt per selected file; blank when absent.",
                       "Selected paths in gallery order, or the folder path when nothing is selected.")
    OUTPUT_NODE = True
    FUNCTION = "browse"
    CATEGORY = "👑 Ray/🔧 Tools"

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("nan")

    def browse(self, folder="", name_filter="", selected_files="{}", settings_json="{}", node_id=None):
        opts = settings(settings_json)
        if not str(folder).strip():
            return {"ui": {"ray_folders": [{"folder": "", "items": [], "name_filter": name_filter}]},
                    "result": ([], [], [], [], [""])}
        try:
            listing = scan(folder, opts, name_filter)
        except (OSError, ValueError) as error:
            listing = {"folder": str(folder), "items": [], "name_filter": name_filter,
                       "counts": {"image": 0, "video": 0, "audio": 0},
                       "error": f"Folder unavailable. Check that it exists and its drive is connected. {error}"}
            return {"ui": {"ray_folders": [listing]}, "result": ([], [], [], [], [str(folder)])}
        root = Path(listing["folder"])
        selected = _selected(selected_files, root)
        images, videos, audio, prompts, paths = [], [], [], [], []
        for item in listing["items"]:
            if item["id"] not in selected:
                continue
            try:
                import comfy.model_management as mm
                mm.throw_exception_if_processing_interrupted()
                path = resolve_media(root, item["id"], opts["recursive"])
                info = metadata(path)
                if item["kind"] == "image":
                    import torch
                    with Image.open(path) as image:
                        image = ImageOps.exif_transpose(image).convert("RGB")
                        images.append(torch.from_numpy(np.array(image).astype(np.float32) / 255)[None])
                elif item["kind"] == "video":
                    from comfy_api.latest import InputImpl
                    videos.append(InputImpl.VideoFromFile(str(path)))
                else:
                    from comfy_extras.nodes_audio import load
                    waveform, rate = load(str(path))
                    audio.append({"waveform": waveform.unsqueeze(0), "sample_rate": rate})
                prompts.append(prompt_text(info, opts))
                paths.append(str(path))
            except MEDIA_ERRORS as error:
                _LOG.warning("[RayFolders] Skipping %s: %s", item["id"], error)
                listing.setdefault("warnings", []).append(f"Unavailable: {item['name']}")
        # Execution messages do not repeat the potentially huge file index; the browser's
        # scan endpoint refreshes that separately, including for a disconnected output node.
        ui = {key: value for key, value in listing.items() if key != "items"}
        return {"ui": {"ray_folders": [ui]}, "result": (images, videos, audio, prompts, paths or [str(root)])}
