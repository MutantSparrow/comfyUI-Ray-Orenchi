"""Optional real Qwen checkpoint and vision integration; never downloads weights."""
import os
from pathlib import Path
from unittest.mock import patch

import pytest
import torch

import ray_fast_vlm as fast

pytestmark = pytest.mark.skipif(not os.environ.get("RAY_QWEN_CHECKPOINT"), reason="set RAY_QWEN_CHECKPOINT to an existing local full Qwen3-VL checkpoint")


@pytest.fixture(scope="module")
def checkpoint_clip():
    import comfy.sd
    import comfyui_version
    checkpoint = Path(os.environ["RAY_QWEN_CHECKPOINT"])
    assert checkpoint.is_absolute() and checkpoint.is_file(), "Use an existing absolute local checkpoint path"
    assert comfyui_version.__version__.startswith("0.42."), "Validate new private APIs before enabling their fast path"
    clip = comfy.sd.load_clip(ckpt_paths=[str(checkpoint)], clip_type=comfy.sd.CLIPType.QWEN_IMAGE)
    _, _, transformer = fast.qwen_model(clip)
    assert isinstance(transformer, fast.Qwen3VL)
    assert clip.patcher.load_device.type == "cuda"
    return clip, transformer


def image():
    pixels = torch.ones((1, 128, 192, 3))
    pixels[:, 24:100, 30:100] = torch.tensor([1., 0., 0.])
    pixels[:, 40:100, 120:170] = torch.tensor([0., 0., 1.])
    return pixels


def infer(clip, **kwargs):
    return fast.RayFastQwen3VL().infer(clip, "Describe the colors and shapes in the image.",
                                     image=image(), max_tokens=kwargs.pop("max_tokens", 64),
                                     repeat_guard=False, **kwargs)[0]


def test_real_native_fast_repeat_and_native_restore(checkpoint_clip):
    clip, transformer = checkpoint_clip
    native = infer(clip, mode="native")
    assert native.strip()
    with patch.object(fast, "_generate_tokens", wraps=fast._generate_tokens) as accelerated:
        first = infer(clip, mode="fast")
        second = infer(clip, mode="fast")
        assert accelerated.call_count == 2
    assert first.strip() and first == second
    # Fast/native attention kernels may round differently. Native restoration
    # must still reproduce its own baseline exactly on the same machine.
    assert infer(clip, mode="native") == native


def test_real_long_generation_interruption_recovery_and_fallback(checkpoint_clip):
    clip, transformer = checkpoint_clip
    assert infer(clip, mode="fast", max_tokens=512).strip()
    original = transformer.sample_token
    count = 0
    def interrupt(*args, **kwargs):
        nonlocal count
        count += 1
        token = original(*args, **kwargs)
        if count == 4:
            fast.mm.interrupt_current_processing(True)
        return token
    try:
        with patch.object(transformer, "sample_token", interrupt):
            with pytest.raises(fast.mm.InterruptProcessingException):
                infer(clip, mode="fast", max_tokens=512)
    finally:
        fast.mm.interrupt_current_processing(False)
    assert count == 4
    assert infer(clip, mode="fast", max_tokens=32).strip()
    with patch.object(fast, "fast_compatibility", side_effect=fast.FastUnavailable("test unsupported contract")):
        assert infer(clip, mode="fast", max_tokens=32).strip()
