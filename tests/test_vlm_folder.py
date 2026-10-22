import importlib.util
import tempfile
import types
import unittest
import weakref
from pathlib import Path
from unittest.mock import Mock, patch

import torch
from PIL import Image


def load_module():
    management = types.ModuleType("comfy.model_management")
    management.get_torch_device = Mock(return_value=torch.device("cuda:0"))
    management.throw_exception_if_processing_interrupted = Mock()
    management.get_free_memory = Mock(return_value=8 * 1024**3)
    management.soft_empty_cache = Mock()
    comfy = types.ModuleType("comfy")
    comfy.model_management = management
    utils = types.ModuleType("comfy.utils")
    utils.ProgressBar = Mock()
    modules = {"comfy": comfy, "comfy.model_management": management, "comfy.utils": utils}
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
        self.args = dict(clip=self.clip, folder=str(self.folder), recurse_subfolders=False,
                         start_index=0, limit=-1, user_prompt="Describe exactly.", max_length=321,
                         temperature=0.25, top_k=17, top_p=0.8, min_p=0.1,
                         repetition_penalty=1.2, seed=42, thinking=True)

    def test_per_image_inference_and_paired_outputs(self):
        texts, images, paths = self.module.RayVLMFolder().process(**self.args, return_images=True)
        self.assertEqual(texts, ["first answer\n", "second answer"])
        self.assertEqual([Path(p).name for p in paths], ["a.png", "b.png"])
        self.assertEqual([tuple(i.shape) for i in images], [(1, 4, 8, 3), (1, 9, 3, 3)])
        self.assertEqual(images[0][0, 0, 0].tolist(), [1., 0., 0.])
        self.assertEqual(images[1][0, 0, 0].tolist(), [0., 0., 1.])
        self.assertEqual(self.clip.generate.call_count, 2)
        for call in self.clip.tokenize.call_args_list:
            self.assertEqual(call.args[0], self.args["user_prompt"])
            self.assertFalse(call.kwargs["skip_template"])
            self.assertTrue(call.kwargs["thinking"])
        self.assertEqual(self.clip.generate.call_args.kwargs, dict(do_sample=True, max_length=321,
                         temperature=0.25, top_k=17, top_p=0.8, min_p=0.1, repetition_penalty=1.2, seed=42))
        self.assertEqual(list(self.folder.glob("*.txt")), [])

    def memory_clip(self, during_generate=None):
        refs = []
        def tokenize(text, **kwargs):
            self.assertTrue(all(ref() is None for ref in refs), "previous source image is retained")
            refs.append(weakref.ref(kwargs["image"]))
            return {"vlm": [[({"type": "image", "data": kwargs["image"]}, 1.0)]]}
        def generate(*args, **kwargs):
            if during_generate:
                during_generate()
            return torch.tensor([1, 2])
        clip = types.SimpleNamespace(patcher=self.clip.patcher, tokenize=tokenize,
                                     generate=generate, decode=lambda ids: "caption")
        return clip, refs

    def test_default_retains_no_source_tensors(self):
        clip, refs = self.memory_clip()
        self.args["clip"] = clip
        texts, images, paths = self.module.RayVLMFolder().process(**self.args)
        self.assertEqual(images, [])
        self.assertEqual(len(texts), 2)
        self.assertEqual(len(paths), 2)
        self.assertTrue(all(ref() is None for ref in refs))

    def test_images_decoded_only_after_inference_finishes(self):
        clip, refs = self.memory_clip()
        self.args["clip"] = clip
        original = self.module.load_image
        loads = []
        def load(path):
            loads.append((path.name, len(refs)))
            return original(path)
        with patch.object(self.module, "load_image", load):
            _, images, _ = self.module.RayVLMFolder().process(**self.args, return_images=True)
        self.assertEqual(loads, [("a.png", 0), ("b.png", 1), ("a.png", 2), ("b.png", 2)])
        self.assertEqual(len(images), 2)
        self.assertTrue(all(ref() is None for ref in refs))

    def test_periodic_and_memory_pressure_cleanup(self):
        for interval, free, expected in ((1, 8 * 1024**3, 3), (0, 8 * 1024**3, 1), (0, 100, 3)):
            clip, _ = self.memory_clip()
            self.args["clip"] = clip
            self.module.model_management.soft_empty_cache.reset_mock()
            self.module.model_management.get_free_memory.return_value = free
            self.module.RayVLMFolder().process(**self.args, cleanup_every=interval)
            self.assertEqual(self.module.model_management.soft_empty_cache.call_count, expected)

    def test_error_releases_transients_and_preserves_cause(self):
        clip, refs = self.memory_clip()
        clip.decode = lambda ids: (_ for _ in ()).throw(RuntimeError("decode failed"))
        self.args["clip"] = clip
        with self.assertRaisesRegex(RuntimeError, "decode failed"):
            self.module.RayVLMFolder().process(**self.args)
        self.assertTrue(all(ref() is None for ref in refs))
        self.module.model_management.soft_empty_cache.assert_called_once()

    def test_deleted_file_during_return_pass_reports_source(self):
        clip, _ = self.memory_clip(lambda: (self.folder / "a.png").unlink(missing_ok=True))
        self.args["clip"] = clip
        with self.assertRaisesRegex(RuntimeError, "Cannot read source image.*a.png"):
            self.module.RayVLMFolder().process(**self.args, return_images=True)

    def test_replaced_source_cannot_be_paired_with_its_old_caption(self):
        clip, _ = self.memory_clip(lambda: Image.new("RGB", (7, 7), "green").save(self.folder / "a.png"))
        self.args["clip"] = clip
        with self.assertRaisesRegex(RuntimeError, "Source image changed during captioning.*a.png"):
            self.module.RayVLMFolder().process(**self.args, return_images=True)

    def test_scan_recursion_range_and_refresh(self):
        sub = self.folder / "sub"
        sub.mkdir()
        Image.new("RGB", (2, 2)).save(sub / "c.JPG")
        scan = self.module.image_files
        self.assertEqual(len(scan(self.folder, False, 0, -1)), 2)
        self.assertEqual([p.name for p in scan(self.folder, True, 1, 2)], ["b.png", "c.JPG"])
        with self.assertRaisesRegex(ValueError, "No supported"):
            scan(self.folder, True, 3, -1)

    def test_cpu_and_cpu_clip_rejected(self):
        self.module.model_management.get_torch_device.return_value = torch.device("cpu")
        with self.assertRaisesRegex(RuntimeError, "GPU inference"):
            self.module.RayVLMFolder().process(**self.args)
        self.clip.tokenize.assert_not_called()
        self.module.model_management.get_torch_device.return_value = torch.device("cuda:0")
        self.clip.patcher.load_device = torch.device("cpu")
        with self.assertRaisesRegex(RuntimeError, "connected CLIP runs on CPU"):
            self.module.RayVLMFolder().process(**self.args)
        self.clip.tokenize.assert_not_called()

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

    def test_interrupt_stops_before_captioning(self):
        self.module.model_management.throw_exception_if_processing_interrupted.side_effect = RuntimeError("cancelled")
        with self.assertRaisesRegex(RuntimeError, "cancelled"):
            self.module.RayVLMFolder().process(**self.args)
        self.clip.tokenize.assert_not_called()

    def test_greedy_and_random_seed(self):
        self.args.update(temperature=0, seed=-1, limit=1)
        with patch.object(self.module.secrets, "randbelow", return_value=123):
            self.module.RayVLMFolder().process(**self.args)
        self.assertFalse(self.clip.generate.call_args.kwargs["do_sample"])
        self.assertEqual(self.clip.generate.call_args.kwargs["seed"], 123)

    def test_clip_is_a_socket_not_a_model_dropdown(self):
        required = self.module.RayVLMFolder.INPUT_TYPES()["required"]
        self.assertEqual(list(required)[0], "clip")
        self.assertEqual(required["clip"][0], "CLIP")
        self.assertNotIn("clip_name", required)

    def test_schema_conventions(self):
        node = self.module.RayVLMFolder
        self.assertEqual(node.CATEGORY, "👑 Ray/💬 LLM")
        self.assertEqual(node.RETURN_NAMES, ("text", "image", "image_path"))
        for entry in node.INPUT_TYPES()["required"].values():
            self.assertIn("tooltip", entry[1])


if __name__ == "__main__":
    unittest.main()
