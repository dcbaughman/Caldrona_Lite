"""Warden gear: 8 icons and catalog rows locked to a job that does not exist yet."""
import hashlib
import json
import unittest
from pathlib import Path

from classes import JOBS, OUTFIT_JOBS
from equipment import CATALOG, SIGNATURE, WARDEN_GEAR, WARDEN_JOB, can_wear, class_kit, equip
from items import gear_icon

ROOT = Path(__file__).resolve().parent
GEAR = json.loads((ROOT / "data" / "warden_gear.json").read_text(encoding="utf-8"))["weapons"]
WEAPONS = ("watchmans_bec_de_corbin", "wardens_pollaxe", "lantern_hook_bardiche", "topazsteel_vigil_pollaxe")
OFF_HANDS = ("nightwatch_heater_shield", "hooded_watch_lantern", "wardens_alarum_horn", "vigil_pavise")
# Hashes Decorum approved for the 8 icons. The files must stay byte for byte.
ICON_SHA256 = {
    "hooded_watch_lantern": "35046405ec68cdc73b03c1c341bd57a6dedacbfb259c14ac8c0426185933f3ff",
    "lantern_hook_bardiche": "e6ce62446a61ff4715767b54fab55c73e13437a4b3a2d49da0a042b617babbff",
    "nightwatch_heater_shield": "b42d7d07073bb7634e76bc96295e29909802bd7bc000c1f47419bbbc1db18c2b",
    "topazsteel_vigil_pollaxe": "4044d675d53511847099b7979c07f022855880fe3a07393e268d8b36147896f8",
    "vigil_pavise": "e203c2fd4f3624969fc2222cbe351d601a014b66a80a2d29041dbf55cdbad25a",
    "wardens_alarum_horn": "43e699594622ad5331e54992c96af474be8ab823d54f70e85e5c833e0581b4b3",
    "wardens_pollaxe": "65692330c4ea4ad05f62718a00749b05221087ca62cc4fb298ffd74b2ae463cc",
    "watchmans_bec_de_corbin": "93db7581c0aec90730c996206105d43234bfcebba880f5e72231929cf46de563",
}


def _png_size(path):
    data = Path(path).read_bytes()
    return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")


class WardenGearTests(unittest.TestCase):
    def test_eight_items_exist_in_the_right_slots_and_are_locked_to_warden(self):
        self.assertEqual(set(WARDEN_GEAR), set(WEAPONS + OFF_HANDS))
        self.assertEqual(len(GEAR), 8)
        for item_id in WEAPONS:
            self.assertEqual(CATALOG[item_id].slot, "weapon", item_id)
        for item_id in OFF_HANDS:
            self.assertEqual(CATALOG[item_id].slot, "shield", item_id)
        for item_id, item in WARDEN_GEAR.items():
            self.assertIs(CATALOG[item_id], item)
            self.assertEqual(item.jobs, (WARDEN_JOB,))
            self.assertEqual(item.characters, ())
        rungs = [CATALOG[item_id].rung for item_id in WEAPONS]
        self.assertEqual(rungs, sorted(rungs))
        self.assertEqual(CATALOG["topazsteel_vigil_pollaxe"].rung, 4)
        self.assertEqual(CATALOG["vigil_pavise"].rung, 4)

    def test_no_current_job_can_wear_or_equip_them(self):
        self.assertNotIn(WARDEN_JOB, JOBS)
        self.assertNotIn(WARDEN_JOB, OUTFIT_JOBS)
        for job in (*JOBS, None, "Unbound", "Cutpurse", "Saint Warrior", "Black Reliquary"):
            member = {"name": "Tester", "job": job, "hp": 10}
            for item_id, item in WARDEN_GEAR.items():
                self.assertFalse(can_wear(member, item), (job, item_id))
                owned = {item_id: 1}
                ok, message = equip(member, item.slot, item_id, owned, [member])
                self.assertFalse(ok, (job, item_id))
                self.assertIn("cannot equip", message)
                self.assertNotIn("equipment", member)

    def test_existing_lineup_and_class_kits_are_untouched(self):
        self.assertEqual(len(SIGNATURE), 36)
        self.assertFalse(set(WARDEN_GEAR) & set(SIGNATURE))
        for job in JOBS:
            self.assertFalse({item.id for item in class_kit(job)} & set(WARDEN_GEAR))
        self.assertEqual(class_kit(WARDEN_JOB), ())

    def test_icons_are_32x32_and_byte_for_byte(self):
        for row in GEAR:
            item = WARDEN_GEAR[row["id"]]
            path = gear_icon(item)
            self.assertIsNotNone(path, row["id"])
            self.assertEqual(path.parent.name, "warden")
            self.assertEqual(_png_size(path), (32, 32), row["id"])
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(digest, ICON_SHA256[row["id"]], row["id"])
            self.assertEqual(digest, row["dest_sha256"], row["id"])

    def test_wired_hooks_are_stored_and_skipped_ones_are_not(self):
        self.assertEqual(CATALOG["watchmans_bec_de_corbin"].hook_parts, (("ability", "Armor Break", 10, ""),))
        self.assertEqual(CATALOG["topazsteel_vigil_pollaxe"].hook_parts, (("ability", "Vigil Strike", 15, ""),))
        self.assertEqual(CATALOG["nightwatch_heater_shield"].hook_parts, (("ability", "Guard", 10, ""),))
        for row in GEAR:
            if "skipped_hook" in row:
                self.assertEqual(row["hook"], "", row["id"])
                self.assertEqual(WARDEN_GEAR[row["id"]].hook_parts, (), row["id"])
        self.assertEqual(sum("skipped_hook" in row for row in GEAR), 5)

    def test_weapons_add_no_live_stats(self):
        for item_id in WEAPONS:
            self.assertEqual(CATALOG[item_id].bonuses, {}, item_id)
            self.assertGreater(CATALOG[item_id].atk, 0)


if __name__ == "__main__":
    unittest.main()
