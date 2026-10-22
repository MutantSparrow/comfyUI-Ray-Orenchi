from pathlib import Path
import tomllib

from packaging.requirements import Requirement

ROOT = Path(__file__).resolve().parents[1]


def requirements(path):
    result = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("-r "):
            result.extend(requirements(path.parent / line[3:]))
        else:
            result.append(Requirement(line))
    return result


def test_registry_and_clone_installs_declare_the_same_dependencies():
    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    normalize = lambda req: (req.name.lower(), str(req.specifier), str(req.marker))
    clone = requirements(ROOT / "requirements.txt")
    assert set(map(normalize, clone)) == {normalize(Requirement(value)) for value in metadata["project"]["dependencies"]}
    assert {req.name for req in clone}.isdisjoint({"torch", "torchvision", "torchaudio"})
    assert {"av", "threadpoolctl"}.issubset({req.name for req in clone})
    assert metadata["tool"]["comfy"]["PublisherId"] == "ray"
    assert metadata["tool"]["comfy"]["requires-comfyui"] == ">=0.42.0"
    assert metadata["project"]["requires-python"] == ">=3.11,<3.14"
