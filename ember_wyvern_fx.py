"""Native-pixel poses and fire effects for the Lower Workings boss and its preview."""
import math
import tkinter as tk


PHASE_NAMES = ("Awakening", "Rising Fury", "Superheated Body")
TRANSITION_SECONDS = {2: 1.20, 3: 1.45}
ATTACK_TIMING = {"bite": (.24, .64), "inhale": (.65, .70), "breath": (.42, .96)}
_FRAMES = 12


class EmberWyvernArt:
    def __init__(self, canvas, folder, sleeping, scale=(2, 1)):
        self.canvas = canvas
        zoom, sample = scale
        self.scale = zoom / sample
        self.forms = {1: sleeping}
        for stage, suffix in ((2, "rising"), (3, "heated")):
            sprite = tk.PhotoImage(master=canvas, file=str(folder / f"ember-wyvern-{suffix}.png")).zoom(zoom)
            self.forms[stage] = sprite if sample == 1 else sprite.subsample(sample)
        self.scorched_floor = (tk.PhotoImage(master=canvas, file=str(folder / "ember-wyvern-scorch.png")).zoom(2)
                               if scale == (2, 1) else None)
        self.buried = self._crop(self.forms[1], round(self.forms[1].height() * .74), ragged=True)
        self._reveals = {}

    def _crop(self, image, height, *, ragged=False):
        width = image.width()
        cropped = tk.PhotoImage(master=self.canvas, width=width, height=height)
        step = max(1, round(8 * self.scale)) if ragged else width
        for x in range(0, width, step):
            seam = height - round((0, 2, 4, 1, 3)[x // step % 5] * self.scale) if ragged else height
            cropped.tk.call(cropped, "copy", image, "-from", x, 0, min(x + step, width), seam, "-to", x, 0)
        return cropped

    def pose(self, stage, age=None):
        if stage == 1:
            return self.buried
        if age is None or age >= TRANSITION_SECONDS[stage]:
            return self.forms[stage]
        if stage == 2 and age < .18:
            return self.buried
        start = .18 if stage == 2 else .10
        progress = max(0, (age - start) / (TRANSITION_SECONDS[stage] - start))
        step = min(_FRAMES, int(progress * _FRAMES))
        key = stage, step
        if key not in self._reveals:
            if stage == 2:
                source = self.forms[2]
                height = round(source.height() * (.73 + .27 * step / _FRAMES))
                self._reveals[key] = self._crop(source, height, ragged=step < _FRAMES)
            else:
                self._reveals[key] = self._burn_frame(step)
        return self._reveals[key]

    def _burn_frame(self, step):
        if step == 0:
            return self.forms[2]
        cool, hot = self.forms[2], self.forms[3]
        width, height = hot.width(), hot.height()
        frame = cool.copy()
        for x in range(0, width, 12):
            cut = max(0, min(height, round(height * (1 - step / _FRAMES)) + (x % 43) - 21))
            if cut < height:
                frame.tk.call(frame, "copy", hot, "-from", x, cut, min(width, x + 12), height,
                              "-to", x, cut, "-compositingrule", "set")
        return frame

    def rubble(self, center, ground, tag):
        """Low piles sit over the cropped edge, making it part of the floor."""
        c = self.canvas
        scale = self.scale / 2
        for dx, width, height in ((-173, 36, 9), (-148, 50, 13), (-103, 42, 7), (-69, 61, 13),
                                  (-19, 54, 8), (25, 52, 11), (71, 38, 9), (103, 51, 13), (142, 33, 8)):
            x, w, h = center + dx * scale, width * scale, height * scale
            c.create_polygon(x, ground, x+4*scale, ground-h*.52, x+w*.38, ground-h, x+w*.65, ground-h*.55,
                             x+w*.86, ground-h*.65, x+w, ground, fill="#312938", outline="#211b2b", tags=tag)
            c.create_line(x+w*.21, ground-h*.5, x+w*.38, ground-h+2,
                          x+w*.55, ground-h*.64, fill="#604757", width=2, tags=tag)

    def transition_effect(self, stage, age, x, ground, tag):
        """Break shale at ground level, then curl sparks up across the moss line."""
        progress = min(1, age / TRANSITION_SECONDS[stage])
        scale = self.scale / 2
        palette = ("#624652", "#8b6570", "#ac7b65") if stage == 2 else ("#a84025", "#e87530", "#f6be64")
        for i in range(22):
            start = (i % 7) * .032
            t = progress - start
            if not 0 < t < .75:
                continue
            dx = ((i * 61) % 284 - 142) * scale
            if stage == 2:
                px = x + dx * (1 + .26 * t)
                py = ground - 9 * scale - (math.sin(math.pi * t / .75) * (24 + i % 6 * 13) * scale)
            else:
                px = x + dx + (i % 3 - 1) * 30 * t * scale
                py = ground - (30 + (i % 5) * 22 + t * 170) * scale
            size = max(2, round((3 + i % 3 * 2) * (1 - t / 2) * scale))
            self.canvas.create_rectangle(round(px), round(py), round(px) + size, round(py) + size,
                                         outline="", fill=palette[i % 3], tags=tag)


def attack(canvas, move, age, mouth, targets, tag):
    mx, my = mouth
    colors = ("#933025", "#e45221", "#ff8b32", "#ffca63", "#fff3ab")
    if move == "inhale":
        for i in range(14):
            t = (age * 1.8 + i * .13) % 1
            x = mx + (55 + i * 4) * (1 - t)
            y = my + (i % 7 - 3) * 12 * (1 - t)
            size = 2 + int(3 * t)
            canvas.create_rectangle(round(x), round(y), round(x) + size, round(y) + size,
                                    fill=colors[i % len(colors)], outline="", tags=tag)
        return
    contact, duration = ATTACK_TIMING[move]
    if age >= duration - .04:
        return
    for tx, ty in targets:
        ty = min(294, ty - 8)
        count = 25 if move == "breath" else 9
        for i in range(count):
            t = age / contact - i * (.035 if move == "breath" else .072)
            if not 0 < t < 1.35:
                continue
            travel = min(1, t)
            spread = (13 + 21 * travel) if move == "breath" else (5 + 9 * travel)
            dx = (tx - mx) * travel
            dy = (ty - my) * travel + math.sin(i * 2.2 + age * 11) * spread * travel
            x, y = round(mx + dx), min(310, round(my + dy))
            size = (4 + i % 5 * 2) if move == "breath" else (3 + i % 3 * 2)
            color = colors[i % len(colors)]
            canvas.create_rectangle(x - size, y - size // 2, x + size, min(318, y + size),
                                    fill=color, outline="", tags=tag)


def ground_flare(canvas, x, y, age, tag):
    for i in range(11):
        t = age * (2.1 + (i % 3) * .22) - (i % 4) * .13
        if 0 < t < 1:
            px = round(x + (i - 5) * (4 + t))
            py = round(min(315, y + 19) - t * (14 + i % 4 * 7))
            size = 4 - int(t * 3)
            canvas.create_rectangle(px, py, px + size, py + size, outline="",
                                    fill=("#ae4129", "#f17b37", "#ffc768")[i % 3], tags=tag)
