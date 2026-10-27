# Node creation rules

This is the implementation contract for creating and changing Ray's Orenchi
nodes. Read it before editing a node, a panel, or a shared helper. It covers the
29 registered nodes and their current default Nodes 2.0 screenshots. It applies
to frontend and backend work, including loaders, savers, and parsers.

**MUST** means required for new work. **SHOULD** means the default unless the
node's actual purpose requires a documented exception. Existing specialized
interfaces are references for their own family, not permission to invent a new
visual system. This guide does not claim every older implementation already
meets every recommendation.

## 1. Start from the existing implementation

1. Read [AGENTS.md](AGENTS.md), this guide, and the closest reference node below.
2. Inspect that node's image in [NODES.md](NODES.md) and its Python and frontend
   code. The screenshot establishes appearance; the shared code establishes
   behavior and exact dimensions.
3. Choose a standard panel or an established specialized interface. Reuse the
   component map in section 9 before writing a new control or parser.
4. Specify native inputs, defaults, outputs, section order, path semantics,
   empty/error states, and resource ownership before implementation.
5. Implement and verify the complete node, including help and screenshots.

If a reference differs from a rule here, follow the explicit rule for new work.
If a shared implementation cannot express it, extend the shared component and
verify all affected nodes. Do not silently fork its CSS or behavior in one node.

## 2. Identity, titles, and native ports

MUST keep existing registered class IDs stable. Register new classes in
`_NODE_MODULES` and `NODE_DISPLAY_NAME_MAPPINGS` in [__init__.py](__init__.py).
Python class IDs, input names, enum values, and output order are workflow API.
Changing a visible label does not justify changing those identifiers.

Use these exact category and display-title patterns:

| Family | Python `CATEGORY` | Display title |
| --- | --- | --- |
| VFX | `👑 Ray/✨ VFX` | `✨ Ray's VFX: <Node name>` |
| Analog | `👑 Ray/🎛️ Analog` | `🎛️ Ray's Analog: <Node name>` |
| LLM | `👑 Ray/💬 LLM` | `💬 Ray's LLM: <Node name>` |
| Tools | `👑 Ray/🔧 Tools` | `🔧 Ray's Tools: <Node name>` |
| Model Tools | `👑 Ray/🧰 Model Tools` | `🧰 Ray's Model Tools: <Node name>` |

- MUST use the family emoji, `Ray's <family>:`, and a concise task name. The
  crown belongs in the category path; do not add it to every node title.
- MUST preserve native typed input/output ports, their labels, and their normal
  connection behavior in both Nodes 2.0 and the legacy canvas. ComfyUI owns port
  colors and placement. Do not replace ports with decorative HTML dots.
- MUST declare `INPUT_TYPES`, `RETURN_TYPES`, `RETURN_NAMES` where needed,
  `FUNCTION`, `CATEGORY`, and a useful `DESCRIPTION`. Use `OUTPUT_NODE` for a
  terminal action when required by its execution semantics.
- MUST provide backend defaults and numeric limits; the frontend must agree.
  Tooltips explain units, special values, formats, and constraints.
- MUST document every required/optional input and every native output through
  schema tooltips, including optional and mode-dependent controls. Shared
  panels read the registered schema from `node.constructor.nodeData`; do not
  rely on ComfyUI copying tooltip text into the native widget object. Custom
  controls use the shared `inputTooltip()` helper where their meaning matches
  a native field, or `outputTooltip()` for a displayed output. Labels must
  receive pointer events so hovering them reaches their tooltip instead of
  the canvas; verify actual label hit testing in both renderers. Keep
  [NODE_REFERENCE.md](NODE_REFERENCE.md) synchronized with
  the registered schemas using `scripts/update_node_reference.py --check`.
- SHOULD keep connected data as typed sockets and editable settings as native
  widgets. Use `forceInput` when a value is intentionally connection-only.
- MUST preserve serialization and migration of existing workflows. A new UI may
  hide a compatibility field without removing its meaning or connected value.

## 3. Visual language and exact shared tokens

The default node body and title bar are black. Family membership is communicated
by title and category, not a different panel color. Use `applyBucketTint()` from
[web/_common.js](web/_common.js), or the existing family initialization. Model
Tools currently use its `Tools` bucket. Preserve intentional user colors when
migrating old saved workflows; [ray_bucket_tints.js](web/ray_bucket_tints.js)
recognizes only the former defaults.

Import the shared panel implementation rather than copying these values. The
table records its current contract; future intentional changes belong in the
shared implementation and this guide together.

| Element | Required shared treatment |
| --- | --- |
| Body/title/panel | `#000000`; `.rp` radius `8px` |
| Main text | `#eee`, `12px system-ui, sans-serif` |
| Field label | `#a3a3a3`, `11px`; ellipsis with a useful tooltip |
| Section heading | `.rp-title`: `#d43aa8`, `600 10px system-ui`, `.08em` tracking, uppercase |
| Section divider | `1px solid #2b2b2b`, `8px` top padding between visible sections |
| Panel spacing | `padding: 6px 6px 8px`; `6px` vertical gap |
| Ordinary row | Minimum height `28px`; label/control gap `8px` |
| Label/control columns | `minmax(64px,34%) minmax(0,1fr)` |
| Input/select/textarea | `#141414` background, `#eee` text, `1px #3a3a3a` border, `5px` radius |
| Single-line input | Height `28px`, padding `4px 9px` |
| Textarea | Minimum height `64px`, padding `6px 9px`, line height `1.4` |
| Placeholder | `#6f6f6f` |
| Button | `#171717` background, `1px #383838` border, `5px` radius |
| Button hover | `#454753` for enabled shared buttons |
| Icon button | `32 × 28px`, no padding, centered `16 × 16px` SVG |
| Settings cog button | `30 × 30px` hit target, centered `16 × 16px` SVG; shared settings variant |
| SVG stroke | `currentColor`, width `1.8`, round caps/joins, no fill |
| Control-to-icon gap | `6px` |
| Toggle | `34 × 18px`, `9px` radius, `12px` thumb |
| Segmented choice | Shared `26px` buttons inside a `1px` border; no gaps between choices |
| Numeric step buttons | `24px` wide inside the shared `28px` numeric control |
| Active segment / toggle | `#e2e2e2` with `#111` text / thumb |
| Keyboard focus | `2px solid #b9a4fa`, offset `1px` |
| Status | `.rp-status`: `11px`, `#9a9a9a`; hidden when empty |
| Disabled controls | Shared opacity: `.55` inputs, `.4` buttons |

Color has a limited meaning:

- **Magenta `#d43aa8`:** section hierarchy and Ray help identity. Do not use it
  as a generic fill for inputs, every action, or whole node title bars.
- **White/light gray:** readable values and active ordinary controls.
- **Muted gray:** labels, explanatory text, borders, and inactive controls.
- **Lavender `#b9a4fa`:** keyboard focus and gallery selection/loading accents.
- **Amber:** attention or link-drop feedback. The shared drop target uses
  `#6b5a2a` when available and `#e5b567` over the target; Model Tools warnings use
  `#edbc78`. Explain the condition in text.
- **Soft red:** actual errors or destructive actions, such as `.rmt-error`
  `#ff9292` and the gallery's `#ff9999`. Do not use error color for ordinary
  empty states.
- **Analog material colors:** belong inside the established hardware face and
  its selected style. Keep the surrounding node shell black.

MUST avoid decorative gradients, colored section cards, oversized action
buttons, new fonts, and one-off accent palettes in ordinary panels. Existing
analog materials and media content are purposeful exceptions.

## 4. Sections, controls, and layout

### Standard panel

MUST use `installPanel(node, spec)` from [web/ray_panel.js](web/ray_panel.js) for
ordinary settings. Plain node layouts belong in `PANEL_SPECS` in
[web/ray_panels.js](web/ray_panels.js). A node with dedicated frontend logic can
call `installPanel` itself; do not mount a second panel for the same controls.

- Group by the user's task: `Source` / `Images`, `Look` / `Processing`,
  `Sampling`, `Metadata`, `Output`, `Preview`. Include only relevant
  groups. Existing nodes may choose a different order for their primary task.
- MUST give every visible group an `.rp-title` heading and `.rp-section`
  container. Use short names; CSS handles uppercase. Do not use emojis,
  oversized headings, or additional brand labels inside every section.
- MUST separate successive visible sections with the shared thin rule. There
  is no leading rule above the first visible section. Hide an empty section,
  its heading, and its separator together. This also applies to custom panels.
- Use `when(node)` on fields or sections for mode-dependent settings. Use
  `setWidgetHidden()` for native-widget visibility logic; panel-managed widgets
  retain logical visibility through `rayLogicHidden`.
- MUST keep linked values visible as link chips when applicable. Do not hide a
  needed connection merely because its local editor is inactive.
- Paths and long text SHOULD use full-width rows with the label above. Ordinary
  scalar controls use the shared label/control columns.
- MUST explicitly place every intended control. `Additional settings` is the
  shared fallback that prevents accidental loss, not a planned section name.
  `skip` is for intentionally managed fields, not forgotten controls.
- Use `label` and `labels` to improve display text while keeping stored values.
  Prefer `Max tokens`, `Folder of images`, and `Output file` over raw API names.
- Keep related controls aligned. Use `min-width:0` in flex/grid children so
  paths and labels do not force overflow.

The shared renderer selects controls from the native widget:

| Value | Shared control |
| --- | --- |
| Boolean | Compact `.rp-toggle`, switch role and `aria-checked` |
| Two to four short enum choices, each at most nine characters | Segmented buttons with `aria-pressed` |
| Longer or larger enum | `.rp-select`; use `kind: "select"` when needed |
| Bounded fractional number with range at most ten | Slider plus numeric editor |
| Other number | Numeric editor with minus/plus and horizontal scrubbing |
| Seed with native `control_after_generate` | Numeric editor plus seed-mode icon |
| Multiline string | `.rp-textarea`; choose a suitable `rows` |
| Browsable path | Editable path plus the shared file/folder button |
| Color | Shared swatch plus text control via `kind: "color"` |

Use explicit `kind` only when that default is unsuitable. Preserve native
precision, range, step, seed-mode behavior, and special sentinel meanings. A
slider must not prevent typing an exact value.

### Specialized panels and sizing

- MUST reuse `ensurePanelStyles()`, `.rp-title`, shared spacing, and icon helpers
  in custom interfaces. A plain element outside `.rp` does not inherit all
  `.rp button` rules; use the established family wrapper or scoped matching
  rules. Do not assume adding a class alone supplies every ancestor selector.
- SHOULD compose custom editors through `field.custom(panel)` or mount a panel
  inside an existing face with `spec.mount`. Use `openPanelSettings()` for
  secondary settings rather than creating a second settings design.
- The standard panel minimum width is `340px`; Model Tools use `470px`. Choose
  the smallest justified family width that fits title, controls, and ports.
  Do not make every node a large dashboard.
- MUST measure inner content rather than the stretched DOM-widget host. Use
  the shared `schedule()` / `fit()` behavior. Avoid resize feedback loops,
  blank hidden-widget rows, clipping, and continually resetting user width.
- MUST preserve compact analog modes, their hardware faces, styles, Dymo
  labels, readouts, menus, and native ports. Extend `registerAnalog()` and the
  analog helpers rather than replacing them with an unrelated settings card.
- Keep gallery and inspection areas bounded. Do not add generic Report sections
  or empty report placeholders. Operation reports use their native outputs;
  Inspector and Compare keep their tools in Inspection and Comparison.

### Compact widget and output rows

Nodes SHOULD place suitable widgets alongside native output ports whenever
there is enough usable horizontal space. Reuse the vertical space occupied by
the output column instead of automatically starting every control below the
last output. The Folders layout is the reference for this space-saving
arrangement: its folder/filter controls can occupy the left side of the same
rows as the output labels and sockets on the right.

- This is a preference for compact layout, not a requirement to put every
  widget on one row. Several short control rows may share the height of an
  output column; long editors, galleries, and previews can continue below.
- MUST preserve native port positions, types, labels, link hit targets, and
  connection behavior. Reserve a separate output lane with enough space for
  its measured labels and socket interaction area. Widgets, browse buttons,
  the settings cog, and their hit targets must never overlap that lane.
- MUST implement row sharing through shared panel/layout support, extending
  the common helper when necessary. Do not reintroduce node-local absolute
  port overlays, hard-coded output-column widths, or renderer-specific CSS
  selectors as a shortcut. Measure the available space and use one shared
  layout policy for ordinary panels and custom interfaces.
- SHOULD use row sharing only while the controls remain readable and useful.
  At narrow widths, with long output labels, or when native inputs/outputs
  prevent a clean arrangement, fall back to stacked controls below the ports.
  Do not force extra node width or shrink controls, text, or button hit targets
  merely to make the compact arrangement fit.
- The settings cog remains at the top right of the **widget content lane**,
  before editable fields and clear of the output lane. Row sharing does not
  move it to a filter row or footer; the Folders example establishes the
  space-saving geometry, not an exception to the settings-placement contract.
- MUST check both Nodes 2.0 and the legacy canvas at normal and narrow widths,
  including long labels, linked inputs, and all default ports. A supported
  stacked fallback is preferable to clipped labels or intercepted links.

Use `installOutputLane()` in [web/output_lane.js](web/output_lane.js) for this
policy. Standard unmounted panels install it automatically; custom Folders
uses the same helper. It measures native output labels and socket geometry,
reserves that lane beside the first visible section, and restores stacked rows
when controls do not fit or native inputs need the space. Never copy the old
Folders-only `widgets_start_y=0` override.

**Current renderer support:** the legacy canvas exposes `widgets_start_y` for
safe row sharing. Nodes 2.0 in frontend 1.57.1 places native slots and DOM
widgets in separate vertical rows and exposes no equivalent placement hook;
the shared helper deliberately uses stacked rows there. Keep this supported
fallback until the frontend provides safe layout support. Do not simulate
support with negative margins, native-template CSS selectors, or port overlays.

## 5. Icons and file/folder actions

MUST use `ICONS` and `iconButton(icon, title, handler)` from `ray_panel.js`.
Reuse the existing SVG geometry, `viewBox`, and stroke treatment. Emojis are
reserved for the established node/category titles, not substitutes for path
buttons. Do not introduce another icon font or external icon dependency.

| Shared icon | Meaning |
| --- | --- |
| `folder` | Choose a directory or the established open-folder action |
| `file` | Choose a source file or an explicit Save As destination |
| `refresh` | Rescan/reload the current source |
| `settings` | Node settings, configuration, options, and additional controls; always in the node header at the top right |
| `edit` | Edit content, such as deck entries; never a substitute for settings |
| `remove` | Remove the item in its row; keep separate from numeric decrement |
| `link`, `unlink` | Connected source and disconnect action |
| `minus`, `plus` | Numeric adjustment |
| `fixed`, `increment`, `decrement`, `randomize` | Native seed-after-run modes |

Every icon-only action MUST have `type="button"`, a useful `title`, and an
`aria-label`; `iconButton()` supplies these. A file icon's tooltip distinguishes
`Choose model file` from `Choose output file`. Preserve the compact button
size and spacing. Use the established family action for opening a saved
location; choosing a folder and opening it in the file manager are different
operations with different handlers.

### One implementation for each action

`ICONS` and `iconButton()` in `web/ray_panel.js` are the shared icon library and
button behavior. MUST extend them instead of defining a node-local SVG, cog
constant, button constructor, size override, or click-handling variant. The
settings cog has exactly one SVG source, one shared CSS size variant, and the
same accessible button behavior everywhere. Its **button hit target is exactly
30 by 30 CSS pixels**; the centered glyph remains 16 by 16 pixels with the shared
stroke. Hover, disabled, keyboard focus, and pointer behavior come from the
shared component, including when mounted outside `.rp`.

MUST use a shared node-header/action mounting helper for node-level actions.
Standard panels and custom galleries use that same header implementation;
neither may independently position a cog with inline margins or offsets.
`installPanel(node, { headerActions, sections })` exposes the declarative node
action API. `headerActions` accepts shared buttons or
`{ icon, title, onClick, label? }` descriptors, or a factory receiving the panel.
Use section `actions` for contextual list-heading actions. Custom interfaces
use `createNodeHeader(title, actions)` and its `element`, `setActions()`, and
`destroy()` lifecycle instead of building another header.
The shared helper owns right alignment, ordering, spacing, and teardown. A
settings action must not be duplicated as another text button in the node body.

### Context and placement contract

The node content header is its first control row below the native title and
before editable source fields. Its first section title is on the left and
node-level actions are aligned at the **top right of the widget content lane**.
When compact row sharing fits, this lane sits beside native output ports;
otherwise it starts below the native port region. Do not overlay or move native
titles or input/output ports. This definition applies in Nodes 2.0 and the legacy
canvas and keeps the action reachable at narrow widths.

| Action/context | Icon and typical placement |
| --- | --- |
| Settings, configuration, options, additional controls | `settings`, one 30 × 30px button at the far right of the node content header |
| Other node-level secondary actions | In the same shared header action group, before the settings cog; settings remains rightmost |
| Add an item to a node's primary list | `plus`, in the list heading's trailing action group; if the list is the node's first section, share its top header before the cog |
| Remove a list item | `remove`, at the right end of that item's row; never a node-level settings action |
| Edit an item's content | `edit`, adjacent to that item or its summary; an entries editor can stay beside the entries summary |
| Choose a source file/folder or Save As | `file` / `folder`, immediately after the corresponding path input |
| Rescan a source folder | `refresh`, after that folder's browse button in the same source row |
| Build a filename/card name | Shared name-builder action beside the corresponding name field |
| Numeric minus/plus and seed modes | Inside or immediately after their value control, using shared editors |
| Copy configuration | Beside the relevant content; use a labeled action when meaning would be unclear. Reports use their STRING output. |

Do not use a pencil for configuration dialogs, place node settings in a footer,
attach the cog to an unrelated filter row, or scatter copies across sections.
Do not add a cog to a node with no secondary settings. Preserve specialized
analog faces and compact modes; existing content-editing pencils are valid.

When updating an existing node, migrate its settings entry point without
changing native widget names, links, values, defaults, or dialog behavior.
Queued Model Loader's Spectrum options, Folders settings, and Model Card's
secondary controls are settings actions and must follow this header contract.

## 6. Path picking, loading, and saving

### Choose the dialog from the field's meaning

| Field meaning | Browse kind | Icon | Expected behavior |
| --- | --- | --- | --- |
| Directory to enumerate or process | `folder` | `folder` | Choose an existing directory |
| Existing image/model/JSON/etc. source | `file` | `file` | Open a file with supported-format filters |
| Explicit output filename | `save` | `file` | Native Save As, including filename and correct extension |
| Destination directory plus a generated name | `folder` | `folder` | Choose the directory; keep filename/prefix separate |

MUST use the field's `browse` spec, `browseInto()`, or `browsePath()` from
[web/browse_common.js](web/browse_common.js). These call the server's
`/ray/browse` route in [browse_routes.py](browse_routes.py). Do not use a browser
upload input to obtain a server filesystem path. The native dialog appears on
the ComfyUI server computer; typed paths also refer to that server.

- Keep the path text editable. A remote browser or unavailable native dialog
  must not prevent users from supplying a valid server path manually.
- Start at the current value. Preserve spaces, Unicode, quoted pasted paths,
  and platform path semantics using the appropriate existing resolver.
- Cancellation returns `null` / `false`: MUST leave the value and graph history
  unchanged. A failed dialog shows the shared notification and preserves input.
- MUST protect linked inputs. Shared panel rows show the connected source
  instead of a local editor; custom actions must guard links too. Recheck after
  awaited work before committing if the connection may have changed.
- Commit a selected path through the native widget callback and graph history,
  just as typing does. Do not silently disconnect an input or create a second
  DOM-only path value.
- Keep filters aligned with the actual parser/writer. `IMAGE_FILTERS` is shared
  for image pickers. Model writers use safetensors; metadata Save As uses JSON
  in sidecar mode and safetensors in model-copy mode. Inspection may advertise
  additional formats only when its backend supports them.
- For mode-dependent outputs, use `browse: node => ({ kind: "save", ... })` so
  the filter reflects the current mode at click time. Validate the suffix again
  in the backend; a dialog filter is not validation.
- MUST present one clear source picker for one source. Preserve hidden legacy
  model selection/path fields and their links using the existing migration
  pattern; do not expose competing dropdown and path selectors again.

### Loading contract

- MUST resolve and validate paths in the backend. Define source precedence
  once and reuse it. For Model Tools, `source_path()` uses a connected live
  MODEL, then `model_data`, then a typed path. Reuse `resolve_file()` for
  ComfyUI model-group names and explicit model paths.
- Use ComfyUI's `folder_paths` for managed models, output, and temp roots.
  Do not hard-code workstation paths or bundle a private model list.
- MUST keep node construction, schema discovery, and default screenshots free
  of model loads/downloads or write operations. Explicit read-only previews
  must stay read-only; expensive work belongs to execution or an explicit
  action with useful feedback.
- MUST keep package discovery usable when an optional feature dependency is
  absent. Declare dependencies in the appropriate requirements group and
  explain missing optional packages when that feature is used. Do not install
  packages, replace Torch/CUDA, or fetch models during import. Choose package
  import mode explicitly and preserve real dependency tracebacks rather than
  masking them with a broad retry from another module location.
- SHOULD inspect headers/indexes before loading tensors. Reuse `TensorSource`
  for supported model files, shards, quantization markers, and tensor access.
  Do not implement a second safetensors reader in a new node.
- Reuse `ModelAsset`, `load_asset()`, and ComfyUI's native loaders. File-only
  operations must remain usable without initializing an inference model. Model
  Tools infer this from MODEL/CLIP/VAE output use; do not add a loading toggle or
  materialize a GPU model just to inspect, convert, merge, or save a file handle.
- MUST cooperate with ComfyUI's model management and interruption handling.
  Avoid global model/device state shared between unrelated nodes. Specialized
  inference optimizations must restore any temporarily changed native behavior
  on success, error, and cancellation.
- Distinguish storage precision from runtime support. Report unsupported
  architecture/format clearly; do not claim conversion restores lost precision
  or silently substitutes another loader.

### Saving contract

- MUST distinguish a destination folder, a filename template/prefix, and an
  explicit output file. Explain blank/default and relative-path behavior in
  the field tooltip. Reuse the family resolver instead of inventing another
  interpretation of a blank path.
- Save Image resolves blank/relative directories under ComfyUI output, and
  treats its prefix as a filename stem, not another directory. Model Tools use
  `save_path()` for automatic prefix-based output or a validated explicit file.
  Save Model uses `save_model_path()` for a destination folder and exact stem,
  without a counter. Its previous path, JSON and explicit-file values stay hidden
  for saved-workflow compatibility; new workflows use the typed source/metadata
  inputs and folder control.
- MUST default to preserving existing files. Save Image uses
  `filename_template.create_unique()` for exclusive creation and collision
  suffixes. Model Tools use `commit_file(..., overwrite=False)`; explicit
  replacement requires the existing overwrite control.
- SHOULD write model/JSON output to a temporary file beside the destination,
  validate it, then commit atomically. Reuse `TensorWriter`, `save_tensors()`,
  `atomic_json()`, and `rewrite_metadata()` as appropriate. Do not replace
  no-clobber handling with an existence check followed by an unsafe overwrite.
- MUST clean owned temporary files and handles on error/interruption. A
  connected or cached result may outlive one execution; preserve backing files
  for as long as its data handle requires them.
- Preserve metadata by default according to the node's contract. Respect
  ComfyUI's global metadata-disable setting and explicit node controls. Keep
  generated temp previews free of embedded workflows and destination paths.
- Return the actual saved path/result report only after success. A preview,
  filename example, or dialog selection must not announce a completed save.

## 7. Parsers, data contracts, and shared processing

- MUST search for a parser/helper before adding one. Keep parsing and data
  transformation independent of DOM code and node registration where practical.
  Validation must also run on the execution path so API-queued workflows
  cannot bypass it.
- **Filename language:** reuse [filename_template.py](filename_template.py)
  and [web/save_name.js](web/save_name.js). Their token syntax, Unicode cleanup,
  reserved-name handling, limits, and formatting must agree. Extend both and
  [tests/filename_cases.json](tests/filename_cases.json) together. Reuse
  `createWidgetPicker()` for workflow-widget selection.
- **Model metadata:** reuse `metadata_fields()`, `parse_metadata_json()`,
  `embedded_metadata()`, and `json_text()` in [model_tools.py](model_tools.py).
  Frontend editing uses `parseMetadataJSON()`, `metadataRows()`, and
  `rowsToMetadata()` in [web/model_tools_ui.mjs](web/model_tools_ui.mjs).
  Preserve text versus explicitly selected JSON values. Reject duplicate keys,
  malformed objects, non-finite numbers, and unsafe integer edits rather than
  silently corrupting values. Preserve raw metadata text when precision needs
  to survive a browser round trip.
- **Image metadata and prompts:** reuse the relevant extraction functions in
  [ray_local_scraper.py](ray_local_scraper.py) and
  [ray_meta_inspect.py](ray_meta_inspect.py). Choose the existing prompt-harvest
  or structured-inspection contract intentionally; do not duplicate their
  EXIF/PNG/sidecar/workflow traversal heuristics in a new loader.
- **Model Card configuration:** reuse `parse_config()` and planning/layout
  helpers in [model_card.py](model_card.py). Errors should identify the line
  and expected syntax. Never evaluate configuration as executable code.
- **Image tensors:** reuse `normalize_image()` and color conversions in
  [_common.py](_common.py) when their RGB contract applies. It normalizes to
  BHWC float32 RGB in `[0,1]` and drops alpha. Do not call it in an
  alpha-preserving path without handling that requirement separately.
- MUST validate shape, dtype, finite values, empty inputs, and size/resource
  limits where relevant. Preserve native IMAGE/MASK/CLIP/MODEL contracts and
  batch behavior. Keep deterministic seeded behavior reproducible.
- MUST report malformed input as an actionable error, not substitute an empty
  object or a successful-looking result. Optional display/cache failures may
  degrade gracefully without concealing execution failures.

## 8. Workflow behavior, responsiveness, and lifecycle

- Native widgets MUST remain the source of truth for values, queueing, API
  execution, and saved workflows. DOM controls edit those widgets through
  `panel.write()` or the established family helper. Auxiliary DOM widgets must
  use `serialize:false`; persistent custom configuration belongs in native
  widgets or documented `node.properties`.
- MUST bracket user edits with `graph.beforeChange()` / `afterChange()`, invoke
  the widget callback, and mark the canvas dirty. Group a drag/typing gesture
  as one undo transaction. Preserve seed-after-generation updates.
- Custom rows MUST reuse `linkChip()`, `linkOf()`, and
  `registerLinkTargets()` where appropriate. Keep the unregister function and
  call it on removal. Preserve both row-drop connections and native sockets.
- MUST chain existing `onNodeCreated`, `onConfigure`, `onExecuted`, resize,
  serialization, and removal hooks with their arguments and return behavior.
  Installation must be idempotent. Loading/duplicating a node must not add
  duplicate panels, listeners, or widgets.
- MUST isolate typing and interactive dragging from canvas shortcuts/panning.
  Keep keyboard alternatives, focus-visible outlines, associated labels, and
  accessible selected/checked states. Scrolling a gallery or editor must not
  accidentally zoom the graph. Reuse analog wheel opt-in and grouped edits.
- MUST disconnect observers, clear timers, abort owned requests, unregister
  targets, revoke object URLs, and remove owned overlays on teardown. Reuse
  family `destroy()` methods rather than leaving work running after deletion.
- SHOULD page/virtualize large collections and load thumbnails lazily. Reuse
  the Folders cache/revision model; do not hold full-resolution media or GPU
  tensors in browser/workflow state. Cache keys must change when files change.
- MUST reject stale async results after a source/mode change. Keep busy, empty,
  canceled, failed, and successful states distinct; cancellation is not an
  error. Give a useful next action and retry path.
- Heavy filesystem/model work in HTTP handlers SHOULD run off the event loop,
  as in `model_tools_routes.py`. Long execution SHOULD report progress and
  honor ComfyUI interruption. Bound caches and peak memory; explain optional
  high-RAM behavior beside its control.
- MUST reuse `route_security.require_local()` for endpoints that open desktop
  dialogs/locations or expose arbitrary server paths. Preserve capability and
  containment checks for gallery assets. Do not weaken existing locality
  checks or construct shell commands from user paths.

## 9. Shared-component map

These are existing modules, not a request to create a new component framework.
Reuse the narrowest appropriate helper. Some older helpers are private;
extract a tested shared API if another node needs them rather than importing
an undocumented private function or copying it.

| Need | Existing implementation to use or extend |
| --- | --- |
| Standard controls, sections, path rows, sizing, settings dialog | [web/ray_panel.js](web/ray_panel.js): `installPanel`, `ensurePanelStyles`, `openPanelSettings` |
| Custom popup surface and controls | [web/ray_panel.js](web/ray_panel.js): `.rp-surface`, `.rp-title`, `.rp-section`, `toggleButton`; keep only content-specific layout in popup CSS |
| Schema descriptions on custom controls | [web/ray_panel.js](web/ray_panel.js): `inputTooltip(node, name, fallback)` |
| Measured content/output lanes and renderer fallback | [web/output_lane.js](web/output_lane.js): `installOutputLane`, `measureOutputLane` |
| Declarative layouts for ordinary nodes | [web/ray_panels.js](web/ray_panels.js): `PANEL_SPECS` |
| Shared SVGs and icon buttons | [web/ray_panel.js](web/ray_panel.js): `ICONS`, `iconButton` |
| Settings cog and node action placement | [web/ray_panel.js](web/ray_panel.js): `iconButton("settings", ...)`, `createNodeHeader`, `installPanel` headerActions / section actions; standard and custom panels use the same API |
| Link chips, row drop targets, native-link compatibility | [web/ray_panel.js](web/ray_panel.js), [web/legacy_panel_links.js](web/legacy_panel_links.js) |
| Black palette, visibility compatibility, Dymo labels | [web/_common.js](web/_common.js), [web/ray_bucket_tints.js](web/ray_bucket_tints.js) |
| Native browsing and notifications | [web/browse_common.js](web/browse_common.js), [browse_routes.py](browse_routes.py) |
| Desktop/filesystem route locality | [route_security.py](route_security.py) |
| Filename parsing, collision-safe creation, name builder/widget picker | [filename_template.py](filename_template.py), [web/save_name.js](web/save_name.js) |
| Image saver, output folder semantics, comparison preview | [ray_save_image.py](ray_save_image.py), [web/ray_save_image.js](web/ray_save_image.js) |
| Model source resolution, snapshots, native loading, output paths, progress | [ray_model_tools.py](ray_model_tools.py): `resolve_file`, `source_path`, `load_asset`, `save_path`, `progress` |
| Tensor sources/assets, conversion, merging, safe writers, model metadata | [model_tools.py](model_tools.py): `TensorSource`, `ModelAsset`, `TensorWriter`, `commit_file` and operation helpers |
| Dependency-free atomic commits and duplicate-key JSON parsing | [data_io.py](data_io.py): `commit_file`, `parse_metadata_json`; Model Tools re-exports both for existing callers |
| Model metadata table/raw editor and paged report | [web/ray_model_tools.js](web/ray_model_tools.js), [web/model_tools_ui.mjs](web/model_tools_ui.mjs) |
| Read-only model previews | [model_tools_routes.py](model_tools_routes.py) |
| Folder/media selection and server asset handling | [web/folders_gallery.js](web/folders_gallery.js), [folders_routes.py](folders_routes.py), [ray_folders.py](ray_folders.py) |
| Gallery styles, filters, settings | [web/folders.css.js](web/folders.css.js), [web/folders_filters.js](web/folders_filters.js), [web/folders_settings.js](web/folders_settings.js) |
| Thumbnail loading, bounded cache, persisted analysis | [web/folders_thumbnails.js](web/folders_thumbnails.js), [web/folders_cache.js](web/folders_cache.js), [web/folders_nsfw.js](web/folders_nsfw.js) |
| Analog registration, edits, wheel interaction, styles and hardware | [web/analog_common.js](web/analog_common.js), [web/analog_themes.js](web/analog_themes.js), [web/analog_hardware.js](web/analog_hardware.js), [web/analog_curve.js](web/analog_curve.js), [web/analog_audio.js](web/analog_audio.js) |
| Shared image normalization and color conversions | [_common.py](_common.py) |
| Prompt harvesting / structured image metadata | [ray_local_scraper.py](ray_local_scraper.py), [ray_meta_inspect.py](ray_meta_inspect.py) |
| Model Card parser, plan, layout, resource limits | [model_card.py](model_card.py), [web/ray_model_card.js](web/ray_model_card.js) |
| Help popup, generated port reference, selection toolbar | [web/help.mjs](web/help.mjs), [web/help_defs.mjs](web/help_defs.mjs), [web/ray_help_toolbar.js](web/ray_help_toolbar.js) |

When a shared helper changes, identify its callers and screenshots. Avoid
backward-incompatible parameter changes, repeated parser implementations, and
node-specific branches in a general helper when a declarative option suffices.

## 10. Reference inventory: every current node

All images below are default Nodes 2.0 captures. Section lists include
conditional groups that may be hidden in the default screenshot. Python entry
modules follow `_NODE_MODULES` in `__init__.py`; Model Tools share
`ray_model_tools.py`. Use the linked image together with the named frontend.

| Registered ID / screenshot | Section vocabulary | Frontend reference |
| --- | --- | --- |
| [RayCRT](screenshots/RayCRT.png) | Screen, Strength | `ray_panels.js` |
| [RayOffsetPrint](screenshots/RayOffsetPrint.png) | Look, Plates, Paper | `ray_panels.js` |
| [RayPixelArtDetector](screenshots/RayPixelArtDetector.png) | Pixels, Palette, Dither | `ray_panels.js`, `ray_pixel_art.js` |
| [RayFilmStock](screenshots/RayFilmStock.png) | Look, Texture, Custom look | `ray_panels.js`, `ray_film_stock.js` |
| [RayVHS](screenshots/RayVHS.png) | Tape, Effects, On-screen display | `ray_panels.js`, `ray_vhs.js` |
| [RayKnob](screenshots/RayKnob.png) | Range, hardware face; compact mode | `ray_knob.js`, `analog_common.js` |
| [RaySwitch](screenshots/RaySwitch.png) | Switch, hardware face; compact mode | `ray_switch.js`, `analog_common.js` |
| [RayButtonDeck](screenshots/RayButtonDeck.png) | Buttons, hardware face; compact mode | `ray_button_deck.js`, `analog_common.js` |
| [RayFaderBank](screenshots/RayFaderBank.png) | Bank, hardware face; compact mode | `ray_fader_bank.js`, `analog_common.js` |
| [RayFastQwen3VL](screenshots/RayFastQwen3VL.png) | Prompt, Sampling, Advanced | `ray_panels.js` |
| [RayVLMFolder](screenshots/RayVLMFolder.png) | Images, Prompt, Sampling, Output, Memory | `ray_panels.js`, `ray_vlm_folder.js` |
| [RayPromptFetcher](screenshots/RayPromptFetcher.png) | Scraper, active Local Folder / PromptDexter / CivitAI source | `ray_prompt_fetcher.js` |
| [RayMetaInspect](screenshots/RayMetaInspect.png) | Metadata; inspect/embed visibility | `ray_panels.js`, `ray_meta_inspect.js` |
| [RayTextFolder](screenshots/RayTextFolder.png) | Prompts, Output | `ray_panels.js`, `ray_txt_folder.js` |
| [RaySaveImage](screenshots/RaySaveImage.png) | Output, Preview | `ray_save_image.js`, `save_name.js` |
| [RayFolders](screenshots/RayFolders.png) | Folder, Media | `ray_folders.js`, `folders_gallery.js` |
| [RayModelCard](screenshots/RayModelCard.png) | Card, Sampling, Configuration; secondary settings | `ray_model_card.js` |
| [RayModelLoadAs](screenshots/RayModelLoadAs.png) | Source, Loading | `ray_model_tools.js` |
| [RayQueuedModelLoader](screenshots/RayQueuedModelLoader.png) | Models; Loader options / Spectrum | `ray_queued_model_loader.js`; shared panel/settings and icons |
| [RayModelConvert](screenshots/RayModelConvert.png) | Source, Conversion | `ray_model_tools.js` |
| [RayModelSave](screenshots/RayModelSave.png) | Output, Metadata | `ray_model_tools.js` |
| [RayModelMetadata](screenshots/RayModelMetadata.png) | Source, Metadata; table/JSON editor | `ray_model_tools.js`, `model_tools_ui.mjs` |
| [RayModelMetadataSave](screenshots/RayModelMetadataSave.png) | Output, Source model, Metadata | `ray_model_tools.js` |
| [RayModelMerge](screenshots/RayModelMerge.png) | Merge, Algorithm, Output | `ray_model_tools.js`, `model_tools_ui.mjs` |
| [RayModelInspector](screenshots/RayModelInspector.png) | Source, Inspection | `ray_model_tools.js` |
| [RayModelCompare](screenshots/RayModelCompare.png) | Sources, Comparison | `ray_model_tools.js` |
| [RayLoraBake](screenshots/RayLoraBake.png) | LoRA, Output | `ray_model_tools.js` |
| [RayLoraExtract](screenshots/RayLoraExtract.png) | Sources, Extraction, Output | `ray_model_tools.js` |
| [RayLoraQKVLoader](screenshots/RayLoraQKVLoader.png) | LoRAs | `ray_lora_qkv_loader.js`, `ray_panel.js` |

Frontend filenames in this table are relative to `web/`. New nodes MUST be
added to this inventory with a reference image and their shared components.

## 11. Minimal panel composition example

This is a spec shape, not a new registered node. The named native widgets must
already exist with matching backend defaults and semantics. Put a plain layout
in `PANEL_SPECS`, or install it once from dedicated node code:

```javascript
import { installPanel } from "./ray_panel.js";
import { IMAGE_FILTERS } from "./browse_common.js";

installPanel(node, {
    sections: [
        { title: "Source", fields: [
            { name: "path", label: "Image file",
              browse: { kind: "file", title: "Choose an image", filters: IMAGE_FILTERS },
              placeholder: "Path to an image" },
        ] },
        { title: "Processing", fields: ["mode", "strength"] },
        { title: "Output", fields: [
            { name: "directory", label: "Output folder",
              browse: { kind: "folder", title: "Choose an output folder" } },
        ] },
    ],
});
```

For an explicit output filename, replace the folder field with a `kind:"save"`
path field and writer-specific filters. For a custom editor, insert a
`{ custom: panel => element }` field in a named section. Let the shared panel
handle visibility, links, callbacks, history, and measurement.

## 12. Completion checklist

- [ ] Stable ID, category/title pattern, native schema, output order, defaults,
      tooltips, and old-workflow behavior are correct.
- [ ] Closest family reused; new controls/parsers have no duplicate shared
      implementation. Black shell, magenta headings, section rules, compact
      sizes, icons, and color meanings match this guide.
- [ ] Every intended control has a named section. Mode switches hide empty
      groups and separators without gaps. Titles and ports remain visible.
- [ ] Suitable controls share rows with outputs where space permits, using
      shared layout support. The output lane and top-right settings remain
      clear; narrow widths and long labels have a usable stacked fallback.
- [ ] Native widget values survive save/load, duplicate, undo/redo, API queueing,
      and execution. Links, unlinking, row-drop targets, and seed modes work.
- [ ] File/folder/Save As behavior matches the field, including cancel,
      unavailable dialogs, linked input, Unicode/space-containing paths, mode
      filters, wrong extensions, and existing destinations.
- [ ] Loading/saving/parsing validates inputs, preserves data and metadata,
      handles errors/interruption, and releases owned resources. Empty and
      high-volume cases stay usable.
- [ ] Node `DESCRIPTION`, tooltips, and help explain features, controls, usage,
      and limitations. Add authored help to `help_defs.mjs` when needed. Update
      [NODES.md](NODES.md) and the relevant end-user guide. Keep maintenance
      instructions in this guide, `AGENTS.md`, or `developer/`.
- [ ] Run relevant checks from [TESTING.md](TESTING.md). Parser changes need
      meaningful round-trip/invalid-input coverage; shared UI changes need
      both renderer paths and affected specialized interfaces checked. Review
      visuals in the real frontend; a static fixture is not a screenshot of a
      registered node.
- [ ] For **any node change**, including backend-only work, recapture all
      affected default Nodes 2.0 screenshots using the
      [screenshot workflow](developer/NODE_SCREENSHOTS.md). Use real defaults,
      unconnected/unexecuted nodes, complete title/controls/ports, dark canvas,
      100% zoom, 2× density, and 24 CSS pixels of padding. Never hand-edit the
      manifest fingerprints to make a stale image pass.
- [ ] Inspect each new PNG; commit it with `screenshots/manifest.json` and its
      documentation. Run `python scripts/check_node_screenshots.py` and resolve
      every reported issue. Shared changes require all affected captures even
      when fresh PNG bytes are identical.

Documentation-only edits to this guide do not change node source fingerprints
or require recapturing unchanged nodes. The freshness check should still pass.
