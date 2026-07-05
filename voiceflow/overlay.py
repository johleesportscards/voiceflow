"""Always-on-top overlay pill: status dot plus live partial transcript.

Runs tkinter in its own thread with a command queue, since tkinter must be
driven from a single thread.
"""
from __future__ import annotations

import queue
import threading
import tkinter as tk

COLORS = {"recording": "#e5484d", "locked": "#e5a13d", "transcribing": "#4d7ee5"}
LABELS = {"recording": "●  recording", "locked": "●  locked on", "transcribing": "…  transcribing"}

MAX_PREVIEW_CHARS = 120  # show the tail of longer dictations


class Overlay:
    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled
        self._q: queue.Queue[tuple[str, str] | None] = queue.Queue()
        if enabled:
            threading.Thread(target=self._run, daemon=True).start()

    def show(self, state: str, text: str = "") -> None:
        """Show the pill for `state`; `text` is the live partial transcript."""
        if self.enabled:
            self._q.put((state, text))

    def hide(self) -> None:
        if self.enabled:
            self._q.put(None)

    def _run(self) -> None:
        root = tk.Tk()
        root.overrideredirect(True)
        root.attributes("-topmost", True)
        root.withdraw()
        frame = tk.Frame(root, bg="#333333")
        frame.pack()
        status = tk.Label(frame, text="", font=("Segoe UI", 11, "bold"),
                          fg="white", bg="#333333", padx=14, pady=6)
        status.pack(side="left")
        # fixed 60-char x 2-line box: the pill never resizes between preview
        # updates, so live text doesn't flicker or make the window jump
        preview = tk.Label(frame, text="", font=("Segoe UI", 11),
                           fg="#e8e8e8", bg="#333333", padx=0, pady=6,
                           width=60, height=2, wraplength=520,
                           justify="left", anchor="w")
        visible = {"shown": False, "with_text": False}

        def place_and_show() -> None:
            root.update_idletasks()
            w = root.winfo_reqwidth()
            x = (root.winfo_screenwidth() - w) // 2
            y = root.winfo_screenheight() - 130
            root.geometry(f"+{x}+{y}")
            root.deiconify()
            visible["shown"] = True

        def poll() -> None:
            try:
                while True:
                    item = self._q.get_nowait()
                    if item is None:
                        root.withdraw()
                        visible["shown"] = False
                        visible["with_text"] = False
                        preview.config(text="")
                        preview.pack_forget()
                        continue
                    state, text = item
                    status.config(text=LABELS.get(state, state),
                                  fg=COLORS.get(state, "white"))
                    if text:
                        tail = text[-MAX_PREVIEW_CHARS:]
                        if len(text) > MAX_PREVIEW_CHARS:
                            tail = "…" + tail
                        preview.config(text=tail)
                        if not visible["with_text"]:
                            preview.pack(side="left", padx=(0, 14))
                            visible["with_text"] = True
                            visible["shown"] = False  # width changed: re-center once
                    if not visible["shown"]:
                        place_and_show()
            except queue.Empty:
                pass
            root.after(50, poll)

        poll()
        root.mainloop()
