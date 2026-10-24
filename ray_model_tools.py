"""ComfyUI nodes for Ray's file and live-model operations."""
from __future__ import annotations

from contextlib import ExitStack, contextmanager
from pathlib import Path
import importlib
import uuid

core = importlib.import_module(".model_tools", __package__) if __package__ else importlib.import_module("model_tools")

CATEGORY = "👑 Ray/🧰 Model Tools"
SCOPES = ["diffusion", "diffusion_and_text", "text_encoder", "all"]
MODEL_IDS = ["RayModelLoadAs", "RayModelConvert", "RayModelSave", "RayModelMetadata",
             "RayModelMetadataSave", "RayModelMerge", "RayModelInspector", "RayModelCompare",
             "RayLoraBake", "RayLoraExtract"]


def text(default="", multiline=False, **options):
    return ("STRING", {"default": default, "multiline": multiline, **options})


def combo(values, default=None, **options):
    return (values, {"default": default or values[0], **options})


def number(default, minimum=0., maximum=1., step=.01):
    return ("FLOAT", {"default": default, "min": minimum, "max": maximum, "step": step})


def files(kind):
    import folder_paths
    names = []
    groups = ["checkpoints", "diffusion_models"] if kind == "models" else ["loras"]
    for group in groups:
        try:
            names.extend(f"{group}: {name}" for name in folder_paths.get_filename_list(group)
                         if name.lower().endswith(".safetensors"))
        except KeyError:
            pass
    return ["Select a file or use path…", *sorted(set(names))]


def resolve_file(name="", path=""):
    import folder_paths
    if path.strip():
        result = core.clean_path(path)
    elif name.startswith(("checkpoints: ", "diffusion_models: ", "loras: ")):
        group, filename = name.split(": ", 1)
        resolved = folder_paths.get_full_path(group, filename)
        if not resolved:
            raise ValueError(f"Model file not found: {filename}")
        result = core.clean_path(resolved)
    elif name.strip() and name != "Select a file or use path…":
        result = core.clean_path(name)
    else:
        raise ValueError("Select a model file or enter its path.")
    if not result.exists():
        raise ValueError(f"File or model directory not found: {result}")
    return str(result)


def cache_path(label="model"):
    import folder_paths
    root = Path(folder_paths.get_temp_directory()) / "ray_model_tools"
    root.mkdir(parents=True, exist_ok=True)
    return str(root / f"{label}-{uuid.uuid4().hex}.safetensors")


def save_path(filename_prefix, output_path, extension):
    import folder_paths
    if output_path.strip():
        path = core.clean_path(output_path)
        if path.suffix.lower() != extension:
            raise ValueError(f"Output path must end in {extension}.")
        return str(path)
    folder, name, counter, _, _ = folder_paths.get_save_image_path(filename_prefix, folder_paths.get_output_directory())
    return str(Path(folder) / f"{name}_{counter:05}_{extension}")


def progress():
    import comfy.utils
    import comfy.model_management as mm
    bar = comfy.utils.ProgressBar(1000)
    def update(current, total):
        mm.throw_exception_if_processing_interrupted()
        bar.update_absolute(int(1000 * current / max(1, total)), 1000)
    return update


def model_metadata(model):
    return dict(getattr(model, "attachments", {}).get("ray_model_metadata", {})) if model else {}


def attach_metadata(model, metadata):
    if model is not None:
        model.set_attachments("ray_model_metadata", dict(metadata))


def snapshot(model, path, clip=None, vae=None, metadata=None):
    import comfy.sd
    meta = dict(metadata if metadata is not None else model_metadata(model))
    meta.pop("_quantization_metadata", None)
    comfy.sd.save_checkpoint(path, model, clip=clip, vae=vae, metadata=core.embedded_metadata(meta))
    core.read_header(path)
    return core.ModelAsset(path, meta)


@contextmanager
def source_path(model=None, model_data=None, path="", clip=None, vae=None):
    if model is not None:
        temp = cache_path("snapshot")
        try:
            yield snapshot(model, temp, clip, vae).path
        finally:
            try:
                Path(temp).unlink(missing_ok=True)
            except PermissionError:
                pass  # Windows can retain an mmap until ComfyUI releases its tensor.
    elif model_data is not None:
        if not isinstance(model_data, core.ModelAsset):
            raise ValueError("Connect a Ray model_data output.")
        yield model_data.path
    elif path.strip():
        yield resolve_file(path=path)
    else:
        raise ValueError("Connect a MODEL or model_data, or enter a model path.")


def load_asset(asset, kind="auto", dtype="auto", components=True):
    import comfy.sd
    import folder_paths
    source = core.TensorSource(asset.path)
    options = {}
    if dtype in ("fp32", "fp16", "bf16"):
        options["dtype"] = {"fp32": core.torch.float32, "fp16": core.torch.float16, "bf16": core.torch.bfloat16}[dtype]
    if kind == "auto":
        kind = "checkpoint" if any(core.component(k) != "diffusion" for k in source.keys) else "diffusion"
    if source.path.is_dir():
        # ComfyUI's native loaders accept state dictionaries, not shard directories.
        state = {k: source.raw(k) for k in source.index}
        if kind == "checkpoint":
            loaded = comfy.sd.load_state_dict_guess_config(state, output_vae=components, output_clip=components,
                embedding_directory=folder_paths.get_folder_paths("embeddings"), model_options=options, metadata=source.metadata)
            if loaded is None:
                raise ValueError("ComfyUI could not detect this checkpoint architecture.")
            model, clip, vae = loaded[:3]
        else:
            model = comfy.sd.load_diffusion_model_state_dict(state, model_options=options, metadata=source.metadata)
            clip = vae = None
    elif kind == "checkpoint":
        model, clip, vae = comfy.sd.load_checkpoint_guess_config(asset.path,
            output_vae=components, output_clip=components, model_options=options,
            embedding_directory=folder_paths.get_folder_paths("embeddings"))[:3]
    else:
        model = comfy.sd.load_diffusion_model(asset.path, model_options=options)
        clip = vae = None
    if model is None:
        raise ValueError("ComfyUI could not load this model architecture. File-only inspection and conversion remain available.")
    attach_metadata(model, source.metadata)
    return model, clip, vae


def result(outputs, report):
    return {"ui": {"model_tools": [report]}, "result": tuple(outputs)}


def changed_path(path="", **_):
    if not path.strip():
        return ""
    p = core.clean_path(path)
    files_ = sorted(p.glob("*.safetensors*")) if p.is_dir() else [p]
    try:
        return tuple((str(f), f.stat().st_mtime_ns, f.stat().st_size) for f in files_)
    except OSError:
        return float("nan")


class RayModelLoadAs:
    DESCRIPTION = "Choose a supported diffusion model or checkpoint file, or a sharded model folder. Disable load_result for file-only merge/convert/save; Auto then passes through the source without loading or rewriting weights. FP8→FP16 cannot restore lost precision."
    CATEGORY, FUNCTION = CATEGORY, "load"
    RETURN_TYPES = ("MODEL", "CLIP", "VAE", "RAY_MODEL_DATA", "RAY_MODEL_METADATA", "STRING")
    RETURN_NAMES = ("model", "clip", "vae", "model_data", "metadata", "report")

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"model_name": text(), "weight_format": combo(["auto", *core.FORMATS]),
                             "loader": combo(["auto", "checkpoint", "diffusion"]),
                             "load_components": ("BOOLEAN", {"default": True})},
                "optional": {"path": text(), "model_data": ("RAY_MODEL_DATA",),
                             "load_result": ("BOOLEAN", {"default": True, "tooltip": "Disable for file-only processing. With Auto or Preserve, model_data references the original file without loading or converting it."})}}

    @classmethod
    def IS_CHANGED(cls, model_name="", path="", model_data=None, **kwargs):
        return changed_path(path=model_data.path if model_data else resolve_file(model_name, path))

    def load(self, model_name="", weight_format="auto", loader="auto", load_components=True, path="", model_data=None, load_result=True):
        source = core.TensorSource(model_data.path if model_data else resolve_file(model_name, path))
        asset = core.ModelAsset(str(source.path), source.metadata)
        target = weight_format
        legacy = False
        if load_result and target in ("auto", "preserve") and any(k.rsplit(".", 1)[-1] == "scaled_int8" for k in source.index):
            # Decode the standalone suite's legacy INT8 layout into the native format.
            target = "int8_row"
            legacy = True
        elif load_result and target in ("auto", "preserve") and any(k.endswith(".scale_weight") for k in source.index):
            target = "fp8_e4m3fn_scaled"
            legacy = True
        if target not in ("auto", "preserve"):
            asset = core.convert(source, cache_path("converted"), target, scope="all" if legacy else "diffusion", progress=progress())
        model, clip, vae = load_asset(asset, loader, target, load_components) if load_result else (None, None, None)
        report = {"operation": "load", "source": str(source.path), "weight_format": target,
                  "loaded": load_result, "architecture": type(model.model).__name__ if model is not None else None,
                  "clip": clip is not None, "vae": vae is not None}
        return result((model, clip, vae, asset, asset.metadata, core.json_text(report)), report)


class RayModelConvert:
    DESCRIPTION = "Convert a model file or the effective state of a connected MODEL. Disable load_result for file-only processing. Non-Linear layers stay bf16 for quantized output."
    CATEGORY, FUNCTION = CATEGORY, "convert"
    RETURN_TYPES = ("MODEL", "CLIP", "VAE", "RAY_MODEL_DATA", "RAY_MODEL_METADATA", "STRING")
    RETURN_NAMES = ("model", "clip", "vae", "model_data", "metadata", "report")

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"weight_format": combo(core.FORMATS[1:], "bf16"), "components": combo(SCOPES),
                             "load_result": ("BOOLEAN", {"default": True})},
                "optional": {"model": ("MODEL",), "clip": ("CLIP",), "vae": ("VAE",),
                             "model_data": ("RAY_MODEL_DATA",), "path": text()}}

    IS_CHANGED = staticmethod(changed_path)

    def convert(self, weight_format, components="diffusion", load_result=True, model=None, clip=None, vae=None, model_data=None, path=""):
        with source_path(model, model_data, path, clip, vae) as src:
            asset = core.convert(src, cache_path("converted"), weight_format, components, progress())
        loaded = load_asset(asset, dtype=weight_format) if load_result else (None, None, None)
        report = {"operation": "convert", "weight_format": weight_format, "components": components,
                  "bytes": Path(asset.path).stat().st_size, "loaded": load_result}
        return result((*loaded, asset, asset.metadata, core.json_text(report)), report)


class RayModelSave:
    DESCRIPTION = "Save the current effective MODEL, baking active LoRA/merge patches. Connect CLIP/VAE to include them. Metadata is merged by default; existing files require overwrite."
    CATEGORY, FUNCTION, OUTPUT_NODE = CATEGORY, "save", True
    RETURN_TYPES, RETURN_NAMES = ("RAY_MODEL_DATA", "STRING"), ("model_data", "saved_path")

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"filename_prefix": text("model_tools/Ray_Model"), "metadata_mode": combo(["merge", "replace"]),
                             "overwrite": ("BOOLEAN", {"default": False})},
                "optional": {"model": ("MODEL",), "clip": ("CLIP",), "vae": ("VAE",),
                             "model_data": ("RAY_MODEL_DATA",), "metadata": ("RAY_MODEL_METADATA",),
                             "metadata_json": text("", True), "path": text(), "output_path": text()}}

    def save(self, filename_prefix="model_tools/Ray_Model", metadata_mode="merge", overwrite=False,
             model=None, clip=None, vae=None, model_data=None, metadata=None, metadata_json="", path="", output_path=""):
        destination = save_path(filename_prefix, output_path, ".safetensors")
        with source_path(model, model_data, path, clip, vae) as src:
            original = core.TensorSource(src).metadata
            supplied = core.metadata_fields(metadata)
            supplied.update(core.metadata_fields(metadata_json))
            if "_quantization_metadata" in supplied and supplied["_quantization_metadata"] != original.get("_quantization_metadata"):
                raise ValueError("Quantization metadata describes the actual weights and cannot be replaced by an unrelated recipe.")
            meta = dict(original) if metadata_mode == "merge" else {k:v for k,v in original.items() if k == "_quantization_metadata"}
            meta.update(supplied)
            if metadata_mode == "merge" and core.HISTORY in original:
                meta[core.HISTORY] = original[core.HISTORY]
            meta = core.with_history(meta, "save")
            core.rewrite_metadata(src, destination, meta, overwrite)
        asset = core.ModelAsset(destination, core.embedded_metadata(meta))
        return result((asset, destination), {"operation": "save", "saved_path": destination})


class RayModelMetadata:
    DESCRIPTION = "Load model metadata or a JSON sidecar. Use Load / Edit to populate the editable table. Strings remain strings; nested JSON can be expanded without changing it."
    CATEGORY, FUNCTION, OUTPUT_NODE = CATEGORY, "load", True
    RETURN_TYPES, RETURN_NAMES = ("RAY_MODEL_METADATA", "STRING"), ("metadata", "metadata_json")

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"path": text(), "editor_json": text("", True), "editor_source": text()},
                "optional": {"model_data": ("RAY_MODEL_DATA",), "metadata": ("RAY_MODEL_METADATA",)}}

    IS_CHANGED = staticmethod(changed_path)

    def load(self, path="", editor_json="", editor_source="", model_data=None, metadata=None):
        original = dict(model_data.metadata) if model_data else core.metadata_fields(metadata)
        if path.strip():
            original = core.load_metadata(path)
        if editor_json.strip():
            if path.strip() and editor_source and core.clean_path(path) != core.clean_path(editor_source):
                raise ValueError("The source path changed. Load / Edit the new file before applying the table.")
            original = core.metadata_fields(editor_json)
        return result((original, core.json_text(original)), {"operation": "metadata", "metadata": original, "metadata_json": core.json_text(original)})


class RayModelMetadataSave:
    DESCRIPTION = "Save metadata as a structured JSON sidecar, or apply it to a safetensors copy without changing any tensor bytes."
    CATEGORY, FUNCTION, OUTPUT_NODE = CATEGORY, "save", True
    RETURN_TYPES, RETURN_NAMES = ("STRING",), ("saved_path",)

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"mode": combo(["json_sidecar", "model_copy"]), "filename_prefix": text("model_tools/Ray_Metadata"),
                             "overwrite": ("BOOLEAN", {"default": False})},
                "optional": {"metadata": ("RAY_MODEL_METADATA",), "metadata_json": text("", True),
                             "source_model_path": text(), "output_path": text()}}

    def save(self, mode="json_sidecar", filename_prefix="model_tools/Ray_Metadata", overwrite=False,
             metadata=None, metadata_json="", source_model_path="", output_path=""):
        meta = core.metadata_fields(metadata)
        meta.update(core.metadata_fields(metadata_json))
        destination = save_path(filename_prefix, output_path, ".json" if mode == "json_sidecar" else ".safetensors")
        if mode == "json_sidecar":
            core.atomic_json(destination, {"schema": core.SCHEMA, "metadata": meta}, overwrite)
        elif mode == "model_copy":
            if not source_model_path.strip():
                raise ValueError("Select a source model for model_copy.")
            original = core.TensorSource(source_model_path).metadata
            if "_quantization_metadata" in original:
                if "_quantization_metadata" in meta and meta["_quantization_metadata"] != original["_quantization_metadata"]:
                    raise ValueError("Cannot replace the model's quantization recipe with different metadata.")
                meta["_quantization_metadata"] = original["_quantization_metadata"]
            core.rewrite_metadata(source_model_path, destination, meta, overwrite)
        else:
            raise ValueError("Unknown metadata save mode.")
        return result((destination,), {"operation": "metadata_save", "saved_path": destination})


class RayModelMerge:
    DESCRIPTION = "Merge compatible models connected to model_a/model_b or data_a/data_b with Ray's nine strategies. Task-vector strategies require a base_model or base_data connection. Intersect, Pad and Trim preserve tensors found in only one input; Pad/Trim also resize shared tensors."
    CATEGORY, FUNCTION = CATEGORY, "merge"
    RETURN_TYPES = ("MODEL", "CLIP", "VAE", "RAY_MODEL_DATA", "RAY_MODEL_METADATA", "STRING")
    RETURN_NAMES = ("model", "clip", "vae", "model_data", "metadata", "report")

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"strategy": combo(core.STRATEGIES), "weight_a": number(.5),
            "weight_format": combo(core.FORMATS[1:], "bf16"), "components": combo(SCOPES),
            "mismatch": combo(["forbid", "intersect", "pad", "trim"], tooltip="Forbid: require matching names and shapes. Intersect: merge shared tensors of matching shape. Pad/Trim: resize shared tensors to the larger/smaller shape. Intersect, Pad and Trim preserve tensors present in only one input unchanged."),
            "seed": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff}),
            "density": number(.5), "lambda": number(1., 0., 5.), "top_trim": number(.1, 0., .99),
            "bottom_trim": number(.01, 0., .99), "load_result": ("BOOLEAN", {"default": True})},
            "optional": {"model_a": ("MODEL",), "model_b": ("MODEL",), "base_model": ("MODEL",),
                "clip_a": ("CLIP",), "clip_b": ("CLIP",), "base_clip": ("CLIP",), "vae_a": ("VAE",),
                "data_a": ("RAY_MODEL_DATA",), "data_b": ("RAY_MODEL_DATA",), "base_data": ("RAY_MODEL_DATA",),
                "path_a": text(), "path_b": text(), "base_path": text(), "block_weights": text("{}", True)}}

    @classmethod
    def IS_CHANGED(cls, path_a="", path_b="", base_path="", **_):
        return changed_path(path_a), changed_path(path_b), changed_path(base_path)

    def merge(self, strategy="LERP", weight_a=.5, weight_format="bf16", components="diffusion", mismatch="forbid",
              seed=0, density=.5, top_trim=.1, bottom_trim=.01, load_result=True,
              model_a=None, model_b=None, base_model=None, clip_a=None, clip_b=None, base_clip=None, vae_a=None,
              data_a=None, data_b=None, base_data=None, path_a="", path_b="", base_path="", block_weights="{}", **kwargs):
        if model_a is None and data_a is None and not path_a.strip():
            raise ValueError("Connect Model A to model_a or data_a.")
        if model_b is None and data_b is None and not path_b.strip():
            raise ValueError("Connect Model B to model_b or data_b.")
        with ExitStack() as stack:
            a = stack.enter_context(source_path(model_a, data_a, path_a, clip_a, vae_a))
            b = stack.enter_context(source_path(model_b, data_b, path_b, clip_b))
            needs_base = strategy not in ("LERP", "SLERP")
            base = stack.enter_context(source_path(base_model, base_data, base_path, base_clip)) if needs_base and (base_model or base_data or base_path.strip()) else None
            asset, check = core.merge_models(a, b, cache_path("merged"), strategy, weight_a, base, weight_format,
                components, mismatch, seed, density, kwargs.get("lambda", 1.), top_trim, bottom_trim,
                block_weights, progress())
        loaded = load_asset(asset, dtype=weight_format) if load_result else (None, None, None)
        report = {"operation": "merge", "strategy": strategy, "weight_a": weight_a, "seed": seed, "comparison": check}
        return result((*loaded, asset, asset.metadata, core.json_text(report)), report)


class RayModelInspector:
    DESCRIPTION = "Inspect safetensors/sharded files without loading weights. Optional GGUF inspection needs gguf. A MODEL connection is exported in its effective state first."
    CATEGORY, FUNCTION, OUTPUT_NODE = CATEGORY, "inspect", True
    RETURN_TYPES, RETURN_NAMES = ("STRING", "RAY_MODEL_METADATA"), ("report", "metadata")

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"path": text(), "max_rows": ("INT", {"default": 5000, "min": 1, "max": 100000})},
                "optional": {"model": ("MODEL",), "model_data": ("RAY_MODEL_DATA",)}}

    IS_CHANGED = staticmethod(changed_path)

    def inspect(self, path="", max_rows=5000, model=None, model_data=None):
        with source_path(model, model_data, path) as src:
            report = core.inspect_model(src, max_rows)
        return result((core.json_text(report), report.get("metadata", {})), report)


class RayModelCompare:
    DESCRIPTION = "Compare tensor names, shapes and dtypes before merging. Header comparison does not measure weight similarity."
    CATEGORY, FUNCTION, OUTPUT_NODE = CATEGORY, "compare", True
    RETURN_TYPES, RETURN_NAMES = ("STRING", "BOOLEAN"), ("report", "structurally_compatible")

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"path_a": text(), "path_b": text(), "components": combo(SCOPES)},
                "optional": {"model_a": ("MODEL",), "model_b": ("MODEL",),
                             "data_a": ("RAY_MODEL_DATA",), "data_b": ("RAY_MODEL_DATA",)}}

    @classmethod
    def IS_CHANGED(cls, path_a="", path_b="", **_):
        return changed_path(path_a), changed_path(path_b)

    def compare(self, path_a="", path_b="", components="diffusion", model_a=None, model_b=None, data_a=None, data_b=None):
        with source_path(model_a, data_a, path_a) as a, source_path(model_b, data_b, path_b) as b:
            report = core.compare_models(a, b, components)
        return result((core.json_text(report), report["structurally_compatible"]), report)


class RayLoraBake:
    DESCRIPTION = "Bake a ComfyUI-supported LoRA into a new model, including convolution and adapter formats supported by ComfyUI. Input branches remain unchanged."
    CATEGORY, FUNCTION = CATEGORY, "bake"
    RETURN_TYPES = ("MODEL", "CLIP", "VAE", "RAY_MODEL_DATA", "RAY_MODEL_METADATA", "STRING")
    RETURN_NAMES = ("model", "clip", "vae", "model_data", "metadata", "report")

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"lora_name": combo(files("loras")), "strength_model": number(1., -20., 20.),
                             "strength_clip": number(1., -20., 20.), "weight_format": combo(core.FORMATS, "preserve"),
                             "load_result": ("BOOLEAN", {"default": True})},
                "optional": {"model": ("MODEL",), "clip": ("CLIP",), "vae": ("VAE",),
                             "model_data": ("RAY_MODEL_DATA",), "path": text(), "lora_path": text()}}

    @classmethod
    def IS_CHANGED(cls, path="", lora_path="", lora_name="", **_):
        return changed_path(path), changed_path(resolve_file(lora_name, lora_path))

    def bake(self, lora_name, strength_model=1., strength_clip=1., weight_format="preserve", load_result=True,
             model=None, clip=None, vae=None, model_data=None, path="", lora_path=""):
        import comfy.sd
        import comfy.utils
        import comfy.lora
        import comfy.lora_convert
        adapter_path = resolve_file(lora_name, lora_path)
        if model is None:
            src = model_data or core.ModelAsset(resolve_file(path=path), core.load_metadata(path))
            model, loaded_clip, loaded_vae = load_asset(src)
            clip, vae = clip or loaded_clip, vae or loaded_vae
        if weight_format != "preserve":
            # Apply the new adapter in floating point, then encode the selected
            # target once. Baking into a quantized source first would round away
            # small LoRA deltas before an explicitly requested fp16/fp32 export.
            with source_path(model=model, clip=clip, vae=vae) as original:
                floating = core.convert(original, cache_path("lora-working"), "fp32", "diffusion_and_text", progress())
            model, clip, vae = load_asset(floating, dtype="fp32")
        lora = comfy.utils.load_torch_file(adapter_path, safe_load=True)
        mapping = comfy.lora.model_lora_keys_unet(model.model, {})
        if clip:
            mapping = comfy.lora.model_lora_keys_clip(clip.cond_stage_model, mapping)
        patches = comfy.lora.load_lora(comfy.lora_convert.convert_lora(lora), mapping, log_missing=False)
        if not patches:
            raise ValueError("No LoRA layers match this model or text encoder.")
        patched, patched_clip = comfy.sd.load_lora_for_models(model, clip, lora, strength_model, strength_clip)
        meta = core.with_history(model_metadata(model), "bake_lora", adapter=adapter_path,
                                 strength_model=strength_model, strength_clip=strength_clip)
        attach_metadata(patched, meta)
        asset = snapshot(patched, cache_path("baked"), patched_clip, vae, meta)
        if weight_format != "preserve":
            old = asset.path
            asset = core.convert(asset.path, cache_path("baked-converted"), weight_format, progress=progress())
            Path(old).unlink(missing_ok=True)
        loaded = load_asset(asset, dtype=weight_format) if load_result else (None, None, None)
        report = {"operation": "bake_lora", "matched_layers": len(patches), "adapter": adapter_path,
                  "strength_model": strength_model, "strength_clip": strength_clip, "weight_format": weight_format}
        return result((*loaded, asset, asset.metadata, core.json_text(report)), report)


class RayLoraExtract:
    DESCRIPTION = "Extract a low-rank approximation of finetuned minus base. Supports Linear and convolution weights. Alpha=0 uses each layer's actual rank. Error is the SVD truncation error before output rounding."
    CATEGORY, FUNCTION, OUTPUT_NODE = CATEGORY, "extract", True
    RETURN_TYPES, RETURN_NAMES = ("STRING", "RAY_MODEL_DATA", "STRING"), ("saved_path", "lora_data", "report")

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"filename_prefix": text("model_tools/Ray_Extracted_LoRA"),
            "rank": ("INT", {"default": 16, "min": 1, "max": 4096}), "alpha": number(0., 0., 4096., 1.),
            "components": combo(["diffusion", "diffusion_and_text", "text_encoder"]),
            "weight_format": combo(["bf16", "fp16", "fp32"]), "include_embeddings": ("BOOLEAN", {"default": False})},
            "optional": {"finetuned_model": ("MODEL",), "base_model": ("MODEL",),
                "finetuned_clip": ("CLIP",), "base_clip": ("CLIP",),
                "finetuned_data": ("RAY_MODEL_DATA",), "base_data": ("RAY_MODEL_DATA",),
                "finetuned_path": text(), "base_path": text(), "output_path": text()}}

    @classmethod
    def IS_CHANGED(cls, finetuned_path="", base_path="", **_):
        return changed_path(finetuned_path), changed_path(base_path)

    def extract(self, filename_prefix="model_tools/Ray_Extracted_LoRA", rank=16, alpha=0., components="diffusion",
                weight_format="bf16", include_embeddings=False, finetuned_model=None, base_model=None,
                finetuned_clip=None, base_clip=None, finetuned_data=None, base_data=None,
                finetuned_path="", base_path="", output_path=""):
        destination = save_path(filename_prefix, output_path, ".safetensors")
        with source_path(finetuned_model, finetuned_data, finetuned_path, finetuned_clip) as ft, \
             source_path(base_model, base_data, base_path, base_clip) as base:
            asset, report = core.extract_lora(ft, base, destination, rank, alpha, components, weight_format,
                                              include_embeddings, progress())
        report.update(operation="extract_lora", saved_path=destination)
        return result((destination, asset, core.json_text(report)), report)
