# R4 — FTMO Rules & Risk Model: Findings

**Track:** R4 — FTMO rules & risk model
**Scope:** Exact FTMO 2-Step Challenge limit mechanics, forbidden-practice enumeration, and the deterministic position-sizing / kill-switch / request-budget / news-blackout math the Risk Governor must enforce.
**Research date:** 2026-06-02. **Rule version:** Current as of fetch. FTMO's *Trading Objectives* page was last modified **2026-05-13** (`meta-article:modified_time`), and the *Forbidden Trading Practices* page **2026-02-02** — so this captures the reported May-2026 revision. Re-verify both pages before each production deploy; FTMO changes them silently.

> **Terminology note.** FTMO now uses "Initial Simulated Capital" for what we call initial capital, "Maximum Daily Loss" for the daily limit, and "Maximum Loss" for the overall limit. The 2-Step product's two phases are the **FTMO Challenge** (Phase 1, 10% target) and **Verification** (Phase 2, 5% target). All quotes below are from FTMO's official pages.

---

## 1. Summary

For the **2-Step Challenge** on a $100,000 account, the Risk Governor must keep account **equity** above two floors at all times:

- A **daily floor** that resets each midnight Prague time: `daily_floor = balance_at_0000_CEST − 0.05 × InitialCapital`. On a $100k account that is a $5,000 daily drawdown budget, anchored to the day's **opening balance** (not opening equity), and it is checked against live **equity** (balance + open P/L). ([Trading Objectives][to])
- A **static overall floor**: `overall_floor = InitialCapital − 0.10 × InitialCapital = $90,000`. For the 2-Step this never moves during a phase — it is **static**, not trailing. (The 1-Step product uses an *end-of-day trailing* Max Loss; do not encode that one.) ([Trading Objectives][to])

Both limits are **equity-based**, so a deep open-trade drawdown breaches them even before you close. The governor's job is to make a breach *structurally impossible* by halting trading at a configurable fraction (recommended 60%) of the daily budget and capping aggregate open risk far below the overall budget.

The two formulas the engineer implements (derived in §6 and §7):

```
# Daily-loss breach test (must never be true)
breach_daily   = equity_now < (balance_at_0000_CEST − 0.05 * InitialCapital)
breach_overall = equity_now < (InitialCapital      − 0.10 * InitialCapital)

# Position size (lots), risk-per-trade off SL distance, kill-switch aware
risk_$        = risk_fraction * equity_now                     # e.g. 0.0035 * equity
risk_$        = min(risk_$, remaining_daily_budget_after_killswitch)
lots          = risk_$ / (SL_distance_in_pips * pip_value_per_lot * (1 + slippage_spread_buffer))
```

Recommended defaults: `risk_fraction = 0.0035` (0.35% equity), daily kill-switch at **60%** of the daily budget, `slippage_spread_buffer = 0.20`, and aggregate open risk capped at **2.0%** of equity. Concrete numbers are worked below.

---

## 2. Precise daily-loss mechanics (Maximum Daily Loss)

**Official definition.** "The **Maximum Daily Loss** rule establishes a limit … below which your account **equity** (i.e., **Balance** + Open Positions P/L ± Swaps – Commissions) cannot drop. If the equity drops below this limit, the rule is considered violated." ([Trading Objectives][to])

**How the limit is computed (2-Step, Max Daily Loss Amount = 5%):** ([Trading Objectives][to])

> "The Maximum Daily Loss Limit is recalculated daily at **00:00 CE(S)T** as the difference between: the **account balance recorded at 00:00 CE(S)T** of the current day, and the **Maximum Daily Loss Amount**, which is **5%** of the Initial Simulated Capital. On the first day of trading, the account balance used for this calculation is the Initial Simulated Capital."

Three things to lock in, because they are the most common source of accidental breaches:

1. **The limit's anchor is the day's opening *balance* (closed-trade equity), not opening equity.** Open floating P/L carried across midnight does **not** raise or lower the anchor — only realized balance does. ([Trading Objectives][to])
2. **The breach test compares that fixed anchor against live *equity*** (Balance + floating P/L ± swaps − commissions). So open-position drawdown counts immediately, intrabar, and can trigger a violation before any trade is closed. ([Trading Objectives][to], [Balance vs Equity FAQ][be])
3. **Reset is 00:00 CE(S)T** — Central European Time / Central European Summer Time, i.e. Prague. In June this is CEST = UTC+2. The governor must compute "today's anchor" using a Europe/Prague tz-aware clock, not server-local or UTC.

**Worked example ($100,000 account, FTMO's own numbers).** ([Trading Objectives][to])

| Day | Opening balance @ 00:00 CEST | Daily floor = balance − $5,000 |
|-----|------------------------------|--------------------------------|
| 1   | $100,000 (= Initial)         | **$95,000** |
| 2   | $102,000                     | **$97,000** |
| 3   | $101,000                     | **$96,000** |

So on Day 2, if equity ever touches $97,000 — whether from a closed loss or from open floating loss — the account is failed.

**Worked example showing open P/L counts.** Suppose on Day 2 the opening balance is $102,000, so the floor is $97,000. You open a position and never close it. If that position's unrealized loss reaches −$5,001 while open, equity = $102,000 − $5,001 = $96,999 < $97,000 → **breach**, even though balance is still $102,000 and you have closed nothing. This is exactly why the governor sizes positions and runs the kill-switch off **equity**, not balance.

**Balance vs equity, per FTMO:** ([Balance vs Equity FAQ][be])
- `Balance = deposits − withdrawals + realized net P/L` (closed trades only).
- `Equity = Balance + unrealized net P/L`.

---

## 3. Maximum (overall) loss mechanics

**2-Step is STATIC.** "The **Maximum Loss** rule establishes a **static** limit … The Maximum Loss Limit is calculated as the difference between the **Initial Simulated Capital** and the **Maximum Loss Amount**, which is **10%** of the Initial Simulated Capital." Worked: "Maximum Loss Amount = $10,000; Limit = **$90,000**." This applies to both phases of the 2-Step and to the subsequent FTMO Account (2-Step). ([Trading Objectives][to])

So for a $100k 2-Step account the overall floor is a flat **$90,000** for the entire phase, regardless of how much profit you bank. Like the daily rule, it is checked against **equity** (Balance + open P/L), so deep floating losses count.

**Contrast — do NOT encode the 1-Step version.** The 1-Step product's Maximum Loss is an **end-of-day trailing** limit: recalculated at 00:00 CE(S)T as `max(highest prior-day-close balance, Initial) − 10%`, can only ratchet up, never down, and resets only on reward withdrawal. ([Trading Objectives][to]) Our bot trades the **2-Step**, so the overall floor is the constant `0.9 × Initial`. Encoding the trailing version would wrongly tighten our floor as we profit. The governor should hard-code `overall_floor = 0.9 × Initial` and assert the product type is 2-Step at startup.

---

## 4. Forbidden trading practices (enumerated from the official page)

All of the following are quoted/paraphrased from FTMO's *Forbidden Trading Practices* page (modified 2026-02-02). "Simulated trading" is FTMO's term — the entire program is a simulated environment. ([Forbidden Trading Practices][fp])

1. **Feed/latency/price-error exploitation.** You must not "knowingly or unknowingly use trading strategies that exploit errors in our Services, such as errors in the display of prices or delays in their updates, or an external or slow data feed." → Encode: never act on a quote that diverges abnormally from a reference feed; never fire on stale ticks.
2. **Coordinated / opposite-position manipulation across accounts.** No "simulated trades or combinations of trades for manipulative purposes, for example by simultaneously entering into opposite positions" — explicitly including between connected accounts or accounts at other providers. Exception: opposing positions on a **single** account are allowed. → Encode: no cross-account hedging; one account per bot identity.
3. **Breach of platform / T&C.** No trades conflicting with FTMO General/Account T&Cs or the trading platform's terms.
4. **AI / ultra-high-speed / mass-entry abuse.** No "software, artificial intelligence, ultra-high-speed tools, or mass data entry that might manipulate, abuse, or give you an unfair advantage." (Automation/EAs per se are allowed; *abusive* automation is not — see the 2,000-request cap below.)
5. **Gap trading (the news + market-close rule — APPLIES DURING EVALUATION).** No opening simulated trades:
   - "when major global news, macroeconomic events, or corporate reports or earnings are **scheduled** and they might affect the relevant financial market"; **or**
   - "**two hours or less before** a relevant financial market is **closed for at least two hours**."
   → Encode as the news-blackout (§9) **and** a market-close blackout: do not *open* within 2h of a ≥2h market close (covers Friday pre-weekend close and session gaps).
6. **Non-replicable / reckless trading.** No trades that "contradict how trading is actually performed in the financial markets" or that could cause FTMO "financial, reputational, or other harm" — explicitly naming **overleveraging, overexposure, one-sided bets, account rolling**.
7. **Server-request hyperactivity — the 2,000/day cap.** No EAs/robots that make the account "hyperactive in the sense of an excessive number of **more than 2,000 server requests per day** on individual simulated trades or pending orders being **opened, modified, or closed**, causing overload of the trading server." → This is the hard number for the request budget (§8). The cap is **2,000 order-management requests per account per day**, counting opens + modifies + closes.
8. **Best Day Rule circumvention via spread/hedge tricks.** No "artificially distribut[ing] profit across multiple days without proportionally distributing market risk, such as hedging or holding opposing positions on the same or highly correlated instruments, or partially closing and managing the same trade idea across multiple trading days, in order to circumvent the **Best Day Rule**."
9. **Risk-management rules — no outsized / inconsistent sizing.** A "reasonable person" risk-management standard. Specifically avoid: "opening substantially **larger position sizes** compared to your other simulated trades"; opening a "substantially smaller or larger **number** of positions" than usual; and "repeated … activity that results in higher **Risk per Trade Idea**" → cumulative exposure in one symbol or correlated symbols. → Encode: a fixed/narrow risk-per-trade band (§6) and per-symbol/correlation exposure caps (§7) directly satisfy this.
10. **Personal-use / no third-party access.** Account is personal; no third party may trade it, and you may not trade others' accounts.

**The "Best Day" / 50% rule — which product?** FTMO's published consistency rule is the **Best Day Rule**: "your Best Day does not represent more than **50%** of your Positive Days' Profit," where Positive Days' Profit is the sum of closed P/L from all profitable days. The Trading Objectives page states this "applies to the **FTMO Challenge: 1-Step** as well as the **FTMO Account (1-Step)**." It is **not** listed among the 2-Step objectives. ([Trading Objectives][to]) The consistency FAQ confirms that, beyond the Trading Objectives, "there are no additional consistency requirements for your trading" provided risk management is sustainable. ([Consistency FAQ][cr]) **Conclusion for our 2-Step bot:** the 50% Best Day Rule is *not a pass/fail objective for us*, but forbidden-practice #8 still bans *artificially* spreading profit via hedging/correlated opposing positions, and #9 bans outsized lots. Treat "keep daily profits roughly even and never use an outsized lot" as a soft self-imposed constraint to avoid manual review flags, but it is not a hard 2-Step gate. (If we ever switch to 1-Step, the 50% rule becomes a hard gate — flag in config.)

### 4b. 2-Step vs 1-Step — the rules we must NOT cross-encode

| Rule | 2-Step (ours) | 1-Step |
|------|---------------|--------|
| Phase 1 / Phase 2 profit target | 10% then 5% | 10%, single phase |
| Max Daily Loss | **5%** of Initial, equity, anchored to opening balance | **3%** of Initial |
| Max (overall) Loss | **10% STATIC** (`0.9×Initial`, never moves) | **10% end-of-day TRAILING** (ratchets up) |
| Min trading days | 4 (each phase) | 4 |
| Best Day / 50% rule | **Not a 2-Step objective** | **Hard objective** |
| Trading period | Unlimited | Unlimited |

Sources for the table: ([Trading Objectives][to], [2-Step Challenge][ts]).

### 4c. News / overnight / weekend restrictions — when they actually bite

This is a subtle and important distinction. FTMO has **two different** news-related rules:

- **The gap-trading forbidden practice (§4 item 5)** — bans *opening* trades around scheduled major news and before long market closes. This applies **during the Evaluation** (Challenge + Verification) **and** on the funded account, regardless of account type, because it is a forbidden practice, not an account-type restriction.
- **The "news trading" account restriction (the 2-minute window)** — FTMO's *Can I trade news?* FAQ states news restrictions "apply only to the **Standard account type**," and "For Standard accounts, these restrictions apply **only once you start trading on an FTMO Account**. They do **not** apply during the Evaluation Process." The Swing account type has no news restriction. The same is true for the overnight/weekend holding restriction: Standard-only, funded-account-only, not during evaluation. ([Can I trade news? FAQ][news], [Overnight/weekend FAQ][ovn], [2-Step Challenge FAQ block][ts])

The widely-cited **2-minute window** (no opening/closing trades, and no SL/TP fills, on the targeted instrument from **2 minutes before to 2 minutes after** a selected high-impact release) is the **Standard funded-account** restriction. It kicks in only after we pass and are on a Standard FTMO Account (2-Step). ([Can I trade news? FAQ][news], corroborated by secondary summaries [TradingFinder][tf]).

**Design implication:** We will encode a news blackout (§9) **from day one** anyway, because (a) the gap-trading forbidden practice already bans opening into scheduled major news during the challenge, and (b) it future-proofs us for the funded Standard account's 2-minute rule. Use the wider, safer window during evaluation; tighten to the exact 2-min instrument-specific window only where we must allow trading.

---

## 5. The numbers, consolidated (what the governor hard-codes for a $100k 2-Step)

| Quantity | Value | Source |
|----------|-------|--------|
| Phase 1 profit target | +10% → $110,000 | [to] |
| Phase 2 (Verification) target | +5% → $105,000 | [to] |
| Max Daily Loss amount | 5% of Initial = $5,000/day | [to] |
| Daily floor (Day N) | `balance_open_N − $5,000`, vs equity | [to] |
| Max (overall) Loss | 10% static → floor **$90,000** | [to] |
| Min trading days | 4 per phase (a day = ≥1 position opened, 00:00–23:59:59 CEST) | [to] |
| Reset time | 00:00 CE(S)T (Europe/Prague) | [to] |
| Server-request cap | **2,000 / account / day** (open+modify+close) | [fp] |
| Trading period | Unlimited | [ts] |

---

## 6. Position-sizing formula (risk-per-trade, SL-based, equity-anchored)

**Goal:** each trade risks a small fixed fraction of *current equity*, sized so that if price hits the stop-loss the realized loss equals that budget, with an explicit buffer for spread + slippage so the *actual* loss never exceeds plan.

**Inputs**
- `E` = current account **equity** (Balance + open P/L), in account currency.
- `f` = risk fraction per trade. Recommend **f = 0.0035** (0.35%); band 0.25%–0.50% per the project philosophy.
- `SL_pips` = stop-loss distance from entry, in pips (or points for non-FX instruments).
- `V` = **pip value per 1.00 standard lot** in account currency for this symbol (e.g. ≈ $10/pip per lot for EURUSD on a USD account; must be looked up live per symbol from the platform's contract specs because cross/JPY/metal/index values differ).
- `b` = slippage+spread safety buffer, fractional. Recommend **b = 0.20** (inflate the planned loss by 20% so fills worse than the stop still stay inside budget).

**Per-trade dollar risk, clamped to the remaining daily allowance:**

```
risk_$_raw   = f * E
risk_$       = min( risk_$_raw, remaining_daily_budget )      # see §7 kill-switch
```

**Lots:**

```
                       risk_$
lots = ────────────────────────────────────────────
        SL_pips * V * (1 + b)
```

Then floor to the broker's lot step and enforce `lots ≥ min_lot`; if the rounded-down lots would be 0, **skip the trade** (do not round up — rounding up breaks the risk cap).

**Worked example.** EURUSD, USD account, `E = $100,000`, `f = 0.0035` → `risk_$_raw = $350`. `SL_pips = 20`, `V = $10/pip/lot`, `b = 0.20`.

```
lots = 350 / (20 * 10 * 1.20) = 350 / 240 = 1.458  →  round down to 1.45 lots
```

At 1.45 lots, a clean 20-pip stop loses `1.45 × 20 × 10 = $290`; the 20% buffer means even a fill ~24 pips beyond entry (4 pips of slippage+spread) still costs `1.45 × 24 × 10 = $348 ≈ planned $350`. Margin used at 1.45 lots EURUSD with 1:30 leverage ≈ `1.45 × 100,000 × 1.10 / 30 ≈ $5,317` — trivial against $100k equity, so leverage/margin is never the binding constraint here; the daily-loss budget is.

**Why off equity, not balance:** the daily and overall limits are equity-based (§2–§3). Sizing off equity means the budget automatically shrinks as the day's open drawdown grows, which is exactly the behavior that keeps us clear of the floor.

---

## 7. Kill-switch, daily-budget math, and concurrent-risk caps

### 7.1 Daily budget and the kill-switch threshold

FTMO's hard daily allowance is `0.05 × Initial` (= $5,000 on $100k). We must **never** approach it. Define a kill-switch fraction `k` (recommend **k = 0.60**) and operate against a *self-imposed* budget:

```
daily_floor_FTMO = balance_open_today − 0.05 * Initial          # the real failure line (equity < this = fail)
daily_loss_now   = balance_open_today − equity_now              # realized + unrealized loss since 00:00 CEST
daily_budget     = 0.05 * Initial                              # = $5,000
soft_budget      = k * daily_budget                            # = 0.60 * 5000 = $3,000 self-imposed cap

remaining_daily_budget = max(0, soft_budget − daily_loss_now)  # feeds §6 clamp
```

**Kill-switch trip:** when `daily_loss_now ≥ soft_budget` (i.e. equity has fallen `k × 5%` below the day's opening balance), the governor **halts all new entries and flattens or tightens open risk**, then stays flat until the next 00:00 CEST reset. On $100k this trips at a $3,000 daily loss — leaving a $2,000 (2%-of-Initial) cushion above the real $95,000 floor to absorb slippage, spread, and the gap between "decision to flatten" and "actually flat." A more conservative `k = 0.50` ($2,500 trip, $2,500 cushion) is recommended while the system is unproven.

A second, tighter **intratrade guard** should force-close positions if `equity_now` falls within a hard buffer (e.g. 1% of Initial = $1,000) of `daily_floor_FTMO` *or* `overall_floor`, regardless of the soft budget — this is the last line of defense against a fast spike.

### 7.2 Maximum concurrent open risk

Per forbidden-practice #9 (no cumulative over-exposure in a symbol or correlated symbols) and to stay clear of both floors, cap **aggregate open risk** (sum of each open position's distance-to-stop loss in dollars) at:

```
open_risk_$ = Σ (lots_i * SL_pips_i * V_i)         # planned loss if every open stop hits
constraint:  open_risk_$ ≤ 0.020 * E               # ≤ 2.0% of equity across ALL open positions
```

2.0% aggregate is well inside the 5% daily budget and miles from the 10% overall floor, even if every open stop hits at once. Additionally:
- **Per-symbol cap:** no single symbol > 1.0% of equity in open risk.
- **Correlation cap:** treat highly-correlated pairs (e.g. EURUSD/GBPUSD, or any pair sharing USD on the same side beyond a threshold) as one bucket for the per-symbol cap, to honor the "correlated symbols" clause.
- **No opposing correlated positions across the account family** (forbidden-practice #2, #8): the governor must reject an order that opens a position opposing an existing correlated one if the intent looks like hedging.

### 7.3 Max trades/day guidance

There is no FTMO cap on *number* of trades beyond the 2,000-request hyperactivity rule (§8) and the consistency expectation. To stay "reasonable" (forbidden-practice #9's "substantially larger/smaller number of positions"), keep trade count in a stable band day-to-day. A practical self-cap: **≤ 15–20 new trade *ideas* per day** and **≤ 5 concurrent open positions**, which combined with §8's cadence keeps requests an order of magnitude under 2,000.

### 7.4 Behavior at the 00:00 CEST reset

- Recompute `balance_open_today` and `daily_floor_FTMO` from the **Europe/Prague** clock at the exact rollover. Floating P/L on positions held across midnight does **not** reset the anchor (anchor = realized balance at 00:00). ([Trading Objectives][to])
- Re-arm the kill-switch (clear the daily halt) only at the verified rollover.
- **Min-trading-days bookkeeping:** a "trading day" counts only if ≥1 position is *opened* between 00:00:00–23:59:59 CEST. Track the count so the bot deliberately opens at least one (tiny, in-budget) position on ≥4 distinct days per phase even in a flat market. ([Trading Objectives][to])

### 7.5 Weekend / gap handling

- **Pre-weekend / pre-close blackout (forbidden-practice #5b):** do not *open* new positions within **2 hours** before any market close lasting ≥2 hours (covers the Friday FX close and instrument-specific session closes). Holding existing positions over the weekend is permitted during the Evaluation (the overnight/weekend restriction is Standard-funded-account-only), but Monday open gaps can blow through stops — so for a challenge-pass-focused bot, prefer flattening before the Friday close as policy, even though it is not strictly required during evaluation. ([Forbidden Trading Practices][fp], [Overnight/weekend FAQ][ovn])
- Because stops can gap, the §6 buffer `b` and the §7.1 hard buffer are the protection against weekend-gap overshoot of the daily/overall floors.

---

## 8. Request-budget design (staying under 2,000 server requests/day)

**The hard limit:** > 2,000 server requests/day (opens + modifies + closes of trades and pending orders) per account is the "hyperactive EA" forbidden practice. ([Forbidden Trading Practices][fp]) Treat **1,500/day as the self-imposed ceiling** (75% of cap) and alert at 1,200.

**Counting model.** Maintain a tz-aware (Europe/Prague) daily counter incremented on every order-management call the platform actually sends to the server:
- `OPEN` (market or pending) = 1 request
- `MODIFY` (change SL/TP/price of an existing order/position) = 1 request
- `CLOSE` / partial close / delete pending = 1 request
- Pure read/quote polling does **not** count (it is not an order action) — but avoid abusive polling anyway under forbidden-practice #4.

**Budgeting.** With ≤5 concurrent positions, the dominant consumer is **trailing-stop / SL modifies**. Each modify is a request. If you trail every position on every tick you will blow the budget fast on low timeframes. Cadence rules to enforce:

- **Trail on bar-close, not on tick.** On an M1 strategy, a single position generates ≤1 modify per minute → ≤1,440/day worst case for one position. With 5 positions trailing every M1 bar that is 7,200/day — **over budget**. Therefore:
- **Throttle modifies per position:** minimum interval between SL modifications of the same position = **`max(timeframe_seconds, 60s)`**, AND only modify when the new SL improves by ≥ a meaningful threshold (e.g. ≥ 0.3 × ATR or ≥ N pips), not on every qualifying bar. This "step trailing" cuts modifies by 5–10×.
- **Global rate limiter (token bucket):** allow at most `R` order-management requests per rolling minute, sized so `R × minutes_market_open_per_day ≤ 1,500`. For ~20 active FX hours/day → `R ≈ 1500 / 1200 ≈ 1.25/min`; round to a **2/min** bucket with a hard daily cap of 1,500. When the bucket/daily cap is exhausted, the governor **queues only risk-reducing actions** (closes, protective SL tightening) and drops cosmetic trailing.
- **Coalesce:** never send a modify that doesn't change the order materially; dedupe identical SL/TP writes.
- **Prefer fewer, wider trailing steps** over many tiny ones — this also reads as more "human/reasonable" under forbidden-practice #9.

This keeps a realistic low-timeframe bot (≤5 positions, step-trailed) comfortably in the 200–800 requests/day range, far under 2,000.

---

## 9. News-blackout design (deterministic "is major news imminent?")

**What FTMO requires.** During evaluation, the binding rule is the **gap-trading forbidden practice**: do not *open* trades when "major global news, macroeconomic events, or corporate reports or earnings are scheduled and they might affect the relevant financial market." On the funded **Standard** account, the additional **2-minutes-before / 2-minutes-after** instrument-level lockout (no open/close, and SL/TP fills in-window count as a breach) applies. ([Forbidden Trading Practices][fp], [Can I trade news? FAQ][news])

**Calendar source (deterministic feed).** Recommended ranked options:
1. **ForexFactory calendar** (scraped/parsed JSON) — the de-facto standard for impact ratings (high/medium/low) FX traders and most prop summaries reference; free, but unofficial/scrape-fragile. Good for the impact classification.
2. **Financial Modeling Prep (FMP) economic calendar API** — clean JSON, impact field, paid tiers, reliable for automation.
3. **Finnhub economic calendar** — JSON API, impact field, generous free tier; good primary for a deterministic check.
4. **Trading Economics calendar API** — authoritative, paid, includes country/importance; best if budget allows.
5. **FTMO's own Economic Calendar / News Indicator** — FTMO publishes an Economic Calendar and a free MT News Indicator that flags the events *they* police; use it to **align our event list with FTMO's**, since matching their classification is what actually matters for compliance. ([FTMO News Indicator blog][ni])

**Design (deterministic, no model in the live path):**
- Nightly, pull the next 24–48h of events; keep only **High-impact** events (and currency-relevant: an event in USD blacks out only USD-quoted/based instruments; EUR events black out EUR instruments, etc.). Persist `(event_time_utc, currency, impact)`.
- For each candidate symbol, derive the affected currencies; `is_blackout(symbol, now)` = true if any High-impact event for those currencies falls within the blackout window.
- **Blackout window:**
  - *Evaluation (challenge/verification):* be conservative — **no new opens from −5 min to +5 min** around each High-impact event (wider than the funded 2-min rule, to safely satisfy the broader "scheduled news" gap-trading wording and absorb calendar-time jitter). Optionally widen to −15/+5 for the highest-tier releases (NFP, CPI, FOMC/central-bank rate decisions).
  - *Funded Standard account:* enforce the exact **−2 min / +2 min** no-open/no-close window on the affected instrument, and additionally **do not leave an SL/TP that could fill inside the window** (move or remove it before the window, since an in-window fill is itself a breach).
- **Pre-close blackout** (same gap-trading clause): no new opens within **2h** of any ≥2h market close (Friday FX close, instrument session closes).
- Fail-safe: if the calendar feed is stale/unreachable, **default to blackout** (no new opens) rather than trading blind — deterministic and conservative.

---

## 10. Checklist of forbidden practices to encode as HARD checks

Each item below should be a deterministic guard in the Risk Governor with veto power over orders.

- [ ] **Daily-loss guard (equity):** reject/flatten so `equity_now ≥ balance_open_today − 0.05×Initial`; trip kill-switch at `k×5%` loss (k=0.60 default). Clock = Europe/Prague. ([to])
- [ ] **Overall-loss guard (equity, STATIC):** reject/flatten so `equity_now ≥ 0.90×Initial` at all times; assert product = 2-Step (do not use trailing 1-Step logic). ([to])
- [ ] **Per-trade risk band:** every order sized to `f×equity` with `f ∈ [0.0025, 0.0050]`; reject any order whose implied loss-at-SL exceeds the band (blocks "substantially larger lot" practice). ([fp] item 9)
- [ ] **Aggregate open-risk cap:** `Σ open risk ≤ 2.0% equity`; per-symbol ≤ 1.0%; correlated bucket ≤ 1.0%. ([fp] item 9)
- [ ] **No cross-account / opposing-correlated hedging:** one account per bot; reject opening a position that opposes an existing correlated one. ([fp] items 2, 8)
- [ ] **Server-request governor:** count opens+modifies+closes per Prague-day; hard stop at 1,500 (alert 1,200); never exceed 2,000. Token-bucket ~2/min; step-trailing only. ([fp] item 7)
- [ ] **News blackout (open):** no new opens within the §9 window around High-impact, currency-relevant events; default-to-blackout on feed failure. ([fp] item 5, [news])
- [ ] **Pre-close / weekend blackout:** no new opens within 2h of any ≥2h market close; flatten before Friday FX close as policy. ([fp] item 5b, [ovn])
- [ ] **No feed/latency exploitation:** reject ticks that deviate abnormally from a reference feed or are stale; never act on suspect quotes. ([fp] item 1)
- [ ] **No AI/HFT abuse signature:** enforce the request governor + reasonable trade-count band; no mass-entry bursts. ([fp] items 4, 9)
- [ ] **Min-trading-days bookkeeping:** ensure ≥1 in-budget position opened on ≥4 distinct Prague-days per phase. ([to])
- [ ] **Personal-use:** single operator/account; no third-party access. ([fp] item 10)
- [ ] **(If ever 1-Step) Best-Day 50% gate + 3% daily + trailing overall** — config-gated, OFF for 2-Step. ([to])

---

## 11. Open items / re-verification notes

- FTMO revised the Trading Objectives **2026-05-13**; re-fetch before deploy and on any FTMO "Trading Updates" notice. The static-vs-trailing distinction (2-Step static, 1-Step trailing) is the highest-risk thing to get wrong.
- The 2-minute funded news window and the precise list of "selected" high-impact events are defined in the FTMO Account Agreement / Standard-account terms and can change; align our calendar to FTMO's own Economic Calendar / News Indicator for the funded phase. ([news], [ni])
- Confirm the per-symbol `pip_value_per_lot V` and lot step **live from the platform contract specs** at runtime — these vary by symbol (JPY pairs, metals, indices) and by account currency; never hard-code $10/pip globally.

---

## Sources

- [Trading Objectives — FTMO (modified 2026-05-13)][to]
- [Forbidden Trading Practices — FTMO (modified 2026-02-02)][fp]
- [FTMO Challenge: 2-Step — FTMO][ts]
- [What is the difference between Balance and Equity? — FTMO FAQ][be]
- [Can I trade news? — FTMO FAQ][news]
- [Do I have to close my positions overnight or before the weekend? — FTMO FAQ][ovn]
- [Do you have any consistency rules? — FTMO FAQ][cr]
- [FTMO News Indicator (free MT tool) — FTMO blog][ni]
- [FTMO Rules 2026 (secondary corroboration of 2-min news window) — TradingFinder][tf]

[to]: https://ftmo.com/en/trading-objectives/
[fp]: https://ftmo.com/en/forbidden-trading-practices/
[ts]: https://ftmo.com/en/2-step-challenge/
[be]: https://ftmo.com/en/faq/what-is-the-difference-between-balance-and-equity/
[news]: https://ftmo.com/en/faq/can-i-trade-news/
[ovn]: https://ftmo.com/en/faq/do-i-have-to-close-my-positions-overnight-or-before-the-weekend/
[cr]: https://ftmo.com/en/faq/do-you-have-any-consistency-rules/
[ni]: https://ftmo.com/en/blog/do-you-want-to-keep-track-of-the-fundamentals-try-the-ftmo-news-indicator-free-for-metatrader/
[tf]: https://tradingfinder.com/props/ftmo/rules/
