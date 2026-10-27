# Inputs, controls, and outputs

This reference describes the registered nodes, their controls, defaults, and connections.
Some controls appear only in the relevant mode. Saved editor/gallery state and compatibility
inputs are listed for workflows using those fields; use the visible panel to edit their contents.
See [the node guide](NODES.md) for examples and each node's default view.

<a id="RayButtonDeck"></a>

## 🎛️ Ray's Analog: Button Deck (`RayButtonDeck`)

A deck of analog push buttons that replaces a dropdown. Enter one value per line; each line becomes a button and the pressed button's text is the output.

Size the node however you like: the buttons take the grid that makes them biggest, a row in a wide node, 2 x 2 in a square one, a column in a tall one. Use the pencil next to Entries (or right-click) to change the list. Right-click also picks the button style, turns on Compact mode (the faceplate alone), mutes the sound, and edits the Dymo label. The pressed button stays lit and the others stay unlit.

| Input / control | Type | Default / choices / limits | Description |
| --- | --- | --- | --- |
| `entries` | STRING | Default: "Option A\nOption B\nOption C" | One value per line. Each line becomes a button. Blank lines and repeated lines are ignored. |
| `selected` | STRING | Default: "" | The pressed button's text (driven by the deck). If it isn't in the list, the first entry is used. |

| Output | Type | Description |
| --- | --- | --- |
| `value` | STRING | The text of the pressed button. |

<a id="RayCRT"></a>

## ✨ Ray's VFX: CRT (`RayCRT`)

Image-space CRT display effect. Simulates phosphor mask (aperture / shadow / slot), scanline beam, halation + bloom, NTSC chroma bleed, barrel curvature, vignette, and reflection gloss.

Presets cover classic Trinitron / PVM monitors plus consoles (Super Famicom, PS1, PS2, DS, GBA, PSP…). Tweak intensity, scanline_strength, and mask_strength to scale the effect over the preset baseline.

| Input / control | Type | Default / choices / limits | Description |
| --- | --- | --- | --- |
| `image` | IMAGE | Connection | Source frame(s). BHWC accepted. |
| `preset` | COMBO | Default: "trinitron_aperture"; Choices: trinitron_aperture, pvm_shadow, consumer_slot, composite_ntsc, arcade_royale, lottes_fast, mattias_stylised, royale_kurozumi, guest_advanced, cyberlab_pixels, newpixie_framed, gtu_composite, hyllian_glow, super_famicom, megadrive, ps1, ps2, nintendo_ds, gameboy_advance, psp | SOTA-inspired CRT preset — monitor or console model. |
| `curvature` | BOOLEAN | Default: true | Barrel-warp the image (out-of-bounds becomes bezel). |
| `intensity` | FLOAT | Default: 1.0; min: 0.0; max: 1.0; step: 0.01 | Master mix vs untouched input. |
| `scanline_strength` | FLOAT | Default: 1.0; min: 0.0; max: 2.0; step: 0.05 | Scales preset scan-line depth. |
| `mask_strength` | FLOAT | Default: 1.0; min: 0.0; max: 2.0; step: 0.05 | Scales preset phosphor-mask depth. |

| Output | Type | Description |
| --- | --- | --- |
| `image` | IMAGE | Filtered image with the CRT effect applied. |

<a id="RayFaderBank"></a>

## 🎛️ Ray's Analog: Fader Bank (`RayFaderBank`)

A bank of analog faders: 2 to 10 in a row, and up to 4 rows. Each fader is a vertical slider that outputs a float from 0 to 1.

Set `faders` to the number in a row and `rows` to the number of rows (6 faders and 2 rows make 12); the node shows one output per fader, numbered row by row, and hides the rest. `values` carries every active fader as a list, in order, for nodes that take a list. Drag a fader, click its track, use the arrow keys, or turn on Mouse wheel control in the right-click menu and scroll over a fader. Right-click also picks the style, mutes the sound and edits the Dymo label.

| Input / control | Type | Default / choices / limits | Description |
| --- | --- | --- | --- |
| `faders` | INT | Default: 4; min: 2; max: 10; step: 1 | How many faders in a row (2 to 10). Only the active faders' outputs are shown. |
| `fader_1` | FLOAT | Default: 0.5; min: 0.0; max: 1.0; step: 0.001 | Fader 1 position, 0 to 1 (driven by the bank). |
| `fader_2` | FLOAT | Default: 0.5; min: 0.0; max: 1.0; step: 0.001 | Fader 2 position, 0 to 1 (driven by the bank). |
| `fader_3` | FLOAT | Default: 0.5; min: 0.0; max: 1.0; step: 0.001 | Fader 3 position, 0 to 1 (driven by the bank). |
| `fader_4` | FLOAT | Default: 0.5; min: 0.0; max: 1.0; step: 0.001 | Fader 4 position, 0 to 1 (driven by the bank). |
| `fader_5` | FLOAT | Default: 0.5; min: 0.0; max: 1.0; step: 0.001 | Fader 5 position, 0 to 1 (driven by the bank). |
| `fader_6` | FLOAT | Default: 0.5; min: 0.0; max: 1.0; step: 0.001 | Fader 6 position, 0 to 1 (driven by the bank). |
| `fader_7` | FLOAT | Default: 0.5; min: 0.0; max: 1.0; step: 0.001 | Fader 7 position, 0 to 1 (driven by the bank). |
| `fader_8` | FLOAT | Default: 0.5; min: 0.0; max: 1.0; step: 0.001 | Fader 8 position, 0 to 1 (driven by the bank). |
| `fader_9` | FLOAT | Default: 0.5; min: 0.0; max: 1.0; step: 0.001 | Fader 9 position, 0 to 1 (driven by the bank). |
| `fader_10` | FLOAT | Default: 0.5; min: 0.0; max: 1.0; step: 0.001 | Fader 10 position, 0 to 1 (driven by the bank). |
| `rows` | INT | Default: 1; min: 1; max: 4; step: 1 | How many rows of faders (1 to 4); each row has `faders` faders. |
| `fader_11` | FLOAT | Default: 0.5; min: 0.0; max: 1.0; step: 0.001 | Fader 11 position, 0 to 1 (driven by the bank). |
| `fader_12` | FLOAT | Default: 0.5; min: 0.0; max: 1.0; step: 0.001 | Fader 12 position, 0 to 1 (driven by the bank). |
| `fader_13` | FLOAT | Default: 0.5; min: 0.0; max: 1.0; step: 0.001 | Fader 13 position, 0 to 1 (driven by the bank). |
| `fader_14` | FLOAT | Default: 0.5; min: 0.0; max: 1.0; step: 0.001 | Fader 14 position, 0 to 1 (driven by the bank). |
| `fader_15` | FLOAT | Default: 0.5; min: 0.0; max: 1.0; step: 0.001 | Fader 15 position, 0 to 1 (driven by the bank). |
| `fader_16` | FLOAT | Default: 0.5; min: 0.0; max: 1.0; step: 0.001 | Fader 16 position, 0 to 1 (driven by the bank). |
| `fader_17` | FLOAT | Default: 0.5; min: 0.0; max: 1.0; step: 0.001 | Fader 17 position, 0 to 1 (driven by the bank). |
| `fader_18` | FLOAT | Default: 0.5; min: 0.0; max: 1.0; step: 0.001 | Fader 18 position, 0 to 1 (driven by the bank). |
| `fader_19` | FLOAT | Default: 0.5; min: 0.0; max: 1.0; step: 0.001 | Fader 19 position, 0 to 1 (driven by the bank). |
| `fader_20` | FLOAT | Default: 0.5; min: 0.0; max: 1.0; step: 0.001 | Fader 20 position, 0 to 1 (driven by the bank). |
| `fader_21` | FLOAT | Default: 0.5; min: 0.0; max: 1.0; step: 0.001 | Fader 21 position, 0 to 1 (driven by the bank). |
| `fader_22` | FLOAT | Default: 0.5; min: 0.0; max: 1.0; step: 0.001 | Fader 22 position, 0 to 1 (driven by the bank). |
| `fader_23` | FLOAT | Default: 0.5; min: 0.0; max: 1.0; step: 0.001 | Fader 23 position, 0 to 1 (driven by the bank). |
| `fader_24` | FLOAT | Default: 0.5; min: 0.0; max: 1.0; step: 0.001 | Fader 24 position, 0 to 1 (driven by the bank). |
| `fader_25` | FLOAT | Default: 0.5; min: 0.0; max: 1.0; step: 0.001 | Fader 25 position, 0 to 1 (driven by the bank). |
| `fader_26` | FLOAT | Default: 0.5; min: 0.0; max: 1.0; step: 0.001 | Fader 26 position, 0 to 1 (driven by the bank). |
| `fader_27` | FLOAT | Default: 0.5; min: 0.0; max: 1.0; step: 0.001 | Fader 27 position, 0 to 1 (driven by the bank). |
| `fader_28` | FLOAT | Default: 0.5; min: 0.0; max: 1.0; step: 0.001 | Fader 28 position, 0 to 1 (driven by the bank). |
| `fader_29` | FLOAT | Default: 0.5; min: 0.0; max: 1.0; step: 0.001 | Fader 29 position, 0 to 1 (driven by the bank). |
| `fader_30` | FLOAT | Default: 0.5; min: 0.0; max: 1.0; step: 0.001 | Fader 30 position, 0 to 1 (driven by the bank). |
| `fader_31` | FLOAT | Default: 0.5; min: 0.0; max: 1.0; step: 0.001 | Fader 31 position, 0 to 1 (driven by the bank). |
| `fader_32` | FLOAT | Default: 0.5; min: 0.0; max: 1.0; step: 0.001 | Fader 32 position, 0 to 1 (driven by the bank). |
| `fader_33` | FLOAT | Default: 0.5; min: 0.0; max: 1.0; step: 0.001 | Fader 33 position, 0 to 1 (driven by the bank). |
| `fader_34` | FLOAT | Default: 0.5; min: 0.0; max: 1.0; step: 0.001 | Fader 34 position, 0 to 1 (driven by the bank). |
| `fader_35` | FLOAT | Default: 0.5; min: 0.0; max: 1.0; step: 0.001 | Fader 35 position, 0 to 1 (driven by the bank). |
| `fader_36` | FLOAT | Default: 0.5; min: 0.0; max: 1.0; step: 0.001 | Fader 36 position, 0 to 1 (driven by the bank). |
| `fader_37` | FLOAT | Default: 0.5; min: 0.0; max: 1.0; step: 0.001 | Fader 37 position, 0 to 1 (driven by the bank). |
| `fader_38` | FLOAT | Default: 0.5; min: 0.0; max: 1.0; step: 0.001 | Fader 38 position, 0 to 1 (driven by the bank). |
| `fader_39` | FLOAT | Default: 0.5; min: 0.0; max: 1.0; step: 0.001 | Fader 39 position, 0 to 1 (driven by the bank). |
| `fader_40` | FLOAT | Default: 0.5; min: 0.0; max: 1.0; step: 0.001 | Fader 40 position, 0 to 1 (driven by the bank). |

| Output | Type | Description |
| --- | --- | --- |
| `values` | FLOAT list | Every active fader, in order, as a list of floats from 0 to 1. |
| `fader_1` | FLOAT | Fader 1, 0 to 1. |
| `fader_2` | FLOAT | Fader 2, 0 to 1. |
| `fader_3` | FLOAT | Fader 3, 0 to 1. |
| `fader_4` | FLOAT | Fader 4, 0 to 1. |
| `fader_5` | FLOAT | Fader 5, 0 to 1. |
| `fader_6` | FLOAT | Fader 6, 0 to 1. |
| `fader_7` | FLOAT | Fader 7, 0 to 1. |
| `fader_8` | FLOAT | Fader 8, 0 to 1. |
| `fader_9` | FLOAT | Fader 9, 0 to 1. |
| `fader_10` | FLOAT | Fader 10, 0 to 1. |
| `fader_11` | FLOAT | Fader 11, 0 to 1. |
| `fader_12` | FLOAT | Fader 12, 0 to 1. |
| `fader_13` | FLOAT | Fader 13, 0 to 1. |
| `fader_14` | FLOAT | Fader 14, 0 to 1. |
| `fader_15` | FLOAT | Fader 15, 0 to 1. |
| `fader_16` | FLOAT | Fader 16, 0 to 1. |
| `fader_17` | FLOAT | Fader 17, 0 to 1. |
| `fader_18` | FLOAT | Fader 18, 0 to 1. |
| `fader_19` | FLOAT | Fader 19, 0 to 1. |
| `fader_20` | FLOAT | Fader 20, 0 to 1. |
| `fader_21` | FLOAT | Fader 21, 0 to 1. |
| `fader_22` | FLOAT | Fader 22, 0 to 1. |
| `fader_23` | FLOAT | Fader 23, 0 to 1. |
| `fader_24` | FLOAT | Fader 24, 0 to 1. |
| `fader_25` | FLOAT | Fader 25, 0 to 1. |
| `fader_26` | FLOAT | Fader 26, 0 to 1. |
| `fader_27` | FLOAT | Fader 27, 0 to 1. |
| `fader_28` | FLOAT | Fader 28, 0 to 1. |
| `fader_29` | FLOAT | Fader 29, 0 to 1. |
| `fader_30` | FLOAT | Fader 30, 0 to 1. |
| `fader_31` | FLOAT | Fader 31, 0 to 1. |
| `fader_32` | FLOAT | Fader 32, 0 to 1. |
| `fader_33` | FLOAT | Fader 33, 0 to 1. |
| `fader_34` | FLOAT | Fader 34, 0 to 1. |
| `fader_35` | FLOAT | Fader 35, 0 to 1. |
| `fader_36` | FLOAT | Fader 36, 0 to 1. |
| `fader_37` | FLOAT | Fader 37, 0 to 1. |
| `fader_38` | FLOAT | Fader 38, 0 to 1. |
| `fader_39` | FLOAT | Fader 39, 0 to 1. |
| `fader_40` | FLOAT | Fader 40, 0 to 1. |

<a id="RayFastQwen3VL"></a>

## 💬 Ray's LLM: Fast Qwen3-VL Infer (`RayFastQwen3VL`)

Generate text with ComfyUI-native Qwen models. Qwen3-VL supports optional images and Ray's fast decode path; text-only Qwen models ignore image input and use their native ComfyUI generator.

| Input / control | Type | Default / choices / limits | Description |
| --- | --- | --- | --- |
| `clip` | CLIP | Connection | ComfyUI-native generative Qwen text encoder: Qwen3, Qwen3.5, Qwen3-VL, or another compatible Qwen wrapper. |
| `prompt` | STRING | Default: "Describe this image in detail." | Prompt for the Qwen model. The connected tokenizer owns the appropriate Qwen chat template. |
| `max_tokens` | INT | Default: 256; min: 1; max: 8192 | Maximum generated tokens. Reaching the cap truncates the answer. |
| `temperature` | FLOAT | Default: 0.0; min: 0.0; max: 2.0; step: 0.01 | Sampling randomness. 0 is greedy decoding; higher values vary the wording. |
| `top_p` | FLOAT | Default: 0.9; min: 0.01; max: 1.0; step: 0.01 | Nucleus sampling threshold. Ignored by greedy decoding. |
| `top_k` | INT | Default: 40; min: 0; max: 1000 | Top-k sampling limit. 0 disables it. Ignored by greedy decoding. |
| `seed` | INT | Default: 42; min: 0; max: 9223372036854775807 | Sampling seed when temperature is above 0. |
| `image` | IMAGE | Connection | Optional image or image batch for Qwen3-VL. If the connected Qwen model is text-only, this input is ignored. |
| `mode` | COMBO | Default: "fast"; Choices: fast, native | fast: use Ray's optimized path when the model is a compatible Qwen3-VL; otherwise automatically use native ComfyUI generation. native: always use the model's stock ComfyUI generator. |
| `sync_interval` | INT | Default: 8; min: 1; max: 32 | Qwen3-VL fast mode only: check stop tokens every N steps. May compute up to N-1 extra tokens which are discarded. |
| `thinking` | BOOLEAN | Default: false | Pass the model's thinking-mode request through its tokenizer. Effect depends on the connected Qwen tokenizer/checkpoint. |
| `repetition_penalty` | FLOAT | Default: 1.0; min: 1.0; max: 2.0; step: 0.01 | Scale down scores of tokens already generated. 1 disables it. |
| `presence_penalty` | FLOAT | Default: 0.0; min: 0.0; max: 2.0; step: 0.1 | Discourage reusing generated tokens. Set 0 to disable. |
| `repeat_guard` | BOOLEAN | Default: true | Qwen3-VL fast mode only: stop if an identical 8–256-token phrase repeats three times. |
| `generation_preset` | COMBO | Default: "custom"; Choices: custom, anti_loop | custom uses the penalty controls (neutral defaults). anti_loop explicitly selects repetition 1.0 and presence 1.5; changes model behavior. |

| Output | Type | Description |
| --- | --- | --- |
| `text` | STRING | Decoded answer from the connected Qwen model. |

<a id="RayFilmStock"></a>

## ✨ Ray's VFX: Film Stock (`RayFilmStock`)

Analytical film-stock emulation. Applies a per-stock tonal curve + color response (Kodak Portra 400, Ilford HP5+, Cinestill, Fujifilm Velvia, and more), plus optional grain and halation.

Point `assets_folder` at a directory of `.cube` / `.3dl` LUTs and `.xmp` develop-setting files to layer a real graded look on top of the analytical baseline. `intensity` scales the whole effect; `expose_stops` shifts exposure before the curve.

| Input / control | Type | Default / choices / limits | Description |
| --- | --- | --- | --- |
| `image` | IMAGE | Connection | Source image batch to process with the selected film stock, exposure, grain, and halation settings. |
| `preset` | COMBO | Default: "Kodak Portra 400"; Choices: Kodak Portra 400, Kodak Ektar 100, Fuji Pro 400H, Fuji Superia 400, CineStill 800T, CineStill 50D, Kodak Vision3 500T, Fuji Eterna 500T, Kodak Tri-X 400, Ilford HP5+, Ilford Delta 3200, Kodak T-Max 100, Fuji Velvia 50, Fuji Provia 100F, Kodak Ektachrome E100, Custom, None | Film-stock analytical curve preset. |
| `intensity` | FLOAT | Default: 1.0; min: 0.0; max: 1.0; step: 0.01 | Master mix vs untouched input. |
| `grain_amount` | FLOAT | Default: 1.0; min: 0.0; max: 4.0; step: 0.05 | Grain strength (0 = off). |
| `halation_amount` | FLOAT | Default: 1.0; min: 0.0; max: 4.0; step: 0.05 | Halation bloom strength (0 = off). |
| `expose_stops` | FLOAT | Default: 0.0; min: -4.0; max: 4.0; step: 0.05 | Exposure compensation in stops. |
| `seed` | INT | Default: -1; min: -1; max: 2147483647 | -1 for random; any >=0 value is reproducible. |
| `assets_folder` | STRING | Default: "" | Optional asset folder — LUTs and XMP develop presets are picked up recursively. |
| `asset_file` | COMBO | Default: "(none)"; Choices: (none) | LUT / XMP file to overlay on top of the analytical curve. |

| Output | Type | Description |
| --- | --- | --- |
| `image` | IMAGE | Film-stock emulated image. |

<a id="RayFolders"></a>

## 🔧 Ray's Tools: Folders (`RayFolders`)

Browse local images, videos and audio. Select files to emit native media lists, matching prompts and paths. The gallery refreshes after the workflow finishes, including with no outputs connected.

| Input / control | Type | Default / choices / limits | Description |
| --- | --- | --- | --- |
| `folder` | STRING | Default: "" | Browse or connect an absolute folder path. |
| `name_filter` | STRING | Default: "" | Fuzzy filename and prompt search; all words must match. |
| `selected_files` | STRING | Default: "{}" | Media chosen in the gallery, retained with the workflow. Click to select one file; Ctrl/Cmd-click toggles additional selections. |
| `settings_json` | STRING | Default: "{}" | Gallery sorting, media types, recursion, color/NSFW filters, and prompt options. Change these through the top-right settings cog. |

| Output | Type | Description |
| --- | --- | --- |
| `images` | IMAGE list | Selected images at original dimensions. |
| `videos` | VIDEO list | Selected native ComfyUI videos. |
| `audio` | AUDIO list | Selected audio at original sample rates. |
| `prompt` | STRING list | One prompt per selected file; blank when absent. |
| `paths` | STRING list | Selected paths in gallery order, or the folder path when nothing is selected. |

<a id="RayKnob"></a>

## 🎛️ Ray's Analog: Control (Knob / Slider) (`RayKnob`)

Analog-style float control: a rotary knob or a slider, themed after studio hardware. Drag turns the knob or moves the slider cap; outputs both an INT (quantized by `clamp`) and a raw FLOAT so it plugs into either side without a converter.

Right-click for the 31 shared hardware styles, Mute sound (knobs, sliders and switches make hardware sounds), Compact mode (the faceplate alone: no title bar, pins, setup panel or node background; drag it by its frame, links meet it under the face), and Edit label. The Dymo tape above the face is double-click editable and is saved with the workflow.

| Input / control | Type | Default / choices / limits | Description |
| --- | --- | --- | --- |
| `min_value` | FLOAT | Default: -100.0; min: -1000000000.0; max: 1000000000.0; step: 0.1 | Lowest allowed output value. Negative limits apply only when Allow negative is enabled. |
| `max_value` | FLOAT | Default: 100.0; min: -1000000000.0; max: 1000000000.0; step: 0.1 | Highest allowed output value. A value below the effective minimum collapses the range to that minimum. |
| `clamp` | FLOAT | Default: 0.0; min: 0.0; max: 1024.0; step: 0.1 | Quantization step for the INT output. 0 truncates. |
| `allow_negative` | BOOLEAN | Default: true | Whether min_value may go below 0. |
| `knob_value` | FLOAT | Default: 0.0; min: -1000000000000.0; max: 1000000000000.0; step: 0.0001 | Current knob value (driven by the widget). |

| Output | Type | Description |
| --- | --- | --- |
| `int` | INT | Knob value quantized to `clamp` steps. |
| `float` | FLOAT | Raw knob value clamped to [min_value, max_value]. |

<a id="RayLoraBake"></a>

## 🧰 Ray's Model Tools: LoRA Bake (`RayLoraBake`)

Bake a ComfyUI-supported LoRA into a new model, including convolution and adapter formats supported by ComfyUI. Input branches remain unchanged.

| Input / control | Type | Default / choices / limits | Description |
| --- | --- | --- | --- |
| `lora_name` | STRING | Default: "" | Choose a registered LoRA file. The folder dropdown searches full paths across all registered LoRA subfolders. |
| `strength_model` | FLOAT | Default: 1.0; min: -20.0; max: 20.0; step: 0.01 | Multiplier for the LoRA's diffusion-model changes. Zero leaves those weights unchanged; negative values reverse the adapter's direction. |
| `strength_clip` | FLOAT | Default: 1.0; min: -20.0; max: 20.0; step: 0.01 | Multiplier for the LoRA's supported text-encoder changes. Zero leaves the text encoder unchanged; negative values reverse those changes. |
| `weight_format` | COMBO | Default: "preserve"; Choices: preserve, fp32, fp16, bf16, fp8_e4m3fn, fp8_e4m3fn_scaled, fp8_e5m2, int8_tensor, int8_row, int8_convrot | Storage precision or quantization for the result. Auto/Preserve keeps the source representation where supported. Converting to higher precision cannot recover information already lost. |
| `model` | MODEL | Connection | Connected model to process, including its active patches and LoRAs. Takes precedence over a model-data handle or file source. |
| `clip` | CLIP | Connection | Optional text encoder to include with the connected model. It must match the model architecture and selected component scope. |
| `vae` | VAE | Connection | Optional VAE to preserve with the connected model when the operation supports complete checkpoints. |
| `model_data` | RAY_MODEL_DATA | Connection | File or in-memory model result from another Model Tools node. Supports data-only processing without initializing inference components. |
| `path` | STRING | Default: "" | Existing source file or supported sharded model folder on the ComfyUI server. A connected live model or model-data handle takes precedence where available. |
| `lora_path` | STRING | Default: "" | Optional explicit LoRA file on the ComfyUI server, including sources outside the registered LoRA folders. |

| Output | Type | Description |
| --- | --- | --- |
| `model` | MODEL | Native ComfyUI diffusion model. Inference components are initialized when this output is used; data-only workflows can use model_data instead. |
| `clip` | CLIP | Native text encoder when available in the source and enabled by the selected loading/component options; otherwise absent. |
| `vae` | VAE | Native VAE when available in the source and enabled by the selected loading/component options; otherwise absent. |
| `model_data` | RAY_MODEL_DATA | Model Tools data handle for a source file or in-memory result. Connect it directly to compatible merge, conversion, inspection, or save nodes without an extra inference load. |
| `metadata` | RAY_MODEL_METADATA | Structured metadata for the source or result, including operation information where applicable. |
| `report` | STRING | Readable inspection or operation report, including compatibility, format, processing, and saved-result information relevant to this operation. |

<a id="RayLoraExtract"></a>

## 🧰 Ray's Model Tools: LoRA Extract (`RayLoraExtract`)

Extract a low-rank approximation of finetuned minus base. Supports Linear and convolution weights. Alpha=0 uses each layer's actual rank. Error is the SVD truncation error before output rounding.

| Input / control | Type | Default / choices / limits | Description |
| --- | --- | --- | --- |
| `filename_prefix` | STRING | Default: "model_tools/Ray_Extracted_LoRA" | Name or prefix for automatic output under ComfyUI's output folder. An explicit Output file takes precedence when available. |
| `rank` | INT | Default: 16; min: 1; max: 4096 | Maximum low-rank dimension retained per extracted LoRA tensor. Higher ranks preserve more of the difference and produce larger adapters. |
| `alpha` | FLOAT | Default: 0.0; min: 0.0; max: 4096.0; step: 1.0 | LoRA alpha written into the adapter scaling metadata. Zero uses the selected rank. |
| `components` | COMBO | Default: "diffusion"; Choices: diffusion, diffusion_and_text, text_encoder | Choose diffusion weights, diffusion plus text encoders, text encoders only, or all supported components. Unselected components follow the operation's preservation rules. |
| `weight_format` | COMBO | Default: "bf16"; Choices: bf16, fp16, fp32 | Storage precision or quantization for the result. Auto/Preserve keeps the source representation where supported. Converting to higher precision cannot recover information already lost. |
| `include_embeddings` | BOOLEAN | Default: false | Include supported embedding changes in the extracted adapter in addition to the selected low-rank weight differences. |
| `finetuned_model` | MODEL | Connection | Fine-tuned live model from which to extract changes relative to the base model. Connected effective weights take precedence over file/data sources. |
| `base_model` | MODEL | Connection | Compatible original live model used as the reference for extraction. Use the actual training base for meaningful differences. |
| `finetuned_clip` | CLIP | Connection | Fine-tuned text encoder for extraction when the selected component scope includes text-encoder weights. |
| `base_clip` | CLIP | Connection | Compatible base text encoder paired with the fine-tuned text encoder for extraction. |
| `finetuned_data` | RAY_MODEL_DATA | Connection | Model-data handle supplying fine-tuned weights when no fine-tuned live model is connected. |
| `base_data` | RAY_MODEL_DATA | Connection | Model-data handle supplying base weights when no base live model is connected. |
| `finetuned_path` | STRING | Default: "" | Fine-tuned checkpoint file used when its live-model and data inputs are unconnected. |
| `base_path` | STRING | Default: "" | Compatible base checkpoint file used when its live-model and data inputs are unconnected. |
| `output_path` | STRING | Default: "" | Optional explicit destination file on the ComfyUI server. Leave blank for automatic output naming; the extension must match the selected output mode. |

| Output | Type | Description |
| --- | --- | --- |
| `saved_path` | STRING | Actual server path of the completed output file. Emitted only after a successful save. |
| `lora_data` | RAY_MODEL_DATA | Model Tools data handle referring to the saved extracted LoRA adapter. |
| `report` | STRING | Readable inspection or operation report, including compatibility, format, processing, and saved-result information relevant to this operation. |

<a id="RayLoraQKVLoader"></a>

## 🧰 Ray's Model Tools: LoRA QKV Loader (`RayLoraQKVLoader`)

Load and stack LoRAs with +, trash and a strength per row. Automatically checks the connected model's native parameter map, repairs unambiguous trainer naming and supported fused/separate QKV mismatches, and otherwise uses native adapters. Applies to the MODEL only. Zero strength skips a row; an empty list passes the model through. Incompatible or unsafe repairs are reported.

| Input / control | Type | Default / choices / limits | Description |
| --- | --- | --- | --- |
| `model` | MODEL | Connection | Diffusion model to patch. The selected LoRAs are applied in row order to a clone; text encoders are not modified. |
| `lora_name` | STRING | Default: "" | Select a registered LoRA from the searchable folder dropdown. Search includes every subfolder. |
| `strength` | FLOAT | Default: 1.0; min: -100.0; max: 100.0; step: 0.01 | First LoRA's model-strength multiplier. Zero skips it; negative values reverse its direction. Each additional row has its own strength. |
| `additional_loras` | STRING | Default: "[]" | Additional LoRA rows with independent strengths, applied in order. |

| Output | Type | Description |
| --- | --- | --- |
| `MODEL` | MODEL | Cloned model with compatible LoRAs applied in row order at their individual strengths. The original model and text encoders are unchanged. |

<a id="RayMetaInspect"></a>

## 🔧 Ray's Tools: Metadata Inspector (`RayMetaInspect`)

Read or write image generation metadata.
  • `Inspect` — parses every known chunk (A1111 parameters, ComfyUI prompt / workflow graph, EXIF UserComment, sidecar text) and exposes prompt_positive, prompt_negative, seed, steps, cfg, sampler, model, LoRAs, dimensions, and the raw JSON blob.
  • `Embed`   — writes an IMAGE tensor + `metadata_json` dict back to disk at `path`, then re-parses the file for round-trip verification.

In Inspect, connect a Load Image node to read that file's metadata (its source file takes precedence when found), or enter a path. Embed writes PNG only and preserves existing files unless Overwrite is enabled.

| Input / control | Type | Default / choices / limits | Description |
| --- | --- | --- | --- |
| `mode` | COMBO | Default: "Inspect"; Choices: Inspect, Embed | Inspect reads metadata; Embed writes a tensor + JSON dict to disk. |
| `path` | STRING | Default: "" | Inspect: source file, used when no source file can be traced from the connected image. Embed: explicit destination .png file on the server; relative paths use the server working directory. |
| `image` | IMAGE | Connection | Inspect: trace a Load Image node through the connected image. A resolved source file wins over `path`; otherwise the typed path is used. Embed: tensor to write. |
| `metadata_json` | STRING | Default: "" | Embed mode: JSON object of metadata fields to attach. Duplicate keys, non-finite numbers, and malformed JSON are rejected. |
| `overwrite` | BOOLEAN | Default: false | Embed only: allow replacing an existing destination PNG. Off preserves existing files and reports a collision. |

| Output | Type | Description |
| --- | --- | --- |
| `prompt_positive` | STRING | Positive prompt extracted from the file's metadata. |
| `prompt_negative` | STRING | Negative prompt extracted from the file's metadata. |
| `seed` | STRING | Seed value if present. |
| `steps` | STRING | Sampler step count if present. |
| `cfg` | STRING | CFG scale if present. |
| `sampler` | STRING | Sampler name if present. |
| `model` | STRING | Model / checkpoint reference if present. |
| `loras_json` | STRING | LoRAs referenced in the metadata, encoded as JSON. |
| `width` | STRING | Image width in pixels. |
| `height` | STRING | Image height in pixels. |
| `raw_metadata_json` | STRING | Full raw metadata as JSON — for debugging or downstream tools. |
| `image` | IMAGE | Source image tensor. |

<a id="RayModelCard"></a>

## 🔧 Ray's Tools: Model Card (`RayModelCard`)

Connect MODEL, CLIP and VAE to generate a complete visual benchmark: black model card, preview, ordered image batch and Markdown report. Copy Config provides the editable default. Image generation only.

| Input / control | Type | Default / choices / limits | Description |
| --- | --- | --- | --- |
| `model` | MODEL | Connection | Diffusion model to benchmark, including upstream patches and LoRAs. Use this model's normal sampler and guidance settings. |
| `clip` | CLIP | Connection | Text encoder matching the benchmark model, used to encode each positive and negative prompt. |
| `vae` | VAE | Connection | VAE matching the benchmark model, used to decode the generated latent images. |
| `seed` | INT | Default: 0; min: 0; max: 18446744073709551615 | Initial seed. Increment/decrement advance before each benchmark image. |
| `seed_mode` | COMBO | Default: "fixed"; Choices: fixed, increment, decrement, randomize | Per-image seed behavior; linked to the native seed control in the Ray panel. |
| `steps` | INT | Default: 20; min: 1; max: 10000 | Sampling steps per benchmark image. Higher values take longer; choose a value suitable for the model. |
| `cfg` | FLOAT | Default: 7.0; min: 0.0; max: 100.0; step: 0.1 | Classifier-free guidance scale used for every image. Distilled and embedded-guidance models may require low CFG; use the model's recommended setting. |
| `sampler_name` | COMBO | Default: "euler"; Choices: euler, euler_cfg_pp, euler_ancestral, euler_ancestral_cfg_pp, heun, heunpp2, exp_heun_2_x0, exp_heun_2_x0_sde, dpm_2, dpm_2_ancestral, lms, dpm_fast, dpm_adaptive, dpmpp_2s_ancestral, dpmpp_2s_ancestral_cfg_pp, dpmpp_sde, dpmpp_sde_gpu, dpmpp_2m, dpmpp_2m_cfg_pp, dpmpp_2m_sde, dpmpp_2m_sde_gpu, dpmpp_2m_sde_heun, dpmpp_2m_sde_heun_gpu, dpmpp_3m_sde, dpmpp_3m_sde_gpu, ddpm, lcm, ipndm, ipndm_v, deis, cfgpp_ud10_ab, res_multistep, res_multistep_cfg_pp, res_multistep_ancestral, res_multistep_ancestral_cfg_pp, gradient_estimation, gradient_estimation_cfg_pp, er_sde, seeds_2, seeds_3, sa_solver, sa_solver_pece, ddim, uni_pc, uni_pc_bh2 | ComfyUI sampling algorithm used for all benchmark images. Use one supported by the supplied model. |
| `scheduler` | COMBO | Default: "normal"; Choices: simple, sgm_uniform, karras, exponential, ddim_uniform, beta, normal, linear_quadratic, kl_optimal | Noise schedule used by the selected sampler for every benchmark image. |
| `denoise` | FLOAT | Default: 1.0; min: 0.0; max: 1.0; step: 0.01 | Fraction of the denoising schedule used from a fresh latent. One uses the full schedule; lower values use only its final part. |
| `image_width` | INT | Default: 1024; min: 64; max: 16384; step: 8 | Generated source-image width in pixels for each benchmark entry. Independent of the completed card's width. |
| `image_height` | INT | Default: 1024; min: 64; max: 16384; step: 8 | Generated source-image height in pixels for each benchmark entry. Larger images increase sampling time and memory use. |
| `card_width` | INT | Default: 3000; min: 256; max: 32768; step: 8 | Completed model-card width in pixels. Height is calculated from the categories, image proportions, headings, and captions. |
| `preview_width` | INT | Default: 1000; min: 64; max: 32768; step: 8 | Maximum preview width; smaller cards are never enlarged. |
| `card_name` | STRING | Default: "" | Card title: type text, connect a STRING, or use the { } builder for dates, times, hashes and widget values. Spaces are preserved. Blank uses MODEL CARD; config =title wins. |
| `guidance_mode` | COMBO | Default: "auto"; Choices: auto, set, disabled | Auto adds embedded guidance for models declaring guidance_embed. Set supplies guidance explicitly. Disabled leaves native conditioning unchanged. |
| `guidance` | FLOAT | Default: 3.5; min: 0.0; max: 100.0; step: 0.1 | Embedded model guidance value, separate from CFG. Applied according to Guidance mode; disabled mode leaves conditioning unchanged. |
| `max_images` | INT | Default: 256; min: 1; max: 4096 | Preflight generation-count safeguard; raise deliberately for larger benchmarks. |
| `memory_limit_mb` | INT | Default: 4096; min: 256; max: 65536; step: 256 | Estimated CPU output/compositing budget in MiB. Model and VRAM memory are additional. |
| `config` | STRING | Default: "+ANIMALS\nGreat white shark swimming underwater::a great white shark swimming through clear blue ocean water, full body viewed from the side, detailed skin, gills and fins, natural underwater light, realistic wildlife photograph\nRed fox sitting in fresh snow::a red fox sitting in fresh snow, full body, detailed orange and white fur, winter daylight, wildlife photograph\nBlue and yellow macaw on a branch::a blue and yellow macaw perched on a wooden branch, full body, detailed feathers, natural light, wildlife photograph\nAfrican elephant crossing dry savanna::an African elephant walking across a dry savanna, full body, detailed wrinkled skin, daylight, wildlife photograph\nGreen tree frog on a wet leaf::a bright green tree frog sitting on a broad wet leaf, close-up, detailed moist skin, natural rainforest light, wildlife photograph\nGreen iguana on a sunlit rock::a green iguana resting on a sunlit rock, full body and long tail fully visible, detailed scales and dorsal spines, natural daylight, realistic wildlife photograph\n\n+PEOPLE\n10yo Korean girl, black bob and red glasses::portrait of a 10-year-old Korean girl, straight black hair in a shoulder-length bob, wearing round red glasses, natural daylight, realistic photograph\n20yo Nigerian man, scar through left eyebrow::portrait of a 20-year-old Nigerian man, short black hair, distinctive small scar through his left eyebrow, natural daylight, realistic photograph\n30yo Irish woman, auburn hair and freckles::portrait of a 30-year-old Irish woman, long auburn hair, prominent freckles across her cheeks and nose, natural daylight, realistic photograph\n40yo Indian man, curled moustache::portrait of a 40-year-old Indian man, dark wavy hair, distinctive curled moustache, natural daylight, realistic photograph\n50yo Brazilian woman, turquoise pendant::portrait of a 50-year-old Brazilian woman, dark curly hair, wearing a single turquoise pendant necklace, natural daylight, realistic photograph\n70yo Japanese man, silver hair and smile lines::portrait of a 70-year-old Japanese man, short silver hair, distinctive deep smile lines around his eyes, natural daylight, realistic photograph\n\n+BODY\nOpen right hand, palm facing camera::extreme close-up photograph of a woman's open right hand, palm facing camera, detailed skin texture, fingers fully visible, neutral studio lighting\nLeft ear, dark hair tucked behind::extreme close-up photograph of a woman's left ear, detailed natural skin texture, dark brown hair tucked behind the ear, neutral studio lighting\nGreen eye, iris and eyelashes in close-up::extreme close-up photograph of a woman's green eye, detailed iris, eyelashes and natural skin texture, neutral studio lighting\nBare right foot with all toes visible::extreme close-up photograph of a woman's bare right foot, toes fully visible, detailed natural skin texture, neutral studio lighting\nRelaxed closed mouth, natural lips::extreme close-up photograph of a woman's relaxed closed mouth, natural lips and surrounding skin texture, neutral studio lighting\nNose in side profile, natural skin texture::extreme close-up photograph of a woman's nose viewed from the side in profile, detailed natural skin texture, neutral studio lighting\n\n+EXPRESSIONS\nNeutral expression, looking at camera::portrait of a 32-year-old Mediterranean woman with olive skin, green almond-shaped eyes, an oval face, straight nose, defined cheekbones, medium-full lips, shoulder-length dark brown wavy hair parted slightly to the left, slim athletic build, wearing a plain fitted gray crew-neck T-shirt, neutral relaxed expression, looking directly at camera, plain light-gray background, realistic photograph\nBroad smile, visible teeth and raised cheeks::portrait of a 32-year-old Mediterranean woman with olive skin, green almond-shaped eyes, an oval face, straight nose, defined cheekbones, medium-full lips, shoulder-length dark brown wavy hair parted slightly to the left, slim athletic build, wearing a plain fitted gray crew-neck T-shirt, broad genuine smile with visible teeth, raised cheeks and slightly narrowed happy eyes, looking directly at camera, plain light-gray background, realistic photograph\nSad expression, downturned mouth and watery eyes::portrait of a 32-year-old Mediterranean woman with olive skin, green almond-shaped eyes, an oval face, straight nose, defined cheekbones, medium-full lips, shoulder-length dark brown wavy hair parted slightly to the left, slim athletic build, wearing a plain fitted gray crew-neck T-shirt, sad expression with lowered eyebrows, slightly downturned mouth and watery eyes, looking directly at camera, plain light-gray background, realistic photograph\nAngry expression, furrowed brows and tense jaw::portrait of a 32-year-old Mediterranean woman with olive skin, green almond-shaped eyes, an oval face, straight nose, defined cheekbones, medium-full lips, shoulder-length dark brown wavy hair parted slightly to the left, slim athletic build, wearing a plain fitted gray crew-neck T-shirt, angry expression with deeply furrowed brows, narrowed eyes and tense jaw, looking directly at camera, plain light-gray background, realistic photograph\nFrightened expression, wide eyes and open mouth::portrait of a 32-year-old Mediterranean woman with olive skin, green almond-shaped eyes, an oval face, straight nose, defined cheekbones, medium-full lips, shoulder-length dark brown wavy hair parted slightly to the left, slim athletic build, wearing a plain fitted gray crew-neck T-shirt, frightened expression with raised eyebrows, wide eyes and tense slightly open mouth, looking directly at camera, plain light-gray background, realistic photograph\nExcited expression, wide eyes and open smile::portrait of a 32-year-old Mediterranean woman with olive skin, green almond-shaped eyes, an oval face, straight nose, defined cheekbones, medium-full lips, shoulder-length dark brown wavy hair parted slightly to the left, slim athletic build, wearing a plain fitted gray crew-neck T-shirt, intensely excited expression with raised eyebrows, wide sparkling eyes and a large open smile, looking directly at camera, plain light-gray background, realistic photograph\n\n+POSES\nStanding upright, arms relaxed at sides::full-body photograph of a 32-year-old Mediterranean woman with olive skin, green almond-shaped eyes, an oval face, shoulder-length dark brown wavy hair parted slightly to the left, 170 cm tall, slim athletic build with moderately broad shoulders, narrow waist and long legs, wearing a fitted gray crew-neck T-shirt, straight dark blue jeans and plain white sneakers, standing upright with feet shoulder-width apart and both arms relaxed at her sides, neutral expression, plain studio background, realistic photograph\nArms crossed firmly over the chest::full-body photograph of a 32-year-old Mediterranean woman with olive skin, green almond-shaped eyes, an oval face, shoulder-length dark brown wavy hair parted slightly to the left, 170 cm tall, slim athletic build with moderately broad shoulders, narrow waist and long legs, wearing a fitted gray crew-neck T-shirt, straight dark blue jeans and plain white sneakers, standing upright with both arms crossed firmly over her chest, neutral expression, plain studio background, realistic photograph\nHands on hips, elbows pointing outward::full-body photograph of a 32-year-old Mediterranean woman with olive skin, green almond-shaped eyes, an oval face, shoulder-length dark brown wavy hair parted slightly to the left, 170 cm tall, slim athletic build with moderately broad shoulders, narrow waist and long legs, wearing a fitted gray crew-neck T-shirt, straight dark blue jeans and plain white sneakers, standing upright with both hands resting on her hips and elbows pointing outward, neutral expression, plain studio background, realistic photograph\nLow crouch, feet flat and hands on thighs::full-body photograph of a 32-year-old Mediterranean woman with olive skin, green almond-shaped eyes, an oval face, shoulder-length dark brown wavy hair parted slightly to the left, 170 cm tall, slim athletic build with moderately broad shoulders, narrow waist and long legs, wearing a fitted gray crew-neck T-shirt, straight dark blue jeans and plain white sneakers, crouching low with both feet flat on the ground, knees bent and hands resting lightly on her thighs, neutral expression, plain studio background, realistic photograph\nWalking toward camera, left foot forward::full-body photograph of a 32-year-old Mediterranean woman with olive skin, green almond-shaped eyes, an oval face, shoulder-length dark brown wavy hair parted slightly to the left, 170 cm tall, slim athletic build with moderately broad shoulders, narrow waist and long legs, wearing a fitted gray crew-neck T-shirt, straight dark blue jeans and plain white sneakers, walking naturally toward the camera with her left foot forward and opposite arm swinging naturally, neutral expression, plain studio background, realistic photograph\nReaching overhead with the right arm::full-body photograph of a 32-year-old Mediterranean woman with olive skin, green almond-shaped eyes, an oval face, shoulder-length dark brown wavy hair parted slightly to the left, 170 cm tall, slim athletic build with moderately broad shoulders, narrow waist and long legs, wearing a fitted gray crew-neck T-shirt, straight dark blue jeans and plain white sneakers, standing while reaching high above her head with her right arm fully extended and her left arm relaxed beside her body, neutral expression, plain studio background, realistic photograph\n\n+FRAMING\nFront view at eye level, full body::full-body photograph of a 32-year-old Mediterranean woman with olive skin, green almond-shaped eyes, an oval face, shoulder-length dark brown wavy hair parted slightly to the left, 170 cm tall, slim athletic build, wearing a fitted gray crew-neck T-shirt, straight dark blue jeans and plain white sneakers, standing upright with arms relaxed at her sides, viewed directly from the front at eye level, symmetrical camera position, plain studio background, realistic photograph\nRear view at eye level, full body::full-body photograph of a 32-year-old Mediterranean woman with olive skin, shoulder-length dark brown wavy hair parted slightly to the left, 170 cm tall, slim athletic build, wearing a fitted gray crew-neck T-shirt, straight dark blue jeans and plain white sneakers, standing upright with arms relaxed at her sides, viewed directly from behind at eye level, back of head and body fully visible, plain studio background, realistic photograph\nHigh camera angle, steep downward view::full-body photograph of a 32-year-old Mediterranean woman with olive skin, green almond-shaped eyes, an oval face, shoulder-length dark brown wavy hair parted slightly to the left, 170 cm tall, slim athletic build, wearing a fitted gray crew-neck T-shirt, straight dark blue jeans and plain white sneakers, standing upright with arms relaxed at her sides, camera positioned high above her looking steeply downward, strong top-down perspective, entire body visible, plain studio floor, realistic photograph\nLow camera angle, looking steeply upward::full-body photograph of a 32-year-old Mediterranean woman with olive skin, green almond-shaped eyes, an oval face, shoulder-length dark brown wavy hair parted slightly to the left, 170 cm tall, slim athletic build, wearing a fitted gray crew-neck T-shirt, straight dark blue jeans and plain white sneakers, standing upright with arms relaxed at her sides, camera positioned very low near floor level looking steeply upward, entire body visible, strong low-angle perspective, plain studio background, realistic photograph\nStrict left profile, body and face at 90°::full-body photograph of a 32-year-old Mediterranean woman with olive skin, green almond-shaped eyes, an oval face, straight nose, shoulder-length dark brown wavy hair parted slightly to the left, 170 cm tall, slim athletic build, wearing a fitted gray crew-neck T-shirt, straight dark blue jeans and plain white sneakers, standing upright with arms relaxed at her sides, strict left-side profile with her body and face turned exactly 90 degrees from the camera, eye-level camera, plain studio background, realistic photograph\nThree-quarter left view, body and face at 45°::full-body photograph of a 32-year-old Mediterranean woman with olive skin, green almond-shaped eyes, an oval face, straight nose, defined cheekbones, shoulder-length dark brown wavy hair parted slightly to the left, 170 cm tall, slim athletic build, wearing a fitted gray crew-neck T-shirt, straight dark blue jeans and plain white sneakers, standing upright with arms relaxed at her sides, body and face rotated approximately 45 degrees toward the camera in a three-quarter left view, eye-level camera, plain studio background, realistic photograph\n\n+LOCATIONS\nRainy European city intersection in the evening::busy modern European city intersection on a rainy evening, pedestrians, cars, storefronts and wet pavement reflections, realistic photograph\nUrban park, spring sunshine and winding paths::large urban park on a sunny spring afternoon, green lawn, mature trees, benches and winding paths, realistic photograph\nModern apartment living room in daylight::comfortable modern apartment living room, sofa, bookshelves, large windows and natural daylight, realistic interior photograph\nAncient forest, moss and shafts of sunlight::dense ancient forest with moss-covered trees, ferns and shafts of sunlight passing through the canopy, realistic landscape photograph\nSandy beach, clear blue water and small waves::wide sandy beach beside clear blue ocean water, small waves, scattered rocks and bright daylight, realistic landscape photograph\nSnowy peaks above an alpine river valley::high alpine valley surrounded by steep snow-capped mountains, small river crossing the valley, clear morning light, realistic landscape photograph\n\n+PROPS\nAnalog clock showing exactly 3:15 PM::analog wall clock clearly showing exactly 3:15 PM, hour hand slightly past 3 and minute hand pointing at 3, centered and viewed straight on against a neutral white background, realistic photograph\nMedieval longsword, steel blade and leather grip::single medieval longsword lying horizontally on a plain white surface against a neutral white background, straight steel blade, leather-wrapped grip and simple crossguard, realistic photograph\nRed sports car, three-quarter front view::red modern sports car parked on a plain white studio floor against a neutral white background, full vehicle visible from a three-quarter front angle, realistic photograph\nWooden recurve bow with taut string and arrow::single wooden recurve bow with a taut string and one arrow resting beside it, lying on a plain white surface against a neutral white background, realistic photograph\nBlue wooden chair, entire chair visible::single blue wooden chair standing upright on a plain white surface against a neutral white background, entire chair visible, realistic photograph\nWhite cup of black coffee, visible steam::white ceramic coffee cup filled with hot black coffee on a plain white surface against a neutral white background, clearly visible steam rising from the cup, realistic photograph\n\n+STYLES\nStudio photograph, blue coat on white::full-body image of a 32-year-old Mediterranean woman with olive skin, green almond-shaped eyes, an oval face, straight nose, defined cheekbones, medium-full lips, shoulder-length dark brown wavy hair parted slightly to the left, 170 cm tall, slim athletic build with moderately broad shoulders, narrow waist and long legs, wearing a fitted cobalt-blue knee-length coat over a black shirt, dark straight-leg trousers and black ankle boots, standing neutrally with arms relaxed at her sides, isolated against a neutral white background, photorealistic professional studio photograph, realistic skin texture, natural lighting\nCinematic movie still, blue coat on white::full-body image of a 32-year-old Mediterranean woman with olive skin, green almond-shaped eyes, an oval face, straight nose, defined cheekbones, medium-full lips, shoulder-length dark brown wavy hair parted slightly to the left, 170 cm tall, slim athletic build with moderately broad shoulders, narrow waist and long legs, wearing a fitted cobalt-blue knee-length coat over a black shirt, dark straight-leg trousers and black ankle boots, standing neutrally with arms relaxed at her sides, isolated against a neutral white background, cinematic live-action movie still, anamorphic lens, shallow depth of field, cinematic color grading, dramatic practical lighting\nRealistic 3D render, blue coat on white::full-body image of a 32-year-old Mediterranean woman with olive skin, green almond-shaped eyes, an oval face, straight nose, defined cheekbones, medium-full lips, shoulder-length dark brown wavy hair parted slightly to the left, 170 cm tall, slim athletic build with moderately broad shoulders, narrow waist and long legs, wearing a fitted cobalt-blue knee-length coat over a black shirt, dark straight-leg trousers and black ankle boots, standing neutrally with arms relaxed at her sides, isolated against a neutral white background, high-end realistic 3D character render, physically based materials, realistic subsurface skin scattering, global illumination\nEditorial illustration, blue coat on white::full-body image of a 32-year-old Mediterranean woman with olive skin, green almond-shaped eyes, an oval face, straight nose, defined cheekbones, medium-full lips, shoulder-length dark brown wavy hair parted slightly to the left, 170 cm tall, slim athletic build with moderately broad shoulders, narrow waist and long legs, wearing a fitted cobalt-blue knee-length coat over a black shirt, dark straight-leg trousers and black ankle boots, standing neutrally with arms relaxed at her sides, isolated against a neutral white background, detailed contemporary editorial illustration, clean shapes, confident linework and controlled shading\nOil painting, visible brushwork, blue coat on white::full-body image of a 32-year-old Mediterranean woman with olive skin, green almond-shaped eyes, an oval face, straight nose, defined cheekbones, medium-full lips, shoulder-length dark brown wavy hair parted slightly to the left, 170 cm tall, slim athletic build with moderately broad shoulders, narrow waist and long legs, wearing a fitted cobalt-blue knee-length coat over a black shirt, dark straight-leg trousers and black ankle boots, standing neutrally with arms relaxed at her sides, isolated against a neutral white background, traditional oil painting on canvas, visible layered brush strokes, rich pigments and naturalistic anatomy\nJapanese anime, cel shading, blue coat on white::full-body image of a 32-year-old Mediterranean woman with olive skin, green almond-shaped eyes, an oval face, straight nose, defined cheekbones, medium-full lips, shoulder-length dark brown wavy hair parted slightly to the left, 170 cm tall, slim athletic build with moderately broad shoulders, narrow waist and long legs, wearing a fitted cobalt-blue knee-length coat over a black shirt, dark straight-leg trousers and black ankle boots, standing neutrally with arms relaxed at her sides, isolated against a neutral white background, polished Japanese anime illustration, clean precise linework, cel shading and detailed character design\n\n+TEXT\nChat bubble: \"Hello, my name is Bob\"::a clean chat interface showing one large white speech bubble on a simple pale background, the bubble contains exactly \"Hello, my name is Bob\" in crisp black sentence-case lettering, generous padding around the words, entire bubble and complete message fully visible, no other text\nDiner neon: \"Sal's\" / \"Open 24 Hours\"::photorealistic interior of a classic American diner at night, chrome counter and red vinyl booths, a large neon sign above the counter displays exactly \"Sal's\" on the upper line and \"Open 24 Hours\" on the lower line, warm red and blue neon light reflected on the chrome, both lines fully visible and clearly legible, no other readable text\nStreet signs: \"Maple Street\" / \"6th Avenue North\"::photorealistic street corner at an intersection, two perpendicular green street-name signs mounted on one pole, one sign reads exactly \"Maple Street\" and the other reads exactly \"6th Avenue North\", crisp white lettering matching that capitalization, camera positioned at a three-quarter angle so the front faces of both signs are clearly visible, both complete signs in frame, natural daylight, city buildings in the background\nPoster: \"The Darkness\"; \"IN CINEMAS SOON\"; \"DAVE PRATT\", \"ZOE DIESEL\"::professionally designed cinematic horror movie poster viewed straight on, dark atmospheric city imagery, clear typography with three distinct levels: exactly \"IN CINEMAS SOON\" across the top, the large prominent title \"The Darkness\" centered in the middle, and the actor names \"DAVE PRATT\" and \"ZOE DIESEL\" directly below the title, both actor names equally prominent, generous spacing, all lettering fully visible and easy to read, no additional text\n\"THE MORNING CHRONICLE\", detailed front-page text::photorealistic overhead photograph of a complete broadsheet newspaper front page lying flat on a wooden table, page aligned square to the camera with all four edges visible, off-white paper, crisp black ink, dense professional multi-column editorial layout, large serif masthead reading exactly \"THE MORNING CHRONICLE\", immediately beneath it the dateline \"FRIDAY, OCTOBER 23, 2026 — BERLIN — €3.20\", dominant headline \"A CITY AWAKES TO A NEW ERA\", directly below it the subheadline \"After years of planning, a landmark public project opens its doors as thousands gather across the capital.\", large news photograph of crowds entering a modern civic building at sunrise, beneath the photograph the caption \"Crowds gathered shortly after sunrise on Friday as the new civic complex opened to the public for the first time.\", three clearly separated secondary stories headed \"MARKETS RALLY AFTER WEEK OF UNCERTAINTY\", \"SCIENCE TEAM REPORTS MAJOR ENERGY BREAKTHROUGH\", and \"AUTUMN FESTIVAL TRANSFORMS CITY STREETS\", bottom teaser strip reading \"SPORT — PAGE 18\", \"BUSINESS — PAGE 22\", \"CULTURE — PAGE 27\", and \"WEATHER — PAGE 31\", small barcode and printed price of €3.20 near the lower edge, authentic major-city newspaper typography, realistic ink and paper texture, subtle shadows, all specified text reproduced exactly as quoted, correctly spelled and fully legible, no gibberish or placeholder text\nRaccoon holding a sign reading \"NOT A DOG\"::photorealistic raccoon standing upright on its hind legs on a busy city street, holding a rectangular white cardboard sign with both front paws, the sign reads exactly \"NOT A DOG\" in large bold black uppercase letters, sign facing directly toward the camera, entire raccoon and complete sign fully visible, detailed realistic fur, daylight, cars and pedestrians visible in the softly focused background\n\n+COMPLEX\nTwo people, distinct outfits and left/right positions::full-body studio photograph of exactly two people standing side by side: on the left a tall dark-skinned Nigerian woman with short tightly curled black hair wearing a bright yellow cropped jacket, green high-waisted trousers and white sneakers; on the right a shorter pale-skinned Korean man with straight black hair wearing a purple crew-neck sweater, blue jeans and red sneakers; both facing the camera, hands visible, neither person touching the other, plain light-gray studio background\n4 mugs, body/handle: red/white, blue/yellow, green/black, yellow/blue::exactly four ceramic mugs arranged in a straight horizontal row on a white table: a red mug with a white handle, a blue mug with a yellow handle, a green mug with a black handle, and a yellow mug with a blue handle, all mugs clearly separated and fully visible\nRed cube on blue sphere; yellow pyramid right; green cylinder between::a small red cube resting directly on top of a large blue sphere, the blue sphere positioned to the left of a tall yellow pyramid, a small green cylinder standing exactly between the sphere and pyramid, clean studio background\n7 objects: 3 red apples, 2 green pears, yellow banana, blue cup::exactly seven objects on a wooden table: three red apples, two green pears, one yellow banana and one blue ceramic cup, every object clearly separated and fully visible\nLeft hand with red pencil; right hand thumbs-up::close-up photograph of two human hands performing different actions: the left hand holding a red pencil between thumb and index finger while the right hand gives a thumbs-up gesture, both hands fully visible with five anatomically correct fingers each\nMirror reflection: green book in left hand, opposite visual side::a 32-year-old Mediterranean woman with olive skin, shoulder-length dark brown wavy hair, slim athletic build, wearing a red jacket, blue jeans and black ankle boots, standing in front of a large vertical mirror, camera positioned behind her so both her back and her frontal reflection are visible, holding a green book in her left hand while the mirror reflection correctly shows the book on the visually opposite side" | Leave disconnected for the built-in 66-image benchmark. Copy Config gives the editable template. |

| Output | Type | Description |
| --- | --- | --- |
| `model_card` | IMAGE | Completed full-resolution card. |
| `preview` | IMAGE | Downscaled copy of the finished card. |
| `images` | IMAGE | Source images in category/column order. |
| `report` | STRING | Markdown text with exact config, settings, prompts and actual seeds. |

<a id="RayModelCompare"></a>

## 🧰 Ray's Model Tools: Model Compare (`RayModelCompare`)

Compare tensor names, shapes and dtypes before merging. Header comparison does not measure weight similarity.

| Input / control | Type | Default / choices / limits | Description |
| --- | --- | --- | --- |
| `path_a` | STRING | Default: "" | Existing model A file to compare. A connected model A or its data handle takes precedence. |
| `path_b` | STRING | Default: "" | Existing model B file to compare. A connected model B or its data handle takes precedence. |
| `components` | COMBO | Default: "diffusion"; Choices: diffusion, diffusion_and_text, text_encoder, all | Choose diffusion weights, diffusion plus text encoders, text encoders only, or all supported components. Unselected components follow the operation's preservation rules. |
| `model_a` | MODEL | Connection | First live model to compare. Its effective weights, including active patches, supply source A. |
| `model_b` | MODEL | Connection | Second live model to compare. Its effective weights, including active patches, supply source B. |
| `data_a` | RAY_MODEL_DATA | Connection | Model-data handle supplying comparison source A when no live model A is connected. |
| `data_b` | RAY_MODEL_DATA | Connection | Model-data handle supplying comparison source B when no live model B is connected. |

| Output | Type | Description |
| --- | --- | --- |
| `report` | STRING | Readable inspection or operation report, including compatibility, format, processing, and saved-result information relevant to this operation. |
| `structurally_compatible` | BOOLEAN | Whether the compared tensor names and shapes are structurally compatible. This does not prove a shared training base or guarantee a good merge. |

<a id="RayModelConvert"></a>

## 🧰 Ray's Model Tools: Convert Model (`RayModelConvert`)

Convert a model file or the effective state of a connected MODEL. Inference outputs are loaded automatically when used. Non-Linear layers stay bf16 for quantized output.

| Input / control | Type | Default / choices / limits | Description |
| --- | --- | --- | --- |
| `weight_format` | COMBO | Default: "bf16"; Choices: fp32, fp16, bf16, fp8_e4m3fn, fp8_e4m3fn_scaled, fp8_e5m2, int8_tensor, int8_row, int8_convrot | Storage precision or quantization for the result. Auto/Preserve keeps the source representation where supported. Converting to higher precision cannot recover information already lost. |
| `components` | COMBO | Default: "diffusion"; Choices: diffusion, diffusion_and_text, text_encoder, all | Choose diffusion weights, diffusion plus text encoders, text encoders only, or all supported components. Unselected components follow the operation's preservation rules. |
| `model` | MODEL | Connection | Connected model to process, including its active patches and LoRAs. Takes precedence over a model-data handle or file source. |
| `clip` | CLIP | Connection | Optional text encoder to include with the connected model. It must match the model architecture and selected component scope. |
| `vae` | VAE | Connection | Optional VAE to preserve with the connected model when the operation supports complete checkpoints. |
| `model_data` | RAY_MODEL_DATA | Connection | File or in-memory model result from another Model Tools node. Supports data-only processing without initializing inference components. |
| `path` | STRING | Default: "" | Existing source file or supported sharded model folder on the ComfyUI server. A connected live model or model-data handle takes precedence where available. |

| Output | Type | Description |
| --- | --- | --- |
| `model` | MODEL | Native ComfyUI diffusion model. Inference components are initialized when this output is used; data-only workflows can use model_data instead. |
| `clip` | CLIP | Native text encoder when available in the source and enabled by the selected loading/component options; otherwise absent. |
| `vae` | VAE | Native VAE when available in the source and enabled by the selected loading/component options; otherwise absent. |
| `model_data` | RAY_MODEL_DATA | Model Tools data handle for a source file or in-memory result. Connect it directly to compatible merge, conversion, inspection, or save nodes without an extra inference load. |
| `metadata` | RAY_MODEL_METADATA | Structured metadata for the source or result, including operation information where applicable. |
| `report` | STRING | Readable inspection or operation report, including compatibility, format, processing, and saved-result information relevant to this operation. |

<a id="RayModelInspector"></a>

## 🧰 Ray's Model Tools: Model Inspector (`RayModelInspector`)

Inspect safetensors/sharded files without loading weights. Optional GGUF inspection needs gguf. A MODEL connection is exported in its effective state first.

| Input / control | Type | Default / choices / limits | Description |
| --- | --- | --- | --- |
| `path` | STRING | Default: "" | Existing source file or supported sharded model folder on the ComfyUI server. A connected live model or model-data handle takes precedence where available. |
| `max_rows` | INT | Default: 5000; min: 1; max: 100000 | Maximum tensor rows included in the inspection table and report. Higher values produce larger reports; total model statistics are still reported. |
| `model` | MODEL | Connection | Connected model to process, including its active patches and LoRAs. Takes precedence over a model-data handle or file source. |
| `model_data` | RAY_MODEL_DATA | Connection | File or in-memory model result from another Model Tools node. Supports data-only processing without initializing inference components. |

| Output | Type | Description |
| --- | --- | --- |
| `report` | STRING | Readable inspection or operation report, including compatibility, format, processing, and saved-result information relevant to this operation. |
| `metadata` | RAY_MODEL_METADATA | Structured metadata for the source or result, including operation information where applicable. |

<a id="RayModelLoadAs"></a>

## 🧰 Ray's Model Tools: Load Model As (`RayModelLoadAs`)

Select a registered diffusion model or checkpoint from the searchable folder dropdown. Inference models are initialized automatically when MODEL, CLIP or VAE outputs are used; data-only workflows avoid that extra load. FP8→FP16 cannot restore lost precision.

| Input / control | Type | Default / choices / limits | Description |
| --- | --- | --- | --- |
| `model_name` | STRING | Default: "" | Choose a registered checkpoint or diffusion model. The folder dropdown searches full paths in every subfolder. |
| `weight_format` | COMBO | Default: "auto"; Choices: auto, preserve, fp32, fp16, bf16, fp8_e4m3fn, fp8_e4m3fn_scaled, fp8_e5m2, int8_tensor, int8_row, int8_convrot | Storage precision or quantization for the result. Auto/Preserve keeps the source representation where supported. Converting to higher precision cannot recover information already lost. |
| `loader` | COMBO | Default: "auto"; Choices: auto, checkpoint, diffusion | Choose automatic architecture detection, a complete checkpoint loader, or a diffusion-only loader. Used when an inference output needs the result. |
| `load_components` | BOOLEAN | Default: true | Include available text encoders and VAE when loading a checkpoint for inference. Diffusion-only files do not contain those components. |
| `path` | STRING | Default: "" | Existing source file or supported sharded model folder on the ComfyUI server. A connected live model or model-data handle takes precedence where available. |
| `model_data` | RAY_MODEL_DATA | Connection | File or in-memory model result from another Model Tools node. Supports data-only processing without initializing inference components. |

| Output | Type | Description |
| --- | --- | --- |
| `model` | MODEL | Native ComfyUI diffusion model. Inference components are initialized when this output is used; data-only workflows can use model_data instead. |
| `clip` | CLIP | Native text encoder when available in the source and enabled by the selected loading/component options; otherwise absent. |
| `vae` | VAE | Native VAE when available in the source and enabled by the selected loading/component options; otherwise absent. |
| `model_data` | RAY_MODEL_DATA | Model Tools data handle for a source file or in-memory result. Connect it directly to compatible merge, conversion, inspection, or save nodes without an extra inference load. |
| `metadata` | RAY_MODEL_METADATA | Structured metadata for the source or result, including operation information where applicable. |
| `report` | STRING | Readable inspection or operation report, including compatibility, format, processing, and saved-result information relevant to this operation. |

<a id="RayModelMerge"></a>

## 🧰 Ray's Model Tools: Model Merge (`RayModelMerge`)

Merge compatible models connected to model_a/model_b or data_a/data_b with Ray's nine strategies. Task-vector strategies require a base_model or base_data connection. Block weights accepts a connected JSON string. Inference outputs load automatically when used. merge_name combines the sources, method, ratio, precision, settings fingerprint and time for use with Save Model.

| Input / control | Type | Default / choices / limits | Description |
| --- | --- | --- | --- |
| `strategy` | COMBO | Default: "LERP"; Choices: LERP, SLERP, TIES, DARE-Linear, DARE-TIES, DELLA, DELLA-TIES, Breadcrumbs, Breadcrumbs-TIES | Merge method. LERP is a fast weighted average; SLERP blends along layer angles. TIES, DARE, DELLA and Breadcrumbs merge changes from a compatible base model. Open node Help for each method's strengths and limitations. |
| `weight_a` | FLOAT | Default: 0.5; min: 0.0; max: 1.0; step: 0.01 | Contribution of A; B uses 1 minus this value. For LERP/SLERP, 1 selects A and 0 selects B. Other methods apply this ratio to pruned changes from the base. Matching block_weights entries override it. |
| `weight_format` | COMBO | Default: "bf16"; Choices: fp32, fp16, bf16, fp8_e4m3fn, fp8_e4m3fn_scaled, fp8_e5m2, int8_tensor, int8_row, int8_convrot | Storage format for merged floating-point weights. Quantized formats target eligible Linear layers; other merged layers stay bf16. Higher precision needs more RAM and disk space and cannot restore precision already lost in a source. |
| `components` | COMBO | Default: "diffusion"; Choices: diffusion, diffusion_and_text, text_encoder, all | Components whose matching tensors are merged: diffusion, diffusion plus text, text encoder only, or all. Unselected components pass through from A unchanged. |
| `mismatch` | COMBO | Default: "forbid"; Choices: forbid, intersect, pad, trim | Forbid: require matching names and shapes. Intersect: merge shared tensors of matching shape. Pad/Trim: resize shared tensors to the larger/smaller shape. Intersect, Pad and Trim preserve tensors present in only one input unchanged. |
| `seed` | INT | Default: 0; min: 0; max: 18446744073709551615 | Random pruning seed for DARE and DELLA. Each tensor derives its own seed from this value and its name. Keep the seed and inputs fixed for repeatable results. |
| `density` | FLOAT | Default: 0.5; min: 0.0; max: 1.0; step: 0.01 | Retention setting for TIES, DARE and DELLA. TIES keeps the largest changes; DARE uses this keep probability; DELLA adjusts it by change magnitude. Lower values prune more changes and can lose detail or amplify retained updates. |
| `lambda` | FLOAT | Default: 1.0; min: 0.0; max: 5.0; step: 0.01 | DELLA importance exponent. Higher values favor larger changes from the base more strongly. Zero gives uniform keep probabilities; use with density and seed. |
| `top_trim` | FLOAT | Default: 0.1; min: 0.0; max: 0.99; step: 0.01 | Breadcrumbs fraction of the largest absolute changes to discard as outliers, per tensor. 0.10 means 10%. Top trim plus Bottom trim must be less than 1. |
| `bottom_trim` | FLOAT | Default: 0.01; min: 0.0; max: 0.99; step: 0.01 | Breadcrumbs fraction of the smallest absolute changes to discard, per tensor. 0.01 means 1%. Top trim plus Bottom trim must be less than 1; excessive trimming can remove learned details. |
| `model_a` | MODEL | Connection | Live model A, including its active patches. Takes priority over data_a and legacy path_a. Effective weights are read one tensor at a time without a temporary source checkpoint. |
| `model_b` | MODEL | Connection | Live model B, including its active patches. Takes priority over data_b and legacy path_b. |
| `base_model` | MODEL | Connection | Compatible original training base for task-vector methods. Required for TIES, DARE, DELLA and Breadcrumbs; unused by LERP and SLERP. Takes priority over base_data. |
| `clip_a` | CLIP | Connection | Text encoder belonging to live model A. Include it when merging text-encoder components or retaining a full checkpoint. |
| `clip_b` | CLIP | Connection | Text encoder belonging to live model B when merging text-encoder components. |
| `base_clip` | CLIP | Connection | Text encoder belonging to the live base model when merging text-encoder changes. |
| `vae_a` | VAE | Connection | VAE to include with live model A. It passes through from A unless the selected components include it. |
| `data_a` | RAY_MODEL_DATA | Connection | Model data for A, usually from Load Model As. Used when model_a is disconnected; reads file or RAM weights without initializing an inference model. |
| `data_b` | RAY_MODEL_DATA | Connection | Model data for B, usually from Load Model As. Used when model_b is disconnected. |
| `base_data` | RAY_MODEL_DATA | Connection | Model data for the compatible base. Used by task-vector methods when base_model is disconnected; not needed for LERP or SLERP. |
| `path_a` | STRING | Default: "" | Legacy model A path retained for saved workflows. Connect Load Model As to data_a for normal file selection; model_a and data_a take priority. |
| `path_b` | STRING | Default: "" | Legacy model B path retained for saved workflows. Connect Load Model As to data_b; model_b and data_b take priority. |
| `base_path` | STRING | Default: "" | Legacy base-model path retained for saved workflows. Connect a compatible base to base_data or base_model instead. |
| `block_weights` | STRING | Default: "{}" | Connect a STRING containing a JSON map of tensor prefixes to A ratios between 0 and 1, for example {"diffusion_model.blocks.0.": 0.7}. The longest prefix wins. Leave disconnected for the global Weight A ratio. |

| Output | Type | Description |
| --- | --- | --- |
| `model` | MODEL | Native ComfyUI diffusion model. Inference components are initialized when this output is used; data-only workflows can use model_data instead. |
| `clip` | CLIP | Native text encoder when available in the source and enabled by the selected loading/component options; otherwise absent. |
| `vae` | VAE | Native VAE when available in the source and enabled by the selected loading/component options; otherwise absent. |
| `model_data` | RAY_MODEL_DATA | Model Tools data handle for a source file or in-memory result. Connect it directly to compatible merge, conversion, inspection, or save nodes without an extra inference load. |
| `metadata` | RAY_MODEL_METADATA | Structured metadata for the source or result, including operation information where applicable. |
| `report` | STRING | Readable inspection or operation report, including compatibility, format, processing, and saved-result information relevant to this operation. |
| `merge_name` | STRING | Suggested merge filename containing resolved source names, strategy, settings, and execution datetime. Connect to Save Model's filename_prefix. |

<a id="RayModelMetadata"></a>

## 🧰 Ray's Model Tools: Metadata Load / Edit (`RayModelMetadata`)

Load model metadata or a JSON sidecar. Use Load / Edit to populate the editable table. Strings remain strings; nested JSON can be expanded without changing it.

| Input / control | Type | Default / choices / limits | Description |
| --- | --- | --- | --- |
| `path` | STRING | Default: "" | Existing source file or supported sharded model folder on the ComfyUI server. A connected live model or model-data handle takes precedence where available. |
| `editor_json` | STRING | Default: "" | Metadata currently entered in the table or JSON editor. Changes are retained with the workflow; malformed JSON prevents execution. |
| `editor_source` | STRING | Default: "" | Source associated with the edited metadata. Updated by Load / Edit so the editor keeps the selected source when the workflow is reopened. |
| `model_data` | RAY_MODEL_DATA | Connection | File or in-memory model result from another Model Tools node. Supports data-only processing without initializing inference components. |
| `metadata` | RAY_MODEL_METADATA | Connection | Structured model metadata from another node. Use Metadata Load / Edit to inspect or change its fields. |

| Output | Type | Description |
| --- | --- | --- |
| `metadata` | RAY_MODEL_METADATA | Structured metadata for the source or result, including operation information where applicable. |
| `metadata_json` | STRING | Edited metadata serialized as JSON text, suitable for a JSON sidecar or metadata input. |

<a id="RayModelMetadataSave"></a>

## 🧰 Ray's Model Tools: Metadata Save (`RayModelMetadataSave`)

Save metadata as a structured JSON sidecar, or apply it to a safetensors copy without changing any tensor bytes.

| Input / control | Type | Default / choices / limits | Description |
| --- | --- | --- | --- |
| `mode` | COMBO | Default: "json_sidecar"; Choices: json_sidecar, model_copy | Save a standalone JSON metadata sidecar, or copy a source model with new embedded metadata while preserving its tensor bytes. |
| `filename_prefix` | STRING | Default: "model_tools/Ray_Metadata" | Name or prefix for automatic output under ComfyUI's output folder. An explicit Output file takes precedence when available. |
| `overwrite` | BOOLEAN | Default: false | Allow replacement of an existing destination file. Off preserves existing files and reports a filename collision instead of replacing them. |
| `metadata` | RAY_MODEL_METADATA | Connection | Structured model metadata from another node. Use Metadata Load / Edit to inspect or change its fields. |
| `metadata_json` | STRING | Default: "" | Additional metadata as a JSON object. Values may be text or JSON values; duplicate keys and invalid numbers are rejected. |
| `source_model_path` | STRING | Default: "" | Source safetensors model whose tensor bytes will be copied with the supplied metadata. Required in model-copy mode. |
| `output_path` | STRING | Default: "" | Optional explicit destination file on the ComfyUI server. Leave blank for automatic output naming; the extension must match the selected output mode. |

| Output | Type | Description |
| --- | --- | --- |
| `saved_path` | STRING | Actual server path of the completed output file. Emitted only after a successful save. |

<a id="RayModelSave"></a>

## 🧰 Ray's Model Tools: Save Model (`RayModelSave`)

Save a connected MODEL or model_data as <filename_prefix>.safetensors in the output folder, without a counter. MODEL saves bake active patches; connect CLIP/VAE to include them. Connect metadata to merge or replace the source metadata. Existing files require overwrite.

| Input / control | Type | Default / choices / limits | Description |
| --- | --- | --- | --- |
| `filename_prefix` | STRING | Default: "Ray_Model" | Filename stem, without .safetensors. No counter is added; spaces and unsupported characters become underscores. |
| `metadata_mode` | COMBO | Default: "merge"; Choices: merge, replace | Merge preserves source metadata and adds connected fields. Replace keeps only connected fields, required quantization metadata and save history. |
| `overwrite` | BOOLEAN | Default: false | Allow replacing an existing file. Off preserves it and reports a filename collision. |
| `output_folder` | STRING | Default: "model_tools" | Destination folder on the server. Blank uses ComfyUI output; relative folders are inside output. Missing folders are created when saving. |
| `model` | MODEL | Connection | Connected model to process, including its active patches and LoRAs. Takes precedence over a model-data handle or file source. |
| `clip` | CLIP | Connection | Optional text encoder to include with the connected model. It must match the model architecture and selected component scope. |
| `vae` | VAE | Connection | Optional VAE to preserve with the connected model when the operation supports complete checkpoints. |
| `model_data` | RAY_MODEL_DATA | Connection | File or in-memory model result from another Model Tools node. Supports data-only processing without initializing inference components. |
| `metadata` | RAY_MODEL_METADATA | Connection | Structured model metadata from another node. Use Metadata Load / Edit to inspect or change its fields. |
| `metadata_json` | STRING | Default: "" | Additional metadata as a JSON object. Values may be text or JSON values; duplicate keys and invalid numbers are rejected. |
| `path` | STRING | Default: "" | Existing source file or supported sharded model folder on the ComfyUI server. A connected live model or model-data handle takes precedence where available. |
| `output_path` | STRING | Default: "" | Optional explicit destination file on the ComfyUI server. Leave blank for automatic output naming; the extension must match the selected output mode. |

| Output | Type | Description |
| --- | --- | --- |
| `model_data` | RAY_MODEL_DATA | Model Tools data handle for a source file or in-memory result. Connect it directly to compatible merge, conversion, inspection, or save nodes without an extra inference load. |
| `saved_path` | STRING | Actual server path of the completed output file. Emitted only after a successful save. |

<a id="RayOffsetPrint"></a>

## ✨ Ray's VFX: Offset Print (`RayOffsetPrint`)

Image-space CMYK / duotone offset-print simulation. Per-plate halftone screens at SWOP angles, plate misregistration, dot gain, ink bleed, paper substrate (tint + grain + texture), optional sepia / vignette / posterize.

Presets cover old newspaper, comic-book, chromolithography, risograph, silk-screen, xerox, glossy magazine, etc. paper_color overrides the preset paper tint; paper_color_mix blends the two.

| Input / control | Type | Default / choices / limits | Description |
| --- | --- | --- | --- |
| `image` | IMAGE | Connection | Source frame(s). BHWC accepted. |
| `preset` | COMBO | Default: "old_newspaper"; Choices: old_newspaper, modern_newspaper, comic_book, chromolithography, inkjet, pulp_magazine, risograph, silk_screen, xerox, glossy_magazine | Print-process preset (paper stock, ink, screen). |
| `intensity` | FLOAT | Default: 1.0; min: 0.0; max: 1.0; step: 0.01 | Master mix vs untouched input. |
| `ink_strength` | FLOAT | Default: 1.0; min: 0.0; max: 2.0; step: 0.05 | Per-plate ink density multiplier. |
| `screen_strength` | FLOAT | Default: 1.0; min: 0.0; max: 1.5; step: 0.05 | Halftone screen depth. |
| `paper_strength` | FLOAT | Default: 1.0; min: 0.0; max: 2.0; step: 0.05 | Paper grain + texture amount. |
| `scale` | FLOAT | Default: 1.0; min: 0.0; max: 4.0; step: 0.05 | Halftone-screen pitch scale. |
| `paper_color` | STRING | Default: "#ffffff" | Paper substrate hex color. |
| `paper_color_mix` | FLOAT | Default: 0.0; min: 0.0; max: 1.0; step: 0.01 | Blend toward paper_color over the preset paper tint. |

| Output | Type | Description |
| --- | --- | --- |
| `image` | IMAGE | Filtered image with the offset-print effect applied. |

<a id="RayPixelArtDetector"></a>

## ✨ Ray's VFX: Pixel Art (`RayPixelArtDetector`)

Repair an exact pixel grid or convert an illustration/photo at the requested resolution with a rounded aspect ratio. Select perceptual colors and optionally dither or outline.

| Input / control | Type | Default / choices / limits | Description |
| --- | --- | --- | --- |
| `image` | IMAGE | Connection | Connect the source image or batch. |
| `input_kind` | COMBO | Choices: repair_pixel_art, illustration_photo | Recover an existing pixel grid, or abstract an illustration/photo into a smaller set of readable regions. |
| `mode` | COMBO | Default: "manual_resize"; Choices: manual_resize, auto_pixel_size, pixel_size | Choose target size, detected grid size, or source pixels per output pixel. |
| `target_resolution` | INT | Default: 128; min: 1; max: 4096 | Longest side. Repair snaps to the exact aspect-ratio lattice without upscaling; illustration/photo uses this edge and rounds the other dimension to the nearest pixel. Also the auto-detection fallback. |
| `pixel_size` | INT | Default: 8; min: 1; max: 128 | Choose source pixels per output pixel in pixel_size mode. |
| `sampling` | COMBO | Choices: grid_snap, nearest, area | Use structure reconstruction for repair, region abstraction for illustration/photo, nearest for crisp sampling, or area for averaging. |
| `reduce_palette` | BOOLEAN | Default: true | Reduce colors and enable palette-based dithering. A connected palette always takes precedence. |
| `max_colors` | INT | Default: 32; min: 2; max: 256 | Limit generated palettes. Connected palettes with at most 256 distinct colors are preserved in full. |
| `palette_style` | COMBO | Choices: source, distinct | Keep source shading, or merge near-duplicate generated shades for clearer color clusters. Supplied palettes stay unchanged. |
| `dither` | COMBO | Choices: none, ordered, error_diffusion | Choose no dither, a stable ordered pattern, or serpentine error diffusion. Protect strong edges automatically. |
| `dither_strength` | FLOAT | Default: 0.7; min: 0; max: 1; step: 0.05 | Control dither intensity without changing the palette. |
| `outline` | COMBO | Choices: none, silhouette, selective | Use a dark inner contour or a colored contour guided by nearby shading. Connect foreground_mask for complex backgrounds. |
| `palette_strategy` | COMBO | Choices: color_families, kmeans_lab, quantize_simple, kmeans_rgb, oklab_source, ramps_oklab | color_families prioritizes distinct hue/lightness groups and neutral colors before extra shades; assignment also protects family identity. Other methods retain their previous behavior. This is not semantic material recognition. |
| `protect_highlights` | BOOLEAN | Default: true | Reserve bright source colors inside the color budget. color_families preserves main families first and protects neutral glints only with spare slots. Other methods can reserve neutral and warm highlights. Supplied palettes are unchanged. |
| `highlight_threshold` | INT | Default: 90; min: 50; max: 100 | CIE Lab lightness cutoff, matching the original node. Lower this if important highlights are less bright. |
| `color_grid` | BOOLEAN | Default: false | Replace only preview with a labeled 3-by-3 grid: the exact current image output followed by all six generated color methods. Uses max_colors and the same seed/effects. Main image stays unchanged. Integer nearest-neighbor tile scaling; extra processing required. |
| `ramp_levels` | INT | Default: 4; min: 2; max: 8 | Lightness bands per chroma family for ramps_oklab; total palette still respects max_colors. |
| `palette_allocation` | COMBO | Choices: area_preserving, frequency | Favor coherent color areas and spend fewer shades on busy texture, or use ordinary color frequency. Highlight protection applies to both. No semantic recognition. |
| `palette_mapping` | COMBO | Choices: auto, legacy_oklab, oklab, lab, rgb, color_families | How pixels choose from the palette, including connected palettes. auto preserves existing behavior; legacy_oklab restores the original node's near-black handling; oklab/Lab use perceptual distance; rgb uses channel distance; color_families adds hue-family preference. Does not change the palette's colors. |
| `seed` | INT | Default: -1; min: -1; max: 2147483647 | -1 for random; any >=0 value is reproducible. |
| `palette_image` | IMAGE | Connection | Connect clean color swatches. Preserve up to 256 exact RGB colors; larger images are reduced to max_colors. |
| `foreground_mask` | MASK | Connection | Optional outline mask: 1 is subject, 0 is background. Invert Load Image alpha masks before connecting. |

| Output | Type | Description |
| --- | --- | --- |
| `image` | IMAGE | Pixel-resolution image: exact source grid for repair, rounded aspect ratio for illustration/photo. |
| `preview` | IMAGE | Nearest-neighbor preview, or labeled method comparison when color grid is enabled. |

<a id="RayPromptFetcher"></a>

## 🔧 Ray's Tools: Prompt Scraper (`RayPromptFetcher`)

One node, three prompt sources. Pick a mode and the JS hides widgets for the others.
  • `Local Folder`  — random image + extracted prompt from a local folder.
  • `PromptDexter`  — random prompt + image from promptdexter.com.
  • `CivitAI`       — random prompt + image from civitai.com.

Outputs are harmonized to `(prompt_single, prompt_multiline, image, image_path)` so any mode is drop-in compatible with downstream wiring. `image_path` is empty for web modes.

| Input / control | Type | Default / choices / limits | Description |
| --- | --- | --- | --- |
| `scraper_mode` | COMBO | Default: "Local Folder"; Choices: Local Folder, PromptDexter, CivitAI | Prompt source to fetch from. Only the widgets for this source are shown. |
| `seed` | INT | Default: -1; min: -1; max: 2147483647 | -1 for random; any >=0 value is reproducible. |
| `local__folder` | STRING | Default: "" | Local mode: absolute path to a folder of images. |
| `local__recurse_subfolders` | BOOLEAN | Default: false | Local mode: walk every subdirectory. |
| `local__skip_no_prompt` | BOOLEAN | Default: false | Local mode: skip images whose metadata yields no prompt. |
| `local__prompt_best_try` | BOOLEAN | Default: false | Local mode: collapse to one prompt per image; skip repeats. |
| `dexter__category` | COMBO | Default: "(any)"; Choices: (any), 3d, animals, anime, architecture, bike-lovers-ai-prompts, birthday-ai-image-prompts, black-and-white, car-lovers-ai-prompts, christmas-ai-image-prompts, cinematic, couple, cyberpunk, digital-art, editorial, fashion, female-mirror-selfie-ai-prompts, fitness-and-sports, food, illustration, interiors, kimono-ai-image-prompts, linkedin-profile-picture-ai-prompts, luxury-lifestyle-ai-prompts-for-men, male-mirror-selfie-ai-prompts, nature, people, portrait, product-photography, rain-ai-image-prompts, saree-ai-image-prompts, sci-fi, selfie, surreal, traditional-art, travel, vehicles, vintage, wedding | PromptDexter mode: sitemap category slug, or (any). |
| `dexter__clear_cache` | BOOLEAN | Default: false | PromptDexter mode: drop the recent-pick deque before selecting. |
| `civitai__mode` | COMBO | Default: "Blue (SFW)"; Choices: Blue (SFW), Red (NSFW) | CivitAI mode: Blue = SFW; Red = all levels. |
| `civitai__base_model` | COMBO | Default: "Any"; Choices: Any, SD 1.5, SDXL 1.0, Pony, Illustrious, NoobAI, Anima, Flux.1 D, Flux.1 S, Flux.2 Klein 9B, SD 3.5, Chroma, HiDream, Krea 2, Qwen, Nano Banana, Grok, Seedream, Z-Image Base, Z-Image Turbo, Wan Video, Wan Video 14B t2v, LTXV 2.3 | CivitAI mode: restrict picks to this base model. |
| `civitai__period` | COMBO | Default: "Week"; Choices: AllTime, Year, Month, Week, Day | CivitAI mode: time window. |
| `civitai__sort` | COMBO | Default: "Random"; Choices: Random, Most Reactions, Most Comments, Newest | CivitAI mode: gallery sort order. |
| `civitai__username` | STRING | Default: "" | CivitAI mode: restrict pool to one uploader. |
| `local__refresh_listing` | BOOLEAN | Default: false | Local mode: force a re-scan of the folder. |
| `dexter__timeout` | INT | Default: 10; min: 2; max: 60; step: 1 | PromptDexter mode: HTTP timeout per request. |
| `civitai__timeout` | INT | Default: 15; min: 2; max: 60; step: 1 | CivitAI mode: HTTP timeout per request. |

| Output | Type | Description |
| --- | --- | --- |
| `prompt_single` | STRING list | Whitespace-collapsed single-line prompt (list). |
| `prompt_multiline` | STRING list | Prompt with original newlines preserved (list). |
| `image` | IMAGE list | Image tensor (BHWC float32 [0,1]). |
| `image_path` | STRING list | For Local mode: absolute path of the source file. Empty for web modes. |

<a id="RayQueuedModelLoader"></a>

## 🧰 Ray's Model Tools: Queued Model Loader (`RayQueuedModelLoader`)

Add diffusion models with + and remove rows with the trash button. One Run outputs a native MODEL list; standard downstream nodes process each model with the same singleton prompts, seeds and settings. Images appear together in one execution's preview. Rebatch Images combines the image list into a tensor batch. Each sampled model and its clones are offloaded through ComfyUI, including on error/cancel. DynamicVRAM also releases its RAM weight buffers; legacy loading can retain CPU weights in the execution cache. Precision is automatic. Loader options contains optional Spectrum autodetection. Keep compatible text encoders and VAE connected separately.

| Input / control | Type | Default / choices / limits | Description |
| --- | --- | --- | --- |
| `model_name` | STRING | Default: "" | Select a registered diffusion model from the searchable folder dropdown. Search includes every subfolder. Precision and supported quantization are handled automatically by ComfyUI. |
| `queued_models` | STRING | Default: "[]" | Additional models in row order. One execution passes a native MODEL list through the workflow, reusing singleton prompts, seeds and settings. |
| `spectrum_enabled` | BOOLEAN | Default: false | Enable optional Spectrum forecasting. Auto selects the installed adapter for each model. This approximation can change image/video results; unsupported models keep native sampling. |

| Output | Type | Description |
| --- | --- | --- |
| `MODEL` | MODEL list | Native ComfyUI MODEL list in selected row order. Downstream nodes process each model in one execution, reusing singleton prompts, seeds, and settings. |

<a id="RaySaveImage"></a>

## 🔧 Ray's Tools: Save Image (`RaySaveImage`)

Save PNG images or compare two inputs with a draggable preview divider. Files are saved as <filename_prefix>.png: build the name from text and tokens (date, counter, hash, widget values...) with the Build filename button. Existing files are never overwritten.

| Input / control | Type | Default / choices / limits | Description |
| --- | --- | --- | --- |
| `image_1` | IMAGE | Connection | Connect the primary image or batch. |
| `save_image` | COMBO | Default: "1"; Choices: none, 1, 2, both | Choose which input batches to save; none only previews. |
| `directory` | STRING | Default: "" | Choose an absolute folder, or a path relative to ComfyUI output. Blank uses output. |
| `filename_prefix` | STRING | Default: "Ray_{date}_{counter}" | The file name, without the extension: text and {tokens} such as {date}, {counter}, {hash}, {index}, {input} and {widget:ID.NAME}. Spaces and characters a filename cannot hold are replaced, and nothing is overwritten. Use the Build filename button. |
| `save_without_metadata` | BOOLEAN | Default: false | Omit all embedded metadata from saved PNGs, including connected custom metadata. |
| `image_2` | IMAGE | Connection | Connect another image or batch to enable slider comparison. |
| `metadata` | STRING | Connection | Optional text to embed verbatim as PNG parameters instead of the ComfyUI prompt and workflow. Unconnected keeps the default metadata; connected empty text replaces it with an empty value. |

| Output | Type | Description |
| --- | --- | --- |
| — | — | Output node; results appear in its preview or saved files. |

<a id="RaySwitch"></a>

## 🎛️ Ray's Analog: Switch (`RaySwitch`)

Analog-style boolean toggle. Click the switch face to flip state. Emits a single BOOLEAN output.

Choose from 31 shared hardware styles with distinct on/off geometry. Right-click for the style picker, Compact mode (the faceplate alone: no title bar, pins or node background; drag it by its frame, links meet it under the face), and Edit label — the Dymo tape above the switch is double-click editable and persists with the workflow.

| Input / control | Type | Default / choices / limits | Description |
| --- | --- | --- | --- |
| `state` | BOOLEAN | Default: false | Switch output: on emits True and off emits False. Click the face or use Space or Enter to toggle. |

| Output | Type | Description |
| --- | --- | --- |
| `bool` | BOOLEAN | Mirror of the toggle state. |

<a id="RayTextFolder"></a>

## 🔧 Ray's Tools: TXT Folder (`RayTextFolder`)

Read .txt files alphabetically from a local folder. Emit one complete prompt and matching save prefix per non-empty file. Connect both list outputs to the same generation/save chain. Re-read files on every run.

| Input / control | Type | Default / choices / limits | Description |
| --- | --- | --- | --- |
| `directory` | STRING | Default: "" | Enter the absolute path to a folder of .txt prompts. |
| `start_index` | INT | Default: 0; min: 0 | Skip this many files in alphabetical filename order, counting empty files. |
| `limit` | INT | Default: -1; min: -1 | Read at most this many files after start_index; use -1 for all remaining files. Empty files count toward this limit. |
| `output_prefix` | STRING | Default: "RayKrea2_FromTXT" | Set the Save Image subfolder or prefix; append each source filename without its .txt extension. |

| Output | Type | Description |
| --- | --- | --- |
| `prompt` | STRING list | Complete text from each non-empty file, in alphabetical filename order. |
| `filename_prefix` | STRING list | Matching save prefix for each prompt, using the source filename stem. |

<a id="RayVHS"></a>

## ✨ Ray's VFX: VHS / Tape (`RayVHS`)

Videotape degradation modeled as a signal chain in YUV space: soft luma with deck sharpening halos, low-bandwidth chroma that smears and lags, cross-colour rainbows, line-level time-base wobble, tracking bands, a head-switching tear, streaky tape noise and dropouts. Effects scale with the picture, so presets look the same at any size.

The preset sets the tape and deck character (softness, halos, colour, levels). Each slider defaults to -1 (use the preset value) and 0..1 overrides that one effect.

effect_fade blends the result back toward the source: 0 is the full effect, 1 is the untouched picture.

The on-screen display has a status line (PLAY / REC / PAUSE / STOP) and a date / time line, each in its own corner, in white, yellow or green. It is burned into the picture before the tape, so it softens, bleeds and wobbles with it. Leave osd_date blank to stamp today's date.

| Input / control | Type | Default / choices / limits | Description |
| --- | --- | --- | --- |
| `image` | IMAGE | Connection | Source image batch to process with the selected VHS preset and tape artifacts. |
| `preset` | COMBO | Default: "Worn EP"; Choices: Pristine SP, S-VHS, Worn EP, Gen-3 dub, VHS-C camcorder, Hi8, Rental tape, Off-air LP, Chewed tape, Custom | Tape and deck: sets softness, halos, colour, levels and the starting value of every slider below. |
| `chroma_blur` | FLOAT | Default: -1.0; min: -1.0; max: 1.0; step: 0.05 | Colour bandwidth loss: how far chroma smears and lags. -1 uses the preset value; 0..1 overrides. |
| `head_switch` | FLOAT | Default: -1.0; min: -1.0; max: 1.0; step: 0.05 | The torn, noisy band at the bottom of the frame. -1 uses the preset value; 0..1 overrides. |
| `tracking_jitter` | FLOAT | Default: -1.0; min: -1.0; max: 1.0; step: 0.05 | Line wobble and tracking bands. -1 uses the preset value; 0..1 overrides. |
| `dropout_rate` | FLOAT | Default: -1.0; min: -1.0; max: 1.0; step: 0.05 | Dropout streaks (short bright or dark lines). -1 uses the preset value; 0..1 overrides. |
| `hiss` | FLOAT | Default: -1.0; min: -1.0; max: 1.0; step: 0.05 | Tape noise in luma and colour. -1 uses the preset value; 0..1 overrides. |
| `yc_separation` | FLOAT | Default: -1.0; min: -1.0; max: 1.0; step: 0.05 | Cross-colour rainbows and dot crawl around fine detail. -1 uses the preset value; 0..1 overrides. |
| `effect_fade` | FLOAT | Default: 0.0; min: 0.0; max: 1.0; step: 0.05 | Blend the result back toward the source image. 0 = full effect, 1 = untouched picture. |
| `osd_status` | COMBO | Default: "Off"; Choices: Off, ▶ PLAY, ● REC, ❚❚ PAUSE, ■ STOP | Deck status readout: Off / ▶ PLAY / ● REC / ❚❚ PAUSE / ■ STOP. |
| `osd_status_corner` | COMBO | Default: "TL"; Choices: TL, TR, BL, BR | Corner for the status readout (TL=top-left, TR=top-right, BL=bottom-left, BR=bottom-right). |
| `osd_stamp` | COMBO | Default: "Off"; Choices: Off, Date, Time, Date+Time | Date and time stamp: Off / Date / Time / Date+Time. Shown together with the status readout. |
| `osd_stamp_corner` | COMBO | Default: "BR"; Choices: TL, TR, BL, BR | Corner for the date / time stamp. Lines sharing a corner stack, status above stamp. |
| `osd_date` | STRING | Default: "" | Date text for the stamp. Leave blank to use today's date. |
| `osd_color` | COMBO | Default: "White"; Choices: White, Yellow, Green | OSD colour: White, Yellow or Green. |
| `seed` | INT | Default: -1; min: -1; max: 2147483647 | -1 for random; any >=0 value is reproducible. |

| Output | Type | Description |
| --- | --- | --- |
| `image` | IMAGE | Tape-degraded image with the OSD burned in. |

<a id="RayVLMFolder"></a>

## 💬 Ray's LLM: Folder Captioner (`RayVLMFolder`)

Caption images alphabetically with a connected CLIP/VLM on GPU. Return aligned lists of answers, original images, and absolute paths. Connect a full vision-language CLIP (for example Qwen3-VL from CLIPLoader, type qwen_image), not a text-only encoder. No sidecars are written. Caption one image at a time. Enable return_images only when needed: output images are decoded after captioning and remain in RAM until outputs are released; use start_index and limit to bound that output.

| Input / control | Type | Default / choices / limits | Description |
| --- | --- | --- | --- |
| `clip` | CLIP | Connection | Full generative vision-language CLIP, such as Qwen3-VL from CLIPLoader (type qwen_image). Text-only encoders cannot caption. |
| `folder` | STRING | Default: "" | Enter the folder containing images to caption. |
| `recurse_subfolders` | BOOLEAN | Default: false | Include images in subfolders, sorted by relative path. |
| `start_index` | INT | Default: 0; min: 0 | Skip this many images in alphabetical relative-path order. |
| `limit` | INT | Default: -1; min: -1 | Caption at most this many images; use -1 for all remaining images. |
| `user_prompt` | STRING | Default: "Describe the visible contents of this image in detail." | Enter the instruction to apply independently to every image. |
| `max_length` | INT | Default: 1024; min: 1; max: 32768 | Set the maximum number of generated tokens per image. |
| `temperature` | FLOAT | Default: 0.25; min: 0.0; max: 2.0; step: 0.01 | Set sampling randomness; use 0 for greedy decoding. |
| `top_k` | INT | Default: 40; min: 0; max: 1000 | Keep this many candidate tokens; use 0 to disable top-k filtering. |
| `top_p` | FLOAT | Default: 0.9; min: 0.0; max: 1.0; step: 0.01 | Set the cumulative probability threshold for nucleus sampling. |
| `min_p` | FLOAT | Default: 0.05; min: 0.0; max: 1.0; step: 0.01 | Filter tokens relative to the most probable token; use 0 to disable. |
| `repetition_penalty` | FLOAT | Default: 1.05; min: 0.0; max: 5.0; step: 0.01 | Set the repetition penalty; use 1 for no penalty. |
| `seed` | INT | Default: -1; min: -1; max: 2147483647 | -1 for random; any >=0 value is reproducible. |
| `thinking` | BOOLEAN | Default: false | Enable thinking when supported by the selected model; return its decoded response unchanged. |
| `return_images` | BOOLEAN | Default: false | Return original-size images after all captions finish. Off keeps the image output empty and avoids retaining the folder's decoded images in RAM. |
| `cleanup_every` | INT | Default: 16; min: 0; max: 1024 | Collect transient objects and release unused ComfyUI VRAM caches every N captions. 0 disables periodic cleanup; low-memory cleanup still applies. |

| Output | Type | Description |
| --- | --- | --- |
| `text` | STRING list | Decoded VLM answers, one per image, in scan order. |
| `image` | IMAGE list | Original RGB images, decoded after captioning when return_images is enabled; otherwise an empty list. |
| `image_path` | STRING list | Absolute source image paths, paired with the answers and images. |
