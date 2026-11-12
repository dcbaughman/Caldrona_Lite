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
        app.party[0]["hp"] = app.hp = 500
        menu = app.game_menu
        menu.open()
        menu.activate()
        menu.activate()
        menu.activate()
        self.assertEqual((app.hp, app.potions), (520, 2))
        menu.activate()
        self.assertEqual(app.potions, 2)
        menu.navigate("down", 1)
        menu.activate()
        self.assertEqual((app.party[1]["hp"], app.potions), (70, 1))
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


if __name__ == "__main__":
    unittest.main()
