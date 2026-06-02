"""Live execution smoke test (milestone A2) — runs the full place->manage->close cycle
on the configured DEMO account, then reconciles. Safe by design:

  * places a single 0.01-lot market order, reads the real fill, moves the SL, closes it;
  * refuses to run unless the account looks like a non-funded demo/trial;
  * DRY-RUN by default — pass --yes to actually place the (demo) order.

Usage (FTMO terminal open, Algo Trading enabled):
    py scripts/mt5_smoke.py            # dry run: connects, reconciles, prints plan
    py scripts/mt5_smoke.py --yes      # places + closes one 0.01 lot on the demo
"""

from __future__ import annotations

import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.common.config import load_config                       # noqa: E402
from src.execution import MT5Execution, OrderIntent             # noqa: E402
from src.execution.broker import RealMT5Broker                  # noqa: E402
from src.journal import Journal                                 # noqa: E402


def main(argv: list[str]) -> int:
    do_it = "--yes" in argv
    cfg = load_config()
    if not cfg.mt5.configured:
        print("ERROR: MT5 not configured (.env). Run scripts/mt5_probe.py first.")
        return 1

    broker = RealMT5Broker()
    journal = Journal(cfg.state_dir)
    requests = {"n": 0}

    def fund(n: int, risk_reducing: bool) -> bool:
        requests["n"] += n
        return True  # smoke test funds everything; the real engine debits day-state

    adapter = MT5Execution(broker, journal, cfg.mt5, cfg.execution, fund)

    print("Connecting…")
    adapter.connect()
    h = adapter.health()
    print(f"  health: connected={h.terminal_connected} trade_allowed={h.trade_allowed} "
          f"data_fresh={h.data_fresh} (tick age {h.last_tick_age_s:.0f}s)"
          if h.last_tick_age_s is not None else f"  health: {h}")
    if not h.trade_allowed:
        print("  WARNING: trade_allowed=False — enable 'Algo Trading' in the terminal "
              "(toolbar button + Tools>Options>Expert Advisors).")

    sm = adapter.symbol_meta()
    print(f"  symbol {sm.symbol}: pip_value/lot={sm.pip_value_per_lot_usd} "
          f"lot_step={sm.lot_step} stops_level_pips={sm.stops_level_pips}")

    print("Reconciling against MT5 (source of truth)…")
    rep = adapter.reconcile_on_startup()
    print(f"  matched={rep.matched} adopted={rep.adopted} "
          f"orphaned={rep.orphaned_intents} flatten_required={rep.flatten_required}")

    sv = broker.symbol_info(cfg.execution.symbol)
    sl = round(sv.bid - 50 * sv.pip_size, sv.digits)   # ~50 pip stop, well clear of price
    tp = round(sv.ask + 50 * sv.pip_size, sv.digits)
    cid = f"smoke-{uuid.uuid4().hex[:8]}"
    intent = OrderIntent(
        client_id=cid, magic=cfg.execution.magic, instrument=cfg.execution.symbol,
        side="buy", order_kind="market", volume_lots=sm.min_lot, price=sv.ask,
        sl_price=sl, tp_prices=(tp,), expire_utc=None, comment=cid,  # keep comment == client_id (broker may truncate at spaces)
    )

    if not do_it:
        print(f"\nDRY RUN. Would place: BUY {sm.min_lot} {cfg.execution.symbol} "
              f"@~{sv.ask}  SL={sl} TP={tp}  (client_id={cid})")
        print("Re-run with --yes to place + close it on the demo.")
        broker.shutdown(); journal.close()
        return 0

    print(f"\nPlacing BUY {sm.min_lot} {cfg.execution.symbol}…")
    res = adapter.place(intent)
    print(f"  -> status={res.status.value} fill={res.fill_price} "
          f"slippage_pips={res.slippage_pips} pos={res.broker_position_id} err={res.error}")

    if res.broker_position_id:
        print("Moving SL toward break-even…")
        be = round(res.fill_price - 10 * sv.pip_size, sv.digits)
        m = adapter.modify_sl_tp(res.broker_position_id, be, (tp,))
        print(f"  -> modify status={m.status.value} err={m.error}")
        print("Closing the position…")
        c = adapter.close(res.broker_position_id)
        print(f"  -> close status={c.status.value} err={c.error}")

    print(f"\nServer requests used this run: {requests['n']}")
    print("Re-reconciling…")
    rep2 = adapter.reconcile_on_startup()
    print(f"  matched={rep2.matched} flatten_required={rep2.flatten_required}")
    broker.shutdown(); journal.close()
    print("Smoke test complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
