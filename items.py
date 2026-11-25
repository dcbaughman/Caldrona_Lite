"""Icon paths for supplies and equipment.

Prices and effects live in ``consumables.py``. Gear stats and who may wear a
piece live in ``equipment.py``. This module only finds the 32×32 pictures.
"""
from pathlib import Path

from consumables import RARE_SUPPLIES, SUPPLIES

ROOT = Path(__file__).resolve().parent
ITEMS_DIR = ROOT / "assets" / "items"

SUPPLY_ICONS = {
    "Potion": "potions/health_potion.png",
    "Ether": "potions/mana_potion.png",
    "Remedy": "potions/antidote_potion.png",
    "Ember Feather": "potions/ember_feather.png",
    "Ember Talisman": "potions/ember_talisman.png",
    "Pitch Torch": "goods/torch.png",
}


def supply_icon(name: str) -> Path | None:
    relative = SUPPLY_ICONS.get(name)
    if not relative:
        return None
    path = ITEMS_DIR / relative
    return path if path.is_file() else None


def gear_icon(item) -> Path | None:
    relative = getattr(item, "icon", "") if item is not None else ""
    if not relative:
        return None
    path = ITEMS_DIR / relative
    return path if path.is_file() else None


def known_supply(name: str) -> bool:
    return name in SUPPLIES or name in RARE_SUPPLIES
