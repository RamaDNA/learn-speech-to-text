"""Unit test: klasifikasi konfirmasi + manajemen pending (termasuk regression bug)."""
import pytest

from app.agent.tools import (_await, cancel_pending, classify_confirmation,
                             execute_tool, get_pending, run_approved_pending)


class _DummyDB:
    pass


class _FakeSession:
    """Tiruan AgentSession — pending disimpan sebagai atribut (bukan dict global)."""

    def __init__(self):
        self.pending = None


class TestClassifyConfirmation:
    @pytest.mark.parametrize(
        "message,expected",
        [
            ("ya", "approve"),
            ("ya setuju", "approve"),
            ("yes", "approve"),
            ("betul", "approve"),
            ("gass", "approve"),
            ("oke lanjut", "approve"),
            # regression bug: "ya" di dalam "saya" bukan approve
            ("saya mau lihat stock dulu", "neutral"),
            ("di mana mur M8", "neutral"),
            ("berapa stok baut", "neutral"),
            ("tidak", "reject"),
            ("nggak jadi", "reject"),
            ("batal saja", "reject"),
            ("jangan dulu", "reject"),
            ("saya batal", "reject"),
            # reject menang bila ada kata negatif dan tidak ada positif
            ("tidak usah, terima kasih", "reject"),
        ],
    )
    def test_classify(self, message, expected):
        assert classify_confirmation(message) == expected

    def test_substring_tidak_menipu(self):
        # "ga" pada "pagar"/"gaji" tidak boleh jadi reject
        assert classify_confirmation("cari barang di pagar") == "neutral"
        assert classify_confirmation("cek gaji karyawan") == "neutral"


class TestPendingFlow:
    def test_await_set_pending(self):
        s = _FakeSession()
        result = _await(s, "take_item", {"item_name": "Baut M8", "quantity": 5})
        assert result.startswith("{{AWAIT_CONFIRM}}")
        assert s.pending == {"tool": "take_item", "args": {"item_name": "Baut M8", "quantity": 5}}

    def test_cancel_pending(self):
        s = _FakeSession()
        _await(s, "take_item", {})
        cancel_pending(s)
        assert get_pending(s) is None

    def test_execute_tool_take_selalu_await_saat_session(self):
        """Regression B1: take/drop dengan session TIDAK boleh dieksekusi langsung."""
        s = _FakeSession()
        # ubah pending lama tetap aktif
        _await(s, "take_item", {"item_name": "Lama", "quantity": 1})
        result = execute_tool(_DummyDB(), "take_item", {"item_name": "Baru", "quantity": 2}, session=s)
        # harus jadi konfirmasi baru, bukan eksekusi
        assert result.startswith("{{AWAIT_CONFIRM}}")
        assert s.pending["args"]["item_name"] == "Baru"

    def test_execute_tool_tanpa_session_eksekusi_langsung(self):
        """Tanpa session (sudah disetujui) executor dipanggil langsung, bukan AWAIT_CONFIRM."""
        s = _FakeSession()
        _await(s, "take_item", {"item_name": "Baut M8", "quantity": 1})
        result = execute_tool(_DummyDB(), "take_item", {"item_name": "Baut M8", "quantity": 1})
        assert not result.startswith("{{AWAIT_CONFIRM}}")
        # DummyDB bukan session SQLAlchemy -> error internal aman (tidak bocor exception)
        assert "Terjadi kesalahan internal" in result

    def test_run_approved_pending_clears_state(self):
        s = _FakeSession()
        _await(s, "drop_item", {"item_name": "Baut M8", "quantity": 3})
        result = run_approved_pending(_DummyDB(), s)
        assert s.pending is None
        assert result is not None

    def test_run_approved_pending_kosong(self):
        s = _FakeSession()
        assert run_approved_pending(_DummyDB(), s) is None