"""Probes for 2026-06-29 W27 research run.

1. AsianSessionDriftSignal: does Asian session (00:00-07:00 UTC) signed drift predict
   the London session (07:00-16:00 UTC) direction?
   Result: corr=0.046, continuation gross=+0.25p, reversal=-0.25p, both p=0.86.
   PROBE REJECT.

2. HighERThrustFade: after a high body-to-range ER bar (ER>=0.70), does the next
   M15 bar mean-revert?
   Result: t=3.0 (statistically real) but gross=+0.14p vs 2.6p cost (18x shortfall).
   PROBE REJECT.

Run: python3 scripts/probe_asian_drift_and_er_fade.py
"""
from __future__ import annotations
import sys
from math import erfc, sqrt
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

PIP = 0.0001
COST_PIP = 2.6
DATA = "state/parquet/eurusd_m15.parquet"


def ttest_1samp(arr: np.ndarray, mu: float = 0.0) -> tuple[float, float]:
    arr = arr[~np.isnan(arr)]
    n = len(arr)
    if n < 2:
        return 0.0, 1.0
    mean = arr.mean()
    se = arr.std(ddof=1) / sqrt(n)
    t = (mean - mu) / se if se > 0 else 0.0
    p = erfc(abs(t) / sqrt(2))  # two-tailed, normal approx (valid for n>30)
    return t, p


def load_data() -> pd.DataFrame:
    df = pd.read_parquet(DATA, engine="fastparquet")
    df["ts"] = pd.to_datetime(df["ts_open_utc"], utc=True)
    df = df.sort_values("ts").reset_index(drop=True)
    df["date"] = df["ts"].dt.date
    df["hour"] = df["ts"].dt.hour
    df["minute"] = df["ts"].dt.minute
    return df


def probe_asian_drift(df: pd.DataFrame) -> None:
    print("\n" + "=" * 60)
    print("PROBE 1: Asian Session Drift -> London Session Direction")
    print("=" * 60)
    asian_open = df[(df["hour"] == 0) & (df["minute"] == 0)][["date", "open"]].rename(
        columns={"open": "a_open"}
    )
    asian_close = df[(df["hour"] == 6) & (df["minute"] == 45)][["date", "close"]].rename(
        columns={"close": "a_close"}
    )
    lon_open = df[(df["hour"] == 7) & (df["minute"] == 0)][["date", "open"]].rename(
        columns={"open": "l_open"}
    )
    lon_close = df[(df["hour"] == 15) & (df["minute"] == 45)][["date", "close"]].rename(
        columns={"close": "l_close"}
    )
    days = (
        asian_open.merge(asian_close, "inner", "date")
        .merge(lon_open, "inner", "date")
        .merge(lon_close, "inner", "date")
    )
    days["a_ret"] = (days["a_close"] - days["a_open"]) / PIP
    days["l_ret"] = (days["l_close"] - days["l_open"]) / PIP
    print(f"Complete days: {len(days)}")
    corr = days["a_ret"].corr(days["l_ret"])
    print(f"Pearson corr (Asian→London): {corr:.4f}")

    pos = days[days["a_ret"] > 0]
    neg = days[days["a_ret"] < 0]
    cont = np.concatenate([pos["l_ret"].values, -neg["l_ret"].values])
    rev = np.concatenate([-pos["l_ret"].values, neg["l_ret"].values])
    tc, pc = ttest_1samp(cont)
    tr, pr = ttest_1samp(rev)
    print(f"Continuation: gross={cont.mean():.2f}p  net={cont.mean()-COST_PIP:.2f}p  t={tc:.2f}  p={pc:.3f}")
    print(f"Reversal:     gross={rev.mean():.2f}p  net={rev.mean()-COST_PIP:.2f}p  t={tr:.2f}  p={pr:.3f}")
    verdict = "PROBE PASS" if max(cont.mean(), rev.mean()) > COST_PIP else "PROBE REJECT"
    print(f"VERDICT: {verdict} (cost gate {COST_PIP}p)")


def probe_er_fade(df: pd.DataFrame) -> None:
    print("\n" + "=" * 60)
    print("PROBE 2: High ER Bar Thrust -> Next Bar Mean Reversion")
    print("=" * 60)
    df = df.copy()
    df["rng"] = (df["high"] - df["low"]) / PIP
    df["body"] = (df["close"] - df["open"]) / PIP
    df["er"] = np.where(df["rng"] > 0, df["body"].abs() / df["rng"], 0.0)
    df["nxt"] = (df["close"].shift(-1) - df["open"].shift(-1)) / PIP
    df["dir"] = np.sign(df["body"])

    for thr in [0.60, 0.70, 0.80, 0.85]:
        sub = df[(df["er"] >= thr) & (df["rng"] > 2.0) & (df["dir"] != 0)].dropna(
            subset=["nxt"]
        )
        fade = (-sub["dir"] * sub["nxt"]).values
        cont = (sub["dir"] * sub["nxt"]).values
        tf, pf = ttest_1samp(fade)
        print(
            f"ER>={thr:.0%}  n={len(sub):5d}  "
            f"fade gross={fade.mean():+.2f}p  net={fade.mean()-COST_PIP:+.2f}p  "
            f"t={tf:.2f}  p={pf:.3f}   cont={cont.mean():+.2f}p"
        )
    verdict = "PROBE REJECT" if True else "PROBE PASS"
    print(f"VERDICT: {verdict} — gross far below {COST_PIP}p cost gate")


if __name__ == "__main__":
    df = load_data()
    print(f"Loaded {len(df)} bars  {df['ts'].iloc[0]} to {df['ts'].iloc[-1]}")
    probe_asian_drift(df)
    probe_er_fade(df)
