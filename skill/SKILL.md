---
name: layer-0-news-triage
description: Triage a batch of news items through a four-layer market signal framework (geopolitical, macro, credit/sector, options microstructure), classify each by market relevance, map to affected tickers against a portfolio, generate explicit causal chains, and propose a trade stance (probe / full / stand down) consistent with a Kelly-plus-entropy sizing discipline. Use this skill whenever the user pastes headlines, provides a JSON batch of news, asks which news affects their portfolio, mentions "Layer 0 triage", "news feed filter", "market-relevant news", "news impact on my positions", or any variation — even if they don't explicitly name the framework. Also use when a caller provides a batch of news for downstream notification routing.
---

# Layer-0 News Triage

Process a batch of news items through a disciplined four-layer signal framework, map each relevant item to affected tickers, walk the causal chain explicitly, and propose a trade stance.

This skill is **decision support within a pre-defined framework**. It applies the user's existing doctrine mechanically to news. It does not invent new recommendations, override the user's sizing rules, or produce advice outside the framework. The final trading decision is the user's.

---

## Inputs

Accept either:

1. **JSON batch** — array of news items. Minimum required field: `title`. Optional: `id`, `source`, `url`, `timestamp`, `body`, `tickers_mentioned`. If no `id` is provided, assign sequential IDs.

2. **Pasted text** — plain headlines, one per line. Treat each line as a separate item with title only.

Optional side inputs:
- **`portfolio.json`** — `[{ticker, position_usd, cost_basis, thesis}]`. The `thesis` field may contain flags like "legal risk", "accumulating credit stress", "accounting" — treat these as Layer 2 overrides.
- If no portfolio is provided, load `assets/macro_fallback_watchlist.json`.

If the input is ambiguous (pasted mix of commentary and headlines), extract the headline-like lines and ignore the rest. Do not ask for clarification unless the input is genuinely undecipherable.

---

## The four-layer framework

Every relevant item maps to one or more layers. Layers are not mutually exclusive — a single headline can carry Layer 0 and Layer 1 implications simultaneously (e.g., "OPEC+ surprise cut" is both geopolitical and macro-regime).

**Layer 0 — Geopolitical.** State actors, conflict and diplomacy, commodity supply chain events, sanctions, regulatory or legal actions against specific entities. Leading indicator. Hardest to front-run because causal chains in novel situations resist pattern-matching.

**Layer 1 — Macro regime.** Rate decisions, yield curve shifts, dollar moves, real rates, credit spread regime changes, central bank language. News here moves the regime frame that governs all positioning.

**Layer 2 — Credit & sector.** Company-specific credit stress, insider cluster signals, sector rotation catalysts, legal/accounting risk on individual names. This layer produces **overrides** — Layer 2 red flags gate the bias from other layers.

**Layer 3 — Options microstructure.** Earnings pinning, gamma walls, unusual flow, dark pool prints, implied volatility regime shifts. News here moves dealer positioning and mechanical hedging pressure.

---

## Relevance scoring (0–10)

- **9–10** — Direct actionable event. Central bank decision, war start/end, major legal ruling, earnings surprise with guidance change, commodity supply rupture.
- **7–8** — Meaningful shift in a priced variable. OPEC rumor with sourcing, credit spread regime move, sanctions escalation, executive departure at a held name.
- **4–6** — Thematic or contextual. Candidate statements, diplomatic meetings, analyst forecasts that move consensus, sector rotation narratives.
- **0–3** — Noise. Recycled facts already priced, clickbait, political noise without policy implication, celebrity news, filler.

Return only items scoring ≥ 4 in the detailed output. Items below 4 go to `noise_items` as IDs only.

### Confidence rubric

The `confidence` field is separate from `relevance_score` — relevance asks "does this matter to markets", confidence asks "how sure is the directional read". Anchor points:

- **0.2–0.3** — weak signal: rumor-stage, forward-looking only, or single-layer with low specificity
- **0.4–0.5** — borderline: genuine event but ambiguous direction, or forecast-dependent
- **0.6–0.7** — typical strong signal: clean causal chain with one or two layers confirmed
- **0.8** — strong confluence: multiple layers align and causal chain is tight
- **0.9+** — rare: full four-layer confluence plus confirming price action. Reserved for events where the skill would be surprised by any other outcome.

Mandatory caps:
- `flags` includes `low_specificity` → confidence capped at 0.4
- `flags` includes `forward_looking_only` → confidence capped at 0.5

---

## Same-theme auto-merge

Two or more headlines in the same batch merge into a single `relevant_items` entry when any of the following applies:

1. They describe the **same underlying event** reported by multiple sources (existing duplicate case).
2. They describe a **primary event and its direct market reaction** — e.g., "Fed minutes show dovish dissent" + "DXY falls to 14-month low on rate-cut bets" are one item (the second is the first's market reaction). Similarly "Hormuz shipping normalizes" + "Brent -4%" merge.
3. They describe the **same policy signal from the same actor** restated across wires.

When merging:
- Choose the most concrete and causally-upstream headline as the canonical `headline`.
- List all contributing IDs in `source_ids`.
- Combine causal chains; keep the most mechanistic version.
- Add `duplicate_merged` to `flags`.
- Relevance score is the max of the contributing items, not the sum.

Do **not** merge:
- Different companies in the same sector (AMAT and LRCX earnings are separate items).
- Same-direction signals from independent actors (Fed dovish + ECB dovish are separate — independent policy signals, not one event).
- Same-direction signals with different mechanisms (oil up from OPEC cut + oil up from hurricane are separate).

Test: *if the second item would not exist without the first, or if they are two reports of the same event, merge. If the second item has its own independent causal footprint, keep separate.*

---

## Ticker mapping

For each relevant item:

1. **Walk the causal chain explicitly.** Minimum three steps. Event → mechanism → market impact.
2. **Name primary tickers** — direct, first-order impact. Maximum 5.
3. **Name secondary tickers** — second-order, correlation-derived. Maximum 5.
4. **Mark portfolio membership** — each ticker gets `in_portfolio: true/false` from the provided portfolio. If no portfolio, all are `false`.
5. **Rank by signal strength**, not alphabet. The strongest causal link is first.

### Good causal chain (from the user's framework)

> Venezuela political development → incumbent administration momentum → shifted probability of Iran confrontation → Strait of Hormuz tension premium → oil complex bid → XOM, MPC long

Three causal hops minimum, each with a named mechanism.

### Bad causal chain (reject this pattern)

> Oil news → oil up → buy XOM

Two hops, no mechanism, tautological.

If a chain has fewer than three genuine mechanistic hops, mark the item `low_specificity` and cap its confidence at 0.4.

---

## Sizing doctrine — stance, not size

The user's sizing formula is **Kelly × (1 − normalized_entropy) × P(regime)**. This skill cannot compute Kelly (needs edge/variance) or regime probability (needs HMM state). It therefore outputs a **stance**, selected from four options based on both holding state and signal strength:

- **`probe`** — holding state: flat or small. Action: initiate a small exploratory position. Default for Layer 0 signal alone, or Layer 0 + Layer 1 confluence. The framework's two-stage entry doctrine explicitly requires this: *small position on Layer 0 signal, scale on order flow confirmation*.

- **`full`** — holding state: flat or probing. Action: initiate full-size position. Requires multi-layer confluence (≥3 of 4 layers aligned, via the meta-rule in `references/causal_chain_examples.md`). Rare from news alone.

- **`reduce`** — holding state: held position. Action: actively take risk off (partial trim, full exit, or hedge). Use when a held position faces an adverse catalyst, support/structure break, or thesis invalidation. Distinct from `stand_down`: `reduce` is an active risk-reduction instruction on an existing exposure.

- **`stand_down`** — holding state: flat. Action: do nothing / do not initiate. Use when the signal is ambiguous, regime entropy is high, or a Layer 2 override blocks the otherwise-bullish stance. Distinct from `reduce`: `stand_down` means "don't touch", `reduce` means "actively take something off".

### Selection logic

```
IF ticker in portfolio AND catalyst is adverse to existing position:
    stance = "reduce"
ELIF layer_2_override fires on the bullish side:
    stance = "stand_down"  (regardless of holding state; existing position is governed by its own plan, not this headline)
ELIF confluence ≥ 3 layers AND holding is flat/probe:
    stance = "full"
ELIF signal is clean AND holding is flat:
    stance = "probe"
ELSE:
    stance = "stand_down"
```

Edge case: when a held position gets a **bullish** confirming catalyst that does not trigger confluence for `full`, prefer `probe` only if the user is still scaling in; otherwise the correct output is no stance change (stance `hold`, or omit the held ticker from `affected_tickers` if the news is not incrementally actionable). Do not invent `full` to justify action.

### Layer 2 override rules

If `portfolio.json` has a `thesis` field containing any of: `legal risk`, `credit stress`, `accounting`, `regulatory investigation`, `going concern`, `accumulating risk` — then **any** bullish news on that ticker flips the stance to `stand_down` with an explicit override note. Bearish news on a Layer-2-flagged name is allowed to remain `probe` (short side).

Always populate the `overrides` array when an override fires.

---

## Output format

Emit exactly one JSON object per batch. When responding in chat (not as a pure API call), also render the `summary_markdown` inline so the user can read it without parsing JSON.

### Top-level schema

```json
{
  "processed_at": "2026-04-21T14:32:00Z",
  "batch_size": 42,
  "portfolio_used": "provided | fallback",
  "relevant_items": [ /* see per-item schema */ ],
  "noise_items": ["id4", "id11", "id17"],
  "summary_markdown": "..."
}
```

### Per-item schema

```json
{
  "id": "item-03",
  "headline": "Fed holds rates, signals two cuts by year end",
  "relevance_score": 9,
  "layer_classification": ["macro", "microstructure"],
  "affected_tickers": [
    {"ticker": "TLT", "direction": "bullish", "order": "primary", "in_portfolio": false},
    {"ticker": "PLD", "direction": "bullish", "order": "primary", "in_portfolio": false},
    {"ticker": "DXY", "direction": "bearish", "order": "primary", "in_portfolio": false}
  ],
  "causal_chain": [
    "Fed pivots dovish in dot plot",
    "Real rate expectations decline; DXY softens",
    "Duration-sensitive assets bid; REITs, long bonds, gold benefit"
  ],
  "directional_bias": "bullish duration / rate-cut beneficiaries",
  "confidence": 0.75,
  "sizing_recommendation": {
    "stance": "probe",
    "rationale": "Macro regime shift confirmed, but requires Layer 3 positioning confirmation before full size. Stances: probe | full | reduce | stand_down.",
    "overrides": []
  },
  "flags": [],
  "reasoning": "One-paragraph synthesis tying the causal chain to the stance."
}
```

### summary_markdown structure

Render it tier-ordered, scannable in 10 seconds:

```
**HIGH PRIORITY (≥7)**
- [headline] → [tickers] → [bias] — stance: [probe/full/reduce/stand_down]
  └ [one-line override note if any]

**WATCH (4–6)**
- [headline] → [tickers] → [bias]

**SYNTHESIS** (only when confluence trigger fires — see below)
[2–4 sentences naming the regime, listing confirming items, calling out affected portfolio positions, and stating what the cross-item pattern implies beyond any single item]

**NOISE FILTERED** — 23 items
```

Never include items with `relevance_score < 4` in `summary_markdown`.

### Synthesis trigger

Append a **SYNTHESIS** section to `summary_markdown` whenever ≥3 items in `relevant_items` share a directional bias. "Share a directional bias" means: same primary ticker trending same direction across items, OR items mapping to the same macro theme with same-direction impact (e.g., three items that all imply rate-cut beneficiaries). The synthesis should:

- Name the regime or theme in plain language
- List which items are confirming it (by id or headline fragment)
- Identify which portfolio positions are most affected
- State what the cross-item pattern implies beyond any single item (e.g., "trim becomes time-critical", "radar-name initiation moment")

Keep the synthesis to 2–4 sentences. This cross-item pattern is the highest-value output when it fires — it is what a human analyst would naturally produce, and making it explicit is the point.

When no confluence trigger fires, omit the SYNTHESIS section entirely; do not pad.

---

## Anti-patterns — reject these

- **Fabricating ticker impact from vague headlines.** "Markets on edge" without a named mechanism → noise.
- **Proposing `full` stance from Layer 0 alone.** The framework prohibits it. If tempted, downgrade to `probe`.
- **Ignoring `portfolio.json`.** If MPC is held and an oil-supply story breaks, the item's affected_tickers must mark MPC as `in_portfolio: true`.
- **Restating the headline as the causal chain.** The chain is the mechanism, not the event.
- **Generic hedging language.** "This could impact markets" is not analysis. Either specify the mechanism or mark as noise.
- **Swallowing Layer 2 overrides.** If a portfolio thesis flags legal/credit risk on a name, bullish news on that name does NOT translate to a bullish stance. It becomes `stand_down` with the override documented.
- **Overcounting duplicates.** Same event across sources → one `relevant_items` entry. Same-theme auto-merge also applies (see the "Same-theme auto-merge" section); if merging is appropriate, do it — don't list Fed minutes and its DXY reaction as two items.

---

## Edge cases

- **Empty batch** → return `{batch_size: 0, relevant_items: [], noise_items: [], summary_markdown: "Empty batch."}`
- **All noise** → `relevant_items: []`, populated `noise_items`, markdown says "No market-relevant items in this batch."
- **Single ambiguous headline** → if score is borderline (4–5) and causal chain is weak, include it but set `flags: ["low_specificity"]` and cap confidence at 0.4.
- **Duplicate story across sources** → merge into one item, list all source IDs in a `source_ids` array on that item.
- **Headline in a language the user does not operate in (non-English)** → only include if the event is major and widely-covered; note language in `flags`.

---

## References

- `references/causal_chain_examples.md` — 10+ worked examples of good vs bad causal reasoning across all four layers, drawn from the user's framework.
- `references/output_schemas.md` — formal JSON schema with all optional fields, validation rules, and error responses.
- `assets/macro_fallback_watchlist.json` — default watchlist (energy majors, rate-sensitive REITs, broad sector ETFs) when no portfolio is provided.
- `assets/portfolio_example.json` — example portfolio structure with thesis flags, for the user to copy and adapt.

Consult the references when: (a) a causal chain is uncertain and a worked example would calibrate it, (b) an edge case in the schema needs resolution, (c) the fallback watchlist needs extending.
