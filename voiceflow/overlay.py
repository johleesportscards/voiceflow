"""Always-on-top overlay pill: status dot plus live partial transcript.

The pill grows upward as the transcript wraps onto more rows (up to
MAX_ROWS) — its bottom edge stays anchored near the bottom of the screen,
so the newest words are always on the bottom row at the same spot. Row
management is display-based: full wrapped rows are trimmed off the top,
so every visible row above the live bottom row is full-width.

Runs tkinter in its own thread with a command queue, since tkinter must be
driven from a single thread.
"""
from __future__ import annotations

import queue
import threading
import tkinter as tk
import tkinter.font as tkfont

COLORS = {"recording": "#e5484d", "locked": "#e5a13d", "transcribing": "#4d7ee5"}
LABELS = {"recording": "●  recording", "locked": "●  locked on", "transcribing": "…  transcribing"}

MAX_ROWS = 7              # pill grows to this many text rows, then scrolls
CHARS_PER_ROW = 62        # row width in '0'-widths of the preview font
MAX_PREVIEW_CHARS = 1200  # perf guard: text handed to the widget per update
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
        # dark root: pixels exposed during a grow paint dark, not the
        # default light gray — kills the resize flash
        root.configure(bg="#333333")
        root.withdraw()
        frame = tk.Frame(root, bg="#333333")
        frame.pack()
        status = tk.Label(frame, text="", font=("Segoe UI", 11, "bold"),
                          fg="white", bg="#333333", padx=14, pady=6)
        status.pack(side="left", anchor="s")
        preview_font = tkfont.Font(root=root, family="Segoe UI", size=11)
        wrap_px = preview_font.measure("0") * (CHARS_PER_ROW - 1)
        # the widget never wraps or trims anything itself: lines are wrapped
        # in code with font.measure and handed over as final content in one
        # delete+insert — a single paint per update, no intermediate layout
        # pass (asking the widget to wrap+count forced a mid-update repaint,
        # which flickered on every text change)
        preview = tk.Text(frame, font=preview_font, fg="#e8e8e8", bg="#333333",
                          width=CHARS_PER_ROW, height=1, wrap="none",
                          bd=0, highlightthickness=0, padx=0, pady=6,
                          cursor="arrow", state="disabled")
        state_track = {"visible": False, "with_text": False, "w": 0, "h": 0}
        last_rows = {"n": 0}
        peak_rows = {"n": 0}  # session high-water mark: height never shrinks
        last_content = {"s": None}

        def wrap_lines(text: str) -> list[str]:
            """Word-wrap with the actual font metrics (kerning included)."""
            lines: list[str] = []
            cur = ""
            for word in text.split():
                while preview_font.measure(word) > wrap_px:  # unbroken run
                    if cur:
                        lines.append(cur)
                        cur = ""
                    cut = max(1, len(word) * wrap_px // preview_font.measure(word))
                    lines.append(word[:cut])
                    word = word[cut:]
                candidate = f"{cur} {word}".strip()
                if preview_font.measure(candidate) <= wrap_px:
                    cur = candidate
                else:
                    lines.append(cur)
                    cur = word
            if cur:
                lines.append(cur)
            return lines or [""]

        def set_preview_text(text: str) -> None:
            lines = wrap_lines(text[-MAX_PREVIEW_CHARS:])[-MAX_ROWS:]
            rows = len(lines)
            # height is monotonic within a dictation: the fast pass keeps
            # revising its wrap count (7→6→7 at the cap) and shrinking reads
            # as resize flicker. Below peak, pad blank rows on top so the
            # text stays bottom-anchored.
            if rows < peak_rows["n"]:
                lines = [""] * (peak_rows["n"] - rows) + lines
                rows = peak_rows["n"]
            else:
                peak_rows["n"] = rows
            content = "\n".join(lines)
            if content == last_content["s"]:
                return
            last_content["s"] = content
            preview.configure(state="normal")
            preview.delete("1.0", "end")
            preview.insert("1.0", content)
            if rows != last_rows["n"]:  # touching height when unchanged still
                last_rows["n"] = rows   # triggers relayout → needless flicker
                preview.configure(height=rows)
            preview.configure(state="disabled")

        def place(force: bool = False) -> None:
            """(Re)position so the pill's BOTTOM edge stays fixed; growth
            pushes the top edge up. Moves when width OR height changed."""
            root.update_idletasks()
            w = root.winfo_reqwidth()
            h = root.winfo_reqheight()
            if (not force and state_track["visible"]
                    and w == state_track["w"] and h == state_track["h"]):
                return
            x = (root.winfo_screenwidth() - w) // 2
            y = root.winfo_screenheight() - BOTTOM_MARGIN - h
            # size AND position in one call: separate resize-then-move
            # paints two frames and reads as flicker when a row is added
            root.geometry(f"{w}x{h}+{x}+{y}")
            state_track["w"] = w
            state_track["h"] = h
            if not state_track["visible"]:
                # let the new geometry apply before revealing, or the first
                # frame shows the window at its previous session's size
                root.update_idletasks()
                root.deiconify()
                state_track["visible"] = True

        def poll() -> None:
            try:
                while True:
                    item = self._q.get_nowait()
                    if item is None:
                        root.withdraw()
                        root.geometry("1x1+-3000+-3000")  # park tiny off-screen
                        state_track["visible"] = False
                        state_track["with_text"] = False
                        state_track["w"] = 0
                        state_track["h"] = 0
                        last_rows["n"] = 0
                        peak_rows["n"] = 0
                        last_content["s"] = None
                        preview.configure(state="normal")
                        preview.delete("1.0", "end")
                        preview.configure(height=1, state="disabled")
                        preview.pack_forget()
                        continue
                    state, text = item
                    status.config(text=LABELS.get(state, state),
                                  fg=COLORS.get(state, "white"))
                    if text:
                        if not state_track["with_text"]:
                            preview.pack(side="left", padx=(0, 14), anchor="s")
                            state_track["with_text"] = True
                        set_preview_text(text)
                    place(force=not state_track["visible"])
            except queue.Empty:
                pass
            root.after(50, poll)

        poll()
        root.mainloop()
