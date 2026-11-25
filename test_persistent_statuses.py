"""Persistent ailment coverage across combat, revival, defeat, and saves."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import Caldrona_Lite as game
from battle import BattleModel, ENEMIES
from consumables import apply_supply
from statuses import StatusBook
from stats import RETRI, TEMUR, member
from save_game import capture,write_slot,read_slot,validate,SaveError
import test_battle_ui

class PermanentStatusTests(unittest.TestCase):
 def test_no_turn_expiry_for_standing_actors_and_ko_clears_all_ailments(self):
  person=member('Retri',RETRI);book=StatusBook();key=('party',0);book.bind(key,person)
  for status in ('poison','darkness','silence'):book.apply(key,status)
  for _ in range(30):book.end_turn(key)
  self.assertEqual(person['ailments'],dict.fromkeys(('poison','darkness','silence'),-1))
  self.assertEqual(book.label(key),'PSN | DRK | SIL')
  for status in ('frozen','webbed'):book.apply(key,status)
  person['hp']=0;book.clear_ko(key)
  self.assertEqual(book.label(key), '')
  self.assertNotIn('ailments',person)

 def test_ember_feather_revives_after_poison_ko_without_ailments(self):
  retri, temur = member('Retri', RETRI), member('Temur', TEMUR)
  retri.update(hp=1, agility=40, ailments={'poison': -1, 'darkness': -1, 'silence': -1})
  temur['agility'] = 12
  model = BattleModel(ENEMIES[0], party=[retri, temur], supplies={'Ember Feather': 1})
  model.begin_ctb()
  self.assertTrue(model.command('Guard'))
  self.assertEqual(model.finish_ctb_turn(), ('party', 1))
  self.assertEqual(retri['hp'], 0)
  self.assertNotIn('ailments', retri)
  self.assertTrue(model.command('Ember Feather', target=0))
  self.assertEqual(retri['hp'], retri['max_hp'] // 4)
  self.assertEqual(model.statuses.label(('party', 0)), '')
  self.assertTrue(model.apply_status(('party', 0), 'poison'))

 def test_revival_items_clear_stale_saved_and_live_ailments(self):
  for item, expected_hp in (('Ember Feather', RETRI['max_hp'] // 4),
                            ('Ember Talisman', RETRI['max_hp'])):
   with self.subTest(item=item):
    person = member('Retri', RETRI)
    person.update(hp=0, ailments={'darkness': -1})
    live = {'poison': -1, 'webbed': 2}
    self.assertTrue(apply_supply(item, person, live)[0])
    self.assertEqual(person['hp'], expected_hp)
    self.assertNotIn('ailments', person)
    self.assertFalse(live)

 def test_party_ailments_carry_to_next_battle_but_enemies_are_fresh(self):
  person=member('Retri',RETRI)
  first=BattleModel(ENEMIES[0],party=[person]);first.statuses.apply(('party',0),'poison')
  first.statuses.apply(('enemy',0),'darkness')
  second=BattleModel(ENEMIES[0],party=[person])
  self.assertTrue(second.statuses.has(('party',0),'poison'))
  self.assertFalse(second.statuses.has(('enemy',0),'darkness'))
  second.statuses.remove(('party',0),'poison')
  third=BattleModel(ENEMIES[0],party=[person]);self.assertFalse(third.statuses.has(('party',0),'poison'))

class PersistentStatusSceneTests(unittest.TestCase):
 def setUp(self):
  case=test_battle_ui.BattleIntegrationTests();case.setUp();self.addCleanup(case.tearDown)
  self.a=case.app;self.scene=case.app.battle

 def test_field_remedy_removes_saved_ailment_without_hp_change(self):
  person=self.a.party[0];person['ailments']={'poison':-1,'darkness':-1,'silence':-1}
  self.a.supplies={'Remedy':1};hp=person['hp']
  self.assertIn('cleansed',self.a._use_menu_item('Remedy',person))
  self.assertNotIn('ailments',person);self.assertEqual(person['hp'],hp)
  self.assertEqual(self.a.supplies['Remedy'],0)

 def test_save_roundtrip_and_validation_are_backward_compatible(self):
  person=self.a.party[0];person['ailments']={'poison':-1,'silence':-1}
  state=capture(self.a)
  with tempfile.TemporaryDirectory() as directory:
   write_slot(Path(directory),1,state);loaded=read_slot(Path(directory),1)['state']
   self.a._load_journey(loaded)
   self.assertEqual(self.a.party[0]['ailments'],{'poison':-1,'silence':-1})
   model=BattleModel(ENEMIES[0],party=self.a.party)
   self.assertTrue(model.statuses.has(('party',0),'poison'))
  old=copy.deepcopy(state);old['party'][0].pop('ailments');validate(old)
  for ailments in ({'poison':2},{'frozen':-1},{'unknown':-1},{'poison':True}):
   bad=copy.deepcopy(state);bad['party'][0]['ailments']=ailments
   with self.assertRaises(SaveError):validate(bad)

 def test_field_revives_fainted_member_from_an_old_save(self):
  state = capture(self.a)
  state['party'][0].update(hp=0, ailments={'poison': -1, 'silence': -1})
  state['supplies']['Ember Talisman'] = 1
  self.a._load_journey(state)
  person = self.a.party[0]
  self.assertNotIn('ailments', person)
  self.assertIn('rises', self.a._use_menu_item('Ember Talisman', person))
  self.assertEqual(self.a.hp, person['max_hp'])
  self.assertNotIn('ailments', person)

 def test_continue_after_defeat_clears_ailments_for_the_entire_roster(self):
  retri, temur = self.a.party[0], member('Temur', TEMUR)
  temur.update(active=False, ailments={'darkness': -1})
  self.a.party.append(temur)
  self.scene.model = BattleModel(ENEMIES[0], party=[retri])
  retri.update(hp=0, ailments={'poison': -1, 'silence': -1})
  self.a._show_game_over(0)
  self.a._activate()
  self.assertEqual((self.a.x, self.a.y), self.a.cave.spawn)
  for person in self.a.party:
   self.assertEqual(person['hp'], person['max_hp'])
   self.assertNotIn('ailments', person)

 def test_loop_persists_until_cure_and_follows_camera(self):
  person=self.a.party[0];person['ailments']={'poison':-1}
  model=BattleModel(ENEMIES[0],party=[person]);self.scene.start(model,0)
  self.scene._draw_ailments(0)
  state=self.scene.poison_fx.states[('party',0)]
  self.assertGreaterEqual(state['frame'][0],4) # Already poisoned: enter the held loop.
  item=state['item'];self.scene._draw_ailments(100)
  self.assertEqual(self.a.canvas.find_withtag('poison_aura'),(item,))
  coords=self.a.canvas.coords(item);self.scene._camera_offset=(4,-2);self.scene._draw_ailments(100.1)
  self.assertEqual(self.a.canvas.coords(item),[coords[0]+4,coords[1]-2])
  model.statuses.cure(('party',0));self.scene._draw_ailments(100.2)
  self.assertFalse(self.a.canvas.find_withtag('poison_aura'))
  self.assertNotIn('ailments',person)

 def test_healthy_party_data_is_unchanged_and_frozen_is_not_saved(self):
  person=self.a.party[0];before=copy.deepcopy(person)
  model=BattleModel(ENEMIES[0],party=[person]);self.assertEqual(person,before)
  model.statuses.apply(('party',0),'frozen')
  self.assertNotIn('ailments',person)
  model.statuses.end_turn(('party',0));self.assertFalse(model.statuses.has(('party',0),'frozen'))

if __name__=='__main__':unittest.main()
