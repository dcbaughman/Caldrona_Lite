"""Equipment definitions and the shared party gear inventory.

Add items to CATALOG with a unique id, one of the four SLOTS, and stat bonuses.
The inventory stores total owned copies; equipment on party members reserves
copies, so the same sword cannot be worn by two characters at once.

Pack weapons are extra catalog rows. Their ATK, SPD, REACH, PEN, magic bonus,
and suggested price are stored and are not added to ``bonuses``, so they do
not change the damage, defense, or shop prices already in the game.
"""
import json
from dataclasses import dataclass, field
from pathlib import Path
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
    icon: str = ""
    # Suggested pack numbers. Battle and menus do not read these.
    atk: int = 0
    spd: int = 0
    reach: str = ""
    pen: int = 0
    tier: int = 0
    magic_bonus: int = 0
    basic_attack_fx: str = ""
    suggested_price: int = 0

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
        Equipment("training_sword", "Training Sword", "weapon", {"strength": 1}, "A reliable starter blade.", basic_attack_fx="sword_strike"),
        Equipment("miner_blade", "Miner's Blade", "weapon", {"strength": 2, "agility": -1}, "A heavier blade with a strong edge.", basic_attack_fx="sword_strike"),
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


def _pack_description(row):
    if row["id"] == "practice_sword":
        return "A blunt wooden trainer."
    if row["id"] == "sunsteel_blade":
        return "A blade from Sunrest Arms."
    notes = (row.get("notes") or "").strip()
    return notes[:96] if notes else row["name"]


def _load_pack_equipment():
    """Add starter-pack weapons beside the existing rows. Never replaces them."""
    path = Path(__file__).resolve().parent / "data" / "weapons_manifest.json"
    if not path.is_file():
        return
    data = json.loads(path.read_text(encoding="utf-8"))
    for row in data["weapons"]:
        if row["id"] in CATALOG:
            continue
        stats = row.get("suggested_stats") or {}
        item = Equipment(
            row["id"],
            row["name"],
            "weapon",
            {},
            _pack_description(row),
            jobs=tuple(row.get("classes") or ()),
            icon=row.get("icon") or "",
            atk=int(stats.get("ATK") or 0),
            spd=int(stats.get("SPD") or 0),
            reach=str(stats.get("REACH") if stats.get("REACH") is not None else ""),
            pen=int(stats.get("PEN") or 0),
            tier=int(row.get("suggested_tier") or 0),
            magic_bonus=int(row.get("suggested_magic_bonus") or 0),
            basic_attack_fx=row.get("basic_attack_fx") or "",
            suggested_price=int(row.get("suggested_price_gold") or 0),
        )
        CATALOG[item.id] = item
    if "spellbook" not in CATALOG:
        # Shield slot, Saint only. No picture. The magic bonus stays 0.
        CATALOG["spellbook"] = Equipment(
            "spellbook", "Spellbook", "shield", {},
            "A Saint's notes. Its magic bonus is stored and not applied.",
            jobs=("Saint",),
        )


_load_pack_equipment()
