import importlib.util
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("ray_txt_folder", Path(__file__).resolve().parents[1] / "ray_txt_folder.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class TextFolderTests(unittest.TestCase):
    def test_pairing_preserves_text_and_skips_empty(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            (folder / "b.TXT").write_bytes(b"second\r\nparagraph\r\n")
            (folder / "a.txt").write_bytes(b"\xef\xbb\xbffirst\n\nparagraph")
            (folder / "c.txt").write_text("  \n")
            (folder / "ignore.png").write_bytes(b"image")
            (folder / "nested").mkdir()
            (folder / "nested" / "ignored.txt").write_text("nested")
            prompts, names = module.RayTextFolder().load(directory, 0, -1, "renders/")
            self.assertEqual(prompts, ["first\n\nparagraph", "second\r\nparagraph\r\n"])
            self.assertEqual(names, ["renders/a", "renders/b"])

    def test_range_and_refresh(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            (folder / "a.txt").write_text("a")
            (folder / "b.txt").write_text("b")
            node = module.RayTextFolder()
            self.assertEqual(node.load(directory, 1, 1, ""), (["b"], ["b"]))
            (folder / "b.txt").write_text("updated")
            self.assertEqual(node.load(directory, 1, 1, ""), (["updated"], ["b"]))
            with self.assertRaisesRegex(ValueError, "No non-empty"):
                node.load(directory, 0, 0, "")

    def test_blank_directory_rejected(self):
        with self.assertRaisesRegex(ValueError, "Enter a folder"):
            module.RayTextFolder().load("", 0, -1, "")


if __name__ == "__main__":
    unittest.main()
