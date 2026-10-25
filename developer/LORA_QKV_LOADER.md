# LoRA QKV loader checks

`tests/test_lora_qkv_loader.py` exercises native ComfyUI adapter loading and
weight calculations with small CPU tensors. Set `COMFYUI_ROOT` to a ComfyUI
checkout and run `python -m pytest tests/test_lora_qkv_loader.py` with its Python
environment (plus pytest). The tests skip when ComfyUI is unavailable.

Coverage includes native pass-through, PEFT/trainer aliases, unequal Q/K/V
dimensions, LoRA, output-axis DoRA, linear LoHa, aligned LoKr, weight differences,
fused model slices, ambiguous names, unsupported conversions, stack ordering,
negative/zero strengths, model cloning, metadata and file-change invalidation.

The repair layer extends a per-call key map and copies the adapter dictionary.
It never patches global loaders, changes registered native targets, rewrites
source files, or materializes a full dense weight difference to convert a LoRA.
Fused-to-separate conversion uses the actual three model output widths.
Separate-to-fused fallback requires a complete triplet whose dimensions span
the fused parameter; otherwise leave the native behavior and report unmatched
modules. Only known concatenated `qkv` / `to_qkv` naming is inferred. Packed
interleaved projections need an architecture-specific native mapping.
