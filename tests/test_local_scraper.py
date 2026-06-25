"""Tests for ray_local_scraper. Synthesizes real PNG/JPEG/WEBP files with
embedded metadata so we exercise PIL's actual loaders.
"""

import json
import pathlib
from collections import deque

import pytest
import torch
from PIL import Image, PngImagePlugin

import ray_local_scraper as rls
from ray_local_scraper import RayLocalScraper


@pytest.fixture(autouse=True)
def reset_globals():
    rls._FILE_LIST_CACHE.clear()
    rls._RECENT_BY_NODE.clear()
    yield
    rls._FILE_LIST_CACHE.clear()
    rls._RECENT_BY_NODE.clear()


# ---------------------------------------------------------------------------
# Image factories
# ---------------------------------------------------------------------------


def _make_solid_png(path: pathlib.Path, info: dict = None, size=(8, 8), color="red"):
    img = Image.new("RGB", size, color=color)
    pi = PngImagePlugin.PngInfo()
    if info:
        for k, v in info.items():
            pi.add_text(k, v)
    img.save(path, "PNG", pnginfo=pi)


def _make_solid_jpeg(path: pathlib.Path, user_comment: str = "", size=(8, 8)):
    img = Image.new("RGB", size, color="blue")
    if user_comment:
        from PIL import Image as _I
        exif = img.getexif()
        # 37510 = UserComment; ASCII prefix per spec.
        exif[37510] = b"ASCII\0\0\0" + user_comment.encode("utf-8")
        img.save(path, "JPEG", exif=exif.tobytes())
    else:
        img.save(path, "JPEG")


def _comfy_prompt_graph(text: str = "a fox in the forest, masterpiece"):
    return json.dumps({
        "1": {"class_type": "CLIPTextEncode", "inputs": {"text": text}},
    })


def _comfy_multi_prompt_graph():
    return json.dumps({
        "1": {"class_type": "CLIPTextEncode",
              "inputs": {"text": "first positive prompt about a fox"}},
        "2": {"class_type": "CLIPTextEncode",
              "inputs": {"text": "second positive prompt about a hawk"}},
        "3": {"class_type": "CLIPTextEncodeSDXL",
              "inputs": {"text_g": "ignored"}},  # different field
    })


# ---------------------------------------------------------------------------
# Extractor unit tests
# ---------------------------------------------------------------------------


def test_strip_a1111_keeps_positive_only():
    blob = ("a beautiful landscape, masterpiece\n"
            "Negative prompt: blurry, lowres\n"
            "Steps: 30, Sampler: Euler a")
    assert rls._strip_a1111(blob) == "a beautiful landscape, masterpiece"


def test_strip_a1111_handles_no_negative():
    blob = "just a positive prompt\nSteps: 20"
    assert rls._strip_a1111(blob) == "just a positive prompt"


def test_extract_prompts_from_a1111_png(tmp_path):
    p = tmp_path / "a1111.png"
    _make_solid_png(p, info={
        "parameters": ("a fox in a meadow, photorealistic\n"
                       "Negative prompt: blurry\nSteps: 25"),
    })
    with Image.open(p) as im:
        prompts = rls.extract_prompts(p, im)
    assert prompts == ["a fox in a meadow, photorealistic"]


def test_extract_prompts_from_comfy_prompt_chunk(tmp_path):
    p = tmp_path / "comfy.png"
    _make_solid_png(p, info={"prompt": _comfy_prompt_graph("a hawk circling")})
    with Image.open(p) as im:
        prompts = rls.extract_prompts(p, im)
    assert prompts == ["a hawk circling"]


def test_extract_prompts_returns_multiple_positives(tmp_path):
    p = tmp_path / "multi.png"
    _make_solid_png(p, info={"prompt": _comfy_multi_prompt_graph()})
    with Image.open(p) as im:
        prompts = rls.extract_prompts(p, im)
    # Both CLIPTextEncode prompts must be present; order = best/longest first.
    assert "first positive prompt about a fox" in prompts
    assert "second positive prompt about a hawk" in prompts
    assert len(prompts) >= 2


def test_extract_prompts_workflow_chunk_fallback(tmp_path):
    p = tmp_path / "workflow.png"
    _make_solid_png(p, info={"workflow": _comfy_prompt_graph("via workflow chunk")})
    with Image.open(p) as im:
        prompts = rls.extract_prompts(p, im)
    assert "via workflow chunk" in prompts


def test_extract_prompts_empty_when_no_metadata(tmp_path):
    p = tmp_path / "bare.png"
    _make_solid_png(p)
    with Image.open(p) as im:
        prompts = rls.extract_prompts(p, im)
    assert prompts == []


def test_extract_prompts_jpeg_user_comment(tmp_path):
    p = tmp_path / "jpeg_a1111.jpg"
    _make_solid_jpeg(p, user_comment=("a sunset over hills\n"
                                       "Negative prompt: ugly\nSteps: 20"))
    with Image.open(p) as im:
        prompts = rls.extract_prompts(p, im)
    assert prompts == ["a sunset over hills"]


def test_extract_prompts_sidecar_txt(tmp_path):
    p = tmp_path / "bare.png"
    _make_solid_png(p)
    sidecar = p.with_suffix(".txt")
    sidecar.write_text("prompt from sidecar file", encoding="utf-8")
    with Image.open(p) as im:
        prompts = rls.extract_prompts(p, im)
    assert prompts == ["prompt from sidecar file"]


def test_extract_prompt_follows_wired_text_multiline(tmp_path):
    """CLIPTextEncode.text wired into a Text Multiline source node."""
    graph = {
        "1": {
            "class_type": "Text Multiline",
            "inputs": {"text": "the actual positive prompt from a text widget"},
        },
        "2": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": ["1", 0]},
        },
    }
    p = tmp_path / "wired.png"
    _make_solid_png(p, info={"prompt": json.dumps(graph)})
    with Image.open(p) as im:
        prompts = rls.extract_prompts(p, im)
    assert "the actual positive prompt from a text widget" in prompts


def test_extract_prompt_follows_wired_show_text(tmp_path):
    """CLIPTextEncode <- ShowText <- String Literal chain."""
    graph = {
        "1": {
            "class_type": "String Literal",
            "inputs": {"string": "literal at the tail of the chain"},
        },
        "2": {
            "class_type": "ShowText|pysssss",
            "inputs": {"text": ["1", 0]},
        },
        "3": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": ["2", 0]},
        },
    }
    p = tmp_path / "chain.png"
    _make_solid_png(p, info={"prompt": json.dumps(graph)})
    with Image.open(p) as im:
        prompts = rls.extract_prompts(p, im)
    assert "literal at the tail of the chain" in prompts


def test_extract_prompt_joins_concat_inputs(tmp_path):
    """Text Concatenate with two literal text inputs should join them."""
    graph = {
        "1": {
            "class_type": "Text Concatenate",
            "inputs": {
                "text_a": "first piece of the prompt",
                "text_b": "second piece of the prompt",
            },
        },
        "2": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": ["1", 0]},
        },
    }
    p = tmp_path / "concat.png"
    _make_solid_png(p, info={"prompt": json.dumps(graph)})
    with Image.open(p) as im:
        prompts = rls.extract_prompts(p, im)
    assert prompts, "should have at least one prompt"
    # Both pieces must be present in the resolved prompt.
    combined = " ".join(prompts)
    assert "first piece of the prompt" in combined
    assert "second piece of the prompt" in combined


def test_extract_prompt_handles_cycle_without_hanging(tmp_path):
    """If two nodes wire into each other, walker must bail, not loop."""
    graph = {
        "1": {"class_type": "ShowText",
              "inputs": {"text": ["2", 0]}},
        "2": {"class_type": "ShowText",
              "inputs": {"text": ["1", 0]}},
        "3": {"class_type": "CLIPTextEncode",
              "inputs": {"text": ["1", 0]}},
    }
    p = tmp_path / "cycle.png"
    _make_solid_png(p, info={"prompt": json.dumps(graph)})
    with Image.open(p) as im:
        prompts = rls.extract_prompts(p, im)
    # No literal text on either node; cycle should be handled, returning
    # an empty prompt list (or at least not crashing).
    assert prompts == []


def test_extract_prompt_multi_encoder_wired(tmp_path):
    """Two CLIPTextEncode nodes each wired to different source nodes — both
    prompts should come back."""
    graph = {
        "1": {"class_type": "Text Multiline",
              "inputs": {"text": "positive from encoder one"}},
        "2": {"class_type": "Text Multiline",
              "inputs": {"text": "positive from encoder two"}},
        "3": {"class_type": "CLIPTextEncode",
              "inputs": {"text": ["1", 0]}},
        "4": {"class_type": "CLIPTextEncode",
              "inputs": {"text": ["2", 0]}},
    }
    p = tmp_path / "multi_wired.png"
    _make_solid_png(p, info={"prompt": json.dumps(graph)})
    with Image.open(p) as im:
        prompts = rls.extract_prompts(p, im)
    assert "positive from encoder one" in prompts
    assert "positive from encoder two" in prompts


def test_extract_prompt_literal_wins_over_walk(tmp_path):
    """When the encoder has a literal text input, we should use it even
    if other nodes exist."""
    graph = {
        "1": {"class_type": "Text Multiline",
              "inputs": {"text": "stray text that should not be picked"}},
        "2": {"class_type": "CLIPTextEncode",
              "inputs": {"text": "the literal we want"}},
    }
    p = tmp_path / "literal_wins.png"
    _make_solid_png(p, info={"prompt": json.dumps(graph)})
    with Image.open(p) as im:
        prompts = rls.extract_prompts(p, im)
    assert "the literal we want" in prompts
    # The stray text must not be returned: encoder-text strategy yields
    # one prompt only when it succeeds.
    assert "stray text that should not be picked" not in prompts


def test_extract_prompts_deduplicates_identical(tmp_path):
    p = tmp_path / "dup.png"
    # parameters AND prompt chunk both contain the same text.
    same = "exactly the same prompt"
    _make_solid_png(p, info={
        "parameters": same + "\nNegative prompt: x\nSteps: 1",
        "prompt": _comfy_prompt_graph(same),
    })
    with Image.open(p) as im:
        prompts = rls.extract_prompts(p, im)
    assert prompts.count(same) == 1


# ---------------------------------------------------------------------------
# Folder enumeration
# ---------------------------------------------------------------------------


def test_enumerate_images_top_level_only(tmp_path):
    _make_solid_png(tmp_path / "a.png")
    sub = tmp_path / "sub"
    sub.mkdir()
    _make_solid_png(sub / "b.png")
    flat = rls._enumerate_images(tmp_path, recurse=False)
    assert [pathlib.Path(p).name for p in flat] == ["a.png"]


def test_enumerate_images_recursive(tmp_path):
    _make_solid_png(tmp_path / "a.png")
    sub = tmp_path / "sub"
    sub.mkdir()
    _make_solid_png(sub / "b.png")
    deep = tmp_path / "sub" / "deeper"
    deep.mkdir()
    _make_solid_png(deep / "c.png")
    full = rls._enumerate_images(tmp_path, recurse=True)
    names = sorted(pathlib.Path(p).name for p in full)
    assert names == ["a.png", "b.png", "c.png"]


def test_enumerate_images_ignores_non_image_files(tmp_path):
    _make_solid_png(tmp_path / "a.png")
    (tmp_path / "notes.txt").write_text("hi")
    (tmp_path / "video.mp4").write_bytes(b"\0")
    found = rls._enumerate_images(tmp_path, recurse=False)
    assert [pathlib.Path(p).name for p in found] == ["a.png"]


def test_file_list_caches_by_folder_and_recurse(tmp_path):
    _make_solid_png(tmp_path / "a.png")
    a = rls._file_list(tmp_path, recurse=False)
    # Add a new file after caching — second call should still return cached.
    _make_solid_png(tmp_path / "b.png")
    b = rls._file_list(tmp_path, recurse=False)
    assert a == b == [str(tmp_path / "a.png")]
    # Refresh picks the new file up.
    c = rls._file_list(tmp_path, recurse=False, refresh=True)
    assert len(c) == 2


# ---------------------------------------------------------------------------
# Full process() integration
# ---------------------------------------------------------------------------


def test_process_returns_four_outputs(tmp_path):
    p = tmp_path / "a.png"
    _make_solid_png(p, info={
        "parameters": "a clean prompt\nNegative prompt: x\nSteps: 20"
    })
    node = RayLocalScraper()
    out = node.process(
        folder=str(tmp_path),
        recurse_subfolders=False,
        skip_no_prompt=False,
        seed=1,
        refresh_listing=True,
        node_id="t",
    )
    single, multi, image, path_out = out
    assert single == "a clean prompt"
    assert multi == "a clean prompt"
    assert image.shape[-1] == 3
    assert pathlib.Path(path_out) == p


def test_process_returns_empty_prompt_when_no_metadata(tmp_path):
    p = tmp_path / "bare.png"
    _make_solid_png(p)
    node = RayLocalScraper()
    single, multi, image, path_out = node.process(
        folder=str(tmp_path),
        recurse_subfolders=False,
        skip_no_prompt=False,
        seed=1,
        refresh_listing=True,
        node_id="t",
    )
    assert single == ""
    assert multi == ""
    assert pathlib.Path(path_out) == p


def test_process_skip_no_prompt_finds_the_one_with_prompt(tmp_path):
    # Three bare PNGs + one with a prompt. With skip_no_prompt on, we must
    # land on the prompted one regardless of seed.
    bare = []
    for i in range(3):
        b = tmp_path / f"bare{i}.png"
        _make_solid_png(b)
        bare.append(b)
    target = tmp_path / "good.png"
    _make_solid_png(target, info={
        "parameters": "the lucky prompt\nNegative prompt: x\nSteps: 10"
    })
    node = RayLocalScraper()
    single, multi, image, path_out = node.process(
        folder=str(tmp_path),
        recurse_subfolders=False,
        skip_no_prompt=True,
        seed=5,
        refresh_listing=True,
        node_id="t",
    )
    assert single == "the lucky prompt"
    assert pathlib.Path(path_out) == target


def test_process_skip_no_prompt_raises_when_none_match(tmp_path):
    for i in range(3):
        _make_solid_png(tmp_path / f"bare{i}.png")
    node = RayLocalScraper()
    with pytest.raises(RuntimeError, match="no images with extractable prompts"):
        node.process(
            folder=str(tmp_path),
            recurse_subfolders=False,
            skip_no_prompt=True,
            seed=1,
            refresh_listing=True,
            node_id="t",
        )


def test_process_recurse_subfolders_finds_nested_image(tmp_path):
    deep = tmp_path / "deep" / "deeper"
    deep.mkdir(parents=True)
    target = deep / "nested.png"
    _make_solid_png(target, info={
        "parameters": "nested prompt\nNegative prompt: x\nSteps: 1"
    })
    node = RayLocalScraper()
    single, multi, image, path_out = node.process(
        folder=str(tmp_path),
        recurse_subfolders=True,
        skip_no_prompt=False,
        seed=1,
        refresh_listing=True,
        node_id="t",
    )
    assert pathlib.Path(path_out) == target
    assert single == "nested prompt"


def test_process_recurse_off_does_not_find_nested(tmp_path):
    deep = tmp_path / "deep"
    deep.mkdir()
    _make_solid_png(deep / "nested.png")
    node = RayLocalScraper()
    with pytest.raises(RuntimeError, match="no supported images"):
        node.process(
            folder=str(tmp_path),
            recurse_subfolders=False,
            skip_no_prompt=False,
            seed=1,
            refresh_listing=True,
            node_id="t",
        )


def test_process_multi_prompt_batched_into_multiline(tmp_path):
    p = tmp_path / "multi.png"
    _make_solid_png(p, info={"prompt": _comfy_multi_prompt_graph()})
    node = RayLocalScraper()
    single, multi, image, path_out = node.process(
        folder=str(tmp_path),
        recurse_subfolders=False,
        skip_no_prompt=False,
        seed=1,
        refresh_listing=True,
        node_id="t",
    )
    assert "\n---\n" in multi
    # single is the first prompt collapsed to one line.
    assert single in (
        "first positive prompt about a fox",
        "second positive prompt about a hawk",
    )
    # All prompts should appear in the batched output.
    assert "first positive prompt about a fox" in multi
    assert "second positive prompt about a hawk" in multi


def test_process_raises_when_folder_missing(tmp_path):
    node = RayLocalScraper()
    with pytest.raises(RuntimeError, match="folder does not exist"):
        node.process(
            folder=str(tmp_path / "nope"),
            recurse_subfolders=False,
            skip_no_prompt=False,
            seed=1,
            node_id="t",
        )


def test_process_raises_when_folder_blank():
    node = RayLocalScraper()
    with pytest.raises(RuntimeError, match="folder path is empty"):
        node.process(
            folder="   ",
            recurse_subfolders=False,
            skip_no_prompt=False,
            seed=1,
            node_id="t",
        )


def test_process_image_path_is_absolute_string(tmp_path):
    p = tmp_path / "a.png"
    _make_solid_png(p)
    node = RayLocalScraper()
    _, _, _, path_out = node.process(
        folder=str(tmp_path),
        recurse_subfolders=False,
        skip_no_prompt=False,
        seed=1,
        refresh_listing=True,
        node_id="t",
    )
    assert isinstance(path_out, str)
    assert pathlib.Path(path_out).is_absolute()


# ---------------------------------------------------------------------------
# Deterministic selection
# ---------------------------------------------------------------------------


def test_select_path_skips_recent():
    import random as _r
    paths = [f"/tmp/{i}.png" for i in range(5)]
    recent = deque([paths[0]], maxlen=20)
    rng = _r.Random(1)
    pick = rls._select_path(paths, recent, rng, deterministic=True)
    assert pick != paths[0]


def test_process_same_seed_picks_same_file(tmp_path):
    for i in range(5):
        _make_solid_png(tmp_path / f"img{i}.png", info={
            "parameters": f"prompt {i}\nSteps: 1"
        })
    node = RayLocalScraper()
    out1 = node.process(folder=str(tmp_path), recurse_subfolders=False,
                        skip_no_prompt=False, seed=42, refresh_listing=True,
                        node_id="A")
    out2 = node.process(folder=str(tmp_path), recurse_subfolders=False,
                        skip_no_prompt=False, seed=42, refresh_listing=True,
                        node_id="B")
    assert out1[3] == out2[3]


def test_clear_cache_resets_state(tmp_path):
    _make_solid_png(tmp_path / "a.png")
    rls._file_list(tmp_path, recurse=False)
    rls._RECENT_BY_NODE["n"] = deque(["x"], maxlen=20)
    assert rls._FILE_LIST_CACHE
    rls.clear_cache()
    assert rls._FILE_LIST_CACHE == {}
    assert rls._RECENT_BY_NODE == {}
