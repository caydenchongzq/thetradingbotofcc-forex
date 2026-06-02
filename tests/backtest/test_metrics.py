"""Metric math (spec 05 §6) against hand fixtures."""

from src.backtest.metrics import (
    expectancy_r, max_drawdown, profit_factor, sharpe, win_rate,
)


def test_expectancy_and_winrate():
    r = [1.0, -1.0, 2.0, -1.0]   # mean 0.25
    assert expectancy_r(r) == 0.25
    assert win_rate(r) == 0.5


def test_profit_factor():
    pnls = [100, -50, 200, -50]   # wins 300 / losses 100 = 3.0
    assert profit_factor(pnls) == 3.0


def test_max_drawdown():
    # cum: 100, 50, 150, 30 -> peak 150 then 30 -> dd 120; earlier 100->50 dd 50.
    pnls = [100, -50, 100, -120]
    assert max_drawdown(pnls) == 120


def test_sharpe_zero_when_no_variance():
    assert sharpe([1.0, 1.0, 1.0]) == 0.0
