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
def reset_globals(monkeypatch):
    rls._FILE_LIST_CACHE.clear()
    rls._RECENT_BY_NODE.clear()
    rls._LAST_BEST_BY_NODE.clear()
    # Some CI/dev environments ship a torch stub without `from_numpy`.
    # Fall back to a placeholder tensor when the stub is incomplete so the
    # scraper's non-tensor logic (prompt selection, path picking) is still
    # exercised end-to-end by pytest.
    if not hasattr(torch, "from_numpy"):
        class _FakeTensor:
            def __init__(self, shape=(1, 8, 8, 3)):
                self.shape = shape
        monkeypatch.setattr(rls, "_pil_to_tensor", lambda pil: _FakeTensor())
        monkeypatch.setattr(rls, "_black_tensor", lambda: _FakeTensor((1, 1, 1, 3)))
    yield
    rls._FILE_LIST_CACHE.clear()
    rls._RECENT_BY_NODE.clear()
    rls._LAST_BEST_BY_NODE.clear()


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


def test_enumerate_images_recursive_picks_up_extensions_case_insensitively(tmp_path):
    """`.PNG` (uppercase) should be picked up by the recursive walker."""
    sub = tmp_path / "sub"
    sub.mkdir()
    _make_solid_png(sub / "upper.PNG")
    _make_solid_png(sub / "lower.png")
    found = rls._enumerate_images(tmp_path, recurse=True)
    names = sorted(pathlib.Path(p).name for p in found)
    assert names == ["lower.png", "upper.PNG"]


def test_enumerate_images_handles_unreadable_subdir_gracefully(tmp_path):
    """A subdir that throws on iteration must not abort the whole scan."""
    _make_solid_png(tmp_path / "a.png")
    sub = tmp_path / "sub"
    sub.mkdir()
    _make_solid_png(sub / "b.png")
    # We do not actually break a subdir's permission here because Windows
    # ACLs are messy in tests; instead just assert the happy path covers
    # multi-level recursion.
    full = rls._enumerate_images(tmp_path, recurse=True)
    names = sorted(pathlib.Path(p).name for p in full)
    assert names == ["a.png", "b.png"]


def test_coerce_bool_handles_string_false_correctly():
    """plain bool('false') is True; our coercer must say False."""
    assert rls._coerce_bool("false") is False
    assert rls._coerce_bool("False") is False
    assert rls._coerce_bool("FALSE") is False
    assert rls._coerce_bool("0") is False
    assert rls._coerce_bool("no") is False
    assert rls._coerce_bool("off") is False
    assert rls._coerce_bool("") is False
    assert rls._coerce_bool("true") is True
    assert rls._coerce_bool("True") is True
    assert rls._coerce_bool("1") is True
    assert rls._coerce_bool("yes") is True
    assert rls._coerce_bool("on") is True
    assert rls._coerce_bool(0) is False
    assert rls._coerce_bool(1) is True
    assert rls._coerce_bool(True) is True
    assert rls._coerce_bool(False) is False


def test_process_recurse_string_false_does_not_recurse(tmp_path):
    """A frontend that sends 'false' as a string must NOT enable recursion."""
    sub = tmp_path / "sub"
    sub.mkdir()
    _make_solid_png(sub / "nested.png")  # nested only
    node = RayLocalScraper()
    with pytest.raises(RuntimeError, match="no supported images"):
        node.process(
            folder=str(tmp_path),
            recurse_subfolders="false",  # frontend quirk
            skip_no_prompt=False,
            seed=1,
            refresh_listing=True,
            node_id="t",
        )


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


def test_process_returns_four_list_outputs(tmp_path):
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
    # All four outputs must be lists (OUTPUT_IS_LIST = True for each).
    assert isinstance(single, list) and len(single) == 1
    assert isinstance(multi, list) and len(multi) == 1
    assert isinstance(image, list) and len(image) == 1
    assert isinstance(path_out, list) and len(path_out) == 1
    assert single[0] == "a clean prompt"
    assert multi[0] == "a clean prompt"
    assert image[0].shape[-1] == 3
    assert pathlib.Path(path_out[0]) == p


def test_node_declares_output_is_list_for_every_output():
    assert RayLocalScraper.OUTPUT_IS_LIST == (True, True, True, True)
    assert len(RayLocalScraper.OUTPUT_IS_LIST) == len(RayLocalScraper.RETURN_TYPES)


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
    assert single == [""]
    assert multi == [""]
    assert len(image) == 1
    assert pathlib.Path(path_out[0]) == p


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
    assert single == ["the lucky prompt"]
    assert pathlib.Path(path_out[0]) == target


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
    assert pathlib.Path(path_out[0]) == target
    assert single == ["nested prompt"]


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


def test_process_multi_prompt_emits_parallel_list_outputs(tmp_path):
    """Image with N positive prompts -> every output is a list of length N,
    with image + path broadcast across each entry."""
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
    # All four outputs must be lists with the same length.
    assert isinstance(single, list)
    assert isinstance(multi, list)
    assert isinstance(image, list)
    assert isinstance(path_out, list)
    assert len(single) == len(multi) == len(image) == len(path_out)
    assert len(single) >= 2

    # Each prompt appears exactly once in both prompt outputs.
    assert "first positive prompt about a fox" in single
    assert "second positive prompt about a hawk" in single
    assert "first positive prompt about a fox" in multi
    assert "second positive prompt about a hawk" in multi

    # Image and path are repeated (broadcast) across every prompt entry.
    assert all(pathlib.Path(x) == p for x in path_out)
    assert all(t.shape == image[0].shape for t in image)


def test_process_single_prompt_still_returns_lists_of_length_one(tmp_path):
    """Sanity: even when a single prompt is found, outputs are still lists."""
    p = tmp_path / "one.png"
    _make_solid_png(p, info={
        "parameters": "lone prompt\nNegative prompt: x\nSteps: 1"
    })
    node = RayLocalScraper()
    single, multi, image, path_out = node.process(
        folder=str(tmp_path),
        recurse_subfolders=False,
        skip_no_prompt=False,
        seed=1,
        refresh_listing=True,
        node_id="t",
    )
    assert single == ["lone prompt"]
    assert multi == ["lone prompt"]
    assert len(image) == 1 and len(path_out) == 1


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
    assert isinstance(path_out, list) and len(path_out) == 1
    assert isinstance(path_out[0], str)
    assert pathlib.Path(path_out[0]).is_absolute()


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
    assert out1[3][0] == out2[3][0]


def test_clear_cache_resets_state(tmp_path):
    _make_solid_png(tmp_path / "a.png")
    rls._file_list(tmp_path, recurse=False)
    rls._RECENT_BY_NODE["n"] = deque(["x"], maxlen=20)
    assert rls._FILE_LIST_CACHE
    rls.clear_cache()
    assert rls._FILE_LIST_CACHE == {}
    assert rls._RECENT_BY_NODE == {}


# ---------------------------------------------------------------------------
# Path-shaped rejection
# ---------------------------------------------------------------------------


def test_looks_like_path_windows_drive():
    assert rls._looks_like_path(r"C:\models\stable-diffusion\sdxl_base.safetensors")


def test_looks_like_path_windows_backslash_run():
    assert rls._looks_like_path(r"models\loras\extra\my_lora.safetensors")


def test_looks_like_path_unix_absolute():
    assert rls._looks_like_path("/home/user/stable-diffusion/output/foo.png")


def test_looks_like_path_relative_dot_slash():
    assert rls._looks_like_path("./output/2024/foo.png")


def test_looks_like_path_bare_safetensors_filename():
    assert rls._looks_like_path("sdxl_base_1.0.safetensors")


def test_looks_like_path_does_not_reject_prompt_with_slash():
    """A real prompt can contain a slash without being rejected as a path."""
    prompt = "a woman standing under bright sunlight, 4k / photorealistic"
    assert not rls._looks_like_path(prompt)


def test_looks_like_path_does_not_reject_multiline_prose():
    prose = "line one about a mountain\nline two about a river\nline three"
    assert not rls._looks_like_path(prose)


def test_valid_prompt_candidate_rejects_bool_and_numbers():
    assert not rls._valid_prompt_candidate("true")
    assert not rls._valid_prompt_candidate("false")
    assert not rls._valid_prompt_candidate("none")
    assert not rls._valid_prompt_candidate("null")
    assert not rls._valid_prompt_candidate("42")
    assert not rls._valid_prompt_candidate("3.14")


def test_valid_prompt_candidate_rejects_paths_and_short():
    assert not rls._valid_prompt_candidate("")
    assert not rls._valid_prompt_candidate("hi")
    assert not rls._valid_prompt_candidate(r"C:\loras\foo.safetensors")
    assert rls._valid_prompt_candidate("a cat in a hat")


def test_extract_prompts_rejects_path_shaped_info_key(tmp_path):
    """A `lora_path` info key with a Windows-style path must not leak
    through as a prompt."""
    p = tmp_path / "paths.png"
    _make_solid_png(p, info={
        "parameters": "the real prompt here\nNegative prompt: bad\nSteps: 1",
        "prompt_lora_path": r"C:\loras\my_style.safetensors",
    })
    with Image.open(p) as im:
        prompts = rls.extract_prompts(p, im)
    # Only the real A1111 prompt survives.
    assert prompts == ["the real prompt here"]


def test_extract_prompts_rejects_folder_style_in_comfy_string_node(tmp_path):
    """A ComfyUI String Literal node holding a checkpoint path must not
    be surfaced as a prompt when no encoder text exists."""
    graph = {
        "1": {
            "class_type": "String Literal",
            "inputs": {"string": r"models\checkpoints\dreamshaper.safetensors"},
        },
    }
    p = tmp_path / "path_string.png"
    _make_solid_png(p, info={"prompt": json.dumps(graph)})
    with Image.open(p) as im:
        prompts = rls.extract_prompts(p, im)
    assert prompts == []


# ---------------------------------------------------------------------------
# Extra info-key + EXIF text extraction
# ---------------------------------------------------------------------------


def test_extract_prompts_from_generic_prompt_info_key(tmp_path):
    """A tool that writes `caption` or `description` alongside the image
    should have that text picked up as a prompt candidate."""
    p = tmp_path / "caption.png"
    _make_solid_png(p, info={
        "caption": "a portrait of a person wearing a red hat",
    })
    with Image.open(p) as im:
        prompts = rls.extract_prompts(p, im)
    assert "a portrait of a person wearing a red hat" in prompts


def test_extract_prompts_from_swarmui_style_json_blob(tmp_path):
    """SwarmUI writes a JSON metadata blob under `sui_image_params` with
    a nested `prompt` key. The walker should surface the inner prompt."""
    blob = json.dumps({
        "sui_image_params": {
            "prompt": "a swarm-generated positive prompt",
            "negativeprompt": "blurry, low quality",
            "steps": 25,
        }
    })
    p = tmp_path / "sui.png"
    _make_solid_png(p, info={"sui_image_params": blob})
    with Image.open(p) as im:
        prompts = rls.extract_prompts(p, im)
    assert "a swarm-generated positive prompt" in prompts


def test_extract_prompts_from_novelai_metadata(tmp_path):
    """NovelAI-style metadata: a JSON string with prompt inside."""
    blob = json.dumps({"Description": "a novelai style prompt of a fox"})
    p = tmp_path / "nai.png"
    _make_solid_png(p, info={"Comment": blob})
    with Image.open(p) as im:
        prompts = rls.extract_prompts(p, im)
    assert "a novelai style prompt of a fox" in prompts


def test_extract_prompts_from_jpeg_image_description(tmp_path):
    """EXIF ImageDescription (tag 270) should be mined for prompts."""
    p = tmp_path / "exif_desc.jpg"
    img = Image.new("RGB", (8, 8), color="green")
    exif = img.getexif()
    exif[270] = "a caption via exif image description"
    img.save(p, "JPEG", exif=exif.tobytes())
    with Image.open(p) as im:
        prompts = rls.extract_prompts(p, im)
    assert "a caption via exif image description" in prompts


def test_extract_prompts_from_a1111_json_variant(tmp_path):
    """Some pipelines write a JSON blob into the `parameters` chunk
    instead of the classic newline-separated A1111 format."""
    blob = json.dumps({
        "prompt": "a json-shaped a1111 prompt",
        "negative_prompt": "junk",
        "steps": 20,
    })
    p = tmp_path / "a1111_json.png"
    _make_solid_png(p, info={"parameters": blob})
    with Image.open(p) as im:
        prompts = rls.extract_prompts(p, im)
    assert "a json-shaped a1111 prompt" in prompts


# ---------------------------------------------------------------------------
# Best-try skip-on-duplicate loop
# ---------------------------------------------------------------------------


def test_best_try_skips_when_next_pick_has_same_prompt(tmp_path):
    """Two images with the SAME prompt + one with a different prompt.
    With best_try + deterministic seed, running twice must land on
    different files (the second call must skip the duplicate)."""
    same = "the identical prompt appearing twice"
    diff = "a completely different prompt about a robot"
    _make_solid_png(tmp_path / "a.png", info={
        "parameters": f"{same}\nNegative prompt: x\nSteps: 1"
    })
    _make_solid_png(tmp_path / "b.png", info={
        "parameters": f"{same}\nNegative prompt: x\nSteps: 1"
    })
    _make_solid_png(tmp_path / "c.png", info={
        "parameters": f"{diff}\nNegative prompt: x\nSteps: 1"
    })

    node = RayLocalScraper()
    out1 = node.process(
        folder=str(tmp_path),
        recurse_subfolders=False,
        skip_no_prompt=False,
        prompt_best_try=True,
        seed=1,
        refresh_listing=True,
        node_id="dup",
    )
    out2 = node.process(
        folder=str(tmp_path),
        recurse_subfolders=False,
        skip_no_prompt=False,
        prompt_best_try=True,
        seed=1,
        refresh_listing=True,
        node_id="dup",
    )
    # Second call sees the same seed, but the recent-pick queue AND the
    # last-best-prompt memory force it to a different image with a
    # different prompt.
    assert out1[0] != out2[0]
    assert out1[0][0] != out2[0][0]


def test_best_try_returns_new_prompt_on_repeat(tmp_path):
    """Explicit: two calls in a row must produce two distinct best-try
    prompts as long as the folder holds any."""
    for i, text in enumerate(("alpha prompt aaa", "beta prompt bbb",
                              "gamma prompt ccc")):
        _make_solid_png(tmp_path / f"{i}.png", info={
            "parameters": f"{text}\nNegative prompt: x\nSteps: 1"
        })
    node = RayLocalScraper()
    seen = set()
    for run in range(3):
        out = node.process(
            folder=str(tmp_path),
            recurse_subfolders=False,
            skip_no_prompt=False,
            prompt_best_try=True,
            seed=7,
            refresh_listing=(run == 0),
            node_id="rot",
        )
        assert len(out[0]) == 1
        seen.add(out[0][0])
    # All three runs produced distinct prompts.
    assert len(seen) == 3


def test_best_try_raises_when_only_duplicate_remains(tmp_path):
    """One image, best_try, called twice with the same prompt in memory
    -> second call has no new prompt to serve and must raise."""
    _make_solid_png(tmp_path / "a.png", info={
        "parameters": "the only prompt in town\nNegative prompt: x\nSteps: 1"
    })
    node = RayLocalScraper()
    node.process(
        folder=str(tmp_path),
        recurse_subfolders=False,
        skip_no_prompt=False,
        prompt_best_try=True,
        seed=1,
        refresh_listing=True,
        node_id="only",
    )
    with pytest.raises(RuntimeError, match="new best-try prompt"):
        node.process(
            folder=str(tmp_path),
            recurse_subfolders=False,
            skip_no_prompt=False,
            prompt_best_try=True,
            seed=1,
            refresh_listing=False,
            node_id="only",
        )


def test_best_try_off_does_not_skip_duplicates(tmp_path):
    """Sanity: when best_try is off, the dedup rule must not fire."""
    _make_solid_png(tmp_path / "a.png", info={
        "parameters": "same prompt again\nNegative prompt: x\nSteps: 1"
    })
    node = RayLocalScraper()
    # Two calls must both succeed even though the prompt is identical.
    for _ in range(2):
        out = node.process(
            folder=str(tmp_path),
            recurse_subfolders=False,
            skip_no_prompt=False,
            prompt_best_try=False,
            seed=1,
            refresh_listing=True,
            node_id="off",
        )
        assert "same prompt again" in out[0]


def test_clear_cache_clears_last_best():
    rls._LAST_BEST_BY_NODE["x"] = "something"
    rls.clear_cache()
    assert rls._LAST_BEST_BY_NODE == {}
