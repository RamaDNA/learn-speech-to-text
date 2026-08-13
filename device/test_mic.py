"""Test mic: rekam N detik -> transkripsi dengan Whisper base."""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np
import sounddevice as sd
import soundfile as sf

from stt.sherpa_stt import WhisperSTT


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=int, default=5)
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent / ".." / "tmp_rec.wav"))
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()

    if args.list:
        print(sd.query_devices())
        return

    print(f"Rekam {args.seconds} detik... BICARA SEKARANG!")
    data = sd.rec(int(args.seconds * 16000), samplerate=16000, channels=1, dtype="int16")
    sd.wait()
    sf.write(args.out, data, 16000, subtype="PCM_16")
    print(f"Tersimpan: {args.out}")

    t0 = time.time()
    stt = WhisperSTT(size="base", language="auto")
    text = stt.transcribe_file(args.out)
    print(f"Transkrip ({time.time() - t0:.2f}s): {text!r}")


if __name__ == "__main__":
    main()