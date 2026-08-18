import ast
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agent.ollama_client import OllamaUnavailable, ollama_client
from app.agent.prompt import SYSTEM_PROMPT
from app.agent.tools import (TOOLS, cancel_pending, classify_confirmation,
                             execute_tool, run_approved_pending)
from app.auth import require_api_key
from app.db import get_db
from app.models import AgentSession
from app.schemas import ChatRequest, ChatResponse

router = APIRouter(prefix="/agent", tags=["agent"], dependencies=[Depends(require_api_key)])

MAX_SESSIONS = 100  # batas aman: buang session terlama bila penuh
MAX_HISTORY = 14    # trim lama, keep system prompt


def _confirm_question(tool_name: str, args: dict) -> str:
    verb = "mengambil" if tool_name == "take_item" else "menaruh"
    name = args.get("item_name", "barang")
    qty = args.get("quantity", "?")
    loc = args.get("location_code") or "lokasi otomatis"
    return f"Konfirmasi: {verb} {qty} {name} di {loc}. Setuju?"


def _get_session(db: Session, session_id: str) -> AgentSession:
    """Muat/simpan session agent di Postgres (persisten, tidak hilang saat restart)."""
    row = db.scalar(select(AgentSession).where(AgentSession.session_id == session_id))
    if row is not None:
        msgs = row.messages or []
        if len(msgs) > MAX_HISTORY:  # trim lama, keep system
            row.messages = [msgs[0]] + msgs[-12:]
        return row
    count = db.scalar(select(func.count()).select_from(AgentSession))
    if count >= MAX_SESSIONS:
        oldest = db.scalar(select(AgentSession).order_by(AgentSession.updated_at).limit(1))
        if oldest is not None:
            db.delete(oldest)
    row = AgentSession(
        session_id=session_id,
        messages=[{"role": "system", "content": SYSTEM_PROMPT}],
    )
    db.add(row)
    return row


@router.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest, db: Session = Depends(get_db)):
    session_id = payload.session_id or f"session-{uuid.uuid4().hex}"
    session = _get_session(db, session_id)
    history = session.messages or []

    # 1) Konfirmasi pending diproses DETERMINISTIK di server, tanpa LLM
    if session.pending is not None:
        verdict = classify_confirmation(payload.message)
        if verdict == "approve":
            result = run_approved_pending(db, session)
            db.commit()
            return ChatResponse(reply=_success_reply(result), session_id=session_id)
        if verdict == "reject":
            cancel_pending(session)
            db.commit()
            return ChatResponse(reply="Baik, aksi dibatalkan. Ada yang lain?", session_id=session_id)
        # netral -> lanjut ke LLM, pending tetap aktif

    def executor(name: str, args: dict) -> str:
        return execute_tool(db, name, args, session=session)

    history.append({"role": "user", "content": payload.message})
    try:
        updated = ollama_client.run_tool_loop(history, tools=TOOLS, tool_executor=executor)
    except OllamaUnavailable:
        logging.error("Agent chat gagal: Ollama tidak tersedia")
        raise HTTPException(
            status_code=503,
            detail="Model AI sedang tidak tersedia, coba lagi nanti",
        ) from None

    final_msg = updated[-1].get("content", "").strip()
    if final_msg.startswith("{{AWAIT_CONFIRM}}"):
        _, tool_name, raw_args = final_msg.split(" ", 2)
        try:
            args = ast.literal_eval(raw_args)
        except (ValueError, SyntaxError):
            logging.warning("AWAIT_CONFIRM args tidak valid: %s", raw_args)
            args = {}
        final_msg = _confirm_question(tool_name, args)
    # list baru (bukan referensi history) agar perubahan JSON terdeteksi SQLAlchemy
    session.messages = list(updated)
    db.commit()
    return ChatResponse(reply=final_msg, session_id=session_id)


def _success_reply(result: str) -> str:
    result = result.strip()
    if result.startswith(("IN berhasil", "OUT berhasil")):
        return "Selesai. " + result
    return result
