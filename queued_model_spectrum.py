"""Optional adapters to registered Spectrum nodes; no bundled forecasting code."""
import logging


LOG = logging.getLogger(__name__)
PROVIDERS = {
    "moss": ("SpectrumMOSSImageAdaptive", "ComfyUI-Spectrum-MOSS", "https://github.com/Rkkss/ComfyUI-Spectrum-MOSS"),
    "minimax": ("SpectrumApplyMiniMaxH3", "ComfyUI-Spectrum-MiniMax-H3", "https://github.com/xmarre/ComfyUI-Spectrum-MiniMax-H3"),
    "sdxl": ("SpectrumSDXL", "comfyui-spectrum-sdxl", "https://github.com/ruwwww/comfyui-spectrum-sdxl"),
    "general": ("Spectrum", "ComfyUI-Spectrum", "https://github.com/judian17/ComfyUI-Spectrum"),
}


def provider_family(model):
    core = model.get_model_object("diffusion_model")
    names = {cls.__name__ for cls in type(core).__mro__}
    names.update(cls.__name__ for cls in type(model.model).__mro__)
    if "MOSSImage" in names:
        return "moss"
    if "MiniMaxH3Model" in names or "MiniMaxH3" in names:
        return "minimax"
    if names.intersection({"SDXL", "SDXLRefiner", "Anima"}):
        return "sdxl"
    return "general"


def _literal(prompt, value, visited=None):
    if not isinstance(value, list):
        return value
    visited = set() if visited is None else visited
    if len(value) != 2 or value[1] != 0 or str(value[0]) in visited:
        return None
    node_id = str(value[0])
    visited.add(node_id)
    source = prompt.get(node_id, {})
    if source.get("class_type") not in {"PrimitiveInt", "PrimitiveFloat", "PrimitiveNode"}:
        return None
    return _literal(prompt, source.get("inputs", {}).get("value"), visited)


def sampling_steps(prompt, loader_id):
    """Find one unambiguous downstream sampler/scheduler step count."""
    if not isinstance(prompt, dict) or loader_id is None:
        return None
    downstream, pending = set(), [str(loader_id)]
    while pending:
        current = pending.pop()
        if current in downstream:
            continue
        downstream.add(current)
        for node_id, node in prompt.items():
            if any(isinstance(v, list) and len(v) == 2 and str(v[0]) == current
                   for v in node.get("inputs", {}).values()):
                pending.append(str(node_id))
    counts = set()
    for node_id in downstream:
        node = prompt.get(node_id, {})
        inputs = node.get("inputs", {})
        if "steps" in inputs:
            value = _literal(prompt, inputs["steps"])
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                return None
            if node.get("class_type") == "KSamplerAdvanced":
                start = _literal(prompt, inputs.get("start_at_step", 0))
                end = _literal(prompt, inputs.get("end_at_step", value))
                if not isinstance(start, int) or not isinstance(end, int):
                    return None
                value = max(0, min(value, end) - start)
            counts.add(value)
        # Custom samplers receive their step count through a SIGMAS chain.
        if "sigmas" in inputs:
            ancestors, sources = set(), [inputs["sigmas"]]
            while sources:
                link = sources.pop()
                if not isinstance(link, list) or len(link) != 2 or str(link[0]) in ancestors:
                    continue
                ancestor_id = str(link[0]); ancestors.add(ancestor_id)
                parent = prompt.get(ancestor_id, {}).get("inputs", {})
                if "steps" in parent:
                    value = _literal(prompt, parent["steps"])
                    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                        return None
                    counts.add(value)
                sources.extend(v for key, v in parent.items() if key in {"sigmas", "steps"})
    return next(iter(counts)) if len(counts) == 1 else None


def _defaults(node_class):
    values = {}
    schema = node_class.INPUT_TYPES()
    for group in ("required", "optional"):
        for name, spec in schema.get(group, {}).items():
            if name == "model":
                continue
            options = spec[1] if len(spec) > 1 and isinstance(spec[1], dict) else {}
            if "default" in options:
                values[name] = options["default"]
            elif isinstance(spec[0], list) and spec[0]:
                values[name] = spec[0][0]
            elif group == "required":
                raise RuntimeError(f"Spectrum adapter input {name} has no default; update the integration or adapter.")
    return values


def _call(node_class, model, values):
    result = getattr(node_class(), node_class.FUNCTION)(model=model, **values)
    if isinstance(result, dict):
        result = result.get("result")
    elif hasattr(result, "result"):
        result = result.result
    if not isinstance(result, (tuple, list)) or len(result) != 1 or result[0] is None:
        raise RuntimeError("The Spectrum adapter did not return a native MODEL.")
    return result[0]


def _sdxl_cleanup(model):
    """Release the adapter's raw-output history between sampler calls."""
    import inspect
    from comfy.patcher_extension import WrappersMP
    function = model.model_options.get("model_function_wrapper")
    if not inspect.isfunction(function):
        return
    state = inspect.getclosurevars(function).nonlocals.get("state")
    if not isinstance(state, dict) or "forecasters" not in state:
        return
    def cleanup(executor, *args, **kwargs):
        state["forecasters"] = None
        state["last_t"] = -1
        try:
            return executor(*args, **kwargs)
        finally:
            state["forecasters"] = None
            state["last_t"] = -1
    model.add_wrapper_with_key(WrappersMP.OUTER_SAMPLE, "ray_spectrum_sdxl_cleanup", cleanup)


def _general_patch(node_class, model, values):
    """Turn upstream's direct Z-Image/Ernie edits into native object patches."""
    core = model.get_model_object("diffusion_model")
    zimage = all(hasattr(core, key) for key in ("noise_refiner", "cap_embedder", "layers"))
    ernie = not zimage and all(hasattr(core, key) for key in ("layers", "final_norm", "text_proj"))
    missing = object()
    names = ("_spectrum_original_layers", "_spectrum_original_patchify", "_spectrum_original_forward", "_spectrum_handle")
    saved = {name: core.__dict__.get(name, missing) for name in names}
    if (zimage or ernie) and any(value is not missing for value in saved.values()):
        raise RuntimeError("This model already has direct Spectrum patches. Use a clean loader branch with only one Spectrum integration.")
    layers = list(core.layers) if zimage else []
    methods = {name: (core.__dict__.get(name, missing), getattr(core, name))
               for name in (("patchify_and_embed",) if zimage else ("forward",) if ernie else ())}
    patched_methods = {}
    try:
        patched = _call(node_class, model.clone(), values)
        if zimage:
            import torch
            class OriginalForward(torch.nn.Module):
                def __init__(self, function):
                    super().__init__()
                    self.function = function
                def forward(self, *args, **kwargs):
                    return self.function(*args, **kwargs)
            for index, layer in enumerate(core.layers):
                if layer is not layers[index]:
                    # Keep native parameter paths intact for weight loading and LoRA
                    # patches. Only the method changes; the upstream wrapper calls
                    # the saved original method without recursively re-entering it.
                    layer.original_layer = OriginalForward(layers[index].forward)
                    patched.add_object_patch(f"diffusion_model.layers.{index}.forward", layer.forward)
        for name, (_, original) in methods.items():
            current = getattr(core, name)
            if current != original:
                patched_methods[name] = current
                patched.add_object_patch(f"diffusion_model.{name}", current)
    finally:
        for index, layer in enumerate(layers):
            core.layers[index] = layer
        for name, (own_value, _) in methods.items():
            if own_value is missing:
                core.__dict__.pop(name, None)
            else:
                setattr(core, name, own_value)
        for name, value in saved.items():
            if value is missing:
                core.__dict__.pop(name, None)
            else:
                setattr(core, name, value)
    state = patched.model_options.get("transformer_options", {}).get("spectrum")
    model_type = getattr(state, "model_type", "unsupported")
    if model_type == "unsupported":
        return model, "unsupported"
    import comfy.patcher_extension as extension

    def cleanup(executor, *args, **kwargs):
        try:
            return executor(*args, **kwargs)
        finally:
            if ernie:
                function = patched_methods.get("forward")
                handle = getattr(function, "_handle", None)
                if handle is not None:
                    handle.remove()
                    delattr(function, "_handle")
                    if getattr(core, "_spectrum_handle", None) is handle:
                        delattr(core, "_spectrum_handle")
            state.stop()

    patched.add_wrapper_with_key(extension.WrappersMP.OUTER_SAMPLE, "ray_spectrum_cleanup", cleanup)
    return patched, model_type


def apply_spectrum(model, prompt=None, loader_id=None, registry=None):
    if registry is None:
        import nodes
        registry = nodes.NODE_CLASS_MAPPINGS
    family = provider_family(model)
    node_id, pack, url = PROVIDERS[family]
    provider = registry.get(node_id)
    if provider is None:
        raise RuntimeError(f"Spectrum needs {pack} for this model. Install {url}, restart ComfyUI, or turn Spectrum off in Loader options.")
    values = _defaults(provider)
    if family == "sdxl":
        steps = sampling_steps(prompt, loader_id)
        if steps is None or not 10 <= steps <= 500:
            message = "Spectrum skipped: SDXL/Anima needs one detectable downstream step count between 10 and 500. Native sampling kept."
            LOG.warning(message)
            return model, {"state": "skipped", "message": message, "provider": node_id}
        values.update(steps=steps, stop_caching_step=max(1, steps - 3))
    if family == "general":
        patched, architecture = _general_patch(provider, model, values)
        if architecture == "unsupported":
            message = f"Spectrum skipped: {type(model.get_model_object('diffusion_model')).__name__} is unsupported by the installed adapter. Native sampling kept."
            LOG.warning(message)
            return model, {"state": "skipped", "message": message, "provider": node_id}
    else:
        patched = _call(provider, model.clone(), values)
        if family == "sdxl":
            _sdxl_cleanup(patched)
        architecture = {"moss": "MOSS-Image Adaptive", "minimax": "MiniMax H3", "sdxl": "SDXL / Anima"}[family]
    message = f"Spectrum attached: {architecture}"
    LOG.info(message)
    return patched, {"state": "attached", "message": message, "provider": node_id}
