"""Silero VAD (onnx) — deteksi start/end bicara dari stream PCM16."""
import numpy as np
import onnxruntime as ort

SAMPLE_RATE_8K = 8000
SAMPLE_RATE_16K = 16000
VAD_FRAME = 512  # silero memproses per 512 sample (16k)


class VAD:
    def __init__(self, model_path: str, threshold: float = 0.5,
                 min_speech_ms: int = 250, min_silence_ms: int = 600):
        self.threshold = threshold
        self.min_speech_samples = int(min_speech_ms * SAMPLE_RATE_16K / 1000)
        self.min_silence_samples = int(min_silence_ms * SAMPLE_RATE_16K / 1000)
        self.session = ort.InferenceSession(
            model_path, providers=["CPUExecutionProvider"]
        )
        # state VAD: context 512 sample + state 2x128 (per input sr)
        self._reset()

    def _reset(self):
        self._context = np.zeros(512, dtype=np.float32)
        self._state = np.zeros((2, 1, 128), dtype=np.float32)
        self._sr = np.array(SAMPLE_RATE_16K, dtype=np.int64)

    def reset(self):
        self._reset()

    def is_speech(self, chunk: bytes) -> float:
        """Berikan probabilitas bicara (0-1) untuk chunk PCM16 (30ms minimal)."""
        samples = np.frombuffer(chunk, dtype=np.int16).astype(np.float32) / 32768.0
        if samples.size == 0:
            return 0.0
        combined = np.concatenate((self._context, samples))
        if combined.size < 512:
            combined = np.pad(combined, (0, 512 - combined.size))
        elif combined.size % 512:
            combined = np.pad(combined, (0, 512 - combined.size % 512))
        self._context = combined[-512:]
        # split jadi blok 512 & proses berurutan (state LSTM dipertahankan)
        blocks = combined.reshape(-1, 512)
        prob = 0.0
        out = None
        for blk in blocks:
            out = self.session.run(
                None,
                {
                    "input": blk[np.newaxis, :].astype(np.float32),
                    "state": self._state,
                    "sr": self._sr,
                },
            )
            prob = float(np.asarray(out[0]).ravel()[0])
            self._state = np.asarray(out[1]) if len(out) > 1 else self._state
        return prob


class SpeechSegmenter:
    """Segmen audio penuh: rekam sampai silence; beri audio speech mulai dikumpulkan."""

    def __init__(self, vad: VAD):
        self.vad = vad

    def feed(self, prob: float, chunk: bytes) -> str:
        """state machine: 'silence' -> 'speech' -> 'done'"""
        raise NotImplementedError("digunakan oleh StreamListener")