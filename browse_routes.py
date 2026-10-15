"""HTTP route that opens the operating system's own file or folder dialog.

A web page cannot learn the absolute path of a folder from the browser's picker, so the Browse buttons ask
the ComfyUI server to open the native dialog and send the chosen path back. The server runs on the same
computer as the browser (ComfyUI Desktop and local installs), so the dialog appears on your screen. The
route refuses requests from other machines, because a dialog opened there would appear on the server.

The dialog comes from the platform: Windows PowerShell / pwsh (WinForms), macOS osascript, Linux zenity or
kdialog, with Tk as a last resort. The path travels back on stdout; nothing the page sends is ever run as code
(it reaches the dialog through environment variables or arguments only).
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import threading

KINDS = ("folder", "file")
TIMEOUT_SECONDS = 15 * 60
MAX_FILTERS = 8
_busy = threading.Lock()


class BrowseUnavailable(Exception):
    """No file dialog can be shown on this machine. `retry` says another dialog program may still work."""

    def __init__(self, message, retry=False):
        super().__init__(message)
        self.retry = retry


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
        exts = [e for e in exts if re.fullmatch(r"[a-z0-9]{1,8}", e)]
        if exts:
            out.append((re.sub(r"[|\n\r]", " ", str(label))[:40] or "Files", exts))
        if len(out) >= MAX_FILTERS:
            break
    return out


def start_location(kind, initial):
    """The directory a dialog should open in (and the file to preselect), from a path the user may have typed
    wrongly: the nearest folder that exists, or nothing."""
    text = str(initial or "").strip().strip('"')
    if not text or not os.path.isabs(text):
        return "", ""
    path = os.path.normpath(text)
    if kind == "file" and os.path.isfile(path):
        return os.path.dirname(path), os.path.basename(path)
    while path and not os.path.isdir(path):
        parent = os.path.dirname(path)
        if parent == path:
            return "", ""
        path = parent
    return path, ""


_POWERSHELL = r"""
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms
[System.Windows.Forms.Application]::EnableVisualStyles()
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
# A hidden top-most owner brings the dialog to the front instead of leaving it behind the browser.
$owner = New-Object System.Windows.Forms.Form
$owner.TopMost = $true; $owner.ShowInTaskbar = $false; $owner.Opacity = 0
$owner.StartPosition = 'CenterScreen'; $owner.Width = 1; $owner.Height = 1
$owner.Show(); $owner.Activate()
try {
    if ($env:RAY_BROWSE_KIND -eq 'folder') {
        $d = New-Object System.Windows.Forms.FolderBrowserDialog
        $d.Description = $env:RAY_BROWSE_TITLE
        try { $d.UseDescriptionForTitle = $true } catch {}
        if ($env:RAY_BROWSE_DIR) { $d.SelectedPath = $env:RAY_BROWSE_DIR }
        $d.ShowNewFolderButton = $true
        if ($d.ShowDialog($owner) -eq [System.Windows.Forms.DialogResult]::OK) { [Console]::Out.Write($d.SelectedPath) }
    } else {
        $d = New-Object System.Windows.Forms.OpenFileDialog
        $d.Title = $env:RAY_BROWSE_TITLE
        $d.Filter = $env:RAY_BROWSE_FILTER
        if ($env:RAY_BROWSE_DIR) { $d.InitialDirectory = $env:RAY_BROWSE_DIR }
        if ($env:RAY_BROWSE_NAME) { $d.FileName = $env:RAY_BROWSE_NAME }
        if ($d.ShowDialog($owner) -eq [System.Windows.Forms.DialogResult]::OK) { [Console]::Out.Write($d.FileName) }
    }
} finally { $owner.Dispose() }
"""

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
    root.attributes("-topmost", True)
except Exception:
    pass
types = [(label, " ".join("*." + e for e in exts)) for label, exts in json.loads(filters)] + [("All files", "*.*")]
if kind == "folder":
    path = filedialog.askdirectory(title=title, initialdir=folder or None, mustexist=False)
else:
    path = filedialog.askopenfilename(title=title, initialdir=folder or None, initialfile=name or None, filetypes=types)
sys.stdout.write(path or "")
"""

_APPLESCRIPT = """on run argv
    set promptText to item 1 of argv
    set kindText to item 2 of argv
    set startDir to item 3 of argv
    if kindText is "folder" then
        if startDir is "" then
            return POSIX path of (choose folder with prompt promptText)
        end if
        return POSIX path of (choose folder with prompt promptText default location (POSIX file startDir as alias))
    end if
    if startDir is "" then
        return POSIX path of (choose file with prompt promptText)
    end if
    return POSIX path of (choose file with prompt promptText default location (POSIX file startDir as alias))
end run"""


def windows_filter(filters):
    parts = []
    for label, exts in filters:
        pattern = ";".join(f"*.{e}" for e in exts)
        parts += [f"{label} ({pattern})", pattern]
    return "|".join(parts + ["All files (*.*)", "*.*"])


def build_candidates(kind, initial, title, filters, platform=None, which=shutil.which):
    """Every (argv, extra environment) that can show the dialog here, best first, ending with Tk. Each prints
    the chosen path. Pure, so it can be tested."""
    platform = platform or sys.platform
    folder, name = start_location(kind, initial)
    filters = clean_filters(filters)
    title = str(title or ("Choose a folder" if kind == "folder" else "Choose a file"))[:120]
    found = []
    if platform.startswith("win"):
        env = {"RAY_BROWSE_KIND": kind, "RAY_BROWSE_TITLE": title, "RAY_BROWSE_DIR": folder,
               "RAY_BROWSE_NAME": name, "RAY_BROWSE_FILTER": windows_filter(filters)}
        # pwsh (PowerShell 7) shows the modern folder dialog; Windows PowerShell shows the older tree.
        for shell in dict.fromkeys(s for s in (which("pwsh"), which("powershell")) if s):
            found.append(([shell, "-NoProfile", "-NonInteractive", "-STA", "-ExecutionPolicy", "Bypass", "-Command", _POWERSHELL], env))
    elif platform == "darwin":
        if which("osascript"):
            found.append((["osascript", "-e", _APPLESCRIPT, title, kind, folder], {}))
    else:
        if which("zenity"):
            argv = ["zenity", "--file-selection", "--title", title]
            if kind == "folder":
                argv.append("--directory")
            if folder:
                argv += ["--filename", os.path.join(folder, name) if name else folder.rstrip("/") + "/"]
            for label, exts in filters:
                argv.append(f"--file-filter={label} | " + " ".join(f"*.{e}" for e in exts))
            found.append((argv, {}))
        if which("kdialog"):
            start = os.path.join(folder, name) if folder else os.path.expanduser("~")
            if kind == "folder":
                found.append((["kdialog", "--title", title, "--getexistingdirectory", start], {}))
            else:
                pattern = "|".join(" ".join(f"*.{e}" for e in exts) + f"|{label}" for label, exts in filters) if filters else "*"
                found.append((["kdialog", "--title", title, "--getopenfilename", start, pattern], {}))
    found.append(([sys.executable, "-c", _TK, kind, folder, name, title, json.dumps(filters)], {}))
    return found


def build_command(kind, initial, title, filters, platform=None, which=shutil.which):
    """The preferred dialog command alone."""
    return build_candidates(kind, initial, title, filters, platform, which)[0]


def run_command(argv, extra_env, timeout=TIMEOUT_SECONDS):
    """Run the dialog. Returns the chosen path, or None when the user closed it."""
    env = dict(os.environ)
    env.update(extra_env)
    kwargs = {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)} if os.name == "nt" else {}
    try:
        done = subprocess.run(argv, capture_output=True, timeout=timeout, env=env, stdin=subprocess.DEVNULL, **kwargs)
    except OSError as error:
        raise BrowseUnavailable(f"The file dialog could not be started ({error}).", retry=True) from error
    except subprocess.TimeoutExpired as error:
        raise BrowseUnavailable("The file dialog was left open for too long and was closed.") from error
    out = done.stdout.decode("utf-8-sig", errors="replace").strip("\r\n")
    err = done.stderr.decode("utf-8", errors="replace").strip()
    if done.returncode == 0:
        return out or None
    # zenity, kdialog and osascript report "cancelled" as exit 1; osascript also says error -128.
    if done.returncode == 1 and (not err or "-128" in err or "cancel" in err.lower()):
        return None
    if done.returncode == 3 and argv and argv[0] == sys.executable:
        raise BrowseUnavailable("No file dialog is available here. Type the path instead.")
    raise BrowseUnavailable((err.splitlines() or ["The file dialog failed."])[-1][:200], retry=True)


def pick(kind, initial="", title="", filters=None):
    if kind not in KINDS:
        raise ValueError("kind must be 'folder' or 'file'.")
    if not _busy.acquire(blocking=False):
        raise BrowseBusy("A file dialog is already open.")
    try:
        last = None
        for argv, extra_env in build_candidates(kind, initial, title, filters):
            try:
                return run_command(argv, extra_env)
            except BrowseUnavailable as error:
                last = error
                if not error.retry:
                    raise
        raise last or BrowseUnavailable("No file dialog is available here. Type the path instead.")
    finally:
        _busy.release()


def is_local(remote):
    return str(remote or "") in ("127.0.0.1", "::1", "::ffff:127.0.0.1", "localhost")


try:
    from aiohttp import web
    from server import PromptServer
except ImportError:
    PromptServer = None

if PromptServer is not None:
    import asyncio

    @PromptServer.instance.routes.post("/ray/browse")
    async def browse(request):
        if not is_local(request.remote):
            return web.json_response({"ok": False, "error": "Browse only works when ComfyUI runs on this computer. Type the path instead."}, status=403)
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
