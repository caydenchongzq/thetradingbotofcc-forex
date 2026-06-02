"""On-box + off-box state backup (spec 07 §7). Schedule hourly + at the 00:00 reset.

    py scripts/backup_state.py
Off-box target comes from TBOT_BACKUP_OFFBOX_URI (a second disk/cloud path)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.common.config import load_config       # noqa: E402
from src.ops.backup import backup_state          # noqa: E402


def main() -> int:
    cfg = load_config()
    off = os.environ.get("TBOT_BACKUP_OFFBOX_URI") or None
    man = backup_state(cfg.state_dir, off_box_dir=off)
    print(f"backup OK -> {man['dest']} ({', '.join(man['files']) or 'no files yet'})"
          + (f"; off-box -> {man['off_box']}" if man['off_box'] else "; off-box: not configured"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
