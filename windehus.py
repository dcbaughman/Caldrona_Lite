"""Windehus, the ridge town north of Sunrest.

The road north from the Sunrest grasslands comes in at the south edge. The map is three
terraces joined by stairs through stone retaining walls:
    the mill ridge (north)      the great tower mill and three houses along a dirt lane
    the inn square (middle)     the inn, a dark flagstone market square with the well, two shops
    the road field (south)      the road in from Sunrest, the bakery, a fenced hay field

ground_ops() is the flat layer and things() everything standing on it, back to front;
draw_ops() is both in order, for the art preview. The game bakes the flat layer into its world
chunks and sorts the party in among the things (windehus_town.py). floor() is where the party
can stand.
"""
from math import cos, sin

WIDTH, HEIGHT = 40, 36
TILE = 16
PAVINGS = ("dirt", "cobble", "brick", "flag")   # later pavings lie over earlier ones at shared edges
CODES = {"dirt": "d", "cobble": "c", "brick": "b", "flag": "f"}   # the letters used in the ground map
WALLISH = ("W", "S")
BUILDINGS = ("inn", "house-red", "house-slate", "cottage", "shop-arms", "shop-goods", "bakery")
# Houses raised on a cellar plinth, with the tile column of their door. A stoop of steps
# stands out from the door onto the row below the house.
STOOPS = {"cottage": 1, "house-slate": 0, "shop-goods": 2}
# Houses on the street, with the tile column of their door: the door sits on the footing,
# 5 px up, with a two-step doorstep out onto the row below.
DOORSTEPS = {"inn": 3, "house-red": 2, "shop-arms": 1, "bakery": 1}
# The town's one tree, in three greens. Most pines are the deep green; now and then one is
# bluer or mossier.
PINE_GREENS = ("deep", "deep", "fir", "deep", "moss")
# Slabs lifted from the market square: (decal, left tile, top tile, width, height in tiles,
# slabs gone). The decal is drawn for the paving texture under those exact tiles.
SQUARE_GAPS = (("square-gap-0", 15, 18, 3, 2, 2), ("square-gap-1", 24, 22, 3, 2, 3))
# The mill's sails share the tower's origin; the renderer cycles the frame.
MILL_SAILS = "windmill-sails-0"
# The road from Sunrest meets the town's south edge on these columns. Stepping south off them
# leads back to the grasslands; a party coming up the road arrives on ARRIVAL.
ROAD_OUT = (18, 19, 20, 21)
ARRIVAL = (19, 35)
# What the party cannot walk through. A building, and a prop that is all ground (a well, a
# stall, a hay mound), fills its whole tile rect. Other props and trees stand on their bottom
# row only; the rows above are behind them. Flowers are walked over. The mill tower stands on
# its middle five columns, and its capstan wheel and millstones take one more tile each side
# at its foot.
DEEP_PROPS = ("well", "stall-red", "stall-blue", "haystack")
MILL_TOWER = range(2, 7)


def _grid(value):
    return [[value for _ in range(WIDTH)] for _ in range(HEIGHT)]


def _fill(grid, x0, y0, x1, y1, value):
    """Fill tiles x0 <= x < x1, y0 <= y < y1."""
    for y in range(max(0, y0), min(HEIGHT, y1)):
        for x in range(max(0, x0), min(WIDTH, x1)):
            grid[y][x] = value


def _layout():
    ground, struct = _grid("."), _grid(None)
    # The mill ridge: a dirt lane past the houses, worn bare in front of the mill door.
    _fill(ground, 3, 12, 37, 14, "d")
    _fill(ground, 30, 11, 33, 12, "d")
    # The great retaining wall, with a stair down to the square.
    _fill(struct, 0, 14, WIDTH, 16, "W")
    _fill(struct, 19, 14, 21, 16, "S")
    # The inn square: a cobbled high street, the flagstone market square, a brick inn yard.
    _fill(ground, 19, 16, 21, 18, "c")
    _fill(ground, 1, 22, 39, 24, "c")
    _fill(ground, 12, 17, 28, 25, "f")
    _fill(ground, 2, 22, 10, 24, "b")
    _fill(ground, 17, 24, 23, 26, "c")
    # A raised flower bed by the shops: a one-course wall with coped ends.
    _fill(struct, 30, 24, 36, 25, "W")
    struct[23][30], struct[23][35] = "<", ">"
    # The lower retaining wall and its broad stair down to the road.
    _fill(struct, 0, 26, WIDTH, 28, "W")
    _fill(struct, 17, 26, 23, 28, "S")
    # The road field: the road in from Sunrest, the bakery's brick step, the hay field.
    _fill(ground, 18, 28, 22, HEIGHT, "d")
    _fill(ground, 3, 35, 9, 36, "b")
    _fill(struct, 26, 29, 38, 30, "F")
    struct[29][31] = "G"
    _fill(struct, 26, 34, 38, 35, "F")
    for y in range(30, 34):
        struct[y][26] = struct[y][37] = "|"
    _fill(struct, 9, 33, 15, 34, "w")
    return ground, struct


GROUND, STRUCT = _layout()

# Objects: (sprite, left tile, bottom row[, tiers]). Sprites narrower than their tiles are
# centred. A pine is two tiles wide; the fourth value is its height in tiles. A lamp names
# its first flame frame; the renderer flickers it through the rest.
OBJECTS = (
    # Ridge: a wood along the top, the houses on the lane, the mill at the east end.
    ("pine", 0, 3, 4), ("pine", 2, 6, 5), ("pine", 13, 3, 4), ("pine", 20, 4, 4), ("pine", 24, 3, 4),
    ("pine", 7, 4, 4), ("bush", 18, 4), ("flowers-2", 11, 5), ("stump", 16, 3),
    ("windmill", 27, 11), ("cottage", 4, 11), ("house-slate", 9, 11), ("house-red", 15, 11),
    ("haystack", 24, 11), ("pine", 0, 12, 4), ("pine", 1, 13, 3), ("pine", 22, 10, 5), ("pine", 36, 11, 4),
    ("pine", 38, 8, 4), ("pine", 38, 13, 3), ("azalea-0", 24, 13), ("bush", 2, 13), ("barrel", 8, 11),
    ("crate", 14, 11), ("flowers-0", 21, 11), ("flowers-2", 25, 7),
    # Inn square.
    ("inn", 2, 21), ("shop-arms", 30, 21), ("shop-goods", 34, 21), ("well", 19, 21),
    ("stall-red", 13, 20), ("stall-blue", 24, 20), ("lamp-0", 11, 21), ("lamp-0", 28, 21), ("lamp-0", 11, 24),
    ("lamp-0", 28, 24), ("bench", 15, 24), ("bench", 23, 24), ("barrel", 9, 21), ("barrel", 10, 21),
    ("crate", 29, 21), ("gourds", 15, 20), ("crates", 12, 18), ("planter-0", 31, 23), ("planter-1", 32, 23), ("planter-2", 33, 23),
    ("planter-0", 34, 23), ("pine", 0, 25, 3), ("azalea-1", 38, 25), ("flowers-1", 1, 17), ("flowers-0", 39, 18),
    # Road field.
    ("bakery", 3, 34), ("town-stone", 23, 32), ("signpost", 16, 32), ("haystack", 30, 33), ("stump", 35, 33),
    # Sheep-birds in the hay pen: one at the hay, two idling. Each is a 32 x 32 idle frame;
    # the renderer cycles frames 0-1-2 of the same facing.
    ("sheepbird-left-0", 32, 33), ("sheepbird-down-1", 28, 31), ("sheepbird-right-2", 34, 31),
    ("pine", 12, 32, 4), ("pine", 0, 35, 4), ("pine", 38, 31, 4), ("bush", 24, 35), ("azalea-0", 15, 35),
    ("flowers-2", 10, 32), ("flowers-1", 13, 31), ("barrel", 8, 34), ("sacks", 1, 34),
)


def grass_index(x, y):
    """The overworld's own meadow pick, so town grass matches the fields around Sunrest."""
    variation = ((x * 73856093) ^ (y * 19349663)) & 0xffffffff
    roll = (variation ^ (variation >> 13) ^ (variation >> 23)) & 255
    if sin(x * 0.43 + y * 0.24) + cos(y * 0.48 - x * 0.21) > 0.8:
        return 3 if roll < 100 else 4 if roll < 205 else 5
    return 0 if roll < 110 else 1 if roll < 195 else 2 if roll < 225 else 5


def _at(grid, x, y):
    return grid[y][x] if 0 <= x < WIDTH and 0 <= y < HEIGHT else None


def paving_mask(x, y, paving):
    """Corner bits (1 TL, 2 TR, 4 BL, 8 BR) whose surrounding tiles include this paving."""
    mask = 0
    for bit, (cx, cy) in ((1, (x, y)), (2, (x + 1, y)), (4, (x, y + 1)), (8, (x + 1, y + 1))):
        if any(_at(GROUND, cx - dx, cy - dy) == CODES[paving] for dx in (0, 1) for dy in (0, 1)):
            mask |= bit
    return mask


def _variant(x, y):
    roll = ((x * 2654435761) ^ (y * 40503)) % 100
    return 1 if roll < 22 else 2 if roll < 32 else 0


def _run_end(x, y, members):
    left, right = _at(STRUCT, x - 1, y) in members, _at(STRUCT, x + 1, y) in members
    return "m" if left and right else "l" if right else "r" if left else "solo"


def structure_piece(x, y):
    code = STRUCT[y][x]
    if code in WALLISH:
        up, down = _at(STRUCT, x, y - 1) in WALLISH, _at(STRUCT, x, y + 1) in WALLISH
        kind = "mid" if up and down else "top" if down else "base" if up else "solo"
        if code == "S":
            return f"stairs-{kind}-{_run_end(x, y, ('S',))}"
        end = _run_end(x, y, WALLISH)
        return f"wall-{kind}-{'l' if end == 'solo' else end}-{_variant(x, y)}"
    if code in ("<", ">"):
        return "edge-l" if code == "<" else "edge-r"
    if code in ("F", "G"):
        return "fence-gate" if code == "G" else f"fence-{_run_end(x, y, ('F', 'G'))}"
    if code == "|":
        return "fence-v"
    if code == "w":
        return f"lowwall-{_run_end(x, y, ('w',))}"
    return None


def foot_shadow(x, y):
    """The shade on a ground tile just below a wall or stair, if any. A wall shades the
    ground at its foot; a stair flight only below its west end, where the cheek's shade runs
    out on the ground."""
    above = _at(STRUCT, x, y - 1)
    if STRUCT[y][x] in WALLISH or above not in WALLISH:
        return None
    if above == "W":
        return "wall-shadow"
    return "shade-stair-foot" if structure_piece(x, y - 1).endswith(("-l", "-solo")) else None


def pine_sprite(tx, bottom, tiers):
    """The sprite for the pine standing at (tx, bottom): its height and its green."""
    return f"pine-{tiers}-{PINE_GREENS[(tx * 7 + bottom * 3) % len(PINE_GREENS)]}"


def pines():
    """Every pine sprite the town uses."""
    return sorted({pine_sprite(tx, bottom, rest[0]) for name, tx, bottom, *rest in OBJECTS if name == "pine"})


def door_px(column, tiles):
    """The x of a house's door inside its sprite, given the door's tile column and the house's
    width in tiles. A door in an end column keeps two pixels in from the corner, so its frame
    and lintel sit on the wall."""
    return 16 * column + 3 + (2 if column == 0 else -2 if column == tiles - 1 else 0)


def building_shade(sizes):
    """Shade tiles east of each building: light comes from the top left, so every house casts
    a strip down its right side, starting on a diagonal and tailing past its front corner."""
    tiles = []
    for name, tx, bottom, *_ in OBJECTS:
        if name not in BUILDINGS:
            continue
        w, h = (v // TILE for v in sizes[name])
        x, top = tx + w, bottom - h + 2
        for y in range(top, bottom + 2):
            if not (0 <= x < WIDTH and 0 <= y < HEIGHT) or STRUCT[y][x] in WALLISH:
                continue
            kind = "strip-top" if y == top else "strip-end" if y == bottom + 1 else "strip"
            tiles.append((f"shade-{kind}", x, y))
    return tiles


def ground_ops(sizes):
    """The flat layer, in drawing order. sizes = {sprite: (w, h)} from the tileset index.
    Steps: ("grass", index, px, py) | ("paving", name, mask, sub, px, py) | ("sprite", name, px, py)."""
    ops = []
    for y in range(HEIGHT):
        for x in range(WIDTH):
            px, py = x * TILE, y * TILE
            ops.append(("grass", grass_index(x, y), px, py))
            if STRUCT[y][x] in WALLISH:
                continue
            for paving in PAVINGS:
                mask = paving_mask(x, y, paving)
                if mask:
                    ops.append(("paving", paving, mask, (y % 4) * 4 + x % 4, px, py))
    for name, x, y, *_ in SQUARE_GAPS:
        ops.append(("sprite", name, x * TILE, y * TILE))
    for y in range(HEIGHT):
        for x in range(WIDTH):
            piece = structure_piece(x, y)
            if piece and STRUCT[y][x] in WALLISH + ("<", ">"):
                ops.append(("sprite", piece, x * TILE, y * TILE))
            elif foot_shadow(x, y):
                ops.append(("sprite", foot_shadow(x, y), x * TILE, y * TILE))
    for name, x, y in building_shade(sizes):
        ops.append(("sprite", name, x * TILE, y * TILE))
    return ops


def things(sizes):
    """Everything standing on the ground, back to front: [(key, px, steps)]. key is the y of the
    thing's foot; steps are its sprites [(name, px, py)] in drawing order. A walker whose foot
    is at or below a thing's key stands in front of it."""
    things = []
    for y in range(HEIGHT):
        for x in range(WIDTH):
            piece = structure_piece(x, y)
            if piece and STRUCT[y][x] not in WALLISH + ("<", ">"):
                things.append(((y + 1) * TILE, x * TILE, [(piece, x * TILE, y * TILE)]))
    for name, tx, bottom, *rest in OBJECTS:
        if name == "pine":
            name = pine_sprite(tx, bottom, rest[0])
        w, h = sizes[name]
        span = -(-w // TILE) * TILE
        px = tx * TILE + (span - w) // 2
        py = (bottom + 1) * TILE - h
        steps = [(name, px, py)]
        if name == "windmill":
            steps.append((MILL_SAILS, px, py))
        things.append(((bottom + 1) * TILE, px, steps))
        # A stoop stands out 12 px into the row below, a doorstep 5 px, so each sorts just
        # after its house. Both line up under the door.
        if name in STOOPS:
            x = tx * TILE + door_px(STOOPS[name], w // TILE) - 3
            things.append(((bottom + 1) * TILE + 12, px, [("stoop", x, (bottom + 1) * TILE - 12)]))
        if name in DOORSTEPS:
            x = tx * TILE + door_px(DOORSTEPS[name], w // TILE) - 3
            things.append(((bottom + 1) * TILE + 5, px, [("doorstep", x, (bottom + 1) * TILE - 5)]))
    return sorted(things, key=lambda t: t[:2])


def draw_ops(sizes):
    """Ordered drawing steps for the whole town: the flat layer, then the things back to front."""
    return ground_ops(sizes) + [("sprite", name, px, py) for _, _, steps in things(sizes) for name, px, py in steps]


def blocked(sizes):
    """Tiles the party cannot stand on (see DEEP_PROPS for the rules)."""
    tiles = {(x, y) for y in range(HEIGHT) for x in range(WIDTH) if STRUCT[y][x] not in (None, "S")}
    for name, tx, bottom, *_ in OBJECTS:
        if name == "pine":
            tiles |= {(tx, bottom), (tx + 1, bottom)}
            continue
        if name.startswith("flowers"):
            continue
        w, h = (-(-v // TILE) for v in sizes[name])
        if name == "windmill":
            tiles |= {(tx + c, y) for c in MILL_TOWER for y in range(bottom - h + 1, bottom + 1)}
            tiles |= {(tx + MILL_TOWER.start - 1, bottom), (tx + MILL_TOWER.stop, bottom)}
            continue
        rows = range(bottom - h + 1, bottom + 1) if name in BUILDINGS or name in DEEP_PROPS else (bottom,)
        tiles |= {(tx + c, y) for c in range(w) for y in rows}
    return tiles


def floor(sizes):
    """Every tile the party can stand on."""
    return {(x, y) for y in range(HEIGHT) for x in range(WIDTH)} - blocked(sizes)


def leaves_town(tile):
    """True for the tile just past the south edge at the end of the road."""
    return tile[1] == HEIGHT and tile[0] in ROAD_OUT
