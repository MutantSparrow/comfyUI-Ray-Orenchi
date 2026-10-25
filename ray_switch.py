class RaySwitch:
    DESCRIPTION = (
        "Analog-style boolean toggle. Click the switch face to flip "
        "state. Emits a single BOOLEAN output.\n\n"
        "Choose from 31 shared hardware styles with distinct on/off "
        "geometry. Right-click for the style "
        "picker, Compact mode (the faceplate alone: no title bar, pins "
        "or node background; drag it by its frame, links meet it under the "
        "face), and Edit label — the "
        "Dymo tape above the switch is double-click editable and "
        "persists with the workflow."
    )

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "state": ("BOOLEAN", {"default": False,
                                       "tooltip": "Switch output: on emits True and off emits False. Click the face or use Space or Enter to toggle."}),
            }
        }

    RETURN_TYPES = ("BOOLEAN",)
    RETURN_NAMES = ("bool",)
    OUTPUT_TOOLTIPS = ("Mirror of the toggle state.",)
    FUNCTION = "process"
    CATEGORY = "👑 Ray/🎛️ Analog"

    def process(self, state):
        return (bool(state),)
