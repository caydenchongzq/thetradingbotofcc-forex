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

## Idea queue (triaged, not yet tested)

| id | name | family | status | one-line |
|---|---|---|---|---|
| [2026-06-07-intraday-ts-momentum](2026-06-07-intraday-ts-momentum.md) | IntradayTSMomentum | trend | idea | London a.m. return → NY p.m. return (Gao et al. 2015 analog); equity evidence only |
| [2026-06-08-london-fix-reversal](2026-06-08-london-fix-reversal.md) | LondonFixReversal | mean-reversion | idea | Fade the pre-fix drift after the 16:00 London WM/R fix; paper-backed (arXiv:1501.07778), strongest month-end |
| [2026-06-07-cross-instrument-confirmation](2026-06-07-cross-instrument-confirmation.md) | CrossInstrumentConfirmation | filter | blocked-on-data | Needs multi-instrument export AND longer history (filter trade-count cap) |

> Retired idea stubs: [2026-06-07-asian-sweep-fade](2026-06-07-asian-sweep-fade.md) (tested 2026-06-08 → rejected).
