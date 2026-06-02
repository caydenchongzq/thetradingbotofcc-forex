# 01 — Strategy Engine (R1)

> The deterministic signal producer. Implements the R1 recommendation: a **session-gated London/NY-overlap volatility breakout on 15m EURUSD**, hard-gated by an **Efficiency-Ratio (ER) + ATR regime filter**. It mines the reference Pine script's regime ideas (ER, ATR-regime band) but **does not** port its laggy SuperTrend-flip entry or its unvalidated "self-learning".
>
> Position in the spine: produces a `Signal`; hands it to the **Risk Governor (02)** which sizes/vetoes; approved orders go to **Execution (03)**. The engine is **swappable** — the same `Strategy` interface is driven by the live loop and the **backtest harness (05)** so a candidate is validated on exactly the code that will trade it.
>
> Hard constraints it must respect: AI never inline (README §2); no trades around major news or ≤2h before a 2h+ close (R4 gap rule — enforced by the engine's blackout check *and* re-checked by risk); request-budget discipline (don't modify every bar); fail-safe on stale/missing data.

---

## 1. Responsibilities (and non-responsibilities)

**Owns:** computing, on each closed bar, whether a valid entry exists; the entry price, direction, initial stop, and target/exit plan expressed in **R-multiples and price levels** (never in lots — sizing is the Risk Governor's job); regime classification; session gating; the deterministic news/holiday blackout check; and the trade-management plan (break-even move, trailing step, partial-TP levels) expressed as rules the execution layer can apply on a throttled cadence.

**Does NOT own:** position size or lot count (02), order placement/modification (03), the FTMO loss accounting (02/04), or any LLM call. It reads market data and config; it emits intent.

**Purity requirement:** given the same bar history + config + `context_bias`, the engine is a **pure function** — identical input ⇒ identical `Signal`. No wall-clock reads except a single injected "now" for session/blackout math, no network, no hidden state beyond what is passed in. This is what makes it backtestable and reproducible.

---

## 2. Interfaces

All times are timezone-aware UTC internally; session windows are defined in Europe/London and converted. Prices are `Decimal` or scaled ints to avoid float drift at the pip level; ER/ATR math may use float.

```python
# src/engine/types.py
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional

class Direction(str, Enum):
    LONG = "long"
    SHORT = "short"

class VolState(str, Enum):
    LOW = "low"        # ATR below band → too quiet, breakout unreliable
    NORMAL = "normal"  # ATR inside band → tradeable
    HIGH = "high"      # ATR above band → too wild for fixed-R sizing safety

class ContextBias(str, Enum):       # the optional R8 seam; default NORMAL forever until proven
    NORMAL = "normal"
    CAUTIOUS = "cautious"           # may reduce size (risk's choice), never forces a trade
    STAND_DOWN = "stand_down"       # engine emits no new entries

@dataclass(frozen=True)
class Bar:
    ts_open_utc: datetime           # bar OPEN time; engine only ever acts on CLOSED bars
    open: float; high: float; low: float; close: float
    volume: float
    # `is_closed` guaranteed True for bars passed to evaluate(); live loop never passes a forming bar

@dataclass(frozen=True)
class RegimeState:
    er: float                       # Efficiency Ratio over `regime.er_window` bars, 0..1
    er_threshold: float             # the gate in force (post context-bias adjustment)
    atr_pips: float
    atr_percentile: float           # ATR rank vs trailing window, 0..1
    vol_state: VolState
    regime_gate_passed: bool        # True only if ER >= threshold AND vol_state == NORMAL

@dataclass(frozen=True)
class ExitPlan:
    initial_sl_price: float
    initial_sl_pips: float
    targets: tuple[float, ...]            # price levels for scaled TPs (R-multiples resolved to price)
    target_r_multiples: tuple[float, ...] # e.g. (1.0, 2.0) — parallel to `targets`
    partial_fractions: tuple[float, ...]  # fraction of position to close at each target, sums <= 1.0
    move_be_after_r: Optional[float]      # move stop to break-even after this R reached (None = never)
    trail: Optional["TrailRule"]          # throttled trailing rule, or None

@dataclass(frozen=True)
class TrailRule:
    activate_after_r: float         # only start trailing past this R
    step_pips: float                # move stop in discrete steps (request-budget friendly)
    distance_pips: float            # trail this far behind price
    min_seconds_between_modifies: int  # hard throttle so we never modify every bar (R4 2k/day cap)

@dataclass(frozen=True)
class Signal:
    instrument: str                 # "EURUSD"
    ts_decision_utc: datetime
    direction: Direction
    entry_type: str                 # "stop" (breakout) — entry placed at the broken level
    entry_price: float              # the breakout level
    exit_plan: ExitPlan
    regime: RegimeState
    session: str                    # "london_ny_overlap"
    breakout_level: float
    entry_reason: str               # human-readable, logged verbatim to the journal
    context_bias: ContextBias       # what was in force at decision time (audit)
    config_version: int             # which strategy config produced this signal

@dataclass(frozen=True)
class NoSignal:
    ts_decision_utc: datetime
    reason: str                     # "outside_session" | "regime_gate_failed" | "no_range_break"
                                    # | "news_blackout" | "stand_down" | "stale_data" | ...
    # NoSignal with reason != "no_range_break"/"outside_session" is logged as a *rejected signal*
```

### 2.1 The Strategy interface (swappable contract)

```python
# src/engine/strategy.py
from typing import Protocol, Sequence, Union

class Strategy(Protocol):
    name: str
    config_version: int

    def warmup_bars(self) -> int:
        """Minimum closed bars of history required before evaluate() is valid."""

    def evaluate(
        self,
        bars: Sequence[Bar],          # chronological, oldest→newest, last element is the just-CLOSED bar
        now_utc: datetime,            # injected clock for session/blackout math
        context_bias: ContextBias,    # default NORMAL; from the cached R8 seam, never blocks via LLM inline
        calendar: "EconomicCalendar", # deterministic news/holiday source (injected)
    ) -> Union[Signal, NoSignal]:
        ...

    def manage(
        self,
        open_trade: "OpenTradeView",  # current position state from MT5/journal (read-only)
        bars: Sequence[Bar],
        now_utc: datetime,
    ) -> "ManageAction":              # {hold | move_sl(price) | partial_close(fraction) | close_all}
        """Throttled trade management; called at most once per closed bar AND respecting
        TrailRule.min_seconds_between_modifies. Returns hold most of the time by design."""
```

The live loop and the backtester both call exactly these two methods. No other surface. A new candidate strategy is a new `Strategy` implementation validated through spec 05 before it can be promoted.

---

## 3. Algorithm (the recommended first strategy)

`SessionBreakoutER` — the concrete `Strategy` implementing R1's pick.

### 3.1 Session gate
1. Define the **London/NY overlap** window in config (default 13:00–16:00 Europe/London ≈ 12:00–15:00 UTC in summer; resolved via tz database, not a fixed offset). Plus a configurable **opening-range** sub-window at the session start used to build the breakout level.
2. If `now_utc` is outside the trading window → `NoSignal("outside_session")` (not logged as a rejection — it's just "not time").
3. If `context_bias == STAND_DOWN` → `NoSignal("stand_down")` (logged as rejection).

### 3.2 Opening-range breakout level
1. During the opening-range sub-window, track `range_high = max(high)` and `range_low = min(low)` over those bars.
2. After the sub-window closes, the **breakout levels** are `range_high` (long) and `range_low` (short), each offset by a configurable `breakout_buffer_pips` to avoid wick-noise triggers.
3. A long signal arises when a **closed** bar's close > `range_high + buffer`; short symmetrically below `range_low − buffer`. (Entry is then a stop order at the level per §3.5 — we trade the break, not the close, to control slippage.)
4. One breakout per side per session (a fired side is disabled until the next session) to bound trade count and request budget.

### 3.3 Regime gate (ER + ATR) — the hard filter
Computed on the bar history *before* admitting any breakout:

- **Efficiency Ratio** over `regime.er_window` bars (default 14): `ER = |close_t − close_{t-n}| / Σ|close_i − close_{i-1}|`. ER∈[0,1]; high ER = directional/efficient market (trend/clean breakout), low ER = chop. Gate: `ER >= er_threshold` (default 0.30, a tuneable lever).
- **ATR band**: compute `atr_pips` (Wilder ATR, `regime.atr_window`, default 14) and its percentile vs a trailing window. `vol_state` = LOW if `atr_pips < atr_floor_pips` or percentile < `atr_low_pct`; HIGH if `> atr_ceiling_pips` or percentile > `atr_high_pct`; else NORMAL.
- `regime_gate_passed = (ER >= er_threshold) AND (vol_state == NORMAL)`.
- If the gate fails → `NoSignal("regime_gate_failed")`, logged as a rejected signal **with the ER/ATR values** so the improvement loop can segment performance by regime (R5 §4).

Why this and not the Pine script's SuperTrend flip: ER + ATR-band is a *leading* condition on whether a breakout is likely to follow through, computed without the lag of a trend-following crossover; we keep the reference script's *regime intuition* and discard its *laggy entry trigger* and *unvalidated self-tuning* (R1).

### 3.4 News / session-edge blackout (deterministic)
1. Query the injected `EconomicCalendar` for high-impact events on EURUSD's currencies (EUR, USD) within `blackout.before_min` / `blackout.after_min` of `now_utc`.
2. Also block new entries `blackout.before_2h_close_min` before any scheduled 2h+ market close/weekend (FTMO gap rule).
3. If blacked out → `NoSignal("news_blackout")`, logged. **This is re-checked by the Risk Governor as defence-in-depth** — the engine should never be the only thing standing between us and the gap rule.

### 3.5 Entry, stop, targets
- **Entry**: a **stop order** at `breakout_level (± buffer)` with an expiry at session end (no fill ⇒ cancelled, no carry).
- **Initial SL**: `max(structure_stop, atr_mult_sl × atr_pips)` where `structure_stop` is the opposite side of the opening range; expressed in price and pips. SL distance feeds 02's sizing directly.
- **Targets**: R-multiple TPs (default `(1.0R, 2.0R)`), `partial_fractions` default `(0.5, 0.5)`; `move_be_after_r` default `1.0` (move to break-even after first target). All tuneable levers.
- **Trailing**: optional `TrailRule`, **off by default** in v1 (trailing every bar is the classic request-budget killer); if enabled, `min_seconds_between_modifies` and `step_pips` bound the modify rate.

### 3.6 `context_bias` seam (R8, default off)
- `NORMAL` (always, until R8 proves otherwise): no effect.
- `CAUTIOUS`: the engine still emits the signal unchanged; it only *tags* it cautious. **Size reduction is the Risk Governor's decision**, not the engine's — the engine never silently shrinks a trade.
- `STAND_DOWN`: engine emits no new entries (existing trades still managed normally).
- The bias is **read from a cached value** written by the (deferred) shadow-mode overlay; the engine never calls an LLM to obtain it. If the cache is missing/stale → treat as `NORMAL` (fail toward the proven default).

---

## 4. Configuration schema

All levers live in the versioned strategy config (see 06/08). Every field below is a candidate the Strategy Researcher may propose changing; none are hard-coded in source.

```yaml
strategy:
  name: SessionBreakoutER
  instrument: EURUSD
  timeframe: 15m                       # R1 floor; 5m/1m only if a backtest proves edge clears costs
session:
  tz: Europe/London
  window_start: "13:00"
  window_end:   "16:00"
  opening_range_minutes: 30            # sub-window to build the breakout level
  one_shot_per_side: true
breakout:
  buffer_pips: 1.5
  entry_order_type: stop
  cancel_at_session_end: true
regime:
  er_window: 14
  er_threshold: 0.30                   # ← key lever
  atr_window: 14
  atr_floor_pips: 4.0
  atr_ceiling_pips: 22.0
  atr_low_pct: 0.20
  atr_high_pct: 0.90
exits:
  atr_mult_sl: 1.2
  target_r_multiples: [1.0, 2.0]
  partial_fractions: [0.5, 0.5]
  move_be_after_r: 1.0
  trail: null                          # disabled in v1
blackout:
  high_impact_currencies: [EUR, USD]
  before_min: 15
  after_min: 15
  before_2h_close_min: 120
context_bias:
  enabled: false                       # R8 seam off; engine reads cache only when true
  cache_path: state/context_bias.json
  stale_after_seconds: 3600
```

---

## 5. Error handling & fail-safe

| Condition | Engine behaviour |
|---|---|
| Fewer than `warmup_bars()` of history | `NoSignal("insufficient_history")`; never guess |
| Last bar not closed / out-of-order timestamps | Refuse: `NoSignal("bad_bar_sequence")`; log health row |
| Stale data (last bar older than 1.5× timeframe during an active session) | `NoSignal("stale_data")` → triggers R3 fail-safe (hold/flatten), **never a new trade** |
| `context_bias` cache missing/stale | Treat as `NORMAL` (proven default), log a warning |
| Calendar source unavailable | **Fail closed**: treat as blackout (`NoSignal("news_blackout_calendar_unavailable")`) — never trade blind into possible news |
| NaN/inf in ER/ATR (degenerate window) | Gate fails closed (`regime_gate_passed=False`), log health row |

The principle (README §2 "fail safe, not open"): every ambiguous or degraded state resolves to **no new trade**, and the only actions that *reduce* risk (manage/close existing) remain available.

---

## 6. Test plan

**Unit (pure, no I/O):**
- ER computation against hand-worked vectors (pure trend ER≈1, pure chop ER≈0, flat→0/0 guarded).
- ATR / percentile / `vol_state` classification at band edges (LOW/NORMAL/HIGH boundaries inclusive-exclusive correctness).
- Session gate across the **summer/winter DST boundary** (London ↔ UTC offset change) — explicit fixture dates.
- Opening-range build, buffer offset, one-shot-per-side exhaustion.
- `regime_gate_passed` truth table (ER pass/fail × vol_state low/normal/high).
- Blackout windows: event exactly at edge of `before_min`/`after_min`; 2h-close rule; calendar-unavailable fails closed.
- `context_bias`: NORMAL no-op, CAUTIOUS tags-only (size unchanged in signal), STAND_DOWN suppresses entries, stale cache → NORMAL.
- ExitPlan math: SL = max(structure, ATR-based); R-multiple targets resolved to correct prices for long and short; partials sum ≤ 1.0.

**Property-based:**
- **Determinism:** same `(bars, now, bias, calendar)` ⇒ identical `Signal` (run N times, assert equality).
- Engine never emits an entry when `regime_gate_passed` is False, in any input.
- Engine never emits an entry during a blackout, in any input.

**Golden-tape:**
- A fixed EURUSD 15m fixture with a hand-annotated expected sequence of Signals/NoSignals (the same fixture used in 05 milestone A3). The engine must reproduce it exactly; this tape is the regression guard for every future change.

**Integration (via the backtest harness, spec 05):**
- Full A4 validation run on Dukascopy tick→15m history; must clear all R6 gates including zero simulated FTMO breaches before the strategy is allowed live.

---

## 7. Open tuning questions (handed to the improvement loop, not hard-coded)
- `er_threshold`, `atr` band edges, `opening_range_minutes`, `move_be_after_r`, whether trailing earns its request-budget cost — all are **levers the Strategy Researcher proposes against** (R5 §2.3), gated by the backtester. v1 ships the defaults above; the loop refines them on evidence, never the engine itself at runtime.
