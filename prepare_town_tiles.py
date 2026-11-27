"""Draw the town tileset for Windehus: paving, retaining walls, stairs, fences, houses and props.

Original art on the game's 16 px grid. Light comes from the top left, and dark ink stays on
the shadow side like the rest of Caldrona. The grass is the overworld's own
(assets/grassland/meadow*.png), so the town sits in the same field. Writes into assets/town/:

    ground-<paving>.png   256 x 256 per paving: column = corner mask (0-15), row = sub-tile
                          (0-15) of a seamless 64 x 64 texture, so the paving never repeats
                          on a visible grid
    tileset.png           every other piece, packed
    tileset.json          {name: [x, y, w, h]} into tileset.png
    windehus-ground.png   the town's whole flat layer (windehus.ground_ops) baked into one
                          opaque image, so the game loads it in one go

Corner masks: bit 1 top-left, 2 top-right, 4 bottom-left, 8 bottom-right corner paved.
Run with the project venv (pygame):  python prepare_town_tiles.py
"""
from math import asin, atan2, cos, pi, sin, sqrt
from pathlib import Path
import json
import random

import pygame

import windehus


ASSETS = Path(__file__).resolve().parent / "assets"
OUT = ASSETS / "town"
TEX = 64
CLEAR = (0, 0, 0, 0)
INK = (22, 17, 22)

# Paving, kept earthy so it sits in the olive Sunrest grass.
COBBLE = ((46, 42, 37), (68, 63, 55), (92, 86, 74), (118, 110, 94), (144, 135, 115), (170, 162, 140))
FLAG = ((64, 60, 52), (90, 84, 72), (118, 110, 94), (146, 138, 118), (172, 164, 142), (198, 190, 166))
# The market square sits a few steps darker than the houses, so the buildings carry the eye.
SQUARE = ((40, 38, 38), (57, 55, 52), (74, 71, 65), (92, 88, 79), (110, 105, 94), (130, 124, 111))
# Flat, crisp shade: one cool translucent tone, the way a 16-bit tileset lays shadow.
SHADE = (26, 20, 44, 118)
BRICK = ((60, 32, 26), (86, 46, 34), (114, 62, 44), (140, 82, 56), (162, 104, 72), (186, 130, 92))
DIRT = ((66, 50, 34), (84, 64, 40), (102, 78, 48), (122, 92, 58), (142, 108, 70), (162, 128, 86))
MORTAR = (50, 46, 34)
# Retaining walls share the overworld cliffs' cool slate.
WALL = ((30, 34, 42), (46, 52, 62), (63, 72, 84), (82, 92, 104), (104, 114, 124), (130, 138, 146))
TUFT = ((74, 92, 30), (98, 112, 36), (126, 132, 46))
MOSS = ((48, 68, 34), (68, 92, 40), (94, 114, 48))
WOOD = ((40, 26, 20), (62, 40, 28), (88, 58, 38), (114, 78, 50), (142, 100, 64), (172, 128, 84))
PLASTER = ((142, 128, 102), (178, 164, 134), (206, 194, 164), (228, 218, 190))
ROOF_RED = ((60, 24, 22), (88, 36, 28), (120, 52, 36), (150, 72, 46), (178, 98, 62), (204, 128, 84))
ROOF_SLATE = ((28, 34, 48), (42, 52, 72), (58, 72, 98), (78, 94, 124), (102, 118, 148), (132, 146, 172))
GLASS = ((24, 30, 44), (42, 56, 78), (84, 110, 138), (172, 198, 214))
LEAF = ((28, 42, 24), (42, 60, 28), (60, 80, 34), (84, 102, 42), (110, 126, 52), (142, 150, 68))
PINE = ((16, 30, 26), (26, 44, 34), (38, 60, 42), (54, 78, 50), (74, 98, 58), (98, 120, 68))
IRON = ((30, 30, 36), (54, 54, 62), (86, 86, 96), (128, 128, 138))
FLAME = ((150, 72, 30), (232, 152, 62), (255, 222, 142))
STRAW = ((96, 72, 30), (132, 102, 42), (170, 138, 60), (204, 174, 90), (230, 206, 128))
CLOTH = ((150, 52, 44), (196, 76, 60), (220, 206, 176))
BLOOMS = ((196, 66, 62), (226, 190, 82), (154, 104, 186), (232, 228, 214))
# The clay bed under the square, where slabs have been lifted.
CLAY = ((50, 34, 26), (74, 50, 36), (98, 66, 46), (122, 84, 58), (144, 104, 72), (168, 128, 92))
LICHEN = ((98, 104, 80), (128, 132, 98), (158, 158, 118))
# The mill: bronze fittings (Windehus buys mill bearings from the south), weathered copper,
# fresh pine sails, a dark shingled cap and rubble stone in four colours.
BRONZE = ((56, 34, 20), (96, 60, 30), (142, 94, 42), (188, 136, 62), (226, 182, 100), (250, 224, 158))
VERDIGRIS = ((44, 88, 76), (74, 130, 108), (120, 176, 146))
SAILWOOD = ((70, 48, 30), (112, 80, 48), (156, 118, 72), (198, 160, 104), (230, 202, 146))
CAP = ((20, 22, 30), (32, 36, 48), (46, 52, 68), (64, 72, 92), (88, 96, 118), (118, 126, 148))
RUBBLE = (FLAG,
          ((62, 50, 36), (90, 74, 50), (120, 98, 66), (148, 124, 86), (174, 150, 108), (202, 180, 136)),
          ((60, 40, 32), (86, 58, 44), (114, 78, 58), (140, 100, 74), (166, 124, 94), (192, 152, 120)),
          ((46, 50, 56), (66, 72, 80), (88, 94, 102), (112, 118, 124), (136, 142, 146), (164, 168, 170)))
RUBBLE_MORTAR = (128, 120, 102)


# --- helpers -----------------------------------------------------------------------------------
def noise(x, y, seed=0):
    n = (int(x) * 374761393 + int(y) * 668265263 + seed * 982451653) & 0xFFFFFFFF
    n = (n ^ (n >> 13)) * 1274126177 & 0xFFFFFFFF
    return ((n ^ (n >> 16)) & 0xFFFF) / 0xFFFF


def mix(a, b, t):
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def ramp(r, v):
    return r[max(0, min(len(r) - 1, int(v)))]


def surface(w, h):
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    s.fill(CLEAR)
    return s


def put(s, x, y, color):
    if 0 <= x < s.get_width() and 0 <= y < s.get_height():
        s.set_at((int(x), int(y)), color)


def solid(s, x, y):
    return 0 <= x < s.get_width() and 0 <= y < s.get_height() and s.get_at((int(x), int(y)))[3] > 200


def soft_outline(s, color=INK, lit_mix=.45):
    """Dark ink on the shadow side (right and below); a rim blended from the edge colour on
    the lit side, so silhouettes hold without a hard black ring."""
    w, h = s.get_size()
    rims = {}
    for y in range(h):
        for x in range(w):
            if not solid(s, x, y):
                continue
            edge = s.get_at((x, y))[:3]
            for nx, ny, shadow in ((x + 1, y, True), (x, y + 1, True), (x - 1, y, False), (x, y - 1, False)):
                if 0 <= nx < w and 0 <= ny < h and not s.get_at((nx, ny))[3]:
                    if shadow:
                        rims[(nx, ny)] = color
                    elif (nx, ny) not in rims:
                        rims[(nx, ny)] = mix(edge, color, lit_mix)
    for spot, rim in rims.items():
        s.set_at(spot, rim)


def shaded(color):
    """An opaque colour under the town's flat shade."""
    return mix(color[:3], SHADE[:3], SHADE[3] / 255)


def line(s, x0, y0, x1, y1, color):
    steps = max(1, int(max(abs(x1 - x0), abs(y1 - y0)) * 3))
    for i in range(steps + 1):
        put(s, round(x0 + (x1 - x0) * i / steps), round(y0 + (y1 - y0) * i / steps), color)


def _wrap(d):
    d = abs(d) % TEX
    return min(d, TEX - d)


def _signed(d):
    return (d + TEX / 2) % TEX - TEX / 2


# --- paving textures (64 x 64, seamless) ----------------------------------------------------------
def _nearest(points, x, y):
    best = sorted((_wrap(x - px) ** 2 + _wrap(y - py) ** 2, i) for i, (px, py) in enumerate(points))
    return best[0][1], best[0][0] ** .5, best[1][0] ** .5


def cobble_texture():
    """Round field cobbles in loose staggered rows, earthy mortar with a little moss."""
    points = []
    rows, cols = 12, 11   # about 6 x 5 px stones; both divide the 64 px repeat evenly
    for r in range(rows):
        for c in range(cols):
            ox = TEX / cols / 2 if r % 2 else 0
            points.append(((c * TEX / cols + ox + (noise(c, r, 11) - .5) * 1.6) % TEX,
                           (r * TEX / rows + 2.6 + (noise(c, r, 12) - .5) * 1.2) % TEX))
    color, cell = {}, {}
    for y in range(TEX):
        for x in range(TEX):
            i, d1, d2 = _nearest(points, x + .5, y + .5)
            px, py = points[i]
            cell[(x, y)] = (px, py)
            edge = d2 - d1
            if edge < .8:
                moss = noise(x, y, 13) > .82
                color[(x, y)] = mix(MORTAR, MOSS[1], .6) if moss else mix(MORTAR, COBBLE[1], .5)
                continue
            dx, dy = _signed(x + .5 - px), _signed(y + .5 - py)
            tone = 2.3 + noise(i, 0, 14) * 1.7 - (dx + dy) * .3 - (.6 if edge < 1.5 else 0)
            color[(x, y)] = ramp(COBBLE, tone + (noise(x, y, 15) - .5) * .5)
    return color, cell


FLAG_PLAN = {}   # the square's slab plan, kept for the lifted-slab decals


def _crumbling(x, y):
    return noise(x // 5, y // 5, 28) > .7


def _grout(x, y):
    """Grout between the square's slabs: dark and gritty, crumbling to open gaps, loose grit
    and the odd weed in patches."""
    n = noise(x, y, 29)
    if _crumbling(x, y):
        if n > .94:
            return MOSS[1] if noise(x, y, 30) > .5 else TUFT[0]
        if n > .58:
            return mix(SQUARE[2], DIRT[3], .45)
        return mix(SQUARE[0], INK, .55) if n < .3 else SQUARE[1]
    return SQUARE[1] if n > .84 else SQUARE[0]


def flag_texture():
    """The market square: dark slabs of mixed sizes laid in no fixed rows, small here and
    large there. No slab is left flat: each has its own grain (specked, banded or mottled),
    pits that catch the light, a worn bevel and a footworn middle; some have chipped corners,
    lichen or a hairline crack. The grout crumbles in patches, and a few long cracks run
    across several stones."""
    rng = random.Random(27)
    units = TEX // 4
    owner, slabs = {}, []
    sizes = ((3, 3), (3, 2), (2, 3), (2, 2), (4, 3), (3, 4), (2, 1), (1, 2), (1, 1), (4, 4), (5, 3))
    weights = (5, 5, 5, 7, 2, 2, 3, 3, 2, 1, 1)
    for uy in range(units):
        for ux in range(units):
            if (ux, uy) in owner:
                continue
            for w, h in rng.choices(sizes, weights, k=8) + [(1, 1)]:
                cells = [((ux + i) % units, (uy + j) % units) for i in range(w) for j in range(h)]
                if all(c not in owner for c in cells):
                    for c in cells:
                        owner[c] = len(slabs)
                    sw, sh = w * 4, h * 4
                    big = sw >= 8 and sh >= 8
                    slabs.append(dict(
                        x=ux * 4, y=uy * 4, w=sw, h=sh, base=2.0 + rng.random() * 1.1,
                        grain=rng.choice(("speck", "speck", "band", "mottle")),
                        chips={c for c in ("tl", "tr", "bl", "br") if rng.random() < .3} if big else set(),
                        lichen=[(rng.randint(2, sw - 3), rng.randint(2, sh - 3))] if big and rng.random() < .18 else [],
                        crack=big and rng.random() < .35, seed=200 + len(slabs) * 7))
                    break
    color, cell, joints, pits = {}, {}, set(), []
    for y in range(TEX):
        for x in range(TEX):
            sl = slabs[owner[(x // 4, y // 4)]]
            w, h = sl["w"], sl["h"]
            lx, ly = (x - sl["x"]) % TEX, (y - sl["y"]) % TEX
            cell[(x, y)] = ((sl["x"] + w / 2) % TEX, (sl["y"] + h / 2) % TEX)
            corner = ("t" if ly == 1 else "b" if ly == h - 1 else "") + ("l" if lx == 1 else "r" if lx == w - 1 else "")
            if lx == 0 or ly == 0 or corner in sl["chips"]:
                joints.add((x, y))
                color[(x, y)] = _grout(x, y)
                continue
            seed = sl["seed"]
            tone = sl["base"] + (ly == 1) * .9 + (lx == 1) * .5 - (ly == h - 1) * .8 - (lx == w - 1) * .5
            n = noise(x, y, seed)
            if sl["grain"] == "speck":
                tone += 1.0 if n > .84 else -.9 if n < .1 else 0
            elif sl["grain"] == "band":
                tone += .5 * sin((ly + lx * .3) * 1.3 + seed) + (1.0 if n > .9 else 0)
            else:
                tone += (noise(x // 2, y // 2, seed) - .5) * 1.2 + (-.9 if n < .08 else 0)
            if w * h >= 96:
                edge = max(abs(lx - w / 2) / (w / 2), abs(ly - h / 2) / (h / 2))
                tone += .4 * (1 - edge)
            tone += (noise(x, y, 26) - .5) * .3
            if noise(x, y, 33) > .975 and 1 < lx < w - 1 and 1 < ly < h - 1:
                pits.append((x, y))
                tone = 0
            color[(x, y)] = ramp(SQUARE, tone)
    # A pit's lower lip catches the light.
    for x, y in pits:
        lip = ((x + 1) % TEX, (y + 1) % TEX)
        if lip not in joints:
            color[lip] = SQUARE[4]
    for sl in slabs:
        for cx, cy in sl["lichen"]:
            # A ragged fleck of lichen, grown by a short random walk.
            for i in range(rng.randint(3, 6)):
                p = ((sl["x"] + cx) % TEX, (sl["y"] + cy) % TEX)
                if p not in joints:
                    color[p] = LICHEN[2] if i == 0 else LICHEN[1] if i % 3 else LICHEN[0]
                cx = max(1, min(sl["w"] - 2, cx + rng.choice((-1, 0, 1))))
                cy = max(1, min(sl["h"] - 2, cy + rng.choice((-1, 0, 0, 1))))
        if sl["crack"]:
            # A hairline crack creeping in from one edge.
            lx, ly = rng.choice(((1, rng.randint(2, sl["h"] - 3)), (rng.randint(2, sl["w"] - 3), 1)))
            down = lx != 1
            for _ in range(rng.randint(4, 7)):
                p = ((sl["x"] + lx) % TEX, (sl["y"] + ly) % TEX)
                if p in joints:
                    break
                color[p] = SQUARE[0]
                below = (p[0], (p[1] + 1) % TEX)
                if below not in joints and not down:
                    color[below] = SQUARE[4]
                if down:
                    ly += 1
                    lx += rng.choice((-1, 0, 0, 1))
                else:
                    lx += 1
                    ly += rng.choice((-1, 0, 0, 1))
                if not (1 <= lx < sl["w"] - 1 and 1 <= ly < sl["h"] - 1):
                    break
    # Where the grout crumbles, the slab edges beside it are chipped too.
    for x, y in joints:
        if not _crumbling(x, y):
            continue
        for p in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            p = (p[0] % TEX, p[1] % TEX)
            if p not in joints and noise(*p, 34) > .55:
                color[p] = SQUARE[1]
    # A few long cracks, each running across several slabs.
    for k in range(3):
        x, y = rng.uniform(0, TEX), rng.uniform(0, TEX)
        heading = rng.uniform(0, 6.28)
        for _ in range(rng.randint(16, 28)):
            heading += rng.uniform(-.7, .7)
            x, y = (x + cos(heading)) % TEX, (y + sin(heading) * .8) % TEX
            px, py = int(x), int(y)
            color[(px, py)] = SQUARE[0]
            below = (px, (py + 1) % TEX)
            if below not in joints:
                color[below] = SQUARE[4]
    FLAG_PLAN.update(slabs=slabs, joints=joints)
    return color, cell, joints


def square_gap(tx, ty, tw, th, count, seed):
    """Slabs lifted from the square, leaving the clay bed showing: dried and cracked, with
    pebbles, a weed or two and, where more than one slab is gone, a broken shard. The slab
    behind the hole shows its edge, and its shadow falls across the clay.
    A decal for fully paved square tiles whose texture origin is (tx, ty) tiles. It holds
    only the hole, so it lies over the paving without a seam."""
    slabs, joints = FLAG_PLAN["slabs"], FLAG_PLAN["joints"]
    W, H = tw * 16, th * 16
    ox, oy = tx * 16, ty * 16
    rng = random.Random(seed)

    def footprint(sl):
        pts = set()
        for a in range(sl["w"] + 1):
            for b in range(sl["h"] + 1):
                p = ((sl["x"] + a) % TEX, (sl["y"] + b) % TEX)
                if (a < sl["w"] and b < sl["h"]) or p in joints:
                    pts.add(((p[0] - ox) % TEX, (p[1] - oy) % TEX))
        return pts

    feet = {i: footprint(sl) for i, sl in enumerate(slabs)}
    fits = [i for i, pts in feet.items() if all(2 <= x < W - 2 and 2 <= y < H - 2 for x, y in pts)]
    fits.sort(key=lambda i: abs(len(feet[i]) - 150))
    chosen = [fits[0]]
    while len(chosen) < count:
        hole = set().union(*(feet[i] for i in chosen))
        near = [i for i in fits if i not in chosen
                and any((x + dx, y + dy) in hole for x, y in feet[i] for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))]
        if not near:
            break
        chosen.append(max(near, key=lambda i: len(feet[i]) + rng.random() * 40))
    hole = set().union(*(feet[i] for i in chosen))
    # The slabs around the hole are broken back a pixel or two, so its edge is ragged.
    for depth, odds in ((1, .45), (2, .2)):
        rim = {(x + dx, y + dy) for x, y in hole for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))} - hole
        hole |= {p for p in rim if 2 <= p[0] < W - 2 and 2 <= p[1] < H - 2 and noise(*p, seed + depth) < odds}
    s = surface(W, H)
    cracks = [(rng.uniform(0, W), rng.uniform(0, H)) for _ in range(len(hole) // 22 + 2)]
    for x, y in sorted(hole):
        up = next((d for d in range(1, 8) if (x, y - d) not in hole), 9)
        ds = sorted((x + .5 - px) ** 2 + (y + .5 - py) ** 2 for px, py in cracks)
        tone = 2.4 + (noise(x // 2, y // 2, seed) - .5) * 1.0 + (noise(x, y, seed + 1) - .5) * .7
        c = ramp(CLAY, tone)
        if ds[1] ** .5 - ds[0] ** .5 < .7:
            c = CLAY[0]
        elif noise(x, y, seed + 2) > .94:
            c = FLAG[3]
        elif noise(x, y, seed + 3) > .965 and up > 3:
            c = TUFT[int(noise(x, y, seed + 4) * 3)]
        if up == 1:
            c = SQUARE[1]
        elif up == 2:
            c = mix(c, INK, .5)
        elif up == 3:
            c = mix(c, INK, .25)
        if (x - 1, y) not in hole and up > 1:
            c = mix(c, INK, .3)
        s.set_at((x, y), c)
    if len(chosen) > 1:
        # A broken corner of slab lying in the clay.
        xs = sorted(x for x, y in hole)
        ys = sorted(y for x, y in hole)
        sx, sy = xs[len(xs) // 2] - 2, ys[len(ys) // 2]
        for j, row in enumerate((".###", "####", "###.")):
            for i, ch in enumerate(row):
                if ch == "#" and (sx + i, sy + j) in hole:
                    s.set_at((sx + i, sy + j), SQUARE[(4, 3, 1)[j]])
        for i in range(4):
            if (sx + i, sy + 3) in hole:
                s.set_at((sx + i, sy + 3), mix(s.get_at((sx + i, sy + 3))[:3], INK, .4))
    return s


def brick_texture():
    """Basket-weave brick paving: pairs of bricks turning a quarter in each 8 x 8 square."""
    color, cell = {}, {}
    for y in range(TEX):
        for x in range(TEX):
            bx, by = x // 8, y // 8
            lx, ly = x % 8, y % 8
            if (bx + by) % 2:
                brick = (bx, by, ly // 4)
                joint = ly % 4 == 3 or lx == 7
                top, left = ly % 4 == 0, lx == 0
                cell[(x, y)] = (bx * 8 + 4, by * 8 + (ly // 4) * 4 + 2)
            else:
                brick = (bx, by, 2 + lx // 4)
                joint = lx % 4 == 3 or ly == 7
                top, left = ly == 0, lx % 4 == 0
                cell[(x, y)] = (bx * 8 + (lx // 4) * 4 + 2, by * 8 + 4)
            if joint:
                color[(x, y)] = mix(BRICK[0], MORTAR, .5)
                continue
            tone = 2.0 + noise(*brick[:2], 31 + brick[2]) * 1.6 + top * .9 + left * .4
            color[(x, y)] = ramp(BRICK, tone + (noise(x, y, 32) - .5) * .5)
    return color, cell


def dirt_texture():
    """Packed road dirt: two scales of grain, pebbles, a few blades of grass."""
    color, cell = {}, {}
    for y in range(TEX):
        for x in range(TEX):
            cell[(x, y)] = (x + .5, y + .5)
            coarse = noise(x // 4, y // 3, 41) * .9 + noise(x // 8, y // 8, 42) * .7
            tone = 1.5 + coarse + (noise(x, y, 43) - .5) * .8
            if noise(x, y, 44) > .96:
                tone = 4.6
                color[(x, (y + 1) % TEX)] = DIRT[0]
            color.setdefault((x, y), None)
            color[(x, y)] = ramp(DIRT, tone)
            if noise(x, y, 45) > .975:
                color[(x, y)] = TUFT[1]
    return color, cell


def ground_sheet(texture, ragged, rim=INK, moss=False):
    """Every (sub-tile, corner mask) of a paving, over transparent grass. Stones are kept or
    dropped whole (the mask is read at each stone's centre), so edges follow the stones.
    With moss, it creeps into the joints and corners nearest the grass."""
    color, cell = texture[0], texture[1]
    joints = texture[2] if len(texture) > 2 else set()
    sheet = surface(256, 256)
    for sub in range(16):
        ox, oy = sub % 4 * 16, sub // 4 * 16
        for mask in range(1, 16):
            c = [bool(mask & bit) for bit in (1, 2, 4, 8)]
            keep = set()
            for y in range(16):
                for x in range(16):
                    if mask == 15:
                        keep.add((x, y))
                        continue
                    cx, cy = cell[(ox + x, oy + y)]
                    u = min(15.5, max(.5, _signed(cx - ox - 8) + 8)) / 16
                    v = min(15.5, max(.5, _signed(cy - oy - 8) + 8)) / 16
                    w = (c[0] * (1 - u) * (1 - v) + c[1] * u * (1 - v) + c[2] * (1 - u) * v + c[3] * u * v)
                    w += (noise(ox + x, oy + y, 51) - .5) * ragged
                    if w > .5:
                        keep.add((x, y))
            # How far each kept pixel is from the grass, for moss.
            reach = {}
            frontier = [(x, y) for y in range(16) for x in range(16) if (x, y) not in keep]
            for p in frontier:
                reach[p] = 0
            while frontier:
                nxt = []
                for x, y in frontier:
                    for n in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                        if n in keep and n not in reach:
                            reach[n] = reach[(x, y)] + 1
                            nxt.append(n)
                frontier = nxt
            for x, y in keep:
                tone = color[(ox + x, oy + y)]
                d = reach.get((x, y), 99)
                if d == 1:
                    tone = mix(tone, rim, .3)
                if moss and d <= 4 and (ox + x, oy + y) in joints:
                    tone = MOSS[int(noise(ox + x, oy + y, 54) * 3)]
                elif moss and d <= 2 and noise(ox + x, oy + y, 55) > .5:
                    tone = mix(tone, MOSS[1], .65)
                sheet.set_at((mask * 16 + x, sub * 16 + y), tone)
            # Grass tufts lean over the paving edge.
            for y in range(16):
                for x in range(16):
                    if (x, y) in keep or noise(ox + x, oy + y, 52) < .55:
                        continue
                    if any(n in keep for n in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1))):
                        sheet.set_at((mask * 16 + x, sub * 16 + y), TUFT[int(noise(x, y, 53) * 3)])
    return sheet


# --- retaining walls, stairs, terrace edges ----------------------------------------------------------
def _wall_pixel(x, y, seed):
    course, row = y // 4, y % 4
    shift = 4 if course % 2 else 0
    bx = (x + shift) % 8
    if row == 3 or bx == 7:
        return WALL[0]
    block = ((x + shift) // 8, course)
    tone = 2.2 + (noise(*block, seed) - .5) * 1.3 + (row == 0) * .9 + (bx == 0) * .5 - (row == 2) * .5 - (bx == 6) * .4
    return ramp(WALL, tone + (noise(x, y, seed + 1) - .5) * .4)


def wall_tile(kind, end, variant):
    """A retaining-wall face tile. kind: top (with coping), mid, base (with plinth) or solo;
    end: l, m or r (quoins at the ends); variant: 0 plain, 1 mossy, 2 ivy."""
    s = surface(16, 16)
    seed = 60 + variant * 7
    for y in range(16):
        for x in range(16):
            s.set_at((x, y), _wall_pixel(x, y + (0 if kind in ("top", "solo") else 16), seed))
    if kind in ("top", "solo"):
        for x in range(16):
            joint = (x + 3) % 8 == 0
            for y in range(3):
                s.set_at((x, y), ramp(WALL, (4.4 if y == 0 else 3.9) - joint * 1.2 + (noise(x, y, 61) - .5) * .4))
            s.set_at((x, 3), WALL[2] if not joint else WALL[1])
            s.set_at((x, 4), WALL[0])
    if kind in ("base", "solo"):
        for x in range(16):
            s.set_at((x, 13), ramp(WALL, 3.4 - ((x + 5) % 8 == 0)))
            s.set_at((x, 14), ramp(WALL, 2.0 + (noise(x, 14, 62) - .5) * .5))
            s.set_at((x, 15), WALL[0])
    if variant == 1:
        for y in range(6, 16):
            for x in range(16):
                if noise(x, y, 63) > .9 - (y - 6) * .03:
                    s.set_at((x, y), MOSS[int(noise(x, y, 64) * 3)])
    if variant == 2:
        for start in (3, 11):
            x = start
            for y in range(4 if kind in ("top", "solo") else 0, 13):
                x += round((noise(start, y, 65) - .5) * 1.4)
                put(s, x, y, MOSS[1])
                if noise(start, y, 66) > .55:
                    put(s, x + (1 if y % 2 else -1), y, MOSS[2] if y % 3 else MOSS[0])
    for side, cols in (("l", range(0, 3)), ("r", range(13, 16))):
        if end != side:
            continue
        for y in range(16):
            quoin = (y // 4) % 2
            for i, x in enumerate(cols):
                if side == "l" and i == 2 and quoin:
                    continue
                if side == "r" and i == 0 and quoin:
                    continue
                edge = (side == "l" and i == 0) or (side == "r" and i == 2)
                tone = 3.4 - (y % 4 == 3) * 2 + (y % 4 == 0) * .6 - edge * (1.4 if side == "r" else -.4)
                s.set_at((x, y), ramp(WALL, tone))
    return s


def stairs_tile(kind, end):
    """Stone steps cut through a retaining wall, with cheek walls at the ends of the flight."""
    s = surface(16, 16)
    for y in range(16):
        step = y % 4
        for x in range(16):
            wear = 1 - abs(x - 7.5) / 8
            tone = (4.4, 3.4, 3.0, 1.2)[step] - wear * .3 * (step != 3) + (noise(x, y, 71) - .5) * .4
            s.set_at((x, y), ramp(FLAG, tone))
    if kind in ("top", "solo"):
        for x in range(16):
            s.set_at((x, 0), FLAG[5])
            s.set_at((x, 1), FLAG[3])
    if kind in ("base", "solo"):
        for x in range(16):
            s.set_at((x, 15), FLAG[0])
    for side, cols in (("l", (0, 1, 2)), ("r", (13, 14, 15))):
        if end not in (side, "solo"):
            continue
        for y in range(16):
            for i, x in enumerate(cols):
                outer = (side == "l" and i == 0) or (side == "r" and i == 2)
                inner = not outer and i != 1
                tone = 4.2 if y < 2 and kind in ("top", "solo") else 2.4 + outer * (.9 if side == "l" else -1.0) - inner * 1.1
                s.set_at((x, y), ramp(WALL, tone - (y % 4 == 3) * .8))
    if end in ("l", "solo"):
        # The west cheek wall shades the flight. The lower the step, the taller the cheek
        # stands over it, so the shade widens step by step on the way down.
        for y in range(16):
            step = y // 4 + (4 if kind in ("mid", "base") else 0)
            for x in range(3, 3 + round(1 + step * 1.25)):
                s.set_at((x, y), shaded(s.get_at((x, y))))
    return s


def side_edge(side):
    """Coping along a terrace's west (l) or east (r) edge, drawn over the upper ground."""
    s = surface(16, 16)
    order = (0, 1, 2, 3) if side == "l" else (15, 14, 13, 12)
    for y in range(16):
        joint = y % 8 == 7
        for i, x in enumerate(order):
            if i == 0:
                color = WALL[1] if side == "l" else WALL[0]
            else:
                color = ramp(WALL, (4.2 if i == 1 else 3.7 if i == 2 else 3.0) - joint * 1.2)
            s.set_at((x, y), color)
        inner = order[3] + (1 if side == "l" else -1)
        s.set_at((inner, y), (16, 14, 20, 70))
    return s


def wall_shadow():
    s = surface(16, 16)
    for y, alpha in enumerate((120, 84, 50, 24, 10)):
        for x in range(16):
            s.set_at((x, y), (16, 14, 20, alpha))
    return s


# --- fences and low walls -----------------------------------------------------------------------
def fence_h(end):
    """A rail fence across the tile: two rails, square posts with lit caps."""
    s = surface(16, 16)
    left = 2 if end in ("l", "solo") else 0
    right = 13 if end in ("r", "solo") else 16
    for y, tone in ((7, 4.4), (8, 2.6), (11, 4.0), (12, 2.4)):
        for x in range(left, right):
            s.set_at((x, y), ramp(WOOD, tone + (noise(x, y, 81) - .5) * .5))
    posts = {"l": (2, 11), "m": (3, 11), "r": (3, 11), "solo": (6,)}[end]
    for px in posts:
        for y in range(4, 16):
            s.set_at((px, y), ramp(WOOD, 4.2 if y > 4 else 5.2))
            s.set_at((px + 1, y), ramp(WOOD, 2.0 if y > 4 else 4.4))
    soft_outline(s)
    return s


def fence_v():
    """A rail fence running north-south, seen from above: posts and a single top rail."""
    s = surface(16, 16)
    for y in range(16):
        s.set_at((7, y), WOOD[4])
        s.set_at((8, y), WOOD[2])
    for py in (2, 10):
        for y in range(py, py + 3):
            for x in range(6, 10):
                s.set_at((x, y), ramp(WOOD, 5 if y == py else 3.6 if x < 8 else 2.2))
        for x in range(6, 10):
            s.set_at((x, py + 3), WOOD[1])
    soft_outline(s)
    return s


def fence_gate():
    s = fence_h("m")
    for y in range(6, 14):
        for x in range(5, 11):
            s.set_at((x, y), ramp(WOOD, 3.4 - (x % 2) * .8 - (y == 13) * 1.2))
    for i in range(6):
        put(s, 5 + i, 12 - i, WOOD[1])
    return s


def low_wall(end):
    """A dry-stone garden wall, about knee high, mossy along the top."""
    s = surface(16, 16)
    left = 1 if end in ("l", "solo") else 0
    right = 15 if end in ("r", "solo") else 16
    for course, y0 in enumerate((7, 11)):
        x = left - (2 if course else 0)
        while x < right:
            w = 3 + int(noise(x, course, 91) * 3)
            for y in range(y0, y0 + 4):
                for xx in range(max(left, x), min(right, x + w)):
                    if (xx == x or xx == x + w - 1) and y in (y0, y0 + 3):
                        continue
                    top = y == y0
                    tone = 2.4 + noise(x, course, 92) * 1.2 + top * 1.0 - (y == y0 + 3) * .9 - (xx == x + w - 1) * .5
                    s.set_at((xx, y), ramp(WALL, tone))
            x += w
    for x in range(left, right):
        if noise(x, 0, 93) > .45:
            s.set_at((x, 7), MOSS[2] if noise(x, 1, 93) > .5 else MOSS[1])
    soft_outline(s)
    return s


# --- buildings ----------------------------------------------------------------------------------------
# Two storeys: a fieldstone footing, a ground floor tall enough for the town's one door,
# a jettied half-timbered upper floor, then the roof. Every door opening in town is the same
# 10 x 20 px as the gates in the cave.
DOOR_W, DOOR_H = 10, 20
FOOT, GROUND, JETTY, UPPER = 5, 25, 3, 22
WALL_H = FOOT + GROUND + JETTY + UPPER
ROOF_H = 28
# Some houses stand on a cellar plinth, so their door sits up off the street with a stoop
# of four 3 px steps in front of it (the "stoop" piece, drawn on the row below the house).
RAISE = 7
STOOP_RISE = FOOT + RAISE


def _window(s, x, y, h, shutter):
    """An 8 px casement: light frame, cross mullion, glints, painted shutters, a sill, and the
    lintel's shade above."""
    for xx in range(x - 1, x + 9):
        if solid(s, xx, y - 1):
            s.set_at((xx, y - 1), mix(s.get_at((xx, y - 1))[:3], INK, .35))
    for yy in range(y, y + h):
        for xx in range(x + 1, x + 7):
            if yy in (y, y + h - 1) or xx in (x + 1, x + 6):
                s.set_at((xx, yy), WOOD[4] if yy == y or xx == x + 1 else WOOD[2])
            elif xx == x + 3 or yy == y + h // 2 - 1:
                s.set_at((xx, yy), WOOD[3])
            else:
                s.set_at((xx, yy), GLASS[2] if (xx - x) + (yy - y) <= 3 else GLASS[1] if yy < y + h - 3 else GLASS[0])
    s.set_at((x + 2, y + 1), GLASS[3])
    s.set_at((x + 4, y + h // 2), GLASS[2])
    for sx in (x - 1, x, x + 7, x + 8):
        for yy in range(y, y + h):
            lit = sx in (x - 1, x + 7)
            slat = (yy - y) % 3 == 2
            s.set_at((sx, yy), mix(shutter, (255, 255, 255), .14) if lit and not slat else
                     mix(shutter, INK, .4) if slat else shutter)
    for xx in range(x - 1, x + 9):
        s.set_at((xx, y + h), WOOD[4])
        s.set_at((xx, y + h + 1), WOOD[1])


def _flower_box(s, x, y, seed):
    for xx in range(x - 1, x + 9):
        s.set_at((xx, y + 1), WOOD[3])
        s.set_at((xx, y + 2), WOOD[1])
        n = noise(xx, y, seed)
        if n > .2:
            s.set_at((xx, y), BLOOMS[int(noise(xx, y, seed + 1) * 3)] if n > .55 else LEAF[3])
            if n > .8:
                put(s, xx, y - 1, LEAF[4])


def _door(s, x, y):
    """The town's one door: a 10 x 20 opening of planks with iron straps and a ring, set in a
    dark frame under a lintel beam. Returns its rectangle."""
    for xx in range(x - 2, x + DOOR_W + 2):
        s.set_at((xx, y - 2), WOOD[4])
        s.set_at((xx, y - 1), WOOD[1])
    for yy in range(y, y + DOOR_H):
        s.set_at((x - 1, yy), WOOD[0])
        s.set_at((x + DOOR_W, yy), WOOD[0])
        for xx in range(x, x + DOOR_W):
            k = (xx - x) % 3
            tone = (3.3, 2.7, 1.2)[k] - (yy > y + DOOR_H - 3) * .5 - (xx > x + 6) * .3
            s.set_at((xx, yy), ramp(WOOD, tone))
    for xx in (x, x + DOOR_W - 1):
        s.set_at((xx, y), WOOD[0])
    for yy in (y + 4, y + 14):
        for xx in range(x, x + DOOR_W - 1):
            s.set_at((xx, yy), IRON[1])
        s.set_at((x + 1, yy), IRON[3])
    s.set_at((x + 7, y + 9), IRON[3])
    s.set_at((x + 7, y + 10), IRON[1])
    s.set_at((x + 6, y + 10), IRON[2])
    return [x, y, DOOR_W, DOOR_H]


def _cellar_plinth(s, x0, x1, top, bottom, width, doors, seed):
    """A raised house's plinth: a lit coping over two courses of big dressed blocks, with
    barred cellar vents between the doors."""
    for y in range(top, bottom):
        r = y - top
        for x in range(x0 - 1, x1 + 1):
            if r < 2:
                joint = (x - x0) % 12 == 11
                s.set_at((x, y), ramp(FLAG, (4.6 if r == 0 else 3.2) - joint * 1.0))
                continue
            if r == 2:
                s.set_at((x, y), mix(FLAG[1], INK, .25))
                continue
            course, row = divmod(r - 3, 5)
            bx = (x - x0 + course * 6) % 12
            if row == 4 or bx == 11 or y == bottom - 1:
                s.set_at((x, y), FLAG[0])
                continue
            block = ((x - x0 + course * 6) // 12, course)
            tone = 2.2 + (noise(*block, seed + 5) - .5) * 1.2 + (row == 0) * .8 + (bx == 0) * .4 - (row == 3) * .5
            s.set_at((x, y), ramp(FLAG, tone + (noise(x, y, seed + 6) - .5) * .5))
    for t in range(width):
        if t in doors or (t + seed) % 2:
            continue
        cx = 16 * t + 8
        for x in range(cx - 4, cx + 4):
            s.set_at((x, top + 3), FLAG[4])
        for y in range(top + 4, top + 8):
            for x in range(cx - 3, cx + 3):
                s.set_at((x, y), GLASS[0] if (x - cx) % 2 else IRON[3] if y == top + 4 else IRON[2])


def stoop():
    """Four 3 px steps up to a raised door, standing out from the cellar plinth toward the
    viewer between two stone cheeks. The house's ground line is y = 12 here and the landing
    meets the door sill at y = 0, so the flight reaches 12 px out into the street. The west
    cheek shades the steps, and the flight casts a little shade east on the ground."""
    s = surface(20, 24)
    for y in range(24):
        r = y % 6
        for x in range(2, 14):
            wear = 1 - abs(x - 7.5) / 6
            tone = (4.4, 3.8, 3.3)[r] + wear * .4 if r < 3 else (2.4, 1.9, 1.3)[r - 3]
            s.set_at((x, y), ramp(FLAG, tone + (noise(x, y, 120) - .5) * .5))
        for x, tone in ((0, 4.2), (1, 3.3), (14, 2.9), (15, 1.9)):
            face = y >= 20
            tone = tone - 1.2 if face else tone
            if y % 5 == 4 and not face:
                tone -= .9
            s.set_at((x, y), ramp(FLAG, tone + (y == 0) * 1.2))
        for x in range(3, 3 + 1 + y // 6):
            s.set_at((x, y), shaded(s.get_at((x, y))))
        if y >= 12:
            for x in range(16, min(20, 16 + (24 - y) // 3)):
                s.set_at((x, y), SHADE)
    soft_outline(s)
    return s


def _storeys(s, x0, x1, top, bottom, width, doors, windows, upper, boxes, ground_style, shutter, seed, raised=0):
    foot_top = bottom - FOOT - raised
    gf_top = foot_top - GROUND
    jetty_top = gf_top - JETTY
    rng = random.Random(seed)
    # Ground floor: dressed stone, or plaster with brick showing where it has fallen away.
    patches = [(rng.randint(x0 + 6, x1 - 8), rng.randint(gf_top + 5, foot_top - 6)) for _ in range(2)]
    for y in range(gf_top, foot_top):
        for x in range(x0, x1):
            if ground_style == "stone":
                course, row = divmod(y - gf_top, 5)
                bx = (x - x0 + (course % 2) * 5) % 10
                if row == 4 or bx == 9:
                    s.set_at((x, y), FLAG[0])
                    continue
                block = ((x - x0 + (course % 2) * 5) // 10, course)
                tone = 2.5 + (noise(*block, seed) - .5) * 1.4 + (row == 0) * .9 + (bx == 0) * .4 - (row == 3) * .6
                s.set_at((x, y), ramp(FLAG, tone))
            else:
                bare = any((x - px) ** 2 / 9 + (y - py) ** 2 / 4 <= 1 for px, py in patches)
                if bare:
                    joint = (y % 3 == 2) or ((x + (y // 3) * 2) % 5 == 4)
                    s.set_at((x, y), BRICK[1] if joint else ramp(BRICK, 2.8 + noise(x // 5, y // 3, seed) * .8))
                else:
                    s.set_at((x, y), ramp(PLASTER, 2.3 + (noise(x // 2, y // 2, seed) - .5) * .6))
    if ground_style != "stone":
        for px in [x0] + [16 * k - 1 for k in range(1, width)] + [x1 - 2]:
            for y in range(gf_top, foot_top):
                s.set_at((px, y), WOOD[3])
                s.set_at((px + 1, y), WOOD[1])
    # Shade under the jetty, deepest right beneath it.
    for y, t in ((gf_top, .45), (gf_top + 1, .25), (gf_top + 2, .1)):
        for x in range(x0, x1):
            s.set_at((x, y), mix(s.get_at((x, y))[:3], INK, t))
    # Fieldstone footing, or a cellar plinth under a raised house.
    if raised:
        _cellar_plinth(s, x0, x1, foot_top, bottom, width, doors, seed)
    for y in range(foot_top, bottom if not raised else foot_top):
        course = (y - foot_top) // 3
        for x in range(x0 - 1, x1 + 1):
            bx = (x + course * 3) % 6
            if (y - foot_top) % 3 == 2 or bx == 5:
                s.set_at((x, y), FLAG[0])
            else:
                s.set_at((x, y), ramp(FLAG, 2.2 + noise((x + course * 3) // 6, course, seed + 1) * 1.4
                                       + ((y - foot_top) % 3 == 0) * .8))
    # The jetty: a bressumer beam with the joist ends showing beneath the upper floor.
    for x in range(x0 - 1, x1 + 1):
        s.set_at((x, jetty_top), WOOD[4])
        s.set_at((x, jetty_top + 1), WOOD[3] if x % 4 < 2 else WOOD[0])
        s.set_at((x, jetty_top + 2), WOOD[1])
    # Upper floor: plaster panels in close studding with braces, overhanging a pixel.
    for y in range(top, jetty_top):
        for x in range(x0 - 1, x1 + 1):
            s.set_at((x, y), ramp(PLASTER, 2.4 + (noise(x // 2, y // 2, seed + 2) - .5) * .6 - (y < top + 4) * .9))
    studs = sorted({x0 - 1, x1 - 1} | {16 * k - 1 for k in range(1, width)} | {16 * t + 7 for t in range(width)
                                                                           if t not in upper})
    rail = top + 11
    for x in range(x0 - 1, x1 + 1):
        for y, lit in ((top + 2, True), (top + 3, False), (rail, True), (rail + 1, False)):
            s.set_at((x, y), WOOD[3] if lit else WOOD[1])
        s.set_at((x, rail + 2), mix(s.get_at((x, rail + 2))[:3], INK, .2))
    for sx in studs:
        for y in range(top + 2, jetty_top):
            s.set_at((sx, y), WOOD[3])
            put(s, sx + 1, y, WOOD[1])
    for a, b in zip(studs, studs[1:]):
        if b - a < 6 or any(16 * t + 3 <= a + 2 <= 16 * t + 12 for t in upper):
            continue
        for i in range(b - a - 2):
            for y0, y1 in ((rail + 2, jetty_top - 1), (top + 4, rail - 1)):
                span = y1 - y0
                yy = y1 - round(i * span / (b - a - 3)) if (a // 8 + y0) % 2 else y0 + round(i * span / (b - a - 3))
                put(s, a + 2 + i, yy, WOOD[2])
    for t in upper:
        _window(s, 16 * t + 4, top + 5, 9, shutter)
        if t in boxes:
            _flower_box(s, 16 * t + 4, top + 15, seed + t)
    for t in windows:
        _window(s, 16 * t + 4, gf_top + 6, 10, shutter)
    rects = []
    for t in doors:
        rects.append(_door(s, 16 * t + 3, foot_top - DOOR_H))
        if raised:
            continue
        for xx in range(16 * t + 1, 16 * t + 15):
            s.set_at((xx, bottom - 2), FLAG[4])
            s.set_at((xx, bottom - 1), FLAG[2])
    return gf_top, rects


def _roof(s, x0, x1, ridge, eave, pal):
    for y in range(ridge + 3, eave + 1):
        k, r = divmod(eave - y, 3)
        shift = 2 if k % 2 else 0
        for x in range(x0, x1):
            tone = 2.6 + (x1 - x) / (x1 - x0) * .5 - (r == 0) * 1.2 + (r == 2) * .7
            if (x + shift) % 4 == 3:
                tone -= .8
            s.set_at((x, y), ramp(pal, tone + (noise(x // 2, y, 101) - .5) * .5))
    for x in range(x0 + 1, x1 - 1):
        joint = x % 5 == 0
        s.set_at((x, ridge), ramp(pal, 4.4 - joint))
        s.set_at((x, ridge + 1), ramp(pal, 3.0 - joint))
        s.set_at((x, ridge + 2), pal[0])
    for y in range(ridge + 1, eave + 1):
        s.set_at((x0, y), pal[4])
        s.set_at((x1 - 1, y), pal[1])
    for y, t in ((eave + 1, .5), (eave + 2, .25)):
        for x in range(x0 + 1, x1 - 1):
            if solid(s, x, y):
                s.set_at((x, y), mix(s.get_at((x, y))[:3], INK, t))


def _chimney(s, cx, ridge):
    top = ridge - 9
    for y in range(top, ridge + 8):
        for x in range(cx - 3, cx + 3):
            row = (y - top) // 2
            joint = (y - top) % 2 == 1 or (x + row * 2) % 4 == 3
            tone = 2.6 + (x == cx - 3) * 1.2 - (x == cx + 2) * 1.2 - joint * .9
            s.set_at((x, y), ramp(BRICK, tone))
    for x in range(cx - 4, cx + 4):
        s.set_at((x, top - 1), FLAG[4])
        s.set_at((x, top), FLAG[2])
    for x in range(cx - 2, cx + 2):
        s.set_at((x, top - 2), FLAG[1])


def _gable(s, gx0, gx1, eave, pal, window, seed):
    """A cross gable: a chevron of roof over a timbered triangle, rising above the main eave."""
    xc = (gx0 + gx1) / 2
    rise = round((gx1 - gx0) / 2 * 1.1)
    peak, depth = eave - rise, 8
    left, right = gx0 - 3, gx1 + 3

    def edge(x):
        if x < xc:
            return eave + 1 - (x - left) * (eave + 1 - (peak - 2)) / (xc - left)
        return eave + 1 - (right - x) * (eave + 1 - (peak - 2)) / (right - xc)

    for x in range(left, right):
        e = edge(x + .5)
        for y in range(int(e) - depth - 2, int(e) + 1):
            dist = e - (y + .5)
            if not 0 <= dist <= depth or y < 0:
                continue
            lit = x < xc
            course = int(dist / 3)
            r = dist % 3
            tone = (3.4 if lit else 2.0) - (r < 1) * 1.0 + (r > 2) * .5 - ((x + course * 2) % 4 == 3) * .7
            s.set_at((x, y), ramp(pal, tone + (noise(x // 2, y, seed) - .5) * .4))
    for y in range(max(0, peak - 2 - depth), peak - 1):
        put(s, int(xc) - 1, y, pal[4])
        put(s, int(xc), y, pal[2])
    collar = eave - round(rise * .45)
    for x in range(gx0, gx1):
        e = edge(x + .5)
        for y in range(int(e) + 1, eave + 1):
            if y == int(e) + 1:
                s.set_at((x, y), WOOD[1])
                continue
            s.set_at((x, y), ramp(PLASTER, 2.3 + (noise(x // 2, y // 2, seed + 1) - .5) * .6 - (y < int(e) + 4) * .8))
            if y in (collar, eave - 1, eave) or abs(x + .5 - xc) < 1:
                s.set_at((x, y), WOOD[3] if (y == collar or y == eave - 1 or x < xc) else WOOD[1])
    if window and rise >= 13:
        wx, wy = int(xc) - 3, collar + 2
        for y in range(wy, wy + 5):
            for x in range(wx, wx + 6):
                edge_px = y in (wy, wy + 4) or x in (wx, wx + 5)
                s.set_at((x, y), WOOD[3] if edge_px else (GLASS[2] if x + y < wx + wy + 4 else GLASS[1]))


def _sign(s, x, y, icon):
    """A board hung from an iron arm, painted with the trade's mark."""
    for xx in range(x - 1, x + 10):
        s.set_at((xx, y), IRON[2])
    s.set_at((x - 1, y + 1), IRON[1])
    for cx in (x + 1, x + 8):
        s.set_at((cx, y + 1), IRON[1])
    for yy in range(y + 2, y + 10):
        for xx in range(x, x + 10):
            edge = yy in (y + 2, y + 9) or xx in (x, x + 9)
            s.set_at((xx, yy), WOOD[1] if edge else ramp(WOOD, 3.8 - (xx > x + 6) * .6))
    _icon(s, x + 2, y + 3, icon)


def _icon(s, x, y, icon):
    ink, hi = (44, 30, 26), (230, 214, 176)
    shapes = {
        "mug": ["#####.", "#.#.##", "#.#..#", "#.#.##", "####..", "####.."],
        "bed": ["#.....", "#.....", "#.###.", "######", "#....#", "#....#"],
        "sword": ["....#.", "...#..", "..#...", "##....", ".#....", "#.#..."],
        "shield": ["######", "#.##.#", "#.##.#", ".####.", ".####.", "..##.."],
        "flask": ["..##..", "..##..", ".#..#.", "#.##.#", "#.##.#", ".####."],
        "loaf": ["......", ".####.", "#.#.##", "######", "######", "......"],
    }
    for j, row in enumerate(shapes[icon]):
        for i, ch in enumerate(row):
            if ch == "#":
                put(s, x + i, y + j, ink)
    if icon in ("shield", "flask"):
        put(s, x + 1, y + 1, hi)


def building(width, roof, gables=(), doors=(), windows=(), upper=(), boxes=(), chimney=None, sign=None,
             ground="plaster", shutter=(78, 96, 72), stoop=False, seed=0):
    """A two-storey timber house: a stone or plaster ground floor with the town's one door,
    a jettied half-timbered upper floor, a tiled roof with cross gables, an optional chimney
    and trade sign. With stoop, it stands on a cellar plinth and its door is up a flight of
    steps. Width in tiles. Returns (sprite, door rectangles)."""
    W = width * 16
    raised = RAISE if stoop else 0
    rises = [round(gw * 16 / 2 * 1.1) for _, gw in gables]
    above = max([ROOF_H + 4] + [r + 12 for r in rises] + ([ROOF_H + 12] if chimney is not None else []))
    H = (WALL_H + raised + above + 15) // 16 * 16
    s = surface(W, H)
    eave = H - WALL_H - raised
    ridge = eave - ROOF_H
    gf_top, doors_at = _storeys(s, 3, W - 3, eave, H, width, doors, windows, upper, boxes, ground, shutter, seed,
                                raised)
    _roof(s, 1, W - 1, ridge, eave, roof)
    if chimney is not None:
        _chimney(s, chimney * 16 + 8, ridge)
    for i, (gx, gw) in enumerate(gables):
        _gable(s, gx * 16 + 4, (gx + gw) * 16 - 4, eave, roof, True, seed + 10 + i)
    if sign is not None:
        t, icon = sign
        _sign(s, 16 * t + 3, gf_top + 3, icon)
    soft_outline(s)
    return s, doors_at


def shade_tile(kind):
    """Shade cast by a building onto the ground east of it (light comes from the top left):
    strip (the left half of a tile), strip-top (its diagonal start), strip-end (the tail
    beyond the building's front corner), full. stair-foot goes on the ground below the west
    end of a stair flight, where the cheek wall's shade runs out."""
    s = surface(16, 16)
    for y in range(16):
        for x in range(16):
            if (kind == "full" or (kind == "strip" and x < 8) or (kind == "strip-top" and x < 8 and y >= 8 - x)
                    or (kind == "strip-end" and x < 8 and y < 8 - x)
                    or (kind == "stair-foot" and y < 7 and x < 13 - y * 1.6)):
                s.set_at((x, y), SHADE)
    return s


def ground_shadow(s, cx, cy, rx, ry):
    """A flat oval of shade on the ground, drawn under a prop before the prop itself."""
    for y in range(int(cy - ry), int(cy + ry) + 1):
        for x in range(int(cx - rx), int(cx + rx) + 1):
            if (x + .5 - cx) ** 2 / rx ** 2 + (y + .5 - cy) ** 2 / ry ** 2 <= 1 and not solid(s, x, y):
                put(s, x, y, SHADE)


# --- props --------------------------------------------------------------------------------------------
def barrel():
    s = surface(16, 16)
    ground_shadow(s, 10, 14.5, 5, 1.5)
    for y in range(3, 15):
        bulge = 1 if 5 <= y <= 12 else 0
        for x in range(3 - bulge, 13 + bulge):
            tone = 3.8 - (x - 2) / 11 * 2.4 - ((x - 3) % 3 == 0) * .5
            s.set_at((x, y), ramp(WOOD, tone))
        if y in (5, 12):
            for x in range(3 - bulge, 13 + bulge):
                s.set_at((x, y), IRON[3] if x < 6 else IRON[1])
    for y in range(1, 4):
        for x in range(4, 12):
            if (x - 7.5) ** 2 / 16 + (y - 2.5) ** 2 / 2.2 <= 1:
                s.set_at((x, y), WOOD[4] if y < 3 else WOOD[3])
    soft_outline(s)
    return s


def crate():
    s = surface(16, 16)
    for y in range(3, 15):
        for x in range(2, 14):
            top = y < 6
            frame = x in (2, 13) or y in (6, 14)
            tone = (4.4 if top else 3.0) - frame * .8 - (x > 10) * .6 - (not top and (y - 6) % 3 == 0) * .7
            s.set_at((x, y), ramp(WOOD, tone))
    for i in range(7):
        put(s, 3 + round(i * 10 / 6), 13 - i, WOOD[1])
    soft_outline(s)
    return s


def sacks():
    s = surface(16, 16)
    for cx, cy in ((5, 10), (11, 11)):
        for y in range(cy - 5, cy + 5):
            for x in range(cx - 4, cx + 5):
                if (x - cx) ** 2 / 18 + (y - cy) ** 2 / 22 <= 1:
                    tone = 3.2 - (x - cx + y - cy) * .25
                    s.set_at((x, y), ramp(STRAW, tone - .8))
        put(s, cx, cy - 6, STRAW[1])
        put(s, cx, cy - 5, STRAW[0])
    soft_outline(s)
    return s


def well():
    s = surface(32, 32)
    ground_shadow(s, 22, 29, 10, 2.5)
    cx, cy = 16, 20
    for y in range(12, 31):
        for x in range(3, 29):
            outer = (x - cx) ** 2 / 144 + (y - cy) ** 2 / 36
            if y > cy:
                if 3 <= x <= 28 and y <= cy + 8 and abs(x - cx) <= 12.5:
                    course = (y - cy) // 3
                    joint = (y - cy) % 3 == 2 or (x + course * 3) % 6 == 5
                    tone = 3.0 - (x - cx) / 12 * 1.2 - joint * 1.4
                    s.set_at((x, y), ramp(WALL, tone))
            if outer <= 1 and y <= cy:
                inner = (x - cx) ** 2 / 81 + (y - cy) ** 2 / 16
                s.set_at((x, y), GLASS[0] if inner <= 1 else ramp(WALL, 4.2 - (y > cy - 2) * 1.0))
    for px in (5, 26):
        for y in range(6, 22):
            s.set_at((px, y), WOOD[4])
            s.set_at((px + 1, y), WOOD[2])
    for x in range(5, 28):
        s.set_at((x, 9), WOOD[3])
        s.set_at((x, 10), WOOD[1])
    for y in range(0, 7):
        for x in range(3 + (6 - y) // 2 - 2, 29 - (6 - y) // 2 + 2):
            tone = 3.0 + (y < 2) * 1.0 - (y == 6) * 1.2 - ((x + y) % 4 == 0) * .6
            s.set_at((x, y), ramp(ROOF_RED, tone))
    for y in range(11, 15):
        s.set_at((16, y), STRAW[1])
    for y in range(15, 18):
        for x in range(14, 19):
            s.set_at((x, y), WOOD[3] if y == 15 else WOOD[2])
    soft_outline(s)
    return s


def lamp_post():
    s = surface(16, 32)
    ground_shadow(s, 11, 30, 4, 1.5)
    for y in range(10, 30):
        s.set_at((7, y), IRON[2])
        s.set_at((8, y), IRON[0])
    for y in range(28, 32):
        for x in range(5, 11):
            s.set_at((x, y), IRON[2] if y == 28 else IRON[1])
    for y in range(4, 11):
        for x in range(5, 11):
            edge = x in (5, 10) or y in (4, 10)
            s.set_at((x, y), IRON[1] if edge else (FLAME[2] if y < 7 else FLAME[1]))
    for i, y in enumerate(range(1, 4)):
        for x in range(6 - i, 10 + i):
            s.set_at((x, y), IRON[2] if x < 8 else IRON[1])
    soft_outline(s)
    return s


def bench():
    s = surface(32, 16)
    for x in range(2, 30):
        for y, tone in ((3, 4.4), (4, 3.0), (8, 4.6), (9, 3.4), (10, 2.0)):
            s.set_at((x, y), ramp(WOOD, tone))
    for px in (4, 26):
        for y in range(3, 15):
            s.set_at((px, y), WOOD[2])
            s.set_at((px + 1, y), WOOD[1])
    soft_outline(s)
    return s


def planter(color):
    s = surface(16, 16)
    for y in range(9, 15):
        for x in range(2, 14):
            s.set_at((x, y), ramp(WOOD, (4.4 if y == 9 else 3.0) - (x > 11) * .7 - (y % 3 == 0) * .6))
    for y in range(3, 10):
        for x in range(2, 14):
            n = noise(x, y, 120 + color)
            if (x - 8) ** 2 / 36 + (y - 8) ** 2 / 25 <= 1 and n > .25:
                s.set_at((x, y), BLOOMS[color] if n > .62 else LEAF[3 if x < 8 else 2])
    soft_outline(s)
    return s


def flower_patch(color):
    s = surface(16, 16)
    for i in range(9):
        x, y = 2 + int(noise(i, color, 130) * 12), 2 + int(noise(i, color, 131) * 12)
        put(s, x, y + 1, LEAF[2])
        put(s, x, y, BLOOMS[color])
        put(s, x + 1, y, mix(BLOOMS[color], (255, 255, 255), .3))
    return s


def bush():
    s = surface(16, 16)
    for y in range(3, 15):
        for x in range(1, 15):
            d = (x - 7.5) ** 2 / 42 + (y - 9.5) ** 2 / 30
            lump = noise(x // 2, y // 2, 140) * .3
            if d <= 1 - lump * .6:
                tone = 3.4 - (x + y - 16) * .14 + (noise(x // 2, y // 2, 141) - .5) * 1.3
                s.set_at((x, y), ramp(LEAF, tone))
    soft_outline(s)
    return s


def _clump(s, x, y, pal, tone):
    """A hand-placed leaf cluster: lit crown, full body, dark underside."""
    for j, row in enumerate((".LL.", "LMMM", "MMMD", ".DD.")):
        for i, ch in enumerate(row):
            if ch != ".":
                put(s, x + i - 2, y + j - 2, ramp(pal, tone + {"L": 1.1, "M": 0, "D": -1.2}[ch]))


def _skirt(s, cx, ground, half, seed):
    """An irregular mound of brush around a trunk's foot, with its shade to the right."""
    rng = random.Random(seed)
    ground_shadow(s, cx + 6, ground - 1.5, half + 2, 2.6)
    spots = []
    for _ in range(24):
        dx = rng.uniform(-half, half)
        spots.append((cx + dx, ground - 1 - rng.uniform(0, 7) * (1 - abs(dx) / (half + 1))))
    spots.sort(key=lambda p: p[1])
    for x, y in spots:
        tone = 3.4 - (x - cx) / half * .8 + rng.uniform(-.4, .4)
        _clump(s, round(x), round(y), LEAF, tone)


def tree_segment(part, seed=0):
    """A broadleaf tree in 16 px tiers that stack: top, mid (repeat for height), bottom
    (the shaded underside where the trunk shows) and base (trunk, roots, brush, shade).
    Crown tiers hang 4 px over the tier below, so a stack reads as one canopy."""
    s = surface(32, 20)
    rng = random.Random(sum(map(ord, part)) * 31 + seed)
    cx = 16
    if part == "base":
        for y in range(0, 15):
            for x in range(13, 19):
                bark = (x - 13) / 5
                tone = 3.6 - bark * 2.2 - ((y + x * 3) % 7 == 0) * .8
                s.set_at((x, y), ramp(WOOD, tone))
        for x, y in ((11, 14), (12, 13), (19, 13), (20, 14), (12, 14), (19, 14)):
            s.set_at((x, y), WOOD[2])
        _skirt(s, cx, 16, 13, seed)
        soft_outline(s)
        return s
    # A round crown: a dome on top, a swell through each middle tier, a rounded underside.
    profile = {"top": lambda r: 14.5 * max(0, 1 - ((15 - r) / 15) ** 2) ** .5,
               "mid": lambda r: 13 + 1.5 * sin(pi * r / 15),
               "bottom": lambda r: 3 + 10 * max(0, 1 - (r / 16) ** 2) ** .5}[part]
    rows = range(1, 16) if part == "top" else range(-1, 15)
    if part == "bottom":
        for y in range(9, 18):
            for x in range(14, 18):
                s.set_at((x, y), ramp(WOOD, 2.6 - (x - 14) * .5))
    for y in rows:
        half = profile(max(0, y))
        for _ in range(4):
            x = cx + rng.uniform(-half, half)
            lean = (x - cx) / half
            tone = 3.3 - lean * .9 - (part == "bottom") * (y / 16) * 1.6 + rng.uniform(-.3, .3)
            _clump(s, round(x), y + 2, LEAF, tone)
    soft_outline(s)
    return s


def pine_segment(part, seed=0):
    """A pine in 16 px tiers that stack: top, mid-0/1/2 (narrow to wide, so a tall pine
    tapers), and base (the widest tier, trunk, brush and shade). Each tier is three drooping
    sprays of needles, lit on the left; sprays hang over the tier below."""
    s = surface(32, 20)
    cx = 16
    widths = {"top": (1, 8), "mid-0": (6, 11), "mid-1": (8, 13), "mid-2": (10, 14.5), "base": (12, 15)}[part]
    if part == "base":
        for y in range(9, 15):
            for x in range(15, 18):
                s.set_at((x, y), ramp(WOOD, 3.0 - (x - 15)))
        _skirt(s, cx, 16, 13, seed + 3)
    sprays = 2 if part == "base" else 3
    for i in range(sprays):
        y0 = i * 5 + (1 if part == "top" else 0)
        y1 = y0 + 7
        w0 = widths[0] + (widths[1] - widths[0]) * i / 3
        w1 = widths[0] + (widths[1] - widths[0]) * (i + 1) / 3
        w0 = w0 * .7
        for y in range(y0, y1):
            t = (y - y0) / (y1 - y0 - 1)
            half = w0 + (w1 - w0) * t
            for x in range(32):
                dx = x + .5 - cx
                if abs(dx) > half:
                    continue
                if y == y1 - 1 and (x % 3 == 1 or abs(dx) < half - 3):
                    continue
                tone = 3.1 - dx / max(half, 1) * 1.2 - t * 1.1 + ((x + y * 2) % 4 == 0) * .6
                if y == y0 and abs(dx) < half:
                    tone += .5
                s.set_at((x, y), ramp(PINE, tone))
    soft_outline(s)
    return s


def stump():
    s = surface(16, 16)
    for y in range(7, 14):
        for x in range(4, 12):
            s.set_at((x, y), ramp(WOOD, 3.2 - (x - 4) * .3))
    for y in range(5, 9):
        for x in range(4, 12):
            if (x - 7.5) ** 2 / 14 + (y - 7) ** 2 / 3 <= 1:
                s.set_at((x, y), WOOD[5] if (x - 7.5) ** 2 + (y - 7) ** 2 > 3 else WOOD[4])
    soft_outline(s)
    return s


def haystack():
    s = surface(32, 32)
    ground_shadow(s, 21, 29, 13, 2.5)
    for y in range(6, 30):
        for x in range(2, 30):
            d = (x - 16) ** 2 / 196 + (y - 22) ** 2 / 256
            if d <= 1 and y <= 29:
                tone = 3.4 - (x - 10) * .06 - (y - 14) * .05 + (noise(x, y // 2, 170) - .5) * 1.4
                s.set_at((x, y), ramp(STRAW, tone))
    soft_outline(s)
    return s


def market_stall(stripe):
    s = surface(32, 32)
    ground_shadow(s, 20, 30, 13, 2)
    for px in (3, 27):
        for y in range(8, 30):
            s.set_at((px, y), WOOD[4])
            s.set_at((px + 1, y), WOOD[2])
    for y in range(18, 30):
        for x in range(2, 30):
            s.set_at((x, y), ramp(WOOD, (4.4 if y == 18 else 3.0 if y < 21 else 2.2) - (x % 6 == 0) * .6))
    goods = (BLOOMS[0], BLOOMS[1], (120, 150, 60), STRAW[3])
    for i, x in enumerate(range(5, 27, 4)):
        for dx in range(3):
            for dy in range(2):
                s.set_at((x + dx, 16 + dy), goods[i % 4] if dy == 0 else mix(goods[i % 4], INK, .3))
    for y in range(2, 12):
        for x in range(1, 31):
            band = (x // 4) % 2
            color = CLOTH[2] if band else stripe
            s.set_at((x, y), mix(color, INK, .28) if y > 8 else color)
        if y == 11:
            for x in range(1, 31):
                if x % 4 in (1, 2):
                    s.set_at((x, y + 1), mix(CLOTH[2] if (x // 4) % 2 else stripe, INK, .35))
    soft_outline(s)
    return s


def signpost():
    s = surface(16, 32)
    for y in range(4, 31):
        s.set_at((7, y), WOOD[4])
        s.set_at((8, y), WOOD[2])
    for y0, direction in ((6, 1), (12, -1)):
        for y in range(y0, y0 + 4):
            for i in range(11):
                x = 8 + i * direction if direction > 0 else 7 - i
                tip = i >= 9 and (y in (y0, y0 + 3) or i == 10 and y in (y0, y0 + 3))
                if tip:
                    continue
                s.set_at((x if direction > 0 else x, y), ramp(WOOD, 4.2 if y == y0 else 3.0))
        s.set_at((8 + 3 * direction if direction > 0 else 4, y0 + 2), (60, 44, 34))
    soft_outline(s)
    return s


def town_stone(word):
    """A broad boundary stone with the town's name cut down it in Selvar."""
    from prepare_lower_workings import carve_mask, word_strokes
    s = surface(24, 48)
    for y in range(4, 44):
        for x in range(3, 21):
            # Rounded shoulders.
            if y < 10 and ((x < 9 and (x - 9) ** 2 + (y - 10) ** 2 > 36.3)
                           or (x > 14 and (x - 14) ** 2 + (y - 10) ** 2 > 36.3)):
                continue
            light = (21 - x) / 18 * .55 + (44 - y) / 40 * .45
            s.set_at((x, y), ramp(FLAG, 1.2 + light * 3 + (noise(x, y, 180) - .5) * .6))
    for y in range(42, 47):
        for x in range(1, 23):
            s.set_at((x, y), ramp(WALL, 3.6 - (y - 42) * .5 - ((x + (y > 44) * 3) % 7 == 0) * 1.2))
    scale = .125
    _, units = word_strokes(word)
    carved = carve_mask(word, scale, (12 - 30 * scale, 8 + (32 - units * scale) / 2), (24, 48))
    for x, y in carved:
        if solid(s, x, y) and y < 42:
            s.set_at((x, y), FLAG[0])
            if solid(s, x, y + 1) and (x, y + 1) not in carved:
                s.set_at((x, y + 1), FLAG[5])
    soft_outline(s)
    return s


# --- the mill -------------------------------------------------------------------------------------------
# Windehus's landmark is a rubble-stone tower mill, tall and broad beside the town's one door
# (still 10 x 20): about five doors high and six across. Two sprites share one origin: the
# tower ("windmill", 128 x 176) and its turning sails ("windmill-sails-<n>", 128 x 128, four
# frames a sixteenth of a turn apart, with the pennant flapping).
WINDMILL_DOOR = []
MILL_W, MILL_H = 128, 184       # the canvas the tower is drawn on...
MILL_OX, MILL_OY = 16, 8        # ...and where it sits in the 144 x 192 sprite
MILL_C = 56                     # the tower's centre line: the door sits on tile column 4
MILL_TOP, MILL_BASE = 74, 174   # the tower body, measured at its limbs
MILL_K = .25                    # roundness: how deep a ring looks against its width
MILL_HUB = (MILL_C, 60)
SAIL_LEN = 64
GALLERY_Y = 113
SAIL_FRAMES = 4


def _ring(y0, half, dx):
    """Screen y of the front of a level ring this wide, dx from the centre line."""
    return y0 + MILL_K * half * sqrt(max(0.0, 1 - (dx / half) ** 2))


def _mill_half(y):
    return 23 + (y - MILL_TOP) / (MILL_BASE - MILL_TOP) * 8


def _lit(n):
    """Light on a cylinder from the top left; n runs from -1 (left limb) to 1 (right limb)."""
    return max(0.0, cos(asin(max(-1.0, min(1.0, n))) + .65))


def _arc(dx, half):
    return asin(max(-1.0, min(1.0, dx / half))) * 26


def _rubble(s):
    """The tower: rubble stone in grey, ochre, rust and blue-grey, laid in rough courses that
    bow toward the viewer, with pale lime mortar and rounded stone corners."""
    rng = random.Random(19)
    courses, v = [], MILL_TOP - 10
    while v < MILL_BASE + 12:
        h = rng.choice((4, 5, 5, 6))
        stones, a = [], -50 + rng.uniform(0, 7)
        while a < 50:
            w = rng.uniform(4.5, 9)
            stones.append((a, a + w, rng.choices(range(4), (5, 3, 2, 2))[0], rng.uniform(-.6, .6)))
            a += w
        courses.append((v, h, stones))
        v += h

    def stone(course, x, half):
        am = _arc(x + .5 - MILL_C, half)
        for i, st in enumerate(course[2]):
            if st[0] <= am < st[1]:
                return i
        return -1

    for x in range(MILL_W):
        dx = x + .5 - MILL_C
        for y in range(MILL_TOP - 4, MILL_BASE + 10):
            half = _mill_half(y)
            if abs(dx) > half or y < _ring(MILL_TOP, half, dx) - 1 or y > _ring(MILL_BASE, half, dx):
                continue
            light = _lit(dx / half)
            v = y - MILL_K * half * sqrt(max(0.0, 1 - (dx / half) ** 2))
            course = next(c for c in courses if c[0] <= v < c[0] + c[1])
            r = int(v - course[0])
            i = stone(course, x, half)
            mortar = (r == course[1] - 1 or i != stone(course, x + 1, half)
                      or (r == 0 and i != stone(course, x - 1, half))
                      or (r == course[1] - 2 and i != stone(course, x + 2, half)))
            if mortar:
                s.set_at((x, y), mix(RUBBLE_MORTAR, INK, .12 + (1 - light) * .55))
                continue
            _, _, pal, off = course[2][i]
            tone = .9 + light * 3.0 + off + (r == 0) * .7 - (r == course[1] - 2) * .6 + (noise(x, y, 191) - .5) * .7
            s.set_at((x, y), ramp(RUBBLE[pal], tone))
    # The plinth ring the tower stands on.
    hb = _mill_half(MILL_BASE) + 1.5
    for x in range(MILL_W):
        dx = x + .5 - MILL_C
        if abs(dx) > hb:
            continue
        top = int(_ring(MILL_BASE - 4, hb, dx))
        light = _lit(dx / hb)
        joint = int(_arc(dx, hb) // 7) != int(_arc(dx + 1, hb) // 7)
        for y in range(top, int(_ring(MILL_BASE + 1, hb, dx)) + 1):
            r = y - top
            tone = (2.2 + light * 2.4) if r == 0 else (1.6 + light * 1.8 - joint * 1.0)
            s.set_at((x, y), FLAG[0] if y == int(_ring(MILL_BASE + 1, hb, dx)) else ramp(FLAG, tone))


def _mill_window(s, cx, y, h=7, shutter=None):
    """A small deep-set window under a brick arch, with a stone sill."""
    narrow = abs(cx - MILL_C) > _mill_half(y) * .6
    half = 1 if narrow else 2
    for i, row in enumerate((half - 1, half, half + 1)):
        for x in range(cx - row, cx + row + 1):
            joint = (x + i) % 2
            s.set_at((x, y - 3 + i), ramp(BRICK, 3.6 - i * .5 - joint * .9 - (x > cx) * .5))
    for yy in range(y, y + h):
        for x in range(cx - half, cx + half + 1):
            edge = x == cx - half or yy == y
            glass = GLASS[3] if (x, yy) == (cx - half + 1, y + 1) else GLASS[1] if yy < y + h - 2 else GLASS[0]
            s.set_at((x, yy), GLASS[0] if edge else glass)
        if not narrow:
            s.set_at((cx, yy), WOOD[3] if yy > y else GLASS[0])
    if not narrow:
        for x in range(cx - half + 1, cx + half + 1):
            s.set_at((x, y + h // 2), WOOD[3])
    if shutter:
        for yy in range(y, y + h):
            for x, lit in ((cx - half - 1, True), (cx + half + 1, False)):
                slat = (yy - y) % 3 == 2
                s.set_at((x, yy), mix(shutter, INK, .4) if slat else mix(shutter, (255, 255, 255), .14) if lit else shutter)
    for x in range(cx - half - 1, cx + half + 2):
        s.set_at((x, y + h), FLAG[4] if x < cx + half + 1 else FLAG[3])
        if solid(s, x, y + h + 1):
            s.set_at((x, y + h + 1), mix(s.get_at((x, y + h + 1))[:3], INK, .45))


def _gallery(s, front):
    """The reefing stage: a plank gallery ringing the tower with a railing, struts beneath
    and bronze bells at the struts. The back half goes down before the tower; the front half
    over it."""
    gy = GALLERY_Y
    ht = _mill_half(gy)
    hw = ht + 9
    ro, rt = MILL_K * hw, MILL_K * ht
    for x in range(MILL_W):
        dx = x + .5 - MILL_C
        if abs(dx) > hw:
            continue
        so = sqrt(max(0.0, 1 - (dx / hw) ** 2))
        yf, yb = gy + ro * so, gy - ro * so
        light = _lit(dx / hw)
        start = int(yb) if not front else int(_ring(gy, ht, dx)) + 1 if abs(dx) < ht else int(yf) + 1
        for y in range(start, int(yf) + 1):
            tone = 2.2 + light * 2.0 - (x % 3 == 2) * .7 + (y == int(yf)) * .6
            s.set_at((x, y), ramp(WOOD, tone))
        if not front:
            for dy, tone in ((7, 3.4), (4, 2.4)):
                put(s, x, int(yb) - dy, ramp(WOOD, tone + light))
            continue
        # The tower takes the deck's shade just under it; then the fascia and the rails.
        for dy, t in ((3, .4), (4, .22), (5, .1)):
            if abs(dx) < ht - 1 and solid(s, x, int(yf) + dy):
                s.set_at((x, int(yf) + dy), mix(s.get_at((x, int(yf) + dy))[:3], INK, t))
        s.set_at((x, int(yf) + 1), WOOD[1])
        s.set_at((x, int(yf) + 2), WOOD[0])
        s.set_at((x, int(yf) - 7), ramp(WOOD, 3.6 + light * 1.2))
        s.set_at((x, int(yf) - 4), ramp(WOOD, 2.4 + light))
    posts = range(-165, 166, 22) if not front else range(-77, 78, 22)
    for deg in posts:
        th = deg * pi / 180
        x = round(MILL_C + hw * sin(th) - .5)
        y = int(gy + ro * cos(th))
        if not front and abs(deg) < 90:
            continue
        for yy in range(y - 7, y + 1):
            put(s, x, yy, WOOD[3] if deg <= 0 else WOOD[2])
        if front and abs(deg) <= 55:
            line(s, x, y + 3, MILL_C + (x - MILL_C) * .82, y + 8, WOOD[1])
        if front and abs(deg) in (55, 33) and deg % 2:
            # A bronze bell under the gallery.
            put(s, x, y + 3, BRONZE[1])
            for i, row in enumerate(((-1, 1), (-1, 1), (-1, 1))):
                for bx in range(x + row[0], x + row[1] + 1):
                    put(s, bx, y + 4 + i, BRONZE[(4, 3, 2)[bx - x + 1] if i < 2 else 1])
            put(s, x, y + 7, BRONZE[1])


def _millstone(s, cx, cy):
    """A spare millstone leaning against the tower: dressed furrows and an iron eye."""
    for x in range(cx - 7, cx + 9):
        for y in range(cy - 8, cy + 9):
            if ((x + .5 - cx - 1.5) / 6) ** 2 + ((y + .5 - cy - .5) / 7) ** 2 <= 1:
                s.set_at((x, y), ramp(FLAG, 1.4 + (x > cx + 3) * -.4))
    for x in range(cx - 7, cx + 8):
        for y in range(cy - 8, cy + 9):
            dx, dy = x + .5 - cx, y + .5 - cy
            d = (dx / 6) ** 2 + (dy / 7) ** 2
            if d > 1:
                continue
            ang = atan2(dy, dx)
            furrow = 2 < sqrt(dx * dx + dy * dy) < 6 and abs((ang * 6 / pi + .5) % 2 - 1) < .18
            tone = 3.6 - (dx + dy) * .12 - (d > .75) * .8 - furrow * 1.3 + (noise(x, y, 196) - .5) * .5
            s.set_at((x, y), ramp(FLAG, tone))
    for x, y in ((cx - 1, cy - 1), (cx, cy - 1), (cx - 1, cy), (cx, cy)):
        s.set_at((x, y), IRON[0] if (x, y) != (cx - 1, cy - 1) else IRON[2])


def _cap(s):
    """The cap: a boarded curb with a bronze band, an ogee dome of dark fish-scale shingles,
    a dormer, a verdigris collar, and a bronze finial with a compass cross, an arrow and a
    cockerel weathervane."""
    hc = 25.5
    for x in range(MILL_W):
        dx = x + .5 - MILL_C
        if abs(dx) > hc:
            continue
        light = _lit(dx / hc)
        top, bottom = int(_ring(67, hc, dx)), int(_ring(75, hc, dx))
        joint = int(_arc(dx, hc) // 3) != int(_arc(dx + 1, hc) // 3)
        for y in range(top, bottom + 1):
            if y >= bottom - 1:
                rivet = int(_arc(dx, hc) // 5) != int(_arc(dx + 1, hc) // 5)
                tone = 1.4 + light * 3.2 + rivet * 1.0 - (y == bottom) * 1.0
                s.set_at((x, y), ramp(BRONZE, tone))
            else:
                tone = 1.2 + light * 2.6 - joint * 1.2 - (y == top) * 1.2
                s.set_at((x, y), ramp(WOOD, tone + (noise(x, y, 192) - .5) * .4))
    hd = 27.0
    for x in range(MILL_W):
        dx = x + .5 - MILL_C
        for y in range(36, int(_ring(67, hd, dx)) + 1 if abs(dx) <= hd else 0):
            t = (66 - y) / 28
            half = hd if t <= 0 else hd * max(0.0, 1 - t ** 2.2) ** .5
            if abs(dx) > half:
                continue
            light = _lit(dx / max(half, 1)) * .8 + max(0.0, t) * .45
            v = y - MILL_K * hd * sqrt(max(0.0, 1 - (dx / hd) ** 2)) * max(0.0, 1 - t)
            c, r = divmod(int(v - 36), 3)
            am = _arc(dx, max(half, 1)) + (c % 2) * 2
            lx = am % 4
            tone = .9 + light * 3.2 + (r == 0) * .5 - (r == 2 and (lx < 1 or lx > 3)) * 1.0
            if y >= int(_ring(67, hd, dx)):
                tone = 0
            elif y == int(_ring(67, hd, dx)) - 1:
                tone += .8
            s.set_at((x, y), ramp(CAP, tone + (noise(x, y, 193) - .5) * .4))
    # A dormer on the dome's lit side, with a bronze peak.
    dx0, dy0 = MILL_C - 13, 50
    for i in range(5):
        for x in range(dx0 - i, dx0 + 6 + i):
            s.set_at((x, dy0 - 4 + i), ramp(CAP, 4.0 - (x > dx0 + 2) * 1.4 - (i == 4) * 1.6))
    put(s, dx0 + 2, dy0 - 5, BRONZE[4])
    put(s, dx0 + 3, dy0 - 5, BRONZE[2])
    for y in range(dy0 + 1, dy0 + 7):
        for x in range(dx0, dx0 + 6):
            edge = x in (dx0, dx0 + 5) or y == dy0 + 1
            s.set_at((x, y), WOOD[3] if edge else GLASS[3] if (x, y) == (dx0 + 1, dy0 + 2) else
                     FLAME[1] if y > dy0 + 3 and x < dx0 + 3 else GLASS[1])
    # Verdigris collar, a bronze finial ball, and a bronze cockerel weathervane on its spike.
    for y, half in ((35, 2), (36, 3), (37, 3), (38, 4)):
        for x in range(MILL_C - half, MILL_C + half):
            s.set_at((x, y), VERDIGRIS[2 if x < MILL_C - 1 else 1 if x < MILL_C + 1 else 0])
    for y in range(22, 35):
        s.set_at((MILL_C - 1, y), BRONZE[3])
    for y in range(28, 31):
        for x in range(MILL_C - 2, MILL_C + 1):
            s.set_at((x, y), BRONZE[5] if (x, y) == (MILL_C - 2, 28) else BRONZE[4] if x < MILL_C else BRONZE[2])
    cock = ("...#........",
            "..###.......",
            ".####.....#.",
            "##.##....##.",
            "...##...###.",
            "...######.#.",
            "..#######...",
            "..#######...",
            "...#####....",
            "....###.....",
            ".....#.#....")
    for j, row in enumerate(cock):
        for i, ch in enumerate(row):
            if ch == "#":
                lit = j + i < 9
                s.set_at((MILL_C - 6 + i, 11 + j), BRONZE[5] if j < 2 else BRONZE[4] if lit else BRONZE[3] if i < 7 else BRONZE[2])
    s.set_at((MILL_C - 5, 12), CLOTH[1])
    s.set_at((MILL_C - 3, 10), CLOTH[1])
    s.set_at((MILL_C - 2, 11), CLOTH[1])
    s.set_at((MILL_C - 4, 13), INK)


def windmill():
    """The tower and everything fixed to it, 144 x 192. The door goes in WINDMILL_DOOR."""
    s = surface(MILL_W, MILL_H)
    _gallery(s, front=False)
    _rubble(s)
    # Shade where the cap overhangs the tower.
    for x in range(MILL_W):
        dx = x + .5 - MILL_C
        if abs(dx) < 23:
            y0 = int(_ring(75, 25.5, dx)) + 1
            for dy, t in ((0, .5), (1, .3), (2, .12)):
                if solid(s, x, y0 + dy):
                    s.set_at((x, y0 + dy), mix(s.get_at((x, y0 + dy))[:3], INK, t))
    shutter = (118, 58, 46)
    for cx, y, kw in ((MILL_C + 11, 88, {}), (MILL_C - 12, 93, {"shutter": shutter}),
                      (MILL_C - 10, 104, {"h": 10, "shutter": (78, 96, 72)}), (MILL_C + 13, 133, {}),
                      (MILL_C - 15, 139, {"shutter": shutter}), (MILL_C + 17, 159, {}), (MILL_C - 18, 158, {})):
        _mill_window(s, cx, y, **kw)
    _gallery(s, front=True)
    # The door, under a brick relieving arch with a bronze medallion in its tympanum.
    door_y = int(_ring(MILL_BASE - 4, _mill_half(MILL_BASE) + 1.5, 0)) - DOOR_H
    for x in range(MILL_C - 9, MILL_C + 9):
        for y in range(door_y - 12, door_y - 2):
            d = sqrt((x + .5 - MILL_C) ** 2 + (y + .5 - (door_y - 2)) ** 2)
            if d <= 8.4:
                if d >= 5.6:
                    joint = int((atan2(y + .5 - (door_y - 2), x + .5 - MILL_C) + pi) * 9 / pi) % 2
                    s.set_at((x, y), ramp(BRICK, 3.4 - joint * 1.0 - (x > MILL_C) * .6 - (d > 7.6) * .6))
                else:
                    s.set_at((x, y), ramp(FLAG, 1.6 - (x > MILL_C) * .4))
    for x in range(MILL_C - 3, MILL_C + 3):
        for y in range(door_y - 8, door_y - 2):
            if (x + .5 - MILL_C) ** 2 + (y + .5 - (door_y - 5)) ** 2 <= 6.5:
                tone = 4.4 - (x - MILL_C + 3) * .45 - (y - door_y + 8) * .3
                s.set_at((x, y), ramp(BRONZE, tone))
    for x, y in ((MILL_C - 1, door_y - 6), (MILL_C, door_y - 5), (MILL_C - 2, door_y - 5), (MILL_C - 1, door_y - 4)):
        s.set_at((x, y), BRONZE[1])
    door = _door(s, MILL_C - 5, door_y)
    for x in range(MILL_C - 7, MILL_C + 7):
        for y, tone in ((door_y + DOOR_H, 4.4), (door_y + DOOR_H + 1, 3.6), (door_y + DOOR_H + 2, 1.6)):
            s.set_at((x, y), ramp(FLAG, tone - (x > MILL_C + 3) * .6))
    # A bronze lantern on an iron bracket by the door.
    lx, ly = MILL_C + 9, door_y + 2
    for x in range(MILL_C + 6, lx + 1):
        s.set_at((x, ly), IRON[2])
    for y in range(ly + 1, ly + 7):
        for x in range(lx - 1, lx + 2):
            edge = y in (ly + 1, ly + 6) or x != lx
            s.set_at((x, y), BRONZE[4 if x < lx else 2] if edge else FLAME[2] if y < ly + 4 else FLAME[1])
    put(s, lx, ly + 7, BRONZE[1])
    # The tail pole and its brace, running down from the cap to a capstan wheel.
    wx, wy = MILL_C - 46, MILL_BASE
    for off, color in ((0, WOOD[2]), (1, WOOD[0])):
        line(s, MILL_C - 25 + off, 70, wx + off, wy, color)
        line(s, MILL_C - 27 + off, 68, MILL_C - 34 + off, 112, color if off else WOOD[3])
    for x in range(wx - 6, wx + 7):
        for y in range(wy - 6, wy + 7):
            d = sqrt((x + .5 - wx - .5) ** 2 + (y + .5 - wy - .5) ** 2)
            ang = atan2(y - wy, x - wx)
            if 4.2 <= d <= 5.6:
                s.set_at((x, y), WOOD[4] if x + y < wx + wy else WOOD[1])
            elif d < 4.2 and abs((ang * 6 / pi) % 2 - 1) > .7:
                s.set_at((x, y), WOOD[2])
    s.set_at((wx, wy), IRON[3])
    # The cap and the pennant staff at the gallery's east end.
    _cap(s)
    sx = round(MILL_C + _mill_half(GALLERY_Y) + 8)
    for y in range(GALLERY_Y - 17, GALLERY_Y + 1):
        s.set_at((sx, y), BRONZE[3] if y > GALLERY_Y - 17 else BRONZE[5])
    # Ivy up the tower's foot, spare millstones, flour sacks.
    for start in (MILL_C - 22, MILL_C - 16, MILL_C + 24):
        x = start
        for y in range(MILL_BASE, MILL_BASE - 28 + (start > MILL_C) * 14, -1):
            x += round((noise(start, y, 197) - .5) * 1.3)
            if solid(s, x, y):
                s.set_at((x, y), MOSS[1])
                if noise(start, y, 198) > .5 and solid(s, x + (1 if y % 2 else -1), y):
                    s.set_at((x + (1 if y % 2 else -1), y), LEAF[4] if y % 3 else MOSS[2])
    _millstone(s, MILL_C - 27, MILL_BASE - 1)
    _millstone(s, MILL_C + 24, MILL_BASE)
    s.blit(sacks(), (MILL_C + 31, MILL_BASE - 7))
    soft_outline(s)
    # Shade: the tower casts a strip east across the ground, as the houses do.
    for y in range(92, MILL_H):
        edge = MILL_C + _mill_half(min(y, MILL_BASE)) + 1
        for x in range(int(edge), int(edge) + min(12, (y - 92) // 2 + 2)):
            if 0 <= x < MILL_W and not s.get_at((x, y))[3]:
                s.set_at((x, y), SHADE)
    ground_shadow(s, MILL_C + 18, MILL_BASE + 7.5, 24, 2.5)
    out = surface(MILL_W + MILL_OX, MILL_H + MILL_OY)
    out.blit(s, (MILL_OX, MILL_OY))
    WINDMILL_DOOR[:] = [door[0] + MILL_OX, door[1] + MILL_OY, door[2], door[3]]
    return out


def windmill_sails(frame):
    """The sails, 144 x 144 on the tower's origin, turning a sixteenth of a turn per frame:
    four open lattice sails on their whips around a bronze hub, and the gallery pennant
    flapping."""
    s = surface(MILL_W + MILL_OX, 144)
    hx, hy = MILL_HUB[0] + MILL_OX, MILL_HUB[1] + MILL_OY
    turn = pi / 4 - frame * pi / (2 * SAIL_FRAMES)
    for k in range(4):
        a = turn + k * pi / 2
        ux, uy = cos(a), sin(a)
        px, py = -uy, ux

        def at(r, w):
            return hx + ux * r + px * w, hy + uy * r + py * w

        def bar(r0, w0, r1, w1, color):
            x0, y0 = at(r0, w0)
            x1, y1 = at(r1, w1)
            line(s, x0, y0, x1, y1, color)

        lit = ux * -.7 + uy * -.7 > -.2
        # Sail bars across the frame, the hemlath down its outer edge, a middle lath, and a
        # leading board on the far side of the whip.
        for i in range(int((SAIL_LEN - 14) / 5.2) + 1):
            r = 14 + i * 5.2
            bar(r, -2.5, r, 10, SAILWOOD[3] if lit else SAILWOOD[2])
        bar(14, 10, SAIL_LEN, 10, SAILWOOD[4] if lit else SAILWOOD[3])
        bar(14, 5.2, SAIL_LEN, 5.2, SAILWOOD[2])
        bar(14, -2.5, SAIL_LEN, -2.5, SAILWOOD[3])
        for w, color in ((-.5, SAILWOOD[2] if lit else SAILWOOD[1]), (.5, SAILWOOD[1])):
            bar(4, w, SAIL_LEN + 1, w, color)
    for y in range(hy - 4, hy + 5):
        for x in range(hx - 4, hx + 5):
            d = (x + .5 - hx - .5) ** 2 + (y + .5 - hy - .5) ** 2
            if d <= 16:
                tone = 4.2 - (x - hx + y - hy) * .32 - (d > 9) * .8
                s.set_at((x, y), ramp(BRONZE, tone))
    for x, y in ((hx - 2, hy - 2), (hx + 2, hy - 2), (hx - 2, hy + 2), (hx + 2, hy + 2)):
        s.set_at((x, y), BRONZE[1])
    s.set_at((hx - 1, hy - 1), BRONZE[5])
    s.set_at((hx, hy), BRONZE[2])
    # The pennant on the gallery staff, streaming east.
    sx = round(MILL_C + _mill_half(GALLERY_Y) + 9) + MILL_OX
    top = GALLERY_Y - 16 + MILL_OY
    for i in range(14):
        wave = round(1.3 * sin(i * .55 - frame * pi / 2))
        depth = 4 - i * 2 // 14
        for j in range(depth):
            if i > 10 and j == depth // 2:
                continue
            color = CLOTH[2] if j == 0 else CLOTH[1] if (i // 3 + frame) % 4 else CLOTH[0]
            put(s, sx + i, top + j + wave, color)
    soft_outline(s, lit_mix=.3)
    return s


# --- the sheep-birds in the hay pen -------------------------------------------------------------------
# The game's mount creature (assets/mounts/sheep-bird/source.png, the user's design), brought
# down to a 32 x 32 cell for the town. The illustration is far bigger than a cell, so it is
# shrunk by averaging (not by picking single pixels), snapped to a small palette, cleaned of
# stray pixels, then given the town's soft outline and a ground shadow.
SHEEPBIRD = ASSETS / "mounts" / "sheep-bird" / "source.png"
BIRD_DIRS = ("down", "left", "right", "up")
BIRD_H = 26          # body height in pixels, horns to toes
BIRD_INK = (46, 26, 18)
BIRD_PEN = {}


def _bird_frames():
    """{(direction, frame): 32 x 32 sprite} for the three idle frames of each facing."""
    if BIRD_PEN:
        return BIRD_PEN
    src = pygame.image.load(str(SHEEPBIRD))
    W, H = src.get_size()
    raw = pygame.image.tobytes(src, "RGBA")

    def alpha(x, y):
        return raw[(y * W + x) * 4 + 3]

    boxes = {}
    for row, direction in enumerate(BIRD_DIRS):
        for col in range(3):
            x0, y0 = round(col * W / 3) + 8, round(row * H / 4) + 8
            x1, y1 = round((col + 1) * W / 3) - 8, round((row + 1) * H / 4) - 8
            xs = [x for x in range(x0, x1) if any(alpha(x, y) >= 128 for y in range(y0, y1, 2))]
            ys = [y for y in range(y0, y1) if any(alpha(x, y) >= 128 for x in range(xs[0], xs[-1] + 1, 2))]
            boxes[(direction, col)] = (xs[0], ys[0], xs[-1] + 1, ys[-1] + 1)
    scale = BIRD_H / max(b[3] - b[1] for b in boxes.values())
    shrunk = {}
    for key, (bx0, by0, bx1, by1) in boxes.items():
        tw, th = round((bx1 - bx0) * scale), round((by1 - by0) * scale)
        cell = {}
        for ty in range(th):
            for tx in range(tw):
                sx0, sx1 = bx0 + int(tx / scale), bx0 + int((tx + 1) / scale)
                sy0, sy1 = by0 + int(ty / scale), by0 + int((ty + 1) / scale)
                r = g = b = a = n = 0
                accents = {"dark": [0, 0, 0, 0], "red": [0, 0, 0, 0], "gold": [0, 0, 0, 0]}
                for sy in range(sy0, sy1):
                    base = (sy * W + sx0) * 4
                    for i in range(base, base + (sx1 - sx0) * 4, 4):
                        pa = raw[i + 3]
                        n += 1
                        if pa < 128:
                            continue
                        pr, pg, pb = raw[i], raw[i + 1], raw[i + 2]
                        r += pr * pa
                        g += pg * pa
                        b += pb * pa
                        a += pa
                        kind = ("dark" if pr * .3 + pg * .59 + pb * .11 < 62 else
                                "red" if pr - pg > 85 and pr > 140 else
                                "gold" if pr > 200 and 120 < pg < 200 and pb < 90 else None)
                        if kind:
                            acc = accents[kind]
                            acc[0] += pr
                            acc[1] += pg
                            acc[2] += pb
                            acc[3] += 1
                if not n or a / n < 118:
                    continue
                # Small sharp details (eyes, the cloth, the beak) keep their own colour rather
                # than melting into the wool around them.
                solid_px = a / 255
                for kind, need in (("dark", .36), ("red", .3), ("gold", .34)):
                    acc = accents[kind]
                    if acc[3] >= need * solid_px:
                        cell[(tx, ty)] = (acc[0] / acc[3], acc[1] / acc[3], acc[2] / acc[3])
                        break
                else:
                    cell[(tx, ty)] = (r / a, g / a, b / a)
        shrunk[key] = (tw, th, cell)
    # One small palette for every frame, so all the facings share their colours: the wool,
    # horn and leather tones by k-means, plus the accents kept as they are.
    colours = [c for _, _, cell in shrunk.values() for c in cell.values()]
    colours.sort(key=lambda c: c[0] * .3 + c[1] * .59 + c[2] * .11)
    centres = [colours[int((i + .5) * len(colours) / 12)] for i in range(12)]
    for _ in range(14):
        groups = [[] for _ in centres]
        for c in colours:
            groups[min(range(len(centres)), key=lambda k: sum((c[j] - centres[k][j]) ** 2 for j in range(3)))].append(c)
        centres = [tuple(sum(c[j] for c in g) / len(g) for j in range(3)) if g else centres[k] for k, g in enumerate(groups)]
    palette = [tuple(round(v) for v in c) for c in centres]
    palette += [(52, 30, 24), (176, 52, 36), (214, 86, 46), (236, 176, 64), (198, 128, 44)]

    def nearest(c):
        return min(palette, key=lambda p: sum((c[j] - p[j]) ** 2 for j in range(3)))

    for (direction, frame), (tw, th, cell) in shrunk.items():
        snapped = {p: nearest(c) for p, c in cell.items()}
        # Stray pixels take the colour their neighbours agree on.
        for (x, y), c in list(snapped.items()):
            around = [snapped.get(n) for n in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1))]
            if None not in around and c not in around:
                best = max(set(around), key=around.count)
                if around.count(best) >= 3:
                    snapped[(x, y)] = best
        s = surface(32, 32)
        ox, oy = (32 - tw) // 2, 29 - th
        for (x, y), c in snapped.items():
            s.set_at((ox + x, oy + y), c)
        # The illustration's own line survives the shrink in most places; close it only
        # where pale wool or gold meets the ground, so the outline never doubles up.
        rims = {}
        for (x, y), c in snapped.items():
            if c[0] * .3 + c[1] * .59 + c[2] * .11 < 90:
                continue
            for nx, ny, shadow in ((x + 1, y, True), (x, y + 1, True), (x - 1, y, False), (x, y - 1, False)):
                if (nx, ny) not in snapped:
                    spot = (ox + nx, oy + ny)
                    rims[spot] = BIRD_INK if shadow or spot in rims else mix(c, BIRD_INK, .55)
        for spot, rim in rims.items():
            put(s, *spot, rim)
        ground_shadow(s, 18, 30, tw / 2 - 1, 1.6)
        BIRD_PEN[(direction, frame)] = s
    return BIRD_PEN


# --- pieces and packing -----------------------------------------------------------------------------
BUILDINGS = {
    "inn": dict(width=7, roof=ROOF_RED, gables=((0, 2), (5, 2)), doors=(3,), windows=(1, 5), upper=(1, 2, 4, 5),
                boxes=(1, 5), chimney=3, sign=(2, "bed"), ground="stone", seed=1),
    "house-red": dict(width=4, roof=ROOF_RED, gables=((0, 2),), doors=(2,), windows=(0,), upper=(0, 1, 3),
                      boxes=(0, 3), chimney=3, seed=2),
    "house-slate": dict(width=5, roof=ROOF_SLATE, gables=((1, 3),), doors=(0,), windows=(2, 4), upper=(1, 3),
                        boxes=(1,), shutter=(118, 58, 46), chimney=4, ground="stone", seed=3),
    "cottage": dict(width=3, roof=ROOF_SLATE, gables=((0, 3),), doors=(1,), windows=(0, 2), upper=(0, 2),
                    boxes=(0, 2), shutter=(118, 58, 46), seed=4),
    "shop-arms": dict(width=4, roof=ROOF_RED, gables=((2, 2),), doors=(1,), windows=(2, 3), upper=(1, 3),
                      sign=(0, "sword"), chimney=0, ground="stone", seed=5),
    "shop-goods": dict(width=4, roof=ROOF_SLATE, gables=((0, 2),), doors=(2,), windows=(0, 1), upper=(0, 2),
                       boxes=(0,), sign=(3, "flask"), shutter=(118, 58, 46), seed=6),
    "bakery": dict(width=4, roof=ROOF_RED, doors=(1,), windows=(0, 3), upper=(0, 2), boxes=(2,), chimney=3,
                   sign=(2, "loaf"), seed=7),
}
PINE_PARTS = ("top", "mid-0", "mid-1", "mid-2", "base")
TREE_PARTS = ("top", "mid", "bottom", "base")


def pieces():
    out, doors = {}, {}
    for kind in ("top", "mid", "base", "solo"):
        for end in ("l", "m", "r"):
            for variant in range(3):
                out[f"wall-{kind}-{end}-{variant}"] = wall_tile(kind, end, variant)
        for end in ("l", "m", "r", "solo"):
            out[f"stairs-{kind}-{end}"] = stairs_tile(kind, end)
    out["edge-l"], out["edge-r"] = side_edge("l"), side_edge("r")
    out["wall-shadow"] = wall_shadow()
    for kind in ("strip", "strip-top", "strip-end", "full", "stair-foot"):
        out[f"shade-{kind}"] = shade_tile(kind)
    for end in ("l", "m", "r", "solo"):
        out[f"fence-{end}"] = fence_h(end)
        out[f"lowwall-{end}"] = low_wall(end)
    out["fence-v"], out["fence-gate"] = fence_v(), fence_gate()
    for name, spec in BUILDINGS.items():
        stooped = name in windehus.STOOPS
        if stooped:
            assert spec["doors"] == (windehus.STOOPS[name],), name
        out[name], doors[name] = building(stoop=stooped, **spec)
    out["stoop"] = stoop()
    if not FLAG_PLAN:
        flag_texture()
    for i, (name, x, y, tw, th, count) in enumerate(windehus.SQUARE_GAPS):
        out[name] = square_gap(x % 4, y % 4, tw, th, count, 300 + i)
    for part in PINE_PARTS:
        out[f"pine-{part}"] = pine_segment(part)
    for part in TREE_PARTS:
        out[f"tree-{part}"] = tree_segment(part)
    out.update({"barrel": barrel(), "crate": crate(), "sacks": sacks(), "well": well(), "lamp": lamp_post(),
                "bench": bench(), "bush": bush(), "stump": stump(),
                "haystack": haystack(), "stall-red": market_stall(CLOTH[1]),
                "stall-blue": market_stall((70, 96, 150)), "signpost": signpost(),
                "town-stone": town_stone("windehus"), "windmill": windmill()})
    for frame in range(SAIL_FRAMES):
        out[f"windmill-sails-{frame}"] = windmill_sails(frame)
    for (direction, frame), sprite in _bird_frames().items():
        out[f"sheepbird-{direction}-{frame}"] = sprite
    doors["windmill"] = [list(WINDMILL_DOOR)]
    for i in range(3):
        out[f"planter-{i}"] = planter(i)
        out[f"flowers-{i}"] = flower_patch(i)
    return out, doors


def pack(images, width=512):
    order = sorted(images, key=lambda n: (-images[n].get_height(), n))
    x = y = shelf = 0
    spots = {}
    for name in order:
        w, h = images[name].get_size()
        if x + w > width:
            x, y, shelf = 0, y + shelf + 1, 0
        spots[name] = (x, y, w, h)
        x += w + 1
        shelf = max(shelf, h)
    atlas = surface(width, y + shelf)
    for name, (x, y, w, h) in spots.items():
        atlas.blit(images[name], (x, y))
    return atlas, spots


def town_ground(atlas, spots):
    """Windehus's flat layer: grass, paving, lifted slabs, walls, stairs and shade."""
    sheets = {name: pygame.image.load(str(OUT / f"ground-{name}.png")) for name in windehus.PAVINGS}
    grass = [pygame.image.load(str(ASSETS / "grassland" / f"meadow{i}.png")) for i in range(6)]
    sizes = {name: (w, h) for name, (x, y, w, h) in spots.items()}
    tile = windehus.TILE
    ground = pygame.Surface((windehus.WIDTH * tile, windehus.HEIGHT * tile))
    for op in windehus.ground_ops(sizes):
        if op[0] == "grass":
            ground.blit(grass[op[1]], op[2:4])
        elif op[0] == "paving":
            _, paving, mask, sub, px, py = op
            ground.blit(sheets[paving], (px, py), (mask * tile, sub * tile, tile, tile))
        else:
            _, name, px, py = op
            ground.blit(atlas, (px, py), spots[name])
    return ground


def main():
    pygame.display.init()
    pygame.display.set_mode((1, 1), pygame.HIDDEN)
    OUT.mkdir(parents=True, exist_ok=True)
    for name, texture, ragged, moss in (("cobble", cobble_texture(), .2, False), ("flag", flag_texture(), .15, True),
                                        ("brick", brick_texture(), .15, False), ("dirt", dirt_texture(), .35, False)):
        pygame.image.save(ground_sheet(texture, ragged, moss=moss), str(OUT / f"ground-{name}.png"))
    images, doors = pieces()
    atlas, spots = pack(images)
    pygame.image.save(atlas, str(OUT / "tileset.png"))
    (OUT / "tileset.json").write_text(json.dumps(spots, indent=1, sort_keys=True), encoding="utf-8")
    pygame.image.save(town_ground(atlas, spots), str(OUT / "windehus-ground.png"))
    info = {name: {"tiles": [spots[name][2] // 16, spots[name][3] // 16], "doors": doors[name],
                   "stoop": name in windehus.STOOPS} for name in doors}
    (OUT / "buildings.json").write_text(json.dumps(info, indent=1, sort_keys=True), encoding="utf-8")


if __name__ == "__main__":
    main()
