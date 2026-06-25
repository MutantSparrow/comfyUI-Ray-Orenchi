"""HTTP routes for RayCivitAI: base-model list + cache refresh."""

from aiohttp import web

try:
    from server import PromptServer
except ImportError:
    PromptServer = None

try:
    from . import ray_civitai as rc
except ImportError:
    import ray_civitai as rc


if PromptServer is not None:

    @PromptServer.instance.routes.get("/ray_civitai/base_models")
    async def list_base_models(request: web.Request):
        return web.json_response({
            "base_models": list(rc.BASE_MODELS),
            "default": rc.BASE_MODELS_DEFAULT,
            "modes": list(rc.MODES),
            "periods": list(rc.PERIODS),
            "sorts": list(rc.SORTS),
            "has_token": rc.has_token(),
            "token_file": rc._TOKEN_FILE.name,
        })

    @PromptServer.instance.routes.post("/ray_civitai/refresh")
    async def refresh_cache(request: web.Request):
        try:
            rc.clear_cache()
            return web.json_response({"ok": True})
        except Exception as e:
            return web.json_response({"ok": False, "error": str(e)}, status=502)
