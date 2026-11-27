"""The rooms inside Windehus: their layout, their furniture and how they join the town."""
import json
import unittest
from collections import deque
from pathlib import Path

import windehus
import windehus_rooms as r

TOWN = Path(__file__).resolve().parent / "assets" / "town"
ROOMS = TOWN / "rooms"


def _sizes(path):
    spots = json.loads(path.read_text(encoding="utf-8"))
    return {name: (w, h) for name, (_, _, w, h) in spots.items()}


class RoomLayoutTests(unittest.TestCase):
    def setUp(self):
        self.sizes = _sizes(ROOMS / "furniture.json")
        self.town_sizes = _sizes(TOWN / "tileset.json")

    def reachable(self, room):
        floor = r.floor(room, self.sizes)
        start = r.arrival(room)
        seen, queue = {start}, deque([start])
        while queue:
            x, y = queue.popleft()
            for step in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if step in floor and step not in seen:
                    seen.add(step)
                    queue.append(step)
        return floor, seen

    def test_the_inn_the_three_shops_and_the_mill_open(self):
        self.assertEqual(set(r.ROOMS), {"inn", "weapons", "armour", "goods", "mill"})
        entrances = r.entrances(self.town_sizes)
        self.assertEqual(sorted(entrances.values()), sorted(r.ROOMS))
        town_floor = windehus.floor(self.town_sizes)
        for door, name in entrances.items():
            # The door is part of its building, faced from open street below it.
            self.assertNotIn(door, town_floor, name)
            self.assertIn((door[0], door[1] + 1), town_floor, name)

    def test_each_room_matches_its_building(self):
        buildings = {name for name, *_ in windehus.OBJECTS}
        for room in r.ROOMS.values():
            self.assertIn(room.building, buildings)
        # The armourer's house is signed with a shield; the forge and hearths stand where the
        # chimneys are outside, and the goods shop, with no chimney, has no fire.
        self.assertEqual(r.ROOMS["armour"].building, "house-slate")
        hearths = {name: [t for t in room.things if t[0].startswith(("hearth-", "forge-"))]
                   for name, room in r.ROOMS.items()}
        self.assertFalse(hearths["goods"])
        self.assertEqual(hearths["weapons"][0][1], 1)            # chimney at the shop's left end
        self.assertGreater(hearths["armour"][0][1], r.ROOMS["armour"].width // 2)   # and at the house's right
        self.assertEqual(r.ROOMS["inn"].wall, "stone")
        self.assertEqual(r.ROOMS["goods"].wall, "plaster")
        self.assertEqual(r.ROOMS["mill"].wall, "rubble")

    def test_the_door_leads_in_and_the_doorway_leads_out(self):
        for room in r.ROOMS.values():
            rows = r.grid(room)
            self.assertEqual(len(rows), room.height)
            self.assertTrue(all(len(row) == room.width for row in rows))
            x, y = r.doorway(room)
            self.assertEqual((x, y), (room.door_x, max(yy for yy, row in enumerate(rows) if r.DOORWAY in row)))
            self.assertEqual(rows[y][x], r.DOORWAY)
            self.assertTrue(r.leaves_room(room, (x, y)))
            self.assertFalse(r.leaves_room(room, r.arrival(room)))
            self.assertEqual(r.arrival(room), (x, y - 1))
            self.assertIn(r.arrival(room), r.floor(room, self.sizes), room.name)

    def test_every_floor_tile_and_spot_is_reachable_from_the_door(self):
        for room in r.ROOMS.values():
            floor, seen = self.reachable(room)
            self.assertEqual(floor, seen, room.name)
            self.assertGreaterEqual(len(room.npc_spots), 2, room.name)
            for who, spot in room.npc_spots.items():
                self.assertIn(spot, floor, (room.name, who))

    def test_furniture_stands_on_the_floor_inside_the_room(self):
        for room in r.ROOMS.values():
            rows = r.grid(room)
            for name, tx, bottom in room.things:
                self.assertIn(name, self.sizes, (room.name, name))
                for x, y in r.footprint(name, tx, bottom, self.sizes):
                    self.assertEqual(rows[y][x], r.FLOOR, (room.name, name, x, y))
            for _, _, steps in r.things(room, self.sizes):
                for name, px, py in steps:
                    w, h = self.sizes[name]
                    self.assertGreaterEqual(px, 0)
                    self.assertLessEqual(px + w, room.width * r.TILE, (room.name, name))
                    self.assertGreaterEqual(py, 0, (room.name, name))

    def test_counters_can_be_spoken_across(self):
        for room in r.ROOMS.values():
            floor, seen = self.reachable(room)
            counters = [(tx, bottom, self.sizes[name][0] // r.TILE) for name, tx, bottom in room.things
                        if name.startswith("counter-")]
            self.assertTrue(counters or room.name == "mill", room.name)
            for tx, bottom, n in counters:
                self.assertTrue(any((x, bottom + 1) in seen for x in range(tx, tx + n)), room.name)

    def test_things_stand_back_to_front(self):
        for room in r.ROOMS.values():
            keys = [key for key, _, _ in r.things(room, self.sizes)]
            self.assertEqual(keys, sorted(keys))

    def test_animated_pieces_have_every_frame(self):
        for prefix, frames in (("hearth-", 3), ("forge-", 3), ("spurwheel-", 4)):
            sizes = {self.sizes[f"{prefix}{frame}"] for frame in range(frames)}
            self.assertEqual(len(sizes), 1, prefix)

    def test_the_mills_spur_wheel_meets_both_stone_nuts(self):
        import prepare_town_rooms as art

        mill = r.ROOMS["mill"]
        wheel = next(t for t in mill.things if t[0].startswith("spurwheel-"))
        ww = self.sizes[wheel[0]][0]
        centre = wheel[1] * r.TILE + ww / 2
        nuts = []
        for name, tx, _ in mill.things:
            if name.startswith("millstones"):
                w = self.sizes[name][0]
                nut = art.NUT_X + 1 if name == "millstones" else w - 1 - art.NUT_X
                nuts.append(tx * r.TILE + nut)
        self.assertEqual(len(nuts), 2)
        for nut in nuts:
            self.assertLess(abs(abs(nut - centre) - art.WHEEL_RX), 6, nut)
        # The spur wheel's shaft stands on one tile; you walk round it, and under the wheel.
        self.assertEqual(len(r.footprint(*wheel, self.sizes)), 1)

    def test_the_baked_rooms_match_the_layout(self):
        import pygame
        import prepare_town_rooms

        for room in r.ROOMS.values():
            baked = pygame.image.load(str(ROOMS / f"{room.name}-ground.png"))
            self.assertEqual(baked.get_size(), (room.width * r.TILE, room.height * r.TILE))
            fresh = prepare_town_rooms.room_ground(room)
            # Rebuild with:  python prepare_town_rooms.py
            self.assertEqual(pygame.image.tobytes(baked, "RGB"), pygame.image.tobytes(fresh, "RGB"), room.name)


if __name__ == "__main__":
    unittest.main()
