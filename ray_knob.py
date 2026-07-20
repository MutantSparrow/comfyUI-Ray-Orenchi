import math


class RayKnob:
    DESCRIPTION = (
        "Analog-style float knob widget. Drag rotates the knob face; "
        "outputs both an INT (quantized by `clamp`) and a raw FLOAT so it "
        "plugs into either side without a converter.\n\n"
        "Right-click for style picker (brushed-metal, black-plastic, "
        "bakelite, brass…), Compact mode (chromeless), and Edit label. "
        "The Dymo tape above the face is double-click editable and is "
        "saved with the workflow."
    )

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "min_value":      ("FLOAT",   {"default": -100.0, "min": -1e9, "max": 1e9, "step": 0.1,
                                                "tooltip": "Range minimum."}),
                "max_value":      ("FLOAT",   {"default":  100.0, "min": -1e9, "max": 1e9, "step": 0.1,
                                                "tooltip": "Range maximum."}),
                "spin_value":     ("FLOAT",   {"default":   20.0, "min": 10.0, "max": 100.0, "step": 0.1,
                                                "tooltip": "Drag sensitivity in px per full sweep."}),
                "clamp":          ("FLOAT",   {"default":    0.0, "min":  0.0, "max": 1024.0, "step": 0.1,
                                                "tooltip": "Quantization step for the INT output. 0 truncates."}),
                "allow_negative": ("BOOLEAN", {"default": True,
                                                "tooltip": "Whether min_value may go below 0."}),
                "knob_value":     ("FLOAT",   {"default":    0.0, "min": -1e12, "max": 1e12, "step": 0.0001,
                                                "tooltip": "Current knob value (driven by the widget)."}),
            }
        }

    RETURN_TYPES = ("INT", "FLOAT")
    RETURN_NAMES = ("int", "float")
    OUTPUT_TOOLTIPS = (
        "Knob value quantized to `clamp` steps.",
        "Raw knob value clamped to [min_value, max_value].",
    )
    FUNCTION = "process"
    CATEGORY = "👑 Ray/🎛️ Analog"

    def process(self, min_value, max_value, spin_value, clamp, allow_negative, knob_value):
        lo = float(min_value) if allow_negative else max(0.0, float(min_value))
        hi = float(max_value)
        if hi < lo:
            hi = lo
        f = max(lo, min(hi, float(knob_value)))

        if clamp <= 0.0:
            i = int(math.trunc(f))
        else:
            i = int(math.floor(f / clamp) * clamp)
        return (i, f)
