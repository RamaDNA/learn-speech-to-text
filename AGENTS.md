# AGENTS.md

Asisten suara gudang bilingual (id/en). Dua bagian terpisah yang TIDAK boleh dicampur:

- `backend/` — FastAPI + agent (Ollama tool-calling) + Postgres 16. Hanya jalan via Docker Compose (`db`, `api`, `ollama`). Entry: `app/main.py` (uvicorn).
- `device/` — klien suara native Python (BUKAN Docker, butuh mic/speaker). Entry: `device/main.py`. STT = sherpa-onnx Whisper, TTS = Piper, VAD = Silero, wake word = OpenWakeWord.
- `scripts/download_models.py` — unduh model ke `models/` (gitignored, tidak boleh di-commit).

## Perintah

Server (Docker):
```
cp .env.example .env
docker compose up -d --build
docker compose exec api python seed_data.py   # manual; seed juga otomatis saat startup API (idempotent)
```

Device (Python 3.12):
```
py -3.12 -m venv device/.venv
device/.venv/Scripts/pip install -r device/requirements.txt
python scripts/download_models.py    # download besar dari HuggingFace; skip file yang sudah ada
device/.venv/Scripts/python device/main.py
```

Tests — urutan penting:
- Backend: BUTUH Postgres yang berjalan. `TEST_DATABASE_URL` default `postgresql+psycopg2://warehouse:warehouse@localhost:5432/warehouse_test`. Compose hanya membuat DB `warehouse`, jadi `warehouse_test` harus dibuat manual (mis. `docker compose exec db createdb -U warehouse warehouse_test`). Jalankan dari `backend/`: `python -m pytest tests -v`.
- Device: hanya butuh `pyyaml` + `pytest` (lihat CI). Jalankan WAJIB dari direktori `device/` (`python -m pytest tests -v`) karena test pakai import top-level (`import config`). `device/test_e2e.py` dan `device/test_mic.py` adalah script manual butuh hardware/server, bukan bagian suite pytest.
- Tidak ada lint/typecheck/formatter config di repo ini.

## Konvensi

- Semua teks repo berbahasa Indonesia: komentar, docstring, README, dan pesan commit (conventional commits, mis. `fix:`, `test:`, `ci:`, `feat:`). Ikuti ini di kode baru.
- Auth API: header `X-API-Key`, compare timing-safe (`app/auth.py`). Default `dev-secret-key-123` di `app/config.py` dan `device/config.yaml`.
- Env override device: `WAREHOUSE_API_URL` dan `WAREHOUSE_API_KEY` menimpa `server` di `device/config.yaml` (dibaca saat import, lihat `device/config.py`).
- `session_id` device di-generate otomatis saat import `device/config.py`: id unik persisten per device, disimpan di `device/.device_id` (gitignored). Jangan hardcode session id per device di kode.
- Path model di `device/config.yaml` relatif ke `device/`, di-resolve absolut oleh `config.resolve()` (contoh: `../models/...` → `<repo>/models/...`). Model wajib ada sebelum device jalan.

## Gotchas arsitektur

- Agent: loop tool-calling di `app/agent/ollama_client.py` (maks 6 step). Tool take/drop butuh konfirmasi user — hasil tool diprefiks `{{AWAIT_CONFIRM}}` dan verdict konfirmasi diproses DETERMINISTIK di `app/routers/agent.py` (`classify_confirmation`), bukan via LLM.
- Riwayat session + pending konfirmasi disimpan di Postgres (`agent_sessions`), BERTAHAN saat API restart. Maks 100 session (yang terlama dibuang), history di-trim ke 13 pesan (system + 12 terakhir).
- Test backend pakai `TestClient` TANPA lifespan (tidak ada seed, tidak ada pull ollama) — lihat `backend/tests/conftest.py`.
- Ollama pull model berjalan di background thread saat API startup (`app/main.py`), tidak memblokir.
- Default DB URL di `app/config.py` memakai host `db` (nama service Docker) — untuk run lokal di luar compose harus override `DATABASE_URL`.