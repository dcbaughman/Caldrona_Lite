"""Pack weapons in Caleb's equipment catalog, and the two Ember revives."""
import hashlib
import json
import struct
import tkinter as tk
import unittest
import zlib
from pathlib import Path

from abilities import learned_abilities, strike_variant
from classes import bind_job
from consumables import RARE_SUPPLIES, SUPPLIES, apply_supply
from equipment import CATALOG, STARTING_GEAR, can_wear, equip, stat_value
from items import gear_icon, supply_icon
from shops import cave_exit_ids, cave_exit_prices
from stats import RETRI, member

ROOT = Path(__file__).resolve().parent
GOLD = {
    (0xFF, 0xFA, 0xF0),
    (0xE6, 0xC8, 0x66),
    (0xC9, 0xA2, 0x27),
    (0x8F, 0x70, 0x19),
    (0x5C, 0x46, 0x12),
}


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _png_rgba(path):
    data = Path(path).read_bytes()
    self_check = data[12:16] == b"IHDR"
    if not self_check:
        raise AssertionError(path)
    width = int.from_bytes(data[16:20], "big")
    height = int.from_bytes(data[20:24], "big")
    pos = 8
    payload = b""
    while pos < len(data):
        length = int.from_bytes(data[pos:pos + 4], "big")
        kind = data[pos + 4:pos + 8]
        chunk = data[pos + 8:pos + 8 + length]
        if kind == b"IDAT":
            payload += chunk
        pos += 12 + length
        if kind == b"IEND":
            break
    raw = zlib.decompress(payload)
    stride = width * 4 + 1
    pixels = []
    for y in range(height):
        row = raw[y * stride + 1:(y + 1) * stride]
        pixels.append([tuple(row[x * 4:x * 4 + 4]) for x in range(width)])
    return pixels


# Paths are relative to assets/items/. Hashes are the wired 32x32 PNGs.
STARTING_GEAR_ICONS = {
    "leather_vest": ("armor/leather_vest.png", "a0f00bb7911bc83682a71249299554fbd17ad524b8861327ba631b0473e3a24e"),
    "quarry_coat": ("armor/quarry_coat.png", "a711eec3b296df456d6a246e69787aeeadf18d5e389fb2e174a96074297d522d"),
    "wood_shield": ("armor/wood_shield.png", "155bc8ac083c8b16317eeb4859cb7fac3c8aaeb44152a1bddf464eccca560b5b"),
    "training_sword": ("weapons/training_sword.png", "eb907a33b966c4d3181f10480fdf9510f982e08d14b4f15261b5db1ffce9815b"),
    "miner_blade": ("weapons/miner_blade.png", "7253e3d684954fa01625c7e4d2fbb5415206361068c69bdc8721c9a7dc9f6e39"),
    "lucky_charm": ("accessories/lucky_charm.png", "0c1f4a35278d353e9dd08804fc48f5e3a0adc27bc464d4bd290a08a6e999a2bc"),
    "quartz_pendant": ("accessories/quartz_pendant.png", "5370122248b370525c15fc0acd2ba1e7f247597e5f9eda6abfca1239668e3678"),
}


class PackEquipmentTests(unittest.TestCase):
    def test_starting_gear_icons_resolve_to_recorded_files(self):
        self.assertEqual(len(STARTING_GEAR_ICONS), 7)
        for item_id, (relative, digest) in STARTING_GEAR_ICONS.items():
            item = CATALOG[item_id]
            self.assertIn(item_id, STARTING_GEAR)
            self.assertEqual(item.icon, relative, item_id)
            path = gear_icon(item)
            self.assertIsNotNone(path, item_id)
            self.assertTrue(path.is_file(), item_id)
            self.assertEqual(path, ROOT / "assets" / "items" / relative)
            header = path.read_bytes()
            self.assertEqual(header[1:4], b"PNG", item_id)
            size = (int.from_bytes(header[16:20], "big"), int.from_bytes(header[20:24], "big"))
            self.assertEqual(size, (32, 32), item_id)
            self.assertEqual(_sha256(path), digest, item_id)
        self.assertEqual(CATALOG["training_sword"].basic_attack_fx, "sword_strike")
        self.assertEqual(CATALOG["miner_blade"].basic_attack_fx, "sword_strike")

    def test_pack_weapons_join_his_catalog_without_replacing_it(self):
        self.assertEqual(STARTING_GEAR["training_sword"], 1)
        self.assertEqual(CATALOG["training_sword"].bonuses["strength"], 1)
        self.assertEqual(CATALOG["miner_blade"].name, "Miner's Blade")
        practice = CATALOG["practice_sword"]
        sunsteel = CATALOG["sunsteel_blade"]
        self.assertEqual(practice.slot, "weapon")
        self.assertEqual(practice.jobs, ("Seer", "Sollers", "Saint"))
        self.assertEqual(practice.description, "A blunt wooden trainer.")
        self.assertEqual(practice.suggested_price, 30)
        self.assertEqual(practice.bonuses, {})
        self.assertEqual(practice.basic_attack_fx, "sword_strike")
        self.assertEqual(sunsteel.jobs, ("Saint",))
        self.assertEqual(sunsteel.suggested_price, 240)
        self.assertEqual(sunsteel.description, "A blade from Sunrest Arms.")
        self.assertEqual(sunsteel.bonuses, {})
        manifest = json.loads((ROOT / "data" / "weapons_manifest.json").read_text())
        lineup = {
            row["id"]: row
            for row in json.loads((ROOT / "data" / "signature_lineup.json").read_text())["weapons"]
        }
        hashes = json.loads((ROOT / "data" / "weapon_art_sha256.json").read_text())
        for row in manifest["weapons"]:
            item = CATALOG[row["id"]]
            self.assertEqual(item.jobs, tuple(row["classes"]))
            # An id whose art the signature kit adopted keeps the lineup's ATK.
            # Every other pack row still matches the manifest, including the
            # Steel Throwing Knife that shares a lineup id with different art.
            if item.lineup_id == row["id"]:
                self.assertEqual(item.atk, int(lineup[row["id"]]["suggested_stats"]["ATK"]))
            else:
                self.assertEqual(item.atk, int(row["suggested_stats"]["ATK"]))
            self.assertNotIn("strength", item.bonuses)
            path = gear_icon(item)
            self.assertEqual(_sha256(path), hashes[row["icon"]]["sha256"])

    def test_spellbook_is_a_saint_shield_and_binding_grants_nothing(self):
        book = CATALOG["spellbook"]
        self.assertEqual(book.slot, "shield")
        self.assertEqual(book.jobs, ("Saint",))
        self.assertEqual(book.magic_bonus, 0)
        self.assertEqual(book.bonuses, {})
        self.assertNotIn("spellbook", STARTING_GEAR)
        person = member("Retri", RETRI)
        before = dict(person["equipment"])
        self.assertTrue(bind_job(person, "Saint"))
        self.assertEqual(person["equipment"], before)
        self.assertFalse(can_wear(member("Retri", RETRI), book))
        person_job = member("Retri", RETRI)
        person_job["job"] = "Saint"
        self.assertTrue(can_wear(person_job, book))
        owned = {"spellbook": 1}
        self.assertTrue(equip(person_job, "shield", "spellbook", owned, [person_job])[0])
        self.assertEqual(stat_value(person_job, "magic"), person_job["magic"])

    def test_class_gate_uses_his_jobs_field(self):
        wand = CATALOG["yew_seer_wand"]
        saint = member("Retri", RETRI)
        saint["job"] = "Saint"
        seer = member("Temur", RETRI)
        seer["name"] = "Temur"
        seer["job"] = "Seer"
        owned = {"yew_seer_wand": 1}
        self.assertFalse(equip(saint, "weapon", wand.id, owned, [saint, seer])[0])
        self.assertTrue(equip(seer, "weapon", wand.id, owned, [saint, seer])[0])

    def test_strike_stays_off_the_list_and_follows_the_sword(self):
        saint = member("Retri", RETRI)
        saint["job"] = "Saint"
        saint["level"] = 3
        self.assertNotIn("strike", [ability.id for ability in learned_abilities(saint)])
        self.assertIsNone(strike_variant(saint))
        saint["equipment"] = {"weapon": "practice_sword"}
        variant = strike_variant(saint)
        self.assertIsNotNone(variant)
        self.assertIn("unattuned", str(variant.frames[0]))
        saint["attuned_stone"] = "first_stone"
        blue = strike_variant(saint)
        self.assertIn("first_stone", str(blue.frames[0]))
        mend = next(ability for ability in learned_abilities(saint) if ability.id == "saint_mend")
        from abilities import variant_for
        gold = variant_for(mend, saint)
        pixels = _png_rgba(gold.frames[len(gold.frames) // 2])
        colors = {pixel[:3] for row in pixels for pixel in row if pixel[3]}
        self.assertTrue(colors & GOLD)

    def test_cave_stall_is_tier_one_weapons_potion_and_ether(self):
        ids = cave_exit_ids()
        self.assertEqual(ids[-2:], ["Potion", "Ether"])
        self.assertNotIn("Ember Feather", ids)
        self.assertNotIn("Ember Talisman", ids)
        self.assertNotIn("Antidote", ids)
        self.assertNotIn("Torch", ids)
        self.assertIn("yew_seer_wand", ids)
        self.assertNotIn("bronze_mace", ids)
        self.assertNotIn("whitewood_mending_wand", ids)
        self.assertNotIn("practice_sword", ids)
        prices = cave_exit_prices()
        self.assertEqual(prices["Potion"], 15)
        self.assertEqual(prices["Ether"], 30)
        self.assertEqual(SUPPLIES["Potion"][0], 10)
        self.assertEqual(SUPPLIES["Ether"][0], 18)

    def test_ember_feather_keeps_his_numbers_and_talisman_is_not_sold(self):
        self.assertEqual(SUPPLIES["Ember Feather"], (30, "Revives a fainted ally at 25% HP."))
        self.assertEqual(
            _sha256(supply_icon("Ember Feather")),
            "248bb9972e21d486eaad84b01c49c0609de73184743f9524922feab234b5ecd4",
        )
        self.assertEqual(
            _sha256(supply_icon("Ember Talisman")),
            "6de90a477ec287ca27afc6b0be8b4d3f0f418ea7e8f2fea166aeb9087580c8f9",
        )
        standing = {"name": "Temur", "hp": 10, "max_hp": 80}
        self.assertFalse(apply_supply("Ember Feather", standing)[0])
        self.assertFalse(apply_supply("Ember Talisman", standing)[0])
        self.assertEqual(standing["hp"], 10)
        fainted = {"name": "Temur", "hp": 0, "max_hp": 80}
        self.assertTrue(apply_supply("Ember Feather", fainted)[0])
        self.assertEqual(fainted["hp"], 20)
        fainted["hp"] = 0
        self.assertTrue(apply_supply("Ember Talisman", fainted)[0])
        self.assertEqual(fainted["hp"], 80)
        self.assertNotIn("Ember Talisman", SUPPLIES)
        self.assertIn("Ember Talisman", RARE_SUPPLIES)

    def test_battle_and_menu_can_spend_the_revives(self):
        from battle import BattleModel, ENEMIES
        import random
        party = [
            {"name": "Retri", "hp": 40, "max_hp": 60, "mp": 4, "max_mp": 8, "equipment": {}},
            {"name": "Temur", "hp": 0, "max_hp": 80, "mp": 0, "max_mp": 6, "equipment": {}},
        ]
        model = BattleModel(ENEMIES[0], party=party, rng=random.Random(1), supplies={
            "Ember Feather": 1, "Ember Talisman": 1,
        })
        self.assertIn("Ember Talisman", model.item_names())
        self.assertFalse(model.command("Ember Feather", target=0))
        self.assertEqual(model.supplies["Ember Feather"], 1)
        model.pending_reply = False
        self.assertTrue(model.command("Ember Feather", target=1))
        self.assertEqual(party[1]["hp"], 20)
        party[1]["hp"] = 0
        model.pending_reply = False
        self.assertTrue(model.command("Ember Talisman", target=1))
        self.assertEqual(party[1]["hp"], 80)


if __name__ == "__main__":
    unittest.main()
