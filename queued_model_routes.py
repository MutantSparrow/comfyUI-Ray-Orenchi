"""Validate model paths without loading weights; retained for older clients."""
from aiohttp import web
from server import PromptServer

from .ray_queued_model_loader import model_path
from .route_security import require_local


@PromptServer.instance.routes.post("/ray/queued-model-loader/validate")
async def validate_models(request):
    require_local(request)
    try:
        data = await request.json()
        models = data.get("models") if isinstance(data, dict) else None
        if not isinstance(models, list) or not models:
            raise ValueError("Choose at least one diffusion model.")
        for model in models:
            model_path(model)
        return web.json_response({"ok": True})
    except (TypeError, ValueError) as error:
        return web.json_response({"error": str(error)}, status=400)
