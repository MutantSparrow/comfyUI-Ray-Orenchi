"""Publish an unpublished package version only after CI passed for this exact main commit."""
import os
from pathlib import Path
import subprocess
import sys
import tomllib

from packaging.version import Version
import requests

REPOSITORY = "MutantSparrow/comfyUI-Ray-Orenchi"


def get_json(url, token=None, allow_missing=False):
    headers = {"Accept": "application/vnd.github+json"} if token else {}
    if token:
        headers.update(Authorization="Bearer " + token, **{"X-GitHub-Api-Version": "2026-03-10"})
    response = requests.get(url, headers=headers, timeout=30, allow_redirects=False)
    if response.status_code == 404 and allow_missing:
        return None
    if response.status_code != 200:
        # Never include a response body or authenticated request in release logs.
        raise RuntimeError(f"Release verification returned HTTP {response.status_code}")
    return response.json()


def preflight(root, sha, github_token):
    metadata = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    project, config = metadata["project"], metadata["tool"]["comfy"]
    if config["PublisherId"] != "ray" or project["name"] != "ray-orenchi":
        raise RuntimeError("Unexpected Registry package or publisher; review publishing configuration.")
    actual = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    if sha != actual:
        raise RuntimeError("The checkout does not match the commit selected for publishing.")
    url = f"https://api.github.com/repos/{REPOSITORY}/actions/workflows/tests.yml/runs?head_sha={sha}&branch=main&event=push&per_page=30"
    runs = get_json(url, github_token)["workflow_runs"]
    eligible = [run for run in runs if run["head_sha"] == sha and run["head_branch"] == "main" and run["event"] == "push"]
    latest = max(eligible, key=lambda run: run["id"], default=None)
    if not latest or latest["status"] != "completed" or latest["conclusion"] != "success":
        raise RuntimeError("The latest Tests run has not passed for this exact main commit; publication is blocked.")
    node = get_json("https://api.comfy.org/nodes/" + project["name"], allow_missing=True)
    if node:
        publisher = node.get("publisher", {}).get("id")
        if publisher and publisher != config["PublisherId"]:
            raise RuntimeError("The Registry package belongs to a different publisher.")
        versions = get_json("https://api.comfy.org/nodes/" + project["name"] + "/versions")
        if any(Version(item["version"]) == Version(project["version"]) for item in versions):
            # A newly uploaded version can remain Pending while latest_version
            # is null. It is already immutable and must not be uploaded twice.
            return project["name"], project["version"], False
        published = (node.get("latest_version") or {}).get("version")
        if published:
            if Version(project["version"]) < Version(published):
                raise RuntimeError("The configured package version is older than the Registry version.")
            if Version(project["version"]) == Version(published):
                return project["name"], project["version"], False
    return project["name"], project["version"], True


def main():
    if os.environ.get("GITHUB_REPOSITORY") != REPOSITORY:
        raise RuntimeError("Registry releases must run in the configured GitHub repository.")
    root = Path(__file__).resolve().parents[1]
    name, version, should_publish = preflight(root, os.environ["PUBLISH_COMMIT"], os.environ["GH_TOKEN"])
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
            output.write(f"publish={str(should_publish).lower()}\n")
    print(f"{name} {version}: " + ("CI passed; ready to publish." if should_publish else "version already registered; skipping."))
    if sys.argv[1:] != ["publish"] or not should_publish:
        return
    token = os.environ.get("REGISTRY_ACCESS_TOKEN", "")
    if not token:
        raise RuntimeError("Set the REGISTRY_ACCESS_TOKEN repository Actions secret.")
    # Resolve the secret at runtime, so workflow source and shell logs contain no
    # expanded token. Avoid CalledProcessError, which includes command arguments.
    result = subprocess.run(["comfy", "--skip-prompt", "--no-enable-telemetry", "node", "publish", "--token", token], cwd=root)
    if result.returncode:
        raise RuntimeError("Comfy Registry publishing failed; inspect the masked CLI output.")
    print(f"Uploaded {name} {version} to the Comfy Registry.")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)
