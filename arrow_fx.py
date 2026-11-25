"""Draw the same nocked and flying arrow on the sprite pixel grid."""

from functools import lru_cache
from math import atan2, cos, hypot, pi, sin, tau


ARROW_LENGTH = 17
DRAW_HAND = (24, 17)
NOCKED_TIP = (DRAW_HAND[0] - ARROW_LENGTH, DRAW_HAND[1])
FLIGHT_MS = 310
IMPACT_MS = 135
TAG = "bow_shot"
HEADINGS = 32

# Points are measured back from the tip along the shaft. The bevel, shaft,
# and fletching stay the same length in the pose sheet and during flight.
ARROW_PARTS = (
    ("#161620", ((0, 0), (-5, -2), (-6, -1), (-13, -1), (-17, -2),
                 (-17, 2), (-13, 1), (-6, 1), (-5, 2))),
    ("#b58957", ((-5, 0), (-16, 0), (-16, 1), (-5, 1))),
    ("#76adc9", ((-13, 0), (-16, -1), (-16, 1))),
    ("#e3edf2", ((0, 0), (-5, -1), (-4, 1))),
)


def arrow_parts(tip, direction, scale=1):
    """Rotate the arrow around its tip so the tip lands on the selected target."""
    x, y = tip
    dx, dy = direction
    distance = hypot(dx, dy)
    ux, uy = (dx / distance, dy / distance) if distance else (-1, 0)
    for color, shape in ARROW_PARTS:
        points = [(round(x + scale * (along*ux - across*uy)),
                   round(y + scale * (along*uy + across*ux)))
                  for along, across in shape]
        yield color, points


def bow_origin(actor, scale):
    # The unpadded body frame is 48×40, with its center at (24, 20).
    return actor[0] + (NOCKED_TIP[0] - 24) * scale, actor[1] + (NOCKED_TIP[1] - 20) * scale


def trajectory(start, target, progress):
    x, y = start
    dx, dy = target[0] - x, target[1] - y
    arc = min(19, abs(dx) * .10)
    return ((x + dx*progress, y + dy*progress - arc*sin(pi*progress)),
            (dx, dy - pi*arc*cos(pi*progress)))


def _polygon_pixels(points):
    edges = tuple(zip(points, points[1:] + points[:1]))
    for y in range(min(p[1] for p in points), max(p[1] for p in points) + 1):
        for x in range(min(p[0] for p in points), max(p[0] for p in points) + 1):
            inside = False
            for (ax, ay), (bx, by) in edges:
                if (x-ax)*(by-ay) == (y-ay)*(bx-ax) and (
                    min(ax, bx) <= x <= max(ax, bx) and min(ay, by) <= y <= max(ay, by)
                ):
                    inside = True
                    break
                if (ay > y) != (by > y) and x < ax + (bx-ax)*(y-ay)/(by-ay):
                    inside = not inside
            if inside:
                yield x, y


@lru_cache(maxsize=HEADINGS)
def _sprite_runs(heading):
    # Rasterize at native size first. Enlarging the runs leaves the same
    # stair-step silhouette at any field or lab zoom.
    angle = heading * tau / HEADINGS
    pixels = {}
    for color, points in arrow_parts((0, 0), (cos(angle), sin(angle))):
        pixels.update(dict.fromkeys(_polygon_pixels(points), color))
    tip = pixels.pop((0, 0))
    runs = []
    for (x, y), color in sorted(pixels.items(), key=lambda pixel: (pixel[0][1], pixel[0][0])):
        if runs and runs[-1][1:] == (y, x, color):
            runs[-1] = (runs[-1][0], y, x+1, color)
        else:
            runs.append((x, y, x+1, color))
    return ((0, 0, 1, tip), *runs)


def draw_shot(canvas, actor, target, elapsed_ms, scale, tags):
    if elapsed_ms < 0 or elapsed_ms >= FLIGHT_MS + IMPACT_MS:
        return
    progress = min(1, elapsed_ms / FLIGHT_MS)
    tip, (dx, dy) = trajectory(bow_origin(actor, scale), target, progress)
    x, y = map(round, tip)
    heading = round(atan2(dy, dx) * HEADINGS / tau) % HEADINGS
    arrow_tag = ("bow_arrow", *tags, TAG)
    for index, (left, row, right, color) in enumerate(_sprite_runs(heading)):
        canvas.create_rectangle(x + left*scale, y + row*scale,
                                x + right*scale, y + (row+1)*scale,
                                fill=color, outline="",
                                tags=arrow_tag if index else (*arrow_tag, "bow_arrow_tip"))
    if progress == 1:
        age = min(2, int((elapsed_ms - FLIGHT_MS) * 3 / IMPACT_MS))
        for dx, dy in ((-2, -2), (-3, 1), (1, -3), (2, 1)):
            px = x + (dx + (age if dx > 0 else -age)) * scale
            py = y + (dy + (age if dy > 0 else -age)) * scale
            canvas.create_rectangle(px, py, px+scale, py+scale, outline="",
                                    fill=("#fff1c3", "#e4ac68", "#927e68")[age],
                                    tags=(*tags, TAG, "bow_impact"))
