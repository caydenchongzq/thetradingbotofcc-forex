---
id: 2026-06-07-cross-instrument-confirmation
name: CrossInstrumentConfirmation
family: filter
status: blocked-on-data
related: [2026-06-02-session-breakout-er]
sources: ["https://www.researchgate.net/publication/46444432_Intra-Day_Seasonality_in_Activities_of_the_Foreign_Exchange_Markets_Evidence_from_the_Electronic_Broking_System"]
trials_used: 0
verdict: "Blocked on data: confirming EURUSD breakouts with DXY/GBPUSD/cross momentum requires instruments we do not export. Also gate-blocked like all subtractive filters (224-trade headroom)."
---

# CrossInstrumentConfirmation — confirm breakouts with correlated instruments

Take SessionBreakoutER signals only when a correlated instrument (DXY inverse, GBPUSD)
breaks the same direction. Requires multi-instrument M15 export (`scripts/mt5_export.py`
extension — backlog #4). ALSO subject to the subtractive-filter trade-count cap recorded
in [[2026-06-07-pre-session-compression-filter]] — even with data, the ≥200-trade gate
binds until the history is ~2× longer. Do not build before both are resolved.
