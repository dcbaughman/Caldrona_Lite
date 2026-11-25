"""Build the close-up tablet shown when Retri inspects the Selvar seal.

Reads `assets/mine-polish/selvar-inscription-source.svg`, rasterises each of its
stacked columns into hard-edged pixel grooves, and sets the columns side by side,
left to right in source order, on a worn purple slate tablet. Fresh Veskar cuts run
across the whole face and glint where they cross the old grooves.

    selvar-closeup.png      the tablet at native pixel density (the game zooms it by SCALE)

Run from the project root:  python prepare_selvar_closeup.py
"""
import math
import random
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pygame

ART = Path(__file__).resolve().parent / "assets" / "mine-polish"
SOURCE = ART / "selvar-inscription-source.svg"
TARGET = ART / "selvar-closeup.png"

GLYPH_HEIGHT = 92      # native pixels for the tallest column
COLUMN_GAP = 9
MARGIN_X, MARGIN_Y = 14, 9
SUPERSAMPLE = 6
COVERAGE = .26         # share of a native pixel a stroke must cover to carve it

RIM = (18, 12, 20)
EDGE = (40, 30, 54)
SLATE = ((58, 46, 78), (86, 70, 108), (110, 92, 132), (140, 122, 158))
GROOVE = (18, 10, 26)
GROOVE_SIDE = (40, 28, 54)
CRACK = (20, 14, 28)
CUT = (204, 194, 214)
CUT_SHADOW = (70, 58, 88)
GLINT = (150, 196, 230)
SVG = "{http://www.w3.org/2000/svg}"


def _translate(element):
    match = re.search(r"translate\(([-\d.]+)[ ,]+([-\d.]+)\)", element.get("transform", ""))
    return (float(match[1]), float(match[2])) if match else (0.0, 0.0)


def _tokens(d):
    return re.findall(r"[MLHVQCZmlhvqcz]|-?\d*\.?\d+", d)


def _polylines(d, steps=14):
    """Flatten the path commands this script uses (M L H V Q C Z, plus relative h)."""
    tokens, i = _tokens(d), 0
    lines, current, start, x, y, command = [], [], (0.0, 0.0), 0.0, 0.0, None
    number = lambda: float(tokens[i])
    while i < len(tokens):
        if re.fullmatch(r"[A-Za-z]", tokens[i]):
            command = tokens[i]
            i += 1
            if command in "Zz":
                current.append(start)
                continue
        if command == "M":
            if len(current) > 1:
                lines.append(current)
            x, y = number(), float(tokens[i + 1]); i += 2
            current, start = [(x, y)], (x, y)
            command = "L"
        elif command == "L":
            x, y = number(), float(tokens[i + 1]); i += 2
            current.append((x, y))
        elif command in "Hh":
            x = number() + (x if command == "h" else 0); i += 1
            current.append((x, y))
        elif command == "V":
            y = number(); i += 1
            current.append((x, y))
        elif command == "Q":
            cx, cy, ex, ey = (float(t) for t in tokens[i:i + 4]); i += 4
            for step in range(1, steps + 1):
                t = step / steps
                current.append(((1-t)**2*x + 2*(1-t)*t*cx + t*t*ex, (1-t)**2*y + 2*(1-t)*t*cy + t*t*ey))
            x, y = ex, ey
        elif command == "C":
            c1x, c1y, c2x, c2y, ex, ey = (float(t) for t in tokens[i:i + 6]); i += 6
            for step in range(1, steps + 1):
                t = step / steps
                a, b, c, e = (1-t)**3, 3*(1-t)**2*t, 3*(1-t)*t*t, t**3
                current.append((a*x + b*c1x + c*c2x + e*ex, a*y + b*c1y + c*c2y + e*ey))
            x, y = ex, ey
        else:
            raise ValueError(f"unsupported path command {command!r}")
    if current:
        lines.append(current)
    return lines


def _columns():
    """Each top-level group under the outer translate is one column of strokes."""
    root = ET.parse(SOURCE).getroot()
    outer = root.find(f"{SVG}g")
    ox, _ = _translate(outer)
    columns = []
    for group in outer.findall(f"{SVG}g"):
        _, gy = _translate(group)
        strokes = []

        def walk(node, dx, dy):
            tx, ty = _translate(node)
            dx, dy = dx + tx, dy + ty
            for child in node:
                if child.tag == f"{SVG}path":
                    width = float(child.get("stroke-width", "3"))
                    for line in _polylines(child.get("d")):
                        strokes.append(([(px + dx, py + dy) for px, py in line], width))
                elif child.tag == f"{SVG}g":
                    walk(child, dx, dy)

        walk(group, ox, -gy)
        columns.append(strokes)
    return columns


def _carve(strokes, scale):
    """Rasterise one column's strokes to a set of native groove pixels."""
    points = [p for line, _ in strokes for p in line]
    pad = 4
    left, top = min(p[0] for p in points) - pad, min(p[1] for p in points) - pad
    width = math.ceil((max(p[0] for p in points) + pad - left) * scale)
    height = math.ceil((max(p[1] for p in points) + pad - top) * scale)
    k = scale * SUPERSAMPLE
    big = pygame.Surface((width * SUPERSAMPLE, height * SUPERSAMPLE))
    for line, stroke in strokes:
        pts = [((px - left) * k, (py - top) * k) for px, py in line]
        radius = max(1, stroke * k / 2)
        for a, b in zip(pts, pts[1:]):
            length = max(1, int(math.dist(a, b)))
            for step in range(length + 1):
                t = step / length
                pygame.draw.circle(big, (255, 255, 255),
                                   (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t), radius)
        if len(pts) == 1:
            pygame.draw.circle(big, (255, 255, 255), pts[0], radius)
    carved = set()
    for y in range(height):
        for x in range(width):
            lit = sum(big.get_at((x * SUPERSAMPLE + i, y * SUPERSAMPLE + j)).r > 0
                      for i in range(SUPERSAMPLE) for j in range(SUPERSAMPLE))
            if lit / SUPERSAMPLE ** 2 >= COVERAGE:
                carved.add((x, y))
    return carved, width, height


def _tablet_mask(width, height, rng):
    cells = set()
    for y in range(height):
        # Worn corners and a few bites out of the long edges.
        inset = max(0, 4 - y, 4 - (height - 1 - y))
        left = inset + (1 if rng.random() < .12 else 0)
        right = width - 1 - inset - (1 if rng.random() < .12 else 0)
        cells.update((x, y) for x in range(left, right + 1))
    return cells


def build():
    columns = _columns()
    tallest = max(max(p[1] for line, _ in c for p in line) - min(p[1] for line, _ in c for p in line)
                  for c in columns)
    scale = GLYPH_HEIGHT / (tallest + 8)
    carved = [_carve(strokes, scale) for strokes in columns]
    width = sum(w for _, w, _ in carved) + COLUMN_GAP * (len(carved) - 1) + MARGIN_X * 2
    height = max(h for _, _, h in carved) + MARGIN_Y * 2
    rng = random.Random(1070)
    surface = pygame.Surface((width, height), pygame.SRCALPHA)
    mask = _tablet_mask(width, height, rng)
    face = {(x, y) for x, y in mask
            if all((x + dx, y + dy) in mask for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))}
    inner = {(x, y) for x, y in face
             if all((x + dx, y + dy) in face for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))}
    for point in mask - face:
        surface.set_at(point, RIM)
    for point in face - inner:
        surface.set_at(point, EDGE)
    for x, y in inner:
        # Broad uneven wear: soft bands plus grit, never a smooth gradient.
        wave = math.sin(x * .09 + y * .05) + math.cos(y * .13 - x * .04)
        tone = 2 if wave > 1.55 else 0 if wave < -1.6 else 1
        roll = rng.random()
        if roll < .07:
            tone = max(0, tone - 1)
        elif roll > .95:
            tone = min(3, tone + 1)
        surface.set_at((x, y), SLATE[tone])
    grooves = set()
    x0 = MARGIN_X
    for cells, w, h in carved:
        y0 = MARGIN_Y
        grooves.update((x0 + x, y0 + y) for x, y in cells)
        x0 += w + COLUMN_GAP
    grooves &= inner
    for x, y in grooves:
        # Light falls from above: the upper wall of a groove is in shadow,
        # the lower lip catches light.
        surface.set_at((x, y), GROOVE if (x, y - 1) in grooves else GROOVE_SIDE)
        if (x, y + 1) in inner and (x, y + 1) not in grooves:
            surface.set_at((x, y + 1), SLATE[3])
    # A natural crack runs down through the stone, older than the carving.
    cx, cy = width * .63, 0
    while cy < height:
        for point in ((round(cx), round(cy)),):
            if point in mask:
                surface.set_at(point, CRACK)
        cy += 1
        cx += rng.choice((-1, 0, 0, 1)) * .8
    # Fresh Veskar cuts: long slashes across the whole face, slightly downhill.
    for (sx, sy), (ex, ey) in (((8, height * .34), (width - 8, height * .28)),
                               ((14, height * .66), (width - 12, height * .58))):
        steps = int(ex - sx)
        for step in range(steps + 1):
            x = round(sx + step)
            y = round(sy + (ey - sy) * step / steps)
            if (x, y) in inner:
                surface.set_at((x, y), GLINT if (x, y) in grooves else CUT)
                if (x, y + 1) in inner and (x, y + 1) not in grooves:
                    surface.set_at((x, y + 1), CUT_SHADOW)
    return surface


def main():
    pygame.image.save(build(), str(TARGET))


if __name__ == "__main__":
    main()
