"""Astral paths and the rules for binding them."""

JOBS = ("Seer", "Sollers", "Saint")
DESCRIPTIONS = {
    "Seer": "Pierces armor. Magic / MP.",
    "Sollers": "Extra gold. Agility / accuracy.",
    "Saint": "Guard heals. HP / defense.",
}
EMBLEMS = {
    "Seer": "seer-emblem.png",
    "Sollers": "cutpurse-emblem.png",
    "Saint": "saint-emblem.png",
}


def current_job(member):
    """Recognize names used by older builds without allowing a respec."""
    job = member.get("job")
    return {"Cutpurse": "Sollers", "Saint Warrior": "Saint"}.get(job, job)


def bind_job(member, job):
    """A class choice is permanent for the current journey.

    Binding does not grant, equip, or remove weapons. Gear is found, bought,
    or looted. ``classes`` on a weapon only says who may equip it later.
    """
    if job not in JOBS or current_job(member):
        return False
    member["job"] = job
    return True
