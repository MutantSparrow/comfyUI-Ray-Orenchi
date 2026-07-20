"""HTTP routes for RayPromptLibrary: stats, source list, clear."""

from aiohttp import web

try:
    from server import PromptServer
except ImportError:
    PromptServer = None

try:
    from . import ray_prompt_library as rpl
except ImportError:
    import ray_prompt_library as rpl


if PromptServer is not None:

    @PromptServer.instance.routes.get("/ray_prompt_library/stats")
    async def lib_stats(request: web.Request):
        try:
            return web.json_response(rpl.stats())
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)

    @PromptServer.instance.routes.get("/ray_prompt_library/sources")
    async def lib_sources(request: web.Request):
        try:
            s = rpl.stats()
            return web.json_response({"sources": s.get("sources", [])})
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)

    @PromptServer.instance.routes.post("/ray_prompt_library/clear")
    async def lib_clear(request: web.Request):
        try:
            data = await request.json()
        except Exception:
            data = {}
        if data.get("confirm") != "yes":
            return web.json_response(
                {"ok": False, "error": "missing confirm=yes"}, status=400
            )
        try:
            n = rpl.clear_library()
            return web.json_response({"ok": True, "deleted": n})
        except Exception as e:
            return web.json_response({"ok": False, "error": str(e)}, status=500)

    @PromptServer.instance.routes.get("/ray_prompt_library/search")
    async def lib_search(request: web.Request):
        q = request.query.get("q", "")
        source = request.query.get("source", "")
        tag = request.query.get("tag", "")
        sort = request.query.get("sort", rpl.SORT_RECENT)
        try:
            limit = int(request.query.get("limit", "200"))
        except ValueError:
            limit = 200
        try:
            offset = int(request.query.get("offset", "0"))
        except ValueError:
            offset = 0
        try:
            res = rpl.search_prompts(
                q=q, source=source, tag=tag, sort=sort,
                limit=limit, offset=offset,
            )
            return web.json_response(res)
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)

    @PromptServer.instance.routes.get("/ray_prompt_library/row")
    async def lib_row(request: web.Request):
        try:
            rid = int(request.query.get("id", "-1"))
        except ValueError:
            return web.json_response({"error": "id must be integer"}, status=400)
        try:
            row = rpl.fetch_by_id(rid)
            if row is None:
                return web.json_response({"error": "not found"}, status=404)
            row.pop("embedding", None)
            return web.json_response(row)
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)
