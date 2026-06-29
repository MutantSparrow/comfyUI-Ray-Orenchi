"""Ray's Orenchi — single ComfyUI custom-node package consolidating all Ray nodes.

Bundles:
  • RayCRT                   — Ray's VFX: CRT
  • RayOffsetPrint           — Ray's VFX: Offset Print
  • RayPixelArtDetector      — Ray's VFX: Pixel Art
  • RayKnob / RaySwitch      — analog-series UI widgets
  • RayOllamaChat            — Ray's LM: Ollama + Clip Chat
  • RayPromptIterator        — Ray's LM: LM Prompt Iterator
  • RayPromptDexter          — Ray's Web: PromptDexter Scraper
  • RayCivitAI               — Ray's Web: CivitAI Gallery Scraper
  • RayLocalScraper          — Ray's Local: Folder Image Scraper
  • RayPromptFetcher         — Ray's Prompt Fetcher (Local + Web combined)
  • RayMetaInspect           — Ray's Local: Metadata Inspector (read/embed)
  • RayPromptLibrary         — Ray's LM: Local Prompt Library (SQLite)
  • RayFilmStock             — Ray's VFX: Film Stock emulation
  • RayVHS                   — Ray's VFX: VHS / Tape degradation

Web assets live under ./web and are served at /extensions/comfyUI-Ray-Orenchi/.
"""

# Tolerate standalone import (e.g. pytest collection) where relative imports fail.
try:
    from .ray_crt import RayCRT
    from .ray_offset_print import RayOffsetPrint
    from .ray_pixel_detector import RayPixelArtDetector
    from .ray_knob import RayKnob
    from .ray_switch import RaySwitch
    from .ray_ollama_chat import RayOllamaChat
    from .ray_prompt_iterator import RayPromptIterator
    from .ray_promptdexter import RayPromptDexter
    from .ray_civitai import RayCivitAI
    from .ray_local_scraper import RayLocalScraper
    from .ray_prompt_fetcher import RayPromptFetcher
    from .ray_meta_inspect import RayMetaInspect
    from .ray_prompt_library import RayPromptLibrary
    from .ray_film_stock import RayFilmStock
    from .ray_vhs import RayVHS
    from . import ollama_routes  # noqa: F401  registers aiohttp routes on import
    from . import promptdexter_routes  # noqa: F401
    from . import civitai_routes  # noqa: F401
    from . import prompt_library_routes  # noqa: F401
    from . import film_stock_routes  # noqa: F401
except ImportError:
    from ray_crt import RayCRT
    from ray_offset_print import RayOffsetPrint
    from ray_pixel_detector import RayPixelArtDetector
    from ray_knob import RayKnob
    from ray_switch import RaySwitch
    from ray_ollama_chat import RayOllamaChat
    from ray_prompt_iterator import RayPromptIterator
    from ray_promptdexter import RayPromptDexter
    from ray_civitai import RayCivitAI
    from ray_local_scraper import RayLocalScraper
    from ray_prompt_fetcher import RayPromptFetcher
    from ray_meta_inspect import RayMetaInspect
    from ray_prompt_library import RayPromptLibrary
    from ray_film_stock import RayFilmStock
    from ray_vhs import RayVHS
    try:
        import ollama_routes  # noqa: F401
    except ImportError:
        pass
    try:
        import promptdexter_routes  # noqa: F401
    except ImportError:
        pass
    try:
        import civitai_routes  # noqa: F401
    except ImportError:
        pass
    try:
        import prompt_library_routes  # noqa: F401
    except ImportError:
        pass
    try:
        import film_stock_routes  # noqa: F401
    except ImportError:
        pass


WEB_DIRECTORY = "./web"

NODE_CLASS_MAPPINGS = {
    "RayCRT":              RayCRT,
    "RayOffsetPrint":      RayOffsetPrint,
    "RayPixelArtDetector": RayPixelArtDetector,
    "RayKnob":             RayKnob,
    "RaySwitch":           RaySwitch,
    "RayOllamaChat":       RayOllamaChat,
    "RayPromptIterator":   RayPromptIterator,
    "RayPromptDexter":     RayPromptDexter,
    "RayCivitAI":          RayCivitAI,
    "RayLocalScraper":     RayLocalScraper,
    "RayPromptFetcher":    RayPromptFetcher,
    "RayMetaInspect":      RayMetaInspect,
    "RayPromptLibrary":    RayPromptLibrary,
    "RayFilmStock":        RayFilmStock,
    "RayVHS":              RayVHS,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "RayCRT":              "Ray's VFX: CRT",
    "RayOffsetPrint":      "Ray's VFX: Offset Print",
    "RayPixelArtDetector": "Ray's VFX: Pixel Art",
    "RayKnob":             "🎛️ Ray's Analog Series: Knob",
    "RaySwitch":           "🔘 Ray's Analog Series: Switch",
    "RayOllamaChat":       "Ray's LM: Ollama + Clip Chat",
    "RayPromptIterator":   "Ray's LM: LM Prompt Iterator",
    "RayPromptDexter":     "Ray's Web: PromptDexter Scraper",
    "RayCivitAI":          "Ray's Web: CivitAI Gallery Scraper",
    "RayLocalScraper":     "Ray's Local: Folder Image Scraper",
    "RayPromptFetcher":    "Ray's Prompt Fetcher",
    "RayMetaInspect":      "Ray's Local: Metadata Inspector",
    "RayPromptLibrary":    "Ray's LM: Prompt Library",
    "RayFilmStock":        "Ray's VFX: Film Stock",
    "RayVHS":              "Ray's VFX: VHS / Tape",
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
