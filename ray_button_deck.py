MAX_ENTRIES = 64
DEFAULT_ENTRIES = "Option A\nOption B\nOption C"


def parse_entries(text) -> list:
    """One entry per line: trimmed, blank lines dropped, repeats ignored, order kept."""
    seen = set()
    entries = []
    for line in str(text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = line.strip()
        if line and line not in seen:
            seen.add(line)
            entries.append(line)
    return entries[:MAX_ENTRIES]


class RayButtonDeck:
    DESCRIPTION = (
        "A deck of analog push buttons that replaces a dropdown. Enter one "
        "value per line; each line becomes a button and the pressed button's "
        "text is the output.\n\n"
        "Size the node however you like: the buttons take the grid that "
        "makes them biggest, a row in a wide node, 2 x 2 in a square one, a "
        "column in a tall one. Use the pencil next to Entries (or right-click) "
        "to change the list. Right-click also picks the button style, turns on "
        "Compact mode (the faceplate alone), mutes the sound, and edits the "
        "Dymo label. The pressed button stays lit and the others stay unlit."
    )

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "entries":  ("STRING", {"multiline": True, "default": DEFAULT_ENTRIES,
                                         "tooltip": "One value per line. Each line becomes a button. "
                                                    "Blank lines and repeated lines are ignored."}),
                "selected": ("STRING", {"default": "",
                                         "tooltip": "The pressed button's text (driven by the deck). "
                                                    "If it isn't in the list, the first entry is used."}),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("value",)
    OUTPUT_TOOLTIPS = ("The text of the pressed button.",)
    FUNCTION = "process"
    CATEGORY = "👑 Ray/🎛️ Analog"

    def process(self, entries, selected):
        items = parse_entries(entries)
        if not items:
            raise ValueError("Button Deck has no entries. Add one value per line.")
        chosen = str(selected or "").strip()
        return (chosen if chosen in items else items[0],)
