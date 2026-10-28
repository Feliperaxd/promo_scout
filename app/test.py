"""Manual script to test the Mercado Libre integration."""

import os
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR / "src"))

from app_name.core.errors import SourceError  # noqa: E402
from app_name.core.http_client import HttpClient  # noqa: E402
from app_name.integrations.mercado_libre.auth import MercadoLibreAuth  # noqa: E402
from app_name.integrations.mercado_libre.source import (  # noqa: E402
    ML_BASE_URL,
    MercadoLibreSource,
)

load_dotenv(BASE_DIR / "config" / ".env.mercado_libre")
TOKENS_PATH = BASE_DIR / "data" / "tokens" / "mercado_libre.json"

BARCODE = "885911457842"  # replace with the barcode you want to test


def build_client() -> HttpClient:
    auth = MercadoLibreAuth(
        TOKENS_PATH,
        app_id=os.environ["ML_APP_ID"],
        client_secret=os.environ["ML_CLIENT_SECRET"],
    )
    return HttpClient(ML_BASE_URL, auth=auth)


def test_barcode(client: HttpClient, barcode: str) -> None:
    """Search the listings for a barcode and print each one."""
    listings = MercadoLibreSource(client).search_by_barcode(barcode)

    print("listings found:", len(listings))
    for listing in listings:
        print(listing)


def main() -> None:
    client = build_client()

    try:
        test_barcode(client, BARCODE)
    except SourceError as error:
        print("ERROR:", error)


if __name__ == "__main__":
    main()