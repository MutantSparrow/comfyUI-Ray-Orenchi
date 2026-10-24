"""Adapter selection and sampling contracts without model weights."""
import copy
from types import SimpleNamespace

import pytest

from queued_model_spectrum import apply_spectrum, provider_family, sampling_steps


class Patcher:
    def __init__(self, core_name="Flux", base_name="BaseModel"):
        self.model = type(base_name, (), {})()
        self.model.diffusion_model = type(core_name, (), {})()
        self.model_options = {}

    def get_model_object(self, name):
        return getattr(self.model, name)

    def clone(self):
        clone = copy.copy(self)
        clone.model_options = copy.deepcopy(self.model_options)
        return clone


@pytest.mark.parametrize("core,base,expected", [
    ("MOSSImage", "BaseModel", "moss"), ("MiniMaxH3Model", "BaseModel", "minimax"),
    ("UNetModel", "SDXL", "sdxl"), ("UNetModel", "SDXLRefiner", "sdxl"),
    ("Anima", "BaseModel", "sdxl"), ("Flux", "BaseModel", "general"),
])
def test_detect_loaded_architecture(core, base, expected):
    assert provider_family(Patcher(core, base)) == expected


def test_sampler_steps_follow_model_branch_and_primitive_links():
    prompt = {"1": {"inputs": {}}, "2": {"class_type": "KSampler", "inputs": {"model": ["1", 0], "steps": ["3", 0]}},
              "3": {"class_type": "PrimitiveInt", "inputs": {"value": 25}},
              "4": {"class_type": "KSampler", "inputs": {"model": ["different", 0], "steps": 90}}}
    assert sampling_steps(prompt, "1") == 25
    prompt["5"] = {"class_type": "KSampler", "inputs": {"model": ["1", 0], "steps": 40}}
    assert sampling_steps(prompt, "1") is None


def test_custom_sampler_sigma_schedule_and_advanced_range():
    prompt = {"1": {"inputs": {}}, "2": {"class_type": "SamplerCustom", "inputs": {"model": ["1", 0], "sigmas": ["3", 0]}},
              "3": {"class_type": "BasicScheduler", "inputs": {"model": ["1", 0], "steps": 30}}}
    assert sampling_steps(prompt, "1") == 30
    prompt = {"1": {"inputs": {}}, "2": {"class_type": "KSamplerAdvanced", "inputs": {"model": ["1", 0], "steps": 30, "start_at_step": 10, "end_at_step": 25}}}
    assert sampling_steps(prompt, "1") == 15


def test_missing_dependency_is_actionable():
    with pytest.raises(RuntimeError, match="ComfyUI-Spectrum-MOSS.*https://github.com"):
        apply_spectrum(Patcher("MOSSImage"), registry={})


def test_specialized_adapter_defaults_and_original_model_are_preserved():
    captured = {}
    class Provider:
        FUNCTION = "patch"
        @classmethod
        def INPUT_TYPES(cls):
            return {"required": {"model": ("MODEL",), "warmup": ("INT", {"default": 8})},
                    "optional": {"device": (["cpu", "vram"], {"default": "cpu"})}}
        def patch(self, model, **values):
            captured.update(values)
            model.model_options["test_patch"] = True
            return (model,)
    original = Patcher("MOSSImage")
    patched, report = apply_spectrum(original, registry={"SpectrumMOSSImageAdaptive": Provider})
    assert captured == {"warmup": 8, "device": "cpu"}
    assert original.model_options == {}
    assert patched is not original and patched.model_options["test_patch"]
    assert report["state"] == "attached"


def test_sdxl_uses_actual_steps_or_native_fallback():
    captured = {}
    class Provider:
        FUNCTION = "patch"
        @classmethod
        def INPUT_TYPES(cls):
            return {"required": {"model": ("MODEL",), "steps": ("INT", {"default": 30}),
                                 "stop_caching_step": ("INT", {"default": -1})}}
        def patch(self, model, **values):
            captured.update(values); return (model,)
    model = Patcher("UNetModel", "SDXL")
    registry = {"SpectrumSDXL": Provider}
    prompt = {"1": {"inputs": {}}, "2": {"class_type": "KSampler", "inputs": {"model": ["1", 0], "steps": 25}}}
    apply_spectrum(model, prompt, "1", registry)
    assert captured == {"steps": 25, "stop_caching_step": 22}
    patched, report = apply_spectrum(model, registry=registry)
    assert patched is model and report["state"] == "skipped"
