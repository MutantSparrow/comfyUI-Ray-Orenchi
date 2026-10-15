MIN_FADERS = 2
MAX_FADERS = 10        # in a row
MAX_ROWS = 4
TOTAL_FADERS = MAX_FADERS * MAX_ROWS
DEFAULT_FADERS = 4
DEFAULT_LEVEL = 0.5


def clamp_count(value) -> int:
    try:
        count = int(value)
    except (TypeError, ValueError):
        count = DEFAULT_FADERS
    return max(MIN_FADERS, min(MAX_FADERS, count))


def clamp_rows(value) -> int:
    try:
        rows = int(value)
    except (TypeError, ValueError):
        rows = 1
    return max(1, min(MAX_ROWS, rows))


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
        "A bank of analog faders: 2 to 10 in a row, and up to 4 rows. Each fader is a vertical "
        "slider that outputs a float from 0 to 1.\n\n"
        "Set `faders` to the number in a row and `rows` to the number of rows (6 faders and 2 rows "
        "make 12); the node shows one output per fader, numbered row by row, and hides the rest. "
        "`values` carries every active fader as a list, in order, for nodes that take a list. "
        "Drag a fader, click its track, use the arrow keys, or turn on Mouse wheel control in "
        "the right-click menu and scroll over a fader. Right-click also picks the "
        "style, mutes the sound and edits the Dymo label."
    )

    @classmethod
    def INPUT_TYPES(cls):
        required = {
            "faders": ("INT", {"default": DEFAULT_FADERS, "min": MIN_FADERS, "max": MAX_FADERS, "step": 1,
                               "tooltip": "How many faders in a row (2 to 10). Only the active faders' outputs are shown."}),
        }

        def level(i):
            return ("FLOAT", {"default": DEFAULT_LEVEL, "min": 0.0, "max": 1.0, "step": 0.001,
                              "tooltip": f"Fader {i} position, 0 to 1 (driven by the bank)."})
        for i in range(1, MAX_FADERS + 1):
            required[f"fader_{i}"] = level(i)
        # After the first row's faders, so workflows saved before rows existed load their values in place.
        required["rows"] = ("INT", {"default": 1, "min": 1, "max": MAX_ROWS, "step": 1,
                                    "tooltip": "How many rows of faders (1 to 4); each row has `faders` faders."})
        for i in range(MAX_FADERS + 1, TOTAL_FADERS + 1):
            required[f"fader_{i}"] = level(i)
        return {"required": required}

    RETURN_TYPES = ("FLOAT",) * (TOTAL_FADERS + 1)
    RETURN_NAMES = ("values",) + tuple(f"fader_{i}" for i in range(1, TOTAL_FADERS + 1))
    OUTPUT_IS_LIST = (True,) + (False,) * TOTAL_FADERS
    OUTPUT_TOOLTIPS = ("Every active fader, in order, as a list of floats from 0 to 1.",) + tuple(
        f"Fader {i}, 0 to 1." for i in range(1, TOTAL_FADERS + 1))
    FUNCTION = "process"
    CATEGORY = "👑 Ray/🎛️ Analog"

    def process(self, faders, rows=1, **levels):
        count = clamp_count(faders) * clamp_rows(rows)
        positions = [clamp_level(levels.get(f"fader_{i}", DEFAULT_LEVEL)) for i in range(1, TOTAL_FADERS + 1)]
        return (positions[:count], *positions)
