"""Probe: does MAGNITUDE-CONDITIONED post-ECB-fix reversion clear cost on EURUSD M15?

Research-engine a-priori probe for 2026-06-17-ecb-fix-conditional-reversion
(spec 08 stage 5, run BEFORE spending a trial).

The academic basis (Krohn, JoF 2024 — 'Foreign Exchange Fixings and Returns around
the Clock', DOI 10.1111/jofi.13306):
  - FX dealers intermediate net demand for USD at the ECB fix (14:15 CET / 13:15 UTC
    winter, 12:15 UTC summer). They pre-hedge by accumulating USD ahead of the fix,
    causing EUR/USD to decline. After the fix they unwind inventory, causing EUR/USD
    to recover (W-shaped return pattern). Annualised returns of 13.6% for EUR/USD in
    the paper's 1999-2019 sample. The reversion is strongest in high-volatility periods.

Our variant (the §4.3-differentiating twist):
  - Rather than a fixed-clock directional leg (closed seasonality family), CONDITION on
    the magnitude of the pre-fix EUR decline. Only trade when the 09:00 UTC → fix-time
    move is large enough that it *may* lift post-fix drift above the ~2.6-pip cost stack.
  - Entry: LONG EURUSD at the bar after the fix (i.e., at the 14:15 CET bar open).
  - Stop: 1.5×ATR below entry (wide enough not to be noise-stopped by the fix candle).
  - Target: NOT measured here (we probe gross drift only; if probe passes, design the
    full exit geometry per spec 08 §5.8 rules).
  - Decision threshold: gross conditional drift > 2.6 pip AND n_cond >= 200 tradeable
    days. If not met, probe-reject (no trial).

ECB fix timing:
  European summer (CEST = UTC+2): 14:15 CEST = 12:15 UTC
  European winter (CET = UTC+1):  14:15 CET  = 13:15 UTC
  CET→CEST: last Sunday of March; CEST→CET: last Sunday of October.

Run:  python3 scripts/probe_ecb_fix_reversion.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

PIP = 0.0001
DATA = "state/parquet/eurusd_m15.parquet"

# Round-trip cost stack (same convention as all prior probes)
# commission: 3 USD/lot/side ≈ 0.3 pip/side → 0.6 pip RT
# slippage:   0.2 pip/side → 0.4 pip RT
# total fixed: 1.0 pip; + actual spread at entry hour
FIXED_RT_PIP = 1.0


def is_cest(dt: pd.Timestamp) -> bool:
    """Return True if the given UTC datetime falls in European Summer Time (CEST)."""
    year = dt.year
    # CET -> CEST: last Sunday of March at 01:00 UTC (02:00 CET -> 03:00 CEST)
    # CEST -> CET: last Sunday of October at 01:00 UTC (03:00 CEST -> 02:00 CET)
    import calendar
    def last_sunday(y: int, m: int) -> pd.Timestamp:
        # last Sunday of month m in year y, at 01:00 UTC
        last_day = calendar.monthrange(y, m)[1]
        ts2 = pd.Timestamp(y, m, last_day, 1, 0, 0, tz="UTC")
        weekday = ts2.weekday()  # Monday=0, Sunday=6
        days_back = (weekday + 1) % 7  # days since last Sunday
        return ts2 - pd.Timedelta(days=days_back)

    cest_start = last_sunday(year, 3)
    cest_end   = last_sunday(year, 10)
    return cest_start <= dt < cest_end


def fix_time_utc(dt_date_utc: pd.Timestamp) -> str:
    """Return the HH:MM UTC string of the ECB fix for the given date."""
    return "12:15" if is_cest(dt_date_utc) else "13:15"


def load() -> pd.DataFrame:
    df = pd.read_parquet(DATA)
    df["ts"] = pd.to_datetime(df["ts_open_utc"], utc=True)
    df = df.set_index("ts").sort_index()
    df["date"] = df.index.date
    return df


def daily_atr(day: pd.DataFrame, atr_period: int = 20) -> float:
    """Rough daily ATR from the day's M15 bars (simple: mean of bar H-L ranges)."""
    return float(((day["high"] - day["low"]) / PIP).mean())


def run_probe(df: pd.DataFrame) -> None:
    """
    For each trading day:
      1. Determine fix time in UTC (12:15 or 13:15 based on DST).
      2. Measure pre-fix window: 09:00 UTC → fix bar open (the building of pre-fix inventory).
      3. Measure post-fix window: fix bar open → fix+1h and fix+2h (the reversion).
      4. Compute gross conditional drift for the LONG post-fix trade.
    """
    print(f"data {df.index.min()} -> {df.index.max()}  ({df['date'].nunique()} total days)")
    print(f"fixed RT cost (comm+slip) = {FIXED_RT_PIP:.1f} pip; + actual entry spread\n")

    rows = []
    skipped = 0

    for date, day in df.groupby("date"):
        day_ts = pd.Timestamp(date, tz="UTC")

        # Fix time in UTC for this day
        fix_hm = fix_time_utc(day_ts)  # "12:15" or "13:15"
        fix_h, fix_m = int(fix_hm[:2]), int(fix_hm[3:])

        # Pre-fix window bars: 09:00 UTC inclusive to the bar BEFORE the fix bar
        pre_fix_start = "09:00"
        pre_fix_end_exclusive = f"{fix_h:02d}:{fix_m - 15:02d}" if fix_m >= 15 else f"{fix_h - 1:02d}:45"
        # actually just use between_time with the end one slot before the fix bar
        pre_end_h, pre_end_m = fix_h, fix_m - 15
        if pre_end_m < 0:
            pre_end_h -= 1
            pre_end_m += 60
        pre_end_str = f"{pre_end_h:02d}:{pre_end_m:02d}"

        pre_window = day.between_time("09:00", pre_end_str)
        if len(pre_window) < 4:  # need at least 1h of data
            skipped += 1
            continue

        # Fix bar and post-fix windows
        fix_bar = day.between_time(fix_hm, fix_hm)
        post_1h = day.between_time(fix_hm, f"{fix_h + 1:02d}:{fix_m:02d}")  # fix → fix+1h
        post_2h = day.between_time(fix_hm, f"{fix_h + 2:02d}:{fix_m:02d}")  # fix → fix+2h

        if len(fix_bar) == 0 or len(post_1h) < 2 or len(post_2h) < 3:
            skipped += 1
            continue

        # Pre-fix return (EUR/USD direction): negative = EUR fell before fix (USD appreciated)
        pre_return_pip = (pre_window["close"].iloc[-1] - pre_window["open"].iloc[0]) / PIP

        # Entry at open of fix bar (first bar of post_1h)
        entry_price = post_1h["open"].iloc[0]
        entry_spread = float(fix_bar["spread_pips"].iloc[0])

        # Post-fix return (LONG trade = buy at fix bar open, close at end of window)
        post_1h_pip = (post_1h["close"].iloc[-1] - entry_price) / PIP
        post_2h_pip = (post_2h["close"].iloc[-1] - entry_price) / PIP

        # ATR for the day (simple average H-L)
        atr_pip = daily_atr(day)

        # Pre-fix return in ATR units
        pre_ret_atr = pre_return_pip / atr_pip if atr_pip > 0 else 0.0

        rows.append({
            "date": date,
            "is_cest": is_cest(day_ts),
            "fix_hm": fix_hm,
            "pre_ret_pip": pre_return_pip,
            "pre_ret_atr": pre_ret_atr,
            "post_1h_pip": post_1h_pip,
            "post_2h_pip": post_2h_pip,
            "entry_spread": entry_spread,
            "atr_pip": atr_pip,
        })

    print(f"Valid days: {len(rows)}  Skipped (missing bars): {skipped}\n")
    if not rows:
        print("ERROR: No valid days.")
        return

    data = pd.DataFrame(rows)
    n_total = len(data)
    n_cest = data["is_cest"].sum()
    print(f"CEST days: {n_cest} ({n_cest / n_total * 100:.0f}%)  "
          f"CET days: {n_total - n_cest} ({(n_total - n_cest) / n_total * 100:.0f}%)\n")

    # Overall (unconditional) stats
    def report_subset(label: str, mask: pd.Series) -> None:
        sub = data[mask]
        n = len(sub)
        if n == 0:
            print(f"  {label}: n=0 (no data)")
            return
        cost = FIXED_RT_PIP + sub["entry_spread"].values
        # Gross: LONG after fix → capture post-fix return
        g1 = sub["post_1h_pip"].values   # gross 1-hour
        g2 = sub["post_2h_pip"].values   # gross 2-hour
        # Net for our LONG trade (we only take the LONG when pre_ret_pip < 0, i.e., EUR fell)
        net1 = g1 - cost
        net2 = g2 - cost
        wr1 = (net1 > 0).mean() * 100
        wr2 = (net2 > 0).mean() * 100
        print(f"  {label} (n={n}):")
        print(f"    1h post-fix:  gross={g1.mean():+.2f}p  net={net1.mean():+.2f}p  wr={wr1:.0f}%"
              f"  spread_mean={sub['entry_spread'].mean():.2f}p")
        print(f"    2h post-fix:  gross={g2.mean():+.2f}p  net={net2.mean():+.2f}p  wr={wr2:.0f}%\n")

    print("=" * 65)
    print("UNCONDITIONAL post-fix LONG (all days — always go LONG at 14:15 CET)")
    print("=" * 65)
    all_mask = pd.Series([True] * n_total, index=data.index)
    report_subset("all days", all_mask)

    # Only on days where EUR actually fell pre-fix (USD appreciation occurred)
    print("=" * 65)
    print("DIRECTIONAL FILTER: only trade on days where pre-fix EUR fell (pre_ret < 0)")
    print("=" * 65)
    neg_mask = data["pre_ret_pip"] < 0
    report_subset(f"pre_ret < 0 pip", neg_mask)

    # Magnitude conditioning on pre-fix return (ATR multiples)
    print("=" * 65)
    print("MAGNITUDE CONDITIONING: only trade when pre-fix EUR decline exceeds threshold")
    print("(hypothesis: larger pre-fix move -> stronger reversion)")
    print("=" * 65)
    for thresh in [0.25, 0.5, 0.75, 1.0, 1.25, 1.5]:
        mask = data["pre_ret_atr"] < -thresh  # EUR fell MORE than thresh*ATR
        n = mask.sum()
        if n < 10:
            print(f"  pre_ret < −{thresh:.2f}×ATR: n={n} (too few days, skip)")
            continue
        sub = data[mask]
        cost = FIXED_RT_PIP + sub["entry_spread"].values
        g1 = sub["post_1h_pip"].values
        g2 = sub["post_2h_pip"].values
        net1 = g1 - cost
        net2 = g2 - cost
        # Also: t-stat for gross_1h vs zero
        from scipy import stats as sp_stats
        t1, p1 = sp_stats.ttest_1samp(g1, 0.0)
        t2, p2 = sp_stats.ttest_1samp(g2, 0.0)
        print(f"  pre_ret < −{thresh:.2f}×ATR: n={n:3d}  "
              f"1h gross={g1.mean():+.2f}p (t={t1:+.2f},p={p1:.2f})  net={net1.mean():+.2f}p  wr1h={(net1>0).mean()*100:.0f}%  |  "
              f"2h gross={g2.mean():+.2f}p (t={t2:+.2f},p={p2:.2f})  net={net2.mean():+.2f}p")
    print()

    # High-vol conditioning (per Krohn: reversion stronger in high-vol periods)
    print("=" * 65)
    print("VOLATILITY CONDITIONING: conditional on daily ATR tercile")
    print("(Krohn 2024: 'reversion strongest in high-volatility periods')")
    print("=" * 65)
    for label, lo, hi in [("low-ATR  ", 0.0, 1/3), ("mid-ATR  ", 1/3, 2/3), ("HIGH-ATR ", 2/3, 1.0)]:
        qlo = data["atr_pip"].quantile(lo)
        qhi = data["atr_pip"].quantile(hi)
        mask = (data["atr_pip"] >= qlo) & (data["atr_pip"] < qhi if hi < 1.0 else data["atr_pip"] <= qhi)
        sub = data[mask]
        n = len(sub)
        if n == 0:
            continue
        cost = FIXED_RT_PIP + sub["entry_spread"].values
        g1 = sub["post_1h_pip"].values
        net1 = g1 - cost
        print(f"  {label}: n={n:4d}  1h gross={g1.mean():+.2f}p  net={net1.mean():+.2f}p  wr={(net1>0).mean()*100:.0f}%")
    print()

    # Combined: high-vol AND large pre-fix decline
    print("=" * 65)
    print("COMBINED: high-ATR day AND large pre-fix EUR decline")
    print("=" * 65)
    hi_atr_thresh = data["atr_pip"].quantile(2/3)
    for thresh_atr in [0.5, 0.75, 1.0]:
        mask = (data["atr_pip"] >= hi_atr_thresh) & (data["pre_ret_atr"] < -thresh_atr)
        sub = data[mask]
        n = len(sub)
        if n < 5:
            print(f"  high-ATR + pre_ret<−{thresh_atr:.2f}×ATR: n={n} (too few)")
            continue
        cost = FIXED_RT_PIP + sub["entry_spread"].values
        g1 = sub["post_1h_pip"].values
        g2 = sub["post_2h_pip"].values
        net1 = g1 - cost
        print(f"  high-ATR + pre_ret<−{thresh_atr:.2f}×ATR: n={n:3d}  "
              f"1h gross={g1.mean():+.2f}p  net={net1.mean():+.2f}p  2h gross={g2.mean():+.2f}p  wr1h={(net1>0).mean()*100:.0f}%")
    print()

    # Summary: does ANY subset meet the threshold (gross > 2.6p, n >= 200)?
    print("=" * 65)
    print("DECISION THRESHOLD: gross > 2.6 pip AND n >= 200?")
    print("(if yes: build full strategy and spend a trial; else: probe-reject)")
    print("=" * 65)
    # Check best conditional subset
    best_label, best_gross, best_n = "none", 0.0, 0
    for thresh in [0.25, 0.5, 0.75, 1.0]:
        mask = data["pre_ret_atr"] < -thresh
        if mask.sum() < 10:
            continue
        sub = data[mask]
        g = sub["post_1h_pip"].mean()
        if g > best_gross:
            best_gross = g
            best_n = mask.sum()
            best_label = f"pre_ret<−{thresh}×ATR"
    print(f"  Best conditional subset: {best_label}  gross={best_gross:+.2f}p  n={best_n}")
    threshold_met = best_gross > 2.6 and best_n >= 200
    print(f"  Threshold met (>2.6p AND >=200): {threshold_met}")
    if threshold_met:
        print("  -> WORTH A TRIAL: build strategy and run full backtest")
    else:
        print("  -> PROBE-REJECT: post-fix reversion does not clear cost in 2024-2026 data")


def main() -> int:
    df = load()
    run_probe(df)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
                                                                                                                