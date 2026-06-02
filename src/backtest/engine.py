"""Event-driven backtester (spec 05 §1-§2) — the system of record / final arbiter.

It replays bars through the EXACT production ``Strategy`` (01) and ``RiskGovernor`` (02)
code plus a simulated execution with the cost model. A backtest that passes is therefore
a statement about the code that will actually trade. ``VectorbtSweeper`` is a coarse
pre-filter only; its hits are re-confirmed here before any gate verdict.

v1 models a single open position with intrabar SL/TP resolution (conservative: if a bar's
range spans both the stop and target, the stop is assumed hit first).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from src.common.timeutil import ensure_utc, ftmo_day_start, is_new_ftmo_day
from src.engine.strategy import to_risk_signal
from src.engine.types import Bar as EngineBar
from src.engine.types import Signal as EngineSignal
from src.risk.governor import RiskGovernor, apply_daily_reset
from src.risk.types import AccountState, ContextBias, DayState, SymbolMeta

from .costs import CostModel
from .ftmo_sim import FtmoTracker
from .gates import GatesConfig, all_passed, evaluate_gates
from .metrics import summarize
from .types import BacktestReport, BacktestRequest, BTBar, SimTrade


@dataclass
class _OpenPosition:
    side: str
    entry_price: float
    lots: float
    sl_price: float
    tp_price: float
    entry_ts: datetime
    risk_usd: float
    spread_at_entry: float
    entry_slippage: float
    mae_pips: float = 0.0
    mfe_pips: float = 0.0
    vol_state: str = "normal"


class _TradeView:
    """Minimal read-only view passed to Strategy.manage()."""
    def __init__(self, pos: _OpenPosition, bars_held: int):
        self.direction = pos.side
        self.entry_price = pos.entry_price
        self.sl_price = pos.sl_price
        self.tp_price = pos.tp_price
        self.lots = pos.lots
        self.bars_held = bars_held


class EventDrivenBacktester:
    def __init__(
        self,
        strategy,
        governor: RiskGovernor,
        symbol_meta: SymbolMeta,
        cost_model: CostModel,
        *,
        initial_balance: float = 100_000.0,
        currency: str = "USD",
        calendar=None,
        gates_cfg: GatesConfig | None = None,
        data_loader=None,
        history_window: int = 400,
    ):
        self.strategy = strategy
        self.governor = governor
        self.sm = symbol_meta
        self.cost = cost_model
        self.initial = initial_balance
        self.currency = currency
        self.calendar = calendar
        self.gates_cfg = gates_cfg or GatesConfig()
        # data_loader: Callable[[BacktestRequest], list[BTBar]] (e.g. read cleaned Parquet).
        self.data_loader = data_loader
        # Bounded trailing window handed to the strategy each bar — keeps the loop O(N*W),
        # not O(N^2). Must comfortably cover warmup + one full session day (~96 M15 bars).
        self.history_window = history_window

    # ------------------------------------------------------------------- run
    def run(self, req: BacktestRequest) -> BacktestReport:
        if self.data_loader is None:
            raise NotImplementedError(
                "no data_loader configured; pass one (e.g. read cleaned Parquet) or call "
                "run_on_bars(bars, req) directly (spec 05 §3)."
            )
        bars = self.data_loader(req)
        return self.run_on_bars(bars, req)

    def run_on_bars(self, bars: list[BTBar], req: BacktestRequest) -> BacktestReport:
        if not bars:
            raise ValueError("no bars to replay")
        pip = self.sm.pip_size
        warmup = self.strategy.warmup_bars()
        ebars = [_to_engine_bar(b) for b in bars]   # convert once, reuse via slicing
        W = max(self.history_window, warmup + 5)

        day = DayState(balance_0000=self.initial, initial=self.initial,
                       reset_ts_utc=ftmo_day_start(bars[0].ts_open_utc))
        ftmo = FtmoTracker(self.initial, self.initial)
        balance = self.initial
        pos: _OpenPosition | None = None
        pos_opened_idx = 0
        trades: list[SimTrade] = []

        for i, bar in enumerate(bars):
            now = ensure_utc(bar.ts_open_utc)

            # 00:00 CE(S)T reset.
            if is_new_ftmo_day(day.reset_ts_utc, now):
                day = apply_daily_reset(day, balance, now)
                ftmo.reset_day(balance)

            if i < warmup:
                ftmo.update(balance)
                continue

            history = ebars[max(0, i - W + 1): i + 1]

            if pos is not None:
                pos.mae_pips, pos.mfe_pips = _update_excursion(pos, bar, pip)
                exit_price, reason = self._intrabar_exit(pos, bar)
                if exit_price is None:
                    action = self._manage(pos, history, now, i - pos_opened_idx)
                    if action == "close":
                        exit_price = self.cost.exit_fill(pos.side, bar.close, bar.spread_pips)
                        reason = "manage_close"
                if exit_price is not None:
                    trades.append(self._close(pos, exit_price, now, reason))
                    balance += trades[-1].pnl_usd
                    day = _dec_open_risk(day, pos.risk_usd)
                    pos = None

            elif day.killswitch.value not in ("halted", "flatten"):
                pos, day, balance = self._maybe_enter(bar, history, now, day, balance, i)
                if pos is not None:
                    pos_opened_idx = i

            equity = balance + (self._unrealized(pos, bar.close) if pos else 0.0)
            ftmo.observe_requests(day.requests_used_today)
            ftmo.update(equity)

        # Close any residual position at the last bar (end of data).
        if pos is not None:
            last = bars[-1]
            exit_price = self.cost.exit_fill(pos.side, last.close, last.spread_pips)
            trades.append(self._close(pos, exit_price, ensure_utc(last.ts_open_utc), "eod"))
            balance += trades[-1].pnl_usd

        metrics = summarize(trades, initial=self.initial)
        ftmo_report = ftmo.report()
        gates = evaluate_gates(metrics, ftmo_report["breaches"], req.trial_count,
                               cfg=self.gates_cfg)
        return BacktestReport(
            request=req, passed=all_passed(gates), gates=gates, metrics=metrics,
            ftmo=ftmo_report, oos={}, overfitting={
                "deflated_sharpe": gates["deflated_sharpe"].value,
                "trial_count": req.trial_count},
            artifacts={"final_balance": balance, "trade_count": len(trades),
                       "trades": trades},
        )

    # ------------------------------------------------------------- internals
    def _maybe_enter(self, bar, history, now, day: DayState, balance, i):
        sig = self.strategy.evaluate(history, now, ContextBias.NORMAL, self.calendar)
        if not isinstance(sig, EngineSignal):
            return None, day, balance
        rsig = to_risk_signal(
            sig, reference_price=sig.entry_price, news_blackout_active=False,
            near_session_gap=False, opposing_position_open=False,
            adds_to_losing_same_dir=False, pending_orders_count=0,
        )
        equity = balance
        acct = AccountState(equity=equity, balance=balance, currency=self.currency,
                            ts_utc=now, is_fresh=True)
        dec = self.governor.evaluate_entry(rsig, acct, day, now, self.sm)
        if not dec.approved or dec.lots <= 0:
            return None, day, balance
        side = sig.direction.value
        fill = self.cost.stop_entry_fill(side, sig.entry_price) if sig.entry_type == "stop" \
            else self.cost.entry_fill(side, sig.entry_price, bar.spread_pips)
        slip = abs(fill - sig.entry_price) / self.sm.pip_size
        risk_usd = abs(fill - sig.exit_plan.initial_sl_price) / self.sm.pip_size \
            * self.sm.pip_value_per_lot_usd * dec.lots
        tp = sig.exit_plan.targets[0] if sig.exit_plan.targets else (
            fill + 100 * self.sm.pip_size if side == "long" else fill - 100 * self.sm.pip_size)
        pos = _OpenPosition(
            side=side, entry_price=fill, lots=dec.lots,
            sl_price=sig.exit_plan.initial_sl_price, tp_price=tp, entry_ts=now,
            risk_usd=risk_usd, spread_at_entry=bar.spread_pips, entry_slippage=slip,
            vol_state=getattr(sig.regime, "vol_state", "normal").value
            if hasattr(getattr(sig.regime, "vol_state", None), "value") else "normal",
        )
        day = DayState(
            balance_0000=day.balance_0000, initial=day.initial,
            requests_used_today=day.requests_used_today + 1, killswitch=day.killswitch,
            open_risk_usd=day.open_risk_usd + risk_usd,
            trades_opened_today=day.trades_opened_today + 1,
            reset_ts_utc=day.reset_ts_utc, recent_risk_usds=day.recent_risk_usds,
        )
        return pos, day, balance

    def _manage(self, pos, history, now, bars_held) -> str:
        if not hasattr(self.strategy, "manage"):
            return "hold"
        try:
            action = self.strategy.manage(_TradeView(pos, bars_held), history, now)
        except NotImplementedError:
            return "hold"
        kind = getattr(action, "kind", "hold")
        return "close" if kind in ("close", "close_all") else "hold"

    def _intrabar_exit(self, pos: _OpenPosition, bar: BTBar):
        """Return (exit_price, reason) if SL/TP hit this bar, else (None, '')."""
        if pos.side == "long":
            hit_sl = bar.low <= pos.sl_price
            hit_tp = bar.high >= pos.tp_price
            if hit_sl:  # conservative: stop assumed first if both in range
                return self.cost.stop_entry_fill("short", pos.sl_price), "sl"
            if hit_tp:
                return pos.tp_price, "tp"
        else:
            hit_sl = bar.high >= pos.sl_price
            hit_tp = bar.low <= pos.tp_price
            if hit_sl:
                return self.cost.stop_entry_fill("long", pos.sl_price), "sl"
            if hit_tp:
                return pos.tp_price, "tp"
        return None, ""

    def _close(self, pos: _OpenPosition, exit_price, now, reason) -> SimTrade:
        gross = self.cost.gross_pips(pos.side, pos.entry_price, exit_price)
        pnl = self.cost.pnl_usd(pos.side, pos.entry_price, exit_price, pos.lots)
        net_pips = gross - self.cost.commission(pos.lots) / (
            self.sm.pip_value_per_lot_usd * pos.lots) if pos.lots else gross
        r = pnl / pos.risk_usd if pos.risk_usd > 0 else 0.0
        return SimTrade(
            entry_ts=pos.entry_ts, exit_ts=now, direction=pos.side,
            entry_price=pos.entry_price, exit_price=exit_price, lots=pos.lots,
            sl_price=pos.sl_price, r_multiple=r, pnl_usd=pnl, gross_pips=gross,
            net_pips=net_pips, mae_pips=pos.mae_pips, mfe_pips=pos.mfe_pips,
            exit_reason=reason, commission_usd=self.cost.commission(pos.lots),
            entry_slippage_pips=pos.entry_slippage, spread_at_entry_pips=pos.spread_at_entry,
            regime_vol_state=pos.vol_state,
        )

    def _unrealized(self, pos: _OpenPosition, price) -> float:
        return self.cost.gross_pips(pos.side, pos.entry_price, price) \
            * self.sm.pip_value_per_lot_usd * pos.lots


def _to_engine_bar(b: BTBar) -> EngineBar:
    return EngineBar(ts_open_utc=b.ts_open_utc, open=b.open, high=b.high, low=b.low,
                     close=b.close, volume=b.volume, is_closed=True)


def _update_excursion(pos: _OpenPosition, bar: BTBar, pip: float):
    if pos.side == "long":
        adverse = (pos.entry_price - bar.low) / pip
        favor = (bar.high - pos.entry_price) / pip
    else:
        adverse = (bar.high - pos.entry_price) / pip
        favor = (pos.entry_price - bar.low) / pip
    return max(pos.mae_pips, adverse), max(pos.mfe_pips, favor)


def _dec_open_risk(day: DayState, risk_usd: float) -> DayState:
    return DayState(
        balance_0000=day.balance_0000, initial=day.initial,
        requests_used_today=day.requests_used_today, killswitch=day.killswitch,
        open_risk_usd=max(0.0, day.open_risk_usd - risk_usd),
        trades_opened_today=day.trades_opened_today, reset_ts_utc=day.reset_ts_utc,
        recent_risk_usds=day.recent_risk_usds,
    )


class VectorbtSweeper:
    """Coarse pre-filter ONLY — never the promotion arbiter (spec 05 §2)."""

    def sweep(self, grid: dict, req: BacktestRequest):  # type: ignore[no-untyped-def]
        raise NotImplementedError("VectorbtSweeper.sweep — milestone A3 (spec 05 §2)")
