# 02 — Risk Governor (R4)

> The gatekeeper. Every order the strategy proposes passes through here; the Governor **sizes** it from the live FTMO loss budget and **vetoes** anything that could breach a rule. It is pure deterministic Python with veto power the strategy cannot override (README §6). Build and test this **before** Execution — "risk before reward".
>
> Source of truth for the math: R4 findings. Daily floor `= balance_at_0000_CEST − 0.05 × Initial`, breach checked on **equity** (balance + open P/L); max overall loss 10% **static**; size `lots = f·equity / (SL_pips · pip_value · (1+buffer))`, `f ≈ 0.35%`; kill-switch halts new entries at **60% of the daily budget**; ≤ **2,000 server requests/day**; 13-item forbidden-practice checklist.

---

## 1. Responsibilities

**Owns:** the single source of account-state truth for sizing (reads live equity/balance from MT5 before every decision, never assumes); the daily-loss and overall-loss budget math and the 00:00 CE(S)T reset; position sizing from SL distance; the **kill-switch** state machine; the **request-budget** counter; and the **forbidden-practice hard checks**. It returns one of: a sized order, a downsized order, or a veto with a reason.

**Does NOT own:** signal generation (01), order placement (03 — it only *approves*), or any LLM call. The Governor is the last deterministic word before execution and **cannot be argued with by the improvement loop** (R5 boundary table).

**Purity:** all decisions are a pure function of `(proposed_order, account_state, day_state, config, now)`. The only side effects are reading account state (injected) and emitting a decision; counters/state are passed in and returned, never hidden.

---

## 2. The FTMO envelope (exact math)

Let `Initial` = the account's initial balance (e.g. 100_000). Let `balance_0000` = account **balance** captured at the most recent 00:00 **CE(S)T** reset (Prague time, DST-aware). Let `equity` = live balance + open P/L.

```
daily_floor_equity   = balance_0000 - 0.05 * Initial          # 5% daily, equity-checked
overall_floor_equity = Initial      - 0.10 * Initial          # 10% static, absolute
daily_budget_usd     = balance_0000 - daily_floor_equity      # == 0.05 * Initial
daily_loss_used_usd  = max(0, balance_0000 - equity)          # how much of today's budget spent
daily_pct_used       = daily_loss_used_usd / daily_budget_usd
overall_dd_usd       = max(0, Initial - equity)
```

**Breach conditions (must never occur):** `equity <= daily_floor_equity` (daily) or `equity <= overall_floor_equity` (overall). The Governor's entire job is to make sure no order it approves *could* cross either floor if fully stopped out, including spread/slippage buffer.

**Reset semantics:** at 00:00 CE(S)T, re-capture `balance_0000` from the *balance* (not equity), reset `daily_loss_used`, reset the kill-switch's daily latch, and reset the request counter. The reset clock is **Europe/Prague** with DST handled by the tz database — never a fixed +1/+2 offset.

---

## 3. Interfaces

```python
# src/risk/types.py
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

@dataclass(frozen=True)
class AccountState:          # read LIVE from MT5 before every sizing decision (never cached across decisions)
    equity: float
    balance: float
    currency: str            # account currency; pip_value math must respect it
    ts_utc: datetime
    is_fresh: bool           # False if the read is stale/failed → Governor must veto (fail-safe)

@dataclass(frozen=True)
class DayState:              # persisted in the journal/state DB, reset at 00:00 CE(S)T
    balance_0000: float
    initial: float
    requests_used_today: int
    killswitch: "KillSwitchState"
    open_risk_usd: float     # sum of (entry→SL) risk of currently-open governor-owned positions
    trades_opened_today: int

class Decision(str, Enum):
    APPROVE = "approve"
    APPROVE_DOWNSIZED = "approve_downsized"
    VETO = "veto"

@dataclass(frozen=True)
class RiskDecision:
    decision: Decision
    lots: float                      # 0.0 on veto
    risk_usd: float                  # modelled loss if stopped (incl. buffer); 0.0 on veto
    reason: str                      # required; logged verbatim (e.g. "killswitch_armed_60pct")
    daily_pct_used_after: float
    requests_remaining: int
    checks: dict[str, bool]          # every forbidden-practice check + its pass/fail (audit)
```

Single entry point:

```python
# src/risk/governor.py
class RiskGovernor:
    def __init__(self, config: RiskConfig): ...

    def evaluate_entry(
        self,
        signal: "Signal",            # from spec 01 — carries SL distance, direction, context_bias
        account: AccountState,       # LIVE read
        day: DayState,
        now_utc: datetime,
        symbol_meta: "SymbolMeta",   # pip_value, contract size, min/max/step lot, stops level
    ) -> RiskDecision: ...

    def evaluate_manage(
        self,
        action: "ManageAction",      # modify/partial/close proposed by strategy.manage()
        account: AccountState,
        day: DayState,
        now_utc: datetime,
    ) -> RiskDecision:
        """Risk-reducing actions (close/partial/move-SL-toward-BE) are always allowed even when
        the kill-switch is armed; only RISK-INCREASING actions are gated."""
```

---

## 4. Position sizing

```
sl_pips         = signal.exit_plan.initial_sl_pips
pip_value_usd   = symbol_meta.pip_value_per_lot(account.currency)   # for EURUSD on a USD acct ≈ $10/lot/pip
buffer          = config.slippage_spread_buffer            # default 0.20 (20% headroom for spread+slippage)
risk_fraction   = effective_risk_fraction(signal, day)     # base f (0.35%) × context/kill-switch modifiers
risk_usd_target = risk_fraction * account.equity

lots_raw        = risk_usd_target / (sl_pips * pip_value_usd * (1 + buffer))
lots            = clamp_to_broker(lots_raw, symbol_meta)   # round DOWN to lot step, respect min/max
risk_usd        = lots * sl_pips * pip_value_usd * (1 + buffer)   # recomputed on the ACTUAL lot size
```

`effective_risk_fraction`:
- base `config.base_risk_fraction` (0.0035).
- `context_bias == CAUTIOUS` → multiply by `config.cautious_size_mult` (default 0.5). *(This is where size reduction lives — the engine only tags; the Governor decides, per spec 01 §3.6.)*
- kill-switch in a "reduce" sub-state → multiply by `config.reduced_size_mult`.
- Near the overall floor (`overall_dd_usd > config.overall_taper_start`) → linearly taper toward 0 as equity approaches `overall_floor_equity` (R4 "trade smaller as the account nears it").

**The budget veto (the core safety check):** approve only if, after opening this position, a **full stop-out at the buffered SL plus current open risk** still leaves equity strictly above **both** floors **and** within the kill-switch's remaining daily allowance:

```
projected_loss = risk_usd + day.open_risk_usd
ok_daily   = (equity - projected_loss) > daily_floor_equity   # strict
ok_overall = (equity - projected_loss) > overall_floor_equity # strict
ok_budget  = (daily_loss_used_usd + projected_loss) <= killswitch_allowance(day)
```

If `lots` rounds below `symbol_meta.min_lot`, or any `ok_*` is false at min lot → **VETO** (can't size safely). If it fits only at a smaller size than requested → **APPROVE_DOWNSIZED**.

---

## 5. Kill-switch state machine

```
        ┌──────────┐  daily_pct_used >= warn_pct (e.g. 0.40)   ┌──────────┐
        │  ARMED   │ ─────────────────────────────────────────►│  REDUCE  │
        │ (normal) │                                            │ (size×m) │
        └──────────┘ ◄─── 00:00 CE(S)T reset ──────────────────└──────────┘
              │  daily_pct_used >= halt_pct (0.60)                   │
              ▼                                                      │ daily_pct_used >= halt_pct
        ┌────────────────────────────────────────────────────────────────┐
        │  HALTED — NO NEW ENTRIES for the rest of the FTMO day.            │
        │  Risk-reducing manage actions still allowed. Latched until reset. │
        └────────────────────────────────────────────────────────────────┘
              │ hard danger (daily_pct_used >= flatten_pct, e.g. 0.85,
              ▼  OR stale data OR overall taper critical)
        ┌────────────────────────────────────────────────────────────────┐
        │  FLATTEN — instruct execution to close all governor-owned         │
        │  positions, cancel pendings; engine halted until a HUMAN clears.  │
        │  Never auto-resumes after a risk-driven flatten (R7 kill-switch). │
        └────────────────────────────────────────────────────────────────┘
```

- `halt_pct = 0.60` is the headline R4 number: stop **opening** trades at 60% of the daily budget, leaving 40% as a buffer against slippage/gaps on positions still open.
- HALT and FLATTEN are **latched** for the day; only the 00:00 reset (HALT) or an explicit human clear (FLATTEN) leaves the state.
- The kill-switch is checked on **every** `evaluate_entry`; risk-reducing `evaluate_manage` actions bypass it.

---

## 6. Request-budget governor (≤ 2,000/day)

The Governor maintains `requests_used_today` and **every** order open/modify/close must be debited through it. Discipline:
- A configurable **soft cap** (`config.request_soft_cap`, e.g. 1,600) past which new *entries* are vetoed (`reason="request_budget_low"`) while still allowing risk-reducing closes.
- A **hard cap** (`config.request_hard_cap`, e.g. 1,900, below FTMO's 2,000) past which only closes are permitted.
- Trade-management modifies are the main consumer → the strategy's `TrailRule.min_seconds_between_modifies` (spec 01) plus this counter together keep us clear. Alert (R7) when crossing the soft cap.
- The counter resets at 00:00 CE(S)T with the rest of day-state.

---

## 7. Forbidden-practice hard checks (the 13-item checklist)

Encoded as deterministic predicates, all evaluated on `evaluate_entry` and recorded in `RiskDecision.checks`. Any failure ⇒ VETO with the corresponding reason. Derived from R4:

1. **No feed-error / latency-arbitrage** — reject entries whose justification is a stale/aberrant tick (cross-check signal price vs latest quote within tolerance).
2. **Request budget ≤ 2,000/day** — §6.
3. **News blackout** — re-check the economic calendar window (defence-in-depth over spec 01 §3.4); veto inside the window.
4. **Gap rule** — no new entry ≤ 2h before a scheduled 2h+ close/weekend.
5. **Consistent position sizing** — reject an order whose `risk_usd` deviates beyond `config.size_consistency_band` from the trailing median (no wildly larger/smaller trades that look like all-or-nothing gambling to FTMO).
6. **No hedging / opposing correlated positions** to game the Best-Day rule — veto an entry that opens an opposing position on the same or a correlated instrument already held.
7. **No martingale / averaging into losers** — veto an entry that adds to an existing losing position in the same direction.
8. **No grid** — veto stacking of multiple pending entries at laddered levels beyond `config.max_concurrent_pendings`.
9. **Max concurrent open risk** — `day.open_risk_usd + risk_usd <= config.max_concurrent_risk_usd`.
10. **Max trades/day** — `day.trades_opened_today < config.max_trades_per_day`.
11. **Min-stop / stops-level compliance** — SL respects the broker's `symbol_meta.stops_level`; veto orders with an SL too close to be legal.
12. **No trading on a stale/forced account state** — `account.is_fresh` must be True; else VETO (fail-safe).
13. **Daily/overall floor protection** — the §4 budget veto; the non-negotiable backstop.

The list is config-extensible; new FTMO terms become new predicates without touching sizing.

---

## 8. Error handling & fail-safe

| Condition | Governor behaviour |
|---|---|
| `account.is_fresh == False` (stale/failed equity read) | **VETO** every entry; permit only closes. Never size off a guessed equity. |
| `symbol_meta` missing pip_value / lot step | VETO (`reason="symbol_meta_unavailable"`). |
| `balance_0000` not yet captured (cold boot before first reset) | Capture from current balance on first run; log it; size conservatively until a real reset occurs. |
| Clock/timezone uncertainty around 00:00 CE(S)T | Treat the reset boundary with a small guard window; if uncertain whether reset happened, use the **more conservative** (lower) `balance_0000`. |
| Computed `lots` is NaN/inf | VETO. |
| Open-risk accounting disagrees with MT5 positions on reconcile | Trust MT5 (source of truth, R7), recompute `open_risk_usd`, log discrepancy, and if it can't be reconciled, FLATTEN-or-hold. |

Every fail-safe path resolves to **fewer/zero new trades and the option to reduce risk**, never to a larger or unguarded position.

---

## 9. Configuration schema

```yaml
risk:
  base_risk_fraction: 0.0035          # f ≈ 0.35% of equity per trade
  slippage_spread_buffer: 0.20        # 20% headroom in the SL→loss model
  cautious_size_mult: 0.5             # applied when context_bias == cautious
  reduced_size_mult: 0.5              # applied in kill-switch REDUCE state
  killswitch:
    warn_pct: 0.40                    # → REDUCE
    halt_pct: 0.60                    # → HALTED (no new entries)  [R4 headline]
    flatten_pct: 0.85                 # → FLATTEN (close all, human clear)
  overall_taper_start: 0.06           # begin tapering size when overall_dd >= 6% of Initial
  max_concurrent_risk_usd_pct: 0.010  # ≤ 1.0% of Initial open at once (sum of per-trade risk)
  max_trades_per_day: 6
  max_concurrent_pendings: 2
  size_consistency_band: 0.50         # ±50% of trailing median risk_usd
  request_soft_cap: 1600
  request_hard_cap: 1900              # < FTMO 2000
```

---

## 10. Test plan

**Unit (exhaustive — this is the safety-critical component):**
- Sizing arithmetic for EURUSD on USD/EUR/other base currencies; lot rounds **down** to step; min/max clamps.
- Budget veto: equity exactly at floor (strict `>` boundary), one tick above, one below; with and without existing open risk.
- Kill-switch transitions at `warn/halt/flatten` exact percentages (boundary-inclusive), latch behaviour, and **reset** clears HALT but **not** FLATTEN.
- Context-bias and overall-taper size multipliers; taper → 0 as equity → overall floor.
- Each of the 13 forbidden-practice predicates: a passing case and a vetoing case, with the correct `reason` and `checks` entry.
- Request-budget soft/hard caps; closes always allowed.
- 00:00 CE(S)T reset across the **DST change** in Europe/Prague (explicit fixture dates).
- `is_fresh == False` ⇒ veto-all-entries, allow-closes.

**Property-based (the load-bearing guarantees):**
- **No approved order can breach a floor.** For randomized `(equity, sl_pips, open_risk, buffer)` within ranges, assert: if `decision != VETO`, then `equity − (risk_usd + open_risk) > both floors`. This is the single most important test in the codebase.
- Sizing is monotonic: larger SL distance ⇒ ≤ lots; higher equity ⇒ ≥ risk_usd (until caps).
- Risk-reducing manage actions are **never** vetoed by the kill-switch.

**Integration:**
- Drive against the backtest harness (05) with the FTMO simulator: across full history the Governor produces **zero** simulated breaches on the chosen strategy (this is also an R6 gate).
- Demo-account loop (A2): the Governor's `open_risk_usd` and request counter stay reconciled with MT5 across a kill-and-restart.
