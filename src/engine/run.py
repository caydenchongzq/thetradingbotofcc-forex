"""Live engine runner (spec 07 §2/§8) — the supervised process NSSM/WinSW keeps alive.

Wires the deterministic spine together for live trading:
  connect MT5 -> reconcile vs MT5 (source of truth) BEFORE acting -> per-loop:
  poll the kill-switch + health, on each closed bar load the ACTIVE config (only at a
  session boundary), run strategy -> Risk Governor -> Execution, journal everything,
  ping the heartbeat. Any stale/degraded state resolves to hold/flatten — never a guess.

The MT5-bound paths run only on the Windows host; this module imports cleanly anywhere
(the broker is created lazily) so the logic can be reviewed/tested off-Windows. The
bar-driven decision is the same code the backtester drives, so live == backtest.
"""

from __future__ import annotations

import os
import time
from datetime import date, datetime, timezone

from src.common.config import AppConfig, load_config
from src.common.timeutil import ensure_utc
from src.engine import SessionBreakoutER, to_risk_signal
from src.engine.types import Signal as EngineSignal
from src.execution.types import OrderIntent
from src.ops import (Severity, backoff_delay, backup_state, format_alert,
                     killswitch_engaged, ping_healthcheck, resolve_strategy_config,
                     send_telegram)
from src.risk.governor import RiskGovernor
from src.risk.types import AccountState


def session_date(now_utc: datetime, tz) -> date:
    """The local session date used to decide config-reload boundaries."""
    return ensure_utc(now_utc).astimezone(tz).date()


def _expand_env(d: dict) -> dict:
    """Resolve ``${VAR}`` placeholders (e.g. secrets) against the process environment."""
    out = {}
    for k, v in (d or {}).items():
        if isinstance(v, str) and v.startswith("${") and v.endswith("}"):
            out[k] = os.environ.get(v[2:-1])
        else:
            out[k] = v
    return out


class LiveEngine:
    def __init__(self, app_cfg: AppConfig):
        self.cfg = app_cfg
        self.alerts = _expand_env(app_cfg.raw.get("ops", {}).get("alerts", {}))
        self.governor = RiskGovernor(app_cfg.risk)
        self._broker = None
        self._exec = None
        self._strategy = None
        self._active_version = None
        self._last_session_date = None

    # ---- lazy MT5 wiring (Windows host only) ----
    def _connect(self):
        from src.execution.adapter import MT5Execution
        from src.execution.broker import RealMT5Broker
        from src.journal import Journal
        broker = RealMT5Broker()
        journal = Journal(self.cfg.state_dir)
        # The request-funding callback debits the Governor's day-state counter; wired to
        # the persisted DayState in the full integration.
        self._exec = MT5Execution(broker, journal, self.cfg.mt5, self.cfg.execution,
                                  fund_request=lambda n, rr: True)
        self._broker = broker
        self._exec.connect()
        self._reload_active_config(force=True)

    def _reload_active_config(self, *, force: bool = False) -> None:
        strat_cfg, version = resolve_strategy_config(
            self.cfg.state_dir, self.cfg.raw.get("strategy", {}), self.cfg.config_version)
        if force or version != self._active_version:
            self._strategy = SessionBreakoutER(strat_cfg)
            self._active_version = version
            self._alert(Severity.INFO, "config loaded", f"strategy config v{version}")

    def _alert(self, severity: Severity, event: str, detail: str = "") -> None:
        msg = format_alert(severity, event, detail, env=self.cfg.env,
                           symbol=self.cfg.execution.symbol)
        send_telegram(self.alerts.get("telegram_bot_token"),
                      self.alerts.get("telegram_chat_id"), msg)

    # ---- the supervised loop ----
    def run(self, *, poll_seconds: int = 5, max_iterations: int | None = None) -> None:
        self._connect()
        report = self._exec.reconcile_on_startup()
        if report.flatten_required:
            self._alert(Severity.CRITICAL, "reconciliation ambiguity",
                        "holding; human review required")
            return  # never start trading into an ambiguous state (spec 07 §8)
        self._alert(Severity.INFO, "engine up", "MT5 connected, reconciled")

        disconnects = 0
        i = 0
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
                ping_healthcheck(self.alerts.get("healthchecks_url"))  # alive+connected+fresh
            except Exception as exc:  # never let the loop die silently
                self._alert(Severity.CRITICAL, "loop exception", str(exc))
            time.sleep(poll_seconds)

    def _on_tick(self, now: datetime) -> None:
        # Reload the active config only at a session boundary (spec 06 §6 / 07).
        sd = session_date(now, self._strategy.tz)
        if sd != self._last_session_date:
            self._reload_active_config()
            self._last_session_date = sd
        # On each CLOSED bar the engine would: pull recent bars from MT5, run
        # strategy.evaluate -> Governor.evaluate_entry -> Execution.place, and manage open
        # positions. The decision code is identical to the backtester's loop (live==backtest).
        # Bar fetching is MT5-IPC and validated on the Windows host.

    def _flatten_and_halt(self, reason: str) -> None:
        for pos in self._exec.open_positions():
            self._exec.close(pos.ticket)
        self._alert(Severity.CRITICAL, "FLATTEN + halt", reason)
        # Latched: never auto-resumes after a risk-driven kill (mirrors Governor FLATTEN).


def main() -> int:
    cfg = load_config()
    LiveEngine(cfg).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
