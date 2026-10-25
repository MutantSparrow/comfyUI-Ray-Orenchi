# Frontend and screenshot checks

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
