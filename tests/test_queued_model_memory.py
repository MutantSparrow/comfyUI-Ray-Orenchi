"""Sampling cleanup uses the actual downstream clone and preserves exceptions."""
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import torch
from comfy.patcher_extension import WrappersMP
from queued_model_memory import install_model_offload, offload_after_sample


@pytest.mark.parametrize("error", [None, RuntimeError("failed"), KeyboardInterrupt("cancelled")])
def test_native_targeted_offload_runs_on_success_error_and_cancel(error):
    clone = object()
    class Executor:
        class_obj = SimpleNamespace(model_patcher=clone)
        def __call__(self, value):
            if error is not None:
                raise error
            return value
    with patch("comfy.model_management.unload_model_and_clones") as unload:
        if error is None:
            assert offload_after_sample(Executor(), 42) == 42
        else:
            with pytest.raises(type(error)):
                offload_after_sample(Executor(), 42)
        unload.assert_called_once_with(clone, all_devices=True)


def test_stateless_wrapper_survives_native_lora_cloning():
    from comfy.model_patcher import ModelPatcher
    base = torch.nn.Linear(2, 2)
    model = ModelPatcher(base, torch.device("cpu"), torch.device("cpu"))
    assert install_model_offload(model) is model
    clone = model.clone()
    assert clone.offload_device == torch.device("cpu")
    assert clone.get_all_wrappers(WrappersMP.OUTER_SAMPLE) == [offload_after_sample]
    assert offload_after_sample.__closure__ is None
