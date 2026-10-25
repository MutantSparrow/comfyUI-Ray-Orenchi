"""Native adapter math, conservative repairs, and model-only stack loading."""
import copy
import json
import os
import sys
from types import SimpleNamespace

import pytest
torch = pytest.importorskip("torch")
from safetensors.torch import save_file

if os.environ.get("COMFYUI_ROOT"):
    sys.path.insert(0, os.environ["COMFYUI_ROOT"])
pytest.importorskip("comfy.cli_args", reason="Set COMFYUI_ROOT to run native LoRA integration tests")
import comfy.cli_args
comfy.cli_args.args.cpu = True
import comfy.lora
import comfy.model_base
from lora_qkv import repair_lora
from ray_lora_qkv_loader import RayLoraQKVLoader, selections


def apply(lora, module, weight, strength=.7):
    patch = comfy.lora.load_lora(lora, {module: "weight"}, log_missing=False)["weight"]
    if isinstance(patch, tuple):
        assert patch[0] == "diff"
        return weight + strength * patch[1][0]
    return patch.calculate_weight(weight.clone(), "weight", strength, 1., None, lambda value: value)


def standard(module, rows=12, rank=2, peft=False):
    up, down = ("lora_B.default.weight", "lora_A.default.weight") if peft else ("lora_up.weight", "lora_down.weight")
    return {module + "." + up: torch.randn(rows, rank),
            module + "." + down: torch.randn(rank, 4), module + ".alpha": torch.tensor(1.25)}


@pytest.mark.parametrize("kind", ["lora", "peft", "dora", "loha", "lokr", "diff"])
def test_split_preserves_native_adapter_math_and_unequal_projection_sizes(kind):
    torch.manual_seed(32)
    module = "transformer.layers.0.proj.qkv"
    lora = standard(module, peft=kind == "peft")
    if kind == "dora":
        lora[module + ".dora_scale"] = torch.rand(12, 1)
    elif kind == "loha":
        lora = {module + "." + name: torch.randn(shape) for name, shape in {
            "hada_w1_a": (12, 2), "hada_w1_b": (2, 4),
            "hada_w2_a": (12, 2), "hada_w2_b": (2, 4)}.items()}
        lora[module + ".alpha"] = torch.tensor(.8)
    elif kind == "lokr":
        lora = {module + ".lokr_w1": torch.randn(6, 2), module + ".lokr_w2": torch.randn(2, 2)}
    elif kind == "diff":
        lora = {module + ".diff": torch.randn(12, 4)}
    base = torch.randn(12, 4)
    native = apply(lora, module, base)
    widths = (6, 4, 2)
    state = {f"diffusion_model.layers.0.proj.{part}.weight": torch.empty(width, 4)
             for part, width in zip("qkv", widths)}
    mapping = {key[:-7]: key for key in state}
    before = dict(lora)
    fixed, adapted_map, report = repair_lora(lora, mapping, state)
    assert report.split == 1
    assert not report.unmatched and not report.warnings
    assert set(lora) == set(before) and all(lora[key] is before[key] for key in before)
    pieces, offset = [], 0
    for index, width in enumerate(widths):
        alias = next(name for name, target in adapted_map.items()
                     if name.startswith("__ray_qkv") and target.endswith(f".{ 'qkv'[index] }.weight"))
        pieces.append(apply(fixed, alias, base[offset:offset + width]))
        offset += width
    torch.testing.assert_close(torch.cat(pieces), native)


def test_native_adapters_and_unrelated_keys_are_unchanged():
    module = "lora_unet_down_blocks_0_attentions_0_to_q"
    lora = standard(module, rows=4)
    lora["unrelated.control"] = torch.tensor(3.)
    mapping = {module: "diffusion_model.down_blocks.0.attentions.0.to_q.weight"}
    fixed, adapted, report = repair_lora(lora, mapping, {})
    assert adapted == mapping and fixed.keys() == lora.keys()
    assert all(fixed[key] is value for key, value in lora.items())
    assert report.aliases == report.split == report.sliced == 0


@pytest.mark.parametrize("prefix", ["transformer.", "base_model.model.", "pipe.dit.", "lora_unet_"])
def test_unambiguous_trainer_names_match_real_targets(prefix):
    module = prefix + ("layers_0_proj_q" if prefix.endswith("_") else "layers.0.proj.q")
    target = "diffusion_model.layers.0.proj.q.weight"
    lora = standard(module, rows=4, peft=True)
    fixed, mapping, report = repair_lora(lora, {target[:-7]: target}, {target: torch.empty(4, 4)})
    assert mapping[module] == target and report.aliases == 1
    assert len(comfy.lora.load_lora(fixed, mapping, log_missing=False)) == 1


def test_ambiguous_alias_is_not_guessed():
    lora = standard("transformer.a_b.c", rows=4)
    mapping = {"diffusion_model.a.b_c": "first.weight", "diffusion_model.a_b.c": "second.weight"}
    fixed, adapted, report = repair_lora(lora, mapping, {})
    assert adapted == mapping and report.unmatched == ["transformer.a_b.c"]
    assert fixed.keys() == lora.keys()


def test_repairs_cannot_overwrite_an_existing_native_adapter():
    native = "diffusion_model.block.attn.q"
    lora = {**standard(native, rows=4), **standard("transformer.block.attn.q", rows=4),
            **standard("transformer.block.attn.qkv")}
    state = {f"diffusion_model.block.attn.{part}.weight": torch.empty(4, 4) for part in "qkv"}
    fixed, mapping, report = repair_lora(lora, {key[:-7]: key for key in state}, state)
    assert report.aliases == report.split == 0 and len(report.warnings) == 2
    patches = comfy.lora.load_lora(fixed, mapping, log_missing=False)
    assert list(patches) == [native + ".weight"]
    torch.testing.assert_close(apply(fixed, native, torch.zeros(4, 4)), apply(lora, native, torch.zeros(4, 4)))


def test_separate_adapters_map_to_fused_slices_without_rank_expansion():
    torch.manual_seed(17)
    lora = {}
    for part, width in zip("qkv", (6, 4, 2)):
        lora.update(standard("transformer.block.attn." + part, rows=width))
    target = "diffusion_model.block.attn.qkv.weight"
    fixed, mapping, report = repair_lora(lora, {target[:-7]: target}, {target: torch.empty(12, 4)})
    patches = comfy.lora.load_lora(fixed, mapping, log_missing=False)
    assert report.sliced == 3 and not report.unmatched
    assert {key[1] for key in patches} == {(0, 0, 6), (0, 6, 4), (0, 10, 2)}
    assert all(fixed[key] is value for key, value in lora.items())
    result = torch.zeros(12, 4)
    expected = []
    for part, width in zip("qkv", (6, 4, 2)):
        expected.append(apply(lora, "transformer.block.attn." + part, torch.zeros(width, 4)))
    for (_, (_, start, width)), patch in patches.items():
        result[start:start + width] = patch.calculate_weight(result[start:start + width].clone(), target, .7, 1., None, lambda value: value)
    torch.testing.assert_close(result, torch.cat(expected))


def test_separate_repair_cannot_double_apply_an_existing_fused_adapter():
    native = "diffusion_model.block.attn.qkv"
    lora = standard(native)
    for part in "qkv":
        lora.update(standard("transformer.block.attn." + part, rows=4))
    target = native + ".weight"
    fixed, mapping, report = repair_lora(lora, {native: target}, {target: torch.empty(12, 4)})
    assert report.sliced == 0 and len(report.warnings) == 1
    assert list(comfy.lora.load_lora(fixed, mapping, log_missing=False)) == [target]


@pytest.mark.parametrize("problem", ["missing_triplet", "bad_shape", "input_dora", "mid", "bias"])
def test_unsafe_or_incomplete_qkv_conversion_keeps_original_tensors(problem):
    module = "block.attn.qkv"
    lora = standard(module)
    state = {f"diffusion_model.block.attn.{part}.weight": torch.empty(4, 4) for part in "qkv"}
    if problem == "missing_triplet":
        del state["diffusion_model.block.attn.v.weight"]
    elif problem == "bad_shape":
        state["diffusion_model.block.attn.q.weight"] = torch.empty(5, 4)
    elif problem == "input_dora":
        lora[module + ".dora_scale"] = torch.ones(1, 4)
    elif problem == "mid":
        lora[module + ".lora_mid.weight"] = torch.randn(2, 2, 3, 3)
    elif problem == "bias":
        lora[module + ".diff_b"] = torch.ones(12)
    mapping = {key[:-7]: key for key in state}
    fixed, _, report = repair_lora(lora, mapping, state)
    assert report.split == 0 and report.unmatched == [module]
    assert fixed.keys() == lora.keys() and all(fixed[key] is value for key, value in lora.items())


class SmallMOSS(comfy.model_base.MOSSImage):
    def __init__(self):
        torch.nn.Module.__init__(self)
        self.model_config = SimpleNamespace(unet_config={"image_model": "moss_image"})
        self.sd = {f"diffusion_model.layers.0.proj.{part}.weight": torch.zeros(4, 4) for part in "qkv"}

    def state_dict(self):
        return self.sd


class Patcher:
    def __init__(self):
        self.model, self.patches, self.attachments = SmallMOSS(), [], {}

    def clone(self):
        result = copy.copy(self)
        result.patches, result.attachments = list(self.patches), dict(self.attachments)
        return result

    def add_patches(self, patches, strength):
        self.patches.append((patches, strength))
        return list(patches)

    def set_attachments(self, key, value):
        self.attachments[key] = value


def test_stack_uses_native_adapters_in_order_with_independent_strengths(tmp_path):
    first, second = tmp_path / "fused.safetensors", tmp_path / "peft.safetensors"
    save_file(standard("lora_unet_layers_0_proj_qkv"), str(first), metadata={"name": "first"})
    save_file(standard("layers.0.proj.q", rows=4, peft=True), str(second))
    base = Patcher()
    result = RayLoraQKVLoader().load(base, str(first), .8, json.dumps([
        {"name": str(second), "strength": -.3}, {"name": "missing.safetensors", "strength": 0.}]))
    model = result["result"][0]
    assert not base.patches and model is not base
    assert [strength for _, strength in model.patches] == [.8, -.3]
    assert [len(patches) for patches, _ in model.patches] == [3, 1]
    reports = result["ui"]["lora_qkv"]
    assert reports[0]["split"] == 1 and reports[1]["loaded"] == 1 and reports[2]["skipped"]
    assert model.attachments["lora_metadata"] == {"name": "first"}


def test_empty_stack_passes_through_and_files_invalidate_cache(tmp_path):
    model = Patcher()
    assert RayLoraQKVLoader().load(model)["result"][0] is model
    source = tmp_path / "lora.safetensors"
    save_file(standard("layers.0.proj.q", rows=4), str(source))
    before = RayLoraQKVLoader.IS_CHANGED(str(source))
    save_file(standard("layers.0.proj.q", rows=4, rank=3), str(source))
    assert RayLoraQKVLoader.IS_CHANGED(str(source)) != before


@pytest.mark.parametrize("peft", [False, True])
def test_ordinary_loading_matches_native_model_patcher_and_weight_math(tmp_path, peft):
    import comfy.model_patcher
    import comfy.sd
    base = comfy.model_patcher.ModelPatcher(SmallMOSS(), torch.device("cpu"), torch.device("cpu"))
    lora = standard("lora_unet_layers_0_proj_q", rows=4, peft=peft)
    source = tmp_path / "native.safetensors"
    save_file(lora, str(source))
    native = comfy.sd.load_lora_for_models(base, None, lora, .6, 0)[0]
    assert native.patches, "The reference adapter must load through native ComfyUI"
    result = RayLoraQKVLoader().load(base, str(source), .6)
    actual = result["result"][0]
    assert actual.patches.keys() == native.patches.keys() and not base.patches
    for key in native.patches:
        # The ordinary LoRA delta is independent of the base weight.
        zeros = torch.zeros(4, 4)
        torch.testing.assert_close(comfy.lora.calculate_weight(actual.patches[key], zeros.clone(), key),
                                   comfy.lora.calculate_weight(native.patches[key], zeros.clone(), key))
    assert result["ui"]["lora_qkv"][0]["aliases"] == 0


@pytest.mark.parametrize("value", [float("nan"), float("inf"), True, 101, "1"])
def test_invalid_strength_is_rejected(value):
    with pytest.raises(ValueError, match="strength"):
        selections("some.safetensors", value)


def test_linked_values_validate_when_available_and_schema_has_only_model_output():
    assert RayLoraQKVLoader.VALIDATE_INPUTS() is True
    assert RayLoraQKVLoader.RETURN_TYPES == ("MODEL",)
    assert RayLoraQKVLoader.INPUT_TYPES()["required"]["lora_name"][0] == "STRING"
    assert "not found" in RayLoraQKVLoader.VALIDATE_INPUTS("missing.safetensors", 1., "[]")
    with pytest.raises(ValueError, match="LoRA 2"):
        selections("first.safetensors", 1, '[{"name":"","strength":1}]')
