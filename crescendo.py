"""Crescendo loadouts and per-character charge."""
from dataclasses import dataclass

from classes import RIQIZAURKEIS, current_job


MAX_CHARGE = 100
HIT_CHARGE = 16
SUPPORT_CHARGE = 12


@dataclass(frozen=True)
class Crescendo:
    id: str
    name: str
    effect: str
    power: int
    description: str
    action_rank: int = 5
    # Extra behaviour handled by kit_effects.py (empty for the original moves).
    rider: str = ""
    element: str | None = None

    @property
    def target(self):
        if self.effect in ("sweep", "magic_sweep", "field"):
            return "all enemies"
        if self.effect in ("strike", "arcane", "riposte"):
            return "single enemy"
        return "party"


LOADOUTS = {
    "Unbound": (
        Crescendo("rising_edge", "Rising Edge", "strike", 18,
                  "Heavy weapon strike against one enemy."),
        Crescendo("quarry_break", "Quarry Break", "sweep", 7,
                  "Sweep every enemy with a physical strike."),
        Crescendo("second_wind", "Second Wind", "heal", 14,
                  "Restore 14 HP plus Magic to every standing ally."),
        Crescendo("steady_line", "Steady Line", "ward", 45,
                  "Ward the standing party against 45% of incoming damage until their next turns."),
    ),
    # Order is the unlock order: C1 is free on bind, C2-C4 follow the class counter.
    "Seer": (
        Crescendo("starbreak", "Starbreak", "arcane", 18,
                  "Concentrate starlight into one heavy magical hit."),
        Crescendo("clear_sky", "Clear Sky", "mp", 5,
                  "Restore up to 5 MP to every standing ally."),
        Crescendo("starlit_shelter", "Starlit Shelter", "ward", 55,
                  "Ward the standing party against 55% of incoming damage until their next turns."),
        Crescendo("constellation_sweep", "Constellation Sweep", "magic_sweep", 11,
                  "Scatter starlight across every enemy."),
    ),
    "Tidecaller": (
        Crescendo("flood_tide", "Flood Tide", "heal", 12,
                  "Heal the party 12 plus Magic now and again next turn.", rider="tide_again"),
        Crescendo("riptide", "Riptide", "magic_sweep", 9,
                  "Water on every enemy. Each is pulled back one turn slot.", rider="delay_all", element="water"),
        Crescendo("slack_water", "Slack Water", "party", 6,
                  "Cleanse every ailment from the party and restore 6 MP each.", rider="slack"),
        Crescendo("return_tide", "Return Tide", "party", 0,
                  "Rewind every ally to the HP they had before the last enemy round.", rider="rewind"),
    ),
    "Weaver": (
        Crescendo("onyx_sever", "Onyx Sever", "arcane", 19,
                  "Snap a shadow strand for heavy Onyx damage to one enemy."),
        Crescendo("shadow_canopy", "Shadow Canopy", "ward", 50,
                  "Ward the standing party against 50% of incoming damage until their next turns."),
        Crescendo("silken_reprieve", "Silken Reprieve", "heal", 16,
                  "Restore 16 HP plus Magic to every standing ally."),
        Crescendo("black_silk_storm", "Black Silk Storm", "magic_sweep", 11,
                  "Sweep every enemy's shadow with Onyx silk."),
    ),
    "Sollers": (
        Crescendo("gilded_strike", "Gilded Strike", "strike", 20,
                  "A heavy physical strike against one enemy."),
        Crescendo("lucky_recovery", "Lucky Recovery", "self_restore", 22,
                  "Restore up to 22 of your own HP and 4 MP."),
        Crescendo("curtain_call", "Curtain Call", "riposte", 10,
                  "Strike one enemy and gain a 45% ward until your next turn."),
        Crescendo("knife_rain", "Knife Rain", "sweep", 8,
                  "Fling blades at every enemy."),
    ),
    RIQIZAURKEIS: (
        Crescendo("lid_crack", "Lid Crack", "arcane", 18,
                  "One heavy hit. x1.5 while the reliquary is open.", rider="relic_x15"),
        Crescendo("mourning_bell", "Mourning Bell", "magic_sweep", 10,
                  "A bell on every enemy. They deal 20% less damage for 2 turns.", rider="weaken_all"),
        Crescendo("ashen_vespers", "Ashen Vespers", "ward", 55,
                  "Ward the standing party against 55% of incoming damage until their next turns."),
        Crescendo("nox_sepulta", "Nox Sepulta", "party", 0,
                  "For one round no ally falls below 1 HP. Lethal harm is stored.", rider="nox"),
    ),
    "Saint": (
        Crescendo("dawn_chorus", "Dawn Chorus", "heal", 22,
                  "Restore 22 HP plus Magic to every standing ally."),
        Crescendo("radiant_verdict", "Radiant Verdict", "arcane", 18,
                  "Deliver a heavy burst of Radiance against one enemy."),
        Crescendo("sanctuary_bell", "Sanctuary Bell", "ward", 65,
                  "Ward the standing party against 65% of incoming damage until their next turns."),
        Crescendo("last_light", "Last Light", "revive", 30,
                  "Revive every fallen ally with 30% of their maximum HP."),
    ),
}


# Crescendo unlocks (movesets.md "Crescendo Unlocks"): C1 free on bind, C2/C3/C4
# at the class counter thresholds; C4 also needs the class mastery move.
UNLOCKS = {
    "Seer": ("Foretell marks landed", (10, 30, 60), "seer_prophecy"),
    "Tidecaller": ("HP restored", (500, 1500, 3000), "tidecaller_spring_tide"),
    "Weaver": ("hits through a Black Thread", (10, 30, 60), "weaver_closing_verse"),
    "Sollers": ("gold stolen with Pilfer", (50, 150, 300), "sollers_sleight_of_hand"),
    RIQIZAURKEIS: ("damage released by Retribution", (400, 1200, 2400), "reliquary_twin_reliquary"),
    "Saint": ("allies revived or saved", (5, 15, 30), "saint_benediction"),
}
PROGRESS_KEY = "crescendo_progress"


def choices_for(member):
    return LOADOUTS.get(current_job(member), LOADOUTS["Unbound"])


def progress(member):
    value = member.get(PROGRESS_KEY, 0)
    return value if type(value) is int and value > 0 else 0


def add_progress(member, job, amount):
    """Count toward a class's own counter; other classes' feats are ignored."""
    if amount > 0 and current_job(member) == job and job in UNLOCKS:
        member[PROGRESS_KEY] = progress(member) + int(amount)
        return True
    return False


def _knows(member, lesson_id):
    from research import researched_ids
    return lesson_id in researched_ids(member)


def is_unlocked(member, move):
    choices = choices_for(member)
    if move not in choices:
        return False
    job = current_job(member)
    rule = UNLOCKS.get(job)
    if rule is None:
        return True  # Unbound keeps its full original loadout.
    slot = choices.index(move)
    if slot == 0:
        return True
    _, thresholds, mastery = rule
    if progress(member) < thresholds[slot - 1]:
        return False
    return slot < 3 or _knows(member, mastery)


def unlock_text(member, move):
    """Short requirement line for the menu; empty when unlocked."""
    if is_unlocked(member, move):
        return ""
    label, thresholds, mastery = UNLOCKS[current_job(member)]
    slot = choices_for(member).index(move)
    need = f"{progress(member)}/{thresholds[slot - 1]} {label}"
    if slot == 3:
        from research import LESSONS
        name = next((x.name for x in LESSONS.get(current_job(member), ()) if x.id == mastery), mastery)
        need += f" + learn {name}"
    return need


def unlocked_choices(member):
    return tuple(move for move in choices_for(member) if is_unlocked(member, move))


def equipped_crescendo(member):
    choices = unlocked_choices(member)
    if not choices:
        return None
    return next((move for move in choices if move.id == member.get("crescendo_choice")), choices[0])


def charge(member):
    return member.get("crescendo_charge", 0)


def add_charge(member, amount):
    if member["hp"] > 0 and amount > 0:
        member["crescendo_charge"] = min(MAX_CHARGE, charge(member) + amount)
