"""Astral binding, party navigation, and legacy class compatibility."""
import random
import tkinter as tk
import unittest
from pathlib import Path

from astral_scene import AstralScene
from battle import BattleModel, ENEMIES
from classes import bind_job, current_job
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
        self.scene.selection = 3
        self.assertEqual(self.scene.confirm(), "close")
        self.assertTrue(all("job" not in p for p in self.party))

        self.scene.start(self.party, 4, reveal=False)
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
        self.scene.confirm()
        self.scene.navigate("left", 7)
        self.scene.confirm()
        self.assertEqual(self.party[1]["job"], "Saint")
        self.assertFalse(bind_job(self.party[1], "Seer"))

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
        images = [i for i in self.canvas.find_withtag(self.scene.TAG)
                  if self.canvas.type(i) == "image"]
        self.assertEqual(len(images), 5)  # Stone, selected silhouette, three existing emblems.
        self.assertIn(str(self.scene.silhouettes["Seer"]),
                      [self.canvas.itemcget(i, "image") for i in images])
        for item in self.canvas.find_withtag(self.scene.TAG):
            if self.canvas.type(item) != "text":
                continue
            text = self.canvas.itemcget(item, "text")
            x1, y1, x2, y2 = self.canvas.bbox(item)
            self.assertTrue(20 <= x1 < x2 <= 940 and 15 <= y1 < y2 <= 525, text)
            if text in DESCRIPTIONS.values():
                self.assertLess(y2 - y1, 50, text)
        self.scene.selection = 3
        self.scene.draw()
        images = [i for i in self.canvas.find_withtag(self.scene.TAG)
                  if self.canvas.type(i) == "image"]
        self.assertEqual(len(images), 4)  # No class silhouette for leaving unattuned.
