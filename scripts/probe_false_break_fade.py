"""PROBE (not a strategy, not a trial): conditional sign + frequency of fading a FAILED
opening-range breakout (Turtle Soup / false-break fade) on EURUSD M15.

Mechanism probed:
  OR window = London 13:00-13:30 (HEAD v4). long_level=range_high+buf, short_level=range_low-buf.
  Post-OR (13:30-16:00): a bar CLOSES beyond a level (the breakout). It then FAILS when a
  later post-OR bar CLOSES back inside the range. On that confirmation bar we FADE at market
  (failed up-break -> SHORT; failed down-break -> LONG). One event per side per day.

We measure, a priori with a pre-registered exit:
  stop   = beyond the breakout excursion extreme + 0.25*ATR buffer
  target = the opposite side of the range (Turtle Soup standard) -> the fade R.
Reported: frequency, win rate, mean R net of cost, and split by ER regime, to decide the gate
and whether the 200-trade floor is even reachable BEFORE spending a trial.
"""
from __future__ import annotations
import pandas as pd, numpy as np
from datetime import time
from zoneinfo import ZoneInfo

LON = ZoneInfo("Europe/London")
PIP = 0.0001
BUF = 1.5 * PIP
COST_PIPS = 2.6          # round-trip commission+slippage+spread (library benchmark)
WIN_START, OR_END, WIN_END = time(13,0), time(13,30), time(16,0)
ER_WIN, ATR_WIN, ER_THR = 14, 14, 0.32

df = pd.read_parquet("state/parquet/eurusd_m15.parquet")
ts = pd.to_datetime(df["ts_open_utc"], utc=True)
df = df.assign(ts=ts).set_index("ts")
lon = df.index.tz_convert(LON)
df["lt"] = lon.time
df["ld"] = lon.date
H, L, C, O = df["high"].values, df["low"].values, df["close"].values, df["open"].values

# Wilder ATR (pips) and efficiency ratio, computed on the full series (close-to-close).
tr = np.maximum(H[1:]-L[1:], np.maximum(np.abs(H[1:]-C[:-1]), np.abs(L[1:]-C[:-1])))
tr = np.concatenate([[H[0]-L[0]], tr])
atr = np.full(len(C), np.nan)
if len(C) > ATR_WIN:
    atr[ATR_WIN] = tr[1:ATR_WIN+1].mean()
    for i in range(ATR_WIN+1, len(C)):
        atr[i] = (atr[i-1]*(ATR_WIN-1)+tr[i])/ATR_WIN
er = np.full(len(C), np.nan)
for i in range(ER_WIN, len(C)):
    direction = abs(C[i]-C[i-ER_WIN])
    vol = np.abs(np.diff(C[i-ER_WIN:i+1])).sum()
    er[i] = direction/vol if vol > 0 else 0.0

idx = {t:i for i,t in enumerate(df.index)}
events = []
for day, g in df.groupby("ld"):
    sess = g[(g["lt"]>=WIN_START)&(g["lt"]<WIN_END)]
    orb = sess[sess["lt"]<OR_END]
    post = sess[sess["lt"]>=OR_END]
    if len(orb)==0 or len(post)<3:
        continue
    rh, rl = orb["high"].max(), orb["low"].min()
    long_lvl, short_lvl = rh+BUF, rl-BUF
    rng = rh-rl
    if rng <= 0:
        continue
    pc = post["close"].values; ph = post["high"].values; pl = post["low"].values
    prows = [idx[t] for t in post.index]
    for side in ("up","down"):
        # find first breakout close beyond the level
        broke = None
        for k in range(len(pc)):
            if side=="up" and pc[k] > long_lvl: broke=k; break
            if side=="down" and pc[k] < short_lvl: broke=k; break
        if broke is None:
            continue
        # find first later bar closing back INSIDE the range (failure confirmation)
        conf = None
        for k in range(broke+1, len(pc)):
            if side=="up" and pc[k] < rh: conf=k; break
            if side=="down" and pc[k] > rl: conf=k; break
        if conf is None:
            continue
        gi = prows[conf]
        e_atr = atr[gi]; e_er = er[gi]
        if not (e_atr>0) or e_er!=e_er:
            continue
        entry = pc[conf]
        excursion_ext = ph[broke:conf+1].max() if side=="up" else pl[broke:conf+1].min()
        atr_px = e_atr*PIP
        if side=="up":   # fade SHORT
            stop = excursion_ext + 0.25*atr_px
            target = rl
            risk = (stop-entry); reward = (entry-target)
        else:            # fade LONG
            stop = excursion_ext - 0.25*atr_px
            target = rh
            risk = (entry-stop); reward = (target-entry)
        if risk <= 0 or reward <= 0:
            continue
        # walk forward to session window end, intrabar stop-then-target priority (conservative)
        outcome = None
        for k in range(conf+1, len(pc)):
            hi, loo = ph[k], pl[k]
            if side=="up":
                if hi >= stop: outcome=-risk; break
                if loo <= target: outcome=reward; break
            else:
                if loo <= stop: outcome=-risk; break
                if hi >= target: outcome=reward; break
        if outcome is None:   # force flat at window end
            outcome = (entry-pc[-1]) if side=="up" else (pc[-1]-entry)
        R = outcome/risk
        R_net = (outcome - COST_PIPS*PIP)/risk
        events.append(dict(day=str(day), side=side, er=e_er, atr=e_atr,
                           rng_pips=rng/PIP, risk_pips=risk/PIP, rr=reward/risk,
                           R=R, R_net=R_net))

ev = pd.DataFrame(events)
def summ(name, d):
    if len(d)==0: print(f"{name:28s} n=0"); return
    print(f"{name:28s} n={len(d):4d}  win%={(d.R_net>0).mean()*100:5.1f}  "
          f"meanR_gross={d.R.mean():+.3f}  meanR_net={d.R_net.mean():+.3f}  "
          f"medRR={d.rr.median():.2f}  medRisk={d.risk_pips.median():.1f}p")
print(f"total raw events: {len(ev)}  unique days: {ev.day.nunique()}")
summ("ALL", ev)
summ("ER<0.32 (ranging)", ev[ev.er<ER_THR])
summ("ER>=0.32 (trending)", ev[ev.er>=ER_THR])
summ("up-break faded SHORT", ev[ev.side=="up"])
summ("down-break faded LONG", ev[ev.side=="down"])
summ("ER<0.32 & risk<=15p", ev[(ev.er<ER_THR)&(ev.risk_pips<=15)])
