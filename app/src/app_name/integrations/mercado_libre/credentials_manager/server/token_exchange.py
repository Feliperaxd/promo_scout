from typing import Any

import requests

TOKEN_URL = "https://api.mercadolibre.com/oauth/token"
REQUEST_TIMEOUT = 15.0


class TokenExchangeError(RuntimeError):
    """Raised when Mercado Libre rejects a token request."""


def _request_token(payload: dict[str, str]) -> dict[str, Any]:
    """Send a token request and return the JSON response."""
    response = requests.post(
        TOKEN_URL,
        headers={
            "accept": "application/json",
            "content-type": "application/x-www-form-urlencoded",
        },
        data=payload,
        timeout=REQUEST_TIMEOUT,
    )

    if not response.ok:
        raise TokenExchangeError(
            f"Mercado Libre returned {response.status_code}: {response.text}"
        )

    return response.json()


def exchange_code_for_token(
    app_id: str,
    client_secret: str,
    code: str,
    redirect_uri: str,
) -> dict[str, Any]:
    """Trade an authorization code for an access token and refresh token."""
    return _request_token(
        {
            "grant_type": "authorization_code",
            "client_id": app_id,
            "client_secret": client_secret,
            "code": code,
            "redirect_uri": redirect_uri,
        }
    )


def refresh_access_token(
    app_id: str,
    client_secret: str,
    refresh_token: str,
) -> dict[str, Any]:
    """Trade a refresh token for a new access token and a new refresh token."""
    return _request_token(
        {
            "grant_type": "refresh_token",
            "client_id": app_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
        }
    )
