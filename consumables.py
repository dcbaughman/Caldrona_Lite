"""Restoratives shared by the field menu, merchant, and battle."""
from equipment import stat_value
from stats import POTION_HEAL

SUPPLIES = {
    "Potion": (10, "Restores up to 30 HP."),
    "Ether": (18, "Restores up to 8 MP."),
    "Ember Feather": (30, "Revives a fainted ally at 25% HP."),
    "Remedy": (12, "Cures Poison, Frozen, Darkness, Silence, and Webbed."),
    "Pitch Torch": (8, "A pitch-soaked torch. Fire loosens the silk on the den gate."),
}

# Owned from a find, never from a shop. Sell price 0 is a placeholder.
RARE_SUPPLIES = {
    "Ember Talisman": "Revives a fainted ally at full HP. Not sold.",
}

def item_gain_text(name, count=1):
    return f"+{count} {name}"


def apply_supply(name, member, ailments=None):
    """Return whether the item was used and a message for the player."""
    target = member["name"]
    if name in ("Ember Talisman", "Ember Feather"):
        if member["hp"] > 0:
            return False, f"{target} is still standing."
        max_hp = stat_value(member, "max_hp")
        member["hp"] = max_hp if name == "Ember Talisman" else max(1, max_hp // 4)
        member.pop("ailments", None)
        if ailments is not None:
            ailments.clear()
        return True, f"{target} rises with {member['hp']} HP!"
    if member["hp"] <= 0:
        return False, f"{name} cannot revive a fainted member."
    if name == "Remedy":
        if ailments is None:ailments=member.get("ailments")
        if not ailments:
            return False, f"{target} has no ailments to cure."
        ailments.clear()
        return True, f"{target}'s ailments are cleansed."
    if name == "Pitch Torch":
        return False, "The torch is for the silk on the den gate."
    if name not in ("Potion", "Ether"):
        return False, "That supply cannot be used."
    key, amount = ("mp", 8) if name == "Ether" else ("hp", POTION_HEAL)
    current = member.get(key, 0)
    restored = min(amount, stat_value(member, f"max_{key}") - current)
    if restored <= 0:
        return False, f"{target} already has full {key.upper()}."
    member[key] = current + restored
    return True, f"{target} recovered {restored} {key.upper()}."
