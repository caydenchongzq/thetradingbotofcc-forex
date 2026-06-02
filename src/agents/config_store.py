"""Versioned config store + promotion (spec 06 §6) — the ONLY write path back to live.

Monotonic versions, each recording parent/diff/approval/status. Promotion uses a
compare-and-swap on the parent version (optimistic concurrency) plus a single-holder
lease, so the LLM never has to reason about concurrency and a stale-parent proposal is
re-queued, never blind-merged. Every promotion is reversible (HEAD checkout)."""

from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.agents.proposal import DiffEntry


class StaleParentError(RuntimeError):
    """Proposal branched from a version that is no longer HEAD — must re-backtest."""


class LeaseHeldError(RuntimeError):
    """Another proposal currently holds the in_promotion lease."""


def apply_diff(base_config: dict, diff: list[DiffEntry]) -> dict:
    """Apply dotted-path param changes to a deep copy of ``base_config``."""
    cfg = copy.deepcopy(base_config)
    for entry in diff:
        parts = entry.param.split(".")
        node = cfg
        for p in parts[:-1]:
            node = node.setdefault(p, {})
        node[parts[-1]] = entry.to_value
    return cfg


class ConfigStore:
    def __init__(self, state_dir: str | Path, base_config: dict):
        self.root = Path(state_dir) / "config" / "versions"
        self.root.mkdir(parents=True, exist_ok=True)
        self.head_file = Path(state_dir) / "config" / "HEAD"
        self.lease_file = Path(state_dir) / "config" / "promotion.lease"
        if not list(self.root.glob("v*.json")):
            self._write(1, {"version": 1, "parent": None, "author": "bootstrap",
                            "diff": [], "approval": "bootstrap", "status": "promoted",
                            "config": base_config,
                            "ts_utc": datetime.now(tz=timezone.utc).isoformat()})
            self._set_head(1)

    # ---- versions ----
    def _write(self, version: int, record: dict) -> None:
        (self.root / f"v{version}.json").write_text(json.dumps(record, indent=2),
                                                    encoding="utf-8")

    def get(self, version: int) -> dict:
        return json.loads((self.root / f"v{version}.json").read_text(encoding="utf-8"))

    def get_config(self, version: int) -> dict:
        return self.get(version)["config"]

    def max_version(self) -> int:
        return max(int(p.stem[1:]) for p in self.root.glob("v*.json"))

    def head_version(self) -> int:
        return int(self.head_file.read_text().strip())

    def _set_head(self, version: int) -> None:
        self.head_file.write_text(str(version), encoding="utf-8")

    # ---- promotion lease ----
    def acquire_lease(self, proposal_id: str) -> None:
        if self.lease_file.exists():
            holder = self.lease_file.read_text().strip()
            if holder and holder != proposal_id:
                raise LeaseHeldError(f"lease held by {holder}")
        self.lease_file.write_text(proposal_id, encoding="utf-8")

    def release_lease(self) -> None:
        if self.lease_file.exists():
            self.lease_file.unlink()

    # ---- promote / rollback ----
    def promote(self, parent_version: int, diff: list[DiffEntry], author: str,
                approval: str, config: dict | None = None) -> int:
        """Compare-and-swap: refuse unless ``parent_version`` is current HEAD."""
        if parent_version != self.head_version():
            raise StaleParentError(
                f"parent {parent_version} != HEAD {self.head_version()}; re-backtest required")
        new_version = self.max_version() + 1
        cfg = config if config is not None else apply_diff(self.get_config(parent_version), diff)
        cfg = dict(cfg)
        cfg["config_version"] = new_version
        self._write(new_version, {
            "version": new_version, "parent": parent_version, "author": author,
            "diff": [{"param": d.param, "from": d.from_value, "to": d.to_value} for d in diff],
            "approval": approval, "status": "promoted", "config": cfg,
            "ts_utc": datetime.now(tz=timezone.utc).isoformat()})
        self._set_head(new_version)
        self.release_lease()
        return new_version

    def rollback(self, to_version: int) -> None:
        """Reversible: point HEAD back to an earlier version (the next session adopts it)."""
        if not (self.root / f"v{to_version}.json").exists():
            raise ValueError(f"no version {to_version}")
        self._set_head(to_version)
