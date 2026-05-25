"""Call Claude with the Layer-0 triage skill loaded.

Strategy: inline the skill content in the system prompt with prompt caching on the
static portion. The skill files (SKILL.md + references) are ~7k tokens and rarely
change, so caching them amortizes cost across the 40ish calls per trading day.

We use 5-minute ephemeral cache by default, which is the zero-beta option. If you
want the 1-hour cache (better fit for 15-min cadence), set USE_EXTENDED_CACHE=True
and the extended-cache-ttl beta will be enabled.

Output is a JSON object matching the skill's schema. We parse it defensively — if
Claude returns malformed JSON, we log it and return an empty result rather than
crashing.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import anthropic

from .config import SKILL_DIR

LOG = logging.getLogger(__name__)

# Flip to True to use 1-hour cache TTL. Requires the extended-cache-ttl beta header.
USE_EXTENDED_CACHE = False

MAX_OUTPUT_TOKENS = 8000


def _load_skill_bundle() -> str:
    """Concatenate SKILL.md + reference files into one blob. This is the static
    content that gets cached."""
    parts = []

    skill_md = SKILL_DIR / "SKILL.md"
    parts.append("# SKILL.md\n\n" + skill_md.read_text())

    for ref in sorted((SKILL_DIR / "references").glob("*.md")):
        parts.append(f"\n\n# references/{ref.name}\n\n" + ref.read_text())

    return "\n".join(parts)


def _load_portfolio(schwab_client_id: str = "", schwab_client_secret: str = "", schwab_refresh_token: str = "") -> str:
    """Return portfolio JSON string. Uses live Schwab positions if credentials are set,
    otherwise falls back to portfolio_example.json."""
    if schwab_client_id and schwab_client_secret and schwab_refresh_token:
        from .sources.schwab import fetch_portfolio
        live = fetch_portfolio(schwab_client_id, schwab_client_secret, schwab_refresh_token)
        if live:
            import json as _json
            return _json.dumps(live, indent=2)
        LOG.warning("Schwab fetch failed; falling back to portfolio_example.json")

    pf = SKILL_DIR / "assets" / "portfolio_example.json"
    if not pf.exists():
        return ""
    return pf.read_text()


def _build_system_prompt(schwab_client_id: str = "", schwab_client_secret: str = "", schwab_refresh_token: str = "") -> List[Dict[str, Any]]:
    skill_blob = _load_skill_bundle()
    portfolio_blob = _load_portfolio(schwab_client_id, schwab_client_secret, schwab_refresh_token)

    system_parts = [
        {
            "type": "text",
            "text": (
                "You are a Layer-0 news triage system. Apply the skill below exactly. "
                "Your output must be a single JSON object matching the schema — no markdown fences, "
                "no preamble, just the JSON.\n\n"
                f"<skill>\n{skill_blob}\n</skill>"
            ),
            # Cache the skill blob — it's the same every call
            "cache_control": {"type": "ephemeral"},
        },
    ]

    if portfolio_blob:
        system_parts.append({
            "type": "text",
            "text": f"<portfolio>\n{portfolio_blob}\n</portfolio>",
        })

    return system_parts


def triage_batch(
    batch: List[Dict[str, Any]],
    api_key: str,
    model: str,
    schwab_client_id: str = "",
    schwab_client_secret: str = "",
    schwab_refresh_token: str = "",
) -> Optional[Dict[str, Any]]:
    """Send a batch of news items through the skill. Returns parsed JSON or None on failure."""
    if not batch:
        return {
            "processed_at": "",
            "batch_size": 0,
            "portfolio_used": "provided",
            "relevant_items": [],
            "noise_items": [],
            "summary_markdown": "Empty batch.",
        }

    client = anthropic.Anthropic(api_key=api_key)

    user_content = (
        "Process this news batch. Emit the JSON object defined by the skill.\n\n"
        f"```json\n{json.dumps({'batch': batch}, indent=2)}\n```"
    )

    kwargs = {
        "model": model,
        "max_tokens": MAX_OUTPUT_TOKENS,
        "system": _build_system_prompt(schwab_client_id, schwab_client_secret, schwab_refresh_token),
        "messages": [{"role": "user", "content": user_content}],
    }

    if USE_EXTENDED_CACHE:
        # Requires the extended cache TTL beta. If your account doesn't have it,
        # fall back to USE_EXTENDED_CACHE=False.
        kwargs["extra_headers"] = {"anthropic-beta": "extended-cache-ttl-2025-04-11"}
        # Mark the cache entry as 1-hour TTL
        kwargs["system"][0]["cache_control"] = {"type": "ephemeral", "ttl": "1h"}

    try:
        resp = client.messages.create(**kwargs)
    except anthropic.APIError as e:
        LOG.error("Claude API error: %s", e)
        return None

    _log_usage(resp)  # cache performance — helpful when tuning
    return _parse_json_response(resp)


def _log_usage(resp: Any) -> None:
    usage = getattr(resp, "usage", None)
    if usage:
        LOG.info(
            "Claude usage: input=%d cache_create=%d cache_read=%d output=%d",
            getattr(usage, "input_tokens", 0),
            getattr(usage, "cache_creation_input_tokens", 0),
            getattr(usage, "cache_read_input_tokens", 0),
            getattr(usage, "output_tokens", 0),
        )


def _parse_json_response(resp: Any) -> Optional[Dict[str, Any]]:
    """Extract text from a Claude response, strip any markdown fences, parse JSON."""
    text = ""
    for block in resp.content:
        if getattr(block, "type", "") == "text":
            text += block.text

    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines)

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        LOG.error("Failed to parse Claude response as JSON: %s\nFirst 500 chars: %s", e, text[:500])
        return None


# ── Morning brief ───────────────────────────────────────────────────────────

BRIEF_INSTRUCTIONS = """You are the user's morning market analyst. Using the four-layer \
framework in the <skill> block as your reasoning discipline, write a single daily \
pre-market briefing from the overnight news batch and the user's live portfolio.

Be specific and mechanistic — name the causal chain, not just the event. Skip filler. \
If a section has nothing genuinely market-relevant, return an empty string for it rather \
than padding. Reference concrete headlines. Where a held position has a clear stance \
implication under the doctrine (probe / full / reduce / stand_down), say so, and honor \
Layer 2 thesis overrides (a `thesis` flag like "legal risk" or "accumulating risk" gates \
bullish news to stand_down).

Output a SINGLE JSON object — no markdown fences, no preamble — with exactly these keys:

{
  "as_of": "YYYY-MM-DD",
  "headline_takeaways": ["3-6 one-line bullets: the must-knows before the open"],
  "market_overview": "Markdown. Overnight/pre-market tape: futures tone, big overnight moves, rates/dollar/oil, what's driving today's session.",
  "policy_politics": "Markdown. Policy & politics that moves markets: White House / Trump comments, executive orders, new rules, tariffs, foreign policy, Fed/SEC. For each, state the market mechanism and likely affected sectors/tickers.",
  "portfolio": "Markdown. Per HELD ticker that has relevant news today: the news, the read, and stance implication. Mark thesis-override gating where it fires. Only include held names with something to say.",
  "radar": "Markdown. SINGLE-NAME CATALYSTS worth a look today, held or not — go beyond macro. Hunt for: FDA approvals / decisions / PDUFA outcomes, government contracts or policy backing (e.g. a federal order or program lifting a name or a whole theme), M&A and activist stakes, earnings results and guidance changes, analyst rating/price-target moves, executive changes, legal/regulatory rulings, and THEMATIC SYMPATHY moves (when one headline lifts a whole cohort — e.g. quantum names ripping on a government-backing story, nuclear/uranium on a policy push). One bullet per name: **TICKER** — the catalyst, the mechanism, and (when the news supports it) the expectation/likelihood and what to watch next. Be specific; if it's just 'stock moved', skip it.",
  "also_relevant": "Markdown. Anything else you judge relevant today that didn't fit above. Empty string if nothing."
}

Use GitHub-flavored markdown inside the string fields (headings with **bold**, bullet lists, \
[links](url) when a source URL is available). Keep the whole brief tight enough to read over coffee."""


def _format_market_data(market_data: Dict[str, Any]) -> str:
    """Render the market snapshot as a compact text block for the prompt."""
    lines = []
    macro = market_data.get("macro") or []
    if macro:
        lines.append("MACRO TAPE (session in brackets):")
        for r in macro:
            chg = f"{r['pct']:+.2f}%" if r.get("unit") == "pct" else f"{r['change']:+.2f}"
            lines.append(f"  {r['name']}: {r['price']} ({chg}) [{r.get('session','')}]")
    holdings = market_data.get("holdings") or []
    if holdings:
        lines.append("\nHOLDINGS PRICE ACTION:")
        for h in holdings:
            basis = (f", {h['pct_from_basis']:+.1f}% vs cost basis {h['cost_basis']}"
                     if "pct_from_basis" in h else "")
            lines.append(f"  {h['ticker']}: {h['price']} ({h['pct']:+.2f}%) [{h.get('session','')}]{basis}")
    return "\n".join(lines)


def _build_brief_system_prompt(
    portfolio_json: Optional[str] = None,
    market_data: Optional[Dict[str, Any]] = None,
    schwab_client_id: str = "", schwab_client_secret: str = "", schwab_refresh_token: str = "",
    instructions: str = BRIEF_INSTRUCTIONS,
    extra_blocks: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    skill_blob = _load_skill_bundle()
    portfolio_blob = portfolio_json if portfolio_json is not None else _load_portfolio(
        schwab_client_id, schwab_client_secret, schwab_refresh_token
    )

    system_parts = [
        {
            "type": "text",
            "text": f"{instructions}\n\n<skill>\n{skill_blob}\n</skill>",
            "cache_control": {"type": "ephemeral"},
        },
    ]
    if portfolio_blob:
        system_parts.append({
            "type": "text",
            "text": f"<portfolio>\n{portfolio_blob}\n</portfolio>",
        })
    if market_data:
        system_parts.append({
            "type": "text",
            "text": (
                "<market_data>\nThese are REAL current prices — use them; do not invent levels.\n"
                f"{_format_market_data(market_data)}\n</market_data>"
            ),
        })
    for block in extra_blocks or []:
        system_parts.append({"type": "text", "text": block})
    return system_parts


def generate_morning_brief(
    items: List[Dict[str, Any]],
    api_key: str,
    model: str,
    portfolio_json: Optional[str] = None,
    market_data: Optional[Dict[str, Any]] = None,
    schwab_client_id: str = "",
    schwab_client_secret: str = "",
    schwab_refresh_token: str = "",
) -> Optional[Dict[str, Any]]:
    """Produce a daily morning brief dict from the overnight news batch, live portfolio,
    and a real market snapshot. Returns parsed JSON (section fields) or None on failure."""
    client = anthropic.Anthropic(api_key=api_key)

    user_content = (
        "Write today's morning brief from this overnight news batch, grounding any "
        "market commentary in the <market_data> snapshot. Emit only the JSON object "
        "defined in your instructions.\n\n"
        f"```json\n{json.dumps({'batch': items}, indent=2)}\n```"
    )

    try:
        resp = client.messages.create(
            model=model,
            max_tokens=MAX_OUTPUT_TOKENS,
            system=_build_brief_system_prompt(
                portfolio_json, market_data,
                schwab_client_id, schwab_client_secret, schwab_refresh_token,
            ),
            messages=[{"role": "user", "content": user_content}],
        )
    except anthropic.APIError as e:
        LOG.error("Claude API error (brief): %s", e)
        return None

    _log_usage(resp)
    return _parse_json_response(resp)


# ── Evening wrap ──────────────────────────────────────────────────────────────

EOD_INSTRUCTIONS = """You are writing an EVENING WRAP for a discretionary trader, sent after \
the US close. Use the four-layer framework in the <skill> block as your lens. You are given: \
this morning's brief (the pre-open setup and calls), the day's news, the live portfolio, and \
the CLOSING market snapshot in <market_data>.

Your job is to CLOSE THE LOOP: how did the day actually go versus this morning's setup? Be \
specific and honest — call out which morning calls played out and which didn't. Ground every \
market statement in the real closing numbers; do not invent levels.

Output a SINGLE JSON object — no markdown fences, no preamble — with exactly these keys (use \
GitHub-flavored markdown in the string fields; omit a field or use "" if nothing worth saying):

{
  "as_of": "YYYY-MM-DD",
  "headline_takeaways": ["3-5 one-line bullets: how the day netted out"],
  "market_recap": "How the tape closed vs this morning: indices, rates, dollar, oil, vol — using the real closing numbers. What drove the session.",
  "portfolio": "Per held name that moved meaningfully today: the move, the why, and where it stands vs cost basis. Flag thesis-relevant developments and stance implications.",
  "played_out": "Reconcile against THIS MORNING'S brief: which catalysts/calls materialized, which fizzled, what surprised. Reference the morning's specific items by name.",
  "tomorrow_watch": "What to watch tomorrow: scheduled events, unresolved catalysts, key levels, earnings on deck for holdings.",
  "also_relevant": "Anything else worth noting. Omit if nothing."
}

The 'played_out' section is the highest-value part — it's the honest scorecard on the morning's read."""


def generate_eod_wrap(
    items: List[Dict[str, Any]],
    api_key: str,
    model: str,
    portfolio_json: Optional[str] = None,
    market_data: Optional[Dict[str, Any]] = None,
    morning_brief: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Produce an evening wrap that reconciles the day against the morning brief.
    Returns parsed JSON (section fields) or None on failure."""
    client = anthropic.Anthropic(api_key=api_key)

    extra_blocks = []
    if morning_brief:
        # Feed the morning's own sections back in as context for the scorecard.
        keys = ["headline_takeaways", "market_overview", "policy_politics", "portfolio", "radar"]
        morning_txt = json.dumps({k: morning_brief.get(k) for k in keys if morning_brief.get(k)}, indent=2)
        extra_blocks.append(f"<this_mornings_brief>\n{morning_txt}\n</this_mornings_brief>")

    user_content = (
        "Write the evening wrap from today's news batch, reconciling against this "
        "morning's brief and grounding market commentary in the <market_data> close. "
        "Emit only the JSON object defined in your instructions.\n\n"
        f"```json\n{json.dumps({'batch': items}, indent=2)}\n```"
    )

    try:
        resp = client.messages.create(
            model=model,
            max_tokens=MAX_OUTPUT_TOKENS,
            system=_build_brief_system_prompt(
                portfolio_json, market_data,
                instructions=EOD_INSTRUCTIONS, extra_blocks=extra_blocks,
            ),
            messages=[{"role": "user", "content": user_content}],
        )
    except anthropic.APIError as e:
        LOG.error("Claude API error (eod wrap): %s", e)
        return None

    _log_usage(resp)
    return _parse_json_response(resp)
