"""Asisten gudang suara — main loop.

Alur: [opsional wake word] -> VAD record -> STT -> agent API -> TTS.
Jalankan: device/.venv/Scripts/python.exe device/main.py
"""
import logging
import sys
import time
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("main")

DEVICE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(DEVICE_DIR))

from api_client import AgentAPI  # noqa: E402
from audio.mic import VoiceCapture  # noqa: E402
from audio.vad import VAD  # noqa: E402
from config import build_config  # noqa: E402
from stt.sherpa_stt import WhisperSTT  # noqa: E402
from tts.piper_tts import PiperTTS  # noqa: E402


class VoiceAssistant:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.wakeword = None
        ww = cfg.get("wakeword", {})
        if ww.get("enabled", False) and ww.get("wake_words"):
            from wakeword.wake import WakeWordDetector

            self.wakeword = WakeWordDetector(
                ww["wake_words"], threshold=ww.get("threshold", 0.5)
            )
            log.info("Wake word aktif: %s", ", ".join(ww["wake_words"]))
        self.tts = PiperTTS(
            voice_id=cfg["tts"]["voice_id"],
            voice_en=cfg["tts"]["voice_en"],
            device=cfg["audio"].get("device"),
        )
        self.stt = WhisperSTT(
            model_dir=cfg["stt"]["model_dir"],
            language=cfg["stt"].get("language", "auto"),
        )
        self.vad = VAD(
            cfg["vad"]["model_path"],
            threshold=cfg["vad"].get("threshold", 0.5),
            min_speech_ms=cfg["vad"].get("min_speech_ms", 250),
            min_silence_ms=cfg["vad"].get("min_silence_ms", 600),
        )
        self.mic = VoiceCapture(
            self.vad, device=cfg["audio"].get("device"),
            max_seconds=30.0,
        )
        self.api = AgentAPI()
        self.last_lang = "id"
        self.awake = self.wakeword is None  # wakeword aktif -> mulai "tidur"

    def _listen_wakeword(self) -> bool:
        """Dengar sampai wake word terdeteksi; return True bila cocok."""
        if self.wakeword is None:
            return True
        log.info("Dengarkan wake word...")
        import sounddevice as sd

        with sd.InputStream(
            samplerate=16000, channels=1, dtype="int16",
            device=self.cfg["audio"].get("device"), blocksize=480,
        ) as stream:
            while True:
                data, _ = stream.read(480)
                hit = self.wakeword.feed(data.tobytes())
                if hit:
                    log.info("Wake word: %s (%.2f)", hit[0], hit[1])
                    return True

    def _detect_lang(self, text: str) -> str:
        from stt.language import guess_language
        return guess_language(text, fallback=self.last_lang)

    def say(self, text: str, lang: str | None = None):
        lang = lang or self.last_lang
        log.info(f"[TTS {lang}] {text}")
        try:
            self.tts.speak(text, lang=lang)
            self.last_lang = lang
        except Exception:
            log.exception("TTS gagal")

    def respond(self, reply: str):
        if not reply:
            return
        lang = self._detect_lang(reply)
        self.say(reply, lang)

    def handle_utterance(self, pcm: bytes):
        t0 = time.time()
        text = self.stt.transcribe(pcm)
        dt = time.time() - t0
        self.last_lang = self._detect_lang(text)
        log.info(f"[STT {self.last_lang}] {text}  ({dt:.2f}s)")
        if not text:
            log.info("STT kosong, acuhkan")
            return
        t1 = time.time()
        try:
            reply, _ = self.api.chat(text)
        except Exception as exc:
            log.error(f"API error: {exc}")
            self.say("Maaf, server sedang tidak tersedia. Coba lagi.", "id")
            return
        log.info(f"[AGENT {time.time()-t1:.2f}s] {reply}")
        self.respond(reply)

    def run(self):
        log.info("Asisten siap. Tekan Ctrl+C untuk berhenti.")
        greeted = False
        while True:
            try:
                if self.awake:
                    if not greeted:
                        self.say("Ada yang bisa saya bantu?", "id")
                        greeted = True
                elif self._listen_wakeword():
                    self.say("Ada yang bisa saya bantu?", "id")
                pcm = self.mic.capture_once()
                if pcm is None:
                    continue
                self.handle_utterance(pcm)
            except KeyboardInterrupt:
                log.info("Berhenti.")
                break
            except Exception:
                log.exception("Error di loop utama")
                self.say("Ada masalah teknis. Silakan coba lagi.", "id")


def main():
    cfg = build_config()
    asst = VoiceAssistant(cfg)
    asst.run()


if __name__ == "__main__":
    main()