import importlib.util
import json
import sys
import threading
from unittest.mock import patch
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("browse_routes", Path(__file__).resolve().parents[1] / "browse_routes.py")
br = importlib.util.module_from_spec(spec)
with patch.dict(sys.modules, {"server": None}):
    spec.loader.exec_module(br)


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


# ---- the dialog command --------------------------------------------------------------------------------

def test_the_dialog_is_python_tk_with_everything_passed_as_arguments(tmp_path):
    hostile = '"); import os; os.system("calc"); ("'
    argv = br.build_command("file", str(tmp_path), hostile, [["Images", ["png"]]])
    assert argv[:2] == [sys.executable, "-c"] and argv[2] == br._TK
    assert argv[3:] == ["file", str(tmp_path), "", hostile, json.dumps([["Images", ["png"]]])]
    assert hostile not in br._TK


def test_default_titles_and_a_long_title_is_cut():
    assert br.build_command("folder", "", "", None)[6] == "Choose a folder"
    assert br.build_command("file", "", None, None)[6] == "Choose a file"
    assert len(br.build_command("file", "", "x" * 500, None)[6]) == 120


def test_the_tk_script_compiles_and_asks_for_a_folder_or_a_file():
    compile(br._TK, "<tk dialog>", "exec")
    assert "askdirectory" in br._TK and "askopenfilename" in br._TK and "-topmost" in br._TK


# ---- running it ----------------------------------------------------------------------------------------

def run(code, **kwargs):
    return br.run_command([sys.executable, "-c", code], **kwargs)


def test_a_chosen_path_comes_back_with_the_systems_separators():
    assert run("print('C:/pictures/shots')") == str(Path("C:/pictures/shots"))


def test_non_ascii_paths_and_a_byte_order_mark_survive():
    picked = run("import sys; sys.stdout.buffer.write('\\ufeffD:/Bilder/日本語/été'.encode('utf-8'))")
    assert picked == str(Path("D:/Bilder/日本語/été"))


def test_closing_the_dialog_is_not_an_error():
    assert run("pass") is None


def test_a_failing_dialog_reports_its_last_error_line():
    with pytest.raises(br.BrowseUnavailable, match="no display"):
        run("import sys; sys.stderr.write('noise\\nno display'); sys.exit(2)")


def test_a_missing_tk_gives_a_helpful_message():
    with pytest.raises(br.BrowseUnavailable, match="Type the path"):
        run("import sys; sys.exit(3)")


def test_a_missing_program_or_a_timeout_is_reported():
    with pytest.raises(br.BrowseUnavailable, match="could not be started"):
        br.run_command(["definitely-not-a-real-program-xyz"])
    with pytest.raises(br.BrowseUnavailable, match="too long"):
        run("import time; time.sleep(5)", timeout=0.3)


# ---- pick ----------------------------------------------------------------------------------------------

def test_pick_checks_the_kind_and_passes_everything_through(monkeypatch):
    seen = {}
    monkeypatch.setattr(br, "run_command", lambda argv: seen.setdefault("argv", argv) and "C:/chosen")
    assert br.pick("file", "", "Title", [["Images", ["png"]]]) == "C:/chosen"
    assert seen["argv"][3] == "file" and seen["argv"][6] == "Title"
    for bad in ("exe", "", None, "Folder"):
        with pytest.raises(ValueError):
            br.pick(bad)


def test_only_one_dialog_at_a_time(monkeypatch):
    started, release = threading.Event(), threading.Event()

    def slow(argv):
        started.set()
        release.wait(5)
        return "C:/a"

    monkeypatch.setattr(br, "run_command", slow)
    first = threading.Thread(target=lambda: br.pick("folder"))
    first.start()
    assert started.wait(5)
    with pytest.raises(br.BrowseBusy):
        br.pick("folder")
    release.set()
    first.join(5)
    assert br.pick("folder") == "C:/a"   # the lock is released afterwards


def test_the_lock_is_released_when_the_dialog_fails(monkeypatch):
    monkeypatch.setattr(br, "run_command", lambda argv: (_ for _ in ()).throw(br.BrowseUnavailable("nope")))
    with pytest.raises(br.BrowseUnavailable):
        br.pick("folder")
    monkeypatch.setattr(br, "run_command", lambda argv: "C:/ok")
    assert br.pick("folder") == "C:/ok"


def test_only_this_computer_may_open_a_dialog():
    for remote in ("127.0.0.1", "::1", "::ffff:127.0.0.1", "localhost"):
        assert br.is_local(remote)
    for remote in ("192.168.1.20", "10.0.0.5", "8.8.8.8", "", None, "127.0.0.2.evil.example"):
        assert not br.is_local(remote)
