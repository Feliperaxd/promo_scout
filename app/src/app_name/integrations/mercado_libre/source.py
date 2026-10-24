
from typing import Any

from ...core.models import BaseProduct
from .http import HttpClient


class MercadoLibreSource:
    name = "mercado_libre"

    def __init__(self, client: HttpClient) -> None:
        self._client = client

    def find_by_barcode(self, code: str) -> list[dict[str, Any]]:
        data = self._client.get(
            "/products/search",
            site_id="MLB",
            product_identifier=code,
        )

        return data.get("results", [])

    def find_listings_by_barcode(
        self, code: str
    ) -> list[dict[str, Any]]:
        products = self.find_by_barcode(code)
        listings = []

        for product in products:
            title = product.get("name")

            if not title:
                continue

            data = self._client.get(
                "/sites/MLB/search",
                q=title,
                limit=50,
            )

            for item in data.get("results", []):
                listings.append({
                    "id": item.get("id"),
                    "title": item.get("title"),
                    "price": item.get("price"),
                    "link": item.get("permalink"),
                })

        return listings
