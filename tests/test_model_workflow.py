"""Model output demand and names without loading model weights."""
from datetime import datetime
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import model_workflow as names
import ray_model_tools as nodes


@pytest.mark.parametrize("slot", range(7))
def test_only_inference_outputs_request_initialization(slot):
    prompt = {"downstream": {"inputs": {"source": [12, slot]}}}
    assert names.inference_requested(prompt, "12") is (slot < 3)
    assert names.inference_requested({}, "12") is False


def test_output_use_changes_loader_cache_key(tmp_path):
    path = tmp_path / "source.safetensors"
    path.write_bytes(b"fingerprint")
    data_prompt = {"consumer": {"inputs": {"model_data": ["12", 3]}}}
    model_prompt = {"consumer": {"inputs": {"model": ["12", 0]}}}
    assert nodes.RayModelLoadAs.IS_CHANGED(model_name=str(path), prompt=data_prompt, unique_id="12") != nodes.RayModelLoadAs.IS_CHANGED(model_name=str(path), prompt=model_prompt, unique_id="12")
    assert nodes.RayModelMerge.IS_CHANGED(prompt=data_prompt, unique_id="12") != nodes.RayModelMerge.IS_CHANGED(prompt=model_prompt, unique_id="12")


def test_model_loading_follows_connected_outputs(tmp_path, monkeypatch):
    import torch
    from safetensors.torch import save_file
    source = tmp_path / "source.safetensors"
    save_file({"proj.weight": torch.ones(2, 2)}, str(source))
    calls = []
    model = SimpleNamespace(model=SimpleNamespace())
    monkeypatch.setattr(nodes, "load_asset", lambda *args: (calls.append(args) or model, None, None))
    data = nodes.RayModelLoadAs().load(str(source), prompt={"save": {"inputs": {"source": ["12", 3]}}}, unique_id="12")
    assert calls == [] and data["result"][0] is None
    live = nodes.RayModelLoadAs().load(str(source), prompt={"sampler": {"inputs": {"model": ["12", 0]}}}, unique_id="12")
    assert len(calls) == 1 and live["result"][0] is model


def test_live_provenance_wins_over_data_and_legacy_path():
    model = SimpleNamespace(attachments={"ray_model_source": "live.safetensors"})
    data = SimpleNamespace(metadata={"ray_source_name": "data"}, _path="converted.safetensors")
    assert names.source_name(model, data, "legacy.safetensors") == "live.safetensors"
    assert names.source_name(data=data, path="legacy.safetensors") == "data"


def test_graph_provenance_follows_model_through_patch_nodes():
    prompt = {"load": {"inputs": {"unet_name": "MOSS/Alpha.safetensors"}},
              "patch": {"inputs": {"model": ["load", 0], "path": "different-adapter.safetensors"}}}
    assert names.graph_source_name(prompt, "patch") == "MOSS/Alpha.safetensors"
    prompt["load"] = {"inputs": {"model": ["patch", 0]}}
    assert names.graph_source_name(prompt, "patch") == ""


def test_names_keep_settings_time_and_precisions_readable():
    now = datetime(2026, 10, 24, 20, 30, 40)
    value = names.merge_name("A.safetensors", "B.safetensors", "Base.safetensors", now=now)
    assert value.startswith("A-A_B-B_LERP_50-50_bf16_") and value.endswith("_20261024-203040")
    assert "Base-" not in value
    assert names.merge_name("A", "B", "Base", strategy="TIES", now=now).startswith("Base-Base_A-A_B-B_TIES_")
    assert names.merge_name("A", "B", now=now, settings={"density": .25}) != names.merge_name("A", "B", now=now)
    assert names.merge_name("A", "B", now=now, settings={"block_weights": '{"x":1}'}) != names.merge_name("A", "B", now=now)


def test_name_case_outputs_are_filesystem_safe():
    cases = json.loads(Path(__file__).with_name("workflow_name_cases.json").read_text(encoding="utf8"))
    for case in cases:
        name = names.merge_name(**case, now=datetime(2026, 10, 24, 20, 30, 40))
        assert len(name) <= 180 and not any(c in name for c in '<>:"/\\|?*{}')
        assert name.endswith("_20261024-203040"), "Long source names must retain the complete datetime"
