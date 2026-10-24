"""Model-only LoRA stacking with automatic compatibility repairs."""
from __future__ import annotations

import json
import logging
import math
from pathlib import Path

import folder_paths

if __package__:
    from .lora_qkv import repair_lora
else:
    from lora_qkv import repair_lora


PLACEHOLDER = "Select a LoRA…"


def strength_value(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or abs(value) > 100:
        raise ValueError("LoRA strength must be a finite number between -100 and 100.")
    return float(value)


def selections(lora_name=PLACEHOLDER, strength=1., additional_loras="[]"):
    strength_value(strength)
    try:
        rest = json.loads(additional_loras)
    except (ValueError, TypeError) as error:
        raise ValueError("The additional LoRA rows must be a JSON array.") from error
    if not isinstance(rest, list) or len(rest) > 255:
        raise ValueError("Use an array with at most 255 additional LoRA rows.")
    rows = [{"name": lora_name, "strength": strength}, *rest]
    if len(rows) == 1 and lora_name in ("", PLACEHOLDER):
        return []
    result = []
    for index, row in enumerate(rows, 1):
        if not isinstance(row, dict) or set(row) != {"name", "strength"}:
            raise ValueError(f"LoRA {index}: each row needs a name and strength.")
        value = strength_value(row["strength"])
        name = row["name"]
        if not isinstance(name, str) or not name.strip() or name == PLACEHOLDER:
            raise ValueError(f"LoRA {index}: choose a LoRA or remove the empty row.")
        result.append((name, value))
    return result


def lora_path(name):
    name = name.strip().strip('"')
    path = folder_paths.get_full_path("loras", name)
    if path is None and Path(name).is_absolute():
        path = name
    if not path or not Path(path).is_file():
        raise ValueError(f"LoRA file not found: {name}")
    if Path(path).suffix.lower() not in folder_paths.supported_pt_extensions:
        raise ValueError("Choose a LoRA file supported by ComfyUI's native loader.")
    return str(path)


class RayLoraQKVLoader:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "model": ("MODEL",),
            "lora_name": ("STRING", {"default": "", "tooltip": "Choose a registered LoRA or use the file button."}),
            "strength": ("FLOAT", {"default": 1., "min": -100., "max": 100., "step": .01}),
            "additional_loras": ("STRING", {"default": "[]", "tooltip": "Additional LoRA rows with independent strengths, applied in order."}),
        }}

    RETURN_TYPES = ("MODEL",)
    RETURN_NAMES = ("MODEL",)
    FUNCTION = "load"
    CATEGORY = "👑 Ray/🧰 Model Tools"
    DESCRIPTION = "Load and stack LoRAs with +, trash and a strength per row. Automatically checks the connected model's native parameter map, repairs unambiguous trainer naming and supported fused/separate QKV mismatches, and otherwise uses native adapters. Applies to the MODEL only. Zero strength skips a row; an empty list passes the model through. Incompatible or unsafe repairs are reported."

    @classmethod
    def VALIDATE_INPUTS(cls, lora_name=None, strength=None, additional_loras=None):
        # Linked values are available only at execution; validate the full stack there.
        if lora_name is None or strength is None or additional_loras is None:
            return True
        try:
            for name, value in selections(lora_name, strength, additional_loras):
                if value:
                    lora_path(name)
        except ValueError as error:
            return str(error)
        return True

    @classmethod
    def IS_CHANGED(cls, lora_name=PLACEHOLDER, strength=1., additional_loras="[]", **kwargs):
        try:
            result = []
            for name, value in selections(lora_name, strength, additional_loras):
                if value:
                    path = lora_path(name)
                    stat = Path(path).stat()
                    result.append((path, stat.st_size, stat.st_mtime_ns))
            return tuple(result)
        except (ValueError, OSError):
            return float("nan")

    def load(self, model, lora_name=PLACEHOLDER, strength=1., additional_loras="[]"):
        import comfy.lora
        import comfy.lora_convert
        import comfy.utils
        rows = selections(lora_name, strength, additional_loras)
        # Resolve every enabled file before reading or applying the first adapter.
        paths = [lora_path(name) if value else None for name, value in rows]
        reports = []
        current = model
        for (name, value), path in zip(rows, paths):
            if not value:
                reports.append({"name": name, "strength": value, "skipped": True})
                continue
            raw, metadata = comfy.utils.load_torch_file(path, safe_load=True, return_metadata=True)
            converted = comfy.lora_convert.convert_lora(raw)
            mapping = comfy.lora.model_lora_keys_unet(current.model, {})
            fixed, mapping, repair = repair_lora(converted, mapping, current.model.state_dict())
            loaded = comfy.lora.load_lora(fixed, mapping, log_missing=False)
            patched = current.clone()
            accepted = set(patched.add_patches(loaded, value))
            if metadata:
                patched.set_attachments("lora_metadata", metadata)
            rejected = [str(key) for key in loaded if key not in accepted]
            warnings = list(repair.warnings)
            if not accepted:
                warnings.append("No model weights matched this LoRA. Check that it was trained for the connected model.")
            if repair.unmatched:
                warnings.append(f"{len(repair.unmatched)} adapter modules did not match the model (including any text-encoder modules).")
            if rejected:
                warnings.append(f"{len(rejected)} patch targets were rejected by the model.")
            for warning in warnings:
                logging.warning("[LoRA QKV Loader] %s: %s", name, warning)
            reports.append({"name": name, "strength": value, "loaded": len(accepted),
                            "aliases": repair.aliases, "split": repair.split, "sliced": repair.sliced,
                            "warnings": warnings, "unmatched": repair.unmatched, "rejected": rejected})
            current = patched
        return {"ui": {"lora_qkv": reports}, "result": (current,)}
