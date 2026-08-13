import json

import httpx

from app.config import settings


class OllamaClient:
    def __init__(self, base_url: str = None, model: str = None):
        self.base_url = base_url or settings.ollama_base_url
        self.model = model or settings.ollama_model

    def _ensure_model(self) -> None:
        try:
            r = httpx.get(f"{self.base_url}/api/show", params={"name": self.model}, timeout=10)
            if r.status_code == 200:
                return
        except httpx.HTTPError:
            pass
        print(f"[ollama] Model {self.model} belum ada, pull dari registry...")
        with httpx.stream(
            "POST", f"{self.base_url}/api/pull",
            json={"name": self.model, "stream": False}, timeout=1800,
        ) as resp:
            resp.raise_for_status()

    def chat(self, messages: list[dict], tools: list | None = None, temperature: float = 0.1) -> dict:
        payload: dict = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature},
        }
        if tools:
            payload["tools"] = tools
        resp = httpx.post(f"{self.base_url}/api/chat", json=payload, timeout=300)
        resp.raise_for_status()
        return resp.json()

    def run_tool_loop(self, messages: list[dict], tools: list | None = None,
                      tool_executor=None, max_steps: int = 6) -> list[dict]:
        """Kirim chat, eksekusi tool sampai model berhenti memanggil tool.
        Kembalikan full message history (sudah termasuk hasil tool)."""
        current = list(messages)
        for _ in range(max_steps):
            resp = self.chat(current, tools=tools)
            msg = resp.get("message", {})
            current.append(msg)
            if not msg.get("tool_calls"):
                break
            for call in msg["tool_calls"]:
                name = call.get("function", {}).get("name", "")
                raw_args = call.get("function", {}).get("arguments", {})
                args = raw_args if isinstance(raw_args, dict) else _safe_loads(raw_args)
                print(f"[agent] tool_call -> {name}({args})")
                result = tool_executor(name, args)
                print(f"[agent] tool_result <- {result[:200]}")
                current.append({
                    "role": "tool",
                    "content": result,
                    "name": name,
                })
                # Tool butuh persetujuan user -> jangan biarkan model mencoba lagi di turn ini
                if result.startswith("{{AWAIT_CONFIRM}}"):
                    return current
        return current


def _safe_loads(raw: str) -> dict:
    try:
        return json.loads(raw)
    except Exception:
        return {"_error": f"JSON tool arguments tidak valid: {raw}"}


ollama_client = OllamaClient()