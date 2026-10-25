"""Output demand and readable names for model-processing workflows."""
from datetime import datetime
import json
from pathlib import PurePosixPath

if __package__:
    from .filename_template import clean_value, finish_stem
else:
    from filename_template import clean_value, finish_stem


def inference_requested(prompt=None, unique_id=None):
    # Direct Python callers retain the normal loader behavior.
    if prompt is None or unique_id is None:
        return True
    return any(isinstance(value, list) and len(value) == 2
               and str(value[0]) == str(unique_id) and value[1] in (0, 1, 2)
               for node in prompt.values() for value in node.get("inputs", {}).values())


def source_stem(value, fallback="Model"):
    value = str(value or "").strip().strip('"').replace("\\", "/").rstrip("/")
    for group in ("checkpoints: ", "diffusion_models: ", "loras: "):
        if value.startswith(group):
            value = value[len(group):]
    name = PurePosixPath(value).name
    for suffix in (".safetensors.index.json", ".safetensors", ".ckpt", ".gguf", ".pth", ".pt", ".bin", ".sft"):
        if name.lower().endswith(suffix):
            name = name[:-len(suffix)]
            break
    return clean_value(name, 28) or fallback


def graph_source_name(prompt, node_id, seen=None):
    seen = set() if seen is None else seen
    node_id = str(node_id)
    if node_id in seen or len(seen) >= 64:
        return ""
    seen.add(node_id)
    node = (prompt or {}).get(node_id, {})
    inputs = node.get("inputs", {})
    # Follow the model/data branch before a patch node's own local file fields.
    connected = False
    for field in ("model", "model_data", "data_a", "model_a"):
        link = inputs.get(field)
        if isinstance(link, list) and len(link) == 2:
            connected = True
            name = graph_source_name(prompt, link[0], seen)
            if name:
                return name
    if connected:
        return ""
    for field in ("model_name", "unet_name", "ckpt_name", "model_path", "path"):
        value = inputs.get(field)
        if isinstance(value, str) and value.strip():
            return value
        if isinstance(value, list) and len(value) == 2:
            upstream = (prompt or {}).get(str(value[0]), {}).get("inputs", {})
            for name in ("value", "text", "string"):
                if isinstance(upstream.get(name), str):
                    return upstream[name]
    return ""


def source_name(model=None, data=None, path="", prompt=None, unique_id=None, fields=()):
    if model is not None:
        name = getattr(model, "attachments", {}).get("ray_model_source")
        if name:
            return name
    elif data is not None:
        return data.metadata.get("ray_merge_name") or data.metadata.get("ray_source_name") or data._path
    elif path:
        return path
    inputs = (prompt or {}).get(str(unique_id), {}).get("inputs", {})
    for field in fields:
        link = inputs.get(field)
        if isinstance(link, list) and len(link) == 2:
            name = graph_source_name(prompt, link[0])
            if name:
                return name
    return ""


def setting_text(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return format(value, ".10f").rstrip("0").rstrip(".") if isinstance(value, float) else str(value)
    return str(value or "")


def name_signature(settings):
    values = [setting_text(settings.get(key, default)) for key, default in
              (("components", "diffusion"), ("mismatch", "forbid"), ("seed", 0),
               ("density", .5), ("lambda", 1.), ("top_trim", .1), ("bottom_trim", .01),
               ("block_weights", "{}"), ("fast_merge", False))]
    try:
        block = json.loads(values[7])
        if isinstance(block, dict):
            block = {key: setting_text(value) for key, value in block.items()}
        values[7] = json.dumps(block, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    except (ValueError, TypeError):
        pass
    digest = 2166136261
    for byte in "\x1f".join(values).encode("utf-8"):
        digest = ((digest ^ byte) * 16777619) & 0xffffffff
    return f"{digest:08x}"


def merge_name(a="", b="", base="", strategy="LERP", weight_a=.5, weight_format="bf16", settings=None, now=None):
    names = []
    if strategy not in ("LERP", "SLERP"):
        names.append("Base-" + source_stem(base, "Base"))
    names.extend(("A-" + source_stem(a, "A"), "B-" + source_stem(b, "B"), strategy))
    ratio = lambda number: f"{float(number) * 100:.4f}".rstrip("0").rstrip(".")
    names.extend((f"{ratio(weight_a)}-{ratio(1-float(weight_a))}", weight_format,
                  name_signature(settings or {}), (now or datetime.now().astimezone()).strftime("%Y%m%d-%H%M%S")))
    return finish_stem("_".join(names))
