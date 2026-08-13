from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.agent.ollama_client import ollama_client
from app.agent.prompt import SYSTEM_PROMPT
from app.agent.tools import (TOOLS, cancel_pending, classify_confirmation,
                             execute_tool, get_pending, run_approved_pending,
                             set_last_message)
from app.auth import require_api_key
from app.db import get_db
from app.schemas import ChatRequest, ChatResponse

router = APIRouter(prefix="/agent", tags=["agent"], dependencies=[Depends(require_api_key)])

_sessions: dict[str, list[dict]] = {}


def _confirm_question(tool_name: str, args: dict) -> str:
    verb = "mengambil" if tool_name == "take_item" else "menaruh"
    name = args.get("item_name", "barang")
    qty = args.get("quantity", "?")
    loc = args.get("location_code") or "lokasi otomatis"
    return f"Konfirmasi: {verb} {qty} {name} di {loc}. Setuju?"


def _get_history(session_id: str) -> list[dict]:
    if session_id not in _sessions:
        _sessions[session_id] = [{"role": "system", "content": SYSTEM_PROMPT}]
    history = _sessions[session_id]
    if len(history) > 14:  # trim lama, keep system
        _sessions[session_id] = [history[0]] + history[-12:]
    return _sessions[session_id]


@router.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest, db: Session = Depends(get_db)):
    session_id = payload.session_id or f"session-{len(_sessions) + 1}"
    history = _get_history(session_id)
    set_last_message(session_id, payload.message)

    # 1) Konfirmasi pending diproses DETERMINISTIK di server, tanpa LLM
    if get_pending(session_id) is not None:
        verdict = classify_confirmation(payload.message)
        if verdict == "approve":
            result = run_approved_pending(db, session_id)
            return ChatResponse(reply=_success_reply(result), session_id=session_id)
        if verdict == "reject":
            cancel_pending(session_id)
            return ChatResponse(reply="Baik, aksi dibatalkan. Ada yang lain?", session_id=session_id)
        # netral -> lanjut ke LLM, pending tetap aktif

    def executor(name: str, args: dict) -> str:
        return execute_tool(db, name, args, session_id=session_id)

    history.append({"role": "user", "content": payload.message})
    updated = ollama_client.run_tool_loop(history, tools=TOOLS, tool_executor=executor)

    final_msg = updated[-1].get("content", "").strip()
    if final_msg.startswith("{{AWAIT_CONFIRM}}"):
        _, tool_name, raw_args = final_msg.split(" ", 2)
        try:
            import json as _json
            args = _json.loads(raw_args.replace("'", '"'))
        except Exception:
            args = {}
        final_msg = _confirm_question(tool_name, args)
    _sessions[session_id] = updated
    return ChatResponse(reply=final_msg, session_id=session_id)


def _success_reply(result: str) -> str:
    result = result.strip()
    if result.startswith(("IN berhasil", "OUT berhasil")):
        return "Selesai. " + result
    return result