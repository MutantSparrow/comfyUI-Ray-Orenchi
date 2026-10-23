"""Generate and compose a complete image-model benchmark in one node."""
from datetime import datetime
from time import perf_counter
import math
import re

import numpy as np
from PIL import Image
import torch

import comfy.model_management as mm
import comfy.samplers
import comfy.utils
import node_helpers
import nodes

if __package__:
    from . import model_card as card
    from . import filename_template as names
    from .ray_save_image import prompt_widgets
else:
    import model_card as card
    import filename_template as names
    from ray_save_image import prompt_widgets


def selected_name(source, prompt, now=None):
    if not isinstance(source, str):
        return ""
    lookup = prompt_widgets(prompt)
    context = {"now": now or datetime.now().astimezone()}
    result = []
    for part in names.parse(source):
        if part[0] == "text":
            result.append(part[1])
        elif part[1] == "widget":
            options = part[2]
            value = lookup(options["node"], options["widget"])
            if isinstance(value, float) and value.is_integer() and abs(value) < 1e15:
                value = int(value)
            value = "" if value is None else str(value).lower() if isinstance(value, bool) else str(value)
            value = card.display_name(value.replace("{", "_").replace("}", "_"))
            if re.search(r"\.(safetensors|ckpt|pt|pth|bin|gguf)$", value, re.I):
                value = re.sub(r"\.[^.]+$", "", value.replace("\\", "/").rsplit("/", 1)[-1])
            result.append(value[:options["limit"]])
        elif part[1] in ("date", "time", "datetime", "timestamp", "hash"):
            result.append(names.render([part], context))
        else:
            raise ValueError(f"{{{part[1]}}} is only available for filenames.")
    return card.display_name("".join(result))


def model_spec(model, vae, width, height):
    if vae is None or not callable(getattr(vae, "decode", None)):
        raise ValueError("Ray Model Card needs a compatible native image VAE.")
    try:
        latent = model.get_model_object("latent_format")
        config = model.get_model_object("model_config").unet_config
        channels, dimensions, scale = latent.latent_channels, latent.latent_dimensions, latent.spacial_downscale_ratio
    except (AttributeError, KeyError, TypeError) as error:
        raise ValueError("Ray Model Card needs a standard ComfyUI image MODEL with a latent format.") from error
    family = config.get("image_model", "standard")
    single_frame = {"anima", "qwen_image", "krea2", "joyimage", "ming_image"}
    if dimensions not in (2, 3) or (dimensions == 3 and family not in single_frame):
        raise ValueError(f"Ray Model Card: {family} uses an unsupported latent format. V1 supports image generation, including single-frame image models; audio/video/3D/edit pipelines are outside its scope.")
    if not isinstance(scale, (int, float)) or scale < 1 or scale != int(scale):
        raise ValueError("Ray Model Card: the model's spatial latent scale is unsupported.")
    scale = int(scale)
    if width % scale or height % scale:
        raise ValueError(f"Ray Model Card: this model requires image width and height divisible by {scale}.")
    if channels != vae.latent_channels or vae.latent_dim not in (2, 3):
        raise ValueError("Ray Model Card: the supplied VAE does not match the model's latent channels/dimensions.")
    if vae.spacial_compression_decode() != scale:
        raise ValueError("Ray Model Card: the VAE and model have different spatial compression ratios.")
    if vae.output_channels not in (3, 4):
        raise ValueError("Ray Model Card needs an RGB or RGBA image VAE.")
    shape = (1, channels) + ((1,) if dimensions == 3 else ()) + (height // scale, width // scale)
    return family, config, shape


def generate_image(model, clip, vae, item, shape, family, guidance, settings):
    positive = negative = latent = sampled = decoded = tokens = None
    try:
        kwargs = {"keep_vision": True, "prevent_empty_text": True} if family == "qwen_image21" else {}
        tokens = clip.tokenize(item.entry.positive, **kwargs)
        positive = clip.encode_from_tokens_scheduled(tokens)
        tokens = clip.tokenize(item.entry.negative, **kwargs)
        negative = clip.encode_from_tokens_scheduled(tokens)
        tokens = None
        if guidance is not None:
            positive = node_helpers.conditioning_set_values(positive, {"guidance": guidance})
            negative = node_helpers.conditioning_set_values(negative, {"guidance": guidance})
        mm.throw_exception_if_processing_interrupted()
        latent = {"samples": torch.zeros(shape, device=mm.intermediate_device())}
        sampled = nodes.common_ksampler(model, item.seed, settings["steps"], settings["cfg"],
                                         settings["sampler_name"], settings["scheduler"], positive, negative,
                                         latent, denoise=settings["denoise"])[0]
        positive = negative = latent = None
        decoded = nodes.VAEDecode().decode(vae, sampled)[0]
        sampled = None
        mm.throw_exception_if_processing_interrupted()
        if decoded.ndim != 4 or decoded.shape[0] != 1 or decoded.shape[-1] not in (3, 4):
            raise ValueError("VAE did not decode one RGB/RGBA image.")
        if tuple(decoded.shape[1:3]) != (settings["image_height"], settings["image_width"]):
            raise ValueError(f"VAE returned {decoded.shape[2]}×{decoded.shape[1]} instead of the requested dimensions.")
        return decoded.detach().to(device="cpu", dtype=torch.float32).clamp_(0, 1)
    finally:
        positive = negative = tokens = latent = sampled = decoded = None


def to_thumbnail(image, layout):
    pixels = (image[0].numpy() * 255).round().astype(np.uint8)
    with Image.fromarray(pixels) as original:
        with original.resize((layout.thumbnail_width, layout.thumbnail_height), Image.Resampling.LANCZOS) as thumb:
            if thumb.mode == "RGBA":
                rgb = Image.new("RGB", thumb.size, "black")
                rgb.paste(thumb, mask=thumb.getchannel("A"))
                return rgb
            return thumb.convert("RGB")


def image_tensor(image):
    # np.asarray is read-only for PIL; the owned array is reused by the output tensor.
    pixels = np.array(image, dtype=np.float32)
    pixels /= 255
    return torch.from_numpy(pixels).unsqueeze(0)


class RayModelCard:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model": ("MODEL",), "clip": ("CLIP",), "vae": ("VAE",),
                "seed": ("INT", {"default": 0, "min": 0, "max": card.SEED_MAX, "control_after_generate": True,
                                  "tooltip": "Initial seed. Increment/decrement advance before each benchmark image."}),
                "seed_mode": (list(card.SEED_MODES), {"default": "fixed", "tooltip": "Per-image seed behavior; linked to the native seed control in the Ray panel."}),
                "steps": ("INT", {"default": 20, "min": 1, "max": 10000}),
                "cfg": ("FLOAT", {"default": 7.0, "min": 0.0, "max": 100.0, "step": .1, "round": .1}),
                "sampler_name": (comfy.samplers.KSampler.SAMPLERS, {"default": "euler"}),
                "scheduler": (comfy.samplers.KSampler.SCHEDULERS, {"default": "normal"}),
                "denoise": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0, "step": .01, "round": .01}),
                "image_width": ("INT", {"default": 1024, "min": 64, "max": 16384, "step": 8}),
                "image_height": ("INT", {"default": 1024, "min": 64, "max": 16384, "step": 8}),
                "card_width": ("INT", {"default": 3000, "min": 256, "max": 32768, "step": 8}),
                "preview_width": ("INT", {"default": 1000, "min": 64, "max": 32768, "step": 8,
                                            "tooltip": "Maximum preview width; smaller cards are never enlarged."}),
                "card_name": ("STRING", {"default": "", "tooltip": "Card title: type text, connect a STRING, or use the { } builder for dates, times, hashes and widget values. Spaces are preserved. Blank uses MODEL CARD; config =title wins."}),
                "guidance_mode": (["auto", "set", "disabled"], {"default": "auto",
                    "tooltip": "Auto adds embedded guidance for models declaring guidance_embed. Set supplies guidance explicitly. Disabled leaves native conditioning unchanged."}),
                "guidance": ("FLOAT", {"default": 3.5, "min": 0.0, "max": 100.0, "step": .1, "round": .1}),
                "max_images": ("INT", {"default": 256, "min": 1, "max": 4096,
                                       "tooltip": "Preflight generation-count safeguard; raise deliberately for larger benchmarks."}),
                "memory_limit_mb": ("INT", {"default": 4096, "min": 256, "max": 65536, "step": 256,
                                            "tooltip": "Estimated CPU output/compositing budget in MiB. Model and VRAM memory are additional."}),
            },
            "optional": {"config": ("STRING", {"multiline": True, "forceInput": True, "default": card.DEFAULT_CONFIG,
                                                  "tooltip": "Leave disconnected for the built-in 66-image benchmark. Copy Config gives the editable template."})},
            "hidden": {"prompt": "PROMPT"},
        }

    RETURN_TYPES = ("IMAGE", "IMAGE", "IMAGE", "STRING")
    RETURN_NAMES = ("model_card", "preview", "images", "report")
    OUTPUT_TOOLTIPS = ("Completed full-resolution card.", "Downscaled copy of the finished card.",
                       "Source images in category/column order.", "Markdown text with exact config, settings, prompts and actual seeds.")
    FUNCTION = "generate"
    OUTPUT_NODE = True
    CATEGORY = "👑 Ray/🔧 Tools"
    DESCRIPTION = "Connect MODEL, CLIP and VAE to generate a complete visual benchmark: black model card, preview, ordered image batch and Markdown report. Copy Config provides the editable default. Image generation only."

    @classmethod
    def IS_CHANGED(cls, seed_mode="fixed", card_name="", prompt=None, **kwargs):
        return float("nan") if seed_mode == "randomize" else selected_name(card_name, prompt)

    def generate(self, model, clip, vae, seed=0, seed_mode="fixed", steps=20, cfg=7.0,
                 sampler_name="euler", scheduler="normal", denoise=1.0, image_width=1024,
                 image_height=1024, card_width=3000, preview_width=1000, card_name="",
                 guidance_mode="auto", guidance=3.5, max_images=256, memory_limit_mb=4096,
                 config=None, prompt=None):
        started = perf_counter()
        benchmark = card.parse_config(card.DEFAULT_CONFIG if config is None else config)
        if not isinstance(steps, int) or not 1 <= steps <= 10000:
            raise ValueError("Ray Model Card steps must be between 1 and 10000.")
        for label, value, high in (("CFG", cfg, 100), ("denoise", denoise, 1), ("guidance", guidance, 100)):
            if not isinstance(value, (float, int)) or not math.isfinite(value) or not 0 <= value <= high:
                raise ValueError(f"Ray Model Card {label} must be a finite number between 0 and {high}.")
        if sampler_name not in comfy.samplers.KSampler.SAMPLERS or scheduler not in comfy.samplers.KSampler.SCHEDULERS:
            raise ValueError("Ray Model Card needs a sampler and scheduler available in this ComfyUI version.")
        if guidance_mode not in ("auto", "set", "disabled"):
            raise ValueError("Ray Model Card guidance mode must be auto, set or disabled.")
        if clip is None or not callable(getattr(clip, "tokenize", None)) or not callable(getattr(clip, "encode_from_tokens_scheduled", None)):
            raise ValueError("Ray Model Card needs a compatible native CLIP text encoder.")
        plan = card.make_plan(benchmark, seed, seed_mode)
        layout = card.calculate_layout(benchmark, card_width, image_width, image_height)
        card.check_memory(plan, layout, image_width, image_height, preview_width, max_images, memory_limit_mb)
        family, model_config, shape = model_spec(model, vae, image_width, image_height)
        embedded_guidance = guidance if guidance_mode == "set" or (guidance_mode == "auto" and model_config.get("guidance_embed", False)) else None
        selected = selected_name(card_name, prompt)
        title = card.display_name(benchmark.title) or selected or "MODEL CARD"
        timestamp = datetime.now().astimezone().strftime("%Y-%m-%d %H_%M_%S %z")
        settings = dict(image_width=image_width, image_height=image_height, card_width=card_width,
                        preview_width=preview_width, steps=steps, cfg=cfg, sampler_name=sampler_name,
                        scheduler=scheduler, denoise=denoise, initial_seed=seed, seed_behavior=seed_mode,
                        model_family=family, guidance_mode=guidance_mode, guidance=guidance, effective_guidance=embedded_guidance,
                        max_images=max_images, memory_limit_mb=memory_limit_mb)
        progress = comfy.utils.ProgressBar(len(plan))
        thumbnails, images, composite, preview, decoded = [], None, None, None, None
        try:
            for item in plan:
                mm.throw_exception_if_processing_interrupted()
                try:
                    decoded = generate_image(model, clip, vae, item, shape, family, embedded_guidance, settings)
                    if images is None:
                        images = torch.empty((len(plan),) + tuple(decoded.shape[1:]), dtype=torch.float32, device="cpu")
                    images[item.index].copy_(decoded[0])
                    thumbnails.append(to_thumbnail(decoded, layout))
                    decoded = None
                except mm.InterruptProcessingException:
                    raise
                except Exception as error:
                    raise RuntimeError(f"Ray Model Card generation failed at index {item.index} (image {item.index + 1}), category {item.category!r}, column {item.column + 1}, caption {item.entry.caption!r}, config line {item.entry.line}: {error}") from error
                progress.update(1)
            mm.throw_exception_if_processing_interrupted()
            composite = card.compose_card(benchmark, plan, thumbnails, layout, title, timestamp,
                                          interrupt=mm.throw_exception_if_processing_interrupted)
            ratio = min(1.0, preview_width / composite.width)
            preview = composite.resize((max(1, round(composite.width * ratio)), max(1, round(composite.height * ratio))), Image.Resampling.LANCZOS)
            full_image, preview_image = image_tensor(composite), image_tensor(preview)
            mm.throw_exception_if_processing_interrupted()
            runtime_seconds = perf_counter() - started
            report = card.make_report(benchmark, plan, title, selected, timestamp, settings, layout,
                                      runtime_seconds=runtime_seconds)
            return full_image, preview_image, images, report
        finally:
            decoded = None
            for thumbnail in thumbnails:
                thumbnail.close()
            if composite is not None:
                composite.close()
            if preview is not None:
                preview.close()
