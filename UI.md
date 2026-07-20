# Ray-Orenchi UI/UX Canon

Styleguide every node in the pack conforms to. Read this before adding a new
node or reworking an existing one — the rules below are the source of truth
for naming, categories, colors, widgets, and the web layer.

## Naming

- **Python class name.** Unchanged from whatever exists (`RayFilmStock`,
  `RayCRT`, `RayPromptIterator`, …). This is the serialization key that ends
  up in every saved workflow. Never rename an existing class.
- **`NODE_CLASS_MAPPINGS` key.** Identical to the Python class name.
- **`NODE_DISPLAY_NAME_MAPPINGS` value.** Format:

      <bucket-emoji> Ray's <Bucket>: <Purpose>

  - `<bucket-emoji>` is the emoji for the node's bucket (see Categories).
  - `<Bucket>` is `VFX`, `Analog`, `Prompts`, or `LLM` — the bucket name
    spelled out.
  - `<Purpose>` is Title Case, no emoji inside, no trailing punctuation.
  - Examples: `✨ Ray's VFX: Film Stock`, `📁 Ray's Prompts: Folder Scraper`,
    `💬 Ray's LLM: Ollama Chat`, `🎛️ Ray's Analog: Knob`.
- **JS extension name.** `Ray.<Feature>` (already the pattern everywhere).

## Categories

Two-level tree, one top-level:

| Bucket  | CATEGORY string        | What lives here                                   |
|---------|------------------------|---------------------------------------------------|
| VFX     | `👑 Ray/✨ VFX`         | Image-space effects — CRT, Print, PixelArt, FilmStock, VHS |
| Analog  | `👑 Ray/🎛️ Analog`     | Analog-style UI widgets — Knob, Switch            |
| Prompts | `👑 Ray/📝 Prompts`     | Scrapers, hub fetcher, metadata inspector         |
| LLM     | `👑 Ray/💬 LLM`         | Chat, Prompt Iterator, Prompt Library             |

The bucket is the single visual cue that groups a node — it drives category,
display-name emoji, and node color.

## Colors

One palette. Shared in `web/_common.js` as `RAY_PALETTE`:

```js
export const RAY_PALETTE = {
  VFX:     { bg: "#2a1f3a", edge: "#8a3ac8" },  // violet
  Analog:  { bg: "#000000", edge: "#000000" },  // pitch black (knob / switch)
  Prompts: { bg: "#1f3a2a", edge: "#3aa867" },  // green
  LLM:     { bg: "#1f2a4a", edge: "#3a73c8" },  // blue
};
```

- Every node's JS calls `applyBucketTint(node, "<bucket>")` on
  `onNodeCreated` and reasserts it on `onDrawBackground` (the knob/switch
  pattern that survives v2 frontend redraws).
- **Mode-tinted nodes** (`RayCivitAI`, `RayPromptFetcher`, `RayPromptLibrary`)
  shift the bucket color via `shiftTint(baseHex, hueDeg)`. The base always comes
  from `RAY_PALETTE[bucket]` — never from a bespoke pair. This keeps sibling
  variants visually related.

## INPUT_TYPES

- **Section order.** `required` → `optional` → `hidden`. No exceptions.
- **`hidden`.** Always includes `"node_id": "UNIQUE_ID"` for any node whose JS
  side needs to correlate execute events to a node instance.
- **Every entry has a `tooltip`.** No exceptions. Sentence case, imperative.
- **Placeholder text.** Sentence case; no leading article; imperative.
  Example: `"Absolute path to a folder of images"`, not `"absolute path…"`.
- **Widget-name prefixing.** `mode__field` double-underscore prefix is only
  used on the hub nodes (`RayPromptFetcher`, `RayPromptLibrary`) where JS
  partitions widgets by mode. It is not a general rule.
- **Seed widget.** Standardize to:

      ("INT", {"default": -1, "min": -1, "max": 2**31 - 1,
               "tooltip": "-1 for random; any >=0 value is reproducible."})

- **Combo enum casing.**
  - Machine tokens (mode strings the code branches on) → `snake_case`
    (`"ollama"`, `"clip"`, `"inspect"`, `"embed"`).
  - Human-facing preset names → Title Case brand strings, verbatim
    (`Kodak Portra 400`, `Ilford HP5+`). Never renamed retroactively.
  - Two-letter axis codes → uppercase (`TL`, `TR`, `BL`, `BR`).
  - New enums added going forward follow these rules.

## RETURN_NAMES & OUTPUT_TOOLTIPS

- `RETURN_NAMES` is always provided and always `snake_case`.
- **`OUTPUT_TOOLTIPS` is always provided** when the node has outputs, as a
  tuple of one-sentence strings paralleling `RETURN_NAMES`.
- IMAGE-out nodes name the primary output `image`. Legacy names
  (`crt_image`, `print_image`) are corrected to `image`; ComfyUI matches
  outputs by index, so the rename does not break workflows.
- `OUTPUT_IS_LIST` remains a per-node opt-in for the fetchers/library.

## Legacy compatibility

- Python class names are frozen. Renaming is disallowed for the lifetime of a
  saved workflow. If a class must effectively be replaced, add an alias entry
  in `NODE_CLASS_MAPPINGS`.
- Display names are cosmetic and never round-trip into a workflow, so they
  can change freely.
- JS state property names (`node.properties.SeedState` and friends) are
  frozen for the same reason as class names.
- v2 frontend compat: all widget-hiding goes through the shared
  `setWidgetHidden(node, widget, hidden)` in `web/_common.js`, which stashes
  the original type under a single property (`_rayOrigType`). No per-file
  variant.

### Legacy output-name aliases

Workflows that predate the audit may reference these old names. ComfyUI
matches by output index; the strings just don't render anymore.

| Node          | Legacy name       | Current name |
|---------------|-------------------|--------------|
| `RayCRT`      | `crt_image`       | `image`      |
| `RayOffsetPrint` | `print_image`  | `image`      |

## Web/JS canon

- One file per node: `web/ray_<name>.js`.
- Every file starts:

      import { app } from "../../scripts/app.js";
      import { applyBucketTint, setWidgetHidden, /* ... */ } from "./_common.js";

- Every file registers exactly one extension: `Ray.<Feature>`.
- Node targeting is by exact string on `nodeData.name` / `node.comfyClass` —
  no regex, no wildcard.
- CSS class prefix: `.ray-` (rooted per widget).

Shared helpers in `web/_common.js`:

| Helper                     | Purpose                                         |
|----------------------------|-------------------------------------------------|
| `TWO_PI`                   | `Math.PI * 2` constant.                        |
| `getRadialBrushedURL()`    | Cached radial brushed-metal texture (knob/switch). |
| `RAY_PALETTE`              | Bucket color palette.                          |
| `applyBucketTint(n, bkt)`  | Assign bg + edge for a node.                   |
| `shiftTint(hex, deg)`      | Hue-rotate a base hex color.                   |
| `setWidgetHidden(n, w, h)` | V2-frontend-safe widget hide/show.             |

## Image output convention

Scrapers, fetchers, and the prompt library expose the emitted image on
the `image` output pin. Users route it to a downstream Preview Image or
Save Image node — the pack does not paint an inline preview inside its
own node bodies.

## Per-node quality checklist

Every node must:

- [ ] Category matches its bucket exactly.
- [ ] Display name follows the pattern.
- [ ] Class-level `DESCRIPTION` set — plain-text fallback surfaced by
      ComfyUI's built-in Info tab. Terse.
- [ ] Rich help entry in `web/help_defs.mjs` — powers the `?` button in
      the selection toolbar. Follows the `{title, tagline, sections[]}`
      shape (see `web/help.mjs`).
- [ ] Every widget has a tooltip.
- [ ] `RETURN_NAMES` uses snake_case; `OUTPUT_TOOLTIPS` is present.
- [ ] JS calls `applyBucketTint(node, "<bucket>")`.
- [ ] JS uses the shared `setWidgetHidden`.
