"""Event-driven backtester (spec 05 §1-§2) — the system of record / final arbiter.

It replays bars through the EXACT production ``Strategy`` (01) and ``RiskGovernor`` (02)
code plus a simulated execution with the cost model. A backtest that passes is therefore
a statement about the code that will actually trade. ``VectorbtSweeper`` is a coarse
pre-filter only; its hits are re-confirmed here before any gate verdict.

Exit model (spec 01 §3.5 — the "full exit model"). One open position at a time. Two
classes of exit, sequenced to be liveable AND conservative:

  * Broker-side, intrabar-exact: the initial stop and the FINAL target are modelled as a
    broker stop + broker take-profit; they fill the instant the bar's range touches them.
    Same-bar ambiguity (range spans both) resolves to the STOP first (pessimistic).
  * Management-driven, close-based: intermediate partial take-profits, the break-even stop
    move, and any trailing stop are decided at BAR CLOSE (one request each, rarely), exactly
    as a live ``strategy.manage`` step on a closed bar would. Close-based => never assumes we
    caught an intrabar spike we couldn't have managed; partials are therefore pessimistic.

A management action on bar N only affects bars N+1.. (it cannot change an intrabar fill that
already happened during bar N). Legs are aggregated into ONE ``SimTrade`` per entry, so the
metrics/gates treat a scaled-out position as a single trade with its blended R-multiple.

PARITY NOTE: the live path does not yet implement intermediate partials (it exits 100% at
the broker TP). Mirroring this model into ``strategy.manage`` + the execution adapter is a
required follow-up (Phase 2) before any config relying on these exits is promoted/deployed.
Until then ``live == backtest`` is preserved only for the single-target (100%-at-target)
configuration; the multi-target exits below are backtest-only R&D.
"""

from __future__ import annotations

from dataclasses import dataclass, field
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

_EPS_LOTS = 1e-9


@dataclass
class _Leg:
    """One realized slice of a position (a partial or the final close)."""
    lots: float
    exit_price: float
    pnl_usd: float
    reason: str


@dataclass
class _Target:
    """An intermediate partial take-profit level managed at bar close."""
    price: float
    fraction: float
    filled: bool = False


@dataclass
class _OpenPosition:
    side: str
    entry_price: float
    initial_lots: float          # size at entry; partials are fractions of THIS
    lots: float                  # remaining open size
    sl_price: float              # current (mutable) stop; may move to BE / trail
    risk_price: float            # |entry - initial_sl| in price; fixes the R denominator
    final_tp: float              # broker take-profit for the runner (the last target)
    entry_ts: datetime
    risk_usd: float
    spread_at_entry: float
    entry_slippage: float
    partial_targets: list = field(default_factory=list)
    move_be_after_r: float | None = None
    trail: object | None = None  # engine.types.TrailRule | None
    be_moved: bool = False
    last_modify_idx: int = 0     # bar index of last trail modify (throttle)
    legs: list = field(default_factory=list)
    mae_pips: float = 0.0
    mfe_pips: float = 0.0
    vol_state: str = "normal"


class _TradeView:
    """Minimal read-only view passed to Strategy.manage() (explicit-close hook only)."""
    def __init__(self, pos, bars_held: int):
        self.direction = pos.side
        self.entry_price = pos.entry_price
        self.sl_price = pos.sl_price
        self.tp_price = pos.final_tp
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

    def run_on_bars(self, bars: list, req: BacktestRequest) -> BacktestReport:
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
        pos = None
        pos_opened_idx = 0
        trades: list = []

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

                # (1) Intrabar broker orders first: stop (current sl) then FINAL target.
                realized, finished = self._intrabar(pos, bar, now)
                balance += realized
                if finished is not None:
                    trades.append(finished)
                    day = _dec_open_risk(day, pos.risk_usd)
                    pos = None
                else:
                    # (2) Closed-bar management: explicit close, partials, BE, trail.
                    realized2, finished2 = self._manage_closed_bar(
                        pos, bar, history, now, i, i - pos_opened_idx)
                    balance += realized2
                    if finished2 is not None:
                        trades.append(finished2)
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
            fill = self.cost.exit_fill(pos.side, last.close, last.spread_pips)
            balance += self._add_leg(pos, pos.lots, fill, "eod")
            trades.append(self._finalize(pos, ensure_utc(last.ts_open_utc)))

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
    def _maybe_enter(self, bar, history, now, day, balance, i):
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
        plan = sig.exit_plan
        risk_price = abs(fill - plan.initial_sl_price)
        risk_usd = risk_price / self.sm.pip_size * self.sm.pip_value_per_lot_usd * dec.lots

        targets = list(plan.targets) if plan.targets else []
        fractions = list(plan.partial_fractions) if plan.partial_fractions else []
        if targets:
            final_tp = targets[-1]
            # Intermediate targets are partial take-profits managed at bar close; the last
            # target is the broker TP for the runner. Pair each intermediate target with its
            # fraction (defaulting to an even split if fractions are absent/misaligned).
            partial_targets = []
            for idx in range(len(targets) - 1):
                frac = fractions[idx] if idx < len(fractions) else (1.0 / len(targets))
                partial_targets.append(_Target(price=targets[idx], fraction=frac))
        else:
            final_tp = (fill + 100 * self.sm.pip_size) if side == "long" \
                else (fill - 100 * self.sm.pip_size)
            partial_targets = []

        pos = _OpenPosition(
            side=side, entry_price=fill, initial_lots=dec.lots, lots=dec.lots,
            sl_price=plan.initial_sl_price, risk_price=risk_price, final_tp=final_tp,
            entry_ts=now, risk_usd=risk_usd, spread_at_entry=bar.spread_pips,
            entry_slippage=slip, partial_targets=partial_targets,
            move_be_after_r=plan.move_be_after_r, trail=plan.trail,
            last_modify_idx=i,
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

    # ---- exit sequencing ------------------------------------------------
    def _intrabar(self, pos, bar, now):
        """Resolve the broker stop (current sl) and the FINAL target, intrabar.

        Conservative: if a bar's range spans both, the STOP is taken first."""
        if pos.side == "long":
            hit_sl = bar.low <= pos.sl_price
            hit_tp = bar.high >= pos.final_tp
        else:
            hit_sl = bar.high >= pos.sl_price
            hit_tp = bar.low <= pos.final_tp

        if hit_sl:
            opp = "short" if pos.side == "long" else "long"
            fill = self.cost.stop_entry_fill(opp, pos.sl_price)
            reason = "be" if (pos.be_moved and _approx(pos.sl_price, pos.entry_price)) else "sl"
            realized = self._add_leg(pos, pos.lots, fill, reason)
            return realized, self._finalize(pos, now)
        if hit_tp:
            realized = self._add_leg(pos, pos.lots, pos.final_tp, "tp")  # limit fill, exact
            return realized, self._finalize(pos, now)
        return 0.0, None

    def _manage_closed_bar(self, pos, bar, history, now, i, bars_held):
        """Close-based management: explicit strategy close, then partials, BE, trailing.

        Decisions here take effect on subsequent bars (a live ``manage`` runs at bar close)."""
        realized = 0.0

        # Explicit discretionary close from the strategy (e.g. a time-stop). Kept as a hook;
        # the default SessionBreakoutER returns hold here (BE/partials are plan-driven).
        if self._manage(pos, history, now, bars_held) == "close":
            fill = self.cost.exit_fill(pos.side, bar.close, bar.spread_pips)
            realized += self._add_leg(pos, pos.lots, fill, "manage_close")
            return realized, self._finalize(pos, now)

        # Intermediate partial take-profits — triggered when the bar CLOSES beyond a level.
        for t in pos.partial_targets:
            if t.filled:
                continue
            reached = (bar.close >= t.price) if pos.side == "long" else (bar.close <= t.price)
            if not reached:
                continue
            leg_lots = self._round_lots(t.fraction * pos.initial_lots)
            leg_lots = min(leg_lots, pos.lots)
            if leg_lots < self.sm.min_lot - _EPS_LOTS:
                t.filled = True            # too small to trade at the broker; skip
                continue
            if pos.lots - leg_lots < self.sm.min_lot - _EPS_LOTS:
                leg_lots = pos.lots        # don't leave un-closeable dust
            fill = self.cost.exit_fill(pos.side, bar.close, bar.spread_pips)
            realized += self._add_leg(pos, leg_lots, fill, "tp")
            t.filled = True
            if pos.lots <= _EPS_LOTS:
                return realized, self._finalize(pos, now)

        # Break-even stop move (close-based fav excursion >= move_be_after_r).
        if pos.move_be_after_r is not None and not pos.be_moved and pos.risk_price > 0:
            fav_r = self._fav_r_close(pos, bar)
            if fav_r >= pos.move_be_after_r:
                pos.sl_price = pos.entry_price
                pos.be_moved = True

        # Trailing stop (optional; off by default in v1).
        if pos.trail is not None:
            self._apply_trail(pos, bar, i)

        return realized, None

    def _apply_trail(self, pos, bar, i):
        trail = pos.trail
        if pos.risk_price <= 0:
            return
        if self._fav_r_close(pos, bar) < trail.activate_after_r:
            return
        # Throttle: respect a minimum spacing between modifies (seconds -> bars).
        tf_min = getattr(self.strategy, "tf_min", 15) or 15
        min_bars = max(1, int(trail.min_seconds_between_modifies // (tf_min * 60)))
        if i - pos.last_modify_idx < min_bars:
            return
        pip = self.sm.pip_size
        dist = trail.distance_pips * pip
        if pos.side == "long":
            candidate = bar.close - dist
            if candidate > pos.sl_price + trail.step_pips * pip - _EPS_LOTS:
                pos.sl_price = candidate
                pos.last_modify_idx = i
        else:
            candidate = bar.close + dist
            if candidate < pos.sl_price - trail.step_pips * pip + _EPS_LOTS:
                pos.sl_price = candidate
                pos.last_modify_idx = i

    def _manage(self, pos, history, now, bars_held) -> str:
        if not hasattr(self.strategy, "manage"):
            return "hold"
        try:
            action = self.strategy.manage(_TradeView(pos, bars_held), history, now)
        except NotImplementedError:
            return "hold"
        kind = getattr(action, "kind", "hold")
        return "close" if kind in ("close", "close_all") else "hold"

    # ---- leg accounting -------------------------------------------------
    def _add_leg(self, pos, lots, exit_price, reason) -> float:
        """Realize ``lots`` of the position at ``exit_price``; return this leg's net P&L."""
        lots = min(lots, pos.lots)
        pnl = self.cost.pnl_usd(pos.side, pos.entry_price, exit_price, lots)
        pos.legs.append(_Leg(lots=lots, exit_price=exit_price, pnl_usd=pnl, reason=reason))
        pos.lots = max(0.0, pos.lots - lots)
        return pnl

    def _finalize(self, pos, now) -> SimTrade:
        """Aggregate all realized legs into a single SimTrade for metrics/gates."""
        legs = pos.legs
        total_lots = sum(leg.lots for leg in legs) or pos.initial_lots
        pnl = sum(leg.pnl_usd for leg in legs)
        vw_exit = sum(leg.lots * leg.exit_price for leg in legs) / total_lots
        gross = self.cost.gross_pips(pos.side, pos.entry_price, vw_exit)
        commission = self.cost.commission(total_lots)
        net_pips = gross - (commission / (self.sm.pip_value_per_lot_usd * total_lots)
                            if total_lots else 0.0)
        r = pnl / pos.risk_usd if pos.risk_usd > 0 else 0.0
        last_reason = legs[-1].reason if legs else "eod"
        reason = last_reason + "+p" if len(legs) > 1 else last_reason
        return SimTrade(
            entry_ts=pos.entry_ts, exit_ts=now, direction=pos.side,
            entry_price=pos.entry_price, exit_price=vw_exit, lots=total_lots,
            sl_price=pos.sl_price, r_multiple=r, pnl_usd=pnl, gross_pips=gross,
            net_pips=net_pips, mae_pips=pos.mae_pips, mfe_pips=pos.mfe_pips,
            exit_reason=reason, commission_usd=commission,
            entry_slippage_pips=pos.entry_slippage, spread_at_entry_pips=pos.spread_at_entry,
            regime_vol_state=pos.vol_state,
        )

    def _fav_r_close(self, pos, bar) -> float:
        fav = (bar.close - pos.entry_price) if pos.side == "long" \
            else (pos.entry_price - bar.close)
        return fav / pos.risk_price if pos.risk_price > 0 else 0.0

    def _round_lots(self, lots) -> float:
        step = self.sm.lot_step or 0.01
        return max(0.0, round(round(lots / step) * step, 8))

    def _unrealized(self, pos, price) -> float:
        return self.cost.gross_pips(pos.side, pos.entry_price, price) \
            * self.sm.pip_value_per_lot_usd * pos.lots


def _approx(a, b, tol=1e-9) -> bool:
    return abs(a - b) <= tol


def _to_engine_bar(b: BTBar) -> EngineBar:
    return EngineBar(ts_open_utc=b.ts_open_utc, open=b.open, high=b.high, low=b.low,
                     close=b.close, volume=b.volume, is_closed=True)


def _update_excursion(pos, bar, pip):
    if pos.side == "long":
        adverse = (pos.entry_price - bar.low) / pip
        favor = (bar.high - pos.entry_price) / pip
    else:
        adverse = (bar.high - pos.entry_price) / pip
        favor = (pos.entry_price - bar.low) / pip
    return max(pos.mae_pips, adverse), max(pos.mfe_pips, favor)


def _dec_open_risk(day, risk_usd):
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
