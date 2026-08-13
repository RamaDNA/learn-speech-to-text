from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Item, ItemStock, Location, StockTransaction


def _get_item(db: Session, item_id: int) -> Item:
    item = db.get(Item, item_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"Item id={item_id} tidak ditemukan")
    return item


def _get_location(db: Session, location_id: int) -> Location:
    loc = db.get(Location, location_id)
    if not loc:
        raise HTTPException(
            status_code=404, detail=f"Lokasi id={location_id} tidak ditemukan"
        )
    return loc


def create_item(db: Session, sku: str, name: str, category: str | None, max_stock: int) -> Item:
    if db.scalar(select(Item).where(Item.sku == sku)):
        raise HTTPException(status_code=409, detail=f"SKU {sku} sudah ada")
    item = Item(sku=sku, name=name, category=category, max_stock=max_stock)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def update_item(db: Session, item_id: int, data: dict) -> Item:
    item = _get_item(db, item_id)
    for field, value in data.items():
        if value is not None:
            setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return item


def delete_item(db: Session, item_id: int) -> None:
    item = _get_item(db, item_id)
    if db.scalar(select(StockTransaction).where(StockTransaction.item_id == item_id)):
        raise HTTPException(
            status_code=409,
            detail=f"Item id={item_id} masih punya riwayat transaksi, tidak bisa dihapus",
        )
    db.delete(item)
    db.commit()


def search_items(db: Session, query: str | None = None) -> list[Item]:
    stmt = select(Item)
    if query:
        like = f"%{query.lower()}%"
        stmt = stmt.where(
            (Item.name.ilike(like)) | (Item.sku.ilike(like)) | (Item.category.ilike(like))
        )
    return list(db.scalars(stmt.order_by(Item.name)).all())


def create_location(db: Session, code: str, zone: str | None, rack: str | None,
                    shelf: str | None, description: str | None) -> Location:
    if db.scalar(select(Location).where(Location.code == code)):
        raise HTTPException(status_code=409, detail=f"Kode lokasi {code} sudah ada")
    loc = Location(code=code, zone=zone, rack=rack, shelf=shelf, description=description)
    db.add(loc)
    db.commit()
    db.refresh(loc)
    return loc


def delete_location(db: Session, location_id: int) -> None:
    loc = _get_location(db, location_id)
    if db.scalar(select(StockTransaction).where(StockTransaction.location_id == location_id)):
        raise HTTPException(
            status_code=409,
            detail=f"Lokasi id={location_id} masih punya riwayat transaksi, tidak bisa dihapus",
        )
    if db.scalar(select(ItemStock).where(ItemStock.location_id == location_id)):
        raise HTTPException(
            status_code=409,
            detail=f"Lokasi id={location_id} masih berisi stock, pindahkan/kosongkan dulu",
        )
    db.delete(loc)
    db.commit()


def get_stock(db: Session, item_id: int) -> list[ItemStock]:
    return list(
        db.scalars(
            select(ItemStock)
            .where(ItemStock.item_id == item_id)
            .order_by(ItemStock.location_id)
        ).all()
    )


def set_stock(db: Session, item_id: int, location_id: int, quantity: int) -> ItemStock:
    _get_item(db, item_id)
    _get_location(db, location_id)
    if quantity < 0:
        raise HTTPException(status_code=400, detail="Quantity tidak boleh negatif")
    stock = db.scalar(
        select(ItemStock).where(
            ItemStock.item_id == item_id, ItemStock.location_id == location_id
        )
    )
    if stock:
        stock.quantity = quantity
    else:
        stock = ItemStock(item_id=item_id, location_id=location_id, quantity=quantity)
        db.add(stock)
    db.commit()
    db.refresh(stock)
    return stock


def record_transaction(db: Session, item_id: int, location_id: int, txn_type: str,
                       quantity: int, employee: str | None, note: str | None) -> StockTransaction:
    _get_item(db, item_id)
    _get_location(db, location_id)
    txn = StockTransaction(
        item_id=item_id,
        location_id=location_id,
        type=txn_type,
        quantity=quantity,
        employee=employee,
        note=note,
    )
    db.add(txn)
    db.commit()
    db.refresh(txn)
    return txn


def take_item(db: Session, item_id: int, location_id: int, quantity: int,
              employee: str | None, note: str | None) -> StockTransaction:
    """Kurangi stock di satu lokasi + catat transaksi OUT (atomic)."""
    _get_item(db, item_id)
    _get_location(db, location_id)
    stock = db.scalar(
        select(ItemStock).where(
            ItemStock.item_id == item_id, ItemStock.location_id == location_id
        )
    )
    current = stock.quantity if stock else 0
    if current < quantity:
        raise HTTPException(
            status_code=400,
            detail=f"Stock tidak cukup: tersedia {current}, diminta {quantity}",
        )
    stock.quantity -= quantity
    txn = StockTransaction(
        item_id=item_id, location_id=location_id, type="OUT",
        quantity=quantity, employee=employee, note=note,
    )
    db.add(txn)
    db.commit()
    db.refresh(txn)
    return txn


def drop_item(db: Session, item_id: int, location_id: int, quantity: int,
              employee: str | None, note: str | None) -> StockTransaction:
    """Tambah stock di satu lokasi + catat transaksi IN (atomic)."""
    _get_item(db, item_id)
    _get_location(db, location_id)
    stock = db.scalar(
        select(ItemStock).where(
            ItemStock.item_id == item_id, ItemStock.location_id == location_id
        )
    )
    if stock:
        stock.quantity += quantity
    else:
        stock = ItemStock(item_id=item_id, location_id=location_id, quantity=quantity)
        db.add(stock)
    txn = StockTransaction(
        item_id=item_id, location_id=location_id, type="IN",
        quantity=quantity, employee=employee, note=note,
    )
    db.add(txn)
    db.commit()
    db.refresh(txn)
    return txn


def find_location_code(db: Session, location_id: int) -> str:
    return _get_location(db, location_id).code


def total_stock(db: Session, item_id: int) -> int:
    return sum(s.quantity for s in get_stock(db, item_id))