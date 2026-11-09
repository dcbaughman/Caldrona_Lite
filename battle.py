"""Step encounters and a small, strictly turn-based cavern battle scene."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import random
import tkinter as tk

# Tune encounters here. Only successful tile moves call EncounterMeter.step().
ENCOUNTER_CHANCE = 0.08
SAFE_STEPS = 12
MAX_HP = 60
MAX_POTIONS = 3
TRANSITION_SECONDS = 0.45


def xp_threshold(level):
    return 30 * level


def gain_xp(level, xp, amount):
    xp += amount
    while xp >= xp_threshold(level):
        xp -= xp_threshold(level)
        level += 1
    return level, xp


class EncounterMeter:
    def __init__(self, rng=None, chance=ENCOUNTER_CHANCE, safe_steps=SAFE_STEPS):
        self.rng = rng if rng is not None else random.Random()
        self.chance = chance
        self.safe_steps = safe_steps
        self.reset()

    def reset(self):
        self.steps_left = self.safe_steps

    def step(self):
        if self.steps_left:
            self.steps_left -= 1
            return False
        if self.rng.random() < self.chance:
            self.reset()
            return True
        return False


@dataclass(frozen=True)
class Enemy:
    name: str
    sprite: str
    hp: int
    attack: tuple[int, int]
    armor: int
    gold: int
    move: str


ENEMIES = (
    Enemy("Ivory Spider", "spider.png", 30, (4, 7), 0, 8, "bites"),
    Enemy("Echo Bat", "bat.png", 24, (3, 6), 0, 6, "swoops"),
    Enemy("Rock Crawler", "crawler.png", 36, (4, 8), 2, 12, "rams"),
)


class BattleModel:
    """No clock advances a turn: a command, then one enemy reply."""
    def __init__(self, enemy, hp=MAX_HP, potions=MAX_POTIONS, rng=None, level=1, xp=0):
        self.enemies = list(enemy) if isinstance(enemy, (list, tuple)) else [enemy]
        self.health = [foe.hp for foe in self.enemies]
        self.target = 0
        self.damage = 0
        self.hp = hp
        self.potions = potions
        self.level, self.xp = level, xp
        self.max_hp = MAX_HP + (level - 1) * 5
        self.gold_reward = sum(foe.gold for foe in self.enemies)
        self.xp_reward = self.gold_reward * 2
        self.rng = rng if rng is not None else random.Random()
        self.outcome = None
        self.pending_reply = False
        self.guarding = False
        self.effect = ""
        self.message = "Enemies approach!" if len(self.enemies) > 1 else f"{self.enemy.name} approaches!"

    @property
    def enemy(self):
        return self.enemies[self.target]

    @property
    def enemy_hp(self):
        return self.health[self.target]

    @enemy_hp.setter
    def enemy_hp(self, value):
        self.health[self.target] = value

    def command(self, action):
        if self.outcome or self.pending_reply:
            return False
        self.effect = action
        if action == "Attack":
            damage = max(1, self.rng.randint(10, 14) + self.level - 1 - self.enemy.armor)
            self.damage = damage
            self.enemy_hp = max(0, self.enemy_hp - damage)
            self.message = f"Retri strikes for {damage}!"
            if not any(self.health):
                self.outcome = "victory"
        elif action == "Guard":
            self.guarding = True
            self.message = "Retri braces for the next blow."
        elif action == "Potion":
            if not self.potions:
                self.message = "No potions left. Choose another action."
                return False
            if self.hp >= self.max_hp:
                self.message = "Retri is already at full health."
                return False
            healed = min(25, self.max_hp - self.hp)
            self.hp += healed
            self.potions -= 1
            self.message = f"Retri recovers {healed} HP."
        elif action == "Flee":
            if self.rng.random() < 0.75:
                self.outcome = "fled"
                self.message = "Retri slips away!"
            else:
                self.message = "The way out is blocked!"
        else:
            return False
        self.pending_reply = self.outcome is None
        return True

    def reply(self):
        if not self.pending_reply or self.outcome:
            return
        self.pending_reply = False
        self.attacker = next(i for i, hp in enumerate(self.health) if hp)
        foe = self.enemies[self.attacker]
        damage = self.rng.randint(*foe.attack)
        if self.guarding:
            damage = max(1, damage // 2)
        self.guarding = False
        self.hp = max(0, self.hp - damage)
        self.damage = damage
        self.effect = "enemy"
        self.message = f"{foe.name} {foe.move} for {damage}!"
        if self.hp == 0:
            self.outcome = "defeat"


class BattleScene:
    TAG = "battle"
    DYNAMIC = "battle_dynamic"
    COMMANDS = ("Attack", "Guard", "Items", "Flee")

    def __init__(self, canvas, font, assets: Path, portrait=None):
        self.canvas, self.font = canvas, font
        self.portrait = portrait
        self.enemies = {
            e.sprite: tk.PhotoImage(master=canvas, file=str(assets / "battle" / e.sprite)).zoom(2)
            for e in ENEMIES
        }
        self.hero = tk.PhotoImage(master=canvas, file=str(assets / "battle" / "retri.png")).zoom(2)
        tile = tk.PhotoImage(master=canvas, file=str(assets / "wall_brick.png")).subsample(2).zoom(3)
        self.backdrop = tk.PhotoImage(master=canvas, width=960, height=96)
        for y in range(0, 96, tile.height()):
            for x in range(0, 960, tile.width()):
                self.backdrop.tk.call(self.backdrop, "copy", tile, "-to", x, y)
        self.model = None

    def start(self, model, now):
        self.model = model
        self.selection = 0
        self.item_menu = False
        self.phase = "command"
        self.held = None
        self.repeat_at = 0.0
        self.phase_at = now
        c = self.canvas
        c.create_rectangle(0, 0, 960, 540, fill="#08090c", outline="", tags=self.TAG)
        c.create_image(0, 0, image=self.backdrop, anchor="nw", tags=self.TAG)
        count = len(model.enemies)
        self.enemy_positions = [(270, 190 + (i - (count - 1) / 2) * 80)
                                for i in range(count)]
        self.enemy_items = [c.create_image(x, y, image=self.enemies[foe.sprite], tags=self.TAG)
                            for (x, y), foe in zip(self.enemy_positions, model.enemies)]
        self.enemy_item = self.enemy_items[0]
        self.hero_item = c.create_image(738, 255, image=self.hero, tags=self.TAG)
        self._frame(18, 320, 942, 382)
        self._frame(18, 394, 296, 526)
        self._frame(308, 394, 942, 526)
        self.draw_status()

    def _frame(self, x1, y1, x2, y2):
        c = self.canvas
        c.create_rectangle(x1, y1, x2, y2, fill="#727980", outline="", tags=self.TAG)
        c.create_rectangle(x1+3, y1+3, x2-3, y2-3, fill="#f2f1df", outline="", tags=self.TAG)
        c.create_rectangle(x1+8, y1+8, x2-8, y2-8, fill="#242181", outline="", tags=self.TAG)

    def draw_status(self):
        c, m = self.canvas, self.model
        c.delete(self.DYNAMIC)
        tags = (self.TAG, self.DYNAMIC)
        if self.phase == "target":
            x, y = self.enemy_positions[m.target]
            c.create_text(x-48, y, text="▶", fill="#ffe37e", font=self.font(24, True), tags=tags)
        c.create_text(40, 350, text=m.message, anchor="w", fill="#ffffff", font=self.font(23), tags=tags)
        commands = (f"Potion x{m.potions}", "Back") if self.item_menu else self.COMMANDS
        for i, command in enumerate(commands):
            x, y = 52 + (i % 2) * 126, 435 + (i // 2) * 43
            text = ("> " if i == self.selection and self.phase == "command" else "  ") + command
            c.create_text(x-16, y, text=text, anchor="w", font=self.font(22),
                          fill="#ffe37e" if i == self.selection else "#ffffff", tags=tags)
        c.create_text(334, 429, text=f"RETRI LV {m.level}", anchor="w", fill="#ffe37e", font=self.font(24, True), tags=tags)
        c.create_text(590, 429, text=f"HP  {m.hp:2} / {m.max_hp}", anchor="w", fill="#ffffff", font=self.font(24), tags=tags)
        c.create_text(334, 474, text=f"XP {m.xp}/{xp_threshold(m.level)}", anchor="w", fill="#80eaf5", font=self.font(21), tags=tags)
        c.create_text(555, 474, text=f"FOE HP  {m.enemy_hp:2} / {m.enemy.hp}", anchor="w", fill="#ffffff", font=self.font(21), tags=tags)
        hint = "ENTER / CROSS" if self.phase == "result" else "CHOOSE A COMMAND"
        c.create_text(914, 504, text=hint, anchor="e", fill="#bec8e4", font=self.font(15), tags=tags)

    def navigate(self, direction, now):
        if self.phase == "target":
            if direction not in ("up", "down", "left", "right"):
                self.held = None
            elif direction != self.held or now >= self.repeat_at:
                self.held, self.repeat_at = direction, now + 0.22
                step = -1 if direction in ("left", "up") else 1
                for _ in self.model.enemies:
                    self.model.target = (self.model.target + step) % len(self.model.enemies)
                    if self.model.enemy_hp:
                        break
                self.draw_status()
            return
        if self.phase != "command":
            return
        if direction not in ("up", "down", "left", "right"):
            self.held = None
            return
        if direction != self.held:
            self.held = direction
            self.repeat_at = now
        if now >= self.repeat_at:
            step = {"up": -2, "down": 2, "left": -1, "right": 1}[direction]
            self.selection = (self.selection + (1 if self.item_menu else step)) % (2 if self.item_menu else 4)
            self.repeat_at = now + 0.22
            self.draw_status()

    def confirm(self, now):
        if self.phase == "result":
            return self.model.outcome
        if self.phase == "target":
            self.model.command("Attack")
            self.phase, self.phase_at = "hero_action", now
            self.draw_status()
            return None
        if self.phase == "command":
            if not self.item_menu and self.COMMANDS[self.selection] == "Attack":
                self.model.target = next(i for i, hp in enumerate(self.model.health) if hp)
                self.phase, self.held = "target", None
                self.model.message = "Choose a target."
                self.draw_status()
                return None
            if not self.item_menu and self.COMMANDS[self.selection] == "Items":
                self.item_menu, self.selection = True, 0
                self.draw_status()
                return None
            if self.item_menu and self.selection == 1:
                self.item_menu, self.selection = False, 2
                self.draw_status()
                return None
            action = "Potion" if self.item_menu else self.COMMANDS[self.selection]
            if self.model.command(action):
                self.item_menu, self.selection = False, 2 if action == "Potion" else self.selection
                self.phase = "hero_action"
                self.phase_at = now
            self.draw_status()
        return None

    def back(self):
        if self.phase == "target":
            self.phase = "command"
            self.draw_status()
            return
        if self.phase == "command":
            if self.item_menu:
                self.item_menu, self.selection = False, 2
            else:
                self.selection = 3
            self.draw_status()

    def click(self, x, y, now):
        if self.phase == "target":
            for i, (ex, ey) in enumerate(self.enemy_positions):
                if self.model.health[i] and abs(x-ex) < 60 and abs(y-ey) < 60:
                    self.model.target = i
                    return self.confirm(now)
            return None
        if self.phase == "result":
            return self.confirm(now)
        if self.phase == "command":
            for i in range(2 if self.item_menu else 4):
                if abs(x - (100 + i % 2 * 126)) < 60 and abs(y - (435 + i // 2 * 43)) < 19:
                    self.selection = i
                    return self.confirm(now)
        return None

    def update(self, now):
        if self.phase == "result" and self.model.outcome == "victory":
            if self.level_item is not None:
                colors = ("#ffe48a", "#ffffff", "#ffad49", "#fff6c0")
                self.canvas.itemconfigure(self.level_item, fill=colors[int((now-self.result_at)*5) % len(colors)])
                self.canvas.coords(self.level_item, 470, 231 + int((now-self.result_at)*4) % 3)
            return
        if self.phase not in ("hero_action", "enemy_action"):
            return
        elapsed = now - self.phase_at
        attacking = self.phase == "hero_action" and self.model.effect == "Attack"
        enemy_attacking = self.phase == "enemy_action"
        # Only coordinates/visibility change while animating; no per-frame art work.
        offset = int(18 * max(0, 1 - abs(elapsed - 0.18) / 0.18))
        c = self.canvas
        index = self.model.target if attacking else getattr(self.model, "attacker", self.model.target)
        self.enemy_item = self.enemy_items[index]
        ex, ey = self.enemy_positions[index]
        c.delete("damage_number")
        if attacking or enemy_attacking:
            c.create_text(738 if enemy_attacking else ex, (205 if enemy_attacking else ey-50)-int(elapsed*25),
                          text=str(self.model.damage), fill="#fff2a4", font=self.font(28, True),
                          tags=(self.TAG, "damage_number"))
        c.coords(self.hero_item, 738 - (offset if attacking else 0), 255)
        c.coords(self.enemy_item, ex + (offset if enemy_attacking else 0), ey)
        c.itemconfigure(self.enemy_item, state="hidden" if attacking and int(elapsed * 16) % 2 else "normal")
        c.itemconfigure(self.hero_item, state="hidden" if enemy_attacking and int(elapsed * 16) % 2 else "normal")
        if elapsed < 0.65:
            return
        c.coords(self.hero_item, 738, 255)
        c.delete("damage_number")
        c.coords(self.enemy_item, ex, ey)
        c.itemconfigure(self.hero_item, state="normal")
        c.itemconfigure(self.enemy_item, state="normal" if self.model.health[index] else "hidden")
        if self.model.outcome:
            self.phase = "result"
            self.model.message = {
                "victory": (f"Victory! {self.model.xp_reward} XP, {self.model.enemy.gold} gold."
                            + (f" Level {gain_xp(self.model.level, self.model.xp, self.model.xp_reward)[0]}!"
                               if gain_xp(self.model.level, self.model.xp, self.model.xp_reward)[0] > self.model.level else "")),
                "defeat": "Retri retreats to the entrance to recover.",
                "fled": "Escaped safely. Continue exploring.",
            }[self.model.outcome]
            if self.model.outcome == "victory":
                self._victory_screen(now)
                return
        elif self.phase == "hero_action":
            self.model.reply()
            self.phase = "enemy_action"
            self.phase_at = now
        else:
            self.phase = "command"
            self.held = None
            self.model.message = "What will Retri do?"
        self.draw_status()

    def _victory_screen(self, now):
        c, m = self.canvas, self.model
        level, xp = gain_xp(m.level, m.xp, m.xp_reward)
        self.result_at = now
        self.level_item = None
        c.delete(self.TAG)
        c.create_rectangle(0, 0, 960, 540, fill="#08090c", outline="", tags=self.TAG)
        self._frame(35, 28, 925, 106)
        self._frame(35, 120, 465, 195)
        self._frame(485, 120, 925, 195)
        self._frame(35, 210, 925, 430)
        self._frame(35, 447, 925, 520)
        def text(x, y, label, size=26, color="#ffffff", **kw):
            return c.create_text(x, y, text=label, anchor="w", fill=color,
                                 font=self.font(size), tags=self.TAG, **kw)
        text(65, 67, "BATTLE COMPLETE", 34, "#ffe48a")
        text(65, 157, f"EXP  +{m.xp_reward}", 29)
        text(515, 157, f"GOLD  +{m.gold_reward}", 29)
        image = self.portrait() if self.portrait else None
        if image:
            c.create_image(150, 320, image=image, tags=self.TAG)
        else:
            c.create_image(150, 320, image=self.hero, tags=self.TAG)
        text(270, 248, "RETRI", 30, "#ffe48a")
        text(270, 305, f"LEVEL  {level}", 28)
        text(270, 355, f"EXP  {xp} / {xp_threshold(level)}", 25)
        text(620, 305, f"NEXT LV  {xp_threshold(level)-xp}", 24, "#80eaf5")
        text(620, 355, "RECOVER HP / POTION", 20)
        if level > m.level:
            self.level_item = text(470, 231, "LEVEL UP!", 32, "#ffe48a")
        text(65, 483, "ENTER / CROSS TO CONTINUE", 25)

    def close(self):
        self.canvas.delete(self.TAG)


class BattleTransition:
    """A twelve-strip shutter, updated by the normal game tick."""
    TAG = "battle_transition"

    def __init__(self, canvas):
        self.canvas = canvas
        self.items = []

    def start(self, now):
        self.started = now
        self.canvas.delete(self.TAG)
        self.items = [self.canvas.create_rectangle(0, y*45, 0, (y+1)*45,
                      fill="#08090c", outline="", tags=self.TAG) for y in range(12)]

    def update(self, now):
        progress = min(1.0, (now - self.started) / TRANSITION_SECONDS)
        edge = int(960 * progress)
        for i, item in enumerate(self.items):
            left, right = (0, edge) if i % 2 == 0 else (960-edge, 960)
            self.canvas.coords(item, left, i*45, right, (i+1)*45)
        self.canvas.tag_raise(self.TAG)
        return progress

    def close(self):
        self.canvas.delete(self.TAG)
