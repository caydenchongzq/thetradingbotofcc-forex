"""Active-config resolution from the versioned store HEAD (spec 06 §6 / 07 §9)."""

from src.agents.config_store import ConfigStore
from src.agents.proposal import DiffEntry
from src.ops.runtime_config import resolve_strategy_config

BASE = {"config_version": 1, "regime": {"er_threshold": 0.30, "atr_floor_pips": 4.0}}


def test_falls_back_to_yaml_when_no_store(tmp_path):
    cfg, ver = resolve_strategy_config(tmp_path, {"regime": {"er_threshold": 0.30}}, 1)
    assert ver == 1
    assert cfg["regime"]["er_threshold"] == 0.30


def test_resolves_head_after_promotion(tmp_path):
    store = ConfigStore(tmp_path, BASE)
    store.promote(1, [DiffEntry("regime.atr_floor_pips", 4.0, 5.0)], "researcher", "human")
    cfg, ver = resolve_strategy_config(tmp_path, BASE, 1)
    assert ver == 2
    assert cfg["regime"]["atr_floor_pips"] == 5.0     # the promoted value is now active
    assert cfg["config_version"] == 2


def test_resolves_rolled_back_head(tmp_path):
    store = ConfigStore(tmp_path, BASE)
    store.promote(1, [DiffEntry("regime.atr_floor_pips", 4.0, 5.0)], "r", "human")
    store.rollback(1)
    cfg, ver = resolve_strategy_config(tmp_path, BASE, 1)
    assert ver == 1
    assert cfg["regime"]["atr_floor_pips"] == 4.0     # rollback restores the baseline
