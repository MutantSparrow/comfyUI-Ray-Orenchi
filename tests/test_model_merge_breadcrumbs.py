"""Numerical and large-layer regressions for Breadcrumbs merging."""
import math

import pytest
import torch
from safetensors.torch import load_file, save_file

import model_tools as tools


def reference(a, b, base, weight, top, bottom, ties):
    deltas = []
    for value in (a, b):
        delta = value - base
        magnitudes = delta.abs().flatten().double()
        lower = torch.quantile(magnitudes, bottom)
        upper = torch.quantile(magnitudes, 1 - top)
        deltas.append(delta * ((delta.abs() >= lower) & (delta.abs() <= upper)))
    da, db = deltas
    if ties:
        sign = (weight * da + (1 - weight) * db).sign()
        sign = torch.where(sign == 0, 1., sign)
        da, db = da * (da.sign() == sign), db * (db.sign() == sign)
        count = ((da != 0).float() + (db != 0).float()).clamp_min(1.)
        return base + (weight * da + (1 - weight) * db) / count
    return base + weight * da + (1 - weight) * db


@pytest.mark.parametrize("strategy", ["Breadcrumbs", "Breadcrumbs-TIES"])
@pytest.mark.parametrize("top,bottom", [(.1, .01), (0., 0.), (.25, .25)])
def test_breadcrumbs_matches_reference_without_mutating_inputs(strategy, top, bottom):
    a = torch.tensor([[0., -1., 3., -3.], [3., -5., 7., 11.]]).T
    b = torch.tensor([[0., 2., -3., -3.], [3., 6., -8., 10.]]).T
    base = torch.full_like(a, .5)
    originals = [value.clone() for value in (a, b, base)]
    actual = tools.blend(a, b, .4, strategy, base, top=top, bottom=bottom)
    expected = reference(a, b, base, .4, top, bottom, strategy.endswith("-TIES"))
    torch.testing.assert_close(actual, expected)
    for value, original in zip((a, b, base), originals):
        assert torch.equal(value, original)


def test_linear_quantile_above_torch_limit(monkeypatch):
    # A real oversized tensor exercises rank precision as well as selection.
    size = 2**24 + 3
    flat = torch.arange(size, dtype=torch.float32).flip(0)

    def no_quantile(*args, **kwargs):
        raise AssertionError("Large layers must not call torch.quantile")

    monkeypatch.setattr(torch, "quantile", no_quantile)
    for q in (0., .01, .375, .9, 1.):
        rank = q * (size - 1)
        index = math.floor(rank)
        lower = torch.tensor(float(index), dtype=flat.dtype)
        upper = torch.tensor(float(math.ceil(rank)), dtype=flat.dtype)
        expected = lower.lerp(upper, rank - index)
        torch.testing.assert_close(tools._linear_quantile(flat, q), expected, rtol=0, atol=0)
    assert flat[0] == size - 1 and flat[-1] == 0


@pytest.mark.parametrize("strategy", ["Breadcrumbs", "Breadcrumbs-TIES"])
def test_breadcrumbs_merges_real_oversized_layer(strategy):
    # 4096 x 4097 is just above the failing quantile size in older Torch builds.
    a = torch.ones(4096, 4097)
    a[::4] = .01
    a[1::4] = 100.
    b, base = a.neg(), torch.zeros_like(a)
    result = tools.blend(a, b, .75, strategy, base, top=.3, bottom=.3)
    assert result.shape == a.shape and result.dtype == a.dtype
    # Each tail has 25% of elements; both percentile cutoffs lie at magnitude 1.
    assert torch.count_nonzero(result[::4]) == 0
    assert torch.count_nonzero(result[1::4]) == 0
    expected = .75 if strategy.endswith("-TIES") else .5
    assert torch.all(result[2::4] == expected)
    assert torch.all(result[3::4] == expected)
    assert torch.all(a[::4] == .01) and torch.all(a[1::4] == 100.)
    assert torch.equal(b, -a) and torch.count_nonzero(base) == 0


@pytest.mark.parametrize("strategy", ["Breadcrumbs", "Breadcrumbs-TIES"])
@pytest.mark.parametrize("fast_merge", [False, True])
def test_breadcrumbs_file_and_ram_results_match_reference(tmp_path, strategy, fast_merge):
    values = [torch.arange(24, dtype=torch.float32).reshape(6, 4) - 7,
              torch.arange(24, dtype=torch.float32).reshape(6, 4).flip(0) - 12,
              torch.ones(6, 4)]
    paths = []
    for label, value in zip(("a", "b", "base"), values):
        path = tmp_path / f"{label}.safetensors"
        save_file({"proj.weight": value}, str(path))
        paths.append(path)
    destination = tmp_path / "merged.safetensors"
    asset, _ = tools.merge_models(*paths[:2], destination, strategy=strategy,
                                  weight=.4, base=paths[2], fmt="fp32", fast_merge=fast_merge)
    actual = (asset.tensors if fast_merge else load_file(asset.path))["proj.weight"]
    torch.testing.assert_close(actual, reference(*values, .4, .1, .01, strategy.endswith("-TIES")))
    assert destination.exists() is (not fast_merge)
    for path, original in zip(paths, values):
        assert torch.equal(load_file(str(path))["proj.weight"], original)


@pytest.mark.parametrize("strategy", ["Breadcrumbs", "Breadcrumbs-TIES"])
def test_breadcrumbs_empty_and_scalar_layers(strategy):
    empty = torch.empty(0)
    assert tools.blend(empty, empty, .5, strategy, empty).shape == (0,)
    actual = tools.blend(torch.tensor(3.), torch.tensor(7.), .5, strategy, torch.tensor(1.))
    expected = 3. if strategy.endswith("-TIES") else 5.
    assert actual.item() == expected
