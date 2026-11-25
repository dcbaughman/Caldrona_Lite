"""Regression tests for Crescendo balance, battle UI, and save compatibility."""
import random
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from battle import BattleModel, ENEMIES, SHALEHORN, ShalehornBattle
from classes import RIQIZAURKEIS, bind_job
from crescendo import LOADOUTS, MAX_CHARGE, UNLOCKS, charge, choices_for, equipped_crescendo
from crescendo_art import CUES, _PLACEHOLDER_CUES
from game_menu import CRESCENDO_PAGE
from save_game import SaveError, capture, validate
from stats import RETRI, TEMUR, member
import test_battle_ui


class CrescendoTests(unittest.TestCase):
    def test_gilded_strike_scales_above_a_normal_hit_at_level_twenty(self):
        from dataclasses import replace

        hero = member("Retri", RETRI)
        hero.update(job="Sollers", level=20, strength=36, crescendo_charge=MAX_CHARGE)
        foe = replace(ENEMIES[0], hp=1000, luck=99)
        rng = Mock()
        rng.randint.return_value = 256
        normal = BattleModel(foe, party=[hero], rng=rng)
        self.assertTrue(normal.command("Attack"))
        ultimate = BattleModel(foe, party=[hero], rng=rng)
        self.assertTrue(ultimate.command("Crescendo", ability_id="gilded_strike"))
        self.assertGreater(ultimate.damage, normal.damage * 1.6)

    def test_every_path_has_four_options_and_working_default(self):
        self.assertEqual(set(CUES), {move.id for options in LOADOUTS.values() for move in options})
        # Drawn cues keep distinct choreography; the movesets placeholders reuse one.
        drawn = [cue for name, cue in CUES.items() if name not in _PLACEHOLDER_CUES]
        self.assertEqual(len({cue.draw for cue in drawn}), len(drawn))
        for job, options in LOADOUTS.items():
            self.assertEqual(len(options), 4)
            for move in options:
                with self.subTest(job=job, move=move.id):
                    hero = member("Retri", RETRI)
                    hero.update(job=job, hp=20, mp=0, crescendo_charge=MAX_CHARGE)
                    ally = member("Temur", TEMUR)
                    ally.update(hp=0 if move.effect == "revive" else 20, mp=0)
                    self.assertEqual(equipped_crescendo(hero), options[0])
                    if job in UNLOCKS:  # open every tier: C2-C4 need the counter and mastery
                        hero.update(crescendo_progress=10**6, researched=[UNLOCKS[job][2]])
                    hero["crescendo_choice"] = move.id
                    model = BattleModel(ENEMIES[:2], party=[hero, ally], rng=random.Random(1))
                    self.assertTrue(model.command("Crescendo", ability_id=move.id))
                    self.assertEqual(charge(hero), 0)
                    self.assertEqual(model.action_rank, move.action_rank)
                    cue = CUES[move.id]
                    self.assertGreaterEqual(cue.duration_ms, 2000)
                    self.assertLess(cue.contact_ms, cue.duration_ms - 700)
                    if move.target == "all enemies" and move.effect != "field":
                        self.assertEqual(set(model.crescendo_hits), {0, 1})

    def test_charge_comes_from_real_actions_and_survived_hits(self):
        hero = member("Retri", RETRI)
        rng = Mock()
        rng.randint.return_value = 7
        model = BattleModel(ENEMIES[0], party=[hero], rng=rng)
        self.assertFalse(model.command("Crescendo"))
        self.assertEqual(charge(hero), 0)
        self.assertTrue(model.command("Attack"))
        self.assertEqual(charge(hero), 16)
        model.reply()
        self.assertEqual(charge(hero), 26)
        model.reply()
        self.assertEqual(charge(hero), 26)
        self.assertTrue(model.command("Guard"))
        self.assertEqual(charge(hero), 26)
        hero["hp"] = 1
        model.reply()
        self.assertEqual(hero["hp"], 0)
        self.assertEqual(charge(hero), 0)

        hero = member("Retri", RETRI)
        hero.update(hp=30, researched=["unbound_first_aid"])
        model = BattleModel(ENEMIES[0], party=[hero])
        self.assertTrue(model.command("Ability", ability_id="unbound_first_aid"))
        self.assertEqual(charge(hero), 12)

    def test_unreachable_target_and_empty_revival_preserve_charge(self):
        hero = member("Retri", RETRI)
        hero["crescendo_charge"] = 100
        model = ShalehornBattle(SHALEHORN, party=[hero])
        model.buried = True
        self.assertFalse(model.command("Crescendo"))
        self.assertEqual(charge(hero), 100)
        hero["crescendo_choice"] = "steady_line"
        self.assertTrue(model.command("Crescendo"))
        self.assertEqual(charge(hero), 0)

        hero = member("Retri", RETRI)
        hero.update(job="Saint", crescendo_choice="last_light", crescendo_charge=100,
                    crescendo_progress=30, researched=["saint_benediction"])
        model = BattleModel(ENEMIES[0], party=[hero])
        self.assertFalse(model.command("Crescendo"))
        self.assertEqual(charge(hero), 100)

    def test_binding_selects_new_class_default_and_keeps_charge(self):
        hero = member("Retri", RETRI)
        hero.update(crescendo_choice="steady_line", crescendo_charge=50)
        self.assertTrue(bind_job(hero, "Seer"))
        self.assertEqual(equipped_crescendo(hero).id, "starbreak")
        self.assertEqual(charge(hero), 50)


class CrescendoIntegrationTests(unittest.TestCase):
    def setUp(self):
        case = test_battle_ui.BattleIntegrationTests()
        case.setUp()
        self.addCleanup(case.tearDown)
        self.app = case.app

    def test_title_lab_plays_and_scrubs_all_crescendos(self):
        app = self.app
        saved = capture(app)
        app._draw_menu()

        def key(name):
            app._key_down(SimpleNamespace(keysym=name))
            app._key_up(SimpleNamespace(keysym=name))

        key("t")
        key("e")
        with patch.object(app, "_controller_buttons", return_value={"member_next"}):
            app._tick()
            app.root.after_cancel(app.tick_after)
        self.assertEqual(app.lab_tab, 2)
        lab = app.crescendo_lab
        seen = []
        for job, moves in LOADOUTS.items():
            for move in moves:
                with self.subTest(move=move.id):
                    scene = lab.scene
                    self.assertIsNot(scene, app.battle)
                    self.assertIn(f"{job} · {move.name}", app.canvas.itemcget(lab.title, "text"))
                    fx = scene.crescendo_fx
                    self.assertIs(fx.cue, CUES[move.id])
                    self.assertEqual(scene.model.party[0]["crescendo_choice"], move.id)
                    self.assertEqual(len(scene.model.crescendo_hits),
                                     0 if move.effect == "field" else
                                     {"party": 0, "single enemy": 1, "all enemies": 2}[move.target])
                    if move.effect == "revive":
                        self.assertTrue(scene.party_fainted[1])
                    stage = set()
                    bright_backdrop = scene.glow_frames[0]
                    self.assertIs(fx.backdrop, bright_backdrop)
                    for _ in range(lab.last_frame):
                        lab.step(1)
                        if 260 <= lab.rendered * 1000 / lab.FPS <= 420:
                            self.assertIsNot(fx.backdrop, bright_backdrop)
                        stage.add(len(app.canvas.find_withtag(fx.TAG)))
                    self.assertGreater(len(stage), 5)
                    self.assertIs(fx.backdrop, bright_backdrop)
                    self.assertEqual(scene._camera_offset, (0, 0))
                    self.assertNotIn(True, scene.party_fainted)
                    if move.effect == "revive":
                        lab.step(-lab.last_frame)
                        self.assertTrue(scene.party_fainted[1])
                    seen.append(move.id)
                    key("right")
        self.assertEqual(len(seen), sum(map(len, LOADOUTS.values())))
        self.assertEqual(lab.index, 0)
        key("down")
        self.assertEqual((lab.rendered, lab.paused), (1, True))
        key("up")
        self.assertEqual(lab.rendered, 0)
        lab.step(3)
        key("return")
        self.assertEqual((lab.rendered, lab.paused), (0, False))
        lab.update(lab.started + 4.5 / lab.FPS)
        self.assertEqual(lab.rendered, 4)
        key("escape")
        self.assertEqual(app.screen, "menu")
        self.assertEqual(capture(app), saved)

    def test_loadout_menu_and_full_meter_activate_through_battle(self):
        app = self.app
        hero = app.party[0]
        app._recruit(member("Temur", TEMUR))
        hero["crescendo_charge"] = 100
        menu = app.game_menu
        menu.open()
        menu.selection = CRESCENDO_PAGE
        menu.activate()
        menu.navigate("down", 1)
        menu.activate()
        self.assertEqual(equipped_crescendo(hero).id, "quarry_break")
        menu.change_equipment_member(1)
        self.assertEqual(menu.crescendo_index, 0)
        self.assertEqual(equipped_crescendo(app.party[1]).id, "rising_edge")
        menu.close()
        app._load_journey(validate(capture(app)))
        self.assertEqual(equipped_crescendo(app.party[0]).id, "quarry_break")
        self.assertEqual(charge(app.party[0]), 100)
        hero = app.party[0]
        hero["agility"] = 40
        scene = app.battle
        scene.start(BattleModel(ENEMIES[:2], party=[hero]), 0)
        badge = app.canvas.find_withtag("battle_crescendo_badge")
        self.assertEqual([app.canvas.itemcget(i, "text") for i in badge if app.canvas.type(i) == "text"],
                         ["CRESCENDO"])
        self.assertTrue(all(app.canvas.type(i) == "rectangle" for i in app.canvas.find_withtag("battle_crescendo")))
        scene.selection = scene.COMMANDS.index("Guard")
        app.screen = "battle"
        with patch.object(app, "_dpad", return_value={"left"}):
            app._tick()
            app.root.after_cancel(app.tick_after)
        self.assertEqual(scene.ability_page, "Crescendo")
        self.assertEqual(scene._menu_abilities(), (choices_for(hero)[1],))
        self.assertEqual(scene._preview_rank(), choices_for(hero)[1].action_rank)
        scene.confirm(1.1)
        self.assertEqual(scene.phase, "ability_fx")
        self.assertEqual(scene.model.action_rank, 5)
        self.assertEqual(charge(hero), 0)
        self.assertFalse(app.canvas.find_withtag("battle_crescendo_badge"))
        self.assertEqual(set(scene.model.crescendo_hits), {0, 1})
        def hud_text():
            return [app.canvas.itemcget(i, "text") for i in app.canvas.find_withtag("battle_ui")
                    if app.canvas.type(i) == "text"]

        scene.update(scene.phase_at + .4)
        self.assertIsNot(scene.crescendo_fx.backdrop, scene.glow_frames[scene.glow_index])
        self.assertTrue(app.canvas.find_withtag(scene.crescendo_fx.TAG))
        self.assertIn(f"HP {ENEMIES[0].hp}/{ENEMIES[0].hp}", hud_text())
        impact_time = scene.phase_at + (scene.crescendo_fx.cue.contact_ms + 100) / 1000
        scene.update(impact_time)
        self.assertEqual(scene.phase, "ability_fx")
        self.assertIn(f"HP {scene.model.enemy_hp}/{ENEMIES[0].hp}", hud_text())
        numbers = [app.canvas.itemcget(i, "text") for i in app.canvas.find_withtag(scene.crescendo_fx.TAG)
                   if app.canvas.type(i) == "text"]
        for damage in scene.model.crescendo_hits.values():
            self.assertIn(str(damage), numbers)
        end = scene.phase_at + scene.ability_duration_ms / 1000 + .02
        scene.update(end)
        self.assertEqual(scene.phase, "hero_action")
        self.assertEqual(scene._camera_offset, (0, 0))
        self.assertFalse(app.canvas.find_withtag(scene.crescendo_fx.TAG))
        self.assertEqual(scene.model.ctb.current, ("party", 0))
        scene.update(end + .7)
        self.assertNotEqual(scene.phase, "hero_action")

    def test_badge_follows_current_turn_and_targeting_can_be_cancelled(self):
        scene, canvas = self.app.battle, self.app.canvas
        hero = member("Retri", RETRI)
        hero.update(agility=40, crescendo_charge=60, researched=["unbound_quick_cut"])
        ally = member("Temur", TEMUR)
        ally["crescendo_charge"] = MAX_CHARGE
        model = BattleModel(ENEMIES[:2], party=[hero, ally])
        scene.start(model, 0)

        def has_badge():
            return bool(canvas.find_withtag("battle_crescendo_badge"))

        def active_row():
            return [canvas.coords(item)[1] for item in canvas.find_withtag("battle_active_party_row")]

        self.assertFalse(has_badge())
        self.assertEqual(active_row(), [canvas._value(405)] * 2)
        scene.navigate("left", 1)
        self.assertEqual(scene.COMMANDS[scene.selection], "Guard")
        hero["crescendo_charge"] = MAX_CHARGE
        scene.draw_status()
        self.assertTrue(has_badge())
        self.assertEqual([move.id for move in scene._menu_abilities()], ["unbound_quick_cut"])
        scene.navigate(None, 1.1)
        scene.navigate("left", 1.2)
        scene.navigate("left", 1.6)
        self.assertEqual(scene.selection, 0)
        scene.confirm(2)
        self.assertEqual(scene.phase, "target")
        self.assertFalse(has_badge())
        self.assertEqual(charge(hero), MAX_CHARGE)
        scene.navigate("right", 2.05)
        self.assertEqual(scene.model.target, 1)
        scene.back()
        self.assertEqual(scene.ability_page, "Crescendo")
        self.assertTrue(has_badge())
        scene.navigate(None, 2.08)
        scene.navigate("right", 2.1)
        self.assertFalse(scene.ability_menu)
        self.assertEqual(scene.COMMANDS[scene.selection], "Guard")
        x, y, _, _ = scene.CRESCENDO_BADGE
        scene.click(x+20, y+7, 2.2)
        self.assertEqual(scene._menu_abilities(), (equipped_crescendo(hero),))
        scene.confirm(2.3)
        scene.confirm(2.4)
        self.assertEqual(scene.phase, "ability_fx")
        self.assertEqual(charge(hero), 0)
        self.assertEqual(charge(ally), MAX_CHARGE)
        self.assertFalse(has_badge())

        scene.close()
        scene.start(BattleModel(ENEMIES[0], party=[hero, ally]), 3)
        scene.model.ctb.current = ("enemy", 0)
        scene._begin_ctb_actor(3)
        scene.draw_status()
        self.assertFalse(has_badge())
        self.assertEqual(active_row(), [])
        scene.model.ctb.current = ("party", 1)
        scene.model._prepare_ctb_actor()
        scene._begin_ctb_actor(4)
        scene.draw_status()
        self.assertTrue(has_badge())
        self.assertEqual(active_row(), [canvas._value(443)] * 2)

    def test_old_saves_get_default_and_invalid_meter_is_rejected(self):
        state = capture(self.app)
        self.assertEqual(charge(validate(state)["party"][0]), 0)
        self.assertEqual(equipped_crescendo(state["party"][0]).id, "rising_edge")
        state["party"][0]["crescendo_charge"] = 101
        with self.assertRaises(SaveError):
            validate(state)
        state["party"][0]["crescendo_charge"] = 100
        state["party"][0]["crescendo_choice"] = "starbreak"
        with self.assertRaises(SaveError):
            validate(state)
