"""Build native pixel frames for the approved Caldrona attack storyboards."""
import json
from pathlib import Path

import pygame

FX = Path(__file__).resolve().parent / "assets" / "battle" / "fx"
SIZE = 64


def segments(surface, color, points, width=1):
    pygame.draw.lines(surface, color, False, points, width)


def dots(surface, color, points):
    for x, y in points:
        surface.set_at((x, y), color)


def cross(surface, colors, x, y, radius):
    core, high, mid, *_ = colors
    pygame.draw.line(surface, mid, (x-radius, y), (x+radius, y))
    pygame.draw.line(surface, mid, (x, y-radius), (x, y+radius))
    pygame.draw.line(surface, high, (x-2, y), (x+2, y))
    pygame.draw.line(surface, high, (x, y-2), (x, y+2))
    surface.set_at((x, y), core)


def quick_cut(surface, c, i):
    if i == 0:
        dots(surface, c[2], [(25, 39), (28, 36)])
    elif i in (1, 2):
        length = 8 if i == 1 else 13
        end = (25+length, 40-length)
        segments(surface, c[1], [(25, 40), end], 2)
        segments(surface, c[0], [(29, 41), (end[0]+4, end[1]+1)])
    elif i == 3:
        segments(surface, c[2], [(26, 39), (30, 35)])
        segments(surface, c[1], [(33, 36), (38, 31)])
    else:
        dots(surface, c[3], [(26, 39), (39, 30)])


def first_aid(surface, c, i):
    if i <= 2:
        cross(surface, c, 32, 35-i*3, 3)
    if i in (1, 2, 3):
        pygame.draw.ellipse(surface, c[3], (21, 42, 23, 7), 1)
        cross(surface, c, 29, 28-i*2, 4)
    if i in (2, 3):
        cross(surface, c, 39, 28-i*3, 3)
    if i == 4:
        dots(surface, c[2], [(28, 19), (38, 14)])


def spark(surface, c, i):
    if i == 0:
        dots(surface, c[1], [(30, 34)])
    elif i == 1:
        segments(surface, c[1], [(37, 24), (28, 30), (34, 32), (26, 39)], 2)
        dots(surface, c[0], [(36, 25), (30, 33), (27, 38)])
    elif i == 2:
        cross(surface, c, 32, 32, 13)
        dots(surface, c[1], [(27, 27), (37, 27), (27, 37), (37, 37)])
    else:
        dots(surface, c[2 if i == 3 else 3], [(25, 32), (32, 24), (40, 31), (31, 40)] if i == 3 else [(32, 24)])


def quarry_echo(surface, c, i):
    if i <= 1:
        segments(surface, c[3], [(28-i*3, 45), (36+i*3, 45)])
    if i in (1, 2):
        pygame.draw.polygon(surface, c[2], [(24, 44), (29, 36), (33, 44), (37, 40), (40, 45)])
        dots(surface, c[0], [(30, 39), (40+2*i, 35-i*3), (25, 35)])
    if i in (2, 3):
        reach = 14 + (i-2)*7
        segments(surface, c[2], [(32-reach, 43), (28-reach, 46), (38+reach, 46), (41+reach, 43)])
        segments(surface, c[3], [(32-reach, 41), (39-reach, 40)])
    if i >= 3:
        dots(surface, c[3], [(45, 28), (22, 33)] if i == 3 else [(43, 31)])


def thrown_blade(surface, c, i):
    if i <= 2:
        pygame.draw.polygon(surface, c[0], [(24, 32), (35, 29), (35, 34), (28, 34)])
        pygame.draw.line(surface, c[2], (27, 33), (35, 33))
        pygame.draw.line(surface, c[1], (35, 28), (35, 36))
        pygame.draw.line(surface, c[3], (36, 32), (39, 32), 2)
        for j in range(i):
            segments(surface, c[2+j], [(42+6*j, 31+j*2), (45+6*j, 31+j*2)])
    elif i == 3:
        cross(surface, c, 32, 32, 13)
        dots(surface, c[1], [(26, 26), (38, 26), (26, 38), (38, 38)])
    else:
        dots(surface, c[3], [(24, 27), (27, 39), (40, 25), (43, 36)])


def blunt_impact(surface, c, i):
    if i == 0:
        return
    if i in (1, 2):
        # One compact half arc with a stair step edge.
        for j in range(4):
            pygame.draw.arc(surface, c[j], (14+j, 13+j, 36-2*j, 39-2*j),
                            0.15 if i == 2 else 1.5, 2.2 if i == 2 else 2.95)
        return
    if i == 3:
        segments(surface, c[1], [(15, 40), (25, 42), (41, 42), (49, 40)], 2)
        pygame.draw.polygon(surface, c[0], [(26, 41), (30, 36), (32, 24), (35, 38), (40, 41)])
        segments(surface, c[2], [(22, 39), (20, 34)])
        segments(surface, c[2], [(40, 38), (44, 33)])
    else:
        dots(surface, c[3], [(18, 36), (24, 32), (36, 39), (46, 35)])


def wand_bolt(surface, c, i):
    if i <= 2:
        cross(surface, c, 30, 32, 4)
        for j in range(i+1):
            segments(surface, c[min(2+j, 4)], [(35+j*6, 32), (37+j*6, 32)])
    elif i == 3:
        cross(surface, c, 32, 32, 11)
    else:
        dots(surface, c[3], [(24, 30), (30, 39), (38, 26)])


def focus_pulse(surface, c, i):
    if i <= 2:
        radius = (11, 7, 3)[i]
        pygame.draw.circle(surface, c[1], (32, 32), radius, 1)
        dots(surface, c[0], [(32, 32-radius+1), (32+radius-1, 32)])
    elif i == 3:
        cross(surface, c, 32, 32, 13)
        for dx, dy in ((-1,-1), (1,-1), (-1,1), (1,1)):
            segments(surface, c[2], [(32+dx*5, 32+dy*5), (32+dx*9, 32+dy*9)])
    else:
        dots(surface, c[3], [(22, 30), (34, 41), (40, 34)])


EFFECTS = {
    "unbound_quick_cut": (quick_cut, (60, 50, 75, 70, 90), 0, None),
    "unbound_first_aid": (first_aid, (95, 90, 100, 110, 100), 0,
                          ("#f4fff0", "#c8ddb1", "#8fb194", "#637950", "#394734")),
    "unbound_spark": (spark, (55, 60, 65, 80, 90), 0,
                       ("#fff5d0", "#ffce76", "#db9b46", "#93562b", "#593b24")),
    "unbound_quarry_echo": (quarry_echo, (80, 70, 85, 95, 100), 0,
                             ("#f5ede0", "#c5b5a2", "#989087", "#746962", "#4a4038")),
    "thrown_blade": (thrown_blade, (50, 48, 48, 75, 100), 146, None),
    "blunt_impact": (blunt_impact, (70, 60, 65, 95, 110), 0, None),
    "wand_bolt": (wand_bolt, (55, 55, 48, 70, 90), 158, None),
    "focus_pulse": (focus_pulse, (75, 65, 55, 80, 95), 0, None),
}


def prepare():
    stone_colors = json.loads((FX / "stones.json").read_text(encoding="utf-8"))
    colors_by_stone = {key: tuple(ramp.values())
                       for key, ramp in stone_colors.items() if key in ("unattuned", "first_stone")}
    manifest = {}
    for key, (draw, timings, travel_ms, fixed) in EFFECTS.items():
        manifest[key] = {}
        palettes = {"untinted": fixed} if fixed is not None else colors_by_stone
        for stone, palette in palettes.items():
            base = FX / "approved_attacks" / key / stone
            frames = base / "frames"
            frames.mkdir(parents=True, exist_ok=True)
            colors = tuple(pygame.Color(rgb) for rgb in palette)
            for i in range(len(timings)):
                image = pygame.Surface((SIZE, SIZE), pygame.SRCALPHA)
                draw(image, colors, i)
                pygame.image.save(image, frames / f"{i:02d}.png")
            metadata = {
                "frames": len(timings), "ms_per_frame": timings, "total_ms": sum(timings),
                "frame_w": SIZE, "frame_h": SIZE, "target_center": [32, 32],
                "scale_in_battle": 2, "travel_ms": travel_ms,
                "contact_ms": sum(timings[:3]) if key in
                ("thrown_blade", "blunt_impact", "wand_bolt", "focus_pulse") else 0,
            }
            path = base / "effect.json"
            path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
            manifest[key][stone] = {"json": path.relative_to(FX).as_posix(),
                                    "frames_dir": frames.relative_to(FX).as_posix()}
    path = FX / "approved_attacks" / "manifest.json"
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    prepare()
