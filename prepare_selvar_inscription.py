"""Build the Selvar wall inscription at native pixel density.

A nearly square patch of worn purple slate, split by a natural crack, with one column of
Selvar script carved down it (hook, stem, zig, diamond and tail strokes, after
`assets/mine-polish/selvar-inscription-source.svg`). Two states are written:

    selvar-inscription.png      the old carving on its own, reusable on any north wall
    selvar-inscription-cut.png  fresh Veskar cuts across it, pale dust and Temur's charcoal
    selvar-fracture.png         the fracture and its traveling blue pulse
    ondastela-pulse.png         the Blue Stone with the same light

Both use a two-cell-wide canvas centered on the inspection tile. The rim reads
as a recess in the rock above the wall course, with the base on the floor line.

Run from the project root:  python prepare_selvar_inscription.py
"""
import math
import random
import struct
import wave
from pathlib import Path

import pygame

OUT = Path(__file__).resolve().parent / "assets" / "mine-polish"
SIZE = (32, 32)

RIM = (29, 26, 48)
SLATE = ((49, 43, 69), (65, 58, 87), (84, 75, 106), (114, 103, 139))
GROOVE = (47, 45, 59)
CRACK = (44, 41, 61)
CUT = (153, 143, 172)
# Where a fresh cut crosses an old groove the crystal light catches the raw edge.
GLINT = (136, 172, 209)
DUST = ((119, 109, 142), (158, 145, 170))
CHARCOAL = ((16, 14, 18), (52, 46, 54))

PANEL = {4: (5, 26), 5: (4, 27), 6: (3, 28), 27: (3, 28), 28: (4, 27), 29: (5, 26)}

# One Selvar column on the tile centerline, read top to bottom.
GLYPH = (
    (12, 10), (13, 9), (14, 8), (15, 8), (16, 8), (17, 9),  # hook
    *((16, y) for y in range(9, 25)),                         # stem
    (15, 11), (14, 12), (13, 13), (14, 14), (15, 15), (17, 15), (18, 16),
    (15, 17), (17, 17), (14, 18), (18, 18), (15, 19), (17, 19),  # diamond
    (15, 22), (14, 23), (13, 24), (15, 24), (17, 25), (18, 25), (19, 24),
)
CRACKS = (((8, 7), (7, 11), (9, 15), (8, 19)), ((24, 18), (23, 21), (24, 25), (22, 27)))
# Fresh cuts cross the middle of the tablet.
CUTS = (
    ((7, 15), (13, 15), (16, 14), (24, 14)),
    ((8, 21), (13, 21), (17, 20), (23, 20)),
)
DUST_SPOTS = ((11, 29), (13, 30), (15, 29), (16, 30), (18, 29), (20, 30))
CHARCOAL_STUB = ((23, 30), (24, 30), (25, 29))
FRACTURE_PATH = ((0, 27), (4, 26), (7, 24), (11, 24), (14, 22), (17, 23),
                 (20, 22), (24, 22), (27, 20), (28, 21), (31, 19), (32, 16),
                 (36, 14), (34, 12), (37, 9), (39, 7))
RESONANCE_BLUE = (121, 198, 255)
RESONANCE_CORE = (220, 246, 255)


def _panel():
    cells = set()
    for y in range(4, 30):
        left, right = PANEL.get(y, (2, 29))
        cells.update((x, y) for x in range(left, right + 1))
    return cells


def build(cut=False):
    rng = random.Random(50)
    surface = pygame.Surface(SIZE, pygame.SRCALPHA)
    panel = _panel()
    face = {(x, y) for x, y in panel
            if all((x + dx, y + dy) in panel for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))}
    for point in panel - face:
        surface.set_at(point, RIM)
    for x, y in face:
        edge = (x - 1, y) not in face or (x + 1, y) not in face
        tone = 0 if edge or y <= 6 else 2 if (x, y + 1) not in face else 1
        roll = rng.random()
        # Age has worn the slate unevenly; a little grit keeps the face from reading flat.
        if roll < .1:
            tone = max(0, tone - 1)
        elif roll > .94:
            tone = min(3, tone + 1)
        surface.set_at((x, y), SLATE[tone])
    for crack in CRACKS:
        pygame.draw.lines(surface, CRACK, False, crack)
    grooves = set(GLYPH)
    for x, y in grooves:
        surface.set_at((x, y), GROOVE)
        # Softened by age: the lower lip of each groove catches a little light.
        if (x, y + 1) in face and (x, y + 1) not in grooves:
            surface.set_at((x, y + 1), SLATE[3])
    if cut:
        for stroke in CUTS:
            pygame.draw.lines(surface, CUT, False, stroke)
        for point in grooves:
            if surface.get_at(point)[:3] == CUT:
                surface.set_at(point, GLINT)
        for i, point in enumerate(DUST_SPOTS):
            surface.set_at(point, DUST[i % 2])
        surface.set_at(CHARCOAL_STUB[0], CHARCOAL[0])
        surface.set_at(CHARCOAL_STUB[1], CHARCOAL[1])
        surface.set_at(CHARCOAL_STUB[2], DUST[0])
    return surface


def _fracture_trace():
    pixels = []
    for (x, y), (next_x, next_y) in zip(FRACTURE_PATH, FRACTURE_PATH[1:]):
        dx, dy = next_x - x, next_y - y
        steps = max(abs(dx), abs(dy))
        pixels.extend((round(x + dx * i / steps), round(y + dy * i / steps)) for i in range(steps))
    return tuple(dict.fromkeys((*pixels, FRACTURE_PATH[-1])))


def build_fracture():
    width, height = 48, 32
    trace = _fracture_trace()
    dormant = pygame.Surface((width, height), pygame.SRCALPHA)
    for index, (x, y) in enumerate(trace):
        if index % 3 == 1:
            dormant.set_at((x, y + 1), (92, 77, 116, 72))
        if 20 <= x <= 37:
            # Stone has chipped away where the fracture passes through the lettering.
            dormant.set_at((x, y + 1), (25, 19, 40, 204))
            if 25 <= x <= 34:
                dormant.set_at((x, y - 1), (32, 24, 46, 218))
                dormant.set_at((x, y + 2), (96, 81, 120, 138))
        dormant.set_at((x, y), (21, 17, 33, min(194, 64 + index * 10)))

    cuts = pygame.Surface((width, height), pygame.SRCALPHA)
    for stroke in CUTS:
        pygame.draw.lines(cuts, (255, 255, 255), False, [(x + 16, y) for x, y in stroke])

    frame_count, tail = 19, 10
    atlas = pygame.Surface((width * frame_count, height), pygame.SRCALPHA)
    for frame in range(frame_count):
        image = dormant.copy()
        head = round((len(trace) + tail) * frame / (frame_count - 1)) - 1
        colors = {}
        for index, (x, y) in enumerate(trace):
            lag = head - index
            if not 0 <= lag < tail:
                continue
            energy = (1 - lag / tail) ** 1.8
            flare = bool(cuts.get_at((x, y)).a) and energy > .35
            for ox, oy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
                point = (x + ox, y + oy)
                if 0 <= point[0] < width:
                    alpha = round(energy * (125 if flare else 82))
                    if alpha > image.get_at(point).a:
                        image.set_at(point, (*RESONANCE_BLUE, alpha))
            shade = RESONANCE_CORE if flare or lag < 2 else RESONANCE_BLUE
            colors[x, y] = (*shade, round(92 + 163 * energy))
        for point, color in colors.items():
            image.set_at(point, color)
        atlas.blit(image, (frame * width, 0))
    return atlas


def build_ondastela_pulse():
    stone = pygame.image.load(OUT.parent / "astral-stone-outlined.png")
    width, height = stone.get_size()
    strengths = (0, .13, .29, .46, .31, .15)
    atlas = pygame.Surface((width * len(strengths), height), pygame.SRCALPHA)
    for index, strength in enumerate(strengths):
        frame = stone.copy()
        for y in range(height):
            for x in range(width):
                color = stone.get_at((x, y))
                if color.a and color.b > 65 and color.b > color.r + 22:
                    target = RESONANCE_CORE if color.g > 130 else RESONANCE_BLUE
                    frame.set_at((x, y), color.lerp((*target, color.a), strength))
        atlas.blit(frame, (index * width, 0))
    return atlas


def write_seal_rumble():
    audio = OUT.parent / "audio"
    audio.mkdir(parents=True, exist_ok=True)
    rate, duration = 22050, .7
    rng = random.Random(47)
    grains = 0.0
    pcm = bytearray()
    for i in range(round(rate * duration)):
        t = i / rate
        grains += .045 * (rng.uniform(-1, 1) - grains)
        envelope = min(t / .12, 1) * (1 - t / duration) ** 1.6
        bass = math.sin(math.tau * (54 * t - 10 * t * t))
        sample = envelope * (.45 * bass + .6 * grains)
        pcm.extend(struct.pack("<h", round(sample * 15000)))
    with wave.open(str(audio / "selvar-rumble.wav"), "wb") as file:
        file.setparams((1, 2, rate, 0, "NONE", "not compressed"))
        file.writeframes(pcm)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    pygame.image.save(build(), str(OUT / "selvar-inscription.png"))
    pygame.image.save(build(cut=True), str(OUT / "selvar-inscription-cut.png"))
    pygame.image.save(build_fracture(), str(OUT / "selvar-fracture.png"))
    pygame.image.save(build_ondastela_pulse(), str(OUT / "ondastela-pulse.png"))
    write_seal_rumble()


if __name__ == "__main__":
    main()
