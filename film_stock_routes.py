"""HTTP route for RayFilmStock: list LUT/XMP assets in a folder."""

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
        folder = request.query.get("folder") or ""
        try:
            files = rfs.list_assets(folder)
            return web.json_response({
                "ok": True,
                "folder": folder,
                "files": files,
                "none": rfs.NONE_CHOICE,
            })
        except Exception as e:
            return web.json_response({"ok": False, "error": str(e)}, status=500)
