"""Journal & State store (spec 04).

Write path (crash-safe ordering, spec 04 §2):
    append the JSONL line + fsync  ->  then upsert into SQLite.
If the process dies between the two, the JSONL line is the source of truth and
SQLite is rebuilt from JSONL on startup (idempotent replay keyed by primary key).
JSONL is append-only; a corrupt partial tail is recoverable by truncation.

Principle: **no un-journaled trades** — if we cannot durably record what we are about
to do, we do not do it (spec 04 §7).
"""

from __future__ import annotations

import os
import sqlite3
import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from src.common.timeutil import PRAGUE, ensure_utc, ftmo_day_start, utc_iso
from src.risk.types import DayState, KillSwitchState

from . import schema
from .migrations import migrate_to_latest


def _deep_merge(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge ``patch`` into ``base`` (patch wins). Returns a new dict."""
    out = dict(base)
    for k, v in patch.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


class Journal:
    """Owns the JSONL -> SQLite -> Parquet write path and day/intent state."""

    def __init__(self, state_dir: str | os.PathLike[str]):
        self.state_dir = Path(state_dir)
        self.journal_dir = self.state_dir / "journal"
        self.sqlite_path = self.state_dir / "live.sqlite"
        self.parquet_dir = self.state_dir / "parquet"
        self.journal_dir.mkdir(parents=True, exist_ok=True)
        self.parquet_dir.mkdir(parents=True, exist_ok=True)

        # Recover any partial JSONL tail from an interrupted append before reading.
        self._truncate_all_partial_tails()

        self._conn = sqlite3.connect(str(self.sqlite_path))
        self._conn.row_factory = sqlite3.Row
        self._init_db()

        # On startup, ensure SQLite reflects the JSONL truth (idempotent).
        self.rebuild_sqlite_from_jsonl()

    # ------------------------------------------------------------------ setup
    def _init_db(self) -> None:
        cur = self._conn.cursor()
        cur.executescript(
            """
            CREATE TABLE IF NOT EXISTS trades (
                trade_id TEXT PRIMARY KEY,
                config_version INTEGER,
                schema_version INTEGER,
                ts_utc TEXT,
                vol_state TEXT,
                r_multiple REAL,
                record TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS rejects (
                record_id TEXT PRIMARY KEY,
                config_version INTEGER,
                ts_utc TEXT,
                stage TEXT,
                reason TEXT,
                record TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS health (
                record_id TEXT PRIMARY KEY,
                ts_utc TEXT,
                engine_up INTEGER,
                record TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS day_state (
                day_key TEXT PRIMARY KEY,
                reset_ts_utc TEXT,
                record TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS intents (
                client_id TEXT PRIMARY KEY,
                magic INTEGER,
                status TEXT,
                ts_utc TEXT,
                record TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS ix_trades_ts ON trades(ts_utc);
            CREATE INDEX IF NOT EXISTS ix_rejects_ts ON rejects(ts_utc);
            """
        )
        self._conn.commit()

    # ----------------------------------------------------------- file helpers
    def _file_for(self, ts_utc: datetime) -> Path:
        """JSONL file for a record's FTMO trading day (Prague calendar date)."""
        day = ensure_utc(ts_utc).astimezone(PRAGUE).date().isoformat()
        return self.journal_dir / f"{day}.jsonl"

    def _truncate_all_partial_tails(self) -> None:
        if not self.journal_dir.exists():
            return
        for path in self.journal_dir.glob("*.jsonl"):
            self._truncate_partial_tail(path)

    @staticmethod
    def _truncate_partial_tail(path: Path) -> None:
        """Truncate a trailing partial line (crash mid-append). JSONL is line-oriented;
        a complete record always ends with a newline, so any bytes after the last
        newline are an incomplete write and must be dropped (spec 04 §7)."""
        if not path.exists() or path.stat().st_size == 0:
            return
        with open(path, "rb") as fh:
            data = fh.read()
        last_nl = data.rfind(b"\n")
        if last_nl == -1:
            # No complete line at all -> whole file is a partial write.
            with open(path, "wb") as fh:
                fh.truncate(0)
            return
        if last_nl != len(data) - 1:
            with open(path, "wb") as fh:
                fh.write(data[: last_nl + 1])

    # ------------------------------------------------------------ write path
    def append(self, record: dict[str, Any]) -> str:
        """Validate, fsync to JSONL, then upsert SQLite. Returns the primary key.

        The record is mutated only to fill an absent ``record_id``/``schema_version``.
        """
        record = dict(record)
        record.setdefault("schema_version", schema.SCHEMA_VERSION)
        if "ts_utc" not in record:
            raise schema.SchemaError("record missing ts_utc")

        if record["record_type"] != "trade" and "record_id" not in record:
            record["record_id"] = self._make_record_id(record)

        schema.validate(record)
        key = schema.primary_key(record)

        # 1) Durable JSONL append + fsync (the source of truth).
        line = schema.to_jsonl(record) + "\n"
        path = self._file_for(_parse_ts(record["ts_utc"]))
        fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
        try:
            os.write(fd, line.encode("utf-8"))
            os.fsync(fd)
        finally:
            os.close(fd)

        # 2) SQLite upsert (rebuildable from JSONL if we crash before this).
        self._upsert(record)
        self._conn.commit()
        return key

    def update_trade(self, trade_id: str, patch: dict[str, Any]) -> None:
        """Append a staged trade update (manage/exit) and merge it into the row."""
        existing = self._get_trade_record(trade_id)
        if existing is None:
            raise KeyError(f"unknown trade_id {trade_id!r}")
        merged_patch = dict(patch)
        merged_patch["record_type"] = "trade"
        merged_patch["trade_id"] = trade_id
        merged_patch.setdefault("ts_utc", _now_iso())
        merged_patch.setdefault("config_version", existing.get("config_version"))
        merged_patch.setdefault("schema_version", schema.SCHEMA_VERSION)
        self.append(merged_patch)

    # --------------------------------------------------------------- upsert
    def _upsert(self, record: dict[str, Any]) -> None:
        record = migrate_to_latest(record)
        rt = record["record_type"]
        if rt == "trade":
            self._upsert_trade(record)
        elif rt == "reject":
            self._upsert_reject(record)
        elif rt == "health":
            self._upsert_health(record)
        elif rt == "day_state":
            self._upsert_day_state(record)
        elif rt == "intent":
            self._upsert_intent(record)

    def _upsert_trade(self, record: dict[str, Any]) -> None:
        trade_id = record["trade_id"]
        prev = self._get_trade_record(trade_id)
        merged = _deep_merge(prev, record) if prev else record
        outcome = merged.get("outcome") or {}
        regime = merged.get("regime") or {}
        self._conn.execute(
            """INSERT INTO trades(trade_id, config_version, schema_version, ts_utc,
                                   vol_state, r_multiple, record)
               VALUES(?,?,?,?,?,?,?)
               ON CONFLICT(trade_id) DO UPDATE SET
                   config_version=excluded.config_version,
                   schema_version=excluded.schema_version,
                   ts_utc=excluded.ts_utc,
                   vol_state=excluded.vol_state,
                   r_multiple=excluded.r_multiple,
                   record=excluded.record""",
            (
                trade_id,
                merged.get("config_version"),
                merged.get("schema_version"),
                merged.get("ts_utc"),
                regime.get("vol_state"),
                outcome.get("r_multiple"),
                schema.to_jsonl(merged),
            ),
        )

    def _upsert_reject(self, record: dict[str, Any]) -> None:
        self._conn.execute(
            """INSERT INTO rejects(record_id, config_version, ts_utc, stage, reason, record)
               VALUES(?,?,?,?,?,?)
               ON CONFLICT(record_id) DO UPDATE SET record=excluded.record""",
            (
                record["record_id"],
                record.get("config_version"),
                record.get("ts_utc"),
                record.get("stage"),
                record.get("reason"),
                schema.to_jsonl(record),
            ),
        )

    def _upsert_health(self, record: dict[str, Any]) -> None:
        self._conn.execute(
            """INSERT INTO health(record_id, ts_utc, engine_up, record)
               VALUES(?,?,?,?)
               ON CONFLICT(record_id) DO UPDATE SET record=excluded.record""",
            (
                record["record_id"],
                record.get("ts_utc"),
                1 if record.get("engine_up") else 0,
                schema.to_jsonl(record),
            ),
        )

    def _upsert_day_state(self, record: dict[str, Any]) -> None:
        self._conn.execute(
            """INSERT INTO day_state(day_key, reset_ts_utc, record)
               VALUES(?,?,?)
               ON CONFLICT(day_key) DO UPDATE SET
                   reset_ts_utc=excluded.reset_ts_utc, record=excluded.record""",
            (record["day_key"], record.get("reset_ts_utc"), schema.to_jsonl(record)),
        )

    def _upsert_intent(self, record: dict[str, Any]) -> None:
        self._conn.execute(
            """INSERT INTO intents(client_id, magic, status, ts_utc, record)
               VALUES(?,?,?,?,?)
               ON CONFLICT(client_id) DO UPDATE SET
                   magic=excluded.magic, status=excluded.status,
                   ts_utc=excluded.ts_utc, record=excluded.record""",
            (
                record["client_id"],
                record.get("magic"),
                record.get("status"),
                record.get("ts_utc"),
                schema.to_jsonl(record),
            ),
        )

    # ----------------------------------------------------------------- reads
    def _get_trade_record(self, trade_id: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT record FROM trades WHERE trade_id=?", (trade_id,)
        ).fetchone()
        return json.loads(row["record"]) if row else None

    def open_intents(self) -> list[dict[str, Any]]:
        """Non-terminal intents for cold-boot reconciliation (spec 03/04 §3.5)."""
        rows = self._conn.execute(
            "SELECT record FROM intents WHERE status NOT IN ('filled','closed','cancelled','rejected')"
        ).fetchall()
        return [json.loads(r["record"]) for r in rows]

    # ------------------------------------------------------------- day state
    def get_day_state(self) -> DayState | None:
        row = self._conn.execute(
            "SELECT record FROM day_state ORDER BY reset_ts_utc DESC LIMIT 1"
        ).fetchone()
        if row is None:
            return None
        return _day_state_from_record(json.loads(row["record"]))

    def put_day_state(self, day: DayState) -> None:
        reset_ts = day.reset_ts_utc
        day_key = (
            ftmo_day_start(reset_ts).date().isoformat()
            if reset_ts is not None
            else "bootstrap"
        )
        record = {
            "record_type": "day_state",
            "schema_version": schema.SCHEMA_VERSION,
            "ts_utc": utc_iso(reset_ts) if reset_ts else _now_iso(),
            "day_key": day_key,
            "reset_ts_utc": utc_iso(reset_ts) if reset_ts else None,
            "balance_0000": day.balance_0000,
            "initial": day.initial,
            "requests_used_today": day.requests_used_today,
            "killswitch": day.killswitch.value,
            "open_risk_usd": day.open_risk_usd,
            "trades_opened_today": day.trades_opened_today,
            "recent_risk_usds": list(day.recent_risk_usds),
        }
        self.append(record)

    # --------------------------------------------------------- maintenance
    def rebuild_sqlite_from_jsonl(self) -> None:
        """Idempotent replay: clear tables, replay every JSONL record in order.

        Reproduces identical SQLite state from the JSONL log (spec 04 §8). Because the
        log is replayed in chronological order, staged trade merges reconstruct exactly.
        """
        cur = self._conn.cursor()
        for tbl in ("trades", "rejects", "health", "day_state", "intents"):
            cur.execute(f"DELETE FROM {tbl}")
        for path in sorted(self.journal_dir.glob("*.jsonl")):
            with open(path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    record = json.loads(line)
                    self._upsert(record)
        self._conn.commit()

    def snapshot_parquet(self) -> None:
        """Export trades/rejects to columnar Parquet for the agents (spec 04 §2).

        Imported lazily so the journal has no hard pandas/pyarrow requirement on the
        live write path.
        """
        import pandas as pd  # noqa: PLC0415

        def _dump(table: str, subdir: str) -> None:
            rows = self._conn.execute(f"SELECT record FROM {table}").fetchall()
            records = [migrate_to_latest(json.loads(r["record"])) for r in rows]
            if not records:
                return
            df = pd.json_normalize(records)
            out_dir = self.parquet_dir / subdir
            out_dir.mkdir(parents=True, exist_ok=True)
            df.to_parquet(out_dir / "snapshot.parquet", index=False)

        _dump("trades", "trades")
        _dump("rejects", "rejects")

    # ----------------------------------------------------------------- util
    def _make_record_id(self, record: dict[str, Any]) -> str:
        rt = record["record_type"]
        instrument = record.get("instrument", "NA")
        ts = record["ts_utc"]
        seq = self._next_seq(rt, ts)
        return f"{rt}-{instrument}-{ts}-{seq}"

    def _next_seq(self, rt: str, ts: str) -> int:
        # Monotonic per (type, ts) so simultaneous records don't collide.
        like = f"{rt}-%-{ts}-%"
        table = {"reject": "rejects", "health": "health", "intent": "intents",
                 "day_state": "day_state"}.get(rt)
        if table is None:
            return 0
        col = {"rejects": "record_id", "health": "record_id", "intents": "client_id",
               "day_state": "day_key"}[table]
        n = self._conn.execute(
            f"SELECT COUNT(*) AS c FROM {table} WHERE {col} LIKE ?", (like,)
        ).fetchone()["c"]
        return int(n)

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "Journal":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


# ---------------------------------------------------------------- free fns
def _parse_ts(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def _now_iso() -> str:
    from datetime import timezone

    return utc_iso(datetime.now(tz=timezone.utc))


def _day_state_from_record(rec: dict[str, Any]) -> DayState:
    reset = rec.get("reset_ts_utc")
    return DayState(
        balance_0000=float(rec["balance_0000"]),
        initial=float(rec["initial"]),
        requests_used_today=int(rec.get("requests_used_today", 0)),
        killswitch=KillSwitchState(rec.get("killswitch", "armed")),
        open_risk_usd=float(rec.get("open_risk_usd", 0.0)),
        trades_opened_today=int(rec.get("trades_opened_today", 0)),
        reset_ts_utc=_parse_ts(reset) if reset else None,
        recent_risk_usds=tuple(rec.get("recent_risk_usds", []) or []),
    )
