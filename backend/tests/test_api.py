"""Test API level (TestClient): auth + CRUD + alur stock."""


def _headers(api_key):
    return {"X-API-Key": api_key}


class TestAuth:
    def test_tanpa_api_key_401(self, client):
        assert client.get("/items").status_code == 401

    def test_api_key_salah_401(self, client):
        assert client.get("/items", headers={"X-API-Key": "salah"}).status_code == 401

    def test_health_tanpa_auth(self, client):
        assert client.get("/health").json() == {"status": "ok"}


class TestItemAPI:
    def test_crud_lengkap(self, client, api_key):
        headers = _headers(api_key)

        created = client.post("/items", json={
            "sku": "NUT-M10", "name": "Mur M10", "category": "Fastener", "max_stock": 200,
        }, headers=headers)
        assert created.status_code == 201
        item_id = created.json()["id"]
        assert created.json()["name"] == "Mur M10"

        listed = client.get("/items", headers=headers)
        assert listed.status_code == 200
        assert any(i["id"] == item_id for i in listed.json())

        updated = client.patch(f"/items/{item_id}", json={"max_stock": 300}, headers=headers)
        assert updated.status_code == 200
        assert updated.json()["max_stock"] == 300

        deleted = client.delete(f"/items/{item_id}", headers=headers)
        assert deleted.status_code == 204
        assert client.get(f"/items/{item_id}", headers=headers).status_code == 404

    def test_duplikat_sku_409(self, client, api_key):
        headers = _headers(api_key)
        payload = {"sku": "DUPE-1", "name": "Dupe", "category": "X", "max_stock": 1}
        assert client.post("/items", json=payload, headers=headers).status_code == 201
        assert client.post("/items", json=payload, headers=headers).status_code == 409


class TestStockAPI:
    def _seed(self, client, headers):
        item = client.post("/items", json={"sku": "SCR-M4", "name": "Sekrup M4", "max_stock": 50}, headers=headers).json()
        loc = client.post("/locations", json={"code": "B2-R1", "description": "Rak B2"}, headers=headers).json()
        return item["id"], loc["id"]

    def test_alur_take_drop(self, client, api_key):
        headers = _headers(api_key)
        item_id, loc_id = self._seed(client, headers)

        client.put(f"/stock/{item_id}/{loc_id}?quantity=40", headers=headers).raise_for_status()
        assert client.get(f"/stock/{item_id}/total", headers=headers).json()["total"] == 40

        out = client.post(f"/stock/take?item_id={item_id}&location_id={loc_id}&quantity=10&employee=Andi", headers=headers)
        assert out.status_code == 201
        assert out.json()["type"] == "OUT"

        ins = client.post(f"/stock/drop?item_id={item_id}&location_id={loc_id}&quantity=5", headers=headers)
        assert ins.status_code == 201
        assert ins.json()["type"] == "IN"
        assert client.get(f"/stock/{item_id}/total", headers=headers).json()["total"] == 35

        txns = client.get(f"/transactions?item_id={item_id}", headers=headers).json()
        assert len(txns) == 2

    def test_take_quantity_invalid_422(self, client, api_key):
        headers = _headers(api_key)
        item_id, loc_id = self._seed(client, headers)
        resp = client.post(f"/stock/take?item_id={item_id}&location_id={loc_id}&quantity=0", headers=headers)
        assert resp.status_code == 422

    def test_take_melebihi_stock_400(self, client, api_key):
        headers = _headers(api_key)
        item_id, loc_id = self._seed(client, headers)
        client.put(f"/stock/{item_id}/{loc_id}?quantity=3", headers=headers).raise_for_status()
        resp = client.post(f"/stock/take?item_id={item_id}&location_id={loc_id}&quantity=5", headers=headers)
        assert resp.status_code == 400

    def test_set_stock_negatif_400(self, client, api_key):
        headers = _headers(api_key)
        item_id, loc_id = self._seed(client, headers)
        resp = client.put(f"/stock/{item_id}/{loc_id}?quantity=-5", headers=headers)
        assert resp.status_code == 400