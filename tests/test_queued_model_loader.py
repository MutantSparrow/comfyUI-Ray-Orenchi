"""Native loading and validation, without loading model weights."""
from unittest.mock import patch
import pytest
from ray_queued_model_loader import RayQueuedModelLoader, additional_models, model_path


def test_registered_and_absolute_paths(tmp_path):
    source = tmp_path / "model.safetensors"
    source.write_bytes(b"fixture")
    with patch("folder_paths.get_full_path", return_value=str(source)):
        assert model_path("model.safetensors") == str(source)
    with patch("folder_paths.get_full_path", return_value=None):
        assert model_path(str(source)) == str(source)
        assert "not found" in RayQueuedModelLoader.VALIDATE_INPUTS("missing.safetensors")


def test_native_string_links_are_validated_at_execution():
    assert RayQueuedModelLoader.INPUT_TYPES()["required"]["model_name"][0] == "STRING"
    assert RayQueuedModelLoader.VALIDATE_INPUTS(model_name=None) is True


def test_file_changes_invalidate_the_loader_cache(tmp_path):
    source = tmp_path / "model.safetensors"
    source.write_bytes(b"first")
    with patch("folder_paths.get_full_path", return_value=str(source)):
        before = RayQueuedModelLoader.IS_CHANGED("model.safetensors")
        source.write_bytes(b"second version")
        assert before != RayQueuedModelLoader.IS_CHANGED("model.safetensors")


def test_spectrum_step_inference_participates_in_cache_key(tmp_path):
    source = tmp_path / "model.safetensors"; source.write_bytes(b"fixture")
    prompt = {"1": {"inputs": {}}, "2": {"inputs": {"model": ["1", 0], "steps": 25}}}
    with patch("folder_paths.get_full_path", return_value=str(source)):
        first = RayQueuedModelLoader.IS_CHANGED("model.safetensors", True, prompt, "1")
        prompt["2"]["inputs"]["steps"] = 30
        assert first != RayQueuedModelLoader.IS_CHANGED("model.safetensors", True, prompt, "1")


@pytest.mark.parametrize("value", ['{}', '[null]', '[""]', 'invalid'])
def test_invalid_model_lists(value):
    with pytest.raises(ValueError):
        additional_models(value)


def test_multi_model_api_requests_require_expansion(tmp_path):
    source = tmp_path / "model.safetensors"
    source.write_bytes(b"fixture")
    with patch("folder_paths.get_full_path", return_value=str(source)):
        assert "one model_name per job" in RayQueuedModelLoader.VALIDATE_INPUTS("model.safetensors", '["other.safetensors"]')


def test_automatic_precision_delegates_to_native_loader(tmp_path):
    source = tmp_path / "model.safetensors"
    source.write_bytes(b"fixture")
    sentinel = object()
    with patch("folder_paths.get_full_path", return_value=str(source)), patch("comfy.sd.load_diffusion_model", return_value=sentinel) as load:
        assert RayQueuedModelLoader().load("model.safetensors") == (sentinel,)
    load.assert_called_once_with(str(source), model_options={})


def test_spectrum_is_optional_and_receives_the_queued_graph(tmp_path):
    source = tmp_path / "model.safetensors"; source.write_bytes(b"fixture")
    model, accelerated = object(), object()
    prompt = {"sampler": {"inputs": {"steps": 25}}}
    with patch("folder_paths.get_full_path", return_value=str(source)), patch("comfy.sd.load_diffusion_model", return_value=model), \
            patch("ray_queued_model_loader.apply_spectrum", return_value=(accelerated, {"state": "attached"})) as spectrum:
        assert RayQueuedModelLoader().load("model.safetensors") == (model,)
        spectrum.assert_not_called()
        result = RayQueuedModelLoader().load("model.safetensors", spectrum_enabled=True, prompt=prompt, unique_id="loader")
        assert result["result"] == (accelerated,)
        spectrum.assert_called_once_with(model, prompt, "loader")
