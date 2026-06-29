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
    assert "fetch__tag" in it["required"]


def test_node_returns_four_lists():
    node = rpl.RayPromptLibrary()
    out = node.process(
        mode="Fetch", prompt_in="", seed=-1,
        save__source="", save__tags="", save__image_path="", save__model="",
        fetch__tag="", fetch__source="", fetch__min_length=0,
        fetch__contains="", fetch__exclude="", fetch__sort=rpl.SORT_RANDOM,
        fetch__similar_to="",
    )
    assert len(out) == 4
    for lst in out:
        assert isinstance(lst, list)
        assert len(lst) == 1
