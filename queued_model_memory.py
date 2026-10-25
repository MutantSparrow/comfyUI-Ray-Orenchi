"""Release each sampled diffusion model through native memory management."""


def offload_after_sample(executor, *args, **kwargs):
    # Use the sampler's actual patcher, including downstream LoRA/patch clones.
    # Keeping this wrapper stateless avoids retaining the loader's base model.
    patcher = executor.class_obj.model_patcher
    try:
        return executor(*args, **kwargs)
    finally:
        import comfy.model_management as management
        management.unload_model_and_clones(patcher, all_devices=True)


def install_model_offload(model):
    import torch
    from comfy.patcher_extension import WrappersMP
    # An explicit CPU destination also releases weights in high-VRAM mode.
    # Precision/quantization still come from the native loader's defaults.
    model.offload_device = torch.device("cpu")
    model.add_wrapper_with_key(WrappersMP.OUTER_SAMPLE, "ray_model_list_offload", offload_after_sample)
    return model
