"""Piper TTS — sintesis suara, mendukung bahasa id & en, dengan cache."""
import hashlib
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

import numpy as np
import sounddevice as sd
import soundfile as sf

BASE = Path(__file__).resolve().parents[2] / "models"

VOICES = {
    "id": BASE / "piper-id_ID-news_tts-medium" / "id_ID-news_tts-medium.onnx",
    "en": BASE / "piper-en_US-lessac-medium" / "en_US-lessac-medium.onnx",
}


class PiperTTS:
    def __init__(self, voice_id: str = "id", voice_en: str = "en", device=None,
                 cache_dir: Path = None):
        self.voice_id = VOICES.get(voice_id, Path(voice_id)) if voice_id in VOICES else Path(voice_id)
        self.voice_en = VOICES.get(voice_en, Path(voice_en)) if voice_en in VOICES else Path(voice_en)
        self.device = device
        self.cache_dir = cache_dir or (Path(__file__).resolve().parents[1] / ".tts_cache")
        self.cache_dir.mkdir(exist_ok=True)
        self._lock = threading.Lock()

    def _voice(self, lang: str):
        return self.voice_id if lang == "id" else self.voice_en

    def _piper_bin(self) -> str:
        # piper-tts Python: pakai module piper cli
        return "piper"

    def synth(self, text: str, lang: str = "id", output_wav: str | Path | None = None,
              sample_rate: int = 22050) -> np.ndarray | None:
        """Sintesis text -> audio float. Bisa tulis file .wav."""
        cache_key = f"{lang}_{hashlib.md5(text.encode('utf-8')).hexdigest()}.wav"
        cache_path = self.cache_dir / cache_key
        if cache_path.exists():
            data, sr = sf.read(str(cache_path), dtype="float32")
            if output_wav:
                sf.write(str(output_wav), data, sr)
            return data

        with tempfile.TemporaryDirectory() as td:
            tmp_wav = Path(td) / "out.wav"
            cmd = [
                sys.executable, "-m", "piper",
                "--model", str(self._voice(lang)),
                "--output_file", str(tmp_wav),
                "--length_scale", "1.0",
                "--sentence_silence", "0.3",
            ]
            proc = subprocess.run(
                cmd, input=text.encode("utf-8"), capture_output=True, timeout=60
            )
            if proc.returncode != 0 or not tmp_wav.exists():
                raise RuntimeError(f"Piper gagal: {proc.stderr.decode(errors='ignore')[:300]}")
            data, sr = sf.read(str(tmp_wav), dtype="float32")
            if output_wav:
                sf.write(str(output_wav), data, sr)
            sf.write(str(cache_path), data, sr)
            return data

    def speak(self, text: str, lang: str = "id", block: bool = True) -> None:
        """Sintesis + mainkan. Menjalankan audio pada thread terpisah."""
        data = self.synth(text, lang=lang)

        def _play():
            with self._lock:
                sd.play(data, 22050, device=self.device)
                sd.wait()

        if block:
            _play()
        else:
            threading.Thread(target=_play, daemon=True).start()

    def speak_blocking_play(self, data: np.ndarray) -> None:
        with self._lock:
            sd.play(data, 22050, device=self.device)
            sd.wait()


if __name__ == "__main__":
    import sys

    tts = PiperTTS()
    text = sys.argv[1] if len(sys.argv) > 1 else "Selamat datang di sistem gudang. Silakan bicara."
    lang = sys.argv[2] if len(sys.argv) > 2 else "id"
    print(f"TTS ({lang}): {text}")
    tts.speak(text, lang)