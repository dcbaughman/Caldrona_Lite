"""Map and route rules for the rooms beyond Sunrest's webbed door."""

DEN_DOOR, DEN_APPROACH, DEN_ENTRY = (55, 26), (55, 27), (55, 25)
DEN_NEST, DEN_STONE = (60, 55), (78, 56)
DEN_STONE_TILES = frozenset((x, 56) for x in (77, 78, 79))
DEN_SHRINE = (58, 44)
DEN_HEART_GATE = (69, 58)
DEN_CHESTS = {
    (70, 28): ("gallery_lockbox", (("Potion", 2), ("Remedy", 2))),
    (80, 41): ("hatchery_lockbox", (("Ether", 2), ("Ember Feather", 1))),
    (81, 59): ("noktakoro_lockbox", (("Ember Talisman", 1), ("Brood Silk", 2))),
}


def boss_footprint(base):
    """Two columns and two rows above the sprite's bottom-left tile."""
    x, y = base
    return frozenset(((x, y), (x + 1, y), (x, y - 1), (x + 1, y - 1)))


DEN_NEST_FOOTPRINT = boss_footprint(DEN_NEST)


def _room(left, top, right, bottom):
    return frozenset((x, y) for y in range(top, bottom + 1) for x in range(left, right + 1))


ENTRY_ROOM = _room(55, 19, 62, 25) - {(55, 19), (62, 19), (62, 25)}
SILK_GALLERY = _room(67, 22, 77, 30) - {(67, 22), (77, 22), (77, 30)}
HATCHERY = _room(71, 34, 81, 43) - {(71, 34), (81, 34), (81, 43)}
FEEDING_TUNNELS = _room(56, 40, 66, 49) - {(56, 40), (66, 49)}
BROOD_CHAMBER = _room(54, 53, 66, 63) - {(54, 53), (66, 53), (54, 63)}
SANCTUM = _room(73, 54, 82, 62) - {(73, 54), (82, 54), (82, 62)}

_PASSAGES = (_room(63, 23, 66, 24) | _room(75, 31, 76, 33) |
             _room(67, 41, 70, 42) | _room(61, 50, 62, 52) | _room(67, 58, 72, 58))
DEN_FLOOR = ENTRY_ROOM | SILK_GALLERY | HATCHERY | FEEDING_TUNNELS | BROOD_CHAMBER | SANCTUM | _PASSAGES
DEN_HEIGHT = max(y for _, y in DEN_FLOOR) + 3

EGG_SACS = {
    (61, 20): 2, (68, 22): 2, (68, 25): 1, (73, 23): 0, (76, 29): 2,
    (72, 35): 0, (74, 36): 1, (77, 36): 0, (79, 37): 0, (80, 39): 1,
    (80, 35): 2, (80, 42): 2, (73, 42): 1, (64, 42): 1, (57, 48): 2,
    (55, 54): 2, (65, 55): 1, (56, 60): 1, (65, 62): 2,
}

# Each entry tiles a whole connected panel behind props and actors.
WEB_PANELS = (
    ((56, 20), 0), ((60, 23), 1), ((64, 22), 1), ((67, 22), 2),
    ((71, 23), 0), ((74, 27), 1), ((74, 31), 2),
    ((71, 35), 0), ((76, 35), 2), ((76, 39), 0), ((71, 41), 1),
    ((67, 40), 1), ((64, 41), 0), ((56, 41), 2), ((57, 46), 0),
    ((60, 48), 1), ((60, 51), 2), ((54, 54), 0), ((59, 53), 1),
    ((63, 54), 2), ((57, 57), 0), ((61, 58), 0), ((55, 61), 1),
    ((68, 57), 1), ((73, 57), 2), ((77, 58), 0), ((79, 54), 1),
)

ROOM_NAMES = (
    (ENTRY_ROOM, "Den Mother's Lair"),
    (SILK_GALLERY, "The Depths · Silk Gallery"),
    (HATCHERY, "The Depths · Hatchery"),
    (FEEDING_TUNNELS, "The Depths · Feeding Tunnels"),
    (BROOD_CHAMBER, "The Depths · Brood Chamber"),
    (SANCTUM, "The Depths · Noktakoro"),
)


def den_location(tile):
    return next((name for room, name in ROOM_NAMES if tile in room), "The Depths")


def den_danger(tile):
    """The vestibule, boss floor, and the Black Stone chamber have no roaming foes."""
    x, y = tile
    near_shrine = abs(x - DEN_SHRINE[0]) + abs(y - DEN_SHRINE[1]) <= 2
    if (near_shrine or tile in ENTRY_ROOM or tile in BROOD_CHAMBER or tile in SANCTUM
            or (x > 66 and y == DEN_HEART_GATE[1])):
        return 0
    return 2 if tile in FEEDING_TUNNELS or tile[1] >= 39 else 1
