"""Equipment definitions and the shared party gear inventory.

Add items to CATALOG with a unique id, one of the four SLOTS, and stat bonuses.
The inventory stores total owned copies; equipment on party members reserves
copies, so the same sword cannot be worn by two characters at once.
"""
from dataclasses import dataclass, field
from typing import Mapping

from classes import current_job

SLOTS = ("armor", "weapon", "shield", "accessory")
SLOT_LABELS = {"armor": "Armor", "weapon": "Weapon", "shield": "Shield", "accessory": "Accessory"}
STAT_LABELS = (
    ("max_hp", "Max HP"), ("max_mp", "Max MP"), ("strength", "Strength"),
    ("defense", "Defense"), ("magic", "Magic"), ("magic_defense", "Magic Def"),
    ("agility", "Agility"), ("luck", "Luck"), ("evasion", "Evasion"),
    ("accuracy", "Accuracy"),
)


@dataclass(frozen=True)
class Equipment:
    id: str
    name: str
    slot: str
    bonuses: Mapping[str, int] = field(default_factory=dict)
    description: str = ""
    # Empty tuples allow everyone. These can restrict future equipment.
    characters: tuple[str, ...] = ()
    jobs: tuple[str, ...] = ()

    def __post_init__(self):
        if self.slot not in SLOTS:
            raise ValueError(f"Unknown equipment slot: {self.slot}")
        unknown = set(self.bonuses) - {key for key, _ in STAT_LABELS}
        if unknown:
            raise ValueError(f"Unknown equipment stats: {', '.join(sorted(unknown))}")


# A small starter collection makes every slot usable while the larger catalog
# is being written. Nothing is automatically equipped or added to base stats.
CATALOG = {
    item.id: item for item in (
        Equipment("leather_vest", "Leather Vest", "armor", {"defense": 1}, "A simple, flexible vest."),
        Equipment("quarry_coat", "Quarry Coat", "armor", {"defense": 2, "agility": -1}, "Sturdy protection for the caves."),
        Equipment("training_sword", "Training Sword", "weapon", {"strength": 1}, "A reliable starter blade."),
        Equipment("miner_blade", "Miner's Blade", "weapon", {"strength": 2, "agility": -1}, "A heavier blade with a strong edge."),
        Equipment("wood_shield", "Wooden Shield", "shield", {"defense": 1}, "A light wooden shield."),
        Equipment("lucky_charm", "Lucky Charm", "accessory", {"luck": 1}, "A small trinket for good fortune."),
        Equipment("quartz_pendant", "Quartz Pendant", "accessory", {"magic_defense": 1, "max_mp": 2}, "A stone that steadies magic."),
    )
}
STARTING_GEAR = {
    "leather_vest": 1, "quarry_coat": 1,
    "training_sword": 1, "miner_blade": 1,
    "wood_shield": 1, "lucky_charm": 1, "quartz_pendant": 1,
}


def item_for(item_id):
    return CATALOG.get(item_id)


def worn_id(member, slot):
    return member.get("equipment", {}).get(slot)


def owned_items(owned, slot):
    """All owned items in this category, including copies being worn."""
    return sorted((item for item in CATALOG.values()
                   if item.slot == slot and owned.get(item.id, 0) > 0),
                  key=lambda item: (item.name.casefold(), item.id))


def available_count(owned, roster, item_id):
    in_use = sum(1 for member in roster for equipped in member.get("equipment", {}).values()
                 if equipped == item_id)
    return max(0, owned.get(item_id, 0) - in_use)


def stat_bonus(member, stat, equipment=None):
    equipped = member.get("equipment", {}) if equipment is None else equipment
    return sum(item.bonuses.get(stat, 0) for item_id in equipped.values()
               if (item := item_for(item_id)) is not None)


def stat_value(member, stat, default=0, equipment=None):
    value = member.get(stat, default) + stat_bonus(member, stat, equipment)
    return max(1 if stat in ("max_hp", "strength") else 0, value)


def preview_value(member, slot, item_id, stat):
    equipment = dict(member.get("equipment", {}))
    if item_id is None:
        equipment.pop(slot, None)
    else:
        equipment[slot] = item_id
    return stat_value(member, stat, equipment=equipment)


def can_wear(member, item):
    return ((not item.characters or member.get("name") in item.characters)
            and (not item.jobs or (current_job(member) or "Unbound") in item.jobs))


def equip(member, slot, item_id, owned, roster):
    """Equip or remove gear and return a message; invalid choices never mutate."""
    if slot not in SLOTS:
        return False, "Unknown equipment slot."
    previous = worn_id(member, slot)
    if item_id == previous:
        return False, "Already equipped." if item_id else "That slot is already empty."
    item = item_for(item_id) if item_id else None
    if item_id is not None:
        if item is None or item.slot != slot:
            return False, "That item cannot go in this slot."
        if not can_wear(member, item):
            return False, f"{member['name']} cannot equip that."
        if available_count(owned, roster, item_id) <= 0:
            return False, "All copies are equipped by other members."
    equipment = member.setdefault("equipment", {})
    if item is None:
        equipment.pop(slot, None)
    else:
        equipment[slot] = item.id
    # Reducing maximum HP/MP never revives or heals a character.
    if "hp" in member:
        member["hp"] = min(member["hp"], stat_value(member, "max_hp"))
    if "mp" in member:
        member["mp"] = min(member["mp"], stat_value(member, "max_mp"))
    return True, f"Equipped {item.name}." if item else f"Removed {SLOT_LABELS[slot].lower()}."
