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

Set `RAY_BROWSER_CHANNEL=msedge` or `chrome` to use an installed Chromium browser
for the Playwright suite and the live node-interface checks. Otherwise the
Playwright suite uses its bundled Chromium.

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

## Registry publishing

The **Publish to Comfy Registry** workflow runs after **Tests** passes on a push to
`main`. It checks out that exact tested commit and publishes its `pyproject.toml`
version if the Registry has not received it yet. Bump the version and push to
`main` to release an update. Existing versions are skipped; older versions are
rejected. Workflow node IDs remain unchanged.

The publishing credential is the encrypted repository Actions secret
`REGISTRY_ACCESS_TOKEN`, belonging to publisher `ray`. Never put the token in
`pyproject.toml`, workflow source, shell commands or committed files. The pinned
Comfy CLI reads it through the release runner's environment, with telemetry disabled.
Only the publishing step receives the Registry secret; CI and pull requests do not.

You can also run **Publish to Comfy Registry** manually from GitHub Actions on
`main`. Manual runs still require a successful Tests run for the exact selected
commit. A failed, pending or unrelated CI result blocks publication.

## Live node interfaces and screenshots

Use a Node.js environment with Playwright and a ComfyUI Python environment for
the checks below. Browser checks use an isolated ComfyUI instance serving the
current checkout; do not clear a user's working graph or change renderer
settings in their main session.

## Shared icons and actions

```shell
node tests/test_browse.cjs
node tests/test_save_name.cjs
node tests/shared_actions_browser.cjs http://127.0.0.1:8194
```

The shared-action browser check covers component geometry, accessible
interaction, disabled states, event isolation, header ordering, conditional
sections, and cleanup. Review the migrated settings and list-add actions in
both Nodes 2.0 and the legacy renderer, including saved-workflow reloads and
native ports. Keep valid content-editing actions beside their content.

## Node screenshots

Follow [the capture workflow](developer/NODE_SCREENSHOTS.md). A change to shared
frontend modules requires recapturing every affected node, including those
whose appearance remains the same.

```shell
node scripts/capture_node_screenshots.cjs --url http://127.0.0.1:8194
python scripts/check_node_screenshots.py
git diff --check
```

Use `--python /path/to/python` when needed. The capture command also supports
`--browser-channel msedge` or `--browser-channel chrome` for an installed
Chromium browser. Inspect the resulting PNGs; source freshness alone cannot
prove that controls are usable or correctly placed.

For `tests/shared_actions_browser.cjs`, the optional `RAY_BROWSER_CHANNEL`
environment variable selects an installed browser such as `msedge` or `chrome`.

## Node contract and documentation

```shell
python scripts/update_node_reference.py --url http://127.0.0.1:8194 --check
node tests/node_contract_browser.cjs http://127.0.0.1:8194
node tests/output_lane_browser.cjs http://127.0.0.1:8194
python -m pytest tests/test_meta_inspect.py tests/test_model_tools.py
```

The contract browser check instantiates every registered node in both renderers.
It verifies input/output help, custom-panel tooltip binding, magenta section
headings and dividers, shared settings placement, popup controls, keyboard
isolation, Apply/Cancel behavior, and mode-dependent image/PNG dialogs. Set
`RAY_BROWSER_CHANNEL` when selecting an installed browser. It never runs models
or opens a real native file dialog.

The output-lane check exercises measured legacy row sharing, native socket hit
targets, unchanged port coordinates, settings containment, narrow/long-label
and native-input fallbacks, teardown, and the supported Nodes 2.0 stacked layout.

After a schema change, update `NODE_REFERENCE.md` by running the reference
command without `--check` against the isolated instance with empty model folders.
The metadata tests cover PNG round trips, duplicate/invalid JSON, no-clobber
saving, explicit overwrite, suffix validation, and temporary-file cleanup.

## Loader dropdowns

```shell
node tests/loader_model_picker_browser.cjs http://127.0.0.1:8191
```

This uses fixture model lists without loading weights. It checks the native
folder menus, recursive path search, keyboard navigation, LoRA strengths,
saved workflows, connected inputs and teardown in both renderers.

## Save Image result restoration

```shell
node tests/save_image_restore_browser.cjs http://127.0.0.1:8197
node tests/save_image_cycle_browser.cjs http://127.0.0.1:8197
```

Use an isolated instance and set `RAY_BROWSER_CHANNEL` if selecting an installed
browser. This test saves small generated images in the instance's output folder,
delivers completion while another workflow is active, and returns to the first
tab. It also loads the completed run's graph and output snapshot from history.
It checks decoded previews, comparison, batch navigation, save status,
destination, and native values in both renderer modes. It requires no models.

The cycling check uses real mouse clicks to verify batch advancement,
wraparound, comparison dragging, arrow controls, and canvas navigation in both
renderers. It also covers a second-input-only batch, singleton pairing, and
single-image and empty previews.

## Backend changes

For model-processing controls, use the isolated checks below:

```shell
node tests/model_workflow_browser.cjs http://127.0.0.1:8191
node tests/save_model_browser.cjs http://127.0.0.1:8191
node tests/test_model_workflow_names.cjs
python -m pytest tests/test_model_workflow.py tests/test_model_tools.py
```

The browser check covers both renderers, live source/configuration names, STRING
block weights, output slot stability and migration of earlier saved widgets.
The shared name cases compare browser previews with Python execution strings.
The Save Model check covers the folder dialog, cancellation, connected inputs,
hidden legacy controls and migration of saved destinations in both renderers.
`tests/model_workflow_api.cjs` additionally runs two tiny Alpha/Beta safetensors
fixtures through loading, Fast merge and Save Model, including the name link.
Keep those fixtures in the isolated instance; use empty model folders for default
documentation captures.

Run the relevant existing Python tests with `python -m pytest` in an environment
that can import ComfyUI and the feature's dependencies. Test source resolution,
parsing, saving, collision behavior, and interruption handling according to the
changed behavior. UI-only changes must preserve registered schemas, values,
links, and defaults.

For native model-list execution and cleanup, run
`python -m pytest tests/test_queued_model_loader.py tests/test_queued_model_memory.py tests/test_queued_model_spectrum.py`.
See [model-list validation](developer/MODEL_LIST_LOADER.md) for the one-execution
browser and native GPU-memory contracts.
