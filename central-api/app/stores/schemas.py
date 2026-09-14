"""Store API output models."""

from pydantic import BaseModel, ConfigDict


class StoreResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
