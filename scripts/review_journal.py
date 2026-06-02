"""Performance Reviewer — deterministic stats + drift detection (spec 06 §4/§5).

Reads the trade journal (READ-ONLY), computes expectancy / rule-budget pressure, runs a
CUSUM drift check, writes a run-summary, and raises a drift flag if warranted. The LLM
scheduled task narrates this output; the numbers themselves are deterministic here.

Exits cleanly with "no trades yet" until the engine is forward-testing."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.agents.drift import cusum_state, drift_action     # noqa: E402
from src.common.config import load_config                  # noqa: E402


def main() -> int:
    cfg = load_config()
    state = Path(cfg.state_dir)
    if not (state / "live.sqlite").exists():
        print("no journal yet (engine has not traded) — nothing to review.")
        return 0

    from src.journal import JournalReader
    reader = JournalReader(state)
    try:
        exp = reader.expectancy()
        pressure = reader.rule_budget_pressure()
        df = reader.trades()
    finally:
        reader.close()

    n = exp.get("n", 0)
    if n == 0:
        print("journal present but no closed trades yet — nothing to review.")
        return 0

    # CUSUM drift on the sequence of trade R-multiples vs the backtest expectancy floor.
    r_series = df["outcome.r_multiple"].dropna().tolist() if "outcome.r_multiple" in df else []
    state_drift = cusum_state(r_series, target=0.10, k=0.05, h_warn=0.8, h_alarm=1.6)
    action = drift_action(state_drift)

    summary = {
        "ts_utc": datetime.now(tz=timezone.utc).isoformat(),
        "trades": n, "expectancy_r": exp.get("avg_r"), "win_rate": exp.get("win_rate"),
        "profit_factor": exp.get("profit_factor"),
        "rule_budget_pressure": pressure,
        "drift_state": state_drift, "drift_action": action.action,
        "drift_owner": action.owner,
    }
    reports = state / "reports"; reports.mkdir(parents=True, exist_ok=True)
    day = datetime.now(tz=timezone.utc).date().isoformat()
    (reports / f"review-{day}.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    if state_drift != "ok":
        flag = {"raised_utc": summary["ts_utc"], "state": state_drift,
                "action": action.action, "owner": action.owner, "note": action.note}
        (state / "drift_flag.json").write_text(json.dumps(flag, indent=2), encoding="utf-8")
        print(f"DRIFT {state_drift.upper()} -> {action.action} (owner: {action.owner}). "
              f"Flag written for the Researcher.")
    else:
        print(f"Reviewed {n} trades: expectancy {exp.get('avg_r'):+.3f}R, "
              f"PF {exp.get('profit_factor'):.2f}. Drift: ok.")
    print(f"Summary -> {reports / f'review-{day}.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
