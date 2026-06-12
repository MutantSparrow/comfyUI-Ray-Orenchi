# comfyUI-Ray-Orenchi

A small pack of ComfyUI custom nodes: image VFX, pixel-art tooling, analog-style UI widgets, an Ollama / CLIP chat node, a prompt iterator, and a node-embedded mini-browser.

| Node | Purpose |
|------|---------|
| 📺 Ray's CRT VFX | CRT display simulation (phosphor mask, scanlines, halation, NTSC bleed, barrel warp) |
| 🗞️ Ray's Offset Print VFX | CMYK / duotone halftone print simulation with paper substrate |
| 🕹️ Ray's Pixel Art Pro | Pixel-art downscale + palette reduction (kmeans / OkLab ramps), dithering, palette-image input, palette preview |
| 🎛️ Ray's Analog Series: Knob | Float knob widget with min/max/spin/clamp |
| 🔘 Ray's Analog Series: Switch | Boolean toggle widget |
| 💬 Ray's LMChat | Chat node — Ollama backend or CLIP text-encoder backend, image + audio attachments |
| 🌐 Ray's Mini Browser | Embedded same-origin browser with DOM picker; returns selected text + screenshots |
| 🔄 Ray's Prompt Iterator | Score image-vs-prompt match and propose a revised prompt via Ollama |

See [Node Documentation](NODES.md) for inputs / controls / outputs per node.

## Install

Clone into your ComfyUI `custom_nodes` directory:

```
cd ComfyUI/custom_nodes
git clone https://github.com/MutantSparrow/comfyUI-Ray-Orenchi.git
```

Install Python dependencies (from the node-pack directory):

```
pip install -r requirements.txt
```

Restart ComfyUI. Nodes appear under the `Ray/*` categories.

### Optional runtime dependencies

- **Ollama** — required for `Ray's LMChat` (Ollama mode) and `Ray's Prompt Iterator`. Install from [ollama.com](https://ollama.com) and pull a model (e.g. `ollama pull llama3.2`).
- **CLIP** — `Ray's LMChat` (CLIP mode) reuses the text encoder of any ComfyUI-loaded CLIP model; nothing extra to install.

## Compatibility

These nodes were originally built against the **legacy ComfyUI frontend**. Some compatibility work has been done for the **v2 frontend** and the pack should run on it. If you hit a glitch on v2 (or anywhere else), please open an issue with the workflow / repro steps — feedback welcome.

## License

Apache License 2.0 — see [LICENSE](LICENSE).
