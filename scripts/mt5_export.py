"""Export EURUSD M15 history from the FTMO terminal -> clean -> Parquet (spec 05 §3).

This is the data pipeline's ingestion step. MT5 is the FINAL validation feed ("the same
data source that will trade"), and pulling from your terminal needs no external account.

MT5 bar timestamps are in the broker's server timezone; we detect that offset from a live
tick and convert everything to true UTC so the session gate (London window) is correct.

Usage (Windows, FTMO terminal open + logged in):
    py scripts/mt5_export.py --start 2024-01-01 --end 2026-06-01
"""

from __future__ import annotations

import argparse
import sys
import time as _time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.backtest.types import BTBar          # noqa: E402
from src.common.config import load_config     # noqa: E402
from src.data.clean import clean_bars         # noqa: E402
from src.data.store import write_parquet      # noqa: E402

try:
    import MetaTrader5 as mt5  # type: ignore
except Exception:
    print("ERROR: MetaTrader5 not installed. Run: py -m pip install MetaTrader5")
    raise SystemExit(1)


def _detect_server_utc_offset(symbol: str) -> int:
    """Seconds the broker server clock is AHEAD of UTC (e.g. +10800 for GMT+3)."""
    tick = mt5.symbol_info_tick(symbol)
    if tick is None or not tick.time:
        return 0
    return round((tick.time - _time.time()) / 3600.0) * 3600


def main(argv) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", required=True, help="YYYY-MM-DD (UTC)")
    ap.add_argument("--end", required=True, help="YYYY-MM-DD (UTC)")
    args = ap.parse_args(argv)

    cfg = load_config()
    symbol = cfg.execution.symbol
    bt = cfg.raw.get("backtest", {})
    pip = float(bt.get("symbol", {}).get("pip_size", 0.0001))
    out_path = bt.get("data_path", "state/parquet/eurusd_m15.parquet")

    if not mt5.initialize(path=cfg.mt5.terminal_path) if cfg.mt5.terminal_path \
            else not mt5.initialize():
        print("ERROR: mt5.initialize failed:", mt5.last_error()); return 1
    try:
        mt5.login(login=cfg.mt5.login, password=cfg.mt5.password, server=cfg.mt5.server)
        mt5.symbol_select(symbol, True)
        offset = _detect_server_utc_offset(symbol)
        print(f"Server-UTC offset detected: {offset/3600:+.0f}h")

        start = datetime.fromisoformat(args.start)
        end = datetime.fromisoformat(args.end)
        rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M15, start, end)
        if rates is None or len(rates) == 0:
            print("ERROR: no rates returned:", mt5.last_error()); return 1
        print(f"Pulled {len(rates)} raw M15 bars from MT5.")

        bars = []
        for r in rates:
            ts_utc = datetime.fromtimestamp(int(r["time"]) - offset, tz=timezone.utc)
            spread_pips = float(r["spread"]) / 10.0   # 5-digit EURUSD: 10 points = 1 pip
            bars.append(BTBar(ts_open_utc=ts_utc, open=float(r["open"]),
                             high=float(r["high"]), low=float(r["low"]),
                             close=float(r["close"]), volume=float(r["tick_volume"]),
                             spread_pips=spread_pips))

        cleaned, rep = clean_bars(bars, tf_min=15, pip_size=pip)
        write_parquet(cleaned, out_path)
        span = (cleaned[0].ts_open_utc.isoformat(), cleaned[-1].ts_open_utc.isoformat())
        print(f"Cleaned: in={rep.input_count} out={rep.output_count} "
              f"dupes={rep.duplicates_removed} weekend={rep.weekend_dropped} "
              f"outliers={rep.outliers_dropped} gaps={len(rep.gaps)}")
        print(f"Span: {span[0]} -> {span[1]}")
        print(f"Wrote {out_path}")
        if rep.gaps[:5]:
            print("First gaps:", rep.gaps[:5])
        return 0
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
