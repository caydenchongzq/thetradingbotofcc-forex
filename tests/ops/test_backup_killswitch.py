"""Backup/restore + sentinel kill-switch (spec 07 §7/§10)."""

import sqlite3

from src.ops.backup import backup_state, restore_state
from src.ops.killswitch import (clear_killswitch, engage_killswitch, killswitch_engaged)


def _seed_state(state):
    (state / "journal").mkdir(parents=True, exist_ok=True)
    (state / "journal" / "2026-06-02.jsonl").write_text('{"record_type":"health"}\n',
                                                         encoding="utf-8")
    con = sqlite3.connect(state / "live.sqlite")
    con.execute("CREATE TABLE t(x)")
    con.execute("INSERT INTO t VALUES(1)")
    con.commit()
    con.close()


def test_backup_then_restore_roundtrip(tmp_path):
    state = tmp_path / "state"
    _seed_state(state)
    off = tmp_path / "offbox"
    man = backup_state(state, off_box_dir=off)
    assert "live.sqlite" in man["files"] and "2026-06-02.jsonl" in man["files"]
    assert man["off_box"] is not None

    scratch = tmp_path / "restored"
    restored = restore_state(man["dest"], scratch)
    assert "live.sqlite" in restored
    # restored DB is runnable
    con = sqlite3.connect(scratch / "live.sqlite")
    assert con.execute("SELECT x FROM t").fetchone()[0] == 1
    con.close()
    assert (scratch / "journal" / "2026-06-02.jsonl").exists()


def test_killswitch_sentinel(tmp_path):
    state = tmp_path / "state"
    assert not killswitch_engaged(state)
    engage_killswitch(state, reason="daily_loss_proximity")
    assert killswitch_engaged(state)
    assert (state / "HALT").read_text() == "daily_loss_proximity"
    clear_killswitch(state)
    assert not killswitch_engaged(state)   # only a human clear lifts it
