"""Shalehorn's pixel-art neck hinge and charged lunge."""
from math import cos, pi, radians, sin
import tkinter as tk

from battle_lighting import muted_battlefield

WINDUP = .34
CONTACT = .76
RECOVER = .90
CHARGE_DURATION = 1.32
HEADBUTT_DURATION = .65
CHARGE_LANDING = (536, 209)
SCALE = 2
PADDING = 8
NECK = (46, 31)
TUSKS = (
    ((46, 29), (47, 25), (50, 22), (51, 26), (55, 23), (58, 19), (59, 23),
     (58, 29), (54, 33), (48, 35), (46, 33)),
    ((66, 31), (69, 27), (70, 22), (71, 20), (72, 21), (72, 33), (68, 36), (66, 35)),
)
TIPS = ((57, 21), (70, 22))
TUSK_PALETTES = (
    ("#284673", "#448fc7", "#91d6fb"),
    ("#245491", "#5cbcf6", "#bef1ff"),
    ("#317caf", "#82daff", "#e8fbff"),
)


def _inside(x, y, polygon):
    inside = False
    x, y = x + .5, y + .5
    for (ax, ay), (bx, by) in zip(polygon, polygon[1:] + polygon[:1]):
        if (ay > y) != (by > y) and x < ax + (bx - ax) * (y - ay) / (by - ay):
            inside = not inside
    return inside


def _ease(value):
    t = max(0, min(1, value))
    return t * t * (3 - 2 * t)


def _joint_weight(x, y):
    # The rotation tapers off into the neck and stops above the front foot.
    return _ease((x - 40) / 20) * _ease((y - 10) / 10) * _ease((44 - y) / 9)


def _turn(x, y, angle):
    px, py = NECK
    theta = radians(angle) * _joint_weight(x, y)
    dx, dy = x - px, y - py
    return px + dx * cos(theta) - dy * sin(theta), py + dx * sin(theta) + dy * cos(theta)


class ShalehornAttack:
    def __init__(self, canvas):
        self.canvas = canvas
        self.sprites = {}
        self.frames = {}
        self.room_frames = {}
        self.debris_colors = {}

    def _native_sprite(self, source):
        key = str(source)
        if key not in self.sprites:
            native = source.subsample(SCALE)
            tusks = {}
            for y in range(native.height()):
                for x in range(native.width()):
                    if any(_inside(x, y, p) for p in TUSKS) and not native.transparency_get(x, y):
                        r, g, b = native.get(x, y)
                        if r >= 115 and g >= r * .65 and r >= b:
                            tusks[x, y] = min(2, max(0, (r + g - 230) // 68))
            self.sprites[key] = native, tusks
        return self.sprites[key]

    def image(self, source, angle, energy=0, sheen=0):
        if not (angle or energy):
            return source
        key = (str(source), angle, energy, sheen)
        if key not in self.frames:
            native, tusks = self._native_sprite(source)
            w, h = native.width(), native.height()
            pose = tk.PhotoImage(master=self.canvas, width=w + PADDING * 2, height=h + PADDING * 2)
            for y in range(-PADDING, h + PADDING):
                run = None
                for x in range(-PADDING, w + PADDING + 1):
                    sx, sy = _turn(x, y, -angle) if angle and x > 40 else (x, y)
                    sx, sy = round(sx), round(sy)
                    valid = 0 <= sx < w and 0 <= sy < h and x < w + PADDING
                    shade = tusks.get((sx, sy)) if energy else None
                    if run is not None:
                        start_x, start_sx, row = run
                        if valid and shade is None and sy == row and sx == start_sx + x - start_x:
                            continue
                        # Copy runs of the source photo so its translucent edge pixels
                        # keep their original alpha as the head rotates.
                        pose.tk.call(pose, "copy", native, "-from", start_sx, row, start_sx + x - start_x, row + 1,
                                     "-to", start_x + PADDING, y + PADDING)
                        run = None
                    if valid and shade is None:
                        run = (x, sx, sy)
                    elif valid:
                        color = TUSK_PALETTES[energy - 1][shade]
                        if shade > 0 and (sx + sy) % 7 in (sheen, sheen + 1):
                            color = "#edfdff"
                        pose.put(color, to=(x + PADDING, y + PADDING))
            self.frames[key] = pose.zoom(SCALE)
        return self.frames[key]

    def muted_room(self, backdrop):
        return muted_battlefield(self.canvas, backdrop, self.room_frames)

    @staticmethod
    def _headbutt(t):
        if t < .22:
            return -12 * _ease(t / .22)
        if t < .37:
            return -12 + 28 * _ease((t - .22) / .15)
        return 16 * (1 - _ease((t - .37) / (HEADBUTT_DURATION - .37)))

    @staticmethod
    def _travel(t):
        if t < CONTACT:
            return max(0, (t - WINDUP) / (CONTACT - WINDUP)) ** 1.25
        return 1 - _ease((t - RECOVER) / (CHARGE_DURATION - RECOVER))

    def draw(self, scene, source, t, charge, tags):
        c = self.canvas
        item = scene.enemy_items[0]
        x, y = scene.enemy_positions[0]
        if not charge:
            angle = 2 * round(self._headbutt(t) / 2)
            c.coords(item, x, y)
            c.itemconfigure(item, image=self.image(source, angle), state="normal")
            return
        travel = self._travel(t)
        neutral_x, neutral_y = CHARGE_LANDING
        cx = x + (neutral_x - x) * travel
        cy = y + (neutral_y - y) * travel
        if t < WINDUP:
            cx -= 7 * sin(pi * t / WINDUP)
            angle = -12 * _ease(t / WINDUP)
            energy = int(t >= .10)
        elif t < CONTACT:
            cy -= 8 * sin(pi * travel)
            angle = -12 + 23 * _ease(travel)
            energy = 2
        else:
            angle = 14 * travel
            energy = 3 if t < RECOVER + .12 else int(t < 1.14)
        angle = 2 * round(angle / 2)
        sheen = (int(t * 34) % 6) if energy else 0
        c.coords(item, round(cx), round(cy))
        c.itemconfigure(item, image=self.image(source, angle, energy, sheen), state="normal")
        self._shale(scene, source, t, x, y, tags)
        if energy:
            self._sparks(cx, cy, angle, t, energy, tags)

    def _shale(self, scene, source, t, x, y, tags):
        if not .23 <= t <= 1.11:
            return
        ground = int(y + source.height() // 2 - 5)
        backdrop = scene.glow_frames[0]
        key = str(backdrop)
        if key not in self.debris_colors:
            self.debris_colors[key] = [
                backdrop.get(int(x) - 58 + i * 2, ground + i % 7)
                for i in range(22)
            ]
        for i, rgb in enumerate(self.debris_colors[key]):
            kick = .23 + i * .024
            phase = (t - kick) / (.26 + i % 4 * .031)
            if 0 <= phase < 1:
                travel = self._travel(kick)
                px = round(x + (CHARGE_LANDING[0]-x) * travel - 56 - (52 + i * 3) * phase)
                py = round(ground + (CHARGE_LANDING[1]-y) * travel - (17 + i % 5 * 8) * sin(pi * phase))
                size = 4 + i % 5
                debris_tags = (*tags, "shalehorn_charge_shale")
                tone = (54*rgb[0] + 183*rgb[1] + 19*rgb[2]) >> 8
                shade = "#%02x%02x%02x" % (tone, tone, min(255, tone + 10))
                gleam = "#%02x%02x%02x" % tuple(min(255, tone + channel) for channel in (35, 37, 49))
                self.canvas.create_rectangle(px, py, px+size, py+size-1, fill=shade, outline="", tags=debris_tags)
                self.canvas.create_rectangle(px+1, py-1, px+size-1, py+1, fill=gleam, outline="", tags=debris_tags)
        self.canvas.tag_lower("shalehorn_charge_shale", scene.enemy_items[0])

    def _sparks(self, x, y, angle, t, energy, tags):
        for tip_x, tip_y in TIPS:
            tip_x, tip_y = _turn(tip_x, tip_y, angle)
            for i in range(energy + 1):
                phase = (t * 8 + i * .37) % 1
                px = round(x + (tip_x - 36) * SCALE + phase * (5 + 5 * energy))
                py = round(y + (tip_y - 24) * SCALE - phase * (6 + i * 4))
                size = 2 if i % 2 else energy + 1
                self.canvas.create_rectangle(px, py, px+size, py+size,
                                             fill=("#65b8f8", "#a3e4ff", "#e3fbff")[i % 3],
                                             outline="", tags=(*tags, "shalehorn_tusk_energy"))
