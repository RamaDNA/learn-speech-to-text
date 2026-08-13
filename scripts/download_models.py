import argparse
import os
import zipfile
from pathlib import Path

import requests

MODELS_DIR = Path(__file__).resolve().parent.parent / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)

BASE_HF = "https://huggingface.co/csukuangfj/sherpa-onnx-whisper-tiny/resolve/main"

STT_SOURCES = {
    "sherpa-onnx-whisper-tiny": [
        f"{BASE_HF}/tiny-encoder.int8.onnx",
        f"{BASE_HF}/tiny-decoder.int8.onnx",
        f"{BASE_HF}/tiny-tokens.txt",
    ],
}

TTS_SOURCES = {
    "piper-id_ID-news_tts-medium": [
        "https://huggingface.co/rhasspy/piper-voices/resolve/main/id/id_ID/news_tts/medium/id_ID-news_tts-medium.onnx",
        "https://huggingface.co/rhasspy/piper-voices/resolve/main/id/id_ID/news_tts/medium/id_ID-news_tts-medium.onnx.json",
    ],
    "piper-en_US-lessac-medium": [
        "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx",
        "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json",
    ],
}

VAD_URL = "https://github.com/snakers4/silero-vad/raw/master/src/silero_vad/data/silero_vad.onnx"

WAKEWORD_URL = "https://github.com/dscripka/openWakeWord/releases/download/v0.6.0/hey_jarvis_v0.1.onnx"


def download(url: str, dest: Path) -> None:
    if dest.exists():
        print(f"  skip  {dest.name}")
        return
    print(f"  get   {url.split('/')[-1]} ({dest.name})")
    r = requests.get(url, stream=True, timeout=120)
    r.raise_for_status()
    tmp = dest.with_suffix(dest.suffix + ".part")
    with open(tmp, "wb") as f:
        for chunk in r.iter_content(chunk_size=1 << 16):
            f.write(chunk)
    tmp.rename(dest)


def extract_tarbz2(path: Path) -> None:
    import tarfile

    print(f"  extract {path.name}")
    with tarfile.open(path, "r:bz2") as t:
        t.extractall(MODELS_DIR, filter="data")
    path.unlink()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stt-only", action="store_true")
    ap.add_argument("--tts-only", action="store_true")
    args = ap.parse_args()

    if not args.tts_only:
        print("[STT] Whisper-tiny int8 (multilingual ind+en)")
        for name, urls in STT_SOURCES.items():
            dest_dir = MODELS_DIR / name
            dest_dir.mkdir(exist_ok=True)
            for url in urls:
                download(url, dest_dir / url.split("/")[-1])

        print("[VAD] silero-vad.onnx")
        download(VAD_URL, MODELS_DIR / "silero_vad.onnx")

        print("[WakeWord] dari package openwakeword (hey jarvis built-in)")

    if not args.stt_only:
        print("[TTS] Piper voices (id + en)")
        for voice, urls in TTS_SOURCES.items():
            vdir = MODELS_DIR / voice
            vdir.mkdir(exist_ok=True)
            for url in urls:
                download(url, vdir / url.split("/")[-1])

    print("\nSelesai. Model tersimpan di:", MODELS_DIR)


if __name__ == "__main__":
    main()