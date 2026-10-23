from dataclasses import dataclass
from pathlib import Path

from dotenv import set_key


@dataclass(frozen=True)
class Credentials:
    """Application credentials typed by the user in the setup form."""

    app_id: str
    client_secret: str
    domain: str

    @property
    def redirect_uri(self) -> str:
        return f"https://{self.domain}"


def save_credentials(path: Path, credentials: Credentials) -> None:
    """Write the credentials to the given .env file, creating it if needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch(exist_ok=True)

    set_key(path, "ML_APP_ID", credentials.app_id)
    set_key(path, "ML_CLIENT_SECRET", credentials.client_secret)
    set_key(path, "ML_REDIRECT_URI", credentials.redirect_uri)
