"""Build Larvel's revised portrait and his twin Rando from the original art.

Sources stay untouched:
    assets/portraits/larvel.png      original Larvel portrait (128 x 128)
    assets/larvel-overworld.png      Larvel walk sheet (3 x 4 cells of 16 x 16)

Outputs:
    assets/portraits/larvel-v2.png   same portrait, nose tip softened by a two-pixel bevel
    assets/portraits/rando.png       Larvel v2 with a hair-matched mustache, facing the other way
    assets/rando-overworld.png       Larvel's walk sheet with a two-pixel mustache on face views

Run from the project root:  python prepare_larvel_twins.py
"""
from pathlib import Path

import pygame

ASSETS = Path(__file__).resolve().parent / "assets"
PORTRAITS = ASSETS / "portraits"

OUTLINE = (14, 12, 14)

# Hair ramp sampled from Larvel's portrait so the mustache reads as the same hair.
HAIR_DARK = (30, 18, 15)
HAIR_SHADOW = (74, 43, 34)
HAIR_MID = (108, 74, 51)
HAIR_LIGHT = (137, 96, 67)
HAIR_GLINT = (176, 131, 90)

# Mustache rows in Larvel's original (facing-left) coordinates: y -> spans of x.
# Bushy over the upper lip, parting at the centre and drooping at both ends.
MUSTACHE = {
    62: ((46, 55),),
    63: ((44, 58),),
    64: ((43, 60),),
    65: ((43, 61),),
    66: ((43, 47), (54, 61)),
    67: ((43, 45), (58, 61)),
    68: ((43, 44), (60, 61)),
    69: ((60, 61),),
}
PART_X = 51


def soften_nose(image):
    """Round the sharp lower-front corner of the nose tip with a small bevel."""
    backdrop = image.get_at((38, 63))
    for point in ((39, 61), (39, 62), (39, 63), (40, 62), (40, 63)):
        image.set_at(point, backdrop)
    for point in ((40, 61), (41, 62)):
        image.set_at(point, OUTLINE)
    # Keep the warm rim light running down the new rounded edge.
    image.set_at((41, 61), (252, 196, 112))


def add_mustache(image):
    cells = {(x, y) for y, spans in MUSTACHE.items() for a, b in spans for x in range(a, b + 1)}
    for x, y in cells:
        top = (x, y - 1) not in cells
        bottom = (x, y + 1) not in cells
        # Strands fan out from the parting: down-left on the left, down-right on the right.
        strand = (x + y) % 3 == 0 if x < PART_X else (x - y) % 3 == 0
        if bottom:
            color = HAIR_DARK
        elif top:
            color = HAIR_MID
        else:
            color = HAIR_LIGHT if strand else HAIR_SHADOW if y >= 65 else HAIR_MID
        image.set_at((x, y), color)
    # A couple of loose hairs catch the same rim light as his profile.
    for point in ((43, 64), (44, 63)):
        image.set_at(point, HAIR_GLINT)


def mustache_sprite(sheet):
    """Turn the lowest row of pale chin pixels into a mustache on each face view.

    Skin is bluer than the lantern's yellow glow (b > 150), which keeps the lantern lit.
    """
    for row in range(3):  # down, left, right; the up row shows no face
        for col in range(3):
            ox, oy = col * 16, row * 16
            pale = [(x, y) for y in range(7, 12) for x in range(16)
                    if (c := sheet.get_at((ox + x, oy + y))).a and c.r > 220 and c.g > 180 and c.b > 150]
            if not pale:
                continue
            chin = max(y for _, y in pale)
            xs = sorted(x for x, y in pale if y == chin)
            for i, x in enumerate(xs):
                sheet.set_at((ox + x, oy + chin), HAIR_MID if i == 0 else HAIR_SHADOW)


def main():
    pygame.init()
    original = pygame.image.load(str(PORTRAITS / "larvel.png"))
    larvel = original.copy()
    soften_nose(larvel)
    pygame.image.save(larvel, str(PORTRAITS / "larvel-v2.png"))

    rando = larvel.copy()
    add_mustache(rando)
    pygame.image.save(pygame.transform.flip(rando, True, False), str(PORTRAITS / "rando.png"))

    sheet = pygame.image.load(str(ASSETS / "larvel-overworld.png")).copy()
    mustache_sprite(sheet)
    pygame.image.save(sheet, str(ASSETS / "rando-overworld.png"))


if __name__ == "__main__":
    main()
