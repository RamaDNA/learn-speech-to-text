from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Item(Base):
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(primary_key=True)
    sku: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    max_stock: Mapped[int] = mapped_column(Integer, default=0)

    stocks: Mapped[list["ItemStock"]] = relationship(
        back_populates="item", cascade="all, delete-orphan"
    )


class Location(Base):
    __tablename__ = "locations"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    zone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    rack: Mapped[str | None] = mapped_column(String(50), nullable=True)
    shelf: Mapped[str | None] = mapped_column(String(50), nullable=True)
    description: Mapped[str | None] = mapped_column(String(200), nullable=True)

    stocks: Mapped[list["ItemStock"]] = relationship(
        back_populates="location", cascade="all, delete-orphan"
    )


class ItemStock(Base):
    __tablename__ = "item_stock"
    __table_args__ = (UniqueConstraint("item_id", "location_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"))
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"))
    quantity: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    item: Mapped[Item] = relationship(back_populates="stocks")
    location: Mapped[Location] = relationship(back_populates="stocks")


class StockTransaction(Base):
    __tablename__ = "stock_transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"))
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"))
    type: Mapped[str] = mapped_column(String(10))  # IN / OUT
    quantity: Mapped[int] = mapped_column(Integer)
    employee: Mapped[str | None] = mapped_column(String(100), nullable=True)
    note: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )