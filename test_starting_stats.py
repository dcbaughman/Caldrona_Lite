import random
import unittest

from battle import BattleModel, ENEMIES
from stats import RETRI, TEMUR, grow, member


class GrowthTests(unittest.TestCase):
    def test_party_gains_stats_and_preserves_fainted_state(self):
        retri, temur = member("Retri", RETRI), member("Temur", TEMUR)
        temur["hp"] = 0
        grow(retri, 1, 3)
        grow(temur, 1, 3)
        self.assertEqual((retri["max_hp"], retri["strength"], retri["defense"]), (76, 10, 3))
        self.assertEqual((temur["max_hp"], temur["strength"], temur["hp"]), (102, 13, 0))

    def test_levels_improve_damage_against_same_enemy(self):
        low = member("Retri", RETRI)
        high = member("Retri", RETRI)
        grow(high, 1, 4)
        first = BattleModel(ENEMIES[0], party=[low], rng=random.Random(3))
        later = BattleModel(ENEMIES[0], party=[high], rng=random.Random(3), level=4)
        first.command("Attack")
        later.command("Attack")
        self.assertGreater(later.damage, first.damage)
        self.assertLess(first.damage, 20)
