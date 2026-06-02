"""Bar store (spec 05 §3): Parquet round-trip + DataFrame<->BTBar.

Pandas/pyarrow are imported lazily so the live spine never hard-depends on them.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Sequence

from src.backtest.types import BTBar
from src.common.timeutil import ensure_utc, utc_iso

_COLUMNS = ["ts_open_utc", "open", "high", "low", "close", "volume", "spread_pips"]


def bars_to_dataframe(bars: Sequence[BTBar]):
    import pandas as pd  # noqa: PLC0415
    rows = [{
        "ts_open_utc": utc_iso(b.ts_open_utc), "open": b.open, "high": b.high,
        "low": b.low, "close": b.close, "volume": b.volume, "spread_pips": b.spread_pips,
    } for b in bars]
    return pd.DataFrame(rows, columns=_COLUMNS)


def dataframe_to_bars(df) -> list[BTBar]:
    out = []
    for _, r in df.iterrows():
        ts = r["ts_open_utc"]
        ts = datetime.fromisoformat(str(ts).replace("Z", "+00:00")) if isinstance(ts, str) \
            else ensure_utc(ts.to_pydatetime() if hasattr(ts, "to_pydatetime") else ts)
        out.append(BTBar(ts_open_utc=ensure_utc(ts), open=float(r["open"]),
                         high=float(r["high"]), low=float(r["low"]),
                         close=float(r["close"]), volume=float(r.get("volume", 0.0)),
                         spread_pips=float(r.get("spread_pips", 0.4))))
    return out


def write_parquet(bars: Sequence[BTBar], path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    bars_to_dataframe(bars).to_parquet(path, index=False)
    return path


def read_parquet_bars(path: str | Path,
                      period: tuple[datetime, datetime] | None = None) -> list[BTBar]:
    import pandas as pd  # noqa: PLC0415
    df = pd.read_parquet(path)
    bars = dataframe_to_bars(df)
    if period is not None:
        lo, hi = ensure_utc(period[0]), ensure_utc(period[1])
        bars = [b for b in bars if lo <= ensure_utc(b.ts_open_utc) <= hi]
    return bars
