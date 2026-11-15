import random
import time
import tkinter as tk
import unittest
from unittest.mock import Mock, patch

import Caldrona_Lite as game
from battle import SHALEHORN, ShalehornBattle
from display_settings import DisplayConfig


class ShalehornTests(unittest.TestCase):
    def test_charge_fracture_tremor_and_burrow(self):
        party = [dict(name=name, hp=600, max_hp=600) for name in ("Retri", "Temur")]
        battle = ShalehornBattle(SHALEHORN, party=party, rng=random.Random(1))

        def round_of(*actions):
            for index, action in enumerate(actions):
                self.assertTrue(battle.command(action))
                self.assertEqual(battle.next_party_turn(), index < len(actions)-1)
            battle.reply()

        round_of("Guard", "Attack")
        self.assertTrue(battle.exposed)
        self.assertEqual(party[0]["hp"], 600)
        before = battle.enemy_hp
        round_of("Attack", "Attack")
        self.assertGreaterEqual(before-battle.enemy_hp, 8)
        self.assertEqual(battle.hits, {0: 10, 1: 10})
        round_of("Attack", "Attack")
        self.assertTrue(battle.buried)
        before = battle.enemy_hp
        round_of("Attack", "Guard")
        self.assertEqual(battle.enemy_hp, before)
        self.assertFalse(battle.buried)

    def test_formation_door_rewards_stone_and_exit(self):
        with patch.object(tk.Tk, "mainloop"), patch.object(game.CaldronaLite, "_init_controller",
                lambda a: setattr(a, "pygame", None)), patch.object(game, "load_display", return_value=DisplayConfig()):
            a = game.CaldronaLite()
        self.addCleanup(a._close)
        a.root.withdraw()
        a._play_music = Mock()
        a._start_cavern()
        a.dialogue.clear()
        for name in ("Temur", "Mira", "Orin"):
            a._recruit(dict(name=name, hp=60, max_hp=60))
        self.assertFalse(a.party[-1]["active"])
        menu = a.game_menu
        menu.open()
        menu.selection = 4
        menu.activate()
        menu.activate()  # Bench Retri.
        for n in range(3):
            menu.navigate("down", 10+n)
        menu.activate()  # Activate Orin.
        menu.close()
        a.x, a.y, a.direction = 49.5*game.TILE, 5.5*game.TILE, "up"
        a._activate()
        self.assertTrue(a.in_chamber and a.dialogue.active)
        while a.dialogue.active:
            a._activate()
        a._update_battle_transition(time.monotonic()+1)
        a._play_music.assert_called_with(game.ASSETS / "audio" / "first-boss.mp3")
        model = a.battle.model
        self.assertEqual([p["name"] for p in model.party], ["Temur", "Mira", "Orin"])
        model.enemy_hp = 1
        a.battle.confirm(0)
        a.battle.confirm(0)
        a.battle.update(1)
        self.assertEqual(a.battle.phase, "result")
        labels = {a.canvas.itemcget(i, "text") for i in a.canvas.find_withtag("battle") if a.canvas.type(i) == "text"}
        self.assertTrue({"TEMUR", "MIRA", "ORIN"} <= labels)
        self.assertNotIn("RETRI", labels)
        a._activate()
        a._update_battle_transition(time.monotonic()+1)
        self.assertTrue(a.boss_cleared)
        a.dialogue.clear()
        a.x, a.y, a.direction = 70.5*game.TILE, 15.5*game.TILE, "up"
        a._activate()
        self.assertTrue(a.astral_sync)
        self.assertEqual(a.screen, "astral")
        self.assertEqual(a.astral_scene.phase, "reveal")
        a._activate()  # Finish the stone reveal.
        a._activate()  # Review Seer for Retri.
        self.assertEqual(a.astral_scene.phase, "confirm")
        a.astral_scene.navigate("left", 1)
        a._activate()  # Confirm the permanent choice.
        self.assertEqual(a.party[0]["job"], "Seer")
        a._back()
        menu.open()
        menu.selection = 1
        self.assertEqual(menu.activate(), "sync")
        menu.close()
        a.x, a.y, a.direction = 70.5*game.TILE, 20.5*game.TILE, "down"
        a._activate()
        self.assertFalse(a.in_chamber)
