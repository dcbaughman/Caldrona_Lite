"""Supplied CTB breakpoints, recovery ranks, status timing, and game integration."""
from collections import Counter
from dataclasses import replace
import unittest
from ctb import CTBQueue, tick_speed, recovery
from battle import BattleModel, ENEMIES
from research import LESSONS
from stats import RETRI, TEMUR, member
import test_battle_ui

class CTBTests(unittest.TestCase):
    def test_every_breakpoint_and_recovery_example(self):
        bands=[(0,0,28),(1,1,26),(2,2,24),(3,3,22),(4,4,20),(5,6,16),(7,9,15),
               (10,11,14),(12,14,13),(15,16,12),(17,18,11),(19,22,10),(23,28,9),
               (29,34,8),(35,43,7),(44,61,6),(62,97,5),(98,169,4),(170,255,3)]
        for lo,hi,speed in bands:
            for agility in range(lo,hi+1):self.assertEqual(tick_speed(agility),speed)
        self.assertEqual((recovery(20,3),recovery(40,3),recovery(40,3,'haste')),(30,21,11))
        self.assertEqual(recovery(40,3,'slow'),42)
        self.assertEqual(tick_speed(999),3)
        self.assertEqual(tick_speed(-1),28)

    def test_faster_actor_gets_more_turns(self):
        q=CTBQueue({'slow':20,'fast':40});counts=Counter()
        for _ in range(300):counts[q.current]+=1;q.advance(3)
        self.assertGreater(counts['fast'],counts['slow']*1.35)
        self.assertLess(counts['fast'],counts['slow']*1.5)

    def test_actions_and_preview_do_not_mutate_waits(self):
        q=CTBQueue({'fast':40,'other':20})
        snapshot=(dict(q.ready),q.tick,q.current,q.completed)
        self.assertNotEqual(q.preview(12,2),q.preview(12,3))
        self.assertEqual(snapshot,(q.ready,q.tick,q.current,q.completed))
        q.advance(2)
        self.assertEqual(q.ready['fast'],21+14)
        self.assertEqual(q.current,'other')

    def test_haste_slow_and_dispel_wait_rules(self):
        q=CTBQueue({'acting':40,'waiting':20}) # tick 21, waiting has 9 ticks left.
        q.set_status('waiting','haste');self.assertEqual(q.ready['waiting']-q.tick,4)
        q.set_status('waiting','haste');self.assertEqual(q.ready['waiting']-q.tick,4)
        q.set_status('waiting',None);self.assertEqual(q.ready['waiting']-q.tick,4)
        q.set_status('waiting','slow');self.assertEqual(q.ready['waiting']-q.tick,8)
        q.set_status('waiting',None);self.assertEqual(q.ready['waiting']-q.tick,8)
        self.assertEqual(recovery(255,3,'haste'),5)

    def test_ties_are_stable_and_dead_units_leave_queue(self):
        living={'a','b','c'};q=CTBQueue(dict.fromkeys(('a','b','c'),8),living.__contains__)
        self.assertEqual(q.current,'a');q.advance();self.assertEqual(q.current,'b')
        living.remove('c');self.assertNotIn('c',q.preview(20))
        q.advance();self.assertEqual(q.current,'a')

    def test_failed_commands_do_not_consume_turns_and_ranks_match(self):
        actor=member('Retri',RETRI);actor['agility']=20
        m=BattleModel(ENEMIES[0],party=[actor]);m.begin_ctb()
        before=(m.ctb.current,dict(m.ctb.ready),m.ctb.tick)
        self.assertFalse(m.command('Potion'))
        self.assertEqual(before,(m.ctb.current,m.ctb.ready,m.ctb.tick))
        self.assertTrue(m.command('Guard'));self.assertEqual(m.action_rank,2)
        m.finish_ctb_turn();self.assertEqual(m.ctb.completed,1)
        self.assertIn(0,m.guarded)
        actor['job']='Sollers';actor['researched']=['sollers_pilfer'];m.ctb=None;m.pending_reply=False
        self.assertTrue(m.command('Ability',ability_id='sollers_pilfer',target=0))
        self.assertEqual(m.action_rank,3)
        ranks={x.id:x.action_rank for x in LESSONS['Seer']}
        self.assertEqual(ranks['seer_gale'],4);self.assertEqual(ranks['seer_astral_flood'],6)

class CTBIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.case=test_battle_ui.BattleIntegrationTests();self.case.setUp();self.addCleanup(self.case.tearDown)
        self.scene=self.case.app.battle

    def test_each_monster_acts_and_has_queue_identity(self):
        actor=member('Retri',RETRI);actor.update(hp=600,max_hp=600,agility=0)
        foes=[replace(ENEMIES[0],agility=44,attack=(1,1)) for _ in range(3)]
        model=BattleModel(foes,party=[actor]);self.scene.start(model,0)
        attackers=[]
        for n in range(3):
            self.assertEqual(self.scene.phase,'enemy_action');attackers.append(model.attacker)
            labels=[self.scene.canvas.itemcget(i,'text') for i in self.scene.canvas.find_withtag('battle_turn_queue') if self.scene.canvas.type(i)=='text']
            self.assertTrue({'MON A','MON B','MON C'}<=set(labels))
            self.scene.update((n+1)*.7)
        self.assertEqual(attackers,[0,1,2])
        self.assertGreaterEqual(model.ctb.completed,3)

    def test_mp_always_shows_and_menu_time_freezes(self):
        actor=member('Retri',RETRI);actor.update(agility=40,job='Seer',researched=['seer_gale'])
        model=BattleModel(replace(ENEMIES[0],agility=20),party=[actor]);self.scene.start(model,0)
        tick=model.ctb.tick
        for phase in ('command','target','ally_target'):
            self.scene.phase=phase;self.scene.draw_status()
            labels=[self.scene.canvas.itemcget(i,'text') for i in self.scene.canvas.find_withtag(self.scene.DYNAMIC) if self.scene.canvas.type(i)=='text']
            self.assertIn('MP 8/8',labels)
            self.scene.update(1000)
            self.assertEqual(model.ctb.tick,tick)
        self.scene.phase='command';self.scene.selection=0
        attack_order=model.ctb.preview(12,self.scene._preview_rank())
        self.scene.selection=1
        self.assertNotEqual(attack_order,model.ctb.preview(12,self.scene._preview_rank()))

    def test_ko_enemy_not_in_preview_and_guard_expires_on_own_turn(self):
        actor=member('Retri',RETRI);actor['agility']=40
        model=BattleModel([ENEMIES[0],ENEMIES[1]],party=[actor]);self.scene.start(model,0)
        model.health[1]=0
        self.assertNotIn(('enemy',1),model.ctb.preview(20))
        self.scene.selection=1;self.scene.confirm(0)
        self.assertEqual(model.action_rank,2)
        self.scene.update(.7)
        self.assertEqual(model.ctb.current,('party',0)) # Short guard recovery beats spider's opening.
        self.assertNotIn(0,model.guarded)

    def test_minimal_location_is_only_one_text_item(self):
        a=self.case.app;c=a.canvas
        items=c.find_withtag('hud')
        self.assertEqual(len(items),1);self.assertEqual(c.type(items[0]),'text')
        self.assertEqual(c.itemcget(items[0],'text'),'Sunrest Excavation')
        a.in_chamber=True;a._update_world()
        self.assertEqual(c.itemcget(a.location_label,'text'),'Astral Hollow')

if __name__=='__main__':unittest.main()
