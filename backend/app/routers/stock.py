from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import require_api_key
from app.db import get_db
from app.schemas import TransactionRead
from app.services import inventory

router = APIRouter(prefix="/stock", tags=["stock"], dependencies=[Depends(require_api_key)])


@router.post("/take", response_model=TransactionRead, status_code=201)
def take_stock(item_id: int, location_id: int, quantity: int,
               employee: str | None = None, note: str | None = None,
               db: Session = Depends(get_db)):
    """Ambil barang dari lokasi (stock berkurang + transaksi OUT)."""
    return inventory.take_item(db, item_id, location_id, quantity, employee, note)


@router.post("/drop", response_model=TransactionRead, status_code=201)
def drop_stock(item_id: int, location_id: int, quantity: int,
               employee: str | None = None, note: str | None = None,
               db: Session = Depends(get_db)):
    """Taruh barang di lokasi (stock bertambah + transaksi IN)."""
    return inventory.drop_item(db, item_id, location_id, quantity, employee, note)


@router.put("/{item_id}/{location_id}")
def set_stock(item_id: int, location_id: int, quantity: int, db: Session = Depends(get_db)):
    """Set jumlah stock secara langsung (admin/koreksi)."""
    stock = inventory.set_stock(db, item_id, location_id, quantity)
    return {"item_id": stock.item_id, "location_id": stock.location_id, "quantity": stock.quantity}


@router.get("/{item_id}/total")
def total_stock(item_id: int, db: Session = Depends(get_db)):
    return {"item_id": item_id, "total": inventory.total_stock(db, item_id)}