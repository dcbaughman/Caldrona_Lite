"""Build the sealed-passage wall prop at native pixel density.

The piece shares the quarry door's 24 x 19 footprint and registration point, so it
drops into any north-wall tile the same way: centred on the tile, overhanging the
row by a pixel or two. Two states are written:

    sealed-passage.png         a stone arch choked with fallen slabs and a snapped brace
    sealed-passage-marked.png  the same seal with fresh pale crosscuts in the slabs

Run from the project root:  python prepare_sealed_passage.py
"""
import random
from pathlib import Path

import pygame

OUT = Path(__file__).resolve().parent / "assets" / "mine-polish"
SIZE = W, H = 24, 19

MORTAR = (18, 12, 20)
CAVITY = (11, 8, 16)
# Warm violet-grey arch stone, sampled from the quarry door's surround.
STONE = ((40, 34, 50), (70, 62, 80), (104, 94, 106), (150, 132, 132))
# Cooler blue-grey for the fallen slabs so the blockage reads apart from the frame.
SLAB = ((34, 38, 54), (60, 66, 88), (92, 100, 122), (136, 142, 160))
TIMBER = ((60, 32, 24), (119, 70, 46), (162, 95, 60), (176, 109, 65))
CUT = (197, 185, 201)
# The door's stone carries the odd warm mauve fleck; borrowing it ties the two together.
WARM = (111, 79, 95)

# Arch blocks: a keystone, two crown voussoirs and stacked jamb stones.
ARCH = (
    ((10, 0), (14, 0), (15, 5), (9, 5)),
    ((5, 2), (8, 1), (10, 0), (9, 5), (7, 6), (4, 5)),
    ((14, 0), (16, 1), (19, 2), (20, 5), (17, 6), (15, 5)),
    ((2, 5), (4, 5), (7, 6), (7, 10), (1, 10), (1, 7)),
    ((17, 6), (20, 5), (22, 6), (23, 10), (17, 10)),
    ((1, 10), (7, 10), (7, 14), (1, 14)),
    ((17, 10), (23, 10), (23, 14), (17, 14)),
    ((1, 14), (7, 14), (7, 19), (0, 19), (0, 16)),
    ((17, 14), (23, 14), (24, 16), (24, 19), (17, 19)),
)
OPENING = ((7, 6), (9, 5), (15, 5), (17, 6), (17, 19), (7, 19))
# One big slab has dropped across the mouth; smaller blocks wedge in around it.
SLABS = (
    ((7, 11), (14, 7), (17, 9), (17, 12), (10, 15), (7, 15)),
    ((14, 6), (17, 6), (17, 8), (15, 8)),
    ((7, 15), (11, 15), (12, 19), (7, 19)),
    ((11, 15), (17, 12), (17, 19), (12, 19)),
)
# The old brace, snapped where the big slab came down; the splinters face each other.
BRACE = (((8, 6), (11, 9)), ((14, 13), (16, 16)))
SPLINTERS = ((12, 9), (13, 13))
CUTS = (((9, 12), (13, 9)), ((11, 13), (12, 12)), ((13, 17), (16, 15)))
# Loose stones spill from the foot of the seal onto the floor line.
SPILL = ((5, 17), (6, 18), (9, 18), (15, 18), (18, 17), (19, 18))


def _mask(polygon):
    layer = pygame.Surface(SIZE, pygame.SRCALPHA)
    pygame.draw.polygon(layer, (255, 255, 255), polygon)
    return {(x, y) for y in range(H) for x in range(W) if layer.get_at((x, y)).a}


def _block(surface, cells, ramp, rng, warm=False):
    """Shade one stone: lit top-left rim, shadowed bottom-right, grit, mortar gap."""
    # Pull the right and bottom edges in a pixel so mortar shows between blocks.
    body = {(x, y) for x, y in cells if (x + 1, y) in cells and (x, y + 1) in cells}
    for x, y in body:
        lit = (x, y - 1) not in body or (x - 1, y) not in body
        shade = (x, y + 1) not in body or (x + 1, y) not in body
        tone = 2 if lit and not shade else 0 if shade and not lit else 1
        roll = rng.random()
        # Sparse grit breaks up flat faces the way the door's stone does.
        if roll < .16:
            tone = max(0, tone - 1)
        elif roll > .9 and tone < 2:
            tone += 1
        color = WARM if warm and tone == 1 and roll > .82 else ramp[tone]
        surface.set_at((x, y), color)
    corner = min(body, key=lambda p: (p[0] + p[1], p[1]), default=None)
    if corner:
        surface.set_at(corner, ramp[3])


def build(marked=False):
    rng = random.Random(51)
    surface = pygame.Surface(SIZE, pygame.SRCALPHA)
    silhouette = set().union(*(_mask(stone) for stone in ARCH), _mask(OPENING))
    # Chip only the crown, so the jambs stay flush with the wall tiles either side.
    rim = [p for p in silhouette if p[1] < 6 and (p[0], p[1] - 1) not in silhouette]
    silhouette -= set(rng.sample(sorted(rim), len(rim) // 4))
    for point in silhouette:
        surface.set_at(point, MORTAR)
    for point in _mask(OPENING) & silhouette:
        surface.set_at(point, CAVITY)
    for slab in SLABS:
        _block(surface, _mask(slab), SLAB, rng)
    for (x1, y1), (x2, y2) in BRACE:
        # Two pixels thick: a lit top face over a dark underside.
        pygame.draw.line(surface, TIMBER[0], (x1, y1 + 1), (x2, y2 + 1))
        pygame.draw.line(surface, TIMBER[1], (x1, y1), (x2, y2))
        surface.set_at((x1, y1), TIMBER[2])
    for point in SPLINTERS:
        surface.set_at(point, TIMBER[3])
    for stone in ARCH:
        _block(surface, _mask(stone) & silhouette, STONE, rng, warm=True)
    # A dark reveal just inside the arch gives the mouth depth.
    for x, y in _mask(OPENING) & silhouette:
        if y < 7 and surface.get_at((x, y))[:3] == CAVITY:
            continue
        if (x - 1, y) not in _mask(OPENING) or (x + 1, y) not in _mask(OPENING):
            surface.set_at((x, y), MORTAR)
    for i, (x, y) in enumerate(SPILL):
        surface.set_at((x, y), SLAB[2 if i % 2 else 1])
        if y + 1 < H:
            surface.set_at((x, y + 1), MORTAR)
    if marked:
        for start, end in CUTS:
            pygame.draw.line(surface, CUT, start, end)
    return surface


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    pygame.image.save(build(), str(OUT / "sealed-passage.png"))
    pygame.image.save(build(marked=True), str(OUT / "sealed-passage-marked.png"))


if __name__ == "__main__":
    main()
