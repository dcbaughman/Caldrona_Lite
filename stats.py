"""Starting statistics for the first party and cavern creatures."""
from classes import current_job
from equipment import stat_value

RETRI = {"max_hp": 60, "max_mp": 8, "strength": 8, "defense": 2,
         "magic": 3, "magic_defense": 3, "agility": 8, "luck": 8,
         "evasion": 5, "accuracy": 8}
TEMUR = {"max_hp": 82, "max_mp": 6, "strength": 11, "defense": 4,
         "magic": 2, "magic_defense": 3, "agility": 5, "luck": 7,
         "evasion": 3, "accuracy": 7}
POTION_HEAL = 30
RETRI_HP_PER_LEVEL = 8


def member(name, base):
    result = {"name": name, **base}
    result.update(hp=base["max_hp"], mp=base["max_mp"], level=1, xp=0, equipment={})
    return result


def grow(member, old_level, new_level):
    """Apply a member’s individual level gains."""
    for level in range(old_level + 1, new_level + 1):
        job = current_job(member)
        hp_gain = (10 if member["name"] == "Temur" else RETRI_HP_PER_LEVEL) + (2 if job == "Saint" else 0)
        member["max_hp"] += hp_gain
        if member["hp"] > 0:
            member["hp"] = min(stat_value(member, "max_hp"), member["hp"] + hp_gain)
        member["strength"] = member.get("strength", 8) + 1
        if level % 2 == 0:
            for stat in ("defense", "magic", "magic_defense", "agility"):
                member[stat] = member.get(stat, 0) + 1
            member["max_mp"] = member.get("max_mp", 0) + 1
            member["mp"] = min(stat_value(member, "max_mp"), member.get("mp", 0) + 1)
        if job == "Seer":
            member["magic"] = member.get("magic", 0) + 1
            member["max_mp"] = member.get("max_mp", 0) + 1
            member["mp"] = min(stat_value(member, "max_mp"), member.get("mp", 0) + 1)
            if level % 2 == 0:
                member["magic_defense"] = member.get("magic_defense", 0) + 1
        elif job == "Sollers":
            member["agility"] = member.get("agility", 0) + 1
            if level % 2 == 0:
                member["strength"] += 1
            else:
                member["accuracy"] = member.get("accuracy", 0) + 1
        elif job == "Saint":
            stat = "defense" if level % 2 == 0 else "magic_defense"
            member[stat] = member.get(stat, 0) + 1
