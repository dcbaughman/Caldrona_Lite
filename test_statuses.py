"""Ailment turn rules, counterplay, enemy skill budgets, and scene transitions."""
from dataclasses import replace
import random
import unittest
from unittest.mock import Mock
from statuses import StatusBook, PLAYER_AILMENTS
from battle import BattleModel, ShalehornBattle, ENEMIES, SHALEHORN, DEN_MOTHER
from research import LESSONS
from stats import member, RETRI, TEMUR
from consumables import apply_supply
import test_battle_ui

def sure():
    rng=Mock();rng.random.return_value=0
    return rng

def hero():
    p=member('Retri',RETRI);p.update(agility=40,mp=100)
    return p

class StatusRulesTests(unittest.TestCase):
    def test_refresh_expiry_and_freeze_resistance(self):
        b=StatusBook();key=('party',0)
        b.apply(key,'poison');b.end_turn(key);self.assertEqual(b.for_actor(key)['poison'],-1)
        b.apply(key,'poison');self.assertEqual(b.for_actor(key)['poison'],-1)
        b.apply(key,'frozen');self.assertFalse(b.apply(key,'frozen'))
        b.end_turn(key);self.assertFalse(b.has(key,'frozen'));self.assertEqual(b.freeze_guard[key],2)
        self.assertFalse(b.apply(key,'frozen'))
        b.end_turn(key);b.end_turn(key);self.assertTrue(b.apply(key,'frozen'))

    def test_poison_ticks_once_on_own_turn_and_can_end_battle(self):
        m=BattleModel(ENEMIES[0],party=[hero()],status_rng=sure());m.begin_ctb()
        m.statuses.apply(('party',0),'poison');m.command('Guard')
        self.assertEqual(m.resolve_turn_end(),[(('party',0),5)])
        self.assertEqual(m.party[0]['hp'],55);self.assertEqual(m.resolve_turn_end(),[])
        self.assertEqual(m.party[0]['hp'],55)
        slow=hero();slow['agility']=0
        m=BattleModel(replace(ENEMIES[0],agility=44),party=[slow],status_rng=sure())
        m.begin_ctb();m.health[0]=1;m.statuses.apply(('enemy',0),'poison')
        m.resolve_turn_end();self.assertEqual(m.outcome,'victory');self.assertEqual(m.health,[0])
        self.assertEqual(m.finish_ctb_turn(),None)
        self.assertEqual(m.rolled_kills,{0})

    def test_darkness_affects_physical_but_not_magic(self):
        p=hero();p.update(job='Seer',researched=['seer_gale'])
        m=BattleModel(replace(ENEMIES[0],hp=200),party=[p],status_rng=sure())
        m.statuses.apply(('party',0),'darkness');m.status_rng.random.return_value=.99
        self.assertTrue(m.command('Attack'));self.assertEqual(m.damage,0);self.assertEqual(m.enemy_hp,200)
        m.pending_reply=False
        self.assertTrue(m.command('Ability',ability_id='seer_gale',target=0));self.assertGreater(m.damage,0)

    def test_silence_blocks_magic_without_spending_mp_or_turn(self):
        p=hero();p.update(job='Seer',researched=['seer_gale','seer_mind_flare'])
        m=BattleModel(replace(ENEMIES[0],hp=200),party=[p]);m.begin_ctb()
        m.statuses.apply(('party',0),'silence');before=m.ctb.tick
        self.assertFalse(m.command('Ability',ability_id='seer_gale'))
        self.assertEqual(p['mp'],100);self.assertFalse(m.pending_reply);self.assertEqual(m.ctb.tick,before)
        self.assertTrue(m.command('Ability',ability_id='seer_mind_flare'));self.assertEqual(p['mp'],98)

    def test_player_moves_apply_all_four_ailments(self):
        applied=set()
        for job,entries in LESSONS.items():
            for lesson in entries:
                if lesson.id not in PLAYER_AILMENTS:continue
                with self.subTest(move=lesson.id):
                    p=hero();p.update(job=job,researched=[lesson.id])
                    m=BattleModel(replace(ENEMIES[0],hp=500),party=[p],status_rng=sure())
                    self.assertTrue(m.command('Ability',ability_id=lesson.id,target=0))
                    status=PLAYER_AILMENTS[lesson.id][0]
                    self.assertTrue(m.statuses.has(('enemy',0),status));applied.add(status)
        self.assertEqual(applied,{'poison','darkness','silence','frozen'})

    def test_physical_damage_thaws_and_grants_protection(self):
        m=BattleModel(replace(ENEMIES[0],hp=100),party=[hero()]);key=('enemy',0)
        m.statuses.apply(key,'frozen');m.command('Attack')
        self.assertFalse(m.statuses.has(key,'frozen'));self.assertEqual(m.statuses.freeze_guard[key],2)
        self.assertFalse(m.statuses.apply(key,'frozen'))

    def test_remedy_cures_without_healing_and_is_not_wasted(self):
        p=hero();ally=member('Temur',TEMUR)
        m=BattleModel(ENEMIES[0],party=[p,ally],supplies={'Remedy':2});key=('party',1)
        for status in ('poison','frozen','darkness','silence'):m.statuses.apply(key,status)
        hp=ally['hp'];self.assertTrue(m.command('Remedy',target=1))
        self.assertFalse(m.statuses.for_actor(key));self.assertEqual(ally['hp'],hp)
        self.assertEqual(m.statuses.freeze_guard[key],2);self.assertEqual(m.supplies['Remedy'],1)
        m.pending_reply=False;self.assertFalse(m.command('Remedy',target=1));self.assertEqual(m.supplies['Remedy'],1)
        self.assertFalse(apply_supply('Remedy',ally)[0])

    def test_saint_mend_and_litany_cleanse(self):
        for ability in ('saint_mend','saint_litany'):
            p=hero();p.update(job='Saint',researched=[ability]);ally=member('Temur',TEMUR)
            ally['hp']=20
            m=BattleModel(ENEMIES[0],party=[p,ally]);key=('party',1)
            m.statuses.apply(key,'poison');m.statuses.apply(key,'silence')
            self.assertTrue(m.command('Ability',ability_id=ability,target=1))
            self.assertFalse(m.statuses.has(key,'poison'))
            self.assertEqual(m.statuses.has(key,'silence'),ability=='saint_mend')

    def test_enemy_skills_consume_mp_and_silence_blocks_casts(self):
        p=hero();p.update(hp=1000,max_hp=1000)
        m=BattleModel(ENEMIES[0],party=[p],status_rng=sure(),rng=random.Random(1))
        for turn in range(1,7):
            m.pending_reply=True;m.reply()
            self.assertEqual(m.enemy_skill is not None,turn in (2,4))
        self.assertEqual(m.enemy_mp,[0]);self.assertTrue(m.statuses.has(('party',0),'poison'))
        m=BattleModel(ENEMIES[1],party=[p],status_rng=sure())
        m.enemy_turns[0]=1;m.statuses.apply(('enemy',0),'silence')
        m.pending_reply=True;m.reply();self.assertIsNone(m.enemy_skill);self.assertEqual(m.enemy_mp,[ENEMIES[1].mp])
        for foe, name in ((ENEMIES[1], "Echo Screech"), (ENEMIES[2], "Dust Ram")):
            target = hero()
            m = BattleModel(foe, party=[target], status_rng=sure())
            m.enemy_turns[0] = 1
            m.pending_reply = True
            m.reply()
            self.assertEqual(m.enemy_skill.name, name)
            self.assertTrue(m.enemy_skill.animation)
            self.assertGreater(m.damage, 0)
            self.assertFalse(m.statuses.for_actor(("party", 0)))
        m = BattleModel(DEN_MOTHER, party=[hero()], status_rng=sure())
        m.enemy_turns[0] = 3
        m.pending_reply = True
        m.reply()
        self.assertEqual(m.enemy_skill.status, "frozen")
        self.assertTrue(m.statuses.has(("party", 0), "frozen"))

    def test_boss_resists_hard_control_and_poison_is_reduced(self):
        m=ShalehornBattle(SHALEHORN,party=[hero()],status_rng=sure());key=('enemy',0)
        self.assertFalse(m.apply_status(key,'frozen'));self.assertFalse(m.apply_status(key,'silence'))
        self.assertTrue(m.apply_status(key,'poison'));m.begin_ctb();m.ctb.current=key
        self.assertEqual(m.resolve_turn_end(),[(key,3)])

class StatusSceneTests(unittest.TestCase):
    def setUp(self):
        case=test_battle_ui.BattleIntegrationTests();case.setUp();self.addCleanup(case.tearDown)
        self.a=case.app;self.scene=case.app.battle

    def test_frozen_turn_skips_and_next_actor_is_reachable(self):
        m=BattleModel(ENEMIES[0],party=[hero()]);self.scene.start(m,0)
        m.statuses.apply(('party',0),'frozen');self.scene._begin_ctb_actor(0)
        self.assertEqual(self.scene.phase,'frozen_action');self.assertFalse(m.command('Attack'))
        self.scene.update(.7)
        self.assertEqual(m.ctb.completed,1);self.assertFalse(m.statuses.has(('party',0),'frozen'))
        self.assertIn(self.scene.phase,('command','enemy_action'))

    def test_lethal_poison_transitions_through_damage_to_result(self):
        p=hero();p['hp']=1
        m=BattleModel(ENEMIES[0],party=[p]);self.scene.start(m,0)
        m.statuses.apply(('party',0),'poison');self.scene.selection=1;self.scene.confirm(0)
        self.scene.update(.7);self.assertEqual(self.scene.phase,'status_tick')
        self.assertEqual(m.outcome,'defeat')
        self.scene.update(1.3);self.assertEqual(self.scene.phase,'result')

    def test_remedy_item_scrolling_and_status_labels(self):
        m=BattleModel(ENEMIES[0],party=[hero()],supplies={'Remedy':1});self.scene.start(m,0)
        m.statuses.apply(('party',0),'silence');self.scene.draw_status()
        labels=[self.a.canvas.itemcget(i,'text') for i in self.a.canvas.find_withtag('battle_status_labels')]
        self.assertTrue(any('SIL' in x for x in labels))
        self.scene.selection=2;self.scene.confirm(0)
        self.scene.selection=m.item_names().index('Remedy');self.scene.draw_status()
        for i in self.a.canvas.find_withtag(self.scene.DYNAMIC):
            x1,y1,x2,y2=self.a.canvas.bbox(i)
            self.assertLessEqual(y2,self.a.canvas._value(518))
        self.scene.confirm(1);self.scene.confirm(1)
        self.assertFalse(m.statuses.has(('party',0),'silence'));self.assertEqual(m.supplies['Remedy'],0)

if __name__=='__main__':unittest.main()
