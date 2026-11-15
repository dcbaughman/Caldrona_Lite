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
    def test_battle_sprites_follow_each_members_class(self):
        from stats import RETRI, TEMUR, member
        scene = self.app.battle
        retri, temur = member("Retri", RETRI), member("Temur", TEMUR)
        for job in ("Sollers", "Saint", "Seer"):
            retri["job"] = temur["job"] = job
            scene.start(BattleModel(ENEMIES[0], party=[retri, temur]), 0)
            self.assertIs(scene.party_sprites[0], scene.class_sprites[("Retri", job)])
            self.assertIs(scene.party_sprites[1], scene.class_sprites[("Temur", job)])
            for sprite, reference in zip(scene.party_sprites, (scene.hero, scene.temur)):
                self.assertEqual((sprite.width(), sprite.height()), (scene.hero.width(), scene.hero.height()))
                def visible_rows(image):
                    return [y for y in range(image.height())
                            if any(not image.transparency_get(x, y) for x in range(image.width()))]
                self.assertEqual((min(visible_rows(sprite)), max(visible_rows(sprite))),
                                 (min(visible_rows(reference)), max(visible_rows(reference))))
            scene.close()
        retri["job"], temur["job"] = "Cutpurse", "Saint"
        scene.start(BattleModel(ENEMIES[0], party=[retri, temur]), 0)
        self.assertIs(scene.party_sprites[0], scene.class_sprites[("Retri", "Sollers")])
        self.assertIs(scene.party_sprites[1], scene.class_sprites[("Temur", "Saint")])
        scene.close()
        del retri["job"]
        del temur["job"]
        scene.start(BattleModel(ENEMIES[0], party=[retri, temur]), 0)
        self.assertIs(scene.party_sprites[0], scene.hero)
        self.assertIs(scene.party_sprites[1], scene.temur)
        scene.close()

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

    def test_reserve_keeps_experience_and_new_recruits_start_at_level_one(self):
        from stats import RETRI, TEMUR, member
        a = self.app
        reserve = member("Temur", TEMUR)
        reserve["active"] = False
        a.party.append(reserve)
        a.party[0]["xp"] = 20
        before = dict(reserve)
        a.battle.model = BattleModel(ENEMIES[0], party=[a.party[0]], level=1, xp=20)
        a._finish_battle("victory")
        self.assertEqual(a.level, 2)
        self.assertEqual(reserve, before)
        self.assertEqual(a.party[0]["max_hp"], RETRI["max_hp"] + 8)
        a.party.remove(reserve)
        a._recruit(member("Temur", TEMUR))
        self.assertEqual((a.party[-1]["level"], a.party[-1]["xp"], a.party[-1]["max_hp"]),
                         (1, 0, TEMUR["max_hp"]))

    def test_guard_poses_follow_guard_state_and_fainting(self):
        from stats import RETRI, TEMUR, member
        scene, canvas = self.app.battle, self.app.canvas
        retri, temur = member("Retri", RETRI), member("Temur", TEMUR)
        retri["job"], temur["job"] = "Seer", "Saint"
        model = BattleModel(ENEMIES[0], party=[retri, temur])
        scene.start(model, 0)
        scene.selection = 1
        scene.confirm(0)
        self.assertEqual(canvas.itemcget(scene.party_items[0], "image"), str(canvas._image(scene.guard_sprites["Retri"])))
        scene.update(0.7)
        scene.selection = 1
        scene.confirm(0.8)
        self.assertEqual(canvas.itemcget(scene.party_items[1], "image"), str(canvas._image(scene.guard_sprites["Temur"])))
        scene.update(1.5)
        self.assertFalse(model.guarded)
        for i in range(2):
            self.assertEqual(canvas.itemcget(scene.party_items[i], "image"), str(canvas._image(scene.party_sprites[i])))
        model.guarded.add(1)
        temur["hp"] = 0
        scene._sync_party_sprites()
        self.assertEqual(canvas.itemcget(scene.party_items[1], "image"), str(canvas._image(scene.temur_fainted)))
        scene.close()

    def test_stone_can_be_deferred_revisited_and_opened_from_menu(self):
        a = self.app
        a.boss_cleared = True
        a.x, a.y, a.direction = 70.5*game.TILE, 15.5*game.TILE, "up"
        a._activate()
        self.assertEqual((a.screen, a.astral_scene.phase), ("astral", "reveal"))
        a._activate()
        a.astral_scene.selection = 3
        a._activate()
        self.assertEqual(a.screen, "game")
        self.assertNotIn("job", a.party[0])
        a._activate()
        self.assertEqual((a.screen, a.astral_scene.phase), ("astral", "choose"))
        a._back()
        a.game_menu.open()
        a.game_menu.selection = 8
        a._activate()
        self.assertEqual((a.screen, a.astral_scene.phase), ("astral", "choose"))
        self.assertNotIn("job", a.party[0])

    def test_walking_into_stone_after_boss_opens_reveal(self):
        a = self.app
        a.boss_cleared = True
        a.in_chamber = True
        a.x, a.y = 70.5 * game.TILE, 15.5 * game.TILE
        a.keys = {"up"}
        self.tick()
        self.assertEqual((a.screen, a.astral_scene.phase), ("astral", "reveal"))

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
        a.party[0]["xp"] = 20
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
        self.assertIsNone(a.battle.confirm(2))
        self.assertEqual(a.battle.result_page, 0)
        self.assertEqual(a.battle.confirm(3), "victory")
        a._finish_battle("victory")
        self.assertEqual(a.level, 2)
        self.assertEqual(a.xp, 20 + m.xp_reward - 30)
        self.assertEqual(a.gold, m.gold_reward)

    def test_fainted_pose_tracks_hp_during_and_between_battles(self):
        from stats import RETRI, TEMUR, member
        scene, canvas = self.app.battle, self.app.canvas
        retri, temur = member("Retri", RETRI), member("Temur", TEMUR)
        retri["job"], temur["job"] = "Seer", "Saint"
        retri["hp"] = 0
        model = BattleModel(ENEMIES[0], party=[retri, temur])
        scene.start(model, 0)
        self.assertEqual(model.actor, 1)
        self.assertEqual(canvas.itemcget(scene.party_items[0], "image"), str(canvas._image(scene.fainted)))
        x, y = scene.party_positions[0]
        self.assertEqual(canvas.coords(scene.party_items[0]), [canvas._value(x), canvas._value(y+8)])
        self.assertEqual(canvas.itemcget(scene.party_items[1], "image"),
                         str(canvas._image(scene.class_sprites[("Temur", "Saint")])))
        # A later revival restores that member's actual class outfit.
        retri["hp"] = 10
        scene.update(0.1)
        self.assertEqual(canvas.itemcget(scene.party_items[0], "image"),
                         str(canvas._image(scene.class_sprites[("Retri", "Seer")])))
        self.assertEqual(canvas.coords(scene.party_items[0]), [canvas._value(x), canvas._value(y)])
        scene.close()

        retri["hp"], temur["hp"] = 60, 1
        rng = Mock()
        rng.randint.return_value = 9
        rng.randrange.return_value = 1
        model = BattleModel(ENEMIES[0], party=[retri, temur], rng=rng)
        scene.start(model, 0)
        scene.selection = 1  # Retri guards.
        scene.confirm(0)
        scene.update(0.7)
        scene.selection = 0  # Temur attacks instead of healing himself via Saint Guard.
        scene.confirm(1)
        scene.confirm(1)
        scene.update(1.7)
        self.assertEqual(temur["hp"], 0)
        self.assertEqual(scene.phase, "enemy_action")
        self.assertEqual(canvas.itemcget(scene.party_items[1], "image"), str(canvas._image(scene.temur_fainted)))
        self.assertEqual(canvas.itemcget(scene.party_items[0], "image"),
                         str(canvas._image(scene.class_sprites[("Retri", "Seer")])))
        scene.update(2.4)
        self.assertEqual(scene.phase, "command")
        self.assertEqual(model.actor, 0)
        scene.close()

    def test_victory_without_level_up_does_not_add_stat_pages(self):
        scene = self.app.battle
        model = BattleModel(ENEMIES[0], party=[self.app.party[0]], level=1, xp=0)
        model.xp_reward = 1
        model.outcome = "victory"
        scene.start(model, 0)
        scene.phase = "result"
        scene._victory_screen(0)
        self.assertEqual(scene.level_pages, [])
        self.assertEqual(scene.confirm(1), "victory")
        scene.close()

    def test_level_up_pages_preview_actual_growth_without_mutating_party(self):
        from stats import RETRI, TEMUR, grow, member
        scene, canvas = self.app.battle, self.app.canvas
        retri, temur, reserve = member("Retri", RETRI), member("Temur", TEMUR), member("Retri", RETRI)
        retri["job"], temur["job"], reserve["job"] = "Saint", "Sollers", "Seer"
        retri["xp"], temur["xp"] = 29, 0
        reserve["name"], reserve["active"], reserve["hp"] = "Mira", False, 0
        roster = [retri, temur, reserve]
        before = [dict(p) for p in roster]
        scene.level_roster = lambda: roster
        model = BattleModel(ENEMIES[0], party=[retri, temur], level=1, xp=29)
        model.xp_reward = 140  # Cross multiple levels.
        model.outcome = "victory"
        scene.start(model, 0)
        scene.phase = "result"
        scene._victory_screen(0)
        self.assertEqual(roster, before)
        self.assertEqual(len(scene.level_pages), 2)
        expected_roster = []
        for i, character in enumerate(before[:2]):
            self.assertIsNone(scene.confirm(i + 1))
            name, active, old_level, new_level, changes = scene.level_pages[i]
            expected = dict(character)
            grow(expected, old_level, new_level)
            expected_roster.append(expected)
            self.assertEqual(name, character["name"])
            self.assertEqual(active, character.get("active", True))
            self.assertIn(("MAX HP", character["max_hp"], expected["max_hp"]), changes)
            self.assertIn(("STRENGTH", character["strength"], expected["strength"]), changes)
            labels = [canvas.itemcget(item, "text") for item in canvas.find_withtag(scene.TAG)
                      if canvas.type(item) == "text"]
            self.assertTrue(any(name.upper() in label for label in labels))
            self.assertIn(f"{character['max_hp']} → {expected['max_hp']}", labels)
            for item in canvas.find_withtag(scene.TAG):
                if canvas.type(item) == "text":
                    x1, y1, x2, y2 = canvas.bbox(item)
                    self.assertTrue(0 <= x1 < x2 <= canvas._value(960))
                    self.assertTrue(0 <= y1 < y2 <= canvas._value(540))
        self.assertEqual(roster, before)  # Preview never awards stats twice.
        self.assertEqual(scene.confirm(5), "victory")
        self.app.party = roster
        self.app.level, self.app.xp = 1, 29
        self.app._finish_battle("victory")
        for actual, expected in zip(roster, expected_roster):
            for key in ("max_hp", "max_mp", "strength", "defense", "magic",
                        "magic_defense", "agility", "luck", "evasion", "accuracy"):
                self.assertEqual(actual[key], expected[key], (actual["name"], key))
        self.assertEqual(reserve, before[2])
        scene.close()

    def test_party_wide_boss_attack_displays_all_fainted_members(self):
        from battle import SHALEHORN, ShalehornBattle
        from stats import RETRI, TEMUR, member
        scene, canvas = self.app.battle, self.app.canvas
        party = [member("Retri", RETRI), member("Temur", TEMUR)]
        for character in party:
            character["hp"] = 1
        model = ShalehornBattle(SHALEHORN, party=party, rng=random.Random(3))
        model.move_index = 1  # Quarry Tremor damages all standing members.
        scene.start(model, 0)
        scene.selection = 1
        scene.confirm(0)
        scene.update(0.7)
        scene.confirm(1)
        scene.update(1.7)
        self.assertEqual([p["hp"] for p in party], [0, 0])
        self.assertEqual(model.outcome, "defeat")
        self.assertEqual(canvas.itemcget(scene.party_items[0], "image"), str(canvas._image(scene.fainted)))
        self.assertEqual(canvas.itemcget(scene.party_items[1], "image"), str(canvas._image(scene.temur_fainted)))
        scene.update(2.4)
        self.assertEqual(scene.phase, "result")
        scene.close()

    def test_potion_ally_targeting_cancel_and_white_indicators(self):
        from stats import RETRI, TEMUR, member
        scene, canvas = self.app.battle, self.app.canvas
        retri, temur = member("Retri", RETRI), member("Temur", TEMUR)
        temur["hp"] = 20
        fainted = {"name": "Mira", "hp": 0, "max_hp": 50}
        model = BattleModel(ENEMIES[0], party=[retri, temur, fainted])
        scene.start(model, 0)
        self.assertEqual(canvas.itemcget(scene.party_items[2], "text"), "Mira (KO)")
        scene.selection = 2
        scene.confirm(0)  # Items.
        scene.confirm(0)  # Potion: choose an ally.
        self.assertEqual(scene.phase, "ally_target")
        marker = canvas.find_withtag("battle_target_indicator")
        self.assertEqual(len(marker), 1)
        self.assertEqual(canvas.itemcget(marker[0], "fill"), "#ffffff")
        scene.navigate("down", 1)
        self.assertEqual(scene.ally_target, 1)
        scene.back()
        self.assertEqual((scene.phase, scene.item_menu, model.potions), ("command", True, 3))
        self.assertFalse(model.pending_reply)
        scene.confirm(2)
        scene.navigate("down", 3)
        scene.navigate("down", 3.3)
        self.assertEqual(scene.ally_target, 2)
        scene.confirm(4)
        self.assertEqual(scene.phase, "ally_target")
        self.assertIn("cannot revive", model.message)
        self.assertEqual(model.potions, 3)
        scene.navigate("up", 5)
        scene.confirm(5)
        self.assertEqual([p["hp"] for p in model.party], [60, 50, 0])
        self.assertEqual(model.potions, 2)
        self.assertTrue(model.pending_reply)
        scene.update(5.7)
        self.assertEqual((scene.phase, model.actor), ("command", 1))
        self.assertFalse(model.pending_reply)
        scene.close()

        scene.start(BattleModel(ENEMIES[0], party=[retri, temur]), 0)
        scene.confirm(0)  # Attack: choose an enemy.
        marker = canvas.find_withtag("battle_target_indicator")
        self.assertEqual(len(marker), 1)
        self.assertEqual(canvas.itemcget(marker[0], "fill"), "#ffffff")
        for item in canvas.find_withtag(scene.DYNAMIC):
            if canvas.type(item) == "text" and canvas.itemcget(item, "text") == "▶":
                self.assertEqual(canvas.itemcget(item, "fill"), "#ffffff")
        scene.close()

        temur["hp"] = 20
        model = BattleModel(ENEMIES[0], party=[retri, temur])
        scene.start(model, 0)
        scene.selection = 2
        scene.confirm(0)
        scene.confirm(0)
        x, y = scene.party_positions[1]
        scene.click(x, y, 1)
        self.assertEqual((temur["hp"], model.potions), (50, 2))
        scene.close()

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
        temur_label = next(item for item in self.app.canvas.find_withtag(scene.DYNAMIC)
                           if self.app.canvas.type(item) == "text"
                           and self.app.canvas.itemcget(item, "text") == "Temur")
        self.assertEqual(self.app.canvas.itemcget(temur_label, "fill"), "#ffe37e")
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
