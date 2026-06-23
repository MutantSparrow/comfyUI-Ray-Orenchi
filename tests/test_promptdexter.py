"""Tests for ray_promptdexter. Network mocked. Run with: pytest tests/test_promptdexter.py"""

from collections import deque
from unittest.mock import patch, MagicMock

import pytest
import torch

import ray_promptdexter as rpd
from ray_promptdexter import RayPromptDexter


@pytest.fixture(autouse=True)
def reset_globals():
    rpd._SITEMAP_CACHE = None
    rpd._RECENT_BY_NODE.clear()
    yield
    rpd._SITEMAP_CACHE = None
    rpd._RECENT_BY_NODE.clear()


def _mock_response(content_bytes=None, text=None, status=200):
    resp = MagicMock()
    resp.status_code = status
    resp.content = content_bytes if content_bytes is not None else (text or "").encode("utf-8")
    resp.text = text if text is not None else (content_bytes or b"").decode("utf-8", errors="replace")
    resp.raise_for_status = MagicMock()
    return resp


# --- sitemap parsing -------------------------------------------------------


SIMPLE_URLSET = b"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://promptdexter.com/</loc></url>
  <url><loc>https://promptdexter.com/prompt/alpha-one</loc></url>
  <url><loc>https://promptdexter.com/prompt/beta-two</loc></url>
  <url><loc>https://promptdexter.com/prompts/people</loc></url>
  <url><loc>https://promptdexter.com/prompt/</loc></url>
  <url><loc>https://promptdexter.com/prompt/gamma-three</loc></url>
</urlset>
"""

SITEMAP_INDEX = b"""<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap><loc>https://promptdexter.com/sitemap-1.xml</loc></sitemap>
  <sitemap><loc>https://promptdexter.com/sitemap-2.xml</loc></sitemap>
</sitemapindex>
"""

CHILD_1 = b"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://promptdexter.com/prompt/a</loc></url>
  <url><loc>https://promptdexter.com/prompt/b</loc></url>
</urlset>
"""

CHILD_2 = b"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://promptdexter.com/prompt/b</loc></url>
  <url><loc>https://promptdexter.com/prompt/c</loc></url>
</urlset>
"""


def test_sitemap_filters_to_prompt_paths():
    with patch.object(rpd, "_http_get", return_value=_mock_response(content_bytes=SIMPLE_URLSET)):
        urls = rpd._load_sitemap(force_refresh=True, timeout=10)
    assert urls == [
        "https://promptdexter.com/prompt/alpha-one",
        "https://promptdexter.com/prompt/beta-two",
        "https://promptdexter.com/prompt/gamma-three",
    ]


def test_sitemap_index_recurses_and_dedupes():
    responses = {
        rpd._SITEMAP_URL: _mock_response(content_bytes=SITEMAP_INDEX),
        "https://promptdexter.com/sitemap-1.xml": _mock_response(content_bytes=CHILD_1),
        "https://promptdexter.com/sitemap-2.xml": _mock_response(content_bytes=CHILD_2),
    }

    def fake_get(url, timeout, retries=1):
        return responses[url]

    with patch.object(rpd, "_http_get", side_effect=fake_get):
        urls = rpd._load_sitemap(force_refresh=True, timeout=10)
    assert urls == [
        "https://promptdexter.com/prompt/a",
        "https://promptdexter.com/prompt/b",
        "https://promptdexter.com/prompt/c",
    ]


def test_sitemap_empty_pool_raises():
    empty = b"""<?xml version="1.0"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://promptdexter.com/</loc></url>
</urlset>
"""
    with patch.object(rpd, "_http_get", return_value=_mock_response(content_bytes=empty)):
        with pytest.raises(RuntimeError, match="no /prompt URLs"):
            rpd._load_sitemap(force_refresh=True, timeout=10)


# --- prompt page parser ----------------------------------------------------


PAGE_PRIMARY = """<!doctype html>
<html><head><meta property="og:image" content="/images/explore/000.webp"></head>
<body>
<main>
  <h2>Prompt</h2>
  <section>A red fox\nsits in the snow.\nGolden hour light.</section>
  <img src="/images/explore/12345.webp" alt="fox">
</main>
</body></html>"""


PAGE_OG_FALLBACK = """<!doctype html>
<html><head>
  <meta property="og:description" content="A serene lake at dusk with mountain reflections.">
  <meta property="og:image" content="https://promptdexter.com/images/explore/777.webp">
</head>
<body><main></main></body></html>"""


PAGE_NO_IMAGE = """<!doctype html>
<html><body>
<main>
  <h2>Prompt</h2>
  <p>Just text and nothing visual on this one.</p>
</main>
</body></html>"""


def test_prompt_parser_primary_path():
    with patch.object(rpd, "_http_get", return_value=_mock_response(text=PAGE_PRIMARY)):
        text, image_url = rpd._fetch_prompt_page("https://promptdexter.com/prompt/x", timeout=10)
    assert "red fox" in text
    assert "\n" in text
    assert image_url == "https://promptdexter.com/images/explore/12345.webp"


def test_prompt_parser_og_description_fallback():
    with patch.object(rpd, "_http_get", return_value=_mock_response(text=PAGE_OG_FALLBACK)):
        text, image_url = rpd._fetch_prompt_page("https://promptdexter.com/prompt/y", timeout=10)
    assert "serene lake" in text
    assert image_url == "https://promptdexter.com/images/explore/777.webp"


def test_single_is_collapsed_multiline():
    with patch.object(rpd, "_http_get", return_value=_mock_response(text=PAGE_PRIMARY)):
        text, _ = rpd._fetch_prompt_page("https://promptdexter.com/prompt/x", timeout=10)
    single, multi, _ = rpd._build_outputs(text, None, timeout=10)
    assert "\n" in multi
    assert "\n" not in single
    assert "  " not in single
    assert single == multi.replace("\n", " ").replace("  ", " ").strip()


# --- image fallback --------------------------------------------------------


def test_no_image_returns_black_tensor():
    with patch.object(rpd, "_http_get", return_value=_mock_response(text=PAGE_NO_IMAGE)):
        text, image_url = rpd._fetch_prompt_page("https://promptdexter.com/prompt/z", timeout=10)
    assert image_url is None
    tensor = rpd._fetch_image_tensor(image_url, timeout=10)
    assert tensor.shape == (1, 1, 1, 3)
    assert tensor.dtype == torch.float32
    assert torch.all(tensor == 0)


# --- determinism -----------------------------------------------------------


URL_POOL = [
    "https://promptdexter.com/prompt/a",
    "https://promptdexter.com/prompt/b",
    "https://promptdexter.com/prompt/c",
    "https://promptdexter.com/prompt/d",
    "https://promptdexter.com/prompt/e",
]


def _stub_node(seed_value, node_id):
    node = RayPromptDexter()
    rpd._SITEMAP_CACHE = list(URL_POOL)
    with patch.object(rpd, "_fetch_prompt_page", return_value=("multi line\nbody", None)), \
         patch.object(rpd, "_fetch_image_tensor", return_value=torch.zeros((1, 1, 1, 3))):
        return node.process(
            seed=seed_value,
            force_refresh_sitemap=False,
            clear_cache=False,
            category_filter="",
            timeout=10,
            node_id=node_id,
        )


def test_two_instances_same_seed_same_url():
    rpd._RECENT_BY_NODE.clear()
    _stub_node(42, "node_A")
    cache_a = list(rpd._RECENT_BY_NODE["node_A"])
    rpd._RECENT_BY_NODE.clear()
    _stub_node(42, "node_B")
    cache_b = list(rpd._RECENT_BY_NODE["node_B"])
    assert cache_a == cache_b


def test_same_seed_skips_to_next_candidate():
    rpd._RECENT_BY_NODE.clear()
    _stub_node(7, "node_X")
    first = list(rpd._RECENT_BY_NODE["node_X"])
    _stub_node(7, "node_X")
    after_two = list(rpd._RECENT_BY_NODE["node_X"])
    assert len(after_two) == 2
    assert after_two[0] != after_two[1]


# --- cache eviction --------------------------------------------------------


def test_cache_evicts_at_20():
    big_pool = [f"https://promptdexter.com/prompt/p{i}" for i in range(50)]
    rpd._SITEMAP_CACHE = list(big_pool)
    rpd._RECENT_BY_NODE.clear()
    node = RayPromptDexter()
    with patch.object(rpd, "_fetch_prompt_page", return_value=("body", None)), \
         patch.object(rpd, "_fetch_image_tensor", return_value=torch.zeros((1, 1, 1, 3))):
        for i in range(25):
            node.process(
                seed=-1,
                force_refresh_sitemap=False,
                clear_cache=False,
                category_filter="",
                timeout=10,
                node_id="cache_test",
            )
    assert len(rpd._RECENT_BY_NODE["cache_test"]) == 20


# --- selection helper unit -------------------------------------------------


def test_select_url_skip_when_recent():
    import random as _r
    recent = deque(["https://promptdexter.com/prompt/a"], maxlen=20)
    rng = _r.Random(123)
    pick = rpd._select_url(URL_POOL, recent, rng, deterministic=True)
    assert pick != "https://promptdexter.com/prompt/a"


def test_select_url_falls_back_when_all_cached():
    import random as _r
    recent = deque(URL_POOL, maxlen=20)
    rng = _r.Random(123)
    pick = rpd._select_url(URL_POOL, recent, rng, deterministic=True)
    assert pick in URL_POOL
