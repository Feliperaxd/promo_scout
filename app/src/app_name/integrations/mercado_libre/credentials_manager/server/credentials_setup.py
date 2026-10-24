import re
import urllib.parse
import webbrowser
from pathlib import Path
from typing import Any

from .callback_server import CallbackServer, NeedsMoreInput
from .env_store import Credentials, save_credentials
from .ngrok_tunnel import NgrokAuthError, NgrokTunnel, set_authtoken
from .token_exchange import exchange_code_for_token
from .token_store import save_tokens

# server/ -> credentials_manager/ -> mercado_libre/ -> integrations/
#   -> app_name/ -> src/ -> app/
ROOT_DIR = Path(__file__).resolve().parents[6]
ENV_PATH = ROOT_DIR / "config" / ".env.mercado_libre"
TOKENS_PATH = ROOT_DIR / "data" / "tokens" / "mercado_libre.json"

AUTHORIZATION_URL = "https://auth.mercadolivre.com.br/authorization"
DOMAIN_PATTERN = re.compile(r"^[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")


class CredentialsSetup:
    """Run the whole flow: form, authorization, token exchange and saving."""

    def __init__(
        self,
        port: int = 8000,
        env_path: Path = ENV_PATH,
        tokens_path: Path = TOKENS_PATH,
    ) -> None:
        self.port: int = port
        self.env_path: Path = env_path
        self.tokens_path: Path = tokens_path

        self._server = CallbackServer(self._on_submit, port)
        self._tunnel: NgrokTunnel | None = None
        self._credentials: Credentials | None = None

    def run(self) -> dict[str, Any]:
        """Open the form, wait for the authorization and save everything."""
        form_url = f"http://localhost:{self.port}"
        print(f"Opening the form at {form_url}")
        webbrowser.open(form_url)

        try:
            code = self._server.wait_for_code()
        finally:
            self._stop_tunnel()

        credentials = self._credentials
        if credentials is None:
            raise RuntimeError("Authorization finished without credentials.")

        tokens = exchange_code_for_token(
            app_id=credentials.app_id,
            client_secret=credentials.client_secret,
            code=code,
            redirect_uri=credentials.redirect_uri,
        )

        # Only persist anything after the token was generated successfully.
        save_credentials(self.env_path, credentials)
        save_tokens(self.tokens_path, tokens)

        return tokens

    def _on_submit(self, form: dict[str, str]) -> str:
        """Handle the form: start the tunnel and return the ML auth URL.

        If ngrok is not authenticated on this computer, ask the form for the
        ngrok authtoken instead of failing.
        """
        credentials = self._parse_form(form)
        ngrok_token = form.get("ngrok_token", "")

        self._stop_tunnel()
        tunnel = NgrokTunnel(credentials.domain, self.port)

        try:
            if ngrok_token:
                set_authtoken(ngrok_token)
            tunnel.start()
        except NgrokAuthError as exc:
            print(f"[setup] ngrok authentication failed: {exc}")
            prefill = {
                "app_id": credentials.app_id,
                "domain": credentials.domain,
            }
            if ngrok_token:
                # A token was already tried, so tell the form it was refused.
                prefill["retry"] = "1"
            raise NeedsMoreInput("ngrok_token", prefill) from exc

        self._tunnel = tunnel
        self._credentials = credentials
        return self._authorization_url(credentials)

    def _parse_form(self, form: dict[str, str]) -> Credentials:
        app_id = form.get("app_id", "")
        client_secret = form.get("client_secret", "")
        domain = form.get("domain", "")

        for prefix in ("https://", "http://"):
            domain = domain.removeprefix(prefix)
        domain = domain.rstrip("/")

        if not app_id.isdigit():
            raise ValueError("The App ID must contain only digits.")
        if not client_secret:
            raise ValueError("Enter the Client Secret.")
        if not DOMAIN_PATTERN.match(domain):
            raise ValueError(
                "Invalid domain. Use something like my.ngrok-free.dev"
            )

        return Credentials(app_id, client_secret, domain)

    def _authorization_url(self, credentials: Credentials) -> str:
        query = urllib.parse.urlencode(
            {
                "response_type": "code",
                "client_id": credentials.app_id,
                "redirect_uri": credentials.redirect_uri,
                "state": self._server.state,
            }
        )
        return f"{AUTHORIZATION_URL}?{query}"

    def _stop_tunnel(self) -> None:
        if self._tunnel is not None:
            self._tunnel.stop()
            self._tunnel = None