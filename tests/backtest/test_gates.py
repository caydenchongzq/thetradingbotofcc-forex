"""Gates + deflated Sharpe (spec 05 §6, §8)."""

from src.backtest.gates import GatesConfig, all_passed, deflated_sharpe, evaluate_gates


def test_dsr_decreases_with_more_trials():
    # Same observed Sharpe; more cumulative trials -> higher bar -> lower DSR (monotone).
    kw = dict(sr=0.25, n=300, skew=0.0, kurt=3.0)
    d1 = deflated_sharpe(**kw, trials=1)
    d10 = deflated_sharpe(**kw, trials=10)
    d100 = deflated_sharpe(**kw, trials=100)
    assert d1 >= d10 >= d100
    assert 0.0 <= d100 <= d1 <= 1.0


def test_ftmo_breach_fails_gates_regardless_of_metrics():
    great = {"expectancy_r": 0.5, "profit_factor": 3.0, "sharpe": 2.0, "sortino": 3.0,
             "trade_count": 500, "_skew": 0.0, "_kurt": 3.0}
    gates = evaluate_gates(great, ftmo_breaches=1, trial_count=1)
    assert gates["ftmo_no_breach"].passed is False
    assert all_passed(gates) is False   # one breach sinks the whole run


def test_clean_strong_strategy_passes():
    good = {"expectancy_r": 0.3, "profit_factor": 1.8, "sharpe": 1.4, "sortino": 2.0,
            "trade_count": 400, "_skew": 0.1, "_kurt": 3.0}
    gates = evaluate_gates(good, ftmo_breaches=0, trial_count=1)
    assert gates["ftmo_no_breach"].passed
    assert all_passed(gates)


def test_thin_sample_fails_size_gate():
    g = {"expectancy_r": 0.3, "profit_factor": 1.8, "sharpe": 1.4, "sortino": 2.0,
         "trade_count": 12, "_skew": 0.0, "_kurt": 3.0}
    gates = evaluate_gates(g, ftmo_breaches=0, trial_count=1)
    assert gates["sample_size"].passed is False
