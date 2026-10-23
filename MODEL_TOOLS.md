# Ray's Model Tools

Ten nodes under **👑 Ray / 🧰 Model Tools**. They run inside ComfyUI; the standalone
ModelMergeTools app and its FastAPI server are not required.

| Node | Purpose |
| --- | --- |
| [Load Model As](screenshots/RayModelLoadAs.png) | Select a checkpoint/diffusion model, or browse to a safetensors file/sharded directory. Auto detects the loader. |
| [Convert Model](screenshots/RayModelConvert.png) | Convert a file or connected MODEL into another storage format. |
| [Save Model](screenshots/RayModelSave.png) | Save the effective model, including active merge and LoRA patches, with optional CLIP/VAE and metadata. |
| [Metadata Load / Edit](screenshots/RayModelMetadata.png) | Read model metadata or a JSON sidecar into an editable table and raw JSON editor. |
| [Metadata Save](screenshots/RayModelMetadataSave.png) | Save a structured JSON sidecar, or apply metadata to a model copy without changing tensor bytes. |
| [Model Merge](screenshots/RayModelMerge.png) | LERP, SLERP, TIES, DARE-Linear, DARE-TIES, DELLA, DELLA-TIES, Breadcrumbs, Breadcrumbs-TIES. |
| [Model Inspector](screenshots/RayModelInspector.png) | Header-only tensor listing, dtype distribution, byte counts, and architecture detection. |
| [Model Compare](screenshots/RayModelCompare.png) | Compare names, shapes and dtypes before merging. |
| [LoRA Bake](screenshots/RayLoraBake.png) | Bake an adapter using ComfyUI's adapter mappings and supported LoRA variants. |
| [LoRA Extract](screenshots/RayLoraExtract.png) | SVD extraction from finetuned minus base, including convolution weights. |

Node names in the table link to their default Nodes 2.0 screenshot. The [node reference](NODES.md) embeds every image.

## Connections and file-only processing

MODEL, CLIP and VAE are normal ComfyUI connections. **model_data** is a Ray
handle to a safetensors file; use it between file operations and Save Model.
**metadata** is a structured connection shared by metadata and save nodes.
Reports are also available as STRING outputs.

A connected MODEL takes priority over model_data and path inputs. Operations on
a live MODEL export its effective weights through ComfyUI's save API first.
Connect CLIP/VAE when those components need to travel with it. A MODEL alone
contains the diffusion model, not the full original checkpoint.

For offline work, use paths or model_data and turn **load_result off**. Connect
the resulting model_data to Save Model to persist it, or to Load Model As to
load it later. File operations use CPU math and temporary disk storage, one
layer at a time rather than complete fp32 copies of all inputs. SVD still needs
memory for the largest individual matrix. Temporary artifacts live under
ComfyUI's temp directory in `ray_model_tools`; save anything you want to retain.

## Precision and quantization

Targets: fp32, fp16, bf16, FP8 E4M3 (raw or scaled), FP8 E5M2, native INT8 with
tensor or row scales, and native INT8 ConvRot. Quantized output targets eligible
2D Linear weights; convolutions, embeddings, normalization weights and biases
stay bf16. ConvRot uses comfy-kitchen's native rotation, group 256, and falls
back to unrotated native row INT8 when a Linear input dimension is not divisible
by 256. Runtime acceleration depends on the device and installed backend.

Auto delegates loading precision to ComfyUI. Preserve retains source storage
where the native loader supports it. The standalone suite's legacy INT8 format
is decoded and re-encoded into native row INT8 when loaded automatically.
Legacy scaled FP8 is normalized into native scaled FP8 markers as well.
FP8→FP16 expands the stored approximation; it cannot recover lost precision.
FP8→INT8 introduces another quantization step. Explicit fp16 conversion fails
on overflow instead of silently writing infinity.

File dequantization supports native FP8, INT8, MXFP8, NVFP4, and the standalone
suite's scaled FP8/INT8/ConvRot. Other packed formats require their native
dequantizer first and produce an explicit error here. GGUF is inspect-only and
requires the optional `gguf` Python package. GGUF/HF conversion through
llama.cpp is outside these diffusion nodes.

## Metadata

Browse to a model or JSON file and click **Load / Edit**. The table supports
adding/removing fields, editing keys, text values and explicitly typed JSON
values, expanding JSON strings, and switching to raw JSON. Unknown fields,
Unicode, whitespace inside string values, and strings such as `001` are
preserved. Invalid JSON and duplicate table keys prevent execution. Changing
the source path requires reloading the editor before applying old edits.
Integer JSON values beyond JavaScript's safe range must stay as text in the
editor; the backend can preserve such sidecars directly without editing them.

Sidecars use `{"schema":"ray.model-metadata/v1","metadata":{...}}` and preserve
JSON structures. Safetensors headers require string values: explicitly typed
JSON values are JSON-encoded when embedded. Embedded strings are never
automatically parsed or reformatted. Metadata Save's model_copy mode streams
the original tensor block unchanged and supports a larger header. Quantization
recipes that describe tensor storage are retained and cannot be replaced by an
unrelated recipe. Save Model merges source metadata by default; replace is an
explicit option. Operations append recipes to `ray.model_tools.history`.

Saves use a counter under `output/model_tools` by default. An explicit output
path must include the extension. Files are published atomically and are not
overwritten unless the node's overwrite option is enabled.

## Merging and extraction

Weight A=1 selects A for LERP/SLERP; Weight A=0 selects B. Task-vector methods
require an explicit compatible base. DARE/DELLA use a per-tensor seed derived
from the supplied seed and tensor name. The density/lambda/trim controls appear
only for methods that use them. **block_weights** is a JSON map of tensor
prefixes to A ratios; the longest matching prefix wins. Unselected components
pass through from A.

Mismatch policies match the standalone suite: forbid is the default; intersect
blends common tensors and copies unique tensors from both inputs; pad/trim
handle common-key shape differences and still require matching key sets.
Padding/trimming cannot make unrelated architectures compatible. Matching
structure does not establish that models share a compatible training base.

LoRA Bake supports formats recognized by installed ComfyUI and reports matched
layers. An explicit target format applies the new adapter in fp32 before the
final conversion, avoiding an intermediate requantization of small LoRA deltas.
LoRA Extract supports Linear and convolution weights, skips unchanged
and 1D weights, and optionally includes embeddings. Alpha=0 uses each layer's
actual rank. Every layer stores its own alpha, including rank-clipped layers.
The reported relative error measures SVD truncation before output rounding.
Output is a ComfyUI generic-format adapter, not a PEFT adapter directory.
Norm/bias changes are not included in a standard LoRA.

Architecture detection uses installed ComfyUI tensor signatures, including
SDXL, Flux and MOSS where available. It identifies structure, not the exact
checkpoint name. Unknown models remain inspectable. The fp16 memory estimate
excludes activations and overhead, and packed-format element counts can differ
from logical parameter counts.

## Example workflows

Open [model_tools_metadata.json](examples/model_tools_metadata.json) or
[model_tools_merge.json](examples/model_tools_merge.json) in ComfyUI, then choose
your source model files before running them.

* Load Model As → MODEL to sampler; CLIP/VAE to their normal destinations.
* Model Merge → model_data to Save Model, metadata from Metadata Load / Edit
  to the same Save Model node. Disable load_result for a file-only merge.
* Metadata Load / Edit → Metadata Save (json_sidecar) to keep a reusable recipe.
* Metadata Load / Edit → Metadata Save (model_copy) to update an existing file
  while preserving its tensor block exactly.
* Modified checkpoint + original base → LoRA Extract → adapter file for LoRA Bake.
