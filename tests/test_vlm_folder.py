import importlib.util
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import torch
from PIL import Image


def load_module():
    management = types.ModuleType("comfy.model_management")
    management.get_torch_device = Mock(return_value=torch.device("cuda:0"))
    management.throw_exception_if_processing_interrupted = Mock()
    sd = types.ModuleType("comfy.sd")
    sd.CLIPType = types.SimpleNamespace(QWEN_IMAGE="qwen_image")
    sd.load_clip = Mock()
    comfy = types.ModuleType("comfy")
    comfy.sd = sd
    comfy.model_management = management
    utils = types.ModuleType("comfy.utils")
    utils.ProgressBar = Mock()
    folders = types.ModuleType("folder_paths")
    folders.get_filename_list = Mock(return_value=["vlm.safetensors"])
    folders.get_full_path_or_raise = Mock(return_value="vlm.safetensors")
    folders.get_folder_paths = Mock(return_value=[])
    modules = {"comfy": comfy, "comfy.sd": sd, "comfy.model_management": management,
               "comfy.utils": utils, "folder_paths": folders}
    spec = importlib.util.spec_from_file_location("ray_vlm_folder", Path(__file__).resolve().parents[1] / "ray_vlm_folder.py")
    module = importlib.util.module_from_spec(spec)
    with patch.dict("sys.modules", modules):
        spec.loader.exec_module(module)
    return module


class VLMFolderTests(unittest.TestCase):
    def setUp(self):
        self.module = load_module()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        Image.new("RGB", (8, 4), "red").save(self.folder / "a.png")
        Image.new("RGB", (3, 9), "blue").save(self.folder / "b.png")
        self.clip = Mock()
        self.clip.patcher.load_device = torch.device("cuda:0")
        self.clip.tokenize.side_effect = lambda text, **kw: {"vlm": [[({"type": "image", "data": kw["image"]}, 1.0)]]}
        self.clip.decode.side_effect = ["first answer\n", "second answer"]
        self.module.comfy.sd.load_clip.return_value = self.clip
        self.args = dict(clip_name="vlm.safetensors", folder=str(self.folder), recurse_subfolders=False,
                         start_index=0, limit=-1, user_prompt="Describe exactly.", max_length=321,
                         temperature=0.25, top_k=17, top_p=0.8, min_p=0.1,
                         repetition_penalty=1.2, seed=42, thinking=True)

    def test_per_image_inference_and_paired_outputs(self):
        texts, images, paths = self.module.RayVLMFolder().process(**self.args)
        self.assertEqual(texts, ["first answer\n", "second answer"])
        self.assertEqual([Path(p).name for p in paths], ["a.png", "b.png"])
        self.assertEqual([tuple(i.shape) for i in images], [(1, 4, 8, 3), (1, 9, 3, 3)])
        self.assertEqual(images[0][0, 0, 0].tolist(), [1., 0., 0.])
        self.assertEqual(images[1][0, 0, 0].tolist(), [0., 0., 1.])
        self.assertEqual(self.module.comfy.sd.load_clip.call_count, 1)
        self.assertEqual(self.clip.generate.call_count, 2)
        for call in self.clip.tokenize.call_args_list:
            self.assertEqual(call.args[0], self.args["user_prompt"])
            self.assertFalse(call.kwargs["skip_template"])
            self.assertTrue(call.kwargs["thinking"])
        self.assertEqual(self.clip.generate.call_args.kwargs, dict(do_sample=True, max_length=321,
                         temperature=0.25, top_k=17, top_p=0.8, min_p=0.1, repetition_penalty=1.2, seed=42))
        self.assertEqual(list(self.folder.glob("*.txt")), [])

    def test_scan_recursion_range_and_refresh(self):
        sub = self.folder / "sub"
        sub.mkdir()
        Image.new("RGB", (2, 2)).save(sub / "c.JPG")
        scan = self.module.image_files
        self.assertEqual(len(scan(self.folder, False, 0, -1)), 2)
        self.assertEqual([p.name for p in scan(self.folder, True, 1, 2)], ["b.png", "c.JPG"])
        with self.assertRaisesRegex(ValueError, "No supported"):
            scan(self.folder, True, 3, -1)

    def test_cpu_and_cpu_fallback_rejected(self):
        self.module.model_management.get_torch_device.return_value = torch.device("cpu")
        with self.assertRaisesRegex(RuntimeError, "GPU inference"):
            self.module.RayVLMFolder().process(**self.args)
        self.module.comfy.sd.load_clip.assert_not_called()
        self.module.model_management.get_torch_device.return_value = torch.device("cuda:0")
        self.clip.patcher.load_device = torch.device("cpu")
        with self.assertRaisesRegex(RuntimeError, "fell back"):
            self.module.RayVLMFolder().process(**self.args)

    def test_missing_vision_tokens_and_empty_answer_rejected(self):
        self.clip.tokenize.side_effect = None
        self.clip.tokenize.return_value = {"text": [[(12, 1.0)]]}
        with self.assertRaisesRegex(ValueError, "No image tokens"):
            self.module.RayVLMFolder().process(**self.args)
        self.clip.generate.assert_not_called()
        self.clip.tokenize.return_value = {"vlm": [[({"type": "image"}, 1.0)]]}
        self.clip.decode.side_effect = [" "]
        with self.assertRaisesRegex(RuntimeError, "empty answer for a.png"):
            self.module.RayVLMFolder().process(**self.args)

    def test_interrupt_stops_before_loading(self):
        self.module.model_management.throw_exception_if_processing_interrupted.side_effect = RuntimeError("cancelled")
        with self.assertRaisesRegex(RuntimeError, "cancelled"):
            self.module.RayVLMFolder().process(**self.args)
        self.module.comfy.sd.load_clip.assert_not_called()

    def test_greedy_and_random_seed(self):
        self.args.update(temperature=0, seed=-1, limit=1)
        with patch.object(self.module.secrets, "randbelow", return_value=123):
            self.module.RayVLMFolder().process(**self.args)
        self.assertFalse(self.clip.generate.call_args.kwargs["do_sample"])
        self.assertEqual(self.clip.generate.call_args.kwargs["seed"], 123)

    def test_schema_conventions(self):
        node = self.module.RayVLMFolder
        self.assertEqual(node.CATEGORY, "👑 Ray/💬 LLM")
        self.assertEqual(node.RETURN_NAMES, ("text", "image", "image_path"))
        for entry in node.INPUT_TYPES()["required"].values():
            self.assertIn("tooltip", entry[1])


if __name__ == "__main__":
    unittest.main()
