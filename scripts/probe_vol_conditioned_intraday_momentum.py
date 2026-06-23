"""Probe: does VOLATILITY-CONDITIONED intraday momentum clear cost on EURUSD M15?

Research-engine a-priori probe for 2026-06-23-vol-conditioned-intraday-momentum
(spec 08 stage 5, run BEFORE spending a trial — cf. the seasonality / false-break-fade /
volume-confirmed probes). It does NOT register a strategy, run a walk-forward, or append to
the trial ledger. It answers the one §4.3 question that differentiates this from the already
probe-rejected [[2026-06-07-intraday-ts-momentum]] (unconditional early->late corr 0.026,
+0.25 pip < cost):

  Gao-Han-Li-Zhou (SSRN 2440866 / JFE 2018): the first-window return predicts the last-window
  return, and the predictability is STRONGER on high first-window-volatility days (R^2 -> 3.3%).
  The prior probe measured the UNCONDITIONAL drift. This probe measures the CONDITIONAL drift
  on the high-first-window-vol subset — the exact conditioning the closed seasonality family
  said could reopen it ("...unless a conditioning mechanism lifts per-leg drift above ~3 pip").

Decision rule (a-priori): worth a trial ONLY if, on the high-vol subset, the directional
signed drift of the last window exceeds the round-trip cost stack (~2.6 pip incl. real
hour-of-day spread) with a clear positive gradient in the conditioner AND >= ~200 tradeable
days. Else probe-reject, no trial.

Run:  python3 scripts/probe_vol_conditioned_intraday_momentum.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

PIP = 0.0001
DATA = "state/parquet/eurusd_m15.parquet"

# Cost stack (matches the probe/harness convention): commission 3 USD/lot/side = 0.3 pip/side,
# slippage 0.2 pip/side -> 0.4 pip RT fixed; + the actual entry-hour spread (paid once).
FIXED_RT_PIP = 0.3 * 2 + 0.2 * 2  # 1.0 pip fixed round-trip (commission + slippage)


def load() -> pd.DataFrame:
    df = pd.read_parquet(DATA)
    df["ts"] = pd.to_datetime(df["ts_open_utc"], utc=True)
    df = df.set_index("ts").sort_index()
    df["date"] = df.index.date
    df["hm"] = df.index.strftime("%H:%M")
    return df


def window_return_pips(day: pd.DataFrame, start: str, end: str):
    """Signed return (close@last bar in window - open@first bar in window) in pips."""
    w = day.between_time(start, end)
    if len(w) < 2:
        return None
    return (w["close"].iloc[-1] - w["open"].iloc[0]) / PIP


def window_realized_vol_pips(day: pd.DataFrame, start: str, end: str):
    """Sum of |bar log-ish returns| over the window, in pips (the conditioner)."""
    w = day.between_time(start, end)
    if len(w) < 2:
        return None
    return float((w["close"].diff().abs().sum()) / PIP)


def entry_spread_pip(day: pd.DataFrame, at: str) -> float:
    w = day.between_time(at, at)
    if len(w) == 0:
        return 1.0
    return float(w["spread_pips"].iloc[0])


def stats(signed: np.ndarray):
    n = len(signed)
    if n == 0:
        return 0, 0.0, 0.0
    return n, float(signed.mean()), float((signed > 0).mean())


def run_pair(df: pd.DataFrame, first: tuple[str, str], last: tuple[str, str],
             entry_at: str) -> None:
    rows = []
    for _, day in df.groupby("date"):
        r1 = window_return_pips(day, *first)
        r2 = window_return_pips(day, *last)
        v1 = window_realized_vol_pips(day, *first)
        if r1 is None or r2 is None or v1 is None:
            continue
        spr = entry_spread_pip(day, entry_at)
        rows.append((r1, r2, v1, spr))
    if not rows:
        print(f"  [no data for {first}->{last}]")
        return
    a = np.array(rows, dtype=float)
    r1, r2, v1, spr = a[:, 0], a[:, 1], a[:, 2], a[:, 3]
    # directional follow-through: trade in sign(r1), capture r2; net cost = fixed + spread
    gross = np.sign(r1) * r2
    cost = FIXED_RT_PIP + spr
    net = gross - cost
    corr = float(np.corrcoef(r1, r2)[0, 1]) if len(r1) > 2 else float("nan")

    print(f"  pair first{first} -> last{last} (entry {entry_at}, mean spread {spr.mean():.2f}p)")
    n, g, w = stats(gross)
    nn, gn, wn = stats(net)
    print(f"    UNCONDITIONAL  n={n:4d}  corr(r1,r2)={corr:+.3f}  "
          f"gross_drift={g:+.2f}p  net={gn:+.2f}p  win={wn*100:.1f}%")
    # conditional on first-window realized vol terciles
    for label, lo, hi in [("low-vol  ", 0.0, 1 / 3), ("mid-vol  ", 1 / 3, 2 / 3),
                          ("HIGH-vol ", 2 / 3, 1.0)]:
        qlo, qhi = np.quantile(v1, lo), np.quantile(v1, hi)
        m = (v1 >= qlo) & (v1 <= qhi) if hi == 1.0 else (v1 >= qlo) & (v1 < qhi)
        gg = np.sign(r1[m]) * r2[m]
        cc = FIXED_RT_PIP + spr[m]
        nnet = gg - cc
        c2 = float(np.corrcoef(r1[m], r2[m])[0, 1]) if m.sum() > 2 else float("nan")
        n2, g2, _ = stats(gg)
        _, gn2, wn2 = stats(nnet)
        print(f"    {label} n={n2:4d}  corr={c2:+.3f}  gross={g2:+.2f}p  "
              f"net={gn2:+.2f}p  win={wn2*100:.1f}%")
    # also the top-quartile high-|r1| magnitude condition (alt conditioner)
    thr = np.quantile(np.abs(r1), 0.75)
    m = np.abs(r1) >= thr
    gg = np.sign(r1[m]) * r2[m]
    nnet = gg - (FIXED_RT_PIP + spr[m])
    n2, g2, _ = stats(gg)
    _, gn2, wn2 = stats(nnet)
    print(f"    top25%|r1| n={n2:4d}  gross={g2:+.2f}p  net={gn2:+.2f}p  win={wn2*100:.1f}%")
    print()


def main() -> int:
    df = load()
    print(f"data {df.index.min()} -> {df.index.max()}  ({df['date'].nunique()} days)")
    print(f"fixed round-trip cost (comm+slip) = {FIXED_RT_PIP:.2f} pip; + entry-hour spread\n")
    # Liquid-window pairs. First window = session-open hour; last window = a later LIQUID hour
    # (avoid the thin late-US hour that killed LateSessionDrift). Entry at start of last window.
    pairs = [
        (("07:00", "07:59"), ("13:00", "13:59"), "13:00"),  # London-open -> NY-open
        (("07:00", "07:59"), ("14:00", "15:59"), "14:00"),  # London-open -> NY-AM overlap
        (("08:00", "08:59"), ("13:00", "14:59"), "13:00"),  # post-London -> NY-AM
        (("12:00", "12:59"), ("15:00", "16:59"), "15:00"),  # pre-NY -> NY core
        (("00:00", "06:59"), ("07:00", "08:59"), "07:00"),  # Asia -> London-open (carry-over)
    ]
    for first, last, entry in pairs:
        run_pair(df, first, last, entry)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
