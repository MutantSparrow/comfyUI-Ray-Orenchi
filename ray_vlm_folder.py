"""Caption a folder with a connected CLIP, using ComfyUI's native multimodal text encoder API."""
import gc
import secrets
from pathlib import Path

import numpy as np
import torch
from PIL import Image, ImageOps

import comfy.model_management as model_management
from comfy.utils import ProgressBar


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff", ".gif"}


def image_files(folder, recurse_subfolders, start_index, limit):
    if not str(folder).strip():
        raise ValueError("Enter a folder containing images.")
    root = Path(folder).expanduser().resolve(strict=True)
    if not root.is_dir():
        raise ValueError(f"Not a directory: {root}")
    if start_index < 0 or limit < -1:
        raise ValueError("Use start_index >= 0 and limit >= -1.")
    candidates = root.rglob("*") if recurse_subfolders else root.iterdir()
    paths = sorted(
        (p for p in candidates if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS),
        key=lambda p: p.relative_to(root).as_posix(),
    )[start_index:]
    if limit >= 0:
        paths = paths[:limit]
    if not paths:
        raise ValueError("No supported images in the selected range.")
    return paths


def has_image_tokens(value):
    if isinstance(value, dict):
        return value.get("type") == "image" or any(has_image_tokens(v) for v in value.values())
    if isinstance(value, (list, tuple)):
        return any(has_image_tokens(v) for v in value)
    return False


def load_image(path):
    try:
        with Image.open(path) as source, ImageOps.exif_transpose(source).convert("RGB") as rgb:
            pixels = np.asarray(rgb, dtype=np.float32)
            pixels /= 255.0
            return torch.from_numpy(pixels).unsqueeze(0)
    except (OSError, ValueError) as error:
        raise RuntimeError(f"Cannot read source image {path}: {error}") from error


def caption_image(clip, path, user_prompt, max_length, temperature, top_k, top_p,
                  min_p, repetition_penalty, seed, thinking):
    # This scope owns every transient tensor, including images held by tokens.
    image = tokens = generated = None
    try:
        image = load_image(path)
        tokens = clip.tokenize(user_prompt, image=image, skip_template=False, min_length=1, thinking=thinking)
        if not has_image_tokens(tokens):
            raise ValueError("No image tokens produced. Connect a full vision-language CLIP (for example Qwen3-VL from CLIPLoader, type qwen_image) and use a plain instruction without manual chat-template markers.")
        generated = clip.generate(
            tokens, do_sample=temperature > 0, max_length=max_length,
            temperature=temperature if temperature > 0 else 1.0,
            top_k=top_k, top_p=top_p, min_p=min_p,
            repetition_penalty=repetition_penalty,
            seed=secrets.randbelow(2**31) if seed < 0 else seed,
        )
        text = clip.decode(generated)
        if not text.strip():
            raise RuntimeError(f"The VLM returned an empty answer for {path.name}. Check the model and instruction.")
        return text
    finally:
        image = tokens = generated = None


def release_transients():
    gc.collect()
    model_management.soft_empty_cache()


def source_revision(path):
    try:
        stat = path.stat()
        return stat.st_mtime_ns, stat.st_size, stat.st_ino
    except OSError as error:
        raise RuntimeError(f"Cannot read source image {path}: {error}") from error


class RayVLMFolder:
    DESCRIPTION = (
        "Caption images alphabetically with a connected CLIP/VLM on GPU. "
        "Return aligned lists of answers, original images, and absolute paths. "
        "Connect a full vision-language CLIP (for example Qwen3-VL from CLIPLoader, "
        "type qwen_image), not a text-only encoder. "
        "No sidecars are written. Caption one image at a time. Enable return_images "
        "only when needed: output images are decoded after captioning and remain in RAM "
        "until outputs are released; use start_index and limit to bound that output."
    )

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "clip": ("CLIP", {"tooltip": "Full generative vision-language CLIP, such as Qwen3-VL from CLIPLoader (type qwen_image). Text-only encoders cannot caption."}),
            "folder": ("STRING", {"default": "", "placeholder": "Absolute path to a folder of images", "tooltip": "Enter the folder containing images to caption."}),
            "recurse_subfolders": ("BOOLEAN", {"default": False, "tooltip": "Include images in subfolders, sorted by relative path."}),
            "start_index": ("INT", {"default": 0, "min": 0, "tooltip": "Skip this many images in alphabetical relative-path order."}),
            "limit": ("INT", {"default": -1, "min": -1, "tooltip": "Caption at most this many images; use -1 for all remaining images."}),
            "user_prompt": ("STRING", {"default": "Describe the visible contents of this image in detail.", "multiline": True, "tooltip": "Enter the instruction to apply independently to every image."}),
            "max_length": ("INT", {"default": 1024, "min": 1, "max": 32768, "tooltip": "Set the maximum number of generated tokens per image."}),
            "temperature": ("FLOAT", {"default": 0.25, "min": 0.0, "max": 2.0, "step": 0.01, "tooltip": "Set sampling randomness; use 0 for greedy decoding."}),
            "top_k": ("INT", {"default": 40, "min": 0, "max": 1000, "tooltip": "Keep this many candidate tokens; use 0 to disable top-k filtering."}),
            "top_p": ("FLOAT", {"default": 0.9, "min": 0.0, "max": 1.0, "step": 0.01, "tooltip": "Set the cumulative probability threshold for nucleus sampling."}),
            "min_p": ("FLOAT", {"default": 0.05, "min": 0.0, "max": 1.0, "step": 0.01, "tooltip": "Filter tokens relative to the most probable token; use 0 to disable."}),
            "repetition_penalty": ("FLOAT", {"default": 1.05, "min": 0.0, "max": 5.0, "step": 0.01, "tooltip": "Set the repetition penalty; use 1 for no penalty."}),
            "seed": ("INT", {"default": -1, "min": -1, "max": 2**31 - 1, "tooltip": "-1 for random; any >=0 value is reproducible."}),
            "thinking": ("BOOLEAN", {"default": False, "tooltip": "Enable thinking when supported by the selected model; return its decoded response unchanged."}),
        }, "optional": {
            "return_images": ("BOOLEAN", {"default": False, "tooltip": "Return original-size images after all captions finish. Off keeps the image output empty and avoids retaining the folder's decoded images in RAM."}),
            "cleanup_every": ("INT", {"default": 16, "min": 0, "max": 1024, "tooltip": "Collect transient objects and release unused ComfyUI VRAM caches every N captions. 0 disables periodic cleanup; low-memory cleanup still applies."}),
        }}

    RETURN_TYPES = ("STRING", "IMAGE", "STRING")
    RETURN_NAMES = ("text", "image", "image_path")
    OUTPUT_TOOLTIPS = (
        "Decoded VLM answers, one per image, in scan order.",
        "Original RGB images, decoded after captioning when return_images is enabled; otherwise an empty list.",
        "Absolute source image paths, paired with the answers and images.",
    )
    OUTPUT_IS_LIST = (True, True, True)
    FUNCTION = "process"
    CATEGORY = "👑 Ray/💬 LLM"

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("nan")

    def process(self, clip, folder, recurse_subfolders, start_index, limit,
                user_prompt, max_length, temperature, top_k, top_p, min_p,
                repetition_penalty, seed, thinking, return_images=False, cleanup_every=16):
        if not 0 <= cleanup_every <= 1024:
            raise ValueError("Use cleanup_every between 0 and 1024.")
        paths = image_files(folder, recurse_subfolders, start_index, limit)
        device = model_management.get_torch_device()
        if device.type == "cpu":
            raise RuntimeError("GPU inference is required. Start ComfyUI with an available GPU backend.")
        model_management.throw_exception_if_processing_interrupted()
        if clip.patcher.load_device.type == "cpu":
            raise RuntimeError("The connected CLIP runs on CPU. In CLIPLoader set device to default, and use a GPU that supports the checkpoint.")
        print(f"[RayVLMFolder] Captioning {len(paths)} images on {clip.patcher.load_device}")
        texts, images, image_paths, revisions = [], [], [], []
        progress = ProgressBar(len(paths))
        try:
            for index, path in enumerate(paths):
                model_management.throw_exception_if_processing_interrupted()
                if return_images:
                    revisions.append(source_revision(path))
                texts.append(caption_image(clip, path, user_prompt, max_length, temperature,
                                          top_k, top_p, min_p, repetition_penalty, seed, thinking))
                image_paths.append(str(path))
                progress.update_absolute(index + 1)
                low_memory = (
                    model_management.get_free_memory(clip.patcher.load_device) < 512 * 1024**2
                    or model_management.get_free_memory(torch.device("cpu")) < 512 * 1024**2
                )
                if low_memory or (cleanup_every and (index + 1) % cleanup_every == 0):
                    release_transients()
        finally:
            release_transients()
        if return_images:
            try:
                for path, revision in zip(paths, revisions):
                    model_management.throw_exception_if_processing_interrupted()
                    if source_revision(path) != revision:
                        raise RuntimeError(f"Source image changed during captioning: {path}. Run again to keep captions and images aligned.")
                    images.append(load_image(path))
                    if source_revision(path) != revision:
                        raise RuntimeError(f"Source image changed while loading outputs: {path}. Run again to keep captions and images aligned.")
            except BaseException:
                # ComfyUI interruption inherits BaseException; discard any partial
                # output batch even when the executor retains an error traceback.
                images.clear()
                raise
        return (texts, images, image_paths)
