"""Coverage for weapon families, stone color, and battle FX playback."""
import unittest
from unittest.mock import patch

from abilities import EXTRA_FX, attune, lesson_variant, strike_variant
from battle import BattleModel, ENEMIES
from classes import bind_job
from equipment import CATALOG, Equipment
from player_motion import action_motion
from research import initialize_research, lessons_for
from stats import RETRI, member
import test_battle_ui


class AttackFXTests(unittest.TestCase):
    def test_every_weapon_has_gray_and_blue_frames(self):
        for item in CATALOG.values():
            if item.slot != "weapon":
                continue
            with self.subTest(weapon=item.id):
                actor = {"equipment": {"weapon": item.id}}
                attune(actor)
                gray = strike_variant(actor)
                self.assertEqual(gray.key, "unattuned")
                bind_job(actor, item.jobs[0] if item.jobs else "Saint")
                blue = strike_variant(actor)
                self.assertEqual(blue.key, "first_stone")
                self.assertNotEqual(gray.frames, blue.frames)
                self.assertTrue(all(frame.is_file() for frame in gray.frames + blue.frames))
                actor["job"] = "Unbound"
                self.assertEqual(strike_variant(actor), gray)

    def test_unbound_elemental_effects_keep_fixed_colors(self):
        actor = member("Retri", RETRI)
        attune(actor)
        lessons = {row.id: row for row in lessons_for(actor)}
        for name in ("spark", "quarry_echo", "first_aid"):
            lesson_id = f"unbound_{name}"
            self.assertEqual(lesson_variant(lessons[lesson_id], actor), EXTRA_FX[lesson_id]["untinted"])
        self.assertEqual(lesson_variant(lessons["unbound_quick_cut"], actor).key, "unattuned")

    def test_actor_motion_uses_weapon_family_and_lesson_tags(self):
        actor = member("Retri", RETRI)
        examples = (("training_sword", "sword"), ("pickpocket_dirk", "dagger"),
                    ("bronze_mace", "mace"), ("shalehorn_crook", "staff"),
                    ("bronze_throwing_knife", "throw"), ("yew_seer_wand", "cast_wand"),
                    ("iron_augur_staff", "cast_staff"), ("obsidian_scrying_mirror", "cast_orb"),
                    (None, "fists"))
        for weapon, style in examples:
            with self.subTest(weapon=weapon):
                actor["equipment"] = {"weapon": weapon}
                self.assertEqual(action_motion(actor).style, style)
        lessons = {lesson.id: lesson for lesson in lessons_for(actor)}
        self.assertEqual(lessons["unbound_quick_cut"].actor_motion, "weapon")
        self.assertEqual(lessons["unbound_spark"].actor_motion, "magic")
        self.assertEqual(lessons["unbound_read_stance"].actor_motion, "")
        self.assertEqual(action_motion(actor, "magic").style, "cast_hand")
        self.assertEqual(action_motion(actor, "fists").style, "fists")

    def test_projectile_moves_in_battle_and_quick_cut_plays(self):
        case = test_battle_ui.BattleIntegrationTests()
        case.setUp()
        self.addCleanup(case.tearDown)
        app = case.app
        actor = member("Retri", RETRI)
        actor["equipment"] = {"weapon": "yew_seer_wand"}
        initialize_research(actor)
        actor["researched"].append("unbound_quick_cut")
        battle = app.battle
        battle.start(BattleModel(ENEMIES[0], party=[actor]), 0)
        battle.confirm(0)
        battle.confirm(0)
        variant = battle.attack_fx
        self.assertGreater(variant.travel_ms, 0)
        start_pose = battle.party_image(0)
        windup = battle.player_motion.windup_ms
        battle.update(.125)
        self.assertIsNot(battle.party_image(0), start_pose)
        self.assertFalse(app.canvas.find_withtag("battle_fx"))
        battle.update((windup + 20) / 1000)
        self.assertFalse(app.canvas.find_withtag("damage_number"))
        start = app.canvas.coords(battle._fx_item)
        battle.update((battle.attack_contact_ms + 1) / 1000)
        self.assertLess(app.canvas.coords(battle._fx_item)[0], start[0])
        self.assertTrue(app.canvas.find_withtag("damage_number"))
        battle.close()
        battle.start(BattleModel(ENEMIES[0], party=[actor]), 1)
        battle.selection = battle.COMMANDS.index("Abilities")
        battle.confirm(1)
        battle.confirm(1)
        battle.confirm(1)
        self.assertEqual(battle.phase, "ability_fx")
        self.assertEqual(battle.player_motion.style, "rod")
        battle.update(1 + (battle.ability_contact_ms + 1) / 1000)
        self.assertTrue(app.canvas.find_withtag("battle_fx"))

    def test_sword_windup_and_follow_through_return_to_critical_pose(self):
        case = test_battle_ui.BattleIntegrationTests()
        case.setUp()
        self.addCleanup(case.tearDown)
        scene, canvas = case.app.battle, case.app.canvas
        actor = member("Temur", {**RETRI, "agility": 40})
        actor.update(job="Saint", hp=15, equipment={"weapon": "training_sword"})
        scene.start(BattleModel(ENEMIES[0], party=[actor]), 0)
        critical = scene.party_image(0)
        self.assertEqual(scene.party_pose[0], "critical")
        scene.confirm(0)
        scene.confirm(0)
        scene.update(.13)
        self.assertIs(scene.party_image(0), scene.player_art.frame(actor, "sword", 1))
        self.assertFalse(canvas.find_withtag("damage_number"))
        scene.update(.20)
        self.assertIs(scene.party_image(0), scene.player_art.frame(actor, "sword", 2))
        self.assertTrue(canvas.find_withtag("damage_number"))
        scene.update(.30)
        self.assertIs(scene.party_image(0), scene.player_art.frame(actor, "sword", 3))
        scene.update(.55)
        self.assertIs(scene.party_image(0), critical)

    def test_bow_tracks_the_selected_enemy_and_waits_for_impact(self):
        case = test_battle_ui.BattleIntegrationTests()
        case.setUp()
        self.addCleanup(case.tearDown)
        scene, canvas = case.app.battle, case.app.canvas
        actor = member("Retri", {**RETRI, "agility": 40})
        actor["equipment"] = {"weapon": "practice_bow"}
        initialize_research(actor)
        actor["researched"].append("unbound_quick_cut")
        lesson = next(lesson for lesson in lessons_for(actor) if lesson.id == "unbound_quick_cut")
        item = Equipment("practice_bow", "Practice Bow", "weapon", weapon_type="bow")

        def arrow_tip():
            return canvas.coords("bow_arrow_tip")[:2]

        def status_text():
            return [canvas.itemcget(item, "text") for item in canvas.find_withtag(scene.DYNAMIC)
                    if canvas.type(item) == "text"]

        with patch.dict(CATALOG, {item.id: item}):
            for target, weapon_lesson in ((0, False), (1, False), (1, True)):
                with self.subTest(target=target, weapon_lesson=weapon_lesson):
                    actor["mp"] = RETRI["max_mp"]
                    model = BattleModel(ENEMIES[:2], party=[actor])
                    scene.start(model, 0)
                    target_x, target_y = scene.enemy_positions[target]
                    if weapon_lesson:
                        scene.chosen_ability = lesson
                        model.target = target
                        scene._begin_ability_fx(0)
                    else:
                        scene.confirm(0)
                        scene.click(target_x, target_y, 0)
                    self.assertEqual(model.target, target)
                    self.assertEqual(scene.player_motion.style, "bow")
                    self.assertLess(model.health[target], ENEMIES[target].hp)
                    self.assertEqual(model.health[1-target], ENEMIES[1-target].hp)
                    self.assertIn(f"HP {ENEMIES[target].hp}/{ENEMIES[target].hp}", status_text())

                    release = scene.player_motion.windup_ms / 1000
                    impact = (scene.ability_contact_ms if weapon_lesson else scene.attack_contact_ms) / 1000
                    number_tag = "ability_damage" if weapon_lesson else "damage_number"
                    scene.update(release - .03)
                    self.assertFalse(canvas.find_withtag("bow_arrow"))
                    scene.update(release + .015)
                    launch_x, _ = arrow_tip()
                    scene.update((release + impact) / 2)
                    self.assertGreater(arrow_tip()[0], canvas._value(target_x))
                    self.assertLess(arrow_tip()[0], launch_x)
                    self.assertFalse(canvas.find_withtag(number_tag))

                    scene.update(impact + .001)
                    # Foes bob while idle; the arrow lands on where the target is at impact.
                    target_x, target_y = scene.enemy_positions[target]
                    self.assertEqual(arrow_tip(), [canvas._value(target_x), canvas._value(target_y)])
                    self.assertTrue(canvas.find_withtag("bow_impact"))
                    for item_id in canvas.find_withtag("bow_shot"):
                        self.assertEqual(canvas.type(item_id), "rectangle")
                        x1, y1, x2, y2 = map(canvas.logical_x, canvas.coords(item_id))
                        self.assertAlmostEqual(y2 - y1, 2, delta=12 / canvas.scale_units)
                        self.assertAlmostEqual((x1-target_x)/2, round((x1-target_x)/2),
                                               delta=6 / canvas.scale_units)
                        self.assertAlmostEqual((y1-target_y)/2, round((y1-target_y)/2),
                                               delta=6 / canvas.scale_units)
                    self.assertTrue(canvas.find_withtag(number_tag))
                    self.assertIn(f"HP {model.health[target]}/{ENEMIES[target].hp}", status_text())
                    scene.update(impact + .40)
                    self.assertFalse(canvas.find_withtag("bow_arrow"))
                    scene.close()
