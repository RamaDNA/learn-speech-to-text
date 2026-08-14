"""Test alur agent: pending approval, konfirmasi approve/reject, mock LLM."""
import ast

import pytest

from app.agent import tools
from app.services import inventory


class FakeOllama:
    """run_tool_loop: bila reply berbentuk AWAIT_CONFIRM, panggil tool_executor
    (seperti aslinya) supaya pending benar-benar terbentuk; lalu balas message tool."""
    calls = 0
    reply = ""

    def run_tool_loop(self, messages, tools=None, tool_executor=None, max_steps=6):
        FakeOllama.calls += 1
        raw = FakeOllama.reply
        current = list(messages)
        if raw.startswith("{{AWAIT_CONFIRM}}"):
            _, name, args_str = raw.split(" ", 2)
            args = ast.literal_eval(args_str)
            result = tool_executor(name, args)
            current.append({"role": "tool", "content": result, "name": name})
        else:
            current.append({"role": "assistant", "content": raw})
        return current


@pytest.fixture()
def fake_ollama(monkeypatch):
    fake = FakeOllama()
    FakeOllama.calls = 0
    FakeOllama.reply = "Baik, ada yang bisa saya bantu?"
    monkeypatch.setattr("app.routers.agent.ollama_client", fake)
    return fake


@pytest.fixture()
def seeded(client, db_session):
    item = inventory.create_item(db_session, sku="WD-40-400", name="WD-40 400ml",
                                 category="Lubricant", max_stock=50)
    loc = inventory.create_location(db_session, code="C1-R1", zone="C",
                                    rack="R1", shelf=None, description="Rak C1")
    inventory.set_stock(db_session, item.id, loc.id, 30)
    return item, loc


def _chat(client, api_key, message, session_id=None):
    return client.post("/agent/chat", headers={"X-API-Key": api_key},
                       json={"message": message, "session_id": session_id})


class TestAgentChat:
    def test_chat_biasa(self, client, api_key, fake_ollama):
        resp = _chat(client, api_key, "halo")
        assert resp.status_code == 200
        assert resp.json()["reply"] == "Baik, ada yang bisa saya bantu?"
        assert resp.json()["session_id"]

    def test_take_memerlukan_konfirmasi(self, client, api_key, fake_ollama, seeded):
        FakeOllama.reply = "{{AWAIT_CONFIRM}} take_item {'item_name': 'WD-40 400ml', 'quantity': 5}"
        resp = _chat(client, api_key, "ambil 5 WD-40", session_id="s-take-1")
        body = resp.json()
        assert "Konfirmasi: mengambil 5 WD-40 400ml" in body["reply"]
        assert tools.get_pending("s-take-1") is not None

    def test_approve_mengeksekusi(self, client, api_key, fake_ollama, seeded):
        session_id = "s-approve-1"
        FakeOllama.reply = "{{AWAIT_CONFIRM}} take_item {'item_name': 'WD-40 400ml', 'quantity': 5}"
        _chat(client, api_key, "ambil 5 WD-40", session_id=session_id)
        # LLM tidak dipanggil untuk "ya" — deterministik
        resp = _chat(client, api_key, "ya", session_id=session_id)
        body = resp.json()
        assert "OUT berhasil" in body["reply"]
        assert tools.get_pending(session_id) is None
        assert FakeOllama.calls == 1  # hanya turn pertama yang kena LLM

    def test_reject_membatalkan(self, client, api_key, fake_ollama):
        session_id = "s-reject-1"
        FakeOllama.reply = "{{AWAIT_CONFIRM}} drop_item {'item_name': 'WD-40 400ml', 'quantity': 2}"
        _chat(client, api_key, "taruh 2 WD-40", session_id=session_id)
        resp = _chat(client, api_key, "tidak jadi", session_id=session_id)
        assert resp.json()["reply"] == "Baik, aksi dibatalkan. Ada yang lain?"
        assert tools.get_pending(session_id) is None
        assert FakeOllama.calls == 1

    def test_neutral_menjaga_pending(self, client, api_key, fake_ollama, seeded):
        session_id = "s-neutral-1"
        FakeOllama.reply = "{{AWAIT_CONFIRM}} take_item {'item_name': 'WD-40 400ml', 'quantity': 1}"
        _chat(client, api_key, "ambil 1 WD-40", session_id=session_id)
        FakeOllama.reply = "Stock WD-40 ada 30 unit di C1-R1."
        resp = _chat(client, api_key, "saya mau lihat stocknya dulu", session_id=session_id)
        assert resp.json()["reply"] == "Stock WD-40 ada 30 unit di C1-R1."
        assert tools.get_pending(session_id) is not None  # pending masih menunggu
        assert FakeOllama.calls == 2  # LLM dipanggil untuk pertanyaan netral

    def test_sesi_anonim_selalu_unik(self, client, api_key, fake_ollama):
        # regresi: dulu setelah cap 100 semua anonim dapat "session-101" (history silang)
        ids = {_chat(client, api_key, "halo").json()["session_id"] for _ in range(105)}
        assert len(ids) == 105

    def test_ollama_down_503(self, client, api_key, monkeypatch):
        class DownOllama:
            def run_tool_loop(self, *args, **kwargs):
                from app.agent.ollama_client import OllamaUnavailable
                raise OllamaUnavailable("koneksi gagal")

        monkeypatch.setattr("app.routers.agent.ollama_client", DownOllama())
        resp = _chat(client, api_key, "halo", session_id="s-down-1")
        assert resp.status_code == 503
        assert "tidak tersedia" in resp.json()["detail"]

    def test_await_confirm_args_dengan_apostrof(self, client, api_key, fake_ollama, seeded):
        # regresi: dulu json.loads gagal pada apostrof -> args {} -> nama barang "barang"
        FakeOllama.reply = "{{AWAIT_CONFIRM}} drop_item {'item_name': \"It's a retur\", 'quantity': 2}"
        resp = _chat(client, api_key, "taruh 2 barang", session_id="s-apos-1")
        body = resp.json()
        assert "It's a retur" in body["reply"]