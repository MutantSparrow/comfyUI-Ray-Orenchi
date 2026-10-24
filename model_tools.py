"""File-based model operations for Orenchi.

Merge mathematics adapted from Ray's Apache-2.0 ModelMergeTools. ComfyUI and
comfy-kitchen are used through their public Python APIs, never copied here.
Tensor operations stream one layer at a time or retain their output in RAM;
files are committed atomically.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import struct
import tempfile
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass, field
from collections import Counter

import torch
from safetensors import safe_open, SafetensorError

SCHEMA = "ray.model-metadata/v1"
HISTORY = "ray.model_tools.history"
FORMATS = ["preserve", "fp32", "fp16", "bf16", "fp8_e4m3fn", "fp8_e4m3fn_scaled",
           "fp8_e5m2", "int8_tensor", "int8_row", "int8_convrot"]
STRATEGIES = ["LERP", "SLERP", "TIES", "DARE-Linear", "DARE-TIES", "DELLA",
              "DELLA-TIES", "Breadcrumbs", "Breadcrumbs-TIES"]
DTYPES = {"F64": torch.float64, "F32": torch.float32, "F16": torch.float16,
          "BF16": torch.bfloat16, "I64": torch.int64, "I32": torch.int32,
          "I16": torch.int16, "I8": torch.int8, "U8": torch.uint8, "BOOL": torch.bool,
          "F8_E4M3": torch.float8_e4m3fn, "F8_E5M2": torch.float8_e5m2}
DTYPE_NAMES = {v: k for k, v in DTYPES.items()}
SIDE_SUFFIXES = (".scale_weight", ".scale_input", ".hadamard_group", ".weight_scale",
                 ".weight_scale_2", ".input_scale", ".pre_quant_scale", ".comfy_quant",
                 ".weight_s_rel", ".weight_s_channel", ".weight_codebook")
SENTINELS = {"scaled_fp8", "scaled_int8"}


def clean_path(value):
    return Path(str(value).strip().strip('"').strip("'")).expanduser().resolve()


def json_text(value):
    return json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)


def metadata_fields(value):
    if value is None or value == "":
        return {}
    if isinstance(value, str):
        value = parse_metadata_json(value)
    if not isinstance(value, dict):
        raise ValueError("Metadata must be a JSON object.")
    if value.get("schema") == SCHEMA and isinstance(value.get("metadata"), dict):
        value = value.get("metadata", {})
    if not isinstance(value, dict) or not all(isinstance(k, str) for k in value):
        raise ValueError("Metadata must have string keys.")
    # Validate without losing numeric types or silently accepting NaN/Infinity.
    json.dumps(value, allow_nan=False)
    return dict(value)


def parse_metadata_json(text):
    def object_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result
    return json.loads(text, object_pairs_hook=object_pairs)


def embedded_metadata(value):
    return {k: v if isinstance(v, str) else json.dumps(v, ensure_ascii=False, allow_nan=False)
            for k, v in metadata_fields(value).items()}


def with_history(metadata, operation, **details):
    result = dict(metadata)
    try:
        history = json.loads(result.get(HISTORY, "[]"))
        if not isinstance(history, list):
            history = []
    except (ValueError, TypeError):
        history = []
    result[HISTORY] = json.dumps(history + [{"operation": operation, **details}], ensure_ascii=False)
    return result


def read_header(path):
    path = clean_path(path)
    with path.open("rb") as f:
        raw = f.read(8)
        if len(raw) != 8:
            raise ValueError("Not a safetensors file: missing header length.")
        size = struct.unpack("<Q", raw)[0]
        if not 2 <= size <= min(100_000_000, path.stat().st_size - 8):
            raise ValueError("Invalid safetensors header length.")
        header = json.loads(f.read(size))
    if not isinstance(header, dict):
        raise ValueError("Invalid safetensors header.")
    # The parser validates offsets, dtypes and shapes without reading weights.
    try:
        with safe_open(str(path), framework="pt"):
            pass
    except SafetensorError as exc:
        raise ValueError(f"Invalid safetensors file: {exc}") from exc
    return header, 8 + size


def commit_file(temp, destination, overwrite=False):
    destination = clean_path(destination)
    if overwrite:
        os.replace(temp, destination)
    elif os.name == "nt":
        # Windows rename is atomic and refuses an existing destination, including
        # on exFAT volumes that do not support hard links.
        os.rename(temp, destination)
    else:
        # POSIX rename replaces existing files; a hard link keeps no-clobber atomic.
        os.link(temp, destination)
        os.unlink(temp)


def atomic_json(path, value, overwrite=False):
    path = clean_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".ray-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(json_text(value) + "\n")
        commit_file(tmp, path, overwrite)
    finally:
        Path(tmp).unlink(missing_ok=True)
    return str(path)


def load_metadata(path):
    path = clean_path(path)
    if path.suffix.lower() == ".json":
        if path.stat().st_size > 100_000_000:
            raise ValueError("Metadata JSON exceeds 100 MB.")
        return metadata_fields(parse_metadata_json(path.read_text(encoding="utf-8-sig")))
    return TensorSource(path).metadata.copy()


def rewrite_metadata(source, destination, metadata, overwrite=False):
    source, destination = clean_path(source), clean_path(destination)
    if source == destination and not overwrite:
        raise ValueError("Replacing the source requires overwrite=true.")
    header, data_start = read_header(source)
    header["__metadata__"] = embedded_metadata(metadata)
    encoded = json.dumps(header, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    encoded += b" " * (-len(encoded) % 8)
    if len(encoded) > 100_000_000:
        raise ValueError("Metadata exceeds the safetensors header limit.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".ray-", suffix=".safetensors", dir=destination.parent)
    try:
        with os.fdopen(fd, "wb") as out, source.open("rb") as inp:
            out.write(struct.pack("<Q", len(encoded)))
            out.write(encoded)
            inp.seek(data_start)
            shutil.copyfileobj(inp, out, 8 * 1024 * 1024)
        read_header(tmp)
        commit_file(tmp, destination, overwrite)
    finally:
        Path(tmp).unlink(missing_ok=True)
    return str(destination)


class TensorWriter:
    """Stream tensor payload to disk, then prepend its completed header."""
    def __init__(self, destination, metadata=None, overwrite=False):
        self.path = clean_path(destination)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.metadata, self.overwrite = embedded_metadata(metadata), overwrite
        self.header, self.offset = {}, 0
        self.payload = tempfile.TemporaryFile(dir=self.path.parent)

    def add(self, key, tensor):
        if key in self.header:
            raise ValueError(f"Duplicate output tensor: {key}")
        tensor = tensor.detach().to(device="cpu").contiguous()
        if tensor.dtype not in DTYPE_NAMES:
            raise ValueError(f"Unsupported output dtype {tensor.dtype}: {key}")
        size = tensor.numel() * tensor.element_size()
        self.header[key] = {"dtype": DTYPE_NAMES[tensor.dtype], "shape": list(tensor.shape),
                            "data_offsets": [self.offset, self.offset + size]}
        self.payload.write(tensor.reshape(-1).view(torch.uint8).numpy().tobytes())
        self.offset += size

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            if exc_type is not None:
                return False
            if not self.header:
                raise ValueError("No tensors were produced; no file was saved.")
            header = {"__metadata__": self.metadata, **self.header}
            encoded = json.dumps(header, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            encoded += b" " * (-len(encoded) % 8)
            if len(encoded) > 100_000_000:
                raise ValueError("Output header exceeds 100 MB.")
            fd, tmp = tempfile.mkstemp(prefix=".ray-", suffix=".safetensors", dir=self.path.parent)
            try:
                with os.fdopen(fd, "wb") as out:
                    out.write(struct.pack("<Q", len(encoded)))
                    out.write(encoded)
                    self.payload.seek(0)
                    shutil.copyfileobj(self.payload, out, 8 * 1024 * 1024)
                read_header(tmp)
                commit_file(tmp, self.path, self.overwrite)
            finally:
                Path(tmp).unlink(missing_ok=True)
        finally:
            self.payload.close()
        return False


def save_tensors(tensors, destination, metadata=None, overwrite=False):
    """Write RAM-backed weights once, with the final metadata, then publish."""
    from safetensors.torch import save_file
    destination = clean_path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not tensors:
        raise ValueError("No tensors were produced; no file was saved.")
    if destination.exists() and not overwrite:
        raise FileExistsError(f"Output already exists: {destination}")
    fd, tmp = tempfile.mkstemp(prefix=".ray-", suffix=".safetensors", dir=destination.parent)
    os.close(fd)
    try:
        save_file(tensors, tmp, metadata=embedded_metadata(metadata))
        read_header(tmp)
        commit_file(tmp, destination, overwrite)
    finally:
        Path(tmp).unlink(missing_ok=True)
    return str(destination)


class MemoryTensorWriter:
    """Own independent CPU tensors; no intermediate model or payload file."""
    def __init__(self, metadata):
        self.metadata = embedded_metadata(metadata)
        self.header, self.tensors = {}, {}

    def add(self, key, tensor):
        if key in self.header:
            raise ValueError(f"Duplicate output tensor: {key}")
        if tensor.dtype not in DTYPE_NAMES:
            raise ValueError(f"Unsupported output dtype {tensor.dtype}: {key}")
        self.tensors[key] = tensor.detach().to(device="cpu").clone(memory_format=torch.contiguous_format)
        self.header[key] = {"dtype": DTYPE_NAMES[tensor.dtype], "shape": list(tensor.shape)}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is not None:
            self.tensors.clear()
        elif not self.tensors:
            raise ValueError("No tensors were produced.")
        return False


def side_tensor(key):
    return key.rsplit(".", 1)[-1] in SENTINELS or key.endswith(SIDE_SUFFIXES)


def layer_name(key):
    return key[:-7] if key.endswith(".weight") else key


def component(key):
    if key.startswith(("first_stage_model.", "vae.")):
        return "vae"
    if key.startswith(("cond_stage_model.", "conditioner.", "text_encoders.", "clip.", "text_encoder.")):
        return "text"
    return "diffusion"


def selected(key, scope):
    return scope == "all" or component(key) == {"text_encoder": "text"}.get(scope, scope) or (
        scope == "diffusion_and_text" and component(key) in ("diffusion", "text"))


def canonical(key):
    if key.startswith("model.diffusion_model."):
        return key[len("model."):]
    if key.startswith("diffusion_model.") or component(key) != "diffusion":
        return key
    return "diffusion_model." + key


class TensorSource:
    def __init__(self, path):
        self._handles = {}
        self.path = clean_path(path)
        if self.path.is_dir():
            indexes = sorted(self.path.glob("*.safetensors.index.json"))
            if len(indexes) > 1:
                raise ValueError("Multiple shard indexes: select one model directory.")
            if indexes:
                weight_map = json.loads(indexes[0].read_text(encoding="utf-8"))["weight_map"]
                files = []
                for name in sorted(set(weight_map.values())):
                    file = (self.path / name).resolve()
                    if not file.is_relative_to(self.path):
                        raise ValueError("Shard index points outside its model directory.")
                    files.append(file)
            else:
                files = sorted(self.path.glob("*.safetensors"))
        else:
            files = [self.path]
        if not files:
            raise ValueError("No safetensors files found.")
        self.headers, self.index, self.metadata, self.configs = {}, {}, {}, {}
        for file in files:
            if file.suffix.lower() != ".safetensors":
                raise ValueError("Weight operations accept safetensors files or shard directories.")
            header, _ = read_header(file)
            meta = header.get("__metadata__", {})
            self.metadata.update({k: v for k, v in meta.items() if k not in self.metadata})
            if "_quantization_metadata" in meta:
                self.configs.update(json.loads(meta["_quantization_metadata"]).get("layers", {}))
            for key, info in header.items():
                if key == "__metadata__":
                    continue
                if key in self.index:
                    raise ValueError(f"Duplicate tensor across shards: {key}")
                self.index[key], self.headers[key] = file, info
        self.keys = sorted(k for k in self.index if not side_tensor(k))
        self.canon = {canonical(k): k for k in self.keys}
        if len(self.canon) != len(self.keys):
            raise ValueError("Ambiguous diffusion-model prefixes in source.")

    def raw(self, key):
        if self.index[key] in self._handles:
            return self._handles[self.index[key]].get_tensor(key)
        with safe_open(str(self.index[key]), framework="pt", device="cpu") as f:
            return f.get_tensor(key)

    @contextmanager
    def opened(self):
        """Reuse mmap handles for weights, scales and markers throughout a merge."""
        if self._handles:
            yield self
            return
        try:
            with ExitStack() as stack:
                for path in set(self.index.values()):
                    self._handles[path] = stack.enter_context(safe_open(str(path), framework="pt", device="cpu"))
                yield self
        finally:
            self._handles.clear()

    def config(self, key):
        layer = layer_name(key)
        name = layer + ".comfy_quant"
        if name in self.index:
            return json.loads(bytes(self.raw(name).tolist()))
        return self.configs.get(layer, {})

    def related(self, key):
        layer = layer_name(key)
        return [layer + suffix for suffix in SIDE_SUFFIXES if layer + suffix in self.index]

    def dense(self, key):
        tensor, config = self.raw(key), self.config(key)
        layer = layer_name(key)
        fmt = config.get("format")
        if fmt:
            from comfy.quant_ops import QUANT_ALGOS, get_layout_class, QuantizedTensor
            if fmt not in QUANT_ALGOS:
                raise ValueError(f"Installed ComfyUI cannot decode {fmt}: {key}")
            layout = get_layout_class(QUANT_ALGOS[fmt]["comfy_tensor_layout"])
            if fmt in ("float8_e4m3fn", "float8_e5m2", "int8_tensorwise"):
                if tensor.dtype == torch.uint8 and fmt.startswith("float8"):
                    tensor = tensor.view(QUANT_ALGOS[fmt]["storage_t"])
                params = {"scale": self.raw(layer + ".weight_scale")}
                if fmt == "int8_tensorwise":
                    extra = config.get("params", {})
                    params.update(convrot=config.get("convrot", extra.get("convrot", False)),
                                  convrot_groupsize=config.get("convrot_groupsize", extra.get("convrot_groupsize", 256)))
            elif fmt == "nvfp4":
                params = {"scale": self.raw(layer + ".weight_scale_2"),
                          "block_scale": self.raw(layer + ".weight_scale")}
            elif fmt == "mxfp8":
                params = {"scale": self.raw(layer + ".weight_scale")}
            else:
                raise ValueError(f"File conversion of {fmt} is not supported; load/dequantize it with its native loader first.")
            shape = list(tensor.shape)
            if fmt == "nvfp4":
                shape[-1] *= 2
            p = layout.Params(**params, orig_dtype=torch.float32, orig_shape=tuple(shape))
            return QuantizedTensor(tensor, QUANT_ALGOS[fmt]["comfy_tensor_layout"], p).dequantize().float()
        if tensor.dtype in (torch.float8_e4m3fn, torch.float8_e5m2, torch.int8):
            scale_key = layer + ".scale_weight"
            if scale_key in self.index:
                scale = self.raw(scale_key).float()
                if scale.numel() > 1:
                    scale = scale.reshape(-1, *([1] * (tensor.ndim - 1)))
                dense = tensor.float() * scale
                group_key = layer + ".hadamard_group"
                group = int(self.raw(group_key).item()) if group_key in self.index else 0
                if group:
                    if group < 1 or group & (group - 1) or dense.shape[-1] % group:
                        raise ValueError(f"Invalid legacy ConvRot group: {key}")
                    h = torch.ones((1, 1))
                    while h.shape[0] < group:
                        h = torch.cat((torch.cat((h, h), 1), torch.cat((h, -h), 1)), 0)
                    dense = (dense.reshape(*dense.shape[:-1], -1, group) @ (h / math.sqrt(group))).reshape(tensor.shape)
                return dense
            if tensor.dtype == torch.int8 and key.endswith(".weight"):
                raise ValueError(f"INT8 weight has no recognized scale: {key}")
        return tensor.float() if tensor.is_floating_point() else tensor

    def copy(self, writer, key, output_key=None):
        output_key = output_key or key
        writer.add(output_key, self.raw(key))
        for side in self.related(key):
            writer.add(layer_name(output_key) + side[len(layer_name(key)):], self.raw(side))
        config = self.configs.get(layer_name(key))
        if config and layer_name(key) + ".comfy_quant" not in self.index:
            writer.add(layer_name(output_key) + ".comfy_quant", marker(config))


def marker(config):
    return torch.tensor(list(json.dumps(config).encode("utf-8")), dtype=torch.uint8)


def encode(writer, key, tensor, fmt):
    if fmt not in FORMATS or fmt == "preserve":
        raise ValueError(f"An explicit output format is required: {fmt}")
    if not tensor.is_floating_point():
        writer.add(key, tensor)
        return
    if not torch.isfinite(tensor).all():
        raise ValueError(f"Non-finite values in {key}; conversion stopped.")
    floats = {"fp32": torch.float32, "fp16": torch.float16, "bf16": torch.bfloat16}
    if fmt in floats:
        converted = tensor.to(floats[fmt])
        if not torch.isfinite(converted).all():
            raise ValueError(f"{key} exceeds {fmt} range; use bf16 or fp32.")
        writer.add(key, converted)
        return
    # Native quantized kernels operate on Linear weights. Keep convolution,
    # normalization, embeddings, biases and other buffers in bfloat16.
    eligible = key.endswith(".weight") and tensor.ndim == 2 and not any(
        word in key.lower() for word in ("embed", "norm", "position", "token"))
    if not eligible:
        writer.add(key, tensor.to(torch.bfloat16))
        return
    layer = layer_name(key)
    if fmt.startswith("int8"):
        from comfy_kitchen.tensor import TensorWiseINT8Layout
        convrot = fmt == "int8_convrot" and tensor.shape[-1] % 256 == 0
        q, params = TensorWiseINT8Layout.quantize(tensor.float(), per_channel=fmt != "int8_tensor",
                                               convrot=convrot, convrot_groupsize=256)
        writer.add(key, q)
        writer.add(layer + ".weight_scale", params.scale)
        config = {"format": "int8_tensorwise"}
        if convrot:
            config.update(convrot=True, convrot_groupsize=256)
        writer.add(layer + ".comfy_quant", marker(config))
    else:
        dtype = torch.float8_e5m2 if fmt == "fp8_e5m2" else torch.float8_e4m3fn
        maximum = torch.finfo(dtype).max
        weight = tensor.float()
        if fmt == "fp8_e4m3fn_scaled":
            scale = (weight.abs().max() / maximum).clamp_min(1e-30).reshape(1)
            writer.add(key, (weight / scale).clamp(-maximum, maximum).to(dtype))
            writer.add(layer + ".weight_scale", scale)
            writer.add(layer + ".comfy_quant", marker({"format": "float8_e4m3fn"}))
        else:
            writer.add(key, weight.clamp(-maximum, maximum).to(dtype))
            writer.add(layer + ".weight_scale", torch.ones(1, dtype=torch.float32))
            writer.add(layer + ".comfy_quant", marker({"format": "float8_e5m2" if dtype == torch.float8_e5m2 else "float8_e4m3fn"}))


def finish_markers(source, writer):
    # Keep legacy sentinels only where legacy scale tensors were preserved.
    for key in source.index:
        if key.rsplit(".", 1)[-1] in SENTINELS and any(k.endswith(".scale_weight") for k in writer.header):
            writer.add(key, source.raw(key))


def output_metadata(source, operation, **details):
    meta = dict(source.metadata)
    # Native layer markers are written into the tensor block. Do not retain a
    # stale header recipe that ComfyUI would apply over the new markers.
    meta.pop("_quantization_metadata", None)
    return with_history(meta, operation, **details)


def convert(source, destination, fmt, scope="diffusion", progress=lambda *_: None, overwrite=False):
    source = source if isinstance(source, TensorSource) else TensorSource(source)
    if fmt == "preserve":
        raise ValueError("Conversion needs a target format; use Save Model to preserve the source.")
    meta = output_metadata(source, "convert", target=fmt, scope=scope)
    with TensorWriter(destination, meta, overwrite) as writer:
        for i, key in enumerate(source.keys):
            progress(i, len(source.keys))
            if selected(key, scope):
                encode(writer, key, source.dense(key), fmt)
            else:
                source.copy(writer, key)
        finish_markers(source, writer)
    return ModelAsset(str(destination), meta)


@dataclass(frozen=True, init=False)
class ModelAsset:
    _path: str
    metadata: dict
    tensors: dict | None = field(default=None, repr=False, compare=False)

    def __init__(self, path, metadata, tensors=None):
        object.__setattr__(self, "_path", str(path))
        object.__setattr__(self, "metadata", metadata)
        object.__setattr__(self, "tensors", tensors)

    @property
    def path(self):
        # Existing file consumers continue to work. Save Model can use the RAM
        # tensors directly and never needs this temporary file.
        if self.tensors is not None and not Path(self._path).exists():
            save_tensors(self.tensors, self._path, self.metadata)
        return self._path


def model_config(source):
    import comfy.model_detection as detection
    shapes = {k: torch.empty(info["shape"], dtype=DTYPES.get(info["dtype"], torch.uint8), device="meta")
              for k, info in source.headers.items()}
    prefix = detection.unet_prefix_from_state_dict(shapes)
    return detection.model_config_from_unet(shapes, prefix, metadata=source.metadata), prefix


def architecture(source):
    try:
        config, prefix = model_config(source)
        if config is not None:
            name = type(config).__name__
            if name == "Flux":
                name = "Flux 1 Dev / guidance-enabled variant" if config.unet_config.get("guidance_embed") else "Flux family"
            elif name == "FluxSchnell":
                name = "Flux 1 Schnell / distilled variant"
            return {"name": name, "confidence": "tensor signature", "prefix": prefix,
                    "note": "Architecture detection does not establish checkpoint identity."}
    except (ValueError, KeyError, TypeError, AttributeError, RuntimeError, ImportError):
        pass
    return {"name": "Unknown", "confidence": "unknown", "note": "No installed ComfyUI detector matched this tensor structure."}


def extraction_entries(source, scope):
    """Map saved text-encoder layouts to ComfyUI's generic adapter key space.

    Run native key conversion on one meta tensor at a time to discover names
    and q/k/v splits without allocating complete text encoders in fp32.
    """
    entries = {}
    config = None
    if any(component(k) == "text" and selected(k, scope) for k in source.keys):
        config, _ = model_config(source)
    for key in source.keys:
        if not selected(key, scope) or not key.endswith((".weight", ".in_proj_weight", ".text_projection")):
            continue
        if component(key) != "text":
            entries[canonical(key)] = (key, None, None)
            continue
        if config is None:
            if key.startswith("text_encoders."):
                entries[key] = (key, None, None)
                continue
            raise ValueError("Cannot map this checkpoint's text encoder to a ComfyUI LoRA; select diffusion-only extraction.")
        info = source.headers[key]
        shapes = {key: torch.empty(info["shape"], device="meta")}
        mapped = config.process_clip_state_dict(shapes)
        for output in mapped:
            if output.endswith(".weight"):
                entries["text_encoders." + output] = (key, output, config)
    return entries


def extraction_tensor(source, entry):
    key, mapped, config = entry
    tensor = source.dense(key)
    return config.process_clip_state_dict({key: tensor})[mapped] if config is not None else tensor


def inspect_model(path, max_rows=5000):
    path = clean_path(path)
    if path.suffix.lower() == ".gguf":
        try:
            from gguf import GGUFReader
        except ImportError as exc:
            raise ValueError("GGUF inspection requires the optional gguf Python package.") from exc
        reader = GGUFReader(str(path))
        rows = [{"name": t.name, "shape": [int(x) for x in t.shape], "dtype": str(t.tensor_type),
                 "elements": math.prod(int(x) for x in t.shape), "bytes": int(t.n_bytes)} for t in reader.tensors]
        arch = {"name": "Unknown", "confidence": "unknown"}
        field = reader.fields.get("general.architecture")
        if field is not None:
            arch = {"name": str(field.contents()), "confidence": "GGUF metadata"}
        metadata = {}
    else:
        source = TensorSource(path)
        rows = [{"name": k, "shape": v["shape"], "dtype": v["dtype"],
                 "elements": math.prod(v["shape"]), "bytes": v["data_offsets"][1] - v["data_offsets"][0],
                 "component": component(k), "auxiliary": side_tensor(k)} for k, v in source.headers.items()]
        arch, metadata = architecture(source), source.metadata
    counts = Counter(r["dtype"] for r in rows)
    params = sum(r["elements"] for r in rows if not r.get("auxiliary"))
    return {"path": str(path), "architecture": arch, "tensor_count": len(rows), "stored_elements": params,
            "tensor_bytes": sum(r["bytes"] for r in rows), "estimated_fp16_bytes": params * 2,
            "dtypes": dict(counts), "metadata": metadata, "rows": sorted(rows, key=lambda r: r["name"])[:max_rows],
            "rows_truncated": max(0, len(rows) - max_rows),
            "memory_note": "FP16 estimate excludes activations and runtime overhead; packed formats may store multiple parameters per element."}


def compare_models(a, b, scope="diffusion"):
    a = a if isinstance(a, TensorSource) else TensorSource(a)
    b = b if isinstance(b, TensorSource) else TensorSource(b)
    ka = {k for k, raw in a.canon.items() if selected(raw, scope)}
    kb = {k for k, raw in b.canon.items() if selected(raw, scope)}
    shapes, dtypes = [], []
    for key in sorted(ka & kb):
        va, vb = a.headers[a.canon[key]], b.headers[b.canon[key]]
        if va["shape"] != vb["shape"]:
            shapes.append({"name": key, "a": va["shape"], "b": vb["shape"]})
        if va["dtype"] != vb["dtype"]:
            dtypes.append({"name": key, "a": va["dtype"], "b": vb["dtype"]})
    return {"common": len(ka & kb), "only_a": sorted(ka - kb), "only_b": sorted(kb - ka),
            "shape_mismatches": shapes, "dtype_mismatches": dtypes,
            "structurally_compatible": bool(ka & kb) and ka == kb and not shapes,
            "note": "Matching shapes are necessary but do not guarantee semantic merge compatibility."}


def blend(a, b, weight, strategy, base=None, density=.5, lam=1., top=.1, bottom=.01, generator=None):
    """Ray's nine strategies; fresh buffers keep all input branches immutable."""
    w, v = float(weight), 1. - float(weight)
    if strategy == "LERP":
        return a * w + b * v
    if strategy == "SLERP":
        af, bf = a.flatten(), b.flatten()
        norm = af.norm() * bf.norm()
        if norm <= 1e-20:
            return a * w + b * v
        dot = ((af @ bf) / norm).clamp(-1., 1.)
        if dot.abs() > .9995:
            return a * w + b * v
        theta = torch.acos(dot)
        return (torch.sin(w * theta) * a + torch.sin(v * theta) * b) / torch.sin(theta)
    if strategy not in STRATEGIES or base is None:
        raise ValueError(f"{strategy} requires a compatible base model.")
    if not 0 <= density <= 1 or not 0 <= top < 1 or not 0 <= bottom < 1 or top + bottom >= 1:
        raise ValueError("Density must be in [0,1]; trims must sum to less than 1.")
    da, db = a - base, b - base
    def sparsify(t):
        if t.numel() == 0:
            return t
        if strategy == "TIES":
            count = min(t.numel(), max(0, math.ceil(t.numel() * density)))
            if count == 0:
                return torch.zeros_like(t)
            threshold = t.abs().flatten().topk(count).values[-1]
            return t * (t.abs() >= threshold)
        if strategy.startswith("DARE"):
            if density == 0:
                return torch.zeros_like(t)
            return t * (torch.rand(t.shape, generator=generator) < density) / density
        if strategy.startswith("DELLA"):
            probs = (t.abs() / t.abs().mean().clamp_min(1e-8)).pow(lam).mul(density).clamp(0, 1)
            return t * (torch.rand(t.shape, generator=generator) < probs) / probs.clamp_min(1e-3)
        if strategy.startswith("Breadcrumbs"):
            flat = t.abs().flatten()
            lower = torch.quantile(flat, bottom) if bottom else flat.min()
            upper = torch.quantile(flat, 1 - top) if top else flat.max()
            return t * ((t.abs() >= lower) & (t.abs() <= upper))
        return t
    da, db = sparsify(da), sparsify(db)
    if strategy == "TIES" or strategy.endswith("-TIES"):
        sign = (w * da + v * db).sign()
        sign = torch.where(sign == 0, 1., sign)
        da = da * (da.sign() == sign)
        db = db * (db.sign() == sign)
        count = ((da != 0).float() + (db != 0).float()).clamp_min(1.)
        return base + (w * da + v * db) / count
    return base + w * da + v * db


def resize_tensor(t, shape, mode):
    if tuple(t.shape) == tuple(shape):
        return t
    if mode == "trim":
        return t[tuple(slice(0, d) for d in shape)]
    if mode == "pad":
        padding = [n for cur, dst in zip(reversed(t.shape), reversed(shape)) for n in (0, dst-cur)]
        return torch.nn.functional.pad(t, padding)
    raise ValueError(f"Shape mismatch: {list(t.shape)} vs {list(shape)}")


def merge_models(a, b, destination, strategy="LERP", weight=.5, base=None, fmt="bf16",
                 scope="diffusion", mismatch="forbid", seed=0, density=.5, lam=1., top=.1,
                 bottom=.01, block_weights=None, progress=lambda *_: None, fast_merge=False):
    a, b = TensorSource(a), TensorSource(b)
    base = TensorSource(base) if base else None
    if strategy not in STRATEGIES or not 0 <= weight <= 1:
        raise ValueError("Unknown merge strategy or weight outside [0,1].")
    if strategy not in ("LERP", "SLERP") and base is None:
        raise ValueError(f"Select an explicit base model for {strategy}.")
    if mismatch not in ("forbid", "intersect", "pad", "trim"):
        raise ValueError("Unknown mismatch policy.")
    weights = metadata_fields(block_weights)
    if any(not isinstance(v, (int, float)) or not math.isfinite(v) or not 0 <= v <= 1 for v in weights.values()):
        raise ValueError("Block weights must map tensor prefixes to ratios in [0,1].")
    check = compare_models(a, b, scope)
    if not check["common"]:
        raise ValueError("Models have no matching tensors in the selected components.")
    if (check["only_a"] or check["only_b"]) and mismatch == "forbid":
        raise ValueError("Tensor key mismatch; Intersect, Pad and Trim preserve tensors found in only one input. "
                         f"Only in A: {check['only_a'][:3]}; only in B: {check['only_b'][:3]}.")
    if check["shape_mismatches"] and mismatch not in ("pad", "trim"):
        raise ValueError(f"Shape mismatch: {check['shape_mismatches'][0]['name']}")
    common = {k for k in a.canon.keys() & b.canon.keys() if selected(a.canon[k], scope)}
    if base is not None and any(k not in base.canon for k in common):
        raise ValueError("Base model is missing required tensors.")
    meta = output_metadata(a, "merge", strategy=strategy, weight_a=weight, seed=int(seed), scope=scope,
                           base=str(base.path) if base else None, density=density, lam=lam, top=top, bottom=bottom,
                           mismatch=mismatch, block_weights=weights, source_a=str(a.path), source_b=str(b.path))
    with ExitStack() as stack:
        for source in (a, b, base):
            if source is not None:
                stack.enter_context(source.opened())
        writer = stack.enter_context(MemoryTensorWriter(meta) if fast_merge else TensorWriter(destination, meta))
        for i, key in enumerate(a.keys):
            progress(i, len(a.keys))
            ck = canonical(key)
            if ck not in common:
                a.copy(writer, key)
                continue
            ta, tb = a.dense(key), b.dense(b.canon[ck])
            if not ta.is_floating_point() or not tb.is_floating_point():
                if not torch.equal(ta, tb):
                    raise ValueError(f"Non-floating buffers differ: {key}")
                writer.add(key, ta)
                continue
            shape = tuple(ta.shape)
            if ta.shape != tb.shape:
                if ta.ndim != tb.ndim:
                    raise ValueError(f"Tensor ranks differ: {key}")
                fn = max if mismatch == "pad" else min
                shape = tuple(fn(x,y) for x,y in zip(ta.shape, tb.shape))
                ta, tb = resize_tensor(ta, shape, mismatch), resize_tensor(tb, shape, mismatch)
            base_t = base.dense(base.canon[ck]) if base else None
            if base_t is not None:
                if base_t.ndim != len(shape):
                    raise ValueError(f"Base tensor rank differs: {key}")
                if tuple(base_t.shape) != shape and mismatch not in ("pad", "trim"):
                    raise ValueError(f"Base tensor shape differs: {key}")
                if tuple(base_t.shape) != shape:
                    if mismatch == "pad" and any(x > y for x,y in zip(base_t.shape, shape)):
                        raise ValueError(f"Base tensor is larger than pad target: {key}")
                    if mismatch == "trim" and any(x < y for x,y in zip(base_t.shape, shape)):
                        raise ValueError(f"Base tensor is smaller than trim target: {key}")
                    base_t = resize_tensor(base_t, shape, mismatch)
            ratio = weight
            for prefix in sorted(weights, key=len):
                if key.startswith(prefix) or ck.startswith(prefix):
                    ratio = float(weights[prefix])
            tensor_seed = (int(seed) + int.from_bytes(hashlib.sha256(ck.encode()).digest()[:8], "little")) % (2**63)
            result = blend(ta.float(), tb.float(), ratio, strategy, base_t, density, lam, top, bottom,
                           torch.Generator().manual_seed(tensor_seed))
            encode(writer, key, result, fmt)
        if mismatch != "forbid":
            for ck in check["only_b"]:
                key = b.canon[ck]
                output_key = ck
                if any(k.startswith("model.diffusion_model.") for k in a.keys) and ck.startswith("diffusion_model."):
                    output_key = "model." + ck
                elif not any(k.startswith(("model.diffusion_model.", "diffusion_model.")) for k in a.keys) and ck.startswith("diffusion_model."):
                    output_key = ck[len("diffusion_model."):]
                b.copy(writer, key, output_key)
        finish_markers(a, writer)
    progress(len(a.keys), len(a.keys))
    return ModelAsset(str(destination), meta, writer.tensors if fast_merge else None), check


def extract_lora(finetuned, base, destination, rank=16, alpha=0., scope="diffusion",
                 dtype="bf16", include_embeddings=False, progress=lambda *_: None):
    ft, base = TensorSource(finetuned), TensorSource(base)
    if rank < 1 or alpha < 0 or not math.isfinite(alpha):
        raise ValueError("Rank must be positive; alpha must be finite and nonnegative (0 = actual rank).")
    if dtype not in ("fp32", "fp16", "bf16"):
        raise ValueError("LoRA output dtype must be fp32, fp16 or bf16.")
    report = {"extracted": 0, "skipped": [], "rank": rank, "alpha": alpha, "layers": []}
    norm_sq = residual_sq = 0.
    meta = with_history({}, "extract_lora", finetuned=str(ft.path), base=str(base.path), rank=rank,
                        alpha=alpha, scope=scope)
    ft_entries, base_entries = extraction_entries(ft, scope), extraction_entries(base, scope)
    keys = sorted(ft_entries)
    if not keys:
        raise ValueError("No weights in the selected components.")
    with TensorWriter(destination, meta) as writer:
        for i, key in enumerate(keys):
            progress(i, len(keys))
            ck = key
            if ck not in base_entries:
                raise ValueError(f"Base model is missing {key}")
            if not include_embeddings and any(w in key.lower() for w in ("embed", "position", "token")):
                report["skipped"].append(key)
                continue
            a, b = extraction_tensor(ft, ft_entries[key]), extraction_tensor(base, base_entries[ck])
            if a.shape != b.shape:
                raise ValueError(f"Base tensor shape differs: {key}")
            if a.ndim < 2 or not a.is_floating_point():
                report["skipped"].append(key)
                continue
            delta = (a.float() - b.float()).flatten(start_dim=1)
            if not torch.isfinite(delta).all():
                raise ValueError(f"Non-finite model difference: {key}")
            if not torch.count_nonzero(delta):
                report["skipped"].append(key)
                continue
            u, s, vh = torch.linalg.svd(delta, full_matrices=False)
            r = min(rank, *delta.shape)
            actual_alpha = float(alpha) if alpha else float(r)
            factor = s[:r].sqrt() * math.sqrt(r / actual_alpha)
            up, down = u[:, :r] * factor, vh[:r] * factor[:, None]
            if a.ndim > 2:
                up = up.reshape(a.shape[0], r, *([1] * (a.ndim - 2)))
                down = down.reshape(r, *a.shape[1:])
            prefix = ck[:-7]
            writer.add(prefix + ".lora_up.weight", up.to({"fp32": torch.float32, "fp16": torch.float16, "bf16": torch.bfloat16}[dtype]))
            writer.add(prefix + ".lora_down.weight", down.to({"fp32": torch.float32, "fp16": torch.float16, "bf16": torch.bfloat16}[dtype]))
            writer.add(prefix + ".alpha", torch.tensor(actual_alpha))
            total = float(s.square().sum())
            residual = max(0., total - float(s[:r].square().sum()))
            norm_sq += total
            residual_sq += residual
            report["extracted"] += 1
            report["layers"].append({"name": key, "rank": r, "relative_error": math.sqrt(residual / total) if total else 0.})
        if not report["extracted"]:
            raise ValueError("No nonzero compatible weight differences; no LoRA was saved.")
        report["relative_error"] = math.sqrt(residual_sq / norm_sq) if norm_sq else 0.
        writer.metadata["ray.model_tools.extraction"] = json.dumps(report)
    return ModelAsset(str(destination), writer.metadata), report
