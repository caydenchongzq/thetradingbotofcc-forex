"""Live engine runner (spec 07 §2/§8) — the supervised process NSSM/WinSW keeps alive.

Wires the deterministic spine together for live trading:
  connect MT5 -> reconcile vs MT5 (source of truth) BEFORE acting -> per-loop:
  poll the kill-switch + health, on each closed bar load the ACTIVE config (only at a
  session boundary), run strategy -> Risk Governor -> Execution, journal everything,
  ping the heartbeat. Any stale/degraded state resolves to hold/flatten — never a guess.

The bar-driven decision is the same code the backtester drives, so live == backtest.
"""

from __future__ import annotations

import logging
import logging.handlers
import time
from dataclasses import replace
from datetime import date, datetime, timezone

from src.common.config import AppConfig, load_config
from src.common.timeutil import ensure_utc, ftmo_day_start, is_new_ftmo_day, utc_iso
from src.engine import build_strategy
from src.engine.decide import decide_entry, decide_manage
from src.ops import (Severity, append_alert_file, backoff_delay, engage_killswitch,
                     format_alert, killswitch_engaged, ping_healthcheck,
                     resolve_strategy_config, send_discord, send_telegram)
from src.risk.envelope import compute_envelope
from src.risk.governor import RiskGovernor, apply_daily_reset
from src.risk.types import ContextBias, DayState, KillSwitchState

log = logging.getLogger("ftmo.engine")


def configure_logging(state_dir) -> None:
    """Console + rotating file logging so a forward test is observable."""
    from pathlib import Path
    logs = Path(state_dir) / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger("ftmo")
    if root.handlers:
        return
    root.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s",
                            datefmt="%Y-%m-%d %H:%M:%S")
    con = logging.StreamHandler()
    con.setFormatter(fmt)
    fileh = logging.handlers.RotatingFileHandler(
        logs / "engine.log", maxBytes=5_000_000, backupCount=10, encoding="utf-8")
    fileh.setFormatter(fmt)
    root.addHandler(con)
    root.addHandler(fileh)


def session_date(now_utc: datetime, tz) -> date:
    """The local session date used to decide config-reload boundaries."""
    return ensure_utc(now_utc).astimezone(tz).date()


class LiveEngine:
    def __init__(self, app_cfg: AppConfig):
        self.cfg = app_cfg
        self.alerts = app_cfg.alerts            # resolved from env/.env by the loader
        self.governor = RiskGovernor(app_cfg.risk)
        self._broker = None
        self._exec = None
        self._strategy = None
        self._active_version = None
        self._last_session_date = None
        self._last_bar_ts = None
        self._tg_warned = False

    # ---- lazy MT5 wiring (Windows host only) ----
    def _connect(self):
        from src.execution.adapter import MT5Execution
        from src.execution.broker import RealMT5Broker
        from src.journal import Journal
        broker = RealMT5Broker()
        journal = Journal(self.cfg.state_dir)
        self._exec = MT5Execution(broker, journal, self.cfg.mt5, self.cfg.execution,
                                  fund_request=lambda n, rr: True)
        self._broker = broker
        self._exec.connect()
        self._reload_active_config(force=True)

    def _reload_active_config(self, *, force: bool = False) -> None:
        strat_cfg, version = resolve_strategy_config(
            self.cfg.state_dir, self.cfg.raw.get("strategy", {}), self.cfg.config_version)
        if force or version != self._active_version:
            # Live always builds from the promoted HEAD config -> only ever runs the
            # promoted strategy (dev strategies are never in the store). See registry.py.
            self._strategy = build_strategy(strat_cfg)
            self._active_version = version
            self._alert(Severity.INFO, "config loaded",
                        f"strategy {strat_cfg.get('name', 'SessionBreakoutER')} config v{version}")

    def _alert(self, severity: Severity, event: str, detail: str = "") -> None:
        msg = format_alert(severity, event, detail, env=self.cfg.env,
                           symbol=self.cfg.execution.symbol)
        log.log(logging.WARNING if severity is not Severity.INFO else logging.INFO,
                "ALERT %s: %s %s", severity.value, event, detail)
        try:   # durable file sink (rides R2 sync; works even if all networks are blocked)
            append_alert_file(self.cfg.state_dir, severity, event, detail,
                              env=self.cfg.env, symbol=self.cfg.execution.symbol)
        except Exception:
            pass
        sent = False
        if self.alerts.telegram_configured:
            sent = send_telegram(self.alerts.telegram_bot_token,
                                 self.alerts.telegram_chat_id, msg) or sent
        if self.alerts.discord_webhook:
            sent = send_discord(self.alerts.discord_webhook, msg) or sent
        if self.alerts.any_channel and not sent and not self._tg_warned:
            log.warning("Alert send FAILED on all channels (network/credentials?) — alerts "
                        "are console/log only until this is fixed")
            self._tg_warned = True

    # ---- the supervised loop ----
    def run(self, *, poll_seconds: int = 5, max_iterations: int | None = None) -> None:
        configure_logging(self.cfg.state_dir)
        log.info("starting engine: env=%s symbol=%s magic=%s state=%s", self.cfg.env,
                 self.cfg.execution.symbol, self.cfg.execution.magic, self.cfg.state_dir)
        if not self.alerts.any_channel:
            log.warning("No push alert channel configured (Telegram or Discord) — running "
                        "with console/log alerts only")
        if not self.alerts.healthchecks_url:
            log.warning("Healthchecks URL not set (TBOT_HEALTHCHECKS_URL) — no dead-man switch")
        self._connect()
        acct = self._exec.account_state()
        log.info("connected: balance=%.2f equity=%.2f %s | strategy v%s session %s-%s %s",
                 acct.balance, acct.equity, acct.currency, self._active_version,
                 self._strategy.win_start, self._strategy.win_end, self._strategy.tz.key)
        report = self._exec.reconcile_on_startup()
        log.info("reconciled: matched=%s adopted=%s orphaned=%s flatten_required=%s",
                 report.matched, report.adopted, report.orphaned_intents,
                 report.flatten_required)
        if report.flatten_required:
            self._alert(Severity.CRITICAL, "reconciliation ambiguity",
                        "holding; human review required")
            return  # never start trading into an ambiguous state (spec 07 §8)
        self._alert(Severity.INFO, "engine up", "MT5 connected, reconciled")

        disconnects = 0
        i = 0
        heartbeat_every = max(1, 60 // poll_seconds)
        while max_iterations is None or i < max_iterations:
            i += 1
            try:
                if killswitch_engaged(self.cfg.state_dir):
                    self._flatten_and_halt("kill-switch sentinel present")
                    return
                health = self._exec.health()
                if not health.ok:
                    disconnects += 1
                    self._alert(Severity.WARN, "degraded health",
                                f"data_fresh={health.data_fresh} reconnecting")
                    time.sleep(backoff_delay(disconnects))
                    continue
                disconnects = 0
                self._on_tick(ensure_utc(datetime.now(tz=timezone.utc)))
                ping_healthcheck(self.alerts.healthchecks_url)  # alive+connected+fresh
                if i % heartbeat_every == 0:
                    log.info("alive: trade_allowed=%s data_fresh=%s last_bar=%s",
                             health.trade_allowed, health.data_fresh,
                             self._last_bar_ts.isoformat() if self._last_bar_ts else "—")
            except Exception as exc:  # never let the loop die silently
                log.exception("loop exception")
                self._alert(Severity.CRITICAL, "loop exception", str(exc))
            time.sleep(poll_seconds)

    def _on_tick(self, now: datetime) -> None:
        # Reload the active config only at a session boundary (spec 06 §6 / 07).
        sd = session_date(now, self._strategy.tz)
        if sd != self._last_session_date:
            self._reload_active_config()
            self._last_session_date = sd

        warmup = self._strategy.warmup_bars()
        bars = self._exec.recent_closed_bars(count=warmup + 400,
                                             timeframe_min=self._strategy.tf_min)
        if not bars:
            return
        last_ts = ensure_utc(bars[-1].ts_open_utc)
        if self._last_bar_ts is not None and last_ts <= self._last_bar_ts:
            return                      # no NEW closed bar yet -> act at most once per bar
        self._last_bar_ts = last_ts

        account = self._exec.account_state()
        if not account.is_fresh:        # stale/degraded -> hold, never guess (spec 02/07)
            self._alert(Severity.WARN, "stale account read", "holding this bar")
            return
        day = self._load_day_state(account, now)
        # Persist any kill-switch escalation so HALT/FLATTEN LATCH for the day (spec 02 §5):
        # without this, an intraday loss that recovers could wrongly un-halt next bar.
        ks = self.governor.effective_killswitch(day, account)
        if ks is not day.killswitch:
            day = replace(day, killswitch=ks)
            self._exec.journal.put_day_state(day)
        env = compute_envelope(day.balance_0000, day.initial, account.equity)
        log.info("new bar %s | equity=%.2f day_pct_used=%.1f%% killswitch=%s",
                 last_ts.isoformat(), account.equity, 100 * env.daily_pct_used, ks.value)

        # Risk-driven FLATTEN: close everything, latch the sentinel, stop (human clears).
        if ks is KillSwitchState.FLATTEN:
            self._flatten_and_halt("governor FLATTEN — daily-loss danger or stale data")
            engage_killswitch(self.cfg.state_dir, "governor_flatten")
            return

        open_positions = self._exec.open_positions()      # filtered by our magic
        if open_positions:
            self._manage(open_positions[0], bars, now, account, day)
            return

        client_id = f"{self.cfg.execution.symbol}-{last_ts.strftime('%Y%m%dT%H%M')}"
        d = decide_entry(self._strategy, self.governor, bars, account, day,
                         self._exec.symbol_meta(), now, ContextBias.NORMAL, None,
                         client_id=client_id, magic=self.cfg.execution.magic,
                         pending_orders_count=len(self._exec.pending_orders()))
        log.info("decision: %s (%s)", d.action, d.reason)
        if d.action == "enter" and d.intent is not None:
            res = self._exec.place(d.intent)
            self._journal_entry(d, res)
            # Persist day-state counters so the Governor sees today's activity next bar.
            day = replace(day, requests_used_today=day.requests_used_today + 1,
                          trades_opened_today=day.trades_opened_today + 1,
                          open_risk_usd=day.open_risk_usd + d.risk_decision.risk_usd)
            self._exec.journal.put_day_state(day)
            self._alert(Severity.INFO, "entry placed",
                        f"{d.intent.side} {d.intent.volume_lots} @ {d.intent.price} "
                        f"(risk ${d.risk_decision.risk_usd:.0f})")
        elif d.action == "vetoed":
            self._exec.journal.append({
                "record_type": "reject", "schema_version": 3,
                "config_version": self._active_version, "ts_utc": utc_iso(now),
                "instrument": self.cfg.execution.symbol, "stage": "risk",
                "reason": d.reason,
                "risk_checks": d.risk_decision.checks if d.risk_decision else None})

    def _manage(self, pos, bars, now, account, day) -> None:
        class _View:
            direction = "long" if pos.type == 0 else "short"
            entry_price = pos.price_open
            sl_price = pos.sl
            tp_price = pos.tp
        d = decide_manage(self._strategy, self.governor, _View(), bars, now, account, day)
        if d.action == "close":
            self._exec.close(pos.ticket)
            day = replace(day, requests_used_today=day.requests_used_today + 1,
                          open_risk_usd=0.0)   # single-position model -> flat after close
            self._exec.journal.put_day_state(day)
            self._alert(Severity.INFO, "position closed", f"ticket {pos.ticket}")
        elif d.action == "modify_sl" and d.new_sl is not None:
            self._exec.modify_sl_tp(pos.ticket, d.new_sl, (pos.tp,))
            day = replace(day, requests_used_today=day.requests_used_today + 1)
            self._exec.journal.put_day_state(day)
            log.info("moved SL on ticket %s -> %s", pos.ticket, d.new_sl)

    def _load_day_state(self, account, now) -> DayState:
        day = self._exec.journal.get_day_state()
        if day is None:
            # Cold boot: capture balance_0000 from current balance, size conservatively.
            day = DayState(balance_0000=account.balance, initial=self.cfg.account.initial,
                           reset_ts_utc=ftmo_day_start(now))
            self._exec.journal.put_day_state(day)
        elif is_new_ftmo_day(day.reset_ts_utc, now):
            day = apply_daily_reset(day, account.balance, ftmo_day_start(now))
            self._exec.journal.put_day_state(day)
        return day

    def _journal_entry(self, decision, exec_result) -> None:
        sig = decision.signal
        self._exec.journal.append({
            "record_type": "trade", "trade_id": decision.intent.client_id,
            "schema_version": 3, "config_version": self._active_version,
            "ts_utc": utc_iso(sig.ts_decision_utc),
            "instrument": self.cfg.execution.symbol,
            "signal": {"session": sig.session, "direction": sig.direction.value,
                       "breakout_level": sig.breakout_level, "er": sig.regime.er,
                       "atr_pips": sig.regime.atr_pips,
                       "regime_gate_passed": sig.regime.regime_gate_passed,
                       "entry_reason": sig.entry_reason},
            "regime": {"er": sig.regime.er, "atr_pips": sig.regime.atr_pips,
                       "vol_state": sig.regime.vol_state.value},
            "sizing": {"lots": decision.intent.volume_lots,
                       "risk_usd": decision.risk_decision.risk_usd,
                       "sl_distance_pips": sig.exit_plan.initial_sl_pips},
            "fills": {"entry_req_price": decision.intent.price,
                      "entry_fill_price": exec_result.fill_price,
                      "entry_slippage_pips": exec_result.slippage_pips},
        })

    # ---- one-shot / diagnostic modes (forward-test helpers) ----
    def run_once(self) -> int:
        """Connect, reconcile, run exactly ONE tick, then exit. For on-demand checks."""
        configure_logging(self.cfg.state_dir)
        self._connect()
        rep = self._exec.reconcile_on_startup()
        if rep.flatten_required:
            log.error("reconciliation ambiguity — not trading"); return 1
        self._on_tick(ensure_utc(datetime.now(tz=timezone.utc)))
        return 0

    def diagnose(self) -> int:
        """Print WHY the engine would/wouldn't trade right now: session, freshness, the
        live regime read (ER/ATR/vol_state), and what evaluate() returns. Places nothing."""
        configure_logging(self.cfg.state_dir)
        self._connect()
        now = ensure_utc(datetime.now(tz=timezone.utc))
        lon = now.astimezone(self._strategy.tz)
        in_session = self._strategy.win_start <= lon.time() < self._strategy.win_end
        bars = self._exec.recent_closed_bars(count=self._strategy.warmup_bars() + 400,
                                             timeframe_min=self._strategy.tf_min)
        acct = self._exec.account_state()
        log.info("=== DIAGNOSE ===")
        log.info("now: %s UTC = %s %s | in_session=%s (window %s-%s)",
                 now.strftime("%H:%M"), lon.strftime("%H:%M"), self._strategy.tz.key,
                 in_session, self._strategy.win_start, self._strategy.win_end)
        log.info("account: balance=%.2f equity=%.2f fresh=%s | bars_loaded=%d last_bar=%s",
                 acct.balance, acct.equity, acct.is_fresh, len(bars),
                 bars[-1].ts_open_utc.isoformat() if bars else "none")
        if bars:
            r = self._strategy._regime(bars)
            log.info("regime: ER=%.3f (thr %.2f) ATR=%.1f pips pct=%.2f vol_state=%s "
                     "-> gate_passed=%s", r.er, r.er_threshold, r.atr_pips,
                     r.atr_percentile, r.vol_state.value, r.regime_gate_passed)
            res = self._strategy.evaluate(bars, now, ContextBias.NORMAL, None)
            from src.engine.types import Signal as _Sig
            if isinstance(res, _Sig):
                log.info("evaluate -> SIGNAL %s breakout@%s SL=%s",
                         res.direction.value, res.breakout_level,
                         res.exit_plan.initial_sl_price)
            else:
                log.info("evaluate -> NoSignal(%s)", res.reason)
        log.info("(diagnose only — no order placed)")
        return 0

    def _flatten_and_halt(self, reason: str) -> None:
        for pos in self._exec.open_positions():
            self._exec.close(pos.ticket)
        self._alert(Severity.CRITICAL, "FLATTEN + halt", reason)
        # Latched: never auto-resumes after a risk-driven kill (mirrors Governor FLATTEN).


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="FTMO EURUSD live engine")
    ap.add_argument("--once", action="store_true", help="run one tick and exit")
    ap.add_argument("--diagnose", action="store_true",
                    help="print session/regime/evaluate diagnostics and exit (no order)")
    args = ap.parse_args(argv)
    eng = LiveEngine(load_config())
    if args.diagnose:
        return eng.diagnose()
    if args.once:
        return eng.run_once()
    eng.run()
    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(main(sys.argv[1:]))
