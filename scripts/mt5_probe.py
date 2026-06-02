"""MT5 connection probe — run this FIRST, before any execution work.

It confirms the Python bridge attaches to the *intended* broker terminal (you have
several installed) and the *intended* account, then prints the broker's real symbol
specs for the configured symbol. Those specs (pip size, tick value, lot step, stops
level) are what the Risk Governor sizes against and what the execution adapter must
respect — they vary by broker, so we capture them from YOUR terminal rather than assume.

Usage (from the repo root, on the Windows host with MT5 installed):

    py -m pip install MetaTrader5
    copy .env.example .env        # then fill in TBOT_MT5_* values
    py scripts/mt5_probe.py

It only READS (account info, symbol info, a quote). It never places an order.
Paste the output back and I'll wire the adapter to your broker's exact specs.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make ``src`` importable when run as a plain script from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.common.config import load_config  # noqa: E402

try:
    import MetaTrader5 as mt5  # type: ignore
except Exception as exc:  # pragma: no cover
    print("ERROR: MetaTrader5 package not installed. Run:  py -m pip install MetaTrader5")
    print(f"  ({exc})")
    raise SystemExit(1)


def _pip_size(symbol_info) -> float:
    # FX convention: 1 pip = 10 points for 5/3-digit quotes, else 1 point.
    point = symbol_info.point
    return point * (10 if symbol_info.digits in (3, 5) else 1)


def main() -> int:
    cfg = load_config()
    m = cfg.mt5
    if not m.configured:
        print("ERROR: MT5 not configured. Fill TBOT_MT5_LOGIN / PASSWORD / SERVER in .env")
        return 1

    print(f"Attaching to terminal: {m.terminal_path or '(default / last used)'}")
    init_kwargs: dict = {}
    if m.terminal_path:
        init_kwargs["path"] = m.terminal_path
    if not mt5.initialize(**init_kwargs):
        print(f"ERROR: mt5.initialize failed: {mt5.last_error()}")
        return 1

    try:
        if not mt5.login(login=m.login, password=m.password, server=m.server):
            print(f"ERROR: mt5.login failed: {mt5.last_error()}")
            return 1

        term = mt5.terminal_info()
        acct = mt5.account_info()
        print("\n=== TERMINAL ===")
        if term is not None:
            print(f"  name={term.name!r}  company={term.company!r}")
            print(f"  path={term.path!r}")
            print(f"  connected={term.connected}  trade_allowed={term.trade_allowed}")

        print("\n=== ACCOUNT (confirm this is the DEMO you intend) ===")
        if acct is not None:
            print(f"  login={acct.login}  server={acct.server!r}  name={acct.name!r}")
            print(f"  currency={acct.currency}  leverage=1:{acct.leverage}")
            print(f"  balance={acct.balance}  equity={acct.equity}")
            print(f"  trade_mode={acct.trade_mode} (0=real,1=demo,2=contest)")

        symbol = cfg.execution.symbol
        if not mt5.symbol_select(symbol, True):
            print(f"\nWARNING: could not select {symbol!r}. "
                  f"Your broker may suffix it (e.g. EURUSD.r). "
                  f"Set execution.symbol in config/default.yaml accordingly.")
        si = mt5.symbol_info(symbol)
        tick = mt5.symbol_info_tick(symbol)
        print(f"\n=== SYMBOL: {symbol} ===")
        if si is not None:
            pip = _pip_size(si)
            spread_pips = (si.spread * si.point) / pip if pip else None
            print(f"  digits={si.digits}  point={si.point}  pip_size={pip}")
            print(f"  trade_tick_value={si.trade_tick_value}  trade_tick_size={si.trade_tick_size}")
            print(f"  -> pip_value_per_lot ~= {si.trade_tick_value * (pip / si.trade_tick_size):.4f} "
                  f"{acct.currency if acct else ''}")
            print(f"  volume_min={si.volume_min}  volume_max={si.volume_max}  volume_step={si.volume_step}")
            print(f"  trade_stops_level={si.trade_stops_level} points "
                  f"(~{(si.trade_stops_level * si.point)/pip:.1f} pips)")
            print(f"  contract_size={si.trade_contract_size}")
            print(f"  current_spread={si.spread} points (~{spread_pips:.2f} pips)" if spread_pips
                  else f"  current_spread={si.spread} points")
        if tick is not None:
            print(f"  quote: bid={tick.bid}  ask={tick.ask}")
        print("\nProbe OK — read-only, no orders placed.")
        return 0
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
