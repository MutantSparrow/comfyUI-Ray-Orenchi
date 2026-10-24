import asyncio
import importlib.util
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from aiohttp import web
from aiohttp.test_utils import make_mocked_request, TestClient, TestServer
from multidict import CIMultiDict
from PIL import Image

import route_security as security

ROOT = Path(__file__).resolve().parents[1]


def request(method="POST", path="/", data=None, peer="127.0.0.1", headers=None):
    fields = CIMultiDict({"Host": "127.0.0.1:8188", "Content-Type": "application/json"})
    fields.update(headers or {})
    transport = Mock()
    transport.get_extra_info.side_effect = lambda name, default=None: ((peer, 12345) if peer is not None else None) if name == "peername" else default
    result = make_mocked_request(method, path, headers=fields, transport=transport)
    result._read_bytes = json.dumps(data or {}).encode()
    return result


def invoke(handler, incoming):
    async def run():
        try:
            return await handler(incoming)
        except web.HTTPException as response:
            return response
    return asyncio.run(run())


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, ROOT / file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def endpoints(monkeypatch, tmp_path):
    table = web.RouteTableDef()
    monkeypatch.delenv("RAY_FOLDERS_REMOTE_ROOTS", raising=False)
    monkeypatch.setitem(sys.modules, "server", SimpleNamespace(PromptServer=SimpleNamespace(instance=SimpleNamespace(routes=table))))
    monkeypatch.setitem(sys.modules, "folder_paths", SimpleNamespace(get_output_directory=lambda: str(tmp_path), get_temp_directory=lambda: str(tmp_path)))
    monkeypatch.setitem(sys.modules, "comfy.cli_args", SimpleNamespace(args=SimpleNamespace(disable_metadata=False)))
    folders = load("folders_routes_security_tests", "folders_routes.py")
    browse = load("browse_routes_security_tests", "browse_routes.py")
    save = load("save_routes_security_tests", "ray_save_image.py")
    save.register_routes()
    handlers = {route.path: route.handler for route in table}
    return SimpleNamespace(folders=folders, browse=browse, save=save, handlers=handlers, table=table)


@pytest.mark.parametrize("address", ["127.0.0.1", "127.0.0.2", "::1", "::ffff:127.0.0.1", "localhost"])
def test_loopback_addresses(address):
    assert security.is_local(address)


@pytest.mark.parametrize("address", [None, "", "192.168.1.20", "10.0.0.1", "8.8.8.8", "::ffff:192.168.1.20", "127.0.0.1.evil.example", "localhost.evil.example", "0.0.0.0", "::"])
def test_nonlocal_addresses(address):
    assert not security.is_local(address)


@pytest.mark.parametrize("headers", [
    {}, {"Origin": "http://localhost:8188"}, {"Host": "[::1]:8188", "Origin": "http://[::1]:8188"},
    {"Forwarded": 'for="[::1]:1234";host="localhost:8188"'},
    {"X-Forwarded-For": "127.0.0.1, ::1", "X-Real-IP": "127.0.0.1"},
])
def test_local_request_uses_socket_and_local_browser_authority(headers):
    assert security.is_local_request(request(headers=headers))


@pytest.mark.parametrize("headers", [
    {"Host": "public.example"}, {"Host": "127.0.0.1:99999"}, {"Host": "localhost#evil"},
    {"Origin": "https://public.example"}, {"Origin": "null"},
    {"X-Forwarded-For": "192.168.1.20"}, {"X-Forwarded-For": "127.0.0.1, 192.168.1.20"},
    {"X-Real-IP": "192.168.1.20"}, {"X-Forwarded-Host": "public.example"},
    {"Forwarded": "for=192.168.1.20"}, {"Forwarded": "for=unknown"}, {"Forwarded": "garbage"},
    {"Forwarded": 'for=127.0.0.1;host="public.example"'},
])
def test_forwarded_remote_requests_and_nonlocal_origins_are_not_local(headers):
    assert not security.is_local_request(request(headers=headers))


def test_spoofed_request_remote_and_forwarding_headers_cannot_make_a_lan_peer_local():
    incoming = request(peer="192.168.1.20", headers={"X-Forwarded-For": "127.0.0.1", "Forwarded": "for=127.0.0.1", "Origin": "http://localhost"})
    incoming._read_bytes = None
    incoming = incoming.clone(remote="127.0.0.1")
    assert not security.is_local_request(incoming)
    assert not security.is_local_request(request(peer=None))


@pytest.mark.parametrize("route,owner,action", [
    ("/ray/browse", "browse", "pick"),
    ("/ray/save-image/open-location", "save", "open_image_location"),
    ("/ray/folders/delete", "folders", "delete_asset"),
])
@pytest.mark.parametrize("peer,headers", [
    ("192.168.1.20", {}), ("127.0.0.1", {"X-Forwarded-For": "192.168.1.20"}),
    ("127.0.0.1", {"Host": "tunnel.example", "Origin": "https://tunnel.example"}),
])
def test_local_actions_reject_remote_requests_before_side_effects(endpoints, monkeypatch, route, owner, action, peer, headers):
    effect = Mock(side_effect=AssertionError("No filesystem or desktop action is permitted"))
    monkeypatch.setattr(getattr(endpoints, owner), action, effect)
    response = invoke(endpoints.handlers[route], request(path=route, peer=peer, headers=headers, data={"path": "C:/", "file": "cat.png", "root": "token", "revision": "v1"}))
    assert response.status == 403
    assert json.loads(response.text)["error"]
    effect.assert_not_called()


def test_remote_scan_is_denied_by_default_before_reading_a_directory_or_granting_a_token(endpoints, monkeypatch, tmp_path):
    scan = Mock(side_effect=AssertionError("An unauthorized directory must not be scanned"))
    monkeypatch.setattr(endpoints.folders.folders, "scan", scan)
    route = "/ray/folders/scan"
    response = invoke(endpoints.handlers[route], request(path=route, peer="192.168.1.20", data={"folder": str(tmp_path)}))
    assert response.status == 403 and not endpoints.folders._ROOTS
    scan.assert_not_called()


def test_local_scan_can_open_an_arbitrary_directory(endpoints, tmp_path):
    route = "/ray/folders/scan"
    response = invoke(endpoints.handlers[route], request(path=route, data={"folder": str(tmp_path)}))
    assert response.status == 200
    assert json.loads(response.text)["root"] in endpoints.folders._ROOTS


def test_remote_scan_only_grants_configured_roots_and_subdirectories(endpoints, monkeypatch, tmp_path):
    allowed = tmp_path / "allowed"; allowed.mkdir()
    nested = allowed / "nested"; nested.mkdir()
    other = tmp_path / "allowed-sibling"; other.mkdir()
    monkeypatch.setenv("RAY_FOLDERS_REMOTE_ROOTS", str(allowed))
    route = "/ray/folders/scan"
    for folder, status in [(allowed, 200), (nested, 200), (other, 403), (allowed / ".." / "allowed-sibling", 403), (tmp_path / "absent", 403)]:
        response = invoke(endpoints.handlers[route], request(path=route, peer="192.168.1.20", data={"folder": str(folder)}))
        assert response.status == status
    assert len(endpoints.folders._ROOTS) == 2


def test_remote_allowlist_supports_multiple_absolute_directories_and_fails_closed(endpoints, monkeypatch, tmp_path):
    first = tmp_path / "a"; first.mkdir()
    second = tmp_path / "b"; second.mkdir()
    monkeypatch.setenv("RAY_FOLDERS_REMOTE_ROOTS", os.pathsep.join([str(first), str(second)]))
    assert endpoints.folders.authorize_folder(second, False) == second.resolve()
    for config in ("", "relative", str(tmp_path / "missing")):
        monkeypatch.setenv("RAY_FOLDERS_REMOTE_ROOTS", config)
        with pytest.raises(web.HTTPForbidden):
            endpoints.folders.authorize_folder(first, False)


@pytest.mark.parametrize("route", ["/ray/folders/media", "/ray/folders/thumbnail", "/ray/folders/metadata", "/ray/folders/search"])
def test_remote_clients_cannot_reuse_local_tokens_for_unapproved_folders(endpoints, monkeypatch, tmp_path, route):
    allowed = tmp_path / "approved"; allowed.mkdir()
    private = tmp_path / "private"; private.mkdir()
    Image.new("RGB", (4, 4)).save(private / "cat.png")
    token = endpoints.folders.grant(private, False)
    monkeypatch.setenv("RAY_FOLDERS_REMOTE_ROOTS", str(allowed))
    if route.endswith("search"):
        incoming = request(path=route, peer="192.168.1.20", data={"root": token, "files": ["cat.png"], "query": "cat"})
    else:
        incoming = request("GET", route + f"?root={token}&file=cat.png", peer="192.168.1.20")
    response = invoke(endpoints.handlers[route], incoming)
    assert response.status == 403


@pytest.mark.parametrize("route", ["/ray/folders/media", "/ray/folders/thumbnail", "/ray/folders/metadata", "/ray/folders/search"])
def test_remote_reads_work_inside_the_allowlist_and_are_revoked_when_it_changes(endpoints, monkeypatch, tmp_path, route):
    Image.new("RGB", (4, 4)).save(tmp_path / "cat.png")
    token = endpoints.folders.grant(tmp_path, False)
    monkeypatch.setenv("RAY_FOLDERS_REMOTE_ROOTS", str(tmp_path))
    def incoming():
        if route.endswith("search"):
            return request(path=route, peer="192.168.1.20", data={"root": token, "files": ["cat.png"], "query": "cat"})
        return request("GET", route + f"?root={token}&file=cat.png", peer="192.168.1.20")
    assert invoke(endpoints.handlers[route], incoming()).status == 200
    monkeypatch.delenv("RAY_FOLDERS_REMOTE_ROOTS")
    assert invoke(endpoints.handlers[route], incoming()).status == 403


def test_remote_allowlist_does_not_allow_deletion(endpoints, monkeypatch, tmp_path):
    path = tmp_path / "cat.png"; Image.new("RGB", (4, 4)).save(path)
    token = endpoints.folders.grant(tmp_path, False)
    monkeypatch.setenv("RAY_FOLDERS_REMOTE_ROOTS", str(tmp_path))
    trash = Mock(); monkeypatch.setattr(endpoints.folders, "send2trash", trash)
    stat = path.stat()
    route = "/ray/folders/delete"
    response = invoke(endpoints.handlers[route], request(path=route, peer="192.168.1.20", data={"root": token, "file": "cat.png", "revision": f"{stat.st_mtime_ns}-{stat.st_size}"}))
    assert response.status == 403 and path.is_file()
    trash.assert_not_called()


@pytest.mark.parametrize("route,owner,action,data", [
    ("/ray/browse", "browse", "pick", {"kind": "folder"}),
    ("/ray/save-image/open-location", "save", "open_image_location", {"path": "C:/"}),
    ("/ray/folders/delete", "folders", "delete_asset", {"root": "token", "file": "cat.png", "revision": "v1"}),
])
def test_local_actions_still_reach_their_handlers(endpoints, monkeypatch, route, owner, action, data):
    effect = Mock(return_value={"file": "cat.png"} if owner == "folders" else None)
    monkeypatch.setattr(getattr(endpoints, owner), action, effect)
    assert invoke(endpoints.handlers[route], request(path=route, data=data)).status == 200
    effect.assert_called_once()


def test_symlink_escape_and_prompt_sidecar_escape_are_denied(endpoints, monkeypatch, tmp_path):
    allowed = tmp_path / "allowed"; allowed.mkdir()
    outside = tmp_path / "outside"; outside.mkdir()
    link = allowed / "link"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("Symbolic links require Windows developer mode or administrator permission")
    monkeypatch.setenv("RAY_FOLDERS_REMOTE_ROOTS", str(allowed))
    with pytest.raises(web.HTTPForbidden):
        endpoints.folders.authorize_folder(link, False)
    Image.new("RGB", (4, 4)).save(allowed / "cat.png")
    secret = outside / "private.txt"; secret.write_text("Must not be read remotely")
    (allowed / "cat.txt").symlink_to(secret)
    token = endpoints.folders.grant(allowed, False)
    for route in ("/ray/folders/metadata", "/ray/folders/search"):
        incoming = request("GET", route + f"?root={token}&file=cat.png", peer="192.168.1.20") if route.endswith("metadata") else request(path=route, peer="192.168.1.20", data={"root": token, "files": ["cat.png"], "query": "private"})
        assert invoke(endpoints.handlers[route], incoming).status == 403


def test_canonical_paths_and_sidecars_are_checked_before_reading(endpoints, monkeypatch, tmp_path):
    allowed = tmp_path / "allowed"; allowed.mkdir()
    outside = tmp_path / "outside"; outside.mkdir()
    link = allowed / "link"
    Image.new("RGB", (4, 4)).save(allowed / "cat.png")
    secret = outside / "secret.txt"; secret.write_text("Private prompt")
    sidecar = allowed / "cat.txt"
    original = Path.resolve
    def resolve(path, *args, **kwargs):
        if path == link:
            return outside
        if path == sidecar:
            return secret
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, "resolve", resolve)
    monkeypatch.setenv("RAY_FOLDERS_REMOTE_ROOTS", str(allowed))
    with pytest.raises(web.HTTPForbidden):
        endpoints.folders.authorize_folder(link, False)
    token = endpoints.folders.grant(allowed, False)
    with pytest.raises(web.HTTPForbidden):
        endpoints.folders.scoped_media(token, "cat.png", False, prompts=True)
    with pytest.raises(web.HTTPForbidden):
        endpoints.folders.search_session(token, ["cat.png"], "Private", False, False)
    assert endpoints.folders.scoped_media(token, "cat.png", False) == (allowed / "cat.png").resolve()


def test_live_http_restrictions_and_local_reading(endpoints, monkeypatch, tmp_path):
    allowed = tmp_path / "allowed"; allowed.mkdir()
    outside = tmp_path / "private"; outside.mkdir()
    Image.new("RGB", (4, 4)).save(allowed / "cat.png")
    Image.new("RGB", (4, 4)).save(outside / "private.png")
    trash = Mock(); monkeypatch.setattr(endpoints.folders, "send2trash", trash)
    explorer = Mock(); monkeypatch.setattr(endpoints.save, "open_image_location", explorer)
    picker = Mock(); monkeypatch.setattr(endpoints.browse, "pick", picker)
    async def exercise():
        app = web.Application(); app.add_routes(endpoints.table)
        async with TestClient(TestServer(app)) as client:
            local = await client.post("/ray/folders/scan", json={"folder": str(outside)})
            assert local.status == 200
            private_token = (await local.json())["root"]
            remote = {"X-Forwarded-For": "192.168.1.20"}
            denied = await client.post("/ray/folders/scan", json={"folder": str(allowed)}, headers=remote)
            assert denied.status == 403 and "error" in await denied.json()
            monkeypatch.setenv("RAY_FOLDERS_REMOTE_ROOTS", str(allowed))
            approved = await client.post("/ray/folders/scan", json={"folder": str(allowed)}, headers=remote)
            assert approved.status == 200
            token = (await approved.json())["root"]
            image = await client.get("/ray/folders/media", params={"root": token, "file": "cat.png"}, headers=remote)
            assert image.status == 200 and (await image.read()).startswith(b"\x89PNG")
            private = await client.get("/ray/folders/media", params={"root": private_token, "file": "private.png"}, headers=remote)
            assert private.status == 403
            for route, data in [
                ("/ray/folders/delete", {"root": token, "file": "cat.png", "revision": "unused"}),
                ("/ray/save-image/open-location", {"path": str(allowed)}),
                ("/ray/browse", {"kind": "folder"}),
            ]:
                response = await client.post(route, json=data, headers=remote)
                assert response.status == 403
                assert "error" in await response.json()
            local_image = await client.get("/ray/folders/media", params={"root": private_token, "file": "private.png"})
            assert local_image.status == 200
            await local_image.read()
    asyncio.run(exercise())
    trash.assert_not_called(); explorer.assert_not_called(); picker.assert_not_called()
