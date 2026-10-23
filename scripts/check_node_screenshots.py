"""Check node screenshot coverage and freshness without importing ComfyUI."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import re
import struct
import sys


ROOT = Path(__file__).resolve().parents[1]


def registry():
    assignments = {
        node.targets[0].id: ast.literal_eval(node.value)
        for node in ast.parse((ROOT / "__init__.py").read_text(encoding="utf-8")).body
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id in {"_NODE_MODULES", "NODE_DISPLAY_NAME_MAPPINGS"}
    }
    return assignments["_NODE_MODULES"], assignments["NODE_DISPLAY_NAME_MAPPINGS"]


def local_module(name, directory):
    path = directory.joinpath(*name.split("."))
    for candidate in (path.with_suffix(".py"), path / "__init__.py"):
        if candidate.is_file() and candidate.is_relative_to(ROOT):
            return candidate
    return None


def python_dependencies(start):
    found, pending = set(), [start]
    while pending:
        path = pending.pop()
        if path in found:
            continue
        found.add(path)
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8-sig"))):
            names = []
            directory = ROOT
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    directory = path.parent
                    for _ in range(node.level - 1):
                        directory = directory.parent
                names = [node.module] if node.module else []
                names += [(node.module + "." if node.module else "") + alias.name
                          for alias in node.names]
            for name in names:
                dependency = local_module(name, directory)
                if dependency and dependency not in found:
                    pending.append(dependency)
    return found


def javascript_dependencies(starts):
    found, pending = set(), list(starts)
    while pending:
        path = pending.pop()
        if path in found:
            continue
        found.add(path)
        source = path.read_text(encoding="utf-8-sig")
        for reference in re.findall(r"(?:from\s*|import\s*\(?)[\"'](\.[^\"']+)[\"']", source):
            dependency = (path.parent / reference).resolve()
            if dependency.is_relative_to(ROOT) and dependency.is_file() and dependency not in found:
                pending.append(dependency)
    return found


def sources():
    modules, names = registry()
    scripts = {p: p.read_text(encoding="utf-8-sig") for p in (ROOT / "web").iterdir()
               if p.suffix in {".js", ".mjs"}}
    result = {}
    for node_id, module in modules.items():
        files = python_dependencies(ROOT / (module + ".py"))
        entries = [path for path, source in scripts.items() if re.search(r"\b" + node_id + r"\b", source)]
        entries.append(ROOT / "web" / "ray_bucket_tints.js")
        files |= javascript_dependencies(entries)
        hashes = {p.relative_to(ROOT).as_posix(): hashlib.sha256(
            p.read_bytes().replace(b"\r\n", b"\n")).hexdigest() for p in sorted(files)}
        signature = {"module":module, "display_name":names[node_id], "files":hashes}
        result[node_id] = hashlib.sha256(json.dumps(signature, sort_keys=True).encode()).hexdigest()
    return result


def check():
    expected = sources()
    folder = ROOT / "screenshots"
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    nodes = manifest["nodes"]
    errors = []
    if manifest.get("renderer") != "ComfyUI Nodes 2.0":
        errors.append("The default screenshot renderer must be Nodes 2.0")
    if set(nodes) != set(expected):
        errors.append(f"Screenshot registry mismatch: {sorted(set(nodes) ^ set(expected))}")
    actual = {path.stem for path in folder.glob("Ray*.png")}
    if actual != set(expected):
        errors.append(f"PNG coverage mismatch: {sorted(actual ^ set(expected))}")
    documentation = (ROOT / "NODES.md").read_text(encoding="utf-8")
    for node_id, fingerprint in expected.items():
        entry = nodes.get(node_id, {})
        path = folder / (node_id + ".png")
        if entry.get("source_fingerprint") != fingerprint:
            errors.append(f"{node_id}: node sources changed; recapture its screenshot")
        if f"(screenshots/{node_id}.png)" not in documentation:
            errors.append(f"{node_id}: missing image in NODES.md")
        if not path.is_file():
            errors.append(f"{node_id}: missing PNG")
            continue
        data = path.read_bytes()
        if data[:8] != b"\x89PNG\r\n\x1a\n":
            errors.append(f"{node_id}: invalid PNG signature")
        else:
            width, height = struct.unpack(">II", data[16:24])
            scale, padding = manifest["device_scale_factor"], manifest["padding_css_px"]
            expected_size = tuple(int(-(-size // 1) + 2 * padding) * scale
                                  for size in (entry.get("width_css_px", 0), entry.get("height_css_px", 0)))
            if (width, height) != expected_size:
                errors.append(f"{node_id}: PNG dimensions do not match the recorded full-node frame")
        if entry.get("sha256") != hashlib.sha256(data).hexdigest():
            errors.append(f"{node_id}: PNG differs from its capture manifest")
        if entry.get("file") != path.name:
            errors.append(f"{node_id}: unexpected image filename")
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(f"All {len(expected)} Nodes 2.0 screenshots are present, linked, and current.")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources-json", action="store_true", help="Source fingerprints for the capture script")
    options = parser.parse_args()
    if options.sources_json:
        print(json.dumps(sources(), sort_keys=True))
    else:
        sys.exit(check())
