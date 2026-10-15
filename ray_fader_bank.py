MIN_FADERS = 2
MAX_FADERS = 10
DEFAULT_FADERS = 4
DEFAULT_LEVEL = 0.5


def clamp_count(value) -> int:
    try:
        count = int(value)
    except (TypeError, ValueError):
        count = DEFAULT_FADERS
    return max(MIN_FADERS, min(MAX_FADERS, count))


def clamp_level(value) -> float:
    """A fader position as a float in 0..1; anything that is not a number falls back to the default."""
    try:
        level = float(value)
    except (TypeError, ValueError):
        return DEFAULT_LEVEL
    if level != level:   # NaN
        return DEFAULT_LEVEL
    return max(0.0, min(1.0, level))


class RayFaderBank:
    DESCRIPTION = (
        "A bank of 2 to 10 analog faders. Each fader is a vertical slider that outputs a float "
        "from 0 to 1.\n\n"
        "Set `faders` to the number you want; the node shows one output per fader and hides the "
        "rest. `values` carries every active fader as a list, in order, for nodes that take a "
        "list. Drag a fader, click its track, use the arrow keys, or turn on Mouse wheel "
        "control in the right-click menu and scroll over a fader. Right-click also picks the "
        "style, mutes the sound and edits the Dymo label."
    )

    @classmethod
    def INPUT_TYPES(cls):
        required = {
            "faders": ("INT", {"default": DEFAULT_FADERS, "min": MIN_FADERS, "max": MAX_FADERS, "step": 1,
                               "tooltip": "How many faders the bank has (2 to 10). Only that many outputs are shown."}),
        }
        for i in range(1, MAX_FADERS + 1):
            required[f"fader_{i}"] = ("FLOAT", {"default": DEFAULT_LEVEL, "min": 0.0, "max": 1.0, "step": 0.001,
                                                 "tooltip": f"Fader {i} position, 0 to 1 (driven by the bank)."})
        return {"required": required}

    RETURN_TYPES = ("FLOAT",) * (MAX_FADERS + 1)
    RETURN_NAMES = ("values",) + tuple(f"fader_{i}" for i in range(1, MAX_FADERS + 1))
    OUTPUT_IS_LIST = (True,) + (False,) * MAX_FADERS
    OUTPUT_TOOLTIPS = ("Every active fader, in order, as a list of floats from 0 to 1.",) + tuple(
        f"Fader {i}, 0 to 1." for i in range(1, MAX_FADERS + 1))
    FUNCTION = "process"
    CATEGORY = "👑 Ray/🎛️ Analog"

    def process(self, faders, **levels):
        count = clamp_count(faders)
        positions = [clamp_level(levels.get(f"fader_{i}", DEFAULT_LEVEL)) for i in range(1, MAX_FADERS + 1)]
        return (positions[:count], *positions)
