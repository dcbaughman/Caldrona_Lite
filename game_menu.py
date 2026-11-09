"""Lightweight in-game menu with reusable retro panels and D-pad navigation."""
from __future__ import annotations

import tkinter as tk
from typing import Callable


class GameMenu:
    TAG = "game_menu"
    OPTIONS = (
        ("Items", "Your pack is empty for now."),
        ("Abilities", "Retri's abilities will appear here."),
        ("Equip", "Equipment management is coming later."),
        ("Status", "Retri is a skirter exploring Sunrest's cavern."),
        ("Formation", "Retri is the only party member right now."),
        ("Configuration", "Display settings can be changed at the title screen."),
        ("Save", "Saving will be added in a later pass."),
        ("Load", "No saved cavern journey exists yet."),
        ("Title Screen", "Leave the cavern and return to the title screen."),
    )

    def __init__(
        self,
        canvas: tk.Canvas,
        font: Callable[[int, bool], tuple[str, int, str]],
        portrait: Callable[[], tk.PhotoImage | None],
    ) -> None:
        self.canvas = canvas
        self.font = font
        self.portrait = portrait
        self.party_names = lambda: ["Retri"]
        self.party_portrait = lambda name: self.portrait() if name == "Retri" else None
        self._small_portraits = {}
        self.active = False
        self.selection = 0
        self.detail: int | None = None
        self.held_direction: str | None = None
        self.repeat_at = 0.0
        self.repeating = False

    def open(self) -> None:
        self.active = True
        self.selection = 0
        self.detail = None
        self.held_direction = None
        self.repeat_at = 0.0
        self.draw()

    def close(self) -> None:
        self.canvas.delete(self.TAG)
        self.active = False
        self.detail = None
        self.held_direction = None

    def back(self) -> None:
        if self.detail is not None:
            self.detail = None
            self.draw()
        else:
            self.close()

    def activate(self) -> str | None:
        if not self.active:
            return None
        if self.detail is not None:
            self.back()
            return None
        if self.selection == len(self.OPTIONS) - 1:
            return "title"
        self.detail = self.selection
        self.draw()
        return None

    def navigate(self, direction: str | None, now: float) -> None:
        if not self.active or self.detail is not None:
            return
        if direction not in ("up", "down"):
            self.held_direction = None
            self.repeating = False
            return
        if direction != self.held_direction:
            self.held_direction = direction
            self.repeat_at = now
            self.repeating = False
        if now >= self.repeat_at:
            step = -1 if direction == "up" else 1
            self.selection = (self.selection + step) % len(self.OPTIONS)
            self.draw()
            self.repeat_at = now + (0.09 if self.repeating else 0.24)
            self.repeating = True

    def click(self, x: int, y: int) -> str | None:
        if not self.active:
            return None
        if self.detail is not None:
            self.back()
            return None
        if 42 <= x <= 274:
            index = round((y - 82) / 40)
            if 0 <= index < len(self.OPTIONS) and abs(y - (82 + index * 40)) <= 18:
                self.selection = index
                return self.activate()
        return None

    def _frame(self, x1: int, y1: int, x2: int, y2: int) -> None:
        c = self.canvas
        tag = self.TAG
        c.create_rectangle(x1 + 5, y1 + 5, x2 + 5, y2 + 5,
                           fill="#070910", outline="", tags=tag)
        c.create_rectangle(x1, y1, x2, y2,
                           fill="#8caeb8", outline="#a9c9cd", width=3, tags=tag)
        c.create_rectangle(x1 + 5, y1 + 5, x2 - 5, y2 - 5,
                           fill="#dce9e7", outline="#eef7ef", width=2, tags=tag)
        c.create_rectangle(x1 + 10, y1 + 10, x2 - 10, y2 - 10,
                           fill="#272b70", outline="", tags=tag)
        c.create_rectangle(x1 + 11, y1 + 11, x2 - 11, y1 + 40,
                           fill="#4b5292", outline="", tags=tag)

    def draw(self) -> None:
        if not self.active:
            return
        c = self.canvas
        tag = self.TAG
        c.delete(tag)
        c.create_rectangle(0, 0, 960, 540, fill="#08090c", outline="", tags=tag)
        self._frame(28, 44, 274, 458)
        self._frame(284, 44, 932, 458)
        self._frame(28, 478, 932, 529)

        for index, (label, _) in enumerate(self.OPTIONS):
            y = 82 + index * 40
            active = index == self.selection
            if active:
                c.create_text(51, y, text="▶", anchor="w", fill="#f7f2dc",
                              font=self.font(25, True), tags=tag)
            c.create_text(76, y, text=label, anchor="w",
                          fill="#ffe37e" if active else "#f4f5f3",
                          font=self.font(23, active), tags=tag)

        if self.detail is None and len(self.party_names()) > 1:
            names = self.party_names()
            row_height = min(160, 320 // len(names))
            for index, name in enumerate(names):
                top = 79 + index * row_height
                image = self.party_portrait(name)
                side = 128 if row_height >= 138 else 64
                if image is not None and side == 64:
                    if name not in self._small_portraits:
                        self._small_portraits[name] = image.subsample(2)
                    image = self._small_portraits[name]
                c.create_rectangle(311, top, 321 + side, top + side + 10,
                                   fill="#1e235f", outline="#d8e9e7", width=3, tags=tag)
                if image is not None:
                    c.create_image(316 + side/2, top + side/2 + 5, image=image, tags=tag)
                c.create_text(475, top + 20, text=name.upper(), anchor="w", fill="#ffffff",
                              font=self.font(30, True), tags=tag)
                c.create_text(475, top + 64, text="Mountain Wanderer" if name == "Temur" else "Skirter",
                              anchor="w", fill="#80eaf5", font=self.font(23), tags=tag)
            c.create_text(315, 425, text="SUNREST EXCAVATION · FLOOR 1", anchor="w",
                          fill="#f5e29b", font=self.font(23), tags=tag)
        elif self.detail is None:
            image = self.portrait()
            c.create_rectangle(311, 79, 449, 217, fill="#1e235f",
                               outline="#d8e9e7", width=3, tags=tag)
            if image is not None:
                c.create_image(380, 148, image=image, tags=tag)
            c.create_text(475, 88, text="RETRI", anchor="w", fill="#ffffff",
                          font=self.font(37, True), tags=tag)
            c.create_text(475, 151, text="Skirter", anchor="w", fill="#dcecf0",
                          font=self.font(27), tags=tag)
            c.create_text(475, 198, text="PARTY  " + " · ".join(self.party_names()), anchor="w",
                          fill="#80eaf5", font=self.font(26), tags=tag)
            c.create_line(311, 242, 905, 242, fill="#a9c2d1", width=3, tags=tag)
            c.create_text(315, 274, text="SUNREST EXCAVATION", anchor="w",
                          fill="#f5e29b", font=self.font(32, True), tags=tag)
            c.create_text(315, 342, text="Following a strange sound...",
                          anchor="w", fill="#ffffff", font=self.font(27), tags=tag)
            c.create_text(315, 401, text="FLOOR  1", anchor="w",
                          fill="#80eaf5", font=self.font(27), tags=tag)
        else:
            title, description = self.OPTIONS[self.detail]
            if title == "Formation":
                description = "Party: " + ", ".join(self.party_names()) + "."
            c.create_text(314, 96, text=title.upper(), anchor="w",
                          fill="#ffe37e", font=self.font(36, True), tags=tag)
            c.create_line(311, 129, 905, 129, fill="#a9c2d1", width=3, tags=tag)
            c.create_text(314, 170, text=description, anchor="nw", width=560,
                          fill="#ffffff", font=self.font(30), tags=tag)
            c.create_text(314, 395, text="PRESS BACK TO RETURN TO THE LIST",
                          anchor="w", fill="#9adbe8", font=self.font(23), tags=tag)

        c.create_text(52, 503,
                      text="D-PAD / ARROWS  MOVE     CROSS / ENTER  SELECT     CIRCLE / ESC  BACK",
                      anchor="w", fill="#ffffff", font=self.font(18), tags=tag)
        c.tag_raise(tag)
