---
id: YYYY-MM-DD-<slug>            # date researched + kebab slug; also the filename
name: <RegistryNameOrConcept>    # registry class name if implemented, else concept name
family: other                    # breakout | mean-reversion | trend | exit-model | filter | other
status: idea                     # idea | blocked-on-data | in-progress | tested-rejected |
                                 # tested-passed | promoted | retired
related: []                      # library ids this builds on / diverges from
sources: []                      # URLs backing the hypothesis
trials_used: 0                   # trial-ledger entries this report consumed
verdict: ""                      # one line; copied into INDEX.md
---

# <Name> — <one-line idea>

## Hypothesis & market rationale
Why should this edge exist, economically? What inefficiency, who is on the other side?
State it falsifiably.

## Sources
Cited list. The backtester — not the source — is the arbiter.

## Relation to prior library work
Which entries does this build on, differ from, or risk repeating? If a related entry is
`tested-rejected`, state explicitly what is different and why the recorded failure mode
does not apply (required by spec 08 §4.3 — otherwise do not test).

## Strategy spec
Entry / exit / regime gate / session / params, precise enough to implement. Note which
params should become `ALLOWED_LEVERS` if promoted.

**Exit geometry (required — spec 08 §5.8):** state the **stop** as an ATR multiple
(~1.0–2.0; 1.2 carries no special status), the **target** R-multiple (R:R ≥ 1:1 floor;
1:2–1:3 preferred where a sub-50% win rate is expected), and a one-line rationale tying each
to *this* strategy's mechanism. Do NOT default to `1.2×ATR / 1R` by inheriting the incumbent
— justify the geometry, or say explicitly why the incumbent's single-1R machinery fits here.

## Implementation notes
Files touched (additive only), registry name, unit tests added. Confirm: pytest green,
no writes to `state/` or the live path. Live-mirror needed? (yes ⇒ flag for human session)

## Backtest results
Command used (incl. `--trials N`). Table vs every R6 gate + walk-forward + lockbox, and
an A/B vs the incumbent HEAD. Judge on gates + lockbox, never raw expectancy.

| metric | gate | candidate | incumbent HEAD |
|---|---|---|---|

## Verdict
Pass/fail per gate; decision; proposal filed (path) or not.

## Lessons
The field future triage reads. What did we learn about the market / the strategy family /
the process — even (especially) on rejection?

## Next steps
Follow-on ideas, queued variants, data needs.
