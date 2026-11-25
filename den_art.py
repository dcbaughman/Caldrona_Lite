"""Hand-drawn native-pixel props for the Depths."""

import tkinter as tk


STONE_OUTLINE = "#08070b"


def _stamp(master, size, facets, details, zoom, *, outline=None):
    width, height = size
    pixels = {}
    for color, polygon in facets:
        edges = tuple(zip(polygon, polygon[1:] + polygon[:1]))
        for y in range(height):
            scan_y = y + .5
            crossings = sorted(
                x1 + (scan_y - y1) * (x2 - x1) / (y2 - y1)
                for (x1, y1), (x2, y2) in edges if min(y1, y2) <= scan_y < max(y1, y2)
            )
            for left, right in zip(crossings[::2], crossings[1::2]):
                for x in range(max(0, round(left)), min(width, round(right))):
                    pixels[x, y] = color
    pixels.update({point: color for color, points in details for point in points})
    if outline is not None:
        edge = {(x + dx, y + dy) for x, y in pixels
                for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0))
                if 0 <= x + dx < width and 0 <= y + dy < height} - pixels.keys()
        pixels.update(dict.fromkeys(edge, outline))
    image = tk.PhotoImage(master=master, width=width, height=height)
    for (x, y), color in pixels.items():
        image.put(color, (x, y))
    return image.zoom(zoom)


def _egg(x, y, width, height):
    # Flatten the base and wrap the silk around a rounded, slightly lopsided sac.
    shape = (
        ("#252139", ((1, 7), (3, 3), (6, 1), (10, 1), (14, 4), (16, 8), (16, 13), (14, 17), (11, 19), (5, 19), (2, 17), (0, 13), (0, 10))),
        ("#524564", ((1, 8), (4, 3), (7, 2), (10, 2), (14, 5), (15, 9), (15, 13), (13, 16), (10, 18), (5, 18), (2, 15), (1, 12))),
        ("#84758e", ((2, 7), (5, 4), (9, 3), (12, 4), (14, 8), (14, 12), (12, 15), (8, 17), (4, 16), (2, 13))),
        ("#b2a091", ((3, 7), (5, 5), (9, 4), (12, 6), (13, 9), (11, 13), (8, 15), (4, 14), (2, 11))),
        ("#d9c7ae", ((4, 7), (6, 5), (9, 5), (10, 7), (8, 9), (5, 10), (3, 9))),
        ("#756282", ((3, 13), (7, 14), (11, 12), (14, 9), (13, 13), (11, 15), (8, 16), (5, 16))),
        ("#d7c9b1", ((3, 10), (7, 11), (10, 10), (13, 8), (12, 10), (9, 12), (6, 13), (3, 12))),
        ("#9688a2", ((6, 16), (10, 15), (13, 13), (12, 16), (9, 17))),
    )
    return tuple((color, tuple((x + round(px * width / 16), y + round(py * height / 20))
                               for px, py in polygon)) for color, polygon in shape)


def egg_sacs(master, zoom):
    bed = (("#302940", ((1, 29), (5, 26), (24, 25), (30, 29), (26, 31), (4, 31))),
           ("#675977", ((2, 30), (8, 27), (18, 26), (24, 28), (28, 30), (17, 29), (7, 31))))
    details = (("#e2d1b7", ((9, 18), (24, 25), (17, 15))), ("#9c8ba0", ((4, 30), (13, 29), (24, 30))))
    corner_bed = (("#302940", ((8, 30), (12, 28), (19, 28), (24, 30), (21, 32), (11, 32))),
                  ("#675977", ((9, 30), (15, 29), (23, 30), (19, 31), (12, 31))))
    return (
        _stamp(master, (32, 32), bed + _egg(2, 16, 14, 14) + _egg(11, 12, 18, 18), details, zoom),
        _stamp(master, (32, 32), bed + _egg(3, 18, 12, 12) + _egg(10, 13, 17, 17) + _egg(21, 20, 10, 11),
               details, zoom),
        _stamp(master, (32, 32), corner_bed + _egg(8, 23, 9, 8) + _egg(13, 19, 11, 12),
               (("#e2d1b7", ((17, 22),)),), zoom),
    )


def black_stone(master, zoom):
    # Intergrown octahedra sit in a low bed of shale. Keep their faces near-black.
    facets = (
        ("#211a32", ((2, 31), (7, 25), (15, 23), (26, 24), (34, 29), (37, 32), (31, 35), (7, 35))),
        ("#493b55", ((3, 31), (9, 26), (18, 26), (22, 28), (14, 29), (10, 33))),
        ("#40364c", ((21, 32), (28, 25), (34, 28), (36, 31), (30, 34))),
        ("#17131f", ((6, 23), (11, 10), (20, 13), (25, 23), (15, 31), (8, 29))),
        ("#4b3b60", ((6, 23), (11, 10), (16, 17), (14, 22), (8, 27))),
        ("#302640", ((11, 10), (20, 13), (23, 20), (16, 17))),
        ("#221a2d", ((23, 20), (25, 24), (15, 31), (14, 22), (16, 17))),
        ("#0e0b17", ((13, 20), (23, 2), (33, 8), (38, 21), (25, 33), (18, 29))),
        ("#34294a", ((13, 20), (23, 2), (28, 14), (22, 22))),
        ("#524162", ((23, 2), (33, 8), (28, 14))),
        ("#251d35", ((28, 14), (33, 8), (38, 21), (28, 23))),
        ("#1b1529", ((13, 20), (22, 22), (28, 23), (25, 33), (18, 29))),
        ("#100d1d", ((28, 23), (38, 21), (25, 33))),
        ("#59486d", ((19, 11), (23, 4), (25, 8), (24, 10), (22, 9))),
        ("#82708f", ((22, 5), (23, 2), (25, 5), (24, 5))),
    )
    details = (("#aa97ae", ((23, 3), (11, 12), (29, 7))),
               ("#615174", ((6, 30), (9, 28), (15, 27), (34, 30), (31, 32), (21, 23))))
    return _stamp(master, (40, 36), facets, details, zoom, outline=STONE_OUTLINE)


def white_stone(master, zoom):
    facets = (
        ("#403c42", ((2, 25), (7, 21), (23, 20), (28, 25), (23, 28), (7, 28))),
        ("#706e78", ((3, 25), (12, 21), (22, 22), (26, 25), (20, 27), (7, 27))),
        ("#9a9ba9", ((6, 24), (5, 14), (12, 2), (19, 0), (25, 13), (23, 24), (15, 27))),
        ("#f5ead3", ((5, 14), (12, 2), (19, 0), (15, 12), (11, 20))),
        ("#e5ddcc", ((15, 12), (19, 0), (25, 13), (19, 18), (11, 20))),
        ("#b8bac5", ((5, 14), (11, 20), (19, 18), (23, 24), (15, 27), (6, 24))),
        ("#86899d", ((25, 13), (23, 24), (19, 18))),
    )
    details = (("#fff9e8", ((12, 3), (11, 5), (10, 7), (14, 11))),
               ("#d2cbb5", ((8, 22), (11, 23), (17, 23))))
    return _stamp(master, (30, 29), facets, details, zoom)
