# Node screenshots

Each PNG shows one newly created node in **ComfyUI Nodes 2.0**, with its default
values, full title and default input/output ports. Nodes are unconnected and have
not run. The images use the dark canvas at 100% zoom, 2× pixel density, and 24 CSS
pixels of padding on every side. A node may be widened to reveal its full title
or port labels; its widget values and properties are unchanged. Empty previews,
folder browsers, and reports are intentionally in their initial state.

Images are named by stable registered class ID, for example `RayCRT.png`, and
embedded in [NODES.md](../NODES.md). Model Tools also appear in
[MODEL_TOOLS.md](../MODEL_TOOLS.md). `manifest.json` records the rendered ports,
default widget values, image dimensions, capture time, image hash, and source
fingerprint for each node.

## Updating images

**Any node change requires a fresh capture.** Recapture all nodes affected by
shared code, including behavior-only changes. An identical image is acceptable
when the appearance is unchanged, but its manifest must record the new capture.

1. Start a separate ComfyUI instance with the current checkout installed as
   `custom_nodes/comfyUI-Ray-Orenchi`. Use its own base/user directories and port
   (the capture command defaults to `8191`). Keep its model folders empty so
   machine-specific models and paths do not enter the default screenshots.
2. Install the repository's browser tools with `npm ci`, then
   `npx playwright install chromium`.
3. Capture all nodes, or the affected registered IDs:

   ```shell
   node scripts/capture_node_screenshots.cjs --url http://127.0.0.1:8191
   node scripts/capture_node_screenshots.cjs --url http://127.0.0.1:8191 --node RayCRT,RayOffsetPrint
   ```

   Use `--python /path/to/python` if Python is not on your PATH. The script enables
   Nodes 2.0 in that instance's settings and clears its test graph. It creates real
   nodes, waits for stable layout/fonts, checks title/port clipping, and captures
   the browser render directly. It never queues a workflow.
4. Inspect every updated image for complete controls and clean framing. Update
   the corresponding documentation if the node's interface changed.
5. Run `python scripts/check_node_screenshots.py`, then commit the images,
   manifest, and documentation together.

The check runs in CI and rejects missing, modified, undocumented, or stale
captures. Backend modules and local imports, matching frontend modules and their
local imports, and display names feed the source fingerprint. It is a freshness
guard; visual inspection is still required.
