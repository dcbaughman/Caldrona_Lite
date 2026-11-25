"""Astral binding, party navigation, and legacy class compatibility."""
import random
import tkinter as tk
import unittest
from pathlib import Path

from astral_scene import AstralScene
from battle import BattleModel, ENEMIES
from classes import BLUE_STONE, NOKTAKORO, RIQIZAURKEIS, SENBRANKA, STONE_PATHS, bind_job, current_job
from classes import DESCRIPTIONS
from display_settings import ScaledCanvas
from game_menu import GameMenu
from stats import RETRI, TEMUR, grow, member


class SyncMenuTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.canvas = ScaledCanvas(self.root, 12)
        self.font = lambda size, bold=False: ("Consolas", size, "bold" if bold else "normal")
        self.party = [member("Retri", RETRI), member("Temur", TEMUR)]
        self.scene = AstralScene(self.canvas, self.font, Path(__file__).parent / "assets")
        self.scene.start(self.party, 0)

    def tearDown(self):
        self.root.destroy()

    def test_reveal_defer_and_irreversible_per_member_binding(self):
        self.assertEqual(self.scene.phase, "reveal")
        self.scene.update(3)
        self.assertEqual(self.scene.phase, "choose")
        self.scene.selection = len(self.scene.paths)
        self.assertEqual(self.scene.confirm(), "close")
        self.assertTrue(all("job" not in p for p in self.party))

        self.scene.start(self.party, 4, reveal=False, stone=NOKTAKORO)
        self.scene.selection = 1
        self.scene.confirm()
        self.assertEqual(self.scene.phase, "confirm")
        self.scene.confirm()  # Default is Go Back.
        self.assertNotIn("job", self.party[0])
        self.scene.confirm()
        self.scene.navigate("left", 5)
        self.scene.confirm()
        self.assertEqual(self.party[0]["job"], "Sollers")
        self.scene.selection = 2
        self.scene.confirm()
        self.assertEqual(self.party[0]["job"], "Sollers")
        self.scene.navigate("right", 6)
        self.assertEqual(self.scene.member_index, 0)
        self.scene.click(620, 78)
        self.assertEqual(self.scene.member_index, 0)
        self.scene.change_member(1)
        self.scene.confirm()
        self.scene.change_member(-1)
        self.assertEqual(self.scene.member_index, 1)
        self.scene.navigate("left", 7)
        self.scene.confirm()
        self.assertEqual(self.party[1]["job"], RIQIZAURKEIS)
        self.assertFalse(bind_job(self.party[1], "Seer"))

    def test_each_stone_offers_only_its_classes(self):
        self.assertEqual(STONE_PATHS[BLUE_STONE], ("Seer", "Tidecaller"))
        self.assertEqual(STONE_PATHS[NOKTAKORO], ("Weaver", "Sollers", RIQIZAURKEIS))
        self.assertEqual(STONE_PATHS[SENBRANKA], ("Saint",))
        self.assertFalse(bind_job(self.party[0], "Saint", BLUE_STONE))
        self.scene.start(self.party, 0, reveal=False, stone=SENBRANKA)
        self.scene.confirm()
        self.scene.navigate("left", 1)
        self.scene.confirm()
        self.assertEqual((current_job(self.party[0]), self.party[0]["attuned_stone"]), ("Saint", SENBRANKA))

    def test_existing_menu_routes_unlocked_sync_to_shared_scene(self):
        menu = GameMenu(self.canvas, self.font, lambda: None)
        menu.roster = lambda: self.party
        menu.sync_unlocked = lambda: True
        menu.open()
        menu.selection = 8
        self.assertEqual(menu.activate(), "sync")
        self.assertTrue(all("job" not in p for p in self.party))

    def test_undiscovered_stone_cannot_bind_from_menu(self):
        menu = GameMenu(self.canvas, self.font, lambda: None)
        menu.roster = lambda: self.party
        menu.sync_unlocked = lambda: False
        menu.open()
        menu.selection = 8
        self.assertIsNone(menu.activate())
        menu.activate()
        self.assertNotIn("job", self.party[0])
        self.assertIn("stone", menu.feedback.lower())

    def test_legacy_names_keep_effects_and_are_locked(self):
        for name in ("Saint", "Saint Warrior"):
            character = {"name": "Retri", "hp": 40, "max_hp": 60, "job": name}
            model = BattleModel(ENEMIES[0], hp=40, party=[character])
            self.assertTrue(model.command("Guard"))
            self.assertEqual(character["hp"], 43)
            self.assertFalse(bind_job(character, "Seer"))
        old = {"name": "Retri", "hp": 60, "max_hp": 60, "job": "Cutpurse"}
        self.assertEqual(current_job(old), "Sollers")
        self.assertFalse(bind_job(old, "Saint"))
        self.assertEqual(BattleModel(ENEMIES[0], party=[old], rng=random.Random(1)).gold_reward,
                         ENEMIES[0].gold + 2)

    def test_class_growth_affects_only_future_levels(self):
        members = [member("Retri", RETRI) for _ in range(4)]
        grow(members[0], 1, 2)
        for target, job in zip(members[1:], ("Seer", "Sollers", "Saint")):
            grow(target, 1, 2)
            self.assertTrue(bind_job(target, job))
            self.assertEqual(target["max_hp"], members[0]["max_hp"])
        for target in members:
            grow(target, 2, 4)
        plain, seer, sollers, saint = members
        self.assertGreater(seer["magic"], plain["magic"])
        self.assertGreater(seer["max_mp"], plain["max_mp"])
        self.assertGreater(sollers["agility"], plain["agility"])
        self.assertGreater(saint["max_hp"], plain["max_hp"])
        self.assertGreater(saint["defense"], plain["defense"])

    def test_only_selected_constellation_appears_and_text_fits(self):
        self.scene.start(self.party, 0, reveal=False)
        permanent_count = len(self.scene.sky_tiles) + 1 + len(self.scene.paths)
        for job in ("Seer", "Tidecaller"):
            self.scene.selection = self.scene.paths.index(job)
            self.scene.draw()
            images = [self.canvas.itemcget(i, "image") for i in self.canvas.find_withtag(self.scene.TAG)
                      if self.canvas.type(i) == "image"]
            self.assertEqual(len(images), permanent_count + 1)
            self.assertIn(str(self.scene.silhouettes[job]), images)
            self.assertIn(str(self.scene.icons[job]), images)
        for item in self.canvas.find_withtag(self.scene.TAG):
            if self.canvas.type(item) != "text":
                continue
            text = self.canvas.itemcget(item, "text")
            x1, y1, x2, y2 = self.canvas.bbox(item)
            self.assertTrue(20 <= x1 < x2 <= 940 and 15 <= y1 < y2 <= 525, text)
            if text in DESCRIPTIONS.values():
                self.assertLess(y2 - y1, 50, text)
        self.scene.selection = len(self.scene.paths)
        self.scene.draw()
        images = [i for i in self.canvas.find_withtag(self.scene.TAG)
                  if self.canvas.type(i) == "image"]
        self.assertEqual(len(images), permanent_count)

    def test_stars_twinkle_without_rebuilding_the_screen(self):
        self.scene.start(self.party, 0, reveal=False)
        star, _, _ = self.scene.twinkle_items[0]
        self.scene.update(0)
        initial = self.canvas.itemcget(star, "fill")
        self.scene.update(0.36)
        self.assertNotEqual(self.canvas.itemcget(star, "fill"), initial)
        self.assertEqual(self.scene.phase, "choose")
        self.scene.navigate("down", 1)
        self.scene.update(1.4)
        self.assertEqual(self.scene.selection, 1)
        self.assertTrue(self.canvas.type(self.scene.twinkle_items[0][0]))

    def test_stone_frames_have_transparent_outer_corners(self):
        for stone in self.scene.stones:
            self.assertTrue(stone.transparency_get(0, 0))
            self.assertTrue(stone.transparency_get(stone.width()-1, stone.height()-1))

    def test_noktakoro_constellations_share_the_blue_preview_and_row_slots(self):
        scene, canvas = self.scene, self.canvas
        scene.start(self.party, 0, reveal=False, stone=BLUE_STONE)
        images = {canvas.itemcget(item, "image"): item for item in canvas.find_withtag(scene.TAG)
                  if canvas.type(item) == "image"}
        blue_position = canvas.coords(images[str(scene.silhouettes["Seer"])])
        scene.start(self.party, 0, reveal=False, stone=NOKTAKORO)
        self.assertGreater(canvas.bbox(scene.stone_item)[1], 109)
        for job in ("Weaver", RIQIZAURKEIS):
            scene.selection = scene.paths.index(job)
            scene.draw()
            images = {canvas.itemcget(item, "image"): item for item in canvas.find_withtag(scene.TAG)
                      if canvas.type(item) == "image"}
            item = images[str(scene.silhouettes[job])]
            self.assertEqual(canvas.coords(item), blue_position)
            self.assertLessEqual(canvas.bbox(item)[3], 237)
            self.assertIn(str(scene.icons[job]), images)

    def test_both_stones_have_an_opaque_black_pixel_outline(self):
        outline = (8, 7, 11)
        self.assertTrue(all(stone.get(32, 58) == outline for stone in self.scene.stones))
        black = self.scene.noktakoro_art
        self.assertTrue(black.transparency_get(0, 0))
        self.assertTrue(any(not black.transparency_get(x, y) and black.get(x, y) == outline
                            for x in range(black.width()) for y in range(black.height())))
