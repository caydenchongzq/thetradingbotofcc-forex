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

## Idea queue (triaged, not yet tested)
*(none — add as `status: idea` entries with a stub report)*
