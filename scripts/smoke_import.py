"""Real dependency/startup smoke test; only the HTTP route host is substituted."""
import argparse
import importlib.util
import os
from pathlib import Path
import sys
from types import SimpleNamespace

parser = argparse.ArgumentParser()
parser.add_argument("--comfy-root", default=os.environ.get("COMFYUI_ROOT"))
options = parser.parse_args()
if not options.comfy_root:
    parser.error("Set COMFYUI_ROOT or pass --comfy-root.")
root = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(root), str(Path(options.comfy_root).resolve())]
sys.argv[:] = [sys.argv[0], "--cpu"]
os.environ["HF_HUB_OFFLINE"] = "1"
import comfy.options
comfy.options.enable_args_parsing()
from aiohttp import web

routes = web.RouteTableDef()
sys.modules["server"] = SimpleNamespace(PromptServer=SimpleNamespace(instance=SimpleNamespace(routes=routes)))
spec = importlib.util.spec_from_file_location("ray_orenchi_smoke", root / "__init__.py", submodule_search_locations=[str(root)])
pack = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = pack
spec.loader.exec_module(pack)
assert len(pack.NODE_CLASS_MAPPINGS) == 29
assert set(pack.NODE_CLASS_MAPPINGS) == set(pack.NODE_DISPLAY_NAME_MAPPINGS)
for node in pack.NODE_CLASS_MAPPINGS.values():
    assert callable(getattr(node, node.FUNCTION))
    assert isinstance(node.INPUT_TYPES(), dict)
for path in ("/ray/folders/scan", "/ray/folders/delete", "/ray/browse", "/ray/save-image/open-location",
             "/ray/model-tools/preview"):
    assert any(route.path == path for route in routes), path
assert (root / pack.WEB_DIRECTORY / "ray_folders.js").is_file()
print(f"Startup smoke passed: {len(pack.NODE_CLASS_MAPPINGS)} stable node IDs, {len(routes)} routes, web assets present")
