"""Media endpoints scoped to folders explicitly opened by the gallery."""
from __future__ import annotations

import asyncio
import os
import secrets
import sys
import time
from collections import OrderedDict
from pathlib import Path

try:
    from . import ray_folders as folders
    from .route_security import forbidden, is_local_request, require_local
except ImportError:
    import ray_folders as folders
    from route_security import forbidden, is_local_request, require_local

_ROOTS = OrderedDict()

try:
    if sys.platform == "win32":
        from send2trash.win.modern import send2trash
    else:
        from send2trash import send2trash
except ImportError:
    send2trash = None


def grant(folder, recursive):
    token = secrets.token_urlsafe(24)
    _ROOTS[token] = (folders.folder_path(folder), recursive, time.monotonic())
    while len(_ROOTS) > 128:
        _ROOTS.popitem(last=False)
    return token


def session(token):
    root = _ROOTS.get(token)
    if not root or time.monotonic() - root[2] > 24 * 3600:
        raise ValueError("This folder session has expired. Refresh the gallery.")
    return root


def resolve(token, relative):
    root = session(token)
    return folders.resolve_media(root[0], relative, root[1])


def remote_roots():
    roots = []
    for value in os.environ.get("RAY_FOLDERS_REMOTE_ROOTS", "").split(os.pathsep):
        if not value.strip():
            continue
        path = Path(value.strip().strip('"')).expanduser()
        if not path.is_absolute():
            continue
        try:
            roots.append((Path(os.path.abspath(path)), folders.folder_path(path)))
        except (OSError, ValueError):
            continue
    return roots


def authorize_folder(value, local):
    if local:
        return folders.folder_path(value)
    roots = remote_roots()
    denied = "Remote Folders access requires a folder in the server's RAY_FOLDERS_REMOTE_ROOTS allowlist."
    if not roots:
        raise forbidden(denied)
    path = Path(str(value or "").strip().strip('"')).expanduser()
    if not path.is_absolute():
        raise forbidden(denied)
    path = Path(os.path.abspath(path))
    if not any(path.is_relative_to(logical) or path.is_relative_to(canonical) for logical, canonical in roots):
        raise forbidden(denied)
    path = path.resolve()
    if not any(path.is_relative_to(canonical) for _, canonical in roots):
        raise forbidden(denied)
    return folders.folder_path(path)


def authorize_session(token, local):
    root = session(token)
    if not local:
        authorize_folder(root[0], False)
    return root


def check_sidecars(path, root):
    for sidecar in (path.with_suffix(path.suffix + ".txt"), path.with_suffix(".txt")):
        if not sidecar.resolve().is_relative_to(root):
            raise forbidden("A prompt sidecar points outside the opened folder.")


def scoped_media(token, relative, local, prompts=False):
    root = authorize_session(token, local)
    path = folders.resolve_media(root[0], relative, root[1])
    if not local and prompts:
        check_sidecars(path, root[0])
    return path


def scan_folder(value, opts, query, local):
    return folders.scan(authorize_folder(value, local), opts, query)


def search_session(token, files, query, hide_no_prompt, local):
    root = authorize_session(token, local)
    if not local:
        for relative in files:
            try:
                path = folders.resolve_media(root[0], relative, root[1])
            except folders.MEDIA_ERRORS:
                continue
            check_sidecars(path, root[0])
    return folders.search_files(root[0], files, query, root[1], hide_no_prompt)


def delete_asset(token, relative, revision):
    root = _ROOTS.get(token)
    path = resolve(token, relative)
    original = root[0] / relative
    if original.is_symlink() or original.absolute() != path:
        raise ValueError("Asset links cannot be deleted from Folders.")
    stat = path.stat()
    if revision != f"{stat.st_mtime_ns}-{stat.st_size}":
        raise ValueError("This asset changed since it was loaded. Refresh the folder before deleting it.")
    if send2trash is None:
        raise RuntimeError("Recycle Bin support is unavailable. Install the node pack requirements and restart ComfyUI.")
    send2trash(str(path))
    return {"file": relative}


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

    async def media_path(request, prompts=False):
        return await work(scoped_media, request.query.get("root", ""), request.query.get("file", ""), is_local_request(request), prompts)

    @PromptServer.instance.routes.post("/ray/folders/scan")
    async def scan(request):
        try:
            data = await request.json()
            if not isinstance(data, dict):
                raise ValueError("Expected a folder request.")
            opts = folders.settings(data.get("settings"))
            result = await work(scan_folder, data.get("folder"), opts, data.get("name_filter", ""), is_local_request(request))
            result["root"] = grant(result["folder"], opts["recursive"])
            return web.json_response(result)
        except folders.MEDIA_ERRORS + (TypeError,) as error:
            return web.json_response({"error": str(error)}, status=400)

    @PromptServer.instance.routes.get("/ray/folders/metadata")
    async def metadata(request):
        try:
            return web.json_response(await work(folders.metadata, await media_path(request, prompts=True)))
        except folders.MEDIA_ERRORS + (TypeError,) as error:
            return web.json_response({"error": str(error)}, status=400)

    @PromptServer.instance.routes.post("/ray/folders/delete")
    async def delete(request):
        require_local(request)
        try:
            data = await request.json()
            if not isinstance(data, dict) or not all(isinstance(data.get(key), str) and data[key] for key in ("root", "file", "revision")):
                raise ValueError("Expected an asset, folder session and file revision.")
            return web.json_response(await work(delete_asset, data["root"], data["file"], data["revision"]))
        except folders.MEDIA_ERRORS + (TypeError, RuntimeError) as error:
            return web.json_response({"error": str(error)}, status=400)

    @PromptServer.instance.routes.post("/ray/folders/search")
    async def search(request):
        try:
            data = await request.json()
            if not isinstance(data, dict) or not isinstance(data.get("query"), str):
                raise ValueError("Expected a filename/prompt search query.")
            files = data.get("files")
            if not isinstance(files, list) or len(files) > 128 or not all(isinstance(item, str) for item in files):
                raise ValueError("Expected a batch of at most 128 relative file paths.")
            result = await work(search_session, data.get("root", ""), files, data["query"], data.get("hide_no_prompt") is True, is_local_request(request))
            return web.json_response(result)
        except folders.MEDIA_ERRORS + (TypeError,) as error:
            return web.json_response({"error": str(error)}, status=400)

    @PromptServer.instance.routes.get("/ray/folders/thumbnail")
    async def thumbnail(request):
        try:
            path = await work(folders.thumbnail, await media_path(request))
            return web.FileResponse(path, headers={"Cache-Control": "private, max-age=86400"})
        except folders.MEDIA_ERRORS + (TypeError,) as error:
            return web.json_response({"error": str(error)}, status=400)

    @PromptServer.instance.routes.get("/ray/folders/media")
    async def media(request):
        try:
            return web.FileResponse(await media_path(request), headers={"Cache-Control": "no-cache"})
        except (OSError, ValueError, TypeError) as error:
            return web.json_response({"error": str(error)}, status=400)
