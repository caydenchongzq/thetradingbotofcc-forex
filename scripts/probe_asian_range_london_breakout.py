"""PROBE (not a strategy, not a trial): live-fillable Asian-range -> London breakout on
EURUSD M15. Settles whether the DIRECTIONAL complement of the closed AsianSweepFade has a
gross edge BEFORE spending a trial.

Mechanism probed:
  Asian box  = consolidation over 00:00-07:00 UTC -> [box_high, box_low].
  Arm a resting-stop OCO at 07:00 UTC: long_stop = box_high + buf, short_stop = box_low - buf.
    (Both levels known at arm time -> live-placeable; first intrabar TOUCH fills -> no 10015,
     unlike the incumbent's level-fill artifact.)
  London window 07:00-12:00 UTC: first side touched fills at its level (resting stop). One
    fill per day (OCO: the other order is cancelled). Skip days whose box is degenerate.

Differentiation vs the library (spec 08 sec 4.3):
  - AsianSweepFade (2026-06-08, tested-rejected): FADED the Asian-range sweep, lost -0.158R/
    PF 0.65. A losing fade => breaks tend to CONTINUE, not revert -> the breakout direction is
    the untested complement. This probe tests that complement directly.
  - Distinct from LondonOpenBreakoutER (2026-06-15): that used a 30-min OPENING range at the
    London open; this uses the 7-hour Asian CONSOLIDATION box (wider, longer-formed -> the
    hypothesis is a lower false-break rate).
  - Distinct from NR7 (2026-06-18): single-bar contraction, not a 7h session box.
  - Live-fillable by construction (resting touch), so it is NOT the incumbent's level-fill
    artifact; it is judged against the live-faithful cost stack.

Pre-registered exit geometry (per spec 08 sec 5.8 -- justified by THIS mechanism, not inherited):
  A range-expansion breakout: give it room and target the measured move.
    stop   = sl_atr_mult x ATR(M15,14) below/above the fill  (volatility-scaled, ~1.0-1.5x)
    target = tp_R x risk                                      (R:R >= 1:1; 1.5-2.0 for a
             continuation move that should run if the hypothesis holds)
  Grid-probed; intrabar resolution is STOP-FIRST on an ambiguous bar (conservative).

Reported: frequency (can it clear the 200-trade floor over 2.4yr?), win rate, mean R net of
the 2.6-pip cost, and the false-break rate, split by ER regime -- to decide a gate and whether
a trial is even warranted.
"""
from __future__ import annotations
import pandas as pd, numpy as np
from datetime import time
from zoneinfo import ZoneInfo

UTC = ZoneInfo("UTC")
PIP = 0.0001
BUF = 1.5 * PIP
COST_PIPS = 2.6                 # round-trip commission+slippage+spread (library benchmark)
BOX_START, BOX_END = time(0, 0), time(7, 0)      # Asian consolidation box (UTC)
WIN_END = time(12, 0)                            # London breakout window ends
ATR_WIN, ER_WIN = 14, 14

df = pd.read_parquet("state/parquet/eurusd_m15.parquet")
ts = pd.to_datetime(df["ts_open_utc"], utc=True)
df = df.assign(ts=ts).set_index("ts").sort_index()
u = df.index  # already UTC
df["ut"] = u.time
df["ud"] = u.date
H, L, C, O = df["high"].values, df["low"].values, df["close"].values, df["open"].values

# Wilder ATR (pips) + efficiency ratio on the full close series.
tr = np.maximum(H[1:] - L[1:], np.maximum(np.abs(H[1:] - C[:-1]), np.abs(L[1:] - C[:-1])))
tr = np.concatenate([[H[0] - L[0]], tr])
atr = np.full(len(C), np.nan)
if len(C) > ATR_WIN:
    atr[ATR_WIN] = tr[1:ATR_WIN + 1].mean()
    for i in range(ATR_WIN + 1, len(C)):
        atr[i] = (atr[i - 1] * (ATR_WIN - 1) + tr[i]) / ATR_WIN
er = np.full(len(C), np.nan)
for i in range(ER_WIN, len(C)):
    direction = abs(C[i] - C[i - ER_WIN])
    vol = np.abs(np.diff(C[i - ER_WIN:i + 1])).sum()
    er[i] = direction / vol if vol > 0 else 0.0
df["atr_pips"] = atr / PIP
df["er"] = er

pos = {t: i for i, t in enumerate(df.index)}

def simulate(sl_atr_mult: float, tp_R: float):
    """One OCO fill per day; resolve to stop/target/window-end with stop-first ambiguity."""
    rows = []
    for day, g in df.groupby("ud"):
        box = g[(g["ut"] >= BOX_START) & (g["ut"] < BOX_END)]
        win = g[(g["ut"] >= BOX_END) & (g["ut"] < WIN_END)]
        if len(box) < 12 or len(win) < 4:
            continue
        bh, bl = box["high"].max(), box["low"].min()
        long_lvl, short_lvl = bh + BUF, bl - BUF
        arm_i = pos[win.index[0]]
        a = df["atr_pips"].values[arm_i]
        e = df["er"].values[arm_i]
        if not np.isfinite(a) or a <= 0:
            continue
        risk = sl_atr_mult * a * PIP
        # find first touch
        fill = None
        wv = win[["high", "low", "close"]].values
        wi = [pos[t] for t in win.index]
        for k, t in enumerate(win.index):
            hi, lo = win["high"].iloc[k], win["low"].iloc[k]
            up = hi >= long_lvl
            dn = lo <= short_lvl
            if up and dn:
                # both in same bar -> ambiguous; take the nearer level to the bar open
                o0 = win["open"].iloc[k]
                side = "long" if abs(long_lvl - o0) <= abs(o0 - short_lvl) else "short"
                fill = (side, k)
                break
            if up:
                fill = ("long", k); break
            if dn:
                fill = ("short", k); break
        if fill is None:
            continue
        side, k0 = fill
        entry = long_lvl if side == "long" else short_lvl
        if side == "long":
            stop = entry - risk; tgt = entry + tp_R * risk
        else:
            stop = entry + risk; tgt = entry - tp_R * risk
        # resolve forward within the same day's remaining session
        outcome = None
        for k in range(k0, len(win)):
            hi, lo = win["high"].iloc[k], win["low"].iloc[k]
            if side == "long":
                hit_stop = lo <= stop; hit_tgt = hi >= tgt
            else:
                hit_stop = hi >= stop; hit_tgt = lo <= tgt
            if hit_stop and hit_tgt:
                outcome = -1.0; break          # stop-first (conservative)
            if hit_stop:
                outcome = -1.0; break
            if hit_tgt:
                outcome = float(tp_R); break
        if outcome is None:
            # close at last window bar
            last = win["close"].iloc[-1]
            outcome = ((last - entry) if side == "long" else (entry - last)) / risk
        cost_R = (COST_PIPS * PIP) / risk
        rows.append((day, side, e, outcome, outcome - cost_R, risk / PIP))
    r = pd.DataFrame(rows, columns=["day", "side", "er", "R_gross", "R_net", "risk_pips"])
    return r

print("Asian-range -> London breakout PROBE (live touch fill, cost %.1fp)\n" % COST_PIPS)
print(f"{'sl_atr':>6} {'tp_R':>5} {'n':>5} {'win%':>6} {'grossR':>8} {'netR':>8} {'PF_net':>7}")
best = None
for sl in (1.0, 1.5):
    for tp in (1.0, 1.5, 2.0):
        r = simulate(sl, tp)
        if len(r) == 0:
            continue
        win = 100 * (r.R_gross > 0).mean()
        g = r.R_gross.mean(); n = r.R_net.mean()
        wins = r.R_net[r.R_net > 0].sum(); losses = -r.R_net[r.R_net < 0].sum()
        pf = wins / losses if losses > 0 else float("inf")
        print(f"{sl:6.1f} {tp:5.1f} {len(r):5d} {win:6.1f} {g:8.3f} {n:8.3f} {pf:7.2f}")
        if best is None or n > best[0]:
            best = (n, sl, tp, r)

print("\n-- best cell by net R --")
n, sl, tp, r = best
print(f"sl_atr={sl} tp_R={tp}  n={len(r)}  net meanR={n:.3f}")
print("ER split (net R):")
for lab, mask in (("low ER<0.32", r.er < 0.32), ("high ER>=0.32", r.er >= 0.32)):
    s = r[mask]
    if len(s):
        print(f"  {lab:14s} n={len(s):4d} win%={100*(s.R_gross>0).mean():5.1f} netR={s.R_net.mean():+.3f}")
print("\nfalse-break read: share of fills that hit stop =",
      f"{100*(r.R_gross<=0).mean():.1f}%")
print("trades/yr ~ %.0f  -> 200-floor over 2.4yr: %s" %
      (len(r)/2.4, "REACHABLE" if len(r) >= 200 else "AT RISK"))
