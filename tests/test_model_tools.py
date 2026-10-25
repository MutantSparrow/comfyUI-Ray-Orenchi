"""Round trips and independent numerical checks for the model-tools backend."""
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch
from safetensors.torch import save_file, load_file

import model_tools as tools
import ray_model_tools as nodes


def model(tmp_path, name, tensors, metadata=None):
    path = tmp_path / f"{name}.safetensors"
    save_file(tensors, str(path), metadata=metadata or {})
    return str(path)


def payload(path):
    _, start = tools.read_header(path)
    return Path(path).read_bytes()[start:]


@pytest.mark.parametrize("folder,relative", [("", ""), ("models/merged", "models/merged"), ('"nested café"', "nested café")])
def test_save_model_folder_uses_output_root_and_exact_prefix(tmp_path, monkeypatch, folder, relative):
    import folder_paths
    output = tmp_path / "Comfy output"
    monkeypatch.setattr(folder_paths, "get_output_directory", lambda: str(output))
    source = model(tmp_path, "source", {"proj.weight": torch.ones(2, 2)}, {"original": "kept"})
    saved = nodes.RayModelSave().save(output_folder=folder, filename_prefix="Ray_Merged",
        model_data=tools.ModelAsset(source, {}), metadata={"author": "Ray", "recipe": {"ratio": [0.5, 0.5]}})
    target = output / relative / "Ray_Merged.safetensors"
    assert Path(saved["result"][1]) == target
    assert saved["ui"]["model_tools"][0]["saved_path"] == str(target)
    assert target.is_file() and payload(source) == payload(target)
    meta = tools.load_metadata(target)
    assert meta["original"] == "kept" and meta["author"] == "Ray"
    assert json.loads(meta["recipe"]) == {"ratio": [0.5, 0.5]}
    before = target.read_bytes()
    with pytest.raises(FileExistsError):
        nodes.RayModelSave().save(output_folder=folder, filename_prefix="Ray_Merged", model_data=tools.ModelAsset(source, {}))
    assert target.read_bytes() == before
    assert list(target.parent.glob("*.safetensors")) == [target]


def test_save_model_absolute_folder_and_safe_stem_do_not_escape_folder(tmp_path):
    folder = tmp_path / "Absolute café"
    asset = tools.ModelAsset("", {"title": "Memory"}, {"proj.weight": torch.zeros(2, 2)})
    saved = nodes.RayModelSave().save(output_folder=f'"{folder}"', filename_prefix="../Ray: Merge", model_data=asset)
    target = Path(saved["result"][1])
    assert target.parent == folder and target.name == "_Ray__Merge.safetensors"
    assert asset.tensors is not None and not list(tmp_path.glob(".ray-*"))
    with pytest.raises(ValueError, match="filename prefix"):
        nodes.RayModelSave().save(output_folder=str(folder), filename_prefix=" ", model_data=asset)
    with pytest.raises(ValueError, match="Connect MODEL or model_data"):
        nodes.RayModelSave().save(output_folder=str(folder))


def test_load_model_schema_keeps_sources_without_enumerating_models(tmp_path, monkeypatch):
    import folder_paths
    def no_listing(*args):
        raise AssertionError("A file picker must not enumerate configured model folders")
    monkeypatch.setattr(folder_paths, "get_filename_list", no_listing)
    assert nodes.RayModelLoadAs.INPUT_TYPES()["required"]["model_name"][0] == "STRING"
    source = model(tmp_path, "my chosen model", {"proj.weight": torch.ones(2, 2)})
    fake_model = SimpleNamespace(model=SimpleNamespace())
    monkeypatch.setattr(nodes, "load_asset", lambda *args: (fake_model, None, None))
    result = nodes.RayModelLoadAs().load(model_name=source)
    assert result["result"][0] is fake_model
    assert result["ui"]["model_tools"][0]["source"] == source
    stat = Path(source).stat()
    assert nodes.RayModelLoadAs.IS_CHANGED(model_name=source) == (((source, stat.st_mtime_ns, stat.st_size),), True)


def test_load_model_picker_preserves_legacy_sources(tmp_path, monkeypatch):
    import folder_paths
    old = model(tmp_path, "old", {"proj.weight": torch.ones(2, 2)})
    chosen = model(tmp_path, "chosen", {"proj.weight": torch.zeros(2, 2)})
    monkeypatch.setattr(folder_paths, "get_full_path", lambda group, filename: old)
    assert nodes.resolve_file("checkpoints: old.safetensors") == old
    assert nodes.resolve_file("checkpoints: old.safetensors", path=chosen) == chosen
    assert nodes.resolve_file(chosen) == chosen
    with pytest.raises(ValueError, match="Select a model file"):
        nodes.resolve_file("Select a file or use path…")


def test_lora_picker_uses_files_and_keeps_legacy_selections(tmp_path, monkeypatch):
    import folder_paths
    def no_listing(*args):
        raise AssertionError("The LoRA file picker must not enumerate configured model folders")
    monkeypatch.setattr(folder_paths, "get_filename_list", no_listing)
    assert nodes.RayLoraBake.INPUT_TYPES()["required"]["lora_name"][0] == "STRING"
    adapter = model(tmp_path, "adapter", {"lora_up.weight": torch.ones(2, 1)})
    monkeypatch.setattr(folder_paths, "get_full_path", lambda group, filename: adapter)
    assert nodes.resolve_file("loras: adapter.safetensors") == adapter
    stat = Path(adapter).stat()
    assert nodes.RayLoraBake.IS_CHANGED(lora_name=adapter)[1] == ((adapter, stat.st_mtime_ns, stat.st_size),)
    assert nodes.RayLoraBake.IS_CHANGED(lora_name="loras: adapter.safetensors")[1] == ((adapter, stat.st_mtime_ns, stat.st_size),)


def test_streaming_writer_scalar_empty_and_bfloat(tmp_path):
    tensors = {"scalar": torch.tensor(3.), "empty": torch.empty(0), "bf16": torch.randn(3, 8).bfloat16(), "flag": torch.tensor(True)}
    path = tmp_path / "stream.safetensors"
    with tools.TensorWriter(path, {"nested": {"x": [1, None]}}) as writer:
        for key, tensor in tensors.items():
            writer.add(key, tensor)
    result = load_file(path)
    assert all(torch.equal(result[key], tensor) for key, tensor in tensors.items())
    assert tools.load_metadata(path)["nested"] == '{"x": [1, null]}'


def test_metadata_can_grow_without_changing_tensor_bytes(tmp_path):
    path = model(tmp_path, "src", {"x": torch.randn(9, 5)}, {"literal": "001", "nested": '{ "x": 1 }'})
    target = tmp_path / "copy.safetensors"
    meta = tools.load_metadata(path)
    meta["long"] = "扩展" * 10000
    tools.rewrite_metadata(path, target, meta)
    assert payload(path) == payload(target)
    assert tools.load_metadata(target) == meta
    assert tools.load_metadata(path).get("long") is None
    tools.rewrite_metadata(target, target, {"updated": "true"}, overwrite=True)
    assert payload(path) == payload(target)


def test_no_clobber_and_failure_leave_original_untouched(tmp_path):
    path = model(tmp_path, "src", {"x": torch.ones(2)})
    before = Path(path).read_bytes()
    with pytest.raises(FileExistsError):
        with tools.TensorWriter(path) as writer:
            writer.add("x", torch.zeros(2))
    assert Path(path).read_bytes() == before
    out = tmp_path / "failed.safetensors"
    with pytest.raises(RuntimeError):
        with tools.TensorWriter(out) as writer:
            writer.add("x", torch.ones(2))
            raise RuntimeError("cancel")
    assert not out.exists()
    assert not list(tmp_path.glob(".ray-*"))


@pytest.mark.skipif(tools.os.name != "nt", reason="Windows exclusive rename semantics")
def test_windows_publication_does_not_require_hard_links(tmp_path, monkeypatch):
    def unsupported(*args, **kwargs):
        raise OSError(1, "Hard links are unsupported on this volume")
    monkeypatch.setattr(tools.os, "link", unsupported)
    source = model(tmp_path, "source", {"proj.weight": torch.ones(2, 2)})
    converted = tmp_path / "converted.safetensors"
    tools.convert(source, converted, "bf16")
    assert load_file(converted)["proj.weight"].dtype == torch.bfloat16
    copied = tmp_path / "metadata.safetensors"
    tools.rewrite_metadata(converted, copied, {"author": "Ray"})
    assert payload(copied) == payload(converted)
    assert tools.load_metadata(copied) == {"author": "Ray"}
    sidecar = tmp_path / "metadata.json"
    tools.atomic_json(sidecar, {"author": "Ray"})
    with pytest.raises(FileExistsError):
        tools.atomic_json(sidecar, {"author": "other"})
    assert tools.load_metadata(sidecar) == {"author": "Ray"}
    with pytest.raises(FileExistsError):
        tools.rewrite_metadata(converted, copied, {"author": "other"})
    assert tools.load_metadata(copied) == {"author": "Ray"}
    assert not list(tmp_path.glob(".ray-*"))


@pytest.mark.parametrize("fmt", ["auto", "preserve"])
def test_file_only_loader_keeps_quantized_source_without_conversion(tmp_path, monkeypatch, fmt):
    source = model(tmp_path, "legacy", {"proj.weight": torch.ones(2, 8, dtype=torch.int8),
                   "proj.scale_weight": torch.tensor(.25), "scaled_int8": torch.tensor(1)})
    def unnecessary(*args, **kwargs):
        raise AssertionError("File-only loading must not initialize a model or rewrite source weights")
    monkeypatch.setattr(nodes, "load_asset", unnecessary)
    monkeypatch.setattr(tools, "convert", unnecessary)
    before = Path(source).read_bytes()
    output = nodes.RayModelLoadAs().load(source, weight_format=fmt, prompt={}, unique_id="test")
    assert output["result"][:3] == (None, None, None)
    assert output["result"][3].path == source
    assert output["ui"]["model_tools"][0]["loaded"] is False
    assert Path(source).read_bytes() == before


def test_file_only_loader_honors_explicit_conversion(tmp_path, monkeypatch):
    import folder_paths
    monkeypatch.setattr(folder_paths, "get_temp_directory", lambda: str(tmp_path))
    def unnecessary(*args, **kwargs):
        raise AssertionError("File-only conversion must not initialize a model")
    monkeypatch.setattr(nodes, "load_asset", unnecessary)
    source = model(tmp_path, "source", {"proj.weight": torch.full((2, 2), .25)})
    output = nodes.RayModelLoadAs().load(source, weight_format="bf16", prompt={}, unique_id="test")
    assert output["result"][:3] == (None, None, None)
    actual = load_file(output["result"][3].path)["proj.weight"]
    assert actual.dtype == torch.bfloat16
    assert torch.equal(actual.float(), torch.full((2, 2), .25))


def test_metadata_json_roundtrip_preserves_structure_and_raw_strings(tmp_path):
    meta = {"raw": '{ "001": [true, null] }', "typed": {"list": [1, True, None, "001"]}, "unicode": "日本語"}
    out = tmp_path / "meta.json"
    tools.atomic_json(out, {"schema": tools.SCHEMA, "metadata": meta})
    assert tools.load_metadata(out) == meta
    with pytest.raises(ValueError):
        tools.metadata_fields({"bad": float("nan")})
    with pytest.raises(ValueError, match="Duplicate"):
        tools.metadata_fields('{"x":1,"x":2}')


def test_shards_index_duplicate_and_traversal(tmp_path):
    root = tmp_path / "shards"; root.mkdir()
    model(root, "a", {"a.weight": torch.ones(2, 2)})
    model(root, "b", {"b.weight": torch.ones(2, 2)})
    (root / "model.safetensors.index.json").write_text(json.dumps({"weight_map": {"a.weight": "a.safetensors", "b.weight": "b.safetensors"}}))
    assert tools.TensorSource(root).keys == ["a.weight", "b.weight"]
    (root / "model.safetensors.index.json").write_text(json.dumps({"weight_map": {"x": "../outside.safetensors"}}))
    with pytest.raises(ValueError, match="outside"):
        tools.TensorSource(root)


@pytest.mark.parametrize("fmt", tools.FORMATS[1:])
def test_conversion_dequantizes_scales_and_handles_conv(tmp_path, fmt):
    torch.manual_seed(42)
    tensors = {"proj.weight": torch.randn(8, 256), "conv.weight": torch.randn(8, 4, 3, 3),
               "norm.weight": torch.randn(8), "counter": torch.tensor(7, dtype=torch.int64)}
    src = model(tmp_path, "src", tensors, {"title": "Example"})
    dst = tmp_path / "converted.safetensors"
    asset = tools.convert(src, dst, fmt)
    source = tools.TensorSource(asset.path)
    for key, original in tensors.items():
        actual = source.dense(key)
        tolerance = .13 if fmt.startswith("fp8") else .04 if fmt.startswith("int8") else .015
        assert torch.allclose(actual.float(), original.float(), atol=tolerance, rtol=tolerance)
    assert tools.load_metadata(dst)["title"] == "Example"
    if fmt.startswith("int8"):
        assert source.config("proj.weight")["format"] == "int8_tensorwise"
        assert source.headers["conv.weight"]["dtype"] == "BF16"
        assert source.config("proj.weight").get("convrot", False) == (fmt == "int8_convrot")
        assert "scaled_int8" not in source.index
    # Converting a quantized model back must include its scale and inverse rotation.
    back = tmp_path / "back.safetensors"
    tools.convert(dst, back, "fp32")
    assert torch.equal(load_file(back)["proj.weight"], source.dense("proj.weight"))


def test_convrot_nondivisible_linear_uses_unrotated_native_int8(tmp_path):
    src = model(tmp_path, "src", {"proj.weight": torch.randn(8, 40)})
    asset = tools.convert(src, tmp_path / "out.safetensors", "int8_convrot")
    assert "convrot" not in tools.TensorSource(asset.path).config("proj.weight")


def test_upcast_legacy_scaled_fp8_and_convrot(tmp_path):
    from math import sqrt
    w = torch.arange(32).reshape(4, 8).float() / 100
    src = model(tmp_path, "fp8", {"proj.weight": (w / .01).to(torch.float8_e4m3fn),
        "proj.scale_weight": torch.tensor([.01]), "scaled_fp8": torch.empty(0, dtype=torch.float8_e4m3fn)})
    tools.convert(src, tmp_path / "fp16.safetensors", "fp16")
    actual = load_file(tmp_path / "fp16.safetensors")["proj.weight"]
    expected = ((w / .01).to(torch.float8_e4m3fn).float() * .01).half()
    assert torch.equal(actual, expected)
    h = torch.tensor([[1., 1.], [1., -1.]]) / sqrt(2)
    rotated = (w.reshape(4, 4, 2) @ h).reshape(4, 8)
    src = model(tmp_path, "legacy", {"proj.weight": (rotated / .005).round().to(torch.int8),
        "proj.scale_weight": torch.tensor([.005]), "proj.hadamard_group": torch.tensor(2), "scaled_int8": torch.empty(0, dtype=torch.int8)})
    assert torch.allclose(tools.TensorSource(src).dense("proj.weight"), w, atol=.005)


def test_nonfinite_and_overflow_fail_without_file(tmp_path):
    for index, value in enumerate([float("nan"), 1e10]):
        src = model(tmp_path, f"src{index}", {"x.weight": torch.tensor([[value]])})
        out = tmp_path / f"bad{index}.safetensors"
        with pytest.raises(ValueError):
            tools.convert(src, out, "fp16")
        assert not out.exists()


@pytest.mark.parametrize("strategy", tools.STRATEGIES)
def test_merge_strategies_reproducible_and_inputs_unchanged(tmp_path, strategy):
    torch.manual_seed(5)
    x = torch.randn(8, 8)
    a = model(tmp_path, "a", {"model.diffusion_model.proj.weight": x + torch.randn_like(x)*.2})
    b = model(tmp_path, "b", {"proj.weight": x + torch.randn_like(x)*.2})
    base = model(tmp_path, "base", {"proj.weight": x})
    original = [Path(p).read_bytes() for p in (a, b, base)]
    output = []
    for i in range(2):
        asset, _ = tools.merge_models(a, b, tmp_path / f"out{i}.safetensors", strategy, .4, base, "fp32", seed=42)
        output.append(load_file(asset.path)["model.diffusion_model.proj.weight"])
    assert torch.equal(*output)
    assert all(Path(p).read_bytes() == raw for p, raw in zip((a, b, base), original))
    if strategy == "LERP":
        expected = .4 * load_file(a)["model.diffusion_model.proj.weight"] + .6 * load_file(b)["proj.weight"]
        assert torch.allclose(output[0], expected)


def test_merge_requires_base_and_checks_shapes_before_writing(tmp_path):
    a = model(tmp_path, "a", {"x.weight": torch.ones(2, 2)})
    b = model(tmp_path, "b", {"x.weight": torch.ones(3, 2)})
    out = tmp_path / "out.safetensors"
    with pytest.raises(ValueError, match="explicit base"):
        tools.merge_models(a, b, out, "TIES")
    with pytest.raises(ValueError, match="Shape mismatch"):
        tools.merge_models(a, b, out)
    assert not out.exists()
    asset, _ = tools.merge_models(a, b, out, mismatch="pad", fmt="fp32")
    assert load_file(asset.path)["x.weight"].shape == (3, 2)


@pytest.mark.parametrize("mode,expected", [
    ("pad", [[3., 1.], [4.5, 2.], [3.5, 0.]]),
    ("trim", [[3.], [4.5]]),
])
def test_pad_trim_resize_shared_tensors_and_preserve_both_unique_sets(tmp_path, mode, expected):
    rope = torch.tensor([2., 3.])
    extra = torch.tensor([9.])
    a = model(tmp_path, "a", {"shared.weight": torch.tensor([[1., 2.], [3., 4.]]), "rope.bands": rope})
    b = model(tmp_path, "b", {"model.diffusion_model.shared.weight": torch.tensor([[5.], [6.], [7.]]),
                              "model.diffusion_model.extra.weight": extra})
    before = [Path(p).read_bytes() for p in (a, b)]
    asset, report = tools.merge_models(a, b, tmp_path / "out.safetensors", mismatch=mode, fmt="fp32")
    actual = load_file(asset.path)
    assert set(actual) == {"shared.weight", "rope.bands", "extra.weight"}
    assert torch.equal(actual["shared.weight"], torch.tensor(expected))
    assert torch.equal(actual["rope.bands"], rope)
    assert torch.equal(actual["extra.weight"], extra)
    assert report["only_a"] == ["diffusion_model.rope.bands"]
    assert report["only_b"] == ["diffusion_model.extra.weight"]
    assert [Path(p).read_bytes() for p in (a, b)] == before


def test_slerp_pad_preserves_missing_rotary_buffer_and_forbid_stays_strict(tmp_path):
    rope = torch.tensor([1., .01, .0001])
    a = model(tmp_path, "a", {"proj.weight": torch.tensor([[1., 0.]]), "rope.bands": rope})
    b = model(tmp_path, "b", {"proj.weight": torch.tensor([[0., 1.]])})
    out = tmp_path / "out.safetensors"
    with pytest.raises(ValueError, match="Tensor key mismatch.*rope.bands"):
        tools.merge_models(a, b, out, strategy="SLERP", mismatch="forbid")
    assert not out.exists()
    asset, _ = tools.merge_models(a, b, out, strategy="SLERP", mismatch="pad", fmt="fp32")
    actual = load_file(asset.path)
    assert torch.equal(actual["rope.bands"], rope)
    assert torch.allclose(actual["proj.weight"], torch.full((1, 2), 2 ** -.5))


def test_merge_node_uses_model_data_connections(tmp_path, monkeypatch):
    a = model(tmp_path, "a", {"proj.weight": torch.ones(2, 2)})
    b = model(tmp_path, "b", {"proj.weight": torch.zeros(2, 2)})
    monkeypatch.setattr(nodes, "cache_path", lambda _: str(tmp_path / "connected.safetensors"))
    monkeypatch.setattr(nodes, "progress", lambda: lambda *_: None)
    result = nodes.RayModelMerge().merge(data_a=tools.ModelAsset(a, {}), data_b=tools.ModelAsset(b, {}),
        path_a="old-a.metadata.json", path_b="old-b.metadata.json", base_path="unused-base.metadata.json",
        weight_a=.25, weight_format="fp32", prompt={}, unique_id="test")
    assert torch.equal(load_file(result["result"][3].path)["proj.weight"], torch.full((2, 2), .25))


def test_merge_node_reports_missing_connections_before_exporting():
    with pytest.raises(ValueError, match="Connect Model A"):
        nodes.RayModelMerge().merge()
    with pytest.raises(ValueError, match="Connect Model B"):
        nodes.RayModelMerge().merge(model_a=object())


def test_merge_controls_have_tooltips_without_changing_defaults():
    schema = nodes.RayModelMerge.INPUT_TYPES()
    for group in ("required", "optional"):
        for name, spec in schema[group].items():
            assert len(spec) > 1 and spec[1].get("tooltip", "").strip(), name
    required, optional = schema["required"], schema["optional"]
    assert required["strategy"][0] == tools.STRATEGIES
    assert required["weight_a"][1]["default"] == .5
    assert required["density"][1]["default"] == .5
    assert required["lambda"][1]["max"] == 5.
    assert required["top_trim"][1]["max"] == .99
    assert required["mismatch"][1]["default"] == "forbid"
    assert "load_result" not in required
    assert optional["block_weights"][1]["forceInput"] is True
    assert optional["fast_merge"][1]["default"] is False


@pytest.mark.parametrize("strategy", tools.STRATEGIES)
def test_fast_merge_matches_streaming_for_every_strategy(tmp_path, strategy):
    generator = torch.Generator().manual_seed(123)
    state = {"proj.weight": torch.randn(4, 256, generator=generator), "counter": torch.tensor(7)}
    a = model(tmp_path, "a", state)
    b = model(tmp_path, "b", {k: v + .2 if v.is_floating_point() else v for k, v in state.items()})
    base = model(tmp_path, "base", {k: v - .1 if v.is_floating_point() else v for k, v in state.items()})
    before = [Path(p).read_bytes() for p in (a, b, base)]
    slow, _ = tools.merge_models(a, b, tmp_path / "slow.safetensors", strategy, base=base, fmt="fp32", seed=42)
    cache = tmp_path / "fast.safetensors"
    fast, _ = tools.merge_models(a, b, cache, strategy, base=base, fmt="fp32", seed=42, fast_merge=True)
    assert not cache.exists()
    expected = load_file(slow.path)
    assert set(fast.tensors) == set(expected)
    assert all(torch.equal(fast.tensors[k], expected[k]) for k in expected)
    assert before == [Path(p).read_bytes() for p in (a, b, base)]
    # A file-based downstream consumer can still materialize the same result.
    assert all(torch.equal(v, load_file(fast.path)[k]) for k, v in expected.items())


@pytest.mark.parametrize("mode", ["intersect", "pad", "trim"])
@pytest.mark.parametrize("fmt", ["bf16", "int8_convrot", "fp8_e4m3fn_scaled"])
def test_fast_merge_keeps_quantization_unmatched_tensors_and_block_weights(tmp_path, mode, fmt):
    a = model(tmp_path, "a", {"proj.weight": torch.arange(1024.).reshape(4, 256) / 1000,
                              "rope.bands": torch.tensor([1., .1]), "text_encoders.bias": torch.tensor([9.])})
    b = model(tmp_path, "b", {"proj.weight": torch.zeros(4 if mode == "intersect" else 5, 256),
                              "extra.weight": torch.ones(2, 2, dtype=torch.int8), "extra.scale_weight": torch.tensor(.5)})
    params = dict(fmt=fmt, mismatch=mode, block_weights={"proj": .25})
    slow, _ = tools.merge_models(a, b, tmp_path / "slow.safetensors", **params)
    fast, _ = tools.merge_models(a, b, tmp_path / "fast.safetensors", fast_merge=True, **params)
    expected = load_file(slow.path)
    assert set(fast.tensors) == set(expected)
    assert all(torch.equal(fast.tensors[k].reshape(-1).view(torch.uint8), expected[k].reshape(-1).view(torch.uint8)) for k in expected)
    assert torch.equal(fast.tensors["rope.bands"], torch.tensor([1., .1]))
    assert torch.equal(fast.tensors["text_encoders.bias"], torch.tensor([9.]))


def test_fast_node_saves_directly_once_with_metadata_and_retains_cached_result(tmp_path, monkeypatch):
    a = model(tmp_path, "a", {"proj.weight": torch.ones(4, 4)}, {"title": "Original"})
    b = model(tmp_path, "b", {"proj.weight": torch.zeros(4, 4)})
    cache = tmp_path / "cache.safetensors"
    monkeypatch.setattr(nodes, "cache_path", lambda _: str(cache))
    monkeypatch.setattr(nodes, "progress", lambda: lambda *_: None)
    def no_intermediate(*args, **kwargs):
        raise AssertionError("Fast merge and direct save must not write or copy an intermediate model")
    monkeypatch.setattr(tools, "TensorWriter", no_intermediate)
    monkeypatch.setattr(tools, "rewrite_metadata", no_intermediate)
    output = nodes.RayModelMerge().merge(data_a=tools.ModelAsset(a, {}), data_b=tools.ModelAsset(b, {}),
                                        fast_merge=True, prompt={}, unique_id="test")
    asset = output["result"][3]
    assert output["ui"]["model_tools"][0]["fast_merge"] is True
    assert not cache.exists()
    for name in ("first", "second"):
        target = tmp_path / f"{name}.safetensors"
        nodes.RayModelSave().save(model_data=asset, output_folder=str(tmp_path), filename_prefix=name,
                                 metadata={"author": "Ray", "details": {"method": "LERP", "name": name}})
        meta = tools.load_metadata(target)
        assert meta["author"] == "Ray" and json.loads(meta["details"])["name"] == name
        assert meta["title"] == "Original"
        assert [entry["operation"] for entry in json.loads(meta[tools.HISTORY])] == ["merge", "save"]
        assert torch.equal(load_file(target)["proj.weight"], torch.full((4, 4), .5).bfloat16())
    assert not cache.exists() and asset.tensors is not None
    before = target.read_bytes()
    with pytest.raises(FileExistsError):
        nodes.RayModelSave().save(model_data=asset, output_folder=str(tmp_path), filename_prefix=name)
    assert target.read_bytes() == before
    nodes.RayModelSave().save(model_data=asset, output_folder=str(tmp_path), filename_prefix=name, overwrite=True, metadata_mode="replace", metadata={"author": "Ray"})
    assert "title" not in tools.load_metadata(target)
    assert not list(tmp_path.glob(".ray-*"))


def test_merge_reuses_handles_and_closes_them_on_cancellation(tmp_path, monkeypatch):
    a = model(tmp_path, "a", {f"block.{i}.weight": torch.ones(2, 2) for i in range(8)})
    b = model(tmp_path, "b", {f"block.{i}.weight": torch.zeros(2, 2) for i in range(8)})
    opened = []
    real_open = tools.safe_open
    def tracked(*args, **kwargs):
        opened.append(args[0])
        return real_open(*args, **kwargs)
    monkeypatch.setattr(tools, "safe_open", tracked)
    tools.merge_models(a, b, tmp_path / "fast.safetensors", fast_merge=True)
    assert len(opened) == 4  # Two header checks and two persistent handles.
    source = tools.TensorSource(a)
    with pytest.raises(RuntimeError, match="cancel"):
        with source.opened():
            source.raw(source.keys[0])
            raise RuntimeError("cancel")
    assert not source._handles
    def cancel(i, total):
        if i == 2:
            raise RuntimeError("cancel")
    with pytest.raises(RuntimeError, match="cancel"):
        tools.merge_models(a, b, tmp_path / "failed.safetensors", progress=cancel, fast_merge=True)
    assert not (tmp_path / "failed.safetensors").exists()
    assert not list(tmp_path.glob(".ray-*"))


def test_fast_save_failure_preserves_destination_and_cached_tensors(tmp_path, monkeypatch):
    import safetensors.torch
    target = tmp_path / "existing.safetensors"
    model(tmp_path, "existing", {"proj.weight": torch.ones(2, 2)})
    before = target.read_bytes()
    state = {"proj.weight": torch.zeros(2, 2)}
    def failed_write(tensors, path, **kwargs):
        Path(path).write_bytes(b"incomplete")
        raise OSError("disk full")
    monkeypatch.setattr(safetensors.torch, "save_file", failed_write)
    with pytest.raises(OSError, match="disk full"):
        tools.save_tensors(state, target, overwrite=True)
    assert target.read_bytes() == before
    assert torch.equal(state["proj.weight"], torch.zeros(2, 2))
    assert not list(tmp_path.glob(".ray-*"))


def test_fast_merge_inference_uses_native_loader_and_remains_saveable(tmp_path, monkeypatch, native_flux):
    import folder_paths
    monkeypatch.setattr(folder_paths, "get_temp_directory", lambda: str(tmp_path))
    source = nodes.snapshot(native_flux, str(tmp_path / "base.safetensors"))
    output = nodes.RayModelMerge().merge(data_a=source, data_b=source, fast_merge=True)
    loaded, _, _, asset = output["result"][:4]
    assert loaded is not None and Path(asset.path).is_file()
    target = tmp_path / "saved.safetensors"
    nodes.RayModelSave().save(model_data=asset, output_folder=str(tmp_path), filename_prefix="saved")
    actual = load_file(target)
    assert set(actual) == set(asset.tensors)
    assert all(torch.equal(actual[k], tensor) for k, tensor in asset.tensors.items())


def test_merge_component_selection_block_weights_and_union(tmp_path):
    a = model(tmp_path, "a", {"x.weight": torch.ones(2, 2), "text_encoders.proj.weight": torch.ones(2, 2)})
    b = model(tmp_path, "b", {"x.weight": torch.zeros(2, 2), "other.weight": torch.ones(2, 2)})
    asset, _ = tools.merge_models(a, b, tmp_path / "out.safetensors", fmt="fp32", mismatch="intersect", block_weights={"x": .25})
    sd = load_file(asset.path)
    assert torch.equal(sd["x.weight"], torch.full((2, 2), .25))
    assert torch.equal(sd["text_encoders.proj.weight"], torch.ones(2, 2))
    assert "other.weight" in sd


@pytest.mark.parametrize("shape", [(6, 5), (6, 3, 3, 3), (6, 3, 1, 1)])
@pytest.mark.parametrize("alpha", [0., 3.])
def test_extraction_reconstructs_delta_and_alpha_uses_actual_rank(tmp_path, shape, alpha):
    torch.manual_seed(24)
    base_w = torch.randn(shape)
    left, right = torch.randn(shape[0], 2), torch.randn(2, torch.tensor(shape[1:]).prod().item())
    delta = (left @ right).reshape(shape)
    base = model(tmp_path, "base", {"proj.weight": base_w})
    ft = model(tmp_path, "ft", {"proj.weight": base_w + delta})
    asset, report = tools.extract_lora(ft, base, tmp_path / "lora.safetensors", rank=20, alpha=alpha, dtype="fp32")
    sd = load_file(asset.path)
    up, down = sd["diffusion_model.proj.lora_up.weight"], sd["diffusion_model.proj.lora_down.weight"]
    actual_rank = down.shape[0]
    rebuilt = (up.flatten(1) @ down.flatten(1)).reshape(shape) * sd["diffusion_model.proj.alpha"] / actual_rank
    assert torch.allclose(rebuilt, delta, atol=2e-5, rtol=2e-5)
    assert report["relative_error"] < .001


def test_quantized_extraction_uses_dequantized_values(tmp_path):
    base = model(tmp_path, "base", {"proj.weight": torch.zeros(4, 256)})
    ft = model(tmp_path, "ft", {"proj.weight": torch.ones(4, 256) * .02})
    quantized = tools.convert(ft, tmp_path / "q.safetensors", "int8_convrot")
    asset, _ = tools.extract_lora(quantized.path, base, tmp_path / "lora.safetensors", rank=4, dtype="fp32")
    sd = load_file(asset.path)
    rebuilt = sd["diffusion_model.proj.lora_up.weight"] @ sd["diffusion_model.proj.lora_down.weight"]
    assert torch.allclose(rebuilt, tools.TensorSource(quantized.path).dense("proj.weight"), atol=1e-5)


def test_no_difference_does_not_save_empty_lora(tmp_path):
    base = model(tmp_path, "base", {"proj.weight": torch.ones(2,2)})
    out = tmp_path / "lora.safetensors"
    with pytest.raises(ValueError, match="No nonzero"):
        tools.extract_lora(base, base, out)
    assert not out.exists()


def test_sdxl_text_encoder_extraction_splits_qkv_and_maps_native_keys(tmp_path, monkeypatch):
    import comfy.supported_models
    config = SimpleNamespace(process_clip_state_dict=lambda state:
        comfy.supported_models.SDXL.process_clip_state_dict(None, state))
    monkeypatch.setattr(tools, "model_config", lambda source: (config, ""))
    name = "conditioner.embedders.1.model.transformer.resblocks.0.attn.in_proj_weight"
    weight = torch.randn(12, 4)
    base = model(tmp_path, "base", {name: torch.zeros_like(weight)})
    ft = model(tmp_path, "ft", {name: weight})
    asset, report = tools.extract_lora(ft, base, tmp_path / "text.safetensors", rank=4, scope="text_encoder", dtype="fp32")
    sd = load_file(asset.path)
    for index, proj in enumerate(("q_proj", "k_proj", "v_proj")):
        prefix = f"text_encoders.clip_g.transformer.text_model.encoder.layers.0.self_attn.{proj}"
        assert torch.allclose(sd[prefix + ".lora_up.weight"] @ sd[prefix + ".lora_down.weight"], weight[index*4:(index+1)*4], atol=2e-6)
    assert report["extracted"] == 3


def test_inspect_is_header_only_and_compare_normalizes_prefixes(tmp_path, monkeypatch):
    a = model(tmp_path, "a", {"model.diffusion_model.proj.weight": torch.zeros(4, 8)}, {"title": "test"})
    b = model(tmp_path, "b", {"proj.weight": torch.zeros(4, 8).half()})
    monkeypatch.setattr(tools.TensorSource, "raw", lambda *_: (_ for _ in ()).throw(AssertionError("read weights")))
    report = tools.inspect_model(a, 1)
    assert report["tensor_bytes"] == 128 and report["stored_elements"] == 32
    assert report["metadata"]["title"] == "test"
    assert tools.compare_models(a, b)["structurally_compatible"]


@pytest.fixture
def native_flux():
    import comfy.ldm.flux.model
    import comfy.ops
    import comfy.sd
    params = dict(in_channels=16, out_channels=16, vec_in_dim=8, context_in_dim=16,
        hidden_size=128, mlp_ratio=4., num_heads=1, depth=1, depth_single_blocks=1,
        axes_dim=[16, 56, 56], theta=10000, patch_size=2, qkv_bias=True, guidance_embed=True, txt_ids_dims=[0])
    torch.manual_seed(30)
    module = comfy.ldm.flux.model.Flux(**params, operations=comfy.ops.disable_weight_init, dtype=torch.float32)
    # disable_weight_init intentionally leaves storage uninitialized.
    for parameter in module.parameters():
        parameter.data.normal_(0., .02)
    patcher = comfy.sd.load_diffusion_model_state_dict(module.state_dict(), model_options={"dtype": torch.float32})
    assert patcher is not None
    return patcher


def test_native_save_load_convert_and_lora_bake_roundtrip(tmp_path, monkeypatch, native_flux):
    import folder_paths
    monkeypatch.setattr(folder_paths, "get_temp_directory", lambda: str(tmp_path))
    monkeypatch.setattr(folder_paths, "get_output_directory", lambda: str(tmp_path))
    original = native_flux.model.diffusion_model.img_in.weight.detach().clone()
    delta = torch.ones_like(original) * .01
    patched = native_flux.clone()
    patched.add_patches({"diffusion_model.img_in.weight": ("diff", (delta,))}, 1.)
    nodes.attach_metadata(patched, {"custom": "retained"})
    saved = nodes.RayModelSave().save(output_folder=str(tmp_path), filename_prefix="patched", model=patched)
    asset = saved["result"][0]
    loaded, _, _ = nodes.load_asset(asset, dtype="fp32", components=False)
    assert torch.allclose(loaded.model.diffusion_model.img_in.weight, original + delta, atol=1e-6)
    base_asset = nodes.snapshot(native_flux, str(tmp_path / "base.safetensors"))
    lora, _ = tools.extract_lora(asset.path, base_asset.path, tmp_path / "delta.safetensors", rank=2, dtype="fp32")
    baked = nodes.RayLoraBake().bake("", lora_path=lora.path, model=native_flux, weight_format="fp32")
    baked_model = baked["result"][0]
    assert torch.allclose(baked_model.model.diffusion_model.img_in.weight, original + delta, atol=2e-6)
    assert not native_flux.patches
    # ComfyUI clones share physical storage and switch patches when loaded.
    # Re-export the original branch to test its effective state, not that cache.
    untouched = nodes.snapshot(native_flux, str(tmp_path / "untouched.safetensors"))
    key = next(k for k in tools.TensorSource(untouched.path).keys if k.endswith("img_in.weight"))
    assert torch.equal(tools.TensorSource(untouched.path).dense(key), original)
    assert tools.load_metadata(asset.path)["custom"] == "retained"
    converted = nodes.RayModelConvert().convert("int8_convrot", model=loaded)
    assert converted["result"][0] is not None
    saved_quant = nodes.RayModelSave().save(model=converted["result"][0], output_folder=str(tmp_path), filename_prefix="quant")
    quant_source = tools.TensorSource(saved_quant["result"][1])
    assert any(k.endswith(".comfy_quant") for k in quant_source.index)
    assert nodes.load_asset(saved_quant["result"][0], components=False)[0] is not None


def test_preview_route_requires_locality_and_returns_metadata(tmp_path, monkeypatch):
    import asyncio
    import importlib.util
    import sys
    import types
    from aiohttp import web
    from tests.test_route_security import request, invoke
    import route_security
    table = web.RouteTableDef()
    monkeypatch.setitem(sys.modules, "server", SimpleNamespace(PromptServer=SimpleNamespace(instance=SimpleNamespace(routes=table))))
    package = types.ModuleType("model_tools_route_tests")
    package.__path__ = [str(Path(__file__).parents[1])]
    monkeypatch.setitem(sys.modules, package.__name__, package)
    monkeypatch.setitem(sys.modules, package.__name__ + ".model_tools", tools)
    monkeypatch.setitem(sys.modules, package.__name__ + ".route_security", route_security)
    spec = importlib.util.spec_from_file_location(package.__name__ + ".model_tools_routes", Path(__file__).parents[1] / "model_tools_routes.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    source = model(tmp_path, "src", {"x": torch.ones(2)}, {"raw": "001"})
    response = invoke(module.preview, request(data={"action": "metadata", "path": source}))
    assert response.status == 200 and json.loads(response.text)["metadata"]["raw"] == "001"
    response = invoke(module.preview, request(data={"action": "metadata", "path": source}, peer="192.168.1.2"))
    assert response.status == 403
    response = invoke(module.preview, request(data={"action": "unknown"}))
    assert response.status == 400


def test_all_ten_nodes_are_registered_with_callable_schemas():
    for name in nodes.MODEL_IDS:
        cls = getattr(nodes, name)
        assert cls.CATEGORY == nodes.CATEGORY
        assert callable(getattr(cls, cls.FUNCTION))
        assert cls.INPUT_TYPES()["required"]


def test_bake_to_float_does_not_requantize_small_lora_delta(tmp_path, monkeypatch, native_flux):
    import folder_paths
    monkeypatch.setattr(folder_paths, "get_temp_directory", lambda: str(tmp_path))
    base = nodes.snapshot(native_flux, str(tmp_path / "base.safetensors"))
    quant = tools.convert(base.path, tmp_path / "quant.safetensors", "int8_row")
    source = tools.TensorSource(quant.path)
    key = next(k for k in source.keys if k.endswith("img_in.weight"))
    expected = source.dense(key) + 1e-5
    adapter = model(tmp_path, "adapter", {"diffusion_model.img_in.lora_up.weight":torch.full((128,1),1e-5),
                                         "diffusion_model.img_in.lora_down.weight":torch.ones(1,64),
                                         "diffusion_model.img_in.alpha":torch.tensor(1.)})
    baked = nodes.RayLoraBake().bake("", path=quant.path, lora_path=adapter, weight_format="fp32")
    assert torch.allclose(baked["result"][0].model.diffusion_model.img_in.weight, expected, atol=1e-7, rtol=1e-6)


@pytest.mark.parametrize("fmt", ["fp8_e4m3fn", "fp8_e4m3fn_scaled", "fp8_e5m2", "int8_row", "int8_convrot"])
def test_native_quantized_models_execute_linear_layers(tmp_path, monkeypatch, native_flux, fmt):
    import folder_paths
    from comfy.quant_ops import QuantizedTensor
    monkeypatch.setattr(folder_paths, "get_temp_directory", lambda: str(tmp_path))
    base = nodes.snapshot(native_flux, str(tmp_path / "base.safetensors"))
    converted = tools.convert(base.path, tmp_path / "quant.safetensors", fmt)
    loaded, _, _ = nodes.load_asset(converted, components=False)
    layer = loaded.model.diffusion_model.img_in
    assert isinstance(layer.weight, QuantizedTensor)
    output = layer(torch.randn(1, 2, 64))
    assert output.shape == (1, 2, 128) and torch.isfinite(output).all()


def test_metadata_save_nodes_and_stale_editor_source(tmp_path):
    source = model(tmp_path, "src", {"x": torch.ones(2)})
    meta = {"text": "001", "data": {"x": [1, True]}}
    output = tmp_path / "metadata.json"
    nodes.RayModelMetadataSave().save(metadata=meta, output_path=str(output))
    assert nodes.RayModelMetadata().load(path=str(output))["result"][0] == meta
    with pytest.raises(ValueError, match="source path changed"):
        nodes.RayModelMetadata().load(path=str(output), editor_json="{}", editor_source=source)


def test_save_keeps_current_operation_history_when_given_old_metadata(tmp_path):
    meta = tools.with_history({}, "merge", strategy="LERP")
    source = model(tmp_path, "src", {"proj.weight":torch.ones(2,2)}, meta)
    output = tmp_path / "saved.safetensors"
    nodes.RayModelSave().save(path=source, metadata={tools.HISTORY:'[]'}, output_path=str(output))
    assert [item["operation"] for item in json.loads(tools.load_metadata(output)[tools.HISTORY])] == ["merge", "save"]


def test_auto_loader_normalizes_legacy_scaled_fp8_checkpoint(tmp_path, monkeypatch, native_flux):
    import folder_paths
    from comfy.quant_ops import QuantizedTensor
    monkeypatch.setattr(folder_paths, "get_temp_directory", lambda: str(tmp_path))
    base = nodes.snapshot(native_flux, str(tmp_path / "base.safetensors"))
    native = tools.convert(base.path, tmp_path / "native.safetensors", "fp8_e4m3fn_scaled")
    state = load_file(native.path)
    legacy = {k.replace(".weight_scale", ".scale_weight"):v for k,v in state.items() if not k.endswith(".comfy_quant")}
    legacy["scaled_fp8"] = torch.empty(0, dtype=torch.float8_e4m3fn)
    src = model(tmp_path, "legacy", legacy)
    output = nodes.RayModelLoadAs().load("", path=src, weight_format="auto", load_components=False)
    assert isinstance(output["result"][0].model.diffusion_model.img_in.weight, QuantizedTensor)
    assert output["ui"]["model_tools"][0]["weight_format"] == "fp8_e4m3fn_scaled"
