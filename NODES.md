# Node Documentation

All nodes live under `👑 Ray/` in the ComfyUI add-node menu, split across
four bucket sub-categories:

- `👑 Ray/✨ VFX` — image-space effects (CRT, Offset Print, PixelArt, FilmStock, VHS).
- `👑 Ray/🎛️ Analog` — analog-style UI widgets (Control: knob / slider, Switch, Button Deck, Fader Bank), all sharing one list of 31 styles.
- `👑 Ray/🔧 Tools` — prompt scraper, metadata inspector, TXT folder, Save Image.
- `👑 Ray/💬 LLM` — local vision-language inference and folder captioning.

Every node is black, body and title bar alike, so it reads the same under any
ComfyUI theme. Workflows saved with the old colored title bars turn black when
they load; a color you set on a node yourself is kept.

---

## ✨ Ray's VFX: CRT (`RayCRT`)

**Purpose.** Image-space CRT display effect. Simulates phosphor mask (aperture / shadow / slot), scanline beam, halation + bloom, NTSC chroma bleed, barrel curvature, vignette, and reflection gloss. Multiple SOTA-inspired presets covering classic monitors and gaming consoles.

**Category:** `👑 Ray/✨ VFX`

| Pin | Type | Notes |
|-----|------|-------|
| **Input** `image` | IMAGE | Source frame(s). BHWC accepted. |
| **Control** `preset` | enum | `trinitron_aperture`, `pvm_shadow`, `consumer_slot`, `composite_ntsc`, `arcade_royale`, `lottes_fast`, `mattias_stylised`, `royale_kurozumi`, `guest_advanced`, `cyberlab_pixels`, `newpixie_framed`, `gtu_composite`, `hyllian_glow`, `super_famicom`, `megadrive`, `ps1`, `ps2`, `nintendo_ds`, `gameboy_advance`, `psp` |
| **Control** `curvature` | bool | Lottes barrel warp (out-of-bounds becomes black bezel). |
| **Control** `intensity` | float 0–1 | Master mix vs untouched input. |
| **Control** `scanline_strength` | float 0–2 | Scales preset scan depth. |
| **Control** `mask_strength` | float 0–2 | Scales preset mask depth + brightness compensation. |
| **Output** `image` | IMAGE | Same H/W/B as input. Legacy workflows may show this pin as `crt_image`; the tensor is unchanged. |

---

## ✨ Ray's VFX: Offset Print (`RayOffsetPrint`)

**Purpose.** Image-space CMYK / duotone offset print simulation. Per-plate halftone screen at SWOP angles, plate misregistration, dot gain, ink bleed, paper substrate (tint + grain + texture), optional sepia / vignette / posterize.

**Category:** `👑 Ray/✨ VFX`

| Pin | Type | Notes |
|-----|------|-------|
| **Input** `image` | IMAGE | Source frame(s). |
| **Control** `preset` | enum | `old_newspaper`, `modern_newspaper`, `comic_book`, `chromolithography`, `inkjet`, `pulp_magazine`, `risograph`, `silk_screen`, `xerox`, `glossy_magazine` |
| **Control** `intensity` | float 0–1 | Master mix vs untouched input. |
| **Control** `ink_strength` | float 0–2 | Per-plate ink density multiplier. |
| **Control** `screen_strength` | float 0–1.5 | Halftone screen depth. |
| **Control** `paper_strength` | float 0–2 | Paper grain + texture amount. |
| **Control** `scale` | float 0–4 | Halftone screen pitch scale. |
| **Control** `paper_color` | string | Paper substrate hex color (e.g. `#fffaf0`). |
| **Control** `paper_color_mix` | float 0–1 | Blend toward `paper_color` over the preset paper tint. |
| **Output** `image` | IMAGE | Same H/W/B as input. Legacy workflows may show this pin as `print_image`; the tensor is unchanged. |

---

## ✨ Ray's VFX: Pixel Art (`RayPixelArtDetector`)

**Purpose.** Repair an existing pixel grid or abstract illustrations/photos into readable regions. Preserve exact aspect ratio, fit perceptual palettes and optionally add restrained dithering or colored outlines.

**Category:** `👑 Ray/✨ VFX`

| Pin / control | Notes |
|---|---|
| `image` | Source image or batch. |
| `input_kind` | `repair_pixel_art` or `illustration_photo`. |
| `mode` | `manual_resize`, `auto_pixel_size`, `pixel_size`. Illustration auto uses target_resolution. |
| `target_resolution`, `pixel_size` | Desired longest side or source pixels per output pixel; exact-aspect dimensions only. |
| `sampling` | `grid_snap` structural processing, `nearest` sampling, `area` averaging. |
| `reduce_palette`, `max_colors` | Fit a generated palette within its color budget. |
| `palette_style` | `source` shading or `distinct` colors; distinct also consolidates weak isolated shades in undithered illustrations. |
| `palette_strategy` | Build a generated palette with color_families, Lab/RGB clustering, simple quantization, OkLab source colors, or ramps. |
| `palette_mapping` | Choose assignment independently: auto, legacy_oklab, oklab, lab, rgb, or color_families. Applies to supplied palettes too. |
| `palette_image` (optional) | Preserve up to 256 exact swatch colors; larger references are reduced to max_colors. Overrides generated palette settings. |
| `dither`, `dither_strength` | `none`, `ordered`, `error_diffusion`; protect flat fills, strong edges and busy texture. |
| `outline` | `none`, dark `silhouette`, or shading-guided colored `selective`. |
| `foreground_mask` (optional) | One means subject, zero means background; enables outlines on complex backgrounds. |
| `seed` | -1 for random; nonnegative values reproduce palette/reconstruction choices. |
| Output `image` | Actual pixel-resolution result. |
| Output `preview` | Nearest-neighbor preview at input dimensions. |

Grid detection uses the attributed MIT-licensed Pixel Art Fixer detector locally. No model or server is required. Irrelevant controls are hidden.

---

## The node panels

Every Ray node shows its settings in one black panel, laid out like Save Image: a small grey label on the left, the control on the right, related settings grouped under short headings, and only the settings that apply to the current mode. Numbers have − and + buttons (or drag sideways on the number; Shift is finer); bounded values have a slider with a value box; short choices are segmented buttons; on/off settings are switches; the seed has an icon that cycles what happens after each run (random, fixed, +1, −1).

**Links.** Drag a link from another node onto any row of the panel to connect it to that setting; the row then shows `From <node> · <output>` with a button to unlink it. Saved workflows, queued prompts and links work exactly as with ComfyUI's own widgets.

### Browse (folder and file paths)

Every folder or file path has a folder or file icon at the right of its field: **Save Image** (Directory), **Folder Captioner** and **Prompt Scraper** (Folder of images, the scraper's only in Local Folder mode), **TXT Folder** (its folder), **Film Stock** (LUT / XMP folder) and **Metadata Inspector** (Image file, filtered to images). The icon opens your operating system's own dialog, then writes the chosen path into the field exactly as if you had typed it. Typing or pasting a path still works, and a linked path cannot be browsed.

A browser never tells a page where a picked file lives on disk, so the ComfyUI server shows the dialog and sends the path back: Python's built-in Tk dialog, which is the standard system dialog on Windows and macOS (on Linux, install `python3-tk`). That means **ComfyUI must be running on the computer you are sitting at** (ComfyUI Desktop and local installs do); opened from another machine, Browse says so and you type the path. The dialog starts in the folder currently in the widget, or the nearest parent that exists.

Only one dialog can be open at a time, and a dialog left open for fifteen minutes is closed.

---

## 🎛️ Ray's Analog: Styles (shared by every analog node)

Every analog node (Control, Switch, Button Deck and Fader Bank) offers the same 31 styles, grouped by family in the **Style…** picker: Console, Broadcast, Mastering and Rack. A style is a look (its materials, panel, accent and lamp colours, and the sound it makes), so picking "Broadcast · Bakelite Flip" on a knob gives a bakelite knob with a brass-lit ring, and on a fader bank bakelite caps.

Each style keeps the hand-drawn face it was designed with on the control it was drawn for. On the other controls the face is built from the style's description, using the same materials, scale marks and lamp behaviour, so it moves and lights up like the hand-drawn ones. On the Control, styles drawn as faders appear as sliders (tagged **slider** in the picker) and the rest as knobs. Style IDs are unchanged, so saved workflows load as before.

| Style | Panel | Hand-drawn for |
|-------|-------|----------------|
| Console · Amber Keys | charcoal | Button Deck |
| Console · Black Faders | charcoal | Fader Bank |
| Console · Blue Grey | charcoal | Control (knob) |
| Console · Channel Fader | silver | Control (slider) |
| Console · Dome Button | charcoal | Switch |
| Console · Illuminated Key | charcoal | Switch |
| Console · Lamp Domes | charcoal | Button Deck |
| Console · LED Ring | charcoal | Control (knob) |
| Console · Linear Fader | charcoal | Control (slider) |
| Console · Minimal Flat | charcoal | Control (knob) |
| Console · Minimal Pill | charcoal | Switch |
| Broadcast · Bakelite Chickenhead | olive | Control (knob) |
| Broadcast · Bakelite Flip | olive | Switch |
| Broadcast · Bakelite Pushbuttons | olive | Button Deck |
| Broadcast · Brass Slide | olive | Switch |
| Broadcast · Cream Faders | olive | Fader Bank |
| Broadcast · Ivory | olive | Control (knob) |
| Broadcast · Knurled Brass | olive | Control (knob) |
| Broadcast · Pan Slider | olive | Control (slider) |
| Broadcast · Steel Lever | olive | Switch |
| Mastering · Aluminium | silver | Control (knob) |
| Mastering · Chrome Notched | silver | Control (knob) |
| Mastering · Chrome Squares | silver | Button Deck |
| Mastering · Silver Faders | silver | Fader Bank |
| Mastering · Silver Paddle | silver | Switch |
| Mastering · Silver Skirted | silver | Control (knob) |
| Rack · Amber Slide | charcoal | Control (slider) |
| Rack · Chrome Rocker | silver | Switch |
| Rack · LED Ladder | charcoal | Control (slider) |
| Rack · Power Rocker | charcoal | Switch |
| Rack · Tape Deck Keys | olive | Button Deck |

---

## 🎛️ Ray's Analog: Response curves (Control and Fader Bank)

The Control and the Fader Bank can map the dial or fader position to the value through a curve instead of a straight line, like the taper of a potentiometer. A log taper makes the low end fine and the top coarse; an S-curve makes both ends fine; a reversed taper does the opposite. It is a setting on the control, so any Control or fader benefits, with no change to the value it stores or outputs.

**Switching it on.** Right-click → **Linear response** (the default) or **Curve response…**, which switches the response to a curve and opens the editor. The `response` property in the node's properties panel holds the same choice. The hint line under the control says **CURVE** while a curve is active. Switches and the Button Deck are not continuous, so they have no response setting.

**What it changes.** Everything that moves along the dial: dragging, clicking a slider track, the arrow keys, the mouse wheel and the position of the cap or pointer. Typing an exact value in the readout still sets exactly that value, Home and End still jump to the limits, and a value always sits where the curve says. The Python nodes, the saved value and the API prompt carry the real value, never a position, so turning a curve on or off does not move or reinterpret any value.

**The editor.** A small floating panel with a **Linear / Curve** switch, a preset list, and a plot of the curve (dial position along the bottom, value up the side, the dashed diagonal is a straight line). Click empty space to add a point, drag a point to shape the curve, double-click it or press Delete to remove it. `[` and `]` pick the previous or next point and the arrow keys move it (Shift for finer). The two end points are fixed at 0 and 1, points cannot cross each other, and the curve never goes downhill, so every value is reachable and means one dial position. Up to 16 points. Hovering shows what a dial position gives, in the control's own units. Every edit is an undo step. Escape, **Done** or a click outside closes it.

**Presets.**

| Preset | Shape | Use it for |
|--------|-------|------------|
| Audio (log) | About 9% of the range at mid-dial | A volume-style taper, fine control near zero |
| Reverse audio | The mirror of audio | Fine control near the maximum |
| Fine low end | Cubic | Gentler start than a straight line |
| Fine high end | Reversed cubic | Gentler finish |
| S-curve | Slow at both ends | Fine control near both limits |
| Fine centre | Slow around the middle | Fine control around a mid value |

The curve is saved with the workflow (the `response` and `curve` properties) and is shared by all faders of a Fader Bank.

### Compact mode (every analog node)

Right-click → **Compact mode** turns the node into its faceplate and nothing else: no title bar, no input or output dots, no setup panel, no badges and no node background, in the legacy canvas and in Nodes 2.0 alike. The Control and the Switch shrink to the size of their face (180 px wide); the Button Deck and the Fader Bank keep the size you gave them.

- **Links stay connected.** In the legacy canvas they run under the faceplate and meet the node out of sight (inputs left of centre, outputs right of it). Nodes 2.0 always attaches a link to the side of a node, so there they meet the left and right edges of the plate, halfway down.
- **Moving and selecting.** Grab the plate anywhere that isn't a working part (its frame, the Dymo strip's surroundings, the readout box, the gaps between buttons) to select and drag the node. The plate's corners resize it, and right-clicking the plate opens the node menu, where **Compact mode** switches it back.
- **Saved with the workflow.** The compact flag and the size are restored exactly on load. Turning compact mode off brings back the title, the dots and the setup panel.

The plate passes the pointer through in normal mode too, so you can drag any analog node by its faceplate.

---

## 🎛️ Ray's Analog: Control (`RayKnob`)

**Purpose.** Analog-style float control, either a rotary knob or a slider, themed after studio hardware. Drag rotates a knob face or moves a slider cap; outputs both an `INT` (quantized by `clamp`) and a raw `FLOAT` so it plugs into either side without a converter. The node keeps its original `RayKnob` ID, so existing workflows load unchanged.

**Category:** `👑 Ray/🎛️ Analog`

| Pin | Type | Notes |
|-----|------|-------|
| **Control** `min_value` | float | Range minimum. |
| **Control** `max_value` | float | Range maximum. |
| **Control** `clamp` | float ≥0 | Quantization step for the INT output (`0` → truncate). |
| **Control** `allow_negative` | bool | Whether `min_value` may go below 0. |
| **Control** `knob_value` | float | Current value (driven by the widget). |
| **Output** `int` | INT | Quantized via `clamp`. |
| **Output** `float` | FLOAT | Raw clamped float in `[min, max]`. |

**Faces.** All 31 shared styles (see Styles above). Fourteen are hand-drawn for the Control: nine knobs and five sliders, all drawn from one material set with the same 0–10 scale and 270° sweep, and the other seventeen are generated to match. Knobs: console blue grey, broadcast ivory, mastering aluminium, mastering chrome notched, console LED ring, broadcast bakelite chickenhead, mastering silver skirted, broadcast knurled brass and console minimal flat. Sliders: console linear fader, console channel fader with a dB scale, rack LED ladder, broadcast pan slider and rack amber slide. The pan slider and amber slide are horizontal; the others are vertical.

**Dragging.** Every knob sweeps 270° from `min_value` to `max_value`, and the dial follows the pointer around its centre, so a 0–1 range is as controllable as 0–1000. Hold **Shift** for 20× finer movement. Arrow keys step 1/200 of the range (Shift: 1/2000), PageUp/PageDown step ten times that, and Home/End jump to the limits. Older workflows that saved a `spin_value` setting are migrated on load; that setting no longer exists.

**Sliders.** Drag the cap, or click the track to jump the cap there. The LED ladder lights segments as the value rises and the amber slide fills behind its cap.

**Sound.** Knobs click through detents that match their printed scale, sliders scrape and tick as they move and thud at the end stops, and the pan slider taps at its centre. Switches voice each face: a thump and clack for the rack rocker, a ringing strike and spring for the steel lever, a push-and-latch for the illuminated key, a clunk for the bakelite flip, a tick-tack for the paddle, a scrape and detent for the brass slider, a soft tap for the pill and a hollow thock for the dome. The sounds are synthesized with Web Audio in `web/analog_audio.js`; there are no audio files. **Mute sound** in the right-click menu (on both the Control and the Switch) silences every analog control and is remembered per browser.

**Right-click menu.** **Linear response** and **Curve response…** (see Response curves above). **Control Style…** opens a floating picker (the 31 styles grouped by family, sliders tagged; arrow keys, Enter and Escape work) rather than a nested submenu, so it stays on screen in both the legacy canvas and Nodes 2.0. **Mute sound** is next to it. **Compact mode** shows only the faceplate (see Compact mode above). **Edit label…** changes the Dymo tape above the face; double-click or Enter also edits it. Drag around a rotary control or along a slider, use Shift for fine movement, or use Arrow/Home/End keys. Exact values can be entered in the readout. Style, compact flag, and label text persist with the workflow.

**Mouse wheel.** **Mouse wheel control** in the right-click menu (off by default, remembered per browser, shared by every analog node) lets the scroll wheel drive the control while the pointer is anywhere over the node: 2% of the range per notch, a tenth of that with Shift, with the same detent and slider sounds as dragging. The canvas does not zoom while the pointer is over a node that takes the wheel; Ctrl / Cmd + wheel still zooms, and a control driven by a link lets the wheel through. A burst of wheel steps is one undo step.

---

## 🎛️ Ray's Analog: Switch (`RaySwitch`)

**Purpose.** Boolean toggle widget in any of the 31 shared styles, nine of them hand-drawn for it. Rockers and illuminated keys show their active state; lever handles point up for ON, and horizontal paddles/sliders move toward the ON label.

**Category:** `👑 Ray/🎛️ Analog`

| Pin | Type | Notes |
|-----|------|-------|
| **Control** `state` | bool | Toggle. |
| **Output** `bool` | BOOLEAN | Mirror of `state`. |

**Right-click menu.** **Switch Style…** opens the shared picker. The hand-drawn faces are: rack power rocker, broadcast steel lever, console illuminated key, rack chrome rocker, console dome button, broadcast bakelite flip, mastering silver paddle, broadcast brass slide and console minimal pill. **Mute sound** is shared with the Control. Every face has its own click, clack or thunk. With **Mouse wheel control** on, wheel up switches on and wheel down switches off. **Compact mode** shows only the faceplate (see Compact mode above). Click the face, or focus it and press Space/Enter. **Edit label…** changes the Dymo tape above the face; double-click or Enter also edits it. Style, compact flag, and label text persist with the workflow. The controls remain usable in both Legacy and Nodes 2.0 frontends.

---

## 🎛️ Ray's Analog: Button Deck (`RayButtonDeck`)

**Purpose.** A bank of analog push buttons that replaces a dropdown. Enter one value per line; each line becomes a button, and the pressed button's text comes out as a `STRING`. Styled after retro console hardware, in the same family as the Control and Switch.

**Category:** `👑 Ray/🎛️ Analog`

| Pin | Type | Notes |
|-----|------|-------|
| **Control** `entries` | multiline string | One value per line. Blank lines and repeated lines are ignored; up to 64 entries. Edited through the popout (the pencil next to **Entries**), so the raw text box stays hidden. |
| **Control** `selected` | string | The pressed button's text, driven by the deck. If it isn't in the list the first entry is used. |
| **Output** `value` | STRING | The pressed button's text, exactly as typed. |

**Layout.** Size the node however you like: the deck lays its buttons out like a wrapping flex box, picking the grid that makes the buttons biggest in the space it has. A long landscape node lines four buttons up in one row (4×1), a square one stacks them 2×2, a tall narrow one puts them in a column. The buttons stay square and scale with the node. A new deck starts big enough for its buttons; after that the node keeps the size you give it, including when you edit the entries.

**Pressing.** The bank is interlocked like a radio-preset panel: exactly one button is pressed down and lit, and every other button stays raised and unlit. Pressing a button releases the previous one; pressing the lit one changes nothing. Arrow keys, Home and End move the selection, and Space or Enter presses the focused button. The selection follows the value, so reordering the entries keeps the same button pressed. If the pressed value is deleted, the first entry takes over (the same rule the node applies when it runs). A deck with no entries raises an error when it runs.

The pencil next to **Entries** (or right-click → **Edit entries…**) opens a popout with a text box (one value per line) and a live count of buttons. **Apply** (or Ctrl+Enter) saves the normalized list; **Cancel** (or Escape) discards the changes.

**Styles.** All 31 shared styles. Five are hand-drawn for the deck, each with its own sound, and either print the text inside the button or put it on a Dymo sticker below; every other style gets a matching generated button that prints its text in a lit window or on a sticker:

| Style | Look | Text | Sound |
|-------|------|------|-------|
| Console · Amber Keys | Ivory keycaps with a backlit amber window | Cut into the key | Clean push and latch |
| Console · Lamp Domes | Chrome-ringed glass domes that glow green | Cut into the lens | Hollow thock |
| Broadcast · Bakelite Pushbuttons | Brown bakelite buttons with an orange lamp ring | Dymo sticker | Dull clunk |
| Mastering · Chrome Squares | Brushed-aluminium keys with a green LED | Dymo sticker | Bright double tick |
| Rack · Tape Deck Keys | Tall rubber keys that sink and light a slot | Dymo sticker | Heavy ka-chunk |

Pressing a button plays its latch sound, followed by a softer release as the previously pressed button pops out. **Mute sound** in the right-click menu silences every analog control. With **Mouse wheel control** on, wheel down presses the next button and wheel up the previous one, stopping at the ends.

**Right-click menu.** **Deck Style…** (the picker used by the other analog nodes), **Edit entries…**, **Compact mode** (the faceplate alone, see Compact mode above), **Edit label…** (the Dymo tape above the deck) and **Mute sound**. Style, compact flag and label persist with the workflow.

---

## 🎛️ Ray's Analog: Fader Bank (`RayFaderBank`)

**Purpose.** A bank of vertical faders, like a small mixing desk: two to ten in a row, in up to four rows (forty faders). Each fader outputs a float from 0 to 1, and the whole bank comes out as a list too. Good for blend weights, strengths and anything else you want to balance by eye.

**Category:** `👑 Ray/🎛️ Analog`

| Pin | Type | Notes |
|-----|------|-------|
| **Control** `faders` | int 2–10 | Faders in a row (**Per row** in the panel). |
| **Control** `rows` | int 1–4 | Rows of faders. `faders` × `rows` faders in all: 6 per row and 2 rows make 12. |
| **Control** `fader_1` … `fader_40` | float 0–1 | Fader positions, driven by the bank, numbered row by row. The raw widgets are hidden; the faders are the control. |
| **Output** `values` | FLOAT (list) | Every active fader, in order, as a list. Downstream nodes run once per value, like the other list outputs in the pack. |
| **Output** `fader_1` … `fader_N` | FLOAT | One output per active fader. |

**Optional outputs.** The outputs follow `faders` × `rows`: raising either adds faders and their outputs at the end, and lowering it removes the last ones, together with any links attached to them. The outputs that stay keep their slot numbers, so existing links are never rewired. `values` is always the first output.

**Using it.** Drag a cap, or click the track to jump it to the pointer. Shift slows a drag to a twentieth. Focus a fader to use Arrow keys (0.01; Shift for 0.001), PageUp/PageDown (0.1), Home (0) and End (1). With **Mouse wheel control** on, scrolling over a fader moves that fader only: 2% per notch, a tenth of that with Shift. The readout under the faders shows the last one touched. A fader fed by a link is locked and the hint line says so. The node widens as you add faders to a row and grows taller as you add rows; it never shrinks what you sized.

**Rows.** Each row is a full strip of `faders` faders, stacked under the previous one. Numbering carries on from row to row (a bank of 6 per row has faders 7 to 12 on its second row), so `values` and the `fader_N` outputs read like a page. Workflows saved before rows existed load as one row, with every fader where it was.

**Styles.** All 31 shared styles. Three are hand-drawn for the bank: Console · Black Faders (grey caps on a charcoal panel), Mastering · Silver Faders (black caps on brushed aluminium) and Broadcast · Cream Faders (cream caps with a red line on an olive panel); every other style supplies its materials and accent colour for the caps. Faders scrape and tick like the slider faces of the Control, and thud at the end stops.

**Right-click menu.** **Fader Style…**, **Linear response** / **Curve response…** (one curve for the whole bank), **Mouse wheel control**, **Compact mode** (the faceplate alone, see Compact mode above), **Edit label…** and **Mute sound**. Style, compact flag, label and fader positions persist with the workflow.

---

## 🔧 Ray's Tools: Prompt Scraper (`RayPromptFetcher`)

**Purpose.** One node, three prompt sources. A `scraper_mode` dropdown picks between `Local Folder`, `PromptDexter`, and `CivitAI`; the frontend hides widgets that don't belong to the active mode. Outputs are harmonized to the local-scraper shape `(prompt_single, prompt_multiline, image, image_path)` so any mode is drop-in compatible with downstream wiring.

**Category:** `👑 Ray/🔧 Tools`

| Pin | Type | Notes |
|-----|------|-------|
| **Control** `scraper_mode` | enum | `Local Folder` / `PromptDexter` / `CivitAI`. Drives which widget group is shown and which backend runs. |
| **Control** `seed` | int | `-1` for random; any `≥0` value is reproducible. Shared across modes. |
| **Local** `local__folder` | string | Absolute path to a folder of images. |
| **Local** `local__recurse_subfolders` | bool | Walk every subdirectory. |
| **Local** `local__skip_no_prompt` | bool | Skip images whose metadata yields no prompt. |
| **Local** `local__prompt_best_try` | bool | Collapse to single longest prompt (always). Skip repeats via recent-best deque in random mode only. |
| **Local** `local__refresh_listing` (optional) | bool | Force a re-scan of the folder. |
| **Dexter** `dexter__category` | dropdown | Sitemap category slug, or `(any)`. |
| **Dexter** `dexter__clear_cache` | bool | Drop the recent-pick deque. |
| **Dexter** `dexter__timeout` (optional) | int 2–60 | HTTP timeout per request. |
| **CivitAI** `civitai__mode` | enum | `Blue (SFW)` / `Red (NSFW)`. |
| **CivitAI** `civitai__base_model` | dropdown | Restrict picks to a base model. |
| **CivitAI** `civitai__period` | enum | Time window. |
| **CivitAI** `civitai__sort` | enum | Gallery sort. |
| **CivitAI** `civitai__username` | string | Restrict to one uploader (optional). |
| **CivitAI** `civitai__timeout` (optional) | int 2–60 | HTTP timeout per request. |
| **Output** `prompt_single` | STRING (list) | Single-line prompt. |
| **Output** `prompt_multiline` | STRING (list) | Prompt with newlines preserved. |
| **Output** `image` | IMAGE (list) | Result image. |
| **Output** `image_path` | STRING (list) | Absolute path for Local mode; empty for web modes. |

**Refresh.** In `PromptDexter` mode the refresh icon next to **Category** re-reads PromptDexter's sitemap and updates the category list; in `CivitAI` mode the icon next to **Base model** clears the cache so the next run fetches again. A status line under them reports the result, and in CivitAI mode notes when no `civitai.secret` file is present and only public access is available. Local Folder mode shows neither.

Switching CivitAI to **Red (NSFW)** shows a small warning the first time; dismiss it and it does not come back in this browser.

### Mode details

**Local Folder.** Picks a random image from a folder and extracts any generation prompt found in its metadata. The pick is seed-deterministic; with seed `-1` a per-node 20-entry memory avoids consecutive repeats. The folder listing is cached until `local__refresh_listing` is set.

**Prompt sources, in priority order:**
1. PNG `parameters` text chunk (Automatic1111 / Forge; JSON blob variants also parsed).
2. PNG `prompt` text chunk (ComfyUI serialized prompt graph, JSON; flat-literal fallback for JustRayzist-style writers).
3. PNG `workflow` text chunk — API format or UI (`nodes[]`/`links[]`) format.
4. Any other `info[]` key whose name looks prompt-shaped (`prompt_*`, `positive*`, `caption`, `description`, `comment`, `sui_image_params`, `invokeai_metadata`, `novelai_metadata`, `dream`…). JSON values are walked recursively for nested `prompt` / `positive` keys.
5. EXIF text tags: UserComment (37510), ImageDescription (270), XPComment (40092), XPSubject / XPTitle / XPKeywords.
6. `<image>.txt` sidecar file in the same directory.

For ComfyUI graphs, the extractor first locates every text-encoder node (`CLIPTextEncode` / `CLIPTextEncodeFlux` / `CLIPTextEncodeSDXL` / `BNK_CLIPTextEncodeAdvanced` / `T5TextEncode` / `ImpactWildcardEncode` etc.). Each encoder contributes one prompt: if its `text` input is a literal string the literal is used; if it's wired to another node, the link is followed back through `ShowText` → `Text Multiline` → `String Literal` → `Text Concatenate` → primitive nodes (up to 8 hops, cycles detected) until a literal is found. Multiple text inputs on a concat-style node are joined with spaces. Encoders that only feed a sampler's `negative` input (`KSampler`, `CFGGuider`, ControlNet apply nodes and the like) are skipped, so only positive prompts come back; an encoder shared by both sides is kept. Graphs with no positive/negative sampler wiring keep every encoder. This applies to both the API `prompt` chunk and the UI `workflow` chunk.

Every candidate is passed through a path-rejection filter that drops strings that look like filesystem paths (drive letters, backslash runs, bare `.safetensors` / `.ckpt` filenames), so random `C:\loras\foo.safetensors`-style fields don't leak through as prompts.

If the image carries multiple positive prompts (e.g. a ComfyUI workflow with several `CLIPTextEncode` nodes), every output is emitted as a ComfyUI **list** — one entry per prompt — so downstream nodes iterate once per prompt. The `image` and `image_path` outputs are broadcast (repeated) across each prompt entry so each iteration sees a matching `(prompt, image, path)` triple. Single-prompt images still return lists of length 1; if no prompt is found and `skip_no_prompt` is off, the output is a single-entry list with an empty string in both prompt slots.

Supported file extensions: `.png`, `.jpg`, `.jpeg`, `.webp`, `.bmp`, `.tiff`, `.tif`.

**PromptDexter.** Fetches a random prompt and its image from [promptdexter.com](https://promptdexter.com/). Discovery is sitemap-driven, so picks reach deep content rather than only the homepage. A frozen seed reproduces the same page on every run; seed `-1` is random and avoids recently shown pages. Choosing a `dexter__category` restricts picks to that category's listed prompts. The image is a 1×1 black tensor if the page has none or the fetch fails.

**CivitAI.** Fetches a random gallery image and its prompt through CivitAI's public REST API. Items with a usable prompt are kept: either the direct `meta.prompt`, or text salvaged from an embedded ComfyUI workflow; items without one are skipped. `Blue (SFW)` requests `browsingLevel=3` and `Red (NSFW)` requests `31`. `civitai__base_model` is sampled live from the gallery, so new architectures appear as uploaders tag them. Setting `civitai__username` forces the period to `AllTime` so small per-user archives don't come up empty.

**Access strategy.** REST API (not scraping, not MCP). Public endpoint, no key required for read access. Higher-tier content unlocks if a token file is present at `civitai.secret` inside the node-pack directory — never hard-coded. The legacy `nsfw` filter is bypassed in favour of `browsingLevel` (bitmask: PG=1, PG13=2, R=4, X=8, XXX=16), which the API documents as taking precedence. Blue = `PG | PG13` = `3`; Red = all levels OR'd = `31`.

**API token.** Optional. Create `civitai.secret` inside the `comfyUI-Ray-Orenchi/` node-pack directory and paste the token as its only contents (trailing whitespace/newlines are trimmed). The token is read fresh on each request — no caching, no persistence beyond the file itself. `civitai.secret` and `*.secret` are listed in `.gitignore`; do not commit them.

---

## 🔧 Ray's Tools: Metadata Inspector (`RayMetaInspect`)

**Purpose.** Read or write image generation metadata. Two modes:

- `Inspect` — parses every known chunk (A1111 `parameters`, ComfyUI `prompt` / `workflow` graph, EXIF UserComment, sidecar text) and exposes the extracted fields as separate STRING outputs plus the raw JSON blob.
- `Embed` — writes an IMAGE tensor + `metadata_json` dict back to disk at `path`, then re-parses the file for round-trip verification.

In `Inspect`, connect a **Load Image** node to `image` and the node reads the metadata of the file it loaded: the connection is traced upstream, through nodes that only transform the image (resize, crop and similar), to the file's name. A connected image wins over `path`. An image that was generated rather than loaded has no file, so enter a `path` instead.

**Category:** `👑 Ray/🔧 Tools`

| Pin | Type | Notes |
|-----|------|-------|
| **Control** `mode` | enum | `Inspect` / `Embed`. |
| **Control** `path` | string | Inspect: source file, used when no image is connected (absolute, `input/...` or `name [input]`). Embed: destination file. |
| **Input** `image` (optional) | IMAGE | Inspect: connect a Load Image node to read that file's metadata. Embed: tensor to write. |
| **Control** `metadata_json` (optional) | string (multiline) | Embed mode: JSON dict of metadata fields to attach. Visible only in Embed mode. |
| **Output** `prompt_positive` | STRING | Positive prompt extracted from the file. |
| **Output** `prompt_negative` | STRING | Negative prompt extracted from the file. |
| **Output** `seed` | STRING | Seed if present. |
| **Output** `steps` | STRING | Sampler step count if present. |
| **Output** `cfg` | STRING | CFG scale if present. |
| **Output** `sampler` | STRING | Sampler name if present. |
| **Output** `model` | STRING | Model / checkpoint reference if present. |
| **Output** `loras_json` | STRING | LoRAs referenced in the metadata, encoded as JSON. |
| **Output** `width` | STRING | Image width in pixels. |
| **Output** `height` | STRING | Image height in pixels. |
| **Output** `raw_metadata_json` | STRING | Full raw metadata JSON — for debugging or downstream tools. |
| **Output** `image` | IMAGE | Source image tensor. |

---

## ✨ Ray's VFX: Film Stock (`RayFilmStock`)

**Purpose.** Analytical film-stock emulation. Applies a per-stock tonal curve + color response, optional grain and halation, and (optionally) layers a real graded look from a `.cube` / `.3dl` LUT or Photoshop / Lightroom `.xmp` develop-setting file.

**Category:** `👑 Ray/✨ VFX`

| Pin | Type | Notes |
|-----|------|-------|
| **Input** `image` | IMAGE | Source frame(s). |
| **Control** `preset` | enum | Film stock name (Kodak Portra 400, Ilford HP5+, Cinestill, Fujifilm Velvia, …). |
| **Control** `intensity` | float 0–1 | Master mix vs untouched input. |
| **Control** `grain_amount` | float 0–4 | Grain strength (0 = off). |
| **Control** `halation_amount` | float 0–4 | Halation bloom strength (0 = off). |
| **Control** `expose_stops` | float ±4 | Exposure compensation before the tonal curve. |
| **Control** `seed` | int | `-1` for random; any `≥0` value is reproducible. |
| **Control** `assets_folder` (optional) | string | Folder recursed for `.cube` / `.3dl` LUTs and `.xmp` develop presets. |
| **Control** `asset_file` (optional) | dropdown | LUT / XMP file to overlay on top of the analytical curve. Repopulated live by the frontend when `assets_folder` changes. |
| **Output** `image` | IMAGE | Emulated film-stock image. |

---

## ✨ Ray's VFX: VHS / Tape (`RayVHS`)

**Purpose.** Videotape degradation modeled as a signal chain in YUV space, plus a VCR or camcorder on-screen display (OSD) that is burned into the picture rather than laid over it. The stages follow the path a tape signal takes: soft luma with deck sharpening halos, low-bandwidth colour that smears and lags behind the picture, cross-colour rainbows around fine detail, smooth line-level time-base wobble with tracking bands and a bent top edge, the torn head-switching band at the bottom, streaky tape noise, and dropouts.

**OSD.** The status readout (PLAY / REC / PAUSE / STOP) and the date / time stamp can be shown together, each in its own corner, in white, yellow or green. Lines that share a corner stack, status above stamp. The text is composited before the tape stages, so it goes through the same luma softening, colour bleed and lag, line wobble, noise and dropouts as the picture, the way a camcorder's burned-in stamp behaves. On top of that the character generator adds a dark outline with a smeared drop shadow, a little line jitter of its own and a faint shimmer along the glyph edges. The margins keep it inside the safe area and clear of the head-switch band.

**Fade.** `effect_fade` alpha-blends the result with the source: `0` is the full effect, `1` is the untouched picture. At any fade the OSD keeps its text, with its analog imperfections fading out along with everything else.

Every effect is sized relative to the picture, not in pixels, so a preset looks the same on a small frame and on a 4K one. A fixed `seed` always gives the same tape, and changing one slider never reshuffles another effect's noise.

Each slider defaults to `-1.0` (meaning "use the preset value") and `0..1` overrides that one effect. Setting every slider to `0` leaves only the preset's softness, colour and levels; the picture is otherwise clean.

**Presets.** Each preset is a tape and deck: it sets the softness, deck sharpening halos, colour handling, levels and the starting value of every slider.

| Preset | What it models |
|--------|----------------|
| Pristine SP | A well-kept standard-play tape on a good deck: soft, slightly lifted blacks, colour smeared a little, hardly any faults. |
| S-VHS | Higher-resolution luma and separated colour (no rainbow artifacts), very stable. |
| Worn EP | A rewatched extended-play tape (the default): soft, noisy, colour lagging, tracking wander, dropouts and a visible head-switch tear. |
| Gen-3 dub | A copy of a copy: very soft, washed-out and hue-drifted colour, strong halos, heavy noise and dropouts. |
| VHS-C camcorder | A compact-cassette camcorder: punchy saturated colour, crunchy highlights, strong sharpening, little tape damage. |
| Hi8 | 8 mm tape: sharper than VHS with good colour and few faults. |
| Rental tape | A shop rental played to death: many dropouts, tracking trouble and a bent top edge. |
| Off-air LP | A long-play recording from broadcast TV: soft, with strong cross-colour rainbows and colour lag. |
| Chewed tape | Damaged tape: tracking bands full of snow, a badly torn bottom edge, constant dropouts. |
| Custom | A neutral middle setting to start your own look from. |

**Category:** `👑 Ray/✨ VFX`

| Pin | Type | Notes |
|-----|------|-------|
| **Input** `image` | IMAGE | Source frame(s). |
| **Control** `preset` | enum | Tape and deck (baseline for the sliders below). |
| **Control** `chroma_blur` | float ±1 | Colour bandwidth loss: how far chroma smears and lags the picture. |
| **Control** `head_switch` | float ±1 | The skewed, noisy band at the bottom of the frame. |
| **Control** `tracking_jitter` | float ±1 | Line wobble and tracking bands (with snow). |
| **Control** `dropout_rate` | float ±1 | Dropout streaks, short bright or dark lines with a soft tail. |
| **Control** `hiss` | float ±1 | Tape noise in brightness and colour, streaky along the scanline. |
| **Control** `yc_separation` | float ±1 | Cross-colour rainbows and dot crawl around fine detail. |
| **Control** `effect_fade` | float 0..1 | Blend back toward the source. `0` (default) is the full effect, `1` the untouched picture. |
| **Control** `osd_status` | enum | `Off` / `▶ PLAY` / `● REC` / `❚❚ PAUSE` / `■ STOP`, drawn in a built-in VCR pixel font. |
| **Control** `osd_status_corner` | enum | `TL` / `TR` / `BL` / `BR` (default `TL`). |
| **Control** `osd_stamp` | enum | `Off` / `Date` / `Time` / `Date+Time`; shows together with the status line. |
| **Control** `osd_stamp_corner` | enum | `TL` / `TR` / `BL` / `BR` (default `BR`). Shares a corner with the status line by stacking. |
| **Control** `osd_date` | string | `YYYY MM DD`; blank stamps today's date. |
| **Control** `osd_color` | enum | `White` / `Yellow` / `Green`. |
| **Control** `seed` | int | `-1` for random; any `≥0` value is reproducible. |
| **Output** `image` | IMAGE | Tape-degraded image with the OSD burned in. |

---

## 🔧 Ray's Tools: TXT Folder (`RayTextFolder`)

**Category:** `👑 Ray/🔧 Tools`

Read UTF-8 .txt files from one folder, alphabetically by filename; subfolders
are excluded. Each non-empty file is one prompt, including its paragraphs
and whitespace. A UTF-8 BOM is removed. Files are re-read on every execution.

| Control / output | Behavior |
|---|---|
| `directory` | Folder containing prompt files |
| `start_index` | Zero-based starting file in alphabetical order |
| `limit` | Maximum files examined; -1 means all remaining files |
| `output_prefix` | Save Image prefix; the source filename stem is appended |
| `prompt` | List of complete, unchanged prompts |
| `filename_prefix` | Equally sized list of matching output prefixes |

Empty files are skipped, but still count toward start_index and limit.
No usable prompts produces an actionable error instead of a blank generation.
Read/decode failures stop execution before any prompt list is emitted.

Connect `prompt` to RayKrea2Sampler's text input and `filename_prefix` to
Save Image's filename_prefix input. Connect the sampler image to Save Image.
ComfyUI maps the paired lists automatically; no extra loop is needed.
Keep the sampler batch size at 1 for one image per file. Save Image saves
each file under exactly that name (it adds `-2`, `-3`, … only if the name is
taken). Use limit 3 for a small test, then -1 for the folder.

## 💬 Ray's LLM: Folder Captioner (`RayVLMFolder`)

**Category:** `👑 Ray/💬 LLM`

Connect a full vision-language `CLIP` (for example Qwen3-VL from a
`CLIPLoader` with type `qwen_image`, the same setup as Fast Qwen3-VL) and caption
each selected image independently on GPU. The node
uses native `CLIP.tokenize/generate/decode` with the image template enabled,
and preserves the supplied instruction and decoded answer. It does not write
sidecars, resize source images, or add a conversation history.

| Control | Behavior |
|---|---|
| `clip` (input) | Full generative VLM CLIP, e.g. Qwen3-VL from `CLIPLoader`; an ordinary text-only CLIP is unsuitable |
| `folder`, `recurse_subfolders` | Source folder and optional recursive scan |
| `start_index`, `limit` | Zero-based alphabetical relative-path range; -1 means all remaining files |
| `user_prompt` | Multiline instruction used independently for each image |
| `max_length` | Maximum generated tokens per image |
| `temperature` | Sampling temperature; 0 selects greedy decoding |
| `top_k`, `top_p`, `min_p` | Native token sampling filters |
| `repetition_penalty` | Native repetition penalty; 1 is neutral |
| `seed` | -1 selects a random seed per image; a fixed seed is reused per image for repeatability |
| `thinking` | Requests model-supported thinking; any decoded reasoning is retained in text |

Outputs `text`, `image`, and `image_path` are aligned lists. Each image is
a separate RGB tensor with EXIF orientation applied, so mixed sizes work.
Connect an output to a display, save, or downstream processing node to run.

Supported formats: JPEG, PNG, WebP, BMP, TIFF, GIF. Animated/multipage files use
their first frame. HEIC is not included. Folder contents are rescanned each run.
Unreadable files, absent vision tokens, CPU fallback, and empty answers stop the
run with an error rather than emitting misleading captions. No files are modified.

All outputs become available after the selected range finishes. Full-resolution
images accumulate in RAM; use a small `limit` and advance `start_index` for
large folders. ComfyUI manages model offloading; CPU staging is allowed, but
the inference device must be a GPU. The checkpoint must fit the available resources.


## 🔧 Ray's Tools: Save Image (`RaySaveImage`)

**Category:** `👑 Ray/🔧 Tools`. Output node; no output sockets.

| Input | Purpose |
|---|---|
| `image_1` | Required IMAGE batch. |
| `image_2` | Optional IMAGE batch; enables comparison. |
| `save_image` | `none`, `1` (default), `2`, or `both`; presented as compact segmented buttons. |
| `directory` | Blank for ComfyUI output (shown as `/output`), relative to output, or an absolute destination. The folder button opens your system's folder dialog; the ▾ in the field recalls the last three save folders. |
| `filename_prefix` | The file's name without the extension, built from text and tokens such as `{date}` and `{counter}`. See Filename builder below. |
| `save_without_metadata` | Right-click toggle; removes prompt/workflow PNG text metadata. Defaults to false. |

Saving happens on execution. Selecting 2 without image_2 gives an actionable
error; Both with only image_1 saves that input. Preview-only mode writes only to
ComfyUI's temporary folder. All saved images retain resolution and alpha. The
comparison fits each image without stretching; a singleton repeats across the
other batch, and unequal non-singleton batches show unpaired trailing images.
Drag the divider or focus it and use Left/Right/Home/End. Folder history holds
three successful destinations per browser, independently of workflow values.

### Filename builder

Files are saved as exactly **`<filename_prefix>.png`**: the prefix is the whole name. Click the **{ }** button next to the filename prefix for a small panel (drag its title bar to move it) where chips insert tokens at the cursor, a live preview shows the result, and a widget picker lists every widget of every node in the workflow. You can also type tokens yourself. A new Save Image starts with `Ray_{date}_{counter}`, which saves `Ray_2026-10-16_0001.png`, `Ray_2026-10-16_0002.png`, and so on.

| Token | Gives | Example |
|-------|-------|---------|
| `{date}` | ISO date | `2026-10-16` |
| `{time}` | Time, with hyphens because filenames cannot hold colons | `14-32-05` |
| `{datetime}` | Both, ISO style | `2026-10-16T14-32-05` |
| `{timestamp}` | Seconds since 1970 | `1792162325` |
| `{counter}` or `{counter:N}` | The next unused number in the folder, padded to N digits (default 4, up to 12). Counts files that share the rest of the name. Use it once | `0007` |
| `{index}` or `{index:N}` | Position of the image in its batch, from 1 | `3` |
| `{input}` | Which image input the file came from, 1 or 2 | `2` |
| `{hash}` or `{hash:N}` | N random hex characters (default 8, from 4 to 32), so two names can never clash | `a1b2c3d4` |
| `{widget:ID.NAME}` | The value of widget NAME on the node with that id. Add `\|N` to keep at most N characters (default 60) | `{widget:12.seed}` → `42` |

**Made safe automatically.** Characters Windows, macOS and Linux reject (`< > : " / \ | ? *` and control characters) and spaces become `_`, so a prefix can never choose a folder. Widget values are also trimmed, cut to length and have repeated underscores collapsed, and braces in them are dropped so a value such as `{hash}` cannot be mistaken for a token. Leading and trailing dots and spaces are removed, Windows device names such as `CON` and `NUL` get a `_` in front, and the name is cut at 180 characters. A blank prefix uses the default.

**Nothing is overwritten.** Files are created exclusively. With `{counter}` the number moves on to the next free one (even when two runs save at once); without it a taken name gets `-2`, `-3`, and so on (`shot.png`, `shot-2.png`). A prefix without tokens therefore always saves under that name, adding a suffix only when the name exists.

**Widget values** are read from the workflow at the moment you queue it, so they are the values on screen, including widgets fed by a link, hidden widgets such as a Control's value, and values changed since the last run. The saved workflow keeps the template you wrote. When the server is used without the web page (an API call), a `{widget:...}` token is read from the queued graph, and skipped if that input comes from another node's output. A misspelt token is reported with the list of valid ones instead of saving a wrongly named file.

Workflows saved with the old prefix model (for example a plain `Ray`) now save `Ray.png`, `Ray-2.png`, … instead of `Ray_1_0001_<id>.png`; add `{counter}` or `{index}` for numbered names.

Right-click **Ray's Tools: Save Image → Open image location in Explorer** to
open the folder from its latest successful save. The option becomes available
after a save in the current session and stays tied to that folder if you edit
the next destination or run preview-only. Explorer opens on the Windows ComfyUI host.
