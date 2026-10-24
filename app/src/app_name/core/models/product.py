from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, kw_only=True)
class BaseProduct:

    title: str
    brand: str
    price: Decimal
    barcode: str 
    manufacturer_code: str

@dataclass(frozen=True, kw_only=True)
class MercadoLibreProduct(BaseProduct):

    id: int
    original_price: Decimal | None
    is_free_shipping: bool = False
    status: str
    permalink: str
    logistic_type: str
