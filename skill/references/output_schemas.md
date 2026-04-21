# Output Schemas

Formal schema for the JSON output of the Layer-0 News Triage skill. Consult this file when an edge case in the output format needs resolution.

---

## Top-level object

```json
{
  "processed_at":    "ISO-8601 UTC timestamp, e.g. 2026-04-21T14:32:00Z",
  "batch_size":      "integer ≥ 0; count of items in the input batch (including noise)",
  "portfolio_used":  "string: 'provided' | 'fallback' | 'none'",
  "relevant_items":  "array of per-item objects (see below); empty array if all noise",
  "noise_items":     "array of string IDs; never full objects",
  "summary_markdown":"string; tier-ordered human-readable brief"
}
```

All six top-level fields are required. Never omit a field — use empty array / empty string when the field has no content.

---

## Per-item object

```json
{
  "id":                    "string; unique within the batch",
  "source_ids":            "array of strings; optional; populated when multiple sources reported the same event",
  "headline":              "string; canonical form of the headline (clean it up if the input was noisy)",
  "relevance_score":       "integer 4–10 (items <4 do not appear here)",
  "layer_classification":  "array of strings from ['geopolitical','macro','credit-sector','microstructure']; at least one",
  "affected_tickers":      "array of ticker objects (see below); max 10 total",
  "causal_chain":          "array of strings; ≥3 elements for any item claiming relevance_score ≥ 5",
  "directional_bias":      "string; short phrase describing the market read",
  "confidence":            "float 0.0–1.0",
  "sizing_recommendation": "object (see below)",
  "flags":                 "array of strings; zero or more; enum in 'Flag values' section",
  "reasoning":             "string; one paragraph tying causal chain to stance"
}
```

### Ticker object

```json
{
  "ticker":       "string; uppercase symbol",
  "direction":    "'bullish' | 'bearish' | 'neutral'",
  "order":        "'primary' | 'secondary'",
  "in_portfolio": "boolean"
}
```

- Maximum 5 primary and 5 secondary per item.
- If the same ticker would appear twice (once primary, once secondary), keep only the primary entry.
- `neutral` is reserved for cases where the news affects a ticker but direction is ambiguous; use sparingly.

### Sizing recommendation object

```json
{
  "stance":    "'probe' | 'full' | 'reduce' | 'stand_down'",
  "rationale": "string; one sentence explaining why this stance given the framework",
  "overrides": "array of strings; each string describes a Layer 2 override that fired"
}
```

Stance semantics (see SKILL.md `Sizing doctrine` for full selection logic):
- `probe` — flat/small holding; initiate small exploratory position
- `full` — flat/small holding; initiate full-size position (requires ≥3-layer confluence)
- `reduce` — held position; actively take risk off (trim, exit, or hedge)
- `stand_down` — flat holding; do not initiate (ambiguous, or Layer 2 override blocks bullish side)

- `overrides` is empty `[]` when no override fires.
- When `stance` is `stand_down` due to a Layer 2 override, the override text must appear in `overrides`.
- When `stance` is `full`, the rationale must name the specific confluence conditions (which layers align).
- When `stance` is `reduce`, the rationale must name the adverse catalyst or thesis-invalidation reason, and the affected ticker must have `in_portfolio: true`.

### Flag values

Enum for the `flags` array:

- `low_specificity` — causal chain has fewer than 3 mechanistic hops; confidence capped at 0.4
- `duplicate_merged` — this item absorbed duplicates from other sources; see `source_ids`
- `non_english_source` — original headline was not in English
- `forward_looking_only` — item is a forecast or opinion, not a confirmed event
- `high_conviction` — all four layers align; use sparingly
- `layer_2_override_active` — a Layer 2 override fired on at least one affected ticker

---

## Error responses

If the input cannot be parsed:

```json
{
  "processed_at": "...",
  "batch_size": 0,
  "portfolio_used": "none",
  "relevant_items": [],
  "noise_items": [],
  "summary_markdown": "Input could not be parsed. Expected JSON array of items or plain headline text.",
  "error": "parse_failed"
}
```

The `error` field is only present when something went wrong. Never use it to avoid the work — only for genuine parse failures.

---

## Validation rules (must all hold)

1. Every `relevance_score` in `relevant_items` is ≥ 4.
2. Every item in `noise_items` has no corresponding entry in `relevant_items`.
3. `batch_size` ≥ `len(relevant_items) + len(noise_items)` (may exceed if duplicates were merged).
4. `summary_markdown` does not mention items with `relevance_score < 4` by headline.
5. Every `causal_chain` on items with `relevance_score ≥ 5` has at least 3 elements.
6. Every `stance: "full"` has a `rationale` that names specific layers in confluence.
7. Every item with a Layer 2 override has `flags` containing `layer_2_override_active`.
8. No ticker appears more than once in a single item's `affected_tickers` array.
9. Every `stance: "reduce"` has at least one ticker with `in_portfolio: true` in `affected_tickers`.
10. Items with `flags` containing `low_specificity` have `confidence ≤ 0.4`.
11. Items with `flags` containing `forward_looking_only` have `confidence ≤ 0.5`.
12. When `summary_markdown` contains a SYNTHESIS section, at least 3 items in `relevant_items` share a directional bias.

---

## Example minimal valid output (all noise)

```json
{
  "processed_at": "2026-04-21T14:32:00Z",
  "batch_size": 17,
  "portfolio_used": "provided",
  "relevant_items": [],
  "noise_items": ["h1","h2","h3","h4","h5","h6","h7","h8","h9","h10","h11","h12","h13","h14","h15","h16","h17"],
  "summary_markdown": "No market-relevant items in this batch."
}
```

## Example minimal valid output (one item)

```json
{
  "processed_at": "2026-04-21T14:32:00Z",
  "batch_size": 3,
  "portfolio_used": "provided",
  "relevant_items": [
    {
      "id": "h2",
      "headline": "OPEC+ agrees to 500kbd cut at emergency meeting",
      "relevance_score": 8,
      "layer_classification": ["geopolitical", "macro"],
      "affected_tickers": [
        {"ticker": "XOM", "direction": "bullish", "order": "primary", "in_portfolio": false},
        {"ticker": "MPC", "direction": "bullish", "order": "primary", "in_portfolio": true},
        {"ticker": "USO", "direction": "bullish", "order": "primary", "in_portfolio": false}
      ],
      "causal_chain": [
        "Surprise production cut announced outside scheduled meeting cadence",
        "Physical crude supply reduced; Brent curve steepens into backwardation",
        "Integrated majors and refiners with favorable crude slate benefit most"
      ],
      "directional_bias": "bullish oil complex, lean toward refiners",
      "confidence": 0.72,
      "sizing_recommendation": {
        "stance": "probe",
        "rationale": "Layer 0 + Layer 1 signal; Layer 3 positioning confirmation required before full size",
        "overrides": []
      },
      "flags": [],
      "reasoning": "OPEC+ surprise cuts have historically produced 2-5% moves in the oil complex on the day, with refiners benefiting disproportionately when the cut tightens the specific crude grades they process. Held MPC position captures the direct benefit; confluence is Layer 0 (coordinated state action) plus Layer 1 (supply-side macro shift)."
    }
  ],
  "noise_items": ["h1", "h3"],
  "summary_markdown": "**HIGH PRIORITY (≥7)**\n- OPEC+ agrees to 500kbd cut → MPC (held), XOM, USO → bullish oil — stance: probe\n\n**NOISE FILTERED** — 2 items"
}
```
