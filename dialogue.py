"""Reusable, queued JRPG dialogue panel for the lite game."""
from __future__ import annotations

import math
import textwrap
import tkinter as tk
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


@dataclass(frozen=True)
class DialogueLine:
    speaker: str
    text: str
    portrait: Path | None = None
    thought: bool = False
    portrait_region: tuple[int, int, int, int] | None = None


class DialogueBox:
    TAG = "dialogue"

    def __init__(
        self,
        canvas: tk.Canvas,
        root: tk.Tk,
        font: Callable[[int, bool], tuple[str, int, str]],
    ) -> None:
        self.canvas = canvas
        self.root = root
        self.font = font
        self.lines: deque[DialogueLine] = deque()
        self.active = False
        self.portraits: dict[tuple[Path, tuple[int, int, int, int] | None], tk.PhotoImage] = {}

    def show(self, lines: list[DialogueLine]) -> None:
        self.clear()
        self.lines.extend(lines)
        self.advance()

    def clear(self) -> None:
        self.lines.clear()
        self.active = False
        self.canvas.delete(self.TAG)

    def advance(self) -> None:
        self.canvas.delete(self.TAG)
        if not self.lines:
            self.active = False
            return
        self.active = True
        line = self.lines.popleft()
        self._draw(line)

    def _portrait(
        self, path: Path, region: tuple[int, int, int, int] | None
    ) -> tk.PhotoImage | None:
        key = (path, region)
        if key in self.portraits:
            return self.portraits[key]
        try:
            source = tk.PhotoImage(master=self.root, file=str(path))
        except tk.TclError:
            return None
        if region is None:
            side = min(source.width(), source.height())
            left = (source.width() - side) // 2
            top = (source.height() - side) // 2
        else:
            left, top, right, bottom = region
            side = min(right - left, bottom - top)
        image = tk.PhotoImage(master=self.root, width=side, height=side)
        image.tk.call(image, "copy", source, "-from", left, top,
                      left + side, top + side)
        if side > 128:
            image = image.subsample(math.ceil(side / 128))
        elif side < 56:
            image = image.zoom(max(1, 128 // side))
        self.portraits[key] = image
        return image

    def _frame(self, x1: int, y1: int, x2: int, y2: int) -> None:
        # Layered grey/white border and indigo inset echo the reference UI.
        c = self.canvas
        tag = self.TAG
        c.create_rectangle(x1 + 5, y1 + 5, x2 + 5, y2 + 5,
                           fill="#08080c", outline="", tags=tag)
        c.create_rectangle(x1, y1, x2, y2, fill="#777b82",
                           outline="#8e9298", width=3, tags=tag)
        c.create_rectangle(x1 + 5, y1 + 5, x2 - 5, y2 - 5,
                           fill="#e7e6dc", outline="#f9f8ed", width=2, tags=tag)
        c.create_rectangle(x1 + 10, y1 + 10, x2 - 10, y2 - 10,
                           fill="#242181", outline="#242181", tags=tag)

    def _draw(self, line: DialogueLine) -> None:
        c = self.canvas
        tag = self.TAG
        has_portrait = line.portrait is not None
        box_left = 179 if has_portrait else 18
        self._frame(box_left, 365, 942, 517)
        if has_portrait:
            self._frame(18, 365, 166, 517)
            image = self._portrait(line.portrait, line.portrait_region)
            if image is not None:
                c.create_image(92, 441, image=image, anchor="center", tags=tag)

        label = line.speaker.upper() + (" · THOUGHT" if line.thought else "")
        c.create_text(box_left + 30, 391, text=label, anchor="w",
                      fill="#f7d58c", font=self.font(25, True), tags=tag)
        wrapped = "\n".join(textwrap.wrap(line.text, width=48 if has_portrait else 60))
        c.create_text(box_left + 30, 424, text=wrapped, anchor="nw",
                      fill="#ffffff", font=self.font(30, False),
                      width=700 if has_portrait else 825, tags=tag)
        c.create_text(903, 492, text="▼", fill="#ffffff",
                      font=self.font(23, True), tags=tag)
        c.tag_raise(tag)
