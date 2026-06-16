# Promotion Brief — 2026-06-16 (Backtest Analyst)

**Verdict: nothing to promote.** No genuine pending proposals. Today's only real candidate was already processed (failed) by the research engine before this run; the lone non-fixture file in `config/proposals/` is a malformed no-op; 4 template/seed files deliberately skipped. **HEAD stays v4.**

## Today's research candidate — already processed (no action)

### `2026-06-16-vwap-stretch-reversion` — FAILED
- Processed by the research engine at **2026-06-16T01:00:02Z**; recorded `status: failed` in `state/config/trial_ledger.jsonl`.
- No JSON sits in `config/proposals/` (engine self-records its own runs); strategy lives in `src/engine/strategy_vwap_reversion.py` with dev config `config/dev/vwap_reversion.yaml` and writeup `docs/research/strategies/2026-06-16-vwap-stretch-reversion.md`.
- Already a terminal ledger entry, so it is correctly out of scope for re-processing. No trial double-count.

## Processed this run

### `opt_2026-06-07-opt-025424.json` — REJECTED (validation)
- **Result:** `REJECTED_VALIDATION` — *"empty diff: a proposal must change at least one lever."*
- Backtester / walk-forward / lockbox **never ran** (failed the pre-flight lever check) → no expectancy / PF / Sharpe / fold / lockbox numbers exist.
- **No trial consumed, ledger unchanged** (still ends at `vwap-stretch-reversion`). Cumulative DSR trial count unaffected.
- **Root cause (unchanged from the 06-15 brief):** optimizer-authored against parent v4, but its June-7 sweep over `exits.target_r_multiples` + `exits.move_be_after_r` found nothing beating v4, so the "winner" equals HEAD and serialized to `diff: []` — a no-op. Consistent with the ≥2R-target family being closed (`tp-2r-sweep-rejected`).
- **Action for Cayden:** none required. Safe to delete `config/proposals/opt_2026-06-07-opt-025424.json` so it stops resurfacing each run.

## Skipped (not genuine pending proposals)

Left unprocessed deliberately — running them through the arbiter would inject junk trials and tighten the DSR penalty against real future proposals. The daily analyst has correctly never processed them since W23:

- **`example.json`** (`2026-06-02-w23-001`) — the template proposal referenced in CLAUDE.md; parent v1 (HEAD is v4).
- **`er_033.json`** (`2026-06-02-w23-002`) — stale W23 seed, parent v1.
- **`atr_floor_5.json`** (`2026-06-02-w23-003`) — stale W23 seed, parent v1.
- **`scaled_exits_example.json`** (`2026-06-03-w23-exits-scaleout`) — explicit "worked example, EXPECTED TO BE REJECTED" (fails the lockbox per `docs/EXIT_MODEL.md`); parent v3.

## Recommendation
Nothing to review or promote today. HEAD remains **v4**. Optional cleanup: delete the empty-diff `opt_2026-06-07-opt-025424.json` and, if desired, the 4 fixture files, to stop them re-surfacing in each daily run.

*Note for context:* the processor reported `period 2026-W25, cap 10` already at `cumulative trials=12` — the W25 weekly trial budget is spent. Worth keeping in mind before queuing fresh sweeps this week.
