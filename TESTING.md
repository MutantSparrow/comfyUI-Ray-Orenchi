# Testing and release checks

Use an existing ComfyUI Python environment. The pack never selects a Torch/CUDA
build; install those through ComfyUI. Install test tools with
`python -m pip install -r requirements-dev.txt`, then set `COMFYUI_ROOT` to the
ComfyUI checkout containing `comfy/` and `folder_paths.py`.

```shell
python scripts/smoke_import.py
python scripts/run_tests.py -q
npm ci
npx playwright install chromium
npm test
npm run test:browser
python -m build
```

Python tests run on CPU and do not start ComfyUI or download a model. The startup
test uses real ComfyUI imports, node schemas and route registration with a small
HTTP host fixture. Decoder integration uses actual Qwen3-VL/ComfyUI classes,
ModelPatcher, KV caches, MRoPE/DeepStack and tiny random local weights. It checks
normal/long generation, interruption recovery, cache isolation and native restoration.
This catches interface changes but does not evaluate the semantic quality of a VLM.

GitHub Actions runs Python 3.11, 3.12 and 3.13 against stable ComfyUI v0.42.4 and
Python 3.12 against current master on every push and PR. A separate Chromium job
runs the JS tests and browser regressions: legacy/Nodes 2.0 layouts, wheel capture,
100,000-file responsiveness, lazy thumbnails, local NSFW inference, prompt cards,
temporary asset deletion, connector alignment and comparison controls. Browser
fixtures bind only to loopback and recreate their own temporary files between tests.
No GPU or private checkpoint is needed for these required jobs. Configure branch
protection to require these checks when enforcing merge rules in GitHub.

## Optional CUDA and checkpoint integration

On a supported CUDA/Kitchen host with ComfyUI's native dynamic allocator:

```shell
# Set RAY_TEST_CUDA=1 in your shell before running:
python scripts/run_tests.py --device cuda -q tests/integration/test_comfy_qwen.py
```

This explicitly initializes the allocator in an isolated process and tests the
real prefetch/graph entry points and shared FixedKV counters. Tiny weights do not
exercise FP8 quantization, model offloading or actual dynamic VBAR block capture.
For those, set `RAY_QWEN_CHECKPOINT` to an **existing absolute local full Qwen3-VL
4B/8B checkpoint**, then run the whole `tests/integration` directory. The checkpoint
suite runs vision preprocessing, native/fast generation, repeated shared-model
requests, long output, cancellation/recovery and initialization fallback. Native
and fast attention kernels may differ numerically; each path must reproduce its
own greedy result on the same machine. No model is downloaded by either suite.

The manual **Optional Qwen CUDA integration** workflow targets only an explicitly
configured self-hosted runner labeled `ray-comfy-cuda`. Give it a ComfyUI Python
environment with the pack/test dependencies and repository variable `COMFYUI_ROOT`.
An optional workflow input supplies the local checkpoint path. GPU jobs never run
automatically for external pull requests.

## Pixel Art evaluation

See [the evaluation guide](benchmarks/pixel_art/README.md) for separate reconstruction
metrics, conversion structure diagnostics and blinded human pairwise comparisons.
Human rankings must be collected; the synthetic starter corpus is explicitly unranked.

## Packaging

`pyproject.toml` declares publisher `ray`, package `ray-orenchi`, Python 3.11–3.13
and ComfyUI 0.42.0+. Registry archives exclude development files through
`.comfyignore`; bundled JS/model assets and third-party notices remain included.
Builds also support a conventional `ray_orenchi` wheel for packaging validation.
ComfyUI loads Registry/cloned custom-node directories; installing a wheel alone is
not a replacement for that discovery mechanism. Stable workflow IDs remain fixed.

Publishing is a separate manual release step using Comfy CLI and the publisher's
Registry credentials; no workflow automatically publishes this package.
