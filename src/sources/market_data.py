"""Market data snapshot for the briefs — real prices, not headline inference.

Uses Yahoo Finance's public chart endpoint (no key, free) to get a last price and
previous close for macro instruments and individual tickers. The morning/EOD briefs
inject this so Opus reasons about where things actually are, not where headlines
imply they might be.

Everything degrades gracefully: a symbol that fails is simply omitted.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import requests

LOG = logging.getLogger(__name__)

CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
HEADERS = {"User-Agent": "Mozilla/5.0"}
TIMEOUT = 10

# (display name, yahoo symbol, unit) for the macro tape.
# unit: "pct" => report % change; "level" => report absolute change (yields, VIX).
MACRO: List[tuple[str, str, str]] = [
    ("S&P 500", "^GSPC", "pct"),
    ("Nasdaq 100", "^NDX", "pct"),
    ("Dow", "^DJI", "pct"),
    ("VIX", "^VIX", "level"),
    ("US 10Y yield", "^TNX", "level"),
    ("Dollar (DXY)", "DX-Y.NYB", "pct"),
    ("WTI crude", "CL=F", "pct"),
    ("Gold", "GC=F", "pct"),
    ("Bitcoin", "BTC-USD", "pct"),
]


def _quote(symbol: str) -> Optional[Dict[str, Any]]:
    """Return {price, prev_close, session} for a symbol, or None on failure.
    `price` prefers an active pre/post-market print so the pre-open brief reflects
    overnight moves; otherwise it's the last regular price."""
    try:
        resp = requests.get(
            CHART_URL.format(symbol=symbol),
            params={"range": "2d", "interval": "1d", "includePrePost": "true"},
            headers=HEADERS,
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        meta = resp.json()["chart"]["result"][0]["meta"]
    except (requests.RequestException, KeyError, ValueError, IndexError, TypeError) as e:
        LOG.warning("market_data quote failed for %s: %s", symbol, e)
        return None

    prev = meta.get("chartPreviousClose") or meta.get("previousClose")
    regular = meta.get("regularMarketPrice")

    pre, post = meta.get("preMarketPrice"), meta.get("postMarketPrice")
    if pre:
        price, session = pre, "pre-market"
    elif post:
        price, session = post, "after-hours"
    else:
        price, session = regular, "last close"

    if price is None or not prev:
        return None
    return {"price": float(price), "prev_close": float(prev), "session": session}


def _changes(price: float, prev: float) -> Dict[str, float]:
    return {"change": round(price - prev, 2), "pct": round((price - prev) / prev * 100, 2)}


def fetch_macro_snapshot() -> List[Dict[str, Any]]:
    """The macro tape: indices, vol, rates, dollar, commodities, crypto."""
    out: List[Dict[str, Any]] = []
    for name, symbol, unit in MACRO:
        q = _quote(symbol)
        if not q:
            continue
        row = {"name": name, "unit": unit, "session": q["session"],
               "price": round(q["price"], 2), **_changes(q["price"], q["prev_close"])}
        out.append(row)
    LOG.info("Market snapshot: %d/%d macro instruments", len(out), len(MACRO))
    return out


def fetch_quotes(tickers: List[str]) -> Dict[str, Dict[str, Any]]:
    """Per-ticker price + change vs previous close, keyed by uppercase ticker."""
    out: Dict[str, Dict[str, Any]] = {}
    for t in tickers:
        sym = t.strip().upper()
        if not sym:
            continue
        q = _quote(sym)
        if not q:
            continue
        out[sym] = {"price": round(q["price"], 2), "session": q["session"],
                    **_changes(q["price"], q["prev_close"])}
    LOG.info("Quotes: %d/%d tickers", len(out), len(tickers))
    return out
