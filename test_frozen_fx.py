"""Frozen overlay follows status and impact timing, with no persistent stale items."""
import unittest
from battle import BattleModel, ENEMIES, DEN_MOTHER
from research import LESSONS
from abilities import lesson_variant
from stats import member, RETRI, TEMUR
import test_battle_ui

class FrozenOverlayTests(unittest.TestCase):
    def setUp(self):
        self.case=test_battle_ui.BattleIntegrationTests();self.case.setUp();self.addCleanup(self.case.tearDown)
        self.scene=self.case.app.battle;self.c=self.scene.canvas
        actor=member('Retri',RETRI);actor['agility']=40
        self.model=BattleModel(ENEMIES[0],party=[actor])
        self.scene.start(self.model,0)

    def test_shell_pops_holds_until_cured_and_then_clears(self):
        key=('party',0);self.model.statuses.apply(key,'frozen')
        self.scene._draw_ailments(0)
        items=self.c.find_withtag('frozen_shell');self.assertEqual(len(items),1)
        self.assertEqual(self.c.itemcget(items[0],'state'),'normal')
        self.scene._draw_ailments(4)
        self.assertEqual(self.c.find_withtag('frozen_shell'),items)
        self.assertEqual(self.c.itemcget(items[0],'state'),'normal')
        self.model.statuses.cure(key);self.scene._draw_ailments(4.1)
        self.assertEqual(len(self.c.find_withtag('frozen_shell')),1)
        self.scene._draw_ailments(4.5)
        self.assertFalse(self.c.find_withtag('frozen_shell'))

    def test_pop_waits_for_spell_contact(self):
        key=('enemy',0);self.model.statuses.apply(key,'frozen')
        lesson=next(x for x in LESSONS['Seer'] if x.id=='seer_mist_ray')
        self.scene.fx_variant=lesson_variant(lesson,{'job':'Seer'})
        self.scene.fx_on_enemy=True;self.scene.phase='ability_fx';self.scene.phase_at=0
        self.scene._draw_ailments(0)
        item=self.c.find_withtag('frozen_shell')[0]
        self.assertEqual(self.c.itemcget(item,'state'),'hidden')
        self.scene._draw_ailments(self.scene.fx_variant.contact_ms/1000+.01)
        self.assertEqual(self.c.itemcget(item,'state'),'normal')

    def test_independent_targets_follow_camera_and_ko_clears(self):
        for key in (('party',0),('enemy',0)):self.model.statuses.apply(key,'frozen')
        self.scene._draw_ailments(0)
        self.assertEqual(len(self.c.find_withtag('frozen_shell')),2)
        state=self.scene.frozen_fx.states[('party',0)];before=self.c.coords(state['item'])
        self.scene._camera_offset=(6,-3);self.scene._draw_ailments(.1)
        after=self.c.coords(state['item'])
        self.assertEqual(after,[before[0]+self.c._value(6),before[1]+self.c._value(-3)])
        self.model.party[0]['hp']=0;self.scene._draw_ailments(.2)
        self.assertNotIn(('party',0),self.scene.frozen_fx.states)
        self.scene.close();self.assertFalse(self.c.find_withtag('frozen_shell'))

    def test_large_enemy_scales_and_battle_restart_resets(self):
        model=BattleModel(DEN_MOTHER,party=self.model.party)
        self.scene.start(model,0);model.statuses.apply(('enemy',0),'frozen')
        self.scene._draw_ailments(0)
        state=self.scene.frozen_fx.states[('enemy',0)]
        self.assertGreater(state['frame'][1],2)
        self.scene.start(BattleModel(ENEMIES[0],party=self.model.party),1)
        self.assertFalse(self.c.find_withtag('frozen_shell'))
        self.assertFalse(self.scene.frozen_fx.states)

    def test_overlay_has_translucent_frames_and_preserves_character_image(self):
        item=self.scene.party_items[0];original=self.c.itemcget(item,'image')
        self.model.statuses.apply(('party',0),'frozen');self.scene._draw_ailments(.5)
        self.assertEqual(self.c.itemcget(item,'image'),original)
        self.assertEqual(self.c.type(self.c.find_withtag('frozen_shell')[0]),'image')
        self.assertFalse(any(self.c.type(i)=='text' for i in self.c.find_withtag('battle_ailment_fx')))

if __name__=='__main__':unittest.main()
