from src.engine.indicators import efficiency_ratio, percentile_rank, wilder_atr


def test_er_trend_vs_chop():
    up = [1.0 + 0.001 * i for i in range(20)]
    chop = [1.0 + (0.001 if i % 2 else 0.0) for i in range(20)]
    assert efficiency_ratio(up, 14) > 0.95
    assert efficiency_ratio(chop, 14) < 0.30


def test_er_flat_is_zero_guarded():
    assert efficiency_ratio([1.0] * 20, 14) == 0.0


def test_wilder_atr_positive():
    highs = [1.0 + 0.001 * i + 0.0005 for i in range(20)]
    lows = [1.0 + 0.001 * i - 0.0005 for i in range(20)]
    closes = [1.0 + 0.001 * i for i in range(20)]
    assert wilder_atr(highs, lows, closes, 14) > 0


def test_percentile_rank():
    assert percentile_rank(5, [1, 2, 3, 4, 5]) == 1.0
    assert percentile_rank(0, [1, 2, 3]) == 0.0
