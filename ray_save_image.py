"""PNG output and comparison previews; no image tensors survive an execution."""
import json
import os
from pathlib import Path
from uuid import uuid4

import numpy as np
from PIL import Image
from PIL.PngImagePlugin import PngInfo
import folder_paths
from comfy.cli_args import args


def destination_path(value):
    root = Path(folder_paths.get_output_directory()).resolve()
    path = Path(value.strip()).expanduser() if value.strip() else root
    if not path.is_absolute():
        path = root / path
    return path.resolve()


class RaySaveImage:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image_1": ("IMAGE", {"tooltip": "Connect the primary image or batch."}),
                "save_image": (["none", "1", "2", "both"], {"default": "1", "tooltip": "Choose which input batches to save; none only previews."}),
                "directory": ("STRING", {"default": "", "tooltip": "Choose an absolute folder, or a path relative to ComfyUI output. Blank uses output."}),
                "filename_prefix": ("STRING", {"default": "Ray", "tooltip": "Set a filename prefix; input number and a unique ID are appended."}),
                "save_without_metadata": ("BOOLEAN", {"default": False, "tooltip": "Omit prompt and workflow metadata from saved PNGs."}),
            },
            "optional": {"image_2": ("IMAGE", {"tooltip": "Connect another image or batch to enable slider comparison."})},
            "hidden": {"prompt": "PROMPT", "extra_pnginfo": "EXTRA_PNGINFO", "node_id": "UNIQUE_ID"},
        }

    RETURN_TYPES = ()
    RETURN_NAMES = ()
    FUNCTION = "save"
    OUTPUT_NODE = True
    CATEGORY = "👑 Ray/✨ VFX"
    DESCRIPTION = "Save PNG images or compare two inputs with a draggable preview divider."

    def save(self, image_1, save_image="1", directory="", filename_prefix="Ray",
             save_without_metadata=False, image_2=None, prompt=None, extra_pnginfo=None, node_id=None):
        if save_image not in ("none", "1", "2", "both"):
            raise ValueError("Save Image must be none, 1, 2, or both.")
        if save_image == "2" and image_2 is None:
            raise ValueError("Connect image_2 or choose Save Image 1 / none.")
        selected = {"none": set(), "1": {1}, "2": {2}, "both": {1, 2}}[save_image]
        # A prefix is a filename, never a second way to select the destination.
        prefix = filename_prefix.strip() or "Ray"
        if selected and (any(c in prefix for c in '<>:"/\\|?*') or any(ord(c) < 32 for c in prefix)):
            raise ValueError("Filename prefix cannot contain path separators or reserved filename characters.")
        output = destination_path(directory) if selected else None
        if output is not None:
            output.mkdir(parents=True, exist_ok=True)
        temp = Path(folder_paths.get_temp_directory()) / "ray_save_image"
        temp.mkdir(parents=True, exist_ok=True)
        metadata = None
        if selected and not save_without_metadata and not args.disable_metadata:
            metadata = PngInfo()
            if prompt is not None:
                metadata.add_text("prompt", json.dumps(prompt))
            for key, value in (extra_pnginfo or {}).items():
                metadata.add_text(key, json.dumps(value))
        previews, saved = [[], []], []
        for number, batch in enumerate((image_1, image_2), 1):
            if batch is None:
                continue
            for index, tensor in enumerate(batch):
                pixels = np.clip(tensor.detach().cpu().float().numpy() * 255, 0, 255).astype(np.uint8)
                if pixels.shape[-1] == 1:
                    pixels = pixels[..., 0]
                image = Image.fromarray(pixels)
                token = uuid4().hex
                if number in selected:
                    filename = f"{prefix}_{number}_{index + 1:04}_{token}.png"
                    target = output / filename
                    # Exclusive creation prevents overwriting even concurrent runs.
                    with target.open("xb") as stream:
                        image.save(stream, format="PNG", pnginfo=metadata, compress_level=4)
                    saved.append(str(target))
                preview_name = f"{token}.png"
                # Temp previews never embed workflows or local destination paths.
                image.save(temp / preview_name, format="PNG", compress_level=1)
                previews[number - 1].append({"filename": preview_name, "subfolder": "ray_save_image", "type": "temp"})
        return {"ui": {"ray_images_1": previews[0], "ray_images_2": previews[1],
                       "ray_saved": saved, "ray_directory": [str(output)] if saved else []}, "result": ()}


def list_directories(value):
    """Folder-only navigation on the machine running ComfyUI."""
    path = destination_path(value)
    children = []
    with os.scandir(path) as entries:
        for entry in entries:
            try:
                if entry.is_dir():
                    children.append({"name": entry.name, "path": str(Path(entry.path).resolve())})
            except OSError:
                continue
    roots = [str(Path(f"{letter}:/")) for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" if Path(f"{letter}:/").exists()] if os.name == "nt" else ["/"]
    return {"path": str(path), "parent": str(path.parent), "folders": sorted(children, key=lambda item: item["name"].casefold()), "roots": roots}


def register_routes():
    import asyncio
    from aiohttp import web
    from server import PromptServer

    @PromptServer.instance.routes.get("/ray/save-image/folders")
    async def folders(request):
        try:
            return web.json_response(await asyncio.to_thread(list_directories, request.query.get("path", "")))
        except (OSError, ValueError) as error:
            return web.json_response({"error": str(error)}, status=400)
