# Curated research sources

> Starting points for stage 2 of the research engine (spec 08 §2). Cayden-maintained —
> add new links freely; the engine reads this file every run alongside general web search.
>
> **Rules of use:** these are *hypothesis sources*, not verdicts — the backtester is the
> arbiter. Any strategy found here must be translated into a falsifiable EURUSD-M15 spec
> and re-implemented pure in our engine; **never copy community code into `src/`**
> (unaudited, wrong abstractions, license risk). Cite the exact repo + file/strategy name
> in the report's `sources:` frontmatter. Weigh evidence quality: paper-backed > backtested
> repo > community script.

## Strategy & idea catalogs (GitHub)
- [wangzhe3224/awesome-systematic-trading](https://github.com/wangzhe3224/awesome-systematic-trading)
  — curated libraries, papers, and strategy lists across FX/futures/crypto; good for
  discovering strategy *families* and the literature behind them.
- [paperswithbacktest/awesome-systematic-trading](https://github.com/paperswithbacktest/awesome-systematic-trading)
  — strategies paired with papers and backtests; the strongest evidence tier here — prefer
  entries that link a published paper.
- [pAulseperformance/awesome-pinescript](https://github.com/pAulseperformance/awesome-pinescript)
  — TradingView Pine community strategies. Large idea surface, **low evidence quality**
  (mostly unvalidated retail scripts): mine it for mechanisms (session logic, filters,
  exit ideas), never for claimed performance. FX/intraday entries are the relevant subset.
  (Local Pine collection: `docs/research/scripts/`.)

## GitHub topic crawls
Browse for active repos when the catalogs run dry — vary `l=` language filter:
- https://github.com/topics/technical-indicators
- https://github.com/topics/trading-strategies
- https://github.com/topics/algorithmic-trading
- https://github.com/topics/forex

## Academic / primary (from spec 08)
- SSRN (quantitative finance), arXiv q-fin.TR — preferred for testable, cited mechanisms.
- Practitioner blogs/forums, broker & quant publications.

## Tooling only — NOT idea sources
- [klinecharts/KLineChart](https://github.com/klinecharts/KLineChart) — lightweight
  charting library; useful if we ever build a visual report/dashboard, irrelevant to
  strategy hypotheses.
