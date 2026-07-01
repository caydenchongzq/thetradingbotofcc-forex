"""PROBE (not a strategy, not a trial): does the SIGN of the realized-semivariance
imbalance (signed jump variation) predict the next-horizon EURUSD M15 return?

Mechanism (Bollerslev/Feunou-style "good vs bad" volatility; Journal of Empirical
Finance v72 2023 "Time series momentum and reversal: intraday information from realized
semivariance"):
  Over a rolling lookback of L M15 bars, decompose realized variance into
    RS+ = sum(r_t^2 for r_t>0)   (upside / "good" variance)
    RS- = sum(r_t^2 for r_t<0)   (downside / "bad" variance)
  Signed-jump imbalance  s = (RS+ - RS-)/(RS+ + RS-)  in [-1,1].
  The paper reports s carries directional information beyond raw momentum: the balance
  of upside vs downside variance separates continuation from reversal.

This is a NEW construction vs the library's closed trend/momentum probes, which all used
RAW signed close-to-close drift (corr~0, gross<cost). Here we test whether the VARIANCE
DECOMPOSITION (not the raw return) has predictive sign. §4.3 a-priori probe BEFORE any trial:
if gross expectancy does not clear the ~2.6p round-trip cost with a real t-stat, no trial.

Reported per (L lookback, H forward horizon, thr |s| threshold), CONTINUATION and REVERSAL:
  n, corr(s, fwd), mean GROSS pip, mean NET pip (cost 2.6p), win rate, t-stat.
Entries restricted to liquid hours (07:00-20:00 UTC) so the 2.6p cost is defensible.
"""
from __future__ import annotations
import numpy as np, pandas as pd

PIP = 1e4
COST_PIPS = 2.6           # round-trip commission+slippage+spread (library benchmark)
LIQ_START, LIQ_END = 7, 20  # UTC hours for entry (London+NY)

df = pd.read_parquet("state/parquet/eurusd_m15.parquet", engine="fastparquet")
ts = pd.to_datetime(df["ts_open_utc"], utc=True)
df = df.assign(ts=ts).set_index("ts").sort_index()
C = df["close"].values.astype(float)
hour = df.index.hour
n = len(C)

# close-to-close returns in pips
r = np.zeros(n)
r[1:] = (C[1:] - C[:-1]) * PIP
r2 = r * r
up = np.where(r > 0, r2, 0.0)
dn = np.where(r < 0, r2, 0.0)

def rsum(x, L):
    c = np.cumsum(np.insert(x, 0, 0.0))
    out = np.full(len(x), np.nan)
    out[L-1:] = c[L:] - c[:-L]  # sum of last L values ending at index i
    return out

liq = (hour >= LIQ_START) & (hour < LIQ_END)

print(f"rows={n}  span={df.index[0]}..{df.index[-1]}  liquid-hour bars={liq.sum()}")
print(f"cost={COST_PIPS}p round-trip; entries restricted to {LIQ_START:02d}-{LIQ_END:02d} UTC\n")

def tstat(x):
    x = x[~np.isnan(x)]
    if len(x) < 2 or x.std(ddof=1) == 0:
        return 0.0
    return x.mean() / (x.std(ddof=1) / np.sqrt(len(x)))

header = f"{'L':>3} {'H':>3} {'thr':>4} {'mode':>5} {'n':>6} {'corr':>7} {'gross':>7} {'net':>7} {'win%':>6} {'t':>6}"
for L in (8, 16, 32):
    rsp = rsum(up, L)
    rsm = rsum(dn, L)
    rv = rsp + rsm
    with np.errstate(invalid="ignore", divide="ignore"):
        s = np.where(rv > 0, (rsp - rsm) / rv, np.nan)  # signal known at close of bar i
    print(header)
    for H in (1, 4, 8, 16):
        fwd = np.full(n, np.nan)
        fwd[:n-H] = (C[H:] - C[:n-H]) * PIP  # forward return over H bars from close_i
        for thr in (0.0, 0.3, 0.5):
            valid = (~np.isnan(s)) & (~np.isnan(fwd)) & liq & (np.abs(s) >= thr)
            if valid.sum() < 30:
                continue
            sv, fv = s[valid], fwd[valid]
            cc = np.corrcoef(sv, fv)[0, 1] if len(sv) > 2 else 0.0
            for mode in ("cont", "rev"):
                sign = np.sign(sv) if mode == "cont" else -np.sign(sv)
                gross = sign * fv
                net = gross - COST_PIPS
                win = (gross > 0).mean() * 100
                print(f"{L:>3} {H:>3} {thr:>4.1f} {mode:>5} {valid.sum():>6} "
                      f"{cc:>7.3f} {gross.mean():>7.3f} {net.mean():>7.3f} {win:>6.1f} {tstat(net):>6.2f}")
        print()
