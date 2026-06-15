---
id: 2026-06-15-london-open-breakout-er
name: LondonOpenBreakoutER
family: breakout
status: idea                     # researched + triaged; NOT yet built/tested (run blocked — see below)
related: [2026-06-02-session-breakout-er, 2026-06-14-trend-aligned-orb, 2026-06-13-second-entry-orb, 2026-06-07-pre-session-compression-filter]
sources:
  - "https://www.quantifiedstrategies.com/london-breakout-strategy/"
  - "https://www.forex.com/en-uk/trading-academy/courses/advanced-strategies/uk-open-range-breakout/"
  - "https://www.litefinance.org/blog/for-beginners/trading-strategies/opening-range-breakout-strategy/"
  - "https://titanfx.com/education/london-forex-trading-session-trading-strategies"
  - "https://www.forexfactory.com/thread/296776-eurusd-session-breakout-and-reverse-strategy"
trials_used: 0
verdict: "Idea — strongest build candidate in the queue. Applies the validated overlap-ORB mechanism to the INDEPENDENT London-open session, escaping the 200-trade-floor trap that killed the subtractive-filter family. NOT built this run: working tree dirty with the uncommitted resting-stop refactor — build once HEAD is clean."
---

# LondonOpenBreakoutER — the validated ORB+ER+ATR mechanism on the London-open session

## Hypothesis & market rationale
The incumbent `SessionBreakoutER` trades exactly one window: the London/NY **overlap**
(13:00–16:00 London), a peak-liquidity *continuation* regime. The **London open** (~08:00
London) is a structurally different and, in the practitioner literature, the single most
consistent breakout window in FX: ~35–40% of daily turnover enters at the London open, and the
session opens against a compressed overnight (Asian) range, so the first directional expansion
is an *initiation* move rather than a mid-trend continuation.

Falsifiable claim: **the same opening-range-breakout edge the incumbent harvests at the overlap
also exists at the London open**, and because the London-open window is a *different time of day*
it produces an **independent trade stream** — not a subset of the incumbent's ~224 trades. If
true, a London-open ORB clears the R6 gates on its own base; if the open is pure noise (efficient
re-pricing of the Asian range), the ER/ATR regime gate should reject most of it and the candidate
fails honestly on edge, not on trade count.

Who is on the other side: overnight mean-reversion desks and Asian-range faders whose stops sit
just beyond the pre-London range; the institutional order flow that arrives at 08:00 runs them.

## Sources
- QuantifiedStrategies — *London Breakout Strategy: Rules and Backtest Performance*
  (https://www.quantifiedstrategies.com/london-breakout-strategy/). **Key caveat, not a green
  light:** a *naive* "buy above / sell below the Asian range" on EUR/USD "often result[s] in
  losses." This is the differentiator, not a refutation — see Relation to prior work.
- FOREX.com — *The Opening Range Breakout Strategy (European/UK open)*: define the range in the
  half-hour before the 08:00 London open; EUR/USD is the canonical pair
  (https://www.forex.com/en-uk/trading-academy/courses/advanced-strategies/uk-open-range-breakout/).
- LiteFinance — *ORB success rate 40–60%, filter-dependent*
  (https://www.litefinance.org/blog/for-beginners/trading-strategies/opening-range-breakout-strategy/).
- TitanFX — London session is the highest-volume session (~35% of turnover)
  (https://titanfx.com/education/london-forex-trading-session-trading-strategies).
- Forex Factory — *EURUSD Session Breakout and Reverse* community thread (mechanism only, no
  performance claim) (https://www.forexfactory.com/thread/296776-eurusd-session-breakout-and-reverse-strategy).

All hypothesis-only. No community code copied; the implementation re-uses our own audited
`SessionBreakoutER` machinery (below). The backtester is the arbiter.

## Relation to prior library work
- **Builds on [[2026-06-02-session-breakout-er]] (promoted incumbent):** identical mechanism —
  opening-range break, ER≥threshold + ATR-normal regime gate, `max(structural, 1.2×ATR)` stop,
  single-1R target, break-even `manage()`. The *only* change is the session window
  (`session.window_start/window_end`). This is deliberate: it isolates one variable (does the
  edge transfer to a new session?) and inherits a fully validated exit/management seam.
- **Escapes the failure mode that killed the filter family
  ([[2026-06-14-trend-aligned-orb]], [[2026-06-07-pre-session-compression-filter]]):** every
  subtractive filter to date dies on the **200-trade hard floor** because the incumbent's base is
  only ~224 (just 24 above the floor). TrendAlignedORB *dominated* HEAD on every quality axis yet
  was rejected for cutting to 149 trades. LondonOpenBreakoutER is **not subtractive** — it does
  not touch the incumbent's trades; it generates its **own** base from a different time of day, so
  it is bounded by its own trade count, not by the incumbent's 24-trade headroom.
- **Differs from [[2026-06-13-second-entry-orb]] (additive-but-dominated):** SecondEntryORB added
  *same-session* re-break entries that diluted the incumbent's expectancy (~+0.04R each). This
  candidate adds a *different-session* stream; it is intended to **stand alone**, judged on its own
  gates, not appended to the incumbent's trades.
- **Re the QuantifiedStrategies "naive London breakout loses" caveat:** the recorded loss is for an
  *un-gated* Asian-range break. Our mechanism only fires inside an ER≥thr + ATR-normal regime —
  precisely the filter the literature says naive London breakouts lack. The candidate is therefore
  a *gated* London ORB, not the naive one shown to lose; if the gate cannot rescue it, the arbiter
  records that cleanly.

Not a variant of any closed family (sweep-fade, trend-continuation). Dedup: no existing library
entry tests a non-overlap session.

## Strategy spec
- **Session:** London open. Window `08:00–11:00` Europe/London (a 3-hour span mirroring the
  incumbent's 3-hour overlap window, to give a comparable trade count), opening-range
  `opening_range_minutes: 30` (range = 08:00–08:30), one-shot per side.
- **Entry:** first bar that breaks `range_high + buffer` (long) / `range_low − buffer` (short),
  using the incumbent's exact entry logic (whichever entry model is HEAD at build time — inherit,
  do not fork).
- **Regime gate:** unchanged — `efficiency_ratio ≥ er_threshold` and ATR in the normal band. The
  ER is computed on the bars leading into 08:00 (i.e. the Asian session), which is the correct
  read of "is the overnight range coiled or already trending."
- **News gate:** unchanged EUR/USD high-impact blackout. Note: 08:00–11:00 London catches several
  EUR data releases (German/EZ prints at ~07:00–10:00 London) — the blackout matters more here than
  at the overlap; verify it engages.

**Exit geometry (spec 08 §5.8 — pre-registered):**
- **Stop:** `max(structural_range_stop, 1.2×ATR)` — *inherited deliberately*, with rationale: the
  entry is the same range-break momentum structure as the incumbent, so the stop that the
  *structure* implies (opposite end of the opening range, floored at 1.2×ATR so a tight range does
  not noise-out the trade) is the geometry this mechanism implies, not an unexamined default.
- **Target:** single **1R** (R:R = 1:1). Why 1R fits here and a ≥2R variant is **pre-closed**: the
  exhaustive incumbent exit record — the ≥2R sweep ([[2026-06-07-tp-2r-sweep]], all 18 failed DSR +
  lockbox) and the scaled-runner full exit model ([[2026-06-03-full-exit-model]], rejected) —
  establishes that this exact breakout mechanism on EUR/USD M15 rewards a high-win-rate ~1R
  structure and punishes high-R targets. Since the London-open entry is the *same mechanism*, that
  finding transfers a priori; a 2R London-open variant would share the recorded failure mode and is
  forbidden under §4.3 unless it brings a new differentiator. **1R is justified by
  mechanism-equivalence, not inherited by reflex.**
- This reuses the incumbent's validated `manage()` (break-even after 1R) byte-for-byte ⇒ **no new
  manage semantics, no live-mirror session required**; only the session config differs.

**Params to expose as `ALLOWED_LEVERS` if ever promoted:** `session.window_start`,
`session.window_end`, `session.opening_range_minutes` (the rest are already levers on the
incumbent).

## Implementation notes (planned — NOT executed this run)
- Additive only: a thin `class LondonOpenBreakoutER(SessionBreakoutER)` in a new module
  `src/engine/strategy_london_open.py` that sets London-open session defaults and inherits
  `evaluate`/`manage` verbatim (no mechanism fork — this guarantees the A/B isolates the session
  variable and that whatever entry model is HEAD is the one tested). One `register(...)` line.
  Unit tests under `tests/engine` (arms in 08:00–11:00, silent in 13:00–16:00; regime/blackout
  paths) and a `tests/backtest` smoke test.
- No writes to `state/`; no live-path edits; never `ConfigStore.promote`.

## Backtest results
**Not run.** Validation command for the next run (sandbox-chunked if needed):
`py scripts/run_backtest.py --strategy LondonOpenBreakoutER --walkforward --trials <cumulative+1>`
(cumulative is **165** after [[2026-06-14-trend-aligned-orb]] ⇒ use `--trials 166`), plus an A/B
vs HEAD via the `scripts/compare_exits.py` pattern. Judge on the R6 gates + walk-forward +
lockbox, never raw expectancy.

| metric | gate | candidate | incumbent HEAD |
|---|---|---|---|
| (pending — build blocked this run) | | | |

## Verdict
**Idea / not tested this run.** Build was deliberately **not** started because the working tree is
mid-refactor: the rejected resting-stop conversion (`docs/RESTING_STOP_FIX.md`,
`tests/engine/test_resting_stop.py`, and ~1,900 lines of uncommitted diff across
`src/engine/strategy.py`, `decide.py`, `run.py`, `src/backtest/engine.py`, execution/journal
types, and ~12 test files) is sitting uncommitted on top of HEAD v4. Backtesting now would (a) run
my candidate's inherited `evaluate` against the **resting-stop** base, not the validated close-based
HEAD, and (b) make any "A/B vs HEAD" compare against a strategy the library has already recorded as
do-not-deploy (win 73%→44%, −0.267R). Per spec 08 §5.5 (fail safe on ambiguous tooling state), this
run does research + triage only and leaves the code tree untouched.

## Lessons
- **The trade-floor wall has a structural escape: a new session, not a new filter.** Every quality
  improvement attempted so far was *subtractive* on the incumbent's 224-trade base and died at the
  200 floor. The way to buy more quality headroom is to *add an independent trade base* (a second
  session), not to keep slicing the existing one. This reframes the library's recurring killer as an
  argument *for* multi-session research, distinct from the additive-same-session dilution that sank
  SecondEntryORB.
- **Process lesson (this run):** an autonomous research run must check `git status` before
  backtesting. A dirty working tree that has modified the incumbent base class silently invalidates
  every `--strategy <candidate>` A/B (subclasses inherit the contaminated base). Added to the
  orientation checklist conceptually for future runs.

## Next steps
1. **Unblock:** Cayden resolves the working-tree resting-stop state (commit the pivot, revert it, or
   stash to a branch) so HEAD v4 is the clean base again.
2. Build LondonOpenBreakoutER per the spec above (thin subclass, additive), pytest green.
3. Validate `--walkforward --trials 166` + A/B vs HEAD. **Key risk to watch:** whether the
   London-open window clears the **200-trade floor on its own** (a 3-hour window with the ER/ATR gate
   may pass fewer trades than the overlap if the open is choppier) — estimate the gated trade count
   first; if < 200, this becomes `blocked-on-data` (needs longer history) like
   [[2026-06-14-trend-aligned-orb]], not a re-test.
4. If London-open stands alone, a later candidate could *combine* both sessions into one strategy to
   roughly double the base — directly buying the headroom that would let TrendAlignedORB's
   quality-veto pass the floor.
