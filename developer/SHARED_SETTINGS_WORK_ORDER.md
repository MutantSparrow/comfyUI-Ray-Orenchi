# Work order: shared settings actions

## Objective and ownership

Implement the icon and context-placement contract in [UI.md](../UI.md), section
5. All runtime work targets the current 29-node checkout on branch
`feature/shared-settings-actions`. The contract reviewer owns `UI.md`, agent
instructions, this work order, screenshot recaptures, and final acceptance.
The implementation agent owns frontend components, node migrations, and focused
tests. Do not change model behavior, registered IDs, or native schemas.

## Required work

1. Extend the existing shared `ICONS` / `iconButton()` API in
   `web/ray_panel.js`. Create exactly one `settings` SVG and one shared 30 × 30
   CSS-pixel button variant, with a centered 16 × 16 glyph. Preserve other
   icon-button sizes. Use the same handler, accessibility, focus, hover, and
   disabled behavior in ordinary panels and custom wrappers.
2. Implement a reusable header/action helper and a declarative `installPanel`
   header-action option. Align the first section title left, actions right,
   settings rightmost. The header sits above source fields and below native
   title/ports. No node-specific absolute positioning or inline margin hacks.
3. Migrate every existing cog to the shared implementation. Remove the local
   `COG` constant and bespoke settings-button construction from Folders. Move
   its cog from the filter row to its first section's top-right header.
4. Replace Queued Model Loader's Loader options pencil with the shared cog and
   move it from below the model list to the top-right header. Keep Add model
   in that header before settings, and preserve all Spectrum option behavior.
5. Replace Model Card's body Settings text button with the same top-right cog.
   Preserve its shared settings dialog and Copy Config content action.
6. Normalize primary-list Add actions through the shared header contract,
   including the LoRA QKV loader. Preserve item-level browse, strength, remove,
   edit-content, and name-builder actions in their relevant contexts.
7. Audit all remaining nodes for cog copies, pencils opening node options, and
   misplaced settings actions. Migrate applicable instances. Keep valid
   content-editing pencils and do not invent secondary settings for nodes that
   have none. Any introduced icon, including a reused removal icon, must use
   the shared library rather than an `innerHTML` replacement per node.
   The metadata editor's Add field belongs in its Metadata section header as a
   shared plus; its per-row removal uses the shared remove button. Preserve
   Load / Edit and Table / JSON as labeled content actions.
8. Cover the shared component and migrated callers with meaningful focused
   checks. Report exact tests and results, modified files, and limitations.
   Leave runtime changes reviewable; do not commit or deploy them.

## Acceptance criteria

- One settings glyph source and one shared component/style path; no local cog
  constant, inline replacement, or settings-specific sizing in node modules.
- All existing settings entry points have a 30 × 30px computed button box and
  a useful tooltip and accessible name; keyboard activation opens the original
  dialog. Their hover/focus/disabled states work outside `.rp` too.
- Queued Model Loader, Folders, and Model Card put settings at the top right of
  the first content header, never in a list footer/filter row/body section.
  Primary-list Add controls align before the settings cog where applicable.
- Narrow nodes, saved workflows, repeated configuration, duplicate nodes,
  both renderer paths, cleanup, and native ports remain correct. No duplicate
  header/action is created after reload or reconfiguration.
- No unrelated popup redesign or backend change is included. The earlier
  path-picker race is outside this work order.
- Reviewer recaptures all nodes affected by shared frontend changes using
  `developer/NODE_SCREENSHOTS.md`, inspects the renders, and runs
  `scripts/check_node_screenshots.py` successfully before acceptance.

## Review record

Accepted after independent contract review.

- One shared settings SVG and 30 × 30px component, including outside-panel
  states; no node-local cog implementation remains.
- Queued Model Loader, Folders, and Model Card settings use the first content
  header. Model/LoRA Add and metadata Add/remove follow their context rules.
- Real Nodes 2.0 and legacy checks passed for the four migrated node layouts:
  placement, dimensions, keyboard dialogs, disabled handling, narrow sizing,
  Add/remove, workflow reload, no duplicate actions, and node-removal cleanup.
- `tests/shared_actions_browser.cjs` passed component-state, first-visible-header
  relocation, focus preservation, teardown, and metadata table/JSON/reload
  checks. Browse, queued-planner, filename, migration, and filter regressions
  passed. End-user help explains the new cog placement.
- Captured and visually inspected all 29 default Nodes 2.0 images. Every
  default-widget map and visible native input/output list matches the baseline.
  `scripts/check_node_screenshots.py` and `git diff --check` passed.
- The capture validator now checks shared-header headings and the cog's
  size, accessible label, first-header placement, and rightmost alignment.
