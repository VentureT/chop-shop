"""eBay OAuth client-credentials grant (Application access token)."""
from __future__ import annotations

import base64
import threading
import time

import httpx

from app.config import Settings

SCOPE = "https://api.ebay.com/oauth/api_scope"
_REFRESH_MARGIN = 600  # seconds before expiry to refresh (tokens last 7200s)


class EbayAuth:
    def __init__(self, settings: Settings) -> None:
        self.s = settings
        self._token: str | None = None
        self._expires_at: float = 0.0
        self._lock = threading.Lock()  # valuations fetch parts in parallel

    @property
    def configured(self) -> bool:
        return self.s.ebay_configured

    def token(self) -> str:
        if self._token and time.time() < self._expires_at - _REFRESH_MARGIN:
            return self._token
        with self._lock:
            if self._token and time.time() < self._expires_at - _REFRESH_MARGIN:
                return self._token
            creds = f"{self.s.ebay_client_id}:{self.s.ebay_client_secret}".encode()
            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "Authorization": "Basic " + base64.b64encode(creds).decode(),
            }
            data = {"grant_type": "client_credentials", "scope": SCOPE}
            with httpx.Client(timeout=20) as client:
                resp = client.post(f"{self.s.ebay_api_base}/identity/v1/oauth2/token", headers=headers, data=data)
                resp.raise_for_status()
                body = resp.json()
            self._token = body["access_token"]
            self._expires_at = time.time() + int(body.get("expires_in", 7200))
            return self._token
