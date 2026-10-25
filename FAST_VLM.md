# Fast Qwen3-VL Infer

Generate text with a native generative Qwen CLIP already loaded in ComfyUI.
Qwen3-VL accepts optional images and can use the fast decode path. Compatible
text-only Qwen models, including native Qwen3 and Qwen3.5 wrappers, use their
native generator and ignore the image input. The node keeps its existing name
and `RayFastQwen3VL` identifier for saved workflows.

## Connect and run

For image understanding, connect a full Qwen3-VL 4B or 8B checkpoint from
**CLIPLoader** with type `qwen_image` (or a compatible `krea2` loader), connect
**image**, and enter the instruction in **prompt**. Use the loader's default GPU
device. Connect **text** to Preview as Text or another text consumer. The same
CLIP can also feed conditioning nodes; the node reuses its weights.

For a text-only native Qwen model, connect its generative CLIP and a prompt.
An ordinary non-generative text-conditioning encoder is unsuitable. The
connected tokenizer supplies its own chat template and thinking behavior.

An image batch is one multi-image conversation. Use **Folder Captioner** when
you want independent captions for individual images. The decoded answer is
returned as one STRING; reaching **Max tokens** can truncate it.

## Controls

| Control | Behavior |
|---|---|
| **Max tokens** | Upper bound on generated tokens; default 256. |
| **Temperature** | 0 uses greedy decoding; positive values sample with the configured seed. |
| **Top P / Top K** | Native sampling filters. Top K 0 disables that filter; greedy decoding ignores both. |
| **Seed** | Reproducible sampling seed when temperature is positive. |
| **Generation preset** | `custom` uses the penalty controls, with neutral defaults. `anti_loop` explicitly uses repetition 1.0 and presence 1.5 and can change the answer. |
| **Repeat penalty / Presence penalty** | Penalize previously generated tokens. Neutral values are 1.0 and 0.0 respectively. |
| **Mode** | `fast` uses the optimized path on compatible Qwen3-VL models and otherwise falls back to native. `native` always uses the stock generator for comparison. |
| **Sync interval** | Fast Qwen3-VL stop-check interval, default 8. It may compute up to N-1 extra tokens, which are discarded after the first stop token. Set 1 for immediate stop checks. |
| **Thinking** | Requests the tokenizer/checkpoint's supported thinking mode; its effect depends on the model. |
| **Repeat guard** | Fast Qwen3-VL only: stops when the same 8-256-token phrase repeats three times. |

## Compatibility and resources

Fast initialization targets compatible full Qwen3-VL models and the native
ComfyUI 0.42.x interfaces. An incompatible model or API uses native generation.
Unknown minor versions and incompatible cache layouts fall back before decoding.
Errors after generation starts, out-of-memory failures and interruption propagate
without silently retrying the request.
Truncated conditioning-only models cannot act as full generative models.
Other Qwen families keep their native generator.

Graph acceleration depends on a supported CUDA device, native dynamic memory
management/compiler support and the decode kernel. If those capabilities are
unavailable, expect less acceleration or the native path. The node does not
convert checkpoint weights or keep a second full copy of them. Generation
buffers and graphs are released after each request, including failures.

Fast and native attention can produce different tokens because of floating-point
rounding. A fixed sampling seed does not guarantee identical text across different
attention backends or checkpoints. Full image preprocessing remains enabled;
very large images can dominate prompt processing time. Resize upstream when
appropriate for the task. Model weights and request buffers must fit available
resources.

A historical RTX 5090 test with an 8B FP8-scaled checkpoint measured a repeated
160-token greedy request at 1.868 seconds versus 10.252 seconds for the warmed
native path. This is one workload, not a general speed guarantee; 4B performance
was not benchmarked. Full measurements, environment, methodology and validation
limits are in [the benchmark notes](developer/FAST_VLM_BENCHMARKS.md).
