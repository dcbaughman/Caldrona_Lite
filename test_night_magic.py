"""Stone binding and the first Noktakoro combat spells."""

from dataclasses import replace
import unittest

from battle import BattleModel, ENEMIES
from classes import RIQIZAURKEIS, SENBRANKA
from save_game import capture, validate
from grassland import SENBRANKA_TILE
from stats import RETRI, TEMUR, member
import test_battle_ui


class NightMagicTests(unittest.TestCase):
    def test_retribution_uses_three_enemy_phases_and_splits_the_shared_pool(self):
        caster = member("Retri", RETRI)
        caster.update(job=RIQIZAURKEIS, magic=32, hp=1000, max_hp=1000, mp=20, max_mp=20,
                      researched=["reliquary_retribution"])
        ally = member("Temur", TEMUR)
        ally.update(hp=1000, max_hp=1000)
        model = BattleModel([replace(foe, hp=400) for foe in ENEMIES], party=[caster, ally])
        self.assertTrue(model.command("Ability", ability_id="reliquary_retribution"))
        self.assertEqual(caster["mp"], 20 - 6)  # Caleb: Retribution stays at his 6 MP
        model.pending_reply = False
        self.assertFalse(model.command("Ability", ability_id="reliquary_retribution"))
        model.begin_ctb()

        def end_enemy_turn(index):
            model.ctb.current = ("enemy", index)
            model.ctb.completed += 1
            model.resolve_turn_end()

        for remaining, incoming in ((2, 200), (1, 200), (0, 100)):
            self.assertEqual(model._take_party_damage(0 if remaining != 1 else 1, incoming), incoming // 2)
            end_enemy_turn(0)
            end_enemy_turn(0)  # The fastest target going twice still counts once.
            end_enemy_turn(1)
            self.assertEqual(model.reliquary.phases, remaining + 1)
            end_enemy_turn(2)
        self.assertIsNone(model.reliquary)
        self.assertEqual(model.health, [290, 290, 290])
        self.assertEqual(model.reliquary_release, {0: 110, 1: 110, 2: 110})
        self.assertEqual((caster["hp"], ally["hp"]), (850, 900))

    def test_wards_apply_before_storage_and_the_pool_is_lost_with_its_caster(self):
        caster = member("Retri", RETRI)
        caster.update(hp=10, mp=10, job=RIQIZAURKEIS, researched=["reliquary_retribution"])
        ally = member("Temur", TEMUR)
        model = BattleModel(replace(ENEMIES[0], attack=(100, 100), hp=400), party=[caster, ally])
        self.assertTrue(model.command("Ability", ability_id="reliquary_retribution"))
        model.wards[0] = 50
        model.rng = type("HitsCaster", (), {"randrange": lambda self, _: 0,
                                           "randint": lambda self, low, high: low})()
        model.reply(0)
        # Caleb, 2026-11-25: if the caster falls before the release, the stored damage is lost.
        self.assertEqual(caster["hp"], 0)
        self.assertIsNone(model.reliquary)
        self.assertIn("24 stored damage is lost", model.message)  # ward applied before storage
        for _ in range(3):
            model._advance_reliquary(0)
        self.assertEqual(model.reliquary_release, {})

    def test_black_thread_only_echoes_one_single_target_spell(self):
        caster = member("Retri", RETRI)
        caster.update(job="Weaver", mp=12, researched=["weaver_black_thread", "weaver_silkbolt"])
        model = BattleModel([replace(foe, hp=100) for foe in ENEMIES], party=[caster])
        self.assertFalse(model.command("Ability", target=(0, 0), ability_id="weaver_black_thread"))
        self.assertTrue(model.command("Ability", target=(0, 1), ability_id="weaver_black_thread"))
        model.pending_reply = False
        self.assertTrue(model.command("Attack"))
        self.assertIsNotNone(model.black_thread)
        model.pending_reply = False
        before = model.health[:]
        self.assertTrue(model.command("Ability", ability_id="weaver_silkbolt"))
        self.assertEqual(model.health, [before[0] - 10, before[1] - 4, before[2]])  # Caleb: 40% echo
        self.assertIsNone(model.black_thread)

    def test_senbranka_can_be_used_at_its_overworld_tile(self):
        case = test_battle_ui.BattleIntegrationTests()
        case.setUp()
        self.addCleanup(case.tearDown)
        app = case.app
        app.grass_intro_seen = True
        app._change_area(True)
        x, y = SENBRANKA_TILE
        app.x, app.y, app.direction = (x - .5) * 16, (y + .5) * 16, "right"
        app._update_world(force=True)
        app._activate()
        self.assertEqual(app.astral_scene.stone, SENBRANKA)
        self.assertEqual(app.astral_scene.paths, ("Saint",))

    def test_legacy_reliquary_save_loads_under_the_new_name(self):
        case = test_battle_ui.BattleIntegrationTests()
        case.setUp()
        self.addCleanup(case.tearDown)
        app = case.app
        state = capture(app)
        state["party"][0].update(job="Black Reliquary", researched=["reliquary_return_the_wound"])
        app._load_journey(validate(state))
        self.assertEqual(app.party[0]["job"], RIQIZAURKEIS)
        self.assertEqual(app.party[0]["researched"], ["reliquary_retribution"])  # renamed on load

    def test_black_thread_prompts_for_two_distinct_battle_targets(self):
        case = test_battle_ui.BattleIntegrationTests()
        case.setUp()
        self.addCleanup(case.tearDown)
        scene = case.app.battle
        caster = member("Retri", RETRI)
        caster.update(job="Weaver", agility=80, researched=["weaver_black_thread"])
        scene.start(BattleModel(ENEMIES[:2], party=[caster]), 0)
        scene.selection = scene.COMMANDS.index("Magic")
        scene.confirm(0)
        scene.confirm(0)
        self.assertEqual(scene.phase, "target")
        scene.confirm(0)
        self.assertEqual((scene.link_first, scene.model.target), (0, 1))
        scene.confirm(0)
        self.assertEqual(scene.model.black_thread, (0, 1, 40))  # Caleb: 40% echo
        scene._draw_ailments(0)
        self.assertTrue(scene.canvas.find_withtag("night_magic"))
