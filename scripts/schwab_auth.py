"""One-time Schwab OAuth setup. Run this locally to get your refresh token.

Usage:
    python scripts/schwab_auth.py

Prerequisites:
    1. Go to https://developer.schwab.com and create an app
    2. Set the callback URL to https://127.0.0.1
    3. Copy your Client ID and Client Secret
    4. pip install requests

After running this script, add the three values to GitHub Secrets:
    SCHWAB_CLIENT_ID
    SCHWAB_CLIENT_SECRET
    SCHWAB_REFRESH_TOKEN
"""
from __future__ import annotations

import base64
import hashlib
import os
import secrets
import urllib.parse
import webbrowser

import requests

AUTH_URL = "https://api.schwabapi.com/v1/oauth/authorize"
TOKEN_URL = "https://api.schwabapi.com/v1/oauth/token"
REDIRECT_URI = "https://127.0.0.1"


def main() -> None:
    client_id = input("Enter your Schwab Client ID: ").strip()
    client_secret = input("Enter your Schwab Client Secret: ").strip()

    # PKCE
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).rstrip(b"=").decode()

    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "scope": "readonly",
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }

    url = AUTH_URL + "?" + urllib.parse.urlencode(params)
    print(f"\nOpening browser to:\n{url}\n")
    webbrowser.open(url)

    print("After you approve, your browser will redirect to a URL like:")
    print("  https://127.0.0.1/?code=XXXXXX&session=YYYY")
    print("The page will show an error (that's normal — copy the full URL from the address bar).\n")

    redirected = input("Paste the full redirect URL here: ").strip()
    parsed = urllib.parse.urlparse(redirected)
    code = urllib.parse.parse_qs(parsed.query).get("code", [None])[0]

    if not code:
        print("ERROR: could not find 'code' in the URL. Make sure you copied the full URL.")
        return

    resp = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "code_verifier": verifier,
        },
        auth=(client_id, client_secret),
        timeout=15,
    )

    if not resp.ok:
        print(f"ERROR: token exchange failed: {resp.status_code} {resp.text}")
        return

    tokens = resp.json()
    refresh_token = tokens.get("refresh_token", "")

    print("\n--- SUCCESS ---")
    print("Add these three values as GitHub Secrets:\n")
    print(f"  SCHWAB_CLIENT_ID     = {client_id}")
    print(f"  SCHWAB_CLIENT_SECRET = {client_secret}")
    print(f"  SCHWAB_REFRESH_TOKEN = {refresh_token}")
    print("\nThe refresh token is valid for 7 days. Re-run this script to renew it.")


if __name__ == "__main__":
    main()
