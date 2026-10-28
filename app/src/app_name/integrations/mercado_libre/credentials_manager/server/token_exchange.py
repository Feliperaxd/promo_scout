from typing import Any

import requests

TOKEN_URL = "https://api.mercadolibre.com/oauth/token"
REQUEST_TIMEOUT = 15.0


class TokenExchangeError(RuntimeError):
    """Raised when Mercado Libre rejects a token request."""


def exchange_code_for_token(
    app_id: str,
    client_secret: str,
    code: str,
    redirect_uri: str,
) -> dict[str, Any]:
    """Trade an authorization code for an access token and refresh token.

    Args:
        app_id: Mercado Libre application id.
        client_secret: application secret.
        code: authorization code received in the OAuth callback.
        redirect_uri: the same redirect URI used to request the code.

    Returns:
        The token response (access token, refresh token, `expires_in`...).

    Raises:
        TokenExchangeError: if Mercado Libre rejects the request.
        requests.RequestException: on network errors or timeouts.
    """
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
    """Trade a refresh token for a new access token and a new refresh token.

    Mercado Libre refresh tokens are single use, so the response must be
    saved: the refresh token sent here stops working.

    Args:
        app_id: Mercado Libre application id.
        client_secret: application secret.
        refresh_token: the current refresh token.

    Returns:
        The token response (access token, refresh token, `expires_in`...).

    Raises:
        TokenExchangeError: if Mercado Libre rejects the request.
        requests.RequestException: on network errors or timeouts.
    """
    return _request_token(
        {
            "grant_type": "refresh_token",
            "client_id": app_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
        }
    )


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
