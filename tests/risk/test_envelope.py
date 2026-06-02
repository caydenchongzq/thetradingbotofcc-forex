"""FTMO envelope math (spec 02 §2)."""

from src.risk.envelope import compute_envelope


def test_floors_and_budget_at_initial():
    e = compute_envelope(balance_0000=100_000, initial=100_000, equity=100_000)
    assert e.daily_floor_equity == 95_000
    assert e.overall_floor_equity == 90_000
    assert e.daily_budget_usd == 5_000
    assert e.daily_loss_used_usd == 0.0
    assert e.daily_pct_used == 0.0
    assert e.overall_dd_usd == 0.0


def test_daily_loss_used_tracks_equity_drop():
    e = compute_envelope(balance_0000=100_000, initial=100_000, equity=98_000)
    assert e.daily_loss_used_usd == 2_000
    assert e.daily_pct_used == 2_000 / 5_000


def test_budget_uses_balance_0000_not_initial_when_in_profit():
    # Up 2k on the day; daily budget is still 5% of INITIAL, floor floats with balance.
    e = compute_envelope(balance_0000=102_000, initial=100_000, equity=101_000)
    assert e.daily_budget_usd == 5_000
    assert e.daily_floor_equity == 97_000
    assert e.daily_loss_used_usd == 1_000  # 102k -> 101k


def test_overall_dd_never_negative():
    e = compute_envelope(balance_0000=100_000, initial=100_000, equity=105_000)
    assert e.overall_dd_usd == 0.0
    assert e.daily_loss_used_usd == 0.0
