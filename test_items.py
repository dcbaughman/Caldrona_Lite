"""Supply icons, his prices, and the framed item slots."""
import tkinter as tk
import unittest
from unittest.mock import patch

import Caldrona_Lite as game
from consumables import SUPPLIES, apply_supply
from display_settings import DisplayConfig
from item_slots import BLACK, GOLD, GLINT_TAG, SLOT_TAG, SlotGlint, draw_item_slot
from items import supply_icon
from stats import POTION_HEAL


def _png_size(path):
    data = path.read_bytes()
    if data[1:4] != b"PNG":
        raise AssertionError(f"{path} is not a PNG")
    width = int.from_bytes(data[16:20], "big")
    height = int.from_bytes(data[20:24], "big")
    return width, height


class CatalogTests(unittest.TestCase):
    def test_his_supply_prices_and_icons_stay(self):
        self.assertEqual(SUPPLIES["Potion"][0], 10)
        self.assertEqual(SUPPLIES["Ether"][0], 18)
        self.assertEqual(SUPPLIES["Ember Feather"][0], 30)
        self.assertNotIn("Ember Talisman", SUPPLIES)
        for name in SUPPLIES:
            path = supply_icon(name)
            self.assertIsNotNone(path, name)
            self.assertEqual(_png_size(path), (32, 32), name)
        member = {"name": "Retri", "hp": 40, "max_hp": 60}
        self.assertTrue(apply_supply("Potion", member)[0])
        self.assertEqual(member["hp"], min(60, 40 + POTION_HEAL))


class MenuIconTests(unittest.TestCase):
    def test_items_page_draws_icons_and_feather_does_not_spend_a_potion(self):
        def no_controller(app):
            app.pygame = app.controller_api = None
        with patch.object(tk.Tk, "mainloop"), patch.object(game.CaldronaLite, "_init_controller", no_controller), patch.object(game, "load_display", return_value=DisplayConfig()):
            app = game.CaldronaLite()
        self.addCleanup(app._close)
        app.root.withdraw()
        app._start_cavern()
        app.dialogue.clear()
        app.supplies["Ember Feather"] = 1
        menu = app.game_menu
        menu.open()
        menu.activate()
        images = [item for item in app.canvas.find_withtag(menu.TAG) if app.canvas.type(item) == "image"]
        self.assertGreaterEqual(len(images), 2)
        labels = [app.canvas.itemcget(item, "text") for item in app.canvas.find_withtag(menu.TAG)
                  if app.canvas.type(item) == "text"]
        self.assertTrue(any("Potion" in text and "x3" in text for text in labels))
        self.assertTrue(any("Ember Feather" in text for text in labels))
        menu.navigate("down", 1)
        menu.navigate("down", 2)
        menu.activate()
        menu.activate()
        self.assertEqual(app.party[0]["hp"], app.party[0]["max_hp"])
        self.assertEqual(app.supplies["Ember Feather"], 1)
        self.assertEqual(app.potions, 3)


def _after_alive(canvas, after_id):
    try:
        canvas.tk.call("after", "info", after_id)
    except tk.TclError:
        return False
    return True


class SlotFrameTests(unittest.TestCase):
    def test_glint_follows_one_slot_and_cancels_on_stop(self):
        root = tk.Tk()
        root.withdraw()
        canvas = tk.Canvas(root, width=120, height=80)
        self.addCleanup(root.destroy)
        first = draw_item_slot(canvas, 24, 24, None)
        second = draw_item_slot(canvas, 80, 24, None)
        wells = [item for item in canvas.find_withtag(SLOT_TAG)
                 if canvas.type(item) == "rectangle" and canvas.itemcget(item, "fill") == BLACK]
        golds = [item for item in canvas.find_withtag(SLOT_TAG)
                 if canvas.type(item) == "rectangle" and canvas.itemcget(item, "fill") == GOLD]
        self.assertEqual(len(wells), 2)
        self.assertEqual(len(golds), 2)
        glint = SlotGlint(canvas)
        glint.play(first)
        started = glint.after_id
        self.assertIsNotNone(started)
        self.assertGreater(len(canvas.find_withtag(GLINT_TAG)), 0)
        glint.play(second)
        self.assertFalse(_after_alive(canvas, started))
        self.assertIsNotNone(glint.after_id)
        self.assertNotEqual(glint.after_id, started)
        moved = glint.after_id
        glint.stop()
        self.assertIsNone(glint.after_id)
        self.assertFalse(_after_alive(canvas, moved))
        self.assertEqual(canvas.find_withtag(GLINT_TAG), ())

    def test_menu_frames_every_icon_and_hover_cancels_on_leave_and_close(self):
        def no_controller(app):
            app.pygame = app.controller_api = None
        with patch.object(tk.Tk, "mainloop"), patch.object(game.CaldronaLite, "_init_controller", no_controller), patch.object(game, "load_display", return_value=DisplayConfig()):
            app = game.CaldronaLite()
        self.addCleanup(app._close)
        app.root.withdraw()
        app._start_cavern()
        app.dialogue.clear()
        menu = app.game_menu
        menu.open()
        menu.activate()
        wells = [item for item in app.canvas.find_withtag(SLOT_TAG)
                 if app.canvas.type(item) == "rectangle" and app.canvas.itemcget(item, "fill") == BLACK]
        self.assertEqual(len(wells), 3)
        self.assertEqual(len(menu._slot_boxes), 3)
        selected = menu.glint.after_id
        self.assertTrue(_after_alive(app.canvas, selected))
        menu.navigate("down", 1)
        self.assertEqual(menu.item_index, 1)
        self.assertFalse(_after_alive(app.canvas, selected))
        self.assertTrue(_after_alive(app.canvas, menu.glint.after_id))
        hovered = menu._slot_boxes[0][1]
        menu._on_motion(type("Event", (), {"x": hovered[0] + 4, "y": hovered[1] + 4})())
        self.assertEqual(menu.hover_index, 0)
        hover_id = menu.glint.after_id
        self.assertIsNotNone(hover_id)
        self.assertGreater(len(app.canvas.find_withtag(GLINT_TAG)), 0)
        menu._on_motion(type("Event", (), {"x": 10, "y": 10})())
        self.assertIsNone(menu.hover_index)
        self.assertFalse(_after_alive(app.canvas, hover_id))
        self.assertTrue(_after_alive(app.canvas, menu.glint.after_id))
        menu.close()
        self.assertIsNone(menu.glint.after_id)
        self.assertFalse(_after_alive(app.canvas, hover_id))
        self.assertEqual(app.canvas.find_withtag(GLINT_TAG), ())
        self.assertFalse(menu.active)

if __name__ == "__main__":
    unittest.main()
