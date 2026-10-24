# Model-list execution and memory

`RayQueuedModelLoader` keeps its registered ID, native fields, and single MODEL
port. `OUTPUT_IS_LIST = (True,)` exposes a native execution list. The browser
does not fan out queue submissions. Direct API execution uses the same backend.
ComfyUI maps downstream nodes over the list and broadcasts singleton inputs;
its normal list pairing rules apply when other inputs are lists too.

The loader validates all model paths before loading any weights and keeps native
precision/quantization selection. Each returned patcher receives a stateless
`OUTER_SAMPLE` wrapper before optional Spectrum adapters are applied. The wrapper
uses `executor.class_obj.model_patcher`, so downstream LoRA clones are cleaned
up as well. In `finally`, native `unload_model_and_clones(..., all_devices=True)`
unloads only the sampled model family. It does not flush unrelated CLIP/VAE or
other cached models. Native wrapper ordering lets adapter cleanup finish before
weight offloading. SDXL Spectrum raw-output history is also cleared between
sampler calls, including interruption.

On DynamicVRAM, native model detachment releases GPU allocations and RAM pin/
weight buffers while preserving disk-backed model handles for subsequent use.
Legacy patchers offload weights to CPU; the execution cache can retain those CPU
weights. Do not promise a system-RAM bound independent of list length in legacy
mode. Samplers that bypass native wrappers retain their own lifecycle contract.

Validation covers native executor list mapping, unchanged singleton settings,
later-file cache invalidation, validation before allocation, clone inheritance,
and cleanup on success/failure/interruption. Browser integration checks one API
submission, three ordered model results, direct preview lists, explicit Rebatch
Images output, save/reload, Spectrum on/off, and both canvas renderers. Targeted
GPU checks should verify that loaded weight bytes return to zero after each
model, DynamicVRAM RAM buffer bytes return to zero, and an unrelated resident
model stays loaded. Use small native file-backed fixtures for these checks.
