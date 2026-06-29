"""HTTP routes for RayFilmStock: list .cube/.3dl LUTs and .xmp sidecars in a folder."""

from aiohttp import web

try:
    from server import PromptServer
except ImportError:
    PromptServer = None

try:
    from . import ray_film_stock as rfs
except ImportError:
    import ray_film_stock as rfs


if PromptServer is not None:

    @PromptServer.instance.routes.get("/ray_film_stock/list")
    async def list_assets(request: web.Request):
        kind = (request.query.get("kind") or "lut").lower()
        folder = request.query.get("folder") or ""
        exts = rfs._LUT_EXTS if kind == "lut" else rfs._XMP_EXTS
        try:
            files = rfs.list_files(folder, exts)
            return web.json_response({
                "ok": True,
                "kind": kind,
                "folder": folder,
                "files": files,
            })
        except Exception as e:
            return web.json_response({"ok": False, "error": str(e)}, status=500)
