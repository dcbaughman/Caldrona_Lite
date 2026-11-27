"""Walking into Windehus from the Sunrest grasslands, around the town, and back out."""
import unittest
from unittest.mock import Mock, patch

from Caldrona_Lite import GRASSLAND_MUSIC
from grassland import FROM_TOWN, KORWARD, TOWN_ROAD
from stats import TEMUR, member
import test_battle_ui
import windehus
from windehus_town import TAG


class WindehusTownTests(unittest.TestCase):
    def setUp(self):
        self.case = test_battle_ui.BattleIntegrationTests()
        self.case.setUp()
        self.addCleanup(self.case.tearDown)
        a = self.a = self.case.app
        a._play_music = Mock()
        a.grass_intro_seen = a.route_map = a.cordon_open = True
        a._change_area(True)
        a.party.append(member("Temur", TEMUR))
        a.encounters.step = Mock(return_value=False)

    def place(self, x, y, direction="down"):
        a = self.a
        a.x, a.y = (x + .5) * 16, (y + .5) * 16
        a.direction = direction
        a._update_world(force=True)

    def step(self, direction):
        self.a.keys = {direction}
        self.a.next_step_at = 0
        self.case.tick()
        self.a.keys = set()
        self.case.tick()

    def walk_in(self):
        self.place(FROM_TOWN[0], FROM_TOWN[1] + 1, "up")
        self.step("up")
        self.assertFalse(self.a.in_town)
        self.step("up")

    def test_the_west_road_runs_north_through_the_cliffs_into_town(self):
        a = self.a
        self.assertIn((FROM_TOWN[0], FROM_TOWN[1] - 1), TOWN_ROAD)
        self.assertIs(a._grassland_tile(7, 2, 0), a.path_tiles[0])
        a._play_music.reset_mock()
        self.walk_in()
        self.assertTrue(a.in_town and a.outdoors)
        self.assertEqual(a._world_tile(), windehus.ARRIVAL)
        self.assertEqual(a.direction, "up")
        self.assertEqual(a.canvas.itemcget(a.location_label, "text"), "Windehus")
        a._play_music.assert_called_with(GRASSLAND_MUSIC)
        self.assertTrue(a.canvas.find_withtag(TAG))
        # Nothing from the fields shows in town.
        for item in (a.merren_item, a.white_stone_item, a.cordon.guard, a.cordon.gate):
            self.assertEqual(a.canvas.itemcget(item, "state"), "hidden")
        # The town is safe: walking it never rolls an encounter.
        a.encounters.step.reset_mock()
        a.encounters.step.return_value = True
        for _ in range(6):
            self.step("up")
        self.assertEqual(a._world_tile(), (windehus.ARRIVAL[0], windehus.ARRIVAL[1] - 6))
        a.encounters.step.assert_not_called()
        self.assertEqual(a.screen, "game")

    def test_walls_and_houses_stop_the_party_and_stairs_do_not(self):
        a = self.a
        self.walk_in()
        self.place(10, 16, "up")     # below the great retaining wall
        self.step("up")
        self.assertEqual(a._world_tile(), (10, 16))
        self.place(19, 16, "up")     # at the foot of the stair up to the mill ridge
        self.step("up")
        self.step("up")
        self.assertEqual(a._world_tile(), (19, 14))
        self.place(5, 13, "up")      # the cottage's stoop, then its door
        self.step("up")
        self.assertEqual(a._world_tile(), (5, 12))
        self.step("up")
        self.assertEqual(a._world_tile(), (5, 12))

    def test_the_party_walks_behind_a_house_and_in_front_of_it(self):
        a = self.a
        self.walk_in()
        house = next(i for i in a.canvas.find_withtag(TAG)
                     if a.canvas.itemcget(i, "image") == str(a.windehus.sprite("bakery")))

        def stacked_above_house(item):
            order = a.canvas.find_all()
            return order.index(item) > order.index(house)

        self.place(7, 31, "up")      # beside the bakery's back wall
        self.assertFalse(stacked_above_house(a.player_item))
        self.place(7, 35, "up")      # out front, past its door row
        self.assertTrue(stacked_above_house(a.player_item))
        # The follower one tile behind is slotted by its own row.
        follower = next(iter(a.field_followers.values()))[0]
        self.assertTrue(stacked_above_house(follower))
        # The interaction hint and the location stay over the town.
        order = a.canvas.find_all()
        self.assertGreater(order.index(a.interaction_hint), order.index(house))
        self.assertGreater(order.index(a.location_label), order.index(house))

    def test_the_sails_turn_and_the_sheep_birds_breathe(self):
        a = self.a
        self.walk_in()
        town = a.windehus
        self.assertIsNotNone(town.sails)
        self.assertEqual(len(town.birds), 3)
        seen_sails, seen_birds = set(), set()
        for tick in range(40):
            town.animate(tick * .1)
            seen_sails.add(a.canvas.itemcget(town.sails, "image"))
            seen_birds.add(a.canvas.itemcget(town.birds[0][0], "image"))
        self.assertEqual(len(seen_sails), 4)
        self.assertEqual(len(seen_birds), 3)

    def test_town_tiles_never_answer_for_the_fields(self):
        a = self.a
        self.walk_in()
        # Korward stands on this tile in the fields; in town it is the lane by the mill.
        self.place(KORWARD[0], KORWARD[1] + 1, "up")
        a._update_interaction_hint()
        self.assertEqual(a.canvas.itemcget(a.interaction_hint, "state"), "hidden")
        a._activate()
        self.assertFalse(a.dialogue.active)
        self.assertEqual(a.screen, "game")

    def test_the_road_south_leads_back_to_the_grasslands(self):
        a = self.a
        self.walk_in()
        self.place(windehus.ROAD_OUT[0] - 1, windehus.HEIGHT - 1, "down")
        self.step("down")
        self.assertTrue(a.in_town)
        self.place(windehus.ROAD_OUT[-1], windehus.HEIGHT - 1, "down")
        a._play_music.reset_mock()
        self.step("down")
        self.assertFalse(a.in_town)
        self.assertTrue(a.outdoors)
        self.assertIs(a.cave, a.grassland_map)
        self.assertEqual(a._world_tile(), FROM_TOWN)
        self.assertEqual(a.direction, "down")
        self.assertFalse(a.canvas.find_withtag(TAG))
        self.assertEqual(a.canvas.itemcget(a.location_label, "text"), "Sunrest Grasslands")
        self.assertEqual(a.canvas.itemcget(a.merren_item, "state"), "normal")
        a._play_music.assert_called()
        # Back on the road, the fields roll encounters again.
        with patch.object(a.encounters, "step", return_value=False) as roll:
            self.step("down")
            roll.assert_called_once()


if __name__ == "__main__":
    unittest.main()
