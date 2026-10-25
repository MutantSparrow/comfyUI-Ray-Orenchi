"""Native MODEL lists in one workflow execution, with managed sample offloading."""
import json
from pathlib import Path

import folder_paths

if __package__:
    from .queued_model_spectrum import apply_spectrum, sampling_steps
    from .queued_model_memory import install_model_offload
else:
    from queued_model_spectrum import apply_spectrum, sampling_steps
    from queued_model_memory import install_model_offload


PLACEHOLDER = "Select a diffusion model…"


def additional_models(value="[]"):
    try:
        models = json.loads(value or "[]")
    except (TypeError, ValueError) as error:
        raise ValueError("The queued model list must be a JSON array of model names.") from error
    if not isinstance(models, list) or any(not isinstance(item, str) or not item.strip() for item in models):
        raise ValueError("Choose a model for every row, or remove the empty row.")
    return models


def model_path(model_name):
    if not isinstance(model_name, str) or not model_name.strip() or model_name == PLACEHOLDER:
        raise ValueError("Choose a diffusion model for every row, or remove the empty row.")
    name = model_name.strip().strip('"')
    path = folder_paths.get_full_path("diffusion_models", name)
    if path is None and Path(name).is_absolute():
        path = name
    if not path or not Path(path).is_file():
        raise ValueError(f"Diffusion model not found: {model_name}")
    if Path(path).suffix.lower() not in folder_paths.supported_pt_extensions:
        raise ValueError("Choose a model supported by ComfyUI's native Load Diffusion Model loader.")
    return str(path)


class RayQueuedModelLoader:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "model_name": ("STRING", {
                "default": "",
                "tooltip": "Select a registered diffusion model from the searchable folder dropdown. Search includes every subfolder. Precision and supported quantization are handled automatically by ComfyUI.",
            }),
            "queued_models": ("STRING", {"default": "[]", "tooltip": "Additional models in row order. One execution passes a native MODEL list through the workflow, reusing singleton prompts, seeds and settings."}),
        }, "optional": {
            "spectrum_enabled": ("BOOLEAN", {"default": False, "tooltip": "Enable optional Spectrum forecasting. Auto selects the installed adapter for each model. This approximation can change image/video results; unsupported models keep native sampling."}),
        }, "hidden": {"prompt": "PROMPT", "unique_id": "UNIQUE_ID"}}

    RETURN_TYPES = ("MODEL",)
    RETURN_NAMES = ("MODEL",)
    OUTPUT_TOOLTIPS = ("Native ComfyUI MODEL list in selected row order. Downstream nodes process each model in one execution, reusing singleton prompts, seeds, and settings.",)
    OUTPUT_IS_LIST = (True,)
    FUNCTION = "load"
    CATEGORY = "👑 Ray/🧰 Model Tools"
    DESCRIPTION = "Add diffusion models with + and remove rows with the trash button. One Run outputs a native MODEL list; standard downstream nodes process each model with the same singleton prompts, seeds and settings. Images appear together in one execution's preview. Rebatch Images combines the image list into a tensor batch. Each sampled model and its clones are offloaded through ComfyUI, including on error/cancel. DynamicVRAM also releases its RAM weight buffers; legacy loading can retain CPU weights in the execution cache. Precision is automatic. Loader options contains optional Spectrum autodetection. Keep compatible text encoders and VAE connected separately."

    @classmethod
    def VALIDATE_INPUTS(cls, model_name=None, queued_models="[]"):
        try:
            # Linked STRING values become available only when the source executes.
            if model_name is not None:
                model_path(model_name)
            for name in additional_models(queued_models):
                model_path(name)
        except ValueError as error:
            return str(error)
        return True

    def load(self, model_name, queued_models="[]", spectrum_enabled=False, prompt=None, unique_id=None):
        validation = self.VALIDATE_INPUTS(model_name, queued_models)
        if validation is not True:
            raise ValueError(validation)
        if prompt:
            # This node cannot freeze random numbers created inside a downstream
            # node's function separately for each MODEL list element.
            pending, visited = [str(unique_id)], set()
            while pending:
                current = pending.pop()
                if current in visited:
                    continue
                visited.add(current)
                for node_id, node in prompt.items():
                    inputs = node.get("inputs", {})
                    if any(isinstance(value, list) and len(value) == 2 and str(value[0]) == current for value in inputs.values()):
                        if node.get("class_type") == "RayModelCard" and inputs.get("seed_mode") == "randomize":
                            raise ValueError("Set Model Card's seed mode to Fixed, Increment or Decrement so each model uses the same seeds.")
                        pending.append(str(node_id))
        import comfy.sd
        import comfy.model_management
        models, reports = [], []
        for name in [model_name, *additional_models(queued_models)]:
            comfy.model_management.throw_exception_if_processing_interrupted()
            # Native precision and quantization; no dtype override or conversion.
            model = install_model_offload(comfy.sd.load_diffusion_model(model_path(name), model_options={}))
            if hasattr(model, "set_attachments"):
                model.set_attachments("ray_model_source", name)
            if spectrum_enabled:
                model, report = apply_spectrum(model, prompt, unique_id)
                reports.append({**report, "model": name})
            models.append(model)
        result = (models,)
        return {"ui": {"queued_model_loader": reports}, "result": result} if reports else result

    @classmethod
    def IS_CHANGED(cls, model_name, spectrum_enabled=False, prompt=None, unique_id=None, queued_models="[]", **kwargs):
        try:
            files = []
            for name in [model_name, *additional_models(queued_models)]:
                path = model_path(name)
                stat = Path(path).stat()
                files.append((path, stat.st_mtime_ns, stat.st_size))
            return files, spectrum_enabled, sampling_steps(prompt, unique_id) if spectrum_enabled else None
        except ValueError:
            return model_name
