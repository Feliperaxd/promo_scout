from collections.abc import Iterator
from typing import Any

from app_name.core.http_client import HttpClient
from app_name.core.models.product import MercadoLibreListing
from app_name.integrations.mercado_libre.mapper import MercadoLibreMapper

ML_BASE_URL = "https://api.mercadolibre.com"  # root URL to build the HttpClient with
_DEFAULT_SITE_ID = "MLB"  # Brazil
_PAGE_SIZE = 50


class MercadoLibreSource:
    """Fetch listings from Mercado Libre.

    API errors (`SourceError`) are not handled here: the caller decides
    whether to log, retry or ignore them.
    """

    def __init__(
        self,
        client: HttpClient,
        mapper: MercadoLibreMapper | None = None,
        site_id: str = _DEFAULT_SITE_ID,
    ) -> None:
        """Create the source.

        Args:
            client: authenticated HTTP client for the Mercado Libre API.
            mapper: converts API responses into listings. Defaults to
                `MercadoLibreMapper()`.
            site_id: Mercado Libre site, e.g. "MLB" (Brazil) or
                "MLA" (Argentina).
        """
        self._client = client
        self._mapper = mapper or MercadoLibreMapper()
        self._site_id = site_id

    def search_by_barcode(
        self,
        barcode: str,
        max_items: int = 200,
    ) -> list[MercadoLibreListing]:
        """Return the active listings for a barcode (GTIN/EAN).

        Args:
            barcode: GTIN/EAN digits only, e.g. "7891000100103".
            max_items: maximum number of listings to return. The search
                stops as soon as this limit is reached.

        Returns:
            Listings without duplicates, in the order the API returned them.
            Empty list if no active catalog product has this barcode.

        Raises:
            SourceError: if any API call fails.
        """
        listings: dict[str, MercadoLibreListing] = {}  # dict avoids duplicates

        for product in self._find_products(barcode):
            for offer in self._iter_offers(product["id"]):
                listing = self._mapper.to_listing(offer, product)
                listings[listing.id] = listing

                if len(listings) >= max_items:
                    return list(listings.values())

        return list(listings.values())

    def _find_products(self, barcode: str) -> list[dict[str, Any]]:
        """Find the active catalog products that have this barcode."""
        found = self._client.get(
            "/products/search",
            site_id=self._site_id,
            product_identifier=barcode,
        )
        # ML sometimes returns inactive/wrong products with the same GTIN.
        return [
            product
            for product in found.get("results", [])
            if product.get("status") == "active"
        ]

    def _iter_offers(self, product_id: str) -> Iterator[dict[str, Any]]:
        """Yield every offer of a catalog product, page by page."""
        offset = 0

        while True:
            page = self._client.get(
                f"/products/{product_id}/items",
                limit=_PAGE_SIZE,
                offset=offset,
            )

            offers = page.get("results", [])
            if not offers:
                return

            yield from offers

            offset += len(offers)
            if offset >= (page.get("paging") or {}).get("total", 0):
                return
            