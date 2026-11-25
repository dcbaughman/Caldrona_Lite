"""Persistence, atomic writes, slot isolation, sphere routing, and full journey restoration."""
import copy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import Caldrona_Lite as game
from equipment import stat_value
from save_game import capture, read_slot, write_slot, SaveError, slot_path
from stats import TEMUR, member
import test_battle_ui

class SaveJourneyTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.directory=Path(self.tmp.name)
        p=patch.object(game,'SAVE_DIRECTORY',self.directory);p.start();self.addCleanup(p.stop)
        self.case=test_battle_ui.BattleIntegrationTests();self.case.setUp();self.addCleanup(self.case.tearDown)
        self.app=self.case.app

    def reach_sphere(self):
        a=self.app;a.x,a.y=46.5*16,6.5*16;a.direction='right';a._update_world(force=True)
        a._activate();self.assertEqual(a.screen,'save_slots')

    def test_four_files_overwrite_and_roundtrip_from_home(self):
        a=self.app
        a._recruit(member('Temur',TEMUR));a.temur_story='joined'
        a.party[0].update(job='Seer',researched=['seer_gale'],rp=7,attuned_stone='first_stone')
        a.party[1].update(job='Saint',active=False)
        a.gold=125;a.potions=4;a.supplies={'Ether':2};a.materials={'bat_wing':3}
        a.materials_sold={'bat_wing':2};a.bazaar_bought={'test_item'}
        a.analects={'Echo Analect':1};a.gear_inventory['pickpocket_dirk']=1
        a.chest_open=a.boss_cleared=a.astral_sync=True
        self.reach_sphere()
        expected=capture(a)
        for i in range(4):
            a.save_scene.selection=i;a._activate()
            self.assertEqual(read_slot(self.directory,i+1)['state'],expected)
        a.gold=999;a.save_scene.selection=0;a._activate()
        self.assertTrue(a.save_scene.confirming);a._activate()
        self.assertEqual(read_slot(self.directory,1)['state']['gold'],125)
        a._activate();a.save_scene.overwrite=True;a._activate()
        self.assertEqual(read_slot(self.directory,1)['state']['gold'],999)
        a._back();self.assertEqual(a.screen,'game')
        a._leave_cavern();a.selection=1;a._activate()
        self.assertEqual(a.screen,'save_slots');self.assertEqual(a.save_scene.mode,'load')
        a.save_scene.selection=1;a._activate()
        self.assertEqual(a.screen,'game');self.assertFalse(a.dialogue.active)
        self.assertEqual(capture(a),expected)
        self.assertEqual(a.canvas.itemcget(a.chest_item,'image'),str(a.canvas._image(a.chest_images[1])))
        self.assertEqual(a.canvas.itemcget(a.save_sphere_item,'state'),'normal')
        self.assertFalse(a.cave.walkable(49.5*16,4.5*16)) # Door remains an interaction tile.

    def test_empty_corrupt_and_failed_write_keep_other_slots(self):
        state=capture(self.app);write_slot(self.directory,2,state)
        self.assertIsNone(read_slot(self.directory,1))
        slot_path(self.directory,1).write_text('{broken')
        with self.assertRaises(SaveError):read_slot(self.directory,1)
        self.assertEqual(read_slot(self.directory,2)['state'],state)
        original=slot_path(self.directory,2).read_bytes()
        with patch('save_game.os.replace',side_effect=OSError('disk full')):
            with self.assertRaises(OSError):write_slot(self.directory,2,state)
        self.assertEqual(slot_path(self.directory,2).read_bytes(),original)
        self.assertFalse(list(self.directory.glob('.saving-*')))
        self.app._leave_cavern();self.app.selection=1;self.app._activate()
        self.app._activate();self.assertEqual(self.app.screen,'save_slots')
        self.app.save_scene.selection=2;self.app._activate()
        self.assertIn('empty',self.app.save_scene.feedback)
        self.app._back();self.assertEqual(self.app.screen,'menu')
        for slot in (0,5,-1):
            with self.assertRaises(SaveError):write_slot(self.directory,slot,state)

    def test_load_rejects_incomplete_data_without_replacing_journey(self):
        state=capture(self.app);del state['party'][0]['max_hp']
        with self.assertRaises(SaveError):self.app._load_journey(state)
        self.assertEqual(self.app.screen,'game')
        state=capture(self.app);state['x']=0;state['y']=0
        with self.assertRaises(SaveError):self.app._load_journey(state)
        self.assertEqual(self.app.screen,'game')

    def test_sphere_is_accessible_and_freezes_movement(self):
        a=self.app
        self.assertIn(a.save_sphere_tile,a.cave.floor)
        a.x, a.y = 46.5 * game.TILE, 6.5 * game.TILE
        position = (a.x, a.y)
        a.keys = {"right"}
        self.case.tick()
        self.assertEqual((a.x, a.y), position)
        self.assertEqual(a.screen, "game")
        enter = SimpleNamespace(keysym="Return")
        a._key_down(enter)
        a._key_down(enter)
        self.assertEqual(a.screen, "save_slots")
        self.assertIsNone(read_slot(self.directory, 1))
        a.keys.add('down');a._tick();a.root.after_cancel(a.tick_after)
        self.assertEqual((a.x,a.y),position)
        a._back();self.assertEqual(a.screen,'game')
        self.assertFalse(a.keys)

    def test_successful_save_restores_hp_mp_and_revives_including_reserves(self):
        a = self.app
        a._recruit(member('Temur', TEMUR))
        retri, temur = a.party
        retri.update(hp=3, mp=1, ailments={'poison': -1},
                     equipment={'armor': 'quarry_mantle', 'accessory': 'quartz_pendant'})
        temur.update(hp=0, mp=0, active=False, ailments={'silence': -1})
        a.hp = 3
        self.reach_sphere()
        self.assertEqual((retri['hp'], temur['hp']), (3, 0))
        a._activate()
        for person in a.party:
            self.assertEqual(person['hp'], stat_value(person, 'max_hp'))
            self.assertEqual(person['mp'], stat_value(person, 'max_mp'))
        self.assertEqual(retri['ailments'], {'poison': -1})
        self.assertNotIn('ailments', temur)
        self.assertEqual(a.hp, retri['hp'])
        saved = read_slot(self.directory, 1)['state']
        self.assertEqual(saved['hp'], a.hp)
        self.assertEqual(saved['party'], a.party)
        a._load_journey(saved)
        self.assertEqual(a.party[1]['hp'], TEMUR['max_hp'])

    def test_cancelled_or_failed_save_does_not_heal(self):
        a = self.app
        a.party[0].update(hp=5, mp=1)
        a.hp = 5
        self.reach_sphere()
        previous = capture(a)
        write_slot(self.directory, 1, previous)
        a._activate()
        self.assertTrue(a.save_scene.confirming)
        a._activate()
        self.assertEqual(capture(a), previous)
        a._activate()
        a.save_scene.overwrite = True
        with patch('save_game.os.replace', side_effect=OSError('disk full')):
            a._activate()
        self.assertIn('Could not save', a.save_scene.feedback)
        self.assertEqual(capture(a), previous)
        self.assertEqual(read_slot(self.directory, 1)['state'], previous)

if __name__=='__main__':unittest.main()
