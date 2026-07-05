"""Insert text at the cursor: clipboard-paste (default) or simulated typing."""
from __future__ import annotations

import logging
import time

import keyboard
import pyperclip

log = logging.getLogger(__name__)

SENTENCE_END = ".!?…\"'"
SMART_SPACE_WINDOW_S = 600.0
_last_injection = {"end_char": "", "at": 0.0}


def _smart_space(text: str) -> str:
    """Consecutive dictations land flush against the previous sentence
    ("...done.Next thing") because we can't read the target field. If the
    previous injection ended a sentence recently, prepend one space."""
    prev = _last_injection
    if (
        text[:1].isalnum()
        and prev["end_char"]
        and prev["end_char"] in SENTENCE_END
        and time.time() - prev["at"] < SMART_SPACE_WINDOW_S
    ):
        return " " + text
    return text


def inject(text: str, mode: str = "paste") -> None:
    if not text:
        return
    text = _smart_space(text)
    _last_injection["end_char"] = text[-1:]
    _last_injection["at"] = time.time()

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
