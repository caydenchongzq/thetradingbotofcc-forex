"""Ops & deployment (spec 07): watchdog, alerts, backups, kill-switch, active config."""
from .runtime_config import resolve_strategy_config
from .watchdog import backoff_delay, backoff_schedule, data_is_fresh
from .alerts import Severity, format_alert, ping_healthcheck, send_telegram
from .backup import backup_state, restore_state
from .killswitch import (clear_killswitch, engage_killswitch, killswitch_engaged,
                         killswitch_path)
__all__ = ["resolve_strategy_config", "backoff_delay", "backoff_schedule", "data_is_fresh",
           "Severity", "format_alert", "ping_healthcheck", "send_telegram",
           "backup_state", "restore_state", "clear_killswitch", "engage_killswitch",
           "killswitch_engaged", "killswitch_path"]
