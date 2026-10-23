"""PNG output and comparison previews; no image tensors survive an execution."""
import json
import os
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import numpy as np
from PIL import Image
from PIL.PngImagePlugin import PngInfo
import folder_paths
from comfy.cli_args import args

try:
    from . import filename_template as names
    from .route_security import require_local
except ImportError:
    import filename_template as names
    from route_security import require_local


def destination_path(value):
    root = Path(folder_paths.get_output_directory()).resolve()
    path = Path(value.strip()).expanduser() if value.strip() else root
    if not path.is_absolute():
        path = root / path
    return path.resolve()


def prompt_widgets(prompt):
    """Looks up a widget value on any node of the queued graph. A value that comes from another node's output (a
    link) has no value yet, so it is skipped; the web page fills those in before the prompt is sent."""
    def lookup(node_id, name):
        node = prompt.get(str(node_id)) if isinstance(prompt, dict) else None
        value = node.get("inputs", {}).get(name) if isinstance(node, dict) else None
        return None if isinstance(value, (list, tuple, dict)) else value
    return lookup


class RaySaveImage:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image_1": ("IMAGE", {"tooltip": "Connect the primary image or batch."}),
                "save_image": (["none", "1", "2", "both"], {"default": "1", "tooltip": "Choose which input batches to save; none only previews."}),
                "directory": ("STRING", {"default": "", "tooltip": "Choose an absolute folder, or a path relative to ComfyUI output. Blank uses output."}),
                "filename_prefix": ("STRING", {"default": names.DEFAULT_TEMPLATE, "tooltip": "The file name, without the extension: text and {tokens} such as {date}, {counter}, {hash}, {index}, {input} and {widget:ID.NAME}. Spaces and characters a filename cannot hold are replaced, and nothing is overwritten. Use the Build filename button."}),
                "save_without_metadata": ("BOOLEAN", {"default": False, "tooltip": "Omit all embedded metadata from saved PNGs, including connected custom metadata."}),
            },
            "optional": {
                "image_2": ("IMAGE", {"tooltip": "Connect another image or batch to enable slider comparison."}),
                "metadata": ("STRING", {"forceInput": True, "tooltip": "Optional text to embed verbatim as PNG parameters instead of the ComfyUI prompt and workflow. Unconnected keeps the default metadata; connected empty text replaces it with an empty value."}),
            },
            "hidden": {"prompt": "PROMPT", "extra_pnginfo": "EXTRA_PNGINFO", "node_id": "UNIQUE_ID"},
        }

    RETURN_TYPES = ()
    RETURN_NAMES = ()
    FUNCTION = "save"
    OUTPUT_NODE = True
    CATEGORY = "👑 Ray/🔧 Tools"
    DESCRIPTION = ("Save PNG images or compare two inputs with a draggable preview divider. Files are saved as "
                   "<filename_prefix>.png: build the name from text and tokens (date, counter, hash, widget values...) "
                   "with the Build filename button. Existing files are never overwritten.")

    def save(self, image_1, save_image="1", directory="", filename_prefix=names.DEFAULT_TEMPLATE,
             save_without_metadata=False, image_2=None, prompt=None, extra_pnginfo=None, node_id=None,
             metadata=None):
        if save_image not in ("none", "1", "2", "both"):
            raise ValueError("Save Image must be none, 1, 2, or both.")
        if save_image == "2" and image_2 is None:
            raise ValueError("Connect image_2 or choose Save Image 1 / none.")
        selected = {"none": set(), "1": {1}, "2": {2}, "both": {1, 2}}[save_image]
        # The prefix is the file's name, never a second way to select the destination: separators and other
        # reserved characters are replaced, so it cannot leave the chosen folder.
        parts = names.parse(filename_prefix.strip() or names.DEFAULT_TEMPLATE) if selected else None
        now, widgets = datetime.now(), prompt_widgets(prompt)
        output = destination_path(directory) if selected else None
        if output is not None:
            output.mkdir(parents=True, exist_ok=True)
        temp = Path(folder_paths.get_temp_directory()) / "ray_save_image"
        temp.mkdir(parents=True, exist_ok=True)
        pnginfo = None
        if selected and not save_without_metadata and not args.disable_metadata:
            pnginfo = PngInfo()
            if metadata is not None:
                pnginfo.add_text("parameters", metadata)
            else:
                if prompt is not None:
                    pnginfo.add_text("prompt", json.dumps(prompt))
                for key, value in (extra_pnginfo or {}).items():
                    pnginfo.add_text(key, json.dumps(value))
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
                    # Exclusive creation prevents overwriting, even by concurrent runs.
                    target, stream = names.create_unique(
                        output, parts, {"now": now, "index": index + 1, "input": number, "widgets": widgets}, ".png")
                    with stream:
                        image.save(stream, format="PNG", pnginfo=pnginfo, compress_level=4)
                    saved.append(str(target))
                preview_name = f"{token}.png"
                # Temp previews never embed workflows or local destination paths.
                image.save(temp / preview_name, format="PNG", compress_level=1)
                previews[number - 1].append({"filename": preview_name, "subfolder": "ray_save_image", "type": "temp"})
        return {"ui": {"ray_images_1": previews[0], "ray_images_2": previews[1],
                       "ray_saved": saved, "ray_directory": [str(output)] if saved else []}, "result": ()}


def open_image_location(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Save an image before opening its location.")
    path = destination_path(value)
    if not path.is_dir():
        raise ValueError("The saved image folder no longer exists.")
    if os.name != "nt":
        raise ValueError("Open in Explorer is available on Windows hosts.")
    # Open only a verified directory, never an arbitrary file or shell command.
    os.startfile(str(path), "explore")


def register_routes():
    import asyncio
    from aiohttp import web
    from server import PromptServer

    @PromptServer.instance.routes.post("/ray/save-image/open-location")
    async def open_location(request):
        require_local(request)
        if request.content_type != "application/json":
            return web.json_response({"error": "Expected a JSON request."}, status=415)
        try:
            data = await request.json()
            if not isinstance(data, dict):
                raise ValueError("Expected a folder path.")
            await asyncio.to_thread(open_image_location, data.get("path"))
            return web.json_response({"ok": True})
        except (OSError, ValueError) as error:
            return web.json_response({"error": str(error)}, status=400)
