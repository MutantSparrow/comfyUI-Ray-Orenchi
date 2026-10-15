import importlib.util
import sys
import threading
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("browse_routes", Path(__file__).resolve().parents[1] / "browse_routes.py")
br = importlib.util.module_from_spec(spec)
spec.loader.exec_module(br)


def shell_only(*present):
    return lambda name: f"/bin/{name}" if name in present else None


# ---- what the page may ask for -------------------------------------------------------------------------

def test_filters_keep_only_plain_extensions():
    cleaned = br.clean_filters([["Images", [".PNG", "jpg", "x;rm", "*", "a b", 7]], ["Bad", ["$$"]], "oops", ["Pipe|Name", ["txt"]]])
    assert cleaned == [("Images", ["png", "jpg"]), ("Pipe Name", ["txt"])]
    assert br.clean_filters(None) == [] and br.clean_filters("png") == []
    assert len(br.clean_filters([[f"F{i}", ["a"]] for i in range(30)])) == br.MAX_FILTERS


def test_start_location_uses_the_nearest_folder_that_exists(tmp_path):
    inner = tmp_path / "a" / "b"
    inner.mkdir(parents=True)
    assert br.start_location("folder", str(inner)) == (str(inner), "")
    assert br.start_location("folder", str(inner / "missing" / "deeper")) == (str(inner), "")
    assert br.start_location("folder", f'"{inner}"') == (str(inner), "")
    picture = inner / "x.png"
    picture.write_bytes(b"x")
    assert br.start_location("file", str(picture)) == (str(inner), "x.png")
    assert br.start_location("folder", str(picture)) == (str(inner), "")


def test_start_location_ignores_relative_blank_and_unusable_paths():
    for value in ("", "   ", None, "relative/path", "..", "~"):
        assert br.start_location("folder", value) == ("", "")


# ---- the command that is run ---------------------------------------------------------------------------

def test_windows_uses_powershell_and_passes_values_only_in_the_environment(tmp_path):
    hostile = '"; Remove-Item -Recurse C:\\ ; "'
    argv, env = br.build_command("folder", str(tmp_path), hostile, [["Images", ["png"]]], platform="win32", which=shell_only("pwsh", "powershell"))
    assert argv[0] == "/bin/pwsh" and "-STA" in argv and "-NonInteractive" in argv
    assert hostile not in " ".join(argv)
    assert env["RAY_BROWSE_KIND"] == "folder" and env["RAY_BROWSE_DIR"] == str(tmp_path) and env["RAY_BROWSE_TITLE"] == hostile
    assert env["RAY_BROWSE_FILTER"].startswith("Images (*.png)|*.png|") and env["RAY_BROWSE_FILTER"].endswith("All files (*.*)|*.*")


def test_windows_prefers_the_modern_pwsh_and_falls_back_to_windows_powershell():
    assert br.build_command("file", "", "", None, platform="win32", which=shell_only("pwsh", "powershell"))[0][0] == "/bin/pwsh"
    assert br.build_command("file", "", "", None, platform="win32", which=shell_only("powershell"))[0][0] == "/bin/powershell"


def test_every_available_dialog_is_listed_best_first_ending_with_tk():
    found = br.build_candidates("folder", "", "", None, platform="win32", which=shell_only("pwsh", "powershell"))
    assert [Path(argv[0]).name for argv, _ in found] == ["pwsh", "powershell", Path(sys.executable).name]
    found = br.build_candidates("folder", "", "", None, platform="win32", which=lambda name: "/bin/same")
    assert len(found) == 2 and found[0][0][0] == "/bin/same"           # the same program is not listed twice
    found = br.build_candidates("file", "", "", None, platform="linux", which=shell_only("zenity", "kdialog"))
    assert [argv[0] for argv, _ in found][:2] == ["zenity", "kdialog"] and found[-1][0][0] == sys.executable
    assert br.build_command("folder", "", "", None, platform="linux", which=shell_only("kdialog")) == br.build_candidates("folder", "", "", None, platform="linux", which=shell_only("kdialog"))[0]


def test_without_a_native_option_the_tk_dialog_is_the_last_resort():
    for platform in ("win32", "darwin", "linux"):
        argv, env = br.build_command("folder", "", "Pick", [["Images", ["png"]]], platform=platform, which=shell_only())
        assert argv[0] == sys.executable and argv[1] == "-c" and argv[3] == "folder" and argv[5] == "" and env == {}
        assert '"Images"' in argv[-1]


def test_macos_uses_osascript_with_arguments_not_string_building(tmp_path):
    argv, env = br.build_command("file", str(tmp_path), 'Say "hi"', None, platform="darwin", which=shell_only("osascript"))
    assert argv[0] == "osascript" and argv[-3:] == ['Say "hi"', "file", str(tmp_path)] and env == {}
    assert 'Say "hi"' not in argv[2]


def test_linux_prefers_zenity_then_kdialog(tmp_path):
    argv, _ = br.build_command("folder", str(tmp_path), "Pick", None, platform="linux", which=shell_only("zenity", "kdialog"))
    assert argv[0] == "zenity" and "--directory" in argv and argv[argv.index("--filename") + 1] == str(tmp_path).rstrip("/") + "/"
    argv, _ = br.build_command("file", "", "Pick", [["Images", ["png", "jpg"]]], platform="linux", which=shell_only("zenity"))
    assert "--directory" not in argv and "--file-filter=Images | *.png *.jpg" in argv
    argv, _ = br.build_command("folder", str(tmp_path), "Pick", None, platform="linux", which=shell_only("kdialog"))
    assert argv[0] == "kdialog" and "--getexistingdirectory" in argv
    argv, _ = br.build_command("file", "", "Pick", [["Images", ["png"]]], platform="linux", which=shell_only("kdialog"))
    assert "--getopenfilename" in argv and "*.png|Images" in argv


def test_default_titles_and_a_long_title_is_cut():
    assert br.build_command("folder", "", "", None, platform="linux", which=shell_only("zenity"))[0][3] == "Choose a folder"
    assert br.build_command("file", "", None, None, platform="linux", which=shell_only("zenity"))[0][3] == "Choose a file"
    assert len(br.build_command("file", "", "x" * 500, None, platform="linux", which=shell_only("zenity"))[0][3]) == 120


def test_the_windows_script_is_valid_and_reads_its_inputs_from_the_environment():
    script = br._POWERSHELL
    for name in ("RAY_BROWSE_KIND", "RAY_BROWSE_TITLE", "RAY_BROWSE_DIR", "RAY_BROWSE_NAME", "RAY_BROWSE_FILTER"):
        assert f"$env:{name}" in script
    assert "FolderBrowserDialog" in script and "OpenFileDialog" in script and "TopMost" in script
    assert script.count("{") == script.count("}") and script.count("(") == script.count(")")


# ---- running it ----------------------------------------------------------------------------------------

def run(code, **kwargs):
    return br.run_command([sys.executable, "-c", code], {}, **kwargs)


def test_a_chosen_path_comes_back_without_the_trailing_newline():
    assert run("print('C:/pictures')") == "C:/pictures"


def test_non_ascii_paths_and_a_byte_order_mark_survive():
    assert run("import sys; sys.stdout.buffer.write('\\ufeffD:/Bilder/日本語/été'.encode('utf-8'))") == "D:/Bilder/日本語/été"


def test_closing_the_dialog_is_not_an_error():
    assert run("pass") is None
    assert run("import sys; sys.exit(1)") is None
    assert run("import sys; sys.stderr.write('execution error: User canceled. (-128)'); sys.exit(1)") is None
    assert run("import sys; sys.stderr.write('cancelled'); sys.exit(1)") is None


def test_a_failing_dialog_reports_its_last_error_line():
    with pytest.raises(br.BrowseUnavailable, match="no display"):
        run("import sys; sys.stderr.write('noise\\nno display'); sys.exit(2)")
    with pytest.raises(br.BrowseUnavailable):
        run("import sys; sys.exit(5)")


def test_a_missing_program_or_a_timeout_is_reported():
    with pytest.raises(br.BrowseUnavailable, match="could not be started") as caught:
        br.run_command(["definitely-not-a-real-program-xyz"], {})
    assert caught.value.retry is True
    with pytest.raises(br.BrowseUnavailable, match="too long"):
        run("import time; time.sleep(5)", timeout=0.3)


def test_tk_missing_gives_a_helpful_message():
    with pytest.raises(br.BrowseUnavailable, match="Type the path"):
        br.run_command([sys.executable, "-c", "import sys; sys.exit(3)"], {})


def test_the_environment_reaches_the_dialog_process():
    assert br.run_command([sys.executable, "-c", "import os; print(os.environ['RAY_X'])"], {"RAY_X": "hello"}) == "hello"


# ---- pick ----------------------------------------------------------------------------------------------

def test_pick_checks_the_kind_and_passes_everything_through(monkeypatch):
    seen = {}
    monkeypatch.setattr(br, "build_candidates", lambda kind, initial, title, filters: [(seen.update(kind=kind, initial=initial, title=title, filters=filters) or ["x"], {})])
    monkeypatch.setattr(br, "run_command", lambda argv, env: "C:/chosen")
    assert br.pick("file", "C:/start", "Title", [["Images", ["png"]]]) == "C:/chosen"
    assert seen == {"kind": "file", "initial": "C:/start", "title": "Title", "filters": [["Images", ["png"]]]}
    for bad in ("exe", "", None, "Folder"):
        with pytest.raises(ValueError):
            br.pick(bad)


def test_a_dialog_that_cannot_start_falls_back_to_the_next_one(monkeypatch):
    tried = []

    def attempt(argv, env):
        tried.append(argv[0])
        if argv[0] == "/bin/pwsh":
            raise br.BrowseUnavailable("access denied", retry=True)
        return "C:/from-" + Path(argv[0]).name

    monkeypatch.setattr(br, "run_command", attempt)
    monkeypatch.setattr(br, "build_candidates", lambda *a: [(["/bin/pwsh"], {}), (["/bin/powershell"], {}), ([sys.executable], {})])
    assert br.pick("folder") == "C:/from-powershell"
    assert tried == ["/bin/pwsh", "/bin/powershell"]


def test_closing_the_dialog_or_a_timeout_does_not_try_the_next_one(monkeypatch):
    tried = []
    monkeypatch.setattr(br, "build_candidates", lambda *a: [(["/bin/a"], {}), (["/bin/b"], {})])
    monkeypatch.setattr(br, "run_command", lambda argv, env: tried.append(argv[0]))
    assert br.pick("file") is None and tried == ["/bin/a"]
    tried.clear()

    def timed_out(argv, env):
        tried.append(argv[0])
        raise br.BrowseUnavailable("left open too long")

    monkeypatch.setattr(br, "run_command", timed_out)
    with pytest.raises(br.BrowseUnavailable, match="too long"):
        br.pick("file")
    assert tried == ["/bin/a"]


def test_when_every_dialog_fails_the_last_error_is_reported(monkeypatch):
    monkeypatch.setattr(br, "build_candidates", lambda *a: [(["/bin/a"], {}), (["/bin/b"], {})])
    monkeypatch.setattr(br, "run_command", lambda argv, env: (_ for _ in ()).throw(br.BrowseUnavailable("failed " + argv[0], retry=True)))
    with pytest.raises(br.BrowseUnavailable, match="failed /bin/b"):
        br.pick("folder")


def test_only_one_dialog_at_a_time(monkeypatch):
    started, release = threading.Event(), threading.Event()

    def slow(argv, env):
        started.set()
        release.wait(5)
        return "C:/a"

    monkeypatch.setattr(br, "run_command", slow)
    monkeypatch.setattr(br, "build_candidates", lambda *a: [(["x"], {})])
    first = threading.Thread(target=lambda: br.pick("folder"))
    first.start()
    assert started.wait(5)
    with pytest.raises(br.BrowseBusy):
        br.pick("folder")
    release.set()
    first.join(5)
    assert br.pick("folder") == "C:/a"   # the lock is released afterwards


def test_the_lock_is_released_when_the_dialog_fails(monkeypatch):
    monkeypatch.setattr(br, "build_candidates", lambda *a: [(["x"], {})])
    monkeypatch.setattr(br, "run_command", lambda argv, env: (_ for _ in ()).throw(br.BrowseUnavailable("nope")))
    with pytest.raises(br.BrowseUnavailable):
        br.pick("folder")
    monkeypatch.setattr(br, "run_command", lambda argv, env: "C:/ok")
    assert br.pick("folder") == "C:/ok"


def test_only_this_computer_may_open_a_dialog():
    for remote in ("127.0.0.1", "::1", "::ffff:127.0.0.1", "localhost"):
        assert br.is_local(remote)
    for remote in ("192.168.1.20", "10.0.0.5", "8.8.8.8", "", None, "127.0.0.2.evil.example"):
        assert not br.is_local(remote)
