"""Media endpoints scoped to folders explicitly opened by the gallery."""
from __future__ import annotations

import asyncio
import secrets
import time
from collections import OrderedDict

try:
    from . import ray_folders as folders
except ImportError:
    import ray_folders as folders

_ROOTS = OrderedDict()


def grant(folder, recursive):
    token = secrets.token_urlsafe(24)
    _ROOTS[token] = (folders.folder_path(folder), recursive, time.monotonic())
    while len(_ROOTS) > 128:
        _ROOTS.popitem(last=False)
    return token


def resolve(token, relative):
    root = _ROOTS.get(token)
    if not root or time.monotonic() - root[2] > 24 * 3600:
        raise ValueError("This folder session has expired. Refresh the gallery.")
    return folders.resolve_media(root[0], relative, root[1])


try:
    from aiohttp import web
    from server import PromptServer
except ImportError:
    PromptServer = None

if PromptServer is not None and getattr(PromptServer, "instance", None) is not None:
    _WORK = asyncio.Semaphore(4)

    async def work(fn, *args):
        async with _WORK:
            return await asyncio.to_thread(fn, *args)

    def media_path(request):
        return resolve(request.query.get("root", ""), request.query.get("file", ""))

    @PromptServer.instance.routes.post("/ray/folders/scan")
    async def scan(request):
        try:
            data = await request.json()
            if not isinstance(data, dict):
                raise ValueError("Expected a folder request.")
            opts = folders.settings(data.get("settings"))
            result = await work(folders.scan, data.get("folder"), opts, data.get("name_filter", ""))
            result["root"] = grant(result["folder"], opts["recursive"])
            return web.json_response(result)
        except folders.MEDIA_ERRORS + (TypeError,) as error:
            return web.json_response({"error": str(error)}, status=400)

    @PromptServer.instance.routes.get("/ray/folders/metadata")
    async def metadata(request):
        try:
            return web.json_response(await work(folders.metadata, media_path(request)))
        except folders.MEDIA_ERRORS + (TypeError,) as error:
            return web.json_response({"error": str(error)}, status=400)

    @PromptServer.instance.routes.get("/ray/folders/thumbnail")
    async def thumbnail(request):
        try:
            path = await work(folders.thumbnail, media_path(request))
            return web.FileResponse(path, headers={"Cache-Control": "private, max-age=86400"})
        except folders.MEDIA_ERRORS + (TypeError,) as error:
            return web.json_response({"error": str(error)}, status=400)

    @PromptServer.instance.routes.get("/ray/folders/media")
    async def media(request):
        try:
            return web.FileResponse(media_path(request), headers={"Cache-Control": "no-cache"})
        except (OSError, ValueError, TypeError) as error:
            return web.json_response({"error": str(error)}, status=400)
