"""Actual ComfyUI decoder/cache/patcher contracts, with tiny local random weights.

No checkpoints or tokenizer downloads. Run with scripts/run_tests.py. CUDA graph
coverage is opt-in: RAY_TEST_CUDA=1 and --device cuda on a supported GPU host.
"""
import os
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import torch
import comfy.model_management as mm
import comfy.memory_management
from comfy.model_patcher import ModelPatcher
from comfy import ops
from comfy.text_encoders.llama import Llama2_, Qwen3VL_4BConfig

import ray_fast_vlm as fast


@pytest.fixture
def clip():
    previous_threads = torch.get_num_threads()
    torch.set_num_threads(1)
    device = torch.device("cuda" if os.environ.get("RAY_TEST_CUDA") == "1" else "cpu")
    head_dim = 128 if device.type == "cuda" else 64
    config = Qwen3VL_4BConfig(vocab_size=128, hidden_size=head_dim * 2, intermediate_size=head_dim * 4,
                              num_hidden_layers=2, num_attention_heads=2, num_key_value_heads=1)
    config.head_dim = head_dim
    config.rope_dims = [24, 20, 20] if head_dim == 128 else [8, 12, 12]
    config.stop_tokens = []
    transformer = fast.Qwen3VL.__new__(fast.Qwen3VL)
    torch.nn.Module.__init__(transformer)
    # This fixture owns ordinary tiny weights, not a checkpoint/VBAR allocation.
    # Construct them eagerly; restore the real allocator for all generation calls.
    with patch.object(comfy.memory_management, "aimdo_enabled", False):
        transformer.model = Llama2_(config, device=device, dtype=torch.float32, ops=ops.manual_cast)
    # Dynamic-mode Embedding constructors intentionally reserve meta weights;
    # materialize the tiny synthetic fixture before filling it with random data.
    transformer.model.to_empty(device=device)
    transformer.model.fixed_kv = False
    transformer.model.graph_dynamic_vbar_blocks = False
    transformer.model.prefetch_dynamic_vbars = False
    generator = torch.Generator(device=device).manual_seed(12)
    for parameter in transformer.parameters():
        parameter.requires_grad_(False)
        parameter.normal_(std=.03, generator=generator)
        if parameter.ndim == 1:
            parameter.fill_(1)
    encoder = torch.nn.Module()
    encoder.transformer = transformer
    stage = torch.nn.Module()
    stage.clip = "qwen3vl_4b"
    stage.qwen3vl_4b = encoder
    patcher = ModelPatcher(stage, load_device=device, offload_device=torch.device("cpu"))

    class Clip:
        cond_stage_model = stage
        def __init__(self, patcher):
            self.patcher = patcher
        def clone(self):
            return Clip(self.patcher.clone())
        def is_dynamic(self):
            return False
    try:
        yield Clip(patcher), transformer, transformer.model.embed_tokens(torch.tensor([[1, 3, 5]], device=device))
    finally:
        mm.interrupt_current_processing(False)
        fast.prefetch.cleanup_prefetch_queues()
        torch.set_num_threads(previous_threads)


def accelerated(clip, transformer, embeds, **kwargs):
    patched = fast.prepare_qwen3vl_fast(clip, "qwen3vl_4b", transformer, repeat_guard=False)
    patched.patcher.patch_model(load_weights=False)
    try:
        return transformer.generate(embeds.clone(), do_sample=False, **kwargs)
    finally:
        patched.patcher.unpatch_model(unpatch_weights=False)


def test_normal_generation_and_model_reuse(clip):
    wrapper, transformer, embeds = clip
    expected = transformer.generate(embeds.clone(), do_sample=False, max_length=24)
    actual = accelerated(wrapper, transformer, embeds, max_length=24)
    assert len(actual) == len(expected) == 24
    if embeds.device.type == "cpu":
        assert actual == expected
    assert accelerated(wrapper, transformer, embeds, max_length=24) == actual
    assert transformer.generate(embeds.clone(), do_sample=False, max_length=24) == expected
    assert not transformer.model.graph_dynamic_vbar_blocks


def test_long_generation_and_fresh_cache_for_different_prompts(clip):
    wrapper, transformer, embeds = clip
    actual = accelerated(wrapper, transformer, embeds, max_length=320)
    assert len(actual) == 320 and all(0 <= token < 128 for token in actual)
    other = transformer.model.embed_tokens(torch.tensor([[4, 7]], device=embeds.device))
    first = accelerated(wrapper, transformer, other, max_length=32)
    accelerated(wrapper, transformer, embeds, max_length=16)
    assert accelerated(wrapper, transformer, other, max_length=32) == first


def test_real_interruption_and_recovery(clip):
    wrapper, transformer, embeds = clip
    original = transformer.sample_token
    calls = []
    def sample(*args, **kwargs):
        calls.append(True)
        mm.interrupt_current_processing(True)
        return original(*args, **kwargs)
    with patch.object(transformer, "sample_token", sample):
        with pytest.raises(mm.InterruptProcessingException):
            accelerated(wrapper, transformer, embeds, max_length=320)
    assert len(calls) == 1
    assert len(accelerated(wrapper, transformer, embeds, max_length=8)) == 8


def test_mrope_deepstack_prefill_matches_native(clip):
    wrapper, transformer, embeds = clip
    positions = torch.tensor([[0, 1, 2], [0, 1, 1], [0, 1, 2]], device=embeds.device)
    mask = torch.tensor([[False, True, False]], device=embeds.device)
    extra = dict(position_ids=positions, visual_pos_masks=mask,
                 deepstack_embeds=[torch.full((1, embeds.shape[-1]), .01, device=embeds.device)])
    expected = transformer.generate(embeds.clone(), do_sample=False, max_length=16, **extra)
    actual = accelerated(wrapper, transformer, embeds, max_length=16, **extra)
    assert len(actual) == 16
    if embeds.device.type == "cpu":
        assert actual == expected


def test_unknown_version_falls_back_before_patching(clip):
    import comfyui_version
    wrapper, transformer, _ = clip
    with patch.object(comfyui_version, "__version__", "0.999.0"):
        with pytest.raises(fast.FastUnavailable):
            fast.prepare_qwen3vl_fast(wrapper, "qwen3vl_4b", transformer)
    assert wrapper.patcher.object_patches == {}


@pytest.mark.skipif(os.environ.get("RAY_TEST_CUDA") != "1", reason="opt-in CUDA graph integration")
def test_cuda_prefetch_graph_and_shared_fixed_counters(clip):
    wrapper, transformer, embeds = clip
    if not fast.comfy_kitchen.flash_attention_decode_is_available(embeds.device):
        pytest.fail("CUDA integration requires Kitchen flash decode support")
    if not fast.prefetch.malloc_graph_enabled(embeds.device):
        pytest.fail("CUDA integration requires ComfyUI's native graph allocator")
    reference = accelerated(wrapper, transformer, embeds, max_length=96)
    # Exercise the real queue/allocator entry points with stable request buffers.
    # Random tiny weights do not use dynamic VBARs, so graph capture eligibility
    # and actual block capture are covered separately by the checkpoint suite.
    transformer.model.fixed_kv = True
    transformer.model.graph_dynamic_vbar_blocks = True
    try:
        with patch.object(fast.prefetch, "malloc_graph_begin", wraps=fast.prefetch.malloc_graph_begin) as begin:
            actual = fast.fast_generate(transformer, embeds.clone(), do_sample=False, max_length=96, repeat_guard=False)
            assert begin.call_count == 95
        assert actual == reference
        assert fast.fast_generate(transformer, embeds.clone(), do_sample=False, max_length=96, repeat_guard=False) == actual
    finally:
        transformer.model.graph_dynamic_vbar_blocks = False
