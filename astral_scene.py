"""The blue stone's reveal and permanent, per-member class choice."""
from __future__ import annotations

import random
import tkinter as tk
from pathlib import Path

from classes import JOBS, DESCRIPTIONS, EMBLEMS, current_job, bind_job


class AstralScene:
    TAG = "astral"
    REVEAL_SECONDS = 2.8

    def __init__(self, canvas, font, assets: Path):
        self.canvas, self.font = canvas, font
        folder = assets / "astral"
        self.stones = [tk.PhotoImage(master=canvas, file=str(folder / f"stone-{i}.png")).zoom(2)
                       for i in range(3)]
        self.silhouettes = {job: tk.PhotoImage(master=canvas, file=str(folder / (job.lower() + ".png")))
                            for job in JOBS}
        self.icons = {job: tk.PhotoImage(master=canvas, file=str(assets / "sync" / EMBLEMS[job]))
                      for job in JOBS}
        rng = random.Random(731)
        self.stars = [(rng.randrange(35, 925), rng.randrange(24, 514),
                       rng.choice(("#375c9a", "#608fca", "#9ecbea")))
                      for _ in range(55)]
        self.active = False

    def start(self, party, now, reveal=True):
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
        c.create_rectangle(0, 0, 960, 540, fill="#080f2b", outline="", tags=tag)
        c.create_rectangle(15, 15, 945, 525, outline="#bc9a5a", width=3, tags=tag)
        c.create_rectangle(21, 21, 939, 519, outline="#355d9d", width=2, tags=tag)
        for x, y, color in self.stars:
            c.create_rectangle(x, y, x+2, y+2, fill=color, outline="", tags=tag)

    def draw(self):
        c, tag = self.canvas, self.TAG
        c.delete(tag)
        self._background()
        if self.phase == "reveal":
            c.create_text(480, 90, text="THE BLUE STONE", fill="#f4d98a",
                          font=self.font(32, True), tags=tag)
            self.stone_item = c.create_image(480, 244, image=self.stones[self.stone_index], tags=tag)
            c.create_text(480, 389, text="A quiet light answers your touch.", fill="#c4eaff",
                          font=self.font(25), tags=tag)
            c.create_text(480, 461, text="ENTER / CROSS TO CONTINUE", fill="#9adbe8",
                          font=self.font(19), tags=tag)
            return

        member = self.party[self.member_index]
        bound = current_job(member)
        c.create_text(480, 39, text="ASTRAL RESONANCE", fill="#f4d98a",
                      font=self.font(28, True), tags=tag)
        c.create_text(480, 78, text=f"◀  {member['name'].upper()}  ·  {(bound or 'UNBOUND').upper()}  ▶",
                      fill="#dff4ff", font=self.font(20, True), tags=tag)
        c.create_text(480, 109, text="LEFT / RIGHT: PARTY MEMBER", fill="#8bcbe5",
                      font=self.font(15), tags=tag)
        self.stone_item = c.create_image(156, 158, image=self.stones[self.stone_index], tags=tag)
        if self.selection < len(JOBS):
            c.create_image(750, 158, image=self.silhouettes[JOBS[self.selection]], tags=tag)
        c.create_text(156, 91, text="CHOOSE YOUR PATH", fill="#9adbe8",
                      font=self.font(16), tags=tag)
        for index, job in enumerate((*JOBS, "Leave unattuned")):
            top = 237 + index * 57
            selected = self.selection == index
            c.create_rectangle(245, top, 915, top+50, fill="#18285d" if selected else "#101b43",
                               outline="#8de7ff" if selected else "#63749b", width=2, tags=tag)
            if selected:
                c.create_text(257, top+25, text="▶", anchor="w", fill="#ffe37e",
                              font=self.font(20, True), tags=tag)
            if index < len(JOBS):
                c.create_image(307, top+25, image=self.icons[job], tags=tag)
                c.create_text(350, top+25, text=job.upper(), anchor="w",
                              fill="#ffe37e" if selected else "#f2f4fb", font=self.font(23, selected), tags=tag)
                c.create_text(500, top+25, text=DESCRIPTIONS[job], anchor="w", width=395,
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
            c.create_text(480, 195, text=f"BIND {member['name'].upper()} TO {JOBS[self.selection].upper()}?",
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
            self.canvas.itemconfigure(self.stone_item, image=self.stones[index])

    def navigate(self, direction, now):
        if self.phase == "reveal":
            return
        if direction not in ("up", "down", "left", "right"):
            self.held = None
            return
        if direction != self.held:
            self.held = direction
            self.repeat_at = now
        if now < self.repeat_at:
            return
        if self.phase == "confirm":
            if direction in ("left", "right"):
                self.confirm_bind = direction == "left"
        elif direction in ("left", "right"):
            step = -1 if direction == "left" else 1
            self.member_index = (self.member_index + step) % len(self.party)
            self.feedback = ""
        else:
            self.selection = (self.selection + (-1 if direction == "up" else 1)) % 4
            self.feedback = ""
        self.repeat_at = now + 0.22
        self.draw()

    def confirm(self):
        if self.phase == "reveal":
            self.phase = "choose"
        elif self.phase == "confirm":
            if self.confirm_bind:
                member = self.party[self.member_index]
                job = JOBS[self.selection]
                self.feedback = (f"{member['name']} is bound to {job}." if bind_job(member, job)
                                 else "This member is already bound.")
            self.phase = "choose"
        elif self.selection == len(JOBS):
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
        if 60 <= y <= 100 and 260 <= x <= 700:
            self.member_index = (self.member_index + (-1 if x < 480 else 1)) % len(self.party)
            self.feedback = ""
            self.draw()
        elif 245 <= x <= 915 and 237 <= y < 465:
            index = int((y - 237) // 57)
            if 0 <= index <= len(JOBS):
                self.selection = index
                return self.confirm()
        return None
