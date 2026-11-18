"""Cave-exit merchant stock. No shop NPC is placed and no shop screen is drawn.

The stall lists tier-1 pack weapons plus Potion and Ether. Mana Potion in the
pack file is Ether. Antidote, Torch, Field Bandages, Ember Feather, and Ember
Talisman are not on this stall. Suggested stall prices stay in the json and
do not replace the prices in ``consumables.py``.
"""
from __future__ import annotations

import json
from pathlib import Path

from equipment import CATALOG

ROOT = Path(__file__).resolve().parent
CAVE_EXIT_STOCK_PATH = ROOT / "data" / "cave_exit_merchant_stock.json"

# The pack's "Mana Potion" is the existing Ether.
CAVE_EXIT_NAME_TO_ID = {
    "Potion": "Potion",
    "Mana Potion": "Ether",
}


def _stock():
    return json.loads(CAVE_EXIT_STOCK_PATH.read_text(encoding="utf-8"))


def cave_exit_ids() -> list[str]:
    data = _stock()
    weapons = [row["id"] for row in data["weapons"] if row["id"] in CATALOG]
    supplies = []
    for row in data["consumables"]:
        item_id = CAVE_EXIT_NAME_TO_ID.get(row["name"])
        if item_id:
            supplies.append(item_id)
    return weapons + supplies


def cave_exit_prices() -> dict[str, int]:
    """Suggested gold for the stall. Catalog and Merren prices are not these."""
    data = _stock()
    prices = {row["id"]: int(row["price_gold_suggested"]) for row in data["weapons"]}
    for row in data["consumables"]:
        item_id = CAVE_EXIT_NAME_TO_ID.get(row["name"])
        if item_id:
            prices[item_id] = int(row["price_gold_suggested"])
    return prices
