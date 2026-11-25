"""Regression coverage for the sealed encounter and brood combat."""
from dataclasses import replace
from collections import deque
import math
import random
import time
import unittest
from unittest.mock import Mock, patch

import Caldrona_Lite as game
from battle import (BattleModel, DEN_MOTHER, DEPTHS_ENEMIES, DenMotherBattle, EMBERWRAITH, ENEMIES,
                    SILK_SARCOPHAGUS, SPIDERLING, depths_encounter)
from consumables import SUPPLIES
from classes import NOKTAKORO
from depths import DEN_CHESTS, DEN_HEART_GATE, DEN_NEST_FOOTPRINT, DEN_SHRINE, EGG_SACS, SANCTUM
from loot import BAZAAR
from save_game import capture, validate
from stats import RETRI, TEMUR, member
import test_battle_ui


class DenMotherTests(unittest.TestCase):
    def setUp(self):
        self.retri = member("Retri", RETRI)
        self.temur = member("Temur", TEMUR)
        self.rng = Mock(wraps=random.Random(1))
        self.rng.random.return_value = 0
        self.status_rng = Mock()
        self.status_rng.random.return_value = 0
        self.battle = DenMotherBattle(party=[self.retri, self.temur], rng=self.rng,
                                      status_rng=self.status_rng, supplies={"Remedy": 1})

    def boss_turn(self, attacker=0):
        self.battle.pending_reply = True
        self.battle.reply(attacker)
        return self.battle.enemy_skill

    def test_lost_spirits_join_the_right_encounter_pools(self):
        rng = random.Random(12)
        for danger, expected in ((1, {EMBERWRAITH}), (2, {EMBERWRAITH, SILK_SARCOPHAGUS})):
            spirits = {EMBERWRAITH, SILK_SARCOPHAGUS}
            found = set()
            for _ in range(90):
                foes = depths_encounter(rng, danger, 2)
                self.assertLessEqual(len(foes), 3)
                self.assertTrue(all(foe.sprite != "crawler.png" for foe in foes))
                found.update(foe for foe in foes if foe in spirits)
            self.assertEqual(found, expected)

    def test_emberwraith_rewards_magic_even_against_armor_piercing_attacks(self):
        rng = Mock()
        rng.randint.return_value = 256
        for job in ("Tidecaller", "Seer"):
            hero = member("Retri", RETRI)
            hero.update(job=job, strength=12, magic=5, level=5)
            battle = BattleModel(EMBERWRAITH, party=[hero], rng=rng)
            self.assertTrue(battle.command("Attack"))
            self.assertEqual(battle.damage, 1)

        hero.update(job="Tidecaller", researched=["tidecaller_tide_dart"])
        battle = BattleModel(EMBERWRAITH, party=[hero], rng=rng)
        self.assertTrue(battle.command("Ability", ability_id="tidecaller_tide_dart"))
        self.assertEqual(battle.damage, 14)

    def test_lost_spirits_use_finite_magic_and_have_distinct_fire_affinities(self):
        for foe, move, damage in ((EMBERWRAITH, "Broodfire", 10),
                                  (SILK_SARCOPHAGUS, "Spiral Seal", 25)):
            with self.subTest(foe=foe.name):
                model = BattleModel(foe, party=[member("Retri", RETRI)])
                model._hit_target(20, element="fire")
                self.assertEqual(model.damage, damage)
                model.enemy_turns[0] = 1
                self.assertEqual(model.enemy_intent(0), move)
                model.pending_reply = True
                model.reply(0)
                self.assertTrue(model.enemy_skill.magic)
                self.assertEqual(model.enemy_mp[0], 2)

    def test_escape_uses_living_agility_and_pursuit(self):
        self.assertEqual(self.battle.escape_chance(), 1)
        self.temur["agility"] = 22
        self.assertEqual(self.battle.escape_chance(), 15)
        self.temur["hp"] = 0
        self.assertEqual(self.battle.escape_chance(), 1)
        self.rng.random.return_value = .01
        self.assertTrue(self.battle.command("Flee"))
        self.assertIsNone(self.battle.outcome)
        self.battle.pending_reply = False
        self.rng.random.return_value = .009
        self.assertTrue(self.battle.command("Flee"))
        self.assertEqual(self.battle.outcome, "fled")
        pair = BattleModel([replace(ENEMIES[0], pursuit=100), ENEMIES[1]], party=[self.retri])
        self.assertEqual(pair.escape_chance(), 1)
        pair.health[0] = 0
        self.assertEqual(pair.escape_chance(), 74)

    def test_web_blocks_escape_and_remedy_cures_it(self):
        self.temur["agility"] = 10
        self.assertEqual(self.boss_turn(), self.battle.SPIN_WEB)
        key = ("party", 1)
        self.assertEqual(self.battle.statuses.label(key), "WEB 3")
        self.assertEqual(self.battle.effective_evasion(key), self.temur["evasion"] / 2)
        self.assertNotIn("ailments", self.temur)
        self.assertTrue(self.battle.command("Flee"))
        self.rng.random.assert_not_called()
        self.assertIn("web holds", self.battle.message)
        self.battle.pending_reply = False
        self.assertTrue(self.battle.command("Remedy", target=1))
        self.assertFalse(self.battle.statuses.has(key, "webbed"))
        self.assertGreater(self.battle.escape_chance(), 0)
        self.battle.apply_status(key, "webbed")
        for _ in range(2):
            self.battle.statuses.end_turn(key)
            self.assertTrue(self.battle.statuses.has(key, "webbed"))
        self.battle.statuses.end_turn(key)
        self.assertFalse(self.battle.statuses.has(key, "webbed"))

    def test_gear_immunity_and_fire_weakness(self):
        self.retri["equipment"] = {"armor": "silkweave_coat", "weapon": "embersteel_blade"}
        self.assertEqual(self.boss_turn(), self.battle.SPIN_WEB)
        self.assertIn("Immune", self.battle.message)
        self.assertFalse(self.battle.apply_status(("enemy", 0), "poison"))
        self.rng.randint.return_value = 256
        crit_rng = Mock()
        crit_rng.randint.return_value = 99
        for enemy, expected in ((ENEMIES[0], 15), (ENEMIES[1], 10), (DEN_MOTHER, 14), (SPIDERLING, 20)):
            with self.subTest(enemy=enemy.name):
                model = BattleModel(enemy, party=[self.retri], rng=self.rng, crit_rng=crit_rng)
                self.assertTrue(model.command("Attack"))
                self.assertEqual(model.damage, expected)

    def test_brood_is_inactive_until_summoned_and_feast_heals(self):
        self.battle.begin_ctb()
        self.assertEqual(self.battle.ctb.current, ("enemy", 0))
        self.assertNotIn(("enemy", 1), self.battle.ctb.preview())
        self.assertEqual(self.boss_turn(), self.battle.SPIN_WEB)
        self.battle.finish_ctb_turn()
        self.assertEqual(self.boss_turn(), self.battle.BROOD_CALL)
        self.assertEqual(self.battle.health[1:], [SPIDERLING.hp, SPIDERLING.hp])
        self.assertGreater(self.battle.ctb.ready[("enemy", 1)], self.battle.ctb.tick)
        loss = math.ceil(DEN_MOTHER.hp * .45)
        self.battle._hit_target(loss)
        self.assertEqual(self.battle.stage, 2)
        self.assertEqual(self.boss_turn(), self.battle.SILK_SHROUD)
        self.assertEqual(self.boss_turn(), self.battle.FEAST)
        self.assertGreater(self.battle.health[0], DEN_MOTHER.hp - loss)
        self.assertEqual(self.battle.health[1:], [SPIDERLING.hp, SPIDERLING.hp])

    def test_last_brood_and_death_embrace_have_counterplay(self):
        self.battle._summon()
        low_health = DEN_MOTHER.hp // 5
        self.battle._hit_target(DEN_MOTHER.hp - low_health)
        self.battle.apply_status(("party", 0), "webbed")
        self.assertEqual(self.boss_turn(), self.battle.LAST_BROOD)
        self.assertEqual(self.battle.brood_consumed, (1, 2))
        self.assertEqual(self.battle.health, [low_health + 2 * math.ceil(DEN_MOTHER.hp * .05), 0, 0])
        self.assertEqual(self.battle.stage, 3)
        self.assertEqual(self.boss_turn(), self.battle.DEATH_TELL)
        self.assertIn("Retri", self.battle.enemy_intent(0))
        self.battle.guarded.add(0)
        self.assertEqual(self.boss_turn(), self.battle.DEATH_EMBRACE)
        enraged = self.battle.EMBRACE_DAMAGE * self.battle.ENRAGED_DAMAGE_PERCENT // 100
        self.assertEqual(self.battle.damage, (enraged - self.retri["defense"]) // 2)
        self.battle.embrace_target = 0
        self.battle.statuses.cure(("party", 0))
        self.assertEqual(self.boss_turn(), self.battle.FANG_STRIKE)


class DenLairTests(unittest.TestCase):
    def setUp(self):
        self.case = test_battle_ui.BattleIntegrationTests()
        self.case.setUp()
        self.addCleanup(self.case.tearDown)
        self.app = self.case.app

    def move_to(self, tile, direction):
        a = self.app
        a.x, a.y = ((coord + .5) * game.TILE for coord in tile)
        a.direction = direction
        a._update_world(force=True)

    def test_gate_stays_sealed_and_hides_the_lair_on_the_main_route(self):
        a = self.app
        self.move_to(game.DEN_APPROACH, "up")
        web, = a.canvas.find_withtag("den_decor")
        self.assertEqual(a.canvas.type(web), "image")
        self.assertTrue(a.den_gate_web.transparency_get(0, 0))
        self.assertEqual(a.canvas.itemcget(a.den_spider_item, "state"), "hidden")
        self.assertNotIn(game.DEN_DOOR, a.cave.floor)
        for x, y in game.DEN_FLOOR:
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                self.assertNotIn((x + dx, y + dy), a.cave.public_floor)
        position = (a.x, a.y)
        a._activate()
        self.assertTrue(a.dialogue.active)
        self.assertEqual((a.x, a.y), position)
        self.assertFalse(a.cave_story["den_unsealed"])

    def test_reserved_lair_path_runs_boss_and_persists_black_stone(self):
        a = self.app
        self.move_to(game.DEN_APPROACH, "up")
        a.cave_story["den_unsealed"] = True  # Already unsealed; this test covers the lair path.
        self.assertTrue(a._interact_den())
        self.assertTrue(a._in_den())
        self.assertEqual(a.canvas.itemcget(a.location_label, "text"), "Den Mother's Lair")
        self.assertEqual(a.canvas.itemcget(a.den_spider_item, "state"), "normal")
        self.assertEqual(a.den_gaze_frames[0].width(), 2 * game.TILE * game.SCALE)
        self.assertEqual(a._area_music(), game.DEN_MUSIC)
        distance = {game.DEN_ENTRY: 0}
        route = deque([game.DEN_ENTRY])
        while route:
            x, y = route.popleft()
            for dx, dy in game.DIRECTIONS.values():
                tile = (x + dx, y + dy)
                if tile not in distance and a._can_walk_world(*((v + .5) * game.TILE for v in tile)):
                    distance[tile] = distance[x, y] + 1
                    route.append(tile)
        self.assertGreaterEqual(distance[(game.DEN_NEST[0], game.DEN_NEST[1]+1)], 65)
        self.assertNotIn(DEN_HEART_GATE, distance)
        self.assertTrue(SANCTUM.isdisjoint(distance))
        self.assertTrue(DEN_NEST_FOOTPRINT.isdisjoint(distance))

        self.move_to((61, 52), "down")
        self.assertEqual(a.canvas.itemcget(a.den_spider_item, "image"), str(a.canvas._image(a.den_gaze_frames[0])))
        a.keys = {"down"}
        self.case.tick()
        self.assertEqual(a._world_tile(), (61, 53))
        self.assertEqual(a.screen, "den_intro")
        self.assertFalse(a.dialogue.active)
        self.assertFalse(a.keys)
        with patch.object(game.time, "monotonic", return_value=a.den_intro_started + .56):
            self.case.tick()
        self.assertNotEqual(a.world_camera, a.den_intro_origin)
        self.assertEqual(a.canvas.itemcget(a.den_spider_item, "image"), str(a.canvas._image(a.den_gaze_frames[1])))
        with patch.object(game.time, "monotonic", return_value=a.den_intro_started + .86):
            self.case.tick()
        self.assertEqual(a.world_camera, a.den_intro_goal)
        self.assertEqual(a.canvas.itemcget(a.den_spider_item, "image"), str(a.canvas._image(a.den_gaze_frames[2])))
        with patch.object(game.time, "monotonic", return_value=a.den_intro_started + game.DEN_INTRO_SECONDS + .1):
            self.case.tick()
        self.assertEqual(a.screen, "battle_in")
        a._update_battle_transition(time.monotonic() + 2)
        self.assertIsInstance(a.battle.model, DenMotherBattle)
        self.assertIs(a.battle.glow_frames, a.battle.depths_backgrounds[0])
        self.assertEqual(a.canvas.itemcget(a.battle.enemy_items[1], "state"), "hidden")
        a.battle.update(time.monotonic() + 3)
        web, = a.canvas.find_withtag("battle_webbed")
        self.assertEqual(a.canvas.type(web), "image")
        self.assertEqual(a.canvas.itemcget(web, "image"), str(a.canvas._image(a.battle.webbed_sprite)))
        a.battle.model._hit_target(DEN_MOTHER.hp)
        self.assertEqual(a.battle.model.outcome, "victory")
        a._finish_battle("victory")
        a._update_battle_transition(time.monotonic() + 2)
        self.assertTrue(a.cave_story["den_cleared"])
        self.assertIsNone(a.den_intro_camera)
        self.assertFalse(a._start_den_intro((62, 53), time.monotonic()))
        self.assertFalse(a.boss_cleared)
        self.assertEqual(a.canvas.itemcget(a.den_spider_item, "state"), "hidden")
        self.assertEqual(a.gear_inventory["broodguard_seal"], 1)
        self.assertTrue(a._can_walk_world(*((v + .5) * game.TILE for v in DEN_HEART_GATE)))
        self.move_to((game.DEN_STONE[0], game.DEN_STONE[1] + 1), "up")
        self.assertTrue(a.chunk_items)
        self.assertTrue(any(row * game.CHUNK_TILES >= a.cavern_map.height for _, row in a.chunk_items))
        self.assertEqual(a.canvas.itemcget(a.quarry_objects[1][2], "state"), "hidden")
        rp = a.party[0]["rp"]
        self.assertTrue(a._interact_den())
        self.assertTrue(a.cave_story["black_stone_attuned"])
        self.assertEqual(a.astral_scene.stone, NOKTAKORO)
        self.assertEqual(a.astral_scene.phase, "reveal")
        self.assertEqual(a.party[0]["rp"], rp + 4)
        self.assertEqual(a.canvas.itemcget(a.den_stone_item, "state"), "normal")
        saved = validate(capture(a))
        a._load_journey(saved)
        self.assertTrue(a.cave_story["black_stone_attuned"])
        self.assertTrue(a._interact_den())
        self.assertEqual(a.party[0]["rp"], rp + 4)
        self.assertEqual(a.canvas.itemcget(a.den_stone_item, "state"), "normal")
        story = saved["cave_story"]
        story["black_stone_claimed"] = story.pop("black_stone_attuned")
        a._load_journey(saved)
        self.assertTrue(a.cave_story["black_stone_attuned"])
        self.move_to(game.DEN_ENTRY, "down")
        self.assertTrue(a._interact_den())
        self.assertFalse(a._in_den())
        self.assertEqual(a._area_music(), game.CAVERN_MUSIC)

    def test_noktakoro_chest_loot_persists_and_only_drops_once(self):
        a = self.app
        a.cave_story.update(den_unsealed=True, den_cleared=True)
        tile = (81, 59)
        x, y = tile
        self.move_to((x - 1, y), "right")
        a._activate()
        self.assertIn(DEN_CHESTS[tile][0], a.cave_story["depths_chests"])
        self.assertEqual(a.supplies["Ember Talisman"], 1)
        a._load_journey(validate(capture(a)))
        self.assertEqual(a.canvas.itemcget(a.den_chest_items[tile], "image"), str(a.canvas._image(a.chest_images[1])))
        a._activate()
        self.assertEqual(a.supplies["Ember Talisman"], 1)

    def test_roaming_battle_is_repeatable_and_deep_shrine_is_accessible(self):
        a = self.app
        a.cave_story["den_unsealed"] = True
        self.move_to((71, 24), "right")
        self.assertTrue(a._in_den())
        for backdrop in a.battle.depths_backgrounds:
            self.move_to((71, 24), "right")
            a.keys = {"right"}
            a.next_step_at = 0
            with patch.object(a.encounters, "step", return_value=True) as roll:
                self.case.tick()
                roll.assert_called_once_with(chance=.16)
            a._update_battle_transition(time.monotonic() + 2)
            self.assertNotIsInstance(a.battle.model, DenMotherBattle)
            self.assertTrue(set(a.battle.model.enemies).issubset(DEPTHS_ENEMIES))
            self.assertIs(a.battle.glow_frames, backdrop)
            a.battle.update(a.battle.glow_started + .5)
            self.assertEqual(a.canvas.itemcget(a.battle.backdrop_item, "image"),
                             str(a.canvas._image(backdrop[1])))
            a._finish_battle("fled")
            a._update_battle_transition(time.monotonic() + 2)
            self.assertEqual(a._area_music(), game.DEN_MUSIC)
        x, y = DEN_SHRINE
        self.move_to((x, y + 1), "up")
        a._activate()
        self.assertEqual(a.screen, "save_slots")
        self.assertEqual(len(a.den_egg_items), len(EGG_SACS))
        for art in a.den_egg_art:
            self.assertEqual((art.width(), art.height()), (32 * game.SCALE, 32 * game.SCALE))
        corner = a.den_egg_art[2].subsample(game.SCALE)
        occupied = {(x, y) for y in range(32) for x in range(32) if not corner.transparency_get(x, y)}
        self.assertTrue(occupied)
        self.assertTrue(all(8 <= x < 24 and 16 <= y < 32 for x, y in occupied))

    def test_sarcophagus_hovers_and_broodfire_uses_its_ember_palette(self):
        a = self.app
        model = BattleModel([EMBERWRAITH, SILK_SARCOPHAGUS], party=a.party, rng=random.Random(1))
        a.battle.start(model, 0, in_depths=True)
        _, y = a.battle.enemy_positions[1]
        a.battle.update(math.pi / 6)
        self.assertEqual(a.battle.enemy_positions[1][1], y + 3)
        self.assertEqual(a.canvas.coords(a.battle.enemy_items[1])[1], a.canvas._value(y + 3))
        model.ctb.current = ("enemy", 0)
        model.enemy_turns[0] = 1
        a.battle._begin_ctb_actor(1)
        a.battle.update(1.34)
        self.assertEqual(a.battle._enemy_variant.key, "ember")
        self.assertIsNotNone(a.battle._fx_item)

    def test_last_brood_wraps_and_reels_in_spiderlings_then_keeps_the_dark_pose(self):
        from brood_fx import BROOD_DURATION, BroodSilk

        a = self.app
        scene = a.battle
        model = DenMotherBattle(party=a.party, rng=random.Random(1))
        scene.start(model, 0, in_depths=True)
        model._summon()
        scene._sync_brood()
        spiderling = scene.enemy_items[1]
        position = a.canvas.coords(spiderling)
        spider_image = a.canvas.itemcget(spiderling, "image")
        model._hit_target(DEN_MOTHER.hp - DEN_MOTHER.hp // 5)
        model.ctb.current = ("enemy", 0)
        scene._begin_ctb_actor(1)
        self.assertEqual(scene.phase, "last_brood")
        self.assertEqual(a.canvas.itemcget(spiderling, "state"), "normal")

        scene.update(1.24)
        self.assertTrue(a.canvas.find_withtag(BroodSilk.TAG))
        self.assertEqual(a.canvas.coords(spiderling), position)
        scene.update(1.62)
        self.assertTrue(a.canvas.find_withtag(BroodSilk.WRAP_TAG))
        self.assertEqual(a.canvas.itemcget(spiderling, "image"), spider_image)
        scene.update(1.94)
        self.assertNotEqual(a.canvas.coords(spiderling), position)
        self.assertNotEqual(a.canvas.itemcget(spiderling, "image"), spider_image)
        self.assertTrue(a.canvas.find_withtag(BroodSilk.TAG))
        initial = sum(scene.enemy_image(0).get(70, 40))
        scene.update(3.08)
        self.assertEqual(a.canvas.itemcget(spiderling, "state"), "hidden")
        self.assertFalse(a.canvas.find_withtag(BroodSilk.TAG))
        middle = sum(scene.enemy_image(0).get(70, 40))
        self.assertLess(middle, initial)
        scene.update(1 + BROOD_DURATION + .01)
        self.assertNotEqual(scene.phase, "last_brood")
        final = sum(scene.enemy_image(0).get(70, 40))
        self.assertLess(final, middle)
        self.assertEqual(model.brood_consumed, (1, 2))

    def test_merren_sells_both_pieces_without_den_loot(self):
        a = self.app
        a.materials_sold = {"Spider Silk": 3, "Echo Wing": 2, "Shale Chip": 3}
        a.gold = 200
        a._open_merren_shop()
        a._change_shop_tab(-1)
        for key in ("silkweave_coat", "embersteel_blade"):
            a.shop_selection = tuple(BAZAAR).index(key)
            a._buy_supply()
            self.assertEqual(a.gear_inventory[key], 1)

    def _dialogue_text(self):
        return " ".join(
            self.app.canvas.itemcget(item, "text")
            for item in self.app.canvas.find_withtag("dialogue")
            if self.app.canvas.type(item) == "text"
        )

    def test_gate_stays_sealed_without_a_torch(self):
        a = self.app
        self.move_to(game.DEN_APPROACH, "up")
        self.assertEqual(a.supplies.get("Pitch Torch", 0), 0)
        web, = a.canvas.find_withtag("den_decor")
        self.assertEqual(a.canvas.type(web), "image")
        position = (a.x, a.y)
        a._activate()
        self.assertTrue(a.dialogue.active)
        self.assertIn("Silk binds the gate to the rock", self._dialogue_text())
        self.assertEqual((a.x, a.y), position)
        self.assertFalse(a.cave_story["den_unsealed"])
        while a.dialogue.active:
            a._activate()
        # The hint is a second page; after dismissing it the gate is still sealed.
        self.assertFalse(a.cave_story["den_unsealed"])
        web, = a.canvas.find_withtag("den_decor")
        self.assertEqual(a.canvas.type(web), "image")

    def test_hint_mentions_fire_when_the_gate_is_sealed(self):
        a = self.app
        self.move_to(game.DEN_APPROACH, "up")
        a._activate()
        self.assertIn("Silk binds the gate", self._dialogue_text())
        a._activate()
        self.assertIn("Maybe fire would loosen it.", self._dialogue_text())
        self.assertFalse(a.cave_story["den_unsealed"])

    def test_torch_burns_the_silk_and_is_spent(self):
        a = self.app
        a.supplies["Pitch Torch"] = 2
        self.move_to(game.DEN_APPROACH, "up")
        web, = a.canvas.find_withtag("den_decor")
        self.assertEqual(a.canvas.type(web), "image")
        position = (a.x, a.y)
        a._activate()
        self.assertTrue(a.cave_story["den_unsealed"])
        self.assertEqual(a.supplies["Pitch Torch"], 1)
        self.assertTrue(a.dialogue.active)
        self.assertIn("Silk burns away", self._dialogue_text())
        self.assertEqual((a.x, a.y), position)
        self.assertFalse(a._in_den())
        self.assertFalse(a.canvas.find_withtag("den_decor"))
        while a.dialogue.active:
            a._activate()
        a._activate()
        self.assertTrue(a._in_den())

    def test_merren_sells_a_pitch_torch_on_supplies(self):
        a = self.app
        a.gold = 20
        a._open_merren_shop()
        self.assertEqual(a.shop_tab, 0)
        self.assertIn("Pitch Torch", SUPPLIES)
        self.assertEqual(SUPPLIES["Pitch Torch"][0], 8)
        self.assertFalse(SUPPLIES["Pitch Torch"][1] == "")
        a.shop_selection = tuple(SUPPLIES).index("Pitch Torch")
        a._buy_supply()
        self.assertEqual(a.supplies.get("Pitch Torch"), 1)
        self.assertEqual(a.gold, 12)
        # No material lock: a second torch can be bought immediately.
        a._buy_supply()
        self.assertEqual(a.supplies["Pitch Torch"], 2)
        self.assertEqual(a.gold, 4)

    def test_den_unsealed_survives_save_and_load(self):
        a = self.app
        a.supplies["Pitch Torch"] = 1
        self.move_to(game.DEN_APPROACH, "up")
        a._activate()
        self.assertTrue(a.cave_story["den_unsealed"])
        self.assertEqual(a.supplies["Pitch Torch"], 0)
        a._load_journey(validate(capture(a)))
        self.assertTrue(a.cave_story["den_unsealed"])
        self.assertEqual(a.supplies.get("Pitch Torch", 0), 0)
        self.move_to(game.DEN_APPROACH, "up")
        self.assertFalse(a.canvas.find_withtag("den_decor"))
        a._activate()
        self.assertTrue(a._in_den())
