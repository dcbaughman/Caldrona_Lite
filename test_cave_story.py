"""Linear route, collapse story/save compatibility, and readable boss move animations."""
from collections import deque
from copy import deepcopy
import random
import unittest
from unittest.mock import Mock
import Caldrona_Lite as game
from battle import BattleModel,ShalehornBattle,SHALEHORN
from cave_story import ENTRY, ENTRY_SHOULDERS, MINER, SIGNS
from save_game import capture,validate,SaveError
import test_battle_ui

class CaveProgressionTests(unittest.TestCase):
 def setUp(self):
  self.case=test_battle_ui.BattleIntegrationTests();self.case.setUp();self.addCleanup(self.case.tearDown)
  self.a=self.case.app

 def test_main_route_passes_through_lower_workings(self):
  cave=game.CavernInstance();start=(8,8);goal=(49,5)
  queue=deque([start]);previous={start:None}
  while queue:
   point=queue.popleft()
   if point==goal:break
   for dx,dy in ((0,1),(0,-1),(1,0),(-1,0)):
    nxt=(point[0]+dx,point[1]+dy)
    if nxt in cave.floor and nxt not in previous:previous[nxt]=point;queue.append(nxt)
  self.assertIn(goal,previous)
  path=[];p=goal
  while p is not None:path.append(p);p=previous[p]
  self.assertTrue(any(y>=21 and x<23 for x,y in path))
  self.assertTrue(any(y>=21 and x>=29 for x,y in path))
  self.assertNotIn((18,8),cave.floor);self.assertIn((18,8),cave.legacy_floor)
  for _,(tile,_,_) in SIGNS.items():self.assertIn(tile,cave.floor)
  self.assertIn(MINER,cave.floor)
  self.assertTrue(all(tile not in cave.floor for tile in ENTRY_SHOULDERS))

 def _advance_dialogue(self):
  while self.a.dialogue.active:
   self.a._activate()

 def _start_opening(self):
  a = self.a
  a._play_sfx = Mock()
  a._draw_menu()
  a.selection = 0
  a._activate()
  self.assertEqual((a.x / 16, a.y / 16), (8.5, 4.5))
  self.assertTrue(a.dialogue.active)
  self.assertEqual(a.canvas.itemcget(a.temur_item, "state"), "hidden")
  self._advance_dialogue()
  self.assertEqual(a.screen, "cave_walk")

 def test_opening_walk_pauses_then_collapses_before_temur_approaches(self):
  self._start_opening()
  a = self.a
  start = a.mine_story.started
  a.mine_story.update_walk(start + .74)
  self.assertEqual((a.x / 16, a.y / 16, a.direction), (8.5, 6.5, "left"))
  a.mine_story.update_walk(start + 1.12)
  self.assertEqual((a.y / 16, a.direction), (6.5, "right"))
  a._play_sfx.assert_not_called()
  a.mine_story.update_walk(start + 1.8)
  self.assertEqual((a.screen, a.y / 16), ("entrance_collapse", 7.5))
  a._play_sfx.assert_called_once_with(game.COLLAPSE_SOUND)
  a._back()
  a._activate()
  self.assertEqual(a.screen, "entrance_collapse")
  base_y = (a.y - a._camera()[1]) * game.SCALE
  collapse = a.mine_story.started
  a.mine_story.update(collapse + .48)
  self.assertLess(a.canvas.coords(a.player_item)[1], base_y - 15)
  self.assertTrue(a.canvas.find_withtag("entrance_debris"))
  a.mine_story.update(collapse + 1.1)
  debris = a.canvas.find_withtag("entrance_debris")
  self.assertTrue(debris)
  self.assertTrue(all(a.canvas.type(item) == "oval" for item in debris))
  a.mine_story.update(collapse + 1.8)
  self.assertEqual(a.screen, "cave_walk")
  self.assertTrue(a.cave_story["entrance_collapsed"])
  self.assertFalse(a.cave.walkable((ENTRY[0]+.5)*16, (ENTRY[1]+.5)*16))
  self.assertEqual(a.canvas.coords(a.player_item)[1], base_y)
  self.assertFalse(a.canvas.find_withtag("entrance_debris"))
  self.assertGreater(a.canvas.coords(a.temur_item)[1], a.canvas._value(540))
  a.mine_story.update_walk(a.mine_story.started + 1.5)
  self.assertTrue(a.dialogue.active)
  self.assertEqual(a.canvas.coords(a.player_item)[1], a.canvas.coords(a.temur_item)[1])
  self.assertEqual(a.canvas.itemcget(a.temur_item, "state"), "normal")
  self._advance_dialogue()
  self.assertEqual(a.screen, "temur_choice")
  self.assertEqual(len(a.party), 1)
  a._activate()
  self._advance_dialogue()
  self.assertEqual(a.temur_story, "joined")
  self.assertEqual([person["name"] for person in a.party], ["Retri", "Temur"])

 def test_decline_walks_offscreen_and_stays_declined_on_load(self):
  self._start_opening()
  a = self.a
  a.mine_story.update_walk(a.mine_story.started + 2)
  a.mine_story.update(a.mine_story.started + 2)
  a.mine_story.update_walk(a.mine_story.started + 2)
  self._advance_dialogue()
  self.assertEqual(a.screen, "temur_choice")
  a.keys.add("down")
  self.case.tick()
  a.keys.clear()
  a._activate()
  self._advance_dialogue()
  self.assertEqual(a.temur_story, "departing")
  a.mine_story.update_walk(a.mine_story.started + 3)
  self.assertEqual((a.screen, a.temur_story), ("game", "declined"))
  self.assertGreater(a.canvas.coords(a.temur_item)[1], a.canvas._value(540))
  self.assertEqual(a.canvas.itemcget(a.temur_item, "state"), "hidden")
  self.assertEqual([person["name"] for person in a.party], ["Retri"])
  state = capture(a)
  a._load_journey(state)
  self.assertFalse(a.dialogue.active)
  self.assertEqual(a.temur_story, "declined")
  a.x, a.y, a.direction = 9.5*16, 7.5*16, "right"
  self.assertFalse(a._interact_temur())
  a._update_world()
  self.assertEqual(a.canvas.itemcget(a.temur_item, "state"), "hidden")

 def test_actor_foot_baseline_agrees_for_all_retri_and_temur_poses(self):
  a = self.a
  retri = [frame for frames in a.player_frames.values() for frame in frames]
  temur = list(a.dialogue_actors["temur"][2].values())
  for frame in retri + temur:
   bottom = next(y for y in reversed(range(frame.height()))
                 if any(not frame.transparency_get(x,y) for x in range(frame.width())))
   self.assertEqual(bottom, 15 * game.SCALE - 1)

 def test_miner_warning_and_inspected_props_persist(self):
  a=self.a;a.x,a.y=47.5*16,8.5*16
  self.assertTrue(a.mine_story.maybe_warn());self.assertTrue(a.cave_story['miner_warned'])
  text=' '.join(line.text for line in a.dialogue.lines)+' '+ ' '.join(a.canvas.itemcget(i,'text') for i in a.canvas.find_withtag(a.dialogue.TAG) if a.canvas.type(i)=='text')
  self.assertIn('blue rock',text);self.assertIn('tearing the cave apart',text)
  a.dialogue.clear();a.x,a.y,a.direction=6.5*16,5.5*16,'right'
  self.assertTrue(a.mine_story.interact());self.assertIn('dropped_tools',a.cave_story['inspected'])
  a.dialogue.clear();state=capture(a);a._load_journey(state)
  self.assertEqual(a.cave_story,state['cave_story']);self.assertFalse(a.opening_intro_active)

 def test_theo_uses_native_portrait_before_and_after_shalehorn(self):
  a = self.a
  portrait = a.dialogue.portrait(game.THEO_PORTRAIT, None)
  self.assertIsNotNone(portrait)
  self.assertEqual((portrait.width(), portrait.height()), (128, 128))
  for cleared in (False, True):
   a.boss_cleared = cleared
   a.mine_story.warning()
   items = a.canvas.find_withtag(a.dialogue.TAG)
   self.assertTrue(any(a.canvas.type(i) == "text" and a.canvas.itemcget(i, "text") == "THEO" for i in items))
   self.assertEqual([a.canvas.itemcget(i, "image") for i in items if a.canvas.type(i) == "image"],
                    [str(a.canvas._image(portrait))])
   self.assertTrue(all(line.portrait == game.THEO_PORTRAIT
                       for line in a.dialogue.lines if line.speaker == "Theo"))

 def test_world_dialogue_turns_visible_speakers_toward_retri(self):
  a = self.a
  for name, outdoors, initiate in (
   ("temur", False, a._interact_temur),
   ("theo", False, a.mine_story.interact),
   ("merren", True, a._interact_merren),
  ):
   item, (tx, ty), frames = a.dialogue_actors[name]
   a.outdoors = outdoors
   a.cave = a.grassland_map if outdoors else a.cavern_map
   a.x, a.y, a.direction = (tx-.5)*16, (ty+.5)*16, "right"
   a._update_world(force=True)
   self.assertTrue(initiate())
   self.assertEqual(a.canvas.itemcget(item, "image"), str(a.canvas._image(frames["left"])))
   a.dialogue.clear()
  a.party.append({"name": "Temur"})
  a.x, a.y = 32.5*16, 3.5*16
  a._grassland_intro()
  while a.dialogue.active:
   a.dialogue.advance()
  item, _, frames = a.grass_temur_actor
  self.assertEqual(a.canvas.itemcget(item, "image"), str(a.canvas._image(frames["up"])))

 def test_late_temur_recruitment_does_not_shake_a_cleared_cave(self):
  a=self.a;a.boss_cleared=True;a.x,a.y,a.direction=9.5*16,7.5*16,'right'
  self.assertTrue(a._interact_temur());self.assertEqual(a.temur_story,'offering')
  self._advance_dialogue()
  a._activate()
  self._advance_dialogue()
  self.assertEqual(a.screen,'game');self.assertEqual(a.temur_story,'joined')
  self.assertIn('Temur',[person['name'] for person in a.party])

 def test_old_save_relocates_removed_corridor_without_replaying_intro(self):
  a=self.a;state=capture(a);state.pop('cave_story');state['x'],state['y']=18.5*16,8.5*16
  a._load_journey(state)
  self.assertTrue(a.cave.walkable(a.x,a.y));self.assertTrue(a.cave_story['entrance_collapsed'])
  self.assertFalse(a.dialogue.active);self.assertEqual(a.screen,'game')
  bad=deepcopy(state);bad['cave_story']={'entrance_collapsed':'yes','miner_warned':False,'inspected':[]}
  with self.assertRaises(SaveError):validate(bad)

class ShalehornAnimationTests(unittest.TestCase):
 def setUp(self):
  self.case=test_battle_ui.BattleIntegrationTests();self.case.setUp();self.addCleanup(self.case.tearDown)
  self.scene=self.case.app.battle

 def boss(self,move):
  p=dict(self.case.app.party[0]);p.update(hp=1000,max_hp=1000,agility=0)
  model=ShalehornBattle(SHALEHORN,party=[p],rng=random.Random(3));model.move_index=move
  self.scene.start(model,0);return model

 def test_burrow_digs_before_hiding_and_hole_persists_to_eruption(self):
  model=self.boss(2);c=self.scene.canvas
  self.assertTrue(model.buried);self.assertEqual(model.boss_move,'burrow')
  self.scene.update(.15);self.assertEqual(c.itemcget(self.scene.enemy_items[0],'state'),'normal')
  self.scene.update(1.1);self.assertEqual(c.itemcget(self.scene.enemy_items[0],'state'),'hidden')
  fx = self.scene.shalehorn_fx
  self.assertTrue(fx.hole)
  self.assertEqual(c.itemcget(self.scene.backdrop_item, 'image'), str(c._image(fx.floor_image)))
  image_key = fx.rendered_floor
  self.scene.update(1.21)  # The ambient glow advances while Shalehorn is underground.
  self.assertNotEqual(fx.rendered_floor, image_key)
  self.assertEqual(c.itemcget(self.scene.backdrop_item, 'image'), str(c._image(fx.floor_image)))
  # Start the already-queued boss eruption explicitly to inspect its animation.
  model.ctb.current=('enemy',0);self.scene._begin_ctb_actor(2)
  self.assertEqual(model.boss_move,'eruption');self.assertFalse(model.buried)
  self.scene.update(2.4);self.assertTrue(fx.hole)
  self.scene.update(3.1)
  self.assertFalse(fx.hole);self.assertEqual(c.itemcget(self.scene.enemy_items[0],'state'),'normal')
  self.assertEqual(c.itemcget(self.scene.backdrop_item, 'image'), str(c._image(self.scene.glow_frames[self.scene.glow_index])))

 def test_darkness_does_not_replace_the_digging_pose(self):
  model=self.boss(2);model.statuses.apply(('enemy',0),'darkness')
  self.scene.update(.6);c=self.scene.canvas
  actual=c.itemcget(self.scene.enemy_items[0],'image')
  self.assertTrue(any(str(c._image(image))==actual for image in self.scene.shalehorn_fx.crops.values()))
  self.assertNotEqual(actual,str(c._image(self.scene.shalehorn_fx._source(self.scene))))

 def test_tremor_moves_ground_but_restores_field(self):
  self.boss(1);c=self.scene.canvas
  self.scene.update(.64)
  fx = self.scene.shalehorn_fx
  self.assertEqual(fx.floor_pose[0], 'tremor')
  self.assertFalse(c.find_withtag('shalehorn_motion'))
  self.assertEqual(c.coords(self.scene.backdrop_item),[0,0])
  display_image = c._image(fx.floor_image)
  self.assertEqual(c.itemcget(self.scene.backdrop_item, 'image'), str(display_image))
  previous = display_image.tk.call(display_image, 'data', '-format', 'ppm')
  self.scene.update(.76)
  self.assertNotEqual(display_image.tk.call(display_image, 'data', '-format', 'ppm'), previous)
  self.scene.update(1.0)
  self.assertEqual(c.coords(self.scene.backdrop_item),[0,0])
  self.assertIsNone(fx.floor_pose)
  self.assertEqual(c.itemcget(self.scene.backdrop_item, 'image'), str(c._image(self.scene.glow_frames[self.scene.glow_index])))
  self.scene.close()

 def test_charge_spotlights_the_tusks_and_lands_away_from_the_party(self):
  from shalehorn_attack import CHARGE_DURATION, CHARGE_LANDING, CONTACT
  self.boss(0)
  scene, c = self.scene, self.scene.canvas
  item = scene.enemy_items[0]
  fx = scene.shalehorn_fx
  original = fx._source(scene)
  scene.update(.18)
  self.assertTrue(fx.charge_focus)
  room = fx.attack.muted_room(scene.glow_frames[0])
  self.assertEqual(c.itemcget(scene.backdrop_item, 'image'), str(c._image(room)))
  self.assertFalse(c.find_withtag('damage_number'))
  self.assertNotEqual(c.itemcget(item, 'image'), str(c._image(original)))
  self.assertTrue(c.find_withtag('shalehorn_tusk_energy'))
  _, tusks = fx.attack._native_sprite(original)
  self.assertGreater(len(tusks), 20)
  scene.update(CONTACT + .02)
  neutral = [c._value(coord) for coord in CHARGE_LANDING]
  self.assertEqual(c.coords(item), neutral)
  self.assertTrue(c.find_withtag('damage_number'))
  debris = c.find_withtag('shalehorn_charge_shale')
  self.assertTrue(debris)
  self.assertTrue(all(c.coords(rock)[2] < c.coords(item)[0] - c._value(48) for rock in debris))
  scene.party_positions[0] = (800, 160)
  scene.update(CONTACT + .08)
  self.assertEqual(c.coords(item), neutral)
  scene.update(CHARGE_DURATION + .01)
  self.assertFalse(fx.charge_focus)
  self.assertEqual(c.itemcget(scene.backdrop_item, 'image'), str(c._image(scene.glow_frames[scene.glow_index])))
  self.assertEqual(c.itemcget(item, 'image'), str(c._image(original)))
  self.assertFalse(c.find_withtag('shalehorn_tusk_energy'))
  self.assertFalse(c.find_withtag('shalehorn_charge_shale'))

if __name__=='__main__':unittest.main()
