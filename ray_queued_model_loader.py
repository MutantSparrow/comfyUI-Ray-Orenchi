"""One native diffusion model per queued workflow execution."""
import json
from pathlib import Path

import folder_paths

if __package__:
    from .queued_model_spectrum import apply_spectrum, sampling_steps
else:
    from queued_model_spectrum import apply_spectrum, sampling_steps


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
                "tooltip": "Choose a diffusion model or use the file button. Precision and supported quantization are handled automatically by ComfyUI.",
            }),
            "queued_models": ("STRING", {"default": "[]", "tooltip": "Additional model rows, saved with the workflow. Run in ComfyUI to queue one complete workflow per model."}),
        }, "optional": {
            "spectrum_enabled": ("BOOLEAN", {"default": False, "tooltip": "Enable optional Spectrum forecasting. Auto selects the installed adapter for each model. This approximation can change image/video results; unsupported models keep native sampling."}),
        }, "hidden": {"prompt": "PROMPT", "unique_id": "UNIQUE_ID"}}

    RETURN_TYPES = ("MODEL",)
    RETURN_NAMES = ("MODEL",)
    FUNCTION = "load"
    CATEGORY = "👑 Ray/🧰 Model Tools"
    DESCRIPTION = "Add diffusion models with + and remove rows with the trash button. Run queues the captured workflow once per model, with native automatic precision. Loader options contains an off-by-default Spectrum toggle: auto-selects installed MOSS, MiniMax H3, SDXL/Anima or general Spectrum adapters. Forecasting approximates model evaluations and can change results. Keep compatible text encoders and VAE connected separately."

    @classmethod
    def VALIDATE_INPUTS(cls, model_name=None, queued_models="[]"):
        try:
            # Linked STRING values become available only when the source executes.
            if model_name is not None:
                model_path(model_name)
            if additional_models(queued_models):
                return "Run this multi-model workflow from ComfyUI. For direct API calls, submit one model_name per job with queued_models set to []."
        except ValueError as error:
            return str(error)
        return True

    def load(self, model_name, queued_models="[]", spectrum_enabled=False, prompt=None, unique_id=None):
        validation = self.VALIDATE_INPUTS(model_name, queued_models)
        if validation is not True:
            raise ValueError(validation)
        import comfy.sd
        # Match native Load Diffusion Model's default: no dtype override or conversion.
        model = comfy.sd.load_diffusion_model(model_path(model_name), model_options={})
        if not spectrum_enabled:
            return (model,)
        model, report = apply_spectrum(model, prompt, unique_id)
        return {"ui": {"queued_model_loader": [report]}, "result": (model,)}

    @classmethod
    def IS_CHANGED(cls, model_name, spectrum_enabled=False, prompt=None, unique_id=None, **kwargs):
        try:
            path = model_path(model_name)
            stat = Path(path).stat()
            return path, stat.st_mtime_ns, stat.st_size, spectrum_enabled, sampling_steps(prompt, unique_id) if spectrum_enabled else None
        except ValueError:
            return model_name
