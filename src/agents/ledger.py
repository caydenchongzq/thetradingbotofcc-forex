"""Trial ledger (spec 06 §5) — the anti-data-snooping backbone.

EVERY hypothesis the Researcher emits (pass OR fail) is recorded against a weekly budget.
The cumulative count is fed to the backtester's deflated-Sharpe (spec 05 §8), so more
proposals automatically raise the significance bar. It is append-only and code-maintained:
there is no decrement method, so an agent cannot reset its own trial count.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def iso_week(dt: datetime) -> str:
    y, w, _ = dt.isocalendar()
    return f"{y}-W{w:02d}"


class TrialLedger:
    def __init__(self, state_dir: str | Path):
        self.path = Path(state_dir) / "config" / "trial_ledger.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.touch(exist_ok=True)

    def record(self, proposal_id: str, period: str, author: str, status: str) -> None:
        """Append one trial. ``status`` in {proposed, passed, failed, promoted, rejected}.
        Append-only by design — no update/delete path exists."""
        entry = {"proposal_id": proposal_id, "period": period, "author": author,
                 "status": status, "ts_utc": datetime.now(tz=timezone.utc).isoformat()}
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, sort_keys=True) + "\n")

    def _entries(self) -> list[dict]:
        out = []
        with open(self.path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    out.append(json.loads(line))
        return out

    def cumulative_count(self) -> int:
        """Total distinct hypotheses ever proposed — the trial count the DSR consumes."""
        return len({e["proposal_id"] for e in self._entries()})

    def count_in_period(self, period: str) -> int:
        return len({e["proposal_id"] for e in self._entries() if e["period"] == period})

    def budget_remaining(self, period: str, cap: int) -> int:
        return max(0, cap - self.count_in_period(period))
