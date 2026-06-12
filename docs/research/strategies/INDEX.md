# Strategy library — index

> Recall surface for the research engine (spec 08). **Read this first every run.** One line
> per researched candidate; full detail in the linked report. Keep lines terse. Statuses:
> idea · blocked-on-data · in-progress · tested-rejected · tested-passed · promoted · retired.
>
> Rules: new entries from `TEMPLATE.md`; re-testing a rejected family+failure-mode without
> stated differentiation is forbidden (spec 08 §4.3); every backtested entry consumes trial
> budget (`state/config/trial_ledger.jsonl`, cap in `config/default.yaml`).

| id | name | family | status | verdict |
|---|---|---|---|---|
| [2026-06-02-session-breakout-er](2026-06-02-session-breakout-er.md) | SessionBreakoutER | breakout | **promoted** | Incumbent, HEAD v4; lockbox +0.303R, PF 2.03 |
| [2026-06-03-full-exit-model](2026-06-03-full-exit-model.md) | FullExitModel | exit-model | tested-rejected | Scaled 1R+runner worse on lockbox (+0.093R, PF 1.17); code kept, off |
| [2026-06-07-tp-2r-sweep](2026-06-07-tp-2r-sweep.md) | Pure ≥2R target | exit-model | tested-rejected | All 18 fail DSR; best fails lockbox (+0.074R, PF 1.08); 1R stands |
| [2026-06-07-pre-session-compression-filter](2026-06-07-pre-session-compression-filter.md) | SessionBreakoutERCompression | filter | blocked-on-data | Degenerate as built (3 trades — morning never quiet vs overnight baseline); whole subtractive-filter family gate-blocked at 224-trade headroom |
| [2026-06-08-asian-sweep-fade](2026-06-08-asian-sweep-fade.md) | AsianSweepFade | mean-reversion | tested-rejected | No edge: −0.158R in-sample, PF 0.65, 0/7 WF folds, lockbox FAIL; symmetric-1R sweep fade is structurally negative |
| [2026-06-09-late-session-drift](2026-06-09-late-session-drift.md) | LateSessionDrift | trend | tested-rejected | Real but un-harvestable: +2.3 pip/night raw drift, but 1.24-pip entry spread (thin-hour) + stop-noise → −0.146R, 1/7 WF folds, lockbox −0.232R PF 0.40; needs-live-mirror flag (moot) |
| [2026-06-10-asian-sweep-fade-rr](2026-06-10-asian-sweep-fade-rr.md) | AsianSweepFadeRR | mean-reversion | tested-rejected | Asymmetric R:R does NOT rescue the fade: tight wick stop + 2R drops win 54.7%→35.8% at constant PF ~0.68 (=no edge); −0.212R, 1/7 WF folds, lockbox −0.083R PF 0.84 FAIL. **Sweep-fade family now closed** (both 1R & 2R rejected) |
| [2026-06-11-breakout-retest](2026-06-11-breakout-retest.md) | BreakoutRetestER | breakout | tested-rejected | Break→retest→resume filter is ANTI-selective: discards the immediate-continuation winners (win 73%→43%, PF 1.99→0.70) AND halves trades to 113 (<200 floor); −0.181R, 2/7 WF folds, lockbox −0.102R PF 0.75 FAIL. **Breakout entry-timing subsets are double-jeopardy** (trade-floor + anti-selection) |
| [2026-06-12-trend-pullback-ema](2026-06-12-trend-pullback-ema.md) | TrendPullbackEMA | trend | tested-rejected | A pullback-to-EMA continuation entry is a 27.4%-win-rate entry a 2R target cannot rescue: -0.141R, PF 0.77, only 84 trades (<200 floor), 0/1 scored WF folds, lockbox -0.064R PF 0.91 FAIL. The exact INVERSE of the incumbent's 73%-win 1R breakout; reconfirms the >=2R rejection from a NEW entry (win rate, not geometry, is the binding constraint). **Trend family now 0/3 (serial-corr, drift, pullback) — selectivity is the recurring killer** |

## Idea queue (triaged, not yet tested)

| id | name | family | status | one-line |
|---|---|---|---|---|
| [2026-06-07-intraday-ts-momentum](2026-06-07-intraday-ts-momentum.md) | IntradayTSMomentum | trend | probe-rejected | early→late session return corr 0.026, mean +0.25 pip < cost (probed 2026-06-09); do not test without a new mechanism |
| [2026-06-08-london-fix-reversal](2026-06-08-london-fix-reversal.md) | LondonFixReversal | mean-reversion | probe-rejected | post-fix reversion ~0.2 pip < cost, wr 51.8%; month-end subset (19d) below 200-trade floor (probed 2026-06-09) |
| [2026-06-07-cross-instrument-confirmation](2026-06-07-cross-instrument-confirmation.md) | CrossInstrumentConfirmation | filter | blocked-on-data | Needs multi-instrument export AND longer history (filter trade-count cap) |
| 2026-06-10-twenty-day-turtle-soup | TwentyDayTurtleSoup | mean-reversion | idea | Fade a sweep of a ≥20-session structural high/low (the actual level in Costa SSRN's >75% stat), NOT the overnight range. Distinct *level* vs the closed Asian-fade family. Risk: rare → likely <200 trades; blocked on trade-count until longer history (queued 2026-06-10) |
| 2026-06-10-sweep-magnitude-fade | SweepMagnitudeFade | mean-reversion | idea | Only fade deep sweeps (penetration > ~0.5×ATR beyond the level) — a different *entry* mechanism (the lever the closed fade family leaves open). Subtractive on an already-borderline trade count; estimate frequency before testing (queued 2026-06-10) |

| 2026-06-11-vwap-stretch-reversion | VWAPStretchReversion | mean-reversion | idea | Fade a large session-VWAP stretch (no sweep) — different mechanism from the closed sweep-fade family. Risk: mean-reversion scrutiny + trade count; estimate frequency first. Queue 2026-06-11 |
| 2026-06-11-second-entry-orb | SecondEntryORB | breakout | idea | ADDITIVE: keep incumbent close-entry AND add a re-break second entry after a first stop-out, to RAISE trade count (inverse of [[2026-06-11-breakout-retest]]). The only retest-adjacent idea worth testing because it is additive, not subtractive. Queue 2026-06-11 |

> Retired idea stubs: [2026-06-07-asian-sweep-fade](2026-06-07-asian-sweep-fade.md) (tested 2026-06-08 → rejected).
> Closed families: **Asian sweep-fade** — both symmetric-1R ([[2026-06-08-asian-sweep-fade]]) and asymmetric-2R ([[2026-06-10-asian-sweep-fade-rr]]) rejected; no further exit-geometry variants (needs a different entry mechanism).
