"""Larvel's sidequest in the Old Workings: map, trail, door, mini-boss, rewards and saves."""
import time
import unittest
from collections import deque
from copy import deepcopy

import Caldrona_Lite as game
import test_battle_ui
import lower_workings as w
from battle import EMBER_WYVERN, EmberWyvernBattle
from depths import DEN_FLOOR
from research import LESSONS, SELVAR_ANALECT, research_status
from save_game import SaveError, capture, validate
from stats import RETRI, member

TILE = 16


def reachable(floor, start, blocked=frozenset()):
    queue, seen = deque([start]), {start}
    while queue:
        x, y = queue.popleft()
        for step in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if step in floor and step not in seen and step not in blocked:
                seen.add(step)
                queue.append(step)
    return seen


def neighbours(tile):
    x, y = tile
    return {(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)}


class WorkingsMapTests(unittest.TestCase):
    def test_workings_are_their_own_island(self):
        cave = game.CavernInstance()
        self.assertFalse(w.WORKINGS_FLOOR & cave.public_floor)
        self.assertFalse(w.WORKINGS_FLOOR & DEN_FLOOR)
        self.assertTrue(w.WORKINGS_FLOOR <= cave.floor)
        # Two rock rows above every floor tile keep the tall walls intact.
        top = min(y for _, y in w.WORKINGS_FLOOR)
        self.assertGreater(top - 2, max(y for _, y in cave.public_floor))

    def test_every_page_and_stone_is_reachable_and_the_door_seals_the_refuge(self):
        props = ({spot for spot, _, _ in w.PAGES.values()} | {spot for spot, _, _ in w.RUBBINGS.values()}
                 | w.STAIR_UP_TILES | {w.CACHE, w.HESK_REFUGE})
        closed = reachable(w.CLOSED_FLOOR, w.ARRIVAL, props)
        for spot in props - {w.HESK_REFUGE}:
            self.assertTrue(neighbours(spot) & closed, spot)
        self.assertNotIn(w.HESK_REFUGE, set().union(*(neighbours(t) for t in closed)))
        opened = reachable(w.OPEN_FLOOR, w.ARRIVAL, props)
        self.assertTrue(neighbours(w.HESK_REFUGE) & opened)

    def test_main_pages_and_stones_never_need_a_side_branch(self):
        side_rooms = {name: tiles for name, tiles in w.ROOM_TILES
                      if name in ("Bad-Air Drift", "Sump", "Foreman's Cache")}
        for key in w.MAIN_PAGES:
            spot = w.PAGES[key][0]
            self.assertFalse(any(spot in tiles for tiles in side_rooms.values()), key)
        for key in w.MAIN_RUBBINGS:
            spot = w.RUBBINGS[key][0]
            self.assertFalse(any(spot in tiles for tiles in side_rooms.values()), key)
        self.assertEqual(len(w.MAIN_RUBBINGS), 3)

    def test_grey_floor_scars_the_gallery_wanders_the_halls_and_dots_the_workings(self):
        rooms = dict(w.ROOM_TILES)
        grey = set(w.GREY_MASKS)
        self.assertTrue(grey <= w.OPEN_FLOOR)
        self.assertTrue(all(1 <= mask <= 15 for mask in w.GREY_MASKS.values()))
        gallery = rooms["Knocking Gallery"]
        # The gallery is scarred, but not filled wall to wall like a recoloured room.
        self.assertGreater(len(grey & gallery), len(gallery) // 3)
        self.assertLess(len(grey & gallery), len(gallery))
        # Partial masks give the patches ragged edges instead of tile-square ones.
        self.assertTrue(any(mask != 15 for tile, mask in w.GREY_MASKS.items() if tile in gallery))
        halls = w.OPEN_FLOOR - set().union(*rooms.values())
        self.assertTrue(grey & halls)
        self.assertGreaterEqual(sum(bool(grey & tiles) for name, tiles in rooms.items()
                                    if name != "Knocking Gallery"), 4)


class WorkingsPlayTests(unittest.TestCase):
    def setUp(self):
        self.case = test_battle_ui.BattleIntegrationTests()
        self.case.setUp()
        self.addCleanup(self.case.tearDown)
        self.a = self.case.app
        self.lw = self.a.lower_workings

    def stand(self, tile, direction):
        a = self.a
        a.x, a.y = (tile[0] + .5) * TILE, (tile[1] + .5) * TILE
        a.direction = direction
        a.chunk_cache.clear()
        a._update_world(force=True)

    def finish_dialogue(self):
        while self.a.dialogue.active:
            self.a.dialogue.advance()

    def shown(self):
        c = self.a.canvas
        return " ".join(c.itemcget(item, "text") for item in c.find_withtag(self.a.dialogue.TAG)
                        if c.type(item) == "text")

    def test_larvel_starts_the_quest_and_the_stair_leads_down_and_back(self):
        a = self.a
        self.stand((18, 16), "right")
        self.assertFalse(a._can_walk_world(19.5 * TILE, 16.5 * TILE))
        a._update_interaction_hint()
        self.assertTrue(a.canvas.itemcget(a.interaction_hint, "text").startswith("TALK"))
        self.assertTrue(self.lw.interact())
        self.assertIn("lamp down there", self.shown())
        self.finish_dialogue()
        self.assertEqual(self.lw.stage, "started")

        self.stand((16, 17), "up")
        a._update_interaction_hint()
        self.assertTrue(a.canvas.itemcget(a.interaction_hint, "text").startswith("DESCEND"))
        self.assertTrue(self.lw.interact())
        self.finish_dialogue()
        self.assertEqual(a._world_tile(), w.ARRIVAL)
        self.assertTrue(self.lw.here())
        self.assertTrue(a.canvas.itemcget(a.location_label, "text").startswith("Lower Workings"))
        self.assertEqual(a.canvas.itemcget(a.cave_objective, "text"), "Find Larvel's crew")
        # The workings and the cavern never mix underfoot.
        self.assertFalse(a._can_walk_world(10.5 * TILE, 16.5 * TILE))
        self.assertTrue(a._can_walk_world(9.5 * TILE, 48.5 * TILE))

        self.stand((8, 48), "up")
        self.assertTrue(self.lw.interact())
        self.assertEqual(a._world_tile(), w.DRIFT_RETURN)
        self.assertFalse(self.lw.here())

    def test_pages_rubbings_and_the_door(self):
        a, s = self.a, self.lw.state
        s["stage"] = "started"
        rubbing = w.RUBBINGS["r1"][0]
        self.stand((rubbing[0], rubbing[1] + 1), "up")
        a._activate()
        self.finish_dialogue()
        self.assertFalse(s["rubbings"])
        self.stand((w.CHARCOAL[0], w.CHARCOAL[1] + 1), "up")
        a._activate()
        self.finish_dialogue()
        self.assertTrue(s["charcoal"])
        s["knocker"] = True
        p1 = w.PAGES["p1"][0]
        self.stand((p1[0], p1[1] + 1), "up")
        self.assertTrue(self.lw.interact())
        self.assertIn("Bad air down the east drift", self.shown())
        self.finish_dialogue()
        self.assertEqual(s["pages"], ["p1"])

        self.stand((31, 68), "up")
        self.lw.interact()
        self.assertIn("shut tight", self.shown())
        self.finish_dialogue()
        s["pages"].append("p4")
        s["rubbings"] = ["r1", "r2"]
        self.lw.interact()
        self.assertIn("I can read 2 of", self.shown())
        self.finish_dialogue()
        self.assertEqual(self.lw.stage, "started")

        r3 = w.RUBBINGS["r3"][0]
        self.stand((r3[0], r3[1] + 1), "up")
        self.lw.interact()
        self.finish_dialogue()
        self.stand((31, 68), "up")
        self.lw.interact()
        self.finish_dialogue()
        self.assertEqual(self.lw.stage, "rescued")
        self.assertTrue(a._can_walk_world(31.5 * TILE, 67.5 * TILE))

    def test_every_rubbing_binds_the_selvar_analect(self):
        s = self.lw.state
        s["charcoal"] = True
        s["rubbings"] = [key for key in w.RUBBINGS if key != "r6"]
        spot = w.RUBBINGS["r6"][0]
        self.stand((spot[0], spot[1] + 1), "up")
        self.lw.interact()
        self.finish_dialogue()
        self.assertEqual(self.a.analects.get(SELVAR_ANALECT), 1)
        ward = next(x for x in LESSONS["Unbound"] if x.id == "unbound_sleepers_ward")
        retri = member("Retri", RETRI)
        retri["level"] = 6
        self.assertEqual(research_status(retri, ward, {}), "Find Selvar Analect")
        self.assertNotEqual(research_status(retri, ward, self.a.analects), "Find Selvar Analect")

    def test_the_ember_wyvern_wakes_once_and_leaves_a_burrow(self):
        a, s = self.a, self.lw.state
        s["stage"] = "started"
        self.stand((11, 72), "right")
        self.assertFalse(self.lw.on_step((11, 72), 0))
        self.stand((12, 72), "right")
        self.assertTrue(self.lw.on_step((12, 72), 0))
        self.assertTrue(self.lw.boss_pending)
        self.finish_dialogue()
        # The floor ruptures first: red cracks, heat at the edges, rocks flung up.
        self.assertEqual(a.screen, "workings_rupture")
        started = self.lw.rupture["started"]
        self.lw.update_rupture(started + w.RUPTURE_BURST_AT + .3)
        self.assertEqual(a.screen, "workings_rupture")
        self.assertTrue(a.canvas.find_withtag("workings_rupture"))
        self.lw.update_rupture(started + w.RUPTURE_SECONDS + .01)
        self.assertFalse(a.canvas.find_withtag("workings_rupture"))
        self.assertEqual(a.screen, "battle_in")
        a._update_battle_transition(started + w.RUPTURE_SECONDS + 1.5)
        model = a.battle.model
        self.assertIsInstance(model, EmberWyvernBattle)
        self.assertEqual(model.enemies, [EMBER_WYVERN])
        self.assertEqual(model.enemy.loot.rank, "Boss")
        self.assertFalse(self.lw.boss_pending)
        self.lw.finish_battle(model, "fled")
        self.assertEqual(a._world_tile(), w.KNOCKER_RETREAT)
        self.lw.finish_battle(model, "victory")
        self.assertTrue(s["knocker"])
        self.assertFalse(self.lw.on_step((14, 72), 0))
        self.assertTrue(self.lw.blocked(w.CRACK))

    def test_workings_and_wyvern_songs_play_once_they_are_added(self):
        from unittest.mock import patch
        from pathlib import Path
        a = self.a
        self.stand(w.ARRIVAL, "down")
        with patch.object(Path, "exists", return_value=False):
            self.assertEqual(a._area_music(), game.CAVERN_MUSIC)
        with patch.object(Path, "exists", return_value=True):
            self.assertEqual(a._area_music(), game.WORKINGS_MUSIC)
        self.stand((18, 16), "right")
        with patch.object(Path, "exists", return_value=True):
            self.assertEqual(a._area_music(), game.CAVERN_MUSIC)

    def test_returning_the_crew_gives_the_pit_lantern_and_sends_them_home(self):
        a, s = self.a, self.lw.state
        s.update(stage="rescued", pages=list(w.PAGES), knocker=True)
        a.cave_story["entrance_collapsed"] = True
        self.stand((18, 17), "right")
        self.assertTrue(self.lw.interact())
        a._back()
        self.assertFalse(a.gear_inventory.get(w.PIT_LANTERN))
        self.assertTrue(self.lw.interact())
        seen = []
        while a.dialogue.active:
            seen.append(self.shown())
            a.dialogue.advance()
        self.assertTrue(any("slashed mark" in line for line in seen))
        self.assertTrue(any("Sunrest" in line for line in seen))
        self.assertEqual(self.lw.stage, "complete")
        self.assertEqual(a.gear_inventory.get(w.PIT_LANTERN), 1)
        self.assertFalse(a.cave_story["entrance_collapsed"])
        self.assertEqual(a.canvas.itemcget(self.lw.larvel_item, "state"), "hidden")
        self.assertTrue(a._can_walk_world(19.5 * TILE, 16.5 * TILE))
        self.stand(w.ENTRANCE_LANDING, "up")
        a._activate()
        self.assertEqual(a._world_tile(), w.SHORTCUT_LANDING)
        a._load_journey(validate(capture(a)))
        self.stand(w.SHORTCUT_LANDING, "up")
        a._activate()
        self.assertEqual(a._world_tile(), w.ENTRANCE_LANDING)
        self.assertEqual(a.gear_inventory.get(w.PIT_LANTERN), 1)

    def test_all_ember_wyvern_forms_fit_inside_the_battlefield(self):
        from battle import FIELD_HEIGHT
        scene = self.a.battle
        model = EmberWyvernBattle(party=[member("Retri", RETRI)])
        scene.start(model, 0)
        buried_height = scene.enemy_image(0).height()
        for stage in range(1, 4):
            with self.subTest(stage=stage):
                if stage > 1:
                    model.enemy_hp = model.enemy.hp * (4 - stage) // 3
                    started = 3 * stage
                    scene._end_action(started)
                    self.assertEqual(scene.phase, "wyvern_reveal")
                    self.assertEqual(model.stage, stage)
                    scene.update(started + .59)
                    self.assertTrue(self.a.canvas.find_withtag("wyvern_effect"))
                    scene.update(started + 2)
                image = scene.enemy_image(0)
                x, y = scene.enemy_positions[0]
                self.assertGreaterEqual(image.width(), 350)
                self.assertGreaterEqual(x - image.width() / 2, 0)
                self.assertLess(x + image.width() / 2, scene.party_positions[0][0])
                self.assertGreaterEqual(y - image.height() / 2, 0)
                self.assertLessEqual(y + image.height() / 2, FIELD_HEIGHT)
                if stage > 1:
                    self.assertGreater(image.height(), buried_height)
        self.assertEqual(self.a.canvas.itemcget(scene.wyvern_floor_item, "state"), "normal")
        self.assertFalse(self.a.canvas.find_withtag("wyvern_rubble"))
        scene.close()

    def test_already_opened_foreman_cache_gives_two_cinder_coats_once(self):
        a, state = self.a, self.lw.state
        state.update(stage="started", cache=True)
        state.pop("cinder_coats")
        self.stand((w.CACHE[0], w.CACHE[1] - 1), "down")
        a._activate()
        self.assertIn("Cinder Coat", self.shown())
        self.finish_dialogue()
        self.assertEqual(a.gear_inventory["cinder_coat"], 2)
        a._load_journey(validate(capture(a)))
        self.stand((w.CACHE[0], w.CACHE[1] - 1), "down")
        a._activate()
        self.finish_dialogue()
        self.assertEqual(a.gear_inventory["cinder_coat"], 2)

    def test_saves_keep_and_check_workings_progress(self):
        s = self.lw.state
        s.update(stage="started", pages=["p1", "o2"], rubbings=["r1"], knocker=True)
        state = capture(self.a)
        validate(deepcopy(state))
        bad = deepcopy(state)
        bad["cave_story"]["workings"]["pages"] = ["p9"]
        with self.assertRaises(SaveError):
            validate(bad)
        bad = deepcopy(state)
        bad["cave_story"]["workings"]["stage"] = "lost"
        with self.assertRaises(SaveError):
            validate(bad)


if __name__ == "__main__":
    unittest.main()
