"""Deterministic coverage for encounter gating and turn resolution."""
from dataclasses import replace
import random
import unittest
from unittest.mock import Mock

from battle import (BattleModel, EncounterMeter, ENEMIES, MAX_HP, SAFE_STEPS,
                    DEN_MOTHER, SHALEHORN, cave_encounter)
from combat_math import critical_chance, physical_damage
from stats import RETRI, member


class BattleTests(unittest.TestCase):
    def test_physical_damage_curve_and_variance(self):
        self.assertEqual(physical_damage(8, 1, 256), 8)
        self.assertEqual(physical_damage(11, 1, 256), 11)
        self.assertEqual(physical_damage(20, 4, 240), 31)
        self.assertEqual(physical_damage(20, 4, 271), 35)
        self.assertEqual(physical_damage(20, 255, 256), 1)
        self.assertEqual(critical_chance(4, 10, 3), 0)
        self.assertEqual(critical_chance(8, 6, 3), 5)
        self.assertEqual(critical_chance(110, 6, 3), 100)

    def test_critical_doubles_a_weapon_hit_before_the_flat_mark_bonus(self):
        foe = replace(ENEMIES[0], hp=200)
        damage_rng = Mock()
        damage_rng.randint.return_value = 256
        crit_rng = Mock()
        crit_rng.randint.return_value = 5
        for action, ability_id in (("Attack", None), ("Ability", "unbound_quick_cut")):
            hits = []
            for charm in (False, True):
                actor = member("Retri", RETRI)
                actor["equipment"] = {"weapon": "training_sword"}
                if charm:
                    actor["equipment"]["accessory"] = "lucky_charm"
                actor["researched"] = ["unbound_quick_cut"]
                model = BattleModel(foe, party=[actor], rng=damage_rng, crit_rng=crit_rng)
                model.marks[0] = 5
                self.assertTrue(model.command(action, ability_id=ability_id))
                self.assertEqual(bool(model.critical_hits), charm)
                self.assertEqual("Critical hit!" in model.message, charm)
                hits.append(model.damage)
            self.assertEqual(hits[1], (hits[0] - 5) * 2 + 5)

    def test_luck_reduces_enemy_crit_rate_and_guard_still_mitigates_damage(self):
        foe = replace(ENEMIES[0], luck=12, attack=(20, 20))
        crit_rng = Mock()
        crit_rng.randint.return_value = 3
        for charm, expected in ((False, 16), (True, 8)):
            actor = member("Retri", RETRI)
            if charm:
                actor["equipment"] = {"accessory": "lucky_charm"}
            model = BattleModel(foe, party=[actor], crit_rng=crit_rng)
            model.command("Guard")
            model.reply()
            self.assertEqual(model.hits, {0: expected})
            self.assertEqual(model.critical_hits, set() if charm else {("party", 0)})

    def test_magic_and_missed_attacks_skip_the_crit_roll(self):
        actor = member("Retri", RETRI)
        actor.update(job="Seer", luck=100, researched=["seer_gale"])
        crit_rng = Mock()
        status_rng = Mock()
        status_rng.random.return_value = .99
        model = BattleModel(ENEMIES[0], party=[actor], crit_rng=crit_rng, status_rng=status_rng)
        model.statuses.apply(("party", 0), "darkness")
        self.assertTrue(model.command("Attack"))
        self.assertEqual(model.damage, 0)
        model.pending_reply = False
        self.assertTrue(model.command("Ability", ability_id="seer_gale"))
        self.assertGreater(model.damage, 0)
        self.assertFalse(model.critical_hits)
        crit_rng.randint.assert_not_called()

    def test_den_mother_is_reserved_for_her_lair(self):
        self.assertGreater(DEN_MOTHER.hp, max(enemy.hp for enemy in ENEMIES))
        self.assertGreater(DEN_MOTHER.hp, SHALEHORN.hp)
        self.assertGreater(DEN_MOTHER.attack[0], max(enemy.attack[0] for enemy in ENEMIES))
        self.assertGreater(DEN_MOTHER.gold, max(enemy.gold for enemy in ENEMIES))
        rng = Mock()
        rng.randint.return_value = 2
        rng.choice.return_value = ENEMIES[0]
        self.assertEqual(cave_encounter(rng), [ENEMIES[0], ENEMIES[0]])
        rng.choice.assert_called_with(ENEMIES)

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
