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
  💬 LLM
  • RayPromptLibrary         — Ray's LLM: Prompt Library (SQLite)
  • RayVLMFolder             — Ray's LLM: Folder Captioner
  • RayFastQwen3VL           — Ray's LLM: Fast Qwen3-VL Infer
  🔧 Tools
  • RayPromptDexter          — Ray's Tools: PromptDexter Scraper
  • RayCivitAI               — Ray's Tools: CivitAI Gallery Scraper
  • RayLocalScraper          — Ray's Tools: Folder Image Scraper
  • RayPromptFetcher         — Ray's Tools: Prompt Fetcher (local + web)
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
    "RayCRT":              "ray_crt",
    "RayOffsetPrint":      "ray_offset_print",
    "RayPixelArtDetector": "ray_pixel_detector",
    "RayKnob":             "ray_knob",
    "RaySwitch":           "ray_switch",
    "RayButtonDeck":       "ray_button_deck",
    "RayPromptDexter":     "ray_promptdexter",
    "RayCivitAI":          "ray_civitai",
    "RayLocalScraper":     "ray_local_scraper",
    "RayTextFolder":       "ray_txt_folder",
    "RayVLMFolder":        "ray_vlm_folder",
    "RayFastQwen3VL":      "ray_fast_vlm",
    "RayPromptFetcher":    "ray_prompt_fetcher",
    "RayMetaInspect":      "ray_meta_inspect",
    "RayPromptLibrary":    "ray_prompt_library",
    "RayFilmStock":        "ray_film_stock",
    "RayVHS":              "ray_vhs",
}

# These register aiohttp routes on import.
_ROUTE_MODULES = (
    "promptdexter_routes",
    "civitai_routes",
    "prompt_library_routes",
    "film_stock_routes",
)

# Tolerate standalone import (e.g. pytest collection) where relative imports
# fail; route modules are then optional.
try:
    _modules = {name: importlib.import_module(f".{name}", __package__)
                for name in _NODE_MODULES.values()}
    for _name in _ROUTE_MODULES:
        importlib.import_module(f".{_name}", __package__)
except (ImportError, TypeError):
    _modules = {name: importlib.import_module(name)
                for name in _NODE_MODULES.values()}
    for _name in _ROUTE_MODULES:
        try:
            importlib.import_module(_name)
        except ImportError:
            pass

NODE_CLASS_MAPPINGS = {
    class_name: getattr(_modules[module], class_name)
    for class_name, module in _NODE_MODULES.items()
}

try:
    _modules["ray_save_image"].register_routes()
except ImportError:
    pass


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
    # 👑 Ray/💬 LLM
    "RayPromptLibrary":    "💬 Ray's LLM: Prompt Library",
    "RayVLMFolder":        "💬 Ray's LLM: Folder Captioner",
    "RayFastQwen3VL":      "💬 Ray's LLM: Fast Qwen3-VL Infer",
    # 👑 Ray/🔧 Tools
    "RayPromptDexter":     "🔧 Ray's Tools: PromptDexter Scraper",
    "RayCivitAI":          "🔧 Ray's Tools: CivitAI Gallery Scraper",
    "RayLocalScraper":     "🔧 Ray's Tools: Folder Image Scraper",
    "RayPromptFetcher":    "🔧 Ray's Tools: Prompt Fetcher",
    "RayMetaInspect":      "🔧 Ray's Tools: Metadata Inspector",
    "RayTextFolder":       "🔧 Ray's Tools: TXT Folder",
    "RaySaveImage":        "🔧 Ray's Tools: Save Image",
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
