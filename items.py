"""Central item catalog for Caldrona Lite.

Shops are not placed in the world. ``data/shops.json`` names which catalog ids
a future shop may sell; ``shops.get_shop_stock`` reads that list.

The journey's base Potion count stays on ``CaldronaLite.potions`` and
``BattleModel.potions`` so the existing heal of ``stats.POTION_HEAL`` is
unchanged. Every other stack lives in the supplies dict.

Revive has no icon of its own in the main game's v7 set. It reuses the elixir
health flask and is flagged ``placeholder_icon``.

Poison is not inflicted in battle yet. Antidote clears ``member["status"]``
when that value is ``"poison"``.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path

from stats import POTION_HEAL

ROOT = Path(__file__).resolve().parent
ITEMS_DIR = ROOT / "assets" / "items"


@dataclass(frozen=True)
class WeaponProfile:
    """Suggested weapon numbers from the starter pack.

    ATK, SPD, REACH, PEN and the magic bonus are stored for Caleb to tune.
    Battle damage does not read them, so equipping a weapon does not change
    how hard a strike hits.
    """
    atk: int
    spd: int
    reach: int | str
    pen: int
    magic_bonus: int
    tier: int
    classes: tuple[str, ...]
    weapon_type: str
    basic_attack_fx: str | None
    notes: str


@dataclass(frozen=True)
class Item:
    id: str
    name: str
    category: str
    description: str
    buy_price: int
    sell_price: int
    stackable: bool
    max_stack: int
    icon: str
    effect: dict | None = None
    placeholder_icon: bool = False
    weapon: WeaponProfile | None = None


@dataclass(frozen=True)
class UseResult:
    ok: bool
    reason: str
    healed: int = 0
    restored_mp: int = 0
    revived: bool = False
    cured: str | None = None


def _item(item_id, name, category, description, buy, icon, *,
          effect=None, stackable=True, max_stack=99, placeholder=False,
          weapon=None):
    return Item(
        id=item_id,
        name=name,
        category=category,
        description=description,
        buy_price=buy,
        sell_price=buy // 2,
        stackable=stackable,
        max_stack=max_stack if stackable else 1,
        icon=icon,
        effect=effect,
        placeholder_icon=placeholder,
        weapon=weapon,
    )


def _gear(item_id, name, category, description, buy, icon, weapon=None, placeholder=False):
    return _item(item_id, name, category, description, buy, icon,
                 stackable=False, max_stack=1, weapon=weapon, placeholder=placeholder)


# Buy prices for goods the main game already sells match that shop list.
# New consumable prices live only in this catalog.
_ROWS = (
    _item("minor_potion", "Minor Potion", "consumable",
          "A slim vial. Restores a little HP.", 20,
          "potions/minor_health_potion.png", effect={"kind": "heal", "amount": 15}),
    _item("potion", "Potion", "consumable",
          "A round flask. Restores HP.", 40,
          "potions/health_potion.png", effect={"kind": "heal", "amount": POTION_HEAL}),
    _item("greater_potion", "Greater Potion", "consumable",
          "A shouldered bottle. Restores a lot of HP.", 90,
          "potions/greater_health_potion.png", effect={"kind": "heal", "amount": 60}),
    _item("elixir", "Elixir", "consumable",
          "A gold-collared flask. Restores all HP.", 200,
          "potions/elixir_health.png", effect={"kind": "full_heal"}),
    _item("antidote", "Antidote", "consumable",
          "Clears poison.", 30,
          "potions/antidote_potion.png", effect={"kind": "cure", "status": "poison"}),
    _item("revive", "Revive", "consumable",
          "Brings a fainted ally back with a quarter of their HP.", 150,
          "potions/elixir_health.png",
          effect={"kind": "revive", "percent": 25}, placeholder=True),
    _item("minor_ether", "Minor Ether", "consumable",
          "A slim blue vial. Restores a little MP.", 30,
          "potions/minor_mana_potion.png", effect={"kind": "restore_mp", "amount": 4}),
    _item("ether", "Ether", "consumable",
          "A blue flask. Restores MP.", 60,
          "potions/mana_potion.png", effect={"kind": "restore_mp", "amount": 8}),
    _item("greater_ether", "Greater Ether", "consumable",
          "A shouldered blue bottle. Restores a lot of MP.", 120,
          "potions/greater_mana_potion.png", effect={"kind": "restore_mp", "amount": 16}),
    _item("mana_elixir", "Mana Elixir", "consumable",
          "A gold-collared blue flask. Restores all MP.", 200,
          "potions/elixir_mana.png", effect={"kind": "restore_mp", "full": True}),
    _item("hearth_bread", "Hearth Bread", "food",
          "A loaf from the hearth. Restores a little HP.", 6,
          "food/hearth_bread.png", effect={"kind": "heal", "amount": 8}),
    _item("trail_meal", "Trail Meal", "food",
          "A packed bowl for the road. Restores HP.", 12,
          "food/trail_meal.png", effect={"kind": "heal", "amount": 16}),
    _item("travel_rations", "Travel Rations", "food",
          "Dried food for a long walk. Restores HP.", 20,
          "food/travel_rations.png", effect={"kind": "heal", "amount": 22}),
    _item("river_trout", "River Trout", "food",
          "A fresh catch. Restores a little HP.", 10,
          "food/river_trout.png", effect={"kind": "heal", "amount": 12}),
    _gear("practice_sword", "Practice Sword", "weapon",
          "A blunt wooden trainer.", 30, "weapons/practice_sword.png"),
    _gear("bronze_saber", "Bronze Saber", "weapon",
          "A curved bronze saber from Sunrest Arms.", 80, "weapons/bronze_saber.png"),
    _gear("wayfarer_spear", "Wayfarer Spear", "weapon",
          "A traveler's spear from Sunrest Arms.", 140, "weapons/wayfarer_spear.png"),
    _gear("sunsteel_blade", "Sunsteel Blade", "weapon",
          "A sunsteel blade from Sunrest Arms.", 240, "weapons/sunsteel_blade.png"),
    _gear("wood_axe", "Wood Axe", "tool",
          "An axe for timber.", 45, "weapons/wood_axe.png"),
    _gear("pickaxe", "Pickaxe", "tool",
          "A pick for ore.", 60, "goods/pickaxe.png"),
    _gear("fishing_rod", "Fishing Rod", "tool",
          "A rod for the river.", 35, "goods/fishing_rod.png"),
    _gear("torch", "Torch", "tool",
          "A wrapped torch.", 10, "goods/torch.png"),
    _gear("waterskin", "Waterskin", "tool",
          "A stitched waterskin.", 18, "goods/waterskin.png"),
    _gear("linen_vest", "Linen Vest", "armor",
          "A light linen vest.", 35, "armor/linen_vest.png"),
    _gear("leather_jerkin", "Leather Jerkin", "armor",
          "A stitched leather jerkin.", 75, "armor/leather_jerkin.png"),
    _gear("wooden_buckler", "Wooden Buckler", "armor",
          "A round wooden buckler, earth-toned.", 45, "armor/wooden_buckler.png"),
    _gear("iron_buckler", "Iron Buckler", "armor",
          "An iron buckler with a wind-metal face.", 70, "armor/iron_buckler.png"),
    _gear("bronze_roundel", "Bronze Roundel", "armor",
          "A bronze roundel with a thunder finish.", 110, "armor/bronze_roundel.png"),
    _gear("heater_shield", "Heater Shield", "armor",
          "A heater shield worked in fire colors.", 150, "armor/heater_shield.png"),
    _gear("kite_shield", "Kite Shield", "armor",
          "A kite shield with a water finish.", 170, "armor/kite_shield.png"),
    _gear("tower_shield", "Tower Shield", "armor",
          "A tall tower shield.", 210, "armor/tower_shield.png"),
    _gear("frost_shield", "Frost Shield", "armor",
          "A frost shield.", 190, "armor/frost_shield.png"),
    _gear("sunrest_shield", "Sunrest Shield", "armor",
          "Sunrest's holy shield.", 250, "armor/sunrest_shield.png"),
    _item("linen_thread", "Linen Thread", "material",
          "A spool of linen thread.", 8, "goods/linen_thread.png"),
    _item("leather_strips", "Leather Strips", "material",
          "Cut strips of leather.", 15, "goods/leather_strips.png"),
    _item("iron_rivets", "Iron Rivets", "material",
          "Domed iron rivets.", 22, "goods/iron_rivets.png"),
    _item("oak_wood", "Oak Wood", "material",
          "A split of oak.", 6, "goods/oak_wood.png"),
    _item("coal", "Coal", "material",
          "Three lumps of coal.", 4, "goods/coal.png"),
    _item("copper_ore", "Copper Ore", "material",
          "A copper nugget.", 8, "goods/copper_ore.png"),
    _item("copper_ingot", "Copper Ingot", "material",
          "A stamped copper bar.", 18, "goods/copper_ingot.png"),
    _item("iron_ore", "Iron Ore", "material",
          "An iron nugget.", 12, "goods/iron_ore.png"),
    _item("iron_ingot", "Iron Ingot", "material",
          "A stamped iron bar.", 28, "goods/iron_ingot.png"),
    _item("silver_ore", "Silver Ore", "material",
          "A silver nugget.", 20, "goods/silver_ore.png"),
    _item("silver_ingot", "Silver Ingot", "material",
          "A stamped silver bar.", 45, "goods/silver_ingot.png"),
    _item("gold_ore", "Gold Ore", "material",
          "A gold nugget.", 40, "goods/gold_ore.png"),
    _item("gold_ingot", "Gold Ingot", "material",
          "A stamped gold bar.", 90, "goods/gold_ingot.png"),
    _item("sunstone_ore", "Sunstone Ore", "material",
          "Sunstone still in the rock.", 60, "goods/sunstone_ore.png"),
    _item("sunsteel_ingot", "Sunsteel Ingot", "material",
          "A stamped sunsteel bar.", 140, "goods/sunsteel_ingot.png"),
    _item("crystal_shard", "Crystal Shard", "material",
          "A shard of cavern crystal.", 25, "goods/crystal_shard.png"),
    _item("amethyst", "Amethyst", "material",
          "A cut amethyst.", 35, "goods/amethyst.png"),
    _item("topaz", "Topaz", "material",
          "A cut topaz.", 40, "goods/topaz.png"),
    _item("onyx", "Onyx", "material",
          "A cut onyx.", 45, "goods/onyx.png"),
    _item("moonstone", "Moonstone", "material",
          "A cut moonstone.", 50, "goods/moonstone.png"),
    _item("emerald", "Emerald", "material",
          "A cut emerald.", 70, "goods/emerald.png"),
    _item("sapphire", "Sapphire", "material",
          "A cut sapphire.", 70, "goods/sapphire.png"),
    _item("ruby", "Ruby", "material",
          "A cut ruby.", 80, "goods/ruby.png"),
    _item("sunstone", "Sunstone", "material",
          "A cut sunstone.", 100, "goods/sunstone.png"),
    _gear("gold", "Gold", "currency",
          "A Sunrest coin. The journey keeps gold as a counter, not a pack stack.",
          1, "currency/gil_coin.png"),
)

def _profile_from_row(row):
    stats = row["suggested_stats"]
    return WeaponProfile(
        atk=int(stats["ATK"]),
        spd=int(stats["SPD"]),
        reach=stats["REACH"],
        pen=int(stats["PEN"]),
        magic_bonus=int(row.get("suggested_magic_bonus") or 0),
        tier=int(row["suggested_tier"]),
        classes=tuple(row["classes"]),
        weapon_type=row["weapon_type"],
        basic_attack_fx=row.get("basic_attack_fx") or None,
        notes=row.get("notes") or "",
    )


def _starter_weapons(existing_ids):
    """Pack weapons that are not already in the catalog.

    Practice Sword and Sunsteel Blade keep their existing name, price, text,
    and icon. Their suggested stats are attached later and do not replace those.
    """
    path = ROOT / "data" / "weapons_manifest.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    weapons = []
    profiles = {}
    for row in data["weapons"]:
        profile = _profile_from_row(row)
        profiles[row["id"]] = profile
        if row["id"] in existing_ids:
            continue
        weapons.append(_gear(
            row["id"], row["name"], "weapon",
            profile.notes or row["name"],
            int(row["suggested_price_gold"]),
            f"weapons/{row['id']}.png",
            weapon=profile,
        ))
    return tuple(weapons), profiles


_NEW_WEAPONS, _WEAPON_PROFILES = _starter_weapons({item.id for item in _ROWS})
_ALL_ITEMS = tuple(
    replace(item, weapon=_WEAPON_PROFILES[item.id]) if item.id in _WEAPON_PROFILES else item
    for item in (*_ROWS, *_NEW_WEAPONS)
)
CATALOG: dict[str, Item] = {item.id: item for item in _ALL_ITEMS}
BY_NAME: dict[str, Item] = {item.name: item for item in _ALL_ITEMS}

if len(BY_NAME) != len(CATALOG):
    raise RuntimeError("Item display names must be unique")


def get_item(item_id: str) -> Item:
    try:
        return CATALOG[item_id]
    except KeyError:
        raise KeyError(f"Unknown item id: {item_id}") from None


def item_by_name(name: str) -> Item | None:
    return BY_NAME.get(name)


def icon_file(item: Item | str) -> Path:
    if isinstance(item, str):
        item = get_item(item)
    return ITEMS_DIR / item.icon


def use_item(item_id: str, member: dict) -> UseResult:
    """Apply a consumable. Failed uses leave the member unchanged."""
    item = get_item(item_id)
    effect = item.effect
    if not effect:
        return UseResult(False, "not_consumable")
    kind = effect["kind"]
    if member.get("hp", 0) <= 0 and kind != "revive":
        return UseResult(False, "fainted")
    if kind == "heal":
        if member["hp"] >= member["max_hp"]:
            return UseResult(False, "full_hp")
        healed = min(effect["amount"], member["max_hp"] - member["hp"])
        member["hp"] += healed
        return UseResult(True, "healed", healed=healed)
    if kind == "full_heal":
        if member["hp"] >= member["max_hp"]:
            return UseResult(False, "full_hp")
        healed = member["max_hp"] - member["hp"]
        member["hp"] = member["max_hp"]
        return UseResult(True, "healed", healed=healed)
    if kind == "revive":
        if member["hp"] > 0:
            return UseResult(False, "not_fainted")
        percent = effect.get("percent", 25)
        healed = max(1, member["max_hp"] * percent // 100)
        member["hp"] = min(member["max_hp"], healed)
        return UseResult(True, "revived", healed=member["hp"], revived=True)
    if kind == "restore_mp":
        if "max_mp" not in member:
            return UseResult(False, "no_mp")
        current = member.get("mp", 0)
        if current >= member["max_mp"]:
            return UseResult(False, "full_mp")
        if effect.get("full"):
            restored = member["max_mp"] - current
            member["mp"] = member["max_mp"]
        else:
            restored = min(effect["amount"], member["max_mp"] - current)
            member["mp"] = current + restored
        return UseResult(True, "restored_mp", restored_mp=restored)
    if kind == "cure":
        # TODO: battles do not inflict poison yet. This only clears a flag
        # another system has already set on the member.
        status = effect.get("status", "poison")
        if member.get("status") != status:
            return UseResult(False, "no_status")
        member["status"] = None
        return UseResult(True, "cured", cured=status)
    return UseResult(False, "not_consumable")


def failure_message(result: UseResult, item: Item, member: dict) -> str:
    name = member.get("name", "They")
    if result.reason == "fainted":
        return f"A {item.name} cannot revive a fainted member."
    if result.reason == "full_hp":
        return name + " already has full HP."
    if result.reason == "not_fainted":
        return name + " is still standing."
    if result.reason == "no_mp":
        return name + " has no MP."
    if result.reason == "full_mp":
        return name + " already has full MP."
    if result.reason == "no_status":
        return name + " is not poisoned."
    if result.reason == "not_consumable":
        return f"{item.name} cannot be used yet."
    return "Nothing happens."


def success_message(result: UseResult, member: dict, *, battle: bool = False) -> str:
    name = member.get("name", "They")
    if result.reason == "healed":
        verb = "recovers" if battle else "recovered"
        return f"{name} {verb} {result.healed} HP."
    if result.reason == "revived":
        return f"{name} is back with {member['hp']} HP."
    if result.reason == "restored_mp":
        verb = "recovers" if battle else "recovered"
        return f"{name} {verb} {result.restored_mp} MP."
    if result.reason == "cured":
        return f"{name} is no longer poisoned."
    return "Nothing happens."
