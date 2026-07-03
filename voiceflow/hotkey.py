"""Global hotkey state machine: hold-to-talk + double-tap lock.

Behaviour:
- Press and hold, speak, release  -> transcribe (hold longer than TAP_MS)
- Two quick taps                  -> lock recording on
- Single tap while locked         -> stop + transcribe
- Escape while recording          -> cancel
- Single tap (caps lock hotkey)   -> normal caps-lock toggle passed through;
  the key's original function survives, delayed by the double-tap window
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
        self._replay_until = 0.0  # window during which caps events pass to the OS
        self._lock = threading.Lock()

    def start(self) -> None:
        self._register()
        keyboard.on_press_key("esc", self._on_escape, suppress=False)
        log.info("Hotkey ready: hold [%s] to talk, double-tap to lock", self.hotkey)

    def _register(self) -> None:
        # caps lock gets suppressed so holding it to talk never toggles caps
        # state; with suppress=True the callback's return value decides per
        # event: True = pass to OS, falsy = block
        suppress = self.hotkey == "caps lock"
        keyboard.on_press_key(self.hotkey, self._on_press, suppress=suppress)
        keyboard.on_release_key(self.hotkey, self._on_release, suppress=suppress)

    def _passthrough_caps(self) -> None:
        """Re-send a suppressed lone caps-lock tap so the normal toggle still
        happens. The handlers let events through (return True) during the
        replay window instead of unhooking, which was racy."""
        self._replay_until = time.monotonic() + 0.3
        keyboard.send("caps lock")

    def _on_press(self, event):
        if time.monotonic() < self._replay_until:
            return True  # our own injected caps toggle: let the OS have it
        with self._lock:
            if self._pressed_at:  # key auto-repeat while held
                return False
            self._pressed_at = time.monotonic()
            if self._locked:
                return False  # tap-to-stop is handled on release
            if not self._recording:
                self._recording = True
                self.on_start()
        return False

    def _on_release(self, event):
        if time.monotonic() < self._replay_until:
            self._replay_until = 0.0  # replay complete
            return True
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
                return False

            if held_ms > TAP_MS:
                # normal hold-to-talk release
                self._recording = False
                self._last_tap_at = 0.0
                self.on_finish()
                return False

            # short tap: maybe first or second of a double-tap
            if (now - self._last_tap_at) * 1000 < DOUBLE_TAP_MS:
                self._locked = True  # second tap: keep recording, hands free
                self._last_tap_at = 0.0
                log.info("Recording locked on")
            else:
                # first tap: recording already started on press; wait briefly
                # to see if a second tap (lock) is coming
                self._last_tap_at = now
                threading.Timer(DOUBLE_TAP_MS / 1000, self._tap_timeout, args=(now,)).start()
        return False

    def _tap_timeout(self, tap_time: float) -> None:
        with self._lock:
            if not (self._last_tap_at == tap_time and self._recording and not self._locked):
                return
            self._recording = False
            self._last_tap_at = 0.0
            if self.hotkey == "caps lock":
                # lone tap = the user wanted plain caps lock, not dictation
                self.on_cancel()
                self._passthrough_caps()
            else:
                self.on_finish()  # treat as a very short dictation

    def _on_escape(self, event) -> None:
        with self._lock:
            if self._recording or self._locked:
                self._recording = False
                self._locked = False
                self._last_tap_at = 0.0
                self.on_cancel()
                log.info("Recording cancelled")
