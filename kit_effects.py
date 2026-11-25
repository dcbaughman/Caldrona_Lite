"""Battle mechanics for the 7-move class kits and the new Crescendos.

Source: movesets.md (Caldrona Lite, 2026-11-24). BattleModel mixes this in so the
original combat code stays where it was; battle.py only calls the hooks below.
Numbers are the doc's suggestions. "Nx magic" is N x (Magic x 2 + 4) and
"Nx attack" is N x Caleb's combat_math.physical_damage (the same curve as Attack),
so they sit on the same scale as the existing lessons. Crits are x2, like Attack. Buffs here are not ailments: cures never remove them.
"""
import math

from classes import RIQIZAURKEIS, current_job
from combat_math import physical_damage
from crescendo import add_progress
from equipment import stat_value
from stats import RETRI
from research import PURIFY_CURES, RINSE_CURES
from statuses import AILMENTS, curable

WAVE_MOVES = frozenset(("tidecaller_rolling_tide", "tidecaller_undertow", "tidecaller_ebb",
                        "tidecaller_spring_tide"))
# Lower action rank = the next turn comes sooner (CTB recovery is speed x rank).
FAST_ACTIONS = {"sollers_knife_flick": 2, "ensifer_sheath_step": 1, "pruinor_hold_breath": 2,
                "tidecaller_swell": 2, "reliquary_lid_shut": 2}
BOSSES = ("Den Mother", "Shalehorn")
STUCK = ("slow", "bogged", "sinking")
CRIT = 2  # matches battle._roll_critical (Caleb's x2 crits)


class KitMixin:
    # ------------------------------------------------------------------ state
    def _kit_init(self):
        self.buffs = {}
        self.kit_notes = []
        self.kit_appliers = {}
        self.last_damage = {}
        self.last_hitter = None
        self.swell = {}
        self.acted = set()
        self.intercepted = {}
        self.rewind = None
        self.potters_wake = set()
        self.twin_used = set()
        self.relic_cooldown = {}
        self.tether = None
        self.thread_turns = 0
        self.thread_caster = None
        self.decoy = 0
        self.ward_sources = {}
        self._kit_current = None
        self._kit_supported = False
        self._kit_incoming_magic = False
        self._kit_redirect = None

    def _buff(self, key, name, turns=-1, value=0, source=None, until_turn=False, **extra):
        self.buffs.setdefault(key, {})[name] = {"turns": turns, "value": value, "source": source,
                                                "next": until_turn, **extra}

    def _get(self, key, name):
        return self.buffs.get(key, {}).get(name)

    def _has(self, key, name):
        return name in self.buffs.get(key, {})

    def _val(self, key, name, default=0):
        buff = self._get(key, name)
        return buff["value"] if buff else default

    def _drop(self, key, name):
        return self.buffs.get(key, {}).pop(name, None)

    def _living_enemies(self):
        return [i for i, hp in enumerate(self.health) if hp > 0]

    def _living_allies(self):
        return [i for i, p in enumerate(self.party) if p["hp"] > 0]

    def _is_boss(self, index):
        foe = self.enemies[index]
        return foe.name in BOSSES or "frozen" in foe.status_immunities

    def _note(self, text):
        if text:
            self.kit_notes.append(text)

    def _flush_notes(self):
        if self.kit_notes:
            self.message = " ".join([self.message, *self.kit_notes]).strip()
            self.kit_notes = []

    # ------------------------------------------------------------- formulas
    def _spell(self, member, mult, power=4):
        return max(1, math.ceil(mult * (stat_value(member, "magic") * 2 + power)))

    def _blow(self, member, mult, power=2, armor=None, index=None):
        """N x attack on Caleb's combat_math physical curve (same as Attack)."""
        index = self.target if index is None else index
        if armor is None:
            armor = self.enemies[index].armor
            if current_job(member) == "Seer" or self.statuses.has(("enemy", index), "sinking"):
                armor = 0
        strength = stat_value(member, "strength", RETRI["strength"] + member.get("level", self.level) - 1)
        return max(1, math.ceil(mult * physical_damage(strength, armor, self.rng.randint(240, 271), power)))

    # ------------------------------------------------------------ CTB helpers
    def _delay(self, key):
        """Push a unit back one slot in the turn order."""
        if self.ctb is None or key not in self.ctb.ready:
            return False
        mine = self.ctb.ready[key]
        later = sorted(v for k, v in self.ctb.ready.items()
                       if k != key and self._ctb_alive(k) and v >= mine)
        self.ctb.ready[key] = (later[0] if later else mine) + 1
        return True

    def _hasten(self, key, share):
        if self.ctb is None or key not in self.ctb.ready:
            return False
        wait = max(0, self.ctb.ready[key] - self.ctb.tick)
        self.ctb.ready[key] = self.ctb.tick + int(wait * (1 - share))
        return True

    def _sync_slow(self, key):
        if self.ctb is None or key not in self.ctb.ready:
            return
        want = "slow" if self.statuses.has(key, "slow") else None
        if self.ctb.status.get(key) != want:
            self.ctb.set_status(key, want)

    # ---------------------------------------------------------- status helpers
    def _inflict(self, index, status, chance=1, turns=None, credit=None):
        key = ("enemy", index)
        if self.health[index] <= 0 or not self.apply_status(key, status, chance, turns):
            return False
        credit = self.actor if credit is None else credit
        if status in STUCK:
            self.kit_appliers[(key, status)] = credit
        if status in ("frozen", "slow"):
            add_progress(self.party[credit], "Pruinor", 1)
        if status == "slow":
            self._sync_slow(key)
        return True

    def _cure(self, index, statuses):
        key = ("party", index)
        removed = [s for s in curable(statuses) if self.statuses.has(key, s)]
        for status in removed:
            self.statuses.remove(key, status)
        if "slow" in removed:
            self._sync_slow(key)
        return removed

    def _heal(self, index, amount, credit=None):
        ally = self.party[index]
        if ally["hp"] <= 0 or amount <= 0:
            return 0
        before = ally["hp"]
        ally["hp"] = min(stat_value(ally, "max_hp"), before + int(amount))
        gained = ally["hp"] - before
        if credit is not None:
            add_progress(self.party[credit], "Tidecaller", gained)
        self.hp = self.party[0]["hp"]
        return gained

    def _restore_mp(self, member, amount):
        current = member.get("mp", 0)
        member["mp"] = max(current, min(stat_value(member, "max_mp"), current + amount))

    def _linked(self, index):
        return self.black_thread is not None and index in self.black_thread[:2]

    def _swell_mult(self, lesson_id):
        if lesson_id not in WAVE_MOVES:
            return 1
        stacks = self.swell.get(self.actor, 0)
        self.swell[self.actor] = 1  # each wave after a wave rides the swell
        return min(2.0, 1 + .5 * stacks)

    # ------------------------------------------------------- outgoing damage
    def kit_outgoing(self, damage, physical):
        if damage <= 0 or self.outcome:
            return damage
        key, me = ("enemy", self.target), ("party", self.actor)
        bonus = 100 + self._val(key, "foretold") + self._val(key, "vulnerable")
        lesson = self._kit_current
        strand = self._get(key, "strand")
        if strand and strand["source"] == self.actor and not physical:
            bonus += strand["value"]
            self._drop(key, "strand")
        if lesson == "seer_lunar_drop" and self._has(key, "foretold"):
            bonus += 25
        if lesson and lesson.startswith("limotex_") and not physical and self.actor in self.potters_wake:
            bonus += 25
        crit = 0
        if physical:
            bonus += self._val(me, "oath") + self._val(me, "vow")
            crit = self._val(me, "oath_crit") + self._val(me, "vow_crit")
        damage = math.ceil(damage * bonus / 100)
        if lesson == "sollers_backstab" and (self.target in self.marks or self._has(key, "foretold")
                                             or any(self.statuses.has(key, s) for s in STUCK)
                                             or self._has(key, "delayed")):
            damage = math.ceil(damage * CRIT)
            self.critical_hits.add(key)
        elif crit and self.status_rng.random() * 100 < crit:
            damage = math.ceil(damage * CRIT)
            self.critical_hits.add(key)
        return damage

    def _kit_hit(self, member, amount, physical=False, index=None):
        if index is not None:
            self.target = index
        if self.health[self.target] <= 0:
            return 0
        if physical and not self._drop(("party", self.actor), "nomiss") and \
                self._misses_in_darkness(("party", self.actor), ("enemy", self.target)):
            self._note("A blow misses in the darkness.")
            return 0
        element = self._weapon_element(member) if physical else None
        key = ("enemy", self.target)
        self._hit_target(amount, physical=physical, element=element,
                         can_crit=physical and key not in self.critical_hits)
        return self.damage

    # --------------------------------------------------------- incoming hits
    def _warden_for(self, index):
        attacker = getattr(self, "attacker", None)
        if attacker is not None:
            taunt = self._get(("enemy", attacker), "taunt")
            if taunt and self.party[taunt["source"]]["hp"] > 0:
                return taunt["source"]
        for w in self._living_allies():
            key = ("party", w)
            if self._has(key, "unbroken") or self._has(key, "last_watch") or self._has(key, "vigil"):
                return w
        intercept = self._drop(("party", index), "intercept")
        if intercept and self.party[intercept["source"]]["hp"] > 0:
            return intercept["source"]
        return None

    def kit_incoming(self, index, damage):
        """Redirect and reduce an enemy hit. Returns (index, damage)."""
        attacker = getattr(self, "attacker", None)
        if self.decoy > 0:
            self.decoy = 0
            self._note("The clay effigy takes the blow and crumbles.")
            return index, 0
        warden = self._warden_for(index)
        if warden is not None and warden != index:
            add_progress(self.party[warden], "Warden", 1)
            self._note(f"{self.party[warden]['name']} takes the hit for {self.party[index]['name']}.")
            index = warden
        if warden is not None:
            self.intercepted[warden] = self.intercepted.get(warden, 0) + damage
            if self._has(("party", warden), "unbroken"):
                damage = max(1, damage // 2)
        elif self._has(("party", index), "veil"):
            others = [i for i in self._living_allies() if i != index and not self._has(("party", i), "veil")]
            if not others:
                self._note("The attack loses its target in the smoke.")
                return index, 0
            index = others[0]
        key = ("party", index)
        ally = self.party[index]
        evade = self._val(key, "evade") + (self._val(("enemy", attacker), "mist") if attacker is not None else 0)
        if evade and self.status_rng.random() * 100 < evade:
            self._note(f"{ally['name']} evades!")
            return index, 0
        pct = self._val(key, "shield_pct")
        if attacker is not None:
            pct += self._val(("enemy", attacker), "weaken")
        if not self._kit_incoming_magic:
            pct += self._val(key, "phys_shield")
        if pct:
            damage = max(1, damage * (100 - min(pct, 90)) // 100)
        if self._has(key, "def_up"):
            damage = max(1, damage - max(1, stat_value(ally, "defense") // 2))
        if not self._kit_incoming_magic and self._drop(key, "edge_mirror"):
            self._counter(index, 1.0, "Edge Mirror")
            return index, 0
        shield = self._get(key, "absorb")
        if shield:
            taken = min(shield["value"], damage)
            shield["value"] -= taken
            damage -= taken
            self._note(f"Hoarfrost absorbs {taken}.")
            if shield["value"] <= 0:
                self._drop(key, "absorb")
            if attacker is not None and self.health[attacker] > 0:
                self._inflict(attacker, "frozen", .40, credit=shield["source"])
        rime = self._get(key, "rime")
        if rime and attacker is not None and self.health[attacker] > 0:
            self._inflict(attacker, "frozen", .30, credit=rime["source"])
        if self.tether is not None and damage > 1 and index in self.tether[:2]:
            partner = self.tether[1] if index == self.tether[0] else self.tether[0]
            if self.party[partner]["hp"] > 0:
                share = damage * 30 // 100
                if share:
                    damage -= share
                    self._take_party_damage(partner, share, incoming=False)
                    self._note(f"Tether Pact shares {share} with {self.party[partner]['name']}.")
        return index, damage

    def kit_floor(self, index, damage):
        ally = self.party[index]
        if damage < ally["hp"] or ally["hp"] <= 0:
            return damage
        guarded = any(self._has(("party", i), "last_watch") or self._has(("party", i), "nox")
                      for i in self._living_allies())
        if not guarded and not self._has(("party", index), "unbroken"):
            return damage
        prevented = damage - (ally["hp"] - 1)
        if self.reliquary is not None and any(self._has(("party", i), "nox") for i in self._living_allies()):
            self.reliquary.stored += prevented
        self._note(f"{ally['name']} holds on at 1 HP.")
        return ally["hp"] - 1

    def kit_after_hit(self, index, damage, hp_before):
        if damage <= 0:
            return
        key = ("party", index)
        ally = self.party[index]
        self.last_damage[index] = damage
        attacker = getattr(self, "attacker", None)
        self.last_hitter = attacker
        if self._has(key, "lid"):
            gain = damage * 25 // 100
            if gain:
                self._restore_mp(ally, gain)
        vigil = self._get(key, "vigil")
        if vigil and not vigil.get("countered") and attacker is not None and ally["hp"] > 0:
            vigil["countered"] = True
            self._counter(index, 1.0, "Vigil")
        ward = self.wards.get(index, 0)
        saint = self.ward_sources.get(index)
        if (saint is not None and ward and ally["hp"] > 0 and
                hp_before <= math.ceil(damage * 100 / max(1, 100 - ward))):
            add_progress(self.party[saint], "Saint", 1)

    def _counter(self, index, mult, name):
        attacker = getattr(self, "attacker", None)
        if attacker is None or self.health[attacker] <= 0:
            return
        member = self.party[index]
        amount = self._blow(member, mult, index=attacker)
        selected = self.target
        self.target = attacker
        self._hit_target(amount, physical=True, include_mark=False)
        self.target = selected
        self._note(f"{name} counters for {amount}!")

    # ---------------------------------------------------------- turn hooks
    def kit_turn_start(self, index):
        key = ("party", index)
        for name, buff in list(self.buffs.get(key, {}).items()):
            if buff["next"]:
                self._drop(key, name)
        regen = self._get(key, "regen")
        if regen:
            healed = self._heal(index, regen["value"], regen["source"])
            if healed:
                self._note(f"{self.party[index]['name']} regenerates {healed} HP.")
            regen["turns"] -= 1
            if regen["turns"] <= 0:
                self._drop(key, "regen")
        if self.relic_cooldown.get(index, 0) > 0:
            self.relic_cooldown[index] -= 1
        if self.tether is not None and self.tether[3] == index:
            a, b, turns, caster = self.tether
            self.tether = (a, b, turns - 1, caster) if turns > 1 else None
        if self.black_thread is not None and self.thread_caster == index:
            self.thread_turns -= 1
            if self.thread_turns <= 0:
                self.black_thread = None
        unbroken = self._get(key, "unbroken")
        if unbroken:
            unbroken["turns"] -= 1
            if unbroken["turns"] <= 0:
                self._drop(key, "unbroken")
                member = self.party[index]
                total = 0
                for i in self._living_enemies():
                    self.target = i
                    self._hit_target(self._blow(member, 1, unbroken["value"], index=i), physical=True,
                                     include_mark=False)
                    total += self.damage
                self._note(f"Unbroken Hour ends with a counter-sweep for {total}!")
                self._check_outcome()

    def kit_turn_end(self, key):
        side, index = key
        if side == "enemy":
            if self.health[index] > 0:
                for status in STUCK:
                    if self.statuses.has(key, status):
                        credit = self.kit_appliers.get((key, status))
                        if credit is not None:
                            add_progress(self.party[credit], "Limotex", 1)
                        break
                mire = self._get(key, "mire")
                if mire:
                    selected = self.target
                    self.target = index
                    self._hit_target(mire["value"], include_mark=False)
                    self.status_events.append((key, self.damage))
                    self.target = selected
            self._sync_slow(key)
            vulnerable = self._get(key, "vulnerable")
            if vulnerable and vulnerable["turns"] == -1 and not self.statuses.has(key, "frozen"):
                self._drop(key, "vulnerable")
        for name, buff in list(self.buffs.get(key, {}).items()):
            if buff["turns"] > 0 and name not in ("regen", "unbroken"):
                buff["turns"] -= 1
                if buff["turns"] <= 0:
                    self._drop(key, name)

    def kit_preempt(self, attacker):
        """Prophecy or Sleight of Hand resolve instead of the enemy's action."""
        key = ("enemy", attacker)
        if self.health[attacker] <= 0:
            return False
        foe = self.enemies[attacker]
        if self._drop(key, "prophecy"):
            self.message = f"Prophecy! {foe.name}'s action was foreseen and cancelled."
            damage, victim = 0, None
        elif self._drop(key, "sleight"):
            others = [i for i in self._living_enemies() if i != attacker] or [attacker]
            victim = others[0]
            selected = self.target
            self.target = victim
            self._hit_target(self.rng.randint(*foe.attack), include_mark=False)
            damage = self.damage
            self.target = selected
            self.message = f"Sleight of Hand! {foe.name} strikes {self.enemies[victim].name} for {damage}!"
        else:
            return False
        self.pending_reply = False
        self.attacker = attacker
        self.enemy_turns[attacker] += 1
        self.enemy_skill = None
        self.action_rank = 3
        self.effect = "enemy"
        self.hits = {}
        self.damage = 0
        self._check_outcome()
        if not self.outcome:
            self.actor = next(i for i, p in enumerate(self.party) if p["hp"] > 0)
        return True

    # -------------------------------------------------------- after commands
    def kit_after_command(self, action, ability_id, member, health_before, hp_before, wards_before):
        job = current_job(member)
        kills = sum(1 for before, now in zip(health_before, self.health) if before > 0 and now <= 0)
        if kills:
            add_progress(member, "Ensifer", kills)
        if action == "Crescendo":
            if job == "Tidecaller":
                add_progress(member, "Tidecaller", sum(self.healed.values()))
            if job == "Saint":
                add_progress(member, "Saint", sum(1 for i, hp in enumerate(hp_before)
                                                  if hp <= 0 < self.party[i]["hp"]))
        if job == "Saint":
            for i, value in self.wards.items():
                if value > wards_before.get(i, 0):
                    self.ward_sources[i] = self.actor
        if not (action == "Ability" and (ability_id in WAVE_MOVES or ability_id == "tidecaller_swell")):
            self.swell.pop(self.actor, None)
        self.acted.add(self.actor)
        self.rewind = [p["hp"] for p in self.party]
        if action == "Ability" and ability_id in FAST_ACTIONS:
            self.action_rank = FAST_ACTIONS[ability_id]
        self._flush_notes()

    # ----------------------------------------------------------- Crescendos
    def kit_crescendo_damage(self, move, index, damage, member):
        rider = move.rider
        if rider == "frozen_x15" and self.statuses.has(("enemy", index), "frozen"):
            return math.ceil(damage * 1.5)
        if rider == "relic_x15" and self.reliquary is not None:
            return math.ceil(damage * 1.5)
        if rider == "reckoning":
            return damage + min(10, self.intercepted.get(self.actor, 0) // 10)
        if rider == "first_crit" and self.actor not in self.acted:
            return math.ceil(damage * CRIT)
        return damage

    def kit_crescendo_rider(self, move, member, targets):
        rider, me = move.rider, self.actor
        magic = stat_value(member, "magic")
        allies = self._living_allies()
        foes = [i for i in targets if self.health[i] > 0] if targets else self._living_enemies()
        if rider == "freeze_50":
            for i in foes:
                self._inflict(i, "frozen", .5)
        elif rider == "rime":
            for i in allies:
                self._buff(("party", i), "rime", source=me, until_turn=True)
        elif rider == "hiems":
            for i in self._living_enemies():
                self._inflict(i, "slow", turns=3)
            normal = [i for i in self._living_enemies() if not self._is_boss(i)]
            if normal:
                self._inflict(min(normal, key=lambda i: self.health[i]), "frozen")
        elif rider == "tide_again":
            for i in allies:
                self._buff(("party", i), "regen", 1, move.power + magic, me)
        elif rider in ("delay_all", "delay"):
            for i in foes:
                self._delay(("enemy", i))
        elif rider == "slack":
            for i in allies:
                self.statuses.cure(("party", i))
                self._sync_slow(("party", i))
                self._restore_mp(self.party[i], move.power)
            self._note("Every ailment washes away.")
        elif rider == "rewind":
            if self.rewind:
                restored = 0
                for i in allies:
                    target = min(stat_value(self.party[i], "max_hp"), self.rewind[i])
                    if target > self.party[i]["hp"]:
                        restored += self._heal(i, target - self.party[i]["hp"])
                self._note(f"The tide rewinds {restored} HP.")
        elif rider == "weaken_all":
            for i in foes:
                self._buff(("enemy", i), "weaken", 2, 20, me)
        elif rider == "nox":
            self._buff(("party", me), "nox", source=me, until_turn=True)
        elif rider == "gate":
            for i in self._living_enemies():
                self._buff(("enemy", i), "taunt", 2, 0, me)
            self.wards[me] = max(move.power, self.wards.get(me, 0))
        elif rider == "beacon":
            for i in allies:
                if i != me:
                    self._hasten(("party", i), .2)
        elif rider == "unbroken":
            self._buff(("party", me), "unbroken", 2, move.power, me)
        elif rider == "vow":
            self._buff(("party", me), "vow", -1, 40, me)
            self._buff(("party", me), "vow_crit", -1, 30, me)
        elif rider == "blade_rain":
            for i in self._living_enemies():
                self._kit_hit(member, self._blow(member, .3, armor=0, index=i), physical=False, index=i)
            self.target = targets[0] if targets and self.health[targets[0]] > 0 else self.target
        elif rider == "slow_all":
            for i in foes:
                self._inflict(i, "slow", turns=2)
        elif rider == "green_bank":
            for i in allies:
                self._buff(("party", i), "regen", 3, 6, me)
        elif rider == "mire":
            for i in self._living_enemies():
                self._inflict(i, "slow", turns=3)
                self._buff(("enemy", i), "mire", 3, magic + 4, me)
            for i in allies:
                self._buff(("party", i), "evade", 3, 20, me)

    # --------------------------------------------------------- kit lessons
    def kit_validate(self, ability, member):
        lid = ability.id
        if lid == "reliquary_twin_reliquary" and self.actor in self.twin_used:
            return "Twin Reliquary works once per battle."
        if lid == "weaver_tether_pact" and len(self._living_allies()) < 2:
            return "Tether Pact needs two standing allies."
        if lid == "weaver_closing_verse" and self.black_thread is None:
            return "There are no threads to detonate."
        if lid == "warden_vadimon" and member["hp"] <= max(1, stat_value(member, "max_hp") * 15 // 100):
            return "Too wounded to pledge."
        if ability.target == "single enemy" and (not self.enemy_hp or getattr(self, "buried", False)):
            return "That enemy can't be reached."
        if ability.target == "all enemies" and (not any(self.health) or getattr(self, "buried", False)):
            return "That enemy can't be reached."
        return ""

    def kit_cast(self, ability, member, ally):
        lid, name, me = ability.id, ability.name, self.actor
        i = self.target
        ekey = ("enemy", i)
        magic = stat_value(member, "magic")
        foe = self.enemies[i].name
        swell = self._swell_mult(lid)
        self._kit_supported = True
        self.message = ""
        say = None

        def spell(mult, index=None, echo=True):
            dealt = self._kit_hit(member, self._spell(member, mult, ability.power or 4), index=index)
            if echo and dealt:
                self._echo_spell()
            return dealt

        if lid == "seer_foretell":
            self._buff(ekey, "foretold", 3, 20, me)
            add_progress(member, "Seer", 1)
            pct = self.enemies[i].fire_damage_percent
            weak = "Weak to fire!" if pct > 100 else "Resists fire." if pct < 100 else "No weakness."
            say = f"Foretell marks {foe}. {weak}"
        elif lid == "seer_starfall_omen":
            say = f"{name} hits for {spell(2.2)}!"
        elif lid == "seer_forewarn":
            self._buff(("party", ally), "evade", 2, ability.power, me)
            if ally != me:
                self._hasten(("party", ally), .5)
            say = f"{name}: {self.party[ally]['name']} reads the next attack."
        elif lid == "seer_twist_of_fate":
            self._delay(ekey)
            self._buff(ekey, "delayed", 1)
            say = f"{name} pushes {foe} back in the turn order."
        elif lid == "seer_prophecy":
            self._buff(ekey, "prophecy", source=me)
            say = f"{name}: {foe}'s next action is foreseen."
        elif lid == "pruinor_rime_lash":
            dealt = spell(1.4)
            self._delay(ekey)
            self._buff(ekey, "delayed", 1)
            say = f"{name} hits for {dealt}!"
        elif lid == "pruinor_hold_breath":
            self._buff(("party", me), "def_up", source=me, until_turn=True)
            self._restore_mp(member, ability.power)
            say = f"{member['name']} holds still and gathers {ability.power} MP."
        elif lid == "pruinor_hoarfrost_veil":
            self._buff(("party", ally), "absorb", -1, ability.power + magic, me)
            say = f"{name} wraps {self.party[ally]['name']} in rime."
        elif lid == "pruinor_still_water":
            pkey = ("party", ally)
            boosted = ally in self.guarded or self._has(pkey, "def_up")
            present = list(self.statuses.for_actor(pkey))
            cleansed = self._cure(ally, present if boosted else present[:1])
            self._buff(pkey, "regen", 3, ability.power * (2 if boosted else 1), me)
            say = f"{name} calms {self.party[ally]['name']}." + (" Ailments cleansed." if cleansed else "")
        elif lid == "pruinor_glacial_field":
            for index in self._living_enemies():
                self._inflict(index, "slow", turns=3)
            say = f"{name} chills the field."
        elif lid == "pruinor_shatter":
            frozen = self.statuses.has(ekey, "frozen")
            dealt = spell(3.0 if frozen else 1.2)
            if frozen:
                self.statuses.remove(ekey, "frozen")
                self._drop(ekey, "vulnerable")
            say = f"{name} hits for {dealt}!" + (" The ice shatters!" if frozen else "")
        elif lid == "pruinor_giants_sleep":
            if self._is_boss(i):
                self._inflict(i, "slow", turns=3)
                self._buff(ekey, "vulnerable", 3, 15, me)
            elif self._inflict(i, "frozen", turns=2):
                self._buff(ekey, "vulnerable", -1, ability.power, me)
            say = f"{name} settles over {foe}."
        elif lid == "tidecaller_rolling_tide":
            amount = math.ceil((ability.power + magic) * swell)
            total = sum(self._heal(a, amount, me) for a in self._living_allies())
            for a in self._living_allies():
                self._buff(("party", a), "regen", 1, amount, me)
            say = f"{name} restores {total} HP to the party."
        elif lid == "tidecaller_undertow":
            dealt = spell(1.2 * swell)
            self._delay(ekey)
            self._buff(ekey, "delayed", 1)
            say = f"{name} hits for {dealt}!"
        elif lid == "tidecaller_rinse":
            cured = self._cure(ally, RINSE_CURES)
            healed = self._heal(ally, ability.power + magic, me)
            say = f"{name} restores {healed} HP to {self.party[ally]['name']}."
            if cured:
                say += " Cured " + ", ".join(AILMENTS[s].label for s in cured) + "."
        elif lid == "tidecaller_swell":
            self.swell[me] = min(2, self.swell.get(me, 0) + 1)
            say = f"{member['name']} gathers the swell (x{1 + .5 * self.swell[me]:g})."
        elif lid == "tidecaller_ebb":
            amount = min(ability.power + magic, math.ceil(self.last_damage.get(ally, 0) * .6))
            healed = self._heal(ally, math.ceil(amount * swell), me)
            say = f"{name} restores {healed} HP to {self.party[ally]['name']}."
        elif lid == "tidecaller_sea_mist":
            for a in self._living_allies():
                self._buff(("party", a), "evade", 2, ability.power, me)
            for index in self._living_enemies():
                self._buff(("enemy", index), "mist", 2, 10, me)
            say = f"{name} veils the party."
        elif lid == "tidecaller_spring_tide":
            amount = math.ceil((ability.power + magic) * swell)
            total = 0
            for a in self._living_allies():
                self._buff(("party", a), "regen", 3, amount, me)
                total += self._heal(a, min(40 + magic, math.ceil(self.last_damage.get(a, 0) * .4)), me)
            say = f"{name} rises. The party ebbs back {total} HP."
        elif lid == "weaver_read_the_strand":
            self._buff(ekey, "strand", -1, ability.power, me)
            say = f"{name} reads {foe}." + (" A Black Thread runs through it." if self._linked(i) else "")
        elif lid == "weaver_onyx_lash":
            say = f"{name} hits for {spell(1.6 * (1.25 if self._linked(i) else 1))}!"
        elif lid == "weaver_weft_snare":
            ends = [x for x in self.black_thread[:2] if self.health[x] > 0] if self._linked(i) else [i]
            for index in ends:
                self._inflict(index, "webbed", ability.power / 100)
            say = f"{name} lashes silk."
        elif lid == "weaver_hush":
            self._inflict(i, "silence", 1 if self._linked(i) else ability.power / 100)
            say = f"{name}."
        elif lid == "weaver_tether_pact":
            a, b = self._living_allies()[:2]
            self.tether = (a, b, 3, me)
            say = f"{name} binds {self.party[a]['name']} and {self.party[b]['name']}."
        elif lid == "weaver_closing_verse":
            ends = [x for x in self.black_thread[:2] if self.health[x] > 0]
            self.black_thread = None
            total = sum(self._kit_hit(member, self._spell(member, 2.0, ability.power), index=x) for x in ends)
            self.damage = total
            say = f"{name} detonates the thread for {total}!"
        elif lid == "sollers_smokescreen":
            self._buff(("party", me), "veil", source=me, until_turn=True)
            say = f"{member['name']} vanishes into the smoke."
        elif lid == "sollers_sleight_of_hand":
            self._buff(ekey, "sleight", source=me)
            self.gold_reward += ability.power
            say = f"{name}: {foe}'s next blow is turned. Pocketed {ability.power} gold."
        elif lid == "reliquary_lid_shut":
            self.wards[me] = max(ability.power, self.wards.get(me, 0))
            self._buff(("party", me), "lid", source=me, until_turn=True)
            say = f"{member['name']} shuts the lid."
        elif lid == "reliquary_hollow_tithe":
            dealt = spell(1.0)
            healed = self._heal(me, dealt // 2)
            say = f"{name} hits for {dealt} and returns {healed} HP."
        elif lid == "reliquary_grave_weight":
            self._buff(ekey, "weaken", 3, ability.power, me)
            say = f"{name} drags at {foe}."
        elif lid == "reliquary_ashen_hush":
            for index in self._living_enemies():
                key = ("enemy", index)
                if self._val(key, "weaken") <= ability.power:
                    self._buff(key, "weaken", 2, ability.power, me)
            say = f"{name} settles over the foes."
        elif lid == "reliquary_twin_reliquary":
            self.twin_used.add(me)
            self._buff(("party", me), "twin", source=me)
            say = f"{name}: the next reliquary opens wider."
        elif lid == "saint_purify":
            cured = sum(len(self._cure(a, PURIFY_CURES)) for a in self._living_allies())
            say = f"{name} cleanses the party." if cured else f"{name}: nothing to cleanse."
        elif lid == "saint_benediction":
            total = sum(self._heal(a, ability.power + magic, me) for a in self._living_allies())
            for a in self._living_allies():
                self._buff(("party", a), "regen", 3, 4, me)
            say = f"{name} restores {total} HP to the party."
        elif lid == "warden_challenge":
            self._buff(ekey, "taunt", 3, 0, me)
            say = f"{name}! {foe} must face {member['name']}."
        elif lid == "warden_intercept":
            if ally == me:
                self.guarded.add(me)
                say = f"{member['name']} braces."
            else:
                self._buff(("party", ally), "intercept", source=me)
                say = f"{member['name']} stands over {self.party[ally]['name']}."
        elif lid == "warden_vigil":
            self._buff(("party", me), "vigil", source=me, until_turn=True)
            say = f"{member['name']} keeps vigil."
        elif lid == "warden_reprisal":
            if self.last_hitter is not None and self.health[self.last_hitter] > 0:
                i = self.target = self.last_hitter
            dealt = self._kit_hit(member, self._blow(member, 1.4, ability.power), physical=True)
            self._delay(("enemy", i))
            say = f"{name} hits for {dealt}!"
        elif lid == "warden_sentrys_call":
            for a in self._living_allies():
                if a != me:
                    self._hasten(("party", a), .25)
            say = f"{name}: the party is alert."
        elif lid == "warden_vadimon":
            cost = max(1, stat_value(member, "max_hp") * 15 // 100)
            member["hp"] -= cost
            for a in self._living_allies():
                self._buff(("party", a), "shield_pct", 2, ability.power, me)
            say = f"{member['name']} pledges {cost} HP. The party is shielded."
        elif lid == "warden_last_watch":
            self._buff(("party", me), "last_watch", source=me, until_turn=True)
            say = f"{member['name']} takes the last watch."
        elif lid == "ensifer_drawing_cut":
            sure = self._drop(("party", me), "sheath")
            chance = .5 if me not in self.acted else .15
            crit = sure or self.status_rng.random() < chance
            if crit:
                self.critical_hits.add(("enemy", self.target))
            dealt = self._kit_hit(member, math.ceil(self._blow(member, 1, ability.power) * (CRIT if crit else 1)),
                                  physical=True)
            say = f"{name} hits for {dealt}!"
        elif lid == "ensifer_sheath_step":
            self._buff(("party", me), "sheath", source=me)
            say = f"{member['name']} sheathes and steps in."
        elif lid in ("ensifer_sword_wheel", "ensifer_arsenal_fall", "ensifer_thousand_edges"):
            plan = {"ensifer_sword_wheel": [(.6, i, None)] * 4,
                    "ensifer_arsenal_fall": [(2.0, i, 0)] + [(.3, i, 0)] * 3}.get(lid)
            if plan is None:
                living = self._living_enemies()
                plan = [(.4, living[self.status_rng.randrange(len(living))], 0) for _ in range(10)] + [(2.0, i, 0)]
            total = 0
            physical = lid == "ensifer_sword_wheel"
            for mult, index, armor in plan:
                if self.health[index] <= 0:
                    living = self._living_enemies()
                    if not living:
                        break
                    index = living[0]
                total += self._kit_hit(member, self._blow(member, mult, ability.power, armor, index),
                                       physical=physical, index=index)
            self.damage = total
            say = f"{name} deals {total} damage!"
        elif lid == "ensifer_edge_mirror":
            self._buff(("party", me), "edge_mirror", source=me)
            say = f"A conjured blade guards {member['name']}."
        elif lid == "ensifer_bearers_oath":
            self._buff(("party", me), "oath", 3, ability.power, me)
            self._buff(("party", me), "oath_crit", 3, 15, me)
            self._buff(("party", me), "nomiss", source=me)
            say = f"{name}!"
        elif lid == "limotex_mire_grasp":
            dealt = spell(1.5)
            self._inflict(i, "slow", turns=2)
            say = f"{name} hits for {dealt}!"
        elif lid == "limotex_clay_shackle":
            self._inflict(i, "bogged", turns=2)
            self._delay(ekey)
            self._buff(ekey, "delayed", 1)
            say = f"{name} binds {foe}."
        elif lid == "limotex_silt_veil":
            self._buff(("party", ally), "phys_shield", 2, ability.power, me)
            say = f"{name} films {self.party[ally]['name']} in silt."
        elif lid == "limotex_clay_effigy":
            self.decoy = ability.power + magic
            say = f"{name}: a clay decoy rises ({self.decoy} HP)."
        elif lid == "limotex_marsh_fume":
            for index in self._living_enemies():
                self._inflict(index, "poison", ability.power / 100)
            say = f"{name} rolls over the foes."
        elif lid == "limotex_sinking_bog":
            dealt = spell(2.4)
            self._inflict(i, "sinking", turns=3)
            say = f"{name} hits for {dealt}!"
        elif lid == "limotex_potters_wake":
            for index in self._living_enemies():
                self._inflict(index, "slow", turns=3)
            self.potters_wake.add(me)
            say = f"{name} reshapes the field into a mire."
        else:
            return False
        self.message = (say or name) + self.message
        return True

    # -------------------------------------------------- existing-move riders
    def kit_lesson_rider(self, ability, member):
        lid = ability.id
        if lid == "sollers_pilfer":
            chance = 50 + stat_value(member, "luck")
            if self.status_rng.random() * 100 < chance:
                pinch = 5
                self.gold_reward += pinch
                add_progress(member, "Sollers", pinch)
                self._note(f"Pocketed {pinch} gold.")
        elif lid == "weaver_black_thread":
            self.thread_caster, self.thread_turns = self.actor, 3
        elif lid == "reliquary_retribution" and self.reliquary is not None:
            if self._drop(("party", self.actor), "twin"):
                self.reliquary.absorb_percent = 75
                self.reliquary.twin = True

    def kit_reliquary_released(self, caster, dealt, twin):
        add_progress(self.party[caster], RIQIZAURKEIS, dealt)
        if not twin:
            self.relic_cooldown[caster] = 2
