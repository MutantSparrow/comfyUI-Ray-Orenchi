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
        for global_disable, node_disable in ((False, True), (True, False)):
            cli.args.disable_metadata = global_disable
            result = self.run_save(save_without_metadata=node_disable)
            with Image.open(result["ray_saved"][0]) as image:
                self.assertNotIn("prompt", image.info)
                self.assertNotIn("workflow", image.info)

    def test_optional_second_input(self):
        self.assertEqual(len(self.node.save(self.one, save_image="both")["ui"]["ray_saved"]), 1)
        with self.assertRaisesRegex(ValueError, "Connect image_2"):
            self.node.save(self.one, save_image="2")

    def test_folder_paths_and_prefix_boundary(self):
        result = self.run_save(directory="nested/folder")
        self.assertEqual(Path(result["ray_saved"][0]).parent, self.root / "output/nested/folder")
        absolute = self.root / "chosen elsewhere"
        result = self.run_save(directory=str(absolute))
        self.assertEqual(Path(result["ray_saved"][0]).parent, absolute)
        for prefix in ("../escape", "C:\\escape", "name:stream", "bad\x00name"):
            with self.assertRaises(ValueError): self.run_save(filename_prefix=prefix)
        with self.assertRaises(ValueError): self.run_save(save_image="invalid")

    def test_folder_listing_only_directories(self):
        self.run_save()
        (self.root / "output" / "Child").mkdir()
        result = module.list_directories("")
        self.assertEqual([f["name"] for f in result["folders"]], ["Child"])
        self.assertEqual(result["path"], str((self.root / "output").resolve()))

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
