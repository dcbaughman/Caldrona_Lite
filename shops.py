"""Shop stock lists. No shop is placed in the world or drawn in a menu.

Each key in ``data/shops.json`` is a shop id. The value is catalog item ids
that shop is allowed to sell. ``get_shop_stock`` returns those items in order.
An unknown shop id yields an empty list.

``cave_exit_merchant`` is data only. Caleb is placing that NPC. Its prices come
from ``data/cave_exit_merchant_stock.json`` and override the catalog price on
the returned items, so the shared catalog price of Potion stays 40 while this
stall sells it for the suggested 15.
"""
from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from items import Item, get_item

ROOT = Path(__file__).resolve().parent
STOCK_PATH = ROOT / "data" / "shops.json"
CAVE_EXIT_STOCK_PATH = ROOT / "data" / "cave_exit_merchant_stock.json"

# The pack's "Mana Potion" is the existing Ether (mana_potion.png, 8 MP).
# Field Bandages already exists as field_bandages. Neither is added twice.
CAVE_EXIT_NAME_TO_ID = {
    "Potion": "potion",
    "Mana Potion": "ether",
    "Antidote": "antidote",
    "Field Bandages": "field_bandages",
    "Torch": "torch",
}


def shop_lists() -> dict[str, list[str]]:
    data = json.loads(STOCK_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("shops.json must map shop ids to item id lists")
    return data


def cave_exit_prices() -> dict[str, int]:
    """Suggested gold prices for the cave-exit stall, keyed by catalog id."""
    data = json.loads(CAVE_EXIT_STOCK_PATH.read_text(encoding="utf-8"))
    prices = {row["id"]: int(row["price_gold_suggested"]) for row in data["weapons"]}
    for row in data["consumables"]:
        item_id = CAVE_EXIT_NAME_TO_ID[row["name"]]
        prices[item_id] = int(row["price_gold_suggested"])
    return prices


def get_shop_stock(shop_id: str) -> list[Item]:
    rows = shop_lists().get(shop_id)
    if not rows:
        return []
    prices = cave_exit_prices() if shop_id == "cave_exit_merchant" else {}
    items = []
    for item_id in rows:
        item = get_item(item_id)
        if item_id in prices:
            price = prices[item_id]
            item = replace(item, buy_price=price, sell_price=price // 2)
        items.append(item)
    return items
