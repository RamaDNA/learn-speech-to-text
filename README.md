# Warehouse Voice Assistant (learn-speech-to-text)

Asisten suara untuk pekerja gudang: tanya posisi barang, ambil/taruh stok, dan input barang — semua lewat suara (bilingual Indonesia/Inggris).

## Arsitektur

```
┌─────────────┐  HTTP (X-API-Key)  ┌──────────────────────┐
│  Device     │ ─────────────────▶ │  Backend (FastAPI)   │
│  (RPi/laptop│  /agent/chat       │  - agent + tools     │
│  native)    │                     │  - CRUD inventori    │
│  STT/TTS/   │                     └──────┬───────┬───────┘
│  VAD/wake   │                            │       │
└─────────────┘                     ┌──────┴──┐ ┌──┴─────────┐
                                    │Postgres │ │ Ollama     │
                                    │ 16      │ │ qwen2.5:3b │
                                    └─────────┘ └────────────┘
```

- **Device (suara)**: berjalan native (bukan Docker) agar bisa akses mic/speaker langsung.
  STT = sherpa-onnx Whisper base int8, TTS = Piper (id/en), VAD = Silero, wake word = OpenWakeWord (opsional).
- **Server**: Docker compose — Postgres (data inventori) + API FastAPI (tool calling, konfirmasi aksi) + Ollama (LLM lokal).

## Setup

### 1. Server (Docker)

```bash
cp .env.example .env   # sesuaikan API_KEY dkk.
docker compose up -d --build
docker compose exec api python seed_data.py   # seed data contoh
```

### 2. Models + device environment

```bash
py -3.12 -m venv device/.venv
device/.venv/Scripts/pip install -r device/requirements.txt
device/.venv/Scripts/python scripts/download_models.py
```

### 3. Jalankan asisten

```bash
device/.venv/Scripts/python device/main.py
```

Ucapkan contoh: *"di mana posisi baut M8?"*, *"ambil 5 mur dari rak A1"*, *"taruh 10 sekrup di B2"*.

## Struktur

```
backend/     FastAPI: CRUD inventori, agent tools, konfirmasi aksi
device/      Klien suara: STT/TTS/VAD/wake word, orkestrasi main.py
scripts/     download_models.py
```

## Keamanan

Credential (API key, password DB) lewat `.env` — jangan di-commit. Model dan venv tidak di-track git (ukuran besar), didownload/dibuat ulang dari script.

## Roadmap

- [ ] Deploy Raspberry Pi (arm64) + systemd service
- [ ] Hotwords untuk nama barang & retry transkripsi
