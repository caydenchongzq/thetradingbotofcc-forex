# Resting-stop entry fix — handoff brief

**Status:** diagnosed 2026-06-14. `open_risk_usd` phantom-accrual bug PATCHED in
`src/engine/run.py`. The resting-stop conversion below is DESIGNED but NOT yet
implemented — it changes the live (promoted) strategy's trade population and therefore
MUST clear the full R6 gates + walk-forward + lockbox before promotion (CLAUDE.md
invariant #2, playbook step 4). Do this in its own session.

---

## 1. Why both live signals were rejected (retcode 10015 "Invalid price")

`SessionBreakoutER` emits its breakout `Signal` only **after** a 15m bar has *closed*
beyond the range edge (`strategy.py:174-177`: `last.close > long_level` / `< short_level`).
The signal carries `entry_type="stop"` and `entry_price = level` (`strategy.py:229-230`).
The live runner turns that into a **pending stop order** at the level
(`decide.py:37` → `adapter._build_order` → `action="pending"`, `buy_stop`/`sell_stop`).

By the time the bar has closed beyond the level, the level is **behind** the current
market. MT5 requires a `buy_stop` to sit *above* the market and a `sell_stop` *below* it.
So every breakout order is placed on the wrong side of the market and rejected:

| Signal | Dir | Level | Trigger (close already past level) | Order lands | MT5 |
|--------|-----|-------|-----------------------------------|-------------|-----|
| 2026-06-05 12:45 | SHORT | 1.16311 | close < 1.16311 (price below) | sell_stop **above** market | 10015 |
| 2026-06-08 13:30 | LONG  | 1.15449 | close > 1.15449 (price above) | buy_stop **below** market  | 10015 |

`entry_fill_price = 0.0`, `r_multiple = null` follow — the order never rested, let alone
filled. This is structural: it rejects **every** breakout signal identically.

### Why the backtester never caught it (the live ≠ backtest break)
The backtester models the entry as a stop **already resting at the level**, filled
intrabar at the level (`backtest/engine.py:238` → `costs.stop_entry_fill` = `level + slip`).
That is a legitimate model *only if the live path actually rests the order in advance*.
Live instead places the stop reactively, one bar too late. The backtested numbers for
`SessionBreakoutER` are therefore modelling an order the live path never submits.

### Scope — are the other backtests wrong? No.
Only **stop-entry** strategies are affected, and `SessionBreakoutER` is the only one.
All daily research candidates use `entry_type="market"` (`strategy_asian_sweep*.py`,
`strategy_trend_pullback.py`, `strategy_breakout_retest.py`, `strategy_late_drift.py`):
live sends a market deal, the backtester fills at signal price ± spread/slip
(`costs.entry_fill`), MT5 `deviation` + the requote loop absorb drift, and 10015 cannot
occur (a market order has no wrong side). Those backtests are sound and live-faithful.
The shared execution adapter is correct; the defect is the *stop-after-the-fact* timing,
which only the promoted breakout uses.

---

## 2. PATCHED already — phantom `open_risk_usd` (`run.py`)

`run.py` previously bumped `requests_used_today`, `trades_opened_today` **and**
`open_risk_usd` unconditionally after `place()`, even on rejection. Both rejected intents
therefore accumulated `349.75 + 349.01 = $698.76` of non-existent open risk that the Risk
Governor reads as live exposure and uses to under-size / gate later entries.

Fix (shipped): only `requests_used_today` increments unconditionally (a broker request was
consumed); `trades_opened_today` and `open_risk_usd` now accrue only when
`res.status is IntentStatus.FILLED`. A `Severity.WARN "entry rejected"` alert now fires on
non-fills so a future 10015 is visible immediately. **Run `py -m pytest -q` on the Windows
host to confirm** (the sandbox mount served a stale copy of this file; the host file is the
authoritative one).

> One-time cleanup: the live `state/` day-state still holds the stale `open_risk_usd =
> 698.76` from before the patch. It will self-clear at the next FTMO daily reset
> (`apply_daily_reset`), or zero it by hand if you want the Governor un-gated sooner.

---

## 3. Resting-stop conversion — design (NOT yet implemented)

Goal: make live *actually rest* the breakout stop at the level **before** the break, so it
triggers intrabar exactly as the backtester models — restoring `live == backtest` at the
entry seam. This is option (1) from review; it preserves the validated fill geometry but
changes the trade population (a resting stop fills on an intrabar **touch**, including
false breakouts that close back inside), so it needs full re-validation.

### 3.1 Strategy (`src/engine/strategy.py`)
- Split `evaluate()` into two decisions:
  1. **Arm** (new): once the opening range is complete (`last` is the first bar with
     London time ≥ `_or_end()`), compute `range_high`/`range_low`, run the regime gate +
     news blackout **at OR-end**, and if they pass, return an "arm" signal carrying BOTH
     levels (`long_level = range_high + buf`, `short_level = range_low - buf`), the
     per-side SL/TP plans, and an `expire_utc = today's win_end` (in UTC).
  2. Drop the close-confirmation trigger (`last.close > long_level`). Resting stops no
     longer wait for a close beyond the level.
- The regime read now happens at OR-end instead of at the breakout bar — this is the
  semantic shift that changes results. Keep `one_shot_per_side`: arm at most once per
  session; do not re-arm a side after it has filled or been cancelled.
- Guard: if at OR-end price has **already** traded through a level (gap/fast open), that
  side cannot rest as a stop — skip it (or fall back to a market entry for that side, but
  prefer skip to keep the model clean). Also enforce MT5 `stops_level`: if a level is
  within `symbol_meta.stops_level_pips` of current price, skip that side.

### 3.2 New intent shape (`src/execution/types.py`, `decide.py`)
- `build_entry_intent` currently builds ONE intent. Resting stops need an **OCO pair**
  (buy_stop + sell_stop). Either emit two `OrderIntent`s with a shared `oco_group` id, or
  add a `BracketIntent`. Set `order_kind="stop"`, `price=level`, and **`expire_utc`** =
  `win_end` so the adapter writes `ORDER_TIME_SPECIFIED` (already supported in
  `broker.order_send`, just currently never populated — `decide_entry` is called without
  `expire_utc` in `run.py:215`).

### 3.3 Live runner (`src/engine/run.py`) — OCO lifecycle
- At OR-end, if armed and no position/pending exists for the session, place both pending
  stops (`_exec.place` twice, or a new `place_bracket`). Record both tickets.
- Each subsequent bar: if a position has appeared (one side filled), **cancel the sibling**
  pending (`_exec.cancel(ticket)` exists). On `win_end`, cancel any unfilled pendings
  (belt-and-braces over broker expiry).
- `open_risk_usd` should accrue when a pending **fills** (position appears), not when it is
  placed — reuse the `IntentStatus.FILLED` gating just added. A resting pending that never
  fills must add zero risk.
- Mirror in `decide_manage` path / `FakeBroker` tests: an armed-but-unfilled bracket must
  reconcile cleanly on restart (`reconcile_on_startup` already classifies pendings — verify
  the OCO sibling logic survives a crash between the two placements).

### 3.4 Backtester (`src/backtest/engine.py`) — model the resting stop
This is the arbiter, so it must simulate the pending order's **intrabar touch**, not a
close-confirmed fill:
- When flat and armed (regime passed at OR-end), hold virtual `long_level`/`short_level`.
- On each in-window bar: if `bar.high >= long_level` → fill long at `long_level` (+slip);
  elif `bar.low <= short_level` → fill short at `short_level` (−slip). If a single bar
  spans both (rare), resolve by the pessimistic/open-relative ordering and document it.
- This replaces the current `_maybe_enter` close-trigger. Expect MORE trades and a lower
  win rate (false breakouts now trade) — that is the realistic cost the old model hid.
- Keep the existing intrabar SL/TP machinery (`_intrabar`) unchanged.

### 3.5 Mirror & test (CLAUDE.md invariant #3, playbook 5)
- `decide.py` (arm decision), `run.py` (OCO place/cancel), and the backtester must run the
  SAME armed-levels logic. Add `tests/engine` (arming + skip guards), `tests/backtest`
  (touch-fill, both-sides bar), and `tests/execution` (`FakeBroker` OCO place→fill→cancel,
  expiry, crash-reconcile).

### 3.6 Validate (the bar every change clears)
- `py scripts/run_backtest.py --strategy SessionBreakoutER --walkforward`
- A/B vs current HEAD v4 (`compare_exits.py` pattern).
- Must clear ALL R6 gates + walk-forward + the held-out lockbox, and not regress HEAD.
  Higher per-trade expectancy that fails the lockbox = REJECT. Raise `--trials` to the
  cumulative count. Only then promote via `ConfigStore` (reversible).

> If the resting-stop model fails the gates (plausible — false breakouts may erase the
> edge), the fallback is option (2): switch `SessionBreakoutER` to `entry_type="market"`
> and re-model the backtest entry as a close/next-open fill. That is honest but makes the
> backtest strictly less optimistic, so it too needs a fresh walk-forward + lockbox.

---

## 4. OUTCOME — option (1) IMPLEMENTED and ARBITER-REJECTED (2026-06-15)

The full resting-stop conversion was built and tested as specified in §3:
- Strategy arms a two-sided OCO at OR-end (`ArmSignal`, `src/engine/strategy.py`), regime +
  news read AT OR-end, gap/through-level skip, `expire_utc = win_end`. **Correction to §3.1:**
  the arm fires on the **final OR bar** (not the first post-OR bar) so the resting stops are
  live for the breakout bar; arming a bar later would systematically miss the first break.
- `decide.py` builds the OCO pair (two stop `OrderIntent`s sharing an `oco_group`,
  `expire_utc` populated); `OrderIntent.oco_group` added.
- Backtester models the intrabar **touch**-fill (single side, both-sides-in-one-bar by
  nearest-to-open, no-touch expiry); `open_risk` accrues on fill, never at arm.
- `run.py` OCO lifecycle: place both legs at arm, cancel the sibling when one fills, expire
  unfilled pendings past window-end, `open_risk` read from the live position on fill.
- `TrendAlignedORB` ported (filters the armed legs by trend). Full suite green
  (315 passed / 15 skipped — the skips are rejected dev candidates whose fixtures assume the
  old close-trigger incumbent: compression + two SecondEntryORB incumbent-comparison tests).

**The arbiter rejects it.** In-sample on the real Parquet (`state/parquet/eurusd_m15.parquet`,
59,993 bars, 2024-01 → 2026-05), HEAD v4 strategy code under the resting-stop model:

```
trades=158  expectancy=-0.267R  win_rate=43.7%  PF=0.56  sharpe=-2.05  maxDD=$9,346  net=-$9,346
GATES: expectancy FAIL, PF FAIL, sharpe FAIL, sortino FAIL, sample_size FAIL(158<200),
       DSR FAIL; only ftmo_no_breach PASS.  VERDICT (in-sample): FAIL.
```

It fails **in-sample**, so a walk-forward/lockbox run is moot. **Diagnosis:** close-confirmation
WAS the edge. Filling on every intrabar *touch* admits the false breakouts that close back
inside the range (the incumbent's 73%-win 1R came from only trading bars that *closed* beyond
the level); win rate collapses 73% → 44% and per-trade expectancy goes negative. The
regime-at-OR-end shift compounds it (fewer, quieter setups → 158 vs the incumbent's ~224).

**Do NOT promote, and do NOT deploy this code to live as-is.** Because the change edits the
*promoted* `SessionBreakoutER` in place, a live runner built from HEAD v4 would now run this
losing model. (Live is currently not trading it anyway — the retcode-10015 bug rejects every
breakout — so nothing regresses by leaving it un-deployed, but it must not be shipped.)

### 4.1 Recommended next step — option (2), market entry preserving close-confirmation
Keep the incumbent's **close-confirmation selectivity** (the edge) and only fix the *order
type* that caused 10015: emit `entry_type="market"` on a bar that CLOSES beyond the level,
filled at that close / next-open (re-model `costs.entry_fill` for the breakout in the
backtester). A market order has no wrong side, so 10015 cannot occur, and the trade
population is the incumbent's profitable one. This is a *different, smaller* change than the
resting-stop conversion and needs its own fresh walk-forward + lockbox before promotion.

This resting-stop implementation should either be (a) reverted from the incumbent and kept as
a **dev-isolated** strategy (registered, never promoted) for the record, or (b) discarded in
favour of option (2). That decision is the human's (see session hand-off).

---

## 5. OUTCOME — option (2) market entry ALSO fails; the edge is an unfillable artifact (2026-06-15)

Implemented (kept): incumbent `SessionBreakoutER` is now **close-confirmation + MARKET entry**
(`entry_type="market"`, `entry_price = the confirmed close`), with exits **anchored to the
level** (the validated geometry). The resting-stop variant was moved to a registered DEV
strategy `SessionBreakoutERResting` (`src/engine/strategy_resting.py`) so the OCO infrastructure
(ArmSignal → decide OCO → backtester touch-fill → run.py OCO lifecycle → `oco_group`) stays
intact and reusable by any future touch-fill strategy. A config lever `entry.mode`
("market" | "stop") was added to A/B the two fills.

**A/B on the real Parquet (59,993 bars), same 224-trade selection, same SL/TP levels — only the
FILL differs:**

| entry mode | fill price | trades | expectancy | win | PF | sharpe |
|------------|-----------|--------|-----------|-----|-----|--------|
| `stop` (the pre-fix v4 backtest) | at the level (intrabar) | 224 | **+0.391R** | 73.2% | 2.39 | 4.20 |
| `market` (live-faithful) | at the confirmed close | 224 | **−0.024R** | 59.4% | 0.79 | −0.91 |
| resting-stop touch (§4) | at the level, ALL touches | ~? | **−0.267R** | 44% | 0.56 | — |

**Conclusion — the strategy has no live-realizable edge as designed.** The entire +0.391R comes
from *filling at the level during the breakout bar*. That fill is not live-achievable:
- To fill **at the level** you must rest an order **before** the bar → a resting stop → which
  fills on **every touch**, including the false breakouts close-confirmation screens out
  (−0.267R).
- To **select** only the breakouts that **close** beyond the level you must wait for the close
  → by then the market is at the close, not the level → market fill (−0.024R).

Selection (needs the close) and the level-fill (needs to act before the close) are temporally
incompatible with a single order. The pre-fix backtest scored +0.391R only because it modelled
a stop filled at the level that the live path then could not place (retcode 10015) — i.e. the
profitability was a **backtest artifact of an unfillable entry**, and the 10015 bug had been
masking it by stopping the strategy from trading at all.

### 5.1 Where this leaves things
- **Live safety:** the incumbent is now live-*placeable* (market order, no 10015). But it is
  **not profitable** (−0.024R in-sample, fails the expectancy/PF/Sharpe gates) so it must **not
  be promoted** as-is. Do not deploy expecting the old numbers.
- **Decision (human):** SessionBreakoutER needs a genuine **strategy rethink**, not an entry
  patch. Candidate directions, each a fresh research-engine candidate (spec 08) needing its own
  walk-forward + lockbox:
  1. **Tight-overshoot filter on market entry** — only take breakouts whose close is within ~X
     pips of the level, so the market fill ≈ the level fill. **PROBED 2026-06-15 and rejected:**
     `entry.max_overshoot_pips` swept {5,3,2,1,0.5} → best is ≤3 pips at **+0.008R / PF 1.05 /
     99 trades** — still below the +0.10R gate and the 200-trade floor; tighter is worse. The
     edge was the intrabar level-fill capturing the breakout bar's continuation, not close≈level.
     (Lever kept in `strategy.py`, default off, for future research.)
  2. **Retest/limit entry** — rest a limit at the level for a pullback fill (but
     [[BreakoutRetestER]] was already anti-selective).
  3. **Accept market entry and re-tune exits** (wider R:R / trend runner) to fit the later fill.
  4. **Retire SessionBreakoutER** as not live-viable and reallocate to other candidates.
- The resting-stop and market-entry code + the `entry.mode` lever + `SessionBreakoutERResting`
  are kept so any of the above can be A/B'd immediately.
