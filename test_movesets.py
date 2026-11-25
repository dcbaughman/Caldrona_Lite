"""movesets.md on Caleb's current roster (6 classes): 7-move kits at fixed levels, 4 Crescendos, unlock counters,
Retribution, and the Rinse / Purify cure split."""
from dataclasses import replace
import random
import tempfile
import unittest

from battle import BattleModel, ENEMIES
from classes import (BLUE_STONE, HOME_STONES, JOBS, NOKTAKORO, RIQIZAURKEIS, SENBRANKA,
                     STONE_PATHS, bind_job, current_job)
from crescendo import (LOADOUTS, MAX_CHARGE, UNLOCKS, equipped_crescendo, is_unlocked, progress,
                       unlocked_choices)
from research import KITS, LESSONS, PURIFY_CURES, RINSE_CURES, kit_for, lessons_for
from save_game import read_slot, validate, write_slot, SaveError
from statuses import AILMENTS, curable
from stats import RETRI, TEMUR, member

# (name, learn level) per class, in kit order, straight from the movesets.md tables.
SPEC_KITS = {
    "Seer": [("Foretell", 2), ("Mind Flare", 4), ("Starfall Omen", 5), ("Lunar Drop", 6),
             ("Forewarn", 7), ("Twist of Fate", 9), ("Prophecy", 12)],
    "Tidecaller": [("Rolling Tide", 2), ("Undertow", 3), ("Rinse", 4), ("Swell", 5), ("Ebb", 6),
                ("Sea Mist", 9), ("Spring Tide", 12)],
    "Weaver": [("Read the Strand", 7), ("Black Thread", 8), ("Onyx Lash", 9), ("Weft Snare", 11),
               ("Hush", 12), ("Tether Pact", 14), ("Closing Verse", 17)],
    "Sollers": [("Knife Flick", 1), ("Steal", 2), ("Smoke Spark", 3), ("Backstab", 4),
                ("Smoke Veil", 6), ("Venom Edge", 8), ("Sleight of Hand", 10)],
    RIQIZAURKEIS: [("Mourner's Veil", 7), ("Lid Shut", 8), ("Retribution", 10), ("Hollow Tithe", 11),
                   ("Grave Weight", 13), ("Ashen Hush", 15), ("Twin Reliquary", 17)],
    "Saint": [("Mend", 1), ("Vigil Strike", 1), ("Smite", 3), ("Sanctuary", 5), ("Purify", 7),
              ("Restoration", 8), ("Benediction", 10)],
}
SPEC_CRESCENDOS = {
    "Seer": ("Starbreak", "Clear Sky", "Starlit Shelter", "Constellation Sweep"),
    "Tidecaller": ("Flood Tide", "Riptide", "Slack Water", "Return Tide"),
    "Weaver": ("Onyx Sever", "Shadow Canopy", "Silken Reprieve", "Black Silk Storm"),
    "Sollers": ("Gilded Strike", "Lucky Recovery", "Curtain Call", "Knife Rain"),
    RIQIZAURKEIS: ("Lid Crack", "Mourning Bell", "Ashen Vespers", "Nox Sepulta"),
    "Saint": ("Dawn Chorus", "Radiant Verdict", "Sanctuary Bell", "Last Light"),
}
SPEC_THRESHOLDS = {"Seer": (10, 30, 60), "Tidecaller": (500, 1500, 3000),
                   "Weaver": (10, 30, 60), "Sollers": (50, 150, 300), RIQIZAURKEIS: (400, 1200, 2400),
                   "Saint": (5, 15, 30)}


class Sure:
    """status_rng stand-in: every chance lands."""
    def random(self): return 0.0
    def randrange(self, n): return 0


def hero(job, **extra):
    person = member("Retri", RETRI)
    person.update(job=job, mp=100, max_mp=100, hp=60, level=30, researched=[x.id for x in kit_for(job)])
    person.update(extra)
    return person


def model_for(party, foes=None, **kw):
    foes = foes or [replace(foe, hp=300) for foe in ENEMIES[:2]]
    model = BattleModel(foes, party=party, status_rng=Sure(), rng=random.Random(4), **kw)
    return model


class ClassRosterTests(unittest.TestCase):
    def test_kits_follow_calebs_roster_and_home_stones(self):
        # Caleb's roster: third blue class not added yet; Saint is the white-stone test class.
        self.assertEqual(STONE_PATHS[BLUE_STONE], ("Seer", "Tidecaller"))
        self.assertEqual(STONE_PATHS[NOKTAKORO], ("Weaver", "Sollers", RIQIZAURKEIS))
        self.assertEqual(STONE_PATHS[SENBRANKA], ("Saint",))
        self.assertEqual(set(JOBS), set(SPEC_KITS))
        self.assertEqual(set(KITS), set(JOBS))
        self.assertEqual(set(UNLOCKS), set(JOBS))
        for job in JOBS:
            self.assertTrue(bind_job(member("Retri", RETRI), job, HOME_STONES[job]))
            wrong = BLUE_STONE if HOME_STONES[job] != BLUE_STONE else NOKTAKORO
            self.assertFalse(bind_job(member("Retri", RETRI), job, wrong))

    def test_tidecaller_keeps_its_name(self):
        self.assertEqual(current_job({"job": "Tidecaller"}), "Tidecaller")
        self.assertEqual(current_job({"job": "Black Reliquary"}), RIQIZAURKEIS)

    def test_every_mastery_move_is_the_last_kit_move(self):
        for job, (_, _, mastery) in UNLOCKS.items():
            with self.subTest(job=job):
                self.assertEqual(kit_for(job)[-1].id, mastery)


class KitTests(unittest.TestCase):
    def test_every_class_has_exactly_its_seven_moves_at_fixed_levels(self):
        for job, spec in SPEC_KITS.items():
            with self.subTest(job=job):
                pool = lessons_for({"job": job, "researched": []})
                self.assertEqual(len(pool), 7)
                self.assertEqual([(x.name, x.level) for x in pool], spec)
                self.assertEqual(len(KITS[job]), 7)
                self.assertEqual(len({x.id for x in pool}), 7)

    def test_seer_drops_mist_ray_but_keeps_it_for_enemy_art(self):
        names = [x.name for x in lessons_for({"job": "Seer", "researched": []})]
        self.assertNotIn("Mist Ray", names)
        self.assertIn("seer_mist_ray", {x.id for x in LESSONS["Seer"]})

    def test_level_gate_uses_character_level(self):
        from research import research_status
        person = member("Retri", RETRI)
        person.update(job="Weaver", level=7, rp=20, researched=[], observations=[])
        strand, thread = lessons_for(person)[:2]
        self.assertEqual(research_status(person, strand, {}), "Ready")
        self.assertEqual(research_status(person, thread, {}), "Reach Lv 8")

    def test_every_kit_move_executes_with_two_allies(self):
        for job in SPEC_KITS:
            for lesson in kit_for(job):
                with self.subTest(job=job, move=lesson.id):
                    party = [hero(job), member("Temur", TEMUR)]
                    model = model_for(party)
                    if lesson.id == "weaver_closing_verse":
                        model.black_thread = (0, 1, 40)
                    target = (0, 1) if lesson.target == "two enemies" else 0
                    self.assertTrue(model.command("Ability", ability_id=lesson.id, target=target), model.message)
                    model.reply()


class CrescendoUnlockTests(unittest.TestCase):
    def test_four_crescendos_per_class_in_unlock_order(self):
        for job, names in SPEC_CRESCENDOS.items():
            self.assertEqual(tuple(move.name for move in LOADOUTS[job]), names)
            self.assertEqual(UNLOCKS[job][1], SPEC_THRESHOLDS[job])

    def test_c1_free_then_counter_tiers_and_c4_needs_mastery(self):
        for job, (c2, c3, c4) in SPEC_THRESHOLDS.items():
            with self.subTest(job=job):
                person = {"job": job, "researched": []}
                moves = LOADOUTS[job]
                self.assertEqual(unlocked_choices(person), moves[:1])
                person["crescendo_progress"] = c2 - 1
                self.assertEqual(unlocked_choices(person), moves[:1])
                person["crescendo_progress"] = c2
                self.assertEqual(unlocked_choices(person), moves[:2])
                person["crescendo_progress"] = c3
                self.assertEqual(unlocked_choices(person), moves[:3])
                person["crescendo_progress"] = c4 + 500
                self.assertEqual(unlocked_choices(person), moves[:3])  # mastery missing
                self.assertFalse(is_unlocked(person, moves[3]))
                person["researched"] = [UNLOCKS[job][2]]
                self.assertEqual(unlocked_choices(person), moves)

    def test_locked_choice_falls_back_and_cannot_fire(self):
        person = hero("Seer", crescendo_choice="constellation_sweep", crescendo_charge=MAX_CHARGE)
        self.assertEqual(equipped_crescendo(person).id, "starbreak")
        model = model_for([person])
        self.assertFalse(model.command("Crescendo", ability_id="constellation_sweep"))
        person["crescendo_progress"] = 60
        self.assertEqual(equipped_crescendo(person).id, "constellation_sweep")

    def test_counters_rise_from_their_own_feats(self):
        seer = hero("Seer")
        model = model_for([seer])
        model.command("Ability", ability_id="seer_foretell", target=0)
        self.assertEqual(progress(seer), 1)

        undifer = hero("Tidecaller", hp=10)
        model = model_for([undifer])
        model.command("Ability", ability_id="tidecaller_rinse", target=0)
        self.assertEqual(progress(undifer), 6 + undifer["magic"])

        sollers = hero("Sollers")
        model = model_for([sollers])
        model.command("Ability", ability_id="sollers_pilfer", target=0)
        self.assertEqual(progress(sollers), 5)

        weaver = hero("Weaver")
        model = model_for([weaver])
        model.command("Ability", ability_id="weaver_black_thread", target=(0, 1))
        model.pending_reply = False
        model.command("Ability", ability_id="weaver_onyx_lash", target=0)
        self.assertEqual(progress(weaver), 1)

        saint, temur = hero("Saint"), member("Temur", TEMUR)
        model = model_for([saint, temur])
        model.command("Ability", ability_id="saint_sanctuary", target=1)
        temur["hp"] = 10
        model.attacker = 0
        model._take_party_damage(1, 25 * (100 - model.wards[1]) // 100)  # a 25 hit after the ward
        self.assertEqual(progress(saint), 1)

    def test_other_classes_do_not_count(self):
        sollers = hero("Seer")
        model = model_for([sollers])
        model.command("Ability", ability_id="seer_mind_flare", target=0)
        self.assertEqual(progress(sollers), 0)


class SaveCounterTests(unittest.TestCase):
    def setUp(self):
        import test_battle_ui
        case = test_battle_ui.BattleIntegrationTests()
        case.setUp()
        self.addCleanup(case.tearDown)
        self.app = case.app

    def test_counter_round_trips_and_old_saves_default_to_zero(self):
        from save_game import capture
        self.app.party[0].update(job="Seer", crescendo_progress=37)
        state = capture(self.app)
        with tempfile.TemporaryDirectory() as folder:
            write_slot(folder, 1, state)
            loaded = read_slot(folder, 1)["state"]
        self.assertEqual(loaded["party"][0]["crescendo_progress"], 37)
        self.assertEqual(progress(loaded["party"][0]), 37)
        old = capture(self.app)
        old["party"][0].pop("crescendo_progress")
        self.assertIs(validate(old), old)
        self.assertEqual(progress(old["party"][0]), 0)
        old["party"][0]["crescendo_progress"] = -1
        with self.assertRaises(SaveError):
            validate(old)


class RetributionTests(unittest.TestCase):
    def _open(self, twin=False):
        caster = hero(RIQIZAURKEIS, magic=0, hp=500, max_hp=500)
        model = model_for([caster], [replace(foe, hp=400) for foe in ENEMIES])
        if twin:
            self.assertTrue(model.command("Ability", ability_id="reliquary_twin_reliquary"))
            model.pending_reply = False
        self.assertTrue(model.command("Ability", ability_id="reliquary_retribution"))
        return caster, model

    def test_costs_six_mp_releases_after_three_phases_with_remainder_to_highest_hp(self):
        caster, model = self._open()
        self.assertEqual(caster["mp"], 94)  # Caleb: 6 MP
        model.health = [400, 390, 400]
        model._take_party_damage(0, 20)  # stores 10 -> 10 x (1 + 0/100)
        for _ in range(3):
            for i in range(3):
                model._advance_reliquary(i)
        self.assertIsNone(model.reliquary)
        self.assertEqual(model.health, [396, 387, 397])  # 3 each, remainder 1 to a 400-HP foe
        self.assertEqual(progress(caster), 10)
        self.assertEqual(model.relic_cooldown[0], 2)
        model.pending_reply = False
        self.assertFalse(model.command("Ability", ability_id="reliquary_retribution"))
        model.kit_turn_start(0)
        model.kit_turn_start(0)
        self.assertTrue(model.command("Ability", ability_id="reliquary_retribution"))

    def test_twin_reliquary_stores_75_and_skips_cooldown_once_per_battle(self):
        caster, model = self._open(twin=True)
        self.assertEqual(model.reliquary.absorb_percent, 75)
        self.assertEqual(model._take_party_damage(0, 20), 5)
        for _ in range(3):
            for i in range(3):
                model._advance_reliquary(i)
        self.assertEqual(model.relic_cooldown.get(0, 0), 0)
        model.pending_reply = False
        self.assertFalse(model.command("Ability", ability_id="reliquary_twin_reliquary"))


    def test_stored_damage_is_lost_if_the_caster_falls_before_release(self):
        caster, model = self._open()
        model._take_party_damage(0, 40)  # stores 20
        self.assertEqual(model.reliquary.stored, 20)
        before = list(model.health)
        model._take_party_damage(0, 2000)
        self.assertEqual(caster["hp"], 0)
        self.assertIsNone(model.reliquary)
        for _ in range(3):
            for i in range(3):
                model._advance_reliquary(i)
        self.assertEqual(model.health, before)
        self.assertEqual(model.reliquary_release, {})
        self.assertEqual(progress(caster), 0)

    def test_old_saves_rename_return_the_wound(self):
        from research import rename_researched, researched_ids
        old = {"job": RIQIZAURKEIS, "researched": ["reliquary_mourners_veil", "reliquary_return_the_wound"]}
        self.assertIn("reliquary_retribution", researched_ids(old))
        rename_researched(old)
        self.assertEqual(old["researched"], ["reliquary_mourners_veil", "reliquary_retribution"])
        self.assertEqual(next(l.name for l in kit_for(RIQIZAURKEIS) if l.id == "reliquary_retribution"),
                         "Retribution")


class CalebNumbersTests(unittest.TestCase):
    def test_retribution_costs_his_six_mp_and_black_thread_echoes_forty_percent(self):
        retribution = next(x for x in kit_for(RIQIZAURKEIS) if x.id == "reliquary_retribution")
        thread = next(x for x in kit_for("Weaver") if x.id == "weaver_black_thread")
        self.assertEqual((retribution.mp, thread.power, thread.mp), (6, 40, 4))


class StatusCureTests(unittest.TestCase):
    def test_cure_lists_match_the_doc_and_skip_missing_statuses(self):
        self.assertEqual(set(curable(RINSE_CURES)), {"poison", "slow", "webbed", "bogged", "sinking", "frozen"})
        self.assertEqual(set(curable(PURIFY_CURES)), {"silence", "darkness", "frozen"})
        self.assertIn("bleed", RINSE_CURES)
        self.assertIn("curse", PURIFY_CURES)
        self.assertNotIn("bleed", AILMENTS)
        self.assertNotIn("curse", AILMENTS)

    def _afflicted(self, job):
        caster, ally = hero(job), member("Temur", TEMUR)
        ally["hp"] = 20
        model = model_for([caster, ally])
        for status in ("poison", "slow", "webbed", "bogged", "sinking", "silence", "darkness", "frozen"):
            model.statuses.apply(("party", 1), status)
        for status in ("poison", "webbed", "darkness"):  # the caster must still be able to cast
            model.statuses.apply(("party", 0), status)
        return caster, ally, model

    def test_rinse_one_ally_body_ailments_and_small_heal(self):
        caster, ally, model = self._afflicted("Tidecaller")
        rinse = next(x for x in kit_for("Tidecaller") if x.name == "Rinse")
        self.assertEqual((rinse.mp, rinse.target), (2, "single ally"))
        self.assertTrue(model.command("Ability", ability_id=rinse.id, target=1))
        self.assertEqual(caster["mp"], 98)
        self.assertEqual(ally["hp"], 20 + 6 + caster["magic"])
        self.assertEqual(set(model.statuses.for_actor(("party", 1))), {"silence", "darkness"})
        self.assertEqual(set(model.statuses.for_actor(("party", 0))), {"poison", "webbed", "darkness"})  # one ally only

    def test_purify_whole_party_mind_ailments_no_heal(self):
        caster, ally, model = self._afflicted("Saint")
        purify = next(x for x in kit_for("Saint") if x.name == "Purify")
        self.assertEqual((purify.mp, purify.target), (4, "party"))
        hp = (caster["hp"], ally["hp"])
        self.assertTrue(model.command("Ability", ability_id=purify.id))
        self.assertEqual(caster["mp"], 96)
        self.assertEqual((caster["hp"], ally["hp"]), hp)
        self.assertEqual(set(model.statuses.for_actor(("party", 1))), {"poison", "slow", "webbed", "bogged", "sinking"})
        self.assertEqual(set(model.statuses.for_actor(("party", 0))), {"poison", "webbed"})  # whole party

    def test_mend_still_cures_poison(self):
        caster, ally, model = self._afflicted("Saint")
        self.assertTrue(model.command("Ability", ability_id="saint_mend", target=1))
        self.assertFalse(model.statuses.has(("party", 1), "poison"))


class ScalingTests(unittest.TestCase):
    """Moves keep their movesets.md ratio to a normal Attack on Caleb's combat_math curve."""

    def _hit(self, job, move, level):
        from unittest.mock import Mock
        person = hero(job, level=level, strength=7 + level, hp=999, max_hp=999)
        person["researched"] = [move]
        rng = Mock()
        rng.randint.return_value = 256
        crit = Mock()
        crit.randint.return_value = 99  # never a crit
        foe = replace(ENEMIES[0], hp=5000)
        attack = BattleModel(foe, party=[person], rng=rng, crit_rng=crit)
        attack.command("Attack")
        model = BattleModel(foe, party=[person], rng=rng, crit_rng=crit, status_rng=Sure())
        self.assertTrue(model.command("Ability", ability_id=move), model.message)
        return attack.damage, model.damage

    def test_attack_multiplier_moves_hold_their_ratio_at_every_level(self):
        from research import ATTACK_MULTIPLIERS
        moves = {"sollers_knife_flick": "Sollers", "sollers_backstab": "Sollers",
                 "sollers_venom_edge": "Sollers", "saint_smite": "Saint"}
        self.assertEqual(set(moves), set(ATTACK_MULTIPLIERS))
        for move, job in moves.items():
            for level in (1, 10, 20, 30):
                with self.subTest(move=move, level=level):
                    attack, hit = self._hit(job, move, level)
                    self.assertLessEqual(abs(hit - ATTACK_MULTIPLIERS[move] * attack), 1 + attack * .05)

    def test_critical_is_one_and_a_half_times_everywhere(self):
        from combat_math import CRIT_MULTIPLIER, critical_damage
        import kit_effects
        self.assertEqual((CRIT_MULTIPLIER, kit_effects.CRIT), (1.5, 1.5))
        self.assertEqual([critical_damage(n) for n in (1, 2, 10, 11)], [2, 3, 15, 17])

    def test_backstab_on_a_marked_foe_crits_once(self):
        from unittest.mock import Mock
        person = hero("Sollers", level=20, strength=27, hp=999, max_hp=999)
        person["researched"] = ["sollers_backstab"]
        rng = Mock()
        rng.randint.return_value = 256
        crit = Mock()
        crit.randint.return_value = 0  # every roll would crit
        foe = replace(ENEMIES[0], hp=5000, luck=0)
        plain = BattleModel(foe, party=[person], rng=rng, crit_rng=crit, status_rng=Sure())
        plain.command("Ability", ability_id="sollers_backstab")
        marked = BattleModel(foe, party=[person], rng=rng, crit_rng=crit, status_rng=Sure())
        marked.marks[0] = 0
        marked.command("Ability", ability_id="sollers_backstab")
        self.assertEqual(marked.damage, plain.damage)  # both crit exactly once


class NewStatusTests(unittest.TestCase):
    def test_slow_reaches_the_turn_queue_and_expires(self):
        model = model_for([hero("Seer")])
        model.begin_ctb()
        model.ctb.current = ("party", 0)
        self.assertTrue(model._inflict(0, "slow", turns=3))
        self.assertEqual(model.ctb.status[("enemy", 0)], "slow")
        for _ in range(3):
            model.statuses.end_turn(("enemy", 0))
        model.kit_turn_end(("enemy", 0))
        self.assertIsNone(model.ctb.status.get(("enemy", 0)))


if __name__ == "__main__":
    unittest.main()
