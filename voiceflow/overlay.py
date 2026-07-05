"""Always-on-top overlay pill: status dot plus live partial transcript.

The pill grows upward as the transcript wraps onto more rows — its bottom
edge stays anchored near the bottom of the screen, so the newest words are
always on the bottom row at the same spot.

Runs tkinter in its own thread with a command queue, since tkinter must be
driven from a single thread.
"""
from __future__ import annotations

import queue
import threading
import tkinter as tk

COLORS = {"recording": "#e5484d", "locked": "#e5a13d", "transcribing": "#4d7ee5"}
LABELS = {"recording": "●  recording", "locked": "●  locked on", "transcribing": "…  transcribing"}

MAX_PREVIEW_CHARS = 480   # a full 7 rows; older text scrolls off the top
BOTTOM_MARGIN = 70        # px between the pill's bottom edge and screen bottom


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
        status.pack(side="left", anchor="s")
        # fixed width so x never shifts; height is free — rows accumulate and
        # the window is re-anchored by its bottom edge whenever size changes.
        # wraplength is kept well under the label's pixel width so the last
        # word on a row wraps instead of clipping at the edge
        preview = tk.Label(frame, text="", font=("Segoe UI", 11),
                           fg="#e8e8e8", bg="#333333", padx=0, pady=6,
                           width=62, wraplength=480,
                           justify="left", anchor="sw")
        state_track = {"visible": False, "with_text": False, "w": 0, "h": 0}

        def place(force: bool = False) -> None:
            """(Re)position so the pill's BOTTOM edge stays fixed; growth
            pushes the top edge up. Moves when width OR height changed —
            width changes when the preview label first appears."""
            root.update_idletasks()
            w = root.winfo_reqwidth()
            h = root.winfo_reqheight()
            if (not force and state_track["visible"]
                    and w == state_track["w"] and h == state_track["h"]):
                return
            x = (root.winfo_screenwidth() - w) // 2
            y = root.winfo_screenheight() - BOTTOM_MARGIN - h
            root.geometry(f"+{x}+{y}")
            state_track["w"] = w
            state_track["h"] = h
            if not state_track["visible"]:
                root.deiconify()
                state_track["visible"] = True

        def poll() -> None:
            try:
                while True:
                    item = self._q.get_nowait()
                    if item is None:
                        root.withdraw()
                        state_track["visible"] = False
                        state_track["with_text"] = False
                        state_track["w"] = 0
                        state_track["h"] = 0
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
                        if not state_track["with_text"]:
                            preview.pack(side="left", padx=(0, 14), anchor="s")
                            state_track["with_text"] = True
                    place(force=not state_track["visible"])
            except queue.Empty:
                pass
            root.after(50, poll)

        poll()
        root.mainloop()
