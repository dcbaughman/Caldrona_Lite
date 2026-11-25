"""Gear ownership, stat effects, and equipment menu interactions."""
import random
import tkinter as tk
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import Caldrona_Lite as game
from battle import BattleModel, ENEMIES, SHALEHORN, ShalehornBattle
from display_settings import DisplayConfig, ScaledCanvas
from equipment import (CATALOG, Equipment, available_count, equip, owned_items,
                       preview_value, stat_value, worn_id)
from game_menu import (EQUIP_ITEM_STEP, EQUIP_ITEM_TOP, EQUIP_MEMBER_X, EQUIP_ROWS,
                       EQUIP_SCROLL_X, EQUIP_SLOT_STEP, EQUIP_SLOT_TOP, GameMenu)
from stats import RETRI, TEMUR, grow, member


class ControllerShoulderTests(unittest.TestCase):
    def test_sdl_and_directinput_shoulder_and_outfit_mappings(self):
        pygame = SimpleNamespace(CONTROLLER_BUTTON_A=0, CONTROLLER_BUTTON_B=1,
                                 CONTROLLER_BUTTON_Y=3,
                                 CONTROLLER_BUTTON_START=6,
                                 CONTROLLER_BUTTON_LEFTSHOULDER=9,
                                 CONTROLLER_BUTTON_RIGHTSHOULDER=10)
        pad = SimpleNamespace(attached=lambda: True, get_button=lambda button: button in {9, 10})
        dummy = SimpleNamespace(pad=pad, joystick=None, pygame=pygame)
        self.assertEqual(game.CaldronaLite._controller_buttons(dummy), {"member_previous", "member_next"})
        pad.get_button = lambda button: button == 3
        self.assertEqual(game.CaldronaLite._controller_buttons(dummy), {"outfit"})
        dummy.pad = None
        dummy.joystick = SimpleNamespace(get_init=lambda: True, get_numbuttons=lambda: 6,
                                         get_button=lambda button: button in {4, 5})
        self.assertEqual(game.CaldronaLite._controller_buttons(dummy), {"member_previous", "member_next"})
        dummy.joystick.get_button = lambda button: button == 3
        self.assertEqual(game.CaldronaLite._controller_buttons(dummy), {"outfit"})
        dummy.joystick = SimpleNamespace(get_init=lambda: True, get_numbuttons=lambda: 4,
                                         get_button=lambda button: False)
        self.assertEqual(game.CaldronaLite._controller_buttons(dummy), set())


class EquipmentRulesTests(unittest.TestCase):
    def setUp(self):
        self.retri, self.temur = member("Retri", RETRI), member("Temur", TEMUR)
        self.roster = [self.retri, self.temur]

    def test_shared_copies_switching_and_removal(self):
        owned = {"training_sword": 1, "miner_blade": 1}
        self.assertEqual([item.name for item in owned_items(owned, "weapon")],
                         ["Miner's Blade", "Training Sword"])
        self.assertTrue(equip(self.retri, "weapon", "training_sword", owned, self.roster)[0])
        self.assertEqual(self.retri["strength"], 8)
        self.assertEqual(stat_value(self.retri, "strength"), 9)
        self.assertEqual(available_count(owned, self.roster, "training_sword"), 0)
        self.assertFalse(equip(self.temur, "weapon", "training_sword", owned, self.roster)[0])
        self.assertIsNone(worn_id(self.temur, "weapon"))
        self.assertTrue(equip(self.retri, "weapon", "miner_blade", owned, self.roster)[0])
        self.assertEqual(available_count(owned, self.roster, "training_sword"), 1)
        self.assertTrue(equip(self.temur, "weapon", "training_sword", owned, self.roster)[0])
        self.assertTrue(equip(self.retri, "weapon", None, owned, self.roster)[0])
        self.assertEqual(stat_value(self.retri, "strength"), 8)
        self.assertEqual(available_count(owned, self.roster, "miner_blade"), 1)

    def test_restrictions_and_preview_do_not_change_state(self):
        item = Equipment("seer_test", "Seer's Test", "accessory", {"magic": 3},
                         jobs=("Seer",), characters=("Retri",))
        with patch.dict(CATALOG, {item.id: item}):
            owned = {item.id: 1}
            before = dict(self.retri)
            self.assertEqual(preview_value(self.retri, "accessory", item.id, "magic"), 6)
            self.assertEqual(self.retri, before)
            self.assertFalse(equip(self.retri, "armor", item.id, owned, self.roster)[0])
            self.assertFalse(equip(self.retri, "accessory", item.id, owned, self.roster)[0])
            self.retri["job"] = "Seer"
            self.assertTrue(equip(self.retri, "accessory", item.id, owned, self.roster)[0])
            self.assertEqual(stat_value(self.retri, "magic"), 6)

    def test_bonus_health_mana_healing_and_level_growth(self):
        charm = Equipment("test_vitality", "Vitality", "accessory", {"max_hp": 10, "max_mp": 3})
        with patch.dict(CATALOG, {charm.id: charm}):
            owned = {charm.id: 1}
            self.assertTrue(equip(self.retri, "accessory", charm.id, owned, self.roster)[0])
            self.assertEqual((self.retri["hp"], stat_value(self.retri, "max_hp")), (60, 70))
            fight = BattleModel(ENEMIES[0], party=[self.retri], potions=1)
            self.assertTrue(fight.command("Potion", target=0))
            self.assertEqual(self.retri["hp"], 70)
            self.retri["mp"] = 11
            grow(self.retri, 1, 2)
            self.assertEqual((self.retri["mp"], stat_value(self.retri, "max_mp")), (12, 12))
            self.assertTrue(equip(self.retri, "accessory", None, owned, self.roster)[0])
            self.assertEqual((self.retri["hp"], self.retri["mp"]), (68, 9))
            self.retri["hp"] = 0
            equip(self.retri, "accessory", charm.id, owned, self.roster)
            self.assertEqual(self.retri["hp"], 0)

    def test_weapon_and_shield_affect_regular_and_boss_combat(self):
        owned = {"training_sword": 1, "wood_shield": 1}
        plain = member("Retri", RETRI)
        equip(self.retri, "weapon", "training_sword", owned, self.roster)
        equip(self.retri, "shield", "wood_shield", owned, self.roster)
        a = BattleModel(ENEMIES[0], party=[plain], rng=random.Random(3))
        b = BattleModel(ENEMIES[0], party=[self.retri], rng=random.Random(3))
        a.command("Attack")
        b.command("Attack")
        self.assertEqual(b.damage, a.damage + 1)
        a.reply()
        b.reply()
        self.assertEqual(b.damage, a.damage - 1)
        self.retri["hp"], plain["hp"] = 60, 60
        a = ShalehornBattle(SHALEHORN, party=[plain], rng=random.Random(1))
        b = ShalehornBattle(SHALEHORN, party=[self.retri], rng=random.Random(1))
        a.command("Attack")
        b.command("Attack")
        a.reply()
        b.reply()
        self.assertEqual(b.damage, a.damage - 1)


class EquipmentMenuTests(unittest.TestCase):
    def setUp(self):
        def no_controller(app):
            app.pygame = app.controller_api = None
        with patch.object(tk.Tk, "mainloop"), patch.object(game.CaldronaLite, "_init_controller", no_controller), patch.object(game, "load_display", return_value=DisplayConfig()):
            self.app = game.CaldronaLite()
        self.app.root.withdraw()
        self.app.root.after_cancel(self.app.tick_after)
        self.app._start_cavern()
        self.app.dialogue.clear()
        self.app._recruit(member("Temur", TEMUR))
        self.menu = self.app.game_menu
        self.menu.open()
        self.menu.selection = 2
        self.menu.activate()

    def tearDown(self):
        self.app._close()

    def labels(self):
        return [self.app.canvas.itemcget(item, "text") for item in self.app.canvas.find_withtag(self.menu.TAG)
                if self.app.canvas.type(item) == "text"]

    def test_choose_compare_equip_switch_and_remove(self):
        menu = self.menu
        self.assertEqual((menu.detail, menu.equip_focus), (2, "category"))
        self.assertIn("EQUIPPED", self.labels())
        self.assertTrue(any(self.app.canvas.itemcget(item, "image") == str(self.app.canvas._image(self.app.battle.hero))
                            for item in self.app.canvas.find_withtag(menu.TAG) if self.app.canvas.type(item) == "image"))
        for name in ("ARMOR", "WEAPON", "SHIELD", "ACCESSORY"):
            self.assertTrue(any(name in label for label in self.labels()))
        menu.navigate("down", 1)
        self.assertEqual(menu.equip_slot, 1)
        menu.activate()
        self.assertEqual(menu.equip_focus, "items")
        self.assertIn("STAT PREVIEW", self.labels())
        self.assertTrue(any("8 > 10" in label for label in self.labels()))
        menu.activate()
        self.assertEqual(worn_id(self.app.party[0], "weapon"), "miner_blade")
        self.assertEqual(stat_value(self.app.party[0], "strength"), 10)
        self.assertTrue(any("[E]" in label for label in self.labels()))
        self.assertIn("0/1", self.labels())
        menu.navigate("right", 2)
        self.assertEqual(menu.member_index, 1)
        menu.activate()
        self.assertIn("other members", menu.feedback)
        self.assertIsNone(worn_id(self.app.party[1], "weapon"))
        menu.navigate("down", 3)
        menu.activate()
        self.assertEqual(worn_id(self.app.party[1], "weapon"), "training_sword")
        menu.navigate("left", 4)
        menu.equip_index = 0
        menu.activate()
        self.assertIsNone(worn_id(self.app.party[0], "weapon"))
        menu.back()
        self.assertEqual(menu.equip_focus, "category")
        menu.back()
        self.assertIsNone(menu.detail)

    def test_shoulders_switch_one_member_per_press_only_in_equipment(self):
        app, menu = self.app, self.menu
        pygame = SimpleNamespace(CONTROLLER_BUTTON_A=0, CONTROLLER_BUTTON_B=1,
                                 CONTROLLER_BUTTON_Y=3,
                                 CONTROLLER_BUTTON_START=6,
                                 CONTROLLER_BUTTON_LEFTSHOULDER=9,
                                 CONTROLLER_BUTTON_RIGHTSHOULDER=10)
        pressed = set()
        pad = SimpleNamespace(attached=lambda: True, get_button=lambda button: button in pressed)
        self.assertTrue(any("L1/R1: CHANGE MEMBER" in label for label in self.labels()))
        for label in ("‹ L1", "RETRI", "R1 ›"):
            self.assertIn(label, self.labels())

        def tick(*buttons):
            pressed.clear()
            pressed.update(buttons)
            app._tick()
            app.root.after_cancel(app.tick_after)

        with patch.object(app, "pygame", pygame), patch.object(app, "pad", pad), \
             patch.object(app, "_scan_controller"), patch.object(app, "_dpad", return_value=set()):
            tick(10)  # R1 selects Temur.
            self.assertEqual(menu.member_index, 1)
            tick(10)  # Holding does not cycle repeatedly.
            self.assertEqual(menu.member_index, 1)
            menu.navigate("left", 2)
            self.assertEqual(menu.member_index, 1)
            menu.navigate("right", 2.1)
            self.assertEqual(menu.member_index, 1)
            menu._equip_click(480, 55)  # The member name itself is not a button.
            self.assertEqual(menu.member_index, 1)
            tick()    # Release re-arms the shoulder button.
            tick(10)
            self.assertEqual(menu.member_index, 0)
            tick()
            menu.activate()  # Switch while browsing an item list.
            self.assertEqual(menu.equip_focus, "items")
            tick(9)   # L1 wraps from Retri to Temur.
            self.assertEqual((menu.member_index, menu.equip_slot, menu.equip_focus), (1, 0, "items"))
            tick()
            tick(9, 10)  # Simultaneous shoulders cancel.
            self.assertEqual(menu.member_index, 1)
            tick()
            menu.back()
            menu.back()  # Main in-game menu: shoulders do nothing.
            self.assertIsNone(menu.detail)
            tick(10)
            self.assertEqual(menu.member_index, 1)

    def test_long_inventory_scrolls_and_mouse_selection_works(self):
        items = {f"test_{i:02}": Equipment(f"test_{i:02}", f"Very Long Training Weapon Number {i:02}", "weapon", {"strength": i})
                 for i in range(15)}
        with patch.dict(CATALOG, items):
            self.app.gear_inventory.update({item_id: 1 for item_id in items})
            self.menu.click(70, EQUIP_SLOT_TOP + EQUIP_SLOT_STEP)
            self.assertEqual((self.menu.equip_slot, self.menu.equip_focus), (1, "items"))
            self.menu.click(EQUIP_SCROLL_X, EQUIP_ITEM_TOP + (EQUIP_ROWS - 1) * EQUIP_ITEM_STEP)
            self.assertGreater(self.menu._equip_scroll(self.menu._equip_entries()), 0)
            for i in range(8):
                self.menu.navigate("down", i + 1)
            self.assertGreater(self.menu._equip_scroll(self.menu._equip_entries()), 0)
            self.assertTrue(any("..." in label for label in self.labels()))
            self.assertIn("▲", self.labels())
            self.app.root.update_idletasks()
            for item in self.app.canvas.find_withtag(self.menu.TAG):
                if self.app.canvas.type(item) == "text":
                    x1, y1, x2, y2 = self.app.canvas.bbox(item)
                    self.assertGreaterEqual(x1, 0)
                    self.assertGreaterEqual(y1, 0)
                    self.assertLessEqual(x2, self.app.canvas._value(960))
                    self.assertLessEqual(y2, self.app.canvas._value(540))

    def test_mouse_equips_switches_member_and_removes(self):
        menu = self.menu
        menu.click(70, EQUIP_SLOT_TOP)
        menu.click(550, EQUIP_ITEM_TOP + EQUIP_ITEM_STEP)
        self.assertEqual(worn_id(self.app.party[0], "armor"), "leather_vest")
        self.assertIn("0/1", self.labels())
        menu.click(EQUIP_MEMBER_X[1], 57)
        self.assertEqual(menu.member_index, 1)
        menu.click(550, EQUIP_ITEM_TOP + EQUIP_ITEM_STEP)
        self.assertIsNone(worn_id(self.app.party[1], "armor"))
        self.assertIn("other members", menu.feedback)
        menu.click(EQUIP_MEMBER_X[0], 57)
        menu.click(550, EQUIP_ITEM_TOP)
        menu.click(550, EQUIP_ITEM_TOP)
        self.assertIsNone(worn_id(self.app.party[0], "armor"))
        self.assertIn("1/1", self.labels())

    def test_bonus_max_hp_in_menu_potions_status_and_battle(self):
        charm = Equipment("test_menu_hp", "Vitality Charm", "accessory", {"max_hp": 10})
        with patch.dict(CATALOG, {charm.id: charm}):
            hero = self.app.party[0]
            self.app.gear_inventory[charm.id] = 1
            self.assertTrue(equip(hero, "accessory", charm.id, self.app.gear_inventory, self.app.party)[0])
            self.assertEqual(self.app._use_menu_item("Potion", hero), "Retri recovered 10 HP.")
            self.assertEqual((hero["hp"], self.app.hp), (70, 70))
            self.menu.back()
            self.menu.selection = 3
            self.menu.activate()
            self.assertTrue(any("70/70" in label for label in self.labels()))
            scene = self.app.battle
            scene.start(BattleModel(ENEMIES[0], party=[hero]), 0)
            battle_labels = [self.app.canvas.itemcget(i, "text") for i in self.app.canvas.find_withtag(scene.DYNAMIC)
                             if self.app.canvas.type(i) == "text"]
            self.assertTrue(any("HP 70 / 70" in label for label in battle_labels))
            scene.close()

    def test_long_description_fits_equipment_panel_at_multiple_scales(self):
        item = Equipment("long_test", "An Exceptionally Long Weapon Name That Needs Room", "weapon",
                         {"strength": 2}, "A detailed description that will be much longer than the panel can display.")
        with patch.dict(CATALOG, {item.id: item}):
            for scale in (8, 12, 24):
                canvas = ScaledCanvas(self.app.root, scale, background="#08090c")
                canvas.pack()
                menu = GameMenu(canvas, self.app._font, lambda: None)
                menu.roster = lambda: self.app.party
                menu.gear_inventory = lambda: {item.id: 1}
                menu.open()
                menu.selection = 2
                menu.activate()
                menu.equip_slot = 1
                menu.activate()
                description = next(i for i in canvas.find_withtag(menu.TAG)
                                   if canvas.type(i) == "text" and canvas.coords(i) ==
                                   [canvas._value(513), canvas._value(297)])
                x1, y1, x2, y2 = canvas.bbox(description)
                self.assertGreaterEqual(x1, canvas._value(508))
                self.assertLessEqual(x2, canvas._value(914))
                self.assertLessEqual(y2, canvas._value(329))
                hint = next(i for i in canvas.find_withtag(menu.TAG)
                            if canvas.type(i) == "text" and "L1/R1" in canvas.itemcget(i, "text"))
                hx1, hy1, hx2, hy2 = canvas.bbox(hint)
                self.assertGreaterEqual(hx1, canvas._value(38))
                self.assertLessEqual(hx2, canvas._value(922))
                self.assertLessEqual(hy2, canvas._value(528))
                header = next(i for i in canvas.find_withtag(menu.TAG)
                              if canvas.type(i) == "text" and "RETRI" == canvas.itemcget(i, "text"))
                x1, y1, x2, y2 = canvas.bbox(header)
                self.assertGreaterEqual(x1, canvas._value(160))
                self.assertLessEqual(x2, canvas._value(810))
                canvas.destroy()


if __name__ == "__main__":
    unittest.main()
