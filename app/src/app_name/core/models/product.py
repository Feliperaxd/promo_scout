from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, kw_only=True)
class BaseProduct:
    """A product offered by a store, independent of the source.

    Attributes:
        price: current price, already with any promotion applied.
        barcode: GTIN/EAN digits only. Empty if the source has none.
        manufacturer_code: model code given by the manufacturer (MPN).
    """

    title: str
    price: Decimal
    barcode: str
    brand: str | None = None
    manufacturer_code: str | None = None


@dataclass(frozen=True, kw_only=True)
class MercadoLibreListing(BaseProduct):
    """A Mercado Libre listing of a catalog product.

    Attributes:
        id: listing id, e.g. "MLB5465432943".
        permalink: public URL of the listing.
        original_price: price before the promotion. None if not on sale.
        logistic_type: how the listing is shipped, as reported by the API
            (e.g. "xd_drop_off", "cross_docking").
        images: picture URLs of the catalog product. Shared by every listing
            of the same product.
    """

    id: str
    permalink: str
    original_price: Decimal | None = None
    logistic_type: str | None = None
    is_free_shipping: bool = False
    images: tuple[str, ...] = ()
    