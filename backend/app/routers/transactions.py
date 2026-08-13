from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_api_key
from app.db import get_db
from app.models import StockTransaction
from app.schemas import TransactionCreate, TransactionRead
from app.services import inventory

router = APIRouter(prefix="/transactions", tags=["transactions"], dependencies=[Depends(require_api_key)])


@router.post("", response_model=TransactionRead, status_code=201)
def create_transaction(payload: TransactionCreate, db: Session = Depends(get_db)):
    """Catat transaksi langsung tanpa ubah stock (misal migrasi) — atau pakai endpoints di /stock."""
    return inventory.record_transaction(db, **payload.model_dump())


@router.get("", response_model=list[TransactionRead])
def list_transactions(
    item_id: int | None = Query(None),
    location_id: int | None = Query(None),
    limit: int = Query(100, le=500),
    db: Session = Depends(get_db),
):
    stmt = select(StockTransaction).order_by(StockTransaction.id.desc()).limit(limit)
    if item_id:
        stmt = stmt.where(StockTransaction.item_id == item_id)
    if location_id:
        stmt = stmt.where(StockTransaction.location_id == location_id)
    return list(db.scalars(stmt).all())