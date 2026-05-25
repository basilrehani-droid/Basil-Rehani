"""Entry point for the Layer-0 news triage service.

Run modes:
    python -m src.main triage       # Default: fetch, reason, route notifications (every 15 min)
    python -m src.main brief        # Generate + email the morning market brief (once each AM)
    python -m src.main digest       # Send the daily email digest (run once per day)
    python -m src.main test         # Sanity-check config and connections without calling Claude

Designed to be idempotent and safe to re-run: dedup store prevents double-processing,
and failures in one source never block the others.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import Any, Dict, List

from . import brief_state
from .config import (
    BRIEF_GDELT_QUERY, CATALYST_FEEDS, COMPANY_NAMES, MARKET_HOLIDAYS,
    POLICY_FEEDS, RSS_FEEDS, load_config,
)
from .dedupe import content_hash
from .notifiers import email_brief, email_digest, telegram
from .reasoning import generate_eod_wrap, generate_morning_brief, triage_batch
from .router import split_by_tier
from .sources import gdelt, market_data, polygon, rss, ticker_news
from .state import load_state, save_state

LOG = logging.getLogger(__name__)
NY_TZ = ZoneInfo("America/New_York")


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def _is_market_hours() -> bool:
    """Rough check: NYSE hours ± 90min. We include pre-market (7am) through
    post-close (5pm) ET, weekdays only. Holidays are NOT checked — an extra call on
    a holiday costs pennies and doesn't hurt."""
    now_ny = datetime.now(NY_TZ)
    if now_ny.weekday() >= 5:  # Saturday=5, Sunday=6
        return False
    minutes = now_ny.hour * 60 + now_ny.minute
    return 7 * 60 <= minutes <= 17 * 60


def _fetch_all_sources(polygon_key: str) -> List[Dict[str, Any]]:
    """Pull from every configured source. One source failing doesn't block others."""
    items: List[Dict[str, Any]] = []

    for fetch_name, fetch_fn in [
        ("GDELT", lambda: gdelt.fetch_gdelt()),
        ("Polygon", lambda: polygon.fetch_polygon(polygon_key)),
        ("RSS", lambda: rss.fetch_rss(RSS_FEEDS)),
    ]:
        try:
            items.extend(fetch_fn())
        except Exception as e:
            LOG.error("%s source blew up unexpectedly: %s", fetch_name, e)
    return items


def _dedupe_against_state(items: List[Dict[str, Any]], state) -> List[Dict[str, Any]]:
    """Filter out items we've already seen. Mark new ones as seen."""
    fresh = []
    for item in items:
        h = content_hash(item.get("title", ""), item.get("body", ""))
        if state.has_seen(h):
            continue
        fresh.append(item)
        state.mark_seen(h)
    return fresh


def cmd_triage() -> int:
    _setup_logging()
    cfg = load_config()

    if cfg.market_hours_only and not _is_market_hours():
        LOG.info("Outside market hours; exiting without work")
        return 0

    state = load_state()

    # 1. Fetch
    raw_items = _fetch_all_sources(cfg.polygon_api_key)
    LOG.info("Fetched %d raw items across sources", len(raw_items))

    # 2. Dedupe
    fresh_items = _dedupe_against_state(raw_items, state)
    LOG.info("%d fresh items after dedup", len(fresh_items))

    if not fresh_items:
        state.stamp_run()
        save_state(state)
        return 0

    # 3. Reason
    triage = triage_batch(
        fresh_items,
        cfg.anthropic_api_key,
        cfg.claude_model,
        cfg.schwab_client_id,
        cfg.schwab_client_secret,
        cfg.schwab_refresh_token,
    )
    if triage is None:
        LOG.error("Triage returned no result; aborting this run without saving state")
        return 1

    # 4. Route
    push_items, digest_items = split_by_tier(
        triage, cfg.relevance_push_threshold, cfg.relevance_digest_min
    )
    LOG.info(
        "Triage complete: %d push, %d digest, %d noise",
        len(push_items), len(digest_items), len(triage.get("noise_items", []))
    )

    # 5. Notify
    if push_items:
        telegram.send_alert(cfg.telegram_bot_token, cfg.telegram_chat_id, push_items)
    if digest_items:
        email_digest.append_to_digest(digest_items)

    # 6. Persist state (dedup store + last run)
    state.stamp_run()
    save_state(state)

    # Also save the full triage output for later review
    _save_run_output(triage)

    return 0


def _today_et() -> str:
    """Authoritative current date in US/Eastern (markets' timezone)."""
    return datetime.now(NY_TZ).strftime("%Y-%m-%d")


def _briefs_dir():
    from .config import DATA_DIR
    d = DATA_DIR / "briefs"
    d.mkdir(exist_ok=True)
    return d


def _save_brief(brief: Dict[str, Any]) -> None:
    (_briefs_dir() / f"{brief['as_of']}.json").write_text(json.dumps(brief, indent=2))


def _load_brief(date: str) -> Dict[str, Any] | None:
    path = _briefs_dir() / f"{date}.json"
    return json.loads(path.read_text()) if path.exists() else None


def _fetch_brief_portfolio(cfg) -> Dict[str, Any]:
    """Live Schwab portfolio for the brief, or the example fallback. Fetched once
    here and threaded through (tickers, cost basis, and the reasoning prompt) so we
    don't hit Schwab multiple times per run."""
    if cfg.schwab_client_id and cfg.schwab_client_secret and cfg.schwab_refresh_token:
        from .sources.schwab import fetch_portfolio
        pf = fetch_portfolio(cfg.schwab_client_id, cfg.schwab_client_secret, cfg.schwab_refresh_token)
        if pf:
            return pf
        LOG.warning("Brief: Schwab fetch failed; using example portfolio")
    from .config import SKILL_DIR
    example = SKILL_DIR / "assets" / "portfolio_example.json"
    return json.loads(example.read_text()) if example.exists() else {"positions": []}


def _holdings_market(portfolio: Dict[str, Any], quotes: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Per-holding price action joined with cost basis: overnight move + distance from basis."""
    rows = []
    for pos in portfolio.get("positions", []):
        t = (pos.get("ticker") or "").upper()
        q = quotes.get(t)
        if not t or not q:
            continue
        row = {"ticker": t, "price": q["price"], "pct": q["pct"], "session": q["session"]}
        basis = pos.get("cost_basis")
        if basis:
            row["cost_basis"] = basis
            row["pct_from_basis"] = round((q["price"] - basis) / basis * 100, 1)
        rows.append(row)
    return rows


def _fetch_brief_sources(polygon_key: str, held_tickers: List[str]) -> List[Dict[str, Any]]:
    """Wide overnight sweep for the morning brief: ~18h window, broad policy/markets
    coverage plus single-name catalysts (FDA) and per-holding ticker news.
    One source failing doesn't block the others."""
    items: List[Dict[str, Any]] = []
    lookback = 18 * 60  # minutes

    for fetch_name, fetch_fn in [
        ("GDELT-brief", lambda: gdelt.fetch_gdelt(query=BRIEF_GDELT_QUERY, maxrecords=80, timespan="18h")),
        ("Polygon", lambda: polygon.fetch_polygon(polygon_key, lookback_minutes=lookback, limit=100)),
        ("RSS-markets", lambda: rss.fetch_rss(RSS_FEEDS, lookback_minutes=lookback)),
        ("RSS-policy", lambda: rss.fetch_rss(POLICY_FEEDS, lookback_minutes=lookback)),
        ("RSS-catalyst", lambda: rss.fetch_rss(CATALYST_FEEDS, lookback_minutes=lookback)),
        ("Ticker-news", lambda: ticker_news.fetch_ticker_news(held_tickers, names=COMPANY_NAMES, lookback_minutes=lookback)),
    ]:
        try:
            items.extend(fetch_fn())
        except Exception as e:
            LOG.error("%s source blew up unexpectedly: %s", fetch_name, e)
    return items


def cmd_brief() -> int:
    """Generate and email the daily morning brief. Run once each weekday morning."""
    _setup_logging()
    cfg = load_config()

    portfolio = _fetch_brief_portfolio(cfg)
    held = [p["ticker"] for p in portfolio.get("positions", []) if p.get("ticker")]
    LOG.info("Brief: tracking %d held tickers for per-stock news: %s", len(held), ", ".join(held) or "(none)")

    # Real market data, so the brief reasons about actual levels, not headline inference.
    market = {
        "macro": market_data.fetch_macro_snapshot(),
        "holdings": _holdings_market(portfolio, market_data.fetch_quotes(held)),
    }
    holiday = MARKET_HOLIDAYS.get(_today_et())
    if holiday:
        market["note"] = f"US markets closed today — {holiday}."
        LOG.info("Brief: %s", market["note"])

    raw_items = _fetch_brief_sources(cfg.polygon_api_key, held)
    LOG.info("Brief: fetched %d raw items across sources", len(raw_items))

    # Dedupe within the batch, then drop anything already covered in recent briefs.
    seen, items = set(), []
    for item in raw_items:
        h = content_hash(item.get("title", ""), item.get("body", ""))
        if h in seen:
            continue
        seen.add(h)
        items.append(item)
    items = brief_state.filter_unseen(items)
    LOG.info("Brief: %d items after within-batch + cross-day dedup", len(items))

    if not items:
        LOG.warning("Brief: no fresh news items; skipping email")
        return 0

    brief = generate_morning_brief(
        items,
        cfg.anthropic_api_key,
        cfg.brief_model,
        portfolio_json=json.dumps(portfolio, indent=2),
        market_data=market,
    )
    if brief is None:
        LOG.error("Brief generation failed; nothing sent")
        return 1

    brief["as_of"] = _today_et()  # authoritative date, not model-guessed
    _save_brief(brief)  # persist so the evening wrap can reconcile against it

    ok = email_brief.send_brief(
        brief, cfg.smtp_host, cfg.smtp_port, cfg.smtp_user, cfg.smtp_password,
        cfg.digest_to_email, market=market,
    )
    if ok:
        brief_state.mark_seen(items)  # only remember items once the brief actually sent
    return 0 if ok else 1


def cmd_eod() -> int:
    """Generate and email the evening wrap. Run once each weekday after the close."""
    _setup_logging()
    cfg = load_config()

    portfolio = _fetch_brief_portfolio(cfg)
    held = [p["ticker"] for p in portfolio.get("positions", []) if p.get("ticker")]

    market = {
        "macro": market_data.fetch_macro_snapshot(),
        "holdings": _holdings_market(portfolio, market_data.fetch_quotes(held)),
    }
    holiday = MARKET_HOLIDAYS.get(_today_et())
    if holiday:
        market["note"] = f"US markets closed today — {holiday}."

    # The day's news. Unlike the morning brief, do NOT apply cross-day dedup —
    # the wrap needs to see what the morning covered in order to reconcile it.
    raw_items = _fetch_brief_sources(cfg.polygon_api_key, held)
    seen, items = set(), []
    for item in raw_items:
        h = content_hash(item.get("title", ""), item.get("body", ""))
        if h not in seen:
            seen.add(h)
            items.append(item)
    LOG.info("EOD: %d unique items; %d holdings", len(items), len(held))

    morning = _load_brief(_today_et())
    if morning is None:
        LOG.info("EOD: no morning brief found for today; wrap will run without the scorecard")

    wrap = generate_eod_wrap(
        items,
        cfg.anthropic_api_key,
        cfg.brief_model,
        portfolio_json=json.dumps(portfolio, indent=2),
        market_data=market,
        morning_brief=morning,
    )
    if wrap is None:
        LOG.error("EOD wrap generation failed; nothing sent")
        return 1

    wrap["as_of"] = _today_et()
    ok = email_brief.send_eod_wrap(
        wrap, cfg.smtp_host, cfg.smtp_port, cfg.smtp_user, cfg.smtp_password,
        cfg.digest_to_email, market=market,
    )
    return 0 if ok else 1


def cmd_test_email() -> int:
    """Send a one-off test email to verify SMTP delivery, independent of Claude/the brief."""
    _setup_logging()
    cfg = load_config()
    LOG.info(
        "Sending test email via %s:%d as %s -> %s",
        cfg.smtp_host, cfg.smtp_port, cfg.smtp_user or "(unset)", cfg.digest_to_email or "(unset)",
    )
    ok = email_brief.send_test_email(
        cfg.smtp_host, cfg.smtp_port, cfg.smtp_user, cfg.smtp_password, cfg.digest_to_email
    )
    print("OK: test email sent — check your inbox (and spam)." if ok
          else "FAIL: test email not sent — see the error above.")
    return 0 if ok else 1


def cmd_digest() -> int:
    _setup_logging()
    cfg = load_config()
    ok = email_digest.build_and_send_digest(
        cfg.smtp_host, cfg.smtp_port, cfg.smtp_user, cfg.smtp_password, cfg.digest_to_email
    )
    return 0 if ok else 1


def cmd_test() -> int:
    """Sanity check: verify config loads, sources are reachable, Telegram can send.
    Does NOT call Claude (to avoid cost during debugging)."""
    _setup_logging()
    try:
        cfg = load_config()
    except Exception as e:
        print(f"FAIL: config: {e}")
        return 1

    print(f"OK: config loaded (model={cfg.claude_model})")

    # Test sources
    gdelt_items = gdelt.fetch_gdelt(maxrecords=5)
    print(f"OK: GDELT returned {len(gdelt_items)} items")

    poly_items = polygon.fetch_polygon(cfg.polygon_api_key, limit=5)
    print(f"OK: Polygon returned {len(poly_items)} items (empty if no API key)")

    rss_items = rss.fetch_rss(RSS_FEEDS, lookback_minutes=24 * 60)
    print(f"OK: RSS returned {len(rss_items)} items")

    # Test Telegram — send a hello if credentials present
    if cfg.telegram_bot_token and cfg.telegram_chat_id:
        fake = [{
            "headline": "Test alert — Layer-0 triage is alive",
            "relevance_score": 9,
            "directional_bias": "neutral",
            "affected_tickers": [],
            "sizing_recommendation": {"stance": "stand_down", "overrides": []},
        }]
        ok = telegram.send_alert(cfg.telegram_bot_token, cfg.telegram_chat_id, fake)
        print(f"{'OK' if ok else 'FAIL'}: Telegram test message")

    print("\nAll checks complete. If everything above is OK, you're ready to run `python -m src.main triage`.")
    return 0


def _save_run_output(triage: Dict[str, Any]) -> None:
    """Save the full triage output to data/outputs/ for retrospective review."""
    from .config import DATA_DIR
    out_dir = DATA_DIR / "outputs"
    out_dir.mkdir(exist_ok=True)
    fname = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + ".json"
    (out_dir / fname).write_text(json.dumps(triage, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser(description="Layer-0 news triage service")
    parser.add_argument("command", choices=["triage", "brief", "eod", "digest", "test", "test-email"])
    args = parser.parse_args()

    return {
        "triage": cmd_triage,
        "brief": cmd_brief,
        "eod": cmd_eod,
        "digest": cmd_digest,
        "test": cmd_test,
        "test-email": cmd_test_email,
    }[args.command]()


if __name__ == "__main__":
    sys.exit(main())
