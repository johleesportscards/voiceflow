"""faster-whisper wrapper. Loads the model once; CUDA with CPU fallback."""
from __future__ import annotations

import logging
import os
import sys
import threading
from pathlib import Path

import numpy as np

log = logging.getLogger(__name__)


def _add_nvidia_dll_dirs() -> None:
    """Make pip-installed cuBLAS/cuDNN DLLs visible to ctranslate2 on Windows.

    ctranslate2 loads cublas64_12.dll etc. at compute time via plain
    LoadLibrary, which ignores os.add_dll_directory — the dirs must be on
    PATH as well.
    """
    if sys.platform != "win32":
        return
    dirs = []
    for pkg in ("nvidia/cublas/bin", "nvidia/cudnn/bin", "nvidia/cuda_nvrtc/bin"):
        for site in sys.path:
            candidate = Path(site) / pkg.replace("/", os.sep)
            if candidate.is_dir():
                os.add_dll_directory(str(candidate))
                dirs.append(str(candidate))
                break
    if dirs:
        os.environ["PATH"] = os.pathsep.join(dirs) + os.pathsep + os.environ.get("PATH", "")


class Transcriber:
    def __init__(self, model_name: str, device: str, language: str) -> None:
        from faster_whisper import WhisperModel

        _add_nvidia_dll_dirs()
        self.language = None if language == "auto" else language
        self.device = device
        # ctranslate2 models aren't safe for concurrent transcribe calls;
        # serializes the preview loop against the final pass
        self._infer_lock = threading.Lock()

        attempts = [("cuda", "float16"), ("cpu", "int8")] if device == "auto" else [
            (device, "float16" if device == "cuda" else "int8")
        ]
        last_err: Exception | None = None
        for dev, compute in attempts:
            try:
                self.model = WhisperModel(model_name, device=dev, compute_type=compute)
                self.device = dev
                log.info("Loaded %s on %s (%s)", model_name, dev, compute)
                return
            except Exception as e:  # ctranslate2 raises RuntimeError on CUDA issues
                last_err = e
                log.warning("Failed to load on %s: %s", dev, e)
        raise RuntimeError(f"Could not load Whisper model {model_name}") from last_err

    def transcribe(self, audio: np.ndarray) -> str:
        """Final-quality pass (beam search)."""
        return self._run(audio, beam_size=5, condition=True)

    def transcribe_partial(self, audio: np.ndarray) -> str:
        """Fast greedy pass for the live preview while still recording."""
        return self._run(audio, beam_size=1, condition=False)

    def _run(self, audio: np.ndarray, beam_size: int, condition: bool) -> str:
        if audio.size < 1600:  # <0.1 s, nothing to do
            return ""
        with self._infer_lock:
            segments, _info = self.model.transcribe(
                audio,
                language=self.language,
                vad_filter=True,
                beam_size=beam_size,
                condition_on_previous_text=condition,
            )
            return " ".join(seg.text.strip() for seg in segments).strip()
