import random
import unittest

from battle import EmberWyvernBattle
from stats import RETRI, TEMUR, member


class EmberWyvernTests(unittest.TestCase):
    def setUp(self):
        self.retri = member("Retri", RETRI)
        self.temur = member("Temur", TEMUR)
        self.temur["equipment"]["armor"] = "cinder_coat"
        self.model = EmberWyvernBattle(party=[self.retri, self.temur], rng=random.Random(0),
                                       crit_rng=random.Random(2), status_rng=random.Random(1))
        self.model.begin_ctb()

    def enemy_action(self):
        self.model.ctb.current = ("enemy", 0)
        self.model.pending_reply = True
        self.model.reply(0)
        self.model.resolve_turn_end()
        self.model.ctb.completed += 1
        return self.model.last_move

    def test_bite_splits_damage_and_can_sunder_for_two_target_turns(self):
        model = EmberWyvernBattle(party=[self.temur], rng=random.Random(0),
                                  crit_rng=random.Random(2), status_rng=random.Random(1))
        model.pending_reply = True
        model.reply()
        self.assertEqual(model.last_move, "bite")
        # Seed 0 rolls 17. Physical damage is 9 minus 5 DEF. The coat halves 8 fire damage.
        self.assertEqual(model.hits, {0: 8})
        key = "party", 0
        self.assertEqual(model.statuses.for_actor(key)["sundered"], 2)
        model.statuses.end_turn(key)
        self.assertTrue(model.statuses.has(key, "sundered"))
        model.statuses.end_turn(key)
        self.assertFalse(model.statuses.has(key, "sundered"))

    def test_breath_waits_for_both_allies_and_uses_guard_and_coat(self):
        model = self.model
        model.enemy_hp = 80
        self.assertTrue(model.advance_phase())
        self.assertEqual([self.enemy_action() for _ in range(3)], ["bite", "bite", "inhale"])
        self.assertIn("inhales deeply", model.message)
        model.ctb.current = ("party", 1)
        model.actor = 1
        self.assertTrue(model.command("Guard"))
        model.resolve_turn_end()
        model.ctb.completed += 1
        before = [self.retri["hp"], self.temur["hp"]]
        self.assertEqual(self.enemy_action(), "inhale")
        self.assertEqual([self.retri["hp"], self.temur["hp"]], before)
        model.ctb.current = ("party", 0)
        model.resolve_turn_end()
        model.ctb.completed += 1
        self.assertEqual(self.enemy_action(), "breath")
        self.assertEqual(set(model.hits), {0, 1})
        self.assertGreaterEqual(model.hits[0], 10)
        self.assertEqual(model.hits[1], model.hits[0] // 4)

    def test_scorch_ticks_once_per_acting_ally_and_the_extra_attack_power_expires(self):
        model = self.model
        self.assertFalse(model.advance_phase())
        model.enemy_hp = 40
        self.assertTrue(model.advance_phase())
        self.assertTrue(model.advance_phase())
        self.assertEqual((model.enemy_element_percent("fire"), model.enemy_element_percent("water"),
                          model.enemy_element_percent("ice")), (50, 150, 150))
        for index, loss in ((0, 4), (1, 3)):
            key = model.ctb.current = ("party", index)
            before = model.party[index]["hp"]
            self.assertEqual(model.resolve_turn_end(), [(key, loss)])
            self.assertEqual(model.resolve_turn_end(), [])
            self.assertEqual(model.party[index]["hp"], before - loss)
            model.ctb.completed += 1
        self.assertEqual(model.heat_turns, 5)
        for expected in reversed(range(5)):
            model.ctb.current = ("enemy", 0)
            self.assertGreaterEqual(model._attack_roll(), 21)
            model.resolve_turn_end()
            model.ctb.completed += 1
            self.assertEqual(model.heat_turns, expected)
        self.assertLessEqual(model._attack_roll(), 18)
        model.ctb.current = ("party", 0)
        self.assertEqual(model.resolve_turn_end(), [(("party", 0), 4)])

    def test_water_and_ice_spells_use_the_exposed_body_weakness(self):
        for job, ability in (("Tidecaller", "tidecaller_undertow"), ("Seer", "seer_mist_ray")):
            with self.subTest(ability=ability):
                def cast(stage):
                    caster = member("Retri", RETRI)
                    caster.update(job=job, mp=20, researched=[ability])
                    model = EmberWyvernBattle(party=[caster])
                    model.stage = stage
                    self.assertTrue(model.command("Ability", ability_id=ability))
                    return model.damage, model.message

                normal, _ = cast(2)
                hot, message = cast(3)
                self.assertEqual(hot, (3 * normal + 1) // 2)
                self.assertIn("weak", message.lower())

    def test_tidecallers_riptide_uses_the_water_weakness(self):
        caster = member("Retri", RETRI)
        caster.update(job="Tidecaller", crescendo_choice="riptide", crescendo_charge=100, crescendo_progress=500)
        model = EmberWyvernBattle(party=[caster])
        model.stage = 3
        self.assertTrue(model.command("Crescendo"))
        self.assertEqual(model.damage, 18)
        self.assertIn("weak to water", model.message.lower())
