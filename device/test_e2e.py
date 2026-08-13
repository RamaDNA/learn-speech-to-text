"""E2E otomatis: mainkan wav -> tangkap via Stereo Mix -> STT -> agent.

Tanpa perlu user bicara. Gunakan device 'Stereo Mix' sebagai mic loopback.
"""
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np
import sounddevice as sd
import soundfile as sf

from api_client import AgentAPI
from audio.mic import VoiceCapture
from audio.vad import VAD
from config import build_config
from stt.language import guess_language
from stt.sherpa_stt import WhisperSTT

ROOT = Path(__file__).resolve().parents[1]


def find_loopback_device():
    for i, d in enumerate(sd.query_devices()):
        name = str(d["name"]).lower()
        if ("stereo mix" in name or "what u hear" in name) and d["max_input_channels"] > 0:
            return i
    return None


def main(utterance_file: str, lang: str):
    cfg = build_config()
    vad = VAD(cfg["vad"]["model_path"], threshold=cfg["vad"]["threshold"])
    stt = WhisperSTT(model_dir=cfg["stt"]["model_dir"], language="auto")
    api = AgentAPI()
    loopback = find_loopback_device()
    print("Stereo Mix device:", loopback)

    data, sr = sf.read(utterance_file, dtype="float32")
    holder = {}

    def capture():
        cap = VoiceCapture(vad, device=loopback, max_seconds=20.0)
        holder["pcm"] = cap.capture_once()

    t = threading.Thread(target=capture)
    t.start()
    time.sleep(0.5)
    sd.play(data, sr)
    t.join(timeout=30)
    pcm = holder.get("pcm")
    if pcm is None:
        print("[FAIL] tidak tertangkap loopback")
        return
    text = stt.transcribe(pcm)
    print(f"[STT] {text!r}")
    if not text:
        print("[FAIL] STT kosong")
        return
    reply, sid = api.chat(text)
    print(f"[AGENT] {reply}")
    gl = guess_language(reply)
    print(f"[LANG] {gl} -> RESULT: {'PASS' if gl else '?'}")


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("wav")
    ap.add_argument("--lang", default="id")
    args = ap.parse_args()
    main(args.wav, args.lang)