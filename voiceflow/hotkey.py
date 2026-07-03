"""Global hotkey state machine: hold-to-talk + double-tap lock.

Behaviour (default key: right ctrl):
- Press and hold, speak, release  -> transcribe (hold longer than TAP_MS)
- Two quick taps                  -> lock recording on
- Single tap while locked         -> stop + transcribe
- Escape while recording          -> cancel
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Callable

import keyboard

log = logging.getLogger(__name__)

TAP_MS = 400          # press shorter than this is a "tap"
DOUBLE_TAP_MS = 500   # two taps within this window lock recording


class HotkeyListener:
    def __init__(
        self,
        hotkey: str,
        on_start: Callable[[], None],
        on_finish: Callable[[], None],
        on_cancel: Callable[[], None],
    ) -> None:
        self.hotkey = hotkey
        self.on_start = on_start
        self.on_finish = on_finish
        self.on_cancel = on_cancel

        self._recording = False
        self._locked = False
        self._pressed_at = 0.0
        self._last_tap_at = 0.0
        self._lock = threading.Lock()

    def start(self) -> None:
        keyboard.on_press_key(self.hotkey, self._on_press, suppress=False)
        keyboard.on_release_key(self.hotkey, self._on_release, suppress=False)
        keyboard.on_press_key("esc", self._on_escape, suppress=False)
        log.info("Hotkey ready: hold [%s] to talk, double-tap to lock", self.hotkey)

    def _on_press(self, event) -> None:
        with self._lock:
            if self._pressed_at:  # key auto-repeat while held
                return
            self._pressed_at = time.monotonic()
            if self._locked:
                return  # tap-to-stop is handled on release
            if not self._recording:
                self._recording = True
                self.on_start()

    def _on_release(self, event) -> None:
        with self._lock:
            now = time.monotonic()
            held_ms = (now - self._pressed_at) * 1000
            self._pressed_at = 0.0

            if self._locked:
                # any tap while locked stops and transcribes
                self._locked = False
                self._recording = False
                self._last_tap_at = 0.0
                self.on_finish()
                return

            if held_ms > TAP_MS:
                # normal hold-to-talk release
                self._recording = False
                self._last_tap_at = 0.0
                self.on_finish()
                return

            # short tap: maybe first or second of a double-tap
            if (now - self._last_tap_at) * 1000 < DOUBLE_TAP_MS:
                self._locked = True  # second tap: keep recording, hands free
                self._last_tap_at = 0.0
                log.info("Recording locked on")
            else:
                # first tap: recording already started on press; wait briefly
                # for a second tap, otherwise treat it as a short dictation
                self._last_tap_at = now
                threading.Timer(DOUBLE_TAP_MS / 1000, self._tap_timeout, args=(now,)).start()

    def _tap_timeout(self, tap_time: float) -> None:
        with self._lock:
            if self._last_tap_at == tap_time and self._recording and not self._locked:
                self._recording = False
                self._last_tap_at = 0.0
                self.on_finish()

    def _on_escape(self, event) -> None:
        with self._lock:
            if self._recording or self._locked:
                self._recording = False
                self._locked = False
                self._last_tap_at = 0.0
                self.on_cancel()
                log.info("Recording cancelled")
