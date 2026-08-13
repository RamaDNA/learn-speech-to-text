"""Unit test api_client device: payload, header auth, parse, error HTTP (tanpa jaringan)."""
import json
import urllib.error

import pytest

from api_client import AgentAPI


class _FakeResponse:
    def __init__(self, body: bytes, status: int = 200):
        self._body = body
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return self._body

    def close(self):
        pass


def _install_fake(monkeypatch, response, errors=()):
    calls = {}

    def fake_urlopen(req, timeout):
        calls["req"] = req
        calls["timeout"] = timeout
        for err in errors:
            if err is not None:
                raise err
        return response

    monkeypatch.setattr("api_client.urllib.request.urlopen", fake_urlopen)
    return calls


class TestChat:
    def test_payload_dan_header(self, monkeypatch):
        body = json.dumps({"reply": "halo", "session_id": "ses-1"}).encode()
        calls = _install_fake(monkeypatch, _FakeResponse(body))

        reply, sid = AgentAPI(api_url="http://x:8000/", api_key="k-1", session_id="ses-1").chat("halo")

        assert (reply, sid) == ("halo", "ses-1")
        req = calls["req"]
        assert req.full_url == "http://x:8000/agent/chat"
        assert req.get_method() == "POST"
        # Python 3.12+ menyimpan header sebagai dict dgn kunci kanonik -> normalisasi lowercase
        h = {k.lower(): v for k, v in req.headers.items()}
        assert h["x-api-key"] == "k-1"
        assert h["content-type"] == "application/json"
        parsed = json.loads(req.data)
        assert parsed == {"message": "halo", "session_id": "ses-1"}

    def test_timeout_diteruskan(self, monkeypatch):
        calls = _install_fake(monkeypatch, _FakeResponse(b'{"reply":"x"}'))
        AgentAPI(api_url="http://x:8000", api_key="k").chat("a", timeout=7.5)
        assert calls["timeout"] == 7.5

    def test_reply_kosong_diubah_string_kosong(self, monkeypatch):
        _install_fake(monkeypatch, _FakeResponse(b'{"reply": null, "session_id": "s2"}'))
        reply, sid = AgentAPI(api_url="http://x:8000", api_key="k", session_id="s2").chat("a")
        assert reply == ""
        assert sid == "s2"

    def test_http_error_jadi_runtimeerror(self, monkeypatch):
        err = urllib.error.HTTPError("http://x", 401, "Unauthorized", {}, _FakeResponse(b'{"detail":"nope"}', 401))
        _install_fake(monkeypatch, _FakeResponse(b"{}"), errors=[err])
        with pytest.raises(RuntimeError, match="API HTTP 401"):
            AgentAPI(api_url="http://x:8000", api_key="k").chat("a")

    def test_base_url_trailing_slash_dirapikan(self, monkeypatch):
        calls = _install_fake(monkeypatch, _FakeResponse(b'{"reply":"ok"}'))
        AgentAPI(api_url="http://x:8000///", api_key="k").chat("a")
        assert calls["req"].full_url == "http://x:8000/agent/chat"