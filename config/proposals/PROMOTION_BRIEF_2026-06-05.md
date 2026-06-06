# Promotion Brief — Backtest Analyst run 2026-06-05

**Verdict for all four unprocessed proposals: REJECTED (validation).** None reached the backtester. Each is **stale** — its `parent_config_version` no longer matches the live HEAD, which has advanced to **v4**. `process_proposal.py` rejects stale proposals before running any backtest, so there are no in-sample metrics, OOS fold stats, or lockbox results to report. This is a structural rejection and was **not** counted as a trial (period 2026-W23 cumulative trials still = 1, cap 4).

The optimizer proposal `2026-06-03-opt-084109` (the only other file present) was already processed and **promoted to HEAD v4** — it is not re-run.

## Current HEAD (v4)
`regime.er_threshold = 0.32`, `regime.atr_floor_pips = 5.0` (SessionBreakoutER). v4 = v3 (human exit-parity fix, single 1R target) + optimizer's ER 0.30→0.32.

## Per-proposal

| Proposal | File | Change | Parent | Verdict |
|---|---|---|---|---|
| 2026-06-02-w23-001 | example.json | ER 0.30 → 0.38 | v1 | REJECTED — stale (v1 ≠ v4) |
| 2026-06-02-w23-002 | er_033.json | ER 0.30 → 0.33 | v1 | REJECTED — stale (v1 ≠ v4) |
| 2026-06-02-w23-003 | atr_floor_5.json | ATR floor 4.0 → 5.0 | v1 | REJECTED — stale (v1 ≠ v4) |
| 2026-06-03-w23-exits-scaleout | scaled_exits_example.json | scale-out 50% @1R, BE, runner 2R | v3 | REJECTED — stale (v3 ≠ v4) |

## Notes for Cayden
- **Two of these are now moot.** HEAD already carries `atr_floor_pips = 5.0` (exactly what `atr_floor_5.json` proposed) and `er_threshold = 0.32` (already past `er_033`'s 0.33 target and partway to `example`'s 0.38). They were written against v1 and the world moved on.
- **`scaled_exits_example.json` is the intentional worked-example reject** (per its own hypothesis and `docs/EXIT_MODEL.md`) — it fails the lockbox for SessionBreakoutER. Stale-rejection here just short-circuits that.
- **No promotions to recommend.** Nothing passed the gates because nothing ran the gates.
- **If you still want to test a higher ER gate** (e.g. 0.38) on top of the current v4, regenerate the proposal with `parent_config_version: 4` and the correct `from` value (`er_threshold` from 0.32), then re-run `py scripts\process_proposal.py config\proposals\<file>.json`. Only that will produce a real backtest verdict.

_No `--approve` was run; no config was promoted; no trades placed; gates untouched._
