"""Risk Governor (spec 02) — the deterministic gatekeeper.

Every order the strategy proposes passes through here. The Governor sizes it from the
live FTMO budget and vetoes anything that could breach a rule. Pure: all decisions are
a function of ``(signal, account, day, now, symbol_meta, config)``; the only inputs are
injected and the only outputs are the returned decision and (caller-persisted) state.

The single load-bearing guarantee (spec 02 §10): **no approved order can breach a floor.**
"""

from __future__ import annotations

import math
from datetime import datetime
from statistics import median

from src.common.config import RiskConfig

from .envelope import Envelope, compute_envelope
from .types import (
    AccountState,
    ContextBias,
    Decision,
    DayState,
    KillSwitchState,
    ManageAction,
    RiskDecision,
    Signal,
    SymbolMeta,
)


class RiskGovernor:
    def __init__(self, config: RiskConfig):
        self.cfg = config

    # =================================================================== entry
    def evaluate_entry(
        self,
        signal: Signal,
        account: AccountState,
        day: DayState,
        now_utc: datetime,
        symbol_meta: SymbolMeta,
    ) -> RiskDecision:
        cfg = self.cfg
        requests_remaining = max(0, cfg.request_hard_cap - day.requests_used_today)

        # --- Fail-safe gates that veto before sizing -------------------------
        # (12) Never trade on a stale/forced account state.
        if not account.is_fresh:
            return self._veto("stale_account", day, account,
                              {"no_stale_account": False}, requests_remaining)

        if symbol_meta.pip_value_per_lot(account.currency) <= 0 or symbol_meta.lot_step <= 0:
            return self._veto("symbol_meta_unavailable", day, account,
                              {"symbol_meta_available": False}, requests_remaining)

        sl_pips = signal.exit_plan.initial_sl_pips
        if not (sl_pips and sl_pips > 0 and math.isfinite(sl_pips)):
            return self._veto("invalid_sl_distance", day, account,
                              {"valid_sl": False}, requests_remaining)

        env = compute_envelope(day.balance_0000, day.initial, account.equity)

        # Kill-switch (latched). HALTED/FLATTEN block all new entries.
        ks = self.effective_killswitch(day, account)
        if ks is KillSwitchState.FLATTEN:
            return self._veto("killswitch_flatten", day, account,
                              {"killswitch_ok": False}, requests_remaining, env)
        if ks is KillSwitchState.HALTED:
            return self._veto("killswitch_halted_60pct", day, account,
                              {"killswitch_ok": False}, requests_remaining, env)

        # --- Size the order ---------------------------------------------------
        pip_value = symbol_meta.pip_value_per_lot(account.currency)
        buffer = cfg.slippage_spread_buffer
        denom = sl_pips * pip_value * (1.0 + buffer)

        f_eff = self._effective_risk_fraction(signal, day, account, env, ks)
        f_base = cfg.base_risk_fraction

        lots = self._lots_for_fraction(f_eff, account.equity, denom, symbol_meta)
        lots_base = self._lots_for_fraction(f_base, account.equity, denom, symbol_meta)

        if not math.isfinite(lots) or lots <= 0:
            return self._veto("unsafe_size_zero_lots", day, account,
                              {"floor_protection": False}, requests_remaining, env)

        risk_usd = lots * denom

        # --- Forbidden-practice checks (the 13-item checklist, §7) ------------
        checks = self._run_checks(signal, account, day, env, symbol_meta,
                                  risk_usd, sl_pips, requests_remaining)

        failed = [name for name, ok in checks.items() if not ok]
        if failed:
            return self._veto(self._reason_for(failed[0]), day, account, checks,
                              requests_remaining, env)

        # --- Decision ---------------------------------------------------------
        daily_pct_after = (env.daily_loss_used_usd) / env.daily_budget_usd \
            if env.daily_budget_usd > 0 else 0.0
        downsized = (lots < lots_base - 1e-12) or (f_eff < f_base - 1e-12)
        decision = Decision.APPROVE_DOWNSIZED if downsized else Decision.APPROVE
        return RiskDecision(
            decision=decision,
            lots=round(lots, 2),
            risk_usd=risk_usd,
            reason="approved_downsized" if downsized else "approved",
            daily_pct_used_after=daily_pct_after,
            requests_remaining=requests_remaining,
            checks=checks,
        )

    # ================================================================== manage
    def evaluate_manage(
        self,
        action: ManageAction,
        account: AccountState,
        day: DayState,
        now_utc: datetime,
    ) -> RiskDecision:
        """Risk-reducing actions (close/partial/move-SL-toward-BE) are always allowed,
        even under the kill-switch; only RISK-INCREASING actions are gated (spec 02 §3)."""
        requests_remaining = max(0, self.cfg.request_hard_cap - day.requests_used_today)
        env = compute_envelope(day.balance_0000, day.initial, account.equity)

        if not action.risk_increasing:
            # Always permit; closes are allowed even past the hard request cap.
            return RiskDecision(
                decision=Decision.APPROVE, lots=0.0, risk_usd=0.0,
                reason="risk_reducing_allowed",
                daily_pct_used_after=env.daily_pct_used,
                requests_remaining=requests_remaining,
                checks={"risk_reducing": True},
            )

        # Risk-increasing manage is gated like an entry on the kill-switch + freshness.
        if not account.is_fresh:
            return self._veto("stale_account", day, account,
                              {"no_stale_account": False}, requests_remaining, env)
        ks = self.effective_killswitch(day, account)
        if ks in (KillSwitchState.HALTED, KillSwitchState.FLATTEN):
            return self._veto("killswitch_blocks_risk_increase", day, account,
                              {"killswitch_ok": False}, requests_remaining, env)
        if day.requests_used_today >= self.cfg.request_soft_cap:
            return self._veto("request_budget_low", day, account,
                              {"request_budget_ok": False}, requests_remaining, env)
        return RiskDecision(
            decision=Decision.APPROVE, lots=0.0, risk_usd=0.0,
            reason="risk_increase_allowed",
            daily_pct_used_after=env.daily_pct_used,
            requests_remaining=requests_remaining,
            checks={"risk_increasing_gated": True},
        )

    # =============================================================== kill-switch
    def effective_killswitch(self, day: DayState, account: AccountState) -> KillSwitchState:
        """Current kill-switch state, honouring the day's latch (spec 02 §5).

        FLATTEN and HALTED are latched: this method never *clears* them (only the 00:00
        reset clears HALTED; only a human clears FLATTEN). It may only escalate.
        """
        env = compute_envelope(day.balance_0000, day.initial, account.equity)
        derived = self._derive_killswitch(env.daily_pct_used, account)
        order = {KillSwitchState.ARMED: 0, KillSwitchState.REDUCE: 1,
                 KillSwitchState.HALTED: 2, KillSwitchState.FLATTEN: 3}
        # Escalate to the more severe of (latched, derived); never de-escalate here.
        return max(day.killswitch, derived, key=lambda s: order[s])

    def _derive_killswitch(self, daily_pct_used: float, account: AccountState) -> KillSwitchState:
        ks = self.cfg.killswitch
        # Hard danger also flattens on a stale read (spec 02 §5).
        if daily_pct_used >= ks.flatten_pct or not account.is_fresh:
            return KillSwitchState.FLATTEN
        if daily_pct_used >= ks.halt_pct:
            return KillSwitchState.HALTED
        if daily_pct_used >= ks.warn_pct:
            return KillSwitchState.REDUCE
        return KillSwitchState.ARMED

    # ================================================================== sizing
    def _effective_risk_fraction(
        self, signal: Signal, day: DayState, account: AccountState,
        env: Envelope, ks: KillSwitchState,
    ) -> float:
        cfg = self.cfg
        f = cfg.base_risk_fraction
        if signal.context_bias is ContextBias.CAUTIOUS:
            f *= cfg.cautious_size_mult
        if signal.context_bias is ContextBias.STAND_DOWN:
            return 0.0
        if ks is KillSwitchState.REDUCE:
            f *= cfg.reduced_size_mult
        # Overall taper: linearly toward 0 as equity approaches the overall floor.
        taper_start_equity = day.initial - cfg.overall_taper_start * day.initial
        if account.equity < taper_start_equity:
            span = taper_start_equity - env.overall_floor_equity
            if span <= 0:
                return 0.0
            frac = (account.equity - env.overall_floor_equity) / span
            f *= max(0.0, min(1.0, frac))
        return f

    def _lots_for_fraction(
        self, f: float, equity: float, denom: float, sm: SymbolMeta,
    ) -> float:
        if f <= 0 or denom <= 0:
            return 0.0
        lots_raw = (f * equity) / denom
        # Round DOWN to the lot step, then clamp to broker min/max.
        stepped = math.floor(lots_raw / sm.lot_step) * sm.lot_step
        if stepped < sm.min_lot:
            return 0.0  # cannot size at/above the broker minimum -> unsafe
        return min(stepped, sm.max_lot)

    # =========================================================== forbidden checks
    def _run_checks(
        self, signal: Signal, account: AccountState, day: DayState, env: Envelope,
        sm: SymbolMeta, risk_usd: float, sl_pips: float, requests_remaining: int,
    ) -> dict[str, bool]:
        cfg = self.cfg
        projected_loss = risk_usd + day.open_risk_usd
        max_conc = cfg.max_concurrent_risk_usd_pct * day.initial

        # (5) consistent sizing vs trailing median.
        if day.recent_risk_usds:
            med = median(day.recent_risk_usds)
            size_ok = med <= 0 or abs(risk_usd - med) / med <= cfg.size_consistency_band
        else:
            size_ok = True

        # (1) stale-tick / feed-error cross-check.
        if signal.reference_price is not None and sm.pip_size > 0:
            divergence_pips = abs(signal.signal_price - signal.reference_price) / sm.pip_size
            feed_ok = divergence_pips <= cfg.stale_quote_tolerance_pips
        else:
            feed_ok = True

        checks = {
            "no_feed_error": feed_ok,                                              # 1
            "request_budget_ok": day.requests_used_today < cfg.request_soft_cap,   # 2
            "news_blackout_clear": not signal.news_blackout_active,                # 3
            "gap_rule_clear": not signal.near_session_gap,                         # 4
            "consistent_sizing": size_ok,                                          # 5
            "no_hedging": not signal.opposing_position_open,                       # 6
            "no_martingale": not signal.adds_to_losing_same_dir,                   # 7
            "no_grid": signal.pending_orders_count < cfg.max_concurrent_pendings,  # 8
            "max_concurrent_risk": (day.open_risk_usd + risk_usd) <= max_conc,     # 9
            "max_trades_per_day": day.trades_opened_today < cfg.max_trades_per_day,  # 10
            "min_stop_compliance": sl_pips >= sm.stops_level_pips,                 # 11
            "no_stale_account": account.is_fresh,                                  # 12
            # (13) the non-negotiable floor protection (strict inequalities).
            "floor_protection": self._floor_ok(account.equity, projected_loss, env),
            "daily_budget_allowance":
                (env.daily_loss_used_usd + projected_loss) <= self._allowance(env),
        }
        return checks

    def _floor_ok(self, equity: float, projected_loss: float, env: Envelope) -> bool:
        after = equity - projected_loss
        return (after > env.daily_floor_equity) and (after > env.overall_floor_equity)

    def _allowance(self, env: Envelope) -> float:
        # Don't let cumulative committed loss cross the halt threshold.
        return self.cfg.killswitch.halt_pct * env.daily_budget_usd

    # ===================================================================== util
    _REASONS = {
        "no_feed_error": "feed_error_or_stale_tick",
        "request_budget_ok": "request_budget_low",
        "news_blackout_clear": "news_blackout",
        "gap_rule_clear": "gap_rule",
        "consistent_sizing": "inconsistent_position_size",
        "no_hedging": "hedging_forbidden",
        "no_martingale": "martingale_forbidden",
        "no_grid": "grid_forbidden",
        "max_concurrent_risk": "max_concurrent_risk_exceeded",
        "max_trades_per_day": "max_trades_per_day_reached",
        "min_stop_compliance": "sl_below_broker_stops_level",
        "no_stale_account": "stale_account",
        "floor_protection": "would_breach_floor",
        "daily_budget_allowance": "killswitch_allowance_exceeded",
    }

    def _reason_for(self, check_name: str) -> str:
        return self._REASONS.get(check_name, check_name)

    def _veto(
        self, reason: str, day: DayState, account: AccountState,
        checks: dict[str, bool], requests_remaining: int,
        env: Envelope | None = None,
    ) -> RiskDecision:
        pct = env.daily_pct_used if env is not None else 0.0
        return RiskDecision(
            decision=Decision.VETO, lots=0.0, risk_usd=0.0, reason=reason,
            daily_pct_used_after=pct, requests_remaining=requests_remaining,
            checks=checks,
        )


def apply_daily_reset(
    prev: DayState, balance_0000: float, reset_ts: datetime,
) -> DayState:
    """Apply the 00:00 CE(S)T reset to day-state (spec 02 §2/§5).

    Re-captures ``balance_0000`` from *balance*, zeroes the daily counters, and clears
    a HALTED latch back to ARMED — but a FLATTEN latch is preserved (only a human clears
    it; the engine never auto-resumes after a risk-driven flatten, R7).
    """
    new_ks = (
        KillSwitchState.FLATTEN
        if prev.killswitch is KillSwitchState.FLATTEN
        else KillSwitchState.ARMED
    )
    return DayState(
        balance_0000=balance_0000,
        initial=prev.initial,
        requests_used_today=0,
        killswitch=new_ks,
        open_risk_usd=prev.open_risk_usd,  # open positions carry across the reset
        trades_opened_today=0,
        reset_ts_utc=reset_ts,
        recent_risk_usds=prev.recent_risk_usds,
    )
