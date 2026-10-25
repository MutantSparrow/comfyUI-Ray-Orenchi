# Node screenshots are required

## Repository identity

Use the repository's configured maintainer identity for commit authors and
committers. Name branches and commits after the actual change. Do not add tool,
vendor, or generated-work attribution to branches, commit messages, co-author
trailers, collaborators, documentation, or other project content. Preserve this
rule in every future change.
Never name the coding service, its vendor, or its chat product anywhere in the
project, including functional provider labels and historical metadata.

## Screenshot maintenance

Every registered node must have a current image at `screenshots/<class_id>.png`,
embedded in its section of `NODES.md`.

**Any change to a node requires recapturing its screenshot in the same change.**
This includes backend behavior, defaults, inputs, outputs, title, controls, styling,
layout, and node-specific browser code. When shared code changes, recapture all
affected nodes. Capture newly created nodes with their actual defaults in ComfyUI
Nodes 2.0, unconnected and unexecuted, with the complete title and all default
input/output ports visible. Keep consistent padding and inspect the images.

Use `scripts/capture_node_screenshots.cjs` against an isolated ComfyUI instance;
see `developer/NODE_SCREENSHOTS.md`. Commit the PNGs, capture manifest, and documentation
together. Do not edit source fingerprints to bypass recapturing. If a change has
no visible effect, a fresh capture may have identical PNG bytes; the manifest must
still record the new capture and current sources.

Run `python scripts/check_node_screenshots.py` before finishing. The source check
covers local Python imports, node frontend modules, shared frontend imports, and
registration names; use judgment for changes outside that dependency inventory.

## Node design

Before changing a node or shared component, read and follow [UI.md](UI.md),
including its shared controls, lifecycle contracts, reference inventory and
completion checklist.

Settings/configuration actions use the single shared `settings` cog button
(30 × 30 CSS pixels) in the shared node header at the top right. Content edits
use the pencil beside their content. Follow the context-placement table in
`UI.md`; do not define node-local cog SVGs, styling, or button behavior.

Prefer placing suitable widgets alongside native output ports to save vertical
space, as in Folders, using shared layout support. Reserve clear space for port
labels, sockets, and link hit targets; fall back to stacked rows when narrow.
The settings cog stays top right of the widget content lane, clear of outputs.

Use the pack's category and title format: category emoji, Ray's group, then the
node name. Keep stable registered class IDs. Group related controls into named
sections using the shared magenta, uppercase `.rp-title` style. Separate visible
sections with the shared thin horizontal rule; hide empty sections and their
separators together. Apply the same treatment to custom panels. Preserve compact
analog modes and native input/output ports.

Use the shared Ray panel path controls and icon helpers for browsing and navigation.
Keep the established file/folder SVGs, compact button dimensions and spacing.
Use the file dialog for sources and Save As for explicit output files; preserve
cancellation and linked-input behavior. Keep output filters aligned with the
node's current mode.

## Documentation audience

README and node documentation are for end users. Describe features, controls,
usage and limitations. Keep development requests, discussions, maintenance rules
and contributor instructions in this file or dedicated developer documentation.
Keep design rationale, icon dimensions and placement standards, shared-component
instructions, and audit results in `UI.md` or `developer/`, never in the README.
