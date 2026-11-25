"""Pixel-art item slots: a black well, a gold bevel, and a traveling glint.

The glint is a short highlight that walks the border of the hovered or
selected slot. It is driven by ``Canvas.after`` and cancelled when the
highlight moves to another slot or the menu closes.
"""
from __future__ import annotations

import tkinter as tk

SLOT_TAG = "item_slot"
GLINT_TAG = "item_slot_glint"
OUTER = 40
FRAME_MS = 40
STEP = 4

BLACK = "#000000"
SHADOW = "#6e4b22"
HIGHLIGHT = "#f6e7b0"
GOLD = "#d4a441"
BRONZE = "#8d6230"
GLINT_COLORS = ("#ffffff", "#fff6d0", "#ffe08a", "#f0c45a", "#d4a441", "#a87a32")


def draw_item_slot(canvas: tk.Canvas, cx: float, cy: float, image, *tags, size=OUTER) -> tuple:
    """Draw a black well and a gold bevel around an icon."""
    half = size // 2
    inset = 3 if size < OUTER else 4
    x1, y1, x2, y2 = cx - half, cy - half, cx + half, cy + half
    slot_tags = (*tags, SLOT_TAG)
    canvas.create_rectangle(x1, y1, x2, y2, fill=SHADOW, outline="", tags=slot_tags)
    canvas.create_rectangle(x1, y1, x2 - 2, y2 - 2, fill=HIGHLIGHT, outline="", tags=slot_tags)
    canvas.create_rectangle(x1 + 2, y1 + 2, x2 - 2, y2 - 2, fill=GOLD, outline="", tags=slot_tags)
    canvas.create_rectangle(x1 + 3, y1 + 3, x2 - 3, y2 - 3, fill=BRONZE, outline="", tags=slot_tags)
    canvas.create_rectangle(x1 + inset, y1 + inset, x2 - inset, y2 - inset, fill=BLACK, outline="", tags=slot_tags)
    if image is not None:
        canvas.create_image(cx, cy, image=image, tags=slot_tags)
    return (x1, y1, x2, y2)


def _rim_point(box: tuple, distance: float) -> tuple[float, float]:
    """Walk clockwise around the border, one pixel in from the outer edge."""
    x1, y1, x2, y2 = box
    x1, y1, x2, y2 = x1 + 1, y1 + 1, x2 - 1, y2 - 1
    width = x2 - x1
    height = y2 - y1
    perimeter = 2 * (width + height)
    if perimeter <= 0:
        return x1, y1
    cursor = distance % perimeter
    if cursor < width:
        return x1 + cursor, y1
    cursor -= width
    if cursor < height:
        return x2, y1 + cursor
    cursor -= height
    if cursor < width:
        return x2 - cursor, y2
    cursor -= width
    return x1, y2 - cursor


class SlotGlint:
    """One moving reflection. A new target cancels the previous callback."""

    def __init__(self, canvas: tk.Canvas) -> None:
        self.canvas = canvas
        self.after_id = None
        self.slot = None
        self.phase = 0
        self._generation = 0
        self.tag = GLINT_TAG

    def play(self, box: tuple) -> None:
        box = tuple(box)
        if self.slot == box and self.after_id is not None:
            self._raise()
            return
        self.stop()
        self.slot = box
        self.phase = 0
        self._step()

    def stop(self) -> None:
        self.slot = None
        self._generation += 1
        if self.after_id is not None:
            try:
                self.canvas.after_cancel(self.after_id)
            except tk.TclError:
                pass
            self.after_id = None
        self._clear()

    def _step(self) -> None:
        token = self._generation
        self.after_id = None
        if self.slot is None or token != self._generation:
            return
        try:
            alive = bool(self.canvas.winfo_exists())
        except tk.TclError:
            self.slot = None
            return
        if not alive or token != self._generation or self.slot is None:
            self.slot = None
            return
        self._paint()
        self.phase += STEP
        if token != self._generation or self.slot is None:
            return
        try:
            self.after_id = self.canvas.after(FRAME_MS, self._step)
        except tk.TclError:
            self.after_id = None

    def _paint(self) -> None:
        self._clear()
        for offset, color in enumerate(GLINT_COLORS):
            px, py = _rim_point(self.slot, self.phase - offset * 3)
            self.canvas.create_rectangle(
                px - 2, py - 2, px + 2, py + 2,
                fill=color, outline="", tags=self.tag,
            )
        self._raise()

    def _raise(self) -> None:
        try:
            self.canvas.tag_raise(self.tag)
        except tk.TclError:
            pass

    def _clear(self) -> None:
        try:
            self.canvas.delete(self.tag)
        except tk.TclError:
            pass
