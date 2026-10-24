import time
from pathlib import Path
from typing import Any

import requests

from app_name.core.errors import AuthenticationError, RateLimitError, SourceError

from .credentials_manager import refresh_access_token
from .credentials_manager import load_tokens, save_tokens

BASE_URL = "https://api.mercadolibre.com"
REQUEST_TIMEOUT = 15.0
MAX_RETRIES = 3
RETRY_STATUS = {429, 500, 502, 503, 504}
    

class HttpClient:
    """Thin HTTP layer: auth header, token refresh, retries and error mapping."""

    def __init__(self, tokens_path: Path, env: dict[str, str]) -> None:
        self._tokens_path = tokens_path
        self._app_id = env["ML_APP_ID"]
        self._secret = env["ML_CLIENT_SECRET"]
        self._session = requests.Session()

    def get(self, path: str, **params: Any) -> Any:
        return self._request("GET", path, params=params)

    def post(self, path: str, json: dict[str, Any]) -> Any:
        return self._request("POST", path, json=json)

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        refreshed = False

        for attempt in range(MAX_RETRIES + 1):
            response = self._session.request(
                method,
                f"{BASE_URL}{path}",
                headers=self._auth_headers(),
                timeout=REQUEST_TIMEOUT,
                **kwargs,
            )

            if response.status_code == 401 and not refreshed:
                self._refresh_tokens()
                refreshed = True
                continue

            if response.status_code in RETRY_STATUS and attempt < MAX_RETRIES:
                time.sleep(2**attempt)  # 1s, 2s, 4s
                continue

            return self._parse(response)

        raise SourceError("Retries exhausted.")

    def _auth_headers(self) -> dict[str, str]:
        tokens = load_tokens(self._tokens_path)
        if tokens is None:
            raise AuthenticationError("No tokens saved. Run the credentials setup.")
        return {"Authorization": f"Bearer {tokens['access_token']}"}

    def _refresh_tokens(self) -> None:
        tokens = load_tokens(self._tokens_path)
        if tokens is None or "refresh_token" not in tokens:
            raise AuthenticationError("No refresh token. Run the credentials setup.")
        new_tokens = refresh_access_token(
            self._app_id, self._secret, tokens["refresh_token"]
        )
        save_tokens(self._tokens_path, new_tokens)

    @staticmethod
    def _parse(response: requests.Response) -> Any:
        if response.status_code == 429:
            raise RateLimitError("Rate limit reached.")
        if response.status_code in (401, 403):
            raise AuthenticationError(response.text)
        if not response.ok:
            raise SourceError(f"{response.status_code}: {response.text}")
        return response.json()
    