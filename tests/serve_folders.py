"""Real media/routes + a small ComfyUI browser fixture. Run with ComfyUI's Python."""
import json
import asyncio
import shutil
import sys
import tempfile
import types
import wave
from pathlib import Path

import av
import numpy as np
from aiohttp import web
from PIL import Image, PngImagePlugin

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
TEMP = tempfile.TemporaryDirectory(prefix="ray-folders-browser-")
MEDIA = Path(TEMP.name) / "media"
MEDIA.mkdir()
INPUT = Path(TEMP.name) / "input"
INPUT.mkdir()
routes = web.RouteTableDef()
sys.modules["server"] = types.SimpleNamespace(PromptServer=types.SimpleNamespace(instance=types.SimpleNamespace(routes=routes)))
import ray_folders
import folders_routes
LARGE = False
SCAN_DELAY = 0
THUMBNAIL_DELAY = 0
METRICS = {"files": [], "active": 0, "peak": 0}
_scan = ray_folders.scan
_resolve_media = ray_folders.resolve_media


def stress_scan(*args, **kwargs):
    result = _scan(*args, **kwargs)
    if LARGE:
        result["items"].extend({"id": f"__virtual_{i:06}.png", "name": f"virtual_{i:06}.png", "kind": "image", "size": 64, "modified": 1, "revision": "synthetic-1"} for i in range(100000))
        result["counts"]["image"] += 100000
    return result


ray_folders.scan = stress_scan
ray_folders.resolve_media = lambda folder, relative, recursive: _resolve_media(folder, "gallery_000.png" if relative.startswith("__virtual_") else relative, recursive)

def create_media():
    MEDIA.mkdir(exist_ok=True)
    png = PngImagePlugin.PngInfo()
    png.add_text("parameters", "A red cat\nsitting in warm light\nNegative prompt: blur\nSteps: 20")
    png.add_text("workflow", json.dumps({"nodes": [{"id": 1, "type": "CLIPTextEncode", "widgets_values": ["A red cat"]}], "links": []}))
    Image.new("RGB", (180, 120), "#d43c39").save(MEDIA / "cat.png", pnginfo=png)
    Image.new("RGB", (100, 180), "#394cd4").save(MEDIA / "dog.png")
    for index in range(80):
        Image.new("RGB", (32, 32), (index * 3, 85, 140)).save(MEDIA / f"gallery_{index:03}.png")
    with wave.open(str(MEDIA / "sound.wav"), "wb") as audio:
        audio.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
        samples = (np.sin(np.arange(16000) * 2 * np.pi * 440 / 16000) * 10000).astype("<i2")
        audio.writeframes(samples.tobytes())
    with av.open(str(MEDIA / "movie.mp4"), "w") as video:
        stream = video.add_stream("libx264", rate=10)
        stream.width, stream.height, stream.pix_fmt = 96, 64, "yuv420p"
        for index in range(10):
            frame = av.VideoFrame.from_ndarray(np.full((64, 96, 3), (60 + index * 10, 120, 160), dtype=np.uint8), format="rgb24")
            for packet in stream.encode(frame):
                video.mux(packet)
        for packet in stream.encode():
            video.mux(packet)


create_media()


@routes.post("/fixture/reset")
async def reset(request):
    global LARGE, SCAN_DELAY, THUMBNAIL_DELAY
    assert MEDIA.resolve().is_relative_to(Path(TEMP.name).resolve())
    if MEDIA.exists():
        shutil.rmtree(MEDIA)
    create_media()
    LARGE, SCAN_DELAY, THUMBNAIL_DELAY = False, 0, 0
    METRICS.update(files=[], active=0, peak=0)
    return web.json_response({"ok": True})


@routes.get("/fixture")
async def fixture(request):
    return web.json_response({"folder": str(MEDIA)})


@routes.post("/fixture/loading")
async def loading(request):
    global SCAN_DELAY, THUMBNAIL_DELAY
    data = await request.json()
    SCAN_DELAY = min(2, max(0, float(data.get("scan_delay", 0))))
    THUMBNAIL_DELAY = min(2, max(0, float(data.get("thumbnail_delay", 0))))
    if data.get("reset"):
        METRICS["files"].clear()
        METRICS["peak"] = METRICS["active"]
    return web.json_response({"ok": True})


@routes.get("/fixture/metrics")
async def metrics(request):
    return web.json_response(METRICS)


@web.middleware
async def loading_metrics(request, handler):
    if request.path == "/ray/folders/scan":
        await asyncio.sleep(SCAN_DELAY)
    if request.path != "/ray/folders/thumbnail":
        return await handler(request)
    METRICS["files"].append(request.query.get("file"))
    METRICS["active"] += 1
    METRICS["peak"] = max(METRICS["peak"], METRICS["active"])
    try:
        await asyncio.sleep(THUMBNAIL_DELAY)
        return await handler(request)
    finally:
        METRICS["active"] -= 1


@routes.post("/fixture/large")
async def large(request):
    global LARGE
    LARGE = (await request.json()).get("enabled", False)
    return web.json_response({"ok": True})


@routes.post("/fixture/recover")
async def recover(request):
    MEDIA.mkdir(exist_ok=True)
    Image.new("RGB", (32, 32), "red").save(MEDIA / "returned.png")
    return web.json_response({"ok": True})


@routes.post("/fixture/delete")
async def delete(request):
    data = await request.json()
    if data.get("folder"):
        assert MEDIA.resolve().is_relative_to(Path(TEMP.name).resolve())
        shutil.rmtree(MEDIA)
    else:
        (MEDIA / "cat.png").unlink(missing_ok=True)
    return web.json_response({"ok": True})


@routes.post("/upload/image")
async def upload(request):
    reader = await request.multipart()
    part = await reader.next()
    name = Path(part.filename).name
    (INPUT / name).write_bytes(await part.read())
    return web.json_response({"name": name, "subfolder": "", "type": "input"})


@routes.get("/view")
async def view(request):
    return web.FileResponse(INPUT / Path(request.query["filename"]).name)


@routes.get("/{tail:.*}")
async def static(request):
    tail = request.match_info["tail"]
    if tail == "scripts/app.js":
        path = ROOT / "tests/folders_fixture.js"
    elif tail == "scripts/api.js":
        return web.Response(text='export const api=Object.assign(new EventTarget(),{apiURL:url=>url,fetchApi:(url,options)=>fetch(url,options)});', content_type="text/javascript")
    elif tail.startswith("extensions/ray/"):
        path = ROOT / "web" / tail[len("extensions/ray/"):]
    else:
        path = ROOT / (tail or "tests/folders_browser.html")
    path = path.resolve()
    if not path.is_relative_to(ROOT) or not path.is_file():
        raise web.HTTPNotFound()
    return web.FileResponse(path, headers={"Cache-Control": "no-store"})


if __name__ == "__main__":
    app = web.Application(middlewares=[loading_metrics])
    app.add_routes(routes)
    web.run_app(app, host="127.0.0.1", port=int(sys.argv[1]) if len(sys.argv) > 1 else 8200)
