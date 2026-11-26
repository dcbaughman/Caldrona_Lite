"""Build the forecourt's stone stair and iron gate at native pixel density.

The gate and stair rise into the two-tile wall while keeping their entrances
on the tile centerline at the floor.

    forecourt-gate.png         a narrow iron door set into a slate frame
    glyph-stair.png            rising steps behind a pulsing seal, as a strip of 32 x 32 frames
    sealed-passage.png         a stone arch choked with fallen slabs and a snapped brace
    sealed-passage-marked.png  the same seal with fresh pale crosscuts in the slabs

Run from the project root:  python prepare_sealed_passage.py
"""
import random
from pathlib import Path

import pygame

OUT = Path(__file__).resolve().parent / "assets" / "mine-polish"
SIZE = W, H = 24, 19
TILE_SIZE = 16
ROOF_MARGIN = 2

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


def build(marked=False, *, rubble=True):
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
    if rubble:
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
    if rubble:
        for i, (x, y) in enumerate(SPILL):
            surface.set_at((x, y), SLAB[2 if i % 2 else 1])
            if y + 1 < H:
                surface.set_at((x, y + 1), MORTAR)
    if marked:
        for start, end in CUTS:
            pygame.draw.line(surface, CUT, start, end)
    return surface


def fit_wall_tile(source):
    tile = pygame.Surface((TILE_SIZE, TILE_SIZE), pygame.SRCALPHA)
    pixels = pygame.transform.scale(source, (TILE_SIZE, TILE_SIZE - ROOF_MARGIN))
    tile.blit(pixels, (0, ROOF_MARGIN))
    return tile


def tall_quarry_gate():
    gate = pygame.Surface((18, 27), pygame.SRCALPHA)
    pygame.draw.polygon(gate, (22, 18, 36),
                        ((0, 26), (0, 5), (2, 2), (4, 1), (14, 1), (17, 4), (17, 26)))
    pygame.draw.polygon(gate, (51, 44, 72),
                        ((1, 25), (1, 6), (3, 3), (5, 2), (13, 2), (16, 5), (16, 25)))
    pygame.draw.lines(gate, (104, 92, 126), False, ((2, 8), (2, 5), (4, 3), (13, 3), (15, 5)))
    pygame.draw.rect(gate, (15, 14, 26), (3, 5, 12, 21))
    pygame.draw.rect(gate, (45, 45, 62), (4, 6, 10, 19))
    pygame.draw.rect(gate, (55, 54, 75), (5, 7, 3, 17))
    pygame.draw.rect(gate, (40, 39, 56), (9, 7, 4, 17))
    pygame.draw.line(gate, (22, 21, 34), (8, 6), (8, 24))
    for points, tone in (
        (((5, 11), (6, 10), (6, 16), (5, 22), (11, 21)), (68, 66, 87)),
        (((7, 12), (5, 17), (10, 11), (12, 16), (10, 23)), (36, 35, 52)),
        (((2, 7), (1, 13), (2, 20), (15, 11), (16, 18), (15, 23)), STONE[1]),
    ):
        for point in points:
            gate.set_at(point, tone)
    for y in (8, 19):
        pygame.draw.line(gate, (104, 97, 119), (4, y), (13, y))
        pygame.draw.line(gate, (30, 29, 44), (4, y + 1), (13, y + 1))
        gate.set_at((5, y), (148, 139, 156))
        gate.set_at((12, y), (130, 123, 143))
    for y in (9, 15, 22):
        pygame.draw.line(gate, MORTAR, (1, y), (2, y))
        pygame.draw.line(gate, MORTAR, (15, y), (16, y))
        gate.set_at((1, y + 1), STONE[2])
        gate.set_at((16, y + 1), STONE[1])
    pygame.draw.line(gate, (163, 150, 170), (7, 14), (9, 14))
    gate.set_at((9, 15), (103, 91, 113))
    pygame.draw.line(gate, (98, 85, 116), (2, 26), (15, 26))
    return gate


def glyph_stair_atlas():
    cell = TILE_SIZE * 2
    arch = pygame.Surface((18, cell), pygame.SRCALPHA)
    pygame.draw.polygon(arch, (26, 22, 42),
                        ((1, 31), (1, 13), (2, 6), (4, 3), (13, 3), (15, 6), (16, 13), (16, 31)))
    pygame.draw.polygon(arch, (50, 43, 68),
                        ((2, 30), (2, 14), (3, 6), (5, 4), (12, 4), (14, 6), (15, 14), (15, 30)))
    pygame.draw.polygon(arch, CAVITY,
                        ((4, 31), (4, 15), (5, 9), (5, 6), (12, 6), (12, 9), (13, 15), (13, 31)))
    # A deep landing and a shallow taper keep the run close to rectangular.
    treads = ((8, 5, 12, 0), (11, 5, 12, 1), (14, 5, 12, 1), (17, 4, 13, 1),
              (20, 4, 13, 1), (23, 4, 13, 2), (27, 4, 13, 2), (30, 4, 13, 2))
    for y, left, right, tone in treads:
        pygame.draw.line(arch, STONE[tone], (left, y), (right, y))
        pygame.draw.line(arch, (35, 30, 50), (left, y + 1), (right, y + 1))
        arch.set_at((left + 1 + y % 3, y), STONE[min(tone + 1, 3)])
        arch.set_at((right - y % 2, y), STONE[max(0, tone - 1)])
    for y in (10, 16, 22, 28):
        for x in (2, 14):
            pygame.draw.line(arch, MORTAR, (x, y), (x + 1, y))
            arch.set_at((x, y + 1), STONE[1])
    pygame.draw.line(arch, STONE[1], (5, 4), (12, 4))
    glyph = {
        (8, 14), (9, 14), (8, 15), (9, 15),
        (7, 16), (10, 16), (6, 17), (11, 17),
        (7, 18), (10, 18), (8, 19), (9, 19), (8, 20), (9, 20),
        (8, 17), (9, 17),
    }
    glow = {(x + dx, y + dy) for x, y in glyph
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1))} - glyph
    strengths = (.24, .34, .51, .63, .51, .34)
    atlas = pygame.Surface((cell * len(strengths), cell), pygame.SRCALPHA)
    for index, strength in enumerate(strengths):
        frame = arch.copy()
        for point in glow:
            frame.set_at(point, frame.get_at(point).lerp((137, 77, 184, 255), strength * .40))
        for point in glyph:
            tone = (197, 147, 241) if point in ((8, 17), (9, 17)) else (162, 104, 207)
            frame.set_at(point, pygame.Color(94, 58, 137).lerp((*tone, 255), strength))
        atlas.blit(frame, (index * cell + (cell - frame.get_width()) // 2, 0))
    return atlas


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    pygame.image.save(tall_quarry_gate(), str(OUT / "forecourt-gate.png"))
    pygame.image.save(glyph_stair_atlas(), str(OUT / "glyph-stair.png"))
    pygame.image.save(fit_wall_tile(build()), str(OUT / "sealed-passage.png"))
    pygame.image.save(fit_wall_tile(build(marked=True)), str(OUT / "sealed-passage-marked.png"))


if __name__ == "__main__":
    main()
