"""Ray's Orenchi — single ComfyUI custom-node package consolidating all Ray nodes.

Bundles:
  • RayCRT                   — image-space CRT display effect (📺)
  • RayPixelArtDetector      — pixel-art downscale + palette reduction (🕹️)
  • RayKnob / RaySwitch      — analog-series UI widgets (🎛️ / 🔘)
  • RayOllamaChat            — LM Chat node (Ollama / CLIP) (💬)
  • RayMiniBrowser           — nested mini-browser with DOM picker (🌐)

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
    from .ray_minibrowser import RayMiniBrowser
    from .ray_prompt_iterator import RayPromptIterator
    from . import ollama_routes  # noqa: F401  registers aiohttp routes on import
    from . import minibrowser_routes  # noqa: F401  registers aiohttp routes on import
except ImportError:
    from ray_crt import RayCRT
    from ray_offset_print import RayOffsetPrint
    from ray_pixel_detector import RayPixelArtDetector
    from ray_knob import RayKnob
    from ray_switch import RaySwitch
    from ray_ollama_chat import RayOllamaChat
    from ray_minibrowser import RayMiniBrowser
    from ray_prompt_iterator import RayPromptIterator
    try:
        import ollama_routes  # noqa: F401
    except ImportError:
        pass
    try:
        import minibrowser_routes  # noqa: F401
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
    "RayMiniBrowser":      RayMiniBrowser,
    "RayPromptIterator":   RayPromptIterator,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "RayCRT":              "📺 Ray's CRT VFX",
    "RayOffsetPrint":      "🗞️ Ray's Offset Print VFX",
    "RayPixelArtDetector": "🕹️ Ray's Pixel Art Pro",
    "RayKnob":             "🎛️ Ray's Analog Series: Knob",
    "RaySwitch":           "🔘 Ray's Analog Series: Switch",
    "RayOllamaChat":       "💬 Ray's LMChat",
    "RayMiniBrowser":      "🌐 Ray's Mini Browser",
    "RayPromptIterator":   "🔄 Ray's Prompt Iterator",
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
