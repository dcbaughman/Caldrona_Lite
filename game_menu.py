"""Lightweight in-game menu with reusable retro panels and D-pad navigation."""
from __future__ import annotations

import tkinter as tk
from pathlib import Path
from typing import Callable


from abilities import learned_abilities, lesson_variant
from classes import BLUE_PATHS as JOBS, EMBLEMS, DESCRIPTIONS, STONE_NAMES, current_job
from crescendo import MAX_CHARGE, charge, choices_for, equipped_crescendo, is_unlocked, unlock_text
from equipment import (SLOTS, SLOT_LABELS, STAT_LABELS, available_count, can_wear,
                       equip, item_for, owned_items, preview_value, stat_value, worn_id)
from item_slots import SlotGlint, draw_item_slot
from items import gear_icon, supply_icon
from research import lessons_for

ITEM_ROW_TOP = 150
ITEM_ROW_HEIGHT = 42
VISIBLE_ITEM_ROWS = 6
EQUIP_SLOT_TOP = 158
EQUIP_SLOT_STEP = 48
EQUIP_SLOT_X = (44, 351)
EQUIP_ITEM_TOP = 153
EQUIP_ITEM_STEP = 24
EQUIP_ITEM_X = (510, 886)
EQUIP_ROWS = 6
EQUIP_SCROLL_X = 905
EQUIP_MEMBER_X = (358, 602)
MENU_ROW_TOP = 82
MENU_ROW_STEP = 34
CRESCENDO_PAGE = 9
CRESCENDO_ROW_TOP = 174
CRESCENDO_ROW_STEP = 55


class GameMenu:
    TAG = "game_menu"
    OPTIONS = (
        ("Items", "Your pack is empty for now."),
        ("Tome", "Read analects and spend RP to research abilities."),
        ("Equip", "Manage weapons, armor, shields and accessories."),
        ("Status", "Retri is a skirter exploring Sunrest's cavern."),
        ("Formation", "Retri is the only party member right now."),
        ("Configuration", "Display settings can be changed at the title screen."),
        ("Save", "Saving will be added in a later pass."),
        ("Load", "No saved cavern journey exists yet."),
        ("Sync", "Discover the stone to awaken Astral Sync."),
        ("Crescendo", "Choose a finishing move for each party member."),
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
        self.party_sprite = lambda name, job: None
        self.roster = lambda: []
        self.field_leader = lambda: None
        self.set_field_leader = lambda name: None
        self.formation_changed = lambda: None
        self.sync_unlocked = lambda: False
        self.member_index = 0
        self.sync_index = 0
        self.crescendo_index = 0
        self.sync_icons = {}
        self.inventory = lambda: {}
        self.use_item = lambda name, member: "Item unavailable."
        self.gear_inventory = lambda: {}
        self.gear_changed = lambda member: None
        self.progress = lambda: (1, 0, 30)
        self.item_index = 0
        self.item_targeting = False
        self.equip_slot = 0
        self.equip_index = 0
        self.equip_focus = "category"
        self.status_tab = "stats"
        self.feedback = ""
        self.glint = SlotGlint(canvas)
        self._icons = {}
        self._slot_box = None
        self._slot_boxes = []
        self.hover_index = None
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
        self.glint.stop()
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
        if self.detail is not None:
            self.detail = None
            self.draw()
        else:
            self.close()

    def activate(self) -> str | None:
        if not self.active:
            return None
        if self.detail is None and self.selection == 1:
            return "tome"
        if self.detail is None and self.selection == 8 and self.sync_unlocked():
            return "sync"
        if self.detail == 2:
            self._equip_activate()
            self.draw()
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
        self.equip_slot = 0
        self.equip_index = 0
        self.equip_focus = "category"
        self.status_tab = "stats"
        self.feedback = ""
        self.detail = self.selection
        if self.detail == CRESCENDO_PAGE:
            self._change_crescendo_member(0)
        if self._sync_page() and self.roster():
            current = self._current_job(self.roster()[self.member_index])
            self.sync_index = JOBS.index(current) if current in JOBS else 0
        self.draw()
        return None

    def _roster_page(self):
        return self.detail in (0, 3, 4, CRESCENDO_PAGE) or self._sync_page()

    def _change_crescendo_member(self, step):
        roster = self.roster()
        if roster:
            self.member_index = (self.member_index + step) % len(roster)
            member = roster[self.member_index]
            move = equipped_crescendo(member)
            self.crescendo_index = choices_for(member).index(move) if move else 0
        self.feedback = ""

    def _sync_page(self):
        return self.detail == 8

    def _current_job(self, member):
        return current_job(member)

    def _sync_icon(self, job):
        if job not in self.sync_icons:
            path = Path(__file__).resolve().parent / "assets" / "sync" / EMBLEMS.get(job, EMBLEMS["Seer"])
            self.sync_icons[job] = tk.PhotoImage(master=self.canvas, file=str(path)).zoom(2)
        return self.sync_icons[job]

    def _choose_member(self):
        members = self.roster()
        if not members:
            return
        member = members[self.member_index]
        if self.detail == CRESCENDO_PAGE:
            choices = choices_for(member)
            if not choices:
                return
            move = choices[self.crescendo_index]
            if not is_unlocked(member, move):
                self.feedback = f"Locked: {unlock_text(member, move)}."
                return
            member["crescendo_choice"] = move.id
            self.feedback = f"{move.name} equipped."
            return
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
                return
            member["active"] = False
        elif len(active) >= 3:
            self.feedback = "Move a fighter to reserve first."
            return
        else:
            member["active"] = True
        self.formation_changed()

    def _choose_field_leader(self):
        roster = self.roster()
        if not roster:
            return
        member = roster[self.member_index]
        if member.get("active", True) and member["hp"] > 0:
            self.set_field_leader(member["name"])
            self.feedback = f"{member['name']} now leads in the field."
        else:
            self.feedback = "Choose a standing, active party member to lead."
        self.draw()

    def navigate(self, direction: str | None, now: float) -> None:
        if self.active and self.detail == 2:
            self._equip_navigate(direction, now)
            return
        if self.active and self.detail == 3 and direction in ("left", "right"):
            self.change_equipment_member(-1 if direction == "left" else 1)
            return
        if self.active and self.detail == 4 and direction == "right":
            if self.held_direction != direction:
                self.held_direction = direction
                self._choose_field_leader()
            return
        if not self.active or (self.detail is not None and not self._roster_page()):
            return
        directions = ("up", "down", "left", "right") if self._sync_page() or self.detail == CRESCENDO_PAGE else ("up", "down")
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
            if self.detail == CRESCENDO_PAGE:
                if direction in ("left", "right"):
                    self._change_crescendo_member(step)
                elif self.roster():
                    member = self.roster()[self.member_index]
                    choices = choices_for(member)
                    if choices:
                        self.crescendo_index = (self.crescendo_index + step) % len(choices)
                    self.feedback = ""
            elif self._sync_page() and direction in ("left", "right"):
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
        if self.active and self.detail == 2:
            self._equip_click(x, y)
            return None
        if self.active and self.detail == CRESCENDO_PAGE:
            if 109 <= y <= 149 and (315 <= x <= 352 or 869 <= x <= 905):
                self._change_crescendo_member(-1 if x <= 352 else 1)
                self.draw()
            elif self.roster() and 315 <= x <= 905:
                row = round((y - CRESCENDO_ROW_TOP) / CRESCENDO_ROW_STEP)
                if 0 <= row < 4 and abs(y - CRESCENDO_ROW_TOP - row * CRESCENDO_ROW_STEP) <= 22:
                    self.crescendo_index = row
                    self._choose_member()
                    self.draw()
            return None
        if self.active and self._sync_page():
            for index, (cx, cy) in enumerate(((610, 170), (752, 302))):
                if abs(x-cx) <= 42 and abs(y-cy) <= 42:
                    self.sync_index = index
                    self._choose_member()
                    self.draw()
                    return None
            return None
        if self.active and self.detail == 0:
            if not self.item_targeting and 315 <= x <= 590:
                row = (y - (ITEM_ROW_TOP - ITEM_ROW_HEIGHT//2)) // ITEM_ROW_HEIGHT
                index = self._item_list_start() + row
                if 0 <= row < VISIBLE_ITEM_ROWS and index < len(self.inventory()):
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
                if self.detail == 4 and x >= 745:
                    self._choose_field_leader()
                else:
                    self._choose_member()
                    self.draw()
            return None
        if not self.active:
            return None
        if self.detail is not None:
            self.back()
            return None
        if 42 <= x <= 274:
            index = round((y - MENU_ROW_TOP) / MENU_ROW_STEP)
            if 0 <= index < len(self.OPTIONS) and abs(y - (MENU_ROW_TOP + index * MENU_ROW_STEP)) <= 16:
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
        return max(0, min(self.equip_index - EQUIP_ROWS + 1, len(entries) - EQUIP_ROWS))

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
        """L1/R1 switches members or the current Status tab."""
        if not self.active or step not in (-1, 1):
            return
        if self.detail == 3:
            self.status_tab = "abilities" if step > 0 else "stats"
            self.feedback = ""
            self.draw()
            return
        if self.detail == CRESCENDO_PAGE:
            self._change_crescendo_member(step)
            self.draw()
            return
        if self.detail != 2:
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
        if direction in ("left", "right"):
            # Keyboard stand-in for L1/R1 while a gear list is open.
            if self.equip_focus != "items":
                self.held_direction = None
                self.repeating = False
                return
            if direction != self.held_direction:
                self.held_direction = direction
                self.repeat_at = now
                self.repeating = False
            if now >= self.repeat_at:
                self.change_equipment_member(-1 if direction == "left" else 1)
                self.repeat_at = now + (0.09 if self.repeating else 0.24)
                self.repeating = True
            return
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
        if 42 <= y <= 73:
            for step, center in zip((-1, 1), EQUIP_MEMBER_X):
                if abs(x - center) <= 32:
                    self.change_equipment_member(step)
                    return
        for index in range(len(SLOTS)):
            center = EQUIP_SLOT_TOP + index * EQUIP_SLOT_STEP
            if EQUIP_SLOT_X[0] <= x <= EQUIP_SLOT_X[1] and abs(y - center) <= 21:
                self.equip_slot = index
                self.equip_focus = "category"
                self._equip_activate()
                self.draw()
                return
        entries = self._equip_entries()
        start = self._equip_scroll(entries)
        if abs(x - EQUIP_SCROLL_X) <= 14:
            scroll_row = None
            if abs(y - EQUIP_ITEM_TOP) <= 11 and start > 0:
                scroll_row = start - 1
            elif abs(y - (EQUIP_ITEM_TOP + (EQUIP_ROWS - 1) * EQUIP_ITEM_STEP)) <= 11 and start + EQUIP_ROWS < len(entries):
                scroll_row = start + EQUIP_ROWS
            if scroll_row is not None:
                self.equip_focus = "items"
                self.equip_index = scroll_row
                self.feedback = ""
                self.draw()
                return
        row = round((y - EQUIP_ITEM_TOP) / EQUIP_ITEM_STEP)
        if (EQUIP_ITEM_X[0] <= x <= EQUIP_ITEM_X[1] and 0 <= row < EQUIP_ROWS
                and abs(y - (EQUIP_ITEM_TOP + row * EQUIP_ITEM_STEP)) <= 11 and start + row < len(entries)):
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
        for panel in ((28, 24, 932, 88), (28, 100, 480, 340), (492, 100, 932, 340),
                      (28, 351, 932, 463), (28, 474, 932, 527)):
            self._frame(*panel)

        def text(x, y, value, size=20, color="#f8f4e8", **kw):
            return c.create_text(x, y, text=value, fill=color, font=self.font(size), tags=tag, **kw)

        gold, blue, muted = "#ffe37e", "#8edce8", "#bdcce1"
        text(50, 55, "EQUIP", 27, gold, anchor="w")
        member = self._equip_member()
        if member is None:
            text(480, 240, "No party members available.", 24)
            return
        job = self._current_job(member)
        text(480, 55, member["name"].upper(), 26, gold)
        text(907, 55, f"LV {member.get('level', 1)}  ·  {job or 'Unbound'}" +
             ("  ·  Reserve" if not member.get("active", True) else ""), 18, muted, anchor="e")
        if len(self.roster()) > 1:
            for cx, label in zip(EQUIP_MEMBER_X, ("‹ L1", "R1 ›")):
                c.create_rectangle(cx-32, 42, cx+32, 72, fill="#303762", outline="#7785ae", tags=tag)
                text(cx, 57, label, 18)

        text(50, 124, "EQUIPPED", 19, blue, anchor="w")
        c.create_line(367, 149, 367, 320, fill="#585f94", tags=tag)
        sprite = self.party_sprite(member["name"], job)
        if sprite is not None:
            c.create_image(416, 226, image=sprite, tags=tag)
        for index, slot in enumerate(SLOTS):
            y = EQUIP_SLOT_TOP + index * EQUIP_SLOT_STEP
            chosen = index == self.equip_slot
            if chosen:
                left, right = EQUIP_SLOT_X
                c.create_rectangle(left, y-21, right, y+21, fill="#384480", outline="#727fb2", tags=tag)
                c.create_rectangle(left, y-21, left+3, y+21, fill=gold, outline="", tags=tag)
            equipped = item_for(worn_id(member, slot))
            box = draw_item_slot(c, 70, y, self._gear_photo(equipped), tag)
            if chosen:
                self._slot_box = box
            text(100, y-9, SLOT_LABELS[slot].upper(), 15, blue, anchor="w")
            text(100, y+8, self._short(equipped.name, 24) if equipped else "Empty", 19,
                 gold if chosen else muted if equipped is None else "#f8f4e8", anchor="w")

        slot = SLOTS[self.equip_slot]
        current = worn_id(member, slot)
        entries = self._equip_entries()
        self.equip_index = min(self.equip_index, len(entries) - 1)
        start = self._equip_scroll(entries)
        browsing = self.equip_focus == "items"
        selected = entries[self.equip_index] if browsing else None
        title = SLOT_LABELS[slot].upper() + "  /  INVENTORY"
        text(512, 124, title, 18, blue, anchor="w")
        text(886, 124, "FREE / OWNED", 15, blue, anchor="e")
        owned, roster = self.gear_inventory(), self.roster()
        for row, item_id in enumerate(entries[start:start+EQUIP_ROWS]):
            y = EQUIP_ITEM_TOP + row * EQUIP_ITEM_STEP
            active = browsing and start + row == self.equip_index
            item = item_for(item_id)
            equipped_here = item_id is not None and item_id == current
            label = "Remove equipment" if item is None else self._short(item.name, 24) + (" [E]" if equipped_here else "")
            if active:
                left, right = EQUIP_ITEM_X
                c.create_rectangle(left, y-11, right, y+11, fill="#384480", outline="", tags=tag)
                text(518, y, "▶", 14, gold, anchor="w")
            text(541, y, label, 17, gold if active else "#f8f4e8", anchor="w")
            if item is not None:
                free = available_count(owned, roster, item_id)
                value = f"{free}/{owned[item_id]}"
                color = muted if free or equipped_here else "#94a1c0"
                if not can_wear(member, item):
                    value, color = "CANNOT", "#e9a7a7"
                text(874, y, value, 16, color, anchor="e")
        if start:
            text(EQUIP_SCROLL_X, EQUIP_ITEM_TOP, "▲", 16, blue)
        if start + EQUIP_ROWS < len(entries):
            text(EQUIP_SCROLL_X, EQUIP_ITEM_TOP + (EQUIP_ROWS - 1) * EQUIP_ITEM_STEP, "▼", 16, blue)
        c.create_line(510, 290, 914, 290, fill="#585f94", tags=tag)
        item = item_for(selected)
        preview = browsing
        if not browsing:
            description = "Select a slot to browse its gear."
        elif item is None:
            description = "Remove the item in this slot." if current else "This slot is empty."
        elif not can_wear(member, item):
            description = f"{member['name']} cannot equip {item.name}."
            preview = False
        elif current != item.id and not available_count(owned, roster, item.id):
            description = "All copies are equipped by other party members."
            preview = False
        else:
            description = item.description or item.name
        if browsing and current is not None and selected == current:
            description = "Equipped. " + description
        description_item = text(513, 297, description, 16, muted, anchor="nw", width=396)
        bottom = getattr(c, "_value", lambda value: value)(329)
        # Fit long descriptions with the actual scaled font.
        while len(description) > 4 and c.bbox(description_item)[3] > bottom:
            plain = description.removesuffix("...")
            description = plain[:-4].rstrip() + "..."
            c.itemconfigure(description_item, text=description)

        text(50, 375, "STAT PREVIEW" if preview and selected != current else "STATS", 19, blue, anchor="w")
        for index, (stat, label) in enumerate(STAT_LABELS):
            x, y = 50 + (index % 5) * 174, 412 + (index // 5) * 27
            before = stat_value(member, stat)
            after = preview_value(member, slot, selected, stat) if preview else before
            text(x, y, label.upper(), 16, muted, anchor="w")
            value = str(before) if before == after else f"{before} > {after}"
            color = "#8fe8ae" if after > before else "#ffaaaa" if after < before else "#f8f4e8"
            text(x+151, y, value, 17, color, anchor="e")
        self.glint.play(self._slot_box)
        instruction = "Select an item to equip or remove." if browsing else "Select an equipment slot."
        text(50, 491, self._short(self.feedback, 90) if self.feedback else instruction,
             16, gold if self.feedback else "#f8f4e8", anchor="w")
        text(50, 513, "UP/DOWN MOVE   L1/R1: CHANGE MEMBER   ENTER/CROSS SELECT   ESC/CIRCLE BACK",
             14, blue, anchor="w")

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
            y = MENU_ROW_TOP + index * MENU_ROW_STEP
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
        elif self.detail == CRESCENDO_PAGE:
            self._draw_crescendo()
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
                if self.detail == 4:
                    leader = member["name"] == self.field_leader()
                    value = "Leader" if leader else "Active" if member.get("active", True) else "Reserve"
                    if not leader and member.get("active", True) and member["hp"] > 0:
                        c.create_text(892, 170+48*row, text="SET LEADER", anchor="e",
                                      fill="#9adbe8", font=self.font(17), tags=tag)
                else:
                    value = member.get("job", "Unbound")
                c.create_text(320, 170+48*row, anchor="w", text=("▶  " if selected else "   ") + member["name"] + "    " + value,
                              fill="#ffe37e" if selected else "#ffffff", font=self.font(25), tags=tag)
            help_text = ("Right sets the field leader. Confirm toggles Active or Reserve."
                         if self.detail == 4 else "Confirm to change this member's path.")
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

    def _draw_crescendo(self):
        roster = self.roster()
        if not roster:
            return
        member = roster[self.member_index]
        equipped = equipped_crescendo(member)
        c, tag = self.canvas, self.TAG

        def text(x, y, value, color="#f4f5f3", size=20, **options):
            c.create_text(x, y, text=value, fill=color, font=self.font(size), tags=tag, **options)

        text(315, 91, "CRESCENDO", "#ffe37e", 28, anchor="w")
        text(900, 91, f"{charge(member)} / {MAX_CHARGE}", "#ffe37e", anchor="e")
        text(333, 130, "◀", "#9adbe8")
        text(887, 130, "▶", "#9adbe8")
        text(610, 130, f"{member['name']}  ·  {current_job(member) or 'Unbound'}")
        for i, move in enumerate(choices_for(member)):
            y = CRESCENDO_ROW_TOP + i * CRESCENDO_ROW_STEP
            selected = self.crescendo_index == i
            if selected:
                c.create_rectangle(313, y-16, 906, y+31, fill="#3d428b", outline="#7883bf", tags=tag)
            text(328, y, ("▶  " if selected else "    ") + move.name,
                 "#ffe37e" if selected else "#f4f5f3", anchor="w")
            text(349, y+19, move.description, "#c5d4ec", 16, anchor="w")
            if move == equipped:
                text(889, y, "EQUIPPED", "#80eaf5", 14, anchor="e")
            elif not is_unlocked(member, move):
                text(889, y, "LOCKED", "#9aa6bf", 14, anchor="e")
        hint = "Full meter unlocks your move under Abilities in battle." if equipped else "Crescendos are awaiting design."
        text(328, 406, self.feedback or hint,
             "#ffe37e" if self.feedback else "#9adbe8", 18, anchor="w")
        text(328, 430, "LEFT/RIGHT OR L1/R1 CHANGE MEMBER", "#c5d4ec", 15, anchor="w")

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

    def _item_list_start(self):
        return max(0, self.item_index - VISIBLE_ITEM_ROWS + 1)

    def _draw_items_or_status(self):
        c, tag = self.canvas, self.TAG
        members = self.roster()
        member = members[self.member_index]
        heading = "ITEMS" if self.detail == 0 else "STATUS"
        c.create_text(315, 96, text=heading, anchor="w", fill="#ffe37e", font=self.font(30, True), tags=tag)
        if self.detail == 0:
            items = list(self.inventory().items())
            self._slot_boxes = []
            self._slot_box = None
            first = self._item_list_start()
            for row, (name, count) in enumerate(items[first:first+VISIBLE_ITEM_ROWS]):
                i = first + row
                y = ITEM_ROW_TOP + row * ITEM_ROW_HEIGHT
                box = draw_item_slot(c, 348, y, self._supply_photo(name), tag)
                self._slot_boxes.append((i, box))
                if i == self.item_index:
                    self._slot_box = box
                marker = "▶ " if i == self.item_index and not self.item_targeting else "   "
                c.create_text(384, y, text=marker + f"{name}  x{count}", anchor="w", fill="#ffffff", font=self.font(23), tags=tag)
            hovered = next((box for index, box in self._slot_boxes if index == self.hover_index), None)
            if hovered is not None:
                self.glint.play(hovered)
            elif self._slot_box is not None:
                self.glint.play(self._slot_box)
            else:
                self.glint.stop()
            if self.item_targeting:
                start = max(0, self.member_index-3)
                for row, target in enumerate(members[start:start+4]):
                    selected = start+row == self.member_index
                    c.create_text(600, 150+row*38, text=("▶ " if selected else "   ") + f"{target['name']} {target['hp']}/{stat_value(target, 'max_hp')}", anchor="w", fill="#ffe37e" if selected else "#ffffff", font=self.font(20), tags=tag)
            hint = "Select an item." if not self.item_targeting else "UP/DOWN target · CONFIRM use · BACK items"
        elif self.status_tab == "abilities":
            self.glint.stop()
            self._draw_status_abilities(member)
            hint = "L1 STATS · R1 ABILITIES · UP/DOWN member"
        else:
            self.glint.stop()
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
            ailments=", ".join(name.title() for name in member.get("ailments",{}))
            c.create_text(320, 380, text=f"SYNC  {job}  |  {ailments or 'Healthy'}", anchor="w", fill="#80eaf5", font=self.font(16), tags=tag)
            c.create_text(700, 96, text="STATS", anchor="e", fill="#ffe37e", font=self.font(16), tags=tag)
            c.create_text(780, 96, text="ABILITIES", anchor="w", fill="#9adbe8", font=self.font(16), tags=tag)
            hint = "L1/R1 switch tab · UP/DOWN member · BACK return"
        c.create_text(320, 399, text=self.feedback or hint, anchor="w", width=570, fill="#9adbe8", font=self.font(21), tags=tag)

    def _on_motion(self, event):
        if not self.active or self.detail != 0:
            return
        for index, box in self._slot_boxes:
            x1, y1, x2, y2 = box
            if x1 <= event.x <= x2 and y1 <= event.y <= y2:
                self.hover_index = index
                self.glint.play(box)
                return
        self.hover_index = None
        if self._slot_box is not None:
            self.glint.play(self._slot_box)

    def _fit_photo(self, path):
        key = str(path)
        if key not in self._icons:
            image = tk.PhotoImage(master=self.canvas, file=key)
            factor = max(image.width(), image.height()) // 32
            if factor > 1:
                image = image.subsample(factor)
            self._icons[key] = image
        return self._icons[key]

    def _gear_photo(self, item):
        path = gear_icon(item)
        return self._fit_photo(path) if path else None

    def _supply_photo(self, name):
        path = supply_icon(name)
        return self._fit_photo(path) if path else None

    def _ability_photo(self, ability, member):
        variant = lesson_variant(ability, member)
        if variant is None:
            return None
        return self._fx_icon(variant.frames)

    def _fx_icon(self, frames, size=32):
        """Build a slot icon from an FX strip: its fullest frame, cropped to the art.

        FX frames are 128 px canvases with thin 1 px line art in the middle, so the
        old middle-frame subsample left a speck. Falls back to that if pygame can't.
        """
        key = ("fx", tuple(map(str, frames)))
        if key in self._icons:
            return self._icons[key]
        try:
            import base64
            import io
            import pygame
            surfaces = [pygame.image.load(str(path)) for path in frames]
            frame = max(surfaces, key=lambda surface: pygame.mask.from_surface(surface).count())
            box = frame.get_bounding_rect()
            side = max(box.width, box.height) + 2
            crop = pygame.Surface((side, side), pygame.SRCALPHA)
            crop.blit(frame, ((side - box.width) // 2 - box.x, (side - box.height) // 2 - box.y))
            if side > size:
                icon = pygame.transform.smoothscale(crop, (size, size))
                shrunk = icon.copy()
                for _ in range(2):  # downscaling thins the line art; stack it back to full strength
                    icon.blit(shrunk, (0, 0))
            else:
                factor = max(1, size // side)
                icon = pygame.transform.scale(crop, (side * factor, side * factor))
            data = io.BytesIO()
            pygame.image.save(icon, data, "icon.png")
            image = tk.PhotoImage(master=self.canvas, data=base64.b64encode(data.getvalue()).decode())
        except Exception:
            return self._fit_photo(frames[len(frames) // 2])
        self._icons[key] = image
        return image

    def _draw_status_abilities(self, member):
        c, tag = self.canvas, self.TAG
        job = self._current_job(member) or "Unbound"
        stone = STONE_NAMES.get(member.get("attuned_stone"), "Unattuned")
        c.create_text(700, 96, text="STATS", anchor="e", fill="#9adbe8", font=self.font(16), tags=tag)
        c.create_text(780, 96, text="ABILITIES", anchor="w", fill="#ffe37e", font=self.font(16), tags=tag)
        c.create_text(320, 140, text=f"{member['name']}   {job}   STONE {stone}", anchor="w",
                      fill="#ffffff", font=self.font(18), tags=tag)
        known = {ability.id for ability in learned_abilities(member)}
        rows = [lesson for lesson in lessons_for(member) if lesson.id in known]
        if not rows:
            c.create_text(320, 190, text="Open Tome to research abilities.", anchor="w", fill="#ffffff", font=self.font(18), tags=tag)
            return
        for index, ability in enumerate(rows[:4]):
            y = 186 + index * 46
            image = self._ability_photo(ability, member)
            draw_item_slot(c, 348, y, image, tag)
            c.create_text(384, y, text=ability.name, anchor="w",
                          fill="#ffffff", font=self.font(18), tags=tag)
        c.create_text(320, 380, text=rows[0].description, anchor="w", width=400,
                      fill="#c5d8e4", font=self.font(16), tags=tag)
