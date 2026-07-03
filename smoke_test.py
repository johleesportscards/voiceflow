"""CUDA smoke test: transcribe a synthetic tone + optional mic clip.

Usage: uv run python smoke_test.py [seconds]
With no mic argument it just verifies the model loads and runs on GPU.
"""
from __future__ import annotations

import sys
import time

import numpy as np

from voiceflow import config as config_mod
from voiceflow.transcriber import Transcriber


def main() -> None:
    cfg = config_mod.load()
    t0 = time.perf_counter()
    tr = Transcriber(cfg.model, cfg.device, cfg.language)
    print(f"Model loaded on {tr.device} in {time.perf_counter() - t0:.1f}s")

    seconds = float(sys.argv[1]) if len(sys.argv) > 1 else 0
    if seconds:
        import sounddevice as sd

        print(f"Recording {seconds:.0f}s — speak now…")
        audio = sd.rec(int(seconds * 16_000), samplerate=16_000, channels=1, dtype="float32")
        sd.wait()
        audio = audio[:, 0]
    else:
        audio = np.zeros(16_000, dtype=np.float32)  # 1s silence, exercises the pipeline

    t0 = time.perf_counter()
    text = tr.transcribe(audio)
    print(f"Transcribed in {time.perf_counter() - t0:.2f}s: {text!r}")


if __name__ == "__main__":
    main()
