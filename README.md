# comfyUI-Ray-Orenchi

16 ComfyUI custom nodes for retro image effects, pixel art, local vision-language
inference, prompt tooling and analog-console controls. Find them under the
**👑 Ray** category in the add-node menu.

## Nodes

| Group | Node | What it does |
|:--|:--|:--|
| **✨ VFX** | **CRT** | Display simulation: phosphor masks, scanlines, halation, NTSC bleed, barrel distortion |
| | **Offset Print** | CMYK or duotone halftone printing with paper simulation |
| | **Pixel Art** | Repair or convert images to true pixel art: palettes, selective dithering, outlines |
| | **Film Stock** | Film response, grain and halation, with optional LUT/XMP assets |
| | **VHS / Tape** | Analog tape degradation, tracking faults, dropouts and a VCR on-screen display |
| **🎛️ Analog** | **Control** | Retro knobs and sliders with sound and optional pot-taper response curves; outputs a float and an int |
| | **Switch** | Retro toggles and rockers with sound; outputs a boolean |
| | **Button Deck** | A bank of push buttons that replaces a dropdown; outputs the pressed button's text |
| | **Fader Bank** | Two to ten vertical faders in a row, up to four rows, each a 0 to 1 float, plus the whole bank as a list |
| **💬 LLM** | **Fast Qwen3-VL Infer** | Fast image-to-text through an already loaded Qwen3-VL CLIP, with no second model copy |
| | **Folder Captioner** | Caption a range of images in a folder with a full VLM; aligned text, image and path lists |
| **🔧 Tools** | **Folders** | Browse and select local images, videos and audio; native media lists, prompts and paths |
| | **Save Image** | Save PNGs or preview them, with a two-image comparison slider and folder picker |
| | **TXT Folder** | Read text files as prompts, with matching save prefixes |
| | **Metadata Inspector** | Read generation metadata from an image, or embed it into one |
| | **Prompt Scraper** | One node for prompts from a local image folder, PromptDexter or CivitAI |

Nodes are named *Ray's &lt;Group&gt;: &lt;Node&gt;* in the menu. Select any Ray node and click the
**?** in its selection toolbar for built-in help: what it does, every input and output,
and usage notes.

## Install

```shell
cd ComfyUI/custom_nodes
git clone https://github.com/MutantSparrow/comfyUI-Ray-Orenchi.git
pip install -r comfyUI-Ray-Orenchi/requirements.txt
```

Install into the Python environment that runs ComfyUI, then restart ComfyUI and refresh
the browser. After updating the pack, restart again so new and changed nodes load.

## Good to know

- **Fast Qwen3-VL Infer** needs a full native Qwen3-VL 4B or 8B checkpoint loaded with
  ComfyUI's `CLIPLoader` (type `qwen_image`, or `krea2`). Connect its `CLIP`, an image and
  a prompt. Details and measurements are in [FAST_VLM.md](FAST_VLM.md).
- **Folder Captioner** needs a GPU and the same kind of full Qwen3-VL `CLIP` from `CLIPLoader` as Fast Qwen3-VL.
- **Browse buttons** under folder and file paths open your system's own file dialog, so ComfyUI has to run on the computer you are using. Typing or pasting a path always works.
- **Prompt Scraper**'s PromptDexter and CivitAI modes need network
  access. CivitAI can read an optional local `civitai.secret` file; it is ignored by Git.
- Works in both the classic canvas and Nodes 2.0. Node IDs are stable, so saved workflows
  keep loading.

## Documentation

[NODES.md](NODES.md) is the node-by-node reference for inputs, outputs and behavior.

## License

Apache License 2.0, see [LICENSE](LICENSE). The vendored Pixel Art Fixer grid detector is
MIT-licensed; see its [license](ray_pixel_fixer/LICENSE) and [notice](ray_pixel_fixer/NOTICE.md).
