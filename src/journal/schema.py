"""Journal record schema + validation (spec 04 §3, schema_version 3).

Records share an envelope. Validation is intentionally strict: a malformed record is
a code bug, not something to silently drop (spec 04 §7). We validate structural
invariants (required envelope fields, known record_type, JSON-serialisable), not deep
field-by-field types — the latter would couple the journal to every producer's schema
and defeat additive evolution.
"""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = 3

RECORD_TYPES = frozenset({"trade", "reject", "health", "day_state", "intent"})

# Envelope fields every record must carry (spec 04 §3).
_ENVELOPE_REQUIRED = ("record_type", "schema_version", "ts_utc")


class SchemaError(ValueError):
    """Raised when a record fails structural validation."""


def validate(record: dict[str, Any]) -> None:
    """Raise SchemaError if ``record`` is not a well-formed journal record."""
    if not isinstance(record, dict):
        raise SchemaError(f"record must be a dict, got {type(record).__name__}")

    for fld in _ENVELOPE_REQUIRED:
        if fld not in record:
            raise SchemaError(f"missing required envelope field: {fld!r}")

    rt = record["record_type"]
    if rt not in RECORD_TYPES:
        raise SchemaError(f"unknown record_type: {rt!r}")

    sv = record["schema_version"]
    if not isinstance(sv, int):
        raise SchemaError(f"schema_version must be int, got {sv!r}")
    if sv > SCHEMA_VERSION:
        raise SchemaError(
            f"record schema_version {sv} is newer than supported {SCHEMA_VERSION}"
        )

    # config_version is required on the contract records (trade/reject); health and
    # day_state/intent are operational and may predate a config bump.
    if rt in ("trade", "reject") and "config_version" not in record:
        raise SchemaError(f"{rt} record missing config_version")

    # Must be JSON-serialisable (the JSONL line is the source of truth).
    try:
        json.dumps(record, sort_keys=True)
    except (TypeError, ValueError) as exc:
        raise SchemaError(f"record is not JSON-serialisable: {exc}") from exc


def primary_key(record: dict[str, Any]) -> str:
    """Stable identifier used for idempotent SQLite upserts / replay dedupe.

    Trades key on ``trade_id`` (so staged entry->manage->exit updates merge); everything
    else keys on ``record_id`` (assigned by the Journal if absent).
    """
    if record["record_type"] == "trade":
        tid = record.get("trade_id")
        if not tid:
            raise SchemaError("trade record missing trade_id")
        return str(tid)
    rid = record.get("record_id")
    if not rid:
        raise SchemaError("record missing record_id")
    return str(rid)


def to_jsonl(record: dict[str, Any]) -> str:
    """Serialise a record to a single deterministic JSONL line (no trailing newline).

    ``sort_keys=True`` makes the line byte-stable for the round-trip test (spec 04 §8).
    """
    return json.dumps(record, sort_keys=True, separators=(",", ":"))
