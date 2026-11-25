"""Stone reveals and permanent, per-member astral class choices."""
from __future__ import annotations

import random
import tkinter as tk
from pathlib import Path

from abilities import remember
from classes import BLUE_STONE, NOKTAKORO, SENBRANKA, STONE_NAMES, STONE_PATHS, DESCRIPTIONS, EMBLEMS, bind_job, current_job
from den_art import STONE_OUTLINE, black_stone, white_stone


_ONDASTELA_CONTOUR = (
    (16, 29), (19, 24), (21, 21), (25, 17), (28, 14), (32, 13),
    (35, 14), (38, 16), (40, 20), (42, 26), (46, 30), (46, 33),
    (43, 38), (40, 41), (37, 44), (31, 47), (28, 49), (25, 48),
    (22, 45), (19, 41), (18, 37), (16, 34),
)


def _ondastela_frame(canvas, path):
    """Ink the faceted stone inside its existing glow on the native pixel grid."""
    art = tk.PhotoImage(master=canvas, file=str(path))
    contour = _ONDASTELA_CONTOUR
    for (x1, y1), (x2, y2) in zip(contour, contour[1:] + contour[:1]):
        steps = max(abs(x2 - x1), abs(y2 - y1))
        for step in range(steps + 1):
            art.put(STONE_OUTLINE, (round(x1 + (x2 - x1) * step / steps),
                                    round(y1 + (y2 - y1) * step / steps)))
    return art.zoom(2)


class AstralScene:
    TAG = "astral"
    REVEAL_SECONDS = 2.8

    def __init__(self, canvas, font, assets: Path):
        self.canvas, self.font = canvas, font
        folder = assets / "astral"
        self.sky = tk.PhotoImage(master=canvas, file=str(folder / "starfield.png"))
        # Smaller pieces avoid large temporary Tk images at fractional fullscreen scales.
        self.sky_tiles = []
        for row in range(3):
            for col in range(3):
                x, y = col * 320, row * 180
                width, height = min(321, 960-x), min(181, 540-y)
                tile = tk.PhotoImage(master=canvas, width=width, height=height)
                tile.tk.call(tile, "copy", self.sky, "-from", x, y, x+width, y+height)
                self.sky_tiles.append((x, y, tile))
        self.stones = [_ondastela_frame(canvas, folder / f"stone-{i}.png") for i in range(3)]
        self.silhouettes = {
            job: tk.PhotoImage(master=canvas, file=str(folder / "constellations" / f"{job.lower()}.png"))
            for job in EMBLEMS
        }
        self.icons = {job: tk.PhotoImage(master=canvas, file=str(assets / "sync" / EMBLEMS[job]))
                      for job in EMBLEMS}
        self.noktakoro_art = black_stone(canvas, 3)
        self.senbranka_art = white_stone(canvas, 6)
        rng = random.Random(731)
        self.stars = [(rng.randrange(35, 925), rng.randrange(24, 514),
                       rng.choice(("#375c9a", "#608fca", "#9ecbea")))
                      for _ in range(28)]
        self.twinkle_stars = [(rng.randrange(40, 920), rng.randrange(30, 510),
                               rng.randrange(4)) for _ in range(14)]
        self.twinkle_items = []
        self.twinkle_step = None
        self.active = False

    def start(self, party, now, reveal=True, *, stone=BLUE_STONE):
        self.stone = stone
        self.paths = STONE_PATHS[stone]
        self.party = party
        self.member_index = 0
        self.selection = 0
        self.confirm_bind = False
        self.phase = "reveal" if reveal else "choose"
        self.started = now
        self.stone_index = 0
        self.held = None
        self.repeat_at = 0.0
        self.feedback = ""
        self.active = True
        self.draw()

    def close(self):
        self.canvas.delete(self.TAG)
        self.active = False

    def _background(self):
        c, tag = self.canvas, self.TAG
        for x, y, tile in self.sky_tiles:
            c.create_image(x, y, image=tile, anchor="nw", tags=tag)
        if self.stone == NOKTAKORO:
            c.create_rectangle(0, 0, 960, 540, fill="#180e2b", stipple="gray50", outline="", tags=tag)
        c.create_rectangle(15, 15, 945, 525, outline="#bc9a5a", width=3, tags=tag)
        c.create_rectangle(21, 21, 939, 519, outline="#355d9d", width=2, tags=tag)
        for x, y, color in self.stars:
            c.create_rectangle(x, y, x+2, y+2, fill=color, outline="", tags=tag)
        self.twinkle_items = []
        self.twinkle_step = None
        for x, y, offset in self.twinkle_stars:
            horizontal = c.create_line(x-3, y, x+3, y, fill="#7295c6", tags=tag)
            vertical = c.create_line(x, y-3, x, y+3, fill="#7295c6", tags=tag)
            self.twinkle_items.append((horizontal, vertical, offset))

    def _stone_image(self):
        if self.stone == SENBRANKA:
            return self.senbranka_art
        return self.noktakoro_art if self.stone == NOKTAKORO else self.stones[self.stone_index]

    def draw(self):
        c, tag = self.canvas, self.TAG
        c.delete(tag)
        self._background()
        if self.phase == "reveal":
            epithet = {BLUE_STONE: "WAVE STAR", NOKTAKORO: "HEART OF NIGHT", SENBRANKA: "WITHOUT FRACTURE"}
            name = f"{STONE_NAMES[self.stone].upper()} · {epithet[self.stone]}"
            c.create_text(480, 90, text=name, fill="#f4d98a",
                          font=self.font(32, True), tags=tag)
            self.stone_item = c.create_image(480, 244, image=self._stone_image(), tags=tag)
            whisper = ("Pinch where your shadow meets your fingers. Now pull." if self.stone == NOKTAKORO
                       else "A quiet light answers your touch.")
            c.create_text(480, 389, text=whisper, fill="#c4eaff",
                          font=self.font(25), tags=tag)
            c.create_text(480, 461, text="ENTER / CROSS TO CONTINUE", fill="#9adbe8",
                          font=self.font(19), tags=tag)
            return

        member = self.party[self.member_index]
        bound = current_job(member)
        c.create_text(480, 39, text=STONE_NAMES[self.stone].upper(), fill="#f4d98a",
                      font=self.font(28, True), tags=tag)
        c.create_text(480, 78, text=f"L1  ·  {member['name'].upper()}  ·  {(bound or 'UNBOUND').upper()}  ·  R1",
                      fill="#dff4ff", font=self.font(20, True), tags=tag)
        c.create_text(480, 109, text="L1 / R1: PARTY MEMBER", fill="#8bcbe5",
                      font=self.font(15), tags=tag)
        self.stone_item = c.create_image(156, 168, image=self._stone_image(), tags=tag)
        if self.selection < len(self.paths):
            c.create_image(750, 136, image=self.silhouettes[self.paths[self.selection]], tags=tag)
        c.create_text(156, 91, text="CHOOSE YOUR PATH", fill="#9adbe8",
                      font=self.font(16), tags=tag)
        for index, job in enumerate((*self.paths, "Leave unattuned")):
            top = 237 + index * 57
            selected = self.selection == index
            c.create_rectangle(245, top, 915, top+50, fill="#18285d" if selected else "#101b43",
                               outline="#8de7ff" if selected else "#63749b", width=2, tags=tag)
            if selected:
                c.create_text(257, top+25, text="▶", anchor="w", fill="#ffe37e",
                              font=self.font(20, True), tags=tag)
            if index < len(self.paths):
                c.create_image(307, top+25, image=self.icons[job], tags=tag)
                c.create_text(350, top+25, text=job.upper(), anchor="w",
                              fill="#ffe37e" if selected else "#f2f4fb", font=self.font(20, selected), tags=tag)
                c.create_text(580, top+25, text=DESCRIPTIONS[job], anchor="w", width=322,
                              fill="#c3dded", font=self.font(16), tags=tag)
            else:
                c.create_text(300, top+25, text="LEAVE UNATTUNED", anchor="w",
                              fill="#ffe37e" if selected else "#f2f4fb", font=self.font(21, selected), tags=tag)
                c.create_text(580, top+25, text="Choose later.", anchor="w", fill="#c3dded",
                              font=self.font(18), tags=tag)
        message = self.feedback or ("Already bound: this choice is permanent." if bound
                                    else "A chosen path is permanent for this journey.")
        c.create_text(480, 479, text=message, fill="#ffe39a" if bound else "#c7e7f8",
                      font=self.font(17), tags=tag)
        c.create_text(480, 504, text="UP / DOWN: PATH   ·   ENTER / CROSS: CHOOSE   ·   ESC / CIRCLE: BACK",
                      fill="#9adbe8", font=self.font(15), tags=tag)
        if self.phase == "confirm":
            c.create_rectangle(232, 160, 728, 363, fill="#10183e", outline="#d1bc7f", width=4, tags=tag)
            c.create_text(480, 195, text=f"BIND {member['name'].upper()} TO {self.paths[self.selection].upper()}?",
                          fill="#ffe399", font=self.font(25, True), tags=tag)
            c.create_text(480, 233, text="This choice is permanent.", fill="#ffffff",
                          font=self.font(22), tags=tag)
            for i, text in enumerate(("BIND", "GO BACK")):
                selected = (i == 0) == self.confirm_bind
                c.create_text(365 + 230*i, 301, text=("▶ " if selected else "  ") + text,
                              fill="#ffe37e" if selected else "#ffffff", font=self.font(23), tags=tag)

    def update(self, now):
        if not self.active:
            return
        if self.phase == "reveal" and now - self.started >= self.REVEAL_SECONDS:
            self.phase = "choose"
            self.draw()
        index = (0, 1, 2, 1)[int(max(0.0, now - self.started) / 0.35) % 4]
        if index != self.stone_index:
            self.stone_index = index
            self.canvas.itemconfigure(self.stone_item, image=self._stone_image())
        step = int(max(0.0, now - self.started) / 0.35)
        if step != self.twinkle_step:
            self.twinkle_step = step
            colors = ("#35537f", "#7295c6", "#c5edff", "#7295c6")
            for horizontal, vertical, offset in self.twinkle_items:
                color = colors[(step + offset) % len(colors)]
                self.canvas.itemconfigure(horizontal, fill=color)
                self.canvas.itemconfigure(vertical, fill=color)

    def change_member(self, step):
        if not self.active or self.phase != "choose" or len(self.party) < 2:
            return
        self.member_index = (self.member_index + step) % len(self.party)
        self.feedback = ""
        self.draw()

    def navigate(self, direction, now):
        if self.phase == "reveal":
            return
        directions = ("left", "right") if self.phase == "confirm" else ("up", "down")
        if direction not in directions:
            self.held = None
            return
        if direction != self.held:
            self.held = direction
            self.repeat_at = now
        if now < self.repeat_at:
            return
        if self.phase == "confirm":
            self.confirm_bind = direction == "left"
        else:
            self.selection = (self.selection + (-1 if direction == "up" else 1)) % (len(self.paths) + 1)
            self.feedback = ""
        self.repeat_at = now + 0.22
        self.draw()

    def confirm(self):
        if self.phase == "reveal":
            self.phase = "choose"
        elif self.phase == "confirm":
            if self.confirm_bind:
                member = self.party[self.member_index]
                job = self.paths[self.selection]
                if bind_job(member, job, self.stone):
                    remember(member)
                    self.feedback = f"{member['name']} is bound to {job}."
                else:
                    self.feedback = "This member is already bound."
            self.phase = "choose"
        elif self.selection == len(self.paths):
            self.close()
            return "close"
        elif current_job(self.party[self.member_index]):
            self.feedback = "This member is already bound."
        else:
            self.phase = "confirm"
            self.confirm_bind = False
        self.draw()
        return None

    def back(self):
        if self.phase == "confirm":
            self.phase = "choose"
            self.draw()
        else:
            self.close()
            return "close"
        return None

    def click(self, x, y):
        if self.phase == "reveal":
            return self.confirm()
        if self.phase == "confirm":
            if 270 <= y <= 332 and 270 <= x <= 460:
                self.confirm_bind = True
                return self.confirm()
            if 270 <= y <= 332 and 500 <= x <= 690:
                self.confirm_bind = False
                return self.confirm()
            return None
        if 245 <= x <= 915 and 237 <= y < 465:
            index = int((y - 237) // 57)
            if 0 <= index <= len(self.paths):
                self.selection = index
                return self.confirm()
        return None
