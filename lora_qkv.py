"""Conservative adapter repairs against a model's native LoRA key map."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field


# Native tensor spellings are retained, including PEFT and LyCORIS variants.
SUFFIXES = sorted({
    "lora_up.weight", "lora_down.weight", "lora_mid.weight", "alpha", "dora_scale",
    "lora_A.default.weight", "lora_B.default.weight", "lora_A.weight", "lora_B.weight",
    "lora.up.weight", "lora.down.weight", "lora_A", "lora_B",
    "lora_linear_layer.up.weight", "lora_linear_layer.down.weight",
    "diff", "diff_b", "set_weight", "w_norm", "b_norm", "reshape_weight",
    "hada_w1_a", "hada_w1_b", "hada_w2_a", "hada_w2_b", "hada_t1", "hada_t2",
    "lokr_w1", "lokr_w1_a", "lokr_w1_b", "lokr_w2", "lokr_w2_a", "lokr_w2_b", "lokr_t2",
}, key=len, reverse=True)
UP_DOWN = (
    ("lora_up.weight", "lora_down.weight"),
    ("lora_B.default.weight", "lora_A.default.weight"),
    ("lora_B.weight", "lora_A.weight"), ("lora.up.weight", "lora.down.weight"),
    ("lora_B", "lora_A"), ("lora_linear_layer.up.weight", "lora_linear_layer.down.weight"),
)
PREFIXES = (
    "unet.base_model.model.", "base_model.model.", "model.diffusion_model.",
    "diffusion_model.", "transformer.", "pipe.dit.", "dit.", "unet.",
    "lora_transformer_", "lora_unet_", "lycoris_",
)
FAMILIES = (("q", "k", "v"), ("q_proj", "k_proj", "v_proj"),
            ("to_q", "to_k", "to_v"), ("query", "key", "value"))


@dataclass
class RepairReport:
    aliases: int = 0
    split: int = 0
    sliced: int = 0
    warnings: list[str] = field(default_factory=list)
    unmatched: list[str] = field(default_factory=list)


def module_key(key):
    for suffix in SUFFIXES:
        if key.endswith("." + suffix):
            return key[:-len(suffix)-1], suffix
    return None


def identity(name):
    # Resolve aliases only when the result identifies exactly one native target.
    previous = None
    while previous != name:
        previous = name
        for prefix in PREFIXES:
            if name.startswith(prefix):
                name = name[len(prefix):]
                break
    return name.replace(".", "").replace("_", "")


def target_shape(target, state):
    key = target[0] if isinstance(target, tuple) else target
    tensor = state.get(key)
    if tensor is None:
        return None
    shape = list(tensor.shape)
    if isinstance(target, tuple):
        # Other tuple forms can include custom patch functions; do not guess.
        if len(target) != 2 or not isinstance(target[1], tuple) or len(target[1]) != 3:
            return None
        axis, start, length = target[1]
        if axis != 0 or start < 0 or length <= 0 or start + length > shape[0]:
            return None
        shape[0] = length
    return tuple(shape)


def _leaf(name, leaves):
    for leaf in sorted(leaves, key=len, reverse=True):
        for separator in (".", "_"):
            if name.endswith(separator + leaf):
                return name[:-len(leaf)-1], leaf
    return None


def _output_rows(tensors):
    for up, _ in UP_DOWN:
        if up in tensors:
            return tensors[up].shape[0]
    for name in ("diff", "hada_w1_a"):
        if name in tensors:
            return tensors[name].shape[0]
    first = tensors.get("lokr_w1", tensors.get("lokr_w1_a"))
    second = tensors.get("lokr_w2", tensors.get("lokr_w2_a"))
    if first is not None and second is not None:
        return first.shape[0] * second.shape[0]
    return None


def _partition(tensors, shapes):
    """Split supported linear adapters by actual target output widths."""
    if any(shape is None or len(shape) != 2 for shape in shapes):
        return "target projections are not plain linear weights"
    widths = [shape[0] for shape in shapes]
    rows = sum(widths)
    if len({shape[1] for shape in shapes}) != 1 or _output_rows(tensors) != rows:
        return "adapter output dimensions do not match the model's Q/K/V projections"
    row_axes, shared = {}, {"alpha"}
    pair = next(((up, down) for up, down in UP_DOWN if up in tensors and down in tensors), None)
    if pair:
        up, down = pair
        if tensors[up].ndim != 2 or tensors[down].ndim != 2 or tensors[down].shape[1] != shapes[0][1]:
            return "adapter input dimensions do not match the model's linear projections"
        if tensors[up].shape[1] != tensors[down].shape[0]:
            return "LoRA up/down ranks do not agree"
        row_axes[up] = 1
        shared.add(down)
    elif {"hada_w1_a", "hada_w1_b", "hada_w2_a", "hada_w2_b"} <= tensors.keys():
        if any(tensors[name].ndim != 2 for name in ("hada_w1_a", "hada_w1_b", "hada_w2_a", "hada_w2_b")):
            return "convolutional LoHa cannot be partitioned as linear QKV"
        if any(tensors[name].shape[1] != shapes[0][1] for name in ("hada_w1_b", "hada_w2_b")):
            return "LoHa input dimensions do not match the model"
        row_axes.update({"hada_w1_a": 1, "hada_w2_a": 1})
        shared.update({"hada_w1_b", "hada_w2_b"})
    elif any(name.startswith("lokr_") for name in tensors):
        first = "lokr_w1" if "lokr_w1" in tensors else "lokr_w1_a"
        second = tensors.get("lokr_w2", tensors.get("lokr_w2_a"))
        if first not in tensors or second is None or "lokr_t2" in tensors:
            return "this LoKr factorization cannot be partitioned exactly"
        factor = second.shape[0]
        first_input = tensors.get("lokr_w1", tensors.get("lokr_w1_b"))
        second_input = tensors.get("lokr_w2", tensors.get("lokr_w2_b"))
        if (first_input is None or second_input is None or
                any(tensor.ndim != 2 for name, tensor in tensors.items() if name.startswith("lokr_")) or
                first_input.shape[1] * second_input.shape[1] != shapes[0][1]):
            return "LoKr input factors do not match the model's linear projections"
        if any(width % factor for width in widths):
            return "Q/K/V boundaries do not align with the LoKr factors"
        row_axes[first] = factor
        shared.update(set(tensors) & {"lokr_w1_b", "lokr_w2", "lokr_w2_a", "lokr_w2_b"})
    elif "diff" in tensors:
        if tuple(tensors["diff"].shape) != (rows, shapes[0][1]):
            return "weight difference dimensions do not match the model"
        row_axes["diff"] = 1
    else:
        return "this adapter type cannot be partitioned exactly"
    if "dora_scale" in tensors:
        if tensors["dora_scale"].ndim == 0 or tensors["dora_scale"].shape[0] != rows:
            return "DoRA scale is not on the output axis"
        row_axes["dora_scale"] = 1
    unsupported = set(tensors) - shared - row_axes.keys()
    if unsupported:
        return "cannot safely partition " + ", ".join(sorted(unsupported))
    for name, factor in row_axes.items():
        if tensors[name].shape[0] * factor != rows:
            return f"{name} does not span the QKV output rows"
    outputs, offset = [], 0
    for width in widths:
        outputs.append({name: (tensor[offset // row_axes[name]:(offset + width) // row_axes[name]]
                               if name in row_axes else tensor) for name, tensor in tensors.items()})
        offset += width
    return outputs


def repair_lora(lora, key_map, state):
    """Return a copied key map/state dict; already recognized adapters stay native."""
    fixed, mapping, report = dict(lora), dict(key_map), RepairReport()
    index = defaultdict(set)
    for name, target in key_map.items():
        try:
            index[identity(name)].add(target)
        except TypeError:
            continue

    def resolve(name):
        if name in mapping:
            return mapping[name]
        targets = index.get(identity(name), ())
        return next(iter(targets)) if len(targets) == 1 else None

    groups = defaultdict(dict)
    for key, tensor in lora.items():
        parsed = module_key(key)
        if parsed:
            module, suffix = parsed
            groups[module][suffix] = tensor
    occupied = [mapping[module] for module in groups if module in mapping]
    for module in groups:
        if module not in mapping:
            target = resolve(module)
            if target is not None:
                if target in occupied:
                    report.warnings.append(f"{module}: duplicate target; existing native adapter kept")
                    continue
                mapping[module] = target
                occupied.append(target)
                report.aliases += 1

    # A separate adapter can use slices of an existing fused model parameter.
    # Infer unequal Q/K/V widths only from a complete adapter triplet.
    separate = defaultdict(dict)
    leaves = [part for family in FAMILIES for part in family]
    for module, tensors in groups.items():
        if module in mapping:
            continue
        parsed = _leaf(module, leaves)
        if parsed:
            stem, leaf = parsed
            family = next(family for family in FAMILIES if leaf in family)
            separate[(stem, family)][leaf] = (module, tensors)
    for (stem, family), parts in separate.items():
        target = next((value for packed in ("qkv", "to_qkv")
                       if (value := resolve(stem + "." + packed)) is not None), None)
        if target is None or isinstance(target, tuple) or set(parts) != set(family):
            continue
        if target in occupied:
            report.warnings.append(f"{stem}: overlaps a fused adapter; existing native adapter kept")
            continue
        shape = target_shape(target, state)
        widths = [_output_rows(parts[part][1]) for part in family]
        if shape is None or len(shape) != 2 or None in widths or sum(widths) != shape[0]:
            report.warnings.append(f"{stem}: separate Q/K/V sizes do not match the fused model weight")
            continue
        offset = 0
        for part, width in zip(family, widths):
            mapping[parts[part][0]] = (target, (0, offset, width))
            offset += width
            report.sliced += 1

    for module, tensors in groups.items():
        if module in mapping:
            continue
        parsed = _leaf(module, ("qkv", "to_qkv"))
        if not parsed:
            continue
        stem, _ = parsed
        targets = None
        for family in FAMILIES:
            candidates = [resolve(stem + "." + part) for part in family]
            if all(value is not None for value in candidates) and len(set(candidates)) == 3:
                targets = candidates
                break
        if targets is None:
            continue
        if any(target in occupied for target in targets):
            report.warnings.append(f"{module}: overlaps separate adapters; existing native adapters kept")
            continue
        partition = _partition(tensors, [target_shape(target, state) for target in targets])
        if isinstance(partition, str):
            report.warnings.append(f"{module}: {partition}; adapter kept unchanged")
            continue
        for suffix in tensors:
            fixed.pop(module + "." + suffix)
        for part, (target, values) in enumerate(zip(targets, partition)):
            alias = f"__ray_qkv_{report.split}_{part}"
            while alias in mapping or any(key.startswith(alias + ".") for key in fixed):
                alias += "_"
            mapping[alias] = target
            fixed.update({alias + "." + suffix: tensor for suffix, tensor in values.items()})
        report.split += 1
        occupied.extend(targets)
    report.unmatched = [module for module in groups if module not in mapping
                        and any(key.startswith(module + ".") for key in fixed)]
    return fixed, mapping, report
