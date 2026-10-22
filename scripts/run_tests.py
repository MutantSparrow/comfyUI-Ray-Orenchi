"""Run the suite against an installed ComfyUI, without starting its server."""
import argparse
import os
from pathlib import Path
import sys

parser = argparse.ArgumentParser()
parser.add_argument("--comfy-root", default=os.environ.get("COMFYUI_ROOT"))
parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
options, pytest_args = parser.parse_known_args()
if not options.comfy_root:
    parser.error("Set COMFYUI_ROOT or pass --comfy-root pointing to a ComfyUI checkout.")
root = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(root), str(Path(options.comfy_root).resolve())]
sys.argv[:] = [sys.argv[0]] + (["--cpu"] if options.device == "cpu" else [])
import comfy.options
comfy.options.enable_args_parsing()
if options.device == "cuda" and os.environ.get("RAY_TEST_CUDA") == "1":
    # Match ComfyUI's native allocator bootstrap in the isolated GPU test process.
    import comfy_aimdo.control as control
    control.init(nvml_pressure=False)
    import comfy.model_management as mm
    import comfy.memory_management
    import comfy.model_patcher
    from comfy.cli_args import args
    if not control.init_devices((device.index, int(args.vram_headroom * 1024**3))
                                for device in mm.get_all_torch_devices()):
        raise RuntimeError("The opt-in CUDA suite requires ComfyUI's working dynamic allocator.")
    comfy.memory_management.aimdo_enabled = True
    comfy.model_patcher.CoreModelPatcher = comfy.model_patcher.ModelPatcherDynamic
import pytest

os.chdir(root)
raise SystemExit(pytest.main(pytest_args or ["-q"]))
