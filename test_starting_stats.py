import unittest
from battle import ENEMIES
from stats import RETRI, TEMUR, member


class StartingStatsTests(unittest.TestCase):
    def test_party_and_enemies_match_supplied_values(self):
        retri, temur = member("Retri", RETRI), member("Temur", TEMUR)
        self.assertEqual((retri["hp"], retri["mp"], retri["strength"], retri["luck"]), (520, 12, 15, 18))
        self.assertEqual((temur["hp"], temur["mp"], temur["strength"], temur["defense"]), (1030, 33, 20, 15))
        bat, beetle = ENEMIES[1:]
        self.assertEqual((bat.hp, bat.mp, bat.strength, bat.agility, bat.evasion), (95, 15, 9, 11, 10))
        self.assertEqual((beetle.hp, beetle.mp, beetle.strength, beetle.magic_defense), (125, 10, 13, 120))
