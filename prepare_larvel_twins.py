"""Build Larvel's revised portrait and his twin Rando from the original art.

Sources stay untouched:
    assets/portraits/larvel.png      original Larvel portrait (128 x 128)
    assets/larvel-overworld.png      Larvel walk sheet (3 x 4 cells of 16 x 16)

Outputs:
    assets/portraits/larvel-v2.png   same portrait, nose tip softened by a two-pixel bevel
    assets/portraits/rando.png       Larvel v2 with a bard's bowl cut and a hair-matched mustache,
                                     facing the other way
    assets/rando-overworld.png       Larvel's walk sheet with a two-pixel mustache on face views

Run from the project root:  python prepare_larvel_twins.py
"""
import math
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


# Rando's bard bowl cut, in the same facing-left coordinates.
# The centre part runs from the crown down to the hairline, and the fringe sweeps away from it on both sides.
PART_TOP, PART_BOT = (60, 4), (52, 29)
PART_SKIN, PART_SKIN_SHADOW = (196, 128, 78), (150, 92, 58)
RIM_LIGHT = (240, 170, 92)
# Face and neck pixels the clean-up of Larvel's loose strands must leave alone.
FACE_KEEP = ((39, 30), (38, 46), (40, 52), (36, 58), (38, 64), (42, 68), (43, 78), (92, 78), (92, 30))


def _part_x(y):
    t = (y - PART_TOP[1]) / (PART_BOT[1] - PART_TOP[1])
    return PART_TOP[0] + (PART_BOT[0] - PART_TOP[0]) * t


def _fringe(x):
    """Lowest hair row in column x."""
    if x < 37:
        return 45                             # far temple lock
    if x <= 43:
        return 44
    if x <= 52:
        return 30 + (52 - x) * 14 / 9         # curtain sweeping from the part to the far temple
    if x <= 79:
        return 30 + (x - 52) * 0.22           # near fringe, just above the brow
    return 65                                 # side panel hangs past the ear


def _in_bowl(x, y):
    # Feathered tips: every few columns a lock ends a pixel short.
    if y > _fringe(x) - (x % 4 == 1) - (x % 7 == 3):
        return False
    if y < 38:
        return ((x - 66) / 36) ** 2 + ((y - 37) / 34) ** 2 <= 1
    if x <= 43:
        return 32 <= x and (y < 42 or x >= 33 + (y - 42))
    if x >= 79:
        return x <= 102 - max(0, y - 53) * 1.3  # rounded back corner
    return False


def _in_polygon(x, y, poly):
    inside, j = False, len(poly) - 1
    for i, (xi, yi) in enumerate(poly):
        xj, yj = poly[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def bowl_cut(image):
    """Replace Larvel's tousled hair with a bard's bowl cut parted in the middle."""
    width = image.get_width()
    hair = {(x, y) for y in range(72) for x in range(width) if _in_bowl(x, y)}
    # Clear the old strands outside the new shape, reusing the backdrop texture from the left columns.
    for y in range(74):
        for x in range(width):
            if (x, y) not in hair and not _in_polygon(x, y, FACE_KEEP):
                image.set_at((x, y), image.get_at((x % 8, y)))
    ramp = (HAIR_DARK, HAIR_SHADOW, HAIR_MID, HAIR_LIGHT, HAIR_GLINT)
    for x, y in sorted(hair):
        part = _part_x(y) if y <= PART_BOT[1] else None
        if part is not None and abs(x - part) < .6:
            image.set_at((x, y), PART_SKIN_SHADOW if y < 8 else PART_SKIN)
            continue
        if any((x + dx, y + dy) not in hair for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
            image.set_at((x, y), OUTLINE)
            continue
        # Strands fall away from the part, combed outward on each side.
        side = -1 if x < (part if part is not None else 52) else 1
        angle = math.atan2(y - PART_TOP[1] + 6, (x - PART_TOP[0]) * side)
        strand = int(angle * 22 + (0 if side < 0 else 3)) % 4
        # Key light from the upper left: a sheen band around the dome, darker at the fringe and back.
        r = math.hypot((x - 66) / 36, (y - 37) / 34)
        shade = 2
        if x > 90 or y > _fringe(x) - 3:
            shade = 1
        if y > _fringe(x) - 1.5 or (x > 79 and y > 60):
            shade = 0
        if .62 < r < .80 and x < 80 and y < 24:
            shade = 3
        if x >= 79 and y > 30:  # side panel: straight locks falling to a curled-under end
            shade = (1, 2, 1, 2, 3, 2)[x % 6] if x < 96 else (0, 1, 1)[x % 3]
            if y > 60:
                shade = max(0, shade - 1)
        if part is not None and abs(x - part) < 1.6:
            shade = min(shade, 1)  # shadow lining the part
        if strand == 0:
            shade = max(0, shade - 1)
        if strand == 2 and shade >= 2:
            shade += 1
        image.set_at((x, y), ramp[min(shade, 4)])
    # Warm rim light down the far edge, matching the light on his profile.
    for x, y in sorted(hair):
        if (x - 1, y) not in hair and (x + 1, y) in hair and 6 < y and x < 46:
            image.set_at((x + 1, y), RIM_LIGHT)
    # Curled-under ends: a light row just above the dark bottom edge of the side panel.
    for x in range(80, 101):
        rows = [y for y in range(40, 72) if (x, y) in hair]
        if rows:
            image.set_at((x, max(rows) - 2), HAIR_LIGHT)


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
    bowl_cut(rando)
    add_mustache(rando)
    pygame.image.save(pygame.transform.flip(rando, True, False), str(PORTRAITS / "rando.png"))

    sheet = pygame.image.load(str(ASSETS / "larvel-overworld.png")).copy()
    mustache_sprite(sheet)
    pygame.image.save(sheet, str(ASSETS / "rando-overworld.png"))


if __name__ == "__main__":
    main()
