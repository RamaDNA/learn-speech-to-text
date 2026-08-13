from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_api_key
from app.db import get_db
from app.models import ItemStock, Location
from app.schemas import LocationCreate, LocationRead, LocationUpdate
from app.services import inventory

router = APIRouter(prefix="/locations", tags=["locations"], dependencies=[Depends(require_api_key)])


@router.post("", response_model=LocationRead, status_code=201)
def create_location(payload: LocationCreate, db: Session = Depends(get_db)):
    return inventory.create_location(db, **payload.model_dump())


@router.get("", response_model=list[LocationRead])
def list_locations(db: Session = Depends(get_db)):
    return list(db.scalars(select(Location).order_by(Location.code)).all())


@router.get("/{location_id}", response_model=LocationRead)
def get_location(location_id: int, db: Session = Depends(get_db)):
    loc = db.get(Location, location_id)
    if not loc:
        raise HTTPException(status_code=404, detail="Lokasi tidak ditemukan")
    return loc


@router.patch("/{location_id}", response_model=LocationRead)
def update_location(location_id: int, payload: LocationUpdate, db: Session = Depends(get_db)):
    loc = db.get(Location, location_id)
    if not loc:
        raise HTTPException(status_code=404, detail="Lokasi tidak ditemukan")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(loc, field, value)
    db.commit()
    db.refresh(loc)
    return loc


@router.delete("/{location_id}", status_code=204)
def delete_location(location_id: int, db: Session = Depends(get_db)):
    inventory.delete_location(db, location_id)


@router.get("/{location_id}/stock", response_model=list)
def location_stock(location_id: int, db: Session = Depends(get_db)):
    result = []
    for s in db.scalars(select(ItemStock).where(ItemStock.location_id == location_id)):
        result.append({
            "id": s.id,
            "item_id": s.item_id,
            "quantity": s.quantity,
            "updated_at": s.updated_at,
        })
    return result