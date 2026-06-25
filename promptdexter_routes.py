"""HTTP routes for RayPromptDexter: list categories and force-refresh sitemap."""

from aiohttp import web

try:
    from server import PromptServer
except ImportError:
    PromptServer = None

try:
    from . import ray_promptdexter as rpd
except ImportError:
    import ray_promptdexter as rpd


if PromptServer is not None:

    @PromptServer.instance.routes.get("/ray_promptdexter/categories")
    async def list_categories(request: web.Request):
        try:
            timeout = int(request.query.get("timeout", "10"))
        except ValueError:
            timeout = 10
        force = request.query.get("force") == "1"
        try:
            cats = rpd.get_categories(force_refresh=force, timeout=timeout)
            return web.json_response({"categories": cats, "any": rpd.ANY_CATEGORY})
        except Exception as e:
            return web.json_response(
                {"error": str(e), "categories": [], "any": rpd.ANY_CATEGORY},
                status=502,
            )

    @PromptServer.instance.routes.post("/ray_promptdexter/refresh")
    async def refresh_sitemap(request: web.Request):
        try:
            body = await request.json()
        except Exception:
            body = {}
        try:
            timeout = int(body.get("timeout", 10))
        except (TypeError, ValueError):
            timeout = 10
        try:
            rpd._SITEMAP_CACHE = None
            rpd._CATEGORIES_CACHE = None
            rpd._CATEGORY_URLS_CACHE.clear()
            cats = rpd.get_categories(force_refresh=True, timeout=timeout)
            return web.json_response({
                "ok": True,
                "categories": cats,
                "any": rpd.ANY_CATEGORY,
                "prompt_url_count": len(rpd._SITEMAP_CACHE or []),
            })
        except Exception as e:
            return web.json_response({"ok": False, "error": str(e)}, status=502)
