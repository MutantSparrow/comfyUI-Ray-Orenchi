import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("ray_button_deck", Path(__file__).resolve().parents[1] / "ray_button_deck.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ButtonDeckTests(unittest.TestCase):
    def test_one_entry_per_line_trimmed_without_blanks_or_repeats(self):
        text = "  alpha \r\n\r\nbeta\n\t\nalpha\ngamma  \n"
        self.assertEqual(module.parse_entries(text), ["alpha", "beta", "gamma"])

    def test_entries_are_capped(self):
        text = "\n".join(f"item {i}" for i in range(200))
        self.assertEqual(len(module.parse_entries(text)), module.MAX_ENTRIES)

    def test_outputs_the_selected_entry(self):
        node = module.RayButtonDeck()
        self.assertEqual(node.process("one\ntwo\nthree", "two"), ("two",))
        self.assertEqual(node.process("one\ntwo\nthree", "  three "), ("three",))

    def test_unknown_or_empty_selection_falls_back_to_first_entry(self):
        node = module.RayButtonDeck()
        self.assertEqual(node.process("one\ntwo", ""), ("one",))
        self.assertEqual(node.process("one\ntwo", "removed"), ("one",))
        self.assertEqual(node.process("one\ntwo", None), ("one",))

    def test_selection_follows_the_value_when_entries_are_reordered(self):
        node = module.RayButtonDeck()
        self.assertEqual(node.process("a\nb\nc", "c"), ("c",))
        self.assertEqual(node.process("c\na\nb", "c"), ("c",))
        self.assertEqual(node.process("x\nc\na", "c"), ("c",))

    def test_values_are_passed_through_untouched(self):
        node = module.RayButtonDeck()
        self.assertEqual(node.process("a photo of a fox, 8k\nfoo: bar | baz", "foo: bar | baz"), ("foo: bar | baz",))

    def test_empty_deck_is_an_error(self):
        with self.assertRaisesRegex(ValueError, "no entries"):
            module.RayButtonDeck().process(" \n\n ", "")

    def test_declares_a_string_output_and_two_inputs(self):
        spec = module.RayButtonDeck.INPUT_TYPES()["required"]
        self.assertEqual(list(spec), ["entries", "selected"])
        self.assertEqual(module.RayButtonDeck.RETURN_TYPES, ("STRING",))
        self.assertTrue(spec["entries"][1]["multiline"])


if __name__ == "__main__":
    unittest.main()
