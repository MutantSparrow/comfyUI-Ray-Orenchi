"""Update or check the end-user reference against real registered node schemas."""
import argparse
import json
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]


def cell(value):
    return str(value).replace("|", "\\|").replace("\r", "").replace("\n", "<br>")


def render(nodes):
    lines = ["# Inputs, controls, and outputs", "",
             "This reference describes the registered nodes, their controls, defaults, and connections.",
             "Some controls appear only in the relevant mode. Saved editor/gallery state and compatibility",
             "inputs are listed for workflows using those fields; use the visible panel to edit their contents.",
             "See [the node guide](NODES.md) for examples and each node's default view.", ""]
    for node_id, data in sorted(nodes.items()):
        lines += [f'<a id="{node_id}"></a>', "", f"## {data['display_name']} (`{node_id}`)", "",
                  data.get("description", "").strip(), "",
                  "| Input / control | Type | Default / choices / limits | Description |",
                  "| --- | --- | --- | --- |"]
        inputs = [(name, spec) for group in ("required", "optional")
                  for name, spec in data.get("input", {}).get(group, {}).items()]
        for name, spec in inputs:
            kind = spec[0]
            opts = spec[1] if len(spec) > 1 else {}
            meta = []
            if "default" in opts:
                meta.append("Default: " + json.dumps(opts["default"], ensure_ascii=False))
            if isinstance(kind, list):
                meta.append("Choices: " + ", ".join(str(v) for v in kind))
            for key in ("min", "max", "step"):
                if key in opts:
                    meta.append(f"{key}: {opts[key]}")
            type_name = "COMBO" if isinstance(kind, list) else str(kind)
            lines.append(f"| `{name}` | {cell(type_name)} | {cell('; '.join(meta) or 'Connection')} | {cell(opts.get('tooltip', ''))} |")
        if not inputs:
            lines.append("| — | — | — | No input controls. |")
        lines += ["", "| Output | Type | Description |", "| --- | --- | --- |"]
        for index, kind in enumerate(data.get("output", [])):
            name = data.get("output_name", data["output"])[index]
            list_tag = " list" if data.get("output_is_list", [False] * len(data["output"]))[index] else ""
            lines.append(f"| `{name}` | {kind}{list_tag} | {cell(data.get('output_tooltips', [])[index])} |")
        if not data.get("output"):
            lines.append("| — | — | Output node; results appear in its preview or saved files. |")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8194")
    parser.add_argument("--schema-json", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.schema_json:
        info = json.loads(args.schema_json.read_text(encoding="utf-8"))
    else:
        with urlopen(args.url.rstrip("/") + "/object_info", timeout=30) as response:
            info = json.load(response)
    nodes = {name: value for name, value in info.items() if name.startswith("Ray")}
    if not nodes:
        raise SystemExit("No registered Ray nodes found.")
    missing = []
    for node_id, data in nodes.items():
        for group in ("required", "optional"):
            for name, spec in data.get("input", {}).get(group, {}).items():
                if len(spec) < 2 or not str(spec[1].get("tooltip", "")).strip():
                    missing.append(f"{node_id}.{name}")
        tips = data.get("output_tooltips", [])
        for i in range(len(data.get("output", []))):
            if i >= len(tips) or not tips[i].strip():
                missing.append(f"{node_id}.output[{i}]")
    if missing:
        raise SystemExit("Missing descriptions: " + ", ".join(missing))
    expected = render(nodes)
    destination = ROOT / "NODE_REFERENCE.md"
    if args.check:
        if not destination.is_file() or destination.read_text(encoding="utf-8") != expected:
            raise SystemExit("NODE_REFERENCE.md does not match the registered schemas.")
    else:
        destination.write_text(expected, encoding="utf-8")
    print(f"{'Checked' if args.check else 'Updated'} complete input/output documentation for {len(nodes)} nodes.")


if __name__ == "__main__":
    main()
