"""The Sunrest gate, encounter boundary, and route save round-trip."""

import random
import unittest
from itertools import combinations, permutations
from unittest.mock import Mock, patch

from Caldrona_Lite import BATTLE_MUSIC, GOLDENLANDS_MUSIC, GRASSLAND_MUSIC
from battle import (ENEMIES, FIELD_GRID, FIELD_HEIGHT, FIELD_HORIZON, GRASSLAND_ENEMIES,
                    BattleModel, grassland_encounter)
from grassland import FENCE, GATE, KORWARD, ROAD
from save_game import capture, validate
from stats import RETRI, TEMUR, member
import test_battle_ui


class GrasslandTests(unittest.TestCase):
    def test_cordon_choice_and_the_first_outside_encounter(self):
        case = test_battle_ui.BattleIntegrationTests()
        case.setUp()
        self.addCleanup(case.tearDown)
        app = case.app
        app._play_music = Mock()
        app.grass_intro_seen = True
        app._change_area(True)
        app._play_music.assert_called_once_with(GRASSLAND_MUSIC)
        app._play_music.reset_mock()

        def tile(x, y):
            app.x, app.y = (x+.5)*16, (y+.5)*16
            app.direction = "down"
            app._update_world(force=True)

        def step(direction):
            app.keys = {direction}
            app.next_step_at = 0
            case.tick()

        def dialogue_done():
            while app.dialogue.active:
                app._activate()

        self.assertIn("korward", app.dialogue.speaker_portraits)
        self.assertTrue(all(not app.grassland_map.walkable(x*16+8, y*16+8) for x, y in FENCE))
        self.assertTrue(app.grassland_map.sheltered(KORWARD))
        self.assertNotIn(KORWARD, app.grassland_map.floor)
        with patch.object(app.encounters, "step", side_effect=(False, True)) as encounter:
            step("down")
            encounter.assert_not_called()
            tile(GATE[0], GATE[1]-1)
            step("down")
            self.assertFalse(app.dialogue.active)
            self.assertEqual(app._facing_tile(), GATE)
            app._activate()
            dialogue_done()
            self.assertEqual(app.screen, "cordon_choice")
            self.assertTrue(app.route_map)
            app._activate()
            self.assertFalse(app.cordon_open)
            app.cordon.show_map()
            self.assertTrue(app.canvas.find_withtag("windehus_map"))
            app._back()
            step("down")
            app._activate()
            dialogue_done()
            app.cordon.select(0)
            app._activate()
            dialogue_done()
            self.assertTrue(app.cordon_open)
            step("down")
            encounter.assert_not_called()
            app._play_music.assert_not_called()
            step("down")
            encounter.assert_called_once()
            app._play_music.assert_called_once_with(GOLDENLANDS_MUSIC)
            step("up")
            app._play_music.assert_called_with(GRASSLAND_MUSIC)
            step("down")
        self.assertEqual(app.screen, "battle_in")
        app._update_battle_transition(float("inf"))
        self.assertTrue(set(app.battle.model.enemies).issubset(GRASSLAND_ENEMIES))
        self.assertIs(app.battle.glow_frames[0], app.battle.grassland_background)
        self.assertEqual(app.screen, "battle")
        app._play_music.assert_called_with(BATTLE_MUSIC, restart=True)
        app._finish_battle("fled")
        app._update_battle_transition(float("inf"))
        app._play_music.assert_called_with(GOLDENLANDS_MUSIC)
        saved = validate(capture(app))
        app._load_journey(saved)
        app._play_music.assert_called_with(GOLDENLANDS_MUSIC)
        self.assertTrue(app.route_map and app.cordon_open)
        app._begin_battle(0)
        app._update_battle_transition(float("inf"))
        app._finish_battle("defeat")
        app._update_battle_transition(float("inf"))
        self.assertEqual((app.x, app.y), app.grassland_map.spawn)
        app._play_music.assert_called_with(GRASSLAND_MUSIC)
        self.assertTrue(all(app.grassland_map.walkable(16*x+8, 16*y+8) for x, y in ROAD))

    def test_solo_encounters_have_one_higher_level_enemy(self):
        rng = random.Random(19)
        formations = [grassland_encounter(rng, 1) for _ in range(40)]
        self.assertEqual({foe for group in formations for foe in group}, set(GRASSLAND_ENEMIES))
        self.assertTrue(all(len(group) == 1 for group in formations))
        self.assertGreater(min(foe.level for foe in GRASSLAND_ENEMIES), max(foe.level for foe in ENEMIES))

    def test_field_grid_fits_all_enemy_sizes_and_keeps_each_target_clickable(self):
        case = test_battle_ui.BattleIntegrationTests()
        case.setUp()
        self.addCleanup(case.tearDown)
        scene = case.app.battle
        hornet, wolf, ram = (scene.enemies[foe.sprite] for foe in GRASSLAND_ENEMIES)
        self.assertLessEqual(hornet.width(), scene.enemies["bat.png"].width() + 4)
        for animal in (wolf, ram):
            self.assertGreater(animal.width(), hornet.width())
            self.assertLessEqual(animal.height(), scene.hero.height())
        self.assertEqual(scene.grassland_background.height(), FIELD_HEIGHT)

        party = [member("Retri", RETRI), member("Temur", TEMUR)]
        for count in (1, 2, 3):
            for foes in permutations(GRASSLAND_ENEMIES, count):
                with self.subTest(foes=[foe.name for foe in foes]):
                    scene.start(BattleModel(foes, party=party), 0, outdoors=True)
                    points = scene.enemy_positions + scene.party_positions
                    self.assertTrue(all(x % FIELD_GRID == 0 for x, _ in points))
                    # In logical coordinates the renderer's full image bounds leave space for movement.
                    enemy_images = [scene.enemies[foe.sprite] for foe in foes]
                    images = enemy_images + scene.party_sprites
                    bounds = [(x - art.width() // 2, y - art.height() // 2,
                               x + (art.width() + 1) // 2, y + (art.height() + 1) // 2)
                              for (x, y), art in zip(points, images, strict=True)]
                    for (left, top, right, bottom), art in zip(bounds, images, strict=True):
                        self.assertGreaterEqual(left, FIELD_GRID)
                        for row in range(max(0, FIELD_HORIZON - top)):
                            self.assertTrue(all(art.transparency_get(x, row) for x in range(art.width())))
                        self.assertLessEqual(right, 896)
                        self.assertLessEqual(bottom, FIELD_HEIGHT - FIELD_GRID)
                    for first, second in combinations(bounds[:count], 2):
                        self.assertTrue(first[2] + FIELD_GRID <= second[0]
                                        or second[2] + FIELD_GRID <= first[0]
                                        or first[3] + FIELD_GRID <= second[1])
                    self.assertLessEqual(max(bound[2] for bound in bounds[:count]) + FIELD_GRID, bounds[count][0])
                    scene.phase = "target"
                    with patch.object(scene, "confirm"):
                        for index, (x, y) in enumerate(scene.enemy_positions):
                            scene.click(x, y, 0)
                            self.assertEqual(scene.model.target, index)
                    scene.close()

        # Regular formations mirror between encounters, including in the cave.
        for outdoors, foes in ((False, ENEMIES), (True, GRASSLAND_ENEMIES)):
            with self.subTest(outdoors=outdoors):
                layouts = []
                for _ in range(2):
                    scene.start(BattleModel(foes, party=party), 0, outdoors=outdoors)
                    layouts.append(scene.enemy_positions)
                    scene.close()
                first, second = layouts
                first_x = [x for x, _ in first]
                second_x = [x for x, _ in second]
                self.assertEqual(first_x, [second_x[1], second_x[0], second_x[1]])
                self.assertNotEqual(first_x[0], first_x[1])
                self.assertEqual([y for _, y in first], [y for _, y in second])
