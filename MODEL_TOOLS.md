# Ray's Model Tools

Nodes under **👑 Ray / 🧰 Model Tools** run inside ComfyUI; the standalone
ModelMergeTools app and its FastAPI server are not required.

| Node | Purpose |
| --- | --- |
| [Queued Model Loader](screenshots/RayQueuedModelLoader.png) | Process a native model list in one workflow execution, with automatic precision and per-sample offloading. |
| [Load Model As](screenshots/RayModelLoadAs.png) | Select a checkpoint/diffusion model from searchable folders. Auto detects the loader. |
| [Convert Model](screenshots/RayModelConvert.png) | Convert a file or connected MODEL into another storage format. |
| [Save Model](screenshots/RayModelSave.png) | Save the effective model, including active merge and LoRA patches, with optional CLIP/VAE and metadata. |
| [Metadata Load / Edit](screenshots/RayModelMetadata.png) | Read model metadata or a JSON sidecar into an editable table and raw JSON editor. |
| [Metadata Save](screenshots/RayModelMetadataSave.png) | Save a structured JSON sidecar, or apply metadata to a model copy without changing tensor bytes. |
| [Model Merge](screenshots/RayModelMerge.png) | LERP, SLERP, TIES, DARE-Linear, DARE-TIES, DELLA, DELLA-TIES, Breadcrumbs, Breadcrumbs-TIES. |
| [Model Inspector](screenshots/RayModelInspector.png) | Header-only tensor listing, dtype distribution, byte counts, and architecture detection. |
| [Model Compare](screenshots/RayModelCompare.png) | Compare names, shapes and dtypes before merging. |
| [LoRA Bake](screenshots/RayLoraBake.png) | Choose a LoRA file and bake it using ComfyUI's adapter mappings and supported LoRA variants. |
| [LoRA Extract](screenshots/RayLoraExtract.png) | SVD extraction from finetuned minus base, including convolution weights. |
| [LoRA QKV Loader](screenshots/RayLoraQKVLoader.png) | Stack LoRAs on a MODEL, with individual strengths and automatic compatibility fixes. |


## Queued model comparisons

Replace a native Load Diffusion Model with **Queued Model Loader** and connect its
single MODEL output to the same destination. Select a registered diffusion model
from the dropdown. Folders open into their subfolders; typing in the filter searches
full paths across every subfolder. Clear the filter to return to the folder tree. Press **+**
beside the Models heading to add rows and use each row's trash icon to remove it. **Run** submits one workflow
with a native MODEL list in row order. Standard downstream nodes process one model
at a time. Three models and a single prompt/latent produce three results together
in that execution's preview. Precision and supported quantization use ComfyUI's
native defaults independently for each file.

The image outputs are a native ComfyUI list. To pass a single tensor batch to a
later node, connect **Rebatch Images** after VAE Decode and set **batch_size** to
the total image count (for example, 3 for three one-image model results). Images
must have matching dimensions. Preview/Save Image can show all list results
directly. A per-model latent batch of two images produces six images for three
models. Saved workflows retain the complete selection.

Singleton prompts, seeds, conditioning and other inputs are reused for every
model, and seed-after-run controls advance once. Native lists of equal length
are paired by index; this is not a Cartesian product of model and prompt lists.
Keep custom random nodes deterministic. For Model Card, use Fixed, Increment or
Decrement seed mode. Text encoders, VAE, LoRAs and sampling settings stay as wired,
so choose compatible diffusion models.

Every file path is validated before loading weights. There is one queue/history
entry and one cancellation action. The same backend behavior works with direct
API calls and subgraphs: `model_name` is the first file and `queued_models` is a
JSON array of additional filenames. Refresh ComfyUI after updating from the older
queue-based implementation.

### Model memory

The loader uses ComfyUI's native ModelPatcher objects. After each sampler call it
explicitly unloads that diffusion model and its clones through native memory
management, including on error or cancellation. This also applies after a LoRA
or model patch creates a downstream clone. Other unrelated loaded models are
preserved. A subsequent sampler can reload the same model normally.

With native **DynamicVRAM**, weights remain backed by their source files and
unloading releases GPU allocations and native RAM weight buffers. With legacy
model loading, VRAM is offloaded to CPU but weights can remain in ComfyUI's
execution cache, so system RAM must accommodate the selected models. The loader
does not change the server's memory mode. Custom samplers must honor ComfyUI's
native sampling wrappers for explicit per-sample cleanup; otherwise native
memory-pressure handling still applies.

### Optional Spectrum acceleration

The top-right **Loader options cog** opens a **Spectrum** switch, off by default.
When enabled, each loaded model automatically selects an installed adapter:

| Model family | Required optional node pack |
| --- | --- |
| MOSS-Image | [ComfyUI-Spectrum-MOSS](https://github.com/Rkkss/ComfyUI-Spectrum-MOSS), Adaptive node |
| MiniMax H3 | [ComfyUI-Spectrum-MiniMax-H3](https://github.com/xmarre/ComfyUI-Spectrum-MiniMax-H3) |
| SDXL / Anima | [comfyui-spectrum-sdxl](https://github.com/ruwwww/comfyui-spectrum-sdxl) |
| Flux/Klein/Longcat, SD3/Qwen Image, Z Image/Lumina2, Ernie, HunyuanVideo and Wan | [ComfyUI-Spectrum](https://github.com/judian17/ComfyUI-Spectrum), according to its installed architecture support |

Adapters remain separate optional packs; no extra Spectrum node is needed in the
workflow. Install the relevant packs and restart ComfyUI before enabling the
switch. Disabled mode needs none of them. A missing adapter gives its installation
link. Unsupported models report that native sampling was kept. The node displays
which adapter was attached; sampler-specific native fallbacks remain controlled
by that adapter, so attachment does not guarantee a speedup.

Spectrum forecasts some model evaluations and can change generated results. Keep
the same toggle value across models when comparing them. Each adapter uses its
own declared defaults; the loader leaves precision, prompts, seeds and sampler
settings unchanged. SDXL/Anima automatically reads downstream sampler/scheduler
steps and preserves three final actual steps. If that count is ambiguous, dynamic,
or outside 10–500, it reports a native fallback. Use the standalone adapter node
when a workflow needs custom Spectrum tuning or a different step contract.

Compatibility and quality vary by architecture and sampler. In particular, the
general adapter discourages Qwen Image Edit and lists LTX support as untested.
Models reported unsupported by the installed adapter keep native sampling.

## Connections and file-only processing

MODEL, CLIP and VAE are normal ComfyUI connections. **model_data** is a Ray
handle to weights held in a file, in RAM after Fast merge, or as pending native
model patches. Use it between model operations and Save Model.
**metadata** is a structured connection shared by metadata and save nodes.
Operation reports are available through the **report** STRING outputs.

Use the file icon beside a source path to choose a model or metadata file.
**Save Model** takes its source from **model** or **model_data**. Choose an
**Output folder**, then set **filename_prefix** without an extension; the file is
saved as `<filename_prefix>.safetensors`, without a counter. Blank folders use
ComfyUI output and relative folders are resolved inside it. The default folder
is `output/model_tools`. Spaces and unsupported filename characters become
underscores. Connect **metadata** from Metadata Load / Edit for custom fields.

For Metadata Save and LoRA Extract, the file icon beside **Output file** opens Save As; Metadata Save switches
between JSON and safetensors according to its mode. Leave Output file blank to
use the filename prefix and ComfyUI output folder. Choosing a path does not
write a file; run the node to save it. Metadata Save's **overwrite** controls
replacement. LoRA Extract has no overwrite switch and preserves existing files
with a collision error.

A connected MODEL takes priority over model_data and path inputs. Compatible
LoRA baking and diffusion-only LERP keep native model patches until a consumer
needs the weights. Save Model uses ComfyUI's save API to apply those patches and
write the final checkpoint directly, including its final metadata. Other
file-based operations may first export the effective weights.
Connect CLIP/VAE when those components need to travel with it. A MODEL alone
contains the diffusion model, not the full original checkpoint.

For offline work, connect paths or **model_data**. The tools initialize inference
models automatically when MODEL, CLIP or VAE outputs are used. Connect
the resulting model_data to Save Model to persist it, or to Load Model As to
load it later. File operations use CPU math one layer at a time rather than
complete fp32 copies of all inputs. The regular merge uses temporary disk
storage; Fast merge retains its complete output in RAM. SVD still needs memory
for the largest individual matrix. Temporary artifacts live under
ComfyUI's temp directory in `ray_model_tools`; save anything you want to retain.

In **Load Model As**, select a registered diffusion model or checkpoint from the
folder dropdown. Its filter searches filenames and full paths across subfolders.
Existing saved paths and connected source inputs remain supported.
Choose **Auto** or **Preserve** and connect only **model_data** to read the source
headers and pass its handle to Model Merge. Set the final precision in Model
Merge. An explicit loader precision converts the file when its selected weights
do not already use that format. Connecting an
inference output loads the model automatically.

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

Use **+** beside the Metadata heading to add a field and each row's trash icon to
remove it. **Load / Edit** and **Table / JSON** stay beside the metadata editor.

Sidecars use `{"schema":"ray.model-metadata/v1","metadata":{...}}` and preserve
JSON structures. Safetensors headers require string values: explicitly typed
JSON values are JSON-encoded when embedded. Embedded strings are never
automatically parsed or reformatted. Metadata Save's model_copy mode streams
the original tensor block unchanged and supports a larger header. Quantization
recipes that describe tensor storage are retained and cannot be replaced by an
unrelated recipe. Save Model merges source metadata by default; replace is an
explicit option. Operations append recipes to `ray.model_tools.history`.

Metadata Save and LoRA Extract use a counter under `output/model_tools` by
default; an explicit output path must include the extension. Save Model uses its
folder and prefix directly. Files are published atomically. An existing filename
is an error unless the node provides **overwrite** and it is enabled.

## Merging and extraction

Connect Model Merge's **model_a** and **model_b**, or use **data_a** and
**data_b** for file handles. Connect **base_model** or **base_data** when the
chosen strategy needs a base. Choose source files in the upstream loader nodes.
Select the Model Merge node and open its **? Help** for a brief purpose,
strengths and limitations of every strategy. Hover a control for its settings,
units and applicable strategies.

Weight A=1 selects A for LERP/SLERP; Weight A=0 selects B. Task-vector methods
require an explicit compatible base. DARE/DELLA use a per-tensor seed derived
from the supplied seed and tensor name. The density/lambda/trim controls appear
only for methods that use them. Connect a STRING containing a JSON map of tensor
prefixes to A ratios to **block_weights**, for example `{"diffusion_model.blocks.0.":0.7}`.
The longest matching prefix wins. Leave it disconnected to use Weight A throughout. Unselected components
pass through from A.

Breadcrumbs and Breadcrumbs-TIES remove the smallest and largest absolute task
deltas using **bottom_trim** and **top_trim**. Percentiles are computed over the
whole tensor, including layers larger than 16,777,216 elements; large layers
still require temporary CPU memory for sorting and merge calculations.

**Forbid** is the default and requires matching tensor names and shapes.
**Intersect**, **Pad** and **Trim** preserve tensors found in only one input
unchanged. Intersect requires matching shapes for shared tensors. Pad zero-pads
shared tensors to the larger size along each axis; Trim crops them to the smaller
size.
Padding/trimming cannot make unrelated architectures compatible. Matching
structure does not establish that models share a compatible training base.

**Fast merge** keeps the complete merged result in system RAM instead of writing
an intermediate model file. Connect **model_data** to Save
Model, with the inference outputs unused, to write weights once with the final
metadata. Using MODEL, CLIP or VAE also creates a temporary model file for
ComfyUI's native loader. Other file-based consumers materialize a temporary file
when needed. Fast merge uses the same CPU calculations, formats, seed and
mismatch rules as the regular merge; it does not require additional VRAM.

Compatible live MODEL inputs use ComfyUI's native patches for diffusion-only
LERP with Forbid, no block overrides, and a preserved or matching floating-point
format. This avoids input checkpoint exports and a merged-model reload. Both
MODEL and model_data can go directly to Save Model. Other strategies, component
scopes, shape policies and format changes use the tensor-processing path.
The regular file writer streams tensors into its final temporary output once;
it keeps source mappings open during processing.

**Warning: high RAM usage.** Allow space for the whole output at its selected
format, plus source mappings, decoded layers and calculation buffers. The result
remains in RAM while ComfyUI caches it, including after saving. Insufficient RAM
can cause paging that slows the merge down, or an allocation failure. Leave Fast
merge off for lower RAM usage. Source files are kept open during either mode to
avoid reopening them for every tensor and scale.
Enabling Fast merge opens a compact RAM warning. **REVERT** turns the toggle
off; **CONFIRM** keeps it on. Both close the popup. Escape also reverts it.

**merge_name** is a STRING output ready to connect to Save Model's
**filename_prefix**. A live preview follows connected source selections and merge
controls. Names use `Base-…_A-…_B-…_STRATEGY_A%-B%_PRECISION_SETTINGS_DATETIME`;
LERP and SLERP omit Base. Source directories and extensions are removed, long
source names are shortened, and the settings fingerprint distinguishes changes
to block weights and algorithm options. The execution output uses the resolved
sources and execution time; computed upstream values may become known only then.

Connect MODEL or model_data to LoRA Bake, then choose the LoRA file and adjust
Model strength, CLIP strength, and Weight format. LoRA Bake supports formats
recognized by installed ComfyUI and reports matched layers. Preserve and a
floating-point format already used by the model keep a native patched clone;
Save Model performs the checkpoint write. The model_data output saves these
pending patches directly too, and creates a temporary file only when another
file-based operation needs it. Changing format uses fp32 before final conversion
to avoid an intermediate requantization of small LoRA deltas.
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

## LoRA QKV Loader

Connect a **MODEL** to **LoRA QKV Loader**, then connect its **MODEL** output to
the sampler. Select a registered LoRA from the dropdown. Folders preserve their
subfolder tree; typing in the filter searches full paths across every subfolder.
Use **+** beside the LoRAs heading to add rows and **trash** to remove them. Each row has its own
**Strength**: 1 uses the trained effect, 0 skips the row, and negative values
reverse the adapter contribution. Drag the number left or right to adjust it,
hold Shift for finer steps, or click to type a value. LoRAs are applied from top
to bottom. Removing
every selection passes the input model through. The first filename and strength,
and the additional-row list, can also be driven by links.

The loader uses ComfyUI's native adapter conversion, parameter mappings and model
patching. It checks each selected LoRA against the connected model and adds
unambiguous trainer-name aliases when necessary. Supported fused QKV adapters
are split to the model's separate Q/K/V dimensions; separate adapters can map to
the corresponding slices of a fused weight. Existing native matches are kept.
Checks apply across model families, including MOSS, rather than requiring a
model-family switch.

Exact splitting supports linear LoRA/PEFT, output-axis DoRA, linear LoHa,
compatible LoKr factors, and weight differences. Unsupported layouts, ambiguous
names, input-axis DoRA, convolutional QKV and incomplete triplets are kept as
they are and reported when they cannot match. Repairs cannot make a LoRA trained
for a different architecture compatible. The status beneath the rows shows how
many model weights loaded and which fixes or warnings occurred. Text-encoder
weights are not applied; this node has no CLIP connections. Loading adds live
model patches and does not write or permanently bake the source model or LoRA.

## Example workflows

Open [model_tools_metadata.json](examples/model_tools_metadata.json) or
[model_tools_merge.json](examples/model_tools_merge.json) in ComfyUI, then choose
your source model files before running them.

* Load Model As → MODEL to sampler; CLIP/VAE to their normal destinations.
* Model Merge → model_data to Save Model, metadata from Metadata Load / Edit
  to the same Save Model node. Connect **merge_name** to **filename_prefix** for
  automatic naming. Use only model_data for a file-only merge.
* Metadata Load / Edit → Metadata Save (json_sidecar) to keep a reusable recipe.
* Metadata Load / Edit → Metadata Save (model_copy) to update an existing file
  while preserving its tensor block exactly.
* Modified checkpoint + original base → LoRA Extract → adapter file for LoRA Bake.
