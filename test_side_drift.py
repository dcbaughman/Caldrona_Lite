"""Larvel's side drift and its stairwell down."""
import unittest
from collections import deque

import Caldrona_Lite as game
import test_battle_ui
from side_drift import STAIRWELL_TILES


class SideDriftTests(unittest.TestCase):
    def setUp(self):
        self.case = test_battle_ui.BattleIntegrationTests()
        self.case.setUp()
        self.addCleanup(self.case.tearDown)
        self.a = self.case.app

    def test_drift_is_reachable_from_the_shaft(self):
        floor = game.CavernInstance().public_floor
        start, goal = (11, 16), (16, 17)
        queue, seen = deque([start]), {start}
        while queue:
            x, y = queue.popleft()
            for step in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if step in floor and step not in seen and step not in STAIRWELL_TILES:
                    seen.add(step)
                    queue.append(step)
        self.assertIn(goal, seen)
        self.assertTrue(STAIRWELL_TILES <= floor)

    def test_stairwell_blocks_and_can_be_inspected(self):
        a = self.a
        a.x, a.y = 16.5 * 16, 17.5 * 16
        a.direction = "up"
        self.assertFalse(a._can_walk_world(16.5 * 16, 16.5 * 16))
        a._update_interaction_hint()
        self.assertTrue(a.canvas.itemcget(a.interaction_hint, "text").startswith("INSPECT"))
        self.assertTrue(a.side_drift.interact())
        self.assertTrue(a.dialogue.active)
        shown = " ".join(a.canvas.itemcget(item, "text") for item in a.canvas.find_withtag(a.dialogue.TAG)
                         if a.canvas.type(item) == "text")
        self.assertIn("lantern", shown)

    def test_stairwell_is_hidden_outdoors(self):
        a = self.a
        a._update_world(force=True)
        self.assertEqual(a.canvas.itemcget(a.side_drift.item, "state"), "normal")
        a.outdoors = True
        a.side_drift.render(a.world_camera)
        self.assertEqual(a.canvas.itemcget(a.side_drift.item, "state"), "hidden")
        self.assertFalse(a.side_drift.is_stairwell((16, 15)))


if __name__ == "__main__":
    unittest.main()
