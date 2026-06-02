# 03 — Execution / MT5 Adapter (R3)

> Translates a **risk-approved** order into MT5 operations and confirms fills — the only component that talks to the broker. Wraps the `MetaTrader5` Python package (Windows-only, IPC to an always-on terminal). It never decides *whether* to trade (01) or *how big* (02); it executes approved intent, idempotently and reconcilably, and never double-trades across a restart.
>
> Source: R3 (GO on MT5+Python; Windows-only; terminal must stay open; watchdog needed) and R7 (magic number, reconcile-on-restart, MT5 as source of truth, persist intent before acting).

---

## 1. Responsibilities

**Owns:** the MT5 IPC lifecycle (`initialize`/`login`/`shutdown`, health, re-init with backoff); placing/modifying/closing orders with SL/TP; tagging every order with the bot's **magic number** and a unique client id; the **idempotent intent log** (persist-before-act); **startup reconciliation** against MT5 as source of truth; debiting every broker call through the Risk Governor's request counter; and surfacing fills/retcodes back to the journal.

**Does NOT own:** signal/sizing/veto logic, the strategy's management *rules* (it applies the `ManageAction` the strategy emits, once the Governor approves it), or alerting/supervision (07 owns the watchdog process; this adapter exposes the health primitives it calls).

---

## 2. The MT5 reality this adapter is built around (R3/R7)

- `MetaTrader5` is **Windows-only** and is an **IPC client to a GUI terminal** that must stay logged in and running. The adapter assumes a live terminal and treats a dead/None `terminal_info()` as a recoverable fault, not a crash.
- Calls can time out / disconnect; the adapter must **re-`initialize()`/`login()`** with exponential backoff and resume.
- Every order op counts against FTMO's **2,000 server requests/day** → the adapter debits the Governor's counter and refuses ops the Governor won't fund.
- FTMO applies an intentional execution delay (~up to 200 ms); we are intraday, so this is irrelevant to correctness — but it means fills can differ from request price → always read back the **actual** fill.

---

## 3. Interfaces

```python
# src/execution/types.py
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

class IntentStatus(str, Enum):
    INTENDED = "intended"      # written BEFORE the broker call
    SENT     = "sent"          # order_send returned, awaiting confirm
    FILLED   = "filled"        # confirmed position/deal exists
    REJECTED = "rejected"      # retcode != DONE
    CANCELLED = "cancelled"    # pending expired/cancelled
    UNKNOWN  = "unknown"       # crash between INTENDED and confirm → reconcile decides

@dataclass(frozen=True)
class OrderIntent:
    client_id: str             # unique, deterministic (uuid persisted before send) — idempotency key
    magic: int                 # the bot's magic number; identifies OUR positions
    instrument: str
    side: str                  # buy/sell
    order_kind: str            # market | stop | limit
    volume_lots: float
    price: float | None        # for stop/limit
    sl_price: float
    tp_prices: tuple[float, ...]
    expire_utc: datetime | None
    comment: str               # carries client_id for cross-identification in the terminal

@dataclass(frozen=True)
class ExecResult:
    client_id: str
    status: IntentStatus
    retcode: int | None
    broker_order_id: int | None
    broker_position_id: int | None
    fill_price: float | None
    fill_volume: float | None
    slippage_pips: float | None
    spread_at_send_pips: float | None
    commission_usd: float | None
    ts_utc: datetime
    error: str | None
```

```python
# src/execution/adapter.py
class MT5Execution:
    def connect(self) -> None: ...                 # initialize + login; raises on unrecoverable
    def health(self) -> "Health": ...              # terminal_info/account_info + data freshness
    def reconcile_on_startup(self) -> "ReconcileReport": ...   # §5 — MUST run before any new order

    def place(self, intent: OrderIntent) -> ExecResult: ...    # persist-before-act, idempotent
    def modify_sl_tp(self, position_id: int, sl: float, tp: tuple[float,...]) -> ExecResult: ...
    def partial_close(self, position_id: int, fraction: float) -> ExecResult: ...
    def close(self, position_id: int) -> ExecResult: ...
    def cancel(self, broker_order_id: int) -> ExecResult: ...

    def open_positions(self) -> list["PositionView"]: ...      # filtered by OUR magic
    def pending_orders(self) -> list["PendingView"]: ...       # filtered by OUR magic
```

**Contract:** `place()` is only ever called with an intent the **Risk Governor approved** (`Decision.APPROVE`/`APPROVE_DOWNSIZED`) and after the Governor has **funded the request** (decremented the counter). The adapter re-asserts the magic and client id but does not re-run risk logic.

---

## 4. Idempotent place (persist-before-act)

The double-trade hazard is a crash *between* deciding to send and confirming the send. The pattern (R7):

```
1. Generate client_id (uuid) for the intent; compute comment carrying it.
2. WRITE intent to the journal/state DB with status=INTENDED  ← durable, BEFORE any broker call.
3. order_send(...).  → on return, status=SENT, record retcode + broker ids.
4. Confirm: poll positions/deals for our magic + client_id/comment.
     - position/deal exists  → status=FILLED, read actual fill_price/volume/commission/slippage.
     - retcode != DONE        → status=REJECTED, record error; do NOT retry blindly.
5. Debit the request counter for the call(s) actually made.
```

On a crash after step 2 but before confirm, startup reconciliation (§5) resolves the dangling `INTENDED`/`SENT`/`UNKNOWN` record by comparing against MT5 — **never** by re-sending blind.

`client_id` is the idempotency key: a retry path checks "does a position/deal with this client_id already exist?" before any new send, so the same intent can never open two positions.

---

## 5. Startup reconciliation (MT5 = source of truth)

Run **before** the engine is allowed to place any new order, on every cold boot / restart / deploy (R7 makes deploys go through this same path):

```
1. connect(): initialize + login to the FTMO server; verify account id + server.
2. Pull live open positions + pending orders, FILTER to our magic number.
3. Pull recent deals/history for our magic over a lookback window.
4. For each persisted intent not in a terminal state (INTENDED/SENT/UNKNOWN):
     - matching live position OR deal exists  → mark FILLED (do NOT resend).
     - no position AND no matching recent deal → the order never landed → mark per fail-safe
       (CANCELLED if it was a pending that expired; else hold and alert).
5. For each live position with our magic that has NO persisted intent (e.g. journal loss):
     - adopt it into state (reconstruct a record), alert — never orphan a real position.
6. Recompute the Risk Governor's open_risk_usd from the reconciled live positions.
7. On ANY unresolved ambiguity → HOLD/FLATTEN per the fail-safe, alert, do not start trading.
```

`ReconcileReport` records every classification for the journal and the daily ops check (R7 runbook).

---

## 6. Retcode & error handling

| Situation | Adapter behaviour |
|---|---|
| `initialize`/`login` fails | Retry with exponential backoff (cap); after N failures, signal the watchdog/fail-safe; never trade without a confirmed connection. |
| `order_send` retcode != `TRADE_RETCODE_DONE` | Mark REJECTED, record retcode + message; classify retryable (e.g. requote/price-off) vs terminal (e.g. invalid stops, no money). Retryable: bounded retries with a fresh quote; terminal: stop, alert. |
| Requote / price moved (stop-entry) | Bounded re-quote attempts within a price tolerance; beyond tolerance, abandon the entry (the breakout edge is gone), log, do not chase. |
| Partial fill | Record actual `fill_volume`; reconcile open_risk to the real size; treat remainder per config (cancel remainder by default). |
| IPC timeout mid-op with unknown result | Mark UNKNOWN; do **not** resend; let reconciliation resolve against MT5. |
| Stale data / dead terminal detected by `health()` | Hand to fail-safe: hold/flatten, never a new trade (R3). |
| Stops too close (`stops_level`) | Should have been vetoed by 02 #11; if broker still rejects, mark REJECTED, alert (indicates a symbol_meta drift). |

`health()` returns terminal liveness, account reachability, and **data freshness** (latest EURUSD tick/bar within tolerance for the active session) — the watchdog (07) polls this; a stale/false health is the trigger for the R3 fail-safe.

---

## 7. Request-budget integration

Every method that issues a broker op calls `governor.fund_request(n)` first; if unfunded (hard cap reached), the op is refused — **except** risk-reducing closes, which are always permitted to fund (you must always be able to flatten). The actual count of server requests per logical op (an entry with SL+TP may be 1–3 requests depending on order type) is measured and debited honestly, not estimated.

---

## 8. Configuration schema

```yaml
execution:
  magic_number: 870201               # unique to this bot/account; immutable per account
  symbol: EURUSD
  deviation_points: 10               # max slippage tolerance on market orders
  requote_max_retries: 2
  requote_price_tolerance_pips: 1.0
  partial_remainder: cancel          # cancel | keep
  reconcile_lookback_hours: 72
  ipc:
    connect_max_retries: 8
    backoff_base_seconds: 2
    backoff_max_seconds: 60
  health:
    tick_freshness_seconds: 90       # during active session; staler ⇒ fail-safe
mt5:
  terminal_path: ${MT5_TERMINAL_PATH}   # env; pinned build (07 parity)
  login: ${MT5_LOGIN}
  password: ${MT5_PASSWORD}             # secret; never committed (07)
  server: ${MT5_SERVER}                 # FTMO London server name
```

---

## 9. Test plan

**Unit (with a mocked `MetaTrader5`):**
- `place()` writes INTENDED **before** calling `order_send` (assert ordering via the mock's call log).
- Idempotency: calling `place()` twice with the same `client_id` ⇒ at most one position; second call detects the existing one.
- Retcode mapping: DONE→FILLED, each rejection code→REJECTED with retryable/terminal classification; requote retry path respects tolerance and max retries.
- Partial fill recomputes open_risk to actual volume.
- `health()` flags stale ticks past `tick_freshness_seconds`.
- Request funding: ops refused when unfunded; closes always funded.

**Reconciliation (the correctness crown jewel):**
- Crash-after-INTENDED-before-send fixture → reconciliation marks CANCELLED/holds, never resends.
- Crash-after-send-before-confirm with a real position → reconciliation marks FILLED, no duplicate.
- Live position with our magic but no journal record → adopted + alerted.
- Live position with a *foreign* magic → ignored (not ours).
- Kill-and-restart integration on a **demo** account (milestone A2): zero duplicate positions across 50 randomized restart points.

**Integration (demo account):**
- Full place→fill→manage→close cycle with SL/TP by magic; actual fill/slippage/commission read back and journaled (feeds 04's `fills`/`model_vs_real`).
- Deploy mid-position → reconcile-on-startup leaves the position intact and correctly accounted.
