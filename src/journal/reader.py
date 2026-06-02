"""Read-only analytics surface for the improvement loop (spec 04 §4).

The improvement loop (06) gets **only** this reader plus the versioned config store —
enforcing the R5 boundary that the LLM can read but never write live state. There are
no write methods here, by construction; any attempt to mutate raises.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from .migrations import migrate_to_latest


class ReadOnlyViolation(RuntimeError):
    """Raised if code attempts to mutate through the read-only reader."""


class JournalReader:
    """READ-ONLY view over the journal. The improvement loop never writes here."""

    def __init__(self, state_dir: str | Path):
        self.state_dir = Path(state_dir)
        sqlite_path = self.state_dir / "live.sqlite"
        # Open in immutable/read-only mode so the OS enforces the boundary too.
        uri = f"file:{sqlite_path}?mode=ro"
        self._conn = sqlite3.connect(uri, uri=True)
        self._conn.row_factory = sqlite3.Row

    # ---- explicit read-only guard ----------------------------------------
    def __setattr__(self, name: str, value: Any) -> None:
        # Allow internal attributes to be set during __init__ only.
        if name in ("state_dir", "_conn"):
            object.__setattr__(self, name, value)
            return
        raise ReadOnlyViolation(f"JournalReader is read-only; cannot set {name!r}")

    def _records(self, table: str) -> list[dict[str, Any]]:
        rows = self._conn.execute(f"SELECT record FROM {table}").fetchall()
        return [migrate_to_latest(json.loads(r["record"])) for r in rows]

    # ---- DataFrame surfaces ----------------------------------------------
    def trades(self, since: str | None = None, regime: str | None = None,
               config_version: int | None = None) -> "Any":
        import pandas as pd  # noqa: PLC0415

        records = self._records("trades")
        df = pd.json_normalize(records) if records else pd.DataFrame()
        if df.empty:
            return df
        if since is not None:
            df = df[df["ts_utc"] >= since]
        if regime is not None and "regime.vol_state" in df.columns:
            df = df[df["regime.vol_state"] == regime]
        if config_version is not None and "config_version" in df.columns:
            df = df[df["config_version"] == config_version]
        return df.reset_index(drop=True)

    def rejects(self, since: str | None = None) -> "Any":
        import pandas as pd  # noqa: PLC0415

        records = self._records("rejects")
        df = pd.json_normalize(records) if records else pd.DataFrame()
        if not df.empty and since is not None:
            df = df[df["ts_utc"] >= since]
        return df.reset_index(drop=True) if not df.empty else df

    def expectancy(self, window: int | None = None) -> dict[str, float]:
        """Avg R, win rate, profit factor, MAE/MFE means over (optionally) the last N trades."""
        df = self.trades()
        if df.empty or "outcome.r_multiple" not in df.columns:
            return {"n": 0, "avg_r": 0.0, "win_rate": 0.0, "profit_factor": 0.0}
        r = df["outcome.r_multiple"].dropna()
        if window:
            r = r.tail(window)
        if len(r) == 0:
            return {"n": 0, "avg_r": 0.0, "win_rate": 0.0, "profit_factor": 0.0}
        wins = r[r > 0].sum()
        losses = -r[r < 0].sum()
        pf = float(wins / losses) if losses > 0 else float("inf")
        out = {
            "n": int(len(r)),
            "avg_r": float(r.mean()),
            "win_rate": float((r > 0).mean()),
            "profit_factor": pf,
        }
        for col, key in (("outcome.mae_pips", "mean_mae_pips"),
                         ("outcome.mfe_pips", "mean_mfe_pips")):
            if col in df.columns:
                out[key] = float(df[col].dropna().mean())
        return out

    def rule_budget_pressure(self, window: int | None = None) -> dict[str, float]:
        """Trailing peak daily-loss % and request usage — lets the Reviewer catch
        creeping rule pressure before a breach (spec 04 §3.1)."""
        df = self.trades()
        if df.empty:
            return {"peak_daily_pct_used": 0.0, "max_requests_used_today": 0.0}
        out: dict[str, float] = {}
        if "rule_budget.daily_pct_used" in df.columns:
            s = df["rule_budget.daily_pct_used"].dropna()
            out["peak_daily_pct_used"] = float(s.tail(window).max()) if len(s) else 0.0
        if "rule_budget.requests_used_today" in df.columns:
            s = df["rule_budget.requests_used_today"].dropna()
            out["max_requests_used_today"] = float(s.tail(window).max()) if len(s) else 0.0
        return out

    def close(self) -> None:
        self._conn.close()
