from decimal import Decimal
from typing import Any

from app_name.core.models.product import MercadoLibreListing

_DEFAULT_PERMALINK_BASE_URL = "https://produto.mercadolivre.com.br"

# Attributes where ML may store the manufacturer code, in priority order.
_MANUFACTURER_CODE_ATTRIBUTES = ("MPN", "ALPHANUMERIC_MODEL", "MODEL")


class MercadoLibreMapper:
    """Converts Mercado Libre API responses into the app's models."""

    def __init__(
        self,
        permalink_base_url: str = _DEFAULT_PERMALINK_BASE_URL,
    ) -> None:
        self._permalink_base_url = permalink_base_url

    def to_listing(
        self,
        offer: dict[str, Any],
        product: dict[str, Any],
    ) -> MercadoLibreListing:
        """Build a MercadoLibreListing from a catalog offer.
 
        Args:
            offer: item from `results` of `/products/{id}/items`
                (price, shipping, id).
            product: catalog product from `/products/search`
                (name, brand, barcode, pictures).
        """
        shipping = offer.get("shipping") or {}
        price = self._to_decimal(offer.get("price"))
 
        return MercadoLibreListing(
            id=offer["item_id"],
            title=product.get("name", ""),
            price=price if price is not None else Decimal("0"),
            original_price=self._to_decimal(offer.get("original_price")),
            barcode=self._extract_barcode(product),
            brand=self._get_attribute(product, "BRAND"),
            manufacturer_code=self._extract_manufacturer_code(product),
            permalink=self._build_permalink(offer["item_id"]),
            logistic_type=shipping.get("logistic_type"),
            is_free_shipping=bool(shipping.get("free_shipping", False)),
            images=self._extract_image_urls(product),
        )

    def _build_permalink(self, item_id: str) -> str:
        """MLB5465432943 -> <base_url>/MLB-5465432943"""
        site_id, number = item_id[:3], item_id[3:]
        return f"{self._permalink_base_url}/{site_id}-{number}"

    def _extract_barcode(self, product: dict[str, Any]) -> str:
        """Return the first GTIN of the catalog product, or "" if it has none."""
        for attribute in product.get("attributes") or []:
            if attribute.get("id") != "GTIN":
                continue
            for value in attribute.get("values") or []:
                if value.get("name"):
                    return value["name"]
        return ""

    def _extract_manufacturer_code(self, product: dict[str, Any]) -> str | None:
        """Return the first filled manufacturer code, or None."""
        for attribute_id in _MANUFACTURER_CODE_ATTRIBUTES:
            value = self._get_attribute(product, attribute_id)
            if value:
                return value
        return None

    @staticmethod
    def _get_attribute(data: dict[str, Any], attribute_id: str) -> str | None:
        """Return the value of an attribute (BRAND, MPN, GTIN...) or None."""
        for attribute in data.get("attributes") or []:
            if attribute.get("id") == attribute_id:
                return attribute.get("value_name")
        return None

    @staticmethod
    def _to_decimal(value: Any) -> Decimal | None:
        """Convert via str so we don't inherit float imprecision."""
        return None if value is None else Decimal(str(value))

    @staticmethod
    def _extract_image_urls(product: dict[str, Any]) -> tuple[str, ...]:
        """Return the picture URLs of the catalog product."""
        return tuple(
            picture["url"]
            for picture in product.get("pictures") or []
            if picture.get("url")
        )
