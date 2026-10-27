"""Queue-time merge validation uses links without evaluating model loaders."""
import asyncio

import pytest
import model_tools as core
import ray_model_tools as model_nodes


@pytest.fixture
def validate_merge(monkeypatch):
    import execution
    import nodes

    class Source:
        RETURN_TYPES = ("MODEL", "RAY_MODEL_DATA", "STRING", "CLIP")
        FUNCTION = "load"

        @classmethod
        def INPUT_TYPES(cls):
            return {"required": {}}

        def load(self):
            pytest.fail("Queue validation must never evaluate a loader")

    monkeypatch.setitem(nodes.NODE_CLASS_MAPPINGS, "MergeValidationSource", Source)
    monkeypatch.setitem(nodes.NODE_CLASS_MAPPINGS, "RayModelMerge", model_nodes.RayModelMerge)

    def validate(strategy, **extra):
        required = model_nodes.RayModelMerge.INPUT_TYPES()["required"]
        inputs = {name: spec[1]["default"] for name, spec in required.items()}
        inputs.update(strategy=strategy, model_a=["source", 0], model_b=["source", 0])
        inputs.update(extra)
        prompt = {"source": {"class_type": "MergeValidationSource", "inputs": {}},
                  "merge": {"class_type": "RayModelMerge", "inputs": inputs}}
        return asyncio.run(execution.validate_inputs("merge-validation", prompt, "merge", {}))

    return validate


@pytest.mark.parametrize("strategy", core.STRATEGIES[2:])
def test_task_vector_methods_reject_a_missing_base_before_execution(validate_merge, strategy):
    valid, errors, _ = validate_merge(strategy)
    assert not valid
    assert any(error["type"] == "custom_validation_failed" and
               "base_model or base_data" in error["details"] and
               "LERP or SLERP" in error["details"] for error in errors)


@pytest.mark.parametrize("strategy", ["LERP", "SLERP"])
def test_direct_blends_allow_two_models(validate_merge, strategy):
    assert validate_merge(strategy)[0]


@pytest.mark.parametrize("base", [
    {"base_model": ["source", 0]},
    {"base_data": ["source", 1]},
    {"base_path": "base.safetensors"},
    {"base_path": ["source", 2]},
])
def test_base_links_and_legacy_paths_allow_queueing(validate_merge, base):
    assert validate_merge("DELLA", **base)[0]


def test_blank_legacy_path_does_not_supply_a_base(validate_merge):
    assert not validate_merge("DELLA", base_path="  ")[0]


@pytest.mark.parametrize("input_name", ["model_a", "model_b", "base_model", "base_data", "base_path"])
def test_native_link_type_checks_are_preserved(validate_merge, input_name):
    valid, errors, _ = validate_merge("DELLA", **{input_name: ["source", 3]})
    assert not valid
    assert any(error["type"] == "return_type_mismatch" for error in errors)


def test_unknown_strategy_is_still_rejected(validate_merge):
    assert not validate_merge("unknown", base_model=["source", 0])[0]
