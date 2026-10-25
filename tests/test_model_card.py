"""The benchmark grammar, layout and run contract; sampling doubles never load weights."""
from types import SimpleNamespace
from datetime import datetime
from unittest.mock import Mock

import numpy as np
from PIL import Image
import pytest
import torch

import model_card as card
import ray_model_card as node
import comfy.latent_formats as formats


@pytest.mark.parametrize("line,caption,positive,negative", [
    ("prompt", "prompt", "prompt", ""),
    ("prompt|bad", "prompt", "prompt", "bad"),
    ("cap::prompt", "cap", "prompt", ""),
    ("cap::prompt|bad", "cap", "prompt", "bad"),
    (r"a\|b::p\::q|n\|x", "a|b", "p::q", "n|x"),
    (r"\+a", "+a", "+a", ""), (r"\=a", "=a", "=a", ""),
    (r"a\\b", "a\\b", "a\\b", ""),
    ("a|b::c|d", "a", "a", "b::c|d"),
    ("  cap :: positive | negative  ", "cap", "positive", "negative"),
])
def test_prompt_grammar(line, caption, positive, negative):
    entry = card.parse_config("\n + A\n" + line).categories[0].entries[0]
    assert (entry.caption, entry.positive, entry.negative) == (caption, positive, negative)


def test_title_order_whitespace_and_exact_config():
    text = "\r\n = Version 1.2\r\n\r\n + Z\r\np\r\n + A\r\nq\r\n"
    parsed = card.parse_config(text)
    assert parsed.config == text
    assert parsed.title == "Version 1.2"
    assert [c.name for c in parsed.categories] == ["Z", "A"]
    assert card.parse_config("+A\np").title is None
    assert card.parse_config("+A\na+b=c").categories[0].entries[0].positive == "a+b=c"


@pytest.mark.parametrize("config,line,message", [
    ("p", 1, "before any category"), ("+\np", 1, "Category name is empty"),
    ("+A", 1, "no prompts"), ("+A\np\n+B", 3, "no prompts"),
    ("=a\n=b\n+A\np", 2, "Duplicate title"), ("=\n+A\np", 1, "Title is empty"),
    ("+A\ncap::|bad", 2, "Positive prompt is empty"),
    ("+A\n::p", 2, "Caption is empty"), ("+A\np\\", 2, "Malformed escaped"),
    ("+A\np\\q", 2, "Malformed escaped"), ("", 1, "At least one category"),
])
def test_errors(config, line, message):
    with pytest.raises(ValueError, match=f"line {line}:") as caught:
        card.parse_config(config)
    assert message in str(caught.value)


@pytest.mark.parametrize("mode,expected", [("fixed", [100]*3), ("increment", [101,102,103]), ("decrement", [99,98,97])])
def test_seed_order(mode, expected):
    plan = card.make_plan(card.parse_config("+Z\na\nb\n+A\nc"), 100, mode)
    assert [p.seed for p in plan] == expected
    assert [(p.index,p.category_index,p.column,p.category) for p in plan] == [(0,0,0,"Z"),(1,0,1,"Z"),(2,1,0,"A")]


def test_seed_wrap_and_random(monkeypatch):
    benchmark = card.parse_config("+A\na\nb")
    assert card.make_plan(benchmark, 0, "decrement")[0].seed == card.SEED_MAX
    assert card.make_plan(benchmark, card.SEED_MAX, "increment")[0].seed == 0
    values = iter([9, 42])
    monkeypatch.setattr(card.secrets, "randbits", lambda bits: next(values))
    assert [p.seed for p in card.make_plan(benchmark, 0, "randomize")] == [9,42]


@pytest.mark.parametrize("counts", [(1,), (4,), (3,3), (6,4,5), (20,1)])
@pytest.mark.parametrize("size", [(1024,1024),(768,1024),(1536,768)])
def test_layout(counts, size):
    parsed = card.parse_config("\n".join("+C" + str(i) + "\n" + "\n".join("p" for _ in range(n)) for i,n in enumerate(counts)))
    layout = card.calculate_layout(parsed, 3001, *size)
    assert layout == card.calculate_layout(parsed, 3001, *size)
    assert layout.columns == max(counts)
    assert layout.xs[0] == layout.margin
    assert abs((layout.card_width - layout.xs[-1] - layout.thumbnail_width) - layout.margin) <= 1
    assert abs(layout.thumbnail_height - layout.thumbnail_width * size[1] / size[0]) <= .5
    assert layout.row_y(len(counts)-1) + layout.category_block_height + layout.margin == layout.card_height


def test_reserved_cells_and_preview():
    benchmark = card.parse_config("+A\na\nb\n+B\nc")
    plan = card.make_plan(benchmark, 0, "fixed")
    layout = card.calculate_layout(benchmark, 800, 64, 96)
    thumbs = [Image.new("RGB", (layout.thumbnail_width,layout.thumbnail_height), color) for color in ("red","green","blue")]
    with card.compose_card(benchmark,plan,thumbs,layout,"TITLE","DATE") as image:
        y = layout.row_y(1) + layout.category_header_height + 5
        assert image.getpixel((layout.xs[0]+5,y)) == (0,0,255)
        assert image.getpixel((layout.xs[1]+5,y)) == (0,0,0)
        assert image.getpixel((0,0)) == (0,0,0)
    for thumb in thumbs:
        thumb.close()


@pytest.mark.parametrize("source,key", [("{widget:12.unet_name}", "unet_name"),("{widget:12.ckpt_name}", "ckpt_name")])
def test_naming(source,key):
    prompt = {"12":{"inputs":{key:r"folder\My Model.v1.safetensors"}}}
    auto = node.selected_name(source,prompt)
    assert card.resolve_title(card.parse_config("+A\np"),auto) == ("My Model.v1","My Model.v1")
    assert card.resolve_title(card.parse_config("=CUSTOM NAME\n+A\np"),auto)[0] == "CUSTOM NAME"
    assert card.resolve_title(card.parse_config("+A\np"),node.selected_name(source,{}))[0] == "MODEL CARD"


@pytest.mark.parametrize("template,expected", [
    ("  My model / comparison: v1.2  ", "My model / comparison: v1.2"),
    ("Benchmark {widget:12.unet_name} - seed {widget:13.seed}", "Benchmark My Model.v1 - seed 42"),
    ("{widget:12.unet_name|8}", "My Model"),
    ("Run {date} at {time}", "Run 2026-10-23 at 14-32-05"),
    ("{datetime}", "2026-10-23T14-32-05"),
    ("{widget:99.missing}", ""),
    ("{widget:13.enabled}", "true"),
    ("CFG {widget:13.cfg}", "CFG 7"),
    ("{widget:13.text}", "a cat / a dog?"),
    ("{widget:13.braces}", "_date_"),
])
def test_card_name_templates(template, expected):
    prompt = {"12": {"inputs": {"unet_name": r"folder\My Model.v1.safetensors"}},
              "13": {"inputs": {"seed": 42, "cfg": 7.0, "enabled": True, "text": "a cat / a dog?", "braces": "{date}"}}}
    assert node.selected_name(template, prompt, datetime(2026, 10, 23, 14, 32, 5)) == expected


def test_report_keeps_markdown_and_config_exact():
    config = '=Test\r\n+A\r\ncaption::a ``` tricky ` prompt|negative\r\n'
    parsed = card.parse_config(config)
    plan = card.make_plan(parsed,100,"increment")
    report = card.make_report(parsed,plan,"Test","Auto","DATE",{"steps":20},card.calculate_layout(parsed,800,64,64))
    for text in [config,"- Seed: 101","- Index: 0","row/category 1, column 1","caption","negative","Steps: 20","````text"]:
        assert text in report


@pytest.mark.parametrize("duration,expected", [
    (0, "00:00:00.00 (0.00 seconds)"),
    (.125, "00:00:00.12 (0.12 seconds)"),
    (123.456, "00:02:03.46 (123.46 seconds)"),
    (3600.999, "01:00:01.00 (3601.00 seconds)"),
    (90061.25, "25:01:01.25 (90061.25 seconds)"),
])
def test_report_runtime_format(duration, expected):
    benchmark = card.parse_config("+A\np")
    report = card.make_report(benchmark, card.make_plan(benchmark, 0, "fixed"), "Test", "", "DATE", {},
                              card.calculate_layout(benchmark, 800, 64, 64), runtime_seconds=duration)
    assert f"- Runtime: {expected}" in report


@pytest.fixture
def pipeline(monkeypatch):
    vae = SimpleNamespace(latent_channels=4,latent_dim=2,output_channels=3,spacial_compression_decode=lambda:8,decode=lambda x:x)
    model = SimpleNamespace(get_model_object=lambda name: formats.SDXL() if name == "latent_format" else SimpleNamespace(unet_config={}))
    clip = SimpleNamespace(tokenize=Mock(side_effect=lambda text,**kw:text),
                           encode_from_tokens_scheduled=Mock(side_effect=lambda tokens:[[torch.ones(1,1,2),{}]]))
    calls = []
    def sample(model,seed,steps,cfg,sampler,scheduler,positive,negative,latent,**kw):
        calls.append((seed,latent["samples"].shape,positive))
        return ({"samples":latent["samples"]},)
    monkeypatch.setattr(node.nodes,"common_ksampler",sample)
    monkeypatch.setattr(node.nodes.VAEDecode,"decode",lambda self,vae,latent:(torch.full((1,64,64,3),len(calls)/10),))
    return model,clip,vae,calls


def run(pipeline, **kwargs):
    model,clip,vae,_ = pipeline
    return node.RayModelCard().generate(model,clip,vae,**{"image_width":64,"image_height":64,"card_width":512,"preview_width":256,
                                       "config":"+A\none\ntwo\n+B\nthree", **kwargs})


def test_complete_run(pipeline):
    full,preview,images,report = run(pipeline,seed=100,seed_mode="increment")
    assert [c[0] for c in pipeline[3]] == [101,102,103]
    assert images.shape == (3,64,64,3)
    assert images[:,0,0,0].tolist() == pytest.approx([.1,.2,.3])
    assert full.shape[2] == 512 and preview.shape[2] == 256
    with Image.fromarray((full[0].numpy()*255).round().astype(np.uint8)) as pil:
        with pil.resize((256,preview.shape[1]),Image.Resampling.LANCZOS) as reduced:
            np.testing.assert_array_equal((preview[0].numpy()*255).round().astype(np.uint8), np.array(reduced))
    assert report.index("one") < report.index("two") < report.index("three")


@pytest.mark.parametrize("kwargs,title", [
    ({"card_name": "My model / comparison: v1.2"}, "My model / comparison: v1.2"),
    ({"card_name": ""}, "MODEL CARD"),
    ({"card_name": "Widget title", "config": "=Config title\n+A\np"}, "Config title"),
    ({"card_name": "Benchmark {widget:12.unet_name}",
      "prompt": {"12": {"inputs": {"unet_name": "folder/My Model.v1.safetensors"}}}}, "Benchmark My Model.v1"),
])
def test_card_name_reaches_rendered_card_and_report(pipeline, monkeypatch, kwargs, title):
    compose = Mock(wraps=card.compose_card)
    monkeypatch.setattr(card, "compose_card", compose)
    report = run(pipeline, **kwargs)[3]
    assert compose.call_args.args[4] == title
    assert f"\n{title}\n" in report


@pytest.mark.parametrize("template", ["{counter}", "{index}", "{input}", "{unknown}"])
def test_invalid_card_name_fails_before_sampling(pipeline, template):
    with pytest.raises(ValueError):
        run(pipeline, card_name=template)
    assert pipeline[3] == []


def test_runtime_includes_validation_generation_render_and_output_conversion(pipeline, monkeypatch):
    clock = [100.0]
    monkeypatch.setattr(node, "perf_counter", lambda: clock[0])

    def timed(function, seconds):
        def call(*args, **kwargs):
            result = function(*args, **kwargs)
            clock[0] += seconds
            return result
        return call

    monkeypatch.setattr(card, "parse_config", timed(card.parse_config, 1))
    monkeypatch.setattr(node, "generate_image", timed(node.generate_image, 2))
    monkeypatch.setattr(card, "compose_card", timed(card.compose_card, 3))
    monkeypatch.setattr(node, "image_tensor", timed(node.image_tensor, 4))
    _, _, _, report = run(pipeline)
    # Validation + three generations + compositing + two output conversions.
    assert "- Runtime: 00:00:18.00 (18.00 seconds)" in report


def test_parse_failure_never_encodes_or_samples(pipeline):
    with pytest.raises(ValueError,match="line 3"):
        run(pipeline,config="+A\none\n+B")
    pipeline[1].tokenize.assert_not_called()
    assert pipeline[3] == []


def test_failed_generation_never_composes_and_closes_thumbnails(pipeline,monkeypatch):
    generate = node.generate_image
    def fail(*args):
        if args[3].index == 1:
            raise RuntimeError("sampling failed")
        return generate(*args)
    monkeypatch.setattr(node,"generate_image",fail)
    compose = Mock()
    monkeypatch.setattr(card,"compose_card",compose)
    closed = []
    original = Image.Image.close
    monkeypatch.setattr(Image.Image,"close",lambda self:(closed.append(self),original(self))[1])
    with pytest.raises(RuntimeError,match="index 1.*category 'A'.*column 2.*line 3"):
        run(pipeline)
    compose.assert_not_called()
    assert closed


def test_interruption_propagates(pipeline,monkeypatch):
    monkeypatch.setattr(node,"generate_image",Mock(side_effect=node.mm.InterruptProcessingException()))
    with pytest.raises(node.mm.InterruptProcessingException):
        run(pipeline)


@pytest.mark.parametrize("latent,family,channels,dim,scale", [
    (formats.SDXL,"standard",4,2,8), (formats.Flux,"flux",16,2,8),
    (formats.Flux2,"flux2",128,2,16), (formats.Flux2,"flux3",128,2,16),
    (formats.Flux2,"moss_image",128,2,16), (formats.Wan21,"krea2",16,3,8),
    (formats.Wan21,"anima",16,3,8), (formats.Wan21,"qwen_image",16,3,8),
    (formats.SD3,"lumina2",16,2,8), (formats.QwenImage21,"qwen_image21",64,2,16),
])
def test_real_native_latent_formats(latent,family,channels,dim,scale):
    model = SimpleNamespace(get_model_object=lambda key:latent() if key=="latent_format" else SimpleNamespace(unet_config={"image_model":family}))
    vae = SimpleNamespace(latent_channels=channels,latent_dim=dim,output_channels=3,spacial_compression_decode=lambda:scale,decode=lambda x:x)
    actual,_,shape = node.model_spec(model,vae,1024,768)
    assert actual == family
    assert shape == (1,channels) + ((1,) if dim==3 else ()) + (768//scale,1024//scale)


def test_unsupported_model_and_vae_fail_before_generation(pipeline):
    model,clip,vae,calls = pipeline
    model.get_model_object = lambda name: formats.StableAudio1() if name=="latent_format" else SimpleNamespace(unet_config={"image_model":"audio"})
    with pytest.raises(ValueError,match="unsupported latent"):
        run(pipeline)
    assert not calls


def test_vae_mismatch_and_unaligned_dimensions_fail_early(pipeline):
    pipeline[2].latent_channels = 16
    with pytest.raises(ValueError,match="VAE does not match"):
        run(pipeline)
    pipeline[2].latent_channels = 4
    with pytest.raises(ValueError,match="divisible by 8"):
        run(pipeline,image_width=65)
    assert not pipeline[3]


def test_guidance_uses_native_conditioning_and_original_model(pipeline):
    model = pipeline[0]
    model.get_model_object = lambda name: formats.SDXL() if name=="latent_format" else SimpleNamespace(unet_config={"guidance_embed":True})
    _,_,_,report = run(pipeline)
    assert all(call[2][0][1]["guidance"] == 3.5 for call in pipeline[3])
    assert "Effective guidance: 3.5" in report
    pipeline[3].clear()
    run(pipeline,guidance_mode="disabled")
    assert all("guidance" not in call[2][0][1] for call in pipeline[3])


def test_output_budget_and_preview_do_not_upscale(pipeline):
    with pytest.raises(ValueError,match="CPU output/compositing budget|retained images/card buffers"):
        run(pipeline,image_width=16384,image_height=16384,memory_limit_mb=256)
    assert not pipeline[3]
    full,preview,_,_ = run(pipeline,preview_width=2048)
    assert torch.equal(full,preview)


@pytest.mark.parametrize("kwargs,message", [
    ({"cfg":float("nan")},"CFG"),({"steps":0},"steps"),({"denoise":2},"denoise"),
    ({"max_images":2},"requests 3 images"),({"sampler_name":"missing"},"sampler"),
    ({"preview_width":0},"preview width"),({"guidance_mode":"bad"},"guidance mode"),
])
def test_preflight_settings(pipeline,kwargs,message):
    # Width overrides are supplied directly rather than duplicated by run().
    with pytest.raises(ValueError,match=message):
        run(pipeline,**kwargs)
    assert not pipeline[3]


def test_default_is_useful_and_no_title():
    parsed = card.parse_config(card.DEFAULT_CONFIG)
    assert parsed.title is None
    assert len(parsed.categories) == 11
    assert [category.name for category in parsed.categories] == [
        "ANIMALS", "PEOPLE", "BODY", "EXPRESSIONS", "POSES", "FRAMING",
        "LOCATIONS", "PROPS", "STYLES", "TEXT", "COMPLEX"]
    assert all(len(category.entries) == 6 for category in parsed.categories)
    assert len(card.make_plan(parsed,0,"fixed")) == 66
    assert node.RayModelCard.OUTPUT_NODE
    assert node.RayModelCard.RETURN_TYPES == ("IMAGE","IMAGE","IMAGE","STRING")
