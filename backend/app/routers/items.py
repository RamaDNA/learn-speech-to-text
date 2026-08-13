from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth import require_api_key
from app.db import get_db
from app.schemas import (ItemCreate, ItemRead, ItemUpdate, LocationCreate,
                         LocationRead, LocationUpdate)
from app.services import inventory

router = APIRouter(prefix="/items", tags=["items"], dependencies=[Depends(require_api_key)])


@router.post("", response_model=ItemRead, status_code=201)
def create_item(payload: ItemCreate, db: Session = Depends(get_db)):
    return inventory.create_item(db, **payload.model_dump())


@router.get("", response_model=list[ItemRead])
def list_items(q: str | None = Query(None), db: Session = Depends(get_db)):
    return inventory.search_items(db, q)


@router.get("/{item_id}", response_model=ItemRead)
def get_item(item_id: int, db: Session = Depends(get_db)):
    from app.services.inventory import _get_item  # reuse internal helper via HTTPException
    return _get_item(db, item_id)


@router.patch("/{item_id}", response_model=ItemRead)
def update_item(item_id: int, payload: ItemUpdate, db: Session = Depends(get_db)):
    return inventory.update_item(db, item_id, payload.model_dump(exclude_unset=True))


@router.delete("/{item_id}", status_code=204)
def delete_item(item_id: int, db: Session = Depends(get_db)):
    inventory.delete_item(db, item_id)


@router.get("/{item_id}/stock", response_model=list)
def item_stock(item_id: int, db: Session = Depends(get_db)):
    result = []
    for s in inventory.get_stock(db, item_id):
        result.append({
            "id": s.id,
            "location": inventory.find_location_code(db, s.location_id),
            "quantity": s.quantity,
            "updated_at": s.updated_at,
        })
    return result