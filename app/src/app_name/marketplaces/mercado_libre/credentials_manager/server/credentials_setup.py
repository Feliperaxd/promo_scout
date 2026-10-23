import re
import urllib.parse
import webbrowser
from pathlib import Path
from typing import Any

from .callback_server import CallbackServer
from .env_store import Credentials, save_credentials
from .ngrok_tunnel import NgrokTunnel
from .token_exchange import exchange_code_for_token
from .token_store import save_tokens

# server/ -> mercado_libre/ -> marketplaces/ -> app_name/ -> src/ -> app/
ROOT_DIR = Path(__file__).resolve().parents[5]
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
        print(f"Abrindo o formulário em {form_url}")
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
        """Handle the form: start the tunnel and return the ML auth URL."""
        credentials = self._parse_form(form)

        self._stop_tunnel()
        tunnel = NgrokTunnel(credentials.domain, self.port)
        tunnel.start()

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
            raise ValueError("O App ID deve conter apenas números.")
        if not client_secret:
            raise ValueError("Informe a senha (Client Secret).")
        if not DOMAIN_PATTERN.match(domain):
            raise ValueError("Domínio inválido. Use algo como meu.ngrok-free.dev")

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
