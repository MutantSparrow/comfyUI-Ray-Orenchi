import math


class RayKnob:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "min_value":      ("FLOAT",   {"default": -100.0, "min": -1e9, "max": 1e9, "step": 0.1}),
                "max_value":      ("FLOAT",   {"default":  100.0, "min": -1e9, "max": 1e9, "step": 0.1}),
                "spin_value":     ("FLOAT",   {"default":   20.0, "min": 10.0, "max": 100.0, "step": 0.1}),
                "clamp":          ("FLOAT",   {"default":    0.0, "min":  0.0, "max": 1024.0, "step": 0.1}),
                "allow_negative": ("BOOLEAN", {"default": True}),
                "knob_value":     ("FLOAT",   {"default":    0.0, "min": -1e12, "max": 1e12, "step": 0.0001}),
            }
        }

    RETURN_TYPES = ("INT", "FLOAT")
    RETURN_NAMES = ("int", "float")
    FUNCTION = "process"
    CATEGORY = "Ray/Analog🎛️"

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
