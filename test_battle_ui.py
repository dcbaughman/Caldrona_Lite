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
    def test_temur_uses_matching_sprite_scale_and_portraits(self):
        a = self.app
        self.assertEqual((a.temur_image.width(), a.temur_image.height()),
                         (a.player_frames["down"][1].width(), a.player_frames["down"][1].height()))
        self.assertEqual((a.battle.temur.width(), a.battle.temur.height()),
                         (a.battle.hero.width(), a.battle.hero.height()))
        a.x, a.y, a.direction = 9 * 16 + 8, 7 * 16 + 8, "right"
        a._interact_temur()
        portrait = a.dialogue.portrait(game.TEMUR_PORTRAIT, None)
        self.assertIsNotNone(portrait)
        self.assertEqual((portrait.width(), portrait.height()), (128, 128))
        images = [item for item in a.canvas.find_withtag("dialogue") if a.canvas.type(item) == "image"]
        self.assertEqual(len(images), 1)
        for line in a.dialogue.lines:
            if line.speaker == "Temur":
                self.assertEqual(line.portrait, game.TEMUR_PORTRAIT)
        a.dialogue.clear()
        a.party.append({"name": "Temur", "hp": 70, "max_hp": 70})
        a.game_menu.open()
        images = [item for item in a.canvas.find_withtag("game_menu") if a.canvas.type(item) == "image"]
        self.assertEqual(len(images), 2)

    def test_temur_recruitment_and_party_turns(self):
        a = self.app
        a.x, a.y, a.direction = 9 * 16 + 8, 7 * 16 + 8, "right"
        self.assertTrue(a._interact_temur())
        while a.dialogue.active:
            a._activate()
        self.assertEqual(a.screen, "cave_shake")
        a.shake_started = time.monotonic() - 2
        self.tick()
        self.assertEqual(a.temur_story, "joining")
        while a.dialogue.active:
            a._activate()
        self.assertEqual([p["name"] for p in a.party], ["Retri", "Temur"])
        self.assertFalse(a._interact_temur())
        a._begin_battle(time.monotonic())
        a._update_battle_transition(time.monotonic()+1)
        m = a.battle.model
        self.assertEqual(len(m.party), 2)
        m.command("Guard")
        self.assertTrue(m.next_party_turn())
        self.assertEqual(m.party[m.actor]["name"], "Temur")
        m.command("Guard")
        self.assertFalse(m.next_party_turn())
        m.reply()
        self.assertFalse(m.pending_reply)

    def test_reserve_member_grows_and_late_recruit_matches_party_level(self):
        from stats import RETRI, TEMUR, member
        a = self.app
        reserve = member("Temur", TEMUR)
        reserve["active"] = False
        a.party.append(reserve)
        a.xp = 20
        a.battle.model = BattleModel(ENEMIES[0], party=[a.party[0]], level=1, xp=20)
        a._finish_battle("victory")
        self.assertEqual(a.level, 2)
        self.assertEqual((reserve["max_hp"], reserve["strength"]), (92, 12))
        self.assertEqual(a.party[0]["max_hp"], RETRI["max_hp"] + 8)
        a.party.remove(reserve)
        a._recruit(member("Temur", TEMUR))
        self.assertEqual((a.party[-1]["max_hp"], a.party[-1]["strength"]), (92, 12))

    def test_game_over_choices(self):
        a = self.app
        for choice in (0, 1):
            a._begin_battle(time.monotonic())
            a._update_battle_transition(time.monotonic() + 1)
            a._show_game_over(time.monotonic())
            a.game_over_selection = choice
            a._activate()
            if choice == 0:
                self.assertEqual(a.screen, "battle_out")
                a._update_battle_transition(time.monotonic() + 1)
                self.assertEqual(a.screen, "game")
            else:
                self.assertEqual(a.screen, "menu")

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

    def test_cave_solid_rock_fills_void_without_becoming_walkable(self):
        a = self.app
        self.assertNotIn((0, 0), a.cave.floor)
        self.assertFalse(a.cave.walkable(8, 8))
        chunk = a._build_chunk((0, 0))
        self.assertFalse(chunk.transparency_get(8, 8))

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

    def test_party_roster_shows_all_active_members_and_updates(self):
        party = [
            {"name": "Retri", "hp": 520, "max_hp": 520},
            {"name": "Temur", "hp": 870, "max_hp": 1030},
            {"name": "Ally", "hp": 123, "max_hp": 200},
        ]
        scene = self.app.battle
        scene.start(BattleModel(ENEMIES[0], party=party), 0)
        def labels():
            c = self.app.canvas
            return [c.itemcget(item, "text") for item in c.find_withtag(scene.DYNAMIC)
                    if c.type(item) == "text"]
        for name, hp in (("Retri", "HP 520 / 520"), ("Temur", "HP 870 / 1030"),
                         ("Ally", "HP 123 / 200")):
            self.assertTrue(any(name in label for label in labels()))
            self.assertIn(hp, labels())
        party[1]["hp"] = 800
        scene.model.actor = 1
        scene.draw_status()
        self.assertIn("HP 800 / 1030", labels())
        self.assertIn("> Temur", labels())
        self.assertEqual((scene.backdrop.width(), scene.backdrop.height()), (960, 321))

    def test_cavern_lights_pulse_during_command_selection(self):
        scene = self.app.battle
        scene.start(BattleModel(ENEMIES[0]), 0)
        scene.update(0.41)
        self.assertEqual(scene.glow_index, 1)
        scene.update(0.81)
        self.assertEqual(scene.glow_index, 2)
        scene.update(1.21)
        self.assertEqual(scene.glow_index, 1)
        self.assertEqual(scene.phase, "command")

    def test_cavern_backgrounds_rotate_without_immediate_repeats(self):
        scene = self.app.battle
        selections = []
        for _ in range(9):
            scene.start(BattleModel(ENEMIES[0]), 0)
            selections.append(scene.background_index)
            self.assertIs(scene.glow_frames, scene.backgrounds[scene.background_index])
            scene.close()
        for start in (0, 3, 6):
            self.assertEqual(set(selections[start:start+3]), {0, 1, 2})
        self.assertTrue(all(a != b for a, b in zip(selections, selections[1:])))


if __name__ == "__main__":
    unittest.main()
