"""Caption a folder with ComfyUI's native multimodal text encoder API."""
import secrets
from pathlib import Path

import numpy as np
import torch
from PIL import Image, ImageOps

import folder_paths
import comfy.model_management as model_management
import comfy.sd
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


class RayVLMFolder:
    DESCRIPTION = (
        "Caption images alphabetically with a local CLIP/VLM on GPU. "
        "Return aligned lists of answers, original images, and absolute paths. "
        "Use a full vision-language checkpoint, not a text-only CLIP encoder. "
        "No sidecars are written. Images remain in RAM until outputs are released; "
        "use start_index and limit for large folders."
    )

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "clip_name": (folder_paths.get_filename_list("text_encoders"), {"tooltip": "Select a full generative vision-language model from text_encoders, such as Qwen3-VL."}),
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
        }}

    RETURN_TYPES = ("STRING", "IMAGE", "STRING")
    RETURN_NAMES = ("text", "image", "image_path")
    OUTPUT_TOOLTIPS = (
        "Decoded VLM answers, one per image, in scan order.",
        "Examined RGB images with EXIF orientation applied, one tensor per file.",
        "Absolute source image paths, paired with the answers and images.",
    )
    OUTPUT_IS_LIST = (True, True, True)
    FUNCTION = "process"
    CATEGORY = "👑 Ray/💬 LLM"

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("nan")

    def process(self, clip_name, folder, recurse_subfolders, start_index, limit,
                user_prompt, max_length, temperature, top_k, top_p, min_p,
                repetition_penalty, seed, thinking):
        paths = image_files(folder, recurse_subfolders, start_index, limit)
        device = model_management.get_torch_device()
        if device.type == "cpu":
            raise RuntimeError("GPU inference is required. Start ComfyUI with an available GPU backend.")
        model_management.throw_exception_if_processing_interrupted()
        clip = comfy.sd.load_clip(
            ckpt_paths=[folder_paths.get_full_path_or_raise("text_encoders", clip_name)],
            embedding_directory=folder_paths.get_folder_paths("embeddings"),
            clip_type=comfy.sd.CLIPType.QWEN_IMAGE,
            model_options={"load_device": device, "offload_device": torch.device("cpu")},
        )
        if clip.patcher.load_device.type == "cpu":
            raise RuntimeError("The VLM fell back to CPU. Choose a checkpoint supported by your GPU.")
        print(f"[RayVLMFolder] Captioning {len(paths)} images on {clip.patcher.load_device}")
        texts, images, image_paths = [], [], []
        progress = ProgressBar(len(paths))
        for index, path in enumerate(paths):
            model_management.throw_exception_if_processing_interrupted()
            with Image.open(path) as source:
                rgb = ImageOps.exif_transpose(source).convert("RGB")
                image = torch.from_numpy(np.array(rgb, dtype=np.float32) / 255.0).unsqueeze(0)
            tokens = clip.tokenize(user_prompt, image=image, skip_template=False, min_length=1, thinking=thinking)
            if not has_image_tokens(tokens):
                raise ValueError("No image tokens produced. Select a full VLM and use a plain instruction without manual chat-template markers.")
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
            texts.append(text)
            images.append(image)
            image_paths.append(str(path))
            progress.update_absolute(index + 1)
        return (texts, images, image_paths)
