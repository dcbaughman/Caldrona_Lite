"""Pixel silk, wrapping, and reeling for the Den Mother's Last Brood."""

from math import pi, sin
import tkinter as tk

from enemy_motion import BROOD_SHADE_STEPS


CAST = .07
CONTACT = .39
REEL = .70
SWALLOW = 1.31
STAGGER = .12
DARKEN = SWALLOW + STAGGER
BROOD_DURATION = 2.92

SILK = "#e4d9d4"
SILK_SHADOW = "#827393"
BALL = (
    "    ssss    ",
    "  ssmmmlss  ",
    " smmlllllms ",
    " smlwllllms ",
    "smllwllmmmss",
    "smlwllmmmmss",
    "smllmmmmmmss",
    "smllmmmmssbs",
    " slmmmssbbs ",
    " smmsssbbbs ",
    "  ssbbbsss  ",
    "    ssss    ",
)
BALL_COLORS = {"b": "#574b67", "s": "#372c45", "m": "#95859d", "l": "#c3b3bb", "w": "#f2e5d7"}


def brood_shade(elapsed):
    progress = (elapsed - DARKEN) / (BROOD_DURATION - DARKEN)
    return max(0, min(BROOD_SHADE_STEPS, int(progress * BROOD_SHADE_STEPS + 1e-9)))


def lerp(source, target, progress):
    return tuple(a + (b-a) * progress for a, b in zip(source, target))


def stepped(points):
    """Snap the vertices to native-sized steps before canvas scaling."""
    pixels = [(round(x / 2) * 2, round(y / 2) * 2) for x, y in points]
    path = list(pixels[0])
    for (x, y), (nx, ny) in zip(pixels, pixels[1:]):
        path.extend((nx, y, nx, ny))
    return path


class BroodSilk:
    TAG = "last_brood_silk"
    WRAP_TAG = "last_brood_wrap"

    def __init__(self, canvas):
        self.canvas = canvas
        self.balls = None

    def _load_balls(self):
        # Slide the bright binding along the ball as its silk rolls up.
        bindings = (((1, 7), (3, 7), (6, 5), (10, 3)),
                    ((3, 9), (4, 7), (6, 5), (8, 2)),
                    ((6, 10), (5, 7), (6, 4), (7, 1)),
                    ((9, 9), (7, 7), (6, 5), (3, 2)))
        frames = []
        for binding in bindings:
            image = tk.PhotoImage(master=self.canvas, width=12, height=12)
            for y, row in enumerate(BALL):
                for x, pixel in enumerate(row):
                    if pixel != " ":
                        image.put(BALL_COLORS[pixel], (x, y))
            path = stepped([(x*2, y*2) for x, y in binding])
            for x, y, nx, ny in zip(path[::2], path[1::2], path[2::2], path[3::2]):
                for px in range(min(x, nx)//2, max(x, nx)//2 + 1):
                    for py in range(min(y, ny)//2, max(y, ny)//2 + 1):
                        if not image.transparency_get(px, py):
                            image.put(SILK, (px, py))
            frames.append(image.zoom(2))
        self.balls = tuple(frames)

    def clear(self):
        self.canvas.delete(self.TAG)
        self.canvas.delete(self.WRAP_TAG)

    def draw(self, age, boss_item, mouth, brood):
        """Draw each victim from its stable origin so lab scrubbing is reversible."""
        self.clear()
        for ordinal, (item, spider, source) in enumerate(brood):
            elapsed = age - ordinal * STAGGER
            if elapsed >= SWALLOW:
                self.canvas.itemconfigure(item, state="hidden", image=spider)
                continue

            position = source
            image = spider
            if elapsed >= REEL:
                travel = (elapsed - REEL) / (SWALLOW - REEL)
                x, y = lerp(source, mouth, travel ** 1.45)
                position = x, y - 10 * sin(pi * travel)
                if self.balls is None:
                    self._load_balls()
                image = self.balls[int(travel * 13) % len(self.balls)]

            self.canvas.itemconfigure(item, state="normal", image=image)
            self.canvas.coords(item, *position)
            if elapsed >= CAST:
                reach = min(1, (elapsed - CAST)/(CONTACT - CAST))
                self._strand(mouth, lerp(mouth, position, reach), elapsed, boss_item)
            if CONTACT <= elapsed < REEL:
                self._wrap(source, (elapsed - CONTACT) / (REEL - CONTACT))

    def _strand(self, mouth, tip, elapsed, boss_item):
        distance = abs(mouth[0] - tip[0]) + abs(mouth[1] - tip[1])
        steps = max(1, round(distance / 5))
        points = []
        for i in range(steps + 1):
            t = i / steps
            x, y = lerp(mouth, tip, t)
            droop = min(8, distance / 12) * sin(pi * t)
            quiver = 2 * sin(t * 3*pi - elapsed*24) * sin(pi * t)
            points.append((x, y + droop + quiver))
        path = stepped(points)
        shadow = self.canvas.create_line(*path, width=3, fill=SILK_SHADOW, tags=self.TAG)
        thread = self.canvas.create_line(*path, width=1, fill=SILK, tags=self.TAG)
        self.canvas.tag_lower(shadow, boss_item)
        self.canvas.tag_lower(thread, boss_item)

    def _wrap(self, source, progress):
        x, y = source
        wraps = (((-14, 2), (-9, 3), (0, 1), (10, -4), (14, -9)),
                 ((-13, -8), (-6, -3), (4, 2), (12, 6)),
                 ((-9, 9), (-2, 7), (7, 3), (12, -4)))
        for row, offsets in enumerate(wraps):
            count = min(len(offsets), max(0, int(progress*11) - 2*row))
            if count > 1:
                path = stepped([(x+dx, y+dy) for dx, dy in offsets[:count]])
                self.canvas.create_line(*path, width=3, fill=SILK_SHADOW, tags=self.WRAP_TAG)
                self.canvas.create_line(*path, width=2, fill=SILK, tags=self.WRAP_TAG)
