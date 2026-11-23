"""Equipment definitions and the shared party gear inventory.

Add items to CATALOG with a unique id, one of the four SLOTS, and stat bonuses.
The inventory stores total owned copies; equipment on party members reserves
copies, so the same sword cannot be worn by two characters at once.

Pack weapons are extra catalog rows. Their ATK, SPD, REACH, PEN, magic bonus,
and suggested price are stored and are not added to ``bonuses``, so they do
not change the damage, defense, or shop prices already in the game.

Signature weapons from ``data/signature_lineup.json`` are four rungs per
weapon type. Main hands use the weapon slot. Saint spellbooks, Sollers
coshes, and Seer foci use the shield slot. Hooks are stored and not applied.
The borrowed bronze/iron pool stays in the catalog so old ids still resolve.
It is not part of ``class_kit`` and the cave-exit stall does not sell it.
"""
import hashlib
import json
import re
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
    # Signature lineup. ``rung`` 0 means this row is not part of the kit.
    # ``tier`` stays the old bronze/iron suggestion when the row had one.
    weapon_type: str = ""
    rung: int = 0
    hook: str = ""
    element: str = ""
    # Parsed placeholder. Each tuple is (kind, label, amount, qualifier).
    hook_parts: tuple = ()
    lineup_id: str = ""

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
        if item.hook_parts:
            # TODO: no-op. Hook numbers stay on the item and do not change stats.
            apply_signature_hook(member, item)
    # Reducing maximum HP/MP never revives or heals a character.
    if "hp" in member:
        member["hp"] = min(member["hp"], stat_value(member, "max_hp"))
    if "mp" in member:
        member["mp"] = min(member["mp"], stat_value(member, "max_mp"))
    return True, f"Equipped {item.name}." if item else f"Removed {SLOT_LABELS[slot].lower()}."


# lineup id -> Equipment, in lineup order. Class kits read this, not the
# borrowed pool that remains in CATALOG.
SIGNATURE: dict[str, Equipment] = {}

_ELEMENT_WORDS = {"holy", "ice", "dark", "poison", "fire", "starlight"}
_ABILITY_VS = re.compile(r"\+(\d+)%\s+(.+?)\s+vs\s+(.+)")
_ABILITY = re.compile(r"\+(\d+)%\s+(.+)")
_STATUS = re.compile(r"(\d+)%\s+(.+)")
_MAX_HP = re.compile(r"\+(\d+)\s+Max HP")
_MAX_MP = re.compile(r"\+(\d+)\s+Max MP")


def class_kit(job: str) -> tuple:
    """Signature weapons this class may equip, in lineup order.

    Practice swords, bronze/iron tiers, Saint wands and staves, and Sollers
    shortswords stay in CATALOG. They are not returned here.
    """
    return tuple(item for item in SIGNATURE.values() if job in item.jobs)


def _parse_hook(hook: str) -> tuple:
    """Split a suggested hook into data. Combat does not read the result.

    ``+N% Name`` is an ability percent. ``N% Name`` is a status chance.
    Element words are stored on ``element`` and are not repeated here.
    """
    parts = []
    for chunk in (hook or "").split("·"):
        text = chunk.strip()
        if not text or text.casefold() in _ELEMENT_WORDS:
            continue
        if (match := _ABILITY_VS.fullmatch(text)):
            parts.append(("ability_vs", match.group(2), int(match.group(1)), match.group(3)))
            continue
        if (match := _ABILITY.fullmatch(text)):
            parts.append(("ability", match.group(2), int(match.group(1)), ""))
            continue
        if (match := _STATUS.fullmatch(text)):
            parts.append(("status", match.group(2), int(match.group(1)), ""))
            continue
        if (match := _MAX_HP.fullmatch(text)):
            parts.append(("max_hp", "Max HP", int(match.group(1)), ""))
            continue
        if (match := _MAX_MP.fullmatch(text)):
            parts.append(("max_mp", "Max MP", int(match.group(1)), ""))
            continue
        if text == "+MAG":
            parts.append(("magic", "MAG", 0, ""))
            continue
        parts.append(("note", text, 0, ""))
    return tuple(parts)


def apply_signature_hook(member, item=None):
    """No-op. Signature hooks are data until an effect system exists.

    TODO: apply element attunement, ability percent, status chance, max HP,
    max MP, and +MAG from ``item.hook_parts``. The numbers are placeholders
    for Caleb to tune. This must not change HP, MP, or combat stats.
    """
    return None


def _signature_price(row, existing):
    """Placeholder gold. Existing catalog prices are left as they were."""
    if existing is not None and existing.suggested_price:
        return existing.suggested_price
    if int(row["rung"]) == 1:
        if row["type"] == "mace":
            return 60
        if row["type"] in {"dagger", "thrown knife", "cosh", "rod", "focus"}:
            return 50
        return 55
    return {2: 110, 3: 175, 4: 250}[int(row["rung"])]


def _icon_file(relative: str) -> Path:
    return Path(__file__).resolve().parent / "assets" / "items" / relative


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


def _signature_icon(row) -> str:
    return f"signature/{row['class'].lower()}/{Path(row['icon']).name}"


def _same_art(existing, row) -> bool:
    """True when this catalog id is already the lineup icon, byte for byte."""
    if not existing.icon:
        return False
    path = _icon_file(existing.icon)
    if not path.is_file():
        return False
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return digest == row["dest_sha256"]


def _load_signature_lineup():
    """Add the signature kit. Never deletes a catalog id or a PNG.

    An id whose current icon already matches the lineup is updated in place
    (same weapon, now carrying rung and hook data). An id that points at
    different art keeps that row, and the signature weapon is added beside it.
    """
    path = Path(__file__).resolve().parent / "data" / "signature_lineup.json"
    if not path.is_file():
        return
    data = json.loads(path.read_text(encoding="utf-8"))
    for row in data["weapons"]:
        relative = _signature_icon(row)
        icon_path = _icon_file(relative)
        digest = hashlib.sha256(icon_path.read_bytes()).hexdigest()
        if digest != row["dest_sha256"]:
            raise RuntimeError(f"{relative} sha256 {digest} != {row['dest_sha256']}")
        stats = row["suggested_stats"]
        lineup_id = row["id"]
        existing = CATALOG.get(lineup_id)
        if existing is not None and _same_art(existing, row):
            catalog_id = lineup_id
            basic_attack_fx = existing.basic_attack_fx
            tier = existing.tier
            bonuses = dict(existing.bonuses)
            characters = existing.characters
        else:
            catalog_id = lineup_id if existing is None else f"lineup_{lineup_id}"
            if catalog_id in CATALOG:
                raise RuntimeError(f"Signature id {catalog_id} is already in the catalog")
            basic_attack_fx = "sword_strike" if row["type"] == "dagger" else ""
            tier = 0
            bonuses = {}
            characters = ()
            existing = None
        reach = stats.get("REACH")
        item = Equipment(
            catalog_id,
            row["name"],
            row["slot"],
            bonuses,
            row.get("flavor") or row["name"],
            characters=characters,
            jobs=(row["class"],),
            icon=relative,
            atk=int(stats.get("ATK") or 0),
            spd=int(stats.get("SPD") or 0),
            reach=str(reach if reach is not None else ""),
            pen=int(stats.get("PEN") or 0),
            tier=tier,
            magic_bonus=int(row.get("suggested_magic_bonus") or 0),
            basic_attack_fx=basic_attack_fx,
            suggested_price=_signature_price(row, existing),
            weapon_type=row["type"],
            rung=int(row["rung"]),
            hook=row.get("hook") or "",
            element=row.get("element") or "",
            hook_parts=_parse_hook(row.get("hook") or ""),
            lineup_id=lineup_id,
        )
        if item.slot not in ("weapon", "shield"):
            raise RuntimeError(f"{lineup_id} slot {item.slot} is not weapon or shield")
        CATALOG[item.id] = item
        SIGNATURE[lineup_id] = item


_load_pack_equipment()
_load_signature_lineup()
