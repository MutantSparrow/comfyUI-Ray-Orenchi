"""Run directly with ComfyUI Python; does not start ComfyUI or load models."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
paths = types.ModuleType("folder_paths")
cli = types.ModuleType("comfy.cli_args")
cli.args = types.SimpleNamespace(disable_metadata=False)
originals = {name: sys.modules.get(name) for name in ("folder_paths", "comfy.cli_args")}
sys.modules["folder_paths"] = paths
sys.modules["comfy.cli_args"] = cli
spec = importlib.util.spec_from_file_location("ray_save_image", ROOT / "ray_save_image.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
for name, original in originals.items():
    if original is None:
        sys.modules.pop(name, None)
    else:
        sys.modules[name] = original


class Tensor:
    def __init__(self, values): self.values = values
    def detach(self): return self
    def cpu(self): return self
    def float(self): return self
    def numpy(self): return self.values


class SaveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        paths.get_output_directory = lambda: str(self.root / "output")
        paths.get_temp_directory = lambda: str(self.root / "temp")
        cli.args.disable_metadata = False
        self.one = [Tensor(np.full((5, 9, 3), .5, dtype=np.float32))]
        self.two = [Tensor(np.ones((9, 5, 4), dtype=np.float32))] * 2
        self.node = module.RaySaveImage()

    def run_save(self, **kwargs):
        return self.node.save(self.one, image_2=self.two, prompt={"test": 1},
                              extra_pnginfo={"workflow": {"nodes": []}}, **kwargs)["ui"]

    def test_selection_and_preview_batches(self):
        for mode, count in (("none", 0), ("1", 1), ("2", 2), ("both", 3)):
            with self.subTest(mode=mode):
                result = self.run_save(save_image=mode)
                self.assertEqual(len(result["ray_saved"]), count)
                self.assertEqual(len(result["ray_images_1"]), 1)
                self.assertEqual(len(result["ray_images_2"]), 2)
                for item in result["ray_images_1"] + result["ray_images_2"]:
                    with Image.open(self.root / "temp" / item["subfolder"] / item["filename"]) as image:
                        self.assertNotIn("prompt", image.info)
                        self.assertNotIn("workflow", image.info)

    def test_none_creates_no_destination(self):
        result = self.run_save(save_image="none", directory=str(self.root / "unused"), filename_prefix="ignored/path")
        self.assertFalse((self.root / "unused").exists())
        self.assertEqual(result["ray_directory"], [])

    def test_pixels_metadata_and_collision(self):
        first = self.run_save()["ray_saved"][0]
        second = self.run_save()["ray_saved"][0]
        self.assertNotEqual(first, second)
        with Image.open(first) as image:
            self.assertEqual(image.size, (9, 5))
            self.assertTrue(np.all(np.asarray(image) == 127))
            self.assertEqual(json.loads(image.info["prompt"]), {"test": 1})
            self.assertIn("workflow", image.info)

    def test_metadata_omission_and_global_override(self):
        for metadata in (None, "custom metadata"):
            for global_disable, node_disable in ((False, True), (True, False), (True, True)):
                with self.subTest(metadata=metadata, global_disable=global_disable, node_disable=node_disable):
                    cli.args.disable_metadata = global_disable
                    result = self.run_save(save_without_metadata=node_disable, metadata=metadata)
                    with Image.open(result["ray_saved"][0]) as image:
                        self.assertEqual(image.text, {})

    def test_custom_metadata_replaces_defaults_verbatim_for_both_batches(self):
        for text in ("a cat\nNegative prompt: blur\nSteps: 20, Seed: 42",
                     '  {"caption": "猫 🐈", "seed": 42}\n  '):
            with self.subTest(text=text):
                result = self.run_save(save_image="both", metadata=text)
                self.assertEqual(len(result["ray_saved"]), 3)
                for saved in result["ray_saved"]:
                    with Image.open(saved) as image:
                        self.assertEqual(image.text, {"parameters": text})
                for item in result["ray_images_1"] + result["ray_images_2"]:
                    with Image.open(self.root / "temp" / item["subfolder"] / item["filename"]) as image:
                        self.assertEqual(image.text, {})

    def test_connected_empty_metadata_replaces_defaults(self):
        result = self.run_save(metadata="")
        with Image.open(result["ray_saved"][0]) as image:
            self.assertEqual(image.text, {"parameters": ""})

    def test_unconnected_metadata_preserves_all_default_chunks(self):
        extra = {"workflow": {"nodes": []}, "custom": ["value"], "parameters": "existing"}
        result = self.node.save(self.one, prompt={"test": 1}, extra_pnginfo=extra)
        with Image.open(result["ui"]["ray_saved"][0]) as image:
            self.assertEqual(image.text, {key: json.dumps(value) for key, value in
                                         {"prompt": {"test": 1}, **extra}.items()})

    def test_optional_second_input(self):
        self.assertEqual(len(self.node.save(self.one, save_image="both")["ui"]["ray_saved"]), 1)
        with self.assertRaisesRegex(ValueError, "Connect image_2"):
            self.node.save(self.one, save_image="2")

    def test_folder_paths_and_prefix_boundary(self):
        result = self.run_save(directory="nested/folder")
        # Compare canonical paths: Windows can hand out the 8.3 short form of the temp folder.
        self.assertEqual(Path(result["ray_saved"][0]).parent.resolve(), (self.root / "output/nested/folder").resolve())
        absolute = self.root / "chosen elsewhere"
        result = self.run_save(directory=str(absolute))
        self.assertEqual(Path(result["ray_saved"][0]).parent.resolve(), absolute.resolve())
        # A prefix is a filename, never a second way to choose the folder: reserved characters are replaced.
        for prefix, stem in (("../escape", "_escape"), ("C:\\escape", "C__escape"), ("name:stream", "name_stream"), ("bad\x00name", "bad_name")):
            saved = Path(self.run_save(filename_prefix=prefix, directory=str(absolute))["ray_saved"][0])
            self.assertEqual(saved.parent.resolve(), absolute.resolve())
            self.assertEqual(saved.name, stem + ".png")
        with self.assertRaises(ValueError): self.run_save(save_image="invalid")

    def saved_names(self, **kwargs):
        kwargs.setdefault("directory", str(self.root / "named"))
        kwargs.setdefault("prompt", {})
        result = self.node.save(self.one, image_2=self.two, extra_pnginfo={}, **kwargs)
        return [Path(p).name for p in result["ui"]["ray_saved"]]

    def test_the_default_name_is_the_date_and_a_counter(self):
        first, second = self.saved_names(), self.saved_names()
        self.assertRegex(first[0], r"^Ray_\d{4}-\d{2}-\d{2}_0001\.png$")
        self.assertRegex(second[0], r"^Ray_\d{4}-\d{2}-\d{2}_0002\.png$")
        self.assertRegex(self.saved_names(filename_prefix="   ")[0], r"^Ray_\d{4}-\d{2}-\d{2}_0003\.png$")   # blank means the default

    def test_a_file_is_saved_as_exactly_the_prefix_and_the_extension(self):
        self.assertEqual(self.saved_names(filename_prefix="shot"), ["shot.png"])
        self.assertEqual(self.saved_names(filename_prefix="shot"), ["shot-2.png"])     # never overwritten
        self.assertEqual(self.saved_names(filename_prefix="  my shot?  "), ["my_shot_.png"])

    def test_tokens_name_each_image_of_each_input(self):
        self.assertEqual(self.saved_names(save_image="both", filename_prefix="p_{input}_{index}"), ["p_1_1.png", "p_2_1.png", "p_2_2.png"])
        self.assertEqual(self.saved_names(save_image="both", filename_prefix="p"), ["p.png", "p-2.png", "p-3.png"])
        self.assertEqual(self.saved_names(save_image="both", filename_prefix="{counter:2}_{input}"), ["01_1.png", "01_2.png", "02_2.png"])      # a counter counts files that share the rest of the name

    def test_widget_values_come_from_the_queued_graph(self):
        prompt = {"5": {"inputs": {"seed": 99, "text": "a cat / a dog?"}}, "6": {"inputs": {"seed": ["5", 0]}}}
        self.assertEqual(self.saved_names(prompt=prompt, filename_prefix="s{widget:5.seed}_{widget:5.text}"), ["s99_a_cat_a_dog.png"])
        self.assertEqual(self.saved_names(prompt=prompt, filename_prefix="v{widget:6.seed}"), ["v.png"])      # a link has no value yet
        self.assertEqual(self.saved_names(prompt=prompt, filename_prefix="m{widget:77.nothing}"), ["m.png"])
        self.assertEqual(self.saved_names(prompt=None, filename_prefix="n{widget:5.seed}"), ["n.png"])

    def test_a_bad_template_is_reported_and_only_matters_when_saving(self):
        with self.assertRaisesRegex(ValueError, "Unknown filename token"):
            self.saved_names(filename_prefix="{nope}")
        self.assertEqual(self.saved_names(save_image="none", filename_prefix="{nope}"), [])
        self.assertFalse((self.root / "named").exists() and any((self.root / "named").iterdir()))

    def test_explorer_opens_only_existing_folder(self):
        self.run_save()
        launch = Mock()
        with patch.object(module, "os", types.SimpleNamespace(name="nt", startfile=launch)):
            module.open_image_location(str(self.root / "output"))
            launch.assert_called_once_with(str((self.root / "output").resolve()), "explore")

    def test_explorer_rejects_files_missing_and_empty_paths(self):
        saved = self.run_save()["ray_saved"][0]
        launch = Mock()
        with patch.object(module, "os", types.SimpleNamespace(name="nt", startfile=launch)):
            for value in (saved, str(self.root / "missing"), "", None):
                with self.assertRaises(ValueError): module.open_image_location(value)
            launch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
