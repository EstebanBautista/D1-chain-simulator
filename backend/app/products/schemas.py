"""Catalog API input and output models.

Field names are in English and match the database columns, so a payload can be
read against the schema with no mental translation.
"""

from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class ProductResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ean: str
    name: str
    price: Decimal
