class RaySwitch:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "state": ("BOOLEAN", {"default": False}),
            }
        }

    RETURN_TYPES = ("BOOLEAN",)
    RETURN_NAMES = ("bool",)
    FUNCTION = "process"
    CATEGORY = "Ray/Analog🎛️"

    def process(self, state):
        return (bool(state),)
