"""Schema migrations applied on read (spec 04 §5).

Each migration is a pure function ``vN -> vN+1``. Old JSONL/Parquet stays loadable
forever: on read we upgrade any record below ``SCHEMA_VERSION`` to the latest in
memory. We bump only on additive/structural change and NEVER silently repurpose a
field (that would corrupt live-vs-backtest attribution).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .schema import SCHEMA_VERSION


def _migrate_v2_to_v3(record: dict[str, Any]) -> dict[str, Any]:
    """v2 -> v3: introduce the ``model_vs_real`` block on trade records.

    v2 trades tracked only modelled costs inline; v3 splits modelled vs realised so
    the Researcher can detect cost/slippage drift. Missing data is recorded as None,
    never fabricated.
    """
    r = dict(record)
    if r.get("record_type") == "trade" and "model_vs_real" not in r:
        r["model_vs_real"] = {
            "modeled_slippage_pips": None,
            "realized_slippage_pips": None,
            "modeled_spread_pips": None,
            "realized_spread_pips": None,
        }
    r["schema_version"] = 3
    return r


# Registry keyed by the *source* version.
_MIGRATIONS: dict[int, Callable[[dict[str, Any]], dict[str, Any]]] = {
    2: _migrate_v2_to_v3,
}


def migrate_to_latest(record: dict[str, Any]) -> dict[str, Any]:
    """Apply successive migrations until the record is at ``SCHEMA_VERSION``."""
    r = record
    sv = int(r.get("schema_version", SCHEMA_VERSION))
    while sv < SCHEMA_VERSION:
        migrate = _MIGRATIONS.get(sv)
        if migrate is None:
            raise ValueError(f"no migration registered for schema_version {sv}")
        r = migrate(r)
        new_sv = int(r["schema_version"])
        if new_sv <= sv:  # guard against a non-advancing migration
            raise ValueError(f"migration from v{sv} did not advance schema_version")
        sv = new_sv
    return r
