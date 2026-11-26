"""Draw the rock-cut descent in Larvel's side drift on its 32 px footprint."""
from pathlib import Path

import pygame


ASSETS = Path(__file__).resolve().parent / "assets"
OUT_PATH = ASSETS / "mine-polish" / "drift-stairwell.png"
SIZE = 32

STONE_SHADOW = (25, 20, 42)
STONE_MID = (53, 44, 82)
STONE_EDGE = (78, 67, 111)
STONE_SEAM = (40, 32, 66)
SHAFT_DARK = (16, 13, 31)

RIM = (
    (2, 6), (4, 3), (7, 3), (8, 2), (13, 2), (15, 1), (19, 2), (24, 2),
    (27, 4), (29, 8), (28, 12), (29, 17), (28, 21), (30, 26), (29, 29),
    (26, 29), (25, 27), (6, 27), (4, 30), (1, 30), (1, 27), (2, 23),
    (1, 19), (2, 16), (2, 11), (3, 9),
)
OPENING = (
    (7, 7), (10, 5), (19, 5), (23, 6), (25, 9), (25, 13), (26, 17),
    (26, 22), (27, 27), (27, 31), (4, 31), (4, 27), (5, 23), (5, 19),
    (6, 15), (6, 11),
)

# From the darkest landing to the near lip. The lower treads occupy fewer rows.
TREADS = (
    (9, 11, (29, 24, 49)),
    (12, 15, (40, 33, 64)),
    (16, 20, (48, 39, 77)),
    (21, 25, (56, 45, 87)),
    (26, 31, (61, 48, 96)),
)


def mix(base, accent, amount):
    return tuple(round(value + (other - value) * amount) for value, other in zip(base, accent))


def draw_rim(sprite, rock):
    pygame.draw.polygon(sprite, STONE_MID, RIM)
    pygame.draw.lines(sprite, STONE_SHADOW, True, RIM)
    for y in range(SIZE):
        for x in range(SIZE):
            if sprite.get_at((x, y))[:3] == STONE_MID:
                grain = rock.get_at((x % rock.get_width(), y % rock.get_height()))[:3]
                sprite.set_at((x, y), mix(STONE_MID, grain, .58))

    # Broken planes at the floor edge, matching the cave wall's purple ledges.
    for face, shade in (
        (((3, 7), (5, 4), (8, 4), (7, 6), (5, 7), (4, 10)), STONE_EDGE),
        (((10, 3), (15, 2), (19, 3), (18, 4), (12, 4)), (69, 57, 99)),
        (((21, 3), (25, 3), (27, 6), (24, 5), (21, 5)), (63, 53, 93)),
        (((3, 15), (5, 13), (5, 17), (3, 20)), (64, 53, 97)),
        (((2, 25), (5, 22), (5, 25), (3, 29), (2, 28)), (70, 57, 101)),
        (((27, 15), (28, 18), (27, 21), (26, 19)), (60, 49, 91)),
        (((27, 24), (29, 26), (29, 28), (27, 27)), (66, 53, 96)),
    ):
        pygame.draw.polygon(sprite, shade, face)

    for seam in (((8, 3), (9, 4), (11, 4)), ((3, 10), (4, 11), (5, 11)),
                 ((2, 21), (4, 21), (5, 20)), ((26, 12), (27, 13), (28, 13))):
        pygame.draw.lines(sprite, STONE_SEAM, False, seam)

    pygame.draw.polygon(sprite, SHAFT_DARK, OPENING)
    pygame.draw.lines(sprite, STONE_SHADOW, False, OPENING[:6])
    pygame.draw.lines(sprite, (37, 29, 61), False, ((7, 7), (6, 12), (5, 18), (5, 22), (4, 27)))
    pygame.draw.lines(sprite, (29, 23, 48), False, ((23, 6), (25, 10), (25, 15), (26, 20), (27, 27)))


def draw_treads(sprite, floor):
    for first, last, stone in TREADS:
        for y in range(first, last + 1):
            left = 8 - (y - 9) // 6
            right = 23 + (y - 9) // 7
            for x in range(left, right + 1):
                grain = floor.get_at((x % floor.get_width(), y % floor.get_height()))[:3]
                color = mix(stone, grain, .25)
                if y == first:
                    color = mix(color, STONE_EDGE, .28)
                elif y == last and last != SIZE - 1:
                    color = mix(color, SHAFT_DARK, .46)
                if x in (left, right):
                    color = mix(color, SHAFT_DARK, .35)
                sprite.set_at((x, y), color)

    for x, y, width in ((10, 12, 4), (17, 16, 3), (8, 21, 3), (18, 21, 4), (12, 26, 6)):
        for px in range(x, x + width):
            color = sprite.get_at((px, y))[:3]
            sprite.set_at((px, y), mix(color, STONE_EDGE, .49))

    # Feather the mouth of the descent into the floor at the near lip.
    for y, alpha in ((29, 224), (30, 144), (31, 52)):
        for x in range(4, 28):
            sprite.set_at((x, y), (*sprite.get_at((x, y))[:3], alpha))


def draw_distant_lantern(sprite):
    # A small pool of light on the far landing and a single hot pixel at its center.
    for y in range(6, 12):
        for x in range(16, 24):
            reach = 1 - ((x - 20) ** 2 / 19 + (y - 8) ** 2 / 7)
            if reach > 0:
                sprite.set_at((x, y), mix(sprite.get_at((x, y))[:3], (136, 83, 66), .43 * reach))
    sprite.set_at((20, 7), (98, 62, 59))
    sprite.set_at((20, 8), (231, 175, 109))
    sprite.set_at((21, 8), (153, 98, 69))
    sprite.set_at((20, 9), (109, 69, 59))


def build():
    cave_art = ASSETS / "crystal_cavern"
    floor = pygame.image.load(str(cave_art / "floor_0.png"))
    rock = pygame.image.load(str(cave_art / "side_wall_1.png"))
    sprite = pygame.Surface((SIZE, SIZE), pygame.SRCALPHA)
    draw_rim(sprite, rock)
    draw_treads(sprite, floor)
    draw_distant_lantern(sprite)
    return sprite


if __name__ == "__main__":
    pygame.image.save(build(), str(OUT_PATH))
