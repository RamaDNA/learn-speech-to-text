"""Audio capture 16kHz mono via sounddevice + VAD segmentasi."""
from pathlib import Path

import numpy as np
import sounddevice as sd

from audio.vad import VAD

SAMPLE_RATE = 16000
CHUNK = int(0.03 * SAMPLE_RATE)  # 30ms


def list_devices() -> None:
    print(sd.query_devices())


class VoiceCapture:
    """Rekam percakapan dari mic: tunggu speech, kumpulkan, akhiri saat silence.

    - pre_roll_ms: audio sebelum speech terdeteksi ikut disertakan (hindari terpotong).
    - max_seconds: batas aman.
    """

    def __init__(self, vad: VAD, device=None, sample_rate: int = SAMPLE_RATE,
                 chunk: int = CHUNK, pre_roll_ms: int = 300,
                 max_seconds: float = 30.0):
        self.vad = vad
        self.device = device
        self.sample_rate = sample_rate
        self.chunk = chunk
        self.pre_roll = int(pre_roll_ms * sample_rate / 1000)
        self.max_seconds = max_seconds
        self._spoken_samples = 0
        self._silence_samples = 0

    def stop(self):
        sd.stop()

    def capture_once(self, wake_fn=None) -> bytes | None:
        """Rekam satu ucapan penuh. wake_fn optional (contoh notifikasi level mic).
        Return PCM16 bytes; None bila timeout tanpa speech."""
        spoken_chunks: list[bytes] = []
        pre_roll: list[bytes] = []
        pre_roll_len = self.pre_roll // self.chunk
        speech_started = False
        total_samples = 0

        with sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype="int16",
            device=self.device,
            blocksize=self.chunk,
        ) as stream:
            speech_run = 0
            while total_samples < self.max_seconds * self.sample_rate:
                data, _ = stream.read(self.chunk)
                pcm = data.tobytes()
                prob = self.vad.is_speech(pcm)
                total_samples += len(data)

                if speech_started:
                    spoken_chunks.append(pcm)
                    self._spoken_samples += len(data)
                    self._silence_samples = self._silence_samples + len(data) if prob < self.vad.threshold else 0
                    if self._silence_samples >= self.vad.min_silence_samples:
                        break  # diam cukup lama -> selesai
                else:
                    pre_roll.append(pcm)
                    if len(pre_roll) > pre_roll_len:
                        pre_roll.pop(0)
                    if prob >= self.vad.threshold:
                        speech_run += len(data)
                        if speech_run >= self.vad.min_speech_samples:
                            speech_started = True
                            spoken_chunks = list(pre_roll) + [pcm]
                            self._spoken_samples = speech_run
                            self._silence_samples = 0
                    else:
                        speech_run = 0
        if not speech_started:
            return None
        self.vad.reset()
        return b"".join(spoken_chunks)


def record_until_silence(
    vad,
    sample_rate: int = SAMPLE_RATE,
    device=None,
    max_seconds: float = 30.0,
    pre_roll_ms: int = 300,
) -> bytes | None:
    """Kompabilitas: rekam sampai VAD mendeteksi akhir ucapan. Return PCM16 bytes."""
    cap = VoiceCapture(vad, device=device, sample_rate=sample_rate, max_seconds=max_seconds,
                       pre_roll_ms=pre_roll_ms)
    return cap.capture_once()


if __name__ == "__main__":
    from config import build_config

    cfg = build_config()
    vad = VAD(cfg["vad"]["model_path"], threshold=cfg["vad"]["threshold"],
              min_speech_ms=cfg["vad"]["min_speech_ms"],
              min_silence_ms=cfg["vad"]["min_silence_ms"])
    print("Bicara sekarang...")
    pcm = record_until_silence(vad, device=cfg["audio"]["device"])
    if pcm:
        Path("last_utterance.raw").write_bytes(pcm)
        print(f"Tertangkap {len(pcm)} bytes")
    else:
        print("Tidak ada ucapan terdeteksi.")