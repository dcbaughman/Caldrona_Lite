"""Coverage for the Sync wheel and the former Saint Warrior name."""
import tkinter as tk
import unittest

from battle import BattleModel, ENEMIES
from display_settings import ScaledCanvas
from game_menu import GameMenu


class SyncMenuTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.canvas = ScaledCanvas(self.root, 12)
        self.menu = GameMenu(self.canvas, lambda size, bold=False: ("Consolas", size, "bold" if bold else "normal"), lambda: None)
        self.party = [{"name": "Retri", "hp": 40, "max_hp": 60},
                      {"name": "Temur", "hp": 40, "max_hp": 70, "job": "Saint Warrior"}]
        self.menu.roster = lambda: self.party
        self.unlocked = False
        self.menu.sync_unlocked = lambda: self.unlocked
        self.menu.open()
        self.menu.selection = 8
        self.menu.activate()

    def tearDown(self):
        self.root.destroy()

    def test_locked_navigation_assignment_and_legacy_value(self):
        self.assertEqual(len(self.menu.sync_icons), 3)
        self.menu.activate()
        self.assertNotIn("job", self.party[0])
        self.unlocked = True
        self.menu.navigate("right", 1)
        self.assertEqual(self.menu.sync_index, 1)
        self.menu.activate()
        self.assertEqual(self.party[0]["job"], "Cutpurse")
        self.menu.navigate("down", 2)
        self.assertEqual(self.menu.sync_index, 2)
        self.assertEqual(self.party[1]["job"], "Saint Warrior")
        self.menu.activate()
        self.assertEqual(self.party[1]["job"], "Saint")
        self.menu.back()
        self.assertIsNone(self.menu.detail)

    def test_both_saint_names_keep_healing_effect(self):
        for name in ("Saint", "Saint Warrior"):
            with self.subTest(name=name):
                member = {"name": "Retri", "hp": 40, "max_hp": 60, "job": name}
                model = BattleModel(ENEMIES[0], hp=40, party=[member])
                self.assertTrue(model.command("Guard"))
                self.assertEqual(member["hp"], 43)


if __name__ == "__main__":
    unittest.main()
