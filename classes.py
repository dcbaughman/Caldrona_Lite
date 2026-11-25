"""Astral paths and the rules for binding them."""

BLUE_STONE = "first_stone"
NOKTAKORO = "noktakoro"
SENBRANKA = "senbranka"
RIQIZAURKEIS = "Riqizaurkeis"
BLUE_PATHS = ("Seer", "Tidecaller")
NIGHT_PATHS = ("Weaver", "Sollers", RIQIZAURKEIS)
STONE_PATHS = {BLUE_STONE: BLUE_PATHS, NOKTAKORO: NIGHT_PATHS, SENBRANKA: ("Saint",)}
STONE_NAMES = {BLUE_STONE: "Ondastela", NOKTAKORO: "Noktakoro", SENBRANKA: "Senbranka"}
JOBS = tuple(job for paths in STONE_PATHS.values() for job in paths)
# Home stone per class (movesets.md roster). Follows STONE_PATHS as Caleb edits it.
HOME_STONES = {job: stone for stone, paths in STONE_PATHS.items() for job in paths}
OUTFIT_JOBS = ("Seer", "Sollers", "Saint", "Weaver", RIQIZAURKEIS, "Tidecaller")
DESCRIPTIONS = {
    "Seer": "Pierces armor. Magic / MP.",
    "Sollers": "Extra gold. Agility / accuracy.",
    "Saint": "Guard heals. HP / defense.",
    "Weaver": "Wurdaro. Links enemies with spoken threads.",
    RIQIZAURKEIS: "Stores harm to release it as magic.",
    "Tidecaller": "Undifer. A caster attuned to water.",
}
EMBLEMS = {
    "Seer": "seer-emblem.png",
    "Tidecaller": "tidecaller-emblem.png",
    "Sollers": "cutpurse-emblem.png",
    "Saint": "saint-emblem.png",
    "Weaver": "weaver-emblem.png",
    RIQIZAURKEIS: "riqizaurkeis-emblem.png",
}


def current_job(member):
    """Recognize names used by older builds without allowing a respec."""
    job = member.get("job")
    return {"Cutpurse": "Sollers", "Saint Warrior": "Saint", "Black Reliquary": RIQIZAURKEIS,
            "Unbound": None}.get(job, job)


def bind_job(member, job, stone=None):
    """A class choice is permanent for the current journey.

    Binding does not grant, equip, or remove weapons. Gear is found, bought,
    or looted. ``classes`` on a weapon only says who may equip it later.
    """
    if job not in JOBS or current_job(member):
        return False
    if stone is not None and job not in STONE_PATHS.get(stone, ()):
        return False
    member["job"] = job
    if stone is not None:
        member["attuned_stone"] = stone
    member.pop("crescendo_choice", None)
    return True
