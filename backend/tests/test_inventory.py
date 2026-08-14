"""Test service inventory terhadap postgres test db (bukan mock)."""
import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from app.models import ItemStock
from app.services import inventory


@pytest.fixture()
def item(db_session):
    return inventory.create_item(db_session, sku="BOLT-M8", name="Baut M8",
                                 category="Fastener", max_stock=100)


@pytest.fixture()
def location(db_session):
    return inventory.create_location(db_session, code="A1-R1", zone="A",
                                     rack="R1", shelf=None, description="Rak A1")


class TestItemCRUD:
    def test_create_and_read(self, db_session, item):
        found = inventory.search_items(db_session, "baut")
        assert [i.id for i in found] == [item.id]
        assert inventory.search_items(db_session, "SKU yang tidak ada") == []

    def test_duplicate_sku_409(self, db_session, item):
        with pytest.raises(HTTPException) as exc:
            inventory.create_item(db_session, sku="BOLT-M8", name="Baut M8 lagi",
                                  category="Fastener", max_stock=5)
        assert exc.value.status_code == 409

    def test_delete_item_tanpa_transaksi(self, db_session, item):
        inventory.delete_item(db_session, item.id)
        assert inventory.search_items(db_session, "baut") == []

    def test_delete_item_dengan_transaksi_409(self, db_session, item, location):
        # transaksi rekam dulu (set_stock bukan transaksi)
        inventory.record_transaction(db_session, item.id, location.id, "IN", 10,
                                     employee=None, note="awal")
        with pytest.raises(HTTPException) as exc:
            inventory.delete_item(db_session, item.id)
        assert exc.value.status_code == 409

    def test_delete_item_berisi_stock_tanpa_transaksi_409(self, db_session, item, location):
        # regresi: item berstock tapi tanpa transaksi jangan terhapus diam-diam
        inventory.set_stock(db_session, item.id, location.id, 10)
        with pytest.raises(HTTPException) as exc:
            inventory.delete_item(db_session, item.id)
        assert exc.value.status_code == 409
        assert inventory.search_items(db_session, "baut")  # masih ada


class TestStockFlow:
    def test_set_stock_dan_total(self, db_session, item, location):
        inventory.set_stock(db_session, item.id, location.id, 25)
        assert inventory.total_stock(db_session, item.id) == 25
        # set ulang (update bukan duplicate row)
        inventory.set_stock(db_session, item.id, location.id, 30)
        assert len(inventory.get_stock(db_session, item.id)) == 1
        assert inventory.total_stock(db_session, item.id) == 30

    def test_quantity_negatif_ditolak(self, db_session, item, location):
        with pytest.raises(HTTPException) as exc:
            inventory.set_stock(db_session, item.id, location.id, -1)
        assert exc.value.status_code == 400

    def test_take_dan_drop_mengubah_stock(self, db_session, item, location):
        inventory.set_stock(db_session, item.id, location.id, 50)
        txn = inventory.take_item(db_session, item.id, location.id, 20,
                                  employee="Andi", note="proyek")
        assert txn.type == "OUT"
        assert txn.quantity == 20
        assert inventory.total_stock(db_session, item.id) == 30

        txn2 = inventory.drop_item(db_session, item.id, location.id, 15,
                                   employee="Andi", note="retur")
        assert txn2.type == "IN"
        assert inventory.total_stock(db_session, item.id) == 45

    def test_take_lebih_dari_stock_400(self, db_session, item, location):
        inventory.set_stock(db_session, item.id, location.id, 5)
        with pytest.raises(HTTPException) as exc:
            inventory.take_item(db_session, item.id, location.id, 10,
                                employee=None, note=None)
        assert exc.value.status_code == 400
        assert inventory.total_stock(db_session, item.id) == 5  # tetap utuh

    def test_take_item_tidak_ditemukan_404(self, db_session, location):
        with pytest.raises(HTTPException):
            inventory.take_item(db_session, 99999, location.id, 1, None, None)

    def test_take_quantity_0_tanpa_stock_row_400(self, db_session, item, location):
        # regresi: dulu AttributeError 500 (stock None -> .quantity), harus 400
        with pytest.raises(HTTPException) as exc:
            inventory.take_item(db_session, item.id, location.id, 0, None, None)
        assert exc.value.status_code == 400

    def test_take_stock_row_kosong_400(self, db_session, item, location):
        # lokasi tanpa baris stock: take > 0 harus 400, bukan 500
        with pytest.raises(HTTPException) as exc:
            inventory.take_item(db_session, item.id, location.id, 5, None, None)
        assert exc.value.status_code == 400

    def test_drop_quantity_0_400(self, db_session, item, location):
        # regresi: drop 0 menciptakan baris stock kosong + transaksi IN
        with pytest.raises(HTTPException) as exc:
            inventory.drop_item(db_session, item.id, location.id, 0, None, None)
        assert exc.value.status_code == 400

    def test_mutasi_stock_mengunci_baris(self, db_session, item, location):
        # regresi: take/drop/set harus pakai FOR UPDATE (cegah lost update)
        stmt = select(ItemStock).where(
            ItemStock.item_id == item.id, ItemStock.location_id == location.id
        ).with_for_update()
        sql = str(stmt.compile(dialect=postgresql.dialect()))
        assert "FOR UPDATE" in sql.upper()


class TestLocation:
    def test_duplicate_location_409(self, db_session, location):
        with pytest.raises(HTTPException) as exc:
            inventory.create_location(db_session, code="A1-R1", zone="A",
                                      rack="R1", shelf=None, description="lagi")
        assert exc.value.status_code == 409

    def test_delete_location_kosong(self, db_session, location):
        inventory.delete_location(db_session, location.id)
        assert inventory.create_location(db_session, code="A1-R1", zone="A",
                                         rack="R1", shelf=None, description="baru")

    def test_delete_location_berisi_stock_409(self, db_session, item, location):
        inventory.set_stock(db_session, item.id, location.id, 10)
        with pytest.raises(HTTPException) as exc:
            inventory.delete_location(db_session, location.id)
        assert exc.value.status_code == 409