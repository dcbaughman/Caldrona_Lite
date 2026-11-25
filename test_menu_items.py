import tkinter as tk
import unittest
from unittest.mock import patch

import Caldrona_Lite as game
from display_settings import DisplayConfig


class MenuItemTests(unittest.TestCase):
    def test_potions_and_status_for_multiple_members(self):
        def no_controller(app):
            app.pygame = app.controller_api = None
        with patch.object(tk.Tk, "mainloop"), patch.object(game.CaldronaLite, "_init_controller", no_controller), patch.object(game, "load_display", return_value=DisplayConfig()):
            app = game.CaldronaLite()
        self.addCleanup(app._close)
        app.root.withdraw()
        app._start_cavern()
        app.dialogue.clear()
        app._recruit({"name": "Temur", "hp": 30, "max_hp": 70})
        app.party[0]["hp"] = app.hp = 40
        menu = app.game_menu
        menu.open()
        menu.activate()
        menu.activate()
        menu.activate()
        self.assertEqual((app.hp, app.potions), (60, 2))
        menu.activate()
        self.assertEqual(app.potions, 2)
        menu.navigate("down", 1)
        menu.activate()
        self.assertEqual((app.party[1]["hp"], app.potions), (60, 1))
        app.party[1]["hp"] = 0
        menu.activate()
        self.assertEqual(app.potions, 1)
        menu.back()
        menu.back()
        menu.selection = 3
        menu.activate()
        menu.navigate("down", 2)
        self.assertEqual(menu.member_index, 1)
        labels = [app.canvas.itemcget(i, "text") for i in app.canvas.find_withtag(menu.TAG) if app.canvas.type(i) == "text"]
        self.assertTrue(any("Temur" in text for text in labels))
        self.assertTrue(any("0/70" in text for text in labels))

    def test_abilities_tab_browses_moves_without_changing_member(self):
        def no_controller(app):
            app.pygame = app.controller_api = None
        with patch.object(tk.Tk, "mainloop"), patch.object(game.CaldronaLite, "_init_controller", no_controller), patch.object(game, "load_display", return_value=DisplayConfig()):
            app = game.CaldronaLite()
        self.addCleanup(app._close)
        app.root.withdraw()
        app._start_cavern()
        app.dialogue.clear()
        app._recruit({"name": "Temur", "hp": 30, "max_hp": 70})
        from research import kit_for
        saint = [lesson.id for lesson in kit_for("Saint")]
        app.party[0].update(job="Saint", level=10, researched=saint)
        menu = app.game_menu
        menu.open()
        menu.selection = 3
        menu.activate()
        self.assertEqual(menu.status_tab, "stats")
        menu.navigate("down", 1)
        self.assertEqual(menu.member_index, 1)
        menu.navigate("up", 2)
        self.assertEqual(menu.member_index, 0)
        menu.change_equipment_member(1)
        self.assertEqual(menu.status_tab, "abilities")
        self.assertEqual(menu.member_index, 0)
        self.assertEqual(menu.ability_index, 0)
        labels = lambda: [app.canvas.itemcget(i, "text") for i in app.canvas.find_withtag(menu.TAG) if app.canvas.type(i) == "text"]
        self.assertTrue(any("UP/DOWN ability" in text for text in labels()))
        self.assertTrue(any("Mend" in text for text in labels()))
        self.assertTrue(any("Also cures Poison" in text for text in labels()))
        menu.navigate("down", 3)
        self.assertEqual((menu.member_index, menu.ability_index), (0, 1))
        menu.navigate("down", 4)
        self.assertEqual((menu.member_index, menu.ability_index), (0, 2))
        self.assertTrue(any("Smite" in text for text in labels()))
        self.assertTrue(any("1.3x attack" in text for text in labels()))
        self.assertFalse(any("Also cures Poison" in text for text in labels()))
        menu.navigate("down", 5)  # wrap stays on this member
        self.assertEqual(menu.member_index, 0)
        menu.change_equipment_member(-1)
        self.assertEqual(menu.status_tab, "stats")
        menu.navigate("down", 6)
        self.assertEqual(menu.member_index, 1)


if __name__ == "__main__":
    unittest.main()
