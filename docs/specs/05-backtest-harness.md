# 05 — Backtest Harness (R6)

> The arbiter. No strategy or proposed config change reaches live without clearing this — and **the backtester, not any LLM, decides whether a change is good** (R5 boundary). Two engines: a **custom event-driven loop** (the system of record, drives the *real* `Strategy` interface and the *real* Risk Governor) and **vectorbt** for fast parameter sweeps. Data: **Dukascopy tick (bid/ask)** for development, the **MT5 feed** for final validation (R6).
>
> The non-negotiable gate: **zero simulated FTMO breaches** across history and Monte-Carlo reshuffles. Anti-overfitting: walk-forward + **deflated Sharpe** under the true trial count.

---

## 1. Responsibilities

**Owns:** replaying historical data through the **exact same** `Strategy` (01) and `RiskGovernor` (02) code that trades live; modelling spread/commission/slippage realistically; simulating the FTMO rule envelope (daily/overall floor, request budget, news/gap blackout) bar-by-bar; computing the acceptance metrics and gates; walk-forward and deflated-Sharpe machinery; and emitting a structured **backtest report** the improvement loop consumes.

**Does NOT own:** generating hypotheses (06's Strategy Researcher) or promoting configs (06/08). It answers one question per run: *does this strategy+config pass every gate on out-of-sample data?* — yes/no, with evidence.

**Critical design rule:** the event-driven loop instantiates the **production** `Strategy.evaluate/manage` and `RiskGovernor.evaluate_*` — not a reimplementation. A backtest that passes is therefore a statement about the code that will actually trade. The vectorbt path is a *fast pre-filter* for sweeps; anything it surfaces is re-confirmed on the event-driven loop before any gate verdict.

---

## 2. Two engines, one source of truth

| Engine | Role | Drives real code? | Speed |
|---|---|---|---|
| **Event-driven loop** | System of record; final verdict | **Yes** — real Strategy + Risk Governor + a simulated Execution | ~1 instrument-year/seconds–minutes |
| **vectorbt** | Parameter sweeps / coarse search | No (vectorized re-expression of the entry/exit rules) | Thousands of combos fast |

Workflow: sweep with vectorbt to find promising regions → **re-run every candidate on the event-driven loop** → only event-driven results feed the gates. This keeps speed where it helps (search) and fidelity where it matters (the verdict).

---

## 3. Data pipeline (R6)

```
Dukascopy tick (bid/ask)  ──► clean/validate ──► resample to 15m (and 5m/1m for cost studies)
   [development & search]         (gaps, dupes,        ──► store as Parquet, partitioned by month
                                   outliers, DST)
MT5 feed (terminal export) ──────────────────────────► FINAL validation set (broker-realistic)
   [final pre-live check]
```

- **Bid/ask tick** is required because an intraday breakout edge lives or dies on spread + slippage; mid-price bars would flatter the strategy. Spread is modelled from the actual bid/ask, not assumed constant.
- **Cleaning:** drop weekend gaps, dedupe, flag/clip outliers, align to exchange/session calendar, handle DST in the session windows (mirrors spec 01).
- **Final validation on the MT5 feed** catches broker-specific quirks (the same data source that will trade) before any live attempt — R6's last gate before forward-test.
- Data quality is itself tested: a fixture with known gaps/dupes must be cleaned to a known-good series.

---

## 4. Cost & fill model

Applied in the event-driven loop so simulated fills resemble FTMO reality:
- **Spread**: from bid/ask at the decision tick (variable, session-dependent), not a constant.
- **Commission**: per-lot per-side from config (FTMO commission schedule).
- **Slippage**: a model with a configurable distribution (e.g. session-dependent mean + tail), plus a worst-case stress mode for Monte-Carlo. Stop-entry fills modelled at the level ± slippage.
- **Execution delay**: optional small delay (FTMO applies up to ~200 ms) to test sensitivity; intraday on 15m it should be negligible, and the test proves it.
- The model writes the **same `model_vs_real` fields** (spec 04) so live drift can later be compared against the assumptions made here.

---

## 5. FTMO simulation (the hard gate)

The loop tracks, bar by bar, the **same** quantities the live Risk Governor does (it literally calls it):
- equity vs `daily_floor_equity` and `overall_floor_equity`, with the 00:00 CE(S)T reset of `balance_0000`;
- request-budget accumulation vs the 2,000/day cap (counts the order ops the strategy+governor would have issued);
- news/gap blackout windows (same calendar contract as 01/02).

**A simulated run "breaches" if equity ever crosses a floor, the request cap is exceeded, or a forbidden-practice predicate trips.** A strategy/config with **any** simulated breach is **rejected outright** — this gate is binary and no metric, profitability, or LLM advocacy can override it (R5 §5).

---

## 6. Metrics & acceptance gates

Computed on **out-of-sample** segments (walk-forward, §7). A config passes only if **all** hold (R5 §1.2 / R6):

| Gate | Threshold |
|---|---|
| Expectancy (avg R, **net** of costs) | ≥ +0.10 R |
| Profit factor | ≥ 1.3 |
| Sharpe / Sortino | ≥ 1.0 / ≥ 1.5 |
| Sample size | ≥ 200–300 trades |
| Walk-forward | no out-of-sample collapse (OOS expectancy ≥ a floor fraction of in-sample) |
| Parameter stability | neighbours in param space perform similarly (no lone spike) |
| **Deflated Sharpe Ratio** | significant **given the true cumulative trial count** (§8) |
| **FTMO breaches** | **exactly zero** (§5) — hard, binary |

The report also includes max drawdown, MAE/MFE distributions, trade-count, regime-segmented expectancy, and the realized cost assumptions — the inputs the Performance Reviewer/Strategy Researcher reason over.

---

## 7. Walk-forward & out-of-sample lockbox

- **Walk-forward**: roll an in-sample (train/tune) window forward over an out-of-sample (test) window across the history; gates are judged on the **stitched OOS** results, never on in-sample.
- **OOS lockbox**: a held-out final window the **improvement loop's LLM never sees in its context** (R5 §5). A proposal must survive data it could not have been fit to. The harness enforces this by only ever exposing in-sample/development summaries to the agents and reserving the lockbox for the final gate.
- **Monte-Carlo**: reshuffle trade order / bootstrap returns and re-check the FTMO floors under worst-case sequencing — a strategy that only survives the *one* historical ordering is rejected.

---

## 8. Anti-overfitting: the trial ledger ↔ deflated Sharpe link

The danger of an LLM in the loop is infinite hypothesis generation → data snooping (R5 §5). The harness is fed the **true cumulative trial count** for the period from the trial ledger (06/08): the more the Researcher has proposed, the higher the **deflated-Sharpe** significance bar its winners must clear. CSCV → Probability of Backtest Overfitting (PBO) is computed alongside. The trial count is **code-maintained and the LLM cannot reset it** — so "the model tried 40 things this month" automatically tightens the gate. This converts proposal volume directly into statistical conservatism.

---

## 9. Interfaces

```python
# src/backtest/types.py
@dataclass(frozen=True)
class BacktestRequest:
    strategy_name: str
    config_version: int
    config: dict
    data_set: str                  # "dukascopy_dev" | "mt5_final"
    period: tuple[datetime, datetime]
    walk_forward: "WFSpec"
    trial_count: int               # from the trial ledger — drives DSR
    monte_carlo_runs: int

@dataclass(frozen=True)
class BacktestReport:
    request: BacktestRequest
    passed: bool                   # AND of every gate
    gates: dict[str, "GateResult"] # per-gate value + threshold + pass/fail
    metrics: dict                  # expectancy, PF, Sharpe/Sortino, maxDD, trade_count, regime breakdown
    ftmo: dict                     # breaches (must be 0), worst daily/overall excursion, requests/day max
    oos: dict                      # walk-forward OOS stitched results, lockbox result
    overfitting: dict              # DSR, PBO, trial_count used
    artifacts: dict                # paths to equity curve, trade tape, plots
```

```python
# src/backtest/engine.py
class EventDrivenBacktester:
    def run(self, req: BacktestRequest) -> BacktestReport: ...   # drives REAL Strategy + RiskGovernor

class VectorbtSweeper:
    def sweep(self, grid: dict, req: BacktestRequest) -> "SweepResult": ...  # coarse pre-filter only
```

The **Backtest Analyst agent** (06) calls `EventDrivenBacktester.run`, applies the gates verbatim (they're code, not prompt), and a cheap LLM call only *narrates* the report into a promotion proposal — it cannot change a verdict.

---

## 10. Error handling

| Condition | Behaviour |
|---|---|
| Data gap inside the test window | Mark the segment; either skip with disclosure or fail the run — never silently interpolate across a real gap. |
| Strategy raises during replay | Fail the run, surface the bar/context — a strategy that errors in backtest is not promotable. |
| vectorbt and event-driven disagree materially | Trust event-driven (system of record); flag the discrepancy (indicates a vectorized re-expression bug). |
| Trial count unavailable | Refuse to run (can't compute an honest DSR) — the gate integrity depends on it. |

---

## 11. Test plan

**Unit:**
- Cost model: spread from bid/ask, commission, slippage applied with correct sign for long/short; stop-entry fill at level ± slippage.
- FTMO simulator flags a **deliberately breaching** synthetic strategy (steps equity below the daily floor) and passes a safe one.
- Metric math (expectancy, PF, Sharpe/Sortino, maxDD) against hand-computed fixtures.
- DSR/PBO against published worked examples; DSR tightens as trial_count rises (monotonic).
- Walk-forward windowing indices correct; lockbox never appears in the agent-facing summary.

**Golden-tape:**
- The same EURUSD 15m fixture as spec 01 §6 produces an identical trade tape through the event-driven loop (ties strategy purity to backtest fidelity).

**Integration (milestone A3/A4):**
- Reproduce a hand-checked trade tape on a fixture (A3).
- Full EURUSD validation run on Dukascopy tick→15m, then MT5 feed, clearing **all** gates incl. zero breaches before the strategy is allowed live (A4).
- vectorbt sweep → event-driven re-confirmation agreement on a sampled set of param combos.
