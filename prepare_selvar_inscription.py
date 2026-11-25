"""Build the Selvar wall inscription at native pixel density.

A narrow patch of worn purple slate, split by a natural crack, with one column of
Selvar script carved down it (hook, stem, zig, diamond and tail strokes, after
`assets/mine-polish/selvar-inscription-source.svg`). Two states are written:

    selvar-inscription.png      the old carving on its own, reusable on any north wall
    selvar-inscription-cut.png  fresh Veskar cuts across it, pale dust and Temur's charcoal

Both are 12 x 22. Rows 0-17 are the slate (anchor the top two pixels above the wall
row, like the quarry door's crown); rows 18-21 spill onto the floor line.

Run from the project root:  python prepare_selvar_inscription.py
"""
import random
from pathlib import Path

import pygame

OUT = Path(__file__).resolve().parent / "assets" / "mine-polish"
SIZE = W, H = 12, 22

RIM = (18, 12, 20)
SLATE = ((58, 46, 78), (86, 70, 108), (110, 92, 132), (140, 122, 158))
GROOVE = (18, 10, 26)
CRACK = (20, 14, 28)
CUT = (204, 194, 214)
# Where a fresh cut crosses an old groove the crystal light catches the raw edge.
GLINT = (150, 196, 230)
DUST = ((150, 140, 160), (186, 176, 192))
CHARCOAL = ((16, 14, 18), (52, 46, 54))

PANEL = {0: (3, 8), 1: (2, 9), 16: (1, 10), 17: (2, 9)}
CHIPS = {(10, 6), (1, 12), (10, 13)}

# One Selvar column, stem on x = 6, read top to bottom.
GLYPH = (
    (4, 3), (5, 2), (6, 2), (7, 3),                      # hook
    *((6, y) for y in range(3, 16)),                     # stem
    (5, 4), (4, 5), (5, 6), (7, 6), (7, 7),              # zig
    (5, 9), (7, 9), (4, 10), (8, 10), (5, 11), (7, 11),  # diamond
    (5, 14), (4, 15), (5, 15), (7, 15), (8, 16), (9, 16),  # tail sweep
)
CRACKS = ((9, 1), (9, 2), (8, 3), (9, 4), (9, 5), (2, 13), (3, 14), (3, 15), (2, 16))
# Fresh cuts run across the carving with a slight downhill slant.
CUTS = (
    ((2, 8), (3, 8), (4, 7), (5, 7), (6, 7), (7, 7), (8, 7), (9, 6)),
    ((3, 13), (4, 12), (5, 12), (6, 12), (7, 12), (8, 11), (9, 11)),
)
DUST_SPOTS = ((3, 18), (5, 18), (4, 19), (2, 19), (6, 19), (5, 20))
CHARCOAL_STUB = ((8, 19), (9, 19), (10, 18))


def _panel():
    cells = set()
    for y in range(18):
        left, right = PANEL.get(y, (1, 10))
        cells.update((x, y) for x in range(left, right + 1))
    return cells - CHIPS


def build(cut=False):
    rng = random.Random(50)
    surface = pygame.Surface(SIZE, pygame.SRCALPHA)
    panel = _panel()
    face = {(x, y) for x, y in panel
            if all((x + dx, y + dy) in panel for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))}
    for point in panel - face:
        surface.set_at(point, RIM)
    for x, y in face:
        lit = (x - 1, y) not in face or (x, y - 1) not in face
        shade = (x + 1, y) not in face or (x, y + 1) not in face
        tone = 2 if lit and not shade else 0 if shade and not lit else 1
        roll = rng.random()
        # Age has worn the slate unevenly; a little grit keeps the face from reading flat.
        if roll < .1:
            tone = max(0, tone - 1)
        elif roll > .94:
            tone = min(3, tone + 1)
        surface.set_at((x, y), SLATE[tone])
    grooves = set(GLYPH) & face
    for x, y in grooves:
        surface.set_at((x, y), GROOVE)
        # Softened by age: the lower lip of each groove catches a little light.
        if (x, y + 1) in face and (x, y + 1) not in grooves:
            surface.set_at((x, y + 1), SLATE[3])
    for point in set(CRACKS) & panel:
        surface.set_at(point, CRACK)
    if cut:
        for stroke in CUTS:
            for point in stroke:
                surface.set_at(point, GLINT if point in grooves else CUT)
        for i, point in enumerate(DUST_SPOTS):
            surface.set_at(point, DUST[i % 2])
        surface.set_at(CHARCOAL_STUB[0], CHARCOAL[0])
        surface.set_at(CHARCOAL_STUB[1], CHARCOAL[1])
        surface.set_at(CHARCOAL_STUB[2], DUST[0])
    return surface


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    pygame.image.save(build(), str(OUT / "selvar-inscription.png"))
    pygame.image.save(build(cut=True), str(OUT / "selvar-inscription-cut.png"))


if __name__ == "__main__":
    main()
