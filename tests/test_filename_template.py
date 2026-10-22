import datetime
import importlib.util
import json
import threading
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("filename_template", ROOT / "filename_template.py")
ft = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ft)

CASES = json.loads((Path(__file__).parent / "filename_cases.json").read_text(encoding="utf-8"))
C = CASES["context"]
NOW = datetime.datetime.fromisoformat(C["now"])


def context(**changes):
    ctx = {"now": NOW, "index": C["index"], "input": C["input"], "hash": C["hash"],
           "widgets": lambda node, name: C["widgets"].get(f"{node}.{name}")}
    ctx.update(changes)
    return ctx


# ---- shared with web/save_name.js ----------------------------------------------------------------------

@pytest.mark.parametrize("template,expected", CASES["render"], ids=[repr(t[0])[:36] for t in CASES["render"]])
def test_shared_render_cases(template, expected):
    assert ft.render(ft.parse(template), context(), C["counter"]) == expected


@pytest.mark.parametrize("template", CASES["errors"])
def test_shared_error_cases(template):
    with pytest.raises(ft.TemplateError):
        ft.parse(template)


def test_every_error_says_what_to_fix():
    with pytest.raises(ft.TemplateError, match=r"Unknown filename token \{nope\}.*\{date\}"):
        ft.parse("{nope}")
    with pytest.raises(ft.TemplateError, match="needs a number from 1 to 12"):
        ft.parse("{counter:0}")
    with pytest.raises(ft.TemplateError, match="only once"):
        ft.parse("{counter}_{counter}")
    with pytest.raises(ft.TemplateError, match="node id and a widget name"):
        ft.parse("{widget:12}")


# ---- details the shared table cannot express ---------------------------------------------------------------

def test_the_timestamp_is_seconds_since_1970():
    assert ft.render(ft.parse("{timestamp}"), context()) == str(int(NOW.timestamp()))


def test_a_random_hash_differs_between_files_and_has_the_requested_length():
    parts = ft.parse("{hash:10}")
    ctx = context(hash=None)
    names = {ft.render(parts, ctx) for _ in range(20)}
    assert len(names) == 20 and all(len(n) == 10 and int(n, 16) >= 0 for n in names)


def test_a_node_id_may_contain_a_colon_for_nodes_inside_groups():
    ctx = context(widgets=lambda node, name: {"12:5.seed": 9}.get(f"{node}.{name}"))
    assert ft.render(ft.parse("{widget:12:5.seed}"), ctx) == "9"


def test_a_widget_value_cannot_inject_a_token_or_a_path():
    ctx = context(widgets=lambda node, name: "{hash}/../../etc")
    stem = ft.render(ft.parse("{widget:1.x}"), ctx)
    assert stem == "hash_.._.._etc"
    assert "/" not in stem and "\\" not in stem and "{" not in stem and "}" not in stem


def test_the_rendered_stem_is_always_a_safe_filename():
    hostile = ['a/b', 'a\\b', 'a:b', 'a*b', 'a?b', 'a"b', 'a<b', 'a>b', 'a|b', 'a\x00b', 'a\x1fb', "CON", "aux.txt", "...", "  ", "tail. ", "x" * 500]
    for text in hostile:
        stem = ft.render(ft.parse(text), context())
        assert stem and len(stem) <= ft.MAX_STEM
        assert not any(ch in stem for ch in '<>:"/\\|?*') and not any(ord(ch) < 32 for ch in stem)
        assert stem == stem.strip() and not stem.endswith(".") and not stem.startswith(".")
        assert stem.split(".")[0].upper() not in ft.RESERVED


# ---- creating files ------------------------------------------------------------------------------------

def make(template, directory, **ctx):
    path, stream = ft.create_unique(directory, ft.parse(template), context(**ctx), ".png")
    with stream:
        stream.write(b"x")
    return path.name


def test_the_counter_continues_from_the_files_already_there(tmp_path):
    assert [make("Ray_{counter}", tmp_path) for _ in range(3)] == ["Ray_0001.png", "Ray_0002.png", "Ray_0003.png"]
    (tmp_path / "Ray_0020.png").write_bytes(b"")
    assert make("Ray_{counter}", tmp_path) == "Ray_0021.png"
    (tmp_path / "Ray_x_0999.png").write_bytes(b"")           # other names do not move it
    (tmp_path / "Ray_0005.jpg").write_bytes(b"")
    assert make("Ray_{counter}", tmp_path) == "Ray_0022.png"


def test_the_counter_is_counted_per_template_and_per_folder(tmp_path):
    other = tmp_path / "other"
    other.mkdir()
    assert make("A_{counter}", tmp_path) == "A_0001.png"
    assert make("B_{counter}", tmp_path) == "B_0001.png"
    assert make("A_{counter}", other) == "A_0001.png"
    assert make("{counter:2}-{date}", tmp_path) == "01-2026-10-16.png"
    assert make("{counter:2}-{date}", tmp_path) == "02-2026-10-16.png"


def test_a_counter_wider_than_its_padding_keeps_counting(tmp_path):
    (tmp_path / "n_99.png").write_bytes(b"")
    assert make("n_{counter:2}", tmp_path) == "n_100.png"


def test_without_a_counter_a_taken_name_gets_a_suffix_and_nothing_is_overwritten(tmp_path):
    assert [make("shot", tmp_path) for _ in range(3)] == ["shot.png", "shot-2.png", "shot-3.png"]
    assert (tmp_path / "shot.png").read_bytes() == b"x"


def test_the_suffix_also_rescues_a_fixed_hash(tmp_path):
    assert make("{hash}", tmp_path) == "a1b2c3d4.png"
    assert make("{hash}", tmp_path) == "a1b2c3d4-2.png"


def test_a_batch_gets_one_name_per_image_with_the_index_token(tmp_path):
    names = [make("img_{index:3}", tmp_path, index=i) for i in (1, 2, 3)]
    assert names == ["img_001.png", "img_002.png", "img_003.png"]
    assert [make("pair_{input}", tmp_path, input=i) for i in (1, 2)] == ["pair_1.png", "pair_2.png"]


def test_the_suffix_keeps_even_a_maximum_length_name_inside_the_limit():
    # Keep the directory short on Windows without LongPathsEnabled. This test
    # exercises the filename limit, independently of the OS full-path limit.
    with tempfile.TemporaryDirectory(prefix="ray-") as directory:
        first, second = make("x" * 400, Path(directory)), make("x" * 400, Path(directory))
    assert first != second and len(second) <= ft.MAX_STEM + len(".png")


def test_two_runs_at_once_never_claim_the_same_file(tmp_path):
    names, errors = [], []

    def worker():
        try:
            for _ in range(15):
                names.append(make("Ray_{counter}", tmp_path))
        except Exception as error:   # pragma: no cover - the assertion below reports it
            errors.append(error)

    threads = [threading.Thread(target=worker) for _ in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors and len(names) == 90 and len(set(names)) == 90
    assert len(list(tmp_path.iterdir())) == 90


def test_next_counter_on_a_missing_folder_starts_at_one(tmp_path):
    assert ft.next_counter(tmp_path / "nope", ft.parse("a_{counter}"), context(), ".png") == 1
