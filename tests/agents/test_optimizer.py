"""Generic optimizer core (spec 06 §5) — pure search-space + ranking logic."""

import pytest

from src.agents.optimizer import (
    apply_overrides, axis_values, build_diff, eligible, enumerate_candidates,
    expand_grid, grid_size, rank, refine_space, sample_random)


def test_axis_values_range_int_float_and_list():
    assert axis_values({"min": 10, "max": 50, "step": 10}) == [10, 20, 30, 40, 50]
    assert axis_values({"min": 0.25, "max": 0.35, "step": 0.05}) == [0.25, 0.30, 0.35]
    assert axis_values({"values": [1, 2, 7]}) == [1, 2, 7]
    assert axis_values([3, 4]) == [3, 4]


def test_grid_size_and_expand():
    space = {"a": {"values": [1, 2, 3]}, "b": {"min": 0, "max": 1, "step": 1}}
    assert grid_size(space) == 6
    grid = expand_grid(space)
    assert len(grid) == 6
    assert {"a": 2, "b": 1} in grid


def test_random_returns_full_grid_when_small_and_is_deterministic():
    space = {"a": {"values": [1, 2]}, "b": {"values": [3, 4]}}
    assert len(sample_random(space, budget=99)) == 4          # grid <= budget -> full grid
    big = {"x": {"min": 0, "max": 100, "step": 1}, "y": {"min": 0, "max": 100, "step": 1}}
    s1 = sample_random(big, budget=20, seed=7)
    s2 = sample_random(big, budget=20, seed=7)
    assert len(s1) == 20 and s1 == s2                         # deterministic for a seed
    assert len({tuple(sorted(c.items())) for c in s1}) == 20  # all distinct


def test_enumerate_methods():
    space = {"a": {"values": [1, 2, 3]}}
    assert len(enumerate_candidates(space, "grid")) == 3
    assert len(enumerate_candidates(space, "coarse_to_fine")) == 3   # coarse pass = grid
    with pytest.raises(ValueError):
        enumerate_candidates(space, "bogus")


def test_refine_space_narrows_numeric_and_pins_values():
    space = {"n": {"min": 0, "max": 10, "step": 2}, "c": {"values": ["a", "b"]}}
    fine = refine_space(space, {"n": 6, "c": "b"})
    assert fine["n"]["step"] == 1.0                # half of 2
    assert fine["n"]["min"] == 4.0 and fine["n"]["max"] == 8.0
    assert fine["c"] == {"values": ["b"]}          # non-numeric axis pinned to winner


def test_apply_overrides_sets_dotted_paths():
    base = {"name": "S", "regime": {"er_threshold": 0.30, "atr_floor_pips": 4}}
    out = apply_overrides(base, {"regime.er_threshold": 0.35, "regime.atr_floor_pips": 6})
    assert out["regime"]["er_threshold"] == 0.35 and out["regime"]["atr_floor_pips"] == 6
    assert base["regime"]["er_threshold"] == 0.30   # base untouched (deep copy)


def test_build_diff_records_from_and_to():
    base = {"regime": {"er_threshold": 0.30}}
    diff = build_diff(base, {"regime.er_threshold": 0.35})
    assert diff[0].param == "regime.er_threshold"
    assert diff[0].from_value == 0.30 and diff[0].to_value == 0.35


def _r(oos, passed=True, severe=False, stitched=False):
    return {"oos_expectancy": oos, "in_sample_expectancy": oos, "sharpe": 1.0,
            "profit_factor": 1.5, "gates_passed": passed, "severe_collapse": severe,
            "stitched_collapse": stitched}


def test_rank_filters_gates_and_collapse_then_sorts():
    results = [
        _r(0.40, passed=False),          # gate fail -> excluded
        _r(0.35),                        # eligible
        _r(0.50, severe=True),           # severe fold -> excluded
        _r(0.20),                        # eligible
        _r(0.45, stitched=True),         # stitched collapse -> excluded
    ]
    ranked = rank(results, "oos_expectancy")
    assert [round(r["oos_expectancy"], 2) for r in ranked] == [0.35, 0.20]
    assert all(eligible(r) for r in ranked)


def test_rank_rejects_unknown_objective():
    with pytest.raises(ValueError):
        rank([_r(0.3)], "made_up_metric")


def test_build_diff_skips_no_op_changes():
    base = {"regime": {"er_threshold": 0.30, "atr_floor_pips": 5.0}}
    diff = build_diff(base, {"regime.er_threshold": 0.32, "regime.atr_floor_pips": 5})
    params = [d.param for d in diff]
    assert params == ["regime.er_threshold"]          # 5.0 == 5 -> dropped
