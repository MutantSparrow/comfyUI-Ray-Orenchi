class RaySwitch:
    DESCRIPTION = (
        "Analog-style boolean toggle. Click the switch face to flip "
        "state. Emits a single BOOLEAN output.\n\n"
        "Six physical styles (Chrome Rocker, Bakelite Flip, Silver "
        "Paddle, Brass Slider, Minimal Pill, Dark Studio Dome), each "
        "modeled with the correct on/off geometry. Right-click for style "
        "picker, Compact mode (hides the node title so the node looks "
        "like a bare analog appliance — chrome panel, Dymo label, and "
        "readout stay), and Edit label — the Dymo tape above the switch "
        "is double-click editable and persists with the workflow."
    )

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "state": ("BOOLEAN", {"default": False,
                                       "tooltip": "Analog toggle state."}),
            }
        }

    RETURN_TYPES = ("BOOLEAN",)
    RETURN_NAMES = ("bool",)
    OUTPUT_TOOLTIPS = ("Mirror of the toggle state.",)
    FUNCTION = "process"
    CATEGORY = "👑 Ray/🎛️ Analog"

    def process(self, state):
        return (bool(state),)
