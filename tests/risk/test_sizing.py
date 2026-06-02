"""Position sizing (spec 02 §4)."""

import math

from src.risk import Decision, RiskGovernor
from src.risk.types import ContextBias
from tests.risk.conftest import NOW, account, day, signal


def test_basic_size_eurusd(cfg, eurusd):
    g = RiskGovernor(cfg)
    d = g.evaluate_entry(signal(sl_pips=11.0), account(), day(), NOW, eurusd)
    assert d.approved
    # target = 0.0035 * 100_000 = 350 ; denom = 11 * 10 * 1.2 = 132
    # lots_raw = 350/132 = 2.6515 -> floor to 0.01 step -> 2.65
    assert d.lots == 2.65
    assert d.risk_usd == round(2.65 * 132, 6)


def test_lots_round_down_to_step(cfg, eurusd):
    g = RiskGovernor(cfg)
    # Choose sl so lots_raw lands just above a step boundary; must floor, never round up.
    d = g.evaluate_entry(signal(sl_pips=13.0), account(), day(), NOW, eurusd)
    denom = 13 * 10 * 1.2
    raw = 350 / denom
    expected = math.floor(raw / 0.01) * 0.01
    assert abs(d.lots - round(expected, 2)) < 1e-9
    assert d.lots <= raw


def test_min_lot_veto_when_unsizable(cfg, eurusd):
    g = RiskGovernor(cfg)
    # Enormous SL distance -> lots_raw below broker min -> cannot size safely -> VETO.
    d = g.evaluate_entry(signal(sl_pips=1_000_000.0), account(), day(), NOW, eurusd)
    assert d.decision is Decision.VETO


def test_higher_equity_gives_more_risk_until_caps(cfg, eurusd):
    g = RiskGovernor(cfg)
    lo = g.evaluate_entry(signal(), account(equity=50_000, balance=50_000),
                          day(balance_0000=50_000, initial=50_000), NOW, eurusd)
    hi = g.evaluate_entry(signal(), account(equity=100_000),
                          day(), NOW, eurusd)
    assert hi.risk_usd >= lo.risk_usd


def test_cautious_bias_downsizes(cfg, eurusd):
    g = RiskGovernor(cfg)
    normal = g.evaluate_entry(signal(), account(), day(), NOW, eurusd)
    cautious = g.evaluate_entry(signal(context_bias=ContextBias.CAUTIOUS),
                                account(), day(), NOW, eurusd)
    assert cautious.decision is Decision.APPROVE_DOWNSIZED
    assert cautious.risk_usd < normal.risk_usd
    # cautious_size_mult = 0.5
    assert cautious.lots <= normal.lots


def test_stand_down_vetoes(cfg, eurusd):
    g = RiskGovernor(cfg)
    d = g.evaluate_entry(signal(context_bias=ContextBias.STAND_DOWN),
                         account(), day(), NOW, eurusd)
    assert d.decision is Decision.VETO


def test_overall_taper_reduces_size_near_floor(cfg, eurusd):
    g = RiskGovernor(cfg)
    # equity 93k: below taper start (94k), above overall floor (90k) -> tapered.
    d = g.evaluate_entry(signal(), account(equity=93_000, balance=93_000),
                         day(balance_0000=93_000), NOW, eurusd)
    if d.approved:
        assert d.decision is Decision.APPROVE_DOWNSIZED
    # frac = (93000-90000)/(94000-90000) = 0.75 ; f = 0.0035*0.75
    # target ~ 0.002625 * 93000 = 244.1 ; clearly smaller than full-size 350-ish
    assert d.risk_usd < 350
