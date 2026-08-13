"""Sherpa-ONNX Whisper — transkripsi offline, auto-detect bahasa.

Model tersedia:
  - sherpa-onnx-whisper-tiny  (ringan, cepat; english bagus, indonesia lebih lemah)
  - sherpa-onnx-whisper-base  (default; lebih akurat untuk bahasa Indonesia)
"""
from pathlib import Path

import numpy as np
import sherpa_onnx
import soundfile as sf

SIZES = {
    "tiny": ("tiny-encoder.int8.onnx", "tiny-decoder.int8.onnx", "tiny-tokens.txt"),
    "base": ("base-encoder.int8.onnx", "base-decoder.int8.onnx", "base-tokens.txt"),
}


def default_model_dir(size: str = "base") -> Path:
    return Path(__file__).resolve().parents[2] / "models" / f"sherpa-onnx-whisper-{size}"


class WhisperSTT:
    def __init__(self, model_dir: str | Path | None = None, size: str = "base",
                 language: str = "auto", num_threads: int = 4,
                 hotwords: list[str] | None = None, tail_paddings: int = 30):
        if model_dir is None:
            model_dir = default_model_dir(size)
        model_dir = Path(model_dir)
        enc, dec, tok = SIZES.get(size, SIZES["base"])
        self.recognizer = sherpa_onnx.OfflineRecognizer.from_whisper(
            encoder=str(model_dir / enc),
            decoder=str(model_dir / dec),
            tokens=str(model_dir / tok),
            language=language if language != "auto" else "",
            task="transcribe",
            tail_paddings=tail_paddings,
            num_threads=num_threads,
            decoding_method="greedy_search",
            provider="cpu",
        )
        self._hotwords = hotwords or []

    def transcribe(self, pcm16: bytes) -> str:
        if not pcm16:
            return ""
        samples = np.frombuffer(pcm16, dtype=np.int16).astype(np.float32) / 32768.0
        stream = self.recognizer.create_stream()
        stream.accept_waveform(16000, samples)
        self.recognizer.decode_stream(stream)
        text = stream.result.text.strip()
        return text

    def transcribe_file(self, wav_path: str | Path) -> str:
        wav_path = Path(wav_path)
        data, sr = sf.read(str(wav_path), dtype="float32", always_2d=False)
        if sr != 16000:
            x_old = np.linspace(0, 1, len(data), endpoint=False)
            x_new = np.linspace(0, 1, int(len(data) * 16000 / sr), endpoint=False)
            data = np.interp(x_new, x_old, data).astype(np.float32)
        samples = data if data.ndim == 1 else data[:, 0]
        stream = self.recognizer.create_stream()
        stream.accept_waveform(16000, np.ascontiguousarray(samples))
        self.recognizer.decode_stream(stream)
        return stream.result.text.strip()


if __name__ == "__main__":
    import sys

    size = "base"
    if len(sys.argv) > 2:
        size = sys.argv[2]
    stt = WhisperSTT(size=size, language="auto")
    wav = sys.argv[1] if len(sys.argv) > 1 else None
    if wav:
        print("Hasil:", stt.transcribe_file(wav))
    else:
        print("Usage: python stt/sherpa_stt.py <file.wav> [tiny|base]")