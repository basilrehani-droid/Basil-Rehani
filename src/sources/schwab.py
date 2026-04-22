"""Fetch live positions from Charles Schwab API.

Auth flow:
  1. One-time: run `python scripts/schwab_auth.py` to get a refresh token
  2. Store SCHWAB_CLIENT_ID, SCHWAB_CLIENT_SECRET, SCHWAB_REFRESH_TOKEN as secrets
  3. Each run: exchange refresh token for access token, fetch positions

If credentials are missing, returns None and the caller falls back to portfolio_example.json.
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Any, Dict, List, Optional

import requests

LOG = logging.getLogger(__name__)

TOKEN_URL = "https://api.schwabapi.com/v1/oauth/token"
ACCOUNTS_URL = "https://api.schwabapi.com/trader/v1/accounts"


def _refresh_access_token(client_id: str, client_secret: str, refresh_token: str) -> Optional[str]:
    resp = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
        auth=(client_id, client_secret),
        timeout=15,
    )
    if not resp.ok:
        LOG.warning("Schwab token refresh failed: %s %s", resp.status_code, resp.text[:200])
        return None
    return resp.json().get("access_token")


def _fetch_accounts(access_token: str) -> List[Dict[str, Any]]:
    resp = requests.get(
        ACCOUNTS_URL,
        params={"fields": "positions"},
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=15,
    )
    if not resp.ok:
        LOG.warning("Schwab accounts fetch failed: %s %s", resp.status_code, resp.text[:200])
        return []
    return resp.json()


def _to_portfolio_json(accounts: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Convert Schwab account positions into the portfolio JSON format the skill expects."""
    positions = []
    for account in accounts:
        for pos in account.get("securitiesAccount", {}).get("positions", []):
            instrument = pos.get("instrument", {})
            asset_type = instrument.get("assetType", "")
            if asset_type not in ("EQUITY", "ETF"):
                continue

            ticker = instrument.get("symbol", "")
            if not ticker:
                continue

            long_qty = pos.get("longQuantity", 0)
            short_qty = pos.get("shortQuantity", 0)
            market_value = pos.get("marketValue", 0)
            avg_price = pos.get("averagePrice", None)

            if long_qty == 0 and short_qty == 0:
                continue

            positions.append({
                "ticker": ticker,
                "position_usd": round(market_value, 2),
                "cost_basis": round(avg_price, 2) if avg_price is not None else None,
                "thesis": "",
            })

    return {
        "description": "Live portfolio from Charles Schwab",
        "as_of": date.today().isoformat(),
        "positions": positions,
    }


def fetch_portfolio(client_id: str, client_secret: str, refresh_token: str) -> Optional[Dict[str, Any]]:
    """Return live portfolio dict or None if credentials are missing/invalid."""
    if not all([client_id, client_secret, refresh_token]):
        return None

    access_token = _refresh_access_token(client_id, client_secret, refresh_token)
    if not access_token:
        return None

    accounts = _fetch_accounts(access_token)
    if not accounts:
        LOG.warning("Schwab returned no accounts")
        return None

    portfolio = _to_portfolio_json(accounts)
    LOG.info("Schwab: loaded %d positions", len(portfolio["positions"]))
    return portfolio
