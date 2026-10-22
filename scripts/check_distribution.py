"""Check that the wheel retains runtime modules, browser models and notices."""
from pathlib import Path
import sys
import zipfile

folder = Path(sys.argv[1] if len(sys.argv) > 1 else "dist")
wheel = next(folder.glob("*.whl"))
with zipfile.ZipFile(wheel) as archive:
    names = set(archive.namelist())
    root = Path(__file__).resolve().parents[1]
    required = {"ray_orenchi/" + path.name for path in root.glob("*.py")}
    required.update({
        "ray_orenchi/web/ray_folders.js", "ray_orenchi/web/help_defs.mjs",
        "ray_orenchi/web/vendor/nsfw/model/model.json",
        "ray_orenchi/web/vendor/nsfw/model/group1-shard1of2",
        "ray_orenchi/web/vendor/nsfw/model/group1-shard2of2",
        "ray_orenchi/ray_pixel_fixer/LICENSE", "ray_orenchi/ray_pixel_fixer/NOTICE.md",
        "ray_orenchi/web/vendor/nsfw/LICENSE-NSFWJS",
        "ray_orenchi/web/vendor/nsfw/LICENSE-TENSORFLOW",
    })
    assert required <= names, f"Missing package files: {sorted(required - names)}"
    assert not any(name.startswith(("tests/", "node_modules/")) for name in names)
print(f"Distribution verified: {len(names)} files; runtime, UI, models and attribution included")
