# Fast Qwen3-VL Infer

Implemented on branch `FastVLM` in `G:\AI_APPS\_APPS\_MyApps\_ComfyUI_A1111_etc\comfyUI-Ray-Orenchi` and installed in the local ComfyUI copy of that pack. Existing uncommitted work was preserved. No core ComfyUI source, checkpoint, or dependency was changed.

## Use

Connect `CLIPLoader (type: qwen_image)` → **Ray's LLM: Fast Qwen3-VL Infer**, plus `IMAGE` and a plain prompt. Connect its `STRING` output to Preview as Text or another text consumer. Branch the **same CLIPLoader output** to conditioning nodes to reuse the same model.

The node takes max tokens, temperature, top-p, top-k, seed, and optional thinking. Temperature zero uses greedy decoding. `mode=native` provides an A/B baseline. `sync_interval=8` checks stopping every eight tokens; it returns only through the first stop token, but may compute up to seven discarded tokens. Set it to 1 for immediate stopping. Cancellation is checked at every step. An image batch is a single multi-image conversation, following the native tokenizer; it is not a batch of independent captions.

The separate development folder and ComfyUI's installed custom-node folder are ordinary directories, not a junction. Both received the new module and registration.

## Measured results

Local RTX 5090 (32 GB), Windows, PyTorch 2.12.1+cu130, ComfyUI v0.35.2 / commit `85eecc613aac153c2a3dfd6322434597c048ea05`, `qwen3vl_8b_fp8_scaled.safetensors`. Dynamic VRAM was enabled. One native model was loaded once and reused sequentially. Test image: 640×480 white background with red rectangle, blue circle, green triangle. Prompt requested shape/color/position descriptions. Every timed run generated 160 tokens; timing was capped, so the responses are not complete captions.

| Path | Whole request | Decode tokens/s | Time to first token |
|---|---:|---:|---:|
| Native, warmed | 10.252 s | 15.77 | 168 ms |
| Fast, first switch | 2.346 s | 94.05 | 653 ms |
| Fast, repeated | 1.868 s | 94.13 | 176 ms |
| Kitchen decode without graphs | 9.303 s | 17.47 | 202 ms |
| Fast, seeded sampling | 2.386 s | 89.13 | 599 ms |
| Kitchen without graphs, sampled | 9.121 s | 17.77 | 170 ms |
| Native after switching back | 10.020 s | 16.20 | 205 ms |

The repeated greedy request was **5.49× faster overall and 5.97× faster during decode** than the warmed native run. These are local measurements on this workload, not universal guarantees. CUDA events measured decode between the first and last sampled tokens; wall time includes vision/prefill, loading transitions, generation, and graph cleanup. Small diagnostic hooks were present in both paths. Cold checkpoint construction is excluded; the first native generation took 12.451 s including initial residency setup.

All 36 decoder blocks captured native managed graphs. Python-level Kitchen decode calls dropped to 72 per request (warmup/capture); the remaining invocations execute through graph replay. Native baseline made zero calls to this decode kernel. Ordinary torch peak-memory statistics do not account fully for Comfy's dynamic allocator, so no peak VRAM reduction is claimed.

## What was slow

`qwen3vl.py` wraps `Llama2_` and `BaseGenerate` in the normal CLIP stack. The tokenizer inserts image embeddings, native preprocessing resizes/normalizes images to [-1,1], and the vision model produces the main embedding plus DeepStack features. Image processing and vision encoding happen once per request. DeepStack features are injected only during prefill. They are not recomputed per generated token.

`BaseGenerate` already allocates the full KV capacity (`prompt length + max_length`) once per request. The ordinary attention path writes into this cache and slices it; it does not ordinarily concatenate/recreate the whole cache every token. Keeping KV across unrelated images would be incorrect without prefix identity and patch invalidation. This node keeps KV request-local.

The important missing optimizations were:

1. Qwen3-VL inherits `fixed_kv=False`. Therefore the existing `FixedKV` / `comfy_kitchen.flash_attention_decode` path was unused.
2. Qwen3-VL leaves native block graph support and dynamic block prefetch disabled. Sequential decode repeatedly dispatches all projections, normalization, rotary operations, MLP operations, cache writes, and attention through Python/PyTorch and weight management. Enabling graphs with valid stable inputs provides most of the measured gain.
3. The native loop calls `.item()` on the generated token every step, synchronizing the host with the GPU. It also creates a new position tensor from a Python scalar each decode step and updates progress every token. The new loop keeps position and output IDs on device, uses the existing sampler, and transfers IDs in bounded groups.

Specialized engines combine model-specific fused kernels, graph execution, memory layouts, KV management, and decode-oriented matrix operations. Their continuous batching also matters for serving throughput. ComfyUI's generic conditioning-oriented path does not automatically enable those optimizations for this model. No llama.cpp/vLLM engine benchmark was run, so this work does not claim parity with them.

## ComfyKitchen: the distinction that matters

Text attention in `llama.py` and vision attention in `qwen35.py` call `optimized_attention_for_device(..., small_input=True)`. In this install, that dispatch returns PyTorch attention (or basic attention), bypassing the global Kitchen INT8 attention selection. Merely enabling `--use-ck-attention` therefore does not enable Kitchen attention in those Qwen paths.

The separate `flash_attention_decode` kernel is already integrated into native `Attention.forward` for `FixedKV` and a one-token query. This node enables that route on supported CUDA devices. It does not force approximate INT8 attention for prefill or vision; both keep the native behavior. See the upstream [attention dispatcher](https://github.com/Comfy-Org/ComfyUI/blob/master/comfy/ldm/modules/attention.py), [native decoder](https://github.com/Comfy-Org/ComfyUI/blob/master/comfy/text_encoders/llama.py), and [Kitchen exports](https://github.com/Comfy-Org/comfy-kitchen/blob/main/comfy_kitchen/__init__.py). The findings above are from the installed commit, not an assumption that upstream will remain identical.

## Graph correctness and memory management

Simply setting the native graph flags produced corrupted output in both the original loop and the initial prototype. Inspection showed hidden-state and RoPE input addresses changing after capture while graph replay validated weight signatures only. This was reproduced with the native loop unchanged.

The final node uses small stable, request-local hidden-state/RoPE buffers for decode and calls the existing decoder layers through native `model_prefetch`. It preserves native cache prepare/advance operations, GQA layout, MRoPE continuation, quantized layers, and final normalization. There is no alternate model implementation or weight conversion.

`clip.clone()` clones the wrapper/patcher metadata only: `cond_stage_model`, tokenizer, and all weights remain the same objects. All behavior changes are registered through `ModelPatcher.add_object_patch`, including the native dynamic block registration. `CLIP.generate` still performs loading, CUDA context selection, and `use_quantized_matmul`; FP8-scaled weights retain the existing Comfy kernels and cast/offload handling. The node does not use `.cuda()` on the model, force full residency, or create a permanent dequantized copy.

Graphs, KV and activation buffers are discarded after each request, including exceptions. Native graph cleanup runs before local buffers expire. Normal Comfy patcher transitions restore behavior when the original CLIP is next used. Graph capture and eviction validation remain owned by Comfy's allocator. With dynamic VRAM/Comfy compiler disabled or the decode kernel unavailable, graph acceleration is skipped; the large speedup should not be expected in that configuration.

## Validation and limits

- Nine regression tests passed: chunked EOS trimming, immediate stopping, partial final chunks, one-token requests, MRoPE continuation, prefill-only DeepStack, cancellation, graph cleanup on success/error, graph-input lifetime through cleanup, and invalid input bounds (some cases share a test).
- Full 160-token greedy output matched the non-graph Kitchen reference exactly across repeated requests.
- Seeded sampling at temperature 0.7, top-k 40, top-p 0.9, seed 1234 matched the non-graph Kitchen reference exactly.
- Original native output was unchanged after switching back. Normal text conditioning returned finite tensors. Unload/reload followed by another VLM call succeeded.
- Object identity checks confirmed all compared wrappers shared the same model.
- The real ComfyUI API workflow completed through CLIPLoader, the new node, and Preview as Text. The server confirmed FP8 MixedPrecisionOps, Kitchen decode and graph eligibility, with zero native compiler graph breaks/rogues. The temporary test server was stopped afterward. Start ComfyUI normally to use the installed node.
- Kitchen and native PyTorch attention can produce different tokens from floating-point differences; exact token parity with the original PyTorch attention path is not promised.
- Tested with the 8B checkpoint above. The node permits the full native 4B model, but 4B was not benchmarked. It rejects truncated 32B conditioning models. GPU-pressure eviction under competing workloads and other hardware were not stress-tested.
- Full image preprocessing is intentionally preserved. Very high-resolution images can still dominate prefill; resize upstream if appropriate for your task.

Files added to the development pack: `ray_fast_vlm.py`, `tests/test_fast_vlm.py`, and `FAST_VLM.md`; the package initializer registers the node. No additional packages are required. Regression tests need the ComfyUI Python environment and ComfyUI on `PYTHONPATH`.
