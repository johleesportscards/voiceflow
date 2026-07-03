"""Small always-on-top status pill shown while recording/transcribing.

Runs tkinter in its own thread with a command queue, since tkinter must be
driven from a single thread.
"""
from __future__ import annotations

import queue
import threading
import tkinter as tk

COLORS = {"recording": "#e5484d", "locked": "#e5a13d", "transcribing": "#4d7ee5"}
LABELS = {"recording": "●  recording", "locked": "●  locked on", "transcribing": "…  transcribing"}


class Overlay:
    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled
        self._q: queue.Queue[str | None] = queue.Queue()
        if enabled:
            threading.Thread(target=self._run, daemon=True).start()

    def show(self, state: str) -> None:
        if self.enabled:
            self._q.put(state)

    def hide(self) -> None:
        if self.enabled:
            self._q.put(None)

    def _run(self) -> None:
        root = tk.Tk()
        root.overrideredirect(True)
        root.attributes("-topmost", True)
        root.withdraw()
        label = tk.Label(root, text="", font=("Segoe UI", 11, "bold"),
                         fg="white", bg="#333333", padx=14, pady=6)
        label.pack()

        def poll() -> None:
            try:
                while True:
                    state = self._q.get_nowait()
                    if state is None:
                        root.withdraw()
                    else:
                        label.config(text=LABELS.get(state, state),
                                     fg=COLORS.get(state, "white"))
                        # bottom-center of the primary screen
                        root.update_idletasks()
                        w = root.winfo_reqwidth()
                        x = (root.winfo_screenwidth() - w) // 2
                        y = root.winfo_screenheight() - 110
                        root.geometry(f"+{x}+{y}")
                        root.deiconify()
            except queue.Empty:
                pass
            root.after(50, poll)

        poll()
        root.mainloop()
