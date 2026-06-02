"""MT5 execution adapter (spec 03).

The only component that talks to the broker, through the ``Broker`` seam (``broker.py``)
and the pure logic in ``logic.py`` — so idempotent place, startup reconciliation and
retcode handling are unit-tested with a FakeBroker and validated on the demo (A2).

It never decides whether to trade (01) or how big (02). Fill confirmation and
reconciliation key off broker TICKETS (returned by order_send), not the order comment,
because FTMO does not reliably preserve comments.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Callable

from src.common.config import ExecutionConfig, MT5Config
from src.risk.types import SymbolMeta

from .broker import Broker, BrokerOrder, SymbolView
from .logic import (
    classify_reconciliation,
    classify_retcode,
    find_existing_for_client,
    slippage_pips,
)
from .types import ExecResult, Health, IntentStatus, OrderIntent, ReconcileReport

FundRequest = Callable[[int, bool], bool]


class ConnectionError_(RuntimeError):
    pass


class AccountMismatch(RuntimeError):
    """Refuse to trade if the connected account/server isn't the configured one."""


def _now_iso(epoch: float | None = None) -> str:
    dt = datetime.fromtimestamp(epoch, tz=timezone.utc) if epoch else datetime.now(tz=timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")


class MT5Execution:
    def __init__(
        self,
        broker: Broker,
        journal,
        mt5_cfg: MT5Config,
        exec_cfg: ExecutionConfig,
        fund_request: FundRequest,
        *,
        connect_max_retries: int = 8,
        backoff_base_s: float = 2.0,
        backoff_max_s: float = 60.0,
        tick_freshness_s: float = 90.0,
        requote_max_retries: int = 2,
    ):
        self.broker = broker
        self.journal = journal
        self.mt5 = mt5_cfg
        self.cfg = exec_cfg
        self.fund_request = fund_request
        self.connect_max_retries = connect_max_retries
        self.backoff_base_s = backoff_base_s
        self.backoff_max_s = backoff_max_s
        self.tick_freshness_s = tick_freshness_s
        self.requote_max_retries = requote_max_retries
        # Advance-based freshness state (robust to broker server-tz offset).
        self._last_tick_epoch: int | None = None
        self._last_advance_wall: float | None = None

    # ------------------------------------------------------------ connection
    def connect(self, *, sleep: Callable[[float], None] = time.sleep) -> None:
        last = None
        for attempt in range(self.connect_max_retries):
            if self.broker.initialize(self.mt5.terminal_path) and self.broker.login(
                self.mt5.login, self.mt5.password, self.mt5.server
            ):
                self._verify_account()
                return
            last = self.broker.last_error()
            sleep(min(self.backoff_base_s * (2 ** attempt), self.backoff_max_s))
        raise ConnectionError_(f"MT5 connect failed after {self.connect_max_retries} tries: {last}")

    def _verify_account(self) -> None:
        acct = self.broker.account_info()
        if acct is None:
            raise ConnectionError_("account_info() returned None after login")
        if self.mt5.login and acct.login != self.mt5.login:
            raise AccountMismatch(f"connected login {acct.login} != configured {self.mt5.login}")
        if self.mt5.server and acct.server != self.mt5.server:
            raise AccountMismatch(f"connected server {acct.server!r} != configured {self.mt5.server!r}")

    # ---------------------------------------------------------------- health
    def health(self, now_epoch: float | None = None) -> Health:
        now = now_epoch if now_epoch is not None else time.time()
        term = self.broker.terminal_info()
        acct = self.broker.account_info()
        sym = self.broker.symbol_info(self.cfg.symbol)

        # Freshness = ticks ADVANCING, not wall-clock delta (FTMO ticks are server-tz).
        data_fresh = False
        age_since_advance: float | None = None
        if sym is not None and sym.tick_time_epoch:
            te = sym.tick_time_epoch
            if self._last_tick_epoch is None or te > self._last_tick_epoch:
                self._last_tick_epoch = te
                self._last_advance_wall = now
                data_fresh = True
                age_since_advance = 0.0
            else:
                age_since_advance = now - (self._last_advance_wall or now)
                data_fresh = age_since_advance <= self.tick_freshness_s
        return Health(
            terminal_connected=bool(term and term.connected),
            trade_allowed=bool(term and term.trade_allowed),
            account_reachable=acct is not None,
            data_fresh=data_fresh,
            last_tick_age_s=age_since_advance,
            note="" if (term and term.trade_allowed) else "algo_trading_disabled",
        )

    # ------------------------------------------------------------ symbol meta
    def symbol_meta(self) -> SymbolMeta:
        sv = self.broker.symbol_info(self.cfg.symbol)
        if sv is None:
            raise ConnectionError_(f"symbol_info({self.cfg.symbol!r}) returned None")
        return _symbol_meta_from_view(sv)

    # --------------------------------------------------------- reconciliation
    def reconcile_on_startup(self, lookback_hours: int = 72) -> ReconcileReport:
        positions = self.broker.positions_get()
        pendings = self.broker.orders_get()
        deals = self.broker.history_deals_get(int(time.time()) - lookback_hours * 3600)
        intents = self.journal.open_intents()

        outcome = classify_reconciliation(intents, positions, pendings, deals, self.cfg.magic)
        for res in outcome.resolutions:
            self._persist_intent(res.client_id, res.resolved_status.value, note=res.note,
                                 broker_position_id=res.position_ticket)
        return ReconcileReport(
            matched=outcome.matched, adopted=len(outcome.adopted_positions),
            orphaned_intents=outcome.orphaned_intents,
            flatten_required=outcome.flatten_required,
            detail={
                "resolutions": [
                    {"client_id": r.client_id, "status": r.resolved_status.value,
                     "note": r.note, "needs_attention": r.needs_attention}
                    for r in outcome.resolutions
                ],
                "adopted_tickets": [p.ticket for p in outcome.adopted_positions],
                "live_position_tickets": [p.ticket for p in outcome.live_positions],
            },
        )

    # ----------------------------------------------------------------- place
    def place(self, intent: OrderIntent) -> ExecResult:
        # 1) Persist BEFORE any broker call (persist-before-act, spec 03 §4).
        self._persist_intent(intent.client_id, IntentStatus.INTENDED.value,
                             magic=intent.magic, order_kind=intent.order_kind)

        # 2) Idempotency: never open a second position for the same intent.
        positions = self.broker.positions_get(intent.instrument)
        deals = self.broker.history_deals_get(int(time.time()) - 24 * 3600)
        if find_existing_for_client(intent.client_id, positions, deals):
            self._persist_intent(intent.client_id, IntentStatus.FILLED.value,
                                 note="idempotent_existing")
            return self._result(intent.client_id, IntentStatus.FILLED, None,
                                note="idempotent_existing")

        # 3) Fund the broker request (entries are NOT risk-reducing).
        if not self.fund_request(1, False):
            self._persist_intent(intent.client_id, IntentStatus.REJECTED.value,
                                 note="request_unfunded")
            return self._result(intent.client_id, IntentStatus.REJECTED, None,
                                error="request_budget_unfunded")

        # 4) Send, with a bounded re-quote loop on retryable codes.
        order = self._build_order(intent)
        res = self.broker.order_send(order)
        retries = 0
        while classify_retcode(res.retcode) == "rejected_retryable" \
                and retries < self.requote_max_retries:
            retries += 1
            sv = self.broker.symbol_info(intent.instrument)
            self.fund_request(1, False)
            res = self.broker.order_send(self._build_order(intent, refreshed=sv))

        # Record the broker order ticket NOW (comment-independent idempotency key).
        self._persist_intent(intent.client_id, IntentStatus.SENT.value,
                             retcode=res.retcode, broker_order_id=res.order or None)

        if classify_retcode(res.retcode) == "done":
            return self._confirm(intent, res)
        self._persist_intent(intent.client_id, IntentStatus.REJECTED.value,
                             retcode=res.retcode, note=res.comment)
        return self._result(intent.client_id, IntentStatus.REJECTED, res, error=res.comment)

    def _confirm(self, intent: OrderIntent, res) -> ExecResult:
        # Find the deal/position by the tickets order_send returned (not by comment).
        deal = None
        if res.deal:
            recent = self.broker.history_deals_get(int(time.time()) - 3600)
            deal = next((d for d in recent if d.ticket == res.deal), None)
        positions = self.broker.positions_get(intent.instrument)
        pos = None
        if res.order:
            pos = next((p for p in positions if p.ticket == res.order), None)
        if pos is None and deal is not None:
            pos = next((p for p in positions if p.ticket == deal.position_id), None)
        if pos is None and intent.client_id:  # last resort if broker kept the comment
            pos = next((p for p in positions if intent.client_id in (p.comment or "")), None)

        sv = self.broker.symbol_info(intent.instrument)
        pip = sv.pip_size if sv else 0.0001
        fill_price = (res.price or (deal.price if deal else None)
                      or (pos.price_open if pos else None))
        slip = slippage_pips(intent.price, fill_price, pip, intent.side)
        spread = round((sv.ask - sv.bid) / pip, 2) if (sv and pip) else None
        position_id = (pos.ticket if pos else None) or (deal.position_id if deal else None)

        self._persist_intent(intent.client_id, IntentStatus.FILLED.value,
                             broker_position_id=position_id, retcode=res.retcode)
        return ExecResult(
            client_id=intent.client_id, status=IntentStatus.FILLED, retcode=res.retcode,
            broker_order_id=res.order or None, broker_position_id=position_id,
            fill_price=fill_price, fill_volume=res.volume or (pos.volume if pos else None),
            slippage_pips=slip, spread_at_send_pips=spread,
            commission_usd=deal.commission if deal else None,
            ts_utc=datetime.now(tz=timezone.utc), error=None,
        )

    # ------------------------------------------------- risk-reducing actions
    def close(self, position_id: int, instrument: str | None = None) -> ExecResult:
        self.fund_request(1, True)  # closes are always funded
        sym = instrument or self.cfg.symbol
        pos = next((p for p in self.broker.positions_get(sym) if p.ticket == position_id), None)
        order_type = "sell" if (pos and pos.type == 0) else "buy"
        res = self.broker.order_send(BrokerOrder(
            action="close", symbol=sym, order_type=order_type,
            volume=pos.volume if pos else 0.0, position=position_id,
            deviation=self.cfg.deviation_points, magic=self.cfg.magic,
            comment=f"close-{position_id}"))
        ok = classify_retcode(res.retcode) == "done"
        return self._result(f"close-{position_id}",
                            IntentStatus.FILLED if ok else IntentStatus.REJECTED, res,
                            error=None if ok else res.comment)

    def modify_sl_tp(self, position_id: int, sl: float, tp: tuple[float, ...]) -> ExecResult:
        self.fund_request(1, True)
        res = self.broker.order_send(BrokerOrder(
            action="sltp", symbol=self.cfg.symbol, order_type="buy", position=position_id,
            sl=sl, tp=tp[0] if tp else 0.0, magic=self.cfg.magic, comment=f"sltp-{position_id}"))
        ok = classify_retcode(res.retcode) == "done"
        return self._result(f"sltp-{position_id}",
                            IntentStatus.FILLED if ok else IntentStatus.REJECTED, res,
                            error=None if ok else res.comment)

    def cancel(self, broker_order_id: int) -> ExecResult:
        self.fund_request(1, True)
        res = self.broker.order_send(BrokerOrder(
            action="remove", symbol=self.cfg.symbol, order_type="buy",
            order_ticket=broker_order_id, magic=self.cfg.magic,
            comment=f"cancel-{broker_order_id}"))
        ok = classify_retcode(res.retcode) == "done"
        return self._result(f"cancel-{broker_order_id}",
                            IntentStatus.CANCELLED if ok else IntentStatus.REJECTED, res,
                            error=None if ok else res.comment)

    # -------------------------------------------------------------- queries
    def open_positions(self):
        return [p for p in self.broker.positions_get() if p.magic == self.cfg.magic]

    def pending_orders(self):
        return [o for o in self.broker.orders_get() if o.magic == self.cfg.magic]

    # ----------------------------------------------------------------- util
    def _build_order(self, intent: OrderIntent, refreshed: SymbolView | None = None) -> BrokerOrder:
        action = "pending" if intent.order_kind in ("stop", "limit") else "deal"
        otype = intent.side if intent.order_kind == "market" \
            else f"{intent.side}_{intent.order_kind}"
        price = intent.price
        if refreshed is not None and intent.order_kind == "market":
            price = refreshed.ask if intent.side == "buy" else refreshed.bid
        return BrokerOrder(
            action=action, symbol=intent.instrument, order_type=otype,
            volume=intent.volume_lots, price=price, sl=intent.sl_price,
            tp=intent.tp_prices[0] if intent.tp_prices else 0.0,
            deviation=self.cfg.deviation_points, magic=intent.magic, comment=intent.comment,
            expire_epoch=int(intent.expire_utc.timestamp()) if intent.expire_utc else None)

    def _persist_intent(self, client_id: str, status: str, **extra) -> None:
        rec = {"record_type": "intent", "schema_version": 3, "ts_utc": _now_iso(),
               "client_id": client_id, "status": status,
               "magic": extra.pop("magic", self.cfg.magic)}
        rec.update({k: v for k, v in extra.items() if v is not None})
        self.journal.append(rec)

    @staticmethod
    def _result(client_id, status, res, error=None, note=None) -> ExecResult:
        return ExecResult(
            client_id=client_id, status=status,
            retcode=getattr(res, "retcode", None) if res else None,
            broker_order_id=(getattr(res, "order", None) or None) if res else None,
            broker_position_id=None,
            fill_price=getattr(res, "price", None) if res else None,
            fill_volume=getattr(res, "volume", None) if res else None,
            slippage_pips=None, spread_at_send_pips=None, commission_usd=None,
            ts_utc=datetime.now(tz=timezone.utc), error=error)


def _symbol_meta_from_view(sv: SymbolView) -> SymbolMeta:
    return SymbolMeta(
        symbol=sv.name, pip_value_per_lot_usd=sv.pip_value_per_lot,
        contract_size=sv.trade_contract_size, min_lot=sv.volume_min,
        max_lot=sv.volume_max, lot_step=sv.volume_step,
        stops_level_pips=sv.stops_level_pips, digits=sv.digits, pip_size=sv.pip_size)
