"""Wake word detection via OpenWakeWord (model bawaan package).

Catatan: model "hey jarvis" dari luar tidak tersedia; gunakan model bawaan
"alexa" / "hey_mycroft" / "hi_melissa" dsb. dari paket openwakeword.
"""
from pathlib import Path

import numpy as np


class WakeWordDetector:
    def __init__(self, wake_words: list[str] | None = None, threshold: float = 0.5):
        import openwakeword

        self.threshold = threshold
        self.names = wake_words or ["hey_mycroft"]
        self._oww = None
        try:
            self._oww = openwakeword.Model(wakeword_models=self.names)
        except Exception as exc:
            raise RuntimeError(
                f"Gagal load OpenWakeWord models {self.names}: {exc}"
            ) from exc

    def feed(self, pcm16: bytes) -> tuple[str, float] | None:
        """Deteksi wake word dari chunk PCM16 16kHz. Return (name, score) bila kena."""
        if not self._oww:
            return None
        samples = np.frombuffer(pcm16, dtype=np.int16).astype(np.float32) / 32768.0
        pred = self._oww.predict(samples)
        for name in self.names:
            score = pred.get(name, 0.0)
            if score >= self.threshold:
                return name, float(score)
        return None

    def reset(self):
        if self._oww:
            self._oww.reset()


def available_models() -> list[str]:
    import openwakeword

    return sorted(openwakeword.MODELS.keys())


if __name__ == "__main__":
    print("Model tersedia:", ", ".join(available_models()))