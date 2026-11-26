"""Draw the Old Workings sidequest art: field props, Hesk, the Old Knocker and the Pit Lantern.

Run with the project venv (pygame). Writes:
    assets/mine-polish/workings/*.png      field props on their native tile grid
    assets/hesk-overworld.png              Larvel's sheet, recoloured for the tally-keeper
    assets/battle/old-knocker.png          the mini-boss, pixelated from old-knocker-source.png
    assets/items/accessories/pit_lantern.png
"""
from math import cos, hypot, pi, sin
from pathlib import Path
import random
import re

import pygame

from lower_workings import RUBBING_FJALORA


ASSETS = Path(__file__).resolve().parent / "assets"
OUT = ASSETS / "mine-polish" / "workings"
CLEAR = (0, 0, 0, 0)
INK = (13, 10, 22)

# Cave stone, sampled from crystal_cavern floor and wall tiles.
STONE = ((25, 20, 42), (40, 32, 66), (53, 44, 82), (66, 52, 101), (82, 67, 117), (104, 88, 138))
# Timber, the same ramp the side drift uses for the cart and tools.
WOOD = ((44, 29, 31), (63, 43, 45), (84, 56, 53), (110, 74, 65), (147, 101, 82), (165, 118, 95))
# Selvar slate, from selvar-inscription.png.
SLATE = ((44, 42, 58), (63, 61, 78), (82, 80, 97), (101, 99, 115), (122, 120, 135), (146, 144, 157))
PAPER = ((150, 132, 104), (196, 178, 140), (226, 212, 176), (243, 233, 204))
CHARCOAL = (34, 31, 38)
BLUE = ((40, 74, 132), (70, 128, 196), (132, 196, 240), (214, 244, 255))
AMBER = ((122, 62, 30), (190, 104, 40), (238, 168, 72), (255, 226, 150))


def mix(a, b, t):
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def surface(w, h):
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    s.fill(CLEAR)
    return s


def outline(sprite, color=INK):
    """A one-pixel ink contour around every opaque pixel, like the battle sprites."""
    w, h = sprite.get_size()
    solid = {(x, y) for y in range(h) for x in range(w) if sprite.get_at((x, y))[3]}
    for x, y in solid:
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in solid:
                sprite.set_at((nx, ny), color)


def ramp_at(ramp, value):
    return ramp[max(0, min(len(ramp) - 1, int(value)))]


# --- field props -------------------------------------------------------------------
def stair_up():
    """Rock-cut steps climbing north into the drift, timbered, with Larvel's signal rope."""
    s = surface(32, 32)
    pygame.draw.rect(s, STONE[2], (2, 0, 28, 32), border_radius=3)
    # The dark mouth above, where the stair turns out of sight.
    pygame.draw.rect(s, (12, 9, 22), (7, 0, 18, 7))
    pygame.draw.rect(s, (20, 16, 34), (7, 7, 18, 2))
    # Treads get lighter as they come toward the viewer.
    for i, y in enumerate(range(9, 31, 4)):
        tread = mix(STONE[1], STONE[4], i / 5)
        pygame.draw.rect(s, tread, (7, y, 18, 3))
        pygame.draw.line(s, mix(tread, STONE[5], .45), (7, y), (24, y))
        pygame.draw.line(s, mix(tread, INK, .55), (7, y + 3), (24, y + 3))
        for x in range(8, 24, 5):
            s.set_at((x + i % 3, y + 1), mix(tread, STONE[0], .35))
    # Timber posts and a cap beam.
    for x in (3, 25):
        pygame.draw.rect(s, WOOD[2], (x, 2, 4, 30))
        pygame.draw.line(s, WOOD[4], (x, 2), (x, 31))
        pygame.draw.line(s, WOOD[0], (x + 3, 2), (x + 3, 31))
        for y in (8, 17, 26):
            s.set_at((x + 1, y), WOOD[1])
            s.set_at((x + 2, y + 1), WOOD[3])
    pygame.draw.rect(s, WOOD[3], (2, 0, 28, 3))
    pygame.draw.line(s, WOOD[5], (2, 0), (29, 0))
    pygame.draw.line(s, WOOD[1], (2, 2), (29, 2))
    # Signal rope down the right side of the steps.
    for y in range(3, 31):
        x = 22 + round(sin(y / 3.2) * .7)
        s.set_at((x, y), (176, 146, 96) if y % 3 else (120, 96, 62))
    s.set_at((22, 3), (210, 180, 120))
    return s


# Warm timber, after the plank references: dark seams, mid boards, honey highlights.
TIMBER = ((34, 21, 20), (56, 36, 29), (80, 52, 37), (106, 70, 46), (136, 93, 60), (168, 122, 80), (196, 152, 102))
IRON = ((30, 28, 36), (58, 56, 68), (98, 96, 110), (150, 148, 160))
INK_SOFT = (20, 15, 26)
HESK_INK = (74, 52, 50)
MOSS = ((44, 62, 58), (66, 92, 78), (96, 124, 96))


def noise(x, y, seed=0):
    n = (x * 374761393 + y * 668265263 + seed * 982451653) & 0xFFFFFFFF
    n = (n ^ (n >> 13)) * 1274126177 & 0xFFFFFFFF
    return ((n ^ (n >> 16)) & 0xFFFF) / 0xFFFF


def ramp(r, v):
    return r[max(0, min(len(r) - 1, int(v)))]


def soft_outline(s, color=INK_SOFT):
    w, h = s.get_size()
    solid = {(x, y) for y in range(h) for x in range(w) if s.get_at((x, y))[3] > 200}
    for x, y in solid:
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in solid and not s.get_at((nx, ny))[3]:
                s.set_at((nx, ny), color)


# --- Selvar script, the stroke data from the Fjalora codex ------------------------------------
SIGNS = {
    "a": ["M30 11 L17 22 30 32 43 22Z"], "e": ["M30 9 C12 10 12 26 30 29"],
    "i": ["M30 15 Q19 16 17 25", "M12 13h.01"], "o": ["M30 10 C52 10 53 32 30 31"],
    "u": ["M30 10 C12 11 11 30 25 29 Q29 28 30 25", "M11 32h.01"],
    "p": ["M30 10 H47 L40 19 H30"], "b": ["M30 10 H47 L40 19 H30 M30 23 H42 L34 31"],
    "t": ["M30 10 L14 17 30 18"], "d": ["M30 10 L14 17 30 18 M30 21 L14 28 30 29"],
    "k": ["M30 22 L46 10 M30 22 L47 27"], "g": ["M30 22 L46 10 M30 22 L47 27 M38 18 L47 18"],
    "f": ["M30 12 L13 12 18 23 30 25"], "v": ["M30 12 L13 12 18 23 30 25 M18 23 L10 30"],
    "s": ["M30 10 L18 18 37 23 30 32"], "z": ["M30 10 L18 18 37 23 30 32", "M15 27h.01"],
    "h": ["M30 12 H44 V24 M30 25 H18 V32"], "m": ["M30 12 C46 5 50 21 38 22 C52 25 43 34 30 31"],
    "n": ["M30 12 C46 5 50 21 38 24 L30 24"], "l": ["M30 13 Q43 20 49 12 Q46 27 30 27"],
    "r": ["M30 9 Q14 14 21 24 Q24 27 30 26 M21 24 L14 32"], "j": ["M30 13 Q17 13 15 7 Q13 22 30 26"],
    "w": ["M30 12 L44 16 32 23 48 30 30 33"], "sh": ["M30 10 L18 18 37 23 30 32 M37 23 L47 17"],
    "th": ["M30 10 L14 17 30 18 M24 18 L16 32"], "ng": ["M30 12 C46 5 50 21 38 24 L30 24 M38 24 L47 31"],
}
OPEN_WORD = "M18 12 Q22 3 34 5 Q39 7 30 13 L30 17"
CLOSE_WORD = "M30 0 Q28 11 15 15 Q36 12 49 17"


def _polylines(d, dx=0, dy=0):
    """Flatten the codex's SVG paths (M L H V Q C Z, and h for dots) into point lists."""
    tokens = re.findall(r"[MLHVQCZh]|-?\d*\.?\d+", d)
    lines, cur, start, cmd, i = [], None, None, None, 0
    num = lambda: float(tokens[i])
    while i < len(tokens):
        t = tokens[i]
        if t.isalpha():
            cmd = t
            i += 1
            if cmd == "Z":
                if cur and start:
                    cur.append(start)
                continue
        if cmd == "M":
            start = (num() + dx, float(tokens[i + 1]) + dy)
            cur = [start]
            lines.append(cur)
            i += 2
            cmd = "L"
        elif cmd == "L":
            cur.append((num() + dx, float(tokens[i + 1]) + dy))
            i += 2
        elif cmd == "H":
            cur.append((num() + dx, cur[-1][1]))
            i += 1
        elif cmd == "V":
            cur.append((cur[-1][0], num() + dy))
            i += 1
        elif cmd == "h":
            cur.append((cur[-1][0] + num(), cur[-1][1]))
            i += 1
        elif cmd in "QC":
            n = 2 if cmd == "Q" else 3
            pts = [cur[-1]] + [(float(tokens[i + 2 * k]) + dx, float(tokens[i + 2 * k + 1]) + dy) for k in range(n)]
            i += 2 * n
            for step in range(1, 13):
                t_ = step / 12
                p = pts[:]
                while len(p) > 1:
                    p = [(a[0] + (b[0] - a[0]) * t_, a[1] + (b[1] - a[1]) * t_) for a, b in zip(p, p[1:])]
                cur.append(p[0])
    return lines


def word_strokes(word):
    """The codex's word layout: hook, spine, signs every 31 units, tail. Returns (lines, width)."""
    letters, k = [], 0
    while k < len(word):
        if word[k:k + 2] in ("sh", "th", "ng"):
            letters.append(word[k:k + 2])
            k += 2
        else:
            letters.append(word[k])
            k += 1
    height = len(letters) * 31
    out = [(OPEN_WORD, 0, 2.8), (f"M30 13V{height + 12}", 0, 3.6)]
    for n, key in enumerate(letters):
        for j, d in enumerate(SIGNS[key]):
            out.append((d, 12 + n * 31, 4.8 if j else 3))
    out.append((CLOSE_WORD, height + 11, 2.8))
    return [(line, w) for d, dy, w in out for line in _polylines(d, 0, dy)], height + 30


def carve_mask(word, scale, origin, size):
    """Supersample the strokes and keep the pixels they cover well: a set of carved pixels."""
    F = 6
    W, H = size
    big = pygame.Surface((W * F, H * F))
    big.fill((0, 0, 0))
    ox, oy = origin
    lines, _ = word_strokes(word)
    for pts, width in lines:
        p = [((x * scale + ox) * F, (y * scale + oy) * F) for x, y in pts]
        thick = max(2, round(width * scale * F * 1.05))
        if len(p) == 1 or all(abs(a[0] - p[0][0]) < 1 and abs(a[1] - p[0][1]) < 1 for a in p):
            pygame.draw.circle(big, (255, 255, 255), p[0], thick * .6)
            continue
        pygame.draw.lines(big, (255, 255, 255), False, p, thick)
        for q in p:
            pygame.draw.circle(big, (255, 255, 255), q, thick / 2)
    carved = set()
    for y in range(H):
        for x in range(W):
            hit = sum(big.get_at((x * F + i, y * F + j))[0] > 0 for i in range(F) for j in range(F))
            if hit / (F * F) >= .3:
                carved.add((x, y))
    return carved


# --- the ledger post ---------------------------------------------------------------------------
def ledger_post(with_page):
    """A squared pit prop under a cap beam, footed on a sill, with Hesk's page nailed on."""
    s = surface(16, 32)
    # Floor shadow.
    for x in range(2, 15):
        s.set_at((x, 31), (14, 10, 22, 120))
    # Sill block the prop stands on.
    for y in range(28, 31):
        for x in range(3, 13):
            v = 3.2 - (y - 28) * .7 + (noise(x, y, 4) - .5) * .9
            s.set_at((x, y), ramp(TIMBER, v))
    for x in range(3, 13):
        s.set_at((x, 28), TIMBER[5] if noise(x, 1, 9) > .25 else TIMBER[4])
    for y in range(28, 31):
        s.set_at((3, y), TIMBER[2])  # end grain
        s.set_at((12, y), TIMBER[1])
    # Post: lit left arris, wavy vertical grain, shaded right face.
    for y in range(7, 28):
        for x in range(5, 11):
            base = {5: 5.1, 6: 4.4, 7: 3.8, 8: 3.5, 9: 2.9, 10: 1.6}[x]
            grain = sin(y * .55 + x * 2.1 + sin(y * .21) * 2) * .55
            v = base + grain * (x not in (5, 10)) + (noise(x, y, 2) - .5) * .5
            s.set_at((x, y), ramp(TIMBER, v))
    # A knot with its grain bending around it, and a long check (split) in the wood.
    for (x, y), c in (((7, 24), TIMBER[1]), ((8, 24), TIMBER[0]), ((7, 23), TIMBER[2]), ((8, 25), TIMBER[2]),
                      ((9, 23), TIMBER[3]), ((6, 25), TIMBER[3])):
        s.set_at((x, y), c)
    for y in range(12, 20):
        s.set_at((9 - (y > 16), y), TIMBER[1])
    # Cap beam: a lit top edge, horizontal grain, darker end grain, shadow onto the post.
    for y in range(2, 7):
        for x in range(0, 16):
            base = {2: 6, 3: 4.6, 4: 4.0, 5: 3.4, 6: 2.4}[y]
            v = base + sin(x * .7 + y * 1.9) * .45 * (y > 2) + (noise(x, y, 5) - .5) * .5
            s.set_at((x, y), ramp(TIMBER, v))
    for y in range(3, 7):
        s.set_at((0, y), TIMBER[3] if y % 2 else TIMBER[2])
        s.set_at((15, y), TIMBER[1] if y % 2 else TIMBER[2])
    s.set_at((0, 2), TIMBER[4])
    s.set_at((15, 2), TIMBER[4])
    for x in range(5, 11):
        s.set_at((x, 7), TIMBER[1])
    # Two iron spikes through the cap into the post.
    for x in (6, 9):
        s.set_at((x, 4), IRON[3])
        s.set_at((x, 5), IRON[1])
    if with_page:
        # Paper: lit left edge, shaded right edge, a curled lower corner showing the back.
        page = pygame.Rect(3, 9, 10, 13)
        for y in range(page.top, page.bottom):
            for x in range(page.left, page.right):
                if x >= 11 and y >= 19 and (x - 11) + (y - 19) >= 1:
                    continue
                v = 2.2 + (x == 3) * .9 - (x == 12) * .9 - (y == 21) * .6 + (noise(x, y, 7) - .5) * .5
                s.set_at((x, y), ramp(PAPER, v))
        s.set_at((11, 20), PAPER[0])
        s.set_at((12, 19), PAPER[0])
        s.set_at((11, 19), PAPER[1])
        # Its shadow on the timber.
        for y in range(10, 22):
            if not (y >= 19):
                s.set_at((13, y), TIMBER[0])
        for x in range(4, 11):
            s.set_at((x, 22), mix(s.get_at((x, 22))[:3], TIMBER[0], .6))
        # Hesk's hand: a heading, three ruled lines, and a tally.
        for x in range(5, 9):
            s.set_at((x, 12), HESK_INK)
        for y, run in ((14, (4, 11)), (16, (4, 10)), (18, (4, 9))):
            for x in range(*run):
                if noise(x, y, 11) > .22:
                    s.set_at((x, y), mix(HESK_INK, PAPER[1], .35))
        for x in (5, 6, 7):
            s.set_at((x, 20), HESK_INK)
        s.set_at((8, 19), HESK_INK)
        s.set_at((9, 20), HESK_INK)
        # The nail, with a dimple in the paper.
        s.set_at((8, 9), IRON[3])
        s.set_at((8, 10), IRON[1])
        s.set_at((7, 10), PAPER[1])
    else:
        # A torn scrap left under the nail.
        for (x, y) in ((7, 9), (8, 9), (9, 9), (7, 10), (8, 10), (9, 10), (8, 11), (7, 11)):
            s.set_at((x, y), PAPER[2] if y < 11 else PAPER[1])
        s.set_at((9, 11), PAPER[0])
        s.set_at((8, 9), IRON[3])
        s.set_at((8, 10), IRON[1])
    soft_outline(s)
    return s


# --- the Selvar marker stone --------------------------------------------------------------------
STELE_W, STELE_H = 24, 40
FACE = pygame.Rect(4, 4, 15, 30)   # the dressed front face
GLYPH_SCALE = .18


def _in_slab(x, y):
    left, right, top = 3, 20, 2
    if not (left <= x <= right and top <= y <= 34):
        return False
    r = 6   # rounded shoulders
    for cx in (left + r, right - r):
        if (x < left + r and cx == left + r) or (x > right - r and cx == right - r):
            if y < top + r and (x - cx) ** 2 + (y - (top + r)) ** 2 > (r + .3) ** 2:
                return False
    return True


def stele(word, rubbed):
    """A slate marker: rounded shoulders, a right-hand side face, a fieldstone plinth, cracks,
    lichen, and one Fjalora word cut down its face in Selvar."""
    s = surface(STELE_W, STELE_H)
    # Plinth: three rough blocks, lit tops, with rubble at the feet.
    for y in range(33, 39):
        for x in range(1, 23):
            block = (x + (y > 35) * 4) // 7
            edge = (x + (y > 35) * 4) % 7 == 0 or y == 36
            v = 4.2 - (y - 33) * .45 - edge * 1.6 + (noise(x, y, block) - .5) * .9
            s.set_at((x, y), ramp(STONE, v))
    for x in range(2, 22):
        s.set_at((x, 33), STONE[5] if noise(x, 3, 1) > .3 else STONE[4])
    for x, y in ((0, 38), (23, 37), (22, 38), (1, 37)):
        s.set_at((x, y), STONE[3])
    for x in range(1, 23):
        s.set_at((x, 39), (14, 10, 22, 140))
    # The slab, lit from the upper left, with a darker side face on the right.
    for y in range(2, 35):
        for x in range(3, 22):
            if x >= 20 and y >= 5 and x <= 21 and y <= 34:
                v = 1.2 - (x == 21) * .5 + (noise(x, y, 3) - .5) * .6
                s.set_at((x, y), ramp(SLATE, v))
                continue
            if not _in_slab(x, y):
                continue
            light = (20 - x) / 17 * .55 + (34 - y) / 32 * .45
            v = 1.4 + light * 3 + (noise(x, y) - .5) * .9 + (noise(x // 3, y // 3, 6) - .5) * .6
            s.set_at((x, y), ramp(SLATE, v))
    # Rounded top of the side face.
    for x, y in ((20, 4), (21, 5), (20, 3)):
        s.set_at((x, y), SLATE[1])
    # Bevel: a bright rim along the shoulders and left edge.
    for y in range(2, 34):
        for x in range(3, 20):
            if _in_slab(x, y) and (not _in_slab(x - 1, y) or not _in_slab(x, y - 1)):
                s.set_at((x, y), SLATE[5] if y < 20 else SLATE[4])
    # A carved border inside the face, two pixels in from the edge.
    def inset(x, y, d):
        return (_in_slab(x - d, y) and _in_slab(x + d, y) and _in_slab(x, y - d)
                and y + d <= 33 and x + d <= 19)
    border = {(x, y) for y in range(2, 34) for x in range(3, 20) if inset(x, y, 2) and not inset(x, y, 3)}
    # The word, centred in the frame.
    _, units = word_strokes(word)
    gh = units * GLYPH_SCALE
    gx = 11.6 - 30 * GLYPH_SCALE
    gy = 7 + (24 - gh) / 2 - 2 * GLYPH_SCALE
    carved = carve_mask(word, GLYPH_SCALE, (gx, gy), (STELE_W, STELE_H))
    carved = {p for p in carved if _in_slab(*p) and p[0] < 20}
    # Weathering: a crack from the right shoulder, a chipped corner, lichen low down.
    crack = [(19, 7), (18, 8), (18, 9), (19, 10), (19, 11), (18, 12)]
    for x, y in crack:
        if (x, y) not in carved:
            s.set_at((x, y), SLATE[0])
            if (x - 1, y) not in carved and (x - 1, y) not in border and _in_slab(x - 1, y):
                s.set_at((x - 1, y), SLATE[4])
    for x in range(4, 19):
        for y in range(27, 33):
            if noise(x, y, 21) > .8 - (y - 27) * .05 and _in_slab(x, y) and (x, y) not in carved:
                s.set_at((x, y), ramp(MOSS, noise(x, y, 22) * 2.9))
    # Cut the border and the glyphs: dark groove, light catching its lower-right lip.
    groove_dark, groove_lip = (30, 27, 42), SLATE[5]
    if rubbed:
        # Charcoal haze where the paper lay, and the cut letters answering with light.
        for y in range(6, 31):
            for x in range(5, 19):
                if _in_slab(x, y) and noise(x, y, 31) > .35:
                    s.set_at((x, y), mix(s.get_at((x, y))[:3], CHARCOAL, .3))
    for cut, dark in ((border, SLATE[0]), (carved, groove_dark)):
        for x, y in cut:
            s.set_at((x, y), dark)
        for x, y in cut:
            for nx, ny in ((x, y + 1),):
                if (nx, ny) not in cut and _in_slab(nx, ny) and nx < 20 and (nx, ny) not in carved and (nx, ny) not in border:
                    s.set_at((nx, ny), mix(s.get_at((nx, ny))[:3], groove_lip, .55))
    if rubbed:
        for x, y in carved:
            s.set_at((x, y), (150, 204, 240))
        for x, y in carved:
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if (nx, ny) not in carved and _in_slab(nx, ny) and nx < 20 and (nx, ny) not in border:
                    s.set_at((nx, ny), mix(s.get_at((nx, ny))[:3], (70, 128, 196), .5))
        # A spent stub of charcoal on the plinth.
        for x, y, c in ((15, 32, CHARCOAL), (16, 32, CHARCOAL), (17, 32, (58, 52, 60))):
            s.set_at((x, y), c)
    soft_outline(s)
    return s


def selvar_glyph(s, origin, variant, color, light=None):
    x, y = origin
    strokes = (
        (((0, 0), (0, 8)), ((0, 2), (3, 0)), ((0, 5), (3, 7)), ((3, 0), (3, 3))),
        (((1, 0), (1, 8)), ((1, 4), (4, 2)), ((1, 4), (4, 6)), ((4, 6), (4, 8))),
        (((0, 1), (4, 1)), ((2, 1), (2, 8)), ((0, 5), (4, 5)), ((0, 8), (1, 8))),
    )[variant % 3]
    for start, end in strokes:
        pygame.draw.line(s, color, (x + start[0], y + start[1]), (x + end[0], y + end[1]))
        if light is not None:
            pygame.draw.line(s, light, (x + start[0] + 1, y + start[1] + 1), (x + end[0] + 1, y + end[1] + 1))
    return s


def selvar_door():
    """A slate slab door in the north wall, carved with three glyphs, sealed with a blue seam."""
    s = surface(32, 32)
    # Carved pillars.
    for x in (0, 27):
        pygame.draw.rect(s, SLATE[1], (x, 0, 5, 32))
        pygame.draw.line(s, SLATE[3], (x, 0), (x, 31))
        pygame.draw.line(s, SLATE[0], (x + 4, 0), (x + 4, 31))
        for y in range(3, 30, 6):
            pygame.draw.line(s, SLATE[0], (x + 1, y), (x + 3, y))
            pygame.draw.line(s, SLATE[2], (x + 1, y + 1), (x + 3, y + 1))
    pygame.draw.rect(s, SLATE[1], (0, 0, 32, 4))
    pygame.draw.line(s, SLATE[4], (0, 0), (31, 0))
    pygame.draw.line(s, SLATE[0], (5, 3), (26, 3))
    # The slab.
    for y in range(4, 32):
        for x in range(5, 27):
            light = (27 - x) / 22 * .55 + (32 - y) / 28 * .45
            tone = ramp_at(SLATE, 1.2 + light * 3 + ((x * 5 + y * 11) % 7 == 0) * .7)
            s.set_at((x, y), tone)
    for i, x in enumerate((8, 14, 20)):
        selvar_glyph(s, (x, 9), i, SLATE[0], SLATE[5])
    # The seal: a thin blue seam down the middle that pulses in the dark.
    for y in range(5, 32):
        s.set_at((16, y), BLUE[1] if y % 5 else BLUE[2])
        if y % 3 == 0:
            s.set_at((15, y), mix(s.get_at((15, y))[:3], BLUE[0], .6))
    for x, y in ((16, 22), (16, 23)):
        s.set_at((x, y), BLUE[3])
    pygame.draw.line(s, SLATE[0], (5, 31), (26, 31))
    return s


def floor_crack():
    """Floor plates heaved up from below, with cracks running out from the middle."""
    rng = random.Random(9)
    s = surface(32, 32)
    centre = (16, 16)
    for angle in (0.25, 1.3, 2.2, 3.1, 4.05, 5.15):
        x, y = centre
        length = rng.randint(10, 14)
        for step in range(length):
            angle += rng.uniform(-.35, .35)
            x += cos(angle)
            y += sin(angle)
            px, py = round(x), round(y)
            if 0 <= px < 32 and 0 <= py < 32:
                s.set_at((px, py), (14, 10, 24, 255))
                if 0 <= py - 1 and step < length - 3:
                    s.set_at((px, py - 1), (*STONE[4], 200))
    # A raised lip around the centre.
    for a in range(0, 360, 8):
        r = 5 + (a % 24 == 0)
        x, y = round(16 + cos(a * pi / 180) * r), round(16 + sin(a * pi / 180) * r * .8)
        s.set_at((x, y), (*STONE[5], 220) if y < 16 else (*STONE[0], 230))
    pygame.draw.ellipse(s, (10, 7, 18, 255), (13, 14, 6, 4))
    return s


def knocker_burrow():
    """Where the Old Knocker came up: a ragged hole ringed with rubble and split timber."""
    rng = random.Random(4)
    s = surface(32, 32)
    pygame.draw.ellipse(s, (*STONE[1], 255), (1, 4, 30, 25))
    for y in range(32):
        for x in range(32):
            d = hypot((x - 16) / 13.5, (y - 16.5) / 10.5)
            if d < 1:
                tone = (6, 4, 12) if d < .62 else (16, 11, 28) if d < .78 else None
                if tone:
                    s.set_at((x, y), tone)
    for _ in range(26):
        a = rng.uniform(0, 2 * pi)
        x = 16 + cos(a) * rng.uniform(11, 15)
        y = 16.5 + sin(a) * rng.uniform(8.5, 11.5)
        tone = STONE[rng.randint(2, 5)]
        pygame.draw.rect(s, tone, (round(x), round(y), rng.randint(1, 3), rng.randint(1, 2)))
    for (x1, y1), (x2, y2) in (((4, 7), (11, 11)), ((25, 25), (20, 21)), ((27, 8), (22, 12))):
        pygame.draw.line(s, WOOD[3], (x1, y1), (x2, y2), 2)
        pygame.draw.line(s, WOOD[5], (x1, y1), (x2, y2))
    outline(s)
    return s


# --- Hesk ------------------------------------------------------------------------------
def hesk_sheet():
    """Larvel's sheet with a slate cap, a rust coat and an ink-dark ledger satchel."""
    sheet = pygame.image.load(str(ASSETS / "larvel-overworld.png")).convert_alpha()
    out = sheet.copy()
    for y in range(sheet.get_height()):
        for x in range(sheet.get_width()):
            r, g, b, a = sheet.get_at((x, y))
            if not a:
                continue
            light = (r + g + b) / 3
            if g > r and g > b and g - b > 8:          # green work coat -> rust
                out.set_at((x, y), (min(255, int(light * 2.1 + 12)), min(255, int(light * 1.0 + 4)), int(light * .7), a))
            elif r > g > b and r - b > 30 and light < 120 and (r - g) < 40:  # brown hat -> slate cap
                out.set_at((x, y), (int(light * .82), int(light * .86), int(light * 1.08), a))
    return out


# --- the Old Knocker --------------------------------------------------------------------
KNOCKER_SOURCE = ASSETS / "battle" / "old-knocker-source.png"
KNOCKER_SIZE = 30           # longest side in native pixels; battle zooms 10x, so ~300 on screen
KNOCKER_COLORS = 12
KNOCKER_BACKDROP = (30, 30, 30)
KNOCKER_MOUTH = (357, 121)  # centre of the round mouth on the source art


def _lum(color):
    return sum(color) / 3


def _grade(color):
    """Lift the dark render so it reads in a dark cave: gamma, contrast and a little saturation."""
    r, g, b = (255 * (v / 255) ** .78 for v in color)
    mean = (r + g + b) / 3
    r, g, b = (mean + (v - mean) * 1.25 for v in (r, g, b))
    return tuple(max(0, min(255, (v - 60) * 1.18 + 64)) for v in (r, g, b))


def _palette(points, count, seed=3):
    """A small k-means palette, the way a pixel artist limits a sprite's ramps."""
    rng = random.Random(seed)
    centres = sorted(rng.sample(points, count))
    for _ in range(14):
        groups = [[] for _ in centres]
        for p in points:
            groups[min(range(count), key=lambda k: sum((a - b) ** 2 for a, b in zip(p, centres[k])))].append(p)
        centres = [tuple(sum(c[i] for c in g) / len(g) for i in range(3)) if g else centres[j]
                   for j, g in enumerate(groups)]
    return [tuple(round(v) for v in c) for c in centres]


def old_knocker():
    """The Old Knocker, pixelated from the concept art: a hunched, tube-mouthed borer.

    The backdrop is flooded away from the borders, each sprite pixel averages the creature's
    pixels under it, and the colours are graded and cut to a small palette. Kept very chunky on
    purpose: 30 native pixels tall, zoomed 10x in battle. Ink only on the shadow side (below and
    right), a soft top-left rim, and one focal point, a dark mouth ring with blue light in the throat.
    """
    from collections import deque
    src = pygame.image.load(str(KNOCKER_SOURCE)).convert()
    w, h = src.get_size()
    px = [[src.get_at((x, y))[:3] for x in range(w)] for y in range(h)]
    back = [[False] * w for _ in range(h)]
    queue = deque([(x, y) for x in range(w) for y in (0, h - 1)] + [(x, y) for y in range(h) for x in (0, w - 1)])
    while queue:
        x, y = queue.popleft()
        if (0 <= x < w and 0 <= y < h and not back[y][x]
                and max(abs(a - b) for a, b in zip(px[y][x], KNOCKER_BACKDROP)) <= 9):
            back[y][x] = True
            queue.extend(((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))
    inside = [(x, y) for y in range(h) for x in range(w) if not back[y][x]]
    x0, x1 = min(x for x, _ in inside), max(x for x, _ in inside) + 1
    y0, y1 = min(y for _, y in inside), max(y for _, y in inside) + 1
    step = max(x1 - x0, y1 - y0) / KNOCKER_SIZE
    tw, th = round((x1 - x0) / step), round((y1 - y0) / step)

    cells = {}
    for ty in range(th):
        for tx in range(tw):
            sx0, sy0 = int(x0 + tx * step), int(y0 + ty * step)
            sx1, sy1 = max(sx0 + 1, int(x0 + (tx + 1) * step)), max(sy0 + 1, int(y0 + (ty + 1) * step))
            under = [px[y][x] for y in range(sy0, min(sy1, h)) for x in range(sx0, min(sx1, w)) if not back[y][x]]
            if len(under) >= (sy1 - sy0) * (sx1 - sx0) * .5:
                cells[(tx, ty)] = _grade(tuple(sum(c[i] for c in under) / len(under) for i in range(3)))

    palette = _palette(list(cells.values()), KNOCKER_COLORS)
    s = surface(tw, th)
    for spot, color in cells.items():
        s.set_at(spot, min(palette, key=lambda c: sum((a - b) ** 2 for a, b in zip(color, c))))
    for x, y in list(cells):  # no stray single pixels on the silhouette
        if sum(n in cells for n in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1))) <= 1:
            s.set_at((x, y), CLEAR)
            del cells[(x, y)]

    solid = set(cells)
    for x, y in solid:  # a soft pale rim where the cave light catches the top-left edges
        if (x - 1, y) not in solid or (x, y - 1) not in solid:
            s.set_at((x, y), mix(s.get_at((x, y))[:3], (214, 214, 190), .2))
    # The mouth reads as one dark ring with blue-stone light deep in the throat.
    cx, cy = round((KNOCKER_MOUTH[0] - x0) / step - .5), round((KNOCKER_MOUTH[1] - y0) / step - .5)
    glow = {0: (168, 224, 252), 1: (60, 122, 196)}
    ring = max(2, round(10 * (KNOCKER_SIZE / 60) ** 2))
    for x, y in solid:
        d2 = (x - cx) ** 2 + (y - cy) ** 2
        if d2 in glow:
            s.set_at((x, y), glow[d2])
        elif d2 <= ring:
            s.set_at((x, y), (40, 35, 33) if x <= cx else (62, 56, 50))
    # Only a little ink: a dark edge under and to the right of the body, where it is in shadow.
    # The lit top and left edges stay open against the cave.
    for x, y in solid:
        for nx, ny in ((x + 1, y), (x, y + 1)):
            if 0 <= nx < tw and 0 <= ny < th and (nx, ny) not in solid and not s.get_at((nx, ny))[3]:
                s.set_at((nx, ny), (26, 22, 21))
    return s


# --- Pit Lantern icon -----------------------------------------------------------------
def pit_lantern():
    s = surface(32, 32)
    iron = ((34, 32, 40), (58, 56, 66), (92, 90, 100), (140, 138, 148))
    # Bail handle.
    pygame.draw.arc(s, iron[2], (10, 2, 12, 10), 0, pi, 2)
    pygame.draw.arc(s, iron[3], (10, 2, 12, 10), pi * .45, pi, 1)
    # Cap and base.
    pygame.draw.polygon(s, iron[2], ((10, 10), (22, 10), (20, 7), (12, 7)))
    pygame.draw.line(s, iron[3], (12, 7), (20, 7))
    pygame.draw.rect(s, iron[1], (9, 24, 14, 4))
    pygame.draw.line(s, iron[2], (9, 24), (22, 24))
    # Glass with the flame.
    for y in range(11, 24):
        for x in range(11, 21):
            d = hypot((x - 15.5) / 5, (y - 18) / 6.5)
            glow = max(0, 1 - d)
            s.set_at((x, y), mix(AMBER[1], AMBER[3], glow))
    pygame.draw.polygon(s, (255, 248, 214), ((15, 15), (17, 18), (16, 21), (14, 20), (14, 17)))
    s.set_at((15, 14), AMBER[3])
    # Cage bars.
    for x in (10, 15, 21):
        pygame.draw.line(s, iron[1] if x != 15 else iron[2], (x, 10), (x, 24))
    s.set_at((12, 12), (255, 255, 240))
    outline(s)
    return s


def charcoal():
    s = surface(16, 16)
    pygame.draw.polygon(s, (34, 26, 43), ((3, 11), (8, 8), (13, 8), (13, 12), (6, 14)))
    pygame.draw.polygon(s, (169, 142, 112), ((4, 11), (8, 9), (12, 9), (12, 11), (6, 13)))
    pygame.draw.line(s, (24, 20, 33), (5, 11), (11, 7), 3)
    pygame.draw.line(s, (107, 92, 116), (7, 10), (11, 7))
    return s


def shortcut():
    s = surface(22, 28)
    pygame.draw.polygon(s, (25, 19, 37), ((1, 27), (1, 9), (5, 4), (9, 2), (14, 2), (19, 6), (21, 11), (21, 27)))
    pygame.draw.polygon(s, (64, 51, 86), ((3, 26), (3, 10), (7, 5), (14, 4), (18, 8), (19, 13), (19, 26)))
    pygame.draw.polygon(s, (17, 14, 29), ((6, 27), (6, 12), (9, 8), (13, 8), (16, 11), (16, 27)))
    pygame.draw.lines(s, (119, 95, 137), False, ((3, 16), (4, 10), (7, 6), (13, 4), (16, 6)))
    pygame.draw.line(s, (77, 60, 103), (6, 26), (16, 26))
    return s


def refuge_miner(coat, hat, skin):
    s = surface(16, 16)
    pygame.draw.polygon(s, (22, 16, 29), ((3, 4), (5, 2), (10, 2), (12, 5), (11, 8),
                                         (13, 11), (12, 15), (4, 15), (3, 12), (5, 8)))
    pygame.draw.polygon(s, coat, ((5, 9), (10, 9), (11, 11), (11, 13), (8, 12), (6, 14), (4, 13)))
    pygame.draw.rect(s, skin, (5, 5, 6, 4))
    pygame.draw.polygon(s, hat, ((4, 5), (6, 3), (9, 3), (11, 4), (12, 5), (10, 6), (4, 6)))
    pygame.draw.line(s, (28, 20, 34), (6, 7), (8, 7))
    s.set_at((10, 7), (33, 22, 37))
    return s


def main():
    pygame.display.init()
    pygame.display.set_mode((1, 1), pygame.HIDDEN)
    OUT.mkdir(parents=True, exist_ok=True)
    pieces = {
        "stair-up": stair_up(),
        "ledger-post": ledger_post(True),
        "ledger-post-bare": ledger_post(False),
        "selvar-door": selvar_door(),
        "floor-crack": floor_crack(),
        "knocker-burrow": knocker_burrow(),
        "charcoal": charcoal(),
        "shortcut": shortcut(),
    }
    for key, word in RUBBING_FJALORA.items():
        pieces[f"stele-{key}"] = stele(word, False)
        pieces[f"stele-{key}-rubbed"] = stele(word, True)
    for i, colors in enumerate((((74, 55, 71), (84, 73, 94), (200, 150, 116)),
                                ((95, 69, 49), (108, 87, 67), (175, 123, 89)),
                                ((53, 70, 82), (63, 60, 79), (151, 106, 86)))):
        pieces[f"crew-{i}"] = refuge_miner(*colors)
    for name, image in pieces.items():
        pygame.image.save(image, str(OUT / f"{name}.png"))
    pygame.image.save(hesk_sheet(), str(ASSETS / "hesk-overworld.png"))
    pygame.image.save(old_knocker(), str(ASSETS / "battle" / "old-knocker.png"))
    pygame.image.save(pit_lantern(), str(ASSETS / "items" / "accessories" / "pit_lantern.png"))


if __name__ == "__main__":
    main()
