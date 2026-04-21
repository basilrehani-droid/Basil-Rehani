# Causal Chain Examples

Worked examples drawn from the user's framework. Each example shows a good causal chain (three or more mechanistic hops) and, where useful, the bad version to contrast against.

---

## Layer 0 — Geopolitical

### Example 1: Strait of Hormuz closure

**Good:**
1. Iran escalation following regional provocation
2. Strait of Hormuz shipping route threatened → insurance premia spike, tankers reroute
3. Global oil supply disruption priced into Brent → WTI spread widens
4. US refiner margins expand on regional crude differential → MPC, VLO, PSX bid

**Affected tickers:** Primary — XOM, MPC, VLO. Secondary — USO, tanker equities (STNG, FRO).

**Bad:**
> Iran tensions → oil up → buy XOM

Two hops, no mechanism for why the user should prefer refiners over integrated majors over upstream.

### Example 2: Strait of Hormuz reopening (ceasefire confirmed)

**Good:**
1. Ceasefire announced, Hormuz shipping normalizes
2. Oil risk premium unwinds → Brent and WTI decline toward pre-tension levels
3. Refiner margins compress as crude differentials normalize
4. Rotation out of energy into rate-sensitive sectors (REITs, homebuilders) as macro narrative shifts back to rate-cut path

**Affected tickers:** Primary — MPC (bearish, trim held position), USO (bearish). Secondary — PLD, EQIX, DHI (bullish, rotation beneficiaries).

This is a **layer 0 + layer 1** item because the geopolitical resolution re-weights the macro regime.

### Example 3: Sanctions on Chinese semiconductor sector

**Good:**
1. New export restrictions on advanced lithography tools
2. Affected foundries face capex delay → process node roadmaps slip
3. US-listed chip-equipment names face China revenue write-down risk → AMAT, LRCX, KLAC bearish
4. Taiwan foundry leader benefits on competitive advantage preservation → TSM bullish at the margin

Layer 0 + Layer 2 (company-specific revenue exposure).

---

## Layer 1 — Macro regime

### Example 4: Fed signals pivot

**Good:**
1. Dot plot shifts dovish, two cuts now baseline for year end
2. Real rate expectations decline → 2y yield drops, curve steepens
3. DXY weakens → EM equities, commodities bid
4. Duration-sensitive domestic assets benefit → TLT, REITs (PLD, EQIX), homebuilders (DHI)

### Example 5: Unexpected hot CPI print

**Good:**
1. Headline CPI prints above consensus, core sticky
2. Rate-cut path pushed further out → 2y yield jumps
3. DXY strengthens, growth-duration assets de-rate
4. Defensive rotation → consumer staples (XLP), healthcare (XLV) outperform; ARK, long-duration tech sell off

---

## Layer 2 — Credit & sector

### Example 6: Oracle-style credit-equity divergence

**Good:**
1. Company CDS spreads widen over several weeks without equity reaction
2. Bond market pricing in previously-hidden balance sheet risk
3. Equity typically reprices to meet credit view with a lag
4. Short equity, long CDS — or at minimum reduce exposure before earnings

### Example 7: SMCI-style legal risk (Layer 2 override in action)

**Good:**
1. Accounting concerns documented, auditor departure, SEC inquiry implied
2. Regardless of positive product/earnings headlines, Layer 2 risk accumulates
3. **Override rule fires:** any bullish news on this name converts `probe` long stance to `stand_down`
4. Only bearish stance or risk reduction is compatible with active Layer 2 flag

**This is the canonical override case.** The skill must recognize any portfolio `thesis` flag containing "legal risk", "accounting", "credit stress", "regulatory investigation", or "accumulating risk" as a Layer 2 override that gates all bullish stances on that ticker.

### Example 8: Insider cluster buying

**Good:**
1. Three or more insiders across different roles (CEO + CFO + independent director) buy open-market within a two-week window
2. Cluster pattern distinguishes signal from 10b5-1 plan noise
3. Alignment of incentives suggests management sees mispricing or upside catalyst
4. Long equity with defined-risk structure (typically held through next earnings)

---

## Layer 3 — Options microstructure

### Example 9: Gamma wall pin into expiration

**Good:**
1. High open interest concentrated at one strike close to spot
2. Dealer positive GEX at that strike creates mechanical buy-the-dip / sell-the-rally hedging
3. Price gravitates toward the strike into Friday close
4. Sell volatility strategies (iron condor, short straddle) have edge; directional bets fight the pin

### Example 10: DEX bearish override on fundamentally bullish name

**Good:**
1. Strong fundamental thesis on a name (e.g., VEEV — durable SaaS, high-quality earnings)
2. Options DEX shows 71.7% bearish positioning → dealers are net short delta, will sell into rallies
3. Microstructure gates fundamentals on entry timing: even a good long thesis is punished mechanically in the near term
4. Stand down on entry; wait for DEX to neutralize before initiating

**This is the microstructure-gates-fundamentals pattern.** News that confirms a good fundamental thesis does NOT justify `full` stance if Layer 3 is hostile.

---

## Cross-layer examples

### Example 11: Pre-earnings pinning with positive GEX (the TSM case)

**Good:**
- Layer 3: 97.8% positive GEX at $380 strike → strong pinning dynamic into earnings
- Layer 0: no meaningful geopolitical catalyst
- Layer 1: macro regime stable
- **Stance:** Short-dated volatility-selling (iron condor pinned on $380), not directional. Confluence across layers (quiet macro + strong microstructure) enables confidence, but the size stays moderate because earnings binary risk remains.

### Example 12: UAL-style earnings binary with identified support

**Good:**
- Layer 3: support mapped at $88–92, options skew shows institutional hedging into print
- Layer 1: travel demand trajectory favorable (lower oil, stable consumer)
- Layer 2: no credit or legal flags
- **Stance:** `probe` long into earnings is acceptable. `full` requires post-earnings confirmation of Layer 3 breakout above the gamma wall.

---

## Meta-rule: the confluence test

Before proposing `full` stance, verify at least three of these are true:
- Layer 0 signal present (or neutral)
- Layer 1 regime supportive
- Layer 2 clean (no overrides)
- Layer 3 positioning supportive

If two or fewer, stance is `probe`. If Layer 2 flag is active on a long bias, stance is `stand_down`.

News-driven items almost never clear this bar on their own. The default for news-triggered bias is `probe`.
