"""Lightweight in-game menu with reusable retro panels and D-pad navigation."""
from __future__ import annotations

import tkinter as tk
from pathlib import Path
from typing import Callable


from battle import JOBS


class GameMenu:
    TAG = "game_menu"
    OPTIONS = (
        ("Items", "Your pack is empty for now."),
        ("Abilities", "Discover the stone to awaken Astral Sync."),
        ("Equip", "Equipment management is coming later."),
        ("Status", "Retri is a skirter exploring Sunrest's cavern."),
        ("Formation", "Retri is the only party member right now."),
        ("Configuration", "Display settings can be changed at the title screen."),
        ("Save", "Saving will be added in a later pass."),
        ("Load", "No saved cavern journey exists yet."),
        ("Sync", "Discover the stone to awaken Astral Sync."),
        ("Title Screen", "Leave the cavern and return to the title screen."),
    )

    def __init__(
        self,
        canvas: tk.Canvas,
        font: Callable[[int, bool], tuple[str, int, str]],
        portrait: Callable[[], tk.PhotoImage | None],
    ) -> None:
        self.canvas = canvas
        self.font = lambda size, bold=False: font(max(1, round(size * 0.88)), bold)
        self.portrait = portrait
        self.party_names = lambda: ["Retri"]
        self.party_portrait = lambda name: self.portrait() if name == "Retri" else None
        self.roster = lambda: []
        self.sync_unlocked = lambda: False
        self.member_index = 0
        self.sync_index = 0
        self.sync_icons = {}
        self.inventory = lambda: {}
        self.use_item = lambda name, member: "Item unavailable."
        self.progress = lambda: (1, 0, 30)
        self.item_index = 0
        self.item_targeting = False
        self.feedback = ""
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
        if self.detail == 0 and self.item_targeting:
            self.item_targeting = False
            self.draw()
            return
        if self.detail is not None:
            self.detail = None
            self.draw()
        else:
            self.close()

    def activate(self) -> str | None:
        if not self.active:
            return None
        if self._roster_page():
            self._choose_member()
            self.draw()
            return None
        if self.detail is not None:
            self.back()
            return None
        if self.selection == len(self.OPTIONS) - 1:
            return "title"
        self.member_index = 0
        self.item_index = 0
        self.item_targeting = False
        self.feedback = ""
        self.detail = self.selection
        if self._sync_page() and self.roster():
            current = self._current_job(self.roster()[self.member_index])
            self.sync_index = JOBS.index(current) if current in JOBS else 0
        self.draw()
        return None

    def _roster_page(self):
        return self.detail in (0, 3, 4) or self._sync_page()

    def _sync_page(self):
        return self.detail == 8 or (self.detail == 1 and self.sync_unlocked())

    def _current_job(self, member):
        job = member.get("job")
        return "Saint" if job == "Saint Warrior" else job

    def _sync_icon(self, job):
        if job not in self.sync_icons:
            path = Path(__file__).resolve().parent / "assets" / "sync" / (job.lower() + "-emblem.png")
            self.sync_icons[job] = tk.PhotoImage(master=self.canvas, file=str(path)).zoom(2)
        return self.sync_icons[job]

    def _choose_member(self):
        members = self.roster()
        member = members[self.member_index]
        if self.detail == 0:
            items = list(self.inventory())
            if not items:
                self.feedback = "Your pack is empty."
            elif not self.item_targeting:
                self.item_targeting = True
                self.feedback = "Choose a party member."
            else:
                self.feedback = self.use_item(items[self.item_index], member)
            return
        if self.detail == 3:
            return
        if self._sync_page():
            if not self.sync_unlocked():
                self.feedback = "Find the blue stone to awaken Sync."
                return
            member["job"] = JOBS[self.sync_index]
            self.feedback = member["name"] + " synced with " + member["job"] + "."
            return
        active = [p for p in members if p.get("active", True)]
        self.feedback = ""
        if member in active:
            if not any(p is not member and p["hp"] > 0 for p in active):
                self.feedback = "Keep one standing fighter active."
            else:
                member["active"] = False
        elif len(active) >= 3:
            self.feedback = "Move a fighter to reserve first."
        else:
            member["active"] = True

    def navigate(self, direction: str | None, now: float) -> None:
        if not self.active or (self.detail is not None and not self._roster_page()):
            return
        directions = ("up", "down", "left", "right") if self._sync_page() else ("up", "down")
        if direction not in directions:
            self.held_direction = None
            self.repeating = False
            return
        if direction != self.held_direction:
            self.held_direction = direction
            self.repeat_at = now
            self.repeating = False
        if now >= self.repeat_at:
            step = -1 if direction in ("up", "left") else 1
            if self._sync_page() and direction in ("left", "right"):
                self.sync_index = (self.sync_index + step) % len(JOBS)
                self.feedback = ""
            elif self._roster_page():
                if self.detail == 0 and not self.item_targeting:
                    items = list(self.inventory())
                    if items:
                        self.item_index = (self.item_index + step) % len(items)
                else:
                    self.member_index = (self.member_index + step) % len(self.roster())
                self.feedback = ""
                if self._sync_page():
                    current = self._current_job(self.roster()[self.member_index])
                    self.sync_index = JOBS.index(current) if current in JOBS else 0
            else:
                self.selection = (self.selection + step) % len(self.OPTIONS)
            self.draw()
            self.repeat_at = now + (0.09 if self.repeating else 0.24)
            self.repeating = True

    def click(self, x: int, y: int) -> str | None:
        if self.active and self._sync_page():
            for index, (cx, cy) in enumerate(((610, 170), (752, 302), (468, 302))):
                if abs(x-cx) <= 42 and abs(y-cy) <= 42:
                    self.sync_index = index
                    self._choose_member()
                    self.draw()
                    return None
            return None
        if self.active and self.detail == 0:
            if not self.item_targeting and 315 <= x <= 590:
                index = (y-131)//38
                if 0 <= index < len(self.inventory()):
                    self.item_index = index
                    self._choose_member()
                    self.draw()
            elif self.item_targeting and 590 <= x <= 905:
                index = max(0, self.member_index-3) + (y-131)//38
                if 0 <= index < len(self.roster()):
                    self.member_index = index
                    self._choose_member()
                    self.draw()
            return None
        if self.active and self.detail == 3:
            if 315 <= x <= 900 and 130 <= y <= 170:
                self.member_index = (self.member_index + 1) % len(self.roster())
                self.draw()
            return None
        if self.active and self._roster_page():
            start = max(0, self.member_index-3)
            row = (y-146)//48
            if 315 <= x <= 900 and 0 <= row < 4 and start+row < len(self.roster()):
                self.member_index = start+row
                self._choose_member()
                self.draw()
            return None
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
        elif self.detail in (0, 3):
            self._draw_items_or_status()
        elif self._sync_page():
            self._draw_sync()
        elif self._roster_page():
            members = self.roster()
            count = sum(p.get("active", True) for p in members)
            heading = f"FORMATION  {count}/3" if self.detail == 4 else "ASTRAL SYNC"
            c.create_text(315, 96, text=heading, anchor="w", fill="#ffe37e", font=self.font(30, True), tags=tag)
            start = max(0, self.member_index-3)
            for row, member in enumerate(members[start:start+4]):
                selected = start+row == self.member_index
                value = ("Active" if member.get("active", True) else "Reserve") if self.detail == 4 else member.get("job", "Unbound")
                c.create_text(320, 170+48*row, anchor="w", text=("▶  " if selected else "   ") + member["name"] + "    " + value,
                              fill="#ffe37e" if selected else "#ffffff", font=self.font(25), tags=tag)
            help_text = "Confirm to change formation." if self.detail == 4 else "Confirm to change this member's path."
            c.create_text(315, 390, text=self.feedback or help_text, width=570, anchor="w", fill="#9adbe8", font=self.font(22), tags=tag)
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

        controls = ("D-PAD MOVE   CROSS SELECT   CIRCLE BACK" if self._sync_page() else
                    "D-PAD / ARROWS  MOVE     CROSS / ENTER  SELECT     CIRCLE / ESC  BACK")
        c.create_text(52, 503,
                      text=controls,
                      anchor="w", fill="#ffffff", font=self.font(18), tags=tag)
        c.tag_raise(tag)

    def _draw_sync(self):
        c, tag = self.canvas, self.TAG
        member = self.roster()[self.member_index]
        current = self._current_job(member) or "Unbound"
        selected = JOBS[self.sync_index]
        descriptions = {"Seer": "Strikes ignore armor.",
                        "Cutpurse": "Earn extra gold on victory.",
                        "Saint": "Guard restores 3 HP."}
        c.create_text(315, 91, text="ASTRAL SYNC", anchor="w", fill="#ffe37e", font=self.font(30, True), tags=tag)
        c.create_text(900, 91, text="UNLOCKED" if self.sync_unlocked() else "LOCKED", anchor="e", fill="#80eaf5", font=self.font(20), tags=tag)
        c.create_text(610, 121, text=f"▲  {member['name']}  ▼   ·   {current}", fill="#ffffff", font=self.font(22), tags=tag)
        c.create_oval(441, 145, 779, 347, outline="#7288c4", width=3, tags=tag)
        for index, (job, (x, y)) in enumerate(zip(JOBS, ((610, 170), (752, 302), (468, 302)))):
            chosen = index == self.sync_index
            c.create_rectangle(x-37, y-37, x+37, y+37, fill="#d5dfed" if chosen else "#485a96",
                               outline="#ffe37e" if chosen else "#8799c6", width=3, tags=tag)
            c.create_image(x, y, image=self._sync_icon(job), tags=tag)
            c.create_text(x, y+50, text=job.upper(), fill="#ffe37e" if chosen else "#ffffff",
                          font=self.font(21, chosen), tags=tag)
        c.create_text(610, 248, text="◀  " + selected.upper() + "  ▶", fill="#ffe37e", font=self.font(23, True), tags=tag)
        message = self.feedback or (descriptions[selected] if self.sync_unlocked() else "Find the blue stone to awaken Sync.")
        c.create_text(610, 389, text=message, fill="#ffffff", font=self.font(21), tags=tag)
        c.create_text(610, 423, text="UP / DOWN MEMBER    LEFT / RIGHT CLASS    CONFIRM TO SYNC", fill="#9adbe8", font=self.font(16), tags=tag)

    def _draw_items_or_status(self):
        c, tag = self.canvas, self.TAG
        members = self.roster()
        member = members[self.member_index]
        heading = "ITEMS" if self.detail == 0 else "STATUS"
        c.create_text(315, 96, text=heading, anchor="w", fill="#ffe37e", font=self.font(30, True), tags=tag)
        if self.detail == 0:
            items = list(self.inventory().items())
            for i, (name, count) in enumerate(items[:4]):
                c.create_text(320, 150+i*38, text=("▶ " if i == self.item_index and not self.item_targeting else "   ") + f"{name}  x{count}", anchor="w", fill="#ffffff", font=self.font(23), tags=tag)
            if self.item_targeting:
                start = max(0, self.member_index-3)
                for row, target in enumerate(members[start:start+4]):
                    selected = start+row == self.member_index
                    c.create_text(600, 150+row*38, text=("▶ " if selected else "   ") + f"{target['name']} {target['hp']}/{target['max_hp']}", anchor="w", fill="#ffe37e" if selected else "#ffffff", font=self.font(20), tags=tag)
            hint = "Select an item." if not self.item_targeting else "UP/DOWN target · CONFIRM use · BACK items"
        else:
            level, xp, needed = self.progress()
            job = self._current_job(member) or "Unbound"
            for i, line in enumerate((f"{member['name']}  ▲▼", f"HP  {member['hp']} / {member['max_hp']}", f"PARTY LEVEL  {level}     XP  {xp} / {needed}", f"SYNC  {job}", f"ATTACK  {10+level-1}–{14+level-1}")):
                c.create_text(320, 150+i*42, text=line, anchor="w", fill="#ffffff", font=self.font(24), tags=tag)
            hint = "UP/DOWN choose member · BACK return"
        c.create_text(320, 399, text=self.feedback or hint, anchor="w", width=570, fill="#9adbe8", font=self.font(21), tags=tag)
