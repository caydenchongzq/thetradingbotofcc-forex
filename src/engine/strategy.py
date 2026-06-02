"""Strategy interface + SessionBreakoutER (spec 01).

The live loop and the backtester (05) both call exactly ``evaluate`` and ``manage`` — no
other surface. The engine is a PURE function of (bars, now, context_bias, calendar):
identical inputs => identical Signal. No wall-clock reads (only the injected ``now``),
no network, no hidden state. Every ambiguous/degraded state resolves to "no new trade"
(fail safe, README §2)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Optional, Protocol, Sequence, Union, runtime_checkable
from zoneinfo import ZoneInfo

from src.common.timeutil import ensure_utc
from src.risk.types import ContextBias
from src.risk.types import Signal as RiskSignal

from .indicators import efficiency_ratio, percentile_rank, true_ranges, wilder_atr
from .types import Bar, Direction, ExitPlan, NoSignal, RegimeState, Signal, VolState


@runtime_checkable
class EconomicCalendar(Protocol):
    def has_high_impact(self, currencies: Sequence[str], at_utc: datetime,
                        before_min: int, after_min: int) -> bool: ...


@runtime_checkable
class Strategy(Protocol):
    name: str
    config_version: int

    def warmup_bars(self) -> int: ...
    def evaluate(self, bars: Sequence[Bar], now_utc: datetime,
                 context_bias: ContextBias, calendar: "EconomicCalendar | None"
                 ) -> Union[Signal, NoSignal]: ...
    def manage(self, open_trade: object, bars: Sequence[Bar],
               now_utc: datetime) -> "ManageDecision": ...


@dataclass(frozen=True)
class ManageDecision:
    kind: str                     # "hold" | "move_sl" | "partial_close" | "close_all"
    sl_price: Optional[float] = None
    fraction: Optional[float] = None


def to_risk_signal(
    sig: Signal, *, reference_price: float | None, news_blackout_active: bool,
    near_session_gap: bool, opposing_position_open: bool,
    adds_to_losing_same_dir: bool, pending_orders_count: int,
) -> RiskSignal:
    """Bridge an engine Signal to the Risk Governor's evaluation request."""
    from src.risk.types import ExitPlan as RiskExitPlan
    return RiskSignal(
        instrument=sig.instrument, direction=sig.direction.value,
        exit_plan=RiskExitPlan(initial_sl_pips=sig.exit_plan.initial_sl_pips),
        signal_price=sig.entry_price, context_bias=sig.context_bias,
        reference_price=reference_price, news_blackout_active=news_blackout_active,
        near_session_gap=near_session_gap, opposing_position_open=opposing_position_open,
        adds_to_losing_same_dir=adds_to_losing_same_dir,
        pending_orders_count=pending_orders_count,
    )


def _t(hhmm: str) -> time:
    h, m = hhmm.split(":")
    return time(int(h), int(m))


class SessionBreakoutER:
    """R1's pick: London/NY-overlap opening-range breakout on 15m EURUSD, ER/ATR-gated."""

    name = "SessionBreakoutER"

    def __init__(self, config: dict):
        self.config = config or {}
        self.config_version = int(self.config.get("config_version", 1))
        s = self.config.get("session", {})
        self.tz = ZoneInfo(s.get("tz", "Europe/London"))
        self.win_start = _t(s.get("window_start", "13:00"))
        self.win_end = _t(s.get("window_end", "16:00"))
        self.or_minutes = int(s.get("opening_range_minutes", 30))
        self.one_shot = bool(s.get("one_shot_per_side", True))
        b = self.config.get("breakout", {})
        self.buffer_pips = float(b.get("buffer_pips", 1.5))
        r = self.config.get("regime", {})
        self.er_window = int(r.get("er_window", 14))
        self.er_threshold = float(r.get("er_threshold", 0.30))
        self.atr_window = int(r.get("atr_window", 14))
        self.atr_floor_pips = float(r.get("atr_floor_pips", 4.0))
        self.atr_ceiling_pips = float(r.get("atr_ceiling_pips", 22.0))
        self.atr_low_pct = float(r.get("atr_low_pct", 0.20))
        self.atr_high_pct = float(r.get("atr_high_pct", 0.90))
        e = self.config.get("exits", {})
        self.atr_mult_sl = float(e.get("atr_mult_sl", 1.2))
        self.target_r = tuple(e.get("target_r_multiples", [1.0, 2.0]))
        self.partials = tuple(e.get("partial_fractions", [0.5, 0.5]))
        self.move_be_after_r = e.get("move_be_after_r", 1.0)
        bl = self.config.get("blackout", {})
        self.blk_currencies = tuple(bl.get("high_impact_currencies", ["EUR", "USD"]))
        self.blk_before = int(bl.get("before_min", 15))
        self.blk_after = int(bl.get("after_min", 15))
        self.pip = float(self.config.get("pip_size", 0.0001))
        self.tf_min = int(self.config.get("timeframe_minutes", 15))

    # ----------------------------------------------------------------------
    def warmup_bars(self) -> int:
        return max(self.er_window, self.atr_window) + 2

    def _london(self, dt: datetime) -> datetime:
        return ensure_utc(dt).astimezone(self.tz)

    def _or_end(self) -> time:
        base = datetime(2000, 1, 1, self.win_start.hour, self.win_start.minute)
        end = (base + timedelta(minutes=self.or_minutes)).time()
        return end

    # ----------------------------------------------------------------------
    def evaluate(self, bars, now_utc, context_bias, calendar=None):
        now = ensure_utc(now_utc)
        if len(bars) < self.warmup_bars():
            return NoSignal(now, "insufficient_history")
        last = bars[-1]
        if not getattr(last, "is_closed", True):
            return NoSignal(now, "bad_bar_sequence")
        if len(bars) >= 2 and ensure_utc(bars[-1].ts_open_utc) <= ensure_utc(bars[-2].ts_open_utc):
            return NoSignal(now, "bad_bar_sequence")
        if context_bias is ContextBias.STAND_DOWN:
            return NoSignal(now, "stand_down")

        lon_now = self._london(now)
        or_end = self._or_end()
        if not (self.win_start <= lon_now.time() < self.win_end):
            return NoSignal(now, "outside_session")

        # Stale data: a closed 15m bar should be recent during an active session.
        age_s = (now - ensure_utc(last.ts_open_utc)).total_seconds()
        if age_s > 1.5 * self.tf_min * 60:
            return NoSignal(now, "stale_data")

        # Today's session bars (same London date), and the opening-range sub-window.
        day = lon_now.date()
        sess = [b for b in bars
                if self._london(b.ts_open_utc).date() == day
                and self.win_start <= self._london(b.ts_open_utc).time() < self.win_end]
        or_bars = [b for b in sess if self._london(b.ts_open_utc).time() < or_end]
        if not or_bars:
            return NoSignal(now, "outside_session")
        if self._london(last.ts_open_utc).time() < or_end:
            return NoSignal(now, "building_opening_range")

        regime = self._regime(bars)
        if not regime.regime_gate_passed:
            return NoSignal(now, "regime_gate_failed")   # logged as a rejected signal

        if self._blackout(now, calendar):
            return NoSignal(now, "news_blackout")

        range_high = max(b.high for b in or_bars)
        range_low = min(b.low for b in or_bars)
        buf = self.buffer_pips * self.pip
        long_level = range_high + buf
        short_level = range_low - buf

        post = [b for b in sess
                if self._london(b.ts_open_utc).time() >= or_end
                and ensure_utc(b.ts_open_utc) < ensure_utc(last.ts_open_utc)]
        long_fired = self.one_shot and any(b.close > long_level for b in post)
        short_fired = self.one_shot and any(b.close < short_level for b in post)

        if last.close > long_level and not long_fired:
            return self._signal(Direction.LONG, long_level, range_low, regime, now, context_bias)
        if last.close < short_level and not short_fired:
            return self._signal(Direction.SHORT, short_level, range_high, regime, now, context_bias)
        return NoSignal(now, "no_range_break")

    # ----------------------------------------------------------------------
    def _regime(self, bars) -> RegimeState:
        closes = [b.close for b in bars]
        highs = [b.high for b in bars]
        lows = [b.low for b in bars]
        er = efficiency_ratio(closes, self.er_window)
        atr_price = wilder_atr(highs, lows, closes, self.atr_window)
        atr_pips = atr_price / self.pip if self.pip else 0.0
        trs_pips = [tr / self.pip for tr in true_ranges(highs, lows, closes)[-60:]]
        pct = percentile_rank(atr_pips, trs_pips)

        degenerate = not (atr_pips > 0) or er != er  # NaN check
        if degenerate:
            vol = VolState.LOW
            passed = False
        else:
            if atr_pips < self.atr_floor_pips or pct < self.atr_low_pct:
                vol = VolState.LOW
            elif atr_pips > self.atr_ceiling_pips or pct > self.atr_high_pct:
                vol = VolState.HIGH
            else:
                vol = VolState.NORMAL
            passed = (er >= self.er_threshold) and (vol is VolState.NORMAL)
        return RegimeState(er=er, er_threshold=self.er_threshold, atr_pips=atr_pips,
                           atr_percentile=pct, vol_state=vol, regime_gate_passed=passed)

    def _blackout(self, now, calendar) -> bool:
        if calendar is None:
            return False  # no calendar injected (dev/backtest); Risk Governor re-checks
        try:
            return bool(calendar.has_high_impact(self.blk_currencies, now,
                                                 self.blk_before, self.blk_after))
        except Exception:
            return True   # fail closed: never trade blind into possible news (spec 01 §5)

    def _signal(self, direction, level, structure_stop, regime, now, bias) -> Signal:
        struct_sl_pips = abs(level - structure_stop) / self.pip
        atr_sl_pips = self.atr_mult_sl * regime.atr_pips
        sl_pips = max(struct_sl_pips, atr_sl_pips)
        if direction is Direction.LONG:
            sl_price = level - sl_pips * self.pip
            targets = tuple(level + r * sl_pips * self.pip for r in self.target_r)
        else:
            sl_price = level + sl_pips * self.pip
            targets = tuple(level - r * sl_pips * self.pip for r in self.target_r)
        plan = ExitPlan(initial_sl_price=sl_price, initial_sl_pips=sl_pips, targets=targets,
                        target_r_multiples=self.target_r, partial_fractions=self.partials,
                        move_be_after_r=self.move_be_after_r, trail=None)
        return Signal(instrument=self.config.get("instrument", "EURUSD"),
                      ts_decision_utc=now, direction=direction, entry_type="stop",
                      entry_price=level, exit_plan=plan, regime=regime,
                      session="london_ny_overlap", breakout_level=level,
                      entry_reason="range_break + ER>=thr + ATR_normal",
                      context_bias=bias, config_version=self.config_version)

    # ----------------------------------------------------------------------
    def manage(self, open_trade, bars, now_utc) -> ManageDecision:
        """Move stop to break-even once price has advanced `move_be_after_r` (spec 01 §3.5).
        Trailing is off by default in v1 (request-budget). Returns hold most of the time."""
        if self.move_be_after_r is None or not bars:
            return ManageDecision("hold")
        price = bars[-1].close
        entry = open_trade.entry_price
        sl = open_trade.sl_price
        risk = abs(entry - sl)
        if risk <= 0:
            return ManageDecision("hold")
        if open_trade.direction == "long":
            if price >= entry + self.move_be_after_r * risk and sl < entry:
                return ManageDecision("move_sl", sl_price=entry)
        else:
            if price <= entry - self.move_be_after_r * risk and sl > entry:
                return ManageDecision("move_sl", sl_price=entry)
        return ManageDecision("hold")
