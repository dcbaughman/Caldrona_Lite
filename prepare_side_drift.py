"""Build the timbered stairwell in Larvel's side drift.

Output:
    assets/mine-polish/drift-stairwell.png   32 x 32, covers a 2 x 2 tile block

The hole is framed by three railed beams, with no beam on the south side.
Worn stone steps drop north into the dark.
Far down, a lantern glimmers: someone is already below.

Run from the project root:  python prepare_side_drift.py
"""
from pathlib import Path

import pygame

OUT_PATH = Path(__file__).resolve().parent / "assets" / "mine-polish" / "drift-stairwell.png"
SIZE = 32

OUTLINE = (20, 14, 24)
# Timber ramp sampled from the mine cart and tools.
WOOD_DARK = (63, 43, 45)
WOOD_SHADOW = (84, 56, 53)
WOOD_MID = (110, 74, 65)
WOOD_LIGHT = (147, 101, 82)
WOOD_HI = (165, 118, 95)
# Steps start a little lighter than the cavern floor and sink to black.
STEP_TOP = (96, 80, 124)
STEP_DEEP = (12, 9, 22)
VOID = (7, 5, 14)
GLIMMER = (244, 207, 127)
GLIMMER_RIM = (150, 98, 70)

BEAM = 4  # beam thickness in pixels
HOLE_LEFT, HOLE_RIGHT, HOLE_TOP = BEAM, SIZE - BEAM - 1, BEAM + 1
STEP_DEPTH = 4  # 3-pixel tread + 1-pixel riser
STEPS = 5


def _mix(a, b, t):
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def _grain(x, y):
    return (x * 7 + y * 13) % 11 == 0


def draw_steps(image):
    for y in range(HOLE_TOP, SIZE):
        depth = SIZE - 1 - y  # 0 at the open south edge
        step, row = divmod(depth, STEP_DEPTH)
        light = 1 - min(1, step / STEPS)
        tread = _mix(STEP_DEEP, STEP_TOP, light ** 1.4)
        if step >= STEPS:
            tread = VOID
        elif row == STEP_DEPTH - 1:
            tread = _mix(tread, VOID, .65)  # riser in shadow under the next step up
        elif row == 0:
            tread = _mix(tread, (140, 124, 160), .25 * light)  # worn nosing catches light
        for x in range(HOLE_LEFT, HOLE_RIGHT + 1):
            color = tread
            # The shaft's side walls close in, darker on the lit west than the east.
            wall = min(x - HOLE_LEFT, HOLE_RIGHT - x)
            if wall < 2:
                color = _mix(color, VOID, .55 if wall == 0 else .3)
            image.set_at((x, y), color)
    # A lantern far below.
    for point, color in (((19, 7), GLIMMER), ((20, 7), GLIMMER_RIM), ((19, 8), GLIMMER_RIM),
                         ((18, 7), (70, 46, 46)), ((19, 6), (70, 46, 46))):
        image.set_at(point, color)


def draw_beam(image, rect, horizontal):
    x0, y0, w, h = rect
    for y in range(y0, y0 + h):
        for x in range(x0, x0 + w):
            # Top face lit from the north-west; the inner face drops into shadow.
            across = (y - y0) if horizontal else (x - x0)
            span = h if horizontal else w
            inner = across == span - 1 if horizontal or x0 == 0 else across == 0
            outer = across == 0 if horizontal or x0 == 0 else across == span - 1
            color = WOOD_DARK if inner else WOOD_LIGHT if outer else WOOD_MID
            if not inner and _grain(x, y):
                color = WOOD_SHADOW
            image.set_at((x, y), color)


def draw_post(image, left, top):
    for y in range(top, top + 6):
        for x in range(left, left + 5):
            edge = x in (left, left + 4) or y in (top, top + 5)
            cap = y <= top + 2
            color = OUTLINE if edge else (WOOD_HI if (x, y) == (left + 1, top + 1) else
                                          WOOD_LIGHT if cap else WOOD_SHADOW)
            image.set_at((x, y), color)


def draw_rails(image):
    # A hand rail runs along the beam tops between the posts.
    for x in range(2, SIZE - 2):
        image.set_at((x, 1), WOOD_HI if x % 5 else WOOD_LIGHT)
        image.set_at((x, 2), WOOD_SHADOW)
    for y in range(2, SIZE - 4):
        for x, rail in ((1, WOOD_HI), (SIZE - 2, WOOD_LIGHT)):
            image.set_at((x, y), rail if y % 5 else WOOD_MID)


def outline(image):
    solid = {(x, y) for x in range(SIZE) for y in range(SIZE) if image.get_at((x, y)).a}
    for x, y in solid:
        if x in (0, SIZE - 1) or y == 0:
            image.set_at((x, y), OUTLINE)


def build():
    image = pygame.Surface((SIZE, SIZE), pygame.SRCALPHA)
    draw_steps(image)
    draw_beam(image, (0, 0, SIZE, BEAM + 1), horizontal=True)
    draw_beam(image, (0, 0, BEAM, SIZE), horizontal=False)
    draw_beam(image, (SIZE - BEAM, 0, BEAM, SIZE), horizontal=False)
    draw_rails(image)
    outline(image)
    for left, top in ((0, 0), (SIZE - 5, 0), (SIZE // 2 - 2, 0), (0, SIZE - 6), (SIZE - 5, SIZE - 6)):
        draw_post(image, left, top)
    return image


def main():
    pygame.init()
    pygame.image.save(build(), str(OUT_PATH))


if __name__ == "__main__":
    main()
