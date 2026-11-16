"""Shop stock lists. No shop is placed in the world or drawn in a menu.

Each key in ``data/shops.json`` is a shop id. The value is catalog item ids
that shop is allowed to sell. ``get_shop_stock`` returns those items in order.
An unknown shop id yields an empty list.
"""
from __future__ import annotations

import json
from pathlib import Path

from items import Item, get_item

STOCK_PATH = Path(__file__).resolve().parent / "data" / "shops.json"


def shop_lists() -> dict[str, list[str]]:
    data = json.loads(STOCK_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("shops.json must map shop ids to item id lists")
    return data


def get_shop_stock(shop_id: str) -> list[Item]:
    rows = shop_lists().get(shop_id)
    if not rows:
        return []
    return [get_item(item_id) for item_id in rows]
