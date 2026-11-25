"""Small, transparent pixel webs for the den gate and battle status."""
import tkinter as tk
from collections import defaultdict


SHADOW = "#655b80"
SILK = "#a89cbc"
LIGHT = "#d2c9df"


def _strand(pixels, start, end, color):
    """Rasterize on the native pixel grid before the canvas enlarges it."""
    x, y = start
    x1, y1 = end
    dx, dy = abs(x1 - x), -abs(y1 - y)
    sx, sy = (1 if x < x1 else -1), (1 if y < y1 else -1)
    error = dx + dy
    while True:
        pixels[x, y] = color
        if (x, y) == end:
            return
        doubled = 2 * error
        if doubled >= dy:
            error += dy
            x += sx
        if doubled <= dx:
            error += dx
            y += sy


def _photo(master, pixels, width, height, zoom, mirrored=False):
    sprite = tk.PhotoImage(master=master, width=width, height=height)
    for (x, y), color in pixels.items():
        sprite.put(color, (width - x - 1 if mirrored else x, y))
    return sprite.zoom(zoom)


def gate_web(master, zoom):
    # An off-center hub with loose ends and uneven spacing across the timber.
    hub = (10, 8)
    anchors = ((0, 6), (4, 2), (11, 0), (19, 1), (24, 5), (24, 12),
               (20, 18), (12, 19), (4, 18), (1, 12))
    pixels = {}
    for ring, fraction in enumerate((.39, .65, .91)):
        points = []
        for i, (x, y) in enumerate(anchors):
            span = fraction + (((i * 3 + ring) % 5) - 2) * .018
            points.append((round(hub[0] + (x - hub[0]) * span), round(hub[1] + (y - hub[1]) * span)))
        for i, (a, b) in enumerate(zip(points, points[1:] + points[:1])):
            if (ring, i) in ((1, 8), (2, 1), (2, 4)):
                continue
            middle = (round((a[0] + b[0]) * .47 + hub[0] * .06), round((a[1] + b[1]) * .47 + hub[1] * .06))
            color = SILK if (i + 2 * ring) % 5 in (0, 1, 2) else SHADOW
            _strand(pixels, a, middle, color)
            _strand(pixels, middle, b, color)
    for i, anchor in enumerate(anchors):
        _strand(pixels, hub, anchor, LIGHT if i in (1, 4, 7) else SILK)
    pixels[hub] = LIGHT
    return _photo(master, pixels, 25, 20, zoom)


def corner_web(master, zoom, mirrored=False):
    pixels = {}
    corner = (0, 0)
    edges = ((13, 2), (12, 5), (10, 9), (6, 12), (1, 14))
    for edge in edges:
        _strand(pixels, corner, edge, SHADOW)
    for fraction in (.38, .62, .90):
        points = [(round(x * fraction), round(y * fraction)) for x, y in edges]
        for a, b in zip(points, points[1:]):
            _strand(pixels, a, b, SILK)
    return _photo(master, pixels, 15, 15, zoom, mirrored)


def floor_web_tiles(master, placements, zoom, tile_size=16):
    """Draw connected silk panels once, then split them into chunk-safe tiles."""
    panel_tiles = []
    for index, (columns, rows) in enumerate(((3, 3), (4, 2), (2, 4))):
        width, height = columns * tile_size, rows * tile_size
        hub = (width * (4 + index) // 10, height * (6 - index) // 10)
        anchors = ((0, height // 5), (width // 4, 0), (width * 5 // 8, 1),
                   (width - 1, height // 10), (width - 2, height // 2),
                   (width - 1, height * 4 // 5), (width * 2 // 3, height - 1),
                   (width // 3, height - 1), (1, height * 4 // 5), (0, height // 2))
        pixels = {}
        for ring, fraction in enumerate((.23, .40, .57, .75, .93)):
            rim = [(round(hub[0] + fraction * (x - hub[0])),
                    round(hub[1] + fraction * (y - hub[1]))) for x, y in anchors]
            for spoke, (a, b) in enumerate(zip(rim, rim[1:] + rim[:1])):
                if (ring * 3 + spoke + index) % 11 == 0:
                    continue
                sag = (round((a[0] + b[0]) * .46 + hub[0] * .08),
                       round((a[1] + b[1]) * .46 + hub[1] * .08))
                ink = "#655c7b" if (ring + spoke) % 3 == 0 else "#776d8b"
                _strand(pixels, a, sag, ink)
                _strand(pixels, sag, b, ink)
        for spoke, anchor in enumerate(anchors):
            _strand(pixels, hub, anchor, "#9284a4" if spoke % 3 == index else "#736581")
        pixels[hub] = "#b8aac1"
        panel = _photo(master, pixels, width, height, 1)
        tiles = {}
        for row in range(rows):
            for col in range(columns):
                tile = tk.PhotoImage(master=master, width=tile_size, height=tile_size)
                x, y = col * tile_size, row * tile_size
                tile.tk.call(tile, "copy", panel, "-from", x, y, x + tile_size, y + tile_size)
                tiles[col, row] = tile.zoom(zoom)
        panel_tiles.append(tiles)
    mapped = defaultdict(list)
    for (x, y), pattern in placements:
        for (col, row), art in panel_tiles[pattern].items():
            mapped[x + col, y + row].append(art)
    return mapped


def bound_web(master, zoom):
    pixels = {}
    for points, color in (
        (((0, 3), (6, 8), (17, 9), (24, 5)), SHADOW),
        (((1, 2), (7, 4), (17, 2), (23, 3)), SILK),
        (((1, 5), (9, 4), (19, 8), (23, 6)), SILK),
        (((3, 8), (9, 6), (15, 4), (21, 1)), LIGHT),
        (((3, 3), (6, 6), (8, 8)), SILK),
        (((14, 1), (12, 5), (12, 9)), SILK),
        (((20, 2), (19, 6), (21, 8)), SILK),
    ):
        for a, b in zip(points, points[1:]):
            _strand(pixels, a, b, color)
    return _photo(master, pixels, 25, 10, zoom)
