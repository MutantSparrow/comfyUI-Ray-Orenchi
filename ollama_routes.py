import asyncio
import json
import time

from aiohttp import web

try:
    from server import PromptServer
except ImportError:
    PromptServer = None

try:
    import ollama
except ImportError:
    ollama = None

from .ray_ollama_chat import IMAGE_CACHE, AUDIO_CACHE


ABORT_FLAGS: dict = {}
MODELS_CACHE: dict = {}  # url -> (timestamp, [{name, capabilities, families}])
MODELS_CACHE_TTL = 60.0


async def _fetch_model_info(client, name: str) -> dict:
    try:
        info = await client.show(name)
        if isinstance(info, dict):
            caps = info.get("capabilities") or []
            details = info.get("details") or {}
        else:
            caps = getattr(info, "capabilities", None) or []
            details = getattr(info, "details", None) or {}
            if hasattr(details, "model_dump"):
                details = details.model_dump()
            elif not isinstance(details, dict):
                details = {}
        families = details.get("families") or []
        family = details.get("family")
        if family and family not in families:
            families = list(families) + [family]
        param_size = details.get("parameter_size") or ""
        return {
            "name": name,
            "capabilities": [str(c) for c in caps],
            "families": [str(f) for f in families],
            "parameter_size": str(param_size),
        }
    except Exception:
        return {"name": name, "capabilities": [], "families": [], "parameter_size": ""}


def _client(host: str):
    if ollama is None:
        raise RuntimeError("ollama package not installed")
    return ollama.AsyncClient(host=host)


if PromptServer is not None:

    @PromptServer.instance.routes.get("/ray_ollama/models")
    async def list_models(request: web.Request):
        url = request.query.get("url", "http://localhost:11434")
        force = request.query.get("force") == "1"
        if ollama is None:
            return web.json_response({"error": "ollama package not installed", "models": []}, status=500)

        now = time.time()
        cached = MODELS_CACHE.get(url)
        if cached and not force and (now - cached[0] < MODELS_CACHE_TTL):
            return web.json_response({"models": cached[1]})

        try:
            client = ollama.AsyncClient(host=url)
            listing = await client.list()
            raw = listing.get("models", []) if isinstance(listing, dict) else getattr(listing, "models", [])
            names = []
            for m in raw:
                if isinstance(m, dict):
                    name = m.get("model") or m.get("name")
                else:
                    name = getattr(m, "model", None) or getattr(m, "name", None)
                if name:
                    names.append(str(name))
            names = sorted(set(names))
            results = await asyncio.gather(*[_fetch_model_info(client, n) for n in names])
            results.sort(key=lambda x: x["name"])
            MODELS_CACHE[url] = (now, results)
            return web.json_response({"models": results})
        except Exception as e:
            return web.json_response({"error": str(e), "models": []}, status=502)

    @PromptServer.instance.routes.post("/ray_ollama/abort")
    async def abort_chat(request: web.Request):
        try:
            body = await request.json()
        except Exception:
            body = {}
        nid = str(body.get("node_id", ""))
        if nid:
            ABORT_FLAGS[nid] = True
        return web.json_response({"ok": True})

    @PromptServer.instance.routes.post("/ray_ollama/chat")
    async def chat_stream(request: web.Request):
        try:
            body = await request.json()
        except Exception as e:
            return web.json_response({"error": f"bad json: {e}"}, status=400)

        server_url = body.get("server_url") or "http://localhost:11434"
        model = body.get("model") or ""
        messages = body.get("messages") or []
        options = body.get("options") or {}
        keep_alive = body.get("keep_alive") or "5m"
        attach_node_id = body.get("attach_image_node_id")
        attached_b64 = body.get("attached_image_b64")
        attached_audio_b64 = body.get("attached_audio_b64")
        attach_audio_node_id = body.get("attach_audio_node_id")
        think = bool(body.get("think", False))
        node_id = str(body.get("node_id", ""))

        imgs = []
        if attached_b64:
            imgs = [attached_b64] if isinstance(attached_b64, str) else list(attached_b64)
        elif attach_node_id is not None:
            imgs = IMAGE_CACHE.get(str(attach_node_id), [])

        auds = []
        if attached_audio_b64:
            auds = [attached_audio_b64] if isinstance(attached_audio_b64, str) else list(attached_audio_b64)
        elif attach_audio_node_id is not None:
            auds = AUDIO_CACHE.get(str(attach_audio_node_id), [])

        if (imgs or auds) and messages:
            for i in range(len(messages) - 1, -1, -1):
                if messages[i].get("role") == "user":
                    if imgs:
                        messages[i]["images"] = imgs
                    if auds:
                        messages[i]["audios"] = auds
                    break

        if not model:
            return web.json_response({"error": "no model selected"}, status=400)
        if ollama is None:
            return web.json_response({"error": "ollama package not installed"}, status=500)

        ABORT_FLAGS.pop(node_id, None)

        resp = web.StreamResponse(
            status=200,
            headers={
                "Content-Type": "text/event-stream",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
        await resp.prepare(request)

        client_gone = False

        async def send(obj):
            nonlocal client_gone
            if client_gone:
                return False
            try:
                await resp.write(f"data: {json.dumps(obj)}\n\n".encode("utf-8"))
                return True
            except (ConnectionResetError, ConnectionError, asyncio.CancelledError):
                client_gone = True
                return False
            except Exception:
                client_gone = True
                return False

        full_text = ""
        try:
            client = _client(server_url)
            chat_kwargs = dict(
                model=model,
                messages=messages,
                stream=True,
                keep_alive=keep_alive,
                options=options,
            )
            if think:
                chat_kwargs["think"] = True
            try:
                stream = await client.chat(**chat_kwargs)
            except TypeError:
                chat_kwargs.pop("think", None)
                stream = await client.chat(**chat_kwargs)
            async for chunk in stream:
                if ABORT_FLAGS.get(node_id) or client_gone:
                    await send({"aborted": True})
                    break
                msg = chunk.get("message") if isinstance(chunk, dict) else getattr(chunk, "message", None)
                piece = ""
                piece_think = ""
                if isinstance(msg, dict):
                    piece = msg.get("content", "") or ""
                    piece_think = msg.get("thinking", "") or ""
                elif msg is not None:
                    piece = getattr(msg, "content", "") or ""
                    piece_think = getattr(msg, "thinking", "") or ""
                if piece_think:
                    if not await send({"think": piece_think}):
                        break
                if piece:
                    full_text += piece
                    if not await send({"chunk": piece}):
                        break
                done = chunk.get("done") if isinstance(chunk, dict) else getattr(chunk, "done", False)
                if done:
                    break
            await send({"done": True, "message": {"role": "assistant", "content": full_text}})
        except (ConnectionResetError, ConnectionError, asyncio.CancelledError):
            client_gone = True
        except Exception as e:
            await send({"error": str(e)})
        finally:
            ABORT_FLAGS.pop(node_id, None)
            if not client_gone:
                try:
                    await resp.write_eof()
                except Exception:
                    pass

        return resp
