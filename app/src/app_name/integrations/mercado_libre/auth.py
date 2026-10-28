from pathlib import Path

from app_name.core.errors import AuthenticationError

from .credentials_manager import load_tokens, refresh_access_token, save_tokens


class MercadoLibreAuth:
    """Authenticate requests with the OAuth tokens saved on disk.

    Implements `app_name.core.http_client.AuthProvider`.
    """

    def __init__(self, tokens_path: Path, app_id: str, client_secret: str) -> None:
        """Create the auth provider.

        Args:
            tokens_path: JSON file where the access and refresh tokens are
                stored.
            app_id: Mercado Libre application id.
            client_secret: application secret.
        """
        self._tokens_path = tokens_path
        self._app_id = app_id
        self._client_secret = client_secret

    def headers(self) -> dict[str, str]:
        """Return the Bearer header built from the saved access token.

        Raises:
            AuthenticationError: if no tokens were saved yet.
        """
        tokens = load_tokens(self._tokens_path)
        if tokens is None:
            raise AuthenticationError("No tokens saved. Run the credentials setup.")
        return {"Authorization": f"Bearer {tokens['access_token']}"}

    def refresh(self) -> None:
        """Get a new access token with the saved refresh token and save it.

        Raises:
            AuthenticationError: if there is no saved refresh token.
            TokenExchangeError: if Mercado Libre rejects the refresh.
        """
        tokens = load_tokens(self._tokens_path)
        if tokens is None or "refresh_token" not in tokens:
            raise AuthenticationError("No refresh token. Run the credentials setup.")
        new_tokens = refresh_access_token(
            self._app_id, self._client_secret, tokens["refresh_token"]
        )
        save_tokens(self._tokens_path, new_tokens)
