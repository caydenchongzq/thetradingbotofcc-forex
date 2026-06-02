"""Resolve the ACTIVE strategy config (spec 06 §6 / 07 §9) — closes the promotion loop.

The improvement loop commits new strategy-config versions to the versioned store, so the
live engine and the backtester must load the store's HEAD version, not just the static
``config/default.yaml``. If no store exists yet, fall back to the YAML strategy block.
The live box only ever adopts a new version at a session boundary."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def resolve_strategy_config(state_dir: str | Path, fallback_strategy: dict[str, Any],
                            fallback_version: int = 1) -> tuple[dict[str, Any], int]:
    """Return (strategy_config, version): the HEAD version from the versioned store if
    present, else the provided fallback (from default.yaml)."""
    head_file = Path(state_dir) / "config" / "HEAD"
    versions = Path(state_dir) / "config" / "versions"
    if head_file.exists() and versions.exists():
        try:
            head = int(head_file.read_text().strip())
            rec = json.loads((versions / f"v{head}.json").read_text(encoding="utf-8"))
            return rec["config"], head
        except Exception:
            pass
    cfg = dict(fallback_strategy)
    cfg.setdefault("config_version", fallback_version)
    return cfg, int(cfg.get("config_version", fallback_version))
