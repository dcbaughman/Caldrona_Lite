"""Step encounters and a small, strictly turn-based cavern battle scene."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import random
import tkinter as tk
from stats import RETRI, RETRI_HP_PER_LEVEL, grow
from classes import JOBS, current_job
from items import failure_message, get_item, success_message, use_item

# Tune encounters here. Only successful tile moves call EncounterMeter.step().
ENCOUNTER_CHANCE = 0.08
SAFE_STEPS = 12
MAX_HP = RETRI["max_hp"]
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
    Enemy("Ivory Spider", "spider.png", 22, (5, 8), 1, 8, "bites", 4, 6, 1, 1, 1, 7, 6, 4, 5),
    Enemy("Echo Bat", "bat.png", 19, (4, 7), 0, 6, "swoops", 4, 5, 0, 1, 1, 9, 6, 5, 5),
    Enemy("Rock Crawler", "crawler.png", 25, (6, 9), 2, 12, "rams", 3, 7, 2, 1, 2, 5, 6, 2, 5),
)


SHALEHORN = Enemy("Shalehorn", "shalehorn.png", 150, (16, 22), 4, 32, "charges", strength=14, defense=4)


class BattleModel:
    """No clock advances a turn: a command, then one enemy reply."""
    def __init__(self, enemy, hp=MAX_HP, potions=MAX_POTIONS, rng=None, level=1, xp=0, party=None, inventory=None):
        self.enemies = list(enemy) if isinstance(enemy, (list, tuple)) else [enemy]
        self.health = [foe.hp for foe in self.enemies]
        self.target = 0
        self.damage = 0
        self.hp = hp
        self.party = party if party is not None else [{"name": "Retri", "hp": hp, "max_hp": MAX_HP + (level-1)*RETRI_HP_PER_LEVEL}]
        self.actor = next((i for i, member in enumerate(self.party) if member["hp"] > 0), 0)
        self.defender = 0
        self.potions = potions
        self.inventory = inventory if inventory is not None else {}
        self.level, self.xp = level, xp
        self.max_hp = MAX_HP + (level - 1) * RETRI_HP_PER_LEVEL
        self.gold_reward = sum(foe.gold for foe in self.enemies)
        self.xp_reward = self.gold_reward * 2
        if any(current_job(p) == "Sollers" for p in self.party):
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

    def command(self, action, target=None, item_id=None):
        if self.outcome or self.pending_reply:
            return False
        self.effect = action
        if action == "Attack":
            armor = 0 if current_job(self.party[self.actor]) == "Seer" else self.enemy.armor
            strength = self.party[self.actor].get("strength", RETRI["strength"] + self.party[self.actor].get("level", self.level) - 1)
            damage = max(1, self.rng.randint(max(1, strength-2), strength+2) - armor)
            self.damage = damage
            self.enemy_hp = max(0, self.enemy_hp - damage)
            self.message = f"{self.party[self.actor]['name']} strikes for {damage}!"
            if not any(self.health):
                self.outcome = "victory"
        elif action == "Guard":
            self.guarded.add(self.actor)
            member = self.party[self.actor]
            if current_job(member) == "Saint":
                member["hp"] = min(member["max_hp"], member["hp"] + 3)
                self.hp = self.party[0]["hp"]
            self.message = f"{member['name']} braces for the next blow."
        elif action == "Potion":
            if not self.potions:
                self.message = "No potions left. Choose another action."
                return False
            target = self.actor if target is None else target
            if not isinstance(target, int) or not 0 <= target < len(self.party):
                self.message = "Choose a party member."
                return False
            member = self.party[target]
            result = use_item("potion", member)
            if not result.ok:
                if result.reason == "fainted":
                    self.message = "A potion cannot revive a fainted member."
                elif result.reason == "full_hp":
                    self.message = f"{member['name']} is already at full health."
                else:
                    self.message = "Choose a party member."
                return False
            self.hp = self.party[0]["hp"]
            self.potions -= 1
            self.message = f"{member['name']} recovers {result.healed} HP."
        elif action == "Use":
            if item_id == "potion":
                return self.command("Potion", target=target)
            try:
                item = get_item(item_id) if item_id else None
            except KeyError:
                item = None
            count = self.inventory.get(item_id, 0) if item_id else 0
            if item is None or not item.effect or count <= 0:
                self.message = "No items left. Choose another action."
                return False
            target = self.actor if target is None else target
            if not isinstance(target, int) or not 0 <= target < len(self.party):
                self.message = "Choose a party member."
                return False
            member = self.party[target]
            result = use_item(item.id, member)
            if not result.ok:
                self.message = failure_message(result, item, member)
                return False
            self.inventory[item_id] = count - 1
            self.hp = self.party[0]["hp"]
            self.message = success_message(result, member, battle=True)
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

    def command(self, action, target=None, item_id=None):
        if action == "Attack" and self.buried and not self.pending_reply and not self.outcome:
            self.damage = 0
            self.effect = "miss"
            self.pending_reply = True
            self.message = "Your strike finds only loose shale."
            return True
        accepted = super().command(action, target=target, item_id=item_id)
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
            self.hits = {self.mark: 0 if self.exposed else 22}
            self.message = ("Charge misses! Its flank cracks against the wall." if self.exposed
                            else "Stonebreaker Charge!")
        elif self.move_index == 1:
            self.hits = {i: 5 if i in self.guarded else 10 for i in living}
            self.message = "Quarry Tremor!"
        elif self.move_index == 2:
            self.buried = True
            self.hits = {}
            self.message = "Shalehorn burrows beneath the floor."
        else:
            self.buried = False
            target = self.rng.choice(living)
            self.hits = {target: 6 if target in self.guarded else 12}
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
        self.temur_fainted = tk.PhotoImage(master=canvas, file=str(assets / "battle" / "temur-fainted-v1.png")).zoom(2)
        self.fainted_sprites = {"Retri": self.fainted, "Temur": self.temur_fainted}
        self.guard_sprites = {
            name: tk.PhotoImage(master=canvas, file=str(assets / "battle" / f"{name.lower()}-guard.png")).zoom(2)
            for name in ("Retri", "Temur")
        }
        self.class_sprites = {
            (name, job): tk.PhotoImage(
                master=canvas,
                file=str(assets / "battle" / "classes" / f"{name.lower()}-{job.lower()}.png"),
            ).zoom(2)
            for name in ("Retri", "Temur") for job in JOBS
        }
        self.class_poses = {
            (name, job, pose): tk.PhotoImage(master=canvas, file=str(
                assets / "battle" / "classes" / f"{name.lower()}-{job.lower()}-{pose}.png"
            )).zoom(2)
            for name in ("Retri", "Temur") for job in JOBS for pose in ("guard", "fainted")
        }
        self.backdrop = tk.PhotoImage(master=canvas, file=str(assets / "battle" / "crystal-quarry.png"))
        self.backgrounds = [
            [tk.PhotoImage(master=canvas, file=str(assets / "battle" / pattern.format(i)))
             for i in range(3)]
            for pattern in ("crystal-glow-{}.png", "crystal-cave-2-glow-{}.png",
                            "crystal-cave-3-glow-{}.png")
        ]
        self.glow_frames = self.backgrounds[0]
        self.background_rng = random.Random()
        self.background_bag = []
        self.background_index = None
        self.model = None
        self.level_roster = None

    def start(self, model, now):
        if not self.background_bag:
            self.background_bag = list(range(len(self.backgrounds)))
            self.background_rng.shuffle(self.background_bag)
            if self.background_index is not None and self.background_bag[-1] == self.background_index:
                self.background_bag[0], self.background_bag[-1] = self.background_bag[-1], self.background_bag[0]
        self.background_index = self.background_bag.pop()
        self.glow_frames = self.backgrounds[self.background_index]
        self.model = model
        self.selection = 0
        self.item_menu = False
        self.chosen_item = "potion"
        self.ally_target = 0
        self.phase = "command"
        self.held = None
        self.repeat_at = 0.0
        self.phase_at = now
        c = self.canvas
        c.create_rectangle(0, 0, 960, 540, fill="#08090c", outline="", tags=self.TAG)
        self.glow_started = now
        self.glow_index = 0
        self.backdrop_item = c.create_image(0, 0, image=self.glow_frames[0], anchor="nw", tags=self.TAG)
        count = len(model.enemies)
        self.enemy_positions = [(270, 190 + (i - (count - 1) / 2) * 80)
                                for i in range(count)]
        self.enemy_items = [c.create_image(x, y, image=self.enemies[foe.sprite], tags=self.TAG)
                            for (x, y), foe in zip(self.enemy_positions, model.enemies)]
        self.enemy_item = self.enemy_items[0]
        self.party_positions = [(738 + 36*i, 255 - 66*i) for i in range(len(model.party))]
        sprites = {"Retri": self.hero, "Temur": self.temur}
        self.party_sprites = [
            self.class_sprites.get((p["name"], current_job(p)), sprites.get(p["name"]))
            for p in model.party
        ]
        self.party_items = []
        for (x, y), image, member in zip(self.party_positions, self.party_sprites, model.party):
            if image is None:
                item = c.create_text(x, y, text=member["name"], fill="#ffffff", font=self.font(20), tags=self.TAG)
            else:
                item = c.create_image(x, y, image=image, tags=self.TAG)
            self.party_items.append(item)
        self.party_fainted = [None] * len(model.party)
        self.party_pose = [None] * len(model.party)
        self._sync_party_sprites()
        self.hero_item = self.party_items[0]
        self._frame(18, 320, 942, 382)
        self._frame(18, 394, 296, 526)
        self._frame(308, 394, 516, 526)
        self._frame(526, 394, 942, 526)
        self.draw_status()

    def _sync_party_sprites(self):
        """Show fainting first, then guarding, otherwise the class pose."""
        for i, member in enumerate(self.model.party):
            fainted = member["hp"] <= 0
            pose = "fainted" if fainted else "guard" if i in self.model.guarded else "standing"
            if self.party_pose[i] == pose:
                continue
            self.party_pose[i], self.party_fainted[i] = pose, fainted
            item = self.party_items[i]
            if self.party_sprites[i] is None:
                suffix = " (KO)" if fainted else " (GUARD)" if pose == "guard" else ""
                self.canvas.itemconfigure(item, text=member["name"] + suffix,
                                          fill="#e99898" if fainted else "#ffffff")
            else:
                images = self.fainted_sprites if fainted else self.guard_sprites if pose == "guard" else {}
                image = self.class_poses.get((member["name"], current_job(member), pose),
                                             images.get(member["name"], self.party_sprites[i]))
                self.canvas.itemconfigure(item, image=image)
            self.canvas.coords(item, *self._party_position(i))

    def _party_position(self, index):
        x, y = self.party_positions[index]
        # The faint artwork's feet sit four native pixels above the standing baseline.
        if self.party_fainted[index] and self.model.party[index]["name"] in self.fainted_sprites:
            y += 8
        return x, y

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
            c.create_text(x-48, y, text="▶", fill="#ffffff", font=self.font(24, True),
                          tags=(*tags, "battle_target_indicator"))
        elif self.phase == "ally_target":
            x, y = self._party_position(self.ally_target)
            c.create_text(x-48, y, text="▶", fill="#ffffff", font=self.font(24, True),
                          tags=(*tags, "battle_target_indicator"))
        c.create_text(40, 350, text=m.message, anchor="w", fill="#ffffff", font=self.font(23), tags=tags)
        if isinstance(m, ShalehornBattle) and self.phase in ("command", "target", "ally_target"):
            c.create_text(480, 65, text=m.tell(), fill="#ffe37e", font=self.font(24, True), tags=tags)
        if self.item_menu:
            commands = tuple(f"{name} x{count}" for name, count, _item in self._item_entries()) + ("Back",)
        else:
            commands = self.COMMANDS
        for i, command in enumerate(commands):
            x, y = self._command_position(i)
            if i == self.selection and self.phase == "command":
                c.create_text(x-12, y, text="▶", anchor="e", fill="#ffffff",
                              font=self.font(16, True), tags=tags)
            c.create_text(x, y, text=command, anchor="w", font=self.font(22),
                          fill="#ffe37e" if i == self.selection else "#ffffff", tags=tags)
        c.create_text(326, 425, text="ENEMY", anchor="w", fill="#80eaf5", font=self.font(17), tags=tags)
        c.create_text(326, 458, text=m.enemy.name, anchor="w", width=172,
                      fill="#ffffff", font=self.font(18), tags=tags)
        c.create_text(326, 494, text=f"HP {m.enemy_hp}/{m.enemy.hp}", anchor="w",
                      fill="#ffffff", font=self.font(17), tags=tags)
        for i, member in enumerate(m.party):
            y = 421 + i * 34
            active = i == m.actor and self.phase in ("command", "target", "ally_target")
            color = "#e99898" if member["hp"] <= 0 else "#ffe37e" if active else "#ffffff"
            if active:
                c.create_text(545, y, text="▶", anchor="w", fill="#ffffff",
                              font=self.font(16, True), tags=tags)
            c.create_text(570, y, text=member["name"], anchor="w", fill=color, font=self.font(20), tags=tags)
            hp_text = f"HP {member['hp']} / {member['max_hp']}" + ("  KO" if member["hp"] <= 0 else "")
            c.create_text(912, y, text=hp_text,
                          anchor="e", fill=color, font=self.font(20), tags=tags)

    def _item_entries(self):
        """Owned consumables. Potion stays first so the existing item row is unchanged."""
        entries = [("Potion", self.model.potions, "potion")]
        for item_id, count in self.model.inventory.items():
            if item_id == "potion" or count <= 0:
                continue
            try:
                item = get_item(item_id)
            except KeyError:
                continue
            if item.effect:
                entries.append((item.name, count, item.id))
        return entries

    def _command_position(self, index):
        if self.item_menu:
            count = len(self._item_entries()) + 1
            if count <= 2:
                return 60, 435 + index * 43
            gap = 96 // (count - 1)
            return 48, 418 + index * gap
        return 60 + (index % 2) * 126, 435 + (index // 2) * 43

    def navigate(self, direction, now):
        if self.phase in ("target", "ally_target"):
            if direction not in ("up", "down", "left", "right"):
                self.held = None
            elif direction != self.held or now >= self.repeat_at:
                self.held, self.repeat_at = direction, now + 0.22
                step = -1 if direction in ("left", "up") else 1
                if self.phase == "ally_target":
                    self.ally_target = (self.ally_target + step) % len(self.model.party)
                    label = "Potion" if self.chosen_item == "potion" else get_item(self.chosen_item).name
                    self.model.message = f"Choose who receives the {label}."
                else:
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
            step = 1 if self.item_menu else {"up": -2, "down": 2, "left": -1, "right": 1}[direction]
            limit = len(self._item_entries()) + 1 if self.item_menu else 4
            self.selection = (self.selection + step) % limit
            self.repeat_at = now + 0.22
            self.draw_status()

    def confirm(self, now):
        if self.phase == "result":
            if self.model.outcome == "victory" and self.result_page + 1 < len(self.level_pages):
                self.result_page += 1
                self._level_up_page()
                return None
            return self.model.outcome
        if self.phase == "target":
            self.model.command("Attack")
            self.phase, self.phase_at = "hero_action", now
            self.draw_status()
            return None
        if self.phase == "ally_target":
            if self.chosen_item == "potion":
                accepted = self.model.command("Potion", target=self.ally_target)
            else:
                accepted = self.model.command("Use", target=self.ally_target, item_id=self.chosen_item)
            if accepted:
                self.item_menu, self.selection = False, 2
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
            entries = self._item_entries()
            if self.item_menu and self.selection == len(entries):
                self.item_menu, self.selection = False, 2
                self.draw_status()
                return None
            if self.item_menu:
                _name, count, item_id = entries[self.selection]
                self.chosen_item = item_id
                if count <= 0:
                    self.model.message = "No potions left. Choose another action." if item_id == "potion" else "None left. Choose another action."
                else:
                    self.ally_target = self.model.actor
                    self.phase, self.held = "ally_target", None
                    label = "Potion" if item_id == "potion" else get_item(item_id).name
                    self.model.message = f"Choose who receives the {label}."
                self.draw_status()
                return None
            action = self.COMMANDS[self.selection]
            if self.model.command(action):
                self._sync_party_sprites()
                self.item_menu, self.selection = False, 2 if action == "Potion" else self.selection
                self.phase = "hero_action"
                self.phase_at = now
            self.draw_status()
        return None

    def back(self):
        if self.phase == "ally_target":
            self.phase, self.held = "command", None
            self.item_menu, self.selection = True, 0
            self.model.message = "Choose an item."
            self.draw_status()
            return
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
        if self.phase == "ally_target":
            for i in range(len(self.party_positions)):
                px, py = self._party_position(i)
                if abs(x-px) < 40 and abs(y-py) < 40:
                    self.ally_target = i
                    return self.confirm(now)
            return None
        if self.phase == "target":
            for i, (ex, ey) in enumerate(self.enemy_positions):
                if self.model.health[i] and abs(x-ex) < 60 and abs(y-ey) < 60:
                    self.model.target = i
                    return self.confirm(now)
            return None
        if self.phase == "result":
            return self.confirm(now)
        if self.phase == "command":
            span = len(self._item_entries()) + 1 if self.item_menu else 4
            for i in range(span):
                tx, ty = self._command_position(i)
                if tx-25 <= x <= tx+100 and abs(y-ty) < 19:
                    self.selection = i
                    return self.confirm(now)
        return None

    def update(self, now):
        if self.phase != "result":
            self._sync_party_sprites()
            index = (0, 1, 2, 1)[int(max(0, now - self.glow_started) / 0.4) % 4]
            if index != self.glow_index:
                self.glow_index = index
                self.canvas.itemconfigure(self.backdrop_item, image=self.glow_frames[index])
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
        ax, ay = self._party_position(i)
        if enemy_attacking and self.model.effect == "tremor":
            ay += 3 if int(elapsed*22)%2 else -3
        c.coords(active_item, ax - (offset if attacking else 0), ay)
        c.coords(self.enemy_item, ex + (offset if enemy_attacking else 0), ey)
        c.itemconfigure(self.enemy_item, state="hidden" if getattr(self.model, "buried", False) or (attacking and int(elapsed * 16) % 2) else "normal")
        c.itemconfigure(active_item, state="hidden" if enemy_attacking and int(elapsed * 16) % 2 else "normal")
        if elapsed < 0.65:
            return
        c.coords(active_item, *self._party_position(i))
        c.delete("damage_number")
        c.coords(self.enemy_item, ex, ey)
        c.itemconfigure(active_item, state="normal")
        c.itemconfigure(self.enemy_item, state="normal" if self.model.health[index] and not getattr(self.model, "buried", False) else "hidden")
        if self.model.outcome:
            self.phase = "result"
            self.model.message = {
                "victory": f"Victory! {self.model.xp_reward} XP, {self.model.gold_reward} gold.",
                "defeat": "Retri retreats to the entrance to recover.",
                "fled": "Escaped safely. Continue exploring.",
            }[self.model.outcome]
            if self.model.outcome == "victory":
                self._victory_screen(now)
                return
        elif self.phase == "hero_action":
            if self.model.next_party_turn():
                self.phase = "command"
                self.held = None
            else:
                self.model.reply()
                self.phase = "enemy_action"
                self.phase_at = now
                self._sync_party_sprites()
        else:
            self.phase = "command"
            self.held = None
            self.model.message = f"What will {self.model.party[self.model.actor]['name']} do?"
        self.draw_status()

    def _victory_screen(self, now):
        c, m = self.canvas, self.model
        self.result_at = now
        self.level_item = None
        self.result_page = -1
        self.level_pages = []
        fields = (
                ("MAX HP", "max_hp", 0), ("MAX MP", "max_mp", 0),
                ("STRENGTH", "strength", 8), ("DEFENSE", "defense", 0),
                ("MAGIC", "magic", 0), ("MAGIC DEF", "magic_defense", 0),
                ("AGILITY", "agility", 0), ("LUCK", "luck", 0),
                ("EVASION", "evasion", 0), ("ACCURACY", "accuracy", 0),
            )
        for member in m.party:
            old_level = member.get("level", m.level)
            level, xp = gain_xp(old_level, member.get("xp", m.xp), m.xp_reward)
            if level <= old_level:
                continue
            projected = dict(member)
            grow(projected, old_level, level)
            changes = [(label, member.get(key, default), projected.get(key, default))
                       for label, key, default in fields
                       if member.get(key, default) != projected.get(key, default)]
            self.level_pages.append((member["name"], True, old_level, level, changes))
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
            old_level = member.get("level", m.level)
            level, xp = gain_xp(old_level, member.get("xp", m.xp), m.xp_reward)
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
        if self.level_pages:
            self.level_item = text(712, 65, "LEVEL UP!", 32, "#ffe48a")
        text(65, 483, "ENTER / CROSS TO VIEW STAT GAINS" if self.level_pages
             else "ENTER / CROSS TO CONTINUE", 25)

    def _level_up_page(self):
        c, m = self.canvas, self.model
        name, active, old_level, new_level, changes = self.level_pages[self.result_page]
        self.level_item = None
        c.delete(self.TAG)
        c.create_rectangle(0, 0, 960, 540, fill="#08090c", outline="", tags=self.TAG)
        self._frame(35, 28, 925, 106)
        self._frame(35, 120, 925, 430)
        self._frame(35, 447, 925, 520)
        c.create_text(65, 66, text=f"LEVEL UP · {name.upper()}" + ("" if active else " · RESERVE"),
                      anchor="w", fill="#ffe48a", font=self.font(29, True), tags=self.TAG)
        c.create_text(895, 66, text=f"LV {old_level} → {new_level}", anchor="e",
                      fill="#ffffff", font=self.font(24), tags=self.TAG)
        for i, (label, before, after) in enumerate(changes):
            x, y = 80 + (i % 2) * 415, 167 + (i // 2) * 52
            c.create_text(x, y, text=label, anchor="w", fill="#80eaf5",
                          font=self.font(21), tags=self.TAG)
            c.create_text(x + 355, y, text=f"{before} → {after}", anchor="e", fill="#ffffff",
                          font=self.font(23), tags=self.TAG)
        c.create_text(65, 483, text=f"MEMBER {self.result_page+1}/{len(self.level_pages)}  ·  ENTER / CROSS TO CONTINUE",
                      anchor="w", fill="#ffffff", font=self.font(21), tags=self.TAG)

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
