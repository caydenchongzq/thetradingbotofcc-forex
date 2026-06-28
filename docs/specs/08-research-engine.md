# 08 — Automated Strategy Research Engine

> Implementation plan for a daily, autonomous strategy-research loop: an agent session that
> researches ideas online, recalls every past tested strategy from a knowledge base, decides
> *improve-existing vs build-new*, implements candidates dev-isolated, backtests them through
> the R6 harness, and files a citable report per candidate. Runs as a **Cowork scheduled
> task**. It extends spec 06's Strategy Researcher from *parameter tuning within
> `ALLOWED_LEVERS`* to *open-ended strategy R&D* — under the same governance.
>
> **Status:** planned 2026-06-07 (decisions: full pipeline dev-isolated; weekly trial cap
> raised 4→10 for ramp-up; daily run at 08:30 SGT). Not yet built — see §7.

## 0. What changes vs spec 06

Spec 06's loop tunes the *incumbent* strategy's allowed levers. This engine adds a fourth
agent role — the **Research Engine** — that may produce *structural* change: new indicators,
new `Strategy` implementations, new exit models. Everything downstream is unchanged: the
backtester is still the arbiter, the trial ledger still counts every hypothesis, promotion is
still human-only through the `ConfigStore`. The Research Engine's authority ends at a report
+ a dev-registered strategy + (if gates pass) a proposal. It can never promote, never touch
HEAD, never alter the live path.

| | Spec 06 Researcher | 08 Research Engine |
|---|---|---|
| Scope | param diffs within `ALLOWED_LEVERS` | new strategies / indicators / exit models |
| Inputs | journal drift flags, backtests | + online sources, + strategy knowledge base |
| Output | proposal JSON | report in library + dev code + tests (+ proposal if passed) |
| Cadence | weekly / drift-triggered | daily (1–2 candidates), dialed down later |
| Promotion | human | human (unchanged) |

## 1. Goals & non-goals

**Goals**
1. One scheduled session per day researches strategy ideas from online sources and the
   internal knowledge base, and takes **1–2 candidates** through implementation + full
   walk-forward backtest, each ending in a detailed report.
2. Every researched/tested strategy is **documented for recall**: future sessions read the
   library first, so ideas build on (or consciously diverge from) past work instead of
   re-testing it.
3. Candidates may be improvements to existing strategies *or* entirely new strategies with
   no reference to the incumbent.
4. Cadence is a dial (daily → lower frequency later) changed only in the scheduled task.

**Non-goals**
- No auto-promotion, ever. Passed candidates wait for Cayden.
- No changes to the live path (`run.py`, `decide.py`, broker adapter) inside a research run.
  If a candidate needs live-path mirroring (new manage semantics), the report flags it for a
  dedicated human-supervised session (CLAUDE.md invariant 3).
- No new data feeds initially: research is bounded by `state/parquet/eurusd_m15.parquet`.
  Ideas needing other instruments/timeframes/tick data are recorded as `blocked-on-data`.

## 2. The daily run — pipeline

Each run is a **fresh agent session** (per the standing workflow) whose prompt points at
CLAUDE.md + this spec. Stages:

```
0 orient   read CLAUDE.md, this spec, library INDEX, ledger budget remaining
1 recall   read relevant past reports (statuses, failure modes, lessons)
2 research web-search 3–5 idea candidates with citations. Start from the curated
           source list `docs/research/strategies/SOURCES.md` (GitHub strategy catalogs,
           topic crawls) plus academic preprints (SSRN/arXiv q-fin), practitioner
           forums/blogs, broker/quant publications. Community code is hypothesis-only:
           re-implement pure, never copy into src/
3 triage   dedupe vs library; classify each idea:
             (a) improvement to an existing strategy (lever change or structural)
             (b) variant of a past-rejected idea  → MUST state what is different and why
                 the recorded failure mode no longer applies, else discard
             (c) new strategy family
           select 1–2 within remaining trial budget; queue the rest as status: idea
4 build    dev-isolated implementation (rules in §5): pure indicator(s) →
           Strategy module → register() → unit tests → pytest green
5 validate py scripts/run_backtest.py --strategy <Name> --walkforward --trials <cumulative>
           + A/B vs current HEAD (compare_exits.py pattern). Judge on gates + lockbox,
           never raw expectancy (docs/EXIT_MODEL.md precedent). ALSO verify the entry is
           LIVE-FILLABLE — the backtest fill must be one the live path can place (market, or
           a resting-stop OCO filled on an intrabar touch); a stop confirmed at the close but
           filled at the level is NOT live-placeable (retcode 10015). docs/RESTING_STOP_FIX.md
           precedent: that unfillable fill made the incumbent look +0.391R when both live fills
           lose. An entry whose edge needs a better fill than a live order gets = REJECT.
6 report   write library report (template §3), update INDEX.md, append trial ledger
           entry; if ALL gates pass → write proposal JSON to config/proposals/
7 handoff  git commit (code + tests + docs), summary message to Cayden;
           passed candidates highlighted for human review
```

Timebox: if a walk-forward won't finish in-session, report partial results, mark the entry
`in-progress`, and let the next run resume it (counts as the same trial, not a new one).

## 3. Knowledge base — the strategy library

**Location:** `docs/research/strategies/` (sibling of the R1–R8 tracks).

- `INDEX.md` — one line per entry: `id · name · family · status · one-line verdict · link`.
  This is the recall surface every run loads first; keep it terse.
- `TEMPLATE.md` — the report template below.
- `YYYY-MM-DD-<slug>.md` — one report per researched candidate.

**Report frontmatter (machine-readable):**

```yaml
---
id: 2026-06-08-asian-range-fade
name: AsianRangeFade
family: mean-reversion        # breakout | mean-reversion | trend | exit-model | filter | other
status: tested-rejected       # idea | blocked-on-data | in-progress | tested-rejected |
                              # tested-passed | promoted | retired
related: [2026-06-07-tp-2r-sweep]   # library ids this builds on / diverges from
sources: ["<url>", "<url>"]
trials_used: 1                # ledger entries this report consumed
verdict: "failed DSR (0.71) and lockbox PF 0.9; chop edge does not survive costs"
---
```

**Report body sections (all required for tested candidates):** Hypothesis & market rationale
· Sources (cited) · Relation to prior library work · Strategy spec (entry/exit/regime/params)
· Implementation notes (files, registry name) · Backtest results vs every R6 gate +
walk-forward + lockbox (table) · A/B vs incumbent HEAD · Verdict · **Lessons** (the field
future triage reads) · Next steps.

**Backfill (M1):** seed the library so day one has memory: `SessionBreakoutER` (incumbent,
`promoted`), the full exit model (`tested-rejected`, from `docs/EXIT_MODEL.md`), the ≥2R TP
sweep (`tested-rejected`, from `docs/TP_2R_SWEEP.md`).

## 4. Governance changes

1. **Weekly trial cap 4 → 10** for the ramp-up phase (revisit after ~4 weeks, see M5).
   Implemented as the budget parameter fed to `TrialLedger.budget_remaining` in
   `src/agents/loop.py` / `scripts/process_proposal.py` — make it a config value
   (`improvement.weekly_trial_cap`), not a constant.
2. **DSR stays honest.** Every backtested candidate appends to the ledger and the
   *cumulative* count (40 as of 2026-06-07) keeps feeding `--trials`. Param sweeps inside a
   candidate count every combo (as `optimize.py` already enforces). The bar rises as we
   spend — that is the point; the mitigation is triage quality, not accounting.
3. **Rejection memory is binding.** Re-testing an idea whose family + failure mode is already
   recorded, without stated differentiation, is forbidden — it burns DSR budget for nothing.
4. **Lockbox stays sealed.** The research engine never tunes on, or reports against, the
   lockbox window beyond the harness's own final verdict.

## 5. Safety invariants for autonomous dev work

The engine writes code, so the dev-isolation rules from CLAUDE.md are tightened:

1. **Registry-only, never promoted.** New strategies enter via `register()` in
   `src/engine/registry.py` and are run with `--strategy`/`--config-file` only. Live builds
   from the ConfigStore HEAD, so an unpromoted strategy cannot trade — preserve this by
   never writing to `state/config/` or calling `ConfigStore.promote`.
2. **Additive-only edits to shared modules** (`indicators.py`, `registry.py`): new pure
   functions and one `register(...)` line. Never modify the incumbent strategy class in
   place — subclass or new module.
3. **Full `python -m pytest -q` green** before any report claims a result. New code ships
   with unit tests under `tests/engine` / `tests/backtest`.
4. **No live-path edits** (`run.py`, `decide.py`, execution, risk). Candidates whose exit /
   management semantics differ from the engine-only seam get `status: tested-passed` +
   an explicit *"needs live-mirror session before promotion"* flag in the report.
5. **Fail safe in research too:** any ambiguous data/tooling state ⇒ stop, report what
   happened, leave the repo green. Never force-push, never rewrite history; one commit per
   run on the working branch.
6. **Citations required** for every online claim; the backtester — not the source — is the
   arbiter of whether the idea is real.
7. Sandbox note: long walk-forwards may need chunked execution (known environment
   constraint); prefer resumable, bounded runs over one giant invocation.
8. **Exit geometry is chosen per mechanism, never defaulted.** A new candidate's stop width
   and reward target are design decisions that must follow from *its own* mechanism and be
   justified a priori — not copy-pasted from the incumbent. The reflex of `stop 1.2×ATR,
   single 1R target` is forbidden as an unexamined inheritance: 1.2×ATR carries no special
   status (a stop that tight noise-outs trades on some mechanisms; give the trade room when
   the structure warrants). Pre-register, in the report's Strategy spec, three things with a
   one-line rationale each: (a) the **stop** as an ATR multiple in the range ~1.0–2.0; (b) the
   **target** R-multiple giving **R:R ≥ 1:1** (1:1 floor; 1:2–1:3 preferred where the
   mechanism implies a sub-50% win rate, e.g. fades/sweeps); (c) why this geometry fits *this*
   strategy. Reusing the validated single-1R exit machinery is allowed only with an explicit
   "why 1R fits here" — never by default. Exit-geometry choices remain subject to the arbiter:
   the gates + walk-forward + lockbox decide, and the recorded ≥2R rejections on the incumbent
   ([[2026-06-07-tp-2r-sweep]]) bind any variant that shares their failure mode (§4.3).

## 6. Scheduled task

- **Cadence:** daily **08:30 SGT** (00:30 UTC) — after NY close, before London open, so
  backtests never compete with the live engine and the report is ready in the morning.
- **Prompt skeleton:**

  > Run the daily strategy-research cycle for the FTMO EURUSD bot per
  > `docs/specs/08-research-engine.md`. Read `CLAUDE.md` and
  > `docs/research/strategies/INDEX.md` first. Check remaining weekly trial budget
  > (cap 10) before selecting candidates. Take 1–2 candidates through stages 0–7. Never
  > promote; never touch `state/`; keep pytest green; end with a summary of verdicts and
  > anything awaiting my approval.

- **Frequency dial:** later reduce to e.g. 2–3×/week by editing the scheduled task only.
- The existing weekly auto-sweep task (param optimization) stays separate — it tunes the
  incumbent; this task researches structure. Both draw from the same trial budget.

## 7. Build plan

| # | Milestone | Work | Done when |
|---|---|---|---|
| M1 | Library scaffold | `docs/research/strategies/` + `INDEX.md` + `TEMPLATE.md`; backfill the 3 seed entries (§3) | INDEX lists 3 entries with correct statuses |
| M2 | Run brief | finalize this spec; add row 08 to `docs/specs/README.md`; (optional) add a `RESEARCH_ENGINE` AgentSpec in `src/agents/specs.py` for Phase-C parity | a fresh session given only the prompt in §6 can execute stages 0–7 |
| M3 | Governance | weekly cap → config value (default 10); confirm `process_proposal.py` / `optimize.py` read it; unit test budget math | cap change is one config edit |
| M4 | Schedule + dry run | create the Cowork scheduled task; run one **supervised** end-to-end cycle (research → build → backtest → report) and fix friction | one real library report produced by the loop |
| M5 | Review (after ~2 weeks) | check trial burn vs DSR bar, report quality, repo hygiene; decide frequency reduction and whether any agent step needs tightening | documented decision in this spec's changelog |

**Acceptance criteria:** (a) two consecutive unsupervised runs each produce a complete,
cited report with a gate-table verdict; (b) zero writes to `state/` or the live path across
those runs; (c) pytest green after each run; (d) a third run demonstrably *recalls* a prior
report in its triage (cites it in "Relation to prior work").

## 8. Risks

- **DSR burn-down.** ~10 trials/week raises the deflated-Sharpe bar quickly on one dataset.
  Counters: hard triage (most ideas die at stage 3 for free), longer history export, and
  eventually a second instrument (backlog #4) to widen the data, not the trial accounting.
- **Idea quality < idea volume.** Daily cadence can devolve into noise. The rejection-memory
  rule (§4.3) and the `idea` queue (triage without testing costs nothing) are the pressure
  valves; M5 exists to cut frequency if reports get thin.
- **Repo rot from autonomous commits.** Bounded by §5 (additive-only, tests green, one
  commit per run); the human review of passed proposals doubles as code review cadence.
- **Compute/timeouts.** Walk-forward on M15 is tractable but chunk long sweeps (§5.7);
  partial runs resume rather than re-trial.

## Changelog
- 2026-06-07 — initial plan (Cayden decisions: full dev-isolated pipeline; cap 10/week;
  daily 08:30 SGT).
- 2026-06-07 — **M1–M4 built.** Library scaffolded at `docs/research/strategies/`
  (INDEX + TEMPLATE + 3 seed backfills); `RESEARCH_ENGINE` AgentSpec added to
  `src/agents/specs.py`; weekly cap moved to `config/default.yaml`
  (`improvement_loop.trial_budget_per_week: 10`, read by `process_proposal.py`, unit
  tested); pipeline mechanics smoke-tested (214 tests green, `--list-strategies` OK).
  Scheduled tasks created: `ftmo-research-engine` (daily 08:30 SGT) and one-shot
  `ftmo-research-engine-m5-review` (2026-06-21). First scheduled run 2026-06-08 — treat
  it as the supervised M4 dry run. Note: Mondays overlap the `weekly-strategy-optimizer`
  task (08:00); both draw from the same trial budget.
- 2026-06-21 — **M5 review complete** (this scheduled, unsupervised run; Cayden not present —
  recommendations below await his explicit confirmation, nothing enacted).
  - **Acceptance criteria met.** Consecutive unsupervised runs each produced complete, cited
    reports with gate-table verdicts; zero writes to `state/` (verified: no `state/` commits
    since 2026-06-08); no live-path edits; **full pytest green (393 passed, 2 skipped)**; later
    runs demonstrably recall prior reports (every report carries a `related:[...]` chain and an
    explicit "Relation to prior work" — e.g. 06-20 follow-through cites the 06-15 market-fill
    finding and the 0/2 prior exit-models).
  - **Trial burn vs cap & DSR.** Burn is **well under the 10/week cap**: W24 ≈ 7 research
    trials, W25 = 5 (06-15/16/18/20/21), with ≥2 ideas/week killed at triage for **zero** trial
    cost (06-17 seasonality, 06-19 false-break-fade — probe-rejected, no ledger entry). The cap
    is **not the binding constraint**; triage quality is. Cumulative trials ≈ **170**, so the
    DSR bar on the single EURUSD-M15 dataset is now high and rising — every further trial on the
    same data tightens it (spec §8 risk, materializing as designed).
  - **Report quality: high.** Machine-readable frontmatter, 5 cited sources each, full required
    sections (Hypothesis/Sources/Relation/Spec/Results-vs-gates/A-B/Verdict/**Lessons**/Next),
    and strong cross-recall. The rejection-memory rule (§4.3) is being honoured (families marked
    closed; variants must state differentiation).
  - **Yield.** Of ~13 candidates since 06-08, **zero promotable**: 1 passed-but-dominated
    (SecondEntryORB), 1 dominates-HEAD-on-quality-but-fails-the-200-trade-floor (TrendAlignedORB,
    the **strongest re-test-on-longer-data candidate**), rest rejected. Families now broadly
    closed under live-faithful fills: directional breakout, mean-reversion (0/4), trend (0/3),
    exit-model (0/4, fill-anchored 06-21 added), fixed-time seasonality. Remaining open space = incumbent-FILTER candidates
    (all 200-trade-floor-bound on current history) and the real lever, a **longer data export /
    second instrument** (§8 backlog #4).
  - **Repo-hygiene flag (for Cayden, not auto-fixed).** Working tree is dirty in a way one-commit-
    per-run should prevent: the 06-18/06-19 reports, `strategy_nr7_breakout.py`, its test, and
    `config/dev/nr7_breakout.yaml` appear as **both staged deletions and untracked files**, with
    `indicators.py` modified-in-index-and-tree and four untracked `PROMOTION_BRIEF_*` files — an
    interrupted/aborted commit. pytest is green and no `state/`/live-path writes occurred, so no
    invariant is breached, but the index should be cleaned up manually.
  - **Recommendation (awaiting Cayden's OK — NOT applied):**
    (1) **Reduce cadence daily → 3×/week** (e.g. Mon/Wed/Fri) by editing only the
    `ftmo-research-engine` cron (`30 8 * * *` → `30 8 * * 1,3,5`). Rationale: the idea space is
    largely exhausted on current data, most runs now yield probe-rejections or floor-blocked
    filters, and slowing trial accrual protects the rising DSR bar for higher-conviction
    candidates. (2) **Keep the weekly cap at 10** — unchanged. It is already non-binding (burn
    4–7) and becomes doubly so at 3×/week; the limiter is triage, not the cap. (3) **Unblocking
    action for Cayden:** prioritise a longer-history and/or second-instrument export (§8 #4) —
    it would revive TrendAlignedORB and the incumbent-filter queue (which must be re-based on the
    **market-fill** incumbent, base −0.024R, not the level-fill artifact). No config/schedule
    changed in this session per the M5 task's standing constraint.
