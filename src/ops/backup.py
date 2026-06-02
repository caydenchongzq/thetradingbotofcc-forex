"""State backups (spec 07 §7, ties to spec 04 §6) — on-box + off-box.

Copies the SQLite DB and the day's JSONL to a timestamped on-box path and (optionally)
mirrors to an off-box target. A whole-host loss must not be terminal."""

from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path


def backup_state(state_dir: str | Path, *, off_box_dir: str | Path | None = None,
                 now: datetime | None = None) -> dict:
    """Timestamped copy of live.sqlite + today's JSONL into state/backups (+ off-box).
    Returns a manifest of what was copied."""
    state = Path(state_dir)
    ts = (now or datetime.now(tz=timezone.utc)).strftime("%Y%m%dT%H%M%SZ")
    dest = state / "backups" / ts
    dest.mkdir(parents=True, exist_ok=True)

    copied: list[str] = []
    sqlite = state / "live.sqlite"
    if sqlite.exists():
        shutil.copy2(sqlite, dest / "live.sqlite")
        copied.append("live.sqlite")

    jdir = state / "journal"
    if jdir.exists():
        for jf in sorted(jdir.glob("*.jsonl"))[-1:]:   # the most recent day's file
            shutil.copy2(jf, dest / jf.name)
            copied.append(jf.name)

    manifest = {"ts": ts, "dest": str(dest), "files": copied, "off_box": None}
    if off_box_dir:
        off = Path(off_box_dir) / ts
        off.mkdir(parents=True, exist_ok=True)
        for f in copied:
            shutil.copy2(dest / f, off / f)
        manifest["off_box"] = str(off)
    return manifest


def restore_state(backup_dir: str | Path, target_state_dir: str | Path) -> list[str]:
    """Restore a backup snapshot into a (scratch) state dir. Part of the B->C restore test."""
    src = Path(backup_dir)
    target = Path(target_state_dir)
    (target / "journal").mkdir(parents=True, exist_ok=True)
    restored = []
    for f in src.glob("*"):
        if f.name == "live.sqlite":
            shutil.copy2(f, target / "live.sqlite")
        elif f.name.endswith(".jsonl"):
            shutil.copy2(f, target / "journal" / f.name)
        else:
            continue
        restored.append(f.name)
    return restored
