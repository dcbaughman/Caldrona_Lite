"""Deterministic coverage for encounter gating and turn resolution."""
import random
import unittest
from unittest.mock import Mock

from battle import (BattleModel, EncounterMeter, ENEMIES, MAX_HP, SAFE_STEPS,
                    DEN_MOTHER, DEN_MOTHER_CHANCE, SHALEHORN, cave_encounter)


class BattleTests(unittest.TestCase):
    def test_rare_den_mother_is_a_strong_solo_encounter(self):
        rng = Mock()
        rng.random.return_value = DEN_MOTHER_CHANCE / 2
        self.assertEqual(cave_encounter(rng), [DEN_MOTHER])
        self.assertGreater(DEN_MOTHER.hp, max(enemy.hp for enemy in ENEMIES))
        self.assertLess(DEN_MOTHER.hp, SHALEHORN.hp)
        self.assertGreater(DEN_MOTHER.attack[0], max(enemy.attack[0] for enemy in ENEMIES))
        self.assertGreater(DEN_MOTHER.gold, max(enemy.gold for enemy in ENEMIES))
        rng.random.return_value = DEN_MOTHER_CHANCE
        rng.randint.return_value = 2
        rng.choice.return_value = ENEMIES[0]
        self.assertEqual(cave_encounter(rng), [ENEMIES[0], ENEMIES[0]])

    def test_potion_targets_another_member_and_cannot_revive(self):
        party = [{"name": "Retri", "hp": 60, "max_hp": 60},
                 {"name": "Temur", "hp": 20, "max_hp": 82},
                 {"name": "Mira", "hp": 0, "max_hp": 50}]
        model = BattleModel(ENEMIES[0], party=party)
        for target in (0, 2, -1, 99):
            self.assertFalse(model.command("Potion", target=target))
            self.assertEqual(model.potions, 3)
            self.assertFalse(model.pending_reply)
        self.assertTrue(model.command("Potion", target=1))
        self.assertEqual([p["hp"] for p in party], [60, 50, 0])
        self.assertEqual(model.potions, 2)
        self.assertTrue(model.pending_reply)

    def test_boss_potion_targets_another_party_member(self):
        from battle import SHALEHORN, ShalehornBattle
        party = [{"name": "Retri", "hp": 60, "max_hp": 60},
                 {"name": "Temur", "hp": 10, "max_hp": 82}]
        model = ShalehornBattle(SHALEHORN, party=party)
        model.buried = True
        self.assertTrue(model.command("Potion", target=1))
        self.assertEqual(party[1]["hp"], 40)
        self.assertEqual(model.potions, 2)

    def test_group_targets_and_rewards(self):
        model = BattleModel([ENEMIES[0], ENEMIES[1]], rng=random.Random(2))
        model.target = 1
        model.enemy_hp = 1
        model.command("Attack")
        self.assertEqual(model.health[1], 0)
        self.assertIsNone(model.outcome)
        self.assertEqual(model.gold_reward, ENEMIES[0].gold + ENEMIES[1].gold)
        model.reply()
        self.assertEqual(model.attacker, 0)
        self.assertGreater(model.damage, 0)

    def test_safe_steps_and_configured_probability(self):
        rng = Mock()
        rng.random.side_effect = [0.5, 0.079]
        meter = EncounterMeter(rng)
        for _ in range(SAFE_STEPS):
            self.assertFalse(meter.step())
        rng.random.assert_not_called()
        self.assertFalse(meter.step())
        self.assertTrue(meter.step())
        self.assertEqual(meter.steps_left, SAFE_STEPS)
        self.assertFalse(meter.step())

    def test_one_reply_per_command_and_no_reply_after_victory(self):
        for enemy in ENEMIES:
            model = BattleModel(enemy, rng=random.Random(3))
            while not model.outcome:
                self.assertTrue(model.command("Attack"))
                self.assertFalse(model.command("Attack"))
                before = model.hp
                model.reply()
                if model.outcome == "victory":
                    self.assertEqual(model.hp, before)
                after = model.hp
                model.reply()
                self.assertEqual(model.hp, after)
            self.assertEqual(model.outcome, "victory")
            self.assertEqual(model.enemy_hp, 0)

    def test_guard_potions_flee_and_defeat(self):
        rng = Mock()
        rng.randint.return_value = 6
        rng.random.side_effect = [0.9, 0.1]
        model = BattleModel(ENEMIES[0], rng=rng)
        self.assertFalse(model.command("Potion"))
        self.assertEqual(model.potions, 3)
        model.command("Guard")
        model.reply()
        self.assertEqual(model.hp, MAX_HP - 3)
        model.command("Potion")
        self.assertEqual(model.hp, MAX_HP)
        self.assertEqual(model.potions, 2)
        model.reply()
        self.assertEqual(model.hp, MAX_HP - 6)
        model.command("Flee")
        self.assertTrue(model.pending_reply)
        model.reply()
        model.command("Flee")
        self.assertEqual(model.outcome, "fled")
        hp = model.hp
        model.reply()
        self.assertEqual(model.hp, hp)
        model = BattleModel(ENEMIES[0], hp=1, potions=0, rng=rng)
        self.assertFalse(model.command("Potion"))
        model.command("Guard")
        model.reply()
        self.assertEqual((model.outcome, model.hp), ("defeat", 0))


if __name__ == "__main__":
    unittest.main()
