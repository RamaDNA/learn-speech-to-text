from sqlalchemy import select

from app.models import Location
from app.services import inventory


def _resolve_item(db, item_name: str) -> tuple[str, int]:
    """Cari item paling cocok berdasarkan nama/SKU. Kembalikan (error_atau_None, item_id)."""
    items = inventory.search_items(db, item_name)
    if not items:
        return f"Barang '{item_name}' tidak ditemukan di gudang.", 0
    if len(items) == 1:
        return None, items[0].id
    exact = [i for i in items if i.name.lower().strip() == item_name.lower().strip()]
    if len(exact) == 1:
        return None, exact[0].id
    candidates = ", ".join(f"{i.name} (id {i.id})" for i in items[:5])
    return f"Ada beberapa barang mirip: {candidates}. Sebutkan nama yang lebih spesifik.", 0


def _resolve_location(db, location_code: str | None, item_id: int, prefer_positive: bool) -> tuple[str, int]:
    """Cari lokasi berdasarkan kode, atau otomatis pilih. Kembalikan (error_atau_None, location_id)."""
    if location_code:
        loc = db.scalar(select(Location).where(Location.code.ilike(location_code.strip())))
        if not loc:
            return f"Lokasi '{location_code}' tidak ditemukan. Gunakan get_locations untuk daftar lokasi.", 0
        return None, loc.id
    stocks = inventory.get_stock(db, item_id)
    if prefer_positive and stocks:
        best = max(stocks, key=lambda s: s.quantity)
        return None, best.location_id
    return "Sebutkan lokasi/rak tujuan (misal A1-R1) atau gunakan get_locations.", 0


def _fmt_items(items: list) -> str:
    return "\n".join(
        f"- {i.name} (SKU: {i.sku}, kategori: {i.category or '-'})"
        for i in items
    ) or "- (tidak ada barang yang cocok)"


def executor_search_items(db, args: dict) -> str:
    items = inventory.search_items(db, args.get("query"))
    lines = []
    for i in items:
        total = inventory.total_stock(db, i.id)
        line = f"- ID {i.id}: {i.name} (SKU {i.sku}), TOTAL STOCK {total} unit:"
        detail = []
        for s in inventory.get_stock(db, i.id):
            code = inventory.find_location_code(db, s.location_id)
            detail.append(f"    lokasi {code} (id {s.location_id}): {s.quantity}")
        if detail:
            line += "\n" + "\n".join(detail)
        else:
            line += " (belum ada stock di lokasi manapun)"
        lines.append(line)
    return "\n".join(lines) if lines else f"Barang '{args.get('query')}' tidak ditemukan."


def executor_get_item(db, args: dict) -> str:
    item_id = int(args["item_id"])
    try:
        item = inventory.search_items(db, None)
        it = next(x for x in item if x.id == item_id)
    except StopIteration:
        return f"Item id {item_id} tidak ditemukan."
    parts = [f"{it.name} (SKU {it.sku})"]
    for s in inventory.get_stock(db, it.id):
        code = inventory.find_location_code(db, s.location_id)
        parts.append(f"  - {code}: {s.quantity}")
    total = inventory.total_stock(db, it.id)
    parts.append(f"  Total: {total}")
    return "\n".join(parts)


def executor_add_item(db, args: dict) -> str:
    try:
        item = inventory.create_item(
            db,
            sku=args["sku"],
            name=args["name"],
            category=args.get("category"),
            max_stock=int(args.get("max_stock", 0)),
        )
        return f"Barang dibuat: {item.name} (SKU {item.sku}, id {item.id})"
    except Exception as e:
        return f"Gagal membuat barang: {e}"


def executor_take_item(db, args: dict) -> str:
    err, item_id = _resolve_item(db, args["item_name"])
    if err:
        return f"Gagal: {err}"
    err, location_id = _resolve_location(db, args.get("location_code"), item_id, prefer_positive=True)
    if err:
        return f"Gagal: {err}"
    try:
        txn = inventory.take_item(
            db,
            item_id=item_id,
            location_id=location_id,
            quantity=int(args["quantity"]),
            employee=args.get("employee") or None,
            note=args.get("note"),
        )
        code = inventory.find_location_code(db, location_id)
        return (
            f"OUT berhasil: {txn.quantity} unit diambil dari lokasi {code} (id {txn.id})"
        )
    except Exception as e:
        return f"Gagal mengambil barang: {e}"


def executor_drop_item(db, args: dict) -> str:
    err, item_id = _resolve_item(db, args["item_name"])
    if err:
        return f"Gagal: {err}"
    err, location_id = _resolve_location(db, args.get("location_code"), item_id, prefer_positive=False)
    if err:
        return f"Gagal: {err}"
    try:
        txn = inventory.drop_item(
            db,
            item_id=item_id,
            location_id=location_id,
            quantity=int(args["quantity"]),
            employee=args.get("employee") or None,
            note=args.get("note"),
        )
        code = inventory.find_location_code(db, location_id)
        return (
            f"IN berhasil: {txn.quantity} unit ditaruh di lokasi {code} (id {txn.id})"
        )
    except Exception as e:
        return f"Gagal menaruh barang: {e}"


def executor_get_locations(db, args: dict) -> str:
    locs = list(db.scalars(select(Location).order_by(Location.code)).all())
    return "\n".join(f"- {l.code}: {l.description or l.zone or '-'}" for l in locs) or "- (kosong)"


def resolve_location(db, location_id: int | str) -> int:
    """Terima ID angka ke lokasi."""
    return int(location_id)