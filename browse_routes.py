"""HTTP route behind the Browse buttons: shows a file or folder dialog and returns the chosen path.

A web page is never told where a picked file lives on disk, so the ComfyUI server shows the dialog itself,
with Python's built-in Tk (the system dialog on Windows and macOS), and sends the path back to be pasted into
the widget. The dialog runs in its own process so a stuck dialog can never block the server, and nothing the
page sends is run as code: values reach it as arguments only.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading

try:
    from .route_security import is_local, require_local
except ImportError:
    from route_security import is_local, require_local

KINDS = ("folder", "file", "save")
TIMEOUT_SECONDS = 15 * 60
MAX_FILTERS = 8
_busy = threading.Lock()


class BrowseUnavailable(Exception):
    """The dialog could not be shown."""


class BrowseBusy(Exception):
    """A dialog is already open."""


def clean_filters(filters):
    """[(label, [ext, ...])] from whatever the page sent: plain extensions only, a few filters at most."""
    out = []
    for item in filters if isinstance(filters, list) else []:
        try:
            label, exts = item
        except (TypeError, ValueError):
            continue
        exts = [e.lstrip(".").lower() for e in exts if isinstance(e, str)] if isinstance(exts, list) else []
        exts = [e for e in exts if re.fullmatch(r"[a-z0-9]{1,16}", e)]
        if exts:
            out.append((re.sub(r"[|\n\r]", " ", str(label))[:40] or "Files", exts))
        if len(out) >= MAX_FILTERS:
            break
    return out


def start_location(kind, initial):
    """The folder a dialog opens in (and the file to preselect), from a path that may be mistyped: the nearest
    folder that exists, or nothing."""
    text = str(initial or "").strip().strip('"')
    if not text or not os.path.isabs(text):
        return "", ""
    path = os.path.normpath(text)
    if kind == "save" and not os.path.isdir(path):
        folder = os.path.dirname(path)
        if os.path.isdir(folder):
            return folder, os.path.basename(path)
    if kind == "file" and os.path.isfile(path):
        return os.path.dirname(path), os.path.basename(path)
    while path and not os.path.isdir(path):
        parent = os.path.dirname(path)
        if parent == path:
            return "", ""
        path = parent
    return path, ""


_TK = r"""
import json, sys
try:
    import tkinter
    from tkinter import filedialog
except Exception:
    sys.exit(3)
kind, folder, name, title, filters = sys.argv[1:6]
root = tkinter.Tk()
root.withdraw()
try:
    root.attributes("-topmost", True)   # in front of the browser rather than behind it
except Exception:
    pass
root.update()
filter_defs = json.loads(filters)
types = [(label, " ".join("*." + e for e in exts)) for label, exts in filter_defs] + [("All files", "*.*")]
if kind == "folder":
    path = filedialog.askdirectory(parent=root, title=title, initialdir=folder or None, mustexist=False)
elif kind == "save":
    extension = "." + filter_defs[0][1][0] if filter_defs else ""
    path = filedialog.asksaveasfilename(parent=root, title=title, initialdir=folder or None, initialfile=name or None,
                                      filetypes=types, defaultextension=extension, confirmoverwrite=False)
else:
    path = filedialog.askopenfilename(parent=root, title=title, initialdir=folder or None, initialfile=name or None, filetypes=types)
sys.stdout.buffer.write((path or "").encode("utf-8"))
"""


def build_command(kind, initial, title, filters):
    """The command that shows the dialog and prints the chosen path. Pure, so it can be tested."""
    folder, name = start_location(kind, initial)
    title = str(title or {"folder": "Choose a folder", "file": "Choose a file", "save": "Choose a save file"}[kind])[:120]
    return [sys.executable, "-c", _TK, kind, folder, name, title, json.dumps(clean_filters(filters))]


def run_command(argv, timeout=TIMEOUT_SECONDS):
    """Run the dialog. Returns the chosen path (with the system's separators), or None when it was closed."""
    kwargs = {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)} if os.name == "nt" else {}
    try:
        done = subprocess.run(argv, capture_output=True, timeout=timeout, stdin=subprocess.DEVNULL, **kwargs)
    except OSError as error:
        raise BrowseUnavailable(f"The file dialog could not be started ({error}).") from error
    except subprocess.TimeoutExpired as error:
        raise BrowseUnavailable("The file dialog was left open for too long and was closed.") from error
    out = done.stdout.decode("utf-8-sig", errors="replace").strip("\r\n")
    if done.returncode == 3:
        raise BrowseUnavailable("Python's Tk is not installed, so no file dialog can be shown. Type the path instead.")
    if done.returncode != 0:
        err = done.stderr.decode("utf-8", errors="replace").strip()
        raise BrowseUnavailable((err.splitlines() or ["The file dialog failed."])[-1][:200])
    return os.path.normpath(out) if out else None


def pick(kind, initial="", title="", filters=None):
    if kind not in KINDS:
        raise ValueError("kind must be 'folder', 'file' or 'save'.")
    if not _busy.acquire(blocking=False):
        raise BrowseBusy("A file dialog is already open.")
    try:
        return run_command(build_command(kind, initial, title, filters))
    finally:
        _busy.release()


try:
    from aiohttp import web
    from server import PromptServer
except ImportError:
    PromptServer = None

if PromptServer is not None:
    import asyncio

    @PromptServer.instance.routes.post("/ray/browse")
    async def browse(request):
        require_local(request)
        if request.content_type != "application/json":
            return web.json_response({"ok": False, "error": "Expected a JSON request."}, status=415)
        try:
            data = await request.json()
            if not isinstance(data, dict):
                raise ValueError("Expected a JSON object.")
            path = await asyncio.to_thread(pick, data.get("kind"), data.get("initial", ""), data.get("title", ""), data.get("filters"))
        except ValueError as error:
            return web.json_response({"ok": False, "error": str(error)}, status=400)
        except BrowseBusy as error:
            return web.json_response({"ok": False, "error": str(error)}, status=409)
        except BrowseUnavailable as error:
            return web.json_response({"ok": False, "error": str(error)}, status=501)
        if path is None:
            return web.json_response({"ok": True, "cancelled": True})
        return web.json_response({"ok": True, "path": path})
