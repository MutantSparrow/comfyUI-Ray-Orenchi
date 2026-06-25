# comfyUI-Ray-Orenchi

A small pack of ComfyUI custom nodes: image VFX, pixel-art tooling, analog-style UI widgets, an Ollama / CLIP chat node, a prompt iterator, and a web prompt scraper.

| Node | Purpose |
|------|---------|
| Ray's VFX: CRT | CRT display simulation (phosphor mask, scanlines, halation, NTSC bleed, barrel warp) |
| Ray's VFX: Offset Print | CMYK / duotone halftone print simulation with paper substrate |
| Ray's VFX: Pixel Art | Pixel-art downscale + palette reduction (kmeans / OkLab ramps), dithering, palette-image input, palette preview |
| 🎛️ Ray's Analog Series: Knob | Float knob widget with min/max/spin/clamp |
| 🔘 Ray's Analog Series: Switch | Boolean toggle widget |
| Ray's LM: Ollama + Clip Chat | Chat node — Ollama backend or CLIP text-encoder backend, image + audio attachments |
| Ray's LM: LM Prompt Iterator | Score image-vs-prompt match and propose a revised prompt via Ollama |
| Ray's Web: PromptDexter Scraper | Random prompt + image scraped from [promptdexter.com](https://promptdexter.com/). Sitemap-driven discovery, seed-deterministic, dynamic category dropdown, click-to-refresh sitemap. |
| Ray's Web: CivitAI Gallery Scraper | Random prompt + image from [civitai.com](https://civitai.com/) via the public REST API. Blue (SFW) / Red (NSFW) toggle, base-model + period + sort filters, only items with prompts kept. Optional `CIVITAI_API_TOKEN` env var. |

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

- **Ollama** — required for `Ray's LM: Ollama + Clip Chat` (Ollama mode) and `Ray's LM: LM Prompt Iterator`. Install from [ollama.com](https://ollama.com) and pull a model. Recommended: [`qwen3.6`](https://ollama.com/library/qwen3.6) — fast, vision-capable, plays well with the prompt iterator (`ollama pull qwen3.6`).
- **CLIP** — `Ray's LM: Ollama + Clip Chat` (CLIP mode) reuses the text encoder of any ComfyUI-loaded CLIP model; nothing extra to install.

## Compatibility

These nodes were originally built against the **legacy ComfyUI frontend**. Some compatibility work has been done for the **v2 frontend** and the pack should run on it. If you hit a glitch on v2 (or anywhere else), please open an issue with the workflow / repro steps — feedback welcome.

## License

Apache License 2.0 — see [LICENSE](LICENSE).
