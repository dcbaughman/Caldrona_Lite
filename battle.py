"""Step encounters and a small, strictly turn-based cavern battle scene."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import random
import tkinter as tk

# Tune encounters here. Only successful tile moves call EncounterMeter.step().
ENCOUNTER_CHANCE = 0.08
SAFE_STEPS = 12
MAX_HP = 520
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
    mp: int = 0
    strength: int = 10
    defense: int = 0
    magic: int = 1
    magic_defense: int = 1
    agility: int = 10
    luck: int = 15
    evasion: int = 0
    accuracy: int = 0


ENEMIES = (
    Enemy("Ivory Spider", "spider.png", 110, (30, 45), 1, 8, "bites", 12, 11, 1, 1, 1, 10, 15, 7, 0),
    Enemy("Echo Bat", "bat.png", 95, (25, 38), 1, 6, "swoops", 15, 9, 1, 1, 1, 11, 15, 10, 0),
    Enemy("Rock Crawler", "crawler.png", 125, (40, 55), 1, 12, "rams", 10, 13, 1, 1, 120, 10, 15, 5, 0),
)


SHALEHORN = Enemy("Shalehorn", "shalehorn.png", 650, (120, 160), 8, 32, "charges", strength=22, defense=8)
JOBS = ("Seer", "Cutpurse", "Saint")


class BattleModel:
    """No clock advances a turn: a command, then one enemy reply."""
    def __init__(self, enemy, hp=MAX_HP, potions=MAX_POTIONS, rng=None, level=1, xp=0, party=None):
        self.enemies = list(enemy) if isinstance(enemy, (list, tuple)) else [enemy]
        self.health = [foe.hp for foe in self.enemies]
        self.target = 0
        self.damage = 0
        self.hp = hp
        self.party = party if party is not None else [{"name": "Retri", "hp": hp, "max_hp": MAX_HP + (level-1)*50}]
        self.actor = next((i for i, member in enumerate(self.party) if member["hp"] > 0), 0)
        self.defender = 0
        self.potions = potions
        self.level, self.xp = level, xp
        self.max_hp = MAX_HP + (level - 1) * 50
        self.gold_reward = sum(foe.gold for foe in self.enemies)
        self.xp_reward = self.gold_reward * 2
        if any(p.get("job") == "Cutpurse" for p in self.party):
            self.gold_reward += len(self.enemies) * 2
        self.rng = rng if rng is not None else random.Random()
        self.outcome = None
        self.pending_reply = False
        self.guarded = set()
        self.hits = {}
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
            armor = 0 if self.party[self.actor].get("job") == "Seer" else self.enemy.armor
            strength = self.party[self.actor].get("strength", 15)
            damage = max(1, self.rng.randint(strength*3, strength*4) + self.level - 1 - armor*2)
            self.damage = damage
            self.enemy_hp = max(0, self.enemy_hp - damage)
            self.message = f"{self.party[self.actor]['name']} strikes for {damage}!"
            if not any(self.health):
                self.outcome = "victory"
        elif action == "Guard":
            self.guarded.add(self.actor)
            member = self.party[self.actor]
            if member.get("job") in ("Saint", "Saint Warrior"):
                member["hp"] = min(member["max_hp"], member["hp"] + 3)
                self.hp = self.party[0]["hp"]
            self.message = f"{member['name']} braces for the next blow."
        elif action == "Potion":
            if not self.potions:
                self.message = "No potions left. Choose another action."
                return False
            member = self.party[self.actor]
            if member["hp"] >= member["max_hp"]:
                self.message = "Already at full health."
                return False
            healed = min(250, member["max_hp"] - member["hp"])
            member["hp"] += healed
            self.hp = self.party[0]["hp"]
            self.potions -= 1
            self.message = f"{member['name']} recovers {healed} HP."
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

    def next_party_turn(self):
        if not self.pending_reply or self.outcome:
            return False
        for index in range(self.actor + 1, len(self.party)):
            if self.party[index]["hp"] > 0:
                self.actor = index
                self.pending_reply = False
                self.message = f"{self.party[index]['name']}: choose a command."
                return True
        return False

    def reply(self):
        if not self.pending_reply or self.outcome:
            return
        self.pending_reply = False
        self.attacker = next(i for i, hp in enumerate(self.health) if hp)
        foe = self.enemies[self.attacker]
        damage = self.rng.randint(*foe.attack)
        living = [i for i, member in enumerate(self.party) if member["hp"] > 0]
        self.defender = living[self.rng.randrange(len(living))] if len(living) > 1 else living[0]
        if self.defender in self.guarded:
            damage = max(1, damage // 2)
        self.guarded.clear()
        self.hits = {self.defender: damage}
        member = self.party[self.defender]
        damage = max(1, damage - member.get("defense", 0))
        self.hits[self.defender] = damage
        member["hp"] = max(0, member["hp"] - damage)
        self.hp = self.party[0]["hp"]
        self.damage = damage
        self.effect = "enemy"
        self.message = f"{foe.name} hits {member['name']} for {damage}!"
        if not any(member["hp"] for member in self.party):
            self.outcome = "defeat"
        else:
            self.actor = next(i for i, member in enumerate(self.party) if member["hp"] > 0)


class ShalehornBattle(BattleModel):
    """One telegraphed move per party round."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.move_index = 0
        self.mark = self.actor
        self.exposed = False
        self.buried = False

    def tell(self):
        return (f"Stonebreaker Charge aims at {self.party[self.mark]['name']}. Guard!",
                "Its flank is exposed! Tremor incoming." if self.exposed else "Its foreclaws rise. Tremor incoming.",
                "Shalehorn digs at the shale.", "Underground! Brace for its return.")[self.move_index]

    def command(self, action):
        if action == "Attack" and self.buried and not self.pending_reply and not self.outcome:
            self.damage = 0
            self.effect = "miss"
            self.pending_reply = True
            self.message = "Your strike finds only loose shale."
            return True
        accepted = super().command(action)
        if accepted and action == "Attack" and self.exposed:
            self.enemy_hp = max(0, self.enemy_hp - self.damage)
            self.damage *= 2
            self.message = f"Fractured armor! {self.damage} damage."
            if self.enemy_hp == 0:
                self.outcome, self.pending_reply = "victory", False
        return accepted

    def reply(self):
        if not self.pending_reply or self.outcome:
            return
        self.pending_reply = False
        self.attacker = 0
        living = [i for i, p in enumerate(self.party) if p["hp"]]
        self.exposed = False
        if self.move_index == 0:
            self.exposed = self.mark in self.guarded
            self.hits = {self.mark: 0 if self.exposed else 160}
            self.message = ("Charge misses! Its flank cracks against the wall." if self.exposed
                            else "Stonebreaker Charge!")
        elif self.move_index == 1:
            self.hits = {i: 40 if i in self.guarded else 80 for i in living}
            self.message = "Quarry Tremor!"
        elif self.move_index == 2:
            self.buried = True
            self.hits = {}
            self.message = "Shalehorn burrows beneath the floor."
        else:
            self.buried = False
            target = self.rng.choice(living)
            self.hits = {target: 45 if target in self.guarded else 90}
            self.message = "Shalehorn erupts from the stone!"
        self.effect = "tremor" if self.move_index == 1 else "enemy"
        self.defender = next(iter(self.hits), living[0])
        self.damage = self.hits.get(self.defender, 0)
        for i, amount in self.hits.items():
            self.party[i]["hp"] = max(0, self.party[i]["hp"] - amount)
        self.hp = self.party[0]["hp"]
        self.guarded.clear()
        living = [i for i in living if self.party[i]["hp"]]
        if not living:
            self.outcome = "defeat"
            return
        self.actor = living[0]
        self.move_index = (self.move_index + 1) % 4
        if self.move_index == 0:
            self.mark = self.rng.choice(living)


class BattleScene:
    TAG = "battle"
    DYNAMIC = "battle_dynamic"
    COMMANDS = ("Attack", "Guard", "Items", "Flee")

    def __init__(self, canvas, font, assets: Path, portrait=None):
        self.canvas, self.font = canvas, font
        self.portrait = portrait
        self.member_portrait = None
        self.reward_portraits = {}
        self.enemies = {
            e.sprite: tk.PhotoImage(master=canvas, file=str(assets / "battle" / e.sprite)).zoom(2)
            for e in (*ENEMIES, SHALEHORN)
        }
        self.hero = tk.PhotoImage(master=canvas, file=str(assets / "battle" / "retri-v2.png")).zoom(2)
        self.fainted = tk.PhotoImage(master=canvas, file=str(assets / "battle" / "retri-fainted-v2.png")).zoom(2)
        self.temur = tk.PhotoImage(master=canvas, file=str(assets / "battle" / "temur-v2.png")).zoom(2)
        self.backdrop = tk.PhotoImage(master=canvas, file=str(assets / "battle" / "crystal-quarry.png"))
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
        self.party_positions = [(738 + 36*i, 255 - 66*i) for i in range(len(model.party))]
        sprites = {"Retri": self.hero, "Temur": self.temur}
        self.party_sprites = [sprites.get(p["name"]) for p in model.party]
        self.party_items = []
        for (x, y), image, member in zip(self.party_positions, self.party_sprites, model.party):
            if image is None:
                item = c.create_text(x, y, text=member["name"], fill="#ffffff", font=self.font(20), tags=self.TAG)
            else:
                item = c.create_image(x, y, image=image, tags=self.TAG)
            self.party_items.append(item)
        self.hero_item = self.party_items[0]
        self._frame(18, 320, 942, 382)
        self._frame(18, 394, 296, 526)
        self._frame(308, 394, 516, 526)
        self._frame(526, 394, 942, 526)
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
        if isinstance(m, ShalehornBattle) and self.phase in ("command", "target"):
            c.create_text(480, 65, text=m.tell(), fill="#ffe37e", font=self.font(24, True), tags=tags)
        commands = (f"Potion x{m.potions}", "Back") if self.item_menu else self.COMMANDS
        for i, command in enumerate(commands):
            x, y = 52 + (i % 2) * 126, 435 + (i // 2) * 43
            text = ("> " if i == self.selection and self.phase == "command" else "  ") + command
            c.create_text(x-16, y, text=text, anchor="w", font=self.font(22),
                          fill="#ffe37e" if i == self.selection else "#ffffff", tags=tags)
        c.create_text(326, 425, text="ENEMY", anchor="w", fill="#80eaf5", font=self.font(17), tags=tags)
        c.create_text(326, 458, text=m.enemy.name, anchor="w", width=172,
                      fill="#ffffff", font=self.font(18), tags=tags)
        c.create_text(326, 494, text=f"HP {m.enemy_hp}/{m.enemy.hp}", anchor="w",
                      fill="#ffffff", font=self.font(17), tags=tags)
        for i, member in enumerate(m.party):
            y = 421 + i * 34
            active = i == m.actor and self.phase in ("command", "target")
            color = "#ffe37e" if active else "#ffffff"
            name = ("> " if active else "  ") + member["name"]
            c.create_text(545, y, text=name, anchor="w", fill=color, font=self.font(20), tags=tags)
            c.create_text(912, y, text=f"HP {member['hp']} / {member['max_hp']}",
                          anchor="e", fill=color, font=self.font(20), tags=tags)

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
                self.canvas.coords(self.level_item, 712, 65 + int((now-self.result_at)*4) % 3)
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
        if attacking:
            c.create_text(ex, ey-50-int(elapsed*25), text=str(self.model.damage), fill="#ffe37e",
                          font=self.font(28, True), tags=(self.TAG, "damage_number"))
        if enemy_attacking:
            for i, loss in self.model.hits.items():
                x, y = self.party_positions[i]
                c.create_text(x, y-38-int(elapsed*25), text=str(loss), fill="#ffe37e",
                              font=self.font(28, True), tags=(self.TAG, "damage_number"))
        i = self.model.defender if enemy_attacking else self.model.actor
        active_item = self.party_items[i]
        ax, ay = self.party_positions[i]
        if enemy_attacking and self.model.effect == "tremor":
            ay += 3 if int(elapsed*22)%2 else -3
        c.coords(active_item, ax - (offset if attacking else 0), ay)
        c.coords(self.enemy_item, ex + (offset if enemy_attacking else 0), ey)
        c.itemconfigure(self.enemy_item, state="hidden" if getattr(self.model, "buried", False) or (attacking and int(elapsed * 16) % 2) else "normal")
        c.itemconfigure(active_item, state="hidden" if enemy_attacking and int(elapsed * 16) % 2 else "normal")
        if elapsed < 0.65:
            return
        c.coords(active_item, *self.party_positions[i])
        c.delete("damage_number")
        c.coords(self.enemy_item, ex, ey)
        c.itemconfigure(active_item, state="normal")
        c.itemconfigure(self.enemy_item, state="normal" if self.model.health[index] and not getattr(self.model, "buried", False) else "hidden")
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
            if self.model.outcome == "defeat":
                for member, item in zip(self.model.party, self.party_items):
                    if member["name"] == "Retri":
                        c.itemconfigure(item, image=self.fainted)
                    else:
                        c.move(item, 0, 12)
        elif self.phase == "hero_action":
            if self.model.next_party_turn():
                self.phase = "command"
                self.held = None
            else:
                self.model.reply()
                self.phase = "enemy_action"
                self.phase_at = now
        else:
            self.phase = "command"
            self.held = None
            self.model.message = f"What will {self.model.party[self.model.actor]['name']} do?"
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
        row_height = 180 // len(m.party)
        for i, member in enumerate(m.party):
            y = 243 + i * row_height
            name = member["name"]
            if name not in self.reward_portraits:
                portrait = self.member_portrait(name) if self.member_portrait else None
                if portrait is not None:
                    self.reward_portraits[name] = portrait.subsample(2)
            image = self.reward_portraits.get(name, self.party_sprites[i])
            if image is not None:
                c.create_image(110, y + 10, image=image, tags=self.TAG)
            text(190, y, member["name"].upper(), 26, "#ffe48a")
            text(405, y, f"LV {level}", 25)
            text(565, y, f"EXP {xp}/{xp_threshold(level)}", 23)
            text(565, y+26, f"NEXT LV  {xp_threshold(level)-xp}", 17, "#80eaf5")
        if level > m.level:
            self.level_item = text(712, 65, "LEVEL UP!", 32, "#ffe48a")
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
