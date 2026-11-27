"""Draw the rooms inside Windehus (windehus_rooms.py): their floors and walls, and the furniture.

Original art on the game's 16 px grid, in the town's view and light (from above and in front,
lit from the top left), with the town's palettes so a room matches its building outside.
Writes into assets/town/rooms/:

    <room>-ground.png   the room's flat layer baked into one opaque image: the dark around it,
                        the floor and its rugs, the back wall's face with its windows and what
                        hangs on it, the tops of the walls, and the doorway
    furniture.png       every piece that stands on the floor, packed
    furniture.json      {name: [x, y, w, h]} into furniture.png

Run with the project venv (pygame):  python prepare_town_rooms.py
"""
from math import asin, atan2, pi, sin, sqrt
import json
import random

import pygame

import prepare_town_tiles as T
from prepare_town_tiles import (BARK, BLOOMS, BRICK, FIRE, FLAG, GLASS, GLOW, INK, IRON, LEAF, PLASTER, RUBBLE,
                                RUBBLE_MORTAR, STRAW, TWINE, WOOD, ground_shadow, mix, noise, put, ramp,
                                soft_outline, surface)
import windehus_rooms as R

OUT = T.OUT / "rooms"
TILE = R.TILE
VOID = (9, 9, 12)                       # the game canvas's own dark, so a room floats in it
BEAM = ((22, 15, 13), (36, 24, 19), (54, 36, 26), (76, 52, 36), (102, 70, 48), (128, 92, 64))
FLOORWOOD = ((52, 34, 24), (74, 50, 34), (98, 66, 44), (122, 84, 56), (146, 104, 70), (168, 126, 88))
STEEL = ((38, 42, 52), (66, 72, 86), (104, 112, 128), (152, 160, 174), (208, 214, 224))
GOLD = ((92, 60, 20), (146, 104, 34), (204, 158, 58), (242, 208, 108))
LINEN = ((140, 136, 126), (182, 178, 166), (216, 212, 200), (240, 238, 230))
FLOUR = ((112, 104, 92), (158, 150, 136), (198, 192, 178), (230, 226, 216))
QUILTS = (((90, 30, 34), (130, 46, 46), (168, 66, 58), (198, 96, 78)),
          ((40, 64, 50), (56, 90, 64), (78, 118, 80), (108, 146, 100)),
          ((44, 52, 96), (60, 74, 130), (84, 102, 160), (118, 136, 188)))
RUG = ((92, 24, 26), (138, 36, 34), (178, 58, 44), (214, 164, 72), (236, 206, 130))
SKY = ((120, 160, 196), (164, 196, 222), (206, 226, 240))
POTIONS = ((176, 40, 48), (52, 92, 190), (60, 150, 80), (196, 160, 50), (150, 70, 170))


# --- floors and walls ---------------------------------------------------------------------------
def _planks(x, y, seed):
    """Floorboards running across the room, 4 px wide, their ends staggered."""
    board, r = divmod(y, 4)
    length = 24 + int(noise(board, 0, seed) * 4) * 8
    offset = int(noise(board, 1, seed) * length)
    piece, along = divmod(x + offset, length)
    tone = 2.6 + (noise(board, piece, seed + 2) - .5) * 1.4
    if r == 3:
        tone -= 1.3                                     # the gap between boards
    elif r == 0:
        tone += .4
    if along == 0:
        return FLOORWOOD[0]
    if along == 2 and r == 1:
        return IRON[1]                                  # a nail head
    tone += (noise(x // 3, y, seed + 3) - .5) * .5
    return ramp(FLOORWOOD, tone)


def _flags(x, y, seed):
    """Big worn flagstones in staggered courses, for a smithy floor."""
    course, r = divmod(y, 12)
    w = 18 + int(noise(course, 0, seed) * 3) * 4
    piece, along = divmod(x + int(noise(course, 1, seed) * w), w)
    if r == 11 or along == 0:
        return FLAG[0]
    tone = 2.3 + (noise(piece, course, seed + 2) - .5) * 1.2 + (r == 0) * .6 + (along == 1) * .4 - (r == 10) * .5
    return ramp(FLAG, tone + (noise(x, y, seed + 3) - .5) * .5)


def _wall_face(room, x, y, seed):
    """The back wall's face, y counted down from the coping (0) to the floor (31)."""
    if room.wall == "plaster":
        if y < 3:
            return ramp(BEAM, 3.6 - y * .8)             # the head beam
        if (x - 8) % 16 in (0, 1):
            return WOOD[3] if (x - 8) % 16 == 0 else WOOD[1]   # timber studs
        if y >= 21:
            if y in (21, 30):
                return WOOD[4] if y == 21 else WOOD[1]
            return ramp(WOOD, 2.6 - ((x % 6) == 5) * 1.0 - (y > 27) * .4)  # plank wainscot
        return ramp(PLASTER, 2.2 + (noise(x // 2, y // 2, seed) - .5) * .7 - (y < 6) * .8)
    if room.wall == "stone":
        if y < 3:
            return ramp(BEAM, 3.6 - y * .8)
        if y >= 29:
            return ramp(FLAG, 1.4 if y == 29 else .8)      # the plinth course
        course, row = divmod(y - 3, 5)
        bx = (x + (course % 2) * 6) % 12
        if row == 4 or bx == 11:
            return FLAG[0]
        block = ((x + (course % 2) * 6) // 12, course)
        tone = 2.3 + (noise(*block, seed) - .5) * 1.2 + (row == 0) * .8 + (bx == 0) * .3 - (row == 3) * .5
        return ramp(FLAG, tone - (y < 7) * .7)
    # Rubble, like the mill tower outside.
    if y < 2:
        return ramp(BEAM, 3.2 - y)
    cell = (x // 7 + (y // 5) * 3, y // 5)
    pal = RUBBLE[int(noise(*cell, seed) * len(RUBBLE))]
    if (x + (y // 5) * 3) % 7 == 0 or y % 5 == 4:
        return mix(RUBBLE_MORTAR, INK, .35)
    return ramp(pal, 2.2 + (y % 5 == 0) * .8 - (y < 8) * .7 + (noise(x, y, seed + 1) - .5) * .6)


def _window(g, x0, y0):
    """A deep-set window in the back wall: a lit sill, daylight in the panes, a cross bar,
    and its light falling in a pale patch on the floor below."""
    for y in range(y0, y0 + 15):
        for x in range(x0 + 2, x0 + 14):
            edge = x in (x0 + 2, x0 + 13) or y in (y0, y0 + 14)
            if edge:
                g.set_at((x, y), BEAM[2] if x == x0 + 13 or y == y0 + 14 else BEAM[4])
            elif x == x0 + 7 or y == y0 + 6:
                g.set_at((x, y), WOOD[2])
            else:
                g.set_at((x, y), SKY[2] if (x - x0) + (y - y0) < 9 else SKY[1] if y < y0 + 10 else SKY[0])
    for x in range(x0 + 1, x0 + 15):
        g.set_at((x, y0 + 15), FLAG[4])
        g.set_at((x, y0 + 16), FLAG[1])
    # Daylight on the floor under it.
    for y in range(y0 + 18, y0 + 34):
        spread = (y - y0 - 18) // 3
        for x in range(x0 + 3 - spread, x0 + 13 + spread):
            if 0 <= x < g.get_width() and y < g.get_height():
                g.set_at((x, y), mix(g.get_at((x, y))[:3], (236, 214, 160), .16 - (y - y0 - 18) * .008))


def _decor(g, piece, x0, y0):
    """Something hung on the back wall, in a 16 px column, y0 the top of the wall face."""
    if piece == "notice":
        for y in range(y0 + 8, y0 + 22):
            for x in range(x0 + 1, x0 + 15):
                edge = x in (x0 + 1, x0 + 14) or y in (y0 + 8, y0 + 21)
                g.set_at((x, y), WOOD[1] if edge else ramp(WOOD, 3.2 + (noise(x, y, 40) - .5)))
        for px, py, w, h in ((3, 10, 5, 6), (9, 11, 4, 5), (5, 15, 6, 4)):
            for y in range(y0 + py, y0 + py + h):
                for x in range(x0 + px, x0 + px + w):
                    g.set_at((x, y), LINEN[3] if y == y0 + py else LINEN[2] if (y - py) % 2 else LINEN[1])
            g.set_at((x0 + px + w // 2, y0 + py), (170, 40, 40))
    elif piece in ("plaque-swords", "plaque-shield"):
        cx = x0 + 8
        for y in range(y0 + 6, y0 + 24):
            half = 6 if y < y0 + 16 else 6 - (y - y0 - 16)
            for x in range(cx - half, cx + half):
                edge = x in (cx - half, cx + half - 1) or y == y0 + 6
                if piece == "plaque-shield":
                    quarter = (x < cx) != (y < y0 + 14)
                    color = (150, 40, 40) if quarter else GOLD[2]
                    g.set_at((x, y), STEEL[3] if edge else mix(color, INK, .25 * (x >= cx)))
                else:
                    g.set_at((x, y), WOOD[1] if edge else ramp(WOOD, 3.4 - (x >= cx) * .8))
        if piece == "plaque-swords":
            for i in range(14):
                for sx, d in ((cx - 7, 1), (cx + 6, -1)):
                    x, y = sx + i * d, y0 + 5 + i
                    g.set_at((x, y), STEEL[4] if i < 10 else GOLD[2])
                    if i == 10:
                        for k in (-1, 1):
                            g.set_at((x + k, y + k * d * 0), GOLD[1])
    elif piece == "herbs":
        for i, cx in enumerate((x0 + 3, x0 + 8, x0 + 12)):
            for y in range(y0 + 3, y0 + 5):
                g.set_at((cx, y), TWINE[1])
            for y in range(y0 + 5, y0 + 13 + i % 2 * 2):
                spread = (y - y0 - 5) // 3
                for x in range(cx - 1 - spread, cx + 2 + spread):
                    if noise(x, y, 41 + i) > .35:
                        g.set_at((x, y), ramp(LEAF, 3.4 - (x - cx) * .5) if i != 1 else ramp(STRAW, 2.4 - (x - cx) * .4))
    elif piece == "lantern":
        cx = x0 + 8
        for x in range(cx - 1, cx + 2):
            g.set_at((x, y0 + 8), IRON[2])
        for y in range(y0 + 9, y0 + 17):
            for x in range(cx - 3, cx + 3):
                edge = x in (cx - 3, cx + 2) or y in (y0 + 9, y0 + 16)
                g.set_at((x, y), IRON[1] if edge else (FIRE[2] if y < y0 + 13 else FIRE[1]))
        for y in range(y0 + 6, y0 + 22):
            for x in range(cx - 8, cx + 8):
                d = sqrt((x + .5 - cx) ** 2 + (y + .5 - y0 - 13) ** 2)
                if 4 < d < 8:
                    g.set_at((x, y), mix(g.get_at((x, y))[:3], (240, 180, 90), .14 * (1 - (d - 4) / 4)))


def _rug(g, x0, y0, x1, y1):
    """A woven rug: a red field with a gold and cream border, a diamond medallion, and
    fringe at its ends."""
    px0, py0, px1, py1 = x0 * TILE + 3, y0 * TILE + 3, (x1 + 1) * TILE - 3, (y1 + 1) * TILE - 3
    cx, cy = (px0 + px1) / 2, (py0 + py1) / 2
    for y in range(py0, py1):
        for x in range(px0, px1):
            inset = min(x - px0, px1 - 1 - x, y - py0, py1 - 1 - y)
            if inset == 0:
                c = RUG[0]
            elif inset in (1, 3):
                c = RUG[3]
            elif inset == 2:
                c = RUG[0]
            else:
                d = abs(x + .5 - cx) / ((px1 - px0) / 2 - 4) + abs(y + .5 - cy) / ((py1 - py0) / 2 - 4)
                c = RUG[4] if abs(d - .6) < .06 else RUG[3] if d < .25 else RUG[1] if d < .6 else RUG[2]
                if (x + y) % 4 == 0 and d > .7:
                    c = RUG[1]
            g.set_at((x, y), c)
    for x in range(px0, px1, 2):
        for y in (py0 - 1, py1):
            g.set_at((x, y), LINEN[2])


def _beam_band(g, x0, y0, w, h, vertical):
    """The top of a wall seen from above: a dark beam, lit along its upper or left edge."""
    for y in range(y0, y0 + h):
        for x in range(x0, x0 + w):
            k = (x - x0) if vertical else (y - y0)
            n = w if vertical else h
            tone = 2.4 - k / n * 1.4 + (k == 0) * 1.4 + (noise(x // 4 if not vertical else x, y // 4 if vertical else y, 9) - .5) * .4
            g.set_at((x, y), ramp(BEAM, tone))


def room_ground(room):
    """The room's flat layer, opaque."""
    rows = R.grid(room)
    w, h = room.width, room.height
    g = pygame.Surface((w * TILE, h * TILE))
    g.fill(VOID)
    seed = sum(map(ord, room.name))
    if room.wall == "rubble":
        _mill_ground(g, room, seed)
        return g
    # Floor, under the doorway too.
    for ty, row in enumerate(rows):
        for tx, ch in enumerate(row):
            if ch in (R.FLOOR, R.DOORWAY):
                for y in range(ty * TILE, (ty + 1) * TILE):
                    for x in range(tx * TILE, (tx + 1) * TILE):
                        g.set_at((x, y), (_planks if room.floor == "planks" else _flags)(x, y, seed))
    for rug in room.rugs:
        _rug(g, *rug)
    # Shade where the back and left walls stand over the floor.
    for y in range(3 * TILE, 3 * TILE + 8):
        for x in range(TILE, (w - 1) * TILE):
            g.set_at((x, y), mix(g.get_at((x, y))[:3], INK, .5 - (y - 3 * TILE) * .06))
    for x in range(TILE, TILE + 5):
        for y in range(3 * TILE, (h - 1) * TILE):
            g.set_at((x, y), mix(g.get_at((x, y))[:3], INK, .3 - (x - TILE) * .06))
    # The back wall's face, its windows and what hangs on it.
    for y in range(TILE, 3 * TILE):
        for x in range(TILE, (w - 1) * TILE):
            g.set_at((x, y), _wall_face(room, x, y - TILE, seed))
    for col in room.windows:
        _window(g, col * TILE, TILE + 7)
    for piece, col in room.decor:
        _decor(g, piece, col * TILE, TILE)
    # Wall tops: the coping along the back, the side walls, the front wall with its doorway.
    _beam_band(g, TILE - 6, TILE - 6, (w - 2) * TILE + 12, 6, False)
    _beam_band(g, TILE - 6, TILE - 6, 6, (h - 1) * TILE + 6, True)
    _beam_band(g, (w - 1) * TILE, TILE - 6, 6, (h - 1) * TILE + 6, True)
    dx = R.doorway(room)[0] * TILE
    for x0, x1 in ((TILE - 6, dx), (dx + TILE, (w - 1) * TILE + 6)):
        _beam_band(g, x0, (h - 1) * TILE, x1 - x0, 6, False)
    _doorway(g, dx, (h - 1) * TILE)
    return g


def _doorway(g, x0, y0):
    """The way out: a stone sill and a mat between the jambs, daylight beyond."""
    for y in range(y0, y0 + TILE):
        for x in range(x0, x0 + TILE):
            if y >= y0 + 9:
                g.set_at((x, y), mix((236, 214, 160), VOID, (y - y0 - 9) / 8))
            elif y >= y0 + 6:
                g.set_at((x, y), FLAG[4] if y == y0 + 6 else FLAG[2])
            else:
                g.set_at((x, y), (130, 54, 44) if (x + y) % 2 else (104, 42, 36))
    for y in range(y0 - 4, y0 + 9):
        for x, c in ((x0 - 1, BEAM[4]), (x0, BEAM[2]), (x0 + TILE - 1, BEAM[1]), (x0 + TILE, BEAM[3])):
            g.set_at((x, y), c)


def _curved_window(g, centre_x, cx, cy, rx, ry, face_h):
    """A window set in the mill's round wall, drawn on the wall itself: its rows follow the
    curve of the courses, it narrows as the wall turns away toward the sides, and the jamb on
    the side facing the room shows its depth."""
    s0 = asin(max(-1.0, min(1.0, (centre_x - cx) / rx))) * rx      # its centre, measured round the wall
    half, top, bottom = 7.0, 7, 22                                  # around the wall, and down the face
    turn = (centre_x - cx) / rx                                     # < 0 on the left: its right jamb shows
    for x in range(int(centre_x - half - 2), int(centre_x + half + 3)):
        dx = (x + .5 - cx) / rx
        if abs(dx) >= 1:
            continue
        u = asin(dx) * rx - s0
        if abs(u) > half + 1:
            continue
        arc = cy - ry * sqrt(1 - dx * dx)
        face_top = arc - face_h
        for v in range(top, bottom + 3):
            y = int(face_top + v)
            if not 0 <= y < g.get_height():
                continue
            if v >= bottom:
                if abs(u) <= half + 1:
                    g.set_at((x, y), FLAG[4] if v == bottom else FLAG[1])        # the sill
                continue
            if abs(u) > half:
                continue
            frame = abs(u) > half - 1.2 or v in (top, bottom - 1)
            reveal = (u > half - 2.6 if turn < 0 else u < -half + 2.6) and not frame
            if frame:
                g.set_at((x, y), BEAM[2] if v == bottom - 1 or (u > 0) == (turn < 0) else BEAM[4])
            elif reveal:
                g.set_at((x, y), ramp(RUBBLE[0], 2.4 - (v - top) * .06))   # the deep jamb, catching light
            elif abs(u) < .6 or v == top + 6:
                g.set_at((x, y), WOOD[2])                                # the cross bar
            else:
                g.set_at((x, y), SKY[2] if (u + half) + (v - top) < 9 else SKY[1] if v < top + 10 else SKY[0])


def _mill_ground(g, room, seed):
    """The mill's round room: worn floorboards in an oval, the rubble wall's face round the
    back of it, its coping round the whole, and the doorway at the front."""
    cx, cy, rx, ry = R.MILL_OVAL
    cx, cy, rx, ry = cx * TILE, cy * TILE, rx * TILE + 4, ry * TILE + 4
    face_h = 2 * TILE
    W, H = g.get_size()
    for y in range(H):
        for x in range(W):
            dx = (x + .5 - cx) / rx
            d = dx * dx + ((y + .5 - cy) / ry) ** 2
            if d <= 1:
                c = _planks(x, y, seed)
                if noise(x // 2, y // 2, seed + 7) > .94:
                    c = mix(c, FLOUR[2], .3)                      # a little flour dust
                g.set_at((x, y), mix(c, INK, max(0.0, d - .55) * .9))
                continue
            if abs(dx) < 1:
                arc = cy - ry * sqrt(1 - dx * dx)
                if arc - face_h <= y + .5 < arc:
                    g.set_at((x, y), _wall_face(room, x, int(y + .5 - (arc - face_h)), seed))
                    continue
            # The coping: a band just outside the floor and over the face.
            outer = (dx / 1.06) ** 2 + ((y + .5 - cy + (face_h * .5 if y < cy else 0)) / (ry + (face_h * .5 if y < cy else 0) + 6)) ** 2
            if outer <= 1:
                g.set_at((x, y), ramp(BEAM, 2.6 - (y < cy) * .4 + (noise(x // 4, y // 4, 9) - .5) * .5))
    for col in room.windows:
        _curved_window(g, col * TILE + 8, cx, cy, rx, ry, face_h)
    for piece, col in room.decor:
        x = col * TILE
        dx = (x + 8 - cx) / rx
        arc = cy - ry * sqrt(max(0.0, 1 - dx * dx))
        _decor(g, piece, x, int(arc - face_h))
    dx, dy = R.doorway(room)
    _doorway(g, dx * TILE, dy * TILE)


# --- furniture -------------------------------------------------------------------------------------
def _box(s, x0, y0, w, depth, h, top, front, seed=0, lip=True):
    """A block seen from above and in front: a top face `depth` rows deep, then a front face
    `h` rows tall. Lit on the top-left; the right end and the foot fall into shade."""
    for y in range(y0, y0 + depth):
        for x in range(x0, x0 + w):
            tone = 3.9 - (x - x0) / w * .8 + (y == y0) * .6 - (x == x0 + w - 1) * .8
            s.set_at((x, y), ramp(top, tone + (noise(x // 3, y, seed) - .5) * .4))
    for y in range(y0 + depth, y0 + depth + h):
        for x in range(x0, x0 + w):
            tone = 2.5 - (x - x0) / w * .8 - (y - y0 - depth) / max(1, h) * .5 + (x == x0) * .6 - (x == x0 + w - 1) * .7
            if lip and y == y0 + depth:
                tone += 1.0
            s.set_at((x, y), ramp(front, tone + (noise(x, y // 3, seed + 1) - .5) * .4))


def stool():
    s = surface(16, 16)
    ground_shadow(s, 9.5, 13.8, 5, 1.3)
    for x, top in ((4, 9), (11, 9), (8, 10)):
        for y in range(top, 14):
            s.set_at((x, y), WOOD[2] if x != 11 else WOOD[1])
    for y in range(4, 10):
        for x in range(2, 14):
            dx, dy = (x + .5 - 8) / 6, (y + .5 - 6.5) / 2.6
            if dx * dx + dy * dy <= 1:
                s.set_at((x, y), ramp(WOOD, 4.2 - dx * .9 - (dy > .4) * 1.6))
    soft_outline(s)
    return s


def table():
    """A tavern table: a round top of boards with mugs, a plate of bread and a candle, on a
    stout trestle."""
    s = surface(32, 24)
    ground_shadow(s, 18, 21.5, 13, 2)
    for x in (9, 22):
        for y in range(12, 21):
            s.set_at((x, y), WOOD[2] if x == 9 else WOOD[1])
            s.set_at((x + 1, y), WOOD[1])
    for x in range(8, 24):
        s.set_at((x, 19), WOOD[2])
    for y in range(1, 14):
        for x in range(1, 31):
            dx, dy = (x + .5 - 16) / 15, (y + .5 - 6.5) / 5.5
            if dx * dx + dy * dy > 1:
                continue
            edge = dx * dx + dy * dy > .7 and dy > .2
            board = (x // 5) % 2
            tone = 3.9 - dx * .8 - board * .3 - (x % 5 == 0) * .6
            if edge:
                tone = 2.0 - dx * .5
            s.set_at((x, y), ramp(WOOD, tone))
    # A pair of mugs with foam, a plate of bread, a candle.
    for mx in (7, 20):
        for y in range(3, 7):
            for x in range(mx, mx + 3):
                s.set_at((x, y), STEEL[3] if x == mx else STEEL[2] if y > 3 else LINEN[3])
        s.set_at((mx + 3, 4), STEEL[1])
    for y in range(6, 9):
        for x in range(12, 18):
            if (x - 14.5) ** 2 / 9 + (y - 7.5) ** 2 / 2 <= 1:
                s.set_at((x, y), LINEN[2] if y > 6 else LINEN[3])
    for x, y, c in ((13, 7, (186, 126, 62)), (14, 7, (206, 150, 80)), (15, 6, (186, 126, 62))):
        s.set_at((x, y), c)
    for y in range(2, 5):
        s.set_at((25, y), LINEN[3])
    s.set_at((25, 1), FIRE[2])
    soft_outline(s)
    return s


def counter(n):
    """A shop counter n tiles long: a lit top with a ledger and a bell on it, and a front of
    framed panels."""
    w = n * TILE
    s = surface(w, 24)
    ground_shadow(s, w / 2 + 3, 22.5, w / 2 + 1, 1.5)
    _box(s, 0, 2, w, 7, 13, WOOD, WOOD, seed=n)
    for x in range(0, w):
        for y in range(10, 22):
            panel = (x % 16) in (0, 15) or y in (10, 21)
            if panel:
                s.set_at((x, y), WOOD[1] if (x % 16) == 15 or y == 21 else WOOD[4])
    for y in range(3, 7):
        for x in range(w - 22, w - 14):
            s.set_at((x, y), (120, 40, 36) if y > 3 else LINEN[3])
    s.set_at((w - 19, 4), LINEN[2])
    for x, y, c in ((7, 4, GOLD[3]), (8, 4, GOLD[2]), (7, 5, GOLD[1]), (8, 5, GOLD[1]), (6, 5, GOLD[2])):
        s.set_at((x, y), c)
    soft_outline(s)
    return s


def bar_shelf():
    """The shelving behind the bar: bottles, mugs and a cask on three shelves."""
    s = surface(64, 40)
    rng = random.Random(51)
    for y in range(0, 40):
        for x in range(0, 64):
            frame = x in (0, 1, 62, 63) or y in (0, 1)
            if frame:
                s.set_at((x, y), WOOD[3] if x in (0, 1) or y in (0, 1) else WOOD[1])
            else:
                s.set_at((x, y), mix(WOOD[1], INK, .3))
    for sy in (12, 24, 36):
        for x in range(1, 63):
            s.set_at((x, sy), WOOD[4])
            s.set_at((x, sy + 1), WOOD[2])
            s.set_at((x, sy + 2), mix(WOOD[1], INK, .4))
    for shelf_y in (12, 24):
        x = 3
        while x < 59:
            kind = rng.random()
            if kind < .55:
                color = rng.choice(((60, 110, 60), (110, 40, 40), (60, 70, 120), (150, 110, 50)))
                for y in range(shelf_y - 8, shelf_y):
                    neck = y < shelf_y - 5
                    for xx in range(x + neck, x + 3 - neck):
                        s.set_at((xx, y), mix(color, (255, 255, 255), .4) if xx == x + neck and not neck else color)
                x += 4
            else:
                for y in range(shelf_y - 5, shelf_y):
                    for xx in range(x, x + 3):
                        s.set_at((xx, y), STEEL[3] if xx == x else STEEL[2])
                s.set_at((x + 3, shelf_y - 4), STEEL[1])
                x += 5
    # A cask on its cradle on the bottom shelf.
    for y in range(26, 36):
        for x in range(20, 44):
            dy = (y + .5 - 31) / 5
            if abs(dy) <= 1:
                tone = 3.6 - dy * 1.4 - ((x - 20) % 6 == 0) * .6
                s.set_at((x, y), IRON[2] if x in (24, 39) else ramp(WOOD, tone))
    for y in range(28, 34):
        for x in range(17, 20):
            s.set_at((x, y), ramp(WOOD, 4.4 - (y - 28) * .5))
    s.set_at((18, 34), IRON[2])
    soft_outline(s)
    return s


def hearth(frame):
    """A stone fireplace: its chimney breast up the wall, a mantel beam with a pot and a
    candlestick, the firebox with logs and a fire (frame 0-2 of its flicker), and a
    hearthstone on the floor."""
    s = surface(32, 48)
    for y in range(0, 40):
        for x in range(2, 30):
            course, row = divmod(y, 5)
            bx = (x + (course % 2) * 4) % 8
            joint = row == 4 or bx == 7
            tone = 2.6 - (x - 2) / 28 * 1.0 + (row == 0) * .6 + (noise((x + (course % 2) * 4) // 8, course, 61) - .5) * 1.0
            s.set_at((x, y), FLAG[0] if joint else ramp(FLAG, tone))
    for x in range(0, 32):
        for y, tone in ((20, 4.4), (21, 3.4), (22, 2.0)):
            s.set_at((x, y), ramp(WOOD, tone - (x > 26) * .6))
    for x, y, c in ((5, 18, IRON[1]), (6, 18, IRON[2]), (5, 19, IRON[1]), (6, 19, IRON[1]), (4, 19, IRON[0]),
                    (25, 16, GOLD[2]), (25, 17, GOLD[1]), (25, 18, GOLD[1]), (24, 19, GOLD[1]), (26, 19, GOLD[1]),
                    (25, 15, LINEN[3]), (25, 14, FIRE[2])):
        s.set_at((x, y), c)
    # The firebox.
    for y in range(26, 40):
        for x in range(7, 25):
            arch = y < 28 and (x < 9 or x > 22)
            if not arch:
                s.set_at((x, y), mix(INK, (60, 20, 10), (y - 26) / 14 * .6))
    for x in range(8, 24):
        s.set_at((x, 38), ramp(BARK, 2.6 - (x % 5 == 0)))
        s.set_at((x, 37), ramp(BARK, 3.2 - (x % 5 == 0)))
    rng = random.Random(70 + frame)
    for tongue in range(5):
        fx = 10 + tongue * 3 + rng.choice((-1, 0, 1))
        height = rng.randint(4, 9) if tongue in (1, 2, 3) else rng.randint(3, 5)
        for i in range(height):
            y = 36 - i
            wobble = round(sin(i * .9 + frame * 2.1 + tongue) * .8)
            core = i < height * .5
            for x in range(fx + wobble - (i < height - 2), fx + wobble + 1 + (i < height - 2)):
                put(s, x, y, FIRE[2 if core else 1] if i < height - 1 else FIRE[0])
    for x in range(10, 22):
        if noise(x, frame, 72) > .4:
            s.set_at((x, 36), FIRE[3])
    # The hearthstone.
    for y in range(40, 47):
        for x in range(0, 32):
            s.set_at((x, y), ramp(FLAG, 4.2 - (y - 40) * .4 - (x > 27) * .7 - (x % 10 == 9) * .8 if y < 45 else 1.4))
    for y in range(40, 44):
        for x in range(8, 24):
            s.set_at((x, y), mix(s.get_at((x, y))[:3], FIRE[1], .18 - (y - 40) * .04))
    soft_outline(s)
    return s


def forge(frame):
    """A smith's forge: a brick hearth under a stone hood that narrows up into the wall,
    coals glowing on its bed (frame 0-2), the bellows on its left and tongs hung on its
    right."""
    s = surface(32, 48)
    for y in range(0, 26):
        inset = max(0, 8 - y // 3) if y < 24 else 0
        for x in range(4 + inset - 4, 28 - inset + 4):
            if not 2 <= x < 30:
                continue
            tone = 2.4 - (x - 2) / 28 * 1.2 + (y % 6 == 0) * .5 - (y % 6 == 5) * .7
            s.set_at((x, y), ramp(FLAG, tone + (noise(x // 5, y // 6, 81) - .5) * .7))
    for y in range(24, 26):
        for x in range(2, 30):
            s.set_at((x, y), FLAG[4] if y == 24 else FLAG[1])
    # The brick hearth block, its top a bed of coals.
    for y in range(26, 44):
        for x in range(2, 30):
            if y < 32:
                d = abs(x + .5 - 16) / 12
                heat = (noise(x, y, 82 + frame) + (1 - d)) / 2
                if y == 26:
                    s.set_at((x, y), BRICK[4])
                    continue
                s.set_at((x, y), FIRE[3] if heat > .82 else FIRE[2] if heat > .66 else FIRE[1] if heat > .5 else
                         (120, 40, 24) if heat > .35 else (60, 26, 20))
                continue
            course, row = divmod(y - 32, 3)
            joint = row == 2 or (x + course * 3) % 6 == 5
            s.set_at((x, y), BRICK[0] if joint else ramp(BRICK, 3.2 - (x - 2) / 28 * 1.2 + (row == 0) * .6))
    for x in range(2, 30):
        s.set_at((x, 32), BRICK[5])
        s.set_at((x, 44), BRICK[0])
    # Bellows on the left, tongs hung on the right.
    for y in range(34, 42):
        for x in range(0, 6):
            if abs(x - 2.5) <= (y - 33) / 2.5:
                s.set_at((x, y), (92, 56, 40) if (y - 34) % 2 else (122, 78, 54))
    for y in range(28, 34):
        s.set_at((1, y), WOOD[3])
    for y in range(28, 42):
        s.set_at((29, y), IRON[3] if y < 36 else IRON[2])
        s.set_at((30, y), IRON[1])
    # Glow on the hood's underside.
    for y in range(18, 26):
        for x in range(6, 26):
            if s.get_at((x, y))[3]:
                s.set_at((x, y), mix(s.get_at((x, y))[:3], FIRE[1], (.12 + frame * .04) * (y - 17) / 8))
    soft_outline(s)
    return s


def stairs_up():
    """Stairs up to the inn's upper floor, climbing along the back wall into the dark of the
    stairwell, with a rail on the open side."""
    s = surface(32, 48)
    for step in range(9):
        y0 = 44 - step * 5
        x0 = 2 + step
        for y in range(y0 - 5, y0):
            for x in range(x0, 30):
                tread = y < y0 - 3
                tone = (4.2 if y == y0 - 5 else 3.6) if tread else 2.0
                s.set_at((x, y), ramp(WOOD, tone - (x > 24) * .7 - step * .12))
    for y in range(0, 6):
        for x in range(10, 30):
            s.set_at((x, y), mix(INK, BEAM[1], y / 8))
    for i in range(46):
        x, y = 30, 46 - i
        if y >= 0:
            s.set_at((x, y), WOOD[4])
            s.set_at((x + 1, y), WOOD[1])
        if i % 8 == 4 and y > 3:
            for k in range(1, 5):
                put(s, 28 + (k % 2), y - k, WOOD[2])
    soft_outline(s)
    return s


def bed(quilt):
    """A bed head to the wall: a carved headboard, a white pillow, a quilt with its fold,
    and a footboard."""
    s = surface(16, 32)
    pal = QUILTS[quilt]
    for y in range(0, 7):
        for x in range(1, 15):
            s.set_at((x, y), ramp(WOOD, 3.8 - (y > 4) * 1.6 - (x > 12) * .6 + (y == 0) * .6))
    for x in (1, 14):
        for y in range(0, 31):
            s.set_at((x, y), WOOD[3] if x == 1 else WOOD[1])
    for y in range(7, 12):
        for x in range(3, 13):
            if not (y in (7, 11) and x in (3, 12)):
                s.set_at((x, y), LINEN[3] if y < 9 and x < 10 else LINEN[2] if y < 11 else LINEN[1])
    for y in range(12, 28):
        for x in range(2, 14):
            tone = 2.6 - (x - 2) / 12 * .9 + (y == 12) * 1.2 + (y == 13) * .5
            if (x + y * 2) % 7 == 0 and y > 14:
                tone -= .6                                     # stitching
            s.set_at((x, y), ramp(pal, tone))
    for x in range(2, 14):
        s.set_at((x, 12), LINEN[3])
    for y in range(28, 31):
        for x in range(1, 15):
            s.set_at((x, y), ramp(WOOD, 3.4 - (y - 28) * .8 - (x > 12) * .5))
    soft_outline(s)
    return s


def partition(n):
    """A low plank partition n tiles long, with a capping rail."""
    w = n * TILE
    s = surface(w, 24)
    _box(s, 0, 2, w, 3, 18, WOOD, WOOD, seed=90 + n)
    for x in range(0, w):
        for y in range(6, 20):
            if x % 5 == 4:
                s.set_at((x, y), WOOD[1])
    soft_outline(s)
    return s


def anvil():
    s = surface(16, 16)
    ground_shadow(s, 9.5, 14, 6, 1.4)
    for y in range(9, 15):
        for x in range(5, 11):
            s.set_at((x, y), ramp(BARK, 3.2 - (x - 5) * .4))
    for y in range(3, 9):
        for x in range(1, 15):
            if y < 6 or 5 <= x <= 10:
                if y == 3 and x < 3:
                    continue
                tone = 3.6 - (y > 5) * 1.4 - (x > 11) * .6 + (y == 3) * .8
                s.set_at((x, y), ramp(STEEL, tone - 1.0))
    soft_outline(s)
    return s


def grindstone():
    s = surface(16, 16)
    ground_shadow(s, 9.5, 14, 6, 1.4)
    for y in range(9, 15):
        for x in (3, 12):
            s.set_at((x, y), WOOD[3] if x == 3 else WOOD[1])
    for x in range(2, 14):
        s.set_at((x, 10), WOOD[3])
        s.set_at((x, 14), WOOD[2])
    for y in range(1, 13):
        for x in range(4, 12):
            dy = (y + .5 - 7) / 6
            if abs(dy) <= 1 and abs(x + .5 - 8) <= 3.5 * sqrt(1 - dy * dy) + .5:
                s.set_at((x, y), ramp(FLAG, 3.6 - dy * 1.3 - (x > 9) * .8 - ((y + 0) % 3 == 0) * .4))
    for x, y in ((13, 6), (14, 6), (14, 5)):
        s.set_at((x, y), WOOD[3])
    soft_outline(s)
    return s


def _blade(s, x, top, length, hilt):
    for y in range(top, top + length):
        s.set_at((x, y), STEEL[4] if y < top + 2 else STEEL[3])
        s.set_at((x + 1, y), STEEL[2])
    for dx in (-1, 0, 1, 2):
        s.set_at((x + dx, top + length), GOLD[2] if hilt else STEEL[2])
    for y in range(top + length + 1, top + length + 4):
        s.set_at((x, y), WOOD[2])
        s.set_at((x + 1, y), WOOD[1])
    s.set_at((x, top + length + 4), GOLD[3] if hilt else STEEL[3])


def rack_swords():
    """A weapon rack against the wall: two uprights, a bar with sword hilts hung from it and
    their blades standing point down in the slotted foot."""
    s = surface(32, 32)
    ground_shadow(s, 18, 29.5, 13, 1.6)
    for x in (2, 28):
        for y in range(4, 30):
            s.set_at((x, y), WOOD[4] if x == 2 else WOOD[2])
            s.set_at((x + 1, y), WOOD[2] if x == 2 else WOOD[1])
    for x in range(2, 30):
        for y, c in ((6, WOOD[4]), (7, WOOD[2]), (24, WOOD[4]), (25, WOOD[3]), (26, WOOD[3]), (27, WOOD[1])):
            s.set_at((x, y), c)
    for i, x in enumerate((7, 12, 17, 22)):
        # Point down: hilt at the top bar, blade into the foot.
        s.set_at((x, 4), GOLD[3] if i % 2 else STEEL[3])
        for y in range(5, 8):
            s.set_at((x, y), WOOD[2])
            s.set_at((x + 1, y), WOOD[1])
        for dx in (-1, 0, 1, 2):
            s.set_at((x + dx, 8), GOLD[2] if i % 2 else STEEL[2])
        for y in range(9, 24):
            s.set_at((x, y), STEEL[4] if y < 11 else STEEL[3])
            s.set_at((x + 1, y), STEEL[2])
    soft_outline(s)
    return s


def rack_spears():
    """A tall rack of spears and a halberd, heads up."""
    s = surface(16, 40)
    ground_shadow(s, 10, 38, 6, 1.4)
    for y in range(20, 38):
        for x in range(1, 15):
            if y in (24, 25, 35, 36) or x in (1, 14):
                s.set_at((x, y), WOOD[4] if y in (24, 35) or x == 1 else WOOD[2])
    for i, x in enumerate((4, 8, 11)):
        for y in range(6 + i % 2 * 2, 37):
            s.set_at((x, y), ramp(WOOD, 3.4 - (y > 30) * .5))
        top = 6 + i % 2 * 2
        for k in range(5):
            for dx in range(-max(0, 1 - abs(k - 2) // 1) , 2):
                put(s, x + dx, top - 5 + k, STEEL[4] if dx <= 0 else STEEL[2])
        if i == 1:
            for y in range(top + 1, top + 5):
                put(s, x + 1, y, STEEL[3])
                put(s, x + 2, y, STEEL[2] if y < top + 4 else STEEL[1])
    soft_outline(s)
    return s


def weapon_barrel():
    """A barrel stuffed with swords and an axe, hilts up."""
    base = T.barrel()
    s = surface(16, 24)
    s.blit(base, (0, 8))
    for x, top, hilt in ((5, 2, True), (8, 0, False), (11, 3, True)):
        for y in range(top, top + 4):
            s.set_at((x, y), WOOD[2])
        s.set_at((x - 1, top + 4), GOLD[2] if hilt else STEEL[2])
        s.set_at((x, top + 4), GOLD[2] if hilt else STEEL[2])
        s.set_at((x + 1, top + 4), GOLD[1] if hilt else STEEL[1])
        for y in range(top + 5, 12):
            s.set_at((x, y), STEEL[3])
    for y in range(1, 4):
        for x in range(9, 12):
            s.set_at((x, y), STEEL[3] if x < 11 else STEEL[1])
    soft_outline(s)
    return s


def _stand(s):
    """A mannequin's cross-footed stand and post."""
    for x in range(3, 13):
        s.set_at((x, 30), WOOD[3] if x < 9 else WOOD[2])
        s.set_at((x, 31), WOOD[1])
    for y in range(18, 30):
        s.set_at((7, y), WOOD[3])
        s.set_at((8, y), WOOD[1])


def armor_mail():
    """A hauberk of mail on a stand, under an open helm."""
    s = surface(16, 32)
    ground_shadow(s, 9.5, 30.5, 5, 1.2)
    _stand(s)
    for y in range(7, 22):
        half = 5 if y < 10 else 4 if y < 20 else 5
        for x in range(8 - half - (y < 10) * 1, 8 + half + (y < 10) * 1):
            ring = (x + y) % 2
            tone = 3.0 - (x - 2) / 12 * 1.4 + ring * .5 - (y > 18) * .4
            s.set_at((x, y), ramp(STEEL, tone))
    for x in range(4, 12):
        s.set_at((x, 15), (100, 66, 40))                     # a belt
    s.set_at((7, 15), GOLD[2])
    for y in range(1, 7):
        for x in range(5, 11):
            if (x + .5 - 8) ** 2 / 9 + (y + .5 - 4.5) ** 2 / 12 <= 1:
                s.set_at((x, y), ramp(STEEL, 3.6 - (x - 5) * .4 + (y < 3) * .6))
    for x in range(6, 10):
        s.set_at((x, 5), INK)
    soft_outline(s)
    return s


def armor_plate():
    """A suit of plate on a stand: a domed breastplate catching the light, pauldrons, and a
    visored helm with a plume."""
    s = surface(16, 32)
    ground_shadow(s, 9.5, 30.5, 5, 1.2)
    _stand(s)
    for y in range(9, 23):
        half = 4 if y < 20 else 3
        for x in range(8 - half, 8 + half):
            dx = (x + .5 - 8) / half
            tone = 3.2 - dx * 1.6 + (abs(dx + .4) < .2) * 1.0 - (y > 16) * .5 - (y == 16) * 1.0
            s.set_at((x, y), ramp(STEEL, tone))
    for cx in (3, 12):
        for y in range(8, 12):
            for x in range(cx - 2, cx + 2):
                if abs(x + .5 - cx) <= 2 - (y == 11):
                    s.set_at((x, y), ramp(STEEL, 3.4 - (cx > 8) * 1.2 + (y == 8) * .6))
    for y in range(2, 9):
        for x in range(5, 11):
            if (x + .5 - 8) ** 2 / 9 + (y + .5 - 5.5) ** 2 / 12 <= 1:
                s.set_at((x, y), ramp(STEEL, 3.4 - (x - 5) * .4 + (y < 4) * .6))
    for x in range(6, 10):
        s.set_at((x, 5), INK if x % 2 else STEEL[1])
    for y, x in ((0, 9), (1, 8), (1, 9), (0, 10)):
        s.set_at((x, y), (170, 40, 44))
    soft_outline(s)
    return s


def shield_rack():
    """Shields leaning on a low rail: a round wooden one with a boss, a kite shield with a
    gold chevron, and a small steel buckler."""
    s = surface(32, 24)
    ground_shadow(s, 18, 22, 13, 1.5)
    for x in range(1, 31):
        s.set_at((x, 9), WOOD[4])
        s.set_at((x, 10), WOOD[2])
    for x in (2, 29):
        for y in range(9, 22):
            s.set_at((x, y), WOOD[3] if x == 2 else WOOD[1])
    for y in range(6, 22):                                   # the round shield
        for x in range(3, 14):
            d = sqrt((x + .5 - 8.5) ** 2 + (y + .5 - 14) ** 2)
            if d <= 5.6:
                s.set_at((x, y), IRON[2] if d > 4.8 else STEEL[4] if d < 1.2 else ramp(WOOD, 3.4 - (x - 3) * .2 - (x % 3 == 0) * .6))
    for y in range(4, 22):                                   # the kite shield
        half = 5 if y < 12 else max(0, 5 - (y - 12) // 2)
        for x in range(19 - half, 19 + half):
            edge = x in (19 - half, 19 + half - 1) or y == 4
            chevron = abs(abs(x + .5 - 19) - (y - 6) * .7) < 1 and y < 14
            s.set_at((x, y), STEEL[3] if edge else GOLD[2] if chevron else (60, 74, 130) if x < 19 else (44, 54, 100))
    for y in range(13, 22):                                  # the buckler
        for x in range(23, 31):
            d = sqrt((x + .5 - 27) ** 2 + (y + .5 - 17.5) ** 2)
            if d <= 4:
                s.set_at((x, y), ramp(STEEL, 3.4 - (x - 23) * .3 + (d < 1.5) * 1.0))
    soft_outline(s)
    return s


def _shelf(s, w, h, shelves):
    """An open shelving unit against the wall, its back in shade."""
    for y in range(h):
        for x in range(w):
            frame = x in (0, 1, w - 2, w - 1) or y in (0, 1)
            if frame:
                s.set_at((x, y), WOOD[3] if x in (0, 1) or y in (0, 1) else WOOD[1])
            else:
                s.set_at((x, y), mix(WOOD[1], INK, .3))
    for sy in shelves:
        for x in range(1, w - 1):
            s.set_at((x, sy), WOOD[4])
            s.set_at((x, sy + 1), WOOD[2])
            if sy + 2 < h:
                s.set_at((x, sy + 2), mix(WOOD[1], INK, .4))


def helm_shelf():
    """A shelf of helms (a nasal helm, a kettle hat, a great helm) with gauntlets below."""
    s = surface(32, 40)
    _shelf(s, 32, 40, (16, 30, 38))
    for cx, kind in ((7, 0), (16, 1), (25, 2)):
        for y in range(7, 16):
            for x in range(cx - 4, cx + 4):
                dx, dy = (x + .5 - cx) / 4, (y + .5 - 12) / 4.5
                inside = dx * dx + dy * dy <= 1 if kind != 2 else abs(dx) <= .9 and y >= 8
                if kind == 1 and y >= 13:
                    inside = abs(dx) <= 1.2
                if inside:
                    s.set_at((x, y), ramp(STEEL, 3.4 - dx * 1.2 + (dy < -.5) * .6))
        if kind == 0:
            for y in range(12, 16):
                s.set_at((cx, y), STEEL[1])
        if kind == 2:
            for x in range(cx - 3, cx + 3):
                s.set_at((x, 11), INK)
    for cx in (9, 20):
        for y in range(23, 30):
            for x in range(cx - 3, cx + 3):
                s.set_at((x, y), ramp(STEEL, 3.0 - (x - cx + 3) * .3 - (y > 27) * .6))
    soft_outline(s)
    return s


def shelf_jars():
    """General goods: crocks and jars, a cheese wheel, loaves and a coil of rope."""
    s = surface(32, 40)
    _shelf(s, 32, 40, (14, 27, 38))
    rng = random.Random(55)
    for shelf in (14, 27):
        x = 3
        while x < 27:
            kind = rng.choice(("jar", "crock", "loaf", "cheese"))
            if kind == "jar":
                for y in range(shelf - 7, shelf):
                    for xx in range(x, x + 4):
                        s.set_at((xx, y), (120, 70, 40) if y == shelf - 7 else ramp(((60, 80, 70), (90, 120, 100), (150, 180, 160)), 1.6 - (xx - x) * .4 + (y < shelf - 4) * .6))
                x += 5
            elif kind == "crock":
                for y in range(shelf - 6, shelf):
                    for xx in range(x, x + 5):
                        if abs(xx + .5 - x - 2.5) <= 2.5 - (y == shelf - 6):
                            s.set_at((xx, y), ramp(CLAY_POT, 2.6 - (xx - x) * .4 + (y == shelf - 5) * .8))
                x += 6
            elif kind == "loaf":
                for y in range(shelf - 3, shelf):
                    for xx in range(x, x + 5):
                        s.set_at((xx, y), (206, 150, 80) if y == shelf - 3 else (168, 112, 56))
                x += 6
            else:
                for y in range(shelf - 4, shelf):
                    for xx in range(x, x + 6):
                        s.set_at((xx, y), GOLD[3] if y == shelf - 4 else GOLD[2] if xx < x + 4 else GOLD[1])
                x += 7
    for y in range(30, 37):
        for x in range(18, 27):
            if 2 <= sqrt((x + .5 - 22.5) ** 2 + ((y + .5 - 33.5) * 1.3) ** 2) <= 4.2:
                s.set_at((x, y), ramp(STRAW, 3.0 - (x - 18) * .2 - ((x + y) % 2) * .5))
    soft_outline(s)
    return s


CLAY_POT = ((90, 46, 30), (128, 70, 44), (166, 100, 62), (196, 132, 86))


def shelf_potions():
    """Potions and tonics in stoppered flasks of red, blue and green, with boxes below."""
    s = surface(32, 40)
    _shelf(s, 32, 40, (14, 27, 38))
    rng = random.Random(57)
    for shelf in (14, 27):
        x = 3
        while x < 28:
            color = rng.choice(POTIONS)
            tall = rng.random() < .5
            h = 8 if tall else 6
            for y in range(shelf - h, shelf):
                neck = y < shelf - h + 3
                for xx in range(x + neck, x + 4 - neck):
                    if y == shelf - h:
                        s.set_at((xx, y), (140, 100, 60))
                    else:
                        lit = xx == x + 1 and not neck
                        s.set_at((xx, y), mix(color, (255, 255, 255), .5) if lit else color if xx < x + 3 else mix(color, INK, .35))
            x += 5
    for x0 in (4, 17):
        for y in range(31, 38):
            for x in range(x0, x0 + 11):
                s.set_at((x, y), ramp(WOOD, 3.8 - (y > 32) * 1.2 - (x > x0 + 8) * .6))
    soft_outline(s)
    return s


def chest():
    s = surface(16, 16)
    ground_shadow(s, 9.5, 14.2, 6.5, 1.3)
    _box(s, 1, 3, 14, 4, 8, WOOD, WOOD, seed=95)
    for y in range(3, 15):
        for x in (3, 12):
            s.set_at((x, y), IRON[2] if y < 7 else IRON[1])
    for x in range(1, 15):
        s.set_at((x, 7), IRON[2])
    for x, y, c in ((7, 8, GOLD[3]), (8, 8, GOLD[2]), (7, 9, GOLD[1]), (8, 9, GOLD[1])):
        s.set_at((x, y), c)
    soft_outline(s)
    return s


# --- the mill's machinery ------------------------------------------------------------------------
# The mill's gearing: the great spur wheel turns on the main shaft at MILL_GEAR_Y px down
# from the top of the room, and its cogs drive a stone nut on each pair of millstones,
# up on the stones' spindles at the same height.
MILL_GEAR_Y = 70
WHEEL_RX, WHEEL_RY = 62, 15
NUT_X = 44            # the stone nut's centre, from the left of the (unflipped) millstones sprite


def millstones(flip=False):
    """A pair of millstones in their wooden tun on a low platform: the hopper above on its
    horse frame feeding grain to the eye of the runner stone, a spout of meal into a sack at
    the front, and the stone spindle rising from the tun to the stone nut, a small cog wheel
    up at the height of the great spur wheel. Flipped, the spindle is on the left, so the
    right-hand pair's nut meets the spur wheel too."""
    s = surface(48, 72)
    oy = 32                                                     # where the old 40 px drawing starts
    ground_shadow(s, 27, oy + 37.5, 22, 2.2)
    _box(s, 2, oy + 26, 44, 4, 6, WOOD, WOOD, seed=101)
    for y in range(oy + 14, oy + 30):
        for x in range(6, 42):
            dx = (x + .5 - 24) / 18
            arc = 5 * sqrt(max(0.0, 1 - dx * dx))
            if y + .5 < oy + 20 - arc or y + .5 > oy + 26 + arc:
                continue
            if y + .5 < oy + 20 + arc:
                rr = sqrt(dx * dx + ((y + .5 - oy - 20) / 5) ** 2)
                if rr > .86:
                    s.set_at((x, y), ramp(WOOD, 4.4 - dx * .8))       # the tun's rim
                else:
                    s.set_at((x, y), ramp(FLAG, 3.8 - dx * .8 - (int(rr * 6) % 2) * .5))  # the runner stone
            else:
                board = int((asin(max(-1.0, min(1.0, dx))) + pi / 2) / .3)
                s.set_at((x, y), ramp(WOOD, 3.0 - dx * 1.4 - (board % 2) * .4))
    for x in range(22, 27):
        s.set_at((x, oy + 20), INK)                                 # the eye
    for y in range(oy + 28, oy + 33):
        s.set_at((24, y), WOOD[2])
        s.set_at((25, y), WOOD[1])
    for y in range(oy + 31, oy + 38):
        for x in range(20, 30):
            if abs(x + .5 - 25) <= 3 + (y - oy - 31) * .4:
                s.set_at((x, y), ramp(FLOUR, 2.6 - (x - 20) * .25))
    # The stone spindle, up from the tun's side to the stone nut.
    for y in range(4, oy + 18):
        s.set_at((NUT_X, y), WOOD[3])
        s.set_at((NUT_X + 1, y), WOOD[1])
        if y % 12 == 0:
            s.set_at((NUT_X, y), IRON[3])
            s.set_at((NUT_X + 1, y), IRON[1])
    # The horse frame, the hopper on it and the shoe.
    for x in (12, 35):
        for y in range(oy + 2, oy + 22):
            s.set_at((x, y), WOOD[3] if x == 12 else WOOD[2])
            s.set_at((x + 1, y), WOOD[1])
    for y in range(oy + 4, oy + 14):
        half = 9 - (y - oy - 4) * .7
        for x in range(round(24 - half), round(24 + half)):
            tone = 3.6 - (x - 24 + half) / (2 * half) * 1.4 + (y == oy + 4) * .8
            s.set_at((x, y), ramp(WOOD, tone))
    for x in range(17, 31):
        s.set_at((x, oy + 5), ramp(STRAW, 3.4 - (x % 3 == 0)))      # grain in the hopper
    for y in range(oy + 14, oy + 18):
        s.set_at((25, y), WOOD[2])
    # The stone nut: a small cog wheel on the spindle's head, seen from above.
    for y in range(0, 9):
        for x in range(NUT_X - 5, NUT_X + 7):
            dx, dy = (x + .5 - NUT_X - 1) / 5.5, (y + .5 - 3.5) / 2.6
            r = dx * dx + dy * dy
            if r <= 1:
                s.set_at((x, y), ramp(WOOD, 3.8 - dx * 1.0 - (dy > .3) * 1.2))
            elif r <= 1.5 and (x + y) % 2 == 0:
                s.set_at((x, y), ramp(WOOD, 2.8 - dx))               # its cogs
    soft_outline(s)
    return pygame.transform.flip(s, True, False) if flip else s


def spurwheel(frame):
    """The mill's main upright shaft, from its bearing on the floor up out of sight, and the
    great spur wheel turning on it overhead: four arms crossing at the shaft, a deep rim, and
    cogs standing on the rim's top. The rim's far side passes behind the shaft and its near
    side in front. Frames 0-3 turn it a quarter cog each."""
    W, H = 144, 128
    s = surface(W, H)
    cx = W // 2
    wy = MILL_GEAR_Y - (9 * TILE - H)                          # the room's gear height, in this sprite
    rx, ry = WHEEL_RX, WHEEL_RY
    ground_shadow(s, cx + 5, H - 3, 12, 2)
    _box(s, cx - 9, H - 12, 18, 4, 7, WOOD, WOOD, seed=110)

    def wheel(half):
        """Draw the wheel's far (half < 0) or near (half > 0) side."""
        for y in range(wy - ry - 4, wy + ry + 8):
            for x in range(W):
                dx, dy = (x + .5 - cx) / rx, (y + .5 - wy) / ry
                if (dy < 0) != (half < 0):
                    continue
                r = sqrt(dx * dx + dy * dy)
                angle = (pi + atan2(dy, dx)) / (2 * pi)
                if r <= 1:
                    if r > .78:
                        cog = r > .86 and int((angle * 56 + frame / 4) % 1 * 2) == 0
                        tone = 4.3 - dx * .9 - (dy > 0) * .5 + (cog * .7) - (not cog and r > .86) * .5
                        s.set_at((x, y), ramp(WOOD, tone))                    # the rim's top and its cogs
                    elif r > .12 and any(abs((angle * 4) % 1 - k) < .03 for k in (0, 1)):
                        s.set_at((x, y), ramp(WOOD, 3.5 - dx * .8))          # an arm
                # The rim's outer face below its top, on the near side.
        if half > 0:
            for x in range(W):
                dx = (x + .5 - cx) / rx
                if abs(dx) >= 1:
                    continue
                front = wy + ry * sqrt(1 - dx * dx)
                for k in range(1, 6):
                    put(s, x, int(front + k), ramp(WOOD, 2.6 - dx * 1.1 - k * .15) if k != 3 else IRON[2 if dx < 0 else 1])

    wheel(-1)
    # The shaft, eight-sided, lit on its left faces, iron-banded.
    for y in range(0, H - 9):
        for x in range(cx - 6, cx + 6):
            face = (x - (cx - 6)) // 3
            tone = (4.0, 3.2, 2.4, 1.6)[face]
            band = y % 32 in (0, 1)
            s.set_at((x, y), IRON[2 + (face < 2)] if band else ramp(WOOD, tone + (noise(x, y // 4, 111) - .5) * .4))
    wheel(1)
    soft_outline(s)
    return s


def ladder():
    """A ladder up through the hatch in the ceiling."""
    s = surface(16, 56)
    for y in range(0, 6):
        for x in range(0, 16):
            s.set_at((x, y), mix(INK, BEAM[1], y / 8))
    for y in range(2, 55):
        for x, c in ((3, WOOD[4]), (4, WOOD[2]), (11, WOOD[3]), (12, WOOD[1])):
            s.set_at((x, y), c)
        if y % 6 == 4:
            for x in range(5, 11):
                s.set_at((x, y), WOOD[4])
                s.set_at((x, y + 1), WOOD[1])
    soft_outline(s)
    return s


def wall_lantern(frame):
    """A lantern hung from an iron bracket on the wall, its four-pane cage lit by a flame
    behind the middle bar. The frames are the town lamps' and the trail lanterns' loop (rest,
    lean left, peak, lean right, dip, ember), and its warm light spills well past the cage
    onto the wall around it, brighter as the flame peaks. The cage's middle is 16 px across
    and 14 down."""
    lean, height, bright = T.LAMP_FLAMES[frame]
    s = surface(32, 36)
    fx, base = 16.0, 18
    # The bracket: a plate on the wall and an arm out over the lantern.
    for y in range(3, 9):
        s.set_at((22, y), IRON[2] if y > 3 else IRON[3])
        s.set_at((23, y), IRON[1])
    for x in range(15, 23):
        s.set_at((x, 4), IRON[3] if x < 18 else IRON[2])
    s.set_at((16, 5), IRON[2])
    # The cap.
    for y, x0, x1 in ((6, 15, 17), (7, 13, 19), (8, 12, 20)):
        for x in range(x0, x1):
            s.set_at((x, y), IRON[3] if x < 16 else IRON[1])
    # The cage and its panes.
    for y in range(9, 20):
        for x in range(12, 20):
            if x in (12, 19) or y in (9, 19):
                s.set_at((x, y), IRON[2] if x == 12 or y == 9 else IRON[0])
                continue
            d = sqrt((x + .5 - fx) ** 2 + ((y + .5 - (base - height / 2)) * .8) ** 2)
            s.set_at((x, y), ramp(GLOW, (3.4 - d * .6) * bright))
    for y in range(base - round(height) + 1, base + 1):
        rise = (base - y) / height
        half = (1 - rise) * 1.9 + .45
        cx = fx + lean * rise
        for x in range(13, 19):
            off = abs(x + .5 - cx)
            if off <= half:
                core = off <= half * .45 and rise < .7
                s.set_at((x, y), FIRE[3 if core and bright > 1 else 2 if core else 1 if off <= half * .8 else 0])
    for y in range(10, 19):
        s.set_at((16, y), mix(IRON[1], GLOW[2], .35 * bright))
    for x in range(13, 19):
        s.set_at((x, 20), IRON[1] if x < 17 else IRON[0])
    s.set_at((15, 21), IRON[2])
    s.set_at((16, 21), IRON[0])
    soft_outline(s)
    # Warm light on the wall round it, on the clear pixels only.
    for y in range(36):
        for x in range(32):
            if s.get_at((x, y))[3]:
                continue
            d = sqrt((x + .5 - fx) ** 2 + ((y + .5 - 14) * 1.1) ** 2)
            reach = 14 * bright
            if d < reach:
                s.set_at((x, y), (255, 184, 92, round(84 * bright * (1 - d / reach) ** 1.3)))
    return s


def hoist():
    """The sack hoist's chain hanging down through the trap, with a full sack on its hook."""
    s = surface(16, 48)
    for y in range(0, 32):
        s.set_at((8, y), IRON[3] if y % 3 else IRON[1])
    for x, y in ((7, 32), (7, 33), (8, 34), (9, 33)):
        s.set_at((x, y), IRON[2])
    for y in range(34, 46):
        for x in range(3, 13):
            if abs(x + .5 - 8) <= 3 + min(y - 34, 6) * .35:
                s.set_at((x, y), ramp(FLOUR, 2.8 - (x - 3) * .25 - (y > 43) * .6))
    for x in range(6, 11):
        s.set_at((x, 35), TWINE[1])
    soft_outline(s)
    return s


def flour_sacks():
    """Full flour sacks of pale sacking: two lying side by side and one stood up on them,
    each with a seam down its middle and a tied neck, dusted with flour at their feet."""
    s = surface(32, 24)
    ground_shadow(s, 18, 22, 14, 1.6)
    for x0, y0, w, h, upright in ((1, 12, 15, 10, False), (16, 12, 15, 10, False), (9, 1, 13, 14, True)):
        for y in range(y0, y0 + h):
            for x in range(x0, x0 + w):
                u, v = (x + .5 - x0) / w * 2 - 1, (y + .5 - y0) / h * 2 - 1
                if u * u * (1.6 if not upright else 1.0) + v * v * (1.0 if not upright else 1.6) > 1.25 or abs(u) > 1 or abs(v) > 1:
                    continue
                tone = 2.4 - u * 1.1 - v * .8 + ((x + y) % 2) * .25
                if abs(u) < .07:
                    tone -= .9                                  # the seam
                s.set_at((x, y), ramp(SACKING, tone))
        if upright:
            cx = x0 + w // 2
            for x, y, tone in ((cx - 1, y0 - 1, 3), (cx, y0 - 1, 2), (cx - 1, y0, 1), (cx, y0, 1)):
                put(s, x, y, SACKING[tone] if tone > 1 else TWINE[1])
    for x, y in ((2, 22), (29, 22), (14, 23), (20, 23)):
        s.set_at((x, y), FLOUR[3])
    soft_outline(s)
    return s


SACKING = ((104, 92, 72), (146, 134, 110), (184, 174, 150), (214, 206, 184), (234, 230, 214))


def wheelbarrow():
    """A wooden barrow with a spoked wheel, half full of grain."""
    s = surface(32, 16)
    ground_shadow(s, 17, 14.5, 13, 1.4)
    for y in range(4, 12):
        top = 4 + (y - 4)
        for x in range(8 + (y - 4) // 2, 28 - (y - 4) // 2):
            tone = 3.4 - (x - 8) / 20 * .8 - (y > 6) * 1.0
            s.set_at((x, y), ramp(WOOD, tone))
    for x in range(10, 26):
        s.set_at((x, 4), ramp(STRAW, 3.6 - (x % 3 == 0)))
    for x in range(1, 10):
        s.set_at((x, 8 + (x < 4)), WOOD[3])
    for y in range(8, 15):
        for x in range(26, 32):
            d = sqrt((x + .5 - 29) ** 2 + (y + .5 - 11.5) ** 2)
            if d <= 3.2:
                s.set_at((x, y), WOOD[1] if d > 2.4 else WOOD[3] if d < 1 else WOOD[2])
    for x in (11, 23):
        for y in range(11, 15):
            s.set_at((x, y), WOOD[2])
    soft_outline(s)
    return s


def furniture():
    out = {"stool": stool(), "table": table(), "bar-shelf": bar_shelf(), "stairs-up": stairs_up(),
           "anvil": anvil(), "grindstone": grindstone(), "rack-swords": rack_swords(), "rack-spears": rack_spears(),
           "weapon-barrel": weapon_barrel(), "armor-mail": armor_mail(), "armor-plate": armor_plate(),
           "shield-rack": shield_rack(), "helm-shelf": helm_shelf(), "shelf-jars": shelf_jars(),
           "shelf-potions": shelf_potions(), "chest": chest(), "millstones": millstones(), "ladder": ladder(),
           "millstones-r": millstones(flip=True), "hoist": hoist(), "flour-sacks": flour_sacks(),
           "wheelbarrow": wheelbarrow(),
           # From the town, so the same barrel stands inside and out.
           "barrel": T.barrel(), "crate": T.crate(), "crates": T.crates(), "sacks": T.sacks(),
           "gourds": T.gourds(), "planter-1": T.planter(1)}
    for n in (4, 5):
        out[f"counter-{n}"] = counter(n)
    out["partition-3"] = partition(3)
    for frame in range(3):
        out[f"hearth-{frame}"] = hearth(frame)
        out[f"forge-{frame}"] = forge(frame)
    for frame in range(4):
        out[f"spurwheel-{frame}"] = spurwheel(frame)
    for frame in range(len(T.LAMP_FLAMES)):
        out[f"lantern-{frame}"] = wall_lantern(frame)
    # A bed per quilt, so a row of beds isn't all one colour.
    for i in range(3):
        out[f"bed-{i}"] = bed(i)
    return out


def main():
    pygame.display.init()
    pygame.display.set_mode((1, 1), pygame.HIDDEN)
    OUT.mkdir(parents=True, exist_ok=True)
    for room in R.ROOMS.values():
        pygame.image.save(room_ground(room), str(OUT / f"{room.name}-ground.png"))
    atlas, spots = T.pack(furniture())
    pygame.image.save(atlas, str(OUT / "furniture.png"))
    (OUT / "furniture.json").write_text(json.dumps(spots, indent=1, sort_keys=True), encoding="utf-8")


if __name__ == "__main__":
    main()
