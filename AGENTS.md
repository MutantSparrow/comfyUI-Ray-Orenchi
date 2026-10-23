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
see `screenshots/README.md`. Commit the PNGs, capture manifest, and documentation
together. Do not edit source fingerprints to bypass recapturing. If a change has
no visible effect, a fresh capture may have identical PNG bytes; the manifest must
still record the new capture and current sources.

Run `python scripts/check_node_screenshots.py` before finishing. The source check
covers local Python imports, node frontend modules, shared frontend imports, and
registration names; use judgment for changes outside that dependency inventory.
