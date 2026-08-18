"""Manajemen pending approval untuk tool agent + klasifikasi konfirmasi.

State pending disimpan di kolom `pending` pada baris AgentSession (DB),
bukan dict in-memory — sehingga konfirmasi tidak hilang saat API restart.
"""
import re
from typing import Any

from sqlalchemy.orm import Session

from app.agent import executors as ex
from app.models import AgentSession

POSITIVE = {"ya", "yes", "y", "betul", "benar", "siap", "oke", "ok", "setuju", "boleh", "lanjut", "gass", "gas", "iya", "bolehkan", "ayo"}
NEGATIVE = {"tidak", "no", "gak", "nggak", "batal", "cancel", "jangan", "stop", "nope", "enggak", "ga"}


def get_pending(session: AgentSession) -> dict | None:
    return session.pending


def cancel_pending(session: AgentSession) -> None:
    session.pending = None


_WORD_RE = re.compile(r"[a-z]+")


def classify_confirmation(message: str) -> str:
    """'approve' | 'reject' | 'neutral' — pencocokan per-kata (bukan substring)."""
    words = set(_WORD_RE.findall(message.lower()))
    if words & NEGATIVE and not words & POSITIVE:
        return "reject"
    if words & POSITIVE:
        return "approve"
    return "neutral"


def _await(session: AgentSession, tool_name: str, args: dict) -> str:
    session.pending = {"tool": tool_name, "args": dict(args)}
    # Kode khusus: router menyulapnya jadi pertanyaan konfirmasi yang natural
    return f"{{{{AWAIT_CONFIRM}}}} {tool_name} {args}"


def execute_tool(db: Session, tool_name: str, args: dict, session: AgentSession | None = None) -> str:
    # take/drop SELALU butuh konfirmasi user; pengeksekusi hanya lewat
    # run_approved_pending() yang memanggil TANPA session (sudah disetujui).
    if session is not None and tool_name in ("take_item", "drop_item"):
        return _await(session, tool_name, args)

    fn = getattr(ex, f"executor_{tool_name}", None)
    if fn is None:
        return f"Tool {tool_name} tidak dikenal."
    try:
        return fn(db, args)
    except Exception as e:  # safety net — jangan bocor exception ke model
        return f"Terjadi kesalahan internal saat eksekusi tool {tool_name}: {e}"


def run_approved_pending(db: Session, session: AgentSession) -> str | None:
    """Eksekusi langsung pending yang sudah disetujui. Return None jika tidak ada."""
    pending = get_pending(session)
    if not pending:
        return None
    cancel_pending(session)
    return execute_tool(db, pending["tool"], pending["args"])


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_items",
            "description": "Cari barang di gudang berdasarkan nama/SKU/kategori. Kembalikan daftar item lengkap dengan jumlah stock per lokasi.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Kata kunci pencarian, misal 'baut' atau 'M8'"}
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_item",
            "description": "Ambil detail stock satu item: daftar lokasi + jumlah per lokasi (biasanya sudah cukup dari search_items).",
            "parameters": {
                "type": "object",
                "properties": {"item_id": {"type": "integer", "description": "ID item dari search_items"}},
                "required": ["item_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_item",
            "description": "Tambah barang baru ke katalog gudang (belum menaruh stock). HANYA jika user eksplisit minta menambah/input barang baru yang belum ada.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sku": {"type": "string", "description": "Kode SKU unik, misal 'BOLT-M8'"},
                    "name": {"type": "string", "description": "Nama barang yang jelas, misal 'Baut M8'"},
                    "category": {"type": "string", "description": "Kategori, misal 'Fastener'"},
                    "max_stock": {"type": "integer", "description": "Kapasitas maksimal, default 0"},
                },
                "required": ["sku", "name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "take_item",
            "description": "Ambil/mengeluarkan barang dari gudang (stock berkurang + transaksi OUT). Berikan NAMA BARANG, bukan ID. Server akan otomatis meminta konfirmasi user sebelum eksekusi.",
            "parameters": {
                "type": "object",
                "properties": {
                    "item_name": {"type": "string", "description": "Nama barang yang jelas, misal 'Baut M8'"},
                    "location_code": {"type": "string", "description": "Kode lokasi/rak, misal 'A1-R1'. Boleh kosong, sistem pilih lokasi dengan stock terbanyak"},
                    "quantity": {"type": "integer", "description": "Jumlah yang diambil"},
                    "employee": {"type": "string", "description": "Nama karyawan yang mengambil, bila ada"},
                    "note": {"type": "string", "description": "Catatan, misal alasan"},
                },
                "required": ["item_name", "quantity"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "drop_item",
            "description": "Menaruh/memasukkan barang ke gudang (stock bertambah + transaksi IN). Berikan NAMA BARANG, bukan ID. Server akan otomatis meminta konfirmasi user sebelum eksekusi.",
            "parameters": {
                "type": "object",
                "properties": {
                    "item_name": {"type": "string", "description": "Nama barang yang jelas, misal 'Baut M8'"},
                    "location_code": {"type": "string", "description": "Kode lokasi/rak tujuan, misal 'B1-R1'. WAJIB diisi jika user menyebut lokasi"},
                    "quantity": {"type": "integer", "description": "Jumlah yang ditaruh"},
                    "employee": {"type": "string", "description": "Nama karyawan, bila ada"},
                    "note": {"type": "string", "description": "Catatan"},
                },
                "required": ["item_name", "quantity"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_locations",
            "description": "Daftar semua lokasi penyimpanan di gudang: kode rak + deskripsi.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
]