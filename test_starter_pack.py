"""Starter pack: unchanged art, class gates, attunement files, and the cave stall."""
import hashlib
import json
import random
import struct
import tkinter as tk
import unittest
import zlib
from pathlib import Path

from abilities import (
    BY_JOB, PLANNED, attuned_stone, class_abilities, frame_at, learned_abilities,
    remember, strike_variant, usable_abilities, variant_for,
)
from astral_scene import AstralScene
from battle import BattleModel, BattleScene, ENEMIES
from classes import JOBS, bind_job
from display_settings import ScaledCanvas
from equipment import can_equip, equip
from items import CATALOG, icon_file
from shops import CAVE_EXIT_NAME_TO_ID, cave_exit_prices, get_shop_stock
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
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _png_rgba(path):
    """Decode an 8-bit RGBA PNG. Used to check Saint gold, not to rewrite it."""
    data = Path(path).read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise AssertionError(f"{path} is not a PNG")
    pos = 8
    width = height = None
    color = None
    idat = b""
    while pos < len(data):
        length = struct.unpack(">I", data[pos:pos + 4])[0]
        kind = data[pos + 4:pos + 8]
        chunk = data[pos + 8:pos + 8 + length]
        pos += 12 + length
        if kind == b"IHDR":
            width, height, bit, color = struct.unpack(">IIBB", chunk[:10])
            if (bit, color) != (8, 6):
                raise AssertionError(f"{path} is not 8-bit RGBA")
        elif kind == b"IDAT":
            idat += chunk
        elif kind == b"IEND":
            break
    raw = zlib.decompress(idat)
    stride = width * 4
    rows = []
    index = 0
    previous = bytearray(stride)
    for _y in range(height):
        filt = raw[index]
        index += 1
        row = bytearray(raw[index:index + stride])
        index += stride
        if filt == 1:
            for x in range(stride):
                left = row[x - 4] if x >= 4 else 0
                row[x] = (row[x] + left) & 255
        elif filt == 2:
            for x in range(stride):
                row[x] = (row[x] + previous[x]) & 255
        elif filt == 3:
            for x in range(stride):
                left = row[x - 4] if x >= 4 else 0
                row[x] = (row[x] + ((left + previous[x]) // 2)) & 255
        elif filt == 4:
            for x in range(stride):
                left = row[x - 4] if x >= 4 else 0
                up = previous[x]
                diag = previous[x - 4] if x >= 4 else 0
                estimate = left + up - diag
                pa, pb, pc = abs(estimate - left), abs(estimate - up), abs(estimate - diag)
                predictor = left if pa <= pb and pa <= pc else up if pb <= pc else diag
                row[x] = (row[x] + predictor) & 255
        elif filt != 0:
            raise AssertionError(f"unsupported filter {filt}")
        previous = row
        rows.append(bytes(row))
    return width, height, rows


def _opaque(rows):
    pixels = []
    for row in rows:
        for x in range(0, len(row), 4):
            if row[x + 3]:
                pixels.append((row[x], row[x + 1], row[x + 2]))
    return pixels


class ArtHashTests(unittest.TestCase):
    def test_weapon_and_ability_files_match_the_pack_hashes(self):
        weapons = json.loads((ROOT / "data" / "weapon_art_sha256.json").read_text(encoding="utf-8"))
        abilities = json.loads((ROOT / "data" / "ability_art_sha256.json").read_text(encoding="utf-8"))
        self.assertEqual(len(weapons), 46)
        self.assertGreaterEqual(len(abilities), 1)
        for relative, meta in weapons.items():
            path = ROOT / "assets" / "items" / relative
            self.assertTrue(path.is_file(), relative)
            self.assertEqual(_sha256(path), meta["sha256"], relative)
            self.assertEqual(_png_rgba(path)[:2], (32, 32), relative)
        for relative, meta in abilities.items():
            pack_path = relative[len("abilities/"):] if relative.startswith("abilities/") else relative
            path = ROOT / "assets" / "battle" / "fx" / pack_path
            self.assertTrue(path.is_file(), relative)
            self.assertEqual(_sha256(path), meta["sha256"], relative)

    def test_manifest_weapons_are_catalog_weapons_with_stored_stats(self):
        manifest = json.loads((ROOT / "data" / "weapons_manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(len(manifest["weapons"]), 46)
        for row in manifest["weapons"]:
            item = CATALOG[row["id"]]
            self.assertEqual(item.category, "weapon")
            self.assertEqual(item.icon, f"weapons/{row['id']}.png")
            self.assertEqual(item.buy_price, row["suggested_price_gold"])
            self.assertEqual(item.weapon.classes, tuple(row["classes"]))
            self.assertEqual(item.weapon.tier, row["suggested_tier"])
            stats = row["suggested_stats"]
            self.assertEqual((item.weapon.atk, item.weapon.spd, item.weapon.reach, item.weapon.pen),
                             (stats["ATK"], stats["SPD"], stats["REACH"], stats["PEN"]))
            self.assertTrue(icon_file(item).is_file())


class ClassGateTests(unittest.TestCase):
    def test_classes_field_only_restricts_equip_and_binding_grants_nothing(self):
        person = member("Retri", RETRI)
        person["weapon"] = "practice_sword"
        supplies = {"bronze_mace": 1, "yew_seer_wand": 1, "spellbook": 1}
        before = (person.get("weapon"), person.get("offhand"), dict(supplies), person.get("magic"))
        self.assertTrue(bind_job(person, "Saint"))
        self.assertEqual((person.get("weapon"), person.get("offhand"), supplies, person.get("magic")), before)
        self.assertFalse(bind_job(person, "Seer"))
        self.assertEqual(supplies, {"bronze_mace": 1, "yew_seer_wand": 1, "spellbook": 1})

        for job in JOBS:
            bare = member("Temur", RETRI)
            self.assertTrue(bind_job(bare, job))
            self.assertIsNone(bare.get("weapon"))
            self.assertIsNone(bare.get("offhand"))

        seer = {"job": "Seer", "level": 1}
        sollers = {"job": "Sollers", "level": 1}
        saint = {"job": "Saint", "level": 1}
        unbound = {"level": 1}
        self.assertTrue(can_equip(seer, "yew_seer_wand")[0])
        self.assertEqual(can_equip(seer, "bronze_knife")[1], "wrong_class")
        self.assertTrue(can_equip(sollers, "bronze_knife")[0])
        self.assertEqual(can_equip(sollers, "yew_seer_wand")[1], "wrong_class")
        self.assertTrue(can_equip(saint, "bronze_mace")[0])
        self.assertEqual(can_equip(saint, "yew_seer_wand")[1], "wrong_class")
        self.assertTrue(can_equip(unbound, "practice_sword")[0])
        self.assertEqual(can_equip(unbound, "bronze_mace")[1], "wrong_class")
        for job, who in (("Seer", seer), ("Sollers", sollers), ("Saint", saint)):
            self.assertTrue(can_equip(who, "practice_sword")[0], job)

    def test_astral_binding_leaves_equipment_empty(self):
        root = tk.Tk()
        root.withdraw()
        self.addCleanup(root.destroy)
        canvas = ScaledCanvas(root, 12)
        font = lambda size, bold=False: ("TkDefaultFont", size, "bold" if bold else "normal")
        party = [member("Retri", RETRI)]
        scene = AstralScene(canvas, font, ROOT / "assets")
        scene.start(party, 0, reveal=False)
        scene.selection = JOBS.index("Saint")
        scene.confirm()
        scene.confirm_bind = True
        scene.confirm()
        self.assertEqual(party[0]["job"], "Saint")
        self.assertIsNone(party[0].get("weapon"))
        self.assertIsNone(party[0].get("offhand"))
        self.assertNotIn("bronze_mace", party[0].get("abilities", []))

    def test_saint_offhand_accepts_a_placeholder_spellbook(self):
        book = CATALOG["spellbook"]
        self.assertTrue(book.placeholder_icon)
        self.assertEqual(book.icon, "")
        self.assertEqual(book.category, "offhand")
        self.assertEqual(book.weapon.weapon_type, "spellbook")
        self.assertEqual(book.weapon.classes, ("Saint",))
        self.assertFalse(icon_file(book).is_file())
        self.assertEqual(list(ROOT.joinpath("assets").rglob("*spellbook*")), [])

        saint = {"name": "Retri", "job": "Saint", "level": 1, "magic": 3}
        supplies = {"spellbook": 1, "bronze_mace": 1}
        self.assertTrue(equip(saint, "bronze_mace", supplies)[0])
        self.assertEqual(can_equip(saint, "bronze_mace", "offhand")[1], "not_offhand")
        self.assertEqual(can_equip(saint, "spellbook", "weapon")[1], "not_weapon")
        self.assertTrue(equip(saint, "spellbook", supplies, "offhand")[0])
        self.assertEqual(saint["weapon"], "bronze_mace")
        self.assertEqual(saint["offhand"], "spellbook")
        self.assertEqual(saint["magic"], 3)
        self.assertNotIn("spellbook", supplies)

        seer = {"job": "Seer", "level": 1, "magic": 8}
        seer_pack = {"spellbook": 1}
        self.assertEqual(can_equip(seer, "spellbook", "offhand")[1], "wrong_class")
        self.assertEqual(seer_pack["spellbook"], 1)
        self.assertIsNone(seer.get("offhand"))

    def test_weapon_stats_do_not_change_attack_damage(self):
        bare = {"name": "Retri", "job": "Saint", "level": 1, "hp": 60, "max_hp": 60, "strength": 8}
        armed = dict(bare, weapon="sunsteel_blade")
        first = BattleModel(ENEMIES[0], party=[bare], rng=random.Random(3))
        second = BattleModel(ENEMIES[0], party=[armed], rng=random.Random(3))
        self.assertTrue(first.command("Attack"))
        self.assertTrue(second.command("Attack"))
        self.assertEqual(first.damage, second.damage)
        self.assertEqual(first.enemy_hp, second.enemy_hp)
        self.assertGreater(CATALOG["sunsteel_blade"].weapon.atk, 0)


class AbilityTests(unittest.TestCase):
    def _who(self, job, level, **extra):
        person = {"name": "Retri", "job": job, "level": level, "hp": 40, "max_hp": 40,
                  "mp": 8, "max_mp": 8, "magic": 3}
        person.update(extra)
        return person

    def test_unlock_thresholds_follow_the_manifest(self):
        expect = {
            "Seer": {1: {"strike"}, 2: {"strike", "seer_foretell"},
                     4: {"strike", "seer_foretell"},
                     5: {"strike", "seer_foretell", "seer_starfall_omen"},
                     7: {"strike", "seer_foretell", "seer_starfall_omen", "seer_forewarn"}},
            "Sollers": {1: {"strike", "sollers_knife_flick"},
                        2: {"strike", "sollers_knife_flick", "sollers_pilfer"},
                        3: {"strike", "sollers_knife_flick", "sollers_pilfer"},
                        4: {"strike", "sollers_knife_flick", "sollers_pilfer", "sollers_backstab"}},
            "Saint": {1: {"strike", "saint_mend"},
                      2: {"strike", "saint_mend"},
                      3: {"strike", "saint_mend", "saint_smite"},
                      5: {"strike", "saint_mend", "saint_smite", "saint_sanctuary"}},
        }
        for job, levels in expect.items():
            for level, ids in levels.items():
                got = {ability.id for ability in learned_abilities(self._who(job, level))}
                self.assertEqual(got, ids, (job, level))
        for job, planned in PLANNED.items():
            self.assertTrue(planned)
            got = {ability.id for ability in learned_abilities(self._who(job, 99))}
            self.assertTrue(set(planned).isdisjoint(got))

    def test_strike_needs_a_sword_and_effects_do_not_change_numbers(self):
        saint = self._who("Saint", 1)
        self.assertIn("strike", {a.id for a in learned_abilities(saint)})
        self.assertNotIn("strike", {a.id for a in usable_abilities(saint)})
        supplies = {"practice_sword": 1}
        self.assertTrue(equip(saint, "practice_sword", supplies)[0])
        self.assertEqual([a.id for a in usable_abilities(saint) if a.id == "strike"], ["strike"])

        before = (saint["hp"], saint["mp"], saint["magic"])
        model = BattleModel(ENEMIES[0], party=[saint], rng=random.Random(1))
        enemy = model.enemy_hp
        self.assertTrue(model.command("Ability", ability_id="saint_mend"))
        self.assertFalse(model.pending_reply)
        self.assertEqual((saint["hp"], saint["mp"], saint["magic"], model.enemy_hp), (*before, enemy))
        self.assertIn("not applied", model.message)

    def test_gray_and_blue_are_file_choices_and_saint_gold_is_untinted(self):
        sword = self._who("Saint", 1, weapon="practice_sword")
        gray = strike_variant(sword)
        self.assertIn("frames_unattuned", str(gray.frames[0]))
        sword["attuned_stone"] = "first_stone"
        blue = strike_variant(sword)
        self.assertIn("frames_first_stone", str(blue.frames[0]))
        self.assertNotEqual(_sha256(gray.frames[0]), _sha256(blue.frames[0]))
        self.assertEqual(gray.ms_per_frame, (50, 40, 40, 70, 60, 70, 80))
        self.assertEqual(gray.total_ms, 410)
        self.assertEqual(gray.scale, 2)
        self.assertEqual(gray.target_center, (32, 32))
        self.assertEqual(frame_at(gray, 0), gray.frames[0])
        self.assertEqual(frame_at(gray, 50), gray.frames[1])
        self.assertEqual(frame_at(gray, 10_000), gray.frames[-1])

        mend = next(a for a in class_abilities("Saint") if a.id == "saint_mend")
        sanctuary = next(a for a in class_abilities("Saint") if a.id == "saint_sanctuary")
        for ability in (mend, sanctuary):
            self.assertFalse(ability.attunement_tinted)
            self.assertEqual(set(ability.variants), {"untinted"})
            bare = self._who("Saint", 5)
            tuned = self._who("Saint", 5, attuned_stone="first_stone")
            self.assertEqual(variant_for(ability, bare).frames, variant_for(ability, tuned).frames)
            _w, _h, rows = _png_rgba(ability.variants["untinted"].frames[4])
            colors = set(_opaque(rows))
            self.assertTrue(colors, ability.id)
            self.assertTrue(colors <= GOLD, ability.id)

        smite = next(a for a in BY_JOB["Saint"] if a.id == "saint_smite")
        plain = smite.variants["unattuned"].frames[3]
        stone = smite.variants["first_stone"].frames[3]
        self.assertNotEqual(_sha256(plain), _sha256(stone))
        _w, _h, plain_rows = _png_rgba(plain)
        _w, _h, stone_rows = _png_rgba(stone)
        gold_match = tint_differs = False
        for prow, srow in zip(plain_rows, stone_rows):
            for x in range(0, len(prow), 4):
                pp = (prow[x], prow[x + 1], prow[x + 2], prow[x + 3])
                sp = (srow[x], srow[x + 1], srow[x + 2], srow[x + 3])
                if pp[:3] in GOLD and pp[3]:
                    self.assertEqual(pp, sp)
                    gold_match = True
                elif pp != sp:
                    tint_differs = True
        self.assertTrue(gold_match)
        self.assertTrue(tint_differs)
        self.assertEqual(attuned_stone({}), "unattuned")
        self.assertEqual(variant_for(smite, {}).key, "unattuned")
        self.assertEqual(variant_for(smite, {"attuned_stone": "first_stone"}).key, "first_stone")


class ShopStockTests(unittest.TestCase):
    def test_cave_exit_stock_ids_are_in_the_catalog_at_suggested_prices(self):
        stock = get_shop_stock("cave_exit_merchant")
        prices = cave_exit_prices()
        self.assertEqual([item.id for item in stock], [
            "yew_seer_wand", "hazel_divining_rod", "bronze_astrolabe_rod",
            "bronze_purse_knife", "bronze_knife", "bronze_throwing_knife",
            "bronze_weighted_cosh", "whitewood_mending_wand", "linen_bound_cudgel",
            "pale_ash_crook", "bronze_mace", "potion", "ether", "field_bandages",
            "antidote", "torch",
        ])
        for item in stock:
            self.assertIn(item.id, CATALOG)
            self.assertEqual(item.buy_price, prices[item.id])
            if item.id != "spellbook":
                self.assertTrue(icon_file(CATALOG[item.id]).is_file())
        self.assertEqual(CAVE_EXIT_NAME_TO_ID["Mana Potion"], "ether")
        self.assertEqual(CATALOG["ether"].name, "Ether")
        self.assertEqual(CATALOG["ether"].effect["amount"], 8)
        self.assertEqual(CATALOG["field_bandages"].effect["amount"], 10)
        self.assertEqual(prices["ether"], 30)
        self.assertEqual(prices["field_bandages"], 25)
        self.assertEqual(prices["potion"], 15)
        self.assertEqual(CATALOG["potion"].buy_price, 40)
        self.assertNotIn("spellbook", {item.id for item in stock})


class BattleFrameTests(unittest.TestCase):
    def test_attack_plays_gray_then_blue_strike_frames(self):
        root = tk.Tk()
        root.withdraw()
        self.addCleanup(root.destroy)
        canvas = ScaledCanvas(root, 12)
        font = lambda size, bold=False: ("TkDefaultFont", size, "bold" if bold else "normal")
        scene = BattleScene(canvas, font, ROOT / "assets")
        person = self_member()
        model = BattleModel(ENEMIES[0], party=[person], rng=random.Random(1))
        scene.start(model, 0)
        scene.confirm(0)
        scene.confirm(0)
        scene.update(0.08)
        self.assertIn("frames_unattuned", str(scene.fx_path))
        self.assertGreater(model.damage, 0)
        scene.close()

        person["attuned_stone"] = "first_stone"
        fresh = BattleModel(ENEMIES[0], party=[person], rng=random.Random(1))
        scene.start(fresh, 1)
        scene.confirm(1)
        scene.confirm(1)
        scene.update(1.08)
        self.assertIn("frames_first_stone", str(scene.fx_path))
        scene.close()


def self_member():
    person = member("Retri", RETRI)
    person["job"] = "Saint"
    person["weapon"] = "practice_sword"
    remember(person)
    return person


if __name__ == "__main__":
    unittest.main()
