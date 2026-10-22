"""Import failures must retain their original cause and never retry sys.path."""
import ast
import importlib
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

SOURCE = (Path(__file__).resolve().parents[1] / "__init__.py").read_text(encoding="utf-8")
NODE_MODULES = ast.literal_eval(next(node.value for node in ast.parse(SOURCE).body
                                   if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "_NODE_MODULES" for t in node.targets)))


@pytest.mark.parametrize("package", ["ray_pack", ""])
@pytest.mark.parametrize("failure", [ImportError("missing pixel dependency"), TypeError("internal initialization failure")])
def test_original_import_failure_propagates(package, failure):
    calls = []
    def load(name, parent=None):
        calls.append((name, parent))
        raise failure
    with patch.object(importlib, "import_module", load):
        with pytest.raises(type(failure)) as caught:
            exec(compile(SOURCE, "__init__.py", "exec"), {"__package__": package})
    assert caught.value is failure
    assert calls == [(".ray_save_image", package) if package else ("ray_save_image", None)]


@pytest.mark.parametrize("package", ["ray_pack", ""])
def test_import_mode_and_stable_ids(package):
    calls = []
    registered = []
    def load(name, parent=None):
        calls.append((name, parent))
        basename = name.lstrip(".")
        contents = {key: object() for key, value in NODE_MODULES.items() if value == basename}
        return SimpleNamespace(**contents, register_routes=lambda: registered.append(True))
    namespace = {"__package__": package}
    with patch.object(importlib, "import_module", load):
        exec(compile(SOURCE, "__init__.py", "exec"), namespace)
    assert set(namespace["NODE_CLASS_MAPPINGS"]) == {
        "RaySaveImage", "RayFolders", "RayCRT", "RayOffsetPrint", "RayPixelArtDetector",
        "RayKnob", "RaySwitch", "RayButtonDeck", "RayFaderBank", "RayTextFolder",
        "RayVLMFolder", "RayFastQwen3VL", "RayPromptFetcher", "RayMetaInspect", "RayFilmStock", "RayVHS"}
    assert all(name.startswith(".") == bool(package) for name, _ in calls)
    assert len(calls) == len(NODE_MODULES) + (5 if package else 0)
    assert registered == ([True] if package else [])
