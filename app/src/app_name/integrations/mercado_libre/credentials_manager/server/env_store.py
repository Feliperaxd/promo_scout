"""Saving of the Mercado Libre credentials to a .env file."""

from dataclasses import dataclass, field
from pathlib import Path

from dotenv import set_key

ENV_APP_ID = "ML_APP_ID"
ENV_CLIENT_SECRET = "ML_CLIENT_SECRET"
ENV_REDIRECT_URI = "ML_REDIRECT_URI"


@dataclass(frozen=True)
class Credentials:
    """Application credentials typed by the user in the setup form.

    Attributes:
        app_id: Mercado Libre application id (digits only).
        client_secret: application secret. Hidden from `repr` so it does not
            leak into logs or tracebacks.
        domain: public domain of the tunnel, without scheme, e.g.
            "my.ngrok-free.dev".
    """

    app_id: str
    client_secret: str = field(repr=False)
    domain: str

    @property
    def redirect_uri(self) -> str:
        """URL where Mercado Libre sends the user after the authorization."""
        return f"https://{self.domain}"


def save_credentials(path: Path, credentials: Credentials) -> None:
    """Write the credentials to the given .env file, creating it if needed.

    The client secret is stored in plain text, so keep this file out of
    version control.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch(exist_ok=True)

    set_key(path, ENV_APP_ID, credentials.app_id)
    set_key(path, ENV_CLIENT_SECRET, credentials.client_secret)
    set_key(path, ENV_REDIRECT_URI, credentials.redirect_uri)
    