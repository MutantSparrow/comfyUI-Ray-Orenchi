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


def test_multi_model_api_requests_are_validated_as_one_execution(tmp_path):
    source = tmp_path / "model.safetensors"
    source.write_bytes(b"fixture")
    with patch("folder_paths.get_full_path", return_value=str(source)):
        assert RayQueuedModelLoader.VALIDATE_INPUTS("model.safetensors", '["other.safetensors"]') is True
    with patch("folder_paths.get_full_path", side_effect=[str(source), None]):
        assert "not found" in RayQueuedModelLoader.VALIDATE_INPUTS("model.safetensors", '["missing.safetensors"]')


def test_automatic_precision_delegates_to_native_loader(tmp_path):
    source = tmp_path / "model.safetensors"
    source.write_bytes(b"fixture")
    sentinel = object()
    with patch("folder_paths.get_full_path", return_value=str(source)), patch("comfy.sd.load_diffusion_model", return_value=sentinel) as load, \
            patch("ray_queued_model_loader.install_model_offload", side_effect=lambda model: model):
        assert RayQueuedModelLoader().load("model.safetensors") == ([sentinel],)
    load.assert_called_once_with(str(source), model_options={})


def test_spectrum_is_optional_and_receives_the_queued_graph(tmp_path):
    source = tmp_path / "model.safetensors"; source.write_bytes(b"fixture")
    model, accelerated = object(), object()
    prompt = {"sampler": {"inputs": {"steps": 25}}}
    with patch("folder_paths.get_full_path", return_value=str(source)), patch("comfy.sd.load_diffusion_model", return_value=model), \
            patch("ray_queued_model_loader.apply_spectrum", return_value=(accelerated, {"state": "attached"})) as spectrum, \
            patch("ray_queued_model_loader.install_model_offload", side_effect=lambda model: model):
        assert RayQueuedModelLoader().load("model.safetensors") == ([model],)
        spectrum.assert_not_called()
        result = RayQueuedModelLoader().load("model.safetensors", spectrum_enabled=True, prompt=prompt, unique_id="loader")
        assert result["result"] == ([accelerated],)
        spectrum.assert_called_once_with(model, prompt, "loader")


def test_model_list_uses_native_execution_and_broadcasts_settings(tmp_path):
    import asyncio
    from execution import merge_result_data, _async_map_node_over_list
    source = tmp_path / "model.safetensors"; source.write_bytes(b"fixture")
    models = [object(), object(), object()]
    loader = RayQueuedModelLoader()
    with patch("folder_paths.get_full_path", return_value=str(source)), \
            patch("comfy.sd.load_diffusion_model", side_effect=models) as native, \
            patch("ray_queued_model_loader.install_model_offload", side_effect=lambda model: model) as offload:
        result = loader.load("a.safetensors", '["b.safetensors", "c.safetensors"]')
    assert native.call_count == offload.call_count == 3
    mapped = merge_result_data([result], loader)
    assert mapped == [models]
    class Sampler:
        FUNCTION = "sample"
        def sample(self, model, seed, prompt):
            return (models.index(model), seed, prompt)
    outputs = asyncio.run(_async_map_node_over_list("test", "2", Sampler(),
                         {"model": mapped[0], "seed": [42], "prompt": ["fixed prompt"]}, "sample"))
    assert outputs == [(0, 42, "fixed prompt"), (1, 42, "fixed prompt"), (2, 42, "fixed prompt")]


def test_later_model_file_changes_invalidate_cache(tmp_path):
    first = tmp_path / "a.safetensors"; first.write_bytes(b"a")
    second = tmp_path / "b.safetensors"; second.write_bytes(b"b")
    with patch("folder_paths.get_full_path", side_effect=lambda _, name: str(tmp_path / name)):
        before = RayQueuedModelLoader.IS_CHANGED(first.name, queued_models='["b.safetensors"]')
        second.write_bytes(b"changed")
        assert before != RayQueuedModelLoader.IS_CHANGED(first.name, queued_models='["b.safetensors"]')


def test_invalid_later_model_is_rejected_before_loading_any_weights(tmp_path):
    first = tmp_path / "a.safetensors"; first.write_bytes(b"a")
    with patch("folder_paths.get_full_path", side_effect=lambda _, name: str(tmp_path / name)), \
            patch("comfy.sd.load_diffusion_model") as native:
        with pytest.raises(ValueError, match="not found"):
            RayQueuedModelLoader().load(first.name, '["missing.safetensors"]')
        native.assert_not_called()
