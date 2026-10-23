"""Ray's Orenchi — single ComfyUI custom-node package consolidating all Ray nodes.

Bundles:
  ✨ VFX
  • RayCRT                   — Ray's VFX: CRT
  • RayOffsetPrint           — Ray's VFX: Offset Print
  • RayPixelArtDetector      — Ray's VFX: Pixel Art
  • RayFilmStock             — Ray's VFX: Film Stock
  • RayVHS                   — Ray's VFX: VHS / Tape
  🎛️ Analog
  • RayKnob                  — Ray's Analog: Control (Knob / Slider)
  • RaySwitch                — Ray's Analog: Switch
  • RayButtonDeck            — Ray's Analog: Button Deck
  • RayFaderBank             — Ray's Analog: Fader Bank
  💬 LLM
  • RayVLMFolder             — Ray's LLM: Folder Captioner
  • RayFastQwen3VL           — Ray's LLM: Fast Qwen3-VL Infer
  🔧 Tools
  • RayPromptFetcher         — Ray's Tools: Prompt Scraper (local + web)
  • RayMetaInspect           — Ray's Tools: Metadata Inspector (read/embed)
  • RayTextFolder            — Ray's Tools: TXT Folder
  • RaySaveImage             — Ray's Tools: Save Image (save + comparison preview)

Web assets live under ./web and are served at /extensions/comfyUI-Ray-Orenchi/.
"""

import importlib


# Class name -> module. Class names are registered IDs; keep them stable so
# existing workflows keep loading.
_NODE_MODULES = {
    "RaySaveImage":        "ray_save_image",
    "RayModelCard":        "ray_model_card",
    "RayModelLoadAs":      "ray_model_tools",
    "RayModelConvert":     "ray_model_tools",
    "RayModelSave":        "ray_model_tools",
    "RayModelMetadata":    "ray_model_tools",
    "RayModelMetadataSave": "ray_model_tools",
    "RayModelMerge":       "ray_model_tools",
    "RayModelInspector":   "ray_model_tools",
    "RayModelCompare":     "ray_model_tools",
    "RayLoraBake":          "ray_model_tools",
    "RayLoraExtract":       "ray_model_tools",
    "RayFolders":          "ray_folders",
    "RayCRT":              "ray_crt",
    "RayOffsetPrint":      "ray_offset_print",
    "RayPixelArtDetector": "ray_pixel_detector",
    "RayKnob":             "ray_knob",
    "RaySwitch":           "ray_switch",
    "RayButtonDeck":       "ray_button_deck",
    "RayFaderBank":        "ray_fader_bank",
    "RayTextFolder":       "ray_txt_folder",
    "RayVLMFolder":        "ray_vlm_folder",
    "RayFastQwen3VL":      "ray_fast_vlm",
    "RayPromptFetcher":    "ray_prompt_fetcher",
    "RayMetaInspect":      "ray_meta_inspect",
    "RayFilmStock":        "ray_film_stock",
    "RayVHS":              "ray_vhs",
}

# These register aiohttp routes on import.
_ROUTE_MODULES = (
    "promptdexter_routes",
    "civitai_routes",
    "film_stock_routes",
    "browse_routes",
    "folders_routes",
    "model_tools_routes",
)

# Choose the import mode before importing. Dependency failures must keep their
# original traceback, rather than retrying unrelated modules from sys.path.
def _load_module(name):
    return importlib.import_module(f".{name}", __package__) if __package__ else importlib.import_module(name)


_modules = {name: _load_module(name) for name in _NODE_MODULES.values()}
if __package__:
    for _name in _ROUTE_MODULES:
        _load_module(_name)

NODE_CLASS_MAPPINGS = {
    class_name: getattr(_modules[module], class_name)
    for class_name, module in _NODE_MODULES.items()
}

if __package__:
    _modules["ray_save_image"].register_routes()


WEB_DIRECTORY = "./web"

NODE_DISPLAY_NAME_MAPPINGS = {
    # 👑 Ray/✨ VFX
    "RayCRT":              "✨ Ray's VFX: CRT",
    "RayOffsetPrint":      "✨ Ray's VFX: Offset Print",
    "RayPixelArtDetector": "✨ Ray's VFX: Pixel Art",
    "RayFilmStock":        "✨ Ray's VFX: Film Stock",
    "RayVHS":              "✨ Ray's VFX: VHS / Tape",
    # 👑 Ray/🎛️ Analog
    "RayKnob":             "🎛️ Ray's Analog: Control (Knob / Slider)",
    "RaySwitch":           "🎛️ Ray's Analog: Switch",
    "RayButtonDeck":       "🎛️ Ray's Analog: Button Deck",
    "RayFaderBank":        "🎛️ Ray's Analog: Fader Bank",
    # 👑 Ray/💬 LLM
    "RayVLMFolder":        "💬 Ray's LLM: Folder Captioner",
    "RayFastQwen3VL":      "💬 Ray's LLM: Fast Qwen3-VL Infer",
    # 👑 Ray/🔧 Tools
    "RayPromptFetcher":    "🔧 Ray's Tools: Prompt Scraper",
    "RayMetaInspect":      "🔧 Ray's Tools: Metadata Inspector",
    "RayTextFolder":       "🔧 Ray's Tools: TXT Folder",
    "RaySaveImage":        "🔧 Ray's Tools: Save Image",
    "RayModelCard":        "🔧 Ray's Tools: Model Card",
    "RayModelLoadAs":      "🧰 Ray's Model Tools: Load Model As",
    "RayModelConvert":     "🧰 Ray's Model Tools: Convert Model",
    "RayModelSave":        "🧰 Ray's Model Tools: Save Model",
    "RayModelMetadata":    "🧰 Ray's Model Tools: Metadata Load / Edit",
    "RayModelMetadataSave": "🧰 Ray's Model Tools: Metadata Save",
    "RayModelMerge":       "🧰 Ray's Model Tools: Model Merge",
    "RayModelInspector":   "🧰 Ray's Model Tools: Model Inspector",
    "RayModelCompare":     "🧰 Ray's Model Tools: Model Compare",
    "RayLoraBake":          "🧰 Ray's Model Tools: LoRA Bake",
    "RayLoraExtract":       "🧰 Ray's Model Tools: LoRA Extract",
    "RayFolders":          "🔧 Ray's Tools: Folders",
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
