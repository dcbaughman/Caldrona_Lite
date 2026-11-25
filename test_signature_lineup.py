"""Signature weapon lineup: slots, classes, art hashes, stall, and binding."""
import hashlib
import json
import unittest
from pathlib import Path

from abilities import strike_variant
from classes import bind_job
from consumables import SUPPLIES
from equipment import (CATALOG, SIGNATURE, STARTING_GEAR, apply_signature_hook,
                       can_wear, class_kit, equip, stat_value)
from items import gear_icon
from shops import cave_exit_ids, cave_exit_prices
from stats import RETRI, member

ROOT = Path(__file__).resolve().parent
LINEUP = json.loads((ROOT / "data" / "signature_lineup.json").read_text(encoding="utf-8"))
HASHES = json.loads((ROOT / "data" / "weapon_art_sha256.json").read_text(encoding="utf-8"))

# Recorded before this lineup. New keys may be added; these values must stay.
LEGACY_ART = {
    "weapons/practice_sword.png": "d7827d320f94c0e1a95b900ee389c0ad8bd836c35577c82fdc265635975619c6",
    "weapons/yew_seer_wand.png": "062f69a8b7545887278f224b8aac8bfdbace56290826873034b0bc0057f3a9fc",
    "weapons/throwing_knife.png": "3fdd15d92586aa8285fd9b39db5c0be4a219e8a7d07d6abdaa4c82baef2f6bd0",
    "weapons/frost_fang.png": "740b95a268969da032e7293987d544002b9f2d06deddc1ae4329939d261e0184",
    "weapons/smoky_quartz_focus.png": "d38247f5bb7f5517e5f042d0b0754e3985e5c969ef78abe42053323fb7e92b55",
    "weapons/bronze_mace.png": "46948ece0b075cb95ce3c11b97062f72da7824983909d1800d550a02f465c69a",
}

STALL_WEAPONS = (
    "pilgrims_mace",
    "prayer_book",
    "purse_knife",
    "lineup_throwing_knife",
    "leather_sap",
    "yew_seer_wand",
    "divining_rod",
    "greywood_runestaff",
    "slate_rune_focus",
)

OFF_HAND = {"spellbook", "cosh", "focus"}


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _png_size(path):
    data = Path(path).read_bytes()
    return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")


class SignatureLineupTests(unittest.TestCase):
    def test_all_thirty_six_load_with_slot_and_class(self):
        self.assertEqual(len(LINEUP["weapons"]), 36)
        self.assertEqual(len(SIGNATURE), 36)
        counts = {"Saint": 0, "Sollers": 0, "Seer": 0}
        for row in LINEUP["weapons"]:
            item = SIGNATURE[row["id"]]
            self.assertIn(item.id, CATALOG)
            self.assertEqual(item.lineup_id, row["id"])
            self.assertEqual(item.name, row["name"])
            self.assertEqual(item.weapon_type, row["type"])
            self.assertEqual(item.rung, row["rung"])
            self.assertEqual(item.hook, row["hook"])
            self.assertEqual(item.element, row["element"] or "")
            self.assertEqual(item.jobs, (row["class"],))
            self.assertEqual(item.slot, row["slot"])
            if row["type"] in OFF_HAND:
                self.assertEqual(item.slot, "shield", row["id"])
            else:
                self.assertEqual(item.slot, "weapon", row["id"])
            self.assertEqual(item.atk, int(row["suggested_stats"]["ATK"]))
            self.assertEqual(item.spd, int(row["suggested_stats"]["SPD"]))
            self.assertEqual(item.pen, int(row["suggested_stats"]["PEN"]))
            self.assertEqual(item.magic_bonus, int(row["suggested_magic_bonus"] or 0))
            self.assertEqual(item.bonuses, {})
            self.assertNotIn("note", [part[0] for part in item.hook_parts])
            self.assertTrue(item.hook_parts, row["id"])
            counts[row["class"]] += 1
        self.assertEqual(counts, {"Saint": 8, "Sollers": 12, "Seer": 16})
        self.assertEqual(len(class_kit("Saint")), 8)
        self.assertEqual(len(class_kit("Sollers")), 12)
        self.assertEqual(len(class_kit("Seer")), 16)
        for borrowed in (
            "practice_sword", "bronze_mace", "whitewood_mending_wand", "healing_wand",
            "pale_ash_crook", "iron_shortsword", "shadow_edge", "bronze_knife",
            "throwing_knife", "spellbook",
        ):
            self.assertNotIn(CATALOG[borrowed].id, [item.id for item in class_kit(CATALOG[borrowed].jobs[0])])

    def test_icon_hashes_match_lineup_and_legacy_entries_stay(self):
        for row in LINEUP["weapons"]:
            item = SIGNATURE[row["id"]]
            path = gear_icon(item)
            self.assertIsNotNone(path, row["id"])
            self.assertEqual(_png_size(path), (32, 32), row["id"])
            self.assertEqual(_sha256(path), row["dest_sha256"], row["id"])
            recorded = HASHES[item.icon]
            self.assertEqual(recorded["sha256"], row["dest_sha256"])
        weapons = [key for key in HASHES if key.startswith("weapons/")]
        self.assertEqual(len(weapons), 46)
        for key, digest in LEGACY_ART.items():
            self.assertEqual(HASHES[key]["sha256"], digest)
            self.assertEqual(_sha256(ROOT / "assets" / "items" / key), digest)

    def test_throwing_knife_id_keeps_the_steel_catalog_row(self):
        steel = CATALOG["throwing_knife"]
        signature = SIGNATURE["throwing_knife"]
        self.assertEqual(steel.name, "Steel Throwing Knife")
        self.assertEqual(steel.icon, "weapons/throwing_knife.png")
        self.assertEqual(steel.rung, 0)
        self.assertEqual(signature.id, "lineup_throwing_knife")
        self.assertEqual(signature.name, "Throwing Knife")
        self.assertEqual(signature.slot, "weapon")
        self.assertEqual(signature.jobs, ("Sollers",))
        self.assertNotEqual(_sha256(gear_icon(steel)), _sha256(gear_icon(signature)))

    def test_off_hands_equip_only_for_their_class(self):
        saint = member("Retri", RETRI)
        saint["job"] = "Saint"
        sollers = member("Temur", RETRI)
        sollers["name"] = "Temur"
        sollers["job"] = "Sollers"
        seer = member("Retri", RETRI)
        seer["name"] = "Vesper"
        seer["job"] = "Seer"
        owned = {item.id: 1 for item in SIGNATURE.values()}
        roster = [saint, sollers, seer]
        mace = SIGNATURE["pilgrims_mace"]
        book = SIGNATURE["prayer_book"]
        knife = SIGNATURE["purse_knife"]
        sap = SIGNATURE["leather_sap"]
        wand = SIGNATURE["yew_seer_wand"]
        focus = SIGNATURE["slate_rune_focus"]
        self.assertEqual(mace.slot, "weapon")
        self.assertEqual(book.slot, "shield")
        self.assertEqual(sap.slot, "shield")
        self.assertEqual(focus.slot, "shield")
        self.assertTrue(equip(saint, "weapon", mace.id, owned, roster)[0])
        self.assertTrue(equip(saint, "shield", book.id, owned, roster)[0])
        self.assertFalse(equip(saint, "weapon", knife.id, owned, roster)[0])
        self.assertFalse(equip(saint, "shield", focus.id, owned, roster)[0])
        self.assertFalse(equip(sollers, "weapon", mace.id, owned, roster)[0])
        self.assertTrue(equip(sollers, "weapon", knife.id, owned, roster)[0])
        self.assertTrue(equip(sollers, "shield", sap.id, owned, roster)[0])
        self.assertFalse(equip(seer, "shield", book.id, owned, roster)[0])
        self.assertTrue(equip(seer, "weapon", wand.id, owned, roster)[0])
        self.assertTrue(equip(seer, "shield", focus.id, owned, roster)[0])
        self.assertFalse(can_wear(member("Retri", RETRI), mace))

    def test_hooks_are_stored_and_do_not_change_stats(self):
        saint = member("Retri", RETRI)
        saint["job"] = "Saint"
        before = (saint["hp"], saint["max_hp"], saint["mp"], stat_value(saint, "max_hp"), stat_value(saint, "magic"))
        cairn = SIGNATURE["cairn_mace"]
        self.assertEqual(cairn.hook_parts, (("max_hp", "Max HP", 4, ""),))
        self.assertEqual(SIGNATURE["birch_rune_wand"].hook_parts, (("max_mp", "Max MP", 4, ""),))
        self.assertEqual(SIGNATURE["frost_fang"].element, "ice")
        self.assertEqual(SIGNATURE["frost_fang"].hook_parts, (("status", "Slow", 15, ""),))
        self.assertEqual(SIGNATURE["ruby_wand"].hook_parts, (("magic", "MAG", 0, ""),))
        self.assertEqual(
            SIGNATURE["blackjack"].hook_parts,
            (("status", "Delay", 20, ""), ("ability_vs", "Backstab", 15, "delayed")),
        )
        owned = {cairn.id: 1}
        self.assertTrue(equip(saint, "weapon", cairn.id, owned, [saint])[0])
        apply_signature_hook(saint, cairn)
        self.assertEqual(
            (saint["hp"], saint["max_hp"], saint["mp"], stat_value(saint, "max_hp"), stat_value(saint, "magic")),
            before,
        )
        self.assertEqual(saint["equipment"]["weapon"], cairn.id)

    def test_cave_stall_is_rung_one_plus_potion_and_ether(self):
        ids = cave_exit_ids()
        self.assertEqual(ids, list(STALL_WEAPONS) + ["Potion", "Ether"])
        prices = cave_exit_prices()
        self.assertEqual(prices["pilgrims_mace"], 60)
        self.assertEqual(prices["yew_seer_wand"], 55)
        self.assertEqual(prices["purse_knife"], 50)
        self.assertEqual(prices["lineup_throwing_knife"], 50)
        self.assertEqual(prices["Potion"], 15)
        self.assertEqual(prices["Ether"], 30)
        self.assertEqual(SUPPLIES["Potion"][0], 10)
        self.assertEqual(SUPPLIES["Ether"][0], 18)
        for dropped in (
            "bronze_mace", "bronze_knife", "bronze_throwing_knife", "bronze_weighted_cosh",
            "whitewood_mending_wand", "pale_ash_crook", "hazel_divining_rod",
            "practice_sword", "training_sword", "Ember Feather", "Ember Talisman",
            "Antidote", "Torch",
        ):
            self.assertNotIn(dropped, ids)
        for item_id in STALL_WEAPONS:
            self.assertEqual(CATALOG[item_id].rung, 1)

    def test_binding_a_class_grants_equips_and_removes_nothing(self):
        person = member("Retri", RETRI)
        person["equipment"] = {"weapon": "training_sword", "shield": "wood_shield"}
        owned = dict(STARTING_GEAR)
        before_gear = dict(person["equipment"])
        before_owned = dict(owned)
        for job in ("Saint", "Sollers", "Seer"):
            traveler = member("Retri", RETRI)
            traveler["equipment"] = {"weapon": "yew_seer_wand"}
            self.assertTrue(bind_job(traveler, job))
            self.assertEqual(traveler["equipment"], {"weapon": "yew_seer_wand"})
            self.assertFalse(bind_job(traveler, "Saint" if job != "Saint" else "Seer"))
            self.assertEqual(traveler["equipment"], {"weapon": "yew_seer_wand"})
        self.assertTrue(bind_job(person, "Saint"))
        self.assertEqual(person["equipment"], before_gear)
        self.assertEqual(owned, before_owned)
        self.assertEqual(STARTING_GEAR["training_sword"], 1)
        self.assertEqual(STARTING_GEAR["miner_blade"], 1)
        self.assertNotIn("pilgrims_mace", STARTING_GEAR)
        self.assertNotIn("prayer_book", person["equipment"].values())

    def test_starter_blades_still_play_sword_strike(self):
        for item_id in ("training_sword", "miner_blade"):
            item = CATALOG[item_id]
            self.assertEqual(item.basic_attack_fx, "sword_strike")
            self.assertEqual(item.rung, 0)
            self.assertEqual(item.jobs, ())
        saint = member("Retri", RETRI)
        saint["job"] = "Saint"
        saint["equipment"] = {"weapon": "training_sword"}
        variant = strike_variant(saint)
        self.assertIsNotNone(variant)
        self.assertIn("unattuned", str(variant.frames[0]))
        saint["equipment"] = {"weapon": "miner_blade"}
        self.assertIsNotNone(strike_variant(saint))
        # Lineup weapons now pick swing art by family: a mace plays the blunt impact.
        saint["equipment"] = {"weapon": SIGNATURE["pilgrims_mace"].id}
        self.assertEqual(SIGNATURE["pilgrims_mace"].basic_attack_fx, "blunt_impact")
        self.assertIsNotNone(strike_variant(saint))
        sollers = member("Temur", RETRI)
        sollers["job"] = "Sollers"
        sollers["equipment"] = {"weapon": SIGNATURE["purse_knife"].id}
        self.assertEqual(CATALOG["purse_knife"].basic_attack_fx, "sword_strike")
        self.assertIsNotNone(strike_variant(sollers))


if __name__ == "__main__":
    unittest.main()
