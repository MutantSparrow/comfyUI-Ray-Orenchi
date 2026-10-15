import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("ray_fader_bank", Path(__file__).resolve().parents[1] / "ray_fader_bank.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def levels(**changes):
    values = {f"fader_{i}": 0.5 for i in range(1, 11)}
    values.update(changes)
    return values


class FaderBankTests(unittest.TestCase):
    def test_declares_a_count_and_ten_float_faders(self):
        required = module.RayFaderBank.INPUT_TYPES()["required"]
        self.assertEqual(required["faders"][1]["min"], 2)
        self.assertEqual(required["faders"][1]["max"], 10)
        for i in range(1, 11):
            kind, options = required[f"fader_{i}"]
            self.assertEqual(kind, "FLOAT")
            self.assertEqual((options["min"], options["max"]), (0.0, 1.0))

    def test_outputs_are_the_list_then_one_float_per_fader(self):
        node = module.RayFaderBank
        self.assertEqual(node.RETURN_TYPES, ("FLOAT",) * 11)
        self.assertEqual(node.RETURN_NAMES[:3], ("values", "fader_1", "fader_2"))
        self.assertEqual(node.OUTPUT_IS_LIST, (True,) + (False,) * 10)
        self.assertEqual(len(node.OUTPUT_TOOLTIPS), 11)

    def test_values_lists_only_the_active_faders_in_order(self):
        out = module.RayFaderBank().process(3, **levels(fader_1=0.1, fader_2=0.2, fader_3=0.3, fader_4=0.9))
        self.assertEqual(out[0], [0.1, 0.2, 0.3])
        self.assertEqual(out[1:4], (0.1, 0.2, 0.3))
        self.assertEqual(len(out), 11)

    def test_every_fader_output_carries_its_own_position(self):
        out = module.RayFaderBank().process(10, **{f"fader_{i}": i / 10 for i in range(1, 11)})
        self.assertEqual(list(out[1:]), [i / 10 for i in range(1, 11)])
        self.assertEqual(out[0], list(out[1:]))

    def test_the_count_is_kept_between_two_and_ten(self):
        node = module.RayFaderBank()
        self.assertEqual(len(node.process(0, **levels())[0]), 2)
        self.assertEqual(len(node.process(2, **levels())[0]), 2)
        self.assertEqual(len(node.process(99, **levels())[0]), 10)
        self.assertEqual(len(node.process("junk", **levels())[0]), module.DEFAULT_FADERS)
        self.assertEqual(len(node.process(None, **levels())[0]), module.DEFAULT_FADERS)

    def test_positions_are_clamped_to_zero_to_one(self):
        out = module.RayFaderBank().process(4, **levels(fader_1=-3, fader_2=7, fader_3=float("nan"), fader_4="oops"))
        self.assertEqual(out[0], [0.0, 1.0, 0.5, 0.5])

    def test_missing_positions_fall_back_to_the_middle(self):
        out = module.RayFaderBank().process(3)
        self.assertEqual(out[0], [0.5, 0.5, 0.5])

    def test_registered_in_the_analog_category(self):
        self.assertEqual(module.RayFaderBank.CATEGORY, "👑 Ray/🎛️ Analog")
        self.assertEqual(module.RayFaderBank.FUNCTION, "process")


if __name__ == "__main__":
    unittest.main()
