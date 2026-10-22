import importlib.util
import json
import math
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import torch
from PIL import Image, PngImagePlugin

import ray_folders as folders
import folders_routes as routes


def picture(path, size=(17, 23), prompt="A small\nred cat", workflow=True):
    info = PngImagePlugin.PngInfo()
    info.add_text("parameters", prompt + "\nNegative prompt: blur\nSteps: 20")
    if workflow:
        info.add_text("workflow", json.dumps({"nodes": [{"id": 1, "type": "CLIPTextEncode", "widgets_values": [prompt]}], "links": []}))
    Image.new("RGB", size, "red").save(path, pnginfo=info)


@pytest.fixture
def media(tmp_path):
    picture(tmp_path / "cat.png")
    picture(tmp_path / "dog.png", (31, 11), "A large dog")
    nested = tmp_path / "nested"
    nested.mkdir()
    picture(nested / "bird.png", (8, 8), "A bird")
    (tmp_path / "ignored.txt").write_text("not media")
    return tmp_path


@pytest.mark.parametrize("name,query,expected", [
    ("Red_Cat_01.png", "red cat", True), ("Red_Cat_01.png", "rdct", True),
    ("Cat portrait.png", "catt", True), ("Bär im Wald.png", "bar wld", True),
    ("cat.png", "zzzz", False), ("cat.png", "", True), ("dog.png", "cat", False),
])
def test_fuzzy_names(name, query, expected):
    assert folders.fuzzy_match(name, query) is expected


def test_scan_types_recursion_filter_and_stable_sort(media):
    assert [x["id"] for x in folders.scan(media)["items"]] == ["cat.png", "dog.png"]
    assert len(folders.scan(media, {"recursive": True})["items"]) == 3
    assert [x["name"] for x in folders.scan(media, {"sort": "name", "descending": True})["items"]] == ["dog.png", "cat.png"]
    assert folders.scan(media, {"types": ["audio"]})["items"] == []
    assert [x["name"] for x in folders.scan(media, name_filter="catt")["items"]] == ["cat.png"]


def test_paths_cannot_escape_the_open_folder(media, tmp_path):
    outside = tmp_path.parent / (tmp_path.name + "_outside.png")
    picture(outside)
    try:
        with pytest.raises(ValueError):
            folders.resolve_media(media, "../" + outside.name)
        with pytest.raises(ValueError):
            folders.resolve_media(media, str(outside))
        with pytest.raises(ValueError):
            folders.resolve_media(media, "nested/bird.png", recursive=False)
        assert folders.resolve_media(media, "nested/bird.png").name == "bird.png"
        with pytest.raises(ValueError):
            folders.resolve_media(media, "ignored.txt")
    finally:
        outside.unlink()


def test_sessions_are_scoped_and_expire(media, monkeypatch):
    token = routes.grant(media, False)
    assert routes.resolve(token, "cat.png").name == "cat.png"
    with pytest.raises(ValueError):
        routes.resolve(token, "nested/bird.png")
    monkeypatch.setattr(routes.time, "monotonic", lambda: 10**20)
    with pytest.raises(ValueError, match="expired"):
        routes.resolve(token, "cat.png")


def test_metadata_uses_scraper_and_retains_workflow(media):
    info = folders.metadata(media / "cat.png")
    assert info["has_prompt"] and any("red cat" in p for p in info["prompts"])
    assert (info["width"], info["height"]) == (17, 23)
    assert info["workflow"]["nodes"][0]["type"] == "CLIPTextEncode"
    assert "\n" not in folders.prompt_text(info, {"prompt_format": "single"})
    assert "\n" in folders.prompt_text(info, {"prompt_format": "multiline"})


def test_metadata_sidecar_changes_invalidate_the_cache(tmp_path):
    path = tmp_path / "plain.png"
    Image.new("RGB", (5, 5)).save(path)
    assert not folders.metadata(path)["has_prompt"]
    path.with_suffix(".txt").write_text("A new sidecar caption")
    assert folders.metadata(path)["prompts"] == ["A new sidecar caption"]


def test_original_image_sizes_and_prompt_path_pairing(media, monkeypatch):
    monkeypatch.setitem(sys.modules, "comfy", SimpleNamespace(model_management=SimpleNamespace(throw_exception_if_processing_interrupted=lambda: None)))
    monkeypatch.setitem(sys.modules, "comfy.model_management", sys.modules["comfy"].model_management)
    selection = json.dumps({"folder": str(media), "files": ["dog.png", "cat.png"]})
    result = folders.RayFolders().browse(str(media), selected_files=selection)["result"]
    images, videos, audio, prompts, paths = result
    assert [tuple(t.shape) for t in images] == [(1, 23, 17, 3), (1, 11, 31, 3)]
    assert images[0].dtype == torch.float32 and images[0].min() >= 0 and images[0].max() <= 1
    assert not videos and not audio and len(prompts) == len(paths) == 2
    assert "red cat" in prompts[0] and "dog" in prompts[1]
    assert [Path(p).name for p in paths] == ["cat.png", "dog.png"]


def test_no_selection_empty_folder_and_stale_selection(media):
    assert folders.RayFolders.OUTPUT_NODE and all(folders.RayFolders.OUTPUT_IS_LIST)
    assert math.isnan(folders.RayFolders.IS_CHANGED())
    assert folders.RayFolders().browse("")["result"] == ([], [], [], [], [""])
    result = folders.RayFolders().browse(str(media))["result"]
    assert result == ([], [], [], [], [str(media)])
    stale = json.dumps({"folder": str(media / "nested"), "files": ["cat.png"]})
    assert folders.RayFolders().browse(str(media), selected_files=stale)["result"] == result


def test_run_always_rescans_and_drops_deleted_selection(media):
    before = folders.RayFolders().browse(str(media))
    picture(media / "new.png")
    after = folders.RayFolders().browse(str(media))
    assert after["ui"]["ray_folders"][0]["counts"]["image"] == before["ui"]["ray_folders"][0]["counts"]["image"] + 1
    selection = json.dumps({"folder": str(media), "files": ["new.png"]})
    (media / "new.png").unlink()
    assert folders.RayFolders().browse(str(media), selected_files=selection)["result"][-1] == [str(media)]


def test_thumbnail_orientation_cache_and_invalidation(media, tmp_path, monkeypatch):
    cache = tmp_path / "cache"
    cache.mkdir()
    monkeypatch.setattr(folders, "_cache_dir", lambda: cache)
    thumb = folders.thumbnail(media / "cat.png")
    assert folders.thumbnail(media / "cat.png") == thumb
    with Image.open(thumb) as image:
        assert image.format == "JPEG" and max(image.size) <= 384
    picture(media / "cat.png", (30, 40))
    assert folders.thumbnail(media / "cat.png") != thumb


def test_mixed_native_media_outputs(media, monkeypatch):
    audio_path = media / "sound.wav"
    audio_path.write_bytes(b"fixture")
    video_path = media / "movie.mp4"
    video_path.write_bytes(b"fixture")
    monkeypatch.setitem(sys.modules, "comfy", SimpleNamespace(model_management=SimpleNamespace(throw_exception_if_processing_interrupted=lambda: None)))
    monkeypatch.setitem(sys.modules, "comfy.model_management", sys.modules["comfy"].model_management)
    monkeypatch.setitem(sys.modules, "comfy_api", SimpleNamespace())
    monkeypatch.setitem(sys.modules, "comfy_api.latest", SimpleNamespace(InputImpl=SimpleNamespace(VideoFromFile=lambda path: {"video_file": path})))
    monkeypatch.setitem(sys.modules, "comfy_extras", SimpleNamespace())
    monkeypatch.setitem(sys.modules, "comfy_extras.nodes_audio", SimpleNamespace(load=lambda path: (torch.zeros(2, 160), 16000)))
    original_metadata = folders.metadata
    monkeypatch.setattr(folders, "metadata", lambda path: {"prompts": ["An audio caption"]} if Path(path).suffix == ".wav" else {"prompts": []} if Path(path).suffix == ".mp4" else original_metadata(path))
    selected = json.dumps({"folder": str(media), "files": ["sound.wav", "movie.mp4", "cat.png"]})
    images, videos, audio, prompts, paths = folders.RayFolders().browse(str(media), selected_files=selected)["result"]
    assert len(images) == len(videos) == len(audio) == 1
    assert videos[0]["video_file"] == str(video_path)
    assert audio[0]["waveform"].shape == (1, 2, 160) and audio[0]["sample_rate"] == 16000
    assert [Path(p).name for p in paths] == ["cat.png", "movie.mp4", "sound.wav"]
    assert prompts[1:] == ["", "An audio caption"]


def test_prompt_best_or_all_keeps_one_string_per_file():
    info = {"prompts": ["Short", "Longer\npositive prompt"]}
    assert folders.prompt_text(info, {"best_prompt": True}) == "Longer\npositive prompt"
    assert folders.prompt_text(info, {"best_prompt": False, "prompt_format": "single"}) == "Short Longer positive prompt"


def test_deleted_folder_or_disconnected_drive_is_nonfatal(tmp_path):
    missing = tmp_path / "removed_drive" / "pictures"
    result = folders.RayFolders().browse(str(missing))
    assert result["result"] == ([], [], [], [], [str(missing)])
    assert "Folder unavailable" in result["ui"]["ray_folders"][0]["error"]


def test_rename_invalidates_old_selection_and_updates_count(media):
    selected = json.dumps({"folder": str(media), "files": ["cat.png"]})
    (media / "cat.png").rename(media / "renamed.png")
    output = folders.RayFolders().browse(str(media), selected_files=selected)
    assert output["result"] == ([], [], [], [], [str(media)])
    assert output["ui"]["ray_folders"][0]["counts"]["image"] == 2


def test_total_counts_include_media_hidden_by_filters(media):
    scan = folders.scan(media, {"types": ["audio"]}, "nothing")
    assert scan["items"] == [] and scan["counts"]["image"] == 2


def test_large_listing_never_opens_image_pixels(tmp_path, monkeypatch):
    monkeypatch.setattr(folders, "folder_path", lambda value: tmp_path)
    monkeypatch.setattr(folders.os, "walk", lambda *a, **k: iter([(str(tmp_path), [], [f"image_{i:06}.png" for i in range(100000)])]))
    monkeypatch.setattr(Path, "stat", lambda self, **kwargs: SimpleNamespace(st_size=64, st_mtime=1, st_mtime_ns=1000))
    monkeypatch.setattr(Path, "resolve", lambda self, **kwargs: self)
    monkeypatch.setattr(Path, "is_dir", lambda self: self == tmp_path)
    monkeypatch.setattr(Image, "open", lambda *a, **k: (_ for _ in ()).throw(AssertionError("Listings must not decode images")))
    result = folders.scan(tmp_path)
    assert result["counts"]["image"] == len(result["items"]) == 100000
    assert result["items"][0]["name"] == "image_000000.png"
    assert result["items"][-1]["name"] == "image_099999.png"


def test_removed_during_decode_is_skipped_without_losing_other_selections(media, monkeypatch):
    monkeypatch.setitem(sys.modules, "comfy", SimpleNamespace(model_management=SimpleNamespace(throw_exception_if_processing_interrupted=lambda: None)))
    monkeypatch.setitem(sys.modules, "comfy.model_management", sys.modules["comfy"].model_management)
    original = folders.metadata
    def metadata(path):
        if Path(path).name == "cat.png":
            raise FileNotFoundError("Drive removed while reading")
        return original(path)
    monkeypatch.setattr(folders, "metadata", metadata)
    selection = json.dumps({"folder": str(media), "files": ["cat.png", "dog.png"]})
    result = folders.RayFolders().browse(str(media), selected_files=selection)
    assert len(result["result"][0]) == 1
    assert Path(result["result"][-1][0]).name == "dog.png"
    assert "cat.png" in result["ui"]["ray_folders"][0]["warnings"][0]


def test_corrupt_media_is_skipped_without_breaking_other_outputs(media, monkeypatch):
    monkeypatch.setitem(sys.modules, "comfy", SimpleNamespace(model_management=SimpleNamespace(throw_exception_if_processing_interrupted=lambda: None)))
    monkeypatch.setitem(sys.modules, "comfy.model_management", sys.modules["comfy"].model_management)
    (media / "broken.png").write_bytes(b"not an image")
    selection = json.dumps({"folder": str(media), "files": ["broken.png", "dog.png"]})
    output = folders.RayFolders().browse(str(media), selected_files=selection)
    assert len(output["result"][0]) == 1
    assert output["ui"]["ray_folders"][0]["warnings"] == ["Unavailable: broken.png"]


def test_prompt_search_fuzzy_terms_across_fields_and_negative_exclusion(media):
    assert folders.search_files(media, ["cat.png", "dog.png"], "small")['matches'] == ['cat.png']
    assert folders.search_files(media, ["cat.png", "dog.png"], "smal red")['matches'] == ['cat.png']
    assert folders.search_files(media, ["cat.png", "dog.png"], "cat small")['matches'] == ['cat.png']
    assert folders.search_files(media, ["cat.png", "dog.png"], "blur")['matches'] == []
    assert [i['name'] for i in folders.scan(media, name_filter='large')['items']] == ['dog.png']
    assert folders.search_match('0001.png', ['Bär im Wäld'], 'bar wald')
    assert not folders.search_match('0001.png', ['A very long unrelated collection of words'], 'zebra')


def test_search_cache_invalidation_sidecars_deletion_and_rename(tmp_path, monkeypatch):
    cache = tmp_path / 'cache'; cache.mkdir()
    monkeypatch.setattr(folders, '_cache_dir', lambda: cache)
    path = tmp_path / 'plain.png'; Image.new('RGB', (5, 5)).save(path)
    sidecar = path.with_suffix('.png.txt'); sidecar.write_text('A violet sunset')
    assert folders.search_files(tmp_path, ['plain.png'], 'violet')['matches'] == ['plain.png']
    original = folders._search_prompts
    monkeypatch.setattr(folders, '_search_prompts', lambda path: (_ for _ in ()).throw(AssertionError('Cached prompts should be reused')))
    assert folders.search_files(tmp_path, ['plain.png'], 'sunset')['matches'] == ['plain.png']
    monkeypatch.setattr(folders, '_search_prompts', original)
    sidecar.write_text('An emerald forest')
    assert folders.search_files(tmp_path, ['plain.png'], 'emerald')['matches'] == ['plain.png']
    assert folders.search_files(tmp_path, ['plain.png'], 'violet')['matches'] == []
    path.rename(tmp_path / 'renamed.png')
    assert folders.search_files(tmp_path, ['plain.png'], 'emerald')['unavailable'] == ['plain.png']
    assert folders.search_files(tmp_path, ['../outside.png'], 'anything')['unavailable'] == ['../outside.png']


def test_search_png_metadata_without_decoding_original_pixels(tmp_path, monkeypatch):
    info = PngImagePlugin.PngInfo()
    info.add_text('parameters', 'A turquoise ocean\nNegative prompt: noise\nSteps: 20', zip=True)
    info.add_itxt('Description', 'A café near the beach', zip=True)
    # Include text after IDAT and EXIF: these are why ordinary Pillow getexif()
    # decodes the original PNG, defeating metadata-only indexing.
    info.add(b'tEXt', b'Comment\0A golden lighthouse', after_idat=True)
    exif = Image.Exif(); exif[270] = 'A coral reef'
    path = tmp_path / 'metadata.png'; Image.new('RGB', (4096, 3072)).save(path, pnginfo=info, exif=exif)
    original_load = PngImagePlugin.PngImageFile.load
    def load(image, *args, **kwargs):
        assert image.size == (1, 1), 'Prompt search must not decode original PNG pixels'
        return original_load(image, *args, **kwargs)
    monkeypatch.setattr(PngImagePlugin.PngImageFile, 'load', load)
    for query in ('turquoise', 'cafe', 'lighthouse', 'coral'):
        assert folders.search_files(tmp_path, ['metadata.png'], query)['matches'] == ['metadata.png']


def test_prompt_search_skips_corrupt_files_and_cache_failure(media, monkeypatch):
    (media / 'broken.png').write_bytes(b'invalid png')
    monkeypatch.setattr(folders, '_cache_dir', lambda: (_ for _ in ()).throw(OSError('Cache drive disconnected')))
    result = folders.search_files(media, ['broken.png', 'cat.png', 'removed.png'], 'small')
    assert result == {'matches': ['cat.png'], 'unavailable': ['broken.png', 'removed.png']}


def test_connected_prompt_filter_matches_workflow_outputs(media, monkeypatch):
    monkeypatch.setitem(sys.modules, 'comfy', SimpleNamespace(model_management=SimpleNamespace(throw_exception_if_processing_interrupted=lambda: None)))
    monkeypatch.setitem(sys.modules, 'comfy.model_management', sys.modules['comfy'].model_management)
    selection = json.dumps({'folder': str(media), 'files': ['dog.png', 'cat.png']})
    output = folders.RayFolders().browse(str(media), name_filter='small red', selected_files=selection)['result']
    assert len(output[0]) == 1 and [Path(p).name for p in output[-1]] == ['cat.png']
