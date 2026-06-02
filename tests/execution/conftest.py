"""FakeBroker + spy journal for execution tests (no live MT5 needed)."""

from __future__ import annotations

from src.execution.broker import (
    AccountView,
    BrokerOrder,
    DealView,
    OrderSendResult,
    PendingView,
    PositionView,
    SymbolView,
    TerminalView,
)
from src.execution.broker import TRADE_RETCODE_DONE
from src.journal import Journal

MAGIC = 770042


class SpyJournal(Journal):
    """Wraps the real Journal, recording append ordering into a shared events list."""

    def __init__(self, state_dir, events):
        super().__init__(state_dir)
        self._events = events

    def append(self, record):
        self._events.append(("journal", record.get("record_type"), record.get("status")))
        return super().append(record)


class FakeBroker:
    def __init__(self, *, fill_on_send=True, magic=MAGIC):
        self.events: list = []
        self.fill_on_send = fill_on_send
        self.magic = magic
        self._positions: list[PositionView] = []
        self._pendings: list[PendingView] = []
        self._deals: list[DealView] = []
        self._ticket = 1000
        self.retcode_sequence: list[int] = []   # pop(0) per send; else DONE
        self.account = AccountView(login=1513571406, server="FTMO-Demo", currency="USD",
                                   balance=100_000.0, equity=100_000.0, trade_mode=0,
                                   leverage=100, name="FTMO Free Trial")
        self.terminal = TerminalView(connected=True, trade_allowed=True, name="FTMO")
        self.symbol = SymbolView(name="EURUSD", digits=5, point=1e-5, trade_tick_value=1.0,
                                 trade_tick_size=1e-5, volume_min=0.01, volume_max=50.0,
                                 volume_step=0.01, trade_stops_level=0.0,
                                 trade_contract_size=100_000.0, bid=1.16526, ask=1.16527,
                                 tick_time_epoch=1_900_000_000)
        self._init_ok = True
        self._login_ok = True

    # connection
    def initialize(self, path): self.events.append(("initialize", path)); return self._init_ok
    def login(self, login, password, server): self.events.append(("login", login)); return self._login_ok
    def shutdown(self): self.events.append(("shutdown",))
    def last_error(self): return (0, "ok")
    def terminal_info(self): return self.terminal
    def account_info(self): return self.account
    def symbol_select(self, symbol, enable): return True
    def symbol_info(self, symbol): return self.symbol

    def positions_get(self, symbol=None):
        return [p for p in self._positions if symbol is None or p.symbol == symbol]

    def orders_get(self, symbol=None):
        return [o for o in self._pendings if symbol is None or o.symbol == symbol]

    def history_deals_get(self, since_epoch):
        return list(self._deals)

    def order_send(self, order: BrokerOrder) -> OrderSendResult:
        self.events.append(("order_send", order.action, order.comment))
        retcode = self.retcode_sequence.pop(0) if self.retcode_sequence else TRADE_RETCODE_DONE
        if retcode != TRADE_RETCODE_DONE:
            return OrderSendResult(retcode=retcode, comment=f"reject {retcode}")
        self._ticket += 1
        price = order.price or (self.symbol.ask if "buy" in order.order_type else self.symbol.bid)
        if order.action in ("deal", "pending"):
            ptype = 0 if order.order_type.startswith("buy") else 1
            self._positions.append(PositionView(
                ticket=self._ticket, symbol=order.symbol, magic=order.magic, type=ptype,
                volume=order.volume, price_open=price, sl=order.sl, tp=order.tp,
                comment=order.comment))
            self._deals.append(DealView(
                ticket=self._ticket, order=self._ticket, position_id=self._ticket,
                symbol=order.symbol, magic=order.magic, volume=order.volume, price=price,
                commission=-3.5, time_epoch=1_900_000_000, comment=order.comment, entry=0))
        elif order.action == "close":
            self._positions = [p for p in self._positions if p.ticket != order.position]
        return OrderSendResult(retcode=retcode, order=self._ticket, deal=self._ticket,
                               price=price, volume=order.volume, comment="done")

    # test helpers
    def add_position(self, comment, magic=None, ticket=None, symbol="EURUSD"):
        self._ticket += 1
        self._positions.append(PositionView(
            ticket=ticket or self._ticket, symbol=symbol, magic=magic or self.magic, type=0,
            volume=0.1, price_open=1.16, sl=1.158, tp=1.165, comment=comment))
        return self._positions[-1]
