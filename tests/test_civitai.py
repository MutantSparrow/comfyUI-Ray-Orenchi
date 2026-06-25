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


def test_mode_blue_maps_to_pg_bitmask():
    assert rc._mode_to_browsing_level(rc.MODE_BLUE) == 1


def test_mode_red_maps_to_r_x_xxx_bitmask():
    assert rc._mode_to_browsing_level(rc.MODE_RED) == 4 | 8 | 16 == 28


# --- query builder -------------------------------------------------------


def test_query_includes_required_params():
    q = rc._build_query(1, "Week", "Random", "Any", None, 50)
    assert "limit=50" in q
    assert "browsingLevel=1" in q
    assert "period=Week" in q
    assert "sort=Random" in q
    assert "withMeta=true" in q
    assert "baseModels" not in q
    assert "nsfw=" not in q


def test_query_adds_base_model_when_not_any():
    q = rc._build_query(28, "Week", "Random", "Pony", "abc", 100)
    assert "browsingLevel=28" in q
    assert "baseModels=Pony" in q
    assert "cursor=abc" in q


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


# --- pagination & caching ------------------------------------------------


def test_load_pool_pages_until_no_cursor():
    pages = [
        (_page([_item(1), _item(2)], next_cursor="c1"), "c1"),
        (_page([_item(3, prompt="")], next_cursor="c2"), "c2"),
        (_page([_item(4)], next_cursor=None), None),
    ]
    call_idx = {"i": 0}

    def fake_fetch(browsing_level, period, sort, base_model, cursor, timeout):
        i = call_idx["i"]
        page, next_c = pages[i]
        call_idx["i"] += 1
        return page["items"], next_c

    with patch.object(rc, "_fetch_page", side_effect=fake_fetch):
        pool = rc._load_pool(rc.MODE_BLUE, "Week", "Random", "Any", timeout=10)
    ids = sorted(p["id"] for p in pool)
    assert ids == [1, 2, 4]


def test_load_pool_uses_red_bitmask_for_red_mode():
    """Red mode must pass browsingLevel=28 in a single call path (no nsfw fallback)."""
    seen = []

    def fake_fetch(browsing_level, period, sort, base_model, cursor, timeout):
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

    def fake_fetch(browsing_level, period, sort, base_model, cursor, timeout):
        fetched.append((browsing_level, period, sort, base_model))
        return ([_item(1)], None)

    with patch.object(rc, "_fetch_page", side_effect=fake_fetch):
        rc._load_pool(rc.MODE_BLUE, "Week", "Random", "Any", timeout=10)
        rc._load_pool(rc.MODE_BLUE, "Week", "Random", "Any", timeout=10)
    assert len(fetched) == 1


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

    def fake_fetch(browsing_level, period, sort, base_model, cursor, timeout):
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
            clear_cache=False,
            timeout=10,
            node_id="t1",
        )
    single, multi, image = out
    assert "rocket" in single
    assert "\n" in multi
    assert "\n" not in single
    assert image.shape == (1, 1, 1, 3)


def test_process_deterministic_same_seed_same_pick():
    rc._PAGE_CACHE[(rc.MODE_BLUE, "Week", "Random", "Any")] = [
        {"id": i, "url": f"http://x/{i}.jpg", "prompt": f"prompt {i}",
         "nsfwLevel": "None", "baseModel": "SDXL 1.0", "username": "u"}
        for i in range(5)
    ]
    node = RayCivitAI()
    with patch.object(rc, "_fetch_image_tensor", return_value=torch.zeros((1, 1, 1, 3))):
        out1 = node.process(seed=99, mode=rc.MODE_BLUE,
                            base_model=rc.BASE_MODELS_DEFAULT, period="Week",
                            sort="Random", clear_cache=False, timeout=10,
                            node_id="A")
        out2 = node.process(seed=99, mode=rc.MODE_BLUE,
                            base_model=rc.BASE_MODELS_DEFAULT, period="Week",
                            sort="Random", clear_cache=False, timeout=10,
                            node_id="B")
    assert out1[0] == out2[0]


# --- token via env -------------------------------------------------------


def test_auth_header_present_when_env_set(monkeypatch):
    monkeypatch.setenv(rc._TOKEN_ENV, "secret-token")
    h = rc._headers()
    assert h.get("Authorization") == "Bearer secret-token"


def test_auth_header_absent_when_env_unset(monkeypatch):
    monkeypatch.delenv(rc._TOKEN_ENV, raising=False)
    h = rc._headers()
    assert "Authorization" not in h


def test_auth_header_absent_when_env_blank(monkeypatch):
    monkeypatch.setenv(rc._TOKEN_ENV, "   ")
    h = rc._headers()
    assert "Authorization" not in h


def test_no_hardcoded_token_in_source():
    """Guard against accidental commit of a real-looking token."""
    import pathlib
    src = pathlib.Path(rc.__file__).read_text(encoding="utf-8")
    # 32-hex tokens
    import re
    assert not re.search(r"[A-Fa-f0-9]{32}", src), "looks like a hex token in source"


# --- clear_cache helper --------------------------------------------------


def test_clear_cache_drops_all():
    rc._PAGE_CACHE[("k",)] = [{"id": 1}]
    rc.clear_cache()
    assert rc._PAGE_CACHE == {}
