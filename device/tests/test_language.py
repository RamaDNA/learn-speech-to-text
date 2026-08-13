"""Unit test deteksi bahasa STT — murni logika, tanpa sherpa/torch."""
import pytest

from stt.language import guess_language


@pytest.mark.parametrize(
    "text,expected",
    [
        ("di mana posisi baut M8", "id"),
        ("berapa stok mur di rak A1", "id"),
        ("tolong cari barang", "id"),
        ("where is the drill bit", "en"),
        ("how many bolts in the rack", "en"),
        ("ambil 5 sekrup", "id"),
        ("take 5 screws from the shelf", "en"),
        ("", "id"),            # kosong -> fallback
        ("Baut M8", "id"),     # SKU + kata Indonesia -> id
    ],
)
def test_guess_language(text, expected):
    assert guess_language(text) == expected


def test_fallback_en_untuk_kosong():
    assert guess_language("", fallback="en") == "en"


def test_tidak_case_sensitive():
    assert guess_language("Di Mana Posisi BAUT M8") == "id"
    assert guess_language("WHERE IS THE DRILL BIT") == "en"