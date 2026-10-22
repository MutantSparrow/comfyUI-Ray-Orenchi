import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("registry_release", ROOT / "scripts" / "registry_release.py")
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)
SHA = "a" * 40


def setup_release(monkeypatch, runs, node=None):
    monkeypatch.setattr(release.subprocess, "check_output", lambda *args, **kwargs: SHA)
    def get(url, token=None, allow_missing=False):
        if url.startswith("https://api.github.com/"):
            assert token == "github-credential"
            return {"workflow_runs": runs}
        assert url == "https://api.comfy.org/nodes/ray-orenchi"
        assert token is None and allow_missing
        return node
    monkeypatch.setattr(release, "get_json", get)


def run(**updates):
    return {"id": 1, "head_sha": SHA, "head_branch": "main", "event": "push",
            "status": "completed", "conclusion": "success", **updates}


def test_unpublished_version_requires_success_for_exact_main_commit(monkeypatch):
    setup_release(monkeypatch, [run()])
    assert release.preflight(ROOT, SHA, "github-credential") == ("ray-orenchi", "1.0.0", True)


@pytest.mark.parametrize("runs", [[], [run(head_sha="b" * 40)], [run(head_branch="feature")],
                                      [run(event="pull_request")], [run(conclusion="failure")],
                                      [run(status="in_progress")], [run(), run(id=2, conclusion="failure")]])
def test_missing_failed_pending_or_unrelated_ci_cannot_release(monkeypatch, runs):
    setup_release(monkeypatch, runs)
    with pytest.raises(RuntimeError, match="latest Tests run has not passed"):
        release.preflight(ROOT, SHA, "github-credential")


def test_different_checkout_cannot_release(monkeypatch):
    setup_release(monkeypatch, [run()])
    with pytest.raises(RuntimeError, match="checkout does not match"):
        release.preflight(ROOT, "b" * 40, "github-credential")


def test_existing_version_is_skipped_and_older_version_is_rejected(monkeypatch):
    setup_release(monkeypatch, [run()], {"publisher": {"id": "ray"}, "latest_version": {"version": "1.0.0"}})
    assert release.preflight(ROOT, SHA, "github-credential")[2] is False
    setup_release(monkeypatch, [run()], {"publisher": {"id": "ray"}, "latest_version": {"version": "1.1.0"}})
    with pytest.raises(RuntimeError, match="older than"):
        release.preflight(ROOT, SHA, "github-credential")


def test_other_publishers_package_is_rejected(monkeypatch):
    setup_release(monkeypatch, [run()], {"publisher": {"id": "someone-else"}, "latest_version": {"version": "1.0.0"}})
    with pytest.raises(RuntimeError, match="different publisher"):
        release.preflight(ROOT, SHA, "github-credential")


def test_registry_errors_do_not_silently_allow_a_release(monkeypatch):
    from types import SimpleNamespace
    for status in (401, 403, 429, 500):
        monkeypatch.setattr(release.requests, "get", lambda *a, **kw: SimpleNamespace(status_code=status))
        with pytest.raises(RuntimeError, match=f"HTTP {status}"):
            release.get_json("https://api.comfy.org/nodes/ray-orenchi", allow_missing=True)
