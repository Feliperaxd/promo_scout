from typing import Any

import requests

TOKEN_URL = "https://api.mercadolibre.com/oauth/token"
REQUEST_TIMEOUT = 15.0


class TokenExchangeError(RuntimeError):
    """Raised when Mercado Libre rejects the authorization code exchange."""


def exchange_code_for_token(
    app_id: str,
    client_secret: str,
    code: str,
    redirect_uri: str,
) -> dict[str, Any]:
    """Trade an authorization code for an access token and refresh token."""
    response = requests.post(
        TOKEN_URL,
        headers={
            "accept": "application/json",
            "content-type": "application/x-www-form-urlencoded",
        },
        data={
            "grant_type": "authorization_code",
            "client_id": app_id,
            "client_secret": client_secret,
            "code": code,
            "redirect_uri": redirect_uri,
        },
        timeout=REQUEST_TIMEOUT,
    )

    if not response.ok:
        raise TokenExchangeError(
            f"Mercado Libre returned {response.status_code}: {response.text}"
        )

    return response.json()
