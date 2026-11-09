"""Tk integration checks: screen lifecycle, step gating, and display bounds."""
import random
import time
import tkinter as tk
import unittest
from unittest.mock import Mock, patch

import Caldrona_Lite as game
from battle import BattleModel, BattleScene, ENEMIES, MAX_HP
from display_settings import DisplayConfig, ScaledCanvas


def no_controller(app):
    app.pygame = app.controller_api = None


class BattleIntegrationTests(unittest.TestCase):
    def setUp(self):
        with patch.object(tk.Tk, "mainloop"), patch.object(game.CaldronaLite, "_init_controller", no_controller), patch.object(game, "load_display", return_value=DisplayConfig()):
            self.app = game.CaldronaLite()
        self.app.root.withdraw()
        self.app.root.after_cancel(self.app.tick_after)
        self.app._start_cavern()
        self.app.dialogue.clear()

    def tearDown(self):
        self.app._close()

    def tick(self):
        self.app._tick()
        self.app.root.after_cancel(self.app.tick_after)

    def test_chest_only_opens_once_and_blocks_movement(self):
        a = self.app
        a.x, a.y = 11 * 16 + 8, 5 * 16 + 8
        a.direction = "right"
        a._interact_chest()
        self.assertTrue(a.chest_open)
        self.assertEqual(a.potions, 4)
        a.dialogue.clear()
        a._interact_chest()
        self.assertEqual(a.potions, 4)
        a.dialogue.clear()
        a.keys = {"right"}
        self.tick()
        self.assertEqual((a.x, a.y), (11 * 16 + 8, 5 * 16 + 8))

    def test_victory_screen_levels_and_awards_once(self):
        a = self.app
        a._play_music = Mock()
        a.xp = 20
        a._begin_battle(time.monotonic())
        a._update_battle_transition(time.monotonic() + 1)
        m = a.battle.model
        for i in range(1, len(m.health)):
            m.health[i] = 0
        m.enemy_hp = 1
        a.battle.confirm(0)
        a.battle.confirm(0)
        a.battle.update(1)
        self.assertEqual(a.battle.phase, "result")
        self.assertIsNotNone(a.battle.level_item)
        a.battle.update(1.5)
        self.assertEqual(a.battle.confirm(2), "victory")
        a._finish_battle("victory")
        self.assertEqual(a.level, 2)
        self.assertEqual(a.xp, 20 + m.xp_reward - 30)
        self.assertEqual(a.gold, m.gold_reward)

    def test_encounters_only_on_walked_tiles_and_input_is_locked_during_wipe(self):
        a = self.app
        a.encounters.step = Mock(return_value=True)
        self.tick()
        a.encounters.step.assert_not_called()
        a.x, a.y = 3 * 16 + 8, 3 * 16 + 8
        a.keys = {"left"}  # Wall at tile (2, 3).
        self.tick()
        a.encounters.step.assert_not_called()
        a.game_menu.open()
        a.keys = {"right"}
        self.tick()
        a.encounters.step.assert_not_called()
        a.game_menu.close()
        a.held_direction = None
        self.tick()
        a.encounters.step.assert_called_once()
        self.assertEqual(a.screen, "battle_in")
        position = (a.x, a.y)
        a._back()
        a._activate()
        self.assertEqual(a.screen, "battle_in")
        self.assertEqual((a.x, a.y), position)
        a._update_battle_transition(time.monotonic() + 1)
        self.assertEqual(a.screen, "battle")
        self.assertFalse(a.game_menu.active)
        hp = a.battle.model.hp
        a.battle.update(time.monotonic() + 100)
        self.assertEqual(a.battle.model.hp, hp)  # No timed enemy turns.

    def test_victory_escape_defeat_and_return_music(self):
        a = self.app
        a._play_music = Mock()
        for outcome in ("victory", "fled", "defeat"):
            a.x, a.y = 168, 136
            a._begin_battle(time.monotonic())
            a._update_battle_transition(time.monotonic() + 1)
            a._play_music.assert_called_with(game.BATTLE_MUSIC)
            a.battle.model = BattleModel(ENEMIES[0], hp=20, potions=1)
            a._finish_battle(outcome)
            a._update_battle_transition(time.monotonic() + 1)
            self.assertEqual(a.screen, "game")
            self.assertFalse(a.canvas.find_withtag("battle"))
            self.assertFalse(a.canvas.find_withtag("battle_transition"))
            a._play_music.assert_called_with(game.CAVERN_MUSIC)
            if outcome == "defeat":
                self.assertEqual((a.x, a.y), a.cave.spawn)
                self.assertEqual(a.hp, MAX_HP)
            else:
                self.assertEqual((a.x, a.y), (168, 136))
                self.assertEqual(a.hp, 28 if outcome == "victory" else 20)
        self.assertEqual(a.gold, 8)

    def test_battle_layout_and_all_enemy_sprites_at_every_scale(self):
        for units in (8, 10, 12, 14, 16, 17, 20, 24, 32):
            c = ScaledCanvas(self.app.root, units)
            scene = BattleScene(c, self.app._font, game.ASSETS)
            for enemy in ENEMIES:
                with self.subTest(scale=units, enemy=enemy.name):
                    scene.start(BattleModel(enemy, rng=random.Random(1)), 0)
                    for item in c.find_withtag(scene.DYNAMIC):
                        x1, y1, x2, y2 = c.bbox(item)
                        self.assertGreaterEqual(x1, 0)
                        self.assertLessEqual(x2, c._value(930))
                        self.assertGreaterEqual(y1, c._value(328))
                        self.assertLessEqual(y2, c._value(518))
                    scene.confirm(0)
                    scene.confirm(0)
                    scene.update(0.7)
                    scene.update(1.4)
                    self.assertEqual(scene.phase, "command")
                    scene.close()
            c.destroy()


if __name__ == "__main__":
    unittest.main()
