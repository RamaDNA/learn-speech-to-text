"""Konfigurasi device — load dari config.yaml (jalur relatif ke file ini)."""
import os
from pathlib import Path

import yaml

_DEVICE_DIR = Path(__file__).resolve().parent
_CONFIG_FILE = _DEVICE_DIR / "config.yaml"

CONFIG = yaml.safe_load(_CONFIG_FILE.read_text(encoding="utf-8"))

CONFIG["server"]["api_key"] = os.getenv("WAREHOUSE_API_KEY", CONFIG["server"].get("api_key"))
CONFIG["server"]["api_url"] = os.getenv("WAREHOUSE_API_URL", CONFIG["server"].get("api_url"))


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