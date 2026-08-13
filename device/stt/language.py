"""Deteksi bahasa kasar (ind/en) dari teks transkripsi STT."""
import re

ID_MARKERS = {
    "ada", "di", "di mana", "mana", "rak", "baris", "sejumlah", "baut", "mur",
    "sekrup", "paku", "obeng", "gergaji", "bor", "kunci", "mata", "untuk",
    "saya", "ambil", "taruh", "bicara", "bahasa", "tidak", "tolong", "berapa",
    "cari", "posisi", "lokasi", "gudang", "barang", "yang", "dan", "dengan",
    "tolong", "selamat", "kembali", "setuju", "batal", "ya", "tidak", "oke",
}
EN_MARKERS = {
    "the", "where", "is", "are", "at", "how", "many", "please", "find",
    "location", "shelf", "rack", "row", "drill", "hammer", "screw", "bolt",
    "nut", "nail", "saw", "wrench", "yes", "no", "ok", "okay", "take", "put",
    "item", "stock", "and", "for", "what",
}


def guess_language(text: str, fallback: str = "id") -> str:
    """Heuristik sederhana: hitung marker bahasa, bandingkan. Default id."""
    words = re.findall(r"[a-zA-Z]+", text.lower())
    if not words:
        return fallback
    id_hits = sum(1 for w in words if w in ID_MARKERS)
    en_hits = sum(1 for w in words if w in EN_MARKERS)
    return "en" if en_hits > id_hits else "id"


if __name__ == "__main__":
    for t in ["di mana posisi baut M8", "where is the drill bit", "berapa stok sekrup"]:
        print(f"{t!r} -> {guess_language(t)}")