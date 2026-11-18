"""Catalog, shop stock, and consumable effect checks."""
import random
import tkinter as tk
import unittest
from unittest.mock import patch

import Caldrona_Lite as game
from battle import BattleModel, ENEMIES
from display_settings import DisplayConfig
from item_slots import BLACK, GOLD, GLINT_TAG, SLOT_TAG, SlotGlint, draw_item_slot
from items import CATALOG, BY_NAME, icon_file, use_item
from shops import get_shop_stock, shop_lists
from stats import POTION_HEAL


def _png_size(path):
    data = path.read_bytes()
    if data[1:4] != b"PNG":
        raise AssertionError(f"{path} is not a PNG")
    width = int.from_bytes(data[16:20], "big")
    height = int.from_bytes(data[20:24], "big")
    return width, height


class CatalogTests(unittest.TestCase):
    def test_every_item_has_a_real_32px_icon(self):
        self.assertGreaterEqual(len(CATALOG), 1)
        self.assertEqual(len(BY_NAME), len(CATALOG))
        for item in CATALOG.values():
            path = icon_file(item)
            self.assertTrue(path.is_file(), item.id)
            self.assertEqual(_png_size(path), (32, 32), item.id)
            self.assertTrue(item.icon.startswith(item.icon.split("/")[0] + "/"))
            self.assertGreaterEqual(item.buy_price, 0)
            self.assertEqual(item.sell_price, item.buy_price // 2)

    def test_only_revive_reuses_elixir_art_as_a_placeholder(self):
        placeholders = [item for item in CATALOG.values() if item.placeholder_icon]
        self.assertEqual(placeholders, [])
        self.assertEqual(CATALOG["ember_feather"].icon, "potions/ember_feather.png")
        self.assertNotEqual(CATALOG["ember_feather"].icon, CATALOG["elixir"].icon)
        self.assertFalse(CATALOG["antidote"].placeholder_icon)
        self.assertEqual(CATALOG["antidote"].icon, "potions/antidote_potion.png")

    def test_base_potion_tracks_the_existing_heal_constant(self):
        self.assertEqual(CATALOG["potion"].effect["amount"], POTION_HEAL)
        self.assertEqual(CATALOG["potion"].name, "Potion")

    def test_shop_stock_ids_exist_and_unknown_shops_are_empty(self):
        listed = shop_lists()
        self.assertIn("default", listed)
        stock = get_shop_stock("default")
        self.assertEqual([item.id for item in stock], listed["default"])
        self.assertTrue(all(item.id in CATALOG for item in stock))
        self.assertEqual(get_shop_stock("no-such-shop"), [])


class EffectTests(unittest.TestCase):
    def member(self, **extra):
        base = {"name": "Retri", "hp": 20, "max_hp": 60, "mp": 2, "max_mp": 8}
        base.update(extra)
        return base

    def test_heal_caps_at_max_hp_and_potion_cannot_revive(self):
        member = self.member(hp=50)
        result = use_item("potion", member)
        self.assertTrue(result.ok)
        self.assertEqual((member["hp"], result.healed), (60, 10))
        again = use_item("greater_potion", member)
        self.assertFalse(again.ok)
        self.assertEqual(member["hp"], 60)

        fainted = self.member(hp=0)
        self.assertFalse(use_item("potion", fainted).ok)
        self.assertFalse(use_item("elixir", fainted).ok)
        self.assertEqual(fainted["hp"], 0)
        standing = self.member(hp=1)
        self.assertTrue(use_item("elixir", standing).ok)
        self.assertEqual(standing["hp"], 60)

    def test_revive_only_works_on_the_fainted(self):
        standing = self.member(hp=10, max_hp=80)
        self.assertFalse(use_item("ember_feather", standing).ok)
        self.assertEqual(standing["hp"], 10)
        fainted = self.member(hp=0, max_hp=80)
        result = use_item("ember_feather", fainted)
        self.assertTrue(result.revived)
        self.assertEqual(fainted["hp"], 20)

    def test_antidote_clears_poison_and_refuses_a_healthy_ally(self):
        poisoned = self.member(status="poison")
        result = use_item("antidote", poisoned)
        self.assertTrue(result.ok)
        self.assertIsNone(poisoned["status"])
        healthy = self.member()
        self.assertFalse(use_item("antidote", healthy).ok)
        self.assertNotIn("status", healthy)

    def test_ether_restores_mp_and_caps_at_the_maximum(self):
        member = self.member(mp=0)
        self.assertTrue(use_item("minor_ether", member).ok)
        self.assertEqual(member["mp"], 4)
        member["mp"] = 6
        result = use_item("ether", member)
        self.assertEqual((result.restored_mp, member["mp"]), (2, 8))
        self.assertFalse(use_item("greater_ether", member).ok)
        member["mp"] = 1
        self.assertTrue(use_item("mana_elixir", member).ok)
        self.assertEqual(member["mp"], 8)
        plain = {"name": "Mira", "hp": 10, "max_hp": 40}
        self.assertFalse(use_item("ether", plain).ok)

    def test_gear_is_not_consumed_as_a_potion(self):
        member = self.member(hp=10)
        self.assertFalse(use_item("bronze_saber", member).ok)
        self.assertEqual(member["hp"], 10)


class BattleItemTests(unittest.TestCase):
    def test_battle_use_heals_revives_cures_and_leaves_the_potion_count(self):
        party = [
            {"name": "Retri", "hp": 55, "max_hp": 60, "mp": 7, "max_mp": 8, "status": "poison"},
            {"name": "Temur", "hp": 0, "max_hp": 80, "mp": 0, "max_mp": 6},
        ]
        model = BattleModel(ENEMIES[0], party=party, potions=3, rng=random.Random(1), inventory={
            "greater_potion": 1, "ember_feather": 1, "antidote": 1, "ether": 1,
        })
        self.assertFalse(model.command("Use", target=0, item_id="ember_feather"))
        self.assertEqual(model.inventory["ember_feather"], 1)
        self.assertFalse(model.pending_reply)
        self.assertTrue(model.command("Use", target=0, item_id="greater_potion"))
        self.assertEqual(party[0]["hp"], 60)
        self.assertEqual(model.potions, 3)
        model.pending_reply = False
        self.assertTrue(model.command("Use", target=0, item_id="antidote"))
        self.assertIsNone(party[0]["status"])
        model.pending_reply = False
        self.assertTrue(model.command("Use", target=0, item_id="ether"))
        self.assertEqual(party[0]["mp"], 8)
        model.pending_reply = False
        self.assertTrue(model.command("Use", target=1, item_id="ember_feather"))
        self.assertEqual(party[1]["hp"], 20)
        self.assertEqual(model.inventory["ember_feather"], 0)
        self.assertEqual(model.potions, 3)


class MenuIconTests(unittest.TestCase):
    def test_items_page_draws_icons_and_antidote_does_not_spend_a_potion(self):
        def no_controller(app):
            app.pygame = app.controller_api = None
        with patch.object(tk.Tk, "mainloop"), patch.object(game.CaldronaLite, "_init_controller", no_controller), patch.object(game, "load_display", return_value=DisplayConfig()):
            app = game.CaldronaLite()
        self.addCleanup(app._close)
        app.root.withdraw()
        app._start_cavern()
        app.dialogue.clear()
        app.supplies["antidote"] = 1
        app.supplies["ether"] = 1
        app.party[0]["status"] = "poison"
        menu = app.game_menu
        menu.open()
        menu.activate()
        images = [item for item in app.canvas.find_withtag(menu.TAG) if app.canvas.type(item) == "image"]
        self.assertGreaterEqual(len(images), 2)
        labels = [app.canvas.itemcget(item, "text") for item in app.canvas.find_withtag(menu.TAG)
                  if app.canvas.type(item) == "text"]
        self.assertTrue(any("Potion" in text and "x3" in text for text in labels))
        self.assertTrue(any("Antidote" in text for text in labels))
        menu.navigate("down", 1)
        menu.activate()
        menu.activate()
        self.assertIsNone(app.party[0]["status"])
        self.assertEqual(app.supplies["antidote"], 0)
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
        app.supplies["antidote"] = 1
        app.supplies["ether"] = 1
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

    def test_battle_item_list_uses_the_same_frame_and_cancels_on_close(self):
        def no_controller(app):
            app.pygame = app.controller_api = None
        with patch.object(tk.Tk, "mainloop"), patch.object(game.CaldronaLite, "_init_controller", no_controller), patch.object(game, "load_display", return_value=DisplayConfig()):
            app = game.CaldronaLite()
        self.addCleanup(app._close)
        app.root.withdraw()
        app._start_cavern()
        app.dialogue.clear()
        scene = app.battle
        scene.start(BattleModel(ENEMIES[0], inventory={"antidote": 1}), 0)
        scene.selection = 2
        scene.confirm(0)
        wells = [item for item in app.canvas.find_withtag(SLOT_TAG)
                 if app.canvas.type(item) == "rectangle" and app.canvas.itemcget(item, "fill") == BLACK]
        self.assertEqual(len(wells), 2)
        self.assertEqual(len(scene._slot_boxes), 2)
        running = scene.glint.after_id
        self.assertTrue(_after_alive(app.canvas, running))
        other = scene._slot_boxes[1][1]
        scene._on_motion(type("Event", (), {"x": other[0] + 3, "y": other[1] + 3})())
        self.assertEqual(scene.hover_index, 1)
        self.assertFalse(_after_alive(app.canvas, running))
        hover_id = scene.glint.after_id
        scene._on_motion(type("Event", (), {"x": 1, "y": 1})())
        self.assertIsNone(scene.hover_index)
        self.assertFalse(_after_alive(app.canvas, hover_id))
        scene.start(BattleModel(ENEMIES[0], inventory={
            "antidote": 1, "ether": 1, "elixir": 1, "ember_feather": 1,
        }), 1)
        scene.selection = 2
        scene.confirm(1)
        boxes = [box for _index, box in scene._slot_boxes]
        self.assertEqual(len(boxes), 2)
        self.assertLessEqual(boxes[0][3], boxes[1][1])
        scene.close()
        self.assertIsNone(scene.glint.after_id)
        self.assertEqual(app.canvas.find_withtag(GLINT_TAG), ())


if __name__ == "__main__":
    unittest.main()
