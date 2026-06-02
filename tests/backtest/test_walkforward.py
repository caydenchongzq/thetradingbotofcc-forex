"""Walk-forward windowing + stability/collapse/lockbox (spec 05 §7)."""

from datetime import datetime, timedelta, timezone

from src.backtest.types import SimTrade, WFSpec
from src.backtest.walkforward import add_months, make_splits, walk_forward


def _period():
    return (datetime(2024, 1, 1, tzinfo=timezone.utc),
            datetime(2026, 1, 1, tzinfo=timezone.utc))


def test_add_months_rolls_year():
    assert add_months(datetime(2025, 11, 1, tzinfo=timezone.utc), 3).month == 2
    assert add_months(datetime(2025, 11, 1, tzinfo=timezone.utc), 3).year == 2026


def test_splits_reserve_lockbox_and_tile_dev():
    split = make_splits(_period(), WFSpec(12, 3, 3, lockbox_months=6))
    assert split.lockbox is not None
    assert split.lockbox[0] == datetime(2025, 7, 1, tzinfo=timezone.utc)
    assert len(split.dev_folds) == 6
    assert split.dev_folds[0][0] == datetime(2024, 1, 1, tzinfo=timezone.utc)


def test_trailing_stub_fold_merged():
    # 19-month dev period: 6 full quarters + a 1-month stub -> stub merges into prior fold.
    period = (datetime(2024, 1, 1, tzinfo=timezone.utc),
              datetime(2026, 2, 1, tzinfo=timezone.utc))   # 25 months, lockbox 6 -> dev 19
    split = make_splits(period, WFSpec(12, 3, 3, lockbox_months=6))
    last = split.dev_folds[-1]
    assert (last[1] - last[0]).days > 100   # merged, not a thin 1-month stub


def _trade(ts, r):
    return SimTrade(entry_ts=ts, exit_ts=ts, direction="long", entry_price=1.1,
                    exit_price=1.1, lots=0.1, sl_price=1.097, r_multiple=r,
                    pnl_usd=r * 100.0, gross_pips=0, net_pips=0, mae_pips=1, mfe_pips=1,
                    exit_reason="tp", commission_usd=1, entry_slippage_pips=0.2,
                    spread_at_entry_pips=0.4)


def _fill(start, end, r, every_days=4):
    out, t = [], start
    while t < end:
        out.append(_trade(t, r))
        t += timedelta(days=every_days)
    return out


def test_consistent_edge_no_collapse_mild_negative_ok():
    # All quarters solidly positive except one mildly negative (-0.05R) -> NOT a collapse.
    trades = _fill(datetime(2024, 1, 5, tzinfo=timezone.utc),
                   datetime(2024, 4, 1, tzinfo=timezone.utc), -0.05)
    trades += _fill(datetime(2024, 4, 1, tzinfo=timezone.utc),
                    datetime(2025, 7, 1, tzinfo=timezone.utc), 0.4)
    wfr = walk_forward(trades, _period(), WFSpec(12, 3, 3, lockbox_months=6),
                       initial=100_000, min_fold_trades=5)
    assert wfr.severe_collapse is False        # -0.05R is mild, above -0.25R floor
    assert wfr.stitched_collapse is False      # stitched stays well above 0.5x in-sample
    assert wfr.weak_folds == 1                 # surfaced as advisory


def test_severe_losing_fold_flagged():
    trades = _fill(datetime(2024, 1, 5, tzinfo=timezone.utc),
                   datetime(2024, 4, 1, tzinfo=timezone.utc), -0.8)   # catastrophic quarter
    trades += _fill(datetime(2024, 4, 1, tzinfo=timezone.utc),
                    datetime(2025, 7, 1, tzinfo=timezone.utc), 0.4)
    wfr = walk_forward(trades, _period(), WFSpec(12, 3, 3, lockbox_months=6),
                       initial=100_000, min_fold_trades=5)
    assert wfr.severe_collapse is True
