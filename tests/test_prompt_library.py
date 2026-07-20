"""Tests for ray_prompt_library — SQLite save/fetch + optional similarity."""

import pathlib

import pytest

import ray_prompt_library as rpl


@pytest.fixture
def db(tmp_path):
    return tmp_path / "test_library.db"


def test_save_inserts_new_prompt(db):
    r = rpl.save_prompt("first prompt", source="manual", tags="cat", db_path=db)
    assert r["ok"] is True
    assert r["inserted"] is True


def test_save_dedups_identical_prompt(db):
    rpl.save_prompt("same text", source="local", db_path=db)
    r2 = rpl.save_prompt("same text", source="local", db_path=db)
    assert r2["ok"] is True
    assert r2["inserted"] is False


def test_save_rejects_empty_prompt(db):
    r = rpl.save_prompt("   ", db_path=db)
    assert r["ok"] is False


def test_fetch_returns_none_when_empty(db):
    row = rpl.fetch_prompt(db_path=db)
    assert row is None


def test_fetch_random_returns_a_row(db):
    rpl.save_prompt("alpha prompt", source="x", db_path=db)
    rpl.save_prompt("beta prompt", source="x", db_path=db)
    row = rpl.fetch_prompt(seed=1, db_path=db)
    assert row is not None
    assert row["prompt"] in {"alpha prompt", "beta prompt"}


def test_fetch_seed_is_deterministic(db):
    for i in range(5):
        rpl.save_prompt(f"prompt number {i}", source="x", db_path=db)
    r1 = rpl.fetch_prompt(seed=42, db_path=db)
    r2 = rpl.fetch_prompt(seed=42, db_path=db)
    assert r1["prompt"] == r2["prompt"]


def test_fetch_by_source(db):
    rpl.save_prompt("from civitai", source="civitai", db_path=db)
    rpl.save_prompt("from local", source="local", db_path=db)
    row = rpl.fetch_prompt(source="civitai", seed=0, db_path=db)
    assert row["prompt"] == "from civitai"


def test_fetch_by_tag(db):
    rpl.save_prompt("cat in tree", tags="cat,tree", db_path=db)
    rpl.save_prompt("dog in tree", tags="dog,tree", db_path=db)
    row = rpl.fetch_prompt(tag="cat", seed=0, db_path=db)
    assert "cat" in row["prompt"]


def test_fetch_min_length(db):
    rpl.save_prompt("short", db_path=db)
    rpl.save_prompt("this prompt is significantly longer than the threshold",
                    db_path=db)
    row = rpl.fetch_prompt(min_length=20, seed=0, db_path=db)
    assert len(row["prompt"]) >= 20


def test_fetch_contains_substring(db):
    rpl.save_prompt("a cat in a tree", db_path=db)
    rpl.save_prompt("a dog in a yard", db_path=db)
    row = rpl.fetch_prompt(contains="cat", seed=0, db_path=db)
    assert "cat" in row["prompt"]


def test_fetch_exclude_substring(db):
    rpl.save_prompt("a cat in a tree", db_path=db)
    rpl.save_prompt("a dog in a yard", db_path=db)
    row = rpl.fetch_prompt(exclude="cat", seed=0, db_path=db)
    assert "cat" not in row["prompt"]


def test_fetch_sort_longest(db):
    rpl.save_prompt("short one", db_path=db)
    rpl.save_prompt("longest prompt of the bunch by character count", db_path=db)
    rpl.save_prompt("medium length", db_path=db)
    row = rpl.fetch_prompt(sort=rpl.SORT_LONGEST, db_path=db)
    assert "longest prompt" in row["prompt"]


def test_fetch_sort_most_recent(db):
    rpl.save_prompt("old prompt", db_path=db)
    import time
    time.sleep(0.05)
    rpl.save_prompt("new prompt", db_path=db)
    row = rpl.fetch_prompt(sort=rpl.SORT_RECENT, db_path=db)
    assert row["prompt"] == "new prompt"


def test_stats(db):
    rpl.save_prompt("a", source="civitai", db_path=db)
    rpl.save_prompt("b", source="local", db_path=db)
    s = rpl.stats(db_path=db)
    assert s["total"] == 2
    assert set(s["sources"]) >= {"civitai", "local"}


def test_clear_library(db):
    rpl.save_prompt("temp prompt", db_path=db)
    n = rpl.clear_library(db_path=db)
    assert n == 1
    assert rpl.stats(db_path=db)["total"] == 0


def test_input_types_declares_required_widgets():
    it = rpl.RayPromptLibrary.INPUT_TYPES()
    assert "mode" in it["required"]
    assert "prompt_in" in it["required"]
    assert "save__source" in it["required"]
    assert "browse__selected_id" in it["required"]
    # Legacy fetch__* widgets removed.
    assert "fetch__tag" not in it["required"]


def test_node_save_mode_returns_four_lists():
    node = rpl.RayPromptLibrary()
    out = node.process(
        mode="Save", prompt_in="test prompt", seed=-1,
        save__source="manual", save__tags="", save__image_path="",
        save__model="", browse__selected_id=-1, browse__last_query="",
    )
    assert len(out) == 4
    for lst in out:
        assert isinstance(lst, list)
        assert len(lst) == 1


def test_node_browse_mode_no_selection_raises():
    node = rpl.RayPromptLibrary()
    with pytest.raises(RuntimeError, match="no prompt selected"):
        node.process(
            mode="Browse", prompt_in="", seed=-1,
            save__source="", save__tags="", save__image_path="",
            save__model="", browse__selected_id=-1, browse__last_query="",
        )


def test_node_browse_mode_missing_id_raises():
    node = rpl.RayPromptLibrary()
    with pytest.raises(RuntimeError, match="no longer in the library"):
        node.process(
            mode="Browse", prompt_in="", seed=-1,
            save__source="", save__tags="", save__image_path="",
            save__model="", browse__selected_id=999999, browse__last_query="",
        )


def test_node_legacy_fetch_mode_falls_through_to_browse():
    """Old workflows serialized mode='Fetch' — must not crash the graph."""
    node = rpl.RayPromptLibrary()
    with pytest.raises(RuntimeError, match="no prompt selected"):
        node.process(
            mode="Fetch", prompt_in="", seed=-1,
            save__source="", save__tags="", save__image_path="",
            save__model="", browse__selected_id=-1, browse__last_query="",
        )


# ---------------------------------------------------------------------------
# fetch_by_id
# ---------------------------------------------------------------------------


def test_fetch_by_id_roundtrip(db):
    rpl.save_prompt("alpha", source="local", tags="cat", db_path=db)
    # Retrieve id via a search.
    res = rpl.search_prompts(q="alpha", db_path=db)
    assert res["rows"]
    rid = res["rows"][0]["id"]
    row = rpl.fetch_by_id(rid, db_path=db)
    assert row is not None
    assert row["prompt"] == "alpha"


def test_fetch_by_id_returns_none_for_missing(db):
    assert rpl.fetch_by_id(9999, db_path=db) is None


def test_fetch_by_id_returns_none_for_negative(db):
    assert rpl.fetch_by_id(-1, db_path=db) is None


# ---------------------------------------------------------------------------
# search_prompts
# ---------------------------------------------------------------------------


def test_search_returns_all_when_no_filter(db):
    for i in range(3):
        rpl.save_prompt(f"row {i}", source="x", db_path=db)
    res = rpl.search_prompts(db_path=db)
    assert res["total"] == 3
    assert len(res["rows"]) == 3


def test_search_keyword_filter(db):
    rpl.save_prompt("a fox in a meadow", db_path=db)
    rpl.save_prompt("a hawk in a canyon", db_path=db)
    res = rpl.search_prompts(q="fox", db_path=db)
    assert res["total"] == 1
    assert "fox" in res["rows"][0]["prompt"]


def test_search_source_filter(db):
    rpl.save_prompt("civ prompt", source="civitai", db_path=db)
    rpl.save_prompt("loc prompt", source="local", db_path=db)
    res = rpl.search_prompts(source="civitai", db_path=db)
    assert res["total"] == 1
    assert res["rows"][0]["source"] == "civitai"


def test_search_tag_filter(db):
    rpl.save_prompt("with cat", tags="cat,animal", db_path=db)
    rpl.save_prompt("with dog", tags="dog,animal", db_path=db)
    res = rpl.search_prompts(tag="cat", db_path=db)
    assert res["total"] == 1


def test_search_sort_longest(db):
    rpl.save_prompt("short", db_path=db)
    rpl.save_prompt("a much longer prompt than the other", db_path=db)
    res = rpl.search_prompts(sort=rpl.SORT_LONGEST, db_path=db)
    assert res["rows"][0]["length"] > res["rows"][1]["length"]


def test_search_sort_shortest(db):
    rpl.save_prompt("short", db_path=db)
    rpl.save_prompt("a much longer prompt than the other", db_path=db)
    res = rpl.search_prompts(sort=rpl.SORT_SHORTEST, db_path=db)
    assert res["rows"][0]["length"] < res["rows"][1]["length"]


def test_search_sort_recent_and_oldest(db):
    import time
    rpl.save_prompt("first row", db_path=db)
    time.sleep(0.05)
    rpl.save_prompt("second row", db_path=db)
    recent = rpl.search_prompts(sort=rpl.SORT_RECENT, db_path=db)
    oldest = rpl.search_prompts(sort=rpl.SORT_OLDEST, db_path=db)
    assert recent["rows"][0]["prompt"] == "second row"
    assert oldest["rows"][0]["prompt"] == "first row"


def test_search_pagination(db):
    for i in range(5):
        rpl.save_prompt(f"prompt {i}", db_path=db)
    page1 = rpl.search_prompts(sort=rpl.SORT_RECENT, limit=2, offset=0, db_path=db)
    page2 = rpl.search_prompts(sort=rpl.SORT_RECENT, limit=2, offset=2, db_path=db)
    assert page1["total"] == 5
    assert len(page1["rows"]) == 2
    assert len(page2["rows"]) == 2
    ids1 = {r["id"] for r in page1["rows"]}
    ids2 = {r["id"] for r in page2["rows"]}
    assert ids1.isdisjoint(ids2)


def test_search_row_has_preview_and_length(db):
    long_text = "x " * 200
    rpl.save_prompt(long_text.strip(), db_path=db)
    res = rpl.search_prompts(db_path=db)
    r = res["rows"][0]
    assert "prompt_preview" in r
    assert "length" in r
    assert len(r["prompt_preview"]) <= 241  # 240 + ellipsis
    assert r["length"] == len(long_text.strip())


def test_search_strips_embedding_from_rows(db):
    rpl.save_prompt("test prompt", db_path=db)
    res = rpl.search_prompts(db_path=db)
    for r in res["rows"]:
        assert "embedding" not in r


def test_search_similarity_falls_back_when_no_embed(db, monkeypatch):
    """When sentence-transformers unavailable, similarity sort still returns rows."""
    monkeypatch.setattr(rpl, "_get_embed_model", lambda: None)
    rpl.save_prompt("something", db_path=db)
    rpl.save_prompt("something else", db_path=db)
    res = rpl.search_prompts(
        q="something", sort=rpl.SORT_SIMILARITY, db_path=db,
    )
    # Should not crash; falls through to keyword ranking.
    assert res["total"] >= 1


def test_search_empty_db_returns_zero(db):
    res = rpl.search_prompts(db_path=db)
    assert res["total"] == 0
    assert res["rows"] == []


def test_search_fts_escape_handles_punctuation(db):
    rpl.save_prompt("a masterpiece, best quality", db_path=db)
    res = rpl.search_prompts(q="masterpiece", db_path=db)
    assert res["total"] == 1
