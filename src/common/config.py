"""Env-driven config loader (spec 00 §6, spec 07).

One artifact, many hosts: behaviour is driven by environment variables plus a
versioned YAML file. Secrets (MT5 credentials) come from the environment / a local
``.env`` file that is never committed. Loading is pure apart from reading the
filesystem/environment, so tests can inject overrides directly.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class KillSwitchConfig:
    warn_pct: float = 0.40
    halt_pct: float = 0.60
    flatten_pct: float = 0.85


@dataclass(frozen=True)
class RiskConfig:
    base_risk_fraction: float = 0.0035
    slippage_spread_buffer: float = 0.20
    cautious_size_mult: float = 0.5
    reduced_size_mult: float = 0.5
    killswitch: KillSwitchConfig = field(default_factory=KillSwitchConfig)
    overall_taper_start: float = 0.06
    max_concurrent_risk_usd_pct: float = 0.010
    max_trades_per_day: int = 6
    max_concurrent_pendings: int = 2
    size_consistency_band: float = 0.50
    request_soft_cap: int = 1600
    request_hard_cap: int = 1900
    stale_quote_tolerance_pips: float = 2.0
    news_blackout_min: int = 2

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "RiskConfig":
        ks = d.get("killswitch", {}) or {}
        return RiskConfig(
            base_risk_fraction=float(d.get("base_risk_fraction", 0.0035)),
            slippage_spread_buffer=float(d.get("slippage_spread_buffer", 0.20)),
            cautious_size_mult=float(d.get("cautious_size_mult", 0.5)),
            reduced_size_mult=float(d.get("reduced_size_mult", 0.5)),
            killswitch=KillSwitchConfig(
                warn_pct=float(ks.get("warn_pct", 0.40)),
                halt_pct=float(ks.get("halt_pct", 0.60)),
                flatten_pct=float(ks.get("flatten_pct", 0.85)),
            ),
            overall_taper_start=float(d.get("overall_taper_start", 0.06)),
            max_concurrent_risk_usd_pct=float(d.get("max_concurrent_risk_usd_pct", 0.010)),
            max_trades_per_day=int(d.get("max_trades_per_day", 6)),
            max_concurrent_pendings=int(d.get("max_concurrent_pendings", 2)),
            size_consistency_band=float(d.get("size_consistency_band", 0.50)),
            request_soft_cap=int(d.get("request_soft_cap", 1600)),
            request_hard_cap=int(d.get("request_hard_cap", 1900)),
            stale_quote_tolerance_pips=float(d.get("stale_quote_tolerance_pips", 2.0)),
            news_blackout_min=int(d.get("news_blackout_min", 2)),
        )


@dataclass(frozen=True)
class AccountConfig:
    initial: float = 100_000.0
    currency: str = "USD"


@dataclass(frozen=True)
class MT5Config:
    """Connection settings for ONE MT5 terminal (you may have several installed).

    ``terminal_path`` is the absolute path to the specific broker's ``terminal64.exe``;
    it is how we guarantee the Python bridge attaches to the intended client and not a
    different broker's terminal. Credentials are secrets — keep them in ``.env`` only.
    """

    login: int | None = None
    password: str | None = None
    server: str | None = None
    terminal_path: str | None = None

    @property
    def configured(self) -> bool:
        return bool(self.login and self.password and self.server)


@dataclass(frozen=True)
class ExecutionConfig:
    magic: int = 770042          # tags OUR orders/positions in the terminal
    symbol: str = "EURUSD"
    deviation_points: int = 20   # max slippage tolerance on market orders, in points


@dataclass(frozen=True)
class AlertsConfig:
    """Alert secrets, resolved from the environment / .env (spec 07 §5/§6)."""
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None
    healthchecks_url: str | None = None

    @property
    def telegram_configured(self) -> bool:
        return bool(self.telegram_bot_token and self.telegram_chat_id)


@dataclass(frozen=True)
class AppConfig:
    env: str
    state_dir: Path
    config_version: int
    schema_version: int
    account: AccountConfig
    risk: RiskConfig
    mt5: MT5Config
    execution: ExecutionConfig
    alerts: AlertsConfig
    strategy: dict[str, Any]
    raw: dict[str, Any]


def _read_yaml(path: Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Config file {path} did not parse to a mapping")
    return data


def read_env_file(path: str | os.PathLike[str]) -> dict[str, str]:
    """Parse a simple ``KEY=value`` ``.env`` file.

    - Blank lines and whole-line ``#`` comments are ignored.
    - A value may be quoted (``"..."`` or ``\'...\'``); quotes are stripped and any
      ``#`` inside the quotes is preserved (passwords often contain ``#``).
    - For an UNQUOTED value, an inline comment introduced by whitespace + ``#`` is
      stripped (so ``KEY=100000   # note`` -> ``100000``), but ``KEY=pa#ss`` (no
      preceding whitespace) keeps the ``#``.

    Returns ``{}`` if the file is absent.
    """
    p = Path(path)
    if not p.exists():
        return {}
    out: dict[str, str] = {}
    for raw_line in p.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip()
        if val[:1] in ('"', "'"):
            quote = val[0]
            end = val.find(quote, 1)
            val = val[1:end] if end != -1 else val[1:]
        else:
            for i in range(1, len(val)):
                if val[i] == "#" and val[i - 1] in " \t":
                    val = val[:i]
                    break
            val = val.strip()
        if key:
            out[key] = val
    return out


def _int_or_none(v: str | None) -> int | None:
    if v is None or v == "":
        return None
    return int(v)


def load_config(
    *,
    env: dict[str, str] | None = None,
    config_file: str | os.PathLike[str] | None = None,
    env_file: str | os.PathLike[str] | None = ".env",
) -> AppConfig:
    """Load config from a YAML file, overlaying env-var overrides.

    When ``env`` is None (a real run) the process environment is used, with any local
    ``.env`` file filling values the environment does not already set. When ``env`` is
    injected (tests) it is used verbatim and no ``.env`` file is read.
    """
    if env is None:
        file_env = read_env_file(env_file) if env_file else {}
        env = {**file_env, **os.environ}  # real environment wins over the .env file
    else:
        env = dict(env)

    cfg_path = Path(
        config_file
        or env.get("TBOT_CONFIG_FILE")
        or "config/default.yaml"
    )
    raw = _read_yaml(cfg_path)

    account_raw = raw.get("account", {}) or {}
    account = AccountConfig(
        initial=float(env.get("TBOT_ACCOUNT_INITIAL", account_raw.get("initial", 100_000))),
        currency=env.get("TBOT_ACCOUNT_CURRENCY", account_raw.get("currency", "USD")),
    )

    state_dir = Path(env.get("TBOT_STATE_DIR", raw.get("state_dir", "./state")))

    mt5 = MT5Config(
        login=_int_or_none(env.get("TBOT_MT5_LOGIN")),
        password=env.get("TBOT_MT5_PASSWORD") or None,
        server=env.get("TBOT_MT5_SERVER") or None,
        terminal_path=env.get("TBOT_MT5_TERMINAL_PATH") or None,
    )

    alerts = AlertsConfig(
        telegram_bot_token=env.get("TBOT_TELEGRAM_BOT_TOKEN") or None,
        telegram_chat_id=env.get("TBOT_TELEGRAM_CHAT_ID") or None,
        healthchecks_url=env.get("TBOT_HEALTHCHECKS_URL") or None,
    )

    exec_raw = raw.get("execution", {}) or {}
    strategy = raw.get("strategy", {}) or {}
    execution = ExecutionConfig(
        magic=int(env.get("TBOT_MAGIC", exec_raw.get("magic", 770042))),
        symbol=exec_raw.get("symbol", strategy.get("instrument", "EURUSD")),
        deviation_points=int(exec_raw.get("deviation_points", 20)),
    )

    return AppConfig(
        env=env.get("TBOT_ENV", "dev"),
        state_dir=state_dir,
        config_version=int(raw.get("config_version", 1)),
        schema_version=int(raw.get("schema_version", 3)),
        account=account,
        risk=RiskConfig.from_dict(raw.get("risk", {}) or {}),
        mt5=mt5,
        execution=execution,
        alerts=alerts,
        strategy=strategy,
        raw=raw,
    )
