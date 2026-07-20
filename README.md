# comfyUI-Ray-Orenchi

A small pack of ComfyUI custom nodes: image VFX, pixel-art tooling, analog-style UI widgets, an Ollama / CLIP chat node, a prompt iterator, and a web prompt scraper.

| Node | Bucket | Purpose |
|------|--------|---------|
| ✨ Ray's VFX: CRT | VFX | CRT display simulation (phosphor mask, scanlines, halation, NTSC bleed, barrel warp) |
| ✨ Ray's VFX: Offset Print | VFX | CMYK / duotone halftone print simulation with paper substrate |
| ✨ Ray's VFX: Pixel Art | VFX | Pixel-art downscale + palette reduction (kmeans / OkLab ramps), dithering, palette-image input, palette preview |
| ✨ Ray's VFX: Film Stock | VFX | Film-stock emulation with LUT / XMP asset dropdown, grain, halation |
| ✨ Ray's VFX: VHS / Tape | VFX | Analog videotape degradation with OSD overlay |
| 🎛️ Ray's Analog: Knob | Analog | Float knob widget with min/max/spin/clamp |
| 🎛️ Ray's Analog: Switch | Analog | Boolean toggle widget |
| 💬 Ray's LLM: Ollama Chat | LLM | Chat node — Ollama backend or CLIP text-encoder backend, image + audio attachments |
| 💬 Ray's LLM: Prompt Iterator | LLM | Score image-vs-prompt match and propose a revised prompt via Ollama |
| 💬 Ray's LLM: Prompt Library | LLM | Save prompts to a local SQLite library with tag / source filters; browse in an inline table |
| 📝 Ray's Prompts: PromptDexter Scraper | Prompts | Random prompt + image from [promptdexter.com](https://promptdexter.com/) |
| 📝 Ray's Prompts: CivitAI Gallery Scraper | Prompts | Random prompt + image from [civitai.com](https://civitai.com/) via the public REST API. Blue (SFW) / Red (NSFW) toggle |
| 📝 Ray's Prompts: Folder Image Scraper | Prompts | Random image + extracted prompt from a local folder |
| 📝 Ray's Prompts: Prompt Fetcher | Prompts | All-in-one wrapper over the three scrapers above |
| 📝 Ray's Prompts: Metadata Inspector | Prompts | Read or embed generation metadata on a specific image |

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

Restart ComfyUI. Nodes appear under the `👑 Ray/` top-level category, split
into four bucket sub-categories: `✨ VFX`, `🎛️ Analog`, `📝 Prompts`, and
`💬 LLM`. See [UI.md](UI.md) for the pack-wide UI/UX canon and [NODES.md](NODES.md)
for per-node reference.

### Optional runtime dependencies

- **Ollama** — required for `Ray's LLM: Ollama Chat` (Ollama mode) and `Ray's LLM: Prompt Iterator`. Install from [ollama.com](https://ollama.com) and pull a model. Recommended: [`qwen3.6`](https://ollama.com/library/qwen3.6) — fast, vision-capable, plays well with the prompt iterator (`ollama pull qwen3.6`).
- **CLIP** — `Ray's LLM: Ollama Chat` (CLIP mode) reuses the text encoder of any ComfyUI-loaded CLIP model; nothing extra to install.

## Compatibility

These nodes were originally built against the **legacy ComfyUI frontend**. Compatibility work for the **v2 frontend** is centralized in `web/_common.js` — every node calls the same `setWidgetHidden` / `applyBucketTint` helpers, so the two frontends run through a single code path. If you hit a glitch on either, please open an issue with the workflow / repro steps — feedback welcome.

Class names are frozen: saved workflows keep loading across UI/UX refreshes.
See [UI.md](UI.md) for the pack-wide styleguide.

## License

Apache License 2.0 — see [LICENSE](LICENSE).
