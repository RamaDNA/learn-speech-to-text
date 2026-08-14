import logging

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db import Base
from app.models import Item, ItemStock, Location

logger = logging.getLogger(__name__)


def seed(engine) -> None:
    db = Session(engine)
    try:
        if db.scalar(select(Location).limit(1)):
            return  # sudah ter-seed

        locations = [
            Location(code="A1-R1", zone="Zona A", rack="1", shelf="R1", description="Rak A1 depan"),
            Location(code="A2-R2", zone="Zona A", rack="2", shelf="R2", description="Rak A2 tengah"),
            Location(code="A3-R3", zone="Zona A", rack="3", shelf="R3", description="Rak A3 belakang"),
            Location(code="B1-R1", zone="Zona B", rack="1", shelf="R1", description="Rak B1 depan"),
            Location(code="B2-R2", zone="Zona B", rack="2", shelf="R2", description="Rak B2 tengah"),
        ]
        db.add_all(locations)
        db.flush()

        items = [
            Item(sku="BOLT-M8", name="Baut M8", category="Fastener", max_stock=500),
            Item(sku="NUT-M8", name="Mur M8", category="Fastener", max_stock=500),
            Item(sku="WASH-FLAT", name="Ring Pipih", category="Fastener", max_stock=800),
            Item(sku="SCREW-5X30", name="Sekrup 5x30", category="Fastener", max_stock=600),
            Item(sku="DRILL-10MM", name="Mata Bor 10mm", category="Tools", max_stock=100),
            Item(sku="CABLE-2MM", name="Kabel Listrik 2mm", category="Electrical", max_stock=200),
            Item(sku="TAPE-MASK", name="Selotip Masking", category="Consumable", max_stock=150),
        ]
        db.add_all(items)
        db.flush()

        stocks = [
            ItemStock(item_id=items[0].id, location_id=locations[0].id, quantity=120),
            ItemStock(item_id=items[0].id, location_id=locations[1].id, quantity=80),
            ItemStock(item_id=items[1].id, location_id=locations[0].id, quantity=200),
            ItemStock(item_id=items[2].id, location_id=locations[2].id, quantity=400),
            ItemStock(item_id=items[3].id, location_id=locations[1].id, quantity=300),
            ItemStock(item_id=items[4].id, location_id=locations[3].id, quantity=45),
            ItemStock(item_id=items[5].id, location_id=locations[4].id, quantity=180),
            ItemStock(item_id=items[6].id, location_id=locations[2].id, quantity=90),
        ]
        db.add_all(stocks)
        db.commit()
        logger.info("%d item, %d lokasi, %d stock dibuat", len(items), len(locations), len(stocks))
    finally:
        db.close()


if __name__ == "__main__":
    engine = create_engine("postgresql+psycopg2://warehouse:warehouse@localhost:5432/warehouse")
    Base.metadata.create_all(bind=engine)
    seed(engine)