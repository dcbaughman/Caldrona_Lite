"""Lightweight in-game menu with reusable retro panels and D-pad navigation."""
from __future__ import annotations

import time
import tkinter as tk
from pathlib import Path
from typing import Callable


from abilities import attuned_stone, class_abilities, frame_at, learned_abilities, variant_for
from classes import JOBS, EMBLEMS, DESCRIPTIONS, current_job
from equipment import (SLOTS, SLOT_LABELS, STAT_LABELS, available_count, can_wear,
                       equip, item_for, owned_items, preview_value, stat_value, worn_id)


class GameMenu:
    TAG = "game_menu"
    OPTIONS = (
        ("Items", "Your pack is empty for now."),
        ("Abilities", "Discover the stone to awaken Astral Sync."),
        ("Equip", "Manage weapons, armor, shields and accessories."),
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
        self.supplies = lambda: {}
        self.use_item = lambda name, member: "Item unavailable."
        self.gear_inventory = lambda: {}
        self.gear_changed = lambda member: None
        self.progress = lambda: (1, 0, 30)
        self.item_index = 0
        self.item_targeting = False
        self.equip_slot = 0
        self.equip_index = 0
        self.equip_focus = "category"
        self.feedback = ""
        self._item_icons = {}
        self._slot_boxes = []
        self.hover_index = None
        self._motion_id = None
        self.glint = SlotGlint(canvas)
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
        self._bind_motion()
        self.draw()

    def close(self) -> None:
        self._stop_preview()
        self.glint.stop()
        self.hover_index = None
        self._slot_boxes = []
        self._unbind_motion()
        self.canvas.delete(self.TAG)
        self.active = False
        self.detail = None
        self.held_direction = None

    def back(self) -> None:
        if self.detail == 2 and self.equip_focus == "items":
            self.equip_focus = "category"
            self.feedback = ""
            self.draw()
            return
        if self.detail == 0 and self.item_targeting:
            self.item_targeting = False
            self.draw()
            return
        if self._equip_page() and self.equip_focus == "list":
            self.equip_focus = "category"
            self.draw()
            return
        if self.detail is not None:
            self._stop_preview()
            self.detail = None
            self.draw()
        else:
            self.close()

    def activate(self) -> str | None:
        if not self.active:
            return None
        if self.detail is None and self.selection in (1, 8) and self.sync_unlocked():
            return "sync"
        if self.detail == 2:
            self._equip_activate()
            self.draw()
            return None
        if self._roster_page():
            self._choose_member()
            self.draw()
            return None
        if self._equip_page():
            self._confirm_equip()
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
        self.equip_slot = 0
        self.equip_index = 0
        self.equip_focus = "category"
        self.feedback = ""
        self.detail = self.selection
        if self.detail == 2:
            self.equip_focus = "category"
            self.equip_category = 1
            self.item_index = 0
        if self._sync_page() and self.roster():
            current = self._current_job(self.roster()[self.member_index])
            self.sync_index = JOBS.index(current) if current in JOBS else 0
        self.draw()
        return None

    def _roster_page(self):
        return self.detail in (0, 3, 4) or self._sync_page()

    def _equip_page(self):
        return self.detail == 2

    def _sync_page(self):
        return self.detail == 8 or (self.detail == 1 and self.sync_unlocked())

    def _current_job(self, member):
        return current_job(member)

    def _sync_icon(self, job):
        if job not in self.sync_icons:
            path = Path(__file__).resolve().parent / "assets" / "sync" / EMBLEMS[job]
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
            self.feedback = "Open Sync to choose a permanent path."
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
        if self.active and self.detail == 2:
            self._equip_navigate(direction, now)
            return
        if not self.active or (self.detail is not None and not self._roster_page()):
            return
        directions = ("up", "down", "left", "right") if (
            self._sync_page() or self._equip_page() or self.detail == 3
        ) else ("up", "down")
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
            elif self._equip_page():
                self._move_equip(direction, step)
            elif self.detail == 3 and direction in ("left", "right"):
                self.status_tab = "stats" if direction == "left" else "abilities"
                self.item_index = 0
                self._preview_key = None
                self._stop_preview()
            elif self.detail == 3 and self.status_tab == "abilities":
                rows = self._status_abilities()
                if rows:
                    self.item_index = (self.item_index + step) % len(rows)
                self._preview_key = None
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
        if self.active and self.detail == 2:
            self._equip_click(x, y)
            return None
        if self.active and self._sync_page():
            for index, (cx, cy) in enumerate(((610, 170), (752, 302), (468, 302))):
                if abs(x-cx) <= 42 and abs(y-cy) <= 42:
                    self.sync_index = index
                    self._choose_member()
                    self.draw()
                    return None
            return None
        if self.active and self.detail == 0:
            if not self.item_targeting:
                for index, (x1, y1, x2, y2) in self._slot_boxes:
                    if x1 <= x <= 590 and y1 <= y <= y2:
                        self.item_index = index
                        self._choose_member()
                        self.draw()
                        break
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
        if self.active and self.detail == 3 and 700 <= x <= 900 and 78 <= y <= 112:
            self.status_tab = "abilities" if x >= 800 else "stats"
            self.item_index = 0
            self._preview_key = None
            self._stop_preview()
            self.draw()
            return None
        if not self.active:
            return None
        if self.detail is not None:
            self.back()
            return None
        if 42 <= x <= 274:
            index = round((y - 82) / 36)
            if 0 <= index < len(self.OPTIONS) and abs(y - (82 + index * 36)) <= 17:
                self.selection = index
                return self.activate()
        return None

    @staticmethod
    def _short(text, limit):
        return text if len(text) <= limit else text[:limit-3] + "..."

    def _equip_member(self):
        roster = self.roster()
        if not roster:
            return None
        self.member_index = min(self.member_index, len(roster)-1)
        return roster[self.member_index]

    def _equip_entries(self):
        slot = SLOTS[self.equip_slot]
        return [None] + [item.id for item in owned_items(self.gear_inventory(), slot)]

    def _equip_scroll(self, entries):
        return max(0, min(self.equip_index - 5, len(entries) - 6))

    def _equip_select_current(self):
        member = self._equip_member()
        entries = self._equip_entries()
        current = worn_id(member, SLOTS[self.equip_slot]) if member else None
        self.equip_index = entries.index(current) if current in entries and current is not None else min(1, len(entries)-1)

    def _equip_activate(self):
        member = self._equip_member()
        if member is None:
            return
        entries = self._equip_entries()
        if self.equip_focus == "category":
            self.equip_focus = "items"
            self._equip_select_current()
            self.feedback = ""
            return
        self.equip_index = min(self.equip_index, len(entries)-1)
        changed, self.feedback = equip(member, SLOTS[self.equip_slot], entries[self.equip_index],
                                       self.gear_inventory(), self.roster())
        if changed:
            self.gear_changed(member)

    def change_equipment_member(self, step):
        """Switch the previewed member without changing the selected slot."""
        if not self.active or self.detail != 2 or step not in (-1, 1):
            return
        roster = self.roster()
        if not roster:
            return
        self.member_index = (self.member_index + step) % len(roster)
        if self.equip_focus == "items":
            self._equip_select_current()
        else:
            self.equip_index = 0
        self.feedback = ""
        self.draw()

    def _equip_navigate(self, direction, now):
        if direction not in ("up", "down"):
            self.held_direction = None
            self.repeating = False
            return
        if direction != self.held_direction:
            self.held_direction = direction
            self.repeat_at = now
            self.repeating = False
        if now < self.repeat_at:
            return
        step = -1 if direction == "up" else 1
        if self.equip_focus == "category":
            self.equip_slot = (self.equip_slot + step) % len(SLOTS)
            self.equip_index = 0
        else:
            self.equip_index = (self.equip_index + step) % len(self._equip_entries())
        self.feedback = ""
        self.draw()
        self.repeat_at = now + (0.09 if self.repeating else 0.24)
        self.repeating = True

    def _equip_click(self, x, y):
        for index in range(len(SLOTS)):
            if 38 <= x <= 264 and abs(y - (169 + index*65)) <= 28:
                self.equip_slot = index
                self.equip_focus = "category"
                self._equip_activate()
                self.draw()
                return
        entries = self._equip_entries()
        start = self._equip_scroll(entries)
        if 288 <= x <= 338 and 130 <= y <= 152 and start:
            self.equip_focus = "items"
            self.equip_index = start - 1
            self.feedback = ""
            self.draw()
            return
        if 288 <= x <= 338 and 356 <= y <= 382 and start + 6 < len(entries):
            self.equip_focus = "items"
            self.equip_index = min(len(entries)-1, start + 6)
            self.feedback = ""
            self.draw()
            return
        row = round((y - 167) / 35)
        if 288 <= x <= 651 and 0 <= row < 6 and abs(y - (167 + row*35)) <= 16 and start + row < len(entries):
            index = start + row
            if self.equip_focus == "items" and self.equip_index == index:
                self._equip_activate()
            else:
                self.equip_focus = "items"
                self.equip_index = index
                self.feedback = ""
            self.draw()

    def _draw_equipment(self):
        c, tag = self.canvas, self.TAG
        c.create_rectangle(0, 0, 960, 540, fill="#08090c", outline="", tags=tag)
        self._frame(28, 24, 932, 94)
        self._frame(28, 103, 264, 454)
        self._frame(276, 103, 654, 454)
        self._frame(666, 103, 932, 454)
        self._frame(28, 470, 932, 528)
        text = lambda x, y, value, size=20, color="#ffffff", **kw: c.create_text(
            x, y, text=value, fill=color, font=self.font(size), tags=tag, **kw)
        text(51, 58, "EQUIP", 29, "#ffe37e", anchor="w")
        member = self._equip_member()
        if member is None:
            text(480, 275, "No party members available.", 24)
            return
        text(508, 57, "L1  <  " + self._short(member["name"].upper(), 16) + "  >  R1", 23)
        text(900, 58, "ACTIVE" if member.get("active", True) else "RESERVE", 18, "#80eaf5", anchor="e")
        text(49, 124, "CATEGORY", 19, "#80eaf5", anchor="w")
        for index, slot in enumerate(SLOTS):
            y = 169 + index*65
            chosen = index == self.equip_slot
            text(48, y, ("> " if chosen else "   ") + SLOT_LABELS[slot].upper(), 19,
                 "#ffe37e" if chosen else "#ffffff", anchor="w")
            equipped = item_for(worn_id(member, slot))
            text(72, y+23, self._short(equipped.name if equipped else "Empty", 16), 14,
                 "#b9c9d6", anchor="w")

        slot = SLOTS[self.equip_slot]
        entries = self._equip_entries()
        self.equip_index = min(self.equip_index, len(entries)-1)
        start = self._equip_scroll(entries)
        selected = entries[self.equip_index] if self.equip_focus == "items" else None
        text(297, 124, SLOT_LABELS[slot].upper(), 19, "#80eaf5", anchor="w")
        text(632, 124, "FREE/TOTAL", 15, "#80eaf5", anchor="e")
        for row, item_id in enumerate(entries[start:start+6]):
            y = 167 + row*35
            active = self.equip_focus == "items" and start+row == self.equip_index
            item = item_for(item_id)
            equipped_here = item is not None and worn_id(member, slot) == item.id
            label = (self._short(item.name, 15) + " [E]" if equipped_here else
                     self._short(item.name, 19)) if item else "Remove equipment"
            text(298, y, ("> " if active else "   ") + label, 18,
                 "#ffe37e" if active else "#ffffff", anchor="w")
            if item:
                total = self.gear_inventory().get(item.id, 0)
                free = available_count(self.gear_inventory(), self.roster(), item.id)
                value = f"{free}/{total}"
                color = "#8693ae" if not free and not equipped_here else "#c9dcf1"
                if not can_wear(member, item):
                    value, color = "CANNOT", "#e9a7a7"
                text(632, y, value, 17, color, anchor="e")
        if start:
            text(300, 146, "^", 14, "#80eaf5", anchor="w")
        if start + 6 < len(entries):
            text(300, 370, "v", 14, "#80eaf5", anchor="w")
        item = item_for(selected)
        if self.equip_focus != "items":
            description = "Choose a category. Accessories include artifacts and trinkets." if slot == "accessory" else "Choose a category, then select equipment."
        elif item is None:
            description = "Remove the item in this slot." if worn_id(member, slot) else "This slot is empty."
        elif not can_wear(member, item):
            description = member["name"] + " cannot equip " + item.name + "."
        elif worn_id(member, slot) != item.id and not available_count(self.gear_inventory(), self.roster(), item.id):
            description = "All copies are equipped by other party members."
        elif worn_id(member, slot) == item.id:
            description = item.name + " is equipped. " + item.description
        else:
            description = item.name + (": " + item.description if item.description else "")
        description = self._short(description, 70)
        description_item = text(298, 388, description, 16, "#b8dce6", anchor="nw", width=330)
        # Tk wraps using the actual font and display scale. Shorten only when
        # necessary so unusually long future item names stay inside the panel.
        bottom = getattr(c, "_value", lambda value: value)(444)
        while len(description) > 4 and c.bbox(description_item)[3] > bottom:
            plain = description[:-3] if description.endswith("...") else description
            description = plain[:-4].rstrip() + "..."
            c.itemconfigure(description_item, text=description)

        text(686, 124, "STATS", 19, "#80eaf5", anchor="w")
        abbreviations = ("MAX HP", "MAX MP", "STR", "DEF", "MAG", "MAG DEF", "AGI", "LUCK", "EVA", "ACC")
        for i, ((stat, _), label) in enumerate(zip(STAT_LABELS, abbreviations)):
            y = 166 + i*24
            before = stat_value(member, stat)
            after = preview_value(member, slot, selected, stat) if self.equip_focus == "items" else before
            text(686, y, label, 15, "#d8ecf3", anchor="w")
            if before == after:
                text(910, y, str(before), 16, "#ffffff", anchor="e")
            else:
                text(910, y, f"{before} > {after}", 16, "#8fe8ae" if after > before else "#ffaaaa", anchor="e")
        text(50, 490, self._short(self.feedback, 72) if self.feedback else
             ("Compare stats. [E] marks equipped gear." if self.equip_focus == "items" else "Choose a category to browse equipment."),
             16, "#ffe37e" if self.feedback else "#ffffff", anchor="w")
        text(50, 513, "UP/DOWN MOVE   L1/R1: CHANGE MEMBER   ENTER SELECT   ESC BACK", 14, "#a8dce7", anchor="w")

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
        if self.detail == 2:
            self._draw_equipment()
            c.tag_raise(tag)
            return
        c.create_rectangle(0, 0, 960, 540, fill="#08090c", outline="", tags=tag)
        self._frame(28, 44, 274, 458)
        self._frame(284, 44, 932, 458)
        self._frame(28, 478, 932, 529)

        for index, (label, _) in enumerate(self.OPTIONS):
            y = 82 + index * 36
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

        controls = "ARROWS/D-PAD MOVE   ENTER/CROSS OK   ESC/CIRCLE BACK"
        c.create_text(52, 503,
                      text=controls,
                      anchor="w", fill="#ffffff", font=self.font(18), tags=tag)
        c.tag_raise(tag)
        self._sync_glint()

    def _draw_sync(self):
        c, tag = self.canvas, self.TAG
        member = self.roster()[self.member_index]
        current = self._current_job(member) or "Unbound"
        selected = JOBS[self.sync_index]
        descriptions = DESCRIPTIONS
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
            if items:
                self.item_index %= len(items)
            if self.hover_index is not None and self.hover_index >= len(items):
                self.hover_index = None
            start = self._visible_item_start()
            self._slot_boxes = []
            for row, (name, count) in enumerate(items[start:start+4]):
                index = start + row
                y = 150 + row * 46
                icon = self._item_icon(name)
                box = draw_item_slot(c, 338, y, icon, tag)
                self._slot_boxes.append((index, box))
                marker = "▶ " if index == self.item_index and not self.item_targeting else "   "
                c.create_text(372, y, text=marker + f"{name}  x{count}", anchor="w", fill="#ffffff", font=self.font(23), tags=tag)
            if items and not self.item_targeting and not self.feedback:
                selected = item_by_name(items[self.item_index][0])
                if selected is not None:
                    c.create_text(320, 340, text=selected.description, anchor="nw", width=560,
                                  fill="#c5d8e4", font=self.font(18), tags=tag)
            if self.item_targeting:
                start = max(0, self.member_index-3)
                for row, target in enumerate(members[start:start+4]):
                    selected = start+row == self.member_index
                    c.create_text(600, 150+row*38, text=("▶ " if selected else "   ") + f"{target['name']} {target['hp']}/{stat_value(target, 'max_hp')}", anchor="w", fill="#ffe37e" if selected else "#ffffff", font=self.font(20), tags=tag)
            hint = "Select an item." if not self.item_targeting else "UP/DOWN target · CONFIRM use · BACK items"
        else:
            level, xp, needed = self.progress()
            if "level" in member:
                level, xp = member["level"], member.get("xp", 0)
                needed = 30 * level
            job = self._current_job(member) or "Unbound"
            c.create_text(320, 140, text=f"{member['name']}  ▲▼    LV {level}   XP {xp}/{needed}", anchor="w", fill="#ffffff", font=self.font(21), tags=tag)
            values = (("HP", f"{member['hp']}/{stat_value(member, 'max_hp')}"), ("MP", f"{member.get('mp', 0)}/{stat_value(member, 'max_mp')}"),
                      ("Strength", stat_value(member, 'strength')), ("Defense", stat_value(member, 'defense')),
                      ("Magic", stat_value(member, 'magic')), ("Magic Defense", stat_value(member, 'magic_defense')),
                      ("Agility", stat_value(member, 'agility')), ("Luck", stat_value(member, 'luck')),
                      ("Evasion", stat_value(member, 'evasion')), ("Accuracy", stat_value(member, 'accuracy')))
            for i, (label, value) in enumerate(values):
                c.create_text(320+(i%2)*285, 185+(i//2)*38, text=f"{label}  {value}", anchor="w", fill="#ffffff", font=self.font(19), tags=tag)
            c.create_text(320, 380, text=f"SYNC  {job}", anchor="w", fill="#80eaf5", font=self.font(19), tags=tag)
            hint = "UP/DOWN choose member · BACK return"
        c.create_text(320, 399, text=self.feedback or hint, anchor="w", width=570, fill="#9adbe8", font=self.font(21), tags=tag)

    def _bind_motion(self):
        if self._motion_id is None:
            self._motion_id = self.canvas.bind("<Motion>", self._on_motion, add="+")

    def _unbind_motion(self):
        if self._motion_id is not None:
            self.canvas.unbind("<Motion>", self._motion_id)
            self._motion_id = None

    def _event_point(self, event):
        canvas = self.canvas
        if hasattr(canvas, "logical_x"):
            return canvas.logical_x(event.x), canvas.logical_y(event.y)
        return event.x, event.y

    def _on_motion(self, event):
        if not self.active or self.detail not in (0, 2):
            return
        x, y = self._event_point(event)
        hover = None
        for index, (x1, y1, x2, y2) in self._slot_boxes:
            if x1 <= x <= x2 and y1 <= y <= y2:
                hover = index
                break
        if hover == self.hover_index:
            return
        self.hover_index = hover
        self._sync_glint()

    def _sync_glint(self):
        if not self.active or self.detail not in (0, 2, 3) or not self._slot_boxes:
            self.hover_index = None
            self.glint.stop()
            return
        if self.detail == 2:
            self.glint.play(self._slot_boxes[0][1])
            return
        index = self.hover_index if self.hover_index is not None else self.item_index
        box = next((bounds for slot, bounds in self._slot_boxes if slot == index), None)
        if box is None:
            self.glint.stop()
        else:
            self.glint.play(box)

    def _visible_item_start(self):
        count = len(self.inventory())
        if count <= 4:
            return 0
        return min(max(0, self.item_index - 3), count - 4)

    def _stop_preview(self):
        if self._fx_after is not None:
            try:
                self.canvas.after_cancel(self._fx_after)
            except tk.TclError:
                pass
            self._fx_after = None

    def _pixel(self, pixels, family="VT323"):
        import tkinter.font as tkfont
        try:
            families = set(tkfont.families(self.canvas))
        except tk.TclError:
            families = set()
        if family in families:
            return (family, -abs(pixels))
        return self.font(max(8, pixels))

    def _equip_member(self):
        members = self.roster()
        if not members:
            return None
        self.member_index %= len(members)
        return members[self.member_index]

    def _library(self, category):
        rows = []
        for item_id, count in self.supplies().items():
            if count <= 0:
                continue
            try:
                item = _lookup(item_id)
            except KeyError:
                continue
            if category_of(item) == category:
                rows.append((item, count))
        return rows

    def _move_equip(self, direction, step):
        members = self.roster()
        if direction in ("left", "right"):
            if members:
                self.member_index = (self.member_index + step) % len(members)
            self.item_index = 0
            self.feedback = ""
            return
        if self.equip_focus == "category":
            self.equip_category = (self.equip_category + step) % len(CATEGORIES)
            self.item_index = 0
        else:
            count = 1 + len(self._library(CATEGORIES[self.equip_category]))
            self.item_index = (self.item_index + step) % count
        self.feedback = ""

    def _confirm_equip(self):
        member = self._equip_member()
        if member is None:
            self.feedback = "No one is here."
            return
        if self.equip_focus == "category":
            self.equip_focus = "list"
            self.item_index = 0
            self.feedback = ""
            return
        category = CATEGORIES[self.equip_category]
        if self.item_index == 0:
            ok, _reason = unequip(member, category)
            self.feedback = "Removed." if ok else "That slot is empty."
            return
        library = self._library(category)
        item, _count = library[self.item_index - 1]
        ok, reason = can_equip(member, item.id)
        if not ok:
            job = self._current_job(member) or "Unbound"
            classes = ", ".join(item.weapon.classes) if item.weapon else ""
            self.feedback = f"{job} cannot equip {item.name}. ({classes})"
            return
        equip(member, item.id)
        self.feedback = f"{member['name']} equips {item.name}."

    def _selected_gear(self, member):
        category = CATEGORIES[self.equip_category]
        if self.equip_focus == "list" and self.item_index > 0:
            library = self._library(category)
            if self.item_index - 1 < len(library):
                return library[self.item_index - 1][0]
        return equipped_item(member, category)

    def _draw_equip_screen(self):
        c, tag = self.canvas, self.TAG
        member = self._equip_member()
        self._frame(18, 16, 942, 78)
        self._frame(18, 90, 250, 430)
        self._frame(262, 90, 680, 430)
        self._frame(692, 90, 942, 430)
        self._frame(18, 444, 942, 522)
        c.create_text(36, 46, text="EQUIP", anchor="w", fill="#ffe37e", font=self._pixel(18, "Press Start 2P"), tags=tag)
        if member is None:
            c.create_text(480, 250, text="No one is here.", fill="#ffffff", font=self._pixel(18), tags=tag)
            return
        name = member["name"].upper()
        c.create_text(480, 46, text=f"L1  <  {name}  >  R1", fill="#f4f5f3", font=self._pixel(16), tags=tag)
        active = "ACTIVE" if member.get("active", True) else "RESERVE"
        c.create_text(910, 46, text=active, anchor="e", fill="#80eaf5", font=self._pixel(16), tags=tag)
        c.create_text(36, 112, text="CATEGORY", anchor="w", fill="#80eaf5", font=self._pixel(14), tags=tag)
        category = CATEGORIES[self.equip_category]
        for index, key in enumerate(CATEGORIES):
            y = 160 + index * 62
            mark = "> " if index == self.equip_category else "  "
            color = "#ffe37e" if index == self.equip_category else "#f4f5f3"
            c.create_text(40, y, text=mark + CATEGORY_LABEL[key], anchor="w", fill=color, font=self._pixel(16), tags=tag)
            worn = equipped_item(member, key)
            c.create_text(58, y + 22, text=worn.name if worn else "Empty", anchor="w",
                          fill="#9adbe8", font=self._pixel(16), tags=tag)
        c.create_text(280, 112, text=CATEGORY_LABEL[category], anchor="w", fill="#80eaf5", font=self._pixel(14), tags=tag)
        c.create_text(660, 112, text="FREE/TOTAL", anchor="e", fill="#80eaf5", font=self._pixel(14), tags=tag)
        library = self._library(category)
        rows = [("remove", None, None)] + [("item", item, count) for item, count in library]
        if self.equip_focus == "list":
            self.item_index %= len(rows)
        if self.equip_focus == "list" and self.item_index > 0:
            shown = rows[self.item_index][1]
        else:
            shown = equipped_item(member, category)
        icon = None
        if shown is not None and shown.category != "shield":
            icon = self._item_icon(shown.name) if shown.id != SPELLBOOK.id else None
        box = draw_item_slot(c, 640, 156, icon, tag)
        self._slot_boxes.append((0, box))
        for index, (kind, item, count) in enumerate(rows[:8]):
            y = 196 + index * 26
            selected = self.equip_focus == "list" and index == self.item_index
            if kind == "remove":
                text = "Remove equipment"
                color = "#ffe37e" if selected else "#f4f5f3"
                right = ""
            else:
                text = item.name
                allowed, _reason = can_equip(member, item.id)
                color = "#ffe37e" if selected else ("#f4f5f3" if allowed else "#8ea0b8")
                right = f"{count}/{count}"
            if selected:
                c.create_text(268, y, text=">", anchor="w", fill="#ffe37e", font=self._pixel(16), tags=tag)
            c.create_text(286, y, text=text, anchor="w", fill=color, font=self._pixel(16), tags=tag)
            if right:
                c.create_text(660, y, text=right, anchor="e", fill=color, font=self._pixel(16), tags=tag)
        hint = self.feedback or (
            "Choose a category, then select equipment." if self.equip_focus == "category"
            else "Enter wears it. Esc returns to categories."
        )
        c.create_text(280, 400, text=hint, anchor="w", width=380, fill="#9adbe8", font=self._pixel(15), tags=tag)
        c.create_text(710, 112, text="STATS", anchor="w", fill="#80eaf5", font=self._pixel(14), tags=tag)
        stat_rows = (
            ("MAX HP", member.get("max_hp", 0)),
            ("MAX MP", member.get("max_mp", 0)),
            ("STR", member.get("strength", 0)),
            ("DEF", member.get("defense", 0)),
            ("MAG", member.get("magic", 0)),
            ("MAG DEF", member.get("magic_defense", 0)),
            ("AGI", member.get("agility", 0)),
            ("LUCK", member.get("luck", 0)),
            ("EVA", member.get("evasion", 0)),
            ("ACC", member.get("accuracy", 0)),
        )
        for index, (label, value) in enumerate(stat_rows):
            y = 150 + index * 26
            c.create_text(710, y, text=label, anchor="w", fill="#f4f5f3", font=self._pixel(15), tags=tag)
            c.create_text(920, y, text=str(value), anchor="e", fill="#f4f5f3", font=self._pixel(15), tags=tag)
        foot = self.feedback or (
            "Choose a category to browse equipment." if self.equip_focus == "category"
            else "Enter wears it. Esc returns to categories."
        )
        c.create_text(36, 468, text=foot, anchor="w", fill="#9adbe8", font=self._pixel(16), tags=tag)
        c.create_text(36, 498, text="UP/DOWN MOVE    L1/R1 CHANGE MEMBER    ENTER SELECT    ESC BACK",
                      anchor="w", fill="#f4f5f3", font=self._pixel(13), tags=tag)

    def _status_abilities(self):
        member = self.roster()[self.member_index] if self.roster() else None
        if member is None:
            return []
        return [ability for ability in class_abilities(self._current_job(member)) if ability.id != "strike"]

    def _ability_icon(self, ability, member):
        variant = variant_for(ability, member)
        # A bright middle frame reads in the slot. The first frame is often nearly empty.
        index = len(variant.frames) // 2
        path = variant.frames[index]
        key = ("ability", str(path))
        if key not in self._item_icons:
            image = tk.PhotoImage(master=self.canvas, file=str(path))
            while image.width() > 32 or image.height() > 32:
                image = image.subsample(2, 2)
            self._item_icons[key] = image
        return self._item_icons[key]

    def _draw_status_abilities(self, member, job):
        c, tag = self.canvas, self.TAG
        stone = attuned_stone(member)
        tone = "blue" if stone == "first_stone" else "gray"
        c.create_text(320, 132, text=f"{member['name']}   {job}   STONE {stone} · {tone}",
                      anchor="w", fill="#ffffff", font=self.font(16), tags=tag)
        rows = self._status_abilities()
        learned = {ability.id for ability in learned_abilities(member)}
        if not rows:
            c.create_text(320, 180, text="Bind a class at Astral Sync to learn abilities.",
                          anchor="w", fill="#ffffff", font=self.font(16), tags=tag)
            return
        self.item_index %= len(rows)
        self._slot_boxes = []
        for index, ability in enumerate(rows):
            y = 168 + index * 48
            icon = self._ability_icon(ability, member)
            box = draw_item_slot(c, 348, y, icon, tag)
            self._slot_boxes.append((index, box))
            known = ability.id in learned
            if not known:
                x1, y1, x2, y2 = box
                c.create_rectangle(x1 + 4, y1 + 4, x2 - 4, y2 - 4, fill="#08090c", stipple="gray50",
                                   outline="", tags=tag)
                c.create_text(348, y + 20, text=f"LV {ability.learn_level}", fill="#ffe37e",
                              font=self.font(10, True), tags=tag)
            mark = "> " if index == self.item_index else "  "
            color = "#ffe37e" if index == self.item_index else ("#ffffff" if known else "#8ea0b8")
            c.create_text(380, y, text=mark + ability.name, anchor="w", fill=color, font=self.font(16), tags=tag)
        chosen = rows[self.item_index]
        c.create_text(520, 200, text=chosen.description, anchor="nw", width=360,
                      fill="#c5d8e4", font=self.font(14), tags=tag)
        self._paint_status_preview(chosen, member)
        self._arm_status_preview()

    def _preview_image(self, path):
        key = ("preview", str(path))
        if key not in self._item_icons:
            image = tk.PhotoImage(master=self.canvas, file=str(path))
            while image.width() > 96 or image.height() > 96:
                image = image.subsample(2, 2)
            self._item_icons[key] = image
        return self._item_icons[key]

    def _paint_status_preview(self, ability, member):
        variant = variant_for(ability, member)
        if self._preview_key != ability.id:
            self._preview_key = ability.id
            self._preview_t0 = time.monotonic()
        elapsed = (time.monotonic() - self._preview_t0) * 1000
        if variant.total_ms:
            elapsed %= variant.total_ms
        image = self._preview_image(frame_at(variant, elapsed))
        self.canvas.create_rectangle(700, 300, 900, 430, fill="#08090c", outline="#d4a441", width=2,
                                     tags=(self.TAG, "ability_preview"))
        self.canvas.create_image(800, 365, image=image, tags=(self.TAG, "ability_preview"))
        if ability.id not in {item.id for item in learned_abilities(member)}:
            self.canvas.create_rectangle(740, 320, 860, 410, fill="#08090c", stipple="gray50",
                                         outline="", tags=(self.TAG, "ability_preview"))

    def _arm_status_preview(self):
        if self._fx_after is None:
            self._fx_after = self.canvas.after(50, self._tick_status_preview)

    def _tick_status_preview(self):
        self._fx_after = None
        if not self.active or self.detail != 3 or self.status_tab != "abilities":
            return
        member = self._equip_member()
        rows = [ability for ability in self._status_abilities() if ability.id != "strike"]
        if member is None or not rows:
            return
        self.canvas.delete("ability_preview")
        self.item_index %= len(rows)
        self._paint_status_preview(rows[self.item_index], member)
        self._fx_after = self.canvas.after(50, self._tick_status_preview)

    def _item_icon(self, name):
        item = item_by_name(name)
        if item is None:
            return None
        path = icon_file(item)
        key = str(path)
        if key not in self._item_icons:
            if not path.is_file():
                return None
            try:
                self._item_icons[key] = tk.PhotoImage(master=self.canvas, file=key)
            except tk.TclError:
                return None
        return self._item_icons[key]
