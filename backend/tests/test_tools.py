"""Unit test: klasifikasi konfirmasi + manajemen pending (termasuk regression bug)."""
import pytest

from app.agent.tools import (_await, cancel_pending, classify_confirmation,
                             execute_tool, get_pending, run_approved_pending)


class _DummyDB:
    pass


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
        result = _await("s1", "take_item", {"item_name": "Baut M8", "quantity": 5})
        assert result.startswith("{{AWAIT_CONFIRM}}")
        assert get_pending("s1") == {"tool": "take_item", "args": {"item_name": "Baut M8", "quantity": 5}}

    def test_cancel_pending(self):
        _await("s2", "take_item", {})
        cancel_pending("s2")
        assert get_pending("s2") is None

    def test_execute_tool_take_selalu_await_saat_session(self):
        """Regression B1: take/drop dengan session_id TIDAK boleh dieksekusi langsung."""
        # ubah pending lama tetap aktif
        _await("s3", "take_item", {"item_name": "Lama", "quantity": 1})
        result = execute_tool(_DummyDB(), "take_item", {"item_name": "Baru", "quantity": 2}, session_id="s3")
        # harus jadi konfirmasi baru, bukan eksekusi
        assert result.startswith("{{AWAIT_CONFIRM}}")
        pending = get_pending("s3")
        assert pending["args"]["item_name"] == "Baru"

    def test_execute_tool_tanpa_session_eksekusi_langsung(self):
        """Tanpa session_id executor dipanggil langsung (bukan AWAIT_CONFIRM)."""
        _await("s4", "take_item", {"item_name": "Baut M8", "quantity": 1})
        result = execute_tool(_DummyDB(), "take_item", {"item_name": "Baut M8", "quantity": 1})
        assert not result.startswith("{{AWAIT_CONFIRM}}")
        # DummyDB bukan session SQLAlchemy -> error internal aman (tidak bocor exception)
        assert "Terjadi kesalahan internal" in result

    def test_run_approved_pending_clears_state(self):
        _await("s5", "drop_item", {"item_name": "Baut M8", "quantity": 3})
        result = run_approved_pending(_DummyDB(), "s5")
        assert get_pending("s5") is None
        assert result is not None

    def test_run_approved_pending_kosong(self):
        cancel_pending("s6")
        assert run_approved_pending(_DummyDB(), "s6") is None