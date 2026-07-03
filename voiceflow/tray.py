"""System tray icon: status color, cleanup-mode menu, quit."""
from __future__ import annotations

from typing import Callable

import pystray
from PIL import Image, ImageDraw

STATE_COLORS = {
    "idle": "#3dd68c",
    "recording": "#e5484d",
    "locked": "#e5a13d",
    "transcribing": "#4d7ee5",
    "error": "#888888",
}


def _icon_image(color: str) -> Image.Image:
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((8, 8, 56, 56), fill=color)
    # simple mic glyph
    d.rounded_rectangle((26, 16, 38, 36), radius=6, fill="white")
    d.arc((20, 24, 44, 44), start=0, end=180, fill="white", width=3)
    d.line((32, 44, 32, 50), fill="white", width=3)
    return img


class Tray:
    def __init__(
        self,
        cleanup_mode: str,
        on_set_cleanup: Callable[[str], None],
        on_quit: Callable[[], None],
    ) -> None:
        self._cleanup_mode = cleanup_mode
        self._on_set_cleanup = on_set_cleanup

        def mode_item(mode: str, label: str) -> pystray.MenuItem:
            return pystray.MenuItem(
                label,
                lambda *args, m=mode: self._set_mode(m),
                checked=lambda item, m=mode: self._cleanup_mode == m,
                radio=True,
            )

        self.icon = pystray.Icon(
            "voiceflow",
            _icon_image(STATE_COLORS["idle"]),
            "VoiceFlow — idle",
            menu=pystray.Menu(
                pystray.MenuItem("Cleanup", pystray.Menu(
                    mode_item("auto", "Auto (Claude → Ollama → LM Studio → raw)"),
                    mode_item("claude", "Claude"),
                    mode_item("ollama", "Ollama"),
                    mode_item("lmstudio", "LM Studio"),
                    mode_item("raw", "Raw transcript"),
                )),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Quit", lambda *args: (self.icon.stop(), on_quit())),
            ),
        )

    def _set_mode(self, mode: str) -> None:
        self._cleanup_mode = mode
        self._on_set_cleanup(mode)

    def set_state(self, state: str) -> None:
        self.icon.icon = _icon_image(STATE_COLORS.get(state, "#888888"))
        self.icon.title = f"VoiceFlow — {state}"

    def run(self) -> None:
        """Blocks; call from the main thread."""
        self.icon.run()
