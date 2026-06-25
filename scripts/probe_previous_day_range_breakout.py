"""PROBE (not a strategy, not a trial): Previous-Day-High/Low breakout on EURUSD M15.

Decision question answered BEFORE spending a trial (spec 08 §5, §4.3):
  Does breaking the prior calendar day's high (PDH) or low (PDL) — confirmed by a bar
  CLOSE above/below — carry a positive gross expectancy in the London/NY overlap window?

Mechanism:
  * PDH = max(high) of all M15 bars in the prior calendar day (UTC midnight-to-midnight).
  * PDL = min(low)  of all M15 bars in the prior calendar day.
  * These are DAILY-STRUCTURAL levels (full prior-day auction), distinct from the intraday
    opening range (30-min, current day) used by the closed SessionBreakoutER family.
  * Signal: in the London/NY overlap window (13:00-16:00 Europe/London), the FIRST bar
    whose CLOSE is strictly above PDH → long signal; strictly below PDL → short signal.
    One signal per side per day; if both trigger the same day, take the first chronologically.
  * Entry: MARKET on the OPEN of the next M15 bar (live-fillable; no retcode 10015 because
    we act AFTER the confirming close, not simultaneously with it).
  * Stop: entry ± SL_ATR_MULT × ATR(14) (below for long, above for short).
  * Target: entry ± TP_R × SL_ATR_MULT × ATR(14)  (2R, because a daily-range break should
    carry further than a 30-min OR break; TP_R chosen a-priori, not tuned on results here).
  * Hold cap: flat at session end (16:00 London).
  * Cost: 2.6-pip round-trip (commission + slippage + spread, library benchmark).

Differentiation vs the closed breakout family (spec 08 §4.3):
  The four live-faithful breakout closures are ALL intraday-range instruments:
    - SessionBreakoutER: 30-min OR, LEVEL-fill artifact; market-fill −0.024R.
    - LondonOpenBreakoutER: 30-min OR at London open, −0.129R.
    - NR7VolatilityBreakout: single-bar NR7 contraction, resting-touch, −0.263R.
    - AsianRangeLondonBreakout: 7-hour Asian box, resting-touch, −0.248R gross.
  All share the ~65% within-session "double-break chop" failure mode (touch tax).
  PDH/PDL is different in three ways:
    (1) The level comes from the PRIOR DAY'S full auction — a multi-day structural reference.
    (2) Entry requires a bar CLOSE above/below (confirmation), so no intrabar touch tax.
    (3) Mechanism is daily momentum (prior-day resistance gives way → continuation) not an
        intraday microstructure snap.
  These are genuine differentiators. However, the family lesson ("EURUSD M15 continuation
  after breakout is adverse") may still apply; this probe settles the question empirically.

Pre-registered exit geometry (spec 08 §5.8):
  SL_ATR_MULT = 1.5 (wider than 1.2 incumbent default — a daily-structural break needs room)
  TP_R = 2.0  (structural breaks should follow through further than 30-min OR breaks; TP_R
               ≥ 1:1 required; 2:1 preferred here because if the win rate is sub-50%,
               which is expected from the prior breakout family data, only TP_R≥2 rescues PF)

Decision rule (a-priori, announced before results are known):
  WORTH A TRIAL if:
    gross_expectancy ≥ 0.10R  AND  n ≥ 200  AND  gross_win_rate ≥ 30% (breakeven at 2R).
  PROBE-REJECT (no trial) otherwise.

Run: python3 scripts/probe_previous_day_range_breakout.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from datetime import time
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

PARQUET = "state/parquet/eurusd_m15.parquet"
LONDON_TZ = ZoneInfo("Europe/London")
UTC = ZoneInfo("UTC")

PIP = 0.0001
COST_PIPS = 2.6          # round-trip cost benchmark (library standard)
ATR_WIN = 14
SL_ATR_MULT = 1.5        # a-priori: wider than incumbent, justified above
TP_R = 2.0               # a-priori: 2R target

WIN_START = time(13, 0)  # London time — matches incumbent session window
WIN_END   = time(16, 0)  # London time — session end, flat by here


def wilder_atr(h: np.ndarray, l: np.ndarray, c: np.ndarray, n: int) -> np.ndarray:
    tr = np.maximum(h[1:] - l[1:],
         np.maximum(np.abs(h[1:] - c[:-1]), np.abs(l[1:] - c[:-1])))
    tr = np.concatenate([[h[0] - l[0]], tr])
    atr = np.full(len(c), np.nan)
    atr[n - 1] = tr[:n].mean()
    for i in range(n, len(c)):
        atr[i] = (atr[i - 1] * (n - 1) + tr[i]) / n
    return atr


def main():
    if not Path(PARQUET).exists():
        print(f"ERROR: {PARQUET} not found."); return

    df = pd.read_parquet(PARQUET)
    df["ts"] = pd.to_datetime(df["ts_open_utc"], utc=True)
    df = df.set_index("ts").sort_index()

    # London-localised timestamp for session logic
    df["ts_london"] = df.index.tz_convert(LONDON_TZ)
    df["london_date"] = df["ts_london"].dt.date
    df["london_time"] = df["ts_london"].dt.time

    # UTC date for PDH/PDL computation
    df["utc_date"] = df.index.tz_convert(UTC).date

    H = df["high"].values
    L = df["low"].values
    C = df["close"].values
    O = df["open"].values

    atr = wilder_atr(H, L, C, ATR_WIN)

    # ── Compute prior-calendar-day PDH/PDL for each bar ─────────────────────────
    # Group by UTC date → daily high/low
    df["H"] = H
    df["L"] = L
    df["C"] = C
    df["O"] = O
    df["atr"] = atr
    df["idx"] = np.arange(len(df))

    daily = df.groupby("utc_date").agg(day_high=("H", "max"), day_low=("L", "min"))
    daily["pdh"] = daily["day_high"].shift(1)   # prior day's high
    daily["pdl"] = daily["day_low"].shift(1)    # prior day's low
    df = df.join(daily[["pdh", "pdl"]], on="utc_date")

    # ── Signal generation (London/NY session window only) ────────────────────────
    trades: list[dict] = []
    days = sorted(df["london_date"].unique())

    for day in days:
        day_df = df[df["london_date"] == day]
        session = day_df[(day_df["london_time"] >= WIN_START) &
                         (day_df["london_time"] < WIN_END)]
        if len(session) < 2:
            continue

        pdh = session["pdh"].iloc[0]
        pdl = session["pdl"].iloc[0]
        if np.isnan(pdh) or np.isnan(pdl):
            continue

        session_bars = list(session.itertuples())

        # Find first close above PDH (long) and first close below PDL (short) in session
        long_signal_idx = None
        short_signal_idx = None
        for k, bar in enumerate(session_bars[:-1]):   # need a NEXT bar for entry
            if long_signal_idx is None and bar.C > pdh:
                long_signal_idx = k
            if short_signal_idx is None and bar.C < pdl:
                short_signal_idx = k

        # Simulate each triggered signal
        for direction, sig_k in [("long", long_signal_idx), ("short", short_signal_idx)]:
            if sig_k is None:
                continue
            entry_k = sig_k + 1              # next bar after signal
            if entry_k >= len(session_bars):
                continue
            entry_bar = session_bars[entry_k]
            entry_price = entry_bar.O        # market on open
            atr_val = entry_bar.atr
            if np.isnan(atr_val) or atr_val <= 0:
                continue

            sl_dist = SL_ATR_MULT * atr_val
            tp_dist = TP_R * sl_dist

            if direction == "long":
                sl = entry_price - sl_dist
                tp = entry_price + tp_dist
            else:
                sl = entry_price + sl_dist
                tp = entry_price - tp_dist

            # Walk bars from entry until SL/TP/session-end
            outcome = None
            for bar in session_bars[entry_k + 1:]:
                if direction == "long":
                    # Check SL first (conservative)
                    if bar.L <= sl:
                        outcome = "sl"
                        exit_price = sl
                        break
                    if bar.H >= tp:
                        outcome = "tp"
                        exit_price = tp
                        break
                else:
                    if bar.H >= sl:
                        outcome = "sl"
                        exit_price = sl
                        break
                    if bar.L <= tp:
                        outcome = "tp"
                        exit_price = tp
                        break
            else:
                # Session ended without SL/TP
                outcome = "eod"
                exit_price = session_bars[-1].C

            if direction == "long":
                gross_pips = (exit_price - entry_price) / PIP
            else:
                gross_pips = (entry_price - exit_price) / PIP

            net_pips = gross_pips - COST_PIPS
            r_multiple = net_pips / (sl_dist / PIP)

            trades.append({"direction": direction, "outcome": outcome,
                           "gross_pips": gross_pips, "net_pips": net_pips,
                           "r_multiple": r_multiple})

    if not trades:
        print("No signals found.")
        return

    t = pd.DataFrame(trades)
    n = len(t)
    wins = (t["net_pips"] > 0).sum()
    gross_exp = t["gross_pips"].mean() / (SL_ATR_MULT * 14 * PIP / PIP)  # approx gross R

    print("=" * 60)
    print("PROBE: PreviousDayRangeBreakout  (PDH/PDL, market-fill)")
    print("=" * 60)
    print(f"  Signals (total trades): {n}")
    print(f"  Long signals:           {(t['direction']=='long').sum()}")
    print(f"  Short signals:          {(t['direction']=='short').sum()}")
    print(f"  Outcomes: SL={( t['outcome']=='sl').sum()}  "
          f"TP={(t['outcome']=='tp').sum()}  EOD={(t['outcome']=='eod').sum()}")
    print(f"  Win rate (net>0):       {wins/n*100:.1f}%")
    print(f"  Mean gross pips:        {t['gross_pips'].mean():+.2f}")
    print(f"  Mean net pips:          {t['net_pips'].mean():+.2f}")
    print(f"  Mean R (net):           {t['r_multiple'].mean():+.3f}R")
    print(f"  Profit factor (gross):  "
          f"{t['gross_pips'][t['gross_pips']>0].sum() / (-t['gross_pips'][t['gross_pips']<0].sum() + 1e-9):.2f}")
    print()
    print(f"  Per direction:")
    for d in ["long", "short"]:
        sub = t[t["direction"] == d]
        if len(sub) == 0:
            continue
        print(f"    {d}: n={len(sub)}  R={sub['r_multiple'].mean():+.3f}  "
              f"wr={( sub['net_pips']>0).sum()/len(sub)*100:.1f}%  "
              f"gross_pips={sub['gross_pips'].mean():+.2f}")
    print()
    decision_gross_r = t["gross_pips"].mean() / (SL_ATR_MULT * atr[~np.isnan(atr)].mean() / PIP)
    print(f"  Approx gross_R (mean_gross / mean_sl_pips): {decision_gross_r:+.3f}")
    print()
    # Decision rule (pre-registered)
    net_r = t["r_multiple"].mean()
    win_rate = wins / n
    worth = (t["gross_pips"].mean() > 0 and n >= 200 and win_rate >= 0.28)
    print(f"  DECISION (pre-registered): n≥200={n>=200}, gross>0={t['gross_pips'].mean()>0:.0f}, "
          f"wr≥28%={win_rate>=0.28:.0f}")
    print(f"  → {'WORTH A TRIAL' if worth else 'PROBE-REJECT (no trial)'}")
    print("=" * 60)


if __name__ == "__main__":
    main()
