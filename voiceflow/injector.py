"""Insert text at the cursor: clipboard-paste (default) or simulated typing."""
from __future__ import annotations

import logging
import time

import keyboard
import pyperclip

log = logging.getLogger(__name__)


def inject(text: str, mode: str = "paste") -> None:
    if not text:
        return
    if mode == "type":
        keyboard.write(text)
        return

    try:
        old = pyperclip.paste()
    except Exception:
        old = None
    pyperclip.copy(text)
    time.sleep(0.05)  # let the clipboard settle before the paste keystroke
    keyboard.send("ctrl+v")
    if old is not None:
        # restore after the target app has read the clipboard
        time.sleep(0.3)
        try:
            pyperclip.copy(old)
        except Exception:
            log.warning("Could not restore previous clipboard contents")
