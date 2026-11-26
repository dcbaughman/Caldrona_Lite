"""Step encounters and a small, strictly turn-based cavern battle scene."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
import math
import random
import tkinter as tk
from stats import RETRI, RETRI_HP_PER_LEVEL, grow
from classes import OUTFIT_JOBS, current_job
from equipment import equipment_crit_bonus, item_for, resist_fire, stat_bonus, stat_value, worn_id
from combat_math import critical_chance, critical_damage, physical_damage
from consumables import RARE_SUPPLIES, SUPPLIES, apply_supply, item_gain_text
from shalehorn_fx import ShalehornEffects
from frozen_fx import FrozenOverlay
from poison_fx import PoisonOverlay
from darkness_silence_fx import DarknessSilenceFX
from ctb import CTBQueue, recovery
from statuses import StatusBook, AILMENTS, PLAYER_AILMENTS
from enemy_skills import EnemySkill, SKILLS
from ember_wyvern_fx import (ATTACK_TIMING as WYVERN_ATTACK_TIMING, PHASE_NAMES as WYVERN_PHASE_NAMES,
                             TRANSITION_SECONDS as WYVERN_REVEAL_SECONDS, EmberWyvernArt,
                             attack as draw_wyvern_attack, ground_flare)
from brood_fx import BROOD_DURATION, BroodSilk, brood_shade
from enemy_motion import BROOD_SHADE_STEPS, enemy_pose_frame, idle_offset, load_brood_shades, load_enemy_frames
from research import ATTACK_MULTIPLIERS, LESSONS
from abilities import RESEARCH_FX, frame_index, learned_abilities, lesson_variant, strike_variant
from arrow_fx import FLIGHT_MS, TAG as BOW_SHOT_TAG, draw_shot
from loot import PROFILES, loot_name, roll_kill, roll_steal
from research import Lesson, record_observation
from item_slots import draw_item_slot
from items import supply_icon
from web_art import bound_web
from crescendo import (Crescendo, HIT_CHARGE, MAX_CHARGE, SUPPORT_CHARGE,
                        add_charge, add_progress, charge, equipped_crescendo)
from crescendo_fx import CrescendoFX
from kit_effects import KitMixin
from player_motion import PROJECTILE_OFFSETS, PlayerMotionArt, action_motion

# Tune encounters here. Only successful tile moves call EncounterMeter.step().
ENCOUNTER_CHANCE = 0.08
SAFE_STEPS = 12
MAX_HP = RETRI["max_hp"]
MAX_POTIONS = 3
TRANSITION_SECONDS = 0.45
FIELD_GRID = 16
FIELD_HORIZON = 104
FIELD_HEIGHT = 320


def _field_backdrop(canvas, path):
    """Reframe the field in two bands, preserving the artwork's two-pixel rows."""
    source = tk.PhotoImage(master=canvas, file=str(path))
    backdrop = tk.PhotoImage(master=canvas, width=source.width(), height=FIELD_HEIGHT)
    source_horizon = 164
    bands = ((0, source_horizon, 0, FIELD_HORIZON),
             (source_horizon, source.height(), FIELD_HORIZON, FIELD_HEIGHT))
    for source_top, source_bottom, top, bottom in bands:
        for y in range(top, bottom, 2):
            row = (y - top + 1) * (source_bottom - source_top) // (2 * (bottom - top))
            source_y = source_top + row * 2
            backdrop.tk.call(backdrop, "copy", source, "-from", 0, source_y,
                             source.width(), source_y + 2, "-to", 0, y)
    return backdrop


def _center_y_on_ground(image, ground_y):
    """Return the center that puts the last visible pixel row on the ground line."""
    for y in range(image.height() - 1, -1, -1):
        if any(not image.transparency_get(x, y) for x in range(image.width())):
            return ground_y - (y + 1 - image.height() // 2)
    return ground_y - image.height() // 2


def _field_enemy_positions(foes, images, mirrored):
    """Put one to three regular foes on the battle grid, from back to front."""
    sprites = [images[foe.sprite] for foe in foes]
    widest = max(sprite.width() for sprite in sprites)
    half_span = max(3, math.ceil((widest + FIELD_GRID) / (2 * FIELD_GRID)))
    center_column, center_row = 16, 14
    slots = (
        ((0, 0),),
        ((-1, -2), (1, 2)),
        ((-1, -4), (1, 0), (-1, 4)),
    )[len(foes) - 1]
    side = -1 if mirrored else 1
    return [((center_column + side * column * half_span) * FIELD_GRID,
             _center_y_on_ground(sprite, (center_row + row) * FIELD_GRID - foe.sprite_lift))
            for foe, sprite, (column, row) in zip(foes, sprites, slots, strict=True)]


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

    def step(self, chance=None):
        if self.steps_left:
            self.steps_left -= 1
            return False
        if self.rng.random() < (self.chance if chance is None else chance):
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
    luck: int = 7
    evasion: int = 0
    accuracy: int = 0
    pursuit: int = 0
    fire_damage_percent: int = 100
    status_immunities: tuple[str, ...] = ()
    level: int = 1
    sprite_scale: tuple[int, int] = (2, 1)
    sprite_lift: int = 0
    sprite_bob: int = 0
    ink_outline: bool = False
    physical_damage_percent: int = 100

    @property
    def loot(self):
        return PROFILES.get(self.name)


@dataclass
class OpenReliquary:
    caster: int
    magic: int
    pending: set[int]
    absorb_percent: int
    phases: int = 3
    stored: int = 0
    twin: bool = False


ENEMIES = (
    Enemy("Ivory Spider", "spider.png", 22, (5, 8), 1, 8, "bites", 4, 6, 1, 1, 1, 7, 6, 4, 5,
          fire_damage_percent=150),
    Enemy("Echo Bat", "bat.png", 19, (4, 7), 0, 6, "swoops", 4, 5, 0, 1, 1, 9, 6, 5, 5,
          sprite_lift=10),
    Enemy("Rock Crawler", "crawler.png", 25, (6, 9), 2, 12, "rams", 3, 7, 2, 1, 2, 5, 6, 2, 5),
)

GRASSLAND_ENEMIES = (
    Enemy("Cinder Hornet", "cinder-hornet.png", 30, (7, 10), 0, 15, "stings",
          mp=4, strength=8, agility=11, evasion=6, accuracy=7, level=3,
          sprite_scale=(1, 1), sprite_lift=FIELD_GRID),
    Enemy("Ashmane Wolf", "ashmane-wolf.png", 38, (8, 12), 1, 19, "lunges",
          mp=4, strength=10, defense=1, agility=12, luck=8, accuracy=8, pursuit=12, level=4,
          sprite_scale=(5, 4)),
    Enemy("Torshield Ram", "torshield-ram.png", 46, (9, 13), 3, 22, "rams",
          mp=4, strength=11, defense=3, magic_defense=2, agility=7, level=5,
          sprite_scale=(7, 6)),
)

EMBERWRAITH = Enemy(
    "Emberwraith", "emberwraith.png", 46, (9, 13), 4, 16, "lashes",
    mp=4, strength=9, magic=8, magic_defense=3, agility=9, luck=8, pursuit=6,
    fire_damage_percent=50, status_immunities=("webbed",), level=5,
    physical_damage_percent=5,
)
SILK_SARCOPHAGUS = Enemy(
    "Silk Sarcophagus", "silk-sarcophagus.png", 59, (11, 15), 2, 21, "sweeps",
    mp=4, strength=10, defense=2, magic=8, magic_defense=2, agility=8, luck=8, pursuit=9,
    fire_damage_percent=125, status_immunities=("webbed",), level=6,
    sprite_lift=FIELD_GRID, sprite_bob=3,
)

DEPTHS_OUTER_ENEMIES = (
    Enemy("Hollow Weaver", "hollow-weaver.png", 40, (9, 13), 1, 12, "bites", mp=4,
          strength=8, agility=10, pursuit=5, fire_damage_percent=150,
          status_immunities=("webbed",), level=4),
    EMBERWRAITH,
)

DEPTHS_ENEMIES = (
    *DEPTHS_OUTER_ENEMIES,
    SILK_SARCOPHAGUS,
    Enemy("Brood Stalker", "brood-stalker.png", 63, (13, 18), 2, 20, "lunges", mp=4, strength=12,
          defense=2, agility=13, luck=9, pursuit=15, fire_damage_percent=150,
          status_immunities=("poison", "webbed"), level=7),
)

DEN_MOTHER = Enemy("Den Mother", "den-mother.png", 335, (26, 36), 4, 76,
                   "bites", 12, 17, 4, 4, 5, 14, 8, 4, 7, level=9,
                   pursuit=68, fire_damage_percent=150, status_immunities=("poison", "webbed", "frozen"))
SPIDERLING = Enemy("Spiderling", "spiderling.png", 18, (9, 12), 0, 0, "nibbles",
                   agility=9, fire_damage_percent=200, status_immunities=("poison", "webbed"))


def cave_encounter(rng):
    return [rng.choice(ENEMIES) for _ in range(rng.randint(1, 3))]


def grassland_encounter(rng, party_size):
    return rng.sample(GRASSLAND_ENEMIES, rng.randint(1, min(2, party_size)))


def depths_encounter(rng, danger, party_size):
    pool = DEPTHS_OUTER_ENEMIES if danger <= 1 else DEPTHS_ENEMIES
    if party_size <= 1 or rng.random() < .28:
        return [rng.choice(pool)]
    count = 3 if danger >= 2 and rng.random() < .22 else 2
    return rng.sample(pool, count)


SHALEHORN = Enemy("Shalehorn", "shalehorn.png", 150, (16, 22), 4, 32, "charges",
                  strength=14, defense=4, luck=9, status_immunities=("frozen", "silence"))

# The bound beast beneath the Lower Workings.
WYVERN_GROUND = 312
EMBER_WYVERN = Enemy("Ember Wyvern", "ember-wyvern.png", 120, (14, 18), 3, 28, "Fire Bite",
                    strength=12, defense=3, magic_defense=2, agility=7, luck=8, pursuit=8,
                    fire_damage_percent=50, status_immunities=("frozen",), level=5)

ENEMY_ROSTER = (*ENEMIES, *GRASSLAND_ENEMIES, *DEPTHS_ENEMIES, SPIDERLING, DEN_MOTHER, SHALEHORN, EMBER_WYVERN)


class BattleModel(KitMixin):
    """Combat effects, with a CTB queue activated by the battle scene."""
    def __init__(self, enemy, hp=MAX_HP, potions=MAX_POTIONS, rng=None, level=1, xp=0, party=None,
                 supplies=None, loot_rng=None, status_rng=None, crit_rng=None):
        self.enemies = list(enemy) if isinstance(enemy, (list, tuple)) else [enemy]
        self.health = [foe.hp for foe in self.enemies]
        self.target = 0
        self.damage = 0
        self.hp = hp
        self.party = party if party is not None else [{"name": "Retri", "hp": hp, "max_hp": MAX_HP + (level-1)*RETRI_HP_PER_LEVEL}]
        self.actor = next((i for i, member in enumerate(self.party) if member["hp"] > 0), 0)
        self.defender = 0
        self.potions = potions
        self.supplies = dict(supplies or {})
        self.level, self.xp = level, xp
        self.max_hp = MAX_HP + (level - 1) * RETRI_HP_PER_LEVEL
        self.gold_reward = sum(foe.gold for foe in self.enemies)
        self.xp_reward = self.gold_reward * 2
        if any(current_job(p) == "Sollers" for p in self.party):
            self.gold_reward += len(self.enemies) * 2
        self.rng = rng if rng is not None else random.Random()
        self.crit_rng = crit_rng if crit_rng is not None else self.rng
        self.loot_rng = loot_rng if loot_rng is not None else random.Random()
        self.drops = Counter()
        self.stolen = Counter()
        self.rolled_kills = set()
        self.steal_attempts = set()
        self.wards = {}
        self.marks = {}
        self.black_thread = None
        self.reliquary = None
        self.reliquary_release = {}
        self.reliquary_origin = 0
        self.outcome = None
        self.pending_reply = False
        self.guarded = set()
        self.hits = {}
        self.critical_hits = set()
        self.crescendo_hits = {}
        self.statuses = StatusBook()
        for i,person in enumerate(self.party):self.statuses.bind(("party",i),person)
        self.status_rng = status_rng if status_rng is not None else random.Random()
        self.enemy_mp = [foe.mp for foe in self.enemies]
        self.enemy_turns = [0 for foe in self.enemies]
        self.enemy_skill = None
        self.status_events = []
        self._status_end_serial = -1
        self.ctb = None
        self.action_rank = 3
        self.effect = ""
        self._kit_init()
        self.message = "Enemies approach!" if len(self.enemies) > 1 else f"{self.enemy.name} approaches!"

    def begin_ctb(self):
        speeds = {("party", i): stat_value(p, "agility", RETRI["agility"]) for i, p in enumerate(self.party)}
        speeds.update({("enemy", i): foe.agility for i, foe in enumerate(self.enemies)})
        self.ctb = CTBQueue(speeds, self._ctb_alive)
        self._prepare_ctb_actor()

    def _ctb_alive(self, key):
        side, index = key
        return self.party[index]["hp"] > 0 if side == "party" else self.health[index] > 0

    def _prepare_ctb_actor(self):
        if self.ctb.current is not None and self.ctb.current[0] == "party":
            self.actor = self.ctb.current[1]
            self.pending_reply = False
            # Guard/wards last until the recipient's next turn, even if several
            # foes attack first. A fast actor can choose to renew Guard.
            self.guarded.discard(self.actor)
            self.wards.pop(self.actor, None)
            self.ward_sources.pop(self.actor, None)
            self.message = f"What will {self.party[self.actor]['name']} do?"
            self.kit_turn_start(self.actor)
            self._flush_notes()

    def finish_ctb_turn(self):
        self.resolve_turn_end()
        if self.outcome:
            return None
        self.ctb.advance(self.action_rank)
        self.action_rank = 3
        self._prepare_ctb_actor()
        return self.ctb.current

    def _check_outcome(self):
        if self.black_thread is not None and any(self.health[i] <= 0 for i in self.black_thread[:2]):
            self.black_thread = None
        for i, hp in enumerate(self.health):
            if hp <= 0:self.statuses.clear_ko(("enemy",i))
        for i, member in enumerate(self.party):
            if member["hp"] <= 0:
                self.statuses.clear_ko(("party", i))
                member.pop("crescendo_charge", None)
        self.hp = self.party[0]["hp"]
        if not any(self.health):self.outcome = "victory"
        elif not any(p["hp"] > 0 for p in self.party):self.outcome = "defeat"
        self.collect_kill_drops()

    def apply_status(self, key, status, chance=1, turns=None):
        if not self._ctb_alive(key):return False
        side, index = key
        if side == "enemy":
            immune = status in self.enemies[index].status_immunities
        else:
            immune = any(status in item.status_immunities
                         for item_id in self.party[index].get("equipment", {}).values()
                         if (item := item_for(item_id)) is not None)
        if immune:
            self.message += f" Immune to {AILMENTS[status].label}."
            return False
        if self.status_rng.random() >= chance or not self.statuses.apply(key, status, turns):
            self.message += f" Resisted {AILMENTS[status].label}."
            return False
        label = AILMENTS[status].label
        duration = self.statuses.for_actor(key)[status]
        self.message += (f" {label} until cured!" if duration == -1
                         else f" {label} ({duration} {'turn' if duration == 1 else 'turns'})!")
        return True

    def effective_evasion(self, key):
        side, index = key
        value = stat_value(self.party[index], "evasion") if side == "party" else self.enemies[index].evasion
        return value / 2 if self.statuses.has(key, "webbed") else value

    def _misses_in_darkness(self, attacker, defender):
        if not self.statuses.has(attacker,"darkness"):return False
        accuracy = stat_value(self.party[attacker[1]],"accuracy") if attacker[0]=="party" else self.enemies[attacker[1]].accuracy
        chance = max(.25,min(.65,.5+(accuracy-self.effective_evasion(defender))/100))
        return self.status_rng.random() >= chance

    def _luck(self, key):
        side, index = key
        if side == "enemy":
            return self.enemies[index].luck
        return stat_value(self.party[index], "luck", RETRI["luck"])

    def _roll_critical(self, damage, attacker, defender):
        if damage <= 0:
            return damage
        side, index = attacker
        bonus = equipment_crit_bonus(self.party[index]) if side == "party" else 0
        chance = critical_chance(self._luck(attacker), self._luck(defender), bonus)
        if chance and self.crit_rng.randint(0, 99) < chance:
            self.critical_hits.add(defender)
            return critical_damage(damage)
        return damage

    def escape_chance(self):
        """Return the party's percentage chance against the strongest pursuer."""
        living = [i for i, ally in enumerate(self.party) if ally["hp"] > 0]
        if not living or any(self.statuses.has(("party", i), "webbed") for i in living):
            return 0
        agility = max(stat_value(self.party[i], "agility", RETRI["agility"]) for i in living)
        pursuit = max((foe.agility + foe.pursuit for foe, hp in zip(self.enemies, self.health) if hp > 0),
                      default=0)
        return max(1, min(100, 75 + agility - pursuit))

    def resolve_turn_end(self):
        if self.ctb is None or self._status_end_serial == self.ctb.completed:return []
        self._status_end_serial = self.ctb.completed
        key=self.ctb.current
        self.status_events=[]
        self.reliquary_release = {}
        if self.outcome or key is None:return []
        if self.statuses.has(key,"poison") and self._ctb_alive(key):
            side,index=key
            maximum=stat_value(self.party[index],"max_hp") if side=="party" else self.enemies[index].hp
            percent=2 if side=="enemy" and self.enemies[index].name=="Shalehorn" else 8
            loss=max(1,math.ceil(maximum*percent/100))
            if side=="party":
                loss = self._take_party_damage(index, loss, clip=True, incoming=False)
                name=self.party[index]["name"]
            else:
                loss=min(loss,self.health[index]);self.health[index]-=loss
                name=self.enemies[index].name
            self.status_events.append((key,loss))
            self.message=f"Poison drains {loss} HP from {name}."
        self.statuses.end_turn(key)
        self.kit_turn_end(key)
        if key[0] == "enemy":
            self._advance_reliquary(key[1])
        self._check_outcome()
        return self.status_events

    def skip_frozen_turn(self):
        key=self.ctb.current
        name=self.party[key[1]]["name"] if key[0]=="party" else self.enemies[key[1]].name
        self.message=f"{name} is Frozen and loses this turn!"
        self.damage=0;self.hits={};self.healed={};self.effect="frozen";self.action_rank=3
        self.critical_hits.clear()
        self.pending_reply=False

    def next_enemy_skill(self,index):
        options=SKILLS.get(self.enemies[index].name,())
        turn=self.enemy_turns[index]+1
        if not options or turn%2:return None
        skill=options[(turn//2-1)%len(options)]
        if self.enemy_mp[index]<skill.mp:return None
        if skill.magic and self.statuses.has(("enemy",index),"silence"):return None
        return skill

    def enemy_intent(self,index):
        skill=self.next_enemy_skill(index)
        return skill.name if skill else self.enemies[index].move.title()

    @property
    def enemy(self):
        return self.enemies[self.target]

    @property
    def enemy_hp(self):
        return self.health[self.target]

    @enemy_hp.setter
    def enemy_hp(self, value):
        self.health[self.target] = value

    @property
    def potion_reward(self):
        return int(self.potions < MAX_POTIONS)

    @property
    def research_reward(self):
        return sum(foe.loot.rp for foe in self.enemies if foe.loot is not None)

    def collect_kill_drops(self):
        for index, (foe, hp) in enumerate(zip(self.enemies, self.health)):
            if hp == 0 and index not in self.rolled_kills and foe.loot is not None:
                self.rolled_kills.add(index)
                self.drops.update(roll_kill(foe.loot, self.loot_rng))

    def _hit_target(self, damage, physical=False, element=None, *, include_mark=True, can_crit=False):
        if include_mark:damage = self.kit_outgoing(damage, physical)
        if physical and damage > 0:
            self.statuses.remove(("enemy", self.target), "frozen")
            damage = max(1, damage * self.enemy.physical_damage_percent // 100)
        affinity = self.enemy_element_percent(element)
        if affinity != 100:
            damage = math.ceil(damage * affinity / 100)
        if can_crit and ("enemy", self.target) not in self.critical_hits:  # no double crit (Backstab)
            damage = self._roll_critical(damage, ("party", self.actor), ("enemy", self.target))
        self.damage = damage + (self.marks.pop(self.target, 0) if include_mark else 0)
        self.enemy_hp = max(0, self.enemy_hp - self.damage)
        if not any(self.health):
            self.outcome = "victory"
        self.collect_kill_drops()
        if self.enemy_hp == 0:self.statuses.clear_ko(("enemy",self.target))

    def _take_party_damage(self, index, damage, *, clip=False, incoming=True, fire_damage=0, single_target=True):
        original = index
        raw_damage = damage
        if incoming:
            self._kit_redirect = None
        if incoming and damage > 0:
            index, damage = self.kit_incoming(index, damage, single_target=single_target)
        if fire_damage and damage > 0:
            fire = math.ceil(damage * fire_damage / raw_damage)
            damage += resist_fire(self.party[index], fire) - fire
        if self.reliquary is not None:
            absorbed = damage * self.reliquary.absorb_percent // 100
            self.reliquary.stored += absorbed
            damage -= absorbed
        member = self.party[index]
        hp_before = member["hp"]
        if clip:
            damage = min(damage, member["hp"])
        if incoming:
            damage = self.kit_floor(index, damage)
        member["hp"] = max(0, member["hp"] - damage)
        if incoming:
            self.kit_after_hit(index, damage, hp_before)
        self._check_reliquary_caster()
        if index != original:
            # A Warden or decoy took the blow: show it on them, not the target.
            self.hits[index] = damage
            self._kit_redirect = (index, damage)
            return 0
        return damage

    def _check_reliquary_caster(self):
        """Retribution: if the caster falls before the release, the stored damage is lost."""
        relic = self.reliquary
        if relic is None or self.party[relic.caster]["hp"] > 0:
            return False
        self.reliquary = None
        self.reliquary_origin = relic.caster
        if not relic.twin:
            self.relic_cooldown[relic.caster] = 2
        lost = f"The reliquary shatters. {relic.stored} stored damage is lost."
        if hasattr(self, "_note"):
            self._note(lost)
        else:
            self.message = lost
        return True

    def _advance_reliquary(self, enemy):
        relic = self.reliquary
        if relic is None or self._check_reliquary_caster():
            return
        living = [i for i, hp in enumerate(self.health) if hp > 0]
        relic.pending.intersection_update(living)
        relic.pending.discard(enemy)
        if relic.pending or not living:
            return
        relic.phases -= 1
        if relic.phases:
            relic.pending = set(living)
            return
        self.reliquary = None
        self.reliquary_origin = relic.caster
        total = relic.stored * (100 + relic.magic) // 100
        damage, remainder = divmod(total, len(living))
        selected = self.target
        # Rounded down per enemy; the remainder goes to the highest-HP enemy.
        heaviest = max(living, key=lambda i: (self.health[i], -i))
        dealt_before = sum(self.health)
        for place, index in enumerate(living):
            amount = damage + (remainder if index == heaviest else 0)
            if amount:
                self.target = index
                self._hit_target(amount, include_mark=False)
                self.reliquary_release[index] = amount
                self.status_events.append((("enemy", index), amount))
        self.target = selected
        self.kit_reliquary_released(relic.caster, dealt_before - sum(self.health), relic.twin)
        self.message = (f"Retribution releases {total} magic damage!" if total
                        else "The reliquary closes without stored damage.")

    def _echo_spell(self):
        thread = self.black_thread
        if thread is None or self.target not in thread[:2] or self.damage <= 0:
            return
        a, b, percent = thread
        self.black_thread = None
        primary = self.target
        other = b if primary == a else a
        if self.health[other] <= 0:
            return
        damage = self.damage
        self.target = other
        echo = max(1, damage * percent // 100)
        self._hit_target(echo, include_mark=False)
        self.target, self.damage = primary, damage
        add_progress(self.party[self.actor if self.thread_caster is None else self.thread_caster], "Weaver", 1)
        self.message += f" Black Thread echoes {echo} to {self.enemies[other].name}!"

    def _weapon_element(self, member):
        weapon = item_for(worn_id(member, "weapon"))
        return weapon.element if weapon is not None else None

    def enemy_element_percent(self, element):
        return self.enemy.fire_damage_percent if element == "fire" else 100

    def _show_element_affinity(self, element):
        percent = self.enemy_element_percent(element)
        if percent > 100:
            self.message += f" Weak to {element}!"
        elif percent < 100:
            self.message += f" Resists {element}!"

    def _player_physical_damage(self, power=0):
        member = self.party[self.actor]
        strength = stat_value(member, "strength", RETRI["strength"] + member.get("level", self.level) - 1)
        armor = 0 if current_job(member) == "Seer" else self.enemy.armor
        return physical_damage(strength, armor, self.rng.randint(240, 271), power)

    def supply_count(self, name):
        return self.potions if name == "Potion" else self.supplies.get(name, 0)

    def item_names(self):
        """Keep the supply rows stable as the party gains or spends items."""
        return (*SUPPLIES, *RARE_SUPPLIES)

    def command(self, action, target=None, ability_id=None):
        if self.outcome or self.pending_reply:
            return False
        if self.ctb is not None and self.ctb.current != ("party", self.actor):
            return False
        if self.statuses.has(("party",self.actor),"frozen"):
            self.message = "Frozen: this turn must be skipped."
            return False
        before_hp = [member['hp'] for member in self.party]
        enemy_hp_before = sum(self.health)
        support_before = (self.wards.copy(), self.marks.copy()) if action == "Ability" else None
        health_before, wards_before = list(self.health), dict(self.wards)
        self._kit_current = ability_id if action in ("Ability", "Crescendo") else None
        self._kit_supported = False
        self.kit_notes = []
        self.healed = {}
        self.damage = 0
        self.critical_hits.clear()
        self.crescendo_hits = {}
        self.effect = action
        if action == "Crescendo":
            if not self._crescendo_command(ability_id):
                return False
        elif action == "Ability":
            if not self._ability_command(ability_id, target):
                return False
        elif action == "Attack":
            member = self.party[self.actor]
            if self._misses_in_darkness(("party",self.actor),("enemy",self.target)):
                self.message = f"{member['name']} misses in the darkness."
            else:
                weapon = item_for(worn_id(member, "weapon"))
                element = weapon.element if weapon else None
                can_crit = weapon is None or weapon.basic_attack_fx not in ("wand_bolt", "focus_pulse")
                self._hit_target(self._player_physical_damage(), physical=True, element=element, can_crit=can_crit)
                self.message = f"{member['name']} strikes for {self.damage}!"
                self._show_element_affinity(element)
        elif action == "Guard":
            self.guarded.add(self.actor)
            member = self.party[self.actor]
            if current_job(member) == "Saint":
                member["hp"] = min(stat_value(member, "max_hp"), member["hp"] + 3)
                self.hp = self.party[0]["hp"]
            self.message = f"{member['name']} braces for the next blow."
        elif action in SUPPLIES or action in RARE_SUPPLIES:
            if not self.supply_count(action):
                self.message = f"No {action} left. Choose another action."
                return False
            target = self.actor if target is None else target
            if not isinstance(target, int) or not 0 <= target < len(self.party):
                self.message = "Choose a party member."
                return False
            ailments=self.statuses.for_actor(("party",target))
            thawing=action=="Remedy" and "frozen" in ailments
            used, self.message = apply_supply(action, self.party[target], ailments)
            if used:
                self.statuses.sync(("party",target))
                if thawing:self.statuses.freeze_guard[("party",target)]=2
            if not used:
                return False
            self.hp = self.party[0]["hp"]
            if action == "Potion":
                self.potions -= 1
            else:
                self.supplies[action] -= 1
        elif action == "Flee":
            chance = self.escape_chance()
            if not chance:
                self.message = "The web holds fast!"
            elif self.rng.random() * 100 < chance:
                self.outcome = "fled"
                self.message = "Retri slips away!"
            else:
                self.message = "The way out is blocked!"
        else:
            return False
        self.healed = {i: member['hp'] - before_hp[i] for i, member in enumerate(self.party)
                       if member['hp'] > before_hp[i]}
        member = self.party[self.actor]
        if action == "Crescendo":
            self.action_rank = equipped_crescendo(member).action_rank
        elif action == "Ability":
            lesson = next((a for a in learned_abilities(member) if a.id == ability_id), None)
            self.action_rank = getattr(lesson, "action_rank", 4)
        else:
            self.action_rank = 2 if action == "Guard" or action in SUPPLIES or action in RARE_SUPPLIES else 3
        if action in ("Attack", "Ability") and sum(self.health) < enemy_hp_before:
            add_charge(member, HIT_CHARGE)
        elif action == "Ability" and (self.healed or support_before != (self.wards, self.marks) or self._kit_supported):
            add_charge(member, SUPPORT_CHARGE)
        self.kit_after_command(action, ability_id, member, health_before, before_hp, wards_before)
        self._kit_current = None
        if self.critical_hits:
            self.message = f"Critical hit! {self.message}"
        self.pending_reply = self.outcome is None
        return True

    def _crescendo_command(self, ability_id):
        member = self.party[self.actor]
        move = equipped_crescendo(member)
        if move is None or ability_id not in (None, move.id) or charge(member) < MAX_CHARGE:
            self.message = "Your equipped Crescendo needs a full meter."
            return False
        if move.target != "party":
            if getattr(self, "buried", False) or not any(self.health):
                self.message = "That enemy can't be reached."
                return False
            if move.target == "single enemy" and not self.enemy_hp:
                self.message = "Choose a standing enemy."
                return False
            targets = [self.target] if move.target == "single enemy" else [i for i, hp in enumerate(self.health) if hp]
            self._crescendo_strike(move, member, targets)
        else:
            if move.effect == "revive" and all(ally["hp"] > 0 for ally in self.party):
                self.message = "There are no fallen allies to revive."
                return False
            targets = []
            self._crescendo_support(move, member)
        if move.rider:
            self.kit_crescendo_rider(move, member, targets)
        member["crescendo_charge"] = 0
        self.hp = self.party[0]["hp"]
        return True

    def _crescendo_strike(self, move, member, targets):
        physical = move.effect in ("strike", "sweep", "riposte")
        magic = stat_value(member, "magic")
        physical_scale = {"strike": 160, "sweep": 120, "riposte": 135}.get(move.effect)
        element = self._weapon_element(member) if physical else move.element
        for i in targets:
            self.target = i
            if move.effect == "field":
                continue
            if physical and self._misses_in_darkness(("party", self.actor), ("enemy", i)):
                continue
            if physical:
                damage = self._player_physical_damage(move.power) * physical_scale // 100
            else:
                damage = magic * (1 if move.effect == "magic_sweep" else 2) + move.power
            damage = self.kit_crescendo_damage(move, i, damage, member)
            self._hit_target(damage, physical=physical, element=element)
            self.crescendo_hits[i] = self.damage
        self.target = targets[0]
        self.damage = sum(self.crescendo_hits.values())
        self.message = (f"{move.name} deals {self.damage} damage!" if self.crescendo_hits
                        else f"{move.name}!" if move.effect == "field"
                        else f"{move.name} misses in the darkness.")
        if move.element and self.damage and len(targets) == 1:
            self._show_element_affinity(element)
        if move.effect == "riposte":
            self.wards[self.actor] = max(45, self.wards.get(self.actor, 0))
            self.message += " Ward raised."
        elif move.effect == "arcane":
            self._echo_spell()

    def _crescendo_support(self, move, member):
        self.message = f"{move.name}!"
        for i, ally in enumerate(self.party):
            if ally["hp"] <= 0:
                if move.effect == "revive":
                    self.statuses.clear_ko(("party", i))
                    ally.pop("crescendo_charge", None)
                    ally["hp"] = max(1, stat_value(ally, "max_hp") * move.power // 100)
                continue
            if move.effect == "ward":
                self.wards[i] = max(move.power, self.wards.get(i, 0))
            elif move.effect == "heal":
                ally["hp"] = min(stat_value(ally, "max_hp"), ally["hp"] + move.power + stat_value(member, "magic"))
            elif move.effect == "mp":
                ally["mp"] = min(stat_value(ally, "max_mp"), ally.get("mp", 0) + move.power)
            elif move.effect == "self_restore" and i == self.actor:
                ally["hp"] = min(stat_value(ally, "max_hp"), ally["hp"] + move.power)
                ally["mp"] = min(stat_value(ally, "max_mp"), ally.get("mp", 0) + 4)

    def _ability_command(self, ability_id, target):
        member = self.party[self.actor]
        known = {ability.id: ability for ability in learned_abilities(member)}
        ability = known.get(ability_id)
        if ability is None:
            self.message = "That ability is not learned."
            return False
        magic = ability.menu == "Magic" if isinstance(ability,Lesson) else ability.job in ("Seer","Saint")
        if magic and self.statuses.has(("party",self.actor),"silence"):
            self.message = "Silence prevents Magic. Use an ability, item, Attack, or Guard."
            return False
        self.active_ability = ability.id
        if not isinstance(ability, Lesson):
            self.message = f"{ability.name} flashes. Its effect is not applied yet."
            return True
        mp = member.get("mp", 0)
        if mp < ability.mp:
            self.message = f"Not enough MP for {ability.name}."
            return False
        if ability.target == "single ally":
            index = self.actor if target is None else target
            if not isinstance(index, int) or not 0 <= index < len(self.party):
                self.message = "Choose a party member."
                return False
            ally = self.party[index]
            if ally["hp"] <= 0:
                self.message = "Choose an ally who is still standing."
                return False
        elif ability.effect == "link":
            if (not isinstance(target, (tuple, list)) or len(target) != 2 or target[0] == target[1]
                    or any(type(i) is not int or not 0 <= i < len(self.health) or self.health[i] <= 0 for i in target)):
                self.message = "Black Thread needs two living enemies."
                return False
        elif ability.effect == "reliquary":
            if self.reliquary is not None:
                self.message = "The party's reliquary is already open."
                return False
            if self.relic_cooldown.get(self.actor, 0) > 0:
                self.message = "The reliquary is still cooling."
                return False
        elif ability.effect == "kit":
            problem = self.kit_validate(ability, member)
            if problem:
                self.message = problem
                return False
        elif not self.enemy_hp or getattr(self, "buried", False):
            self.message = "That enemy can't be reached."
            return False
        if ability.effect == "steal" and (self.target in self.steal_attempts or self.enemy.loot is None):
            self.message = "There's nothing more to steal from this enemy."
            return False
        member["mp"] = mp - ability.mp
        self.damage = 0
        effect, power = ability.effect, ability.power
        if effect == "kit":
            if not self.kit_cast(ability, member, index if ability.target == "single ally" else None):
                member["mp"] = mp
                return False
        elif effect == "physical":
            if self._misses_in_darkness(("party",self.actor),("enemy",self.target)):
                self.message=f"{ability.name} misses in the darkness."
                return True
            element = self._weapon_element(member)
            if ability.id in ATTACK_MULTIPLIERS:
                hit = max(1, math.ceil(ATTACK_MULTIPLIERS[ability.id] * self._player_physical_damage(0)))
            else:
                hit = self._player_physical_damage(power)
            self._hit_target(hit, physical=True, element=element, can_crit=True)
            self.message = f"{ability.name} hits for {self.damage}!"
            self._show_element_affinity(element)
        elif effect == "arcane":
            element = {"unbound_ember_arc": "fire", "tidecaller_tide_dart": "water", "seer_mist_ray": "ice",
                       "weaver_silkbolt": "onyx"}.get(ability.id)
            self._hit_target(stat_value(member, "magic") * 2 + power, element=element)
            self.message = f"{ability.name} hits for {self.damage}!"
            self._show_element_affinity(element)
            self._echo_spell()
        elif effect == "link":
            self.black_thread = (*target, power)
            self.message = "Black Thread binds the two shadows."
        elif effect == "reliquary":
            self.reliquary = OpenReliquary(self.actor, stat_value(member, "magic"),
                                          {i for i, hp in enumerate(self.health) if hp > 0}, power)
            self.message = "The reliquary opens and begins to catch wounds."
        elif effect in ("heal", "restore"):
            key = "hp" if effect == "heal" else "mp"
            amount = power + (stat_value(member, "magic") if key == "hp" else 0)
            previous = ally.get(key, 0)
            ally[key] = min(stat_value(ally, f"max_{key}"), previous + amount)
            self.hp = self.party[0]["hp"]
            self.message = f"{ability.name} restores {ally[key]-previous} {key.upper()} to {ally['name']}."
        elif effect == "ward":
            self.wards[index] = max(power, self.wards.get(index, 0))
            self.message = f"{ability.name} protects {ally['name']}."
        elif effect == "mark":
            self.marks[self.target] = power
            self.message = f"{ability.name} exposes {self.enemy.name}."
        elif effect == "steal":
            self.steal_attempts.add(self.target)
            enhanced = worn_id(member, "weapon") == "pickpocket_dirk"
            take = roll_steal(self.enemy.loot, self.loot_rng, enhanced)
            self.stolen.update(take)
            gains = ", ".join(item_gain_text(loot_name(key), count) for key, count in take.items())
            self.message = f"Stole {gains}." if gains else "Steal missed."
        if ability.id in PLAYER_AILMENTS and self.damage > 0:
            status,chance=PLAYER_AILMENTS[ability.id]
            self.apply_status(("enemy",self.target),status,chance)
        self.kit_lesson_rider(ability, member)
        if ability.id == "saint_mend":
            self.statuses.remove(("party",index),"poison")
        elif ability.id == "saint_litany":
            self.statuses.cure(("party",index))
            self.message += " Ailments cleansed."
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

    def reply(self, attacker=None):
        if not self.pending_reply or self.outcome:
            return
        first = next((i for i, hp in enumerate(self.health) if hp), 0) if attacker is None else attacker
        if self.kit_preempt(first):
            return
        before = [member["hp"] for member in self.party]
        self.kit_notes = []
        self.critical_hits.clear()
        self._reply(attacker)
        self._kit_incoming_magic = False
        if self.critical_hits:
            self.message = f"Critical hit! {self.message}"
        self._flush_notes()
        for member, hp in zip(self.party, before):
            loss = hp - member["hp"]
            if loss > 0 and member["hp"] > 0:
                maximum = stat_value(member, "max_hp", hp)
                add_charge(member, min(20, 8 + 30 * loss // maximum))

    def _reply(self, attacker=None):
        self.pending_reply = False
        self.attacker = next(i for i, hp in enumerate(self.health) if hp) if attacker is None else attacker
        foe = self.enemies[self.attacker]
        skill = self.next_enemy_skill(self.attacker)
        self.enemy_turns[self.attacker] += 1
        self.enemy_skill = skill
        if skill:self.enemy_mp[self.attacker] -= skill.mp
        self.action_rank=skill.rank if skill else 3
        record_observation(self.party,skill.name if skill else {"bites":"Bite","swoops":"Echo Swoop","rams":"Rock Ram"}.get(foe.move,foe.move))
        living=[i for i,p in enumerate(self.party) if p["hp"]>0]
        self.defender=living[self.rng.randrange(len(living))] if len(living)>1 else living[0]
        magical=skill is not None and skill.magic
        self._kit_incoming_magic=magical
        damage=max(1,foe.magic*2+2) if magical else self.rng.randint(*foe.attack)
        reduction=max(self.wards.get(self.defender,0),50 if self.defender in self.guarded else 0)
        damage=max(1,damage*(100-reduction)//100)
        if self.ctb is None:self.guarded.clear();self.wards.clear()
        target=self.party[self.defender]
        damage=max(1,damage-stat_value(target,"magic_defense" if magical else "defense"))
        missed=not magical and self._misses_in_darkness(("enemy",self.attacker),("party",self.defender))
        if missed:damage=0
        if damage and not magical:
            self.statuses.remove(("party", self.defender), "frozen")
            damage = self._roll_critical(damage, ("enemy", self.attacker), ("party", self.defender))
        damage = self._take_party_damage(self.defender, damage,
                                         fire_damage=damage if skill and skill.element == "fire" else 0)
        if self._kit_redirect:
            self.defender, damage = self._kit_redirect
            target = self.party[self.defender]
        self.hits={self.defender:damage};self.damage=damage;self.effect="enemy"
        name=skill.name if skill else foe.name
        self.message=f"{name} misses in the darkness." if missed else f"{name} hits {target['name']} for {damage}!"
        if skill and skill.status and damage:self.apply_status(("party",self.defender),skill.status,skill.chance)
        self._check_outcome()
        if not self.outcome:self.actor=next(i for i,p in enumerate(self.party) if p["hp"]>0)


class DenMotherBattle(BattleModel):
    """A staged brood fight with two CTB slots reserved for summons."""

    SPIN_WEB = EnemySkill("Spin Web", "seer_mist_ray", rank=3)
    FANG_STRIKE = EnemySkill("Fang Strike", "sollers_venom_edge", rank=3)
    BROOD_CALL = EnemySkill("Brood Call", "unbound_quarry_echo")
    SILK_SHROUD = EnemySkill("Silk Shroud", "seer_mist_ray")
    FEAST = EnemySkill("Feast", "sollers_venom_edge")
    VENOM_SPRAY = EnemySkill("Venom Spray", "sollers_smoke_spark")
    LAST_BROOD = EnemySkill("Last Brood", "seer_mind_flare")
    DEATH_TELL = EnemySkill("Death Embrace (windup)", "seer_mind_flare")
    DEATH_EMBRACE = EnemySkill("Death Embrace", "unbound_quarry_echo", rank=5)
    WEB_SHOT = EnemySkill("Web Shot", "seer_mist_ray", rank=3)
    NIBBLE = EnemySkill("Nibble", "sollers_venom_edge", rank=3)
    EMBRACE_DAMAGE = 72
    FEAST_DAMAGE = 37
    ENRAGED_DAMAGE_PERCENT = 150

    def __init__(self, hp=MAX_HP, potions=MAX_POTIONS, **kwargs):
        super().__init__(DEN_MOTHER, hp, potions, **kwargs)
        self.enemies.extend((SPIDERLING, SPIDERLING))
        self.health.extend((0, 0))
        self.enemy_turns.extend((0, 0))
        self.enemy_mp.extend((0, 0))
        self.stage = 1
        self.announced_stage = 1
        self.brood_calls = set()
        self.brood_consumed = ()
        self.shroud_at = -4
        self.embrace_at = -3
        self.embrace_target = None
        self.fury_at = -4

    def _hit_target(self, damage, physical=False, element=None, *, include_mark=True, can_crit=False):
        super()._hit_target(damage, physical, element, include_mark=include_mark, can_crit=can_crit)
        if self.health[0] * 4 < DEN_MOTHER.hp:
            self.stage = 3
        elif self.health[0] * 100 <= DEN_MOTHER.hp * 60:
            self.stage = max(self.stage, 2)
        if (self.target == 0 and self.health[0] > 0 and element == "fire" and self.stage == 3
                and self.enemy_turns[0] - self.fury_at >= 4):
            self.fury_at = self.enemy_turns[0]

    @property
    def furious(self):
        return self.enemy_turns[0] - self.fury_at < 3

    def _living_party(self):
        return [i for i, ally in enumerate(self.party) if ally["hp"] > 0]

    def _webbed(self):
        return [i for i in self._living_party() if self.statuses.has(("party", i), "webbed")]

    def next_enemy_skill(self, index):
        webbed = self._webbed()
        if index:
            return self.NIBBLE if webbed or self.enemy_turns[index] else self.WEB_SHOT
        turn = self.enemy_turns[0]
        if self.embrace_target is not None:
            return self.DEATH_EMBRACE if self.embrace_target in webbed else self.FANG_STRIKE
        if self.stage == 3:
            if self.announced_stage < 3 and any(self.health[1:]):
                return self.LAST_BROOD
            if webbed and turn - self.embrace_at >= 3 and not self.furious:
                return self.DEATH_TELL
        if self.stage == 2 and turn - self.shroud_at >= 4:
            return self.SILK_SHROUD
        if self.stage < 3 and self.stage not in self.brood_calls and not all(self.health[1:]) and turn:
            return self.BROOD_CALL
        if self.stage >= 2 and webbed:
            return self.FEAST
        if not self.furious and len(webbed) < len(self._living_party()) and turn % 3 == 0:
            return self.SPIN_WEB
        if self.stage == 2 and not webbed:
            return self.VENOM_SPRAY
        return self.FANG_STRIKE

    def enemy_intent(self, index):
        if index == 0 and self.embrace_target in self._webbed():
            return f"Death Embrace → {self.party[self.embrace_target]['name']}"
        skill = self.next_enemy_skill(index)
        return skill.name if skill else "Defend"

    def _summon(self):
        for i in range(1, len(self.enemies)):
            if self.health[i] == 0:
                self.health[i] = SPIDERLING.hp
                self.enemy_turns[i] = 0
                if self.ctb is not None:
                    key = ("enemy", i)
                    self.ctb.ready[key] = self.ctb.tick + recovery(self.ctb.agility[key])

    def _damage_ally(self, index, damage):
        key = ("party", index)
        ally = self.party[index]
        if self._misses_in_darkness(("enemy", self.attacker), key):
            return 0
        reduction = max(self.wards.get(index, 0), 50 if index in self.guarded else 0)
        damage = max(1, damage - stat_value(ally, "defense"))
        damage = max(1, damage * (100 - reduction) // 100)
        if self.attacker:
            damage = self._roll_critical(damage, ("enemy", self.attacker), key)
        damage = self._take_party_damage(index, damage, clip=True)
        self.statuses.remove(key, "frozen")
        self.hits[index] = damage
        return damage

    def _reply(self, attacker=None):
        self.pending_reply = False
        self.attacker = 0 if attacker is None else attacker
        skill = self.enemy_skill = self.next_enemy_skill(self.attacker)
        furious = self.furious
        turn = self.enemy_turns[self.attacker]
        self.enemy_turns[self.attacker] += 1
        self.action_rank = skill.rank if skill else 2
        self.effect, self.hits, self.damage = "enemy", {}, 0
        living, webbed = self._living_party(), self._webbed()
        unwebbed = [i for i in living if i not in webbed]
        self.defender = living[0]
        self.message = f"{skill.name}!" if skill else "The Spiderling crouches and waits."
        if skill:
            record_observation(self.party, skill.name)

        if skill in (self.SPIN_WEB, self.WEB_SHOT):
            self.defender = max(unwebbed, key=lambda i: stat_value(self.party[i], "agility", RETRI["agility"]))
            self.message = f"{skill.name} targets {self.party[self.defender]['name']}."
            self.apply_status(("party", self.defender), "webbed", turns=1 if skill == self.WEB_SHOT else None)
        elif skill == self.BROOD_CALL:
            self._summon()
            self.brood_calls.add(self.stage)
            self.message = "Brood Call! Spiderlings scuttle into the den."
        elif skill == self.SILK_SHROUD:
            self.shroud_at = turn
            caught = []
            for i in unwebbed:
                if self.apply_status(("party", i), "webbed", .65):
                    self.defender = i
                    caught.append(self.party[i]["name"])
            self.message = f"Silk Shroud snares {' and '.join(caught)}!" if caught else "The party weathers Silk Shroud."
        elif skill == self.LAST_BROOD:
            self.brood_consumed = tuple(i for i, hp in enumerate(self.health) if i and hp > 0)
            self.health[1:] = [0, 0]
            healed = min(DEN_MOTHER.hp - self.health[0], len(self.brood_consumed) * math.ceil(DEN_MOTHER.hp * .05))
            self.health[0] += healed
            self.message = f"Last Brood restores {healed} HP. Den Mother grows stronger!"
        elif skill == self.DEATH_TELL:
            self.embrace_at = turn
            self.defender = self.embrace_target = webbed[0]
            self.message = f"Death Embrace looms over {self.party[self.defender]['name']}. Guard or clear the web!"
        elif skill == self.VENOM_SPRAY:
            poisoned = []
            for i in living:
                if self._damage_ally(i, 17) and self.apply_status(("party", i), "poison", .40):
                    poisoned.append(self.party[i]["name"])
            self.message = "Venom Spray washes over the party!"
            if poisoned:
                self.message += f" {' and '.join(poisoned)} poisoned!"
        elif skill is not None:
            target = (self.embrace_target if skill == self.DEATH_EMBRACE else
                      webbed[0] if webbed and skill in (self.FEAST, self.NIBBLE) else self.rng.choice(living))
            self.defender = target
            base = {self.DEATH_EMBRACE: self.EMBRACE_DAMAGE, self.FEAST: self.FEAST_DAMAGE}.get(skill)
            if base is None:
                base = self.rng.randint(*self.enemies[self.attacker].attack)
            if self.attacker == 0 and (furious or self.brood_consumed):
                base = base * self.ENRAGED_DAMAGE_PERCENT // 100
            self.damage = self._damage_ally(target, base)
            name = self.party[target]["name"]
            self.message = (f"{skill.name} hits {name} for {self.damage}!" if self.damage
                            else f"{skill.name} misses {name} in the darkness.")
            if self.damage and skill == self.FANG_STRIKE:
                self.apply_status(("party", target), "poison", .30)
            elif self.damage and skill == self.FEAST:
                healed = min(DEN_MOTHER.hp - self.health[0], self.damage // 2)
                self.health[0] += healed
                self.message += f" Den Mother regains {healed} HP."
        if self.attacker == 0:
            if skill != self.DEATH_TELL:
                self.embrace_target = None
            if self.stage > self.announced_stage:
                shift = "Her eyes gleam." if self.stage == 2 else "Den Mother shrieks!"
                self.message = f"{shift} {self.message}"
                self.announced_stage = self.stage
            if furious and turn == self.fury_at:
                self.message = f"Burn the Nest enrages her! {self.message}"
        self._check_outcome()


class EmberWyvernBattle(BattleModel):
    """The mountain spirit's binding gives way as the Wyvern loses HP."""

    HEAT_TURNS = 5
    SCORCH_PERCENT = 7
    BREATH_PERCENT = 65

    def __init__(self, **kwargs):
        super().__init__(EMBER_WYVERN, **kwargs)
        self.stage = 1
        self.heat_turns = 0
        self.bites_until_inhale = 2
        self.breath_waiting = None
        self.last_move = None
        self.scorch_event = None

    def advance_phase(self):
        if self.outcome or not self.enemy_hp or self.stage == 3:
            return False
        if 3 * self.enemy_hp > (3 - self.stage) * self.enemy.hp:
            return False
        self.stage += 1
        if self.stage == 3:
            self.heat_turns = self.HEAT_TURNS
        return True

    def enemy_element_percent(self, element):
        if self.stage == 3 and element in ("water", "ice"):
            return 150
        return super().enemy_element_percent(element)

    def enemy_intent(self, index):
        if self.breath_waiting is not None:
            return "Fire Breath · Guard!"
        if self.stage >= 2 and self.bites_until_inhale == 0:
            return "Deep Inhale"
        return "Fire Bite"

    def resolve_turn_end(self):
        queue = self.ctb
        if queue is None or self._status_end_serial == queue.completed:
            return []
        key = queue.current
        events = super().resolve_turn_end()
        self.scorch_event = None
        if self.outcome or key is None:
            return events
        side, index = key
        if side == "party":
            if self.breath_waiting is not None:
                self.breath_waiting.discard(index)
            if self.stage == 3 and self._ctb_alive(key):
                maximum = stat_value(self.party[index], "max_hp")
                fire = max(1, (maximum * self.SCORCH_PERCENT + 50) // 100)
                loss = self._take_party_damage(index, fire, clip=True, incoming=False, fire_damage=fire)
                if loss:
                    self.scorch_event = (key, loss)
                    events.append(self.scorch_event)
                    self.message += f" Scorched Ground burns {self.party[index]['name']} for {loss}."
                    self._check_outcome()
        elif self.heat_turns:
            self.heat_turns -= 1
        return events

    def finish_ctb_turn(self):
        self.resolve_turn_end()
        while self.advance_phase():
            pass
        return super().finish_ctb_turn()

    def reply(self, attacker=None):
        self.last_move = None
        super().reply(attacker)

    def _reply(self, attacker=None):
        self.pending_reply = False
        self.attacker = 0
        self.enemy_turns[0] += 1
        self.enemy_skill = None
        self.effect = "enemy"
        self.hits = {}
        self.damage = 0
        living = [index for index, member in enumerate(self.party) if member["hp"] > 0]
        self.defender = living[0]
        if self.breath_waiting is not None and not self.breath_waiting.intersection(living):
            self._fire_breath(living)
        elif self.stage >= 2 and self.bites_until_inhale == 0:
            self.message = "The Wyvern holds its breath... Guard!"
            if self.breath_waiting is None:
                self.breath_waiting = set(living) if self.ctb is not None else set()
                self.message = "The beast inhales deeply... Guard against Fire Breath!"
            self.last_move = "inhale"
            self.action_rank = 4
        else:
            self._fire_bite(living)
            if self.stage >= 2:
                self.bites_until_inhale -= 1
        if self.ctb is None:
            self.guarded.clear()
            self.wards.clear()
        self._check_outcome()

    def _attack_roll(self):
        damage = self.rng.randint(*self.enemy.attack)
        return damage * 3 // 2 if self.heat_turns else damage

    def _guarded_damage(self, index, damage):
        reduction = max(self.wards.get(index, 0), 50 if index in self.guarded else 0)
        return damage * max(0, 100 - reduction) // 100

    def _fire_bite(self, living):
        self.last_move = "bite"
        self.action_rank = 3
        self.defender = index = living[0] if len(living) == 1 else self.rng.choice(living)
        record_observation(self.party, "Fire Bite")
        key = ("party", index)
        if self._misses_in_darkness(("enemy", 0), key):
            self.message = "Fire Bite misses in the darkness."
            return
        bite = self._attack_roll()
        defense = stat_value(self.party[index], "defense")
        if self.statuses.has(key, "sundered"):
            defense = max(0, defense - 2)
        fire = self._guarded_damage(index, bite // 2)
        physical = self._guarded_damage(index, max(1, math.ceil(bite / 2) - defense))
        physical = self._roll_critical(physical, ("enemy", 0), key)
        damage = self._take_party_damage(index, physical + fire, fire_damage=fire)
        if self._kit_redirect:
            self.defender, damage = self._kit_redirect
        self.damage = self.hits[self.defender] = damage
        self.message = f"Fire Bite hits {self.party[self.defender]['name']} for {damage}!"
        if damage and self.status_rng.random() < .30:
            self.apply_status(("party", self.defender), "sundered", turns=2)

    def _fire_breath(self, living):
        self.last_move = "breath"
        self.action_rank = 4
        self.breath_waiting = None
        self.bites_until_inhale = 2
        self._kit_incoming_magic = True
        record_observation(self.party, "Fire Breath")
        fire = math.ceil(self._attack_roll() * self.BREATH_PERCENT / 100)
        for index in living:
            damage = self._guarded_damage(index, fire)
            self.hits[index] = self._take_party_damage(index, damage, fire_damage=damage, single_target=False)
        self.damage = sum(self.hits.values())
        self.message = "Fire Breath sweeps across the party!"


class ShalehornBattle(BattleModel):
    """One telegraphed move per party round."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.move_index = 0
        self.mark = self.actor
        self.exposed = False
        self.buried = False
        self.boss_move = None

    def tell(self):
        return (f"Stonebreaker Charge aims at {self.party[self.mark]['name']}. Guard!",
                "Its flank is exposed! Tremor incoming." if self.exposed else "Its foreclaws rise. Tremor incoming.",
                "Shalehorn digs at the shale.", "Underground! Brace for its return.")[self.move_index]

    def command(self, action, target=None, ability_id=None):
        if action == "Attack" and self.buried and not self.pending_reply and not self.outcome and not self.statuses.has(("party",self.actor),"frozen") and (self.ctb is None or self.ctb.current == ("party",self.actor)):
            self.damage = 0
            self.critical_hits.clear()
            self.effect = "miss"
            self.pending_reply = True
            self.action_rank = 3
            self.healed = {}
            self.message = "Your strike finds only loose shale."
            return True
        accepted = super().command(action, target=target, ability_id=ability_id)
        if accepted and action == "Attack" and self.exposed:
            self.enemy_hp = max(0, self.enemy_hp - self.damage)
            self.damage *= 2
            if self.damage:
                hit = "Critical hit! " if self.critical_hits else ""
                self.message = f"{hit}Fractured armor! {self.damage} damage."
            if self.enemy_hp == 0:
                self.outcome, self.pending_reply = "victory", False
                self.collect_kill_drops()
        return accepted

    def _reply(self, attacker=None):
        self.pending_reply = False
        self.attacker = 0
        self.enemy_skill = None
        self.boss_move = ("charge","tremor","burrow","eruption")[self.move_index]
        living = [i for i, p in enumerate(self.party) if p["hp"]]
        self.exposed = False
        if self.mark not in living:
            self.mark = living[0]
        if self.move_index == 0:
            record_observation(self.party, "Stonebreaker Charge")
            self.exposed = self.mark in self.guarded
            self.hits = {self.mark: 0 if self.exposed else 22}
            self.message = ("Charge misses! Its flank cracks against the wall." if self.exposed
                            else "Stonebreaker Charge!")
        elif self.move_index == 1:
            record_observation(self.party, "Quarry Tremor")
            self.hits = {i: 5 if i in self.guarded else 10 for i in living}
            self.message = "Quarry Tremor!"
        elif self.move_index == 2:
            record_observation(self.party, "Burrow")
            self.buried = True
            self.hits = {}
            self.message = "Shalehorn burrows beneath the floor."
        else:
            record_observation(self.party, "Shalehorn Eruption")
            self.buried = False
            target = self.rng.choice(living)
            self.hits = {target: 6 if target in self.guarded else 12}
            self.message = "Shalehorn erupts from the stone!"
        self.effect = "tremor" if self.move_index == 1 else "enemy"
        for i, amount in self.hits.items():
            ward = self.wards.get(i, 0)
            if ward and amount:
                baseline = 50 if i in self.guarded and self.move_index in (1, 3) else 0
                if ward > baseline:
                    amount = max(1, amount * (100 - ward) // (100 - baseline))
            # Boss moves already have tuned damage; apply equipment defense
            # without changing their existing unarmed balance or a missed hit.
            amount = max(1, amount - stat_bonus(self.party[i], "defense")) if amount else 0
            if amount and self.move_index != 1 and self._misses_in_darkness(("enemy",0),("party",i)):
                amount=0;self.hits[i]=0
            if amount:self.statuses.remove(("party",i),"frozen")
            self.hits[i] = self._take_party_damage(i, amount)
            if amount and self.move_index == 1:self.apply_status(("party",i),"darkness",.35)
        self.defender = next(iter(self.hits), living[0])
        self.damage = self.hits.get(self.defender, 0)
        self.hp = self.party[0]["hp"]
        if self.ctb is None:
            self.guarded.clear()
            self.wards.clear()
        self._check_outcome()
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
    COMMANDS = ("Attack", "Guard", "Items", "Flee", "Abilities", "Magic")
    CRESCENDO_BADGE = (29, 384, 181, 403)

    def __init__(self, canvas, font, assets: Path, portrait=None):
        self.canvas, self.font = canvas, font
        self.portrait = portrait
        self.member_portrait = None
        self.reward_portraits = {}
        self._turn_icons = {}
        self.frozen_fx = FrozenOverlay(canvas, assets)
        self.poison_fx = PoisonOverlay(canvas, assets)
        self.darkness_silence_fx = DarknessSilenceFX(canvas)
        self.shalehorn_fx = ShalehornEffects(canvas)
        self.crescendo_fx = CrescendoFX(canvas)
        self.player_art = PlayerMotionArt(canvas, assets)
        self.webbed_sprite = bound_web(canvas, 2)
        self.enemy_frames = {}
        self.battle_assets = assets / "battle"
        self.brood_shades = None
        self.brood_silk = BroodSilk(canvas)
        for foe in ENEMY_ROSTER:
            if foe.sprite not in self.enemy_frames:
                self.enemy_frames[foe.sprite] = load_enemy_frames(canvas, self.battle_assets, foe)
        self.enemies = {file: frames[0] for file, frames in self.enemy_frames.items()}
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
            for name in ("Retri", "Temur") for job in OUTFIT_JOBS
        }
        self.class_poses = {
            (name, job, pose): tk.PhotoImage(master=canvas, file=str(
                assets / "battle" / "classes" / f"{name.lower()}-{job.lower()}-{pose}.png"
            )).zoom(2)
            for name in ("Retri", "Temur") for job in OUTFIT_JOBS for pose in ("guard", "fainted")
        }
        self.backdrop = tk.PhotoImage(master=canvas, file=str(assets / "battle" / "crystal-quarry.png"))
        self.backgrounds = [
            [tk.PhotoImage(master=canvas, file=str(assets / "battle" / pattern.format(i)))
             for i in range(3)]
            for pattern in ("crystal-glow-{}.png", "crystal-cave-2-glow-{}.png",
                            "crystal-cave-3-glow-{}.png")
        ]
        self.glow_frames = self.backgrounds[0]
        self.grassland_background = _field_backdrop(canvas, assets / "battle" / "sunrest-field.png")
        self.depths_backgrounds = tuple(
            tuple(tk.PhotoImage(master=canvas, file=str(assets / "battle" / pattern.format(i)))
                  for i in range(3))
            for pattern in ("depths-abandoned-adventurer-glow-{}.png",
                            "depths-abandoned-halberdier-glow-{}.png")
        )
        self.next_depths_background = 0
        self.background_rng = random.Random()
        self.background_bag = []
        self.background_index = None
        self.formation_mirrored = False
        self.wyvern_art = None
        self.wyvern_floor_item = None
        self.model = None
        self.level_roster = None
        self.ability_menu = False
        self.chosen_ability = None
        self.link_first = None
        self.attack_fx = None
        self.player_motion = None
        self._actor_frame = None
        self._bow_target_hp = None
        self.fx_variant = None
        self._enemy_variant = None
        self._fx_images = {}
        self._heal_images = {}
        self._supply_icons = {}
        self.ability_page = "Abilities"
        self._fx_item = None
        self._camera_offset = (0, 0)

    def start(self, model, now, *, outdoors=False, in_depths=False):
        self.crescendo_fx.clear(self)
        self.shalehorn_fx.clear()
        self.darkness_silence_fx.clear(self)
        self.frozen_fx.clear()
        self.wyvern_floor_item = None
        if isinstance(model, EmberWyvernBattle):
            self.glow_frames = self.backgrounds[2]
            if self.wyvern_art is None:
                self.wyvern_art = EmberWyvernArt(self.canvas, self.battle_assets, self.enemies[EMBER_WYVERN.sprite])
        elif outdoors:
            self.glow_frames = [self.grassland_background] * 3
        elif in_depths or isinstance(model, DenMotherBattle):
            if isinstance(model, DenMotherBattle):
                index = 0
            else:
                index = self.next_depths_background
                self.next_depths_background = (index + 1) % len(self.depths_backgrounds)
            self.glow_frames = self.depths_backgrounds[index]
        else:
            if not self.background_bag:
                self.background_bag = list(range(len(self.backgrounds)))
                self.background_rng.shuffle(self.background_bag)
                if self.background_index is not None and self.background_bag[-1] == self.background_index:
                    self.background_bag[0], self.background_bag[-1] = self.background_bag[-1], self.background_bag[0]
            self.background_index = self.background_bag.pop()
            self.glow_frames = self.backgrounds[self.background_index]
        self.model = model
        self.poison_fx.begin(model)
        model.begin_ctb()
        self.loot_pages = []
        self.loot_page = 0
        self.selection = 0
        self.item_menu = False
        self.ability_menu = False
        self.ability_page = "Abilities"
        self.crescendo_return_selection = 0
        self.chosen_ability = None
        self.link_first = None
        self.attack_fx = None
        self.player_motion = None
        self._actor_frame = None
        self._bow_target_hp = None
        self.fx_variant = None
        self._enemy_variant = None
        self._fx_item = None
        self._camera_offset = (0, 0)
        self.ally_target = 0
        self.phase = "command"
        self.held = None
        self.repeat_at = 0.0
        self.phase_at = now
        self.canvas.create_rectangle(0, 0, 960, 540, fill="#08090c", outline="", tags=self.TAG)
        self._draw_battlefield(now, outdoors=outdoors)
        self._frame(18, FIELD_HEIGHT, 942, 382)
        self._frame(18, 394, 296, 526)
        self._frame(308, 394, 516, 526)
        self._frame(526, 394, 942, 526)
        self._begin_ctb_actor(now)
        self.draw_status()

    def _draw_battlefield(self, now, *, outdoors=False):
        c, model = self.canvas, self.model
        self.glow_started = now
        self.glow_index = 0
        self.backdrop_item = c.create_image(0, 0, image=self.glow_frames[0], anchor="nw", tags=self.TAG)
        wyvern = isinstance(model, EmberWyvernBattle)
        if isinstance(model, DenMotherBattle):
            self.enemy_positions = [(230, 177), (363, 140), (373, 243)]
        elif isinstance(model, ShalehornBattle):
            self.enemy_positions = [(270, 190)]
        elif wyvern:
            pose = self.wyvern_art.pose(model.stage)
            self.enemy_positions = [(270, WYVERN_GROUND - pose.height() // 2)]
            self.wyvern_floor_item = c.create_image(0, 0, image=self.wyvern_art.scorched_floor,
                                                   anchor="nw", state="hidden", tags=self.TAG)
        else:
            self.enemy_positions = _field_enemy_positions(model.enemies, self.enemies, self.formation_mirrored)
            if len(model.enemies) > 1:
                self.formation_mirrored = not self.formation_mirrored
        self.enemy_poses = [pose] if wyvern else [self.enemies[foe.sprite] for foe in model.enemies]
        self.enemy_items = [c.create_image(x, y, image=image, tags=self.TAG,
                                           state="normal" if hp > 0 else "hidden")
                            for (x, y), image, hp in zip(self.enemy_positions, self.enemy_poses, model.health)]
        self.enemy_stances = tuple(self.enemy_positions)
        self.enemy_item = self.enemy_items[0]
        if wyvern and model.stage == 1:
            self.wyvern_art.rubble(270, WYVERN_GROUND, (self.TAG, "wyvern_rubble"))
        if wyvern and model.stage == 3:
            c.itemconfigure(self.wyvern_floor_item, state="normal")
        sprites = {"Retri": self.hero, "Temur": self.temur}
        self.party_sprites = [
            self.class_sprites.get((p["name"], current_job(p)), sprites.get(p["name"]))
            for p in model.party
        ]
        if outdoors:
            self.party_positions = [
                ((44 + 4 * i) * FIELD_GRID,
                 _center_y_on_ground(image if image is not None else self.hero,
                                     (18 - 3 * (i % 2)) * FIELD_GRID))
                for i, image in enumerate(self.party_sprites)
            ]
        else:
            self.party_positions = [(738 + 36*i, 255 - 66*i) for i in range(len(model.party))]
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

    def _sync_party_sprites(self, hp_before_preview=None):
        """Show guarding and critical HP on the same ground line as the class pose."""
        for i, member in enumerate(self.model.party):
            hp = member["hp"] if hp_before_preview is None else hp_before_preview[i]
            fainted = hp <= 0
            if fainted:
                pose = "fainted"
            elif i in self.model.guarded:
                pose = "guard"
            elif hp * 4 <= stat_value(member, "max_hp"):
                pose = "critical"
            else:
                pose = "standing"
            if self.party_pose[i] == pose:
                continue
            self.party_pose[i], self.party_fainted[i] = pose, fainted
            item = self.party_items[i]
            if self.party_sprites[i] is None:
                suffix = {"fainted": " (KO)", "guard": " (GUARD)", "critical": " (LOW HP)"}.get(pose, "")
                self.canvas.itemconfigure(item, text=member["name"] + suffix,
                                          fill="#e99898" if fainted else "#ffffff")
            else:
                self.canvas.itemconfigure(item, image=self.party_image(i))
            self.canvas.coords(item, *self._party_position(i))

    def party_image(self, index):
        pose = self.party_pose[index]
        member = self.model.party[index]
        base = self.party_sprites[index]
        if self._actor_frame is not None and index == self.model.actor and pose != "fainted":
            return self._actor_frame
        if pose == "critical":
            return self.player_art.frame(member, "critical") or base
        images = self.fainted_sprites if pose == "fainted" else self.guard_sprites if pose == "guard" else {}
        return self.class_poses.get((member["name"], current_job(member), pose), images.get(member["name"], base))

    def _draw_actor_motion(self, elapsed_ms, release_ms):
        if self.player_motion is None:
            return
        actor = self.model.actor
        if self.party_sprites[actor] is None:
            return
        column = self.player_motion.column(elapsed_ms, release_ms)
        frame = (self.player_art.frame(self.model.party[actor], self.player_motion.style, column)
                 if column is not None else None)
        if frame is not self._actor_frame:
            self._actor_frame = frame
            self.canvas.itemconfigure(self.party_items[actor], image=self.party_image(actor))

    def _motion_timing(self, variant):
        if self.player_motion is None:
            return 0, 0
        return self.player_motion.timing(variant.contact_ms if variant else 0)

    @property
    def _uses_bow(self):
        return self.player_motion is not None and self.player_motion.style == "bow"

    def _party_position(self, index):
        x, y = self.party_positions[index]
        # The faint artwork's feet sit four native pixels above the standing baseline.
        if self.party_fainted[index] and self.model.party[index]["name"] in self.fainted_sprites:
            y += 8
        return x, y

    def _frame(self, x1, y1, x2, y2):
        c = self.canvas
        c.create_rectangle(x1, y1, x2, y2, fill="#727980", outline="", tags=(self.TAG, "battle_ui"))
        c.create_rectangle(x1+3, y1+3, x2-3, y2-3, fill="#f2f1df", outline="", tags=(self.TAG, "battle_ui"))
        c.create_rectangle(x1+8, y1+8, x2-8, y2-8, fill="#242181", outline="", tags=(self.TAG, "battle_ui"))

    def draw_status(self):
        c, m = self.canvas, self.model
        c.delete(self.DYNAMIC)
        c.delete("battle_turn_queue")
        c.delete("battle_status_labels")
        tags = (self.TAG, self.DYNAMIC, "battle_ui")
        if self.phase == "target":
            x, y = self.enemy_positions[m.target]
            width = self.enemies[m.enemy.sprite].width()
            c.create_text(x-max(48, width // 2 + 16), y, text="▶", fill="#ffffff", font=self.font(24, True),
                          tags=(*tags, "battle_target_indicator"))
        elif self.phase == "ally_target":
            x, y = self._party_position(self.ally_target)
            c.create_text(x-48, y, text="▶", fill="#ffffff", font=self.font(24, True),
                          tags=(*tags, "battle_target_indicator"))
        message=m.message
        windup = self.crescendo_fx.cue is not None and not self.crescendo_fx.impact_shown
        if windup:
            message = self.crescendo_fx.move.name + "!"
        elif self._bow_target_hp is not None:
            message = f"{m.party[m.actor]['name']} draws the bow."
        if isinstance(m,ShalehornBattle) and self.phase == "command" and not self.item_menu and not self.ability_menu:
            message=m.tell()
        if (isinstance(m, DenMotherBattle) and self.phase == "command"
                and not self.item_menu and not self.ability_menu and m.embrace_target in m._webbed()):
            message = f"Death Embrace looms over {m.party[m.embrace_target]['name']}."
        c.create_text(40, 350, text=message, anchor="w", width=872,
                      fill="#ffffff", font=self.font(18 if len(message)>64 else 23), tags=tags)
        names = m.item_names()
        commands = self.COMMANDS
        if self.ability_menu:
            commands = tuple(ability.name for ability in self._menu_abilities()) + ("Back",)
        elif self.item_menu:
            commands = tuple(f"{name} x{m.supply_count(name)}" for name in names) + ("Back",)
        start = min(max(0, self.selection - 2), max(0, len(commands) - 4)) if self.ability_menu or self.item_menu else 0
        visible = commands[start:start+4] if self.ability_menu or self.item_menu else commands
        for i, command in enumerate(visible, start):
            x, y = self._command_position(i)
            if self.item_menu and i < len(names):
                name = names[i]
                if name not in self._supply_icons:
                    path = supply_icon(name)
                    self._supply_icons[name] = (tk.PhotoImage(master=c, file=str(path)).subsample(2)
                                                if path is not None else None)
                draw_item_slot(c, 55, y, self._supply_icons[name], *tags, size=22)
            if i == self.selection and self.phase == "command":
                c.create_text(42 if self.item_menu else x-12, y, text="▶", anchor="e", fill="#ffffff",
                              font=self.font(16, True), tags=tags)
            c.create_text(x, y, text=command, anchor="w", font=self.font(19 if self.item_menu or self.ability_menu else 20),
                          fill="#ffe37e" if i == self.selection else "#ffffff", tags=tags)
        if self._crescendo_badge_visible():
            self._draw_crescendo_badge(tags)
        c.create_text(326, 425, text="ENEMY", anchor="w", fill="#80eaf5", font=self.font(17), tags=tags)
        den_boss = isinstance(m, DenMotherBattle) and m.target == 0
        c.create_text(326, 458, text=m.enemy.name + (f" · {chr(65+m.target)}" if len(m.enemies)>1 and not den_boss else ""), anchor="w", width=172,
                      fill="#ffffff", font=self.font(18), tags=tags)
        enemy_hp = self.crescendo_fx.starting_enemy_hp[m.target] if windup else m.enemy_hp
        if self._bow_target_hp is not None:
            enemy_hp = self._bow_target_hp
        c.create_text(326, 482, text=f"HP {enemy_hp}/{m.enemy.hp}", anchor="w",
                      fill="#ffffff", font=self.font(17), tags=tags)
        enemy_detail=m.statuses.label(("enemy",m.target)) or (f"Next: {m.enemy_intent(m.target)}" if not isinstance(m,ShalehornBattle) else "Watch its tell")
        if isinstance(m, EmberWyvernBattle):
            if m.breath_waiting is not None:
                enemy_detail = m.enemy_intent(0)
            c.create_rectangle(17, 13, 239, 53 if m.stage == 3 else 36, fill="#1e1624", outline="#785344", tags=tags)
            c.create_text(25, 25, text=WYVERN_PHASE_NAMES[m.stage - 1].upper(), anchor="w",
                          fill="#ffd090", font=self.font(16, True), tags=tags)
            if m.stage == 3:
                heat = f"  ·  HEAT {m.heat_turns}" if m.heat_turns else ""
                c.create_text(25, 43, text="SCORCHED GROUND" + heat, anchor="w", fill="#f0a16e", font=self.font(13), tags=tags)
        c.create_text(326, 503, text=enemy_detail, anchor="w", width=174, fill="#c8bf9e", font=self.font(11), tags=tags)
        if m.enemy.loot is not None and m.enemy.loot.rank != "Regular":
            c.create_text(490, 425, text="BOSS" if den_boss else m.enemy.loot.rank.upper(), anchor="e",
                          fill="#ffe37e", font=self.font(13, True), tags=tags)
        elif m.enemy.level > 1:
            c.create_text(490, 425, text=f"LV {m.enemy.level}", anchor="e",
                          fill="#ffe37e", font=self.font(13, True), tags=tags)
        for i, member in enumerate(m.party):
            y = 416 + i * 38
            active = m.ctb.current == ("party", i) and self.phase != "result"
            hp = self.crescendo_fx.starting_hp[i] if windup else member["hp"]
            mp = self.crescendo_fx.starting_mp[i] if windup else member.get("mp", 0)
            color = "#e99898" if hp <= 0 else "#ffe37e" if active else "#ffffff"
            if active and hp > 0:
                band = (*tags, "battle_active_party_row")
                c.create_rectangle(535, y-11, 933, y+22, fill="#393b92", outline="", tags=band)
                c.create_rectangle(535, y-11, 537, y+22, fill="#7772cc", outline="", tags=band)
            c.create_text(546, y, text=member["name"], anchor="w", fill=color, font=self.font(16), tags=tags)
            c.create_text(922, y, text=f"MP {mp}/{stat_value(member, 'max_mp')}", anchor="e",
                          fill="#80eaf5", font=self.font(15), tags=tags)
            hp_text = f"HP {hp} / {stat_value(member, 'max_hp')}" + (" KO" if hp <= 0 else "")
            c.create_text(800, y, text=hp_text, anchor="e", fill=color, font=self.font(16), tags=tags)
            if equipped_crescendo(member) is None:
                continue
            meter = charge(member) if hp > 0 else 0
            ready = meter >= MAX_CHARGE
            meter_tags = (*tags, "battle_crescendo")
            c.create_rectangle(546, y+12, 673, y+18, fill="#141439", outline="#655fa0", tags=meter_tags)
            if meter:
                c.create_rectangle(547, y+13, 547 + 125 * meter / MAX_CHARGE, y+17,
                                   fill="#ffc779" if ready else "#a996e8", outline="", tags=meter_tags)
        self._draw_turn_queue((self.TAG, "battle_turn_queue", "battle_ui"))
        self._draw_status_labels()
        if self.phase != "result":self.darkness_silence_fx.draw(self,self.phase_at)

    def _draw_crescendo_badge(self, tags):
        c = self.canvas
        x, y, right, bottom = self.CRESCENDO_BADGE
        tags = (*tags, "battle_crescendo_badge")
        c.create_polygon(x, y+5, x+5, y, right-6, y, right, y+6, right, bottom-3,
                         right-7, bottom, x+5, bottom, x, bottom-5,
                         fill="#452627", outline="#221922", tags=tags)
        c.create_polygon(x+2, y+6, x+6, y+2, right-7, y+2, right-2, y+7,
                         right-2, bottom-5, right-8, bottom-2, x+6, bottom-2, x+2, bottom-6,
                         fill="#934829", outline="#bd7948", tags=tags)
        c.create_line(x+7, y+3, right-8, y+3, fill="#f3bd79", tags=tags)
        c.create_line(x+7, bottom-3, right-9, bottom-3, fill="#743e2b", tags=tags)
        if not self.ability_menu:
            c.create_polygon(x+11, y+10, x+17, y+6, x+17, y+14, fill="#ffe5ab", tags=tags)
        c.create_text(x+28, y+10, text="CRESCENDO", anchor="w", fill="#fff0cb",
                      font=self.font(16, True), tags=tags)

    def _begin_ctb_actor(self, now):
        m = self.model
        if m.ctb.current is not None and m.statuses.has(m.ctb.current,"frozen"):
            m.skip_frozen_turn()
            self.phase,self.phase_at="frozen_action",now
            return
        if m.ctb.current is not None and m.ctb.current[0] == "enemy":
            m.action_rank = 3
            m.pending_reply = True
            m.reply(attacker=m.ctb.current[1])
            self._enemy_variant = None
            if isinstance(m, DenMotherBattle):
                if m.enemy_skill is m.LAST_BROOD:
                    self.phase, self.phase_at = "last_brood", now
                    self._sync_party_sprites()
                    return
                self._sync_brood()
            if m.enemy_skill:
                lesson_id=m.enemy_skill.animation
                lesson=next(x for entries in LESSONS.values() for x in entries if x.id==lesson_id)
                self._enemy_variant = RESEARCH_FX.get(lesson_id, {}).get(m.enemy_skill.palette)
                if self._enemy_variant is None:
                    self._enemy_variant = lesson_variant(lesson, {"job": "Seer", "attuned_stone": "first_stone"})
            self.phase, self.phase_at = "enemy_action", now
            if isinstance(m,ShalehornBattle):self.shalehorn_fx.start(self,now,m.boss_move)
            self._sync_party_sprites()
        else:
            self.phase = "command"
            self.held = None
            # Reset submenus on a new combatant's turn.
            self.item_menu = self.ability_menu = False
            self.ability_page = "Abilities"
            self.chosen_ability = None
            self.selection = 0
            self._sync_party_sprites()

    def _sync_brood(self):
        for index, item in enumerate(self.enemy_items):
            self.canvas.itemconfigure(item, state="normal" if self.model.health[index] else "hidden")
        if not self.model.enemy_hp:
            self.model.target = next((i for i, hp in enumerate(self.model.health) if hp), 0)

    def enemy_image(self, index):
        return self.enemy_poses[index]

    def _animate_last_brood(self, now):
        elapsed = now - self.phase_at
        if elapsed >= BROOD_DURATION:
            self.brood_silk.clear()
            self._sync_brood()
            self._end_action(now)
            return
        x, y = self.enemy_positions[0]
        sprite = self.enemy_image(0)
        dx, dy = self._camera_offset
        mouth = (x + dx + sprite.width() * .06, y + dy + sprite.height() * .18)
        brood = []
        for index in self.model.brood_consumed:
            source_x, source_y = self.enemy_positions[index]
            brood.append((self.enemy_items[index], self.enemy_image(index), (source_x + dx, source_y + dy)))
        self.brood_silk.draw(elapsed, self.enemy_items[0], mouth, brood)

    def _preview_rank(self):
        if self.chosen_ability is not None:
            return getattr(self.chosen_ability, "action_rank", 4)
        if self.item_menu and self.phase in ("command", "ally_target"):
            return 2
        if self.phase != "command":
            return self.model.action_rank
        if self.ability_menu:
            entries = self._menu_abilities()
            return getattr(entries[self.selection], "action_rank", 4) if self.selection < len(entries) else 3
        return 2 if self.COMMANDS[self.selection] in ("Guard", "Items") else 3

    def _draw_turn_queue(self, tags):
        c, m = self.canvas, self.model
        if m.ctb is None or self.phase == "result":
            return
        small_font = (self.font(11)[0], -9)
        c.create_text(924, 18, text=f"T{m.ctb.completed+1}", fill="#a8b6bd", font=small_font, tags=tags)
        for j, (side, index) in enumerate(m.ctb.preview(6, self._preview_rank())):
            y = 30 + j*32
            c.create_rectangle(908, y, 940, y+28, fill="#14202c",
                               outline="#c3a86d" if j==0 else "#35434e", tags=tags)
            if j == 0:
                c.create_text(901, y+14, text="▶", fill="#c3a86d", font=small_font, tags=tags)
            if side == "party":
                name = m.party[index]["name"]
                cache_key = (name, "compact")
                if cache_key not in self._turn_icons:
                    image = self.member_portrait(name) if self.member_portrait else self.party_sprites[index]
                    if image is not None:
                        self._turn_icons[cache_key] = image.subsample(max(1, math.ceil(max(image.width(),image.height())/24)))
                image = self._turn_icons.get(cache_key)
                if image is not None:
                    c.create_image(924, y+14, image=image, tags=tags)
                else:
                    c.create_text(924, y+14, text=name[:2], fill="#d4dce0", font=small_font, tags=tags)
            else:
                foe=m.enemies[index]
                boss = ((isinstance(m, DenMotherBattle) and index == 0) or
                        (foe.loot is not None and foe.loot.rank == "Boss"))
                c.create_text(924, y+14, text="BOSS" if boss else f"MON {chr(65+index)}",
                              fill="#c9ad87" if boss else "#c2b3aa", font=small_font, tags=tags)
            state=m.statuses.for_actor((side,index))
            if state:
                status="frozen" if "frozen" in state else next(iter(state))
                c.create_rectangle(908,y+8,910,y+20,fill=AILMENTS[status].color,outline="",tags=tags)

    def _draw_status_labels(self):
        c,m=self.canvas,self.model
        tags=(self.TAG,"battle_status_labels","battle_ui")
        for i,member in enumerate(m.party):
            label=m.statuses.label(("party",i))
            if label:c.create_text(570,434+i*38,text=label,anchor="w",fill="#cbd8dc",font=(self.font(11)[0],-9),tags=tags)

    def _draw_ailments(self, now):
        self.darkness_silence_fx.draw(self,now)
        self.poison_fx.draw(self,now)
        self.frozen_fx.draw(self,now)
        c = self.canvas
        c.delete("battle_webbed")
        for i, member in enumerate(self.model.party):
            if member["hp"] <= 0 or not self.model.statuses.has(("party", i), "webbed"):
                continue
            x, y = self._party_position(i)
            tags = (self.TAG, "battle_webbed")
            c.create_image(x, y+22, image=self.webbed_sprite, tags=tags)
        self.canvas.tag_raise(self.darkness_silence_fx.TAG)
        self._draw_night_magic(now)
        self.canvas.tag_raise("battle_ui")

    def _draw_night_magic(self, now):
        c, m = self.canvas, self.model
        tag = "night_magic"
        tags = (self.TAG, tag)
        c.delete(tag)
        dx, dy = self._camera_offset
        if m.black_thread:
            a, b, _ = m.black_thread
            x1, y1 = self.enemy_positions[a]
            x2, y2 = self.enemy_positions[b]
            x1, y1, x2, y2 = x1 + dx, y1 + dy + 14, x2 + dx, y2 + dy + 14
            middle = (x1 + x2) / 2, (y1 + y2) / 2 + 10
            c.create_line(x1, y1, *middle, x2, y2, fill="#271630", width=4, tags=tags)
            c.create_line(x1, y1, *middle, x2, y2, fill="#c4b2dc", width=1, dash=(4, 6), tags=tags)
        relic = m.reliquary
        release = self.phase == "status_tick" and m.reliquary_release
        if not relic and not release:
            return
        origin = relic.caster if relic else m.reliquary_origin
        x, y = self._party_position(origin)
        x, y = x + dx - 36, y + dy - 17
        if relic:
            c.create_polygon(x, y-11, x+10, y-4, x+7, y+10, x-7, y+10, x-10, y-4,
                             fill="#21152c", outline="#ad8fc8", width=2, tags=tags)
            cracks = min(3, (relic.stored + 3) // 4)
            for end, turn in (((x-7, y+8), (x-2, y+2)), ((x+8, y+4), (x+3, y-2)),
                              ((x-6, y-7), (x-4, y-1)))[:cracks]:
                c.create_line(x, y+1, *turn, *end, fill="#f0c6fa", width=1, tags=tags)
            c.create_text(x, y+22, text=f"{relic.stored} · {relic.phases}", fill="#e1c5e9",
                          font=self.font(11), tags=tags)
        elif release:
            t = min(1, (now - self.phase_at) / .85)
            color = "#f9ebff" if t < .3 else "#a988ca"
            radius = 6 + int(t * 30)
            for index in m.reliquary_release:
                ex, ey = self.enemy_positions[index]
                ex, ey = ex + dx, ey + dy
                px, py = x + (ex-x)*min(1, t*2.8), y + (ey-y)*min(1, t*2.8)
                c.create_line(x, y, (x+px)/2, (y+py)/2-12, px, py, fill=color, width=3, tags=tags)
                if t >= .35:
                    c.create_oval(ex-radius, ey-radius, ex+radius, ey+radius, outline=color, width=2, tags=tags)
            for ox, oy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
                sx, sy = x + ox * radius, y + oy * radius
                c.create_polygon(sx-4, sy, sx, sy-4, sx+4, sy, sx, sy+4, fill=color, tags=tags)

    def _end_action(self, now):
        if self.model.resolve_turn_end():
            self.phase,self.phase_at="status_tick",now
            self.draw_status()
            return
        self._finish_action(now)

    def _menu_abilities(self):
        member = self.model.party[self.model.actor]
        if self.ability_page == "Crescendo":
            move = self._ready_crescendo()
            return (move,) if move else ()
        entries = learned_abilities(member)
        def is_magic(ability):
            if isinstance(ability, Lesson):
                return ability.menu == "Magic"
            return ability.job in ("Saint", "Seer")
        return tuple(ability for ability in entries if is_magic(ability) == (self.ability_page == "Magic"))

    def _ready_crescendo(self):
        model = self.model
        member = model.party[model.actor]
        if (model.ctb.current == ("party", model.actor) and member["hp"] > 0
                and charge(member) >= MAX_CHARGE and model.outcome is None):
            return equipped_crescendo(member)
        return None

    def _crescendo_badge_visible(self):
        return (self.phase == "command" and not self.item_menu
                and (not self.ability_menu or self.ability_page == "Crescendo")
                and self._ready_crescendo() is not None)

    def _open_crescendo(self):
        self.crescendo_return_selection = self.selection
        self.ability_page = "Crescendo"
        self.ability_menu, self.selection = True, 0
        self.model.message = self._ready_crescendo().description
        self.draw_status()

    def _draw_healing(self, elapsed):
        c = self.canvas
        c.delete("battle_healing")
        if elapsed >= 0.65:
            return
        for i, amount in getattr(self.model, "healed", {}).items():
            x, y = self._party_position(i)
            dx, dy = self._camera_offset
            x, y = x + dx, y + dy
            # Tint the current character pose green without changing transparent pixels.
            if int(elapsed * 12) % 2 == 0:
                source = self.party_image(i)
                if source is not None:
                    key = str(source)
                    if key not in self._heal_images:
                        glow = tk.PhotoImage(master=c, width=source.width(), height=source.height())
                        for py in range(source.height()):
                            for px in range(source.width()):
                                if not source.transparency_get(px, py):
                                    r, g, b = source.get(px, py)
                                    glow.put("#%02x%02x%02x" % (r // 3, min(255, 150 + g // 2), b // 3), (px, py))
                        self._heal_images[key] = glow
                    c.create_image(x, y, image=self._heal_images[key], tags=(self.TAG, "battle_healing"))
            c.create_text(x, y-52-int(elapsed*25), text=f"+{amount} HP", fill="#65ff89",
                          font=self.font(24, True), tags=(self.TAG, "battle_healing"))

    def _command_position(self, index):
        if self.ability_menu and self.ability_page == "Crescendo":
            return 60, 432 + index * 36
        if self.ability_menu:
            count = len(self._menu_abilities()) + 1
            start = min(max(0, self.selection - 2), max(0, count - 4))
            return 60, 413 + (index - start) * 29
        if self.item_menu:
            count=len(self.model.item_names())+1
            start=min(max(0,self.selection-2),max(0,count-4))
            return 76, 413 + (index-start)*29
        return 53 + (index % 2) * 126, 419 + (index // 2) * 40

    def navigate(self, direction, now):
        if self.phase in ("target", "ally_target"):
            if direction not in ("up", "down", "left", "right"):
                self.held = None
            elif direction != self.held or now >= self.repeat_at:
                self.held, self.repeat_at = direction, now + 0.22
                step = -1 if direction in ("left", "up") else 1
                if self.phase == "ally_target":
                    self.ally_target = (self.ally_target + step) % len(self.model.party)
                    if self.chosen_ability is not None:
                        self.model.message = f"Choose who receives {self.chosen_ability.name}."
                    else:
                        self.model.message = f"Choose who receives the {self.model.item_names()[self.selection]}."
                else:
                    for _ in self.model.enemies:
                        self.model.target = (self.model.target + step) % len(self.model.enemies)
                        if self.model.enemy_hp and self.model.target != self.link_first:
                            break
                self.draw_status()
            return
        if self.phase != "command":
            return
        if direction not in ("up", "down", "left", "right"):
            self.held = None
            return
        pressed = direction != self.held
        if pressed:
            self.held = direction
            self.repeat_at = now
        if self.ability_menu and self.ability_page == "Crescendo" and direction in ("left", "right"):
            if direction == "right" and pressed:
                self.repeat_at = now + 0.22
                self._close_ability_menu()
            return
        if direction == "left" and not self.ability_menu and self._crescendo_badge_visible():
            if pressed:
                self._open_crescendo()
            return
        if now >= self.repeat_at:
            step = {"up": -2, "down": 2, "left": -1, "right": 1}[direction]
            if self.item_menu or self.ability_menu:
                step = -1 if direction in ("up", "left") else 1
                count = len(self.model.item_names()) + 1 if self.item_menu else len(self._menu_abilities()) + 1
                self.selection = (self.selection + step) % count
            else:
                row, column = divmod(self.selection, 2)
                if direction in ("up", "down"):
                    row = (row + (-1 if direction == "up" else 1)) % 3
                else:
                    column = 1 - column
                self.selection = row * 2 + column
            self.repeat_at = now + 0.22
            self.draw_status()

    def confirm(self, now):
        if self.phase == "result":
            if getattr(self, "loot_page", 0) < len(getattr(self, "loot_pages", ())):
                self._loot_summary(self.loot_pages[self.loot_page])
                self.loot_page += 1
                return None
            if self.model.outcome == "victory" and self.result_page + 1 < len(self.level_pages):
                self.result_page += 1
                self._level_up_page()
                return None
            return self.model.outcome
        if self.phase == "target":
            if self.chosen_ability is not None:
                if self.chosen_ability.target == "two enemies" and self.link_first is None:
                    self.link_first = self.model.target
                    self.model.target = next(i for i, hp in enumerate(self.model.health) if hp and i != self.link_first)
                    self.model.message = "Choose a second enemy for Black Thread."
                    self.draw_status()
                    return None
                self._begin_ability_fx(now)
                return None
            target_hp = self.model.enemy_hp
            if not self.model.command("Attack"):
                self.phase = "command"
                self.draw_status()
                return None
            member = self.model.party[self.model.actor]
            self.player_motion = action_motion(member)
            if self._uses_bow:
                self._bow_target_hp = target_hp
                self.attack_fx = None
            else:
                self.attack_fx = strike_variant(member)
            self.phase, self.phase_at = "hero_action", now
            self._draw_actor_motion(0, self._motion_timing(self.attack_fx)[1])
            self.draw_status()
            return None
        if self.phase == "ally_target":
            if self.chosen_ability is not None:
                self._begin_ability_fx(now)
                return None
            if self.model.command(self.model.item_names()[self.selection], target=self.ally_target):
                self._sync_party_sprites()
                self.item_menu, self.selection = False, 2
                self.phase, self.phase_at = "hero_action", now
            self.draw_status()
            return None
        if self.phase == "command":
            if self.ability_menu:
                self._confirm_ability(now)
                return None
            if not self.item_menu and self.COMMANDS[self.selection] in ('Abilities', 'Magic'):
                self.ability_page = self.COMMANDS[self.selection]
                self.ability_menu, self.selection = True, 0
                self.chosen_ability = None
                self.model.message = "Choose magic." if self.ability_page == "Magic" else "Choose an ability."
                self.draw_status()
                return None
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
            names = self.model.item_names()
            if self.item_menu and self.selection == len(names):
                self.item_menu, self.selection = False, 2
                self.draw_status()
                return None
            if self.item_menu:
                name = names[self.selection]
                if not self.model.supply_count(name):
                    self.model.message = f"No {name} left. Choose another action."
                else:
                    self.ally_target = self.model.actor
                    self.phase, self.held = "ally_target", None
                    self.model.message = f"Choose who receives the {name}."
                self.draw_status()
                return None
            action = self.COMMANDS[self.selection]
            if self.model.command(action):
                self._sync_party_sprites()
                self.phase = "hero_action"
                self.phase_at = now
            self.draw_status()
        return None

    def back(self):
        if self.phase == "ally_target":
            self.phase, self.held = "command", None
            if self.chosen_ability is not None:
                self.ability_menu, self.item_menu = True, False
                self.model.message = "Choose magic." if self.ability_page == "Magic" else "Choose an ability."
            else:
                self.item_menu = True
                self.model.message = "Choose an item."
            self.draw_status()
            return
        if self.phase == "target":
            self.phase = "command"
            self.link_first = None
            if self.chosen_ability is not None:
                self.ability_menu = True
                if self.ability_page == "Crescendo":
                    self.model.message = self.chosen_ability.description
                self.chosen_ability = None
            self.draw_status()
            return
        if self.phase == "command":
            if self.ability_menu:
                self._close_ability_menu()
                return
            elif self.item_menu:
                self.item_menu, self.selection = False, 2
            else:
                self.selection = 3
            self.draw_status()

    def _close_ability_menu(self):
        self.selection = self.crescendo_return_selection if self.ability_page == "Crescendo" else 0
        self.ability_page = "Abilities"
        self.ability_menu = False
        self.chosen_ability = None
        self.model.message = f"What will {self.model.party[self.model.actor]['name']} do?"
        self.draw_status()

    def _confirm_ability(self, now):
        entries = self._menu_abilities()
        if self.selection >= len(entries):
            self._close_ability_menu()
            return
        ability = entries[self.selection]
        if ability.target == "two enemies" and sum(hp > 0 for hp in self.model.health) < 2:
            self.model.message = "Black Thread needs two living enemies."
            self.draw_status()
            return
        self.chosen_ability = ability
        self.ability_menu = False
        if ability.target == "single ally":
            self.ally_target = self.model.actor
            self.phase, self.held = "ally_target", None
            self.model.message = f"Choose who receives {ability.name}."
            self.draw_status()
            return
        if ability.target in ("single enemy", "two enemies"):
            self.link_first = None
            self.model.target = next(i for i, hp in enumerate(self.model.health) if hp)
            self.phase, self.held = "target", None
            self.model.message = (f"Choose the first enemy for {ability.name}." if ability.target == "two enemies"
                                  else f"Choose a target for {ability.name}.")
            self.draw_status()
            return
        self._begin_ability_fx(now)

    def _begin_ability_fx(self, now):
        ability = self.chosen_ability
        accepted = ability is not None and self._cast_ability(ability, self.ally_target)
        self.link_first = None
        if not accepted:
            self.chosen_ability = None
            self.ability_menu = True
            self.phase = "command"
            self.draw_status()
            return
        self._ability_presented = self.ability_duration_ms > 0
        self.attack_fx = None
        self.chosen_ability = None
        self.phase = "ability_fx" if self._ability_presented else "hero_action"
        self.phase_at = now
        if self._ability_presented:
            self._draw_ability_frame(0)
        self.draw_status()

    @property
    def ability_duration_ms(self):
        if self.crescendo_fx.cue is not None:
            return self.crescendo_fx.duration_ms
        delay, release = self._motion_timing(self.fx_variant)
        effect_end = delay + (self.fx_variant.total_ms if self.fx_variant else 0)
        pose_end = release + self.player_motion.release_duration_ms if self.player_motion else 0
        healing_end = (self.ability_contact_ms + 430
                       if (self.fx_variant or self.player_motion) and self.model.healed else 0)
        return max(effect_end, pose_end, healing_end)

    @property
    def ability_contact_ms(self):
        return self._contact_ms(self.fx_variant)

    @property
    def attack_contact_ms(self):
        return self._contact_ms(self.attack_fx)

    def _contact_ms(self, variant):
        delay, _ = self._motion_timing(variant)
        if variant is not None:
            return delay + variant.contact_ms
        return delay + (self.player_motion.travel_ms if self.player_motion else 0)

    def _cast_ability(self, ability, ally_target):
        if isinstance(ability, Crescendo):
            return self.crescendo_fx.cast(self, ability)
        target_hp = self.model.enemy_hp
        target = (self.link_first, self.model.target) if ability.target == "two enemies" else ally_target
        if not self.model.command("Ability", target=target, ability_id=ability.id):
            return False
        member = self.model.party[self.model.actor]
        if isinstance(ability, Lesson):
            tag = ability.actor_motion
        else:
            tag = {"physical": "weapon", "physical+holy": "weapon",
                   "magic": "magic", "heal": "magic"}.get(ability.kind, "")
        self.player_motion = action_motion(member, tag)
        if self._uses_bow:
            self._bow_target_hp = target_hp
            self.fx_variant = None
        else:
            self.fx_variant = lesson_variant(ability, member)
        self.fx_on_enemy = ability.target not in ("party", "single ally")
        self.fx_ally = self.model.actor if ability.target == "party" else ally_target
        return True

    def _draw_ability_frame(self, elapsed_ms):
        if self.crescendo_fx.cue is not None:
            self.crescendo_fx.draw(self, elapsed_ms)
            return
        variant = self.fx_variant
        delay, release = self._motion_timing(variant)
        self._draw_actor_motion(elapsed_ms, release)
        if self._uses_bow:
            self._draw_bow_shot(elapsed_ms - release, self._fx_point())
        if elapsed_ms < delay:
            return
        hit = (elapsed_ms - self.ability_contact_ms) / 1000
        if variant is not None:
            self._animate_atmosphere(variant, elapsed_ms - delay)
        elif self.model.damage > 0 and hit >= 0:
            self._draw_ability_damage(hit)
        if hit >= 0:
            self._draw_healing(hit)
        if variant is not None:
            point = self._attack_fx_point(variant, elapsed_ms - delay, self._fx_point())
            self._show_fx(variant, elapsed_ms - delay, point)

    def _draw_bow_shot(self, elapsed_ms, target):
        c = self.canvas
        c.delete(BOW_SHOT_TAG)
        if elapsed_ms >= FLIGHT_MS and self._bow_target_hp is not None:
            self._bow_target_hp = None
            self.draw_status()
        x, y = self._party_position(self.model.actor)
        dx, dy = self._camera_offset
        draw_shot(c, (x + dx, y + dy), target, elapsed_ms, scale=2, tags=(self.TAG,))
        c.tag_raise("battle_ui")

    def _fx_point(self):
        if getattr(self, "fx_on_enemy", True):
            x, y = self.enemy_positions[self.model.target]
        else:
            x, y = self._party_position(self.fx_ally)
        dx, dy = self._camera_offset
        return x + dx, y + dy

    def _attack_fx_point(self, variant, elapsed_ms, target):
        if not variant.travel_ms or elapsed_ms >= variant.travel_ms:
            return target
        x, y = self._party_position(self.model.actor)
        dx, dy = self._camera_offset
        style = self.player_motion.style if self.player_motion else ""
        ox, oy = PROJECTILE_OFFSETS.get(style, (-24, -5))
        x, y = x + dx + ox, y + dy + oy
        travel = elapsed_ms / variant.travel_ms
        return x + (target[0]-x)*travel, y + (target[1]-y)*travel

    def _show_fx(self, variant, elapsed_ms, point):
        if variant is None:
            return
        path = variant.frames[frame_index(variant, elapsed_ms)]
        key = str(path)
        if key not in self._fx_images:
            image = tk.PhotoImage(master=self.canvas, file=key)
            if variant.scale > 1:
                image = image.zoom(variant.scale)
            self._fx_images[key] = image
        if self._fx_item is None:
            self._fx_item = self.canvas.create_image(
                point[0], point[1], image=self._fx_images[key], tags=(self.TAG, "battle_fx"))
        else:
            self.canvas.itemconfigure(self._fx_item, image=self._fx_images[key])
            self.canvas.coords(self._fx_item, *point)
        self.canvas.tag_raise("battle_ui")

    def _reset_camera(self):
        self.canvas.delete("battle_atmosphere")
        self.canvas.delete("ability_damage")
        if self._camera_offset != (0, 0):
            self._position_battlefield(0, 0)

    def _position_battlefield(self, dx, dy):
        old_x, old_y = self._camera_offset
        self._camera_offset = (dx, dy)
        self.canvas.coords(self.backdrop_item, dx, dy)
        if self.wyvern_floor_item is not None:
            self.canvas.coords(self.wyvern_floor_item, dx, dy)
            self.canvas.move("wyvern_rubble", dx - old_x, dy - old_y)
        for item, (x, y) in zip(self.enemy_items, self.enemy_positions):
            self.canvas.coords(item, x + dx, y + dy)
        for i, item in enumerate(self.party_items):
            x, y = self._party_position(i)
            self.canvas.coords(item, x + dx, y + dy)

    def _animate_atmosphere(self, variant, elapsed_ms):
        # Camera motion affects only the battlefield. Menu and status panels stay still.
        c = self.canvas
        c.delete("battle_atmosphere")
        t = max(0, min(1, elapsed_ms / variant.total_ms))
        hit = (elapsed_ms - variant.contact_ms) / 1000
        envelope = math.sin(math.pi * t) ** 2
        shake = variant.camera_shake * max(0, 1 - max(0, hit) / .30) if hit >= 0 else 0
        dx = round(variant.camera_pan * envelope + math.sin(elapsed_ms * .075) * shake)
        dy = round(math.cos(elapsed_ms * .093) * shake * .55)
        self._position_battlefield(dx, dy)
        if variant.tier >= 3 and 0 <= hit < .075:
            c.create_rectangle(0, 0, 960, 318, fill=variant.flash_color, outline="",
                               stipple="gray25", tags=(self.TAG, "battle_atmosphere"))
        if variant.camera_shake and 0 <= hit < .4:
            x, y = self._fx_point()
            radius = 18 + hit * (95 + variant.tier * 20)
            c.create_oval(x-radius, y+30-radius*.15, x+radius, y+30+radius*.15,
                          outline="#b9b5a0", width=2, tags=(self.TAG, "battle_atmosphere"))
        if self.model.damage > 0 and hit >= 0:
            self._draw_ability_damage(hit)
        else:
            c.delete("ability_damage")

    def _draw_ability_damage(self, hit):
        self.canvas.delete("ability_damage")
        x, y = self._fx_point()
        self._draw_damage_number(x, y-66-int(hit*24), self.model.damage, "ability_damage",
                                 ("enemy", self.model.target) in self.model.critical_hits)

    def _draw_damage_number(self, x, y, amount, tag, critical):
        color = "#ffaf61" if critical else "#ffe37e"
        self.canvas.create_text(x, y, text=str(amount), fill=color,
                                font=self.font(33 if critical else 28, True), tags=(self.TAG, tag))
        if critical:
            label_y = y - 18 if y >= 29 else y + 18
            self.canvas.create_text(x, label_y, text="CRIT!", fill="#fff0ad", font=self.font(16, True),
                                    tags=(self.TAG, tag, "critical_hit"))

    def _clear_fx(self):
        self.crescendo_fx.clear(self)
        self._reset_camera()
        self.canvas.delete("battle_healing")
        self.canvas.delete(BOW_SHOT_TAG)
        self._bow_target_hp = None
        if self._fx_item is not None:
            self.canvas.delete(self._fx_item)
            self._fx_item = None
        self.attack_fx = None
        self.fx_variant = None
        self.player_motion = None
        if self._actor_frame is not None:
            self._actor_frame = None
            index = self.model.actor
            self.canvas.itemconfigure(self.party_items[index], image=self.party_image(index))

    def click(self, x, y, now):
        if self.phase == "ally_target":
            for i in range(len(self.party_positions)):
                px, py = self._party_position(i)
                if abs(x-px) < 40 and abs(y-py) < 40:
                    self.ally_target = i
                    return self.confirm(now)
            return None
        if self.phase == "target":
            hits = []
            for i, (ex, ey) in enumerate(self.enemy_positions):
                sprite = self.enemies[self.model.enemies[i].sprite]
                dx, dy = x - ex, y - ey
                if (i != self.link_first and self.model.health[i] and abs(dx) < max(60, sprite.width() // 2)
                        and abs(dy) < max(60, sprite.height() // 2)):
                    hits.append((dx * dx + dy * dy, i))
            if hits:
                _, self.model.target = min(hits)
                return self.confirm(now)
            return None
        if self.phase == "result":
            return self.confirm(now)
        if self.phase == "command":
            if self._crescendo_badge_visible():
                left, top, right, bottom = self.CRESCENDO_BADGE
                if left <= x <= right and top <= y <= bottom:
                    if self.ability_menu:
                        self._close_ability_menu()
                    else:
                        self._open_crescendo()
                    return None
            if self.ability_menu:
                count = len(self._menu_abilities()) + 1
                start = min(max(0, self.selection - 2), max(0, count - 4))
                indices = range(start, min(count, start + 4))
            elif self.item_menu:
                count=len(self.model.item_names())+1
                start=min(max(0,self.selection-2),max(0,count-4))
                indices=range(start,min(count,start+4))
            else:
                indices = range(len(self.COMMANDS))
            for i in indices:
                tx, ty = self._command_position(i)
                if self.item_menu or self.ability_menu:
                    hit = 35 <= x <= 280 and abs(y-ty) < 12
                else:
                    hit = tx-25 <= x <= tx+100 and abs(y-ty) < 19
                if hit:
                    self.selection = i
                    return self.confirm(now)
        return None

    def update(self, now):
        if self.phase == "wyvern_reveal":
            self._update_wyvern_reveal(now)
            return
        if self.phase != "result":
            dx, dy = self._camera_offset
            elapsed = max(0, now - self.glow_started)
            attacker = (getattr(self.model, "attacker", None)
                        if self.phase in ("enemy_action", "last_brood") else None)
            for i, (foe, (rest_x, rest_y)) in enumerate(zip(self.model.enemies, self.enemy_stances)):
                if not self.model.health[i] or self.model.statuses.has(("enemy", i), "frozen"):
                    continue
                action_elapsed = now - self.phase_at if attacker == i else None
                pose_index = enemy_pose_frame(foe, max(0, elapsed - i * .23), action_elapsed=action_elapsed)
                pose = self.enemy_frames[foe.sprite][pose_index]
                if isinstance(self.model, EmberWyvernBattle):
                    pose = self.wyvern_art.pose(self.model.stage)
                if i == 0 and isinstance(self.model, DenMotherBattle) and self.model.brood_consumed:
                    shade = brood_shade(now - self.phase_at) if self.phase == "last_brood" else BROOD_SHADE_STEPS
                    if shade:
                        if self.brood_shades is None:
                            self.brood_shades = load_brood_shades(self.canvas, self.battle_assets, foe)
                        pose = self.brood_shades[shade - 1][pose_index]
                if pose is not self.enemy_poses[i]:
                    self.enemy_poses[i] = pose
                    self.canvas.itemconfigure(self.enemy_items[i], image=pose)
                # Shalehorn's authored moves set their own pose and camera.
                if isinstance(self.model, ShalehornBattle) and (self.phase == "enemy_action" or self.model.buried):
                    sx, sy = 0, 0
                else:
                    sx, sy = idle_offset(foe, elapsed if foe.sprite_bob else max(0, elapsed - i * .23))
                x, y = rest_x + sx, rest_y + sy
                if (x, y) != self.enemy_positions[i]:
                    self.enemy_positions[i] = (x, y)
                    self.canvas.coords(self.enemy_items[i], x + dx, y + dy)
            if self.crescendo_fx.cue is None:
                self._sync_party_sprites()
            index = (0, 1, 2, 1)[int(max(0, now - self.glow_started) / 0.4) % 4]
            if index != self.glow_index:
                self.glow_index = index
                if self.crescendo_fx.cue is None:
                    self.shalehorn_fx.update_backdrop(self)
        if self.phase == "result" and self.model.outcome == "victory":
            if self.level_item is not None:
                colors = ("#ffe48a", "#ffffff", "#ffad49", "#fff6c0")
                self.canvas.itemconfigure(self.level_item, fill=colors[int((now-self.result_at)*5) % len(colors)])
                self.canvas.coords(self.level_item, 712, 65 + int((now-self.result_at)*4) % 3)
            return
        if self.phase != "result":self._draw_ailments(now)
        if self.phase == "last_brood":
            self._animate_last_brood(now)
            return
        if self.phase == "frozen_action":
            if now-self.phase_at >= .6:self._end_action(now)
            return
        if self.phase == "status_tick":
            self.canvas.delete("status_damage")
            for event in self.model.status_events:
                (side, i), loss = event
                x,y=self._party_position(i) if side=="party" else self.enemy_positions[i]
                release = side == "enemy" and self.model.reliquary_release.get(i) == loss
                scorch = isinstance(self.model, EmberWyvernBattle) and event is self.model.scorch_event
                if scorch:
                    ground_flare(self.canvas, x, y, now - self.phase_at, (self.TAG, "status_damage"))
                lift = 80 if scorch and len(self.model.status_events) > 1 else 55
                color = "#ff9d55" if scorch else "#e4b5fc" if release else "#89d67b"
                self.canvas.create_text(x,y-lift-int((now-self.phase_at)*24),text=f"-{loss}",fill=color,
                                        font=self.font(24,True),tags=(self.TAG,"status_damage"))
            if now-self.phase_at >= (.85 if self.model.reliquary_release else .55):
                self.canvas.delete("status_damage")
                self.canvas.delete("night_magic")
                self._finish_action(now)
            return
        if self.phase == "ability_fx":
            elapsed_ms = (now - self.phase_at) * 1000
            duration = self.ability_duration_ms
            fx = self.crescendo_fx
            if fx.cue and not fx.impact_shown and elapsed_ms >= fx.cue.contact_ms:
                fx.impact_shown = True
                self.draw_status()
            self._draw_ability_frame(elapsed_ms)
            self._draw_ailments(now)
            if elapsed_ms < duration:
                return
            self._clear_fx()
            self.phase = "hero_action"
            self.phase_at = now
            return
        if self.phase not in ("hero_action", "enemy_action"):
            return
        elapsed = now - self.phase_at
        if self.phase == "hero_action" and not (self.model.effect == "Crescendo" or
                                                self.model.effect == "Ability" and self._ability_presented):
            self._draw_healing(elapsed)
        attacking = self.phase == "hero_action" and (
            self.model.effect == "Attack" or self.model.effect == "Ability" and self.model.damage > 0
            and not getattr(self, "_ability_presented", False))
        enemy_attacking = self.phase == "enemy_action"
        boss_fx = self.shalehorn_fx if enemy_attacking and isinstance(self.model, ShalehornBattle) else None
        wyvern_move = self.model.last_move if enemy_attacking and isinstance(self.model, EmberWyvernBattle) else None
        wyvern_timing = WYVERN_ATTACK_TIMING.get(wyvern_move)
        enemy_hit_elapsed = elapsed - (boss_fx.hit_delay if boss_fx else wyvern_timing[0] if wyvern_timing else 0)
        offset = int(18 * max(0, 1 - abs(elapsed - 0.18) / 0.18))
        c = self.canvas
        index = getattr(self.model, "attacker", self.model.target) if enemy_attacking else self.model.target
        self.enemy_item = self.enemy_items[index]
        ex, ey = self.enemy_positions[index]
        c.delete("damage_number")
        delay, release = self._motion_timing(self.attack_fx)
        if attacking:
            elapsed_ms = elapsed * 1000
            self._draw_actor_motion(elapsed_ms, release)
            if self._uses_bow:
                self._draw_bow_shot(elapsed_ms - release, (ex, ey))
            elif self.attack_fx is not None and elapsed_ms >= delay:
                point = self._attack_fx_point(self.attack_fx, elapsed_ms - delay, (ex, ey))
                self._show_fx(self.attack_fx, elapsed_ms - delay, point)
        hit_at = self.attack_contact_ms / 1000 if attacking else 0
        hit_elapsed = elapsed - hit_at
        if attacking and hit_elapsed >= 0:
            height = self.enemy_poses[index].height()
            y = max(36, ey-max(50, height // 2 + 12))-int(hit_elapsed*25)
            self._draw_damage_number(ex, y, self.model.damage, "damage_number",
                                     ("enemy", index) in self.model.critical_hits)
        if enemy_attacking and self._enemy_variant is not None:
            self._show_fx(self._enemy_variant,elapsed*1000,self._party_position(self.model.defender))
            self._draw_ailments(now)
        if enemy_attacking and enemy_hit_elapsed >= 0:
            for i, loss in self.model.hits.items():
                x, y = self.party_positions[i]
                self._draw_damage_number(x, y-38-int(enemy_hit_elapsed*25), loss, "damage_number",
                                         ("party", i) in self.model.critical_hits)
        i = self.model.defender if enemy_attacking else self.model.actor
        active_item = self.party_items[i]
        ax, ay = self._party_position(i)
        if enemy_attacking and self.model.effect == "tremor":
            ay += 3 if int(elapsed*22)%2 else -3
        c.coords(active_item, ax - (offset if attacking and self.player_motion is None else 0), ay)
        c.coords(self.enemy_item, ex + (offset if enemy_attacking else 0), ey)
        hidden = (getattr(self.model, "buried", False) or
                  (attacking and hit_elapsed >= 0 and int(hit_elapsed * 16) % 2) or
                  (not attacking and not self.model.health[index]))
        c.itemconfigure(self.enemy_item, state="hidden" if hidden else "normal")
        c.itemconfigure(active_item, state="hidden" if enemy_attacking and self.model.hits.get(i)
                        and enemy_hit_elapsed >= 0 and int(enemy_hit_elapsed * 16) % 2 else "normal")
        self.darkness_silence_fx.draw(self,now)
        if boss_fx:
            boss_fx.draw(self,now)
            boss_frame=c.itemcget(self.enemy_item,"image")
            self._draw_ailments(now)
            c.itemconfigure(self.enemy_item,image=boss_frame)
        if wyvern_timing:
            c.delete("wyvern_effect")
            sprite = self.enemy_poses[index]
            mouth = (ex + .37 * sprite.width(), ey - sprite.height() * (.09 if self.model.stage == 1 else .17))
            targets = [self._party_position(i) for i in self.model.hits]
            draw_wyvern_attack(c, wyvern_move, elapsed, mouth, targets, (self.TAG, "wyvern_effect"))
        duration=boss_fx.duration if boss_fx else max(.65,self._enemy_variant.total_ms/1000) if enemy_attacking and self._enemy_variant is not None else .65
        if wyvern_timing:
            duration = wyvern_timing[1]
        if attacking and self.player_motion is not None:
            effect_end = delay + (self.attack_fx.total_ms if self.attack_fx else 0)
            pose_end = release + self.player_motion.release_duration_ms
            duration = max(duration, effect_end / 1000, pose_end / 1000)
        if elapsed < duration:
            return
        c.coords(active_item, *self._party_position(i))
        c.delete("damage_number")
        c.delete('battle_healing')
        c.delete("wyvern_effect")
        self._clear_fx()
        if boss_fx:boss_fx.finish(self)
        c.coords(self.enemy_item, ex, ey)
        c.itemconfigure(active_item, state="normal")
        c.itemconfigure(self.enemy_item, state="normal" if self.model.health[index] and not getattr(self.model, "buried", False) else "hidden")
        self._end_action(now)

    def _finish_action(self, now):
        if isinstance(self.model, DenMotherBattle):
            self._sync_brood()
        if self.model.outcome:
            self.shalehorn_fx.clear()
            self.shalehorn_fx.update_backdrop(self)
            self.darkness_silence_fx.clear(self)
            self.frozen_fx.clear()
            self.poison_fx.clear()
            self.canvas.delete("battle_webbed")
            self.phase = "result"
            self.model.message = {
                "victory": f"Victory! {self.model.xp_reward} XP, {self.model.gold_reward} gold.",
                "defeat": "Retri retreats to the entrance to recover.",
                "fled": "Escaped safely. Continue exploring.",
            }[self.model.outcome]
            if self.model.outcome == "victory":
                self._victory_screen(now)
                return
            if self.model.outcome == "fled":
                self._prepare_loot_pages()
                if self.loot_pages:
                    self._loot_summary(self.loot_pages[0])
                    self.loot_page = 1
                    return
        else:
            if isinstance(self.model, EmberWyvernBattle) and self.model.advance_phase():
                self.phase, self.phase_at = "wyvern_reveal", now
                self.model.message = ("The Wyvern tears free of the shale! Watch its breath." if self.model.stage == 2 else
                                      "The moss burns away. Scorched Ground burns each acting ally. Water and ice cut deeper.")
                self.draw_status()
                return
            self.model.finish_ctb_turn()
            self._begin_ctb_actor(now)
        self.draw_status()

    def _update_wyvern_reveal(self, now):
        stage = self.model.stage
        age = max(0, now - self.phase_at)
        pose = self.wyvern_art.pose(stage, age)
        c = self.canvas
        c.delete("wyvern_effect")
        if stage == 2 and age >= .24:
            c.delete("wyvern_rubble")
        if stage == 3 and age >= .36:
            c.itemconfigure(self.wyvern_floor_item, state="normal")
        x, y = 270, WYVERN_GROUND - pose.height() // 2
        self.enemy_poses[0] = pose
        self.enemy_positions[0] = (x, y)
        self.enemy_stances = ((x, y),)
        c.itemconfigure(self.enemy_items[0], image=pose, state="normal")
        c.coords(self.enemy_items[0], x, y)
        if age < WYVERN_REVEAL_SECONDS[stage]:
            self.wyvern_art.transition_effect(stage, age, x, WYVERN_GROUND, (self.TAG, "wyvern_effect"))
            return
        self._finish_action(now)

    def _victory_screen(self, now):
        c, m = self.canvas, self.model
        self._prepare_loot_pages()
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
            changes = [(label, stat_value(member, key, default), stat_value(projected, key, default))
                       for label, key, default in fields
                       if stat_value(member, key, default) != stat_value(projected, key, default)]
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
        text(65, 145, f"EXP  +{m.xp_reward}", 24)
        text(65, 172, f"RP  +{m.research_reward} PER ACTIVE MEMBER", 17, "#80eaf5")
        if m.potion_reward:
            text(515, 145, f"GOLD  +{m.gold_reward}", 24)
            text(515, 172, item_gain_text("Potion", m.potion_reward), 19, "#80eaf5")
        else:
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
        footer = "ENTER / CROSS TO VIEW LOOT" if self.loot_pages else "ENTER / CROSS TO CONTINUE"
        if self.level_pages and not self.loot_pages:
            footer = "ENTER / CROSS TO VIEW STAT GAINS"
        text(65, 483, footer, 25)

    def _prepare_loot_pages(self):
        model = self.model
        model.collect_kill_drops()
        lines = [(loot_name(key), count, method)
                 for method, spoils in (("DROP", model.drops), ("STOLEN", model.stolen))
                 for key, count in spoils.items()]
        self.loot_pages = [lines[i:i+8] for i in range(0, len(lines), 8)]
        self.loot_page = 0

    def _loot_summary(self, entries):
        c = self.canvas
        self.level_item = None
        c.delete(self.TAG)
        c.create_rectangle(0, 0, 960, 540, fill="#08090c", outline="", tags=self.TAG)
        self._frame(35, 28, 925, 106)
        self._frame(35, 120, 925, 430)
        self._frame(35, 447, 925, 520)
        c.create_text(65, 66, text="BATTLE LOOT", anchor="w", fill="#ffe48a",
                      font=self.font(32, True), tags=self.TAG)
        for i, (name, count, method) in enumerate(entries):
            y = 153 + 34*i
            c.create_text(72, y, text=item_gain_text(name, count), anchor="w", fill="#ffffff",
                          font=self.font(23), tags=self.TAG)
            c.create_text(884, y, text=method, anchor="e", fill="#80eaf5",
                          font=self.font(16), tags=self.TAG)
        c.create_text(65, 483, text=f"PAGE {self.loot_page+1}/{len(self.loot_pages)}  ·  ENTER / CROSS TO CONTINUE",
                      anchor="w", fill="#ffffff", font=self.font(21), tags=self.TAG)

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
        self.shalehorn_fx.clear()
        self.brood_silk.clear()
        self.darkness_silence_fx.clear(self)
        self.poison_fx.clear()
        self.frozen_fx.clear()
        self._clear_fx()
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
