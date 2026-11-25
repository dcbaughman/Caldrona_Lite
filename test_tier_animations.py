"""Tier growth, readable battle UI, impact timing, and camera restoration."""
import unittest
from abilities import lesson_variant
from research import LESSONS
from battle import BattleModel, ENEMIES
from stats import RETRI, member
import test_battle_ui

class TierAnimationTests(unittest.TestCase):
    def test_strength_grows_across_tiers(self):
        lessons={x.id:x for x in LESSONS['Seer']}
        variants=[lesson_variant(lessons['seer_'+name],{'job':'Seer'}) for name in ('gale','echo_glass','dream_tide','astral_flood')]
        self.assertEqual([v.tier for v in variants],[1,2,3,4])
        self.assertEqual([v.camera_shake for v in variants],[0,2,4,6])
        self.assertTrue(all(a.total_ms < b.total_ms for a,b in zip(variants,variants[1:])))
        self.assertTrue(all(0<v.contact_ms<v.total_ms for v in variants))

    def test_cinematic_moves_restore_field_and_keep_menu_still(self):
        case=test_battle_ui.BattleIntegrationTests();case.setUp();self.addCleanup(case.tearDown)
        scene=case.app.battle;c=scene.canvas
        actor=member('Retri',RETRI);actor.update(job='Seer',researched=['seer_final_omen'],mp=100)
        scene.start(BattleModel(ENEMIES[0],party=[actor]),0)
        scene.chosen_ability=next(x for x in LESSONS['Seer'] if x.id=='seer_final_omen')
        scene._begin_ability_fx(0)
        # The message is a fixed UI reference while the battlefield pans.
        message=next(item for item in c.find_withtag(scene.DYNAMIC) if c.type(item)=='text')
        menu_coords=c.coords(message)
        base=c.coords(scene.party_items[0])
        scene.update((scene.ability_contact_ms+30)/1000)
        self.assertNotEqual(c.coords(scene.party_items[0]),base)
        self.assertEqual(c.coords(message),menu_coords)
        self.assertTrue(c.find_withtag('battle_atmosphere'))
        self.assertTrue(c.find_withtag('ability_damage'))
        scene.update(scene.ability_duration_ms/1000+.01)
        self.assertEqual(c.coords(scene.party_items[0]),base)
        self.assertEqual(scene._camera_offset,(0,0))
        self.assertFalse(c.find_withtag('battle_atmosphere'))
        self.assertFalse(c.find_withtag('ability_damage'))
        scene.close()

if __name__=='__main__': unittest.main()
