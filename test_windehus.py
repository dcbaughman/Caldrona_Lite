"""The Windehus town tileset and its test layout."""
import json
import unittest
from collections import deque
from pathlib import Path

import windehus as w

TOWN = Path(__file__).resolve().parent / "assets" / "town"


class TownTilesetTests(unittest.TestCase):
    def setUp(self):
        self.spots = json.loads((TOWN / "tileset.json").read_text(encoding="utf-8"))
        self.sizes = {name: (sw, sh) for name, (_, _, sw, sh) in self.spots.items()}

    def test_every_paving_sheet_and_core_piece_exists(self):
        for paving in w.PAVINGS:
            self.assertTrue((TOWN / f"ground-{paving}.png").exists(), paving)
        for name in ("wall-top-m-0", "wall-base-l-1", "wall-solo-r-2", "stairs-top-solo", "edge-l", "edge-r",
                     "wall-shadow", "fence-m", "fence-v", "fence-gate", "lowwall-m", "inn", "cottage", "well",
                     "windmill", "windmill-sails-0", "windmill-sails-3", "town-stone", "lamp", "shade-strip",
                     "shade-strip-top", "shade-strip-end", "shade-full", "shade-stair-foot", "stoop",
                     "square-gap-0", "square-gap-1", "pine-top", "pine-mid-0", "pine-mid-2", "pine-base",
                     "tree-top", "tree-mid", "tree-bottom", "tree-base"):
            self.assertIn(name, self.spots)

    def test_tiles_sit_on_the_16_px_grid(self):
        for name, (sw, sh) in self.sizes.items():
            if name.startswith(("wall-", "stairs-", "edge-", "fence-", "lowwall-", "planter-", "flowers-")):
                self.assertEqual((sw, sh), (16, 16), name)
        info = json.loads((TOWN / "buildings.json").read_text(encoding="utf-8"))
        for name, entry in info.items():
            tw, th = entry["tiles"]
            self.assertEqual(self.sizes[name], (tw * 16, th * 16), name)
        # Tree tiers are 16 px steps that stack, with 4 px of hanging tips below.
        for name in self.sizes:
            if name.startswith(("pine-", "tree-")):
                self.assertEqual(self.sizes[name], (32, 20), name)

    def test_every_door_in_town_is_the_same_size_as_the_cave_gates(self):
        info = json.loads((TOWN / "buildings.json").read_text(encoding="utf-8"))
        doors = [door for entry in info.values() for door in entry["doors"]]
        self.assertGreaterEqual(len(doors), 8)
        for x, y, dw, dh in doors:
            self.assertEqual((dw, dh), (10, 20))
        # A house stands its door on the footing, or up a four-step stoop on a cellar plinth,
        # so doors line up across the street at one of two heights.
        bottoms = {name: entry["tiles"][1] * 16 - (y + dh) for name, entry in info.items()
                   for x, y, dw, dh in entry["doors"] if name != "windmill"}
        for name, rise in bottoms.items():
            self.assertEqual(rise, 12 if name in w.STOOPS else 5, name)
            self.assertEqual(info[name]["stoop"], name in w.STOOPS)
        self.assertGreaterEqual(len(w.STOOPS), 3)
        for name, column in w.STOOPS.items():
            x, y, dw, dh = info[name]["doors"][0]
            self.assertEqual((x + dw // 2) // 16, column, name)

    def test_the_mill_towers_over_its_door(self):
        info = json.loads((TOWN / "buildings.json").read_text(encoding="utf-8"))
        mill = info["windmill"]
        (x, y, dw, dh), = mill["doors"]
        self.assertEqual((dw, dh), (10, 20))
        tw, th = mill["tiles"]
        self.assertGreaterEqual(th * 16, dh * 9)
        self.assertGreaterEqual(tw * 16, dw * 12)
        self.assertEqual((x + dw // 2) // 16, 4)
        for frame in range(4):
            self.assertEqual(self.sizes[f"windmill-sails-{frame}"], (144, 144))
        ops = [op for op in w.draw_ops(self.sizes) if op[0] == "sprite"]
        tower = next(i for i, op in enumerate(ops) if op[1] == "windmill")
        self.assertEqual(ops[tower + 1][1], w.MILL_SAILS)
        self.assertEqual(ops[tower + 1][2:], ops[tower][2:])

    def test_buildings_cast_shade_down_their_right_side(self):
        shade = w.building_shade(self.sizes)
        inn = [(name, x, y) for name, x, y in shade if x == 2 + self.sizes["inn"][0] // 16]
        self.assertEqual(inn[0][0], "shade-strip-top")
        self.assertEqual(inn[-1][0], "shade-strip-end")
        self.assertTrue(all(name == "shade-strip" for name, _, _ in inn[1:-1]))
        self.assertFalse(any(w.STRUCT[y][x] in w.WALLISH for _, x, y in shade))

    def test_stoops_stand_out_from_the_raised_doors(self):
        ops = [op for op in w.draw_ops(self.sizes) if op[0] == "sprite"]
        for name, tx, bottom, *_ in w.OBJECTS:
            if name not in w.STOOPS:
                continue
            spot = ("sprite", "stoop", (tx + w.STOOPS[name]) * 16, (bottom + 1) * 16 - 12)
            self.assertIn(spot, ops, name)
            house = next(i for i, op in enumerate(ops) if op[1] == name)
            self.assertGreater(ops.index(spot), house)
            # The steps come down onto open ground, not into a wall.
            self.assertNotIn(w.STRUCT[bottom + 1][tx + w.STOOPS[name]], w.WALLISH)

    def test_lifted_slabs_lie_on_whole_square_tiles(self):
        ops = w.draw_ops(self.sizes)
        for name, x, y, tw, th, count in w.SQUARE_GAPS:
            self.assertEqual(self.sizes[name], (tw * 16, th * 16))
            self.assertIn(("sprite", name, x * 16, y * 16), ops)
            for ty in range(y, y + th):
                for tx in range(x, x + tw):
                    self.assertEqual(w.GROUND[ty][tx], "f", (name, tx, ty))
                    self.assertEqual(w.paving_mask(tx, ty, "flag"), 15)

    def test_stair_flights_shade_the_ground_below_their_west_end(self):
        self.assertEqual(w.foot_shadow(17, 28), "shade-stair-foot")
        self.assertIsNone(w.foot_shadow(18, 28))
        self.assertEqual(w.foot_shadow(19, 16), "shade-stair-foot")
        self.assertEqual(w.foot_shadow(5, 16), "wall-shadow")
        self.assertIsNone(w.foot_shadow(5, 15))

    def test_sheep_birds_idle_inside_the_hay_pen(self):
        for direction in ("down", "left", "right", "up"):
            for frame in range(3):
                self.assertEqual(self.sizes[f"sheepbird-{direction}-{frame}"], (32, 32))
        birds = [(name, x, bottom) for name, x, bottom, *_ in w.OBJECTS if name.startswith("sheepbird-")]
        self.assertGreaterEqual(len(birds), 3)
        for name, x, bottom in birds:
            for ty in (bottom - 1, bottom):
                for tx in (x, x + 1):
                    # Inside the fence, clear of the posts and rails.
                    self.assertIsNone(w.STRUCT[ty][tx], (name, tx, ty))
                    self.assertTrue(27 <= tx <= 36 and 30 <= ty <= 33, (name, tx, ty))

    def test_trees_stack_from_their_tiers(self):
        self.assertEqual(w.tree_parts("pine", 4), ["pine-base", "pine-mid-2", "pine-mid-0", "pine-top"])
        self.assertEqual(w.tree_parts("tree", 4), ["tree-base", "tree-bottom", "tree-mid", "tree-top"])

    def test_the_test_town_draws_only_known_pieces_inside_the_map(self):
        ops = w.draw_ops(self.sizes)
        self.assertEqual(sum(op[0] == "grass" for op in ops), w.WIDTH * w.HEIGHT)
        for op in ops:
            if op[0] == "paving":
                _, paving, mask, sub, px, py = op
                self.assertIn(paving, w.PAVINGS)
                self.assertTrue(1 <= mask <= 15 and 0 <= sub < 16)
            elif op[0] == "sprite":
                _, name, px, py = op
                self.assertIn(name, self.spots)
                sw, sh = self.sizes[name]
                self.assertGreaterEqual(px, 0)
                self.assertLessEqual(px + sw, w.WIDTH * 16)
                self.assertLessEqual(py + sh, w.HEIGHT * 16 + (4 if name.startswith(("pine-", "tree-")) else 0))

    def test_paving_edges_reach_into_neighbouring_grass(self):
        # A cobbled street tile is fully paved; the grass beside it gets a ragged partial edge.
        self.assertEqual(w.paving_mask(33, 22, "cobble"), 15)
        self.assertTrue(0 < w.paving_mask(33, 21, "cobble") < 15)
        self.assertEqual(w.paving_mask(20, 9, "cobble"), 0)

    def test_walls_get_coping_on_top_a_plinth_below_and_stairs_cut_through(self):
        self.assertTrue(w.structure_piece(5, 14).startswith("wall-top-m"))
        self.assertTrue(w.structure_piece(5, 15).startswith("wall-base-m"))
        self.assertEqual(w.structure_piece(19, 14), "stairs-top-l")
        self.assertEqual(w.structure_piece(20, 15), "stairs-base-r")
        self.assertTrue(w.structure_piece(30, 24).startswith("wall-solo-l"))
        self.assertEqual(w.structure_piece(30, 23), "edge-l")


class TownWalkTests(unittest.TestCase):
    def setUp(self):
        spots = json.loads((TOWN / "tileset.json").read_text(encoding="utf-8"))
        self.sizes = {name: (sw, sh) for name, (_, _, sw, sh) in spots.items()}
        self.floor = w.floor(self.sizes)

    def reachable(self):
        queue, seen = deque([w.ARRIVAL]), {w.ARRIVAL}
        while queue:
            x, y = queue.popleft()
            for step in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if step in self.floor and step not in seen:
                    seen.add(step)
                    queue.append(step)
        return seen

    def test_the_road_from_sunrest_reaches_every_door(self):
        info = json.loads((TOWN / "buildings.json").read_text(encoding="utf-8"))
        seen = self.reachable()
        places = {name: (tx, bottom) for name, tx, bottom, *_ in w.OBJECTS if name in info}
        self.assertEqual(set(places), set(info))
        for name, (tx, bottom) in places.items():
            (x, _, dw, _), = info[name]["doors"]
            # The door's own tile is part of the house; the party faces it from the tile below.
            door = (tx + (x + dw // 2) // 16, bottom)
            self.assertNotIn(door, self.floor, name)
            self.assertIn((door[0], bottom + 1), seen, name)
        for terrace in ((25, 12), (19, 22), (30, 28)):
            self.assertIn(terrace, seen)

    def test_walls_houses_and_trees_block_but_stairs_and_stoops_do_not(self):
        for y in range(w.HEIGHT):
            for x in range(w.WIDTH):
                code = w.STRUCT[y][x]
                if code is not None:
                    self.assertEqual((x, y) in self.floor, code == "S", (code, x, y))
        houses = set()
        for name, tx, bottom, *_ in w.OBJECTS:
            if name in w.BUILDINGS:
                tw, th = (v // 16 for v in self.sizes[name])
                houses |= {(x, y) for y in range(bottom - th + 1, bottom + 1) for x in range(tx, tx + tw)}
        self.assertTrue(houses.isdisjoint(self.floor))
        for name, tx, bottom, *_ in w.OBJECTS:
            if name in ("pine", "tree"):
                self.assertFalse({(tx, bottom), (tx + 1, bottom)} & self.floor, (name, tx, bottom))
            elif name.startswith("flowers") and (tx, bottom) not in houses:
                self.assertTrue((tx, bottom) in self.floor, (name, tx, bottom))
            if name in w.STOOPS:
                self.assertTrue((tx + w.STOOPS[name], bottom + 1) in self.floor, name)
        # A tree's canopy hangs over open ground the party can walk behind.
        self.assertTrue((12, 31) in self.floor and (12, 30) in self.floor)
        # The mill stands on its tower and the gear at its foot; the lane before it is open.
        self.assertTrue({(x, 11) for x in range(28, 35)}.isdisjoint(self.floor))
        self.assertTrue({(x, 12) for x in range(27, 36)} <= self.floor)

    def test_the_sheep_birds_stay_penned(self):
        seen = self.reachable()
        pen = {(x, y) for x in range(27, 37) for y in range(30, 34)}
        self.assertTrue(pen.isdisjoint(seen))

    def test_only_the_end_of_the_road_leads_out(self):
        self.assertIn(w.ARRIVAL, self.floor)
        self.assertEqual(w.ARRIVAL[1], w.HEIGHT - 1)
        exits = {(x, y) for x in range(-1, w.WIDTH + 1) for y in range(-1, w.HEIGHT + 1) if w.leaves_town((x, y))}
        self.assertEqual(exits, {(x, w.HEIGHT) for x in w.ROAD_OUT})
        for x in w.ROAD_OUT:
            self.assertEqual(w.GROUND[w.HEIGHT - 1][x], "d")
            self.assertIn((x, w.HEIGHT - 1), self.floor)

    def test_things_stand_back_to_front(self):
        things = w.things(self.sizes)
        keys = [key for key, _, _ in things]
        self.assertEqual(keys, sorted(keys))
        flat = [("sprite", name, px, py) for _, _, steps in things for name, px, py in steps]
        self.assertEqual(w.draw_ops(self.sizes), w.ground_ops(self.sizes) + flat)
        self.assertFalse(any(op[0] == "sprite" and op[1] in w.BUILDINGS for op in w.ground_ops(self.sizes)))

    def test_the_baked_ground_matches_the_layout(self):
        import pygame
        import prepare_town_tiles

        atlas = pygame.image.load(str(TOWN / "tileset.png"))
        spots = json.loads((TOWN / "tileset.json").read_text(encoding="utf-8"))
        baked = pygame.image.load(str(TOWN / "windehus-ground.png"))
        fresh = prepare_town_tiles.town_ground(atlas, spots)
        self.assertEqual(baked.get_size(), (w.WIDTH * 16, w.HEIGHT * 16))
        # Rebuild with:  python prepare_town_tiles.py
        self.assertEqual(pygame.image.tobytes(baked, "RGB"), pygame.image.tobytes(fresh, "RGB"))


if __name__ == "__main__":
    unittest.main()
