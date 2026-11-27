"""Inside Windehus: the rooms behind the town's doors.

Each room takes its materials and shape from its building outside:
    inn           the inn: stone walls like its ground floor, the hearth under its chimney, a bar,
                  tables, stairs up to its upper floor and a corner of beds
    weapons       the weaponsmith (the shop with the sword sign): a forge under its chimney,
                  racks of blades and spears, a counter, an anvil and a grindstone
    armour        the armourer (the slate house on the ridge, with the shield sign): stands of
                  mail and plate, a rack of shields, a shelf of helms, the hearth under its chimney
    goods         the general goods shop (the flask sign): plaster walls like its ground floor,
                  shelves of jars and potions, sacks, barrels and crates; no chimney, no hearth
    mill          the ground floor of the tower mill: a round room of rubble stone round the
                  main shaft and its great spur wheel, two pairs of millstones, the ladder up,
                  the sack hoist, flour sacks and a barrow

A room is a rectangle of tiles drawn the way the town is, from above and in front: the back
wall's face fills the two rows under its coping, the side walls show only their tops, and the
door is a gap in the front wall's top on the bottom row. Stepping into the doorway leads
back to the street, in front of the door you came in by. The mill is round instead; its
floor is the oval inside its wall.

Rooms keep open floor in front of each counter and round the tables, and npc_spots marks where
the people who work in them will stand, for scenes to come.
"""
from dataclasses import dataclass, field

import windehus

TILE = 16
VOID, TOP, FACE, FLOOR, DOORWAY = " ", "#", "W", ".", "D"
# Things that stand on more than their bottom row: {name prefix: rows}. Every other thing
# stands on its bottom row only, and the rows above it are behind it (or, for the millstones'
# spindles, overhead).
DEEP = {"bed": 2, "millstones": 2, "table": 2}
# Things the party walks under or past: they block nothing.
OPEN = ("hoist",)
# The mill's great spur wheel turns overhead on its shaft: only the shaft's tile blocks.
SHAFT = "spurwheel"
# The mill's floor: an oval in tiles (centre x, centre y, x radius, y radius).
MILL_OVAL = (7.5, 8.0, 6.6, 5.3)


@dataclass(frozen=True)
class Room:
    name: str
    title: str                  # shown in the corner while inside
    building: str               # the building outside, in windehus.OBJECTS
    width: int
    height: int
    door_x: int                 # the doorway's column, on the bottom row
    floor: str                  # "planks" or "flag"
    wall: str                   # "stone", "plaster" or "rubble"
    windows: tuple = ()         # columns of windows in the back wall
    decor: tuple = ()           # (piece, column) hung on the back wall
    rugs: tuple = ()            # (x0, y0, x1, y1) tile rects, inclusive
    things: tuple = ()          # (sprite, left tile, bottom row)
    npc_spots: dict = field(default_factory=dict)


ROOMS = {room.name: room for room in (
    Room("inn", "Windehus Inn", "inn", 18, 13, door_x=9, floor="planks", wall="stone",
         windows=(5, 13), decor=(("notice", 7),),
         rugs=((7, 4, 10, 5),),
         things=(("bar-shelf", 1, 3), ("counter-4", 1, 5), ("hearth-0", 8, 3), ("stairs-up", 11, 3),
                 ("bed-0", 14, 4), ("bed-1", 15, 4), ("bed-2", 16, 4), ("partition-3", 14, 6),
                 ("table", 5, 8), ("stool", 4, 8), ("stool", 7, 8),
                 ("table", 11, 8), ("stool", 10, 8), ("stool", 13, 8),
                 ("table", 5, 10), ("stool", 4, 10), ("stool", 7, 10),
                 ("table", 11, 10), ("stool", 10, 10), ("stool", 13, 10),
                 ("barrel", 1, 7), ("barrel", 1, 8), ("crate", 1, 11), ("planter-1", 16, 11)),
         npc_spots={"innkeeper": (2, 4), "by the hearth": (8, 6), "the beds": (13, 5)}),
    Room("weapons", "Weaponsmith", "shop-arms", 12, 10, door_x=4, floor="flag", wall="stone",
         windows=(6, 10), decor=(("plaque-swords", 4),),
         things=(("forge-0", 1, 3), ("anvil", 3, 4), ("rack-swords", 7, 3), ("rack-spears", 9, 3),
                 ("counter-5", 6, 5), ("grindstone", 1, 6), ("weapon-barrel", 1, 8), ("crate", 10, 8)),
         npc_spots={"smith": (8, 4), "customer": (4, 6)}),
    Room("armour", "Armourer", "house-slate", 13, 10, door_x=2, floor="planks", wall="stone",
         windows=(6, 11), decor=(("plaque-shield", 1), ("plaque-shield", 4)),
         rugs=((3, 7, 6, 8),),
         things=(("shield-rack", 3, 3), ("helm-shelf", 7, 3), ("hearth-0", 9, 3),
                 ("armor-mail", 1, 5), ("armor-plate", 1, 7), ("armor-mail", 5, 5),
                 ("counter-5", 7, 6), ("chest", 11, 8)),
         npc_spots={"armourer": (9, 5), "customer": (4, 5)}),
    Room("goods", "General Goods", "shop-goods", 12, 10, door_x=7, floor="planks", wall="plaster",
         windows=(2, 4), decor=(("herbs", 7), ("herbs", 8)),
         things=(("shelf-jars", 6, 3), ("shelf-potions", 9, 3), ("counter-5", 5, 5),
                 ("sacks", 1, 4), ("barrel", 1, 6), ("gourds", 2, 6), ("crates", 1, 8), ("barrel", 10, 8)),
         npc_spots={"shopkeeper": (8, 4), "customer": (7, 6)}),
    Room("mill", "The Mill", "windmill", 15, 14, door_x=7, floor="planks", wall="rubble",
         windows=(3, 11), decor=(("lantern", 5), ("lantern", 10)),
         things=(("spurwheel-0", 3, 8), ("millstones", 1, 8), ("millstones-r", 11, 8), ("ladder", 9, 3),
                 ("hoist", 4, 5), ("flour-sacks", 3, 11), ("wheelbarrow", 10, 11), ("barrel", 12, 10)),
         npc_spots={"miller": (9, 9), "by the stones": (4, 9)}),
)}


def _mill_floor(x, y):
    cx, cy, rx, ry = MILL_OVAL
    return ((x + .5 - cx) / rx) ** 2 + ((y + .5 - cy) / ry) ** 2 <= 1


def grid(room):
    """The room's tiles as rows of VOID / TOP / FACE / FLOOR / DOORWAY."""
    w, h = room.width, room.height
    if room.wall == "rubble":
        floor = {(x, y) for y in range(h) for x in range(w) if _mill_floor(x, y)}
        face = set()
        for x in {x for x, _ in floor}:
            top = min(y for xx, y in floor if xx == x)
            face |= {(x, top - 1), (x, top - 2)}
        inside = floor | face
        cells = {}
        for y in range(h):
            for x in range(w):
                if (x, y) in floor:
                    cells[x, y] = FLOOR
                elif (x, y) in face:
                    cells[x, y] = FACE
                elif any((x + dx, y + dy) in inside for dx in (-1, 0, 1) for dy in (-1, 0, 1)):
                    cells[x, y] = TOP
                else:
                    cells[x, y] = VOID
        foot = max(y for x, y in floor if x == room.door_x)
        cells[room.door_x, foot + 1] = DOORWAY
        return ["".join(cells[x, y] for x in range(w)) for y in range(h)]
    rows = [TOP * w]
    rows += [TOP + FACE * (w - 2) + TOP for _ in range(2)]
    rows += [TOP + FLOOR * (w - 2) + TOP for _ in range(h - 4)]
    rows.append(TOP * room.door_x + DOORWAY + TOP * (w - room.door_x - 1))
    return rows


def doorway(room):
    """The doorway tile: the room's way out, and where the party arrives facing in."""
    rows = grid(room)
    return next((x, y) for y, row in enumerate(rows) for x, ch in enumerate(row) if ch == DOORWAY)


def arrival(room):
    """Where the party stands on coming in: the floor just inside the doorway."""
    x, y = doorway(room)
    return x, y - 1


def leaves_room(room, tile):
    """True for the doorway: stepping into it goes back out to the street."""
    return tile == doorway(room)


def _thing_size(name, sizes):
    w, h = sizes[name]
    return -(-w // TILE), -(-h // TILE)


def footprint(name, tx, bottom, sizes):
    """The tiles a thing stands on."""
    if name.startswith(OPEN):
        return set()
    tw, th = _thing_size(name, sizes)
    if name.startswith(SHAFT):
        return {(tx + tw // 2, bottom)}
    deep = next((rows for prefix, rows in DEEP.items() if name.startswith(prefix)), 1)
    rows = range(bottom - deep + 1, bottom + 1)
    return {(tx + c, y) for c in range(tw) for y in rows}


def floor(room, sizes):
    """Every tile the party can stand on: the floor, less what stands on it. (The doorway is
    the way out, not somewhere to stand.)"""
    open_tiles = {(x, y) for y, row in enumerate(grid(room)) for x, ch in enumerate(row) if ch == FLOOR}
    for name, tx, bottom in room.things:
        open_tiles -= footprint(name, tx, bottom, sizes)
    return open_tiles


def things(room, sizes):
    """The room's furniture back to front, like windehus.things: [(key, px, [(name, px, py)])]."""
    out = []
    for name, tx, bottom in room.things:
        w, h = sizes[name]
        span = -(-w // TILE) * TILE
        px = tx * TILE + (span - w) // 2
        out.append(((bottom + 1) * TILE, px, [(name, px, (bottom + 1) * TILE - h)]))
    return sorted(out, key=lambda t: t[:2])


def _door_column(name, sizes):
    if name == "windmill":
        return 4
    steps = {**windehus.STOOPS, **windehus.DOORSTEPS}
    return steps[name]


def entrances(sizes):
    """{door tile in town: room name}: the tile of each enterable building's door. The party
    faces it from the row below and steps in."""
    out = {}
    by_building = {room.building: room.name for room in ROOMS.values()}
    for name, tx, bottom, *_ in windehus.OBJECTS:
        if name in by_building:
            out[(tx + _door_column(name, sizes), bottom)] = by_building[name]
    return out
