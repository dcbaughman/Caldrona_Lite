"""Darkness and Silence coexist with poison and restore the right sprite on cure."""
import unittest
from battle import BattleModel, ENEMIES
from stats import RETRI, member
import test_battle_ui

class DarknessSilenceTests(unittest.TestCase):
 def setUp(self):
  case=test_battle_ui.BattleIntegrationTests();case.setUp();self.addCleanup(case.tearDown)
  self.scene=case.app.battle;self.c=self.scene.canvas
  p=member('Retri',RETRI);p['agility']=40
  self.m=BattleModel(ENEMIES[0],party=[p]);self.scene.start(self.m,0)

 def test_darkness_blackens_preserves_mask_and_poison_keeps_looping(self):
  key=('party',0)
  self.m.statuses.apply(key,'darkness');self.m.statuses.apply(key,'poison')
  self.scene._draw_ailments(0)
  source=self.scene.party_sprites[0];tint=self.scene.darkness_silence_fx.images[str(source)]
  self.assertEqual(self.c.itemcget(self.scene.party_items[0],'image'),str(self.c._image(tint)))
  self.assertTrue(self.c.find_withtag('poison_aura'))
  for y in range(source.height()):
   for x in range(source.width()):
    self.assertEqual(source.transparency_get(x,y),tint.transparency_get(x,y))
    if not source.transparency_get(x,y):self.assertLess(max(tint.get(x,y)),45)
  self.m.statuses.remove(key,'darkness');self.scene._draw_ailments(1)
  self.assertEqual(self.c.itemcget(self.scene.party_items[0],'image'),str(self.c._image(source)))
  self.assertTrue(self.c.find_withtag('poison_aura'))

 def test_sealed_lips_are_face_attached_and_all_three_coexist(self):
  key=('party',0)
  for status in ('darkness','silence','poison'):self.m.statuses.apply(key,status)
  self.scene._draw_ailments(0)
  seal=self.scene.darkness_silence_fx.seals[key]
  self.assertEqual(len(seal['items']),8)
  self.assertFalse(any(self.c.type(i)=='text' for i in self.c.find_withtag('silence_seal')))
  before=self.c.coords(seal['items'][0])
  actor=self.scene.party_items[0];px,py=self.c.coords(actor);self.c.coords(actor,px+4,py-2)
  self.scene._draw_ailments(.1)
  after=self.c.coords(seal['items'][0])
  self.assertEqual(after,[v+(4 if j%2==0 else -2) for j,v in enumerate(before)])
  self.assertTrue(self.c.find_withtag('poison_aura'))
  self.m.statuses.remove(key,'silence');self.scene._draw_ailments(.2)
  self.assertFalse(self.c.find_withtag('silence_seal'));self.assertIn(key,self.scene.darkness_silence_fx.darkened)

 def test_pose_changes_cure_and_battle_cleanup(self):
  key=('party',0);self.m.party[0]['job']='Saint'
  self.m.statuses.apply(key,'darkness');self.m.statuses.apply(key,'silence')
  self.m.guarded.add(0);self.scene._sync_party_sprites();self.scene._draw_ailments(0)
  source=self.scene.class_poses[('Retri','Saint','guard')]
  self.assertEqual(self.c.itemcget(self.scene.party_items[0],'image'),str(self.c._image(self.scene.darkness_silence_fx.images[str(source)])))
  self.m.statuses.cure(key);self.scene._draw_ailments(.1)
  self.assertEqual(self.c.itemcget(self.scene.party_items[0],'image'),str(self.c._image(source)))
  self.assertFalse(self.c.find_withtag('silence_seal'))
  self.m.statuses.apply(('enemy',0),'darkness');self.m.statuses.apply(('enemy',0),'silence');self.scene._draw_ailments(.2)
  self.assertTrue(self.scene.darkness_silence_fx.darkened)
  self.scene.close();self.assertFalse(self.c.find_withtag('silence_seal'))
  self.assertFalse(self.scene.darkness_silence_fx.darkened)

if __name__=='__main__':unittest.main()
