from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ItemBase(BaseModel):
    sku: str
    name: str
    category: str | None = None
    max_stock: int = 0


class ItemCreate(ItemBase):
    pass


class ItemUpdate(BaseModel):
    sku: str | None = None
    name: str | None = None
    category: str | None = None
    max_stock: int | None = None


class LocationBase(BaseModel):
    code: str
    zone: str | None = None
    rack: str | None = None
    shelf: str | None = None
    description: str | None = None


class LocationCreate(LocationBase):
    pass


class LocationUpdate(BaseModel):
    code: str | None = None
    zone: str | None = None
    rack: str | None = None
    shelf: str | None = None
    description: str | None = None


class ItemStockRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    item_id: int
    location_id: int
    quantity: int
    updated_at: datetime


class ItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sku: str
    name: str
    category: str | None
    max_stock: int


class ItemWithStock(ItemRead):
    stock: list[ItemStockRead] = []


class LocationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    zone: str | None
    rack: str | None
    shelf: str | None
    description: str | None


class TransactionCreate(BaseModel):
    item_id: int
    location_id: int
    type: str = Field(pattern="^(IN|OUT)$")
    quantity: int = Field(gt=0)
    employee: str | None = None
    note: str | None = None


class TransactionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    item_id: int
    location_id: int
    type: str
    quantity: int
    employee: str | None
    note: str | None
    created_at: datetime


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    employee: str | None = None


class ChatResponse(BaseModel):
    reply: str
    session_id: str
