"""Deterministic coverage for encounter gating and turn resolution."""
import random
import unittest
from unittest.mock import Mock

from battle import BattleModel, EncounterMeter, ENEMIES, MAX_HP, SAFE_STEPS


class BattleTests(unittest.TestCase):
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
