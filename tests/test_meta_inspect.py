"""Tests for ray_meta_inspect — inspect + embed metadata round-trips."""

import json
import pathlib

import pytest
from PIL import Image, PngImagePlugin

import ray_meta_inspect as rmi


def _png(path, info=None, size=(8, 8), color="red"):
    img = Image.new("RGB", size, color=color)
    pi = PngImagePlugin.PngInfo()
    for k, v in (info or {}).items():
        pi.add_text(k, v)
    img.save(path, "PNG", pnginfo=pi)
    return path


def test_inspect_a1111_parameters(tmp_path):
    p = _png(tmp_path / "a.png", info={
        "parameters": (
            "a cat in a chair, masterpiece\n"
            "Negative prompt: blurry, low quality\n"
            "Steps: 20, Sampler: Euler a, CFG scale: 7.5, Seed: 1234, Model: foo"
        ),
    })
    out = rmi.inspect_file(pathlib.Path(p))
    assert out["prompt_positive"] == "a cat in a chair, masterpiece"
    assert out["prompt_negative"] == "blurry, low quality"
    assert out["seed"] == "1234"
    assert out["steps"] == "20"
    assert out["cfg"] == "7.5"
    assert out["sampler"] == "Euler a"
    assert out["model"] == "foo"
    assert out["width"] == "8"
    assert out["height"] == "8"


def test_inspect_comfy_prompt_chunk(tmp_path):
    graph = json.dumps({
        "1": {"class_type": "CLIPTextEncode", "inputs": {"text": "a fox in the forest"}},
    })
    p = _png(tmp_path / "b.png", info={"prompt": graph})
    out = rmi.inspect_file(pathlib.Path(p))
    assert out["prompt_positive"] == "a fox in the forest"


def test_inspect_ui_workflow_chunk(tmp_path):
    ui_wf = json.dumps({
        "nodes": [{
            "id": 5,
            "type": "CLIPTextEncodeFlux",
            "widgets_values": ["a hawk above the canyon", "a hawk above the canyon", 3],
        }],
        "links": [],
    })
    p = _png(tmp_path / "c.png", info={"workflow": ui_wf})
    out = rmi.inspect_file(pathlib.Path(p))
    assert out["prompt_positive"] == "a hawk above the canyon"


def test_inspect_flat_prompt_keys(tmp_path):
    p = _png(tmp_path / "d.png", info={
        "prompt": "this is just a flat string, not a graph",
        "prompt_effective": "longest version of the prompt with much more detail in it",
        "prompt_original": "short original",
    })
    out = rmi.inspect_file(pathlib.Path(p))
    assert "longest version" in out["prompt_positive"]


def test_inspect_returns_raw_metadata_json(tmp_path):
    p = _png(tmp_path / "e.png", info={"parameters": "test prompt\nSteps: 10"})
    out = rmi.inspect_file(pathlib.Path(p))
    raw = json.loads(out["raw_metadata_json"])
    assert "_info_keys" in raw
    assert "parameters" in raw["_info_keys"]


def test_inspect_missing_file_returns_error_json(tmp_path):
    out = rmi.inspect_file(tmp_path / "does_not_exist.png")
    raw = json.loads(out["raw_metadata_json"])
    assert "error" in raw


def test_embed_writes_parameters_chunk(tmp_path):
    src = Image.new("RGB", (8, 8), color="green")
    target = tmp_path / "out.png"
    rmi.embed_file(src, {
        "positive": "round-trip positive prompt",
        "negative": "round-trip negative prompt",
        "Seed": 42,
        "Steps": 15,
    }, target)
    assert target.is_file()
    out = rmi.inspect_file(target)
    assert "round-trip positive" in out["prompt_positive"]
    assert "round-trip negative" in out["prompt_negative"]
    assert out["seed"] == "42"
    assert out["steps"] == "15"


def test_embed_writes_comfy_chunks(tmp_path):
    src = Image.new("RGB", (8, 8), color="purple")
    target = tmp_path / "out2.png"
    rmi.embed_file(src, {
        "prompt": {"1": {"class_type": "CLIPTextEncode", "inputs": {"text": "embedded fox"}}},
    }, target)
    out = rmi.inspect_file(target)
    assert out["prompt_positive"] == "embedded fox"


def test_embed_writes_flat_keys(tmp_path):
    src = Image.new("RGB", (8, 8), color="orange")
    target = tmp_path / "out3.png"
    rmi.embed_file(src, {
        "prompt_effective": "this is the resolved flat prompt that should survive",
        "model_name": "TestModel-v1",
    }, target)
    out = rmi.inspect_file(target)
    assert "resolved flat prompt" in out["prompt_positive"]
    raw = json.loads(out["raw_metadata_json"])
    assert "TestModel-v1" in str(raw)


def test_node_inspect_returns_twelve_outputs(tmp_path):
    p = _png(tmp_path / "n.png", info={"parameters": "a thing\nSteps: 1"})
    node = rmi.RayMetaInspect()
    out = node.process(mode="Inspect", path=str(p))
    assert len(out) == 12
    assert out[0] == "a thing"


def test_node_inspect_empty_path_returns_error(tmp_path):
    node = rmi.RayMetaInspect()
    out = node.process(mode="Inspect", path="")
    raw = json.loads(out[10])
    assert "error" in raw


def test_node_embed_then_inspect_round_trip(tmp_path):
    import torch
    target = tmp_path / "round.png"
    img = torch.zeros((1, 4, 4, 3), dtype=torch.float32)
    img[..., 0] = 0.5
    node = rmi.RayMetaInspect()
    meta = json.dumps({"positive": "embedded then inspected", "Seed": 99})
    out = node.process(mode="Embed", path=str(target), image=img, metadata_json=meta)
    assert "embedded then inspected" in out[0]
    assert out[2] == "99"


def test_node_embed_invalid_json(tmp_path):
    import torch
    img = torch.zeros((1, 4, 4, 3), dtype=torch.float32)
    node = rmi.RayMetaInspect()
    out = node.process(mode="Embed", path=str(tmp_path / "x.png"),
                       image=img, metadata_json="not json{")
    raw = json.loads(out[10])
    assert "error" in raw


def test_input_types_declares_required_widgets():
    it = rmi.RayMetaInspect.INPUT_TYPES()
    assert "mode" in it["required"]
    assert "path" in it["required"]
    assert "image" in it["optional"]
    assert "metadata_json" in it["optional"]


def test_return_names_match_count():
    rt = rmi.RayMetaInspect.RETURN_TYPES
    rn = rmi.RayMetaInspect.RETURN_NAMES
    assert len(rt) == len(rn) == 12


# ----- path resolution -----------------------------------------------------


def test_resolve_path_direct_absolute(tmp_path):
    p = _png(tmp_path / "x.png")
    out = rmi._resolve_path(str(p))
    assert out == p


@pytest.mark.parametrize("wrap", [
    ('"', '"'),
    ("'", "'"),
    ("«", "»"),
    ("“", "”"),
    ("‘", "’"),
])
def test_resolve_path_strips_surrounding_quotes(tmp_path, wrap):
    """Windows Explorer's 'Copy as path' wraps in `"…"`; macOS and some
    locales use guillemets / smart quotes. A wrapped path must still resolve."""
    p = _png(tmp_path / "quoted.png")
    quoted = f"{wrap[0]}{p}{wrap[1]}"
    out = rmi._resolve_path(quoted)
    assert out == p


def test_resolve_path_strips_quotes_around_annotated(tmp_path, monkeypatch):
    target = _png(tmp_path / "annot.png")

    class _Stub:
        @staticmethod
        def get_input_directory():
            return str(tmp_path)

        @staticmethod
        def get_output_directory():
            return str(tmp_path)

        @staticmethod
        def get_temp_directory():
            return str(tmp_path)

    monkeypatch.setattr(rmi, "folder_paths", _Stub)
    out = rmi._resolve_path('"annot.png [input]"')
    assert out == target


def test_resolve_path_empty_returns_non_file():
    out = rmi._resolve_path("")
    # Empty input → a Path that isn't a real file. The caller (_do_inspect)
    # short-circuits on empty input before reaching the resolver anyway.
    assert not out.is_file()


def test_resolve_path_annotated_input_via_folder_paths(tmp_path, monkeypatch):
    """The /upload/image drag-drop returns `name [input]` — the resolver must
    route that through folder_paths.get_input_directory() so the file is
    located even when CWD is not ComfyUI's root."""
    target = _png(tmp_path / "__00039_.png")

    class _Stub:
        @staticmethod
        def get_input_directory():
            return str(tmp_path)

        @staticmethod
        def get_output_directory():
            return str(tmp_path)

        @staticmethod
        def get_temp_directory():
            return str(tmp_path)

    monkeypatch.setattr(rmi, "folder_paths", _Stub)
    out = rmi._resolve_path("__00039_.png [input]")
    assert out == target


def test_resolve_path_relative_input_prefix(tmp_path, monkeypatch):
    target = _png(tmp_path / "shot.png")

    class _Stub:
        @staticmethod
        def get_input_directory():
            return str(tmp_path)

        @staticmethod
        def get_output_directory():
            return str(tmp_path)

        @staticmethod
        def get_temp_directory():
            return str(tmp_path)

    monkeypatch.setattr(rmi, "folder_paths", _Stub)
    out = rmi._resolve_path("input/shot.png")
    assert out == target


def test_resolve_path_annotated_with_subfolder(tmp_path, monkeypatch):
    (tmp_path / "sub").mkdir()
    target = _png(tmp_path / "sub" / "nested.png")

    class _Stub:
        @staticmethod
        def get_input_directory():
            return str(tmp_path)

        @staticmethod
        def get_output_directory():
            return str(tmp_path)

        @staticmethod
        def get_temp_directory():
            return str(tmp_path)

    monkeypatch.setattr(rmi, "folder_paths", _Stub)
    out = rmi._resolve_path("sub/nested.png [input]")
    assert out == target


def test_resolve_path_missing_file_returns_original(tmp_path, monkeypatch):
    """When nothing resolves, return the user-supplied path verbatim so
    inspect_file() can surface a clear 'not a file' error."""
    class _Stub:
        @staticmethod
        def get_input_directory():
            return str(tmp_path)

        @staticmethod
        def get_output_directory():
            return str(tmp_path)

        @staticmethod
        def get_temp_directory():
            return str(tmp_path)

    monkeypatch.setattr(rmi, "folder_paths", _Stub)
    out = rmi._resolve_path("does_not_exist.png [input]")
    # Resolver falls back to the direct expanduser path.
    assert "does_not_exist.png" in str(out)
    assert not out.is_file()
