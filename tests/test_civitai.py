"""Tests for ray_civitai. Network mocked. Run with: pytest tests/test_civitai.py"""

import os
from collections import deque
from unittest.mock import patch, MagicMock

import pytest
import torch

import ray_civitai as rc
from ray_civitai import RayCivitAI


@pytest.fixture(autouse=True)
def reset_globals():
    rc._PAGE_CACHE.clear()
    rc._RECENT_BY_NODE.clear()
    yield
    rc._PAGE_CACHE.clear()
    rc._RECENT_BY_NODE.clear()


def _mock_response(payload=None, content=None, status=200):
    resp = MagicMock()
    resp.status_code = status
    resp.json = MagicMock(return_value=payload or {})
    resp.content = content if content is not None else b""
    resp.raise_for_status = MagicMock()
    return resp


def _item(id_, prompt="A red fox in snow.", url=None, nsfw_level="None", base="SDXL 1.0"):
    return {
        "id": id_,
        "url": url or f"https://image.civitai.com/p/{id_}.jpg",
        "width": 832,
        "height": 1216,
        "nsfwLevel": nsfw_level,
        "baseModel": base,
        "meta": {"prompt": prompt} if prompt else None,
        "username": "tester",
    }


def _page(items, next_cursor=None):
    return {"items": items, "metadata": {"nextCursor": next_cursor}}


# --- mode → browsingLevel mapping ---------------------------------------


def test_mode_blue_maps_to_pg_plus_pg13_bitmask():
    assert rc._mode_to_browsing_level(rc.MODE_BLUE) == 1 | 2 == 3


def test_mode_red_maps_to_full_bitmask():
    assert rc._mode_to_browsing_level(rc.MODE_RED) == 1 | 2 | 4 | 8 | 16 == 31


# --- query builder -------------------------------------------------------


def test_query_includes_required_params():
    q = rc._build_query(3, "Week", "Random", "Any", None, 50)
    assert "limit=50" in q
    assert "browsingLevel=3" in q
    assert "period=Week" in q
    assert "sort=Random" in q
    assert "withMeta=true" in q
    assert "baseModels" not in q
    assert "nsfw=" not in q
    assert "username" not in q


def test_query_adds_base_model_when_not_any():
    q = rc._build_query(31, "Week", "Random", "Pony", "abc", 100)
    assert "browsingLevel=31" in q
    assert "baseModels=Pony" in q
    assert "cursor=abc" in q


def test_query_adds_username_when_set():
    q = rc._build_query(1, "Week", "Random", "Any", None, 100, username="VISITOR01")
    assert "username=VISITOR01" in q


def test_query_omits_username_when_blank():
    q = rc._build_query(1, "Week", "Random", "Any", None, 100, username="")
    assert "username=" not in q


# --- prompt filtering ----------------------------------------------------


def test_filter_keeps_only_items_with_prompts():
    items = [
        _item(1, prompt="good"),
        _item(2, prompt=""),
        _item(3, prompt=None),
        _item(4, prompt="another good"),
    ]
    kept = rc._filter_with_prompt(items)
    assert [k["id"] for k in kept] == [1, 4]


def test_filter_drops_items_with_missing_url():
    items = [
        {"id": 1, "url": "", "meta": {"prompt": "x"}},
        {"id": 2, "url": "http://x/y.jpg", "meta": {"prompt": "y"}},
    ]
    kept = rc._filter_with_prompt(items)
    assert [k["id"] for k in kept] == [2]


# --- comfy-workflow prompt salvage --------------------------------------


def _comfy_meta_with_text(text: str, class_type: str = "CLIPTextEncode") -> dict:
    """Build a meta dict whose comfy field embeds a workflow with a prompt."""
    workflow = {
        "prompt": {
            "1": {"class_type": class_type, "inputs": {"text": text}},
        }
    }
    import json as _j
    return {"prompt": "", "comfy": _j.dumps(workflow)}


def test_extract_prompt_falls_back_to_comfy_workflow():
    item = {
        "id": 1,
        "url": "http://x/1.jpg",
        "meta": _comfy_meta_with_text("a long detailed prompt about a fox"),
    }
    assert rc._extract_prompt(item) == "a long detailed prompt about a fox"


def test_extract_prompt_prefers_clip_text_encode_over_text_multiline():
    workflow = {
        "prompt": {
            "1": {"class_type": "Text Multiline", "inputs": {"text": "noise xxxxxxxxxxxxxx"}},
            "2": {"class_type": "CLIPTextEncode",
                  "inputs": {"text": "real positive prompt"}},
        }
    }
    import json as _j
    item = {"id": 1, "url": "http://x/1.jpg",
            "meta": {"prompt": "", "comfy": _j.dumps(workflow)}}
    assert rc._extract_prompt(item) == "real positive prompt"


def test_extract_prompt_meta_prompt_still_wins_when_present():
    workflow = {
        "prompt": {
            "1": {"class_type": "CLIPTextEncode", "inputs": {"text": "workflow text"}},
        }
    }
    import json as _j
    item = {"id": 1, "url": "http://x/1.jpg",
            "meta": {"prompt": "primary direct prompt",
                     "comfy": _j.dumps(workflow)}}
    assert rc._extract_prompt(item) == "primary direct prompt"


def test_extract_prompt_returns_empty_when_no_signal():
    item = {"id": 1, "url": "http://x/1.jpg", "meta": {"prompt": "", "comfy": ""}}
    assert rc._extract_prompt(item) == ""


def test_extract_prompt_handles_unparseable_comfy_blob():
    item = {"id": 1, "url": "http://x/1.jpg",
            "meta": {"prompt": "", "comfy": "{not json"}}
    assert rc._extract_prompt(item) == ""


def test_filter_keeps_items_via_comfy_workflow_when_meta_prompt_empty():
    items = [
        {"id": 9, "url": "http://x/9.jpg",
         "meta": _comfy_meta_with_text("salvaged from workflow")},
    ]
    kept = rc._filter_with_prompt(items)
    assert len(kept) == 1
    assert kept[0]["prompt"] == "salvaged from workflow"


# --- pagination & caching ------------------------------------------------


def test_load_pool_pages_until_no_cursor():
    pages = [
        (_page([_item(1), _item(2)], next_cursor="c1"), "c1"),
        (_page([_item(3, prompt="")], next_cursor="c2"), "c2"),
        (_page([_item(4)], next_cursor=None), None),
    ]
    call_idx = {"i": 0}

    def fake_fetch(browsing_level, period, sort, base_model, cursor, timeout, username=""):
        i = call_idx["i"]
        page, next_c = pages[i]
        call_idx["i"] += 1
        return page["items"], next_c

    with patch.object(rc, "_fetch_page", side_effect=fake_fetch):
        pool = rc._load_pool(rc.MODE_BLUE, "Week", "Random", "Any", timeout=10)
    ids = sorted(p["id"] for p in pool)
    assert ids == [1, 2, 4]


def test_load_pool_uses_red_bitmask_for_red_mode():
    """Red mode must pass browsingLevel=31 in a single call path (no nsfw fallback)."""
    seen = []

    def fake_fetch(browsing_level, period, sort, base_model, cursor, timeout, username=""):
        seen.append(browsing_level)
        return ([_item(1)], None)

    with patch.object(rc, "_fetch_page", side_effect=fake_fetch):
        rc._load_pool(rc.MODE_RED, "Week", "Random", "Any", timeout=10)
    assert seen == [rc.BROWSING_LEVEL_RED]


def test_load_pool_raises_when_empty():
    with patch.object(rc, "_fetch_page", return_value=([], None)):
        with pytest.raises(RuntimeError, match="no images with prompts"):
            rc._load_pool(rc.MODE_BLUE, "Week", "Random", "Any", timeout=10)


def test_load_pool_cached_by_key():
    fetched = []

    def fake_fetch(browsing_level, period, sort, base_model, cursor, timeout, username=""):
        fetched.append((browsing_level, period, sort, base_model))
        return ([_item(1)], None)

    with patch.object(rc, "_fetch_page", side_effect=fake_fetch):
        rc._load_pool(rc.MODE_BLUE, "Week", "Random", "Any", timeout=10)
        rc._load_pool(rc.MODE_BLUE, "Week", "Random", "Any", timeout=10)
    assert len(fetched) == 1


def test_load_pool_username_in_cache_key():
    """Different usernames must NOT collide in the cache."""
    fetched = []

    def fake_fetch(browsing_level, period, sort, base_model, cursor, timeout, username=""):
        fetched.append(username)
        return ([_item(1)], None)

    with patch.object(rc, "_fetch_page", side_effect=fake_fetch):
        rc._load_pool(rc.MODE_BLUE, "Week", "Random", "Any", timeout=10, username="alice")
        rc._load_pool(rc.MODE_BLUE, "Week", "Random", "Any", timeout=10, username="bob")
        rc._load_pool(rc.MODE_BLUE, "Week", "Random", "Any", timeout=10, username="alice")
    assert fetched == ["alice", "bob"]


def test_load_pool_passes_username_through():
    seen = []

    def fake_fetch(browsing_level, period, sort, base_model, cursor, timeout, username=""):
        seen.append(username)
        return ([_item(1)], None)

    with patch.object(rc, "_fetch_page", side_effect=fake_fetch):
        rc._load_pool(rc.MODE_BLUE, "AllTime", "Random", "Any", timeout=10, username="VISITOR01")
    assert seen == ["VISITOR01"]


def test_load_pool_forces_alltime_when_username_set():
    """Per-user feeds rarely fit Week/Day; we override to AllTime so a small
    archive doesn't come back as 0 hits."""
    seen_periods = []

    def fake_fetch(browsing_level, period, sort, base_model, cursor, timeout, username=""):
        seen_periods.append(period)
        return ([_item(1)], None)

    with patch.object(rc, "_fetch_page", side_effect=fake_fetch):
        rc._load_pool(rc.MODE_BLUE, "Week", "Random", "Any", timeout=10, username="VISITOR01")
    assert seen_periods == ["AllTime"]


def test_load_pool_keeps_period_when_no_username():
    seen_periods = []

    def fake_fetch(browsing_level, period, sort, base_model, cursor, timeout, username=""):
        seen_periods.append(period)
        return ([_item(1)], None)

    with patch.object(rc, "_fetch_page", side_effect=fake_fetch):
        rc._load_pool(rc.MODE_BLUE, "Week", "Random", "Any", timeout=10, username="")
    assert seen_periods == ["Week"]


# --- selection -----------------------------------------------------------


def test_select_skips_recent():
    import random as _r
    pool = [{"id": i, "url": "x", "prompt": "p"} for i in range(5)]
    recent = deque([0], maxlen=20)
    rng = _r.Random(1)
    picked = rc._select_item(pool, recent, rng, deterministic=True)
    assert picked["id"] != 0


def test_select_falls_back_when_all_recent():
    import random as _r
    pool = [{"id": i, "url": "x", "prompt": "p"} for i in range(3)]
    recent = deque([0, 1, 2], maxlen=20)
    rng = _r.Random(1)
    picked = rc._select_item(pool, recent, rng, deterministic=True)
    assert picked["id"] in {0, 1, 2}


# --- full process() integration -----------------------------------------


def test_process_returns_three_outputs():
    pool_pages = [([_item(7, prompt="A rocket\nlaunching")], None)]
    call_idx = {"i": 0}

    def fake_fetch(browsing_level, period, sort, base_model, cursor, timeout, username=""):
        i = call_idx["i"]
        items, nxt = pool_pages[i]
        call_idx["i"] += 1
        return items, nxt

    node = RayCivitAI()
    with patch.object(rc, "_fetch_page", side_effect=fake_fetch), \
         patch.object(rc, "_fetch_image_tensor", return_value=torch.zeros((1, 1, 1, 3))):
        out = node.process(
            seed=42,
            mode=rc.MODE_BLUE,
            base_model=rc.BASE_MODELS_DEFAULT,
            period="Week",
            sort="Random",
            username="",
            timeout=10,
            node_id="t1",
        )
    single, multi, image = out
    assert "rocket" in single
    assert "\n" in multi
    assert "\n" not in single
    assert image.shape == (1, 1, 1, 3)


def test_process_deterministic_same_seed_same_pick():
    rc._PAGE_CACHE[(rc.MODE_BLUE, "Week", "Random", "Any", "")] = [
        {"id": i, "url": f"http://x/{i}.jpg", "prompt": f"prompt {i}",
         "nsfwLevel": "None", "baseModel": "SDXL 1.0", "username": "u"}
        for i in range(5)
    ]
    node = RayCivitAI()
    with patch.object(rc, "_fetch_image_tensor", return_value=torch.zeros((1, 1, 1, 3))):
        out1 = node.process(seed=99, mode=rc.MODE_BLUE,
                            base_model=rc.BASE_MODELS_DEFAULT, period="Week",
                            sort="Random", username="", timeout=10,
                            node_id="A")
        out2 = node.process(seed=99, mode=rc.MODE_BLUE,
                            base_model=rc.BASE_MODELS_DEFAULT, period="Week",
                            sort="Random", username="", timeout=10,
                            node_id="B")
    assert out1[0] == out2[0]


def test_process_passes_username_to_pool():
    captured = {}

    def fake_load_pool(**kwargs):
        captured.update(kwargs)
        return [{"id": 1, "url": "http://x/1.jpg", "prompt": "p", "nsfwLevel": "None",
                 "baseModel": "SDXL 1.0", "username": "VISITOR01"}]

    node = RayCivitAI()
    with patch.object(rc, "_load_pool", side_effect=fake_load_pool), \
         patch.object(rc, "_fetch_image_tensor", return_value=torch.zeros((1, 1, 1, 3))):
        node.process(seed=1, mode=rc.MODE_BLUE,
                     base_model=rc.BASE_MODELS_DEFAULT, period="Week",
                     sort="Random", username="  VISITOR01  ", timeout=10,
                     node_id="t")
    assert captured.get("username") == "VISITOR01"


# --- token via local secret file ----------------------------------------


@pytest.fixture
def tmp_token_file(tmp_path, monkeypatch):
    """Redirect _TOKEN_FILE to a tmp path for isolated test files."""
    p = tmp_path / "civitai.secret"
    monkeypatch.setattr(rc, "_TOKEN_FILE", p)
    return p


def test_auth_header_present_when_secret_file_has_token(tmp_token_file):
    tmp_token_file.write_text("secret-token\n", encoding="utf-8")
    h = rc._headers()
    assert h.get("Authorization") == "Bearer secret-token"
    assert rc.has_token() is True


def test_auth_header_absent_when_secret_file_missing(tmp_token_file):
    assert not tmp_token_file.exists()
    h = rc._headers()
    assert "Authorization" not in h
    assert rc.has_token() is False


def test_auth_header_absent_when_secret_file_blank(tmp_token_file):
    tmp_token_file.write_text("   \n   ", encoding="utf-8")
    h = rc._headers()
    assert "Authorization" not in h
    assert rc.has_token() is False


def test_token_file_lives_in_pack_dir():
    """Default token path must live alongside ray_civitai.py."""
    import pathlib
    expected = pathlib.Path(rc.__file__).resolve().parent / "civitai.secret"
    assert rc._TOKEN_FILE == expected


def test_no_hardcoded_token_in_source():
    """Guard against accidental commit of a real-looking token."""
    import pathlib
    src = pathlib.Path(rc.__file__).read_text(encoding="utf-8")
    import re
    assert not re.search(r"[A-Fa-f0-9]{32}", src), "looks like a hex token in source"


def test_secret_file_not_tracked_by_git():
    """If a real civitai.secret exists in the repo, .gitignore must hide it."""
    import pathlib
    import subprocess
    pack_dir = pathlib.Path(rc.__file__).resolve().parent
    gitignore = pack_dir / ".gitignore"
    assert gitignore.exists(), ".gitignore missing"
    text = gitignore.read_text(encoding="utf-8")
    assert "civitai.secret" in text or "*.secret" in text, \
        "civitai.secret must be in .gitignore"


# --- clear_cache helper --------------------------------------------------


def test_clear_cache_drops_all():
    rc._PAGE_CACHE[("k",)] = [{"id": 1}]
    rc._RECENT_BY_NODE["n1"] = deque([1, 2], maxlen=20)
    rc.clear_cache()
    assert rc._PAGE_CACHE == {}
    assert rc._RECENT_BY_NODE == {}
