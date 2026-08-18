"""Konfigurasi device — load dari config.yaml (jalur relatif ke file ini)."""
import os
import uuid
from pathlib import Path

import yaml

_DEVICE_DIR = Path(__file__).resolve().parent
_CONFIG_FILE = _DEVICE_DIR / "config.yaml"

CONFIG = yaml.safe_load(_CONFIG_FILE.read_text(encoding="utf-8"))

CONFIG["server"]["api_key"] = os.getenv("WAREHOUSE_API_KEY", CONFIG["server"].get("api_key"))
CONFIG["server"]["api_url"] = os.getenv("WAREHOUSE_API_URL", CONFIG["server"].get("api_url"))


def _device_session_id() -> str:
    """Session id unik per device; persisten di file .device_id (jangan di-commit).

    Dua device tidak boleh berbagi sesi agent — id dibuat sekali lalu dipakai ulang
    supaya riwayat percakapan bertahan antar restart device.
    """
    id_file = _DEVICE_DIR / ".device_id"
    try:
        if id_file.exists():
            sid = id_file.read_text(encoding="utf-8").strip()
            if sid:
                return sid
        sid = f"device-{uuid.uuid4().hex}"
        id_file.write_text(sid, encoding="utf-8")
        return sid
    except OSError:
        # tidak bisa menulis file -> id acak per proses
        return f"device-{uuid.uuid4().hex}"


CONFIG["agent"]["session_id"] = _device_session_id()


def resolve(rel_path: str | None, default: str | None = None) -> str:
    """Resolve path relatif (terhadap device/) ke path absolut."""
    raw = rel_path or default
    if not raw:
        return ""
    p = Path(raw)
    if p.is_absolute():
        return str(p)
    return str((_DEVICE_DIR / p).resolve())


def build_config() -> dict:
    """Konfigurasi runtime dengan semua path model di-resolve."""
    cfg = CONFIG
    audio = dict(cfg["audio"])
    stt = dict(cfg["stt"])
    stt["model_dir"] = resolve(stt.get("model_dir"))
    vad = dict(cfg["vad"])
    vad["model_path"] = resolve(vad.get("model_path"))
    tts = dict(cfg["tts"])
    tts["voice_id"] = resolve(tts.get("voice_id"))
    tts["voice_en"] = resolve(tts.get("voice_en"))
    wake = dict(cfg["wakeword"])
    server = dict(cfg["server"])
    agent = dict(cfg["agent"])
    return {
        "audio": audio,
        "stt": stt,
        "vad": vad,
        "tts": tts,
        "wakeword": wake,
        "server": server,
        "agent": agent,
    }


if __name__ == "__main__":
    import pprint

    pprint.pprint(build_config())