"""Manual kill-switch via a sentinel file (spec 07 §10).

The engine polls for a sentinel file each loop; if present, it flattens engine-owned
positions and halts (no new entries) until a human removes the file — mirroring the
Risk Governor's latched FLATTEN (never auto-resumes after a risk-driven kill)."""

from __future__ import annotations

from pathlib import Path


def killswitch_path(state_dir: str | Path) -> Path:
    return Path(state_dir) / "HALT"


def killswitch_engaged(state_dir: str | Path) -> bool:
    return killswitch_path(state_dir).exists()


def engage_killswitch(state_dir: str | Path, reason: str = "manual") -> None:
    p = killswitch_path(state_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(reason, encoding="utf-8")


def clear_killswitch(state_dir: str | Path) -> None:
    p = killswitch_path(state_dir)
    if p.exists():
        p.unlink()
