"""Read-only previews for the Model Tools panels, using Orenchi's locality checks."""
import asyncio
from aiohttp import web
from server import PromptServer
from .route_security import require_local
from . import model_tools as core


@PromptServer.instance.routes.post("/ray/model-tools/preview")
async def preview(request):
    require_local(request)
    try:
        body = await request.json()
        action = body.get("action")
        if action == "metadata":
            data = await asyncio.to_thread(core.load_metadata, body.get("path", ""))
            return web.json_response({"metadata": data, "metadata_json": core.json_text(data), "source": str(core.clean_path(body["path"]))})
        if action == "inspect":
            data = await asyncio.to_thread(core.inspect_model, body.get("path", ""), 5000)
        elif action == "compare":
            data = await asyncio.to_thread(core.compare_models, body.get("path_a", ""), body.get("path_b", ""), body.get("components", "diffusion"))
        else:
            raise ValueError("Unknown preview action.")
        return web.json_response(data)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        return web.json_response({"error": str(exc)}, status=400)
