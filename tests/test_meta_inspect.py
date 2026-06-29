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
