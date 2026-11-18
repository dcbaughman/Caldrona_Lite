"""Restoratives shared by the field menu, merchant, and battle."""
from equipment import stat_value
from stats import POTION_HEAL

SUPPLIES = {
    "Potion": (10, "Restores up to 30 HP."),
    "Ether": (18, "Restores up to 8 MP."),
    "Ember Feather": (30, "Revives a fainted ally at 25% HP."),
}


def apply_supply(name, member):
    """Return whether the item was used and a message for the player."""
    target = member["name"]
    if name == "Ember Feather":
        if member["hp"] > 0:
            return False, f"{target} is still standing."
        member["hp"] = max(1, stat_value(member, "max_hp") // 4)
        return True, f"{target} rises with {member['hp']} HP!"
    if member["hp"] <= 0:
        return False, f"{name} cannot revive a fainted member."
    key, amount = ("mp", 8) if name == "Ether" else ("hp", POTION_HEAL)
    current = member.get(key, 0)
    restored = min(amount, stat_value(member, f"max_{key}") - current)
    if restored <= 0:
        return False, f"{target} already has full {key.upper()}."
    member[key] = current + restored
    return True, f"{target} recovered {restored} {key.upper()}."
