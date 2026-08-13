"""HTTP client ke backend warehouse agent (/agent/chat)."""
import json
import urllib.error
import urllib.request

from config import CONFIG


class AgentAPI:
    def __init__(self, api_url: str | None = None, api_key: str | None = None, session_id: str | None = None):
        cfg = CONFIG["server"]
        self.base_url = (api_url or cfg["api_url"]).rstrip("/")
        self.api_key = api_key or cfg["api_key"]
        self.session_id = session_id or CONFIG["agent"].get("session_id", "device-demo-01")

    def chat(self, message: str, timeout: float = 60.0) -> tuple[str, str]:
        """Kirim pesan, return (reply, session_id)."""
        payload = json.dumps(
            {"message": message, "session_id": self.session_id}
        ).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/agent/chat",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "X-API-Key": self.api_key,
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"API HTTP {e.code}: {body}") from e
        reply = str(data.get("reply", "")).strip()
        sid = str(data.get("session_id") or self.session_id)
        return reply, sid


if __name__ == "__main__":
    api = AgentAPI()
    reply, sid = api.chat("di mana posisi baut M8?")
    print(f"[{sid}] {reply}")