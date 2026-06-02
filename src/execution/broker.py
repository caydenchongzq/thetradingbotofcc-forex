"""Broker seam — isolates ALL direct MetaTrader5 calls behind one interface.

The adapter (``adapter.py``) and the order/reconciliation logic (``logic.py``) are
written against the ``Broker`` protocol and neutral plain-data views below, so they can
be unit-tested with a ``FakeBroker`` and never need a live terminal. ``RealMT5Broker``
is the only code that touches the Windows-only ``MetaTrader5`` package; its mapping to
these views is thin and constant.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

# --- MT5 trade retcodes / order-type codes we depend on (stable constants) ---
TRADE_RETCODE_DONE = 10009
# Retryable: transient pricing/connection conditions worth a bounded re-quote.
RETRYABLE_RETCODES = frozenset({
    10004,  # REQUOTE
    10020,  # PRICE_CHANGED
    10021,  # PRICE_OFF (no quotes)
    10024,  # TOO_MANY_REQUESTS
    10031,  # CONNECTION (no connection to trade server)
})


# --- Neutral data views (broker-agnostic) -----------------------------------
@dataclass(frozen=True)
class TerminalView:
    connected: bool
    trade_allowed: bool
    name: str = ""
    company: str = ""
    path: str = ""


@dataclass(frozen=True)
class AccountView:
    login: int
    server: str
    currency: str
    balance: float
    equity: float
    trade_mode: int          # 0=real (FTMO challenge/trial run as 'real'), 1=demo, 2=contest
    leverage: int = 0
    name: str = ""


@dataclass(frozen=True)
class SymbolView:
    name: str
    digits: int
    point: float
    trade_tick_value: float
    trade_tick_size: float
    volume_min: float
    volume_max: float
    volume_step: float
    trade_stops_level: float       # in points
    trade_contract_size: float
    bid: float = 0.0
    ask: float = 0.0
    tick_time_epoch: int = 0       # last tick server time (epoch seconds)

    @property
    def pip_size(self) -> float:
        return self.point * (10 if self.digits in (3, 5) else 1)

    @property
    def pip_value_per_lot(self) -> float:
        if self.trade_tick_size <= 0:
            return 0.0
        return self.trade_tick_value * (self.pip_size / self.trade_tick_size)

    @property
    def stops_level_pips(self) -> float:
        return (self.trade_stops_level * self.point) / self.pip_size if self.pip_size else 0.0


@dataclass(frozen=True)
class PositionView:
    ticket: int
    symbol: str
    magic: int
    type: int           # 0 = buy, 1 = sell
    volume: float
    price_open: float
    sl: float
    tp: float
    comment: str = ""
    profit: float = 0.0


@dataclass(frozen=True)
class PendingView:
    ticket: int
    symbol: str
    magic: int
    type: int
    volume_current: float
    price_open: float
    sl: float
    tp: float
    comment: str = ""


@dataclass(frozen=True)
class DealView:
    ticket: int
    order: int
    position_id: int
    symbol: str
    magic: int
    volume: float
    price: float
    commission: float
    time_epoch: int
    comment: str = ""
    entry: int = 0      # 0 = in, 1 = out


@dataclass(frozen=True)
class BrokerOrder:
    """Neutral order request the adapter builds; RealMT5Broker maps it to mt5 fields."""

    action: str          # "deal" | "pending" | "sltp" | "remove" | "close"
    symbol: str
    order_type: str      # "buy" | "sell" | "buy_stop" | "sell_stop" | "buy_limit" | "sell_limit"
    volume: float = 0.0
    price: float | None = None
    sl: float = 0.0
    tp: float = 0.0
    deviation: int = 20
    magic: int = 0
    comment: str = ""
    position: int | None = None      # ticket for close/sltp
    order_ticket: int | None = None  # ticket for remove
    expire_epoch: int | None = None


@dataclass(frozen=True)
class OrderSendResult:
    retcode: int
    order: int = 0
    deal: int = 0
    price: float = 0.0
    volume: float = 0.0
    comment: str = ""


class Broker(Protocol):
    def initialize(self, path: str | None) -> bool: ...
    def login(self, login: int, password: str, server: str) -> bool: ...
    def shutdown(self) -> None: ...
    def last_error(self) -> tuple: ...
    def terminal_info(self) -> TerminalView | None: ...
    def account_info(self) -> AccountView | None: ...
    def symbol_select(self, symbol: str, enable: bool) -> bool: ...
    def symbol_info(self, symbol: str) -> SymbolView | None: ...
    def positions_get(self, symbol: str | None = None) -> list[PositionView]: ...
    def orders_get(self, symbol: str | None = None) -> list[PendingView]: ...
    def history_deals_get(self, since_epoch: int) -> list[DealView]: ...
    def order_send(self, order: BrokerOrder) -> OrderSendResult: ...


class RealMT5Broker:
    """The only code that imports MetaTrader5 (Windows-only). Maps mt5 named tuples to
    the neutral views above. Untested off-Windows by design; validated on the demo (A2)."""

    def __init__(self) -> None:
        try:
            import MetaTrader5 as mt5  # type: ignore
        except Exception as exc:  # pragma: no cover
            raise RuntimeError(
                "MetaTrader5 is unavailable (Windows-only, terminal must be running)."
            ) from exc
        self._mt5 = mt5
        self._order_type_map = {
            "buy": mt5.ORDER_TYPE_BUY, "sell": mt5.ORDER_TYPE_SELL,
            "buy_stop": mt5.ORDER_TYPE_BUY_STOP, "sell_stop": mt5.ORDER_TYPE_SELL_STOP,
            "buy_limit": mt5.ORDER_TYPE_BUY_LIMIT, "sell_limit": mt5.ORDER_TYPE_SELL_LIMIT,
        }

    def initialize(self, path: str | None) -> bool:
        return bool(self._mt5.initialize(path=path) if path else self._mt5.initialize())

    def login(self, login: int, password: str, server: str) -> bool:
        return bool(self._mt5.login(login=login, password=password, server=server))

    def shutdown(self) -> None:
        self._mt5.shutdown()

    def last_error(self) -> tuple:
        return self._mt5.last_error()

    def terminal_info(self) -> TerminalView | None:
        t = self._mt5.terminal_info()
        if t is None:
            return None
        return TerminalView(connected=t.connected, trade_allowed=t.trade_allowed,
                            name=t.name, company=t.company, path=t.path)

    def account_info(self) -> AccountView | None:
        a = self._mt5.account_info()
        if a is None:
            return None
        return AccountView(login=a.login, server=a.server, currency=a.currency,
                           balance=a.balance, equity=a.equity, trade_mode=a.trade_mode,
                           leverage=a.leverage, name=a.name)

    def symbol_select(self, symbol: str, enable: bool) -> bool:
        return bool(self._mt5.symbol_select(symbol, enable))

    def symbol_info(self, symbol: str) -> SymbolView | None:
        s = self._mt5.symbol_info(symbol)
        if s is None:
            return None
        tick = self._mt5.symbol_info_tick(symbol)
        return SymbolView(
            name=s.name, digits=s.digits, point=s.point,
            trade_tick_value=s.trade_tick_value, trade_tick_size=s.trade_tick_size,
            volume_min=s.volume_min, volume_max=s.volume_max, volume_step=s.volume_step,
            trade_stops_level=s.trade_stops_level, trade_contract_size=s.trade_contract_size,
            bid=getattr(tick, "bid", 0.0), ask=getattr(tick, "ask", 0.0),
            tick_time_epoch=int(getattr(tick, "time", 0)),
        )

    def positions_get(self, symbol: str | None = None) -> list[PositionView]:
        rows = self._mt5.positions_get(symbol=symbol) if symbol else self._mt5.positions_get()
        return [PositionView(ticket=p.ticket, symbol=p.symbol, magic=p.magic, type=p.type,
                             volume=p.volume, price_open=p.price_open, sl=p.sl, tp=p.tp,
                             comment=p.comment, profit=p.profit) for p in (rows or [])]

    def orders_get(self, symbol: str | None = None) -> list[PendingView]:
        rows = self._mt5.orders_get(symbol=symbol) if symbol else self._mt5.orders_get()
        return [PendingView(ticket=o.ticket, symbol=o.symbol, magic=o.magic, type=o.type,
                            volume_current=o.volume_current, price_open=o.price_open,
                            sl=o.sl, tp=o.tp, comment=o.comment) for o in (rows or [])]

    def history_deals_get(self, since_epoch: int) -> list[DealView]:
        import time
        rows = self._mt5.history_deals_get(since_epoch, int(time.time()) + 3600)
        return [DealView(ticket=d.ticket, order=d.order, position_id=d.position_id,
                         symbol=d.symbol, magic=d.magic, volume=d.volume, price=d.price,
                         commission=d.commission, time_epoch=int(d.time),
                         comment=d.comment, entry=d.entry) for d in (rows or [])]

    def order_send(self, order: BrokerOrder) -> OrderSendResult:
        mt5 = self._mt5
        req: dict = {"symbol": order.symbol, "magic": order.magic,
                     "comment": order.comment, "deviation": order.deviation}
        if order.action == "deal":
            req["action"] = mt5.TRADE_ACTION_DEAL
        elif order.action == "pending":
            req["action"] = mt5.TRADE_ACTION_PENDING
            req["type_time"] = mt5.ORDER_TIME_GTC if not order.expire_epoch else mt5.ORDER_TIME_SPECIFIED
            if order.expire_epoch:
                req["expiration"] = order.expire_epoch
        elif order.action == "sltp":
            req["action"] = mt5.TRADE_ACTION_SLTP
            req["position"] = order.position
        elif order.action == "remove":
            req["action"] = mt5.TRADE_ACTION_REMOVE
            req["order"] = order.order_ticket
        elif order.action == "close":
            req["action"] = mt5.TRADE_ACTION_DEAL
            req["position"] = order.position
        if order.order_type in self._order_type_map and order.action in ("deal", "pending", "close"):
            req["type"] = self._order_type_map[order.order_type]
        if order.volume:
            req["volume"] = order.volume
        if order.price is not None:
            req["price"] = order.price
        if order.sl:
            req["sl"] = order.sl
        if order.tp:
            req["tp"] = order.tp
        res = mt5.order_send(req)
        if res is None:
            return OrderSendResult(retcode=-1, comment=str(mt5.last_error()))
        return OrderSendResult(retcode=res.retcode, order=res.order, deal=res.deal,
                               price=res.price, volume=res.volume, comment=res.comment)
