"""FTMO simulator (spec 05 §5) — flags a breach, passes a safe path."""

from src.backtest.ftmo_sim import FtmoTracker


def test_breach_when_equity_crosses_daily_floor():
    t = FtmoTracker(initial=100_000, balance_0000=100_000)  # daily floor 95_000
    assert t.update(96_000) is False
    assert t.update(94_999) is True       # crossed the 5% daily floor
    assert t.breaches == 1


def test_overall_floor_breach():
    t = FtmoTracker(initial=100_000, balance_0000=100_000)  # overall floor 90_000
    assert t.update(89_999) is True


def test_safe_path_never_breaches():
    t = FtmoTracker(initial=100_000, balance_0000=100_000)
    for eq in (100_500, 99_000, 97_000, 101_000):
        t.update(eq)
    assert t.breached is False
    assert t.breaches == 0
