"""Strategy registry (spec 01): config selects the strategy; dev strategies stay isolated."""

import pytest

from src.engine import available, build_strategy, register
from src.engine.strategy import SessionBreakoutER


def test_default_builds_session_breakout():
    s = build_strategy({})                       # no name -> default
    assert isinstance(s, SessionBreakoutER)
    assert s.name == "SessionBreakoutER"


def test_builds_by_name():
    s = build_strategy({"name": "SessionBreakoutER", "config_version": 3})
    assert isinstance(s, SessionBreakoutER)
    assert s.config_version == 3


def test_unknown_name_raises():
    with pytest.raises(KeyError):
        build_strategy({"name": "NopeNotReal"})


def test_available_lists_builtin():
    assert "SessionBreakoutER" in available()


def test_register_and_build_dev_strategy():
    class _DevStrat:
        name = "DevStrat"
        config_version = 0
        def __init__(self, config):
            self.config = config
        def warmup_bars(self):
            return 1

    register("DevStrat", _DevStrat)
    assert "DevStrat" in available()
    s = build_strategy({"name": "DevStrat", "foo": 1})
    assert isinstance(s, _DevStrat)
    assert s.config["foo"] == 1


def test_register_duplicate_different_factory_rejected():
    register("Dup", lambda c: object())
    with pytest.raises(ValueError):
        register("Dup", lambda c: object())     # different factory -> refuse


def test_build_strategy_needs_only_a_dict_no_store():
    # Pure construction from a plain dict — no state_dir / config store touched, so a dev
    # strategy can be backtested without any chance of mutating live production state.
    s = build_strategy({"name": "SessionBreakoutER"})
    assert s is not None
