"""Versioned config store + promotion mutex (spec 06 §6/§8)."""

import pytest

from src.agents.config_store import ConfigStore, StaleParentError, apply_diff
from src.agents.proposal import DiffEntry

BASE = {"config_version": 1, "regime": {"er_threshold": 0.30}, "exits": {"atr_mult_sl": 1.2}}


def _diff():
    return [DiffEntry("regime.er_threshold", 0.30, 0.38)]


def test_apply_diff_sets_nested_path():
    out = apply_diff(BASE, _diff())
    assert out["regime"]["er_threshold"] == 0.38
    assert BASE["regime"]["er_threshold"] == 0.30   # original untouched (deep copy)


def test_bootstrap_head_is_v1(tmp_path):
    store = ConfigStore(tmp_path, BASE)
    assert store.head_version() == 1
    assert store.get_config(1)["regime"]["er_threshold"] == 0.30


def test_promote_is_monotonic_and_cas_guarded(tmp_path):
    store = ConfigStore(tmp_path, BASE)
    v2 = store.promote(1, _diff(), author="researcher", approval="human")
    assert v2 == 2
    assert store.head_version() == 2
    assert store.get_config(2)["regime"]["er_threshold"] == 0.38
    assert store.get_config(2)["config_version"] == 2
    # A proposal branched from the now-stale v1 must be refused (compare-and-swap).
    with pytest.raises(StaleParentError):
        store.promote(1, [DiffEntry("exits.atr_mult_sl", 1.2, 1.5)], "r", "human")


def test_rollback_restores_exact_parent(tmp_path):
    store = ConfigStore(tmp_path, BASE)
    store.promote(1, _diff(), "r", "human")
    assert store.head_version() == 2
    store.rollback(1)
    assert store.head_version() == 1
    assert store.get_config(store.head_version())["regime"]["er_threshold"] == 0.30


def test_promotion_lease_blocks_second_holder(tmp_path):
    from src.agents.config_store import LeaseHeldError
    store = ConfigStore(tmp_path, BASE)
    store.acquire_lease("p1")
    with pytest.raises(LeaseHeldError):
        store.acquire_lease("p2")
    store.release_lease()
    store.acquire_lease("p2")   # free now
