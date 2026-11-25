"""Per-member Tome progress and the four playable paths' research entries."""
from dataclasses import dataclass

from classes import RIQIZAURKEIS, current_job
from statuses import AILMENTS, PLAYER_AILMENTS

CATEGORIES = ("Combat", "Healing", "Arcane", "Support")
QUARRY_ANALECT = "Quarry Analect"
ECHO_ANALECT = "Echo Analect"
ANALECTS = (QUARRY_ANALECT, ECHO_ANALECT)


@dataclass(frozen=True)
class Lesson:
    id: str
    name: str
    category: str
    level: int
    rp: int
    mp: int
    effect: str
    power: int
    source: str = ""
    command: str = ""
    motion: str = ""

    @property
    def menu(self):
        return self.command or ("Magic" if self.category in ("Healing", "Arcane") or self.effect == "ward" else "Abilities")

    @property
    def actor_motion(self):
        if self.motion:
            return self.motion
        return "magic" if self.menu == "Magic" or self.effect == "arcane" else ""

    @property
    def action_rank(self):
        if self.effect == "steal":
            return 3
        if self.effect in ("ward", "mark"):
            return 2
        if self.effect in ("heal", "restore"):
            return 3
        return 6 if self.level >= 12 else 4

    @property
    def target(self):
        if self.effect == "kit":
            return KIT_TARGETS.get(self.id, "single enemy")
        if self.effect in ("heal", "ward", "restore"):
            return "single ally"
        if self.effect == "link":
            return "two enemies"
        if self.effect == "reliquary":
            return "party"
        return "single enemy"

    @property
    def description(self):
        if self.id in KIT_TEXT:
            return KIT_TEXT[self.id]
        description = {
            "physical": f"A physical hit with +{self.power} power. Strength raises damage, and armor reduces it.",
            "arcane": f"Deal twice Magic + {self.power}, ignoring armor.",
            "heal": f"Restore {self.power} HP plus Magic to one ally.",
            "restore": f"Restore up to {self.power} MP to one ally.",
            "ward": f"Reduce one ally's damage by {self.power}% for the next enemy round.",
            "mark": f"Add {self.power} damage to the next hit against this enemy.",
            "steal": "Roll all three of this enemy's steal slots.",
            "link": f"Link two foes. The next spell on either echoes {self.power}% of its damage to the other.",
            "reliquary": "Store half the party's incoming damage for three enemy phases. Release it as magic damage.",
        }[self.effect]
        if self.id in PLAYER_AILMENTS:
            status, chance = PLAYER_AILMENTS[self.id]
            info = AILMENTS[status]
            description += (f" {int(chance*100)}%: {info.label} until cured." if info.duration==-1 else f" {int(chance*100)}%: {info.label} ({info.duration} target turns).")
        if self.id == "saint_mend":
            description += " Also cures Poison."
        elif self.id == "saint_litany":
            description += " Also cleanses all ailments."
        return description


def _lessons(prefix, rows):
    return tuple(Lesson(f"{prefix}_{key}", name, category, level, rp, mp, effect, power, *source)
                 for key, name, category, level, rp, mp, effect, power, *source in rows)


LESSONS = {
    "Unbound": _lessons("unbound", (
        ("quick_cut", "Quick Cut", "Combat", 1, 1, 1, "physical", 3, "", "", "weapon"),
        ("hard_edge", "Hard Edge", "Combat", 3, 2, 2, "physical", 7, QUARRY_ANALECT, "", "weapon"),
        ("low_sweep", "Low Sweep", "Combat", 5, 3, 2, "physical", 10, "", "", "weapon"),
        ("counter_cut", "Counter Cut", "Combat", 8, 4, 3, "physical", 14, "", "", "weapon"),
        ("last_stand", "Last Stand", "Combat", 14, 6, 5, "physical", 23, "", "", "weapon"),
        ("first_aid", "First Aid", "Healing", 2, 2, 2, "heal", 12),
        ("field_dress", "Field Dressing", "Healing", 6, 3, 3, "heal", 22),
        ("steady_breath", "Steady Breath", "Healing", 9, 4, 3, "restore", 5),
        ("spark", "Spark", "Arcane", 4, 2, 2, "arcane", 3, ECHO_ANALECT),
        ("flint_burst", "Flint Burst", "Arcane", 7, 3, 3, "arcane", 7),
        ("quarry_echo", "Quarry Echo", "Arcane", 5, 3, 4, "arcane", 13,
         "Witness Quarry Tremor"),
        ("ember_arc", "Ember Arc", "Arcane", 15, 6, 6, "arcane", 20),
        ("cover", "Cover", "Support", 2, 2, 2, "ward", 35),
        ("read_stance", "Read Stance", "Support", 5, 3, 2, "mark", 5),
        ("hold_line", "Hold the Line", "Support", 12, 5, 3, "ward", 70),
    )),
    "Seer": _lessons("seer", (
        ("glimpse", "Glimpse", "Support", 1, 1, 1, "mark", 4, "", "Abilities"),
        ("farseal", "Farseal", "Support", 2, 2, 2, "ward", 30, "", "Abilities"),
        ("mind_flare", "Mind Flare", "Combat", 4, 2, 2, "arcane", 6, "", "Abilities"),
        ("echo_glass", "Echo Glass", "Combat", 6, 3, 3, "arcane", 10, ECHO_ANALECT, "Abilities"),
        ("premonition", "Premonition", "Support", 8, 3, 3, "ward", 50, "", "Abilities"),
        ("star_thread", "Star Thread", "Combat", 10, 4, 4, "arcane", 16, "", "Abilities"),
        ("destiny_mark", "Destiny Mark", "Support", 12, 4, 3, "mark", 15, "", "Abilities"),
        ("moon_pulse", "Moon Pulse", "Combat", 15, 5, 5, "arcane", 24, "", "Abilities"),
        ("veil_sight", "Veil Sight", "Support", 18, 6, 4, "ward", 70, "", "Abilities"),
        ("final_omen", "Final Omen", "Combat", 20, 7, 7, "arcane", 36, "", "Abilities"),
        ("gale", "Gale", "Arcane", 2, 1, 2, "arcane", 4, "", "Magic"),
        ("mist_ray", "Mist Ray", "Arcane", 4, 2, 3, "arcane", 8, "", "Magic"),
        ("lunar_drop", "Lunar Drop", "Arcane", 6, 3, 4, "arcane", 13, "", "Magic"),
        ("star_pulse", "Star Pulse", "Arcane", 9, 4, 5, "arcane", 19, "", "Magic"),
        ("dream_tide", "Dream Tide", "Arcane", 12, 5, 6, "arcane", 27, "", "Magic"),
        ("astral_flood", "Astral Flood", "Arcane", 16, 6, 8, "arcane", 38, "", "Magic"),
        # 7-move kit additions (movesets.md). Ids match the drawn manifest art.
        ("foretell", "Foretell", "Support", 2, 1, 2, "kit", 0, "", "Abilities"),
        ("starfall_omen", "Starfall Omen", "Arcane", 5, 2, 5, "kit", 4, "", "Magic"),
        ("forewarn", "Forewarn", "Support", 7, 3, 4, "kit", 30, "", "Abilities"),
        ("twist_of_fate", "Twist of Fate", "Support", 9, 4, 4, "kit", 0, "", "Abilities"),
        ("prophecy", "Prophecy", "Support", 12, 5, 7, "kit", 0, "", "Abilities"),
    )),
    "Sollers": _lessons("sollers", (
        ("knife_flick", "Knife Flick", "Combat", 1, 1, 0, "physical", 2, "", "Abilities", "throw"),
        ("pilfer", "Steal", "Support", 2, 2, 1, "steal", 0, "", "Abilities"),
        ("backstab", "Backstab", "Combat", 4, 3, 3, "physical", 11, "", "Abilities", "weapon"),
        ("feint", "Feint", "Support", 6, 3, 2, "mark", 7, "", "Abilities"),
        ("shadowstep", "Shadowstep", "Support", 8, 3, 3, "ward", 50, "", "Abilities"),
        ("venom_edge", "Venom Edge", "Combat", 8, 4, 4, "physical", 19, "", "Abilities", "weapon"),
        ("smokescreen", "Smoke Veil", "Support", 6, 3, 3, "kit", 0, "", "Magic"),
        ("cutpurse_mark", "Sollers' Mark", "Support", 15, 6, 3, "mark", 20, "", "Abilities"),
        ("stitch_up", "Stitch Up", "Healing", 2, 2, 2, "heal", 11, "", "Magic"),
        ("smoke_spark", "Smoke Spark", "Arcane", 3, 2, 2, "arcane", 5, ECHO_ANALECT, "Magic"),
        ("fox_fire", "Fox Fire", "Arcane", 12, 5, 5, "arcane", 20, "", "Magic"),
        ("sleight_of_hand", "Sleight of Hand", "Support", 10, 4, 4, "kit", 5, "", "Abilities"),
    )),
    "Saint": _lessons("saint", (
        ("vigil_strike", "Vigil Strike", "Combat", 1, 1, 1, "physical", 4, "", "Abilities", "weapon"),
        ("smite", "Smite", "Combat", 3, 2, 3, "physical", 11, "", "Abilities", "weapon"),
        ("mend", "Mend", "Healing", 1, 1, 3, "heal", 18, "", "Magic"),
        ("restoration", "Restoration", "Healing", 8, 4, 5, "heal", 39, "", "Magic"),
        ("litany", "Litany", "Healing", 11, 5, 4, "restore", 8, "", "Magic"),
        ("votive_flame", "Votive Flame", "Arcane", 3, 2, 2, "arcane", 5, ECHO_ANALECT, "Magic"),
        ("sanctuary", "Sanctuary", "Support", 5, 3, 4, "ward", 65, "", "Magic"),
        ("purify", "Purify", "Healing", 7, 3, 4, "kit", 0, "", "Magic"),
        ("benediction", "Benediction", "Healing", 10, 4, 7, "kit", 14, "", "Magic"),
    )),
    "Weaver": _lessons("weaver", (
        ("silkbolt", "Silkbolt", "Arcane", 1, 1, 2, "arcane", 4),
        ("black_thread", "Black Thread", "Arcane", 8, 3, 4, "link", 50, "", "Magic"),
        ("read_the_strand", "Read the Strand", "Support", 7, 3, 1, "kit", 20, "", "Abilities"),
        ("onyx_lash", "Onyx Lash", "Arcane", 9, 4, 3, "kit", 4, "", "Magic"),
        ("weft_snare", "Weft Snare", "Arcane", 11, 4, 4, "kit", 70, "", "Magic"),
        ("hush", "Hush", "Support", 12, 5, 2, "kit", 80, "", "Abilities"),
        ("tether_pact", "Tether Pact", "Support", 14, 5, 4, "kit", 30, "", "Magic"),
        ("closing_verse", "Closing Verse", "Arcane", 17, 6, 8, "kit", 4, "", "Magic"),
    )),
    RIQIZAURKEIS: _lessons("reliquary", (
        ("retribution", "Retribution", "Arcane", 10, 4, 10, "reliquary", 50, "", "Magic"),
        ("mourners_veil", "Mourner's Veil", "Support", 7, 3, 2, "ward", 30, "", "Magic"),
        ("lid_shut", "Lid Shut", "Support", 8, 3, 0, "kit", 60, "", "Abilities"),
        ("hollow_tithe", "Hollow Tithe", "Arcane", 11, 4, 3, "kit", 4, "", "Magic"),
        ("grave_weight", "Grave Weight", "Support", 13, 5, 4, "kit", 25, "", "Magic"),
        ("ashen_hush", "Ashen Hush", "Support", 15, 6, 5, "kit", 20, "", "Magic"),
        ("twin_reliquary", "Twin Reliquary", "Support", 17, 6, 8, "kit", 75, "", "Magic"),
    )),
    "Tidecaller": _lessons("tidecaller", (
        ("tide_dart", "Tide Dart", "Arcane", 1, 1, 2, "arcane", 4),
        ("rolling_tide", "Rolling Tide", "Healing", 2, 1, 4, "kit", 8, "", "Magic"),
        ("undertow", "Undertow", "Arcane", 3, 2, 2, "kit", 4, "", "Abilities"),
        ("rinse", "Rinse", "Healing", 4, 2, 2, "kit", 6, "", "Magic"),
        ("swell", "Swell", "Support", 5, 2, 0, "kit", 50, "", "Abilities"),
        ("ebb", "Ebb", "Healing", 6, 3, 3, "kit", 40, "", "Magic"),
        ("sea_mist", "Sea Mist", "Support", 9, 4, 4, "kit", 20, "", "Magic"),
        ("spring_tide", "Spring Tide", "Healing", 12, 5, 8, "kit", 8, "", "Magic"),
    )),
}

# The 7 learnable moves per class, in learn order (movesets.md, fixed character levels).
# Other entries stay in LESSONS for old saves, enemy skill art, and FX lookups.
KITS = {
    "Seer": ("foretell", "mind_flare", "starfall_omen", "lunar_drop", "forewarn", "twist_of_fate", "prophecy"),
    "Tidecaller": ("rolling_tide", "undertow", "rinse", "swell", "ebb", "sea_mist", "spring_tide"),
    "Weaver": ("read_the_strand", "black_thread", "onyx_lash", "weft_snare", "hush", "tether_pact", "closing_verse"),
    "Sollers": ("knife_flick", "pilfer", "smoke_spark", "backstab", "smokescreen", "venom_edge", "sleight_of_hand"),
    RIQIZAURKEIS: ("mourners_veil", "lid_shut", "retribution", "hollow_tithe", "grave_weight", "ashen_hush", "twin_reliquary"),
    "Saint": ("mend", "vigil_strike", "smite", "sanctuary", "purify", "restoration", "benediction"),
}
MASTERY = {job: kit[-1] for job, kit in KITS.items()}
KEEP_LEGACY_LEARNED = True

# Status cures (movesets.md "Status cures"). Bleed and Curse are listed for when they
# exist; they are filtered against statuses.AILMENTS at use time.
RINSE_CURES = ("poison", "slow", "webbed", "bogged", "sinking", "bleed", "frozen")
PURIFY_CURES = ("silence", "darkness", "curse", "frozen")

KIT_TARGETS = {
    "seer_foretell": "single enemy", "seer_starfall_omen": "single enemy", "seer_forewarn": "single ally",
    "seer_twist_of_fate": "single enemy", "seer_prophecy": "single enemy",
    "sollers_smokescreen": "party", "sollers_sleight_of_hand": "single enemy",
    "saint_purify": "party", "saint_benediction": "party",
    "weaver_read_the_strand": "single enemy", "weaver_onyx_lash": "single enemy",
    "weaver_weft_snare": "single enemy", "weaver_hush": "single enemy",
    "weaver_tether_pact": "party", "weaver_closing_verse": "all enemies",
    "reliquary_lid_shut": "party", "reliquary_hollow_tithe": "single enemy",
    "reliquary_grave_weight": "single enemy", "reliquary_ashen_hush": "all enemies",
    "reliquary_twin_reliquary": "party",
    "tidecaller_rolling_tide": "party", "tidecaller_undertow": "single enemy",
    "tidecaller_rinse": "single ally", "tidecaller_swell": "party", "tidecaller_ebb": "single ally",
    "tidecaller_sea_mist": "party", "tidecaller_spring_tide": "party",
}

# Menu text for kit moves and reused moves whose behaviour changed (from movesets.md).
KIT_TEXT = {
    "seer_foretell": "Mark a foe: shows weakness, +20% damage 3 turns.",
    "seer_starfall_omen": "2.2x magic damage to one foe, ignoring armor.",
    "seer_lunar_drop": "Deal twice Magic + 13. +25% on a Foretold foe.",
    "seer_forewarn": "Ally: +30% evasion 2 turns, next turn sooner.",
    "seer_twist_of_fate": "Push one foe back one slot in the turn order.",
    "seer_prophecy": "Foresee and cancel this foe's next action.",
    "tidecaller_rolling_tide": "Heal party 8 + Magic now and next turn.",
    "tidecaller_undertow": "1.2x magic water hit. Delays the foe a slot.",
    "tidecaller_rinse": "Cure body ailments on one ally, heal 6 + Magic.",
    "tidecaller_swell": "Gather water: next wave move +50% (to x2).",
    "tidecaller_ebb": "Restore 60% of an ally's last damage taken.",
    "tidecaller_sea_mist": "Party +20% evasion 2 turns; foes -10% accuracy.",
    "tidecaller_spring_tide": "Party regen 8 + Magic 3 turns, plus a 40% Ebb.",
    "weaver_read_the_strand": "Mark a foe: your next spell on it +20%.",
    "weaver_onyx_lash": "1.6x magic damage, +25% on a linked foe.",
    "weaver_weft_snare": "70% Webbed; both ends if the foe is linked.",
    "weaver_hush": "80% Silence; certain on a linked foe.",
    "weaver_tether_pact": "Link both allies 3 turns: share 30% of damage.",
    "weaver_closing_verse": "Detonate the thread: 2.0x magic to linked foes.",
    "sollers_knife_flick": "Strength + 2 thrown hit. Next turn comes sooner.",
    "sollers_pilfer": "Roll the steal slots; may pocket 5 gold.",
    "sollers_backstab": "Strength + 11. Crits on a delayed or marked foe.",
    "sollers_smokescreen": "Drop out of enemy targeting until next turn.",
    "sollers_sleight_of_hand": "Foe's next attack hits another foe. +5 gold.",
    "reliquary_mourners_veil": "One ally takes 30% less damage to next turn.",
    "reliquary_lid_shut": "Guard 60%; 25% of damage taken becomes MP.",
    "reliquary_retribution": "Store half the party's harm 3 phases, release it.",
    "reliquary_hollow_tithe": "1.0x magic damage; heal half of it.",
    "reliquary_grave_weight": "One foe deals 25% less damage for 3 turns.",
    "reliquary_ashen_hush": "All foes deal 20% less damage for 2 turns.",
    "reliquary_twin_reliquary": "Once a battle: next reliquary stores 75%.",
    "saint_purify": "Party: cure Silence, Darkness and Frozen.",
    "saint_benediction": "Heal party 14 + Magic, regen 4 for 3 turns.",
}

# Old learned ids that map to a kit move when a save is loaded.
KIT_MIGRATION = {"seer_glimpse": "seer_foretell", "seer_premonition": "seer_forewarn"}
# Pure renames: same move, new id. Saves are rewritten on load (see rename_researched).
RENAMED_LESSONS = {"reliquary_return_the_wound": "reliquary_retribution"}


def rename_researched(member):
    """Rewrite renamed lesson ids in a loaded member, keeping order and dropping duplicates."""
    out = []
    for lesson_id in member.get("researched", ()):
        lesson_id = RENAMED_LESSONS.get(lesson_id, lesson_id)
        if lesson_id not in out:
            out.append(lesson_id)
    if "researched" in member:
        member["researched"] = out
    return member

_LEARNABLE = {job: frozenset(kit) for job, kit in KITS.items()}

# Preserve researched progress when loading a journey made before the pool revision.
LEGACY_SEER_IDS = dict(zip(
    ("threadcut", "split_omen", "fate_edge", "second_wind", "mindspring", "silver_spark",
     "echo_lance", "starfall_omen", "nightglass", "astral_ray", "dark_meridian",
     "foretell", "forewarn", "shale_reading", "fate_screen"),
    ("mind_flare", "echo_glass", "star_thread", "farseal", "premonition", "gale",
     "mist_ray", "lunar_drop", "star_pulse", "dream_tide", "astral_flood",
     "glimpse", "premonition", "destiny_mark", "veil_sight")))

def researched_ids(member):
    known = set(member.get("researched", ()))
    if current_job(member) == "Seer":
        known.update("seer_" + new for old, new in LEGACY_SEER_IDS.items() if "seer_" + old in known)
    known.update(new for old, new in KIT_MIGRATION.items() if old in known)
    known.update(new for old, new in RENAMED_LESSONS.items() if old in known)
    return known


def lessons_for(member):
    job = current_job(member)
    entries = LESSONS.get(job, LESSONS["Unbound"])
    kit = KITS.get(job)
    if kit is None:
        return entries
    by_key = {lesson.id.split("_", 1)[1]: lesson for lesson in entries}
    pool = tuple(by_key[key] for key in kit)
    if not KEEP_LEGACY_LEARNED:
        return pool
    # Caleb's earlier pool rule: a journey keeps moves it already researched, but
    # nothing outside the 7-move kit can be newly learned.
    known = set(member.get("researched", ()))
    if job == "Seer":
        known.update("seer_" + new for old, new in LEGACY_SEER_IDS.items() if "seer_" + old in known)
    kept = tuple(lesson for lesson in entries if lesson.id in known and lesson not in pool
                 and lesson.id not in KIT_MIGRATION)
    return pool + kept


def kit_for(job):
    """The class's 7 learnable moves, ignoring anything an old save kept."""
    entries = {lesson.id.split("_", 1)[1]: lesson for lesson in LESSONS.get(job, ())}
    return tuple(entries[key] for key in KITS.get(job, ()))


def initialize_research(member):
    member.setdefault("rp", 2)
    member.setdefault("researched", [])
    member.setdefault("observations", [])


def record_observation(party, move):
    """Keep witnessed move names so a later class can use the same discoveries."""
    for member in party:
        if member["hp"] > 0 and "researched" in member:
            seen = member.setdefault("observations", [])
            if move not in seen:
                seen.append(move)


def research_status(member, lesson, analects):
    if lesson.id in researched_ids(member):
        return "Learned"
    if member.get("level", 1) < lesson.level:
        return f"Reach Lv {lesson.level}"
    if lesson.source in ANALECTS and not analects.get(lesson.source, 0):
        return f"Find {lesson.source}"
    if lesson.source.startswith("Witness ") and lesson.source[8:] not in member.get("observations", ()):
        return lesson.source
    if member.get("rp", 0) < lesson.rp:
        return "Need more RP"
    return "Ready"


def research_lesson(member, lesson, analects):
    if lesson not in lessons_for(member) or (current_job(member) in KITS and lesson not in kit_for(current_job(member))
                                              and lesson.id not in researched_ids(member)):
        return "That entry belongs to another path."
    status = research_status(member, lesson, analects)
    if status != "Ready":
        return status
    member["rp"] -= lesson.rp
    member["researched"].append(lesson.id)
    return f"Learned {lesson.name}."
