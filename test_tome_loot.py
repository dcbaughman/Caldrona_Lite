"""Progression and loot checks for the in-game research flow."""
from unittest import TestCase
from unittest.mock import Mock
import time

from abilities import learned_abilities
from battle import BattleModel, DEN_MOTHER, ENEMIES, SHALEHORN, ShalehornBattle
from classes import RIQIZAURKEIS
from loot import PROFILES, roll_kill, roll_steal
from research import (ECHO_ANALECT, LESSONS, initialize_research, lessons_for,
                      research_lesson, research_status)
from stats import RETRI, member
import test_battle_ui


def rng_with(*rolls):
    rng = Mock()
    rng.random.side_effect = rolls
    return rng


class ResearchRulesTests(TestCase):
    def test_research_gates_and_lesson_execution(self):
        self.assertEqual({path: len(lessons_for({"job": path})) for path in LESSONS},
                         {"Unbound": 15, "Seer": 7, "Sollers": 7, "Saint": 7, "Weaver": 7,
                          RIQIZAURKEIS: 7, "Tidecaller": 7})
        retri = member("Retri", RETRI)
        initialize_research(retri)
        quick_cut, hard_edge = lessons_for(retri)[:2]
        self.assertEqual(learned_abilities(retri), ())
        self.assertEqual(research_status(retri, hard_edge, {}), "Reach Lv 3")
        self.assertEqual(research_lesson(retri, quick_cut, {}), "Learned Quick Cut.")
        self.assertEqual(research_lesson(retri, quick_cut, {}), "Learned")
        self.assertEqual(retri["rp"], 1)
        damage_rng = Mock()
        damage_rng.randint.return_value = 256
        crit_rng = Mock()
        crit_rng.randint.return_value = 99
        model = BattleModel(ENEMIES[0], party=[retri], rng=damage_rng, crit_rng=crit_rng)
        self.assertTrue(model.command("Ability", ability_id=quick_cut.id))
        self.assertEqual((retri["mp"], model.enemy_hp), (7, 11))
        retri.update(level=5, rp=5)
        spark = next(lesson for lesson in lessons_for(retri) if lesson.id == "unbound_spark")
        self.assertEqual(research_status(retri, spark, {}), "Find Echo Analect")
        self.assertEqual(research_lesson(retri, spark, {ECHO_ANALECT: 1}), "Learned Spark.")
        echo = next(lesson for lesson in lessons_for(retri) if lesson.id == "unbound_quarry_echo")
        self.assertEqual(research_status(retri, echo, {}), "Witness Quarry Tremor")
        boss = ShalehornBattle(SHALEHORN, party=[retri])
        boss.move_index, boss.pending_reply = 1, True
        boss.reply()
        self.assertEqual(research_status(retri, echo, {}), "Ready")

    def test_independent_slots_fixed_drop_and_equipped_steal(self):
        self.assertTrue(all(len(profile.drops) == 4 for profile in PROFILES.values()))
        self.assertEqual(sum(roll_kill(ENEMIES[0].loot, rng_with(0, 0, 0, 0)).values()), 4)
        self.assertEqual(roll_kill(SHALEHORN.loot, rng_with(.99, .99, .99, .99)),
                         {"shalehorn_crook": 1})
        self.assertEqual(DEN_MOTHER.loot.rank, "Boss")
        self.assertEqual(roll_kill(DEN_MOTHER.loot, rng_with(.99, .99, .99, .99)),
                         {"broodguard_seal": 1, "silkweave_coat": 1})
        self.assertEqual(roll_steal(ENEMIES[0].loot, rng_with(.60, .20, .05)), {})
        retri = member("Retri", RETRI)
        initialize_research(retri)
        retri.update(job="Sollers", level=2, equipment={"weapon": "pickpocket_dirk"})
        steal = next(lesson for lesson in lessons_for(retri) if lesson.effect == "steal")
        research_lesson(retri, steal, {})
        model = BattleModel(ENEMIES[0], party=[retri], loot_rng=rng_with(.60, .20, .05))
        self.assertTrue(model.command("Ability", ability_id=steal.id))
        self.assertEqual(sum(model.stolen.values()), 3)
        model.pending_reply = False
        self.assertFalse(model.command("Ability", ability_id=steal.id))
        self.assertEqual(retri["mp"], 7)


class ResearchFlowTests(TestCase):
    def test_tome_loot_and_bazaar_through_game(self):
        case = test_battle_ui.BattleIntegrationTests()
        case.setUp()
        self.addCleanup(case.tearDown)
        app = case.app
        app.game_menu.open()
        app.game_menu.selection = 1
        app._activate()
        self.assertEqual(app.screen, "tome")
        app._activate()
        app._activate()
        self.assertIn("unbound_quick_cut", app.party[0]["researched"])
        app._back()
        app._back()
        app.game_menu.close()
        model = BattleModel(ENEMIES[1], party=app.party, loot_rng=rng_with(0, 0, 0, 0))
        app.battle.start(model, time.monotonic())
        model.enemy_hp = 1
        model.command("Attack")
        app._finish_battle("victory")
        self.assertEqual(app.analects[ECHO_ANALECT], 1)
        self.assertEqual(app.party[0]["rp"], 2)
        self.assertEqual(app.materials["Echo Wing"], 1)
        app._open_merren_shop()
        app.materials.update({"Spider Silk": 3, "Shale Chip": 2})
        app._change_shop_tab(1)
        for index, count in ((0, 3), (2, 2)):
            app.shop_selection = index
            for _ in range(count):
                app._activate()
        app._change_shop_tab(1)
        self.assertTrue(app._bazaar_unlocked("field_guard"))
        app.gold = 24
        app._activate()
        self.assertEqual((app.gear_inventory["field_guard"], app.gold), (1, 0))
        app._activate()
        self.assertEqual(app.gear_inventory["field_guard"], 1)
