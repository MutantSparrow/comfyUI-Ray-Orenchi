"""Shared checks for routes that access the server's local filesystem or desktop."""
import ipaddress
import json
from urllib.parse import urlsplit

from aiohttp import web


def is_local(address):
    if address == "localhost":
        return True
    try:
        ip = ipaddress.ip_address(address)
    except (ValueError, TypeError):
        return False
    mapped = getattr(ip, "ipv4_mapped", None)
    return ip.is_loopback or bool(mapped and mapped.is_loopback)


def _local_authority(value):
    try:
        authority = urlsplit("//" + value)
        authority.port  # Validate malformed or out-of-range ports, too.
        return not authority.username and not authority.password and not authority.path and not authority.query and not authority.fragment and is_local(authority.hostname)
    except ValueError:
        return False


def _local_forwarded_address(value):
    value = value.strip()
    if is_local(value):
        return True
    return _local_authority(value)


def is_local_request(request):
    # Headers and request.remote (which middleware can override) cannot establish locality.
    peer = request.transport.get_extra_info("peername") if request.transport is not None else None
    if not isinstance(peer, (tuple, list)) or not peer or not is_local(peer[0]):
        return False
    if not _local_authority(request.headers.get("Host", "")):
        return False
    for value in request.headers.getall("Origin", ()):
        try:
            origin = urlsplit(value)
            if origin.scheme not in ("http", "https") or origin.path or origin.query or origin.fragment or not _local_authority(origin.netloc):
                return False
        except ValueError:
            return False
    for name in ("X-Forwarded-For", "X-Real-IP", "X-Forwarded-Host"):
        for value in request.headers.getall(name, ()):
            if not all(_local_forwarded_address(part) for part in value.split(",")):
                return False
    if "Forwarded" in request.headers:
        if not request.forwarded:
            return False
        for proxy in request.forwarded:
            if not _local_forwarded_address(proxy.get("for", "")):
                return False
            if "host" in proxy and not _local_authority(proxy["host"]):
                return False
    return True


def forbidden(message):
    return web.HTTPForbidden(text=json.dumps({"ok": False, "error": message}), content_type="application/json")


def require_local(request):
    if not is_local_request(request):
        raise forbidden("This action is available only from ComfyUI on this computer.")
