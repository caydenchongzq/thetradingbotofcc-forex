# 04 — Journal & State (the live↔improvement contract)

> The durable record of everything the live loop does, and the **only** channel between the deterministic live box and the AI improvement loop. Build this **first** (milestone A0): every other component reads or writes it, so its schema is frozen early and versioned. It serves two masters — make every live decision **auditable**, and give the agents **clean, structured, machine-readable** inputs (R5 §4).
>
> Format split (R5 §4): **append-only JSONL** is the crash-safe write path; **SQLite** is the indexed live-state/query store; **Parquet** snapshots are the agents' columnar analytics surface. JSONL for the contract, SQLite for live state, Parquet for analysis.

---

## 1. Responsibilities

**Owns:** the per-trade record, the rejected-signal record, the health/heartbeat record, and the day-state row; the write path (JSONL append → SQLite upsert → periodic Parquet snapshot); schema versioning and migration; and backups (on-box + off-box, R7). It is the system of record the backtester (05) treats as ground truth for live-vs-backtest attribution.

**Does NOT own:** any trading or sizing logic; it only records what the other components decide and read back state on restart.

**Key invariant:** **every** record carries `config_version` and `schema_version`, so a trade is always attributable to the exact strategy params that produced it and the exact record format it was written in. This is what makes live-vs-backtest comparison honest (R5 §4).

---

## 2. Storage layout

```
state/
  journal/
    2026-06-02.jsonl          ← append-only, one record per line, per trading day (write path)
    ...
  live.sqlite                 ← indexed mirror: trades, rejects, health, day_state, intents, config
  parquet/
    trades/                   ← periodic columnar snapshots for analytics (partitioned by month)
    rejects/
  config/                     ← versioned strategy config (see 06/08); may be a git repo
  context_bias.json           ← the R8 seam cache (default normal)
  backups/                    ← timestamped sqlite + jsonl copies (on-box); mirrored off-box
```

**Write path (crash-safe ordering):** append the JSONL line and `fsync` → then upsert into SQLite. If the process dies between the two, the JSONL line is the source of truth and SQLite is rebuilt from JSONL on startup (idempotent replay keyed by record id). JSONL is never rewritten, only appended — so a corrupt tail is recoverable by truncating the last partial line.

---

## 3. Record schemas (schema_version 3)

All records share an envelope:

```json
{ "record_type": "trade|reject|health|day_state|intent",
  "record_id": "<type>-<instrument>-<utc-iso>-<seq>",
  "schema_version": 3,
  "config_version": 47,
  "ts_utc": "2026-06-02T14:03:17Z" }
```

### 3.1 Trade record (the core — R5 §4)
Minimum fields (extends the envelope):

```json
{
  "record_type": "trade",
  "trade_id": "EURUSD-2026-06-02-0317",
  "config_version": 47,
  "schema_version": 3,
  "signal":   { "session": "london_ny_overlap", "breakout_level": 1.08742,
                "direction": "long", "er": 0.41, "atr_pips": 9.3,
                "regime_gate_passed": true, "entry_reason": "range_high_break + ER>=thr + ATR in band" },
  "regime":   { "er": 0.41, "atr_pips": 9.3, "atr_percentile": 0.62, "vol_state": "normal" },
  "sizing":   { "risk_fraction": 0.0035, "equity_at_entry": 101230.50, "risk_usd": 354.31,
                "sl_distance_pips": 11.0, "lots": 0.32,
                "slippage_spread_buffer": 0.20, "killswitch_state": "armed_60pct" },
  "fills":    { "entry_req_price": 1.08742, "entry_fill_price": 1.08745, "entry_slippage_pips": 0.3,
                "spread_at_entry_pips": 0.4, "commission_usd": 4.48,
                "exit_fill_price": 1.08901, "exit_slippage_pips": 0.2, "exit_reason": "trail_step" },
  "outcome":  { "r_multiple": 1.42, "pnl_usd": 502.10, "gross_pips": 15.9, "net_pips": 15.0,
                "mae_pips": 4.1, "mfe_pips": 18.3, "duration_min": 73, "partial_tp_hit": true },
  "rule_budget": { "daily_loss_used_usd": 612.40, "daily_budget_usd": 5000.0, "daily_pct_used": 0.122,
                   "overall_dd_usd": 1870.0, "killswitch_tripped": false, "requests_used_today": 184 },
  "model_vs_real": { "modeled_slippage_pips": 0.25, "realized_slippage_pips": 0.30,
                     "modeled_spread_pips": 0.40, "realized_spread_pips": 0.40 },
  "timestamps": { "signal_utc": "...", "entry_utc": "...", "exit_utc": "..." }
}
```

Why each block matters (R5 §4): **signal+regime** let the Researcher segment performance by regime; **sizing** lets it verify R4 without re-running it; **fills + model_vs_real** are the make-or-break columns that expose cost/slippage drift (the silent killer of an intraday breakout edge); **outcome incl. MAE/MFE** drives expectancy and stop/target tuning; **rule_budget** lets the Reviewer catch creeping rule pressure *before* a breach. A trade is written in stages (entry → managed updates → exit), each appended; the SQLite row is the merged latest state keyed by `trade_id`.

### 3.2 Rejected-signal record
A signal fired but a gate/risk/news-blackout/kill-switch blocked it. Lets the AI learn from trades **not** taken (R5 §4).

```json
{ "record_type": "reject", "config_version": 47, "schema_version": 3,
  "ts_utc": "...", "instrument": "EURUSD",
  "stage": "engine|risk",
  "reason": "regime_gate_failed",
  "context": { "er": 0.22, "er_threshold": 0.30, "atr_pips": 3.1, "vol_state": "low",
               "would_be_direction": "long", "would_be_sl_pips": 10.5 },
  "risk_checks": null }
```
For `stage="risk"`, `risk_checks` carries the Governor's full `checks` dict + the veto `reason`.

### 3.3 Health / heartbeat record
Distinguishes "no edge today" from "engine was down" (R5 §4) and feeds the R7 dead-man's-switch.

```json
{ "record_type": "health", "schema_version": 3, "ts_utc": "...",
  "engine_up": true, "mt5_connected": true, "data_fresh": true,
  "last_tick_utc": "...", "requests_used_today": 184, "killswitch_state": "armed",
  "open_positions": 1, "note": "" }
```

### 3.4 Day-state row (SQLite, R4 reset)
`balance_0000`, `initial`, `requests_used_today`, `killswitch` state, `open_risk_usd`, `trades_opened_today`, `reset_ts_utc`. One row per FTMO day; rewritten at the 00:00 CE(S)T reset. This is the `DayState` the Risk Governor reads (spec 02 §3).

### 3.5 Intent row (SQLite, R3 idempotency)
The persist-before-act record from execution (spec 03 §4): `client_id`, `magic`, `status`, broker ids, timestamps. Drives startup reconciliation.

---

## 4. Read/write API

```python
# src/journal/journal.py
class Journal:
    def append(self, record: dict) -> str: ...          # validates schema, fsyncs JSONL, upserts SQLite; returns record_id
    def update_trade(self, trade_id: str, patch: dict) -> None: ...  # stage update (manage/exit)
    def get_day_state(self) -> "DayState": ...
    def put_day_state(self, day: "DayState") -> None: ...
    def open_intents(self) -> list[dict]: ...           # non-terminal intents for reconciliation
    def rebuild_sqlite_from_jsonl(self) -> None: ...     # idempotent replay (crash recovery)
    def snapshot_parquet(self) -> None: ...              # periodic columnar export for the agents

# Read-only analytics surface used by the improvement loop (06):
class JournalReader:                                     # READ-ONLY — improvement loop never writes here
    def trades(self, since=None, regime=None, config_version=None) -> "DataFrame": ...
    def rejects(self, since=None) -> "DataFrame": ...
    def expectancy(self, window) -> dict: ...            # avg R, win rate, PF, MAE/MFE distributions
    def rule_budget_pressure(self, window) -> dict: ...
```

The improvement loop gets **only** `JournalReader` (read-only) plus the versioned config store — enforcing the R5 boundary that the LLM can read but never write live state.

---

## 5. Schema versioning & migration

- `schema_version` on every record; a `migrations/` set of pure functions `vN→vN+1` applied on read so old JSONL/Parquet stays loadable forever.
- Bump only on additive/structural change; **never silently repurpose a field** (that would corrupt live-vs-backtest attribution).
- Parquet snapshots store their `schema_version`; the reader normalizes to the latest in memory.
- The backtester (05) reads the **same** schema, so a backtest tape and a live tape are directly comparable.

---

## 6. Backups (R7)

- **On-box:** timestamped SQLite + the day's JSONL copied to a second path on a schedule (e.g. hourly + at the 00:00 reset).
- **Off-box:** mirror to object storage or the AI box so a whole-host loss isn't terminal (R7). In Phase A "off-box" = another disk/cloud from the local PC; in Phase B = off the VPS.
- **Restore test** is part of the B→C readiness gate: prove a backup restores into a runnable state.

---

## 7. Error handling & fail-safe

| Condition | Behaviour |
|---|---|
| JSONL write/fsync fails | Treat as a critical fault — the engine must not place trades it cannot record. Alert; fail-safe hold. |
| SQLite corrupt / out of sync with JSONL | Rebuild SQLite from JSONL on startup (JSONL is truth); if JSONL also damaged, restore from latest backup, alert. |
| Partial last JSONL line (crash mid-append) | Truncate the partial line on startup; the intent/reconciliation layer (03) resolves any in-flight order. |
| Disk full | Alert early (R7 monitors); engine fail-safe holds rather than trading un-journaled. |
| Schema validation failure on append | Reject the record, raise — a malformed record is a code bug, not something to silently drop. |

Principle: **no un-journaled trades.** If we cannot durably record what we're about to do, we don't do it.

---

## 8. Test plan

**Unit:**
- Round-trip every record type: append → read back from JSONL and from SQLite, byte-stable for the JSONL line.
- `rebuild_sqlite_from_jsonl` is idempotent and reproduces identical SQLite state from the JSONL log.
- Partial-line truncation recovery on a deliberately corrupted tail.
- Schema migration `v2→v3` on a fixture old record loads correctly.
- Staged trade write (entry → manage → exit) merges to the correct final SQLite row.
- `JournalReader` is genuinely read-only (no write methods; attempts raise).

**Property-based:**
- For any sequence of appends + a crash at a random byte offset, startup recovery yields a consistent state with no duplicated or lost *committed* records.

**Integration:**
- The Risk Governor and Execution adapter write/read day-state and intents through this layer across a kill-and-restart (shared with A2).
- Parquet snapshot of a day's trades loads in the improvement-loop reader and reproduces the SQLite expectancy numbers.
