"""Pool counts, explicit commands, executable effects, and animation completeness."""
import unittest
from abilities import learned_abilities, lesson_variant
from battle import BattleModel, BattleScene, ENEMIES
from classes import RIQIZAURKEIS
from research import KIT_MIGRATION, LESSONS, initialize_research, lessons_for
from stats import RETRI, TEMUR, member

class MovePoolTests(unittest.TestCase):
    def test_pool_sizes_and_command_assignment(self):
        # (Abilities, Magic) per 7-move kit in movesets.md.
        expected = {'Seer':(5,2),'Tidecaller':(2,5),'Weaver':(2,5),'Sollers':(5,2),
                    RIQIZAURKEIS:(1,6),'Saint':(2,5)}
        for job, counts in expected.items():
            scene = BattleScene.__new__(BattleScene)
            actor = member('Retri', RETRI)
            actor.update(job=job, researched=[])
            entries = lessons_for(actor)
            self.assertEqual(tuple(sum(x.menu == menu for x in entries) for menu in ('Abilities','Magic')), counts)
            actor["researched"] = [x.id for x in entries]
            scene.model = BattleModel(ENEMIES[0],party=[actor])
            for magic, count in zip((False,True),counts):
                scene.ability_page = "Magic" if magic else "Abilities"
                self.assertEqual(len(scene._menu_abilities()),count)

    def test_every_lesson_has_files_and_executes(self):
        for job, lessons in LESSONS.items():
            for lesson in lessons:
                if lesson.id in KIT_MIGRATION:
                    continue  # old research that now loads as its kit move
                with self.subTest(job=job, move=lesson.id):
                    actor = member('Retri',RETRI)
                    actor.update(job=job, researched=[lesson.id],mp=100,hp=20)
                    for stone in ('unattuned','first_stone'):
                        actor['attuned_stone']=stone
                        variant=lesson_variant(lesson,actor)
                        self.assertIsNotNone(variant)
                        self.assertTrue(all(frame.is_file() for frame in variant.frames))
                        self.assertEqual(sum(variant.ms_per_frame),variant.total_ms)
                    model=BattleModel(ENEMIES[:2],party=[actor, member('Temur',TEMUR)])
                    if lesson.id == 'weaver_closing_verse':
                        model.black_thread = (0, 1, 50)  # Closing Verse needs a thread to detonate
                    target = (0, 1) if lesson.target == "two enemies" else 0
                    self.assertTrue(model.command('Ability',ability_id=lesson.id,target=target))
                    self.assertEqual(actor['mp'],100-lesson.mp if lesson.effect!='restore' else min(actor['max_mp'],100-lesson.mp+lesson.power))

    def test_legacy_seer_research_still_works(self):
        actor=member('Retri',RETRI)
        actor.update(job='Seer',researched=['seer_forewarn','seer_silver_spark'])
        # Old Premonition research now maps to the kit's Forewarn; Gale is kept as already learned.
        self.assertEqual({x.id for x in learned_abilities(actor)}, {'seer_forewarn','seer_gale'})

if __name__ == '__main__':
    unittest.main()
