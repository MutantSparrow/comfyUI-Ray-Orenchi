# Node compliance audit — 2026-10-25

Reviewed all 29 registered nodes against [the design contract](../UI.md), their
registered schemas, authored help, end-user guides, and real frontend renders.
The review uses frontend 1.57.1 with an isolated CPU ComfyUI instance.

## Findings and completed fixes

| Finding | Resolution |
| --- | --- |
| 85 inputs and 39 outputs lacked descriptions | Filled the missing descriptions; all 304 current inputs/controls and 121 outputs have help. The input total includes the new optional Embed overwrite control. |
| Native schema tooltips were absent from custom panel controls | Shared `inputTooltip()` binds registered descriptions to rows, labels, editors and choices. Custom source pickers, path fields and actions also have useful help. |
| Popup headings, surfaces, controls and focus colors differed | Filename, curve, deck and Folders popups use the shared black surface, magenta title, neutral controls and lavender focus treatment. Folders settings use named sections and shared toggles. |
| Documentation disagreed with current nodes | Updated folder-captioning image retention, native model-list execution, Save Model naming/metadata, Pixel Art resizing/palettes, analog styles, and current text generation. Added authored help for the missing eight Model Tools nodes. All 29 nodes now have authored help. |
| No complete end-user input/output reference | Added [the complete reference](../NODE_REFERENCE.md) and a schema-backed update/check command. Existing defaults, choices, bounds and connections are documented. |
| Metadata Inspector used Open for an Embed destination | Inspect uses the source-image dialog; Embed uses PNG Save As. Embed-only fields follow the mode. Shared dialogs preserve cancellation and inputs connected while the dialog was open. |
| Embed could overwrite files and return successful-looking empty results for invalid metadata | Added an optional overwrite toggle, off by default; validate PNG suffix and metadata; use atomic no-clobber commits with temporary-file cleanup. Invalid Embed inputs fail execution clearly. Existing Inspect empty/error outputs remain supported. |
| Repeated file commits and duplicate-key parsers | Extracted dependency-free `data_io.py`; Model Tools re-exports its existing API and Metadata Inspector reuses it. |
| Async previews could replace edits after changing source | Metadata/report previews reject stale responses and abort owned requests on replacement/removal. Reopening a curve editor closes its previous listeners and owned overlay. |
| Compact output-row placement was node-specific | Added shared measured legacy layout support for panels and Folders, with clear output lanes, native-input/width fallbacks, lifecycle cleanup and settings containment. Nodes 2.0 uses the supported stacked fallback below. |

Settings use the same shared 30 × 30 cog and first-content header. Content
editing keeps the pencil beside its content; add/remove and path actions retain
their contextual positions. Registered class IDs and output order are unchanged.
The only schema addition is optional `RayMetaInspect.overwrite`, default false;
existing inputs, defaults and limits are preserved.

## Verification

- All 29 default interfaces passed section, tooltip and settings checks in both
  Nodes 2.0 and the legacy renderer, without frontend exceptions.
- Shared actions passed geometry, focus, keyboard, disabled-state, graph-event,
  conditional-placement, teardown and saved-workflow metadata-editor checks.
- Output-lane tests passed production integration, actual legacy row sharing,
  narrow/long-label/native-input fallback, unchanged native port coordinates,
  socket hit targets, cog containment and restoration of owned layout state.
- Popup checks passed Folders Apply/Cancel, curve editing/cleanup, filename and
  deck styling, custom-editor keyboard isolation, PNG dialog mode and stale
  metadata-response rejection.
- Metadata Inspector and Model Tools: 130 tests passed. Model workflow and image
  saving: 26 tests and 4 subtests passed. Filename parsing: 76 shared cases passed;
  browse cancellation/link guarding and browser/Python merge-name parity passed.
- All modified frontend modules passed syntax checks; Python sources parsed;
  the complete reference matches the live schemas; whitespace checks passed.
- All 29 default Nodes 2.0 screenshots were recaptured with complete titles,
  default controls and native ports, visually reviewed, and checked for source
  freshness using the repository screenshot workflow.

Commands and repeatable checks are in [TESTING.md](../TESTING.md).

## Main branch integration validation

The merge retains the main branch's filesystem-access rules, release workflows,
package checks and decoder integration coverage. Startup and import checks now
expect all 29 stable node IDs. Screenshot freshness is checked by CI.

The combined branch passed 839 CPU tests with 5 expected skips and 4 subtests,
all six JavaScript suites, all six browser fixture suites, and the real-node
contract and output-lane checks in both renderers. Distribution and startup
smoke checks passed. The affected Model Card and Folders captures were refreshed
again after integration; all 29 screenshots and the full schema reference pass
their freshness checks.

## Renderer limit and review scope

The legacy frontend documents and consumes `widgets_start_y` in
`src/lib/litegraph/src/LGraphNode.ts` (property documentation, `computeSize()`
and `_arrangeWidgets()`). It can share the native output column's height without
moving ports. Frontend 1.57.1's Nodes 2.0 `LGraphNode.vue` renders `NodeSlots`
followed by `NodeWidgets` in separate vertical flex rows; `WidgetDOM.vue` exposes
no equivalent placement hook. The shared helper therefore returns
`native-renderer-stacks-slots` and uses stacked content there. No negative
margins, native-template selectors or cloned ports simulate unsupported layout.

This is a design, documentation and interaction review with focused backend
regressions. It does not benchmark every model architecture or certify numerical
output quality across GPU hardware. Model loading is excluded from default
rendering and screenshot capture.
