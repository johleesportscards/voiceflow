"""VoiceFlow entry point: wires hotkey -> recorder -> whisper -> cleanup -> paste."""
from __future__ import annotations

import logging
import threading

from . import cleanup as cleanup_mod
from . import config as config_mod
from .hotkey import HotkeyListener
from .injector import inject
from .overlay import Overlay
from .recorder import Recorder
from .transcriber import Transcriber
from .tray import Tray

log = logging.getLogger("voiceflow")


class App:
    def __init__(self) -> None:
        self.cfg = config_mod.load()
        log.info("Loading Whisper model %s (device=%s)…", self.cfg.model, self.cfg.device)
        self.transcriber = Transcriber(self.cfg.model, self.cfg.device, self.cfg.language)
        self.recorder = Recorder()
        self.overlay = Overlay(self.cfg.overlay)
        self.chain = cleanup_mod.build_chain(self.cfg.cleanup, self.cfg)
        self._preview_stop = threading.Event()
        self.tray = Tray(self.cfg.cleanup, self._set_cleanup_mode, on_quit=lambda: None)
        self.listener = HotkeyListener(
            self.cfg.hotkey,
            on_start=self._on_start,
            on_finish=self._on_finish,
            on_cancel=self._on_cancel,
        )

    def _set_cleanup_mode(self, mode: str) -> None:
        self.chain = cleanup_mod.build_chain(mode, self.cfg)

    def _on_start(self) -> None:
        self.recorder.start()
        self.tray.set_state("recording")
        self.overlay.show("recording")
        if self.cfg.preview:
            self._preview_stop = threading.Event()
            threading.Thread(
                target=self._preview_loop, args=(self._preview_stop,), daemon=True
            ).start()

    # preview transcribes only this much trailing audio — keeps each pass
    # fast no matter how long the dictation runs (pill shows the tail anyway)
    PREVIEW_WINDOW_SAMPLES = 15 * 16_000

    def _preview_loop(self, stop: threading.Event) -> None:
        """Live partial text while speaking: re-transcribe the trailing audio
        window with a fast greedy pass and show it in the overlay. If a pass
        is slower than the interval, the next tick simply waits (single
        flight via the transcriber's inference lock)."""
        last_shown = ""
        while not stop.wait(self.cfg.preview_interval):
            if not self.recorder.recording:
                break
            audio = self.recorder.snapshot()
            if audio.size < 16_000:  # wait for ≥1 s of audio
                continue
            try:
                text = self.transcriber.transcribe_partial(
                    audio[-self.PREVIEW_WINDOW_SAMPLES:]
                )
            except Exception:
                log.exception("Preview transcription failed")
                break
            if stop.is_set() or not self.recorder.recording:
                break
            if text and text != last_shown:
                last_shown = text
                self.overlay.show("recording", text)

    def _on_finish(self) -> None:
        if self.cfg.preview:
            self._preview_stop.set()
        audio = self.recorder.stop()
        self.tray.set_state("transcribing")
        self.overlay.show("transcribing")
        # transcribe off the keyboard-hook thread so the hook never stalls
        threading.Thread(target=self._process, args=(audio,), daemon=True).start()

    def _process(self, audio) -> None:
        try:
            text = self.transcriber.transcribe(audio)
            if text:
                text = cleanup_mod.clean(self.chain, text)
                inject(text, self.cfg.inject)
                log.info("Injected %d chars", len(text))
            else:
                log.info("No speech detected")
        except Exception:
            log.exception("Dictation failed")
        finally:
            self.tray.set_state("idle")
            self.overlay.hide()

    def _on_cancel(self) -> None:
        if self.cfg.preview:
            self._preview_stop.set()
        self.recorder.cancel()
        self.tray.set_state("idle")
        self.overlay.hide()

    def run(self) -> None:
        self.listener.start()
        log.info("VoiceFlow ready — hold [%s] and speak.", self.cfg.hotkey)
        self.tray.run()  # blocks until Quit


def _already_running() -> bool:
    """Single-instance guard: two instances mean doubled keyboard hooks and
    double-pasted text. Uses a named Windows mutex held for process lifetime."""
    import ctypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    global _instance_mutex
    _instance_mutex = kernel32.CreateMutexW(None, False, "voiceflow-single-instance")
    return ctypes.get_last_error() == 183  # ERROR_ALREADY_EXISTS


def main() -> None:
    import sys
    from pathlib import Path

    # Always log to a file: under the startup launcher (pythonw) there is no
    # usable console, and stderr detection is unreliable behind cmd wrappers.
    log_file = Path(__file__).resolve().parent.parent / "voiceflow.log"
    handlers: list[logging.Handler] = [logging.FileHandler(log_file, encoding="utf-8")]
    if sys.stderr is not None:
        handlers.append(logging.StreamHandler())
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=handlers,
    )

    if _already_running():
        log.info("VoiceFlow is already running — exiting this instance.")
        return
    App().run()


if __name__ == "__main__":
    main()
