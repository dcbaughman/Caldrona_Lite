"""Build the 1x player motion sheets from the approved costumes (requires Pillow)."""

from dataclasses import dataclass, replace
from math import hypot
from pathlib import Path

from PIL import Image, ImageDraw

from arrow_fx import DRAW_HAND, NOCKED_TIP, arrow_parts
from player_motion import CAST_STYLES, CELL_H, CELL_W, PAD_X, STYLES
from prepare_class_skins import NEW_COSTUMES, insignia


ROOT = Path(__file__).resolve().parent / "assets"
INK = "#17131b"
BOOTS = ("#613932", "#a46a4a")
RIGID_LENGTHS = {"sword": 14, "greatsword": 22, "pike": 24, "halberd": 20}
TWO_HANDS = {"greatsword": 6, "pike": 10, "halberd": 8}

# Dark, mid, highlight, and trim for each of the existing outfits.
COSTUMES = {
    ("retri", "unbound"): ("#242338", "#314b6d", "#537da5", "#dc923c"),
    ("retri", "seer"): ("#24234a", "#484c99", "#7685c8", "#63d9fc"),
    ("retri", "sollers"): ("#222234", "#3d4153", "#626273", "#9c6949"),
    ("retri", "saint"): ("#3e3940", "#81777f", "#d1c0a7", "#e4aa53"),
    ("temur", "unbound"): ("#20233a", "#344776", "#657bb1", "#ad5848"),
    ("temur", "seer"): ("#282248", "#534c91", "#8b80bd", "#8dd6f0"),
    ("temur", "sollers"): ("#222130", "#414051", "#6d5d63", "#9a6a4b"),
    ("temur", "saint"): ("#39343b", "#827670", "#cab9a4", "#e0a24d"),
    **{(character, job): palette for character in ("retri", "temur")
       for job, palette in NEW_COSTUMES.items()},
}
SKIN = {"retri": ("#6c3c2e", "#b27749", "#efb779"),
        "temur": ("#644138", "#a86b52", "#f3bd88")}


@dataclass(frozen=True)
class Pose:
    head: tuple
    shoulder: tuple
    waist: tuple
    lead_arm: tuple
    back_arm: tuple
    lead_leg: tuple
    back_leg: tuple


READY = Pose((0, 0), (25, 17), (25, 24), ((22, 20), (18, 20)), ((28, 20), (26, 23)),
             ((22, 27), (20, 31)), ((28, 27), (30, 31)))
DRAW_BACK = Pose((2, 0), (27, 17), (27, 23), ((29, 20), (32, 14)), ((24, 20), (22, 18)),
                 ((23, 27), (20, 31)), ((30, 27), (32, 31)))
OVERHEAD = Pose((1, -1), (26, 16), (27, 23), ((28, 13), (27, 9)), ((23, 18), (23, 14)),
                ((23, 26), (20, 31)), ((30, 27), (31, 31)))
LOW_DRAW = Pose((2, 1), (27, 18), (26, 24), ((31, 20), (30, 24)), ((24, 19), (21, 18)),
                ((22, 27), (19, 31)), ((30, 27), (32, 31)))
HIGH_CUT = Pose((-4, 1), (21, 18), (24, 24), ((17, 17), (13, 15)), ((24, 21), (23, 23)),
                ((19, 26), (17, 31)), ((28, 27), (31, 31)))
THRUST = Pose((-4, 1), (21, 18), (24, 23), ((16, 20), (12, 19)), ((27, 20), (27, 23)),
              ((19, 26), (17, 31)), ((28, 27), (31, 31)))
FOLLOW = Pose((-5, 4), (20, 21), (24, 25), ((17, 24), (13, 25)), ((24, 23), (24, 19)),
              ((19, 27), (17, 31)), ((28, 28), (31, 31)))
SLAM = Pose((-4, 3), (21, 20), (24, 25), ((17, 22), (14, 23)), ((22, 20), (17, 21)),
            ((19, 27), (17, 31)), ((28, 28), (31, 31)))
GUARD = Pose((0, 1), (24, 18), (25, 24), ((19, 20), (17, 16)), ((27, 21), (23, 18)),
             ((21, 27), (19, 31)), ((28, 27), (29, 31)))
COIL = Pose((1, 2), (25, 19), (27, 24), ((28, 20), (29, 22)), ((22, 20), (19, 17)),
            ((23, 27), (20, 31)), ((29, 27), (31, 31)))
CROSS = Pose((-5, 2), (20, 19), (23, 24), ((17, 20), (14, 16)), ((23, 22), (21, 23)),
             ((18, 26), (17, 31)), ((27, 27), (30, 31)))
CAST = Pose((0, 0), (25, 17), (25, 24), ((21, 20), (17, 19)), ((28, 19), (27, 22)),
            ((22, 27), (20, 31)), ((28, 27), (30, 31)))
CAST_HOLD = Pose((-1, 0), (24, 17), (25, 24), ((19, 19), (15, 18)), ((27, 20), (26, 22)),
                 ((22, 27), (20, 31)), ((28, 27), (30, 31)))
CAST_RELEASE = Pose((-2, 0), (23, 17), (25, 24), ((18, 19), (12, 17)), ((27, 20), (26, 22)),
                    ((22, 27), (20, 31)), ((28, 27), (30, 31)))
KNEEL = Pose((-3, 8), (22, 24), (25, 28), ((20, 26), (18, 27)), ((26, 26), (26, 28)),
             ((19, 27), (17, 31)), ((25, 31), (30, 31)))

BOW_READY = replace(READY, lead_arm=((18, 19), (13, 18)), back_arm=((27, 22), (22, 19)))
BOW_DRAW = replace(READY, head=(1, 0), shoulder=(26, 17),
                   lead_arm=((16, 18), (12, 17)), back_arm=((30, 19), DRAW_HAND))
BOW_RELEASE = replace(BOW_DRAW, back_arm=((30, 19), (28, 16)))
BOW_LOWER = replace(READY, lead_arm=((18, 21), (14, 20)), back_arm=((28, 21), (25, 22)))

# For rigid weapons these vectors set the angle around the gripping hand.
# The weapon length is defined separately from the poses.
SWINGS = {
    "sword": ((READY, (-8, -9)), (DRAW_BACK, (10, -12)), (HIGH_CUT, (-11, -7)),
              (FOLLOW, (-12, 2)), (READY, (-9, 5))),
    "greatsword": ((replace(READY, lead_arm=((22, 19), (20, 20))), (-7, -8)),
                   (DRAW_BACK, (11, -5)),
                   (replace(HIGH_CUT, lead_arm=((18, 17), (14, 17))), (-13, -3)),
                   (replace(FOLLOW, lead_arm=((17, 23), (15, 24))), (-14, 2)),
                   (READY, (-12, 4))),
    "pike": ((replace(READY, lead_arm=((24, 20), (21, 20))), (-13, -7)),
             (replace(LOW_DRAW, head=(3, 1), lead_arm=((30, 19), (31, 19))), (-16, -2)),
             (THRUST, (-24, 0)),
             (replace(THRUST, head=(-2, 1), lead_arm=((18, 21), (15, 21))), (-19, 2)),
             (READY, (-15, -2))),
    "halberd": ((READY, (-7, -10)), (DRAW_BACK, (12, -7)), (HIGH_CUT, (-20, -1)),
                (SLAM, (-18, 1)), (READY, (-13, 1))),
    "bow": tuple((pose, None) for pose in (BOW_READY, BOW_DRAW, BOW_RELEASE, BOW_LOWER, BOW_READY)),
    "whip": (
        (READY, ((0, 0), (-4, 1), (-7, 4), (-7, 8), (-4, 10), (1, 9), (3, 6), (1, 4))),
        (DRAW_BACK, ((0, 0), (4, -5), (9, -8), (14, -8), (17, -5),
                     (18, 0), (14, 4), (9, 3), (7, 1))),
        (THRUST, ((0, 0), (-5, -3), (-10, -5), (-15, -5), (-20, -3),
                  (-23, -3), (-25, -5))),
        (FOLLOW, ((0, 0), (-5, 3), (-11, 5), (-17, 4), (-21, 0), (-20, -5), (-16, -7))),
        (READY, ((0, 0), (-5, 1), (-8, 5), (-6, 8), (-1, 9), (2, 7), (0, 4))),
    ),
    "dagger": ((READY, (-5, -4)), (LOW_DRAW, (6, 3)), (THRUST, (-7, 0)),
               (FOLLOW, (-6, 4)), (READY, (-5, 3))),
    "mace": ((READY, (-6, -6)), (OVERHEAD, (8, -4)), (HIGH_CUT, (-8, -3)),
             (SLAM, (-6, 6)), (READY, (-5, 5))),
    "staff": ((READY, (-5, -12)), (DRAW_BACK, (8, -11)), (THRUST, (-9, -4)),
              (SLAM, (-12, 4)), (READY, (-6, 7))),
    "rod": ((READY, (-4, -7)), (DRAW_BACK, (6, -8)), (HIGH_CUT, (-9, -2)),
            (FOLLOW, (-8, 2)), (READY, (-5, 4))),
    "throw": ((GUARD, (-5, -3)), (DRAW_BACK, (4, -5)), (THRUST, None),
              (FOLLOW, None), (GUARD, None)),
    "fists": tuple((pose, None) for pose in (GUARD, COIL, THRUST, CROSS, GUARD)),
}


def line(draw, points, colors, width):
    dark, base, light = colors
    draw.line(points, fill=INK, width=width + 2)
    draw.line(points, fill=dark, width=width)
    draw.line(points, fill=base, width=max(1, width - 1))
    (x, y), (ex, ey) = points[0], points[1]
    draw.point((round((x+ex)/2), round((y+ey)/2)-1), fill=light)


def armor(draw, source, pose, palette, job):
    sx, sy = pose.shoulder
    wx, wy = pose.waist
    dark, mid, light, trim = palette
    draw.polygon(((sx-4, sy-1), (sx+2, sy-2), (sx+4, sy+1),
                  (wx+3, wy+2), (wx-4, wy+2), (sx-5, sy+2)),
                 fill=dark, outline=INK)
    draw.polygon(((sx-3, sy), (sx+2, sy), (wx+2, wy), (wx-3, wy)),
                 fill=mid)
    # Carry the original breastplate and sash pixels across the shift of the torso.
    for y in range(14, 20):
        t = (y - 14) / 5
        row = round(sy + (wy - sy) * t)
        shift = round(sx + (wx - sx) * t) - 16
        for x in range(14, 19):
            color = source.getpixel((x, y))
            if color[3] > 127:
                draw.point((x + shift, row), fill=color)
    draw.line(((wx-3, wy), (wx+2, wy)), fill=dark, width=2)
    draw.point((wx-1, wy), fill=trim)
    draw.line(((sx+1, sy-1), (sx+3, sy+1)), fill=light)
    if job in NEW_COSTUMES:
        draw.point(insignia(job, (sx+wx)//2, (sy+wy)//2), fill=trim)


def limb(draw, shoulder, arm, palette, front):
    elbow, hand = arm
    x, y = shoulder
    arm_root = (x-2, y+1) if front else (x+2, y+1)
    line(draw, (arm_root, elbow, hand), palette[:3] if front else (palette[0], palette[1], palette[1]), 3)
    return hand


def grip(draw, point, skin, open_hand=False):
    x, y = point
    if open_hand:
        draw.line(((x-2,y-1), (x+1,y+1)), fill=INK, width=3)
        draw.line(((x-2,y-1), (x,y)), fill=skin[1])
        draw.point((x-2,y-1), fill=skin[2])
    else:
        draw.rectangle((x-1, y-1, x+2, y+2), fill=INK)
        draw.point((x, y), fill=skin[2])
        draw.line(((x+1,y), (x+1,y+1)), fill=skin[1])


def bow(draw, hand, rear_hand, drawn):
    x, y = hand
    limb = [(x+dx, y+dy) for dx, dy in
            ((5,-11), (2,-10), (-1,-6), (-1,-3), (-1,3), (-1,6), (2,10), (5,11))]
    nock = rear_hand if drawn else (x+5, y)
    draw.line((limb[0], nock, limb[-1]), fill="#b4bcc8")
    draw.line(limb, fill=INK, width=3)
    draw.line(limb, fill="#a96537", width=2)
    draw.line(limb[1:4], fill="#eab971")
    draw.line(limb[4:7], fill="#ce8b49")
    for point in (limb[0], limb[-1]):
        draw.point(point, fill="#efd496")
    if drawn:
        for color, points in arrow_parts((NOCKED_TIP[0] + PAD_X, NOCKED_TIP[1]), (-1, 0)):
            draw.polygon(points, fill=color)


def weapon(draw, hand, vector, style):
    x, y = hand
    if style == "cast_orb":
        gem = (x-4, y-4)
        gx, gy = gem
        draw.polygon(((gx, gy-4), (gx+3, gy-1), (gx+3, gy+2),
                      (gx, gy+4), (gx-4, gy+1), (gx-4, gy-1)), fill="#46396e", outline=INK)
        draw.line(((gx-2, gy-1), (gx, gy-3), (gx+2, gy-1)), fill="#a5c7f3")
        draw.point((gx-1, gy+1), fill="#6e84bd")
        return gem
    if vector is None:
        return hand
    if style == "whip":
        cord = [(x+dx, y+dy) for dx, dy in vector]
        draw.line(cord, fill=INK, width=2)
        draw.line(cord, fill="#b3754b")
        draw.line(cord[1:4], fill="#deaa6e")
        draw.line(cord[-2:], fill="#f1cc94")
        draw.rectangle((x-2, y-1, x+2, y+2), fill="#553432", outline=INK)
        return cord[-1]
    dx, dy = vector
    distance = hypot(dx, dy)
    ux, uy = dx / distance, dy / distance
    cross = -uy, ux

    def point(along, across=0):
        return (round(x+ux*along+cross[0]*across),
                round(y+uy*along+cross[1]*across))

    length = RIGID_LENGTHS.get(style, distance)
    tip = point(length)
    if style in ("sword", "greatsword", "dagger", "throw"):
        heavy = style == "greatsword"
        width = 3.1 if heavy else 2 if style == "sword" else 1.45
        taper = 5 if heavy else 3
        draw.line((point(-8 if heavy else -3), point(3)), fill=INK, width=3)
        draw.line((point(-7 if heavy else -2), point(2)), fill="#a86c41")
        edge = [point(2, width), point(length-taper, width), tip]
        if heavy:
            edge.append(point(length-taper, -width))
        edge.append(point(2, -width))
        draw.polygon(edge, fill="#8496ae", outline=INK)
        if heavy:
            draw.line((point(5, .8), point(length-5, .8)), fill="#566379")
        draw.line((point(3, -1 if heavy else 0), point(length-taper, -.6 if heavy else .2), tip),
                  fill="#d2e1e5")
        draw.line((point(2,-width-1), point(2,width+1)), fill="#ca9653")
    elif style in ("pike", "halberd"):
        butt = point(-14 if style == "pike" else -12)
        neck = point(length-5)
        draw.line((butt, neck), fill=INK, width=3)
        draw.line((butt, neck), fill="#ac7950")
        draw.line((point(length-7), point(length-3)), fill="#d1a369", width=2)
        if style == "halberd":
            axe = (point(length-8, 1), point(length-8, 4), point(length-12, 6),
                   point(length-9, 7), point(length-4, 6), point(length-3, 3),
                   point(length-3, 0), point(length-5, -3), point(length-9, -4),
                   point(length-7, -1))
            draw.polygon(axe, fill="#788a9e", outline=INK)
            draw.line(axe[2:6], fill="#d4e9ec")
        draw.polygon((tip, point(length-6, 2), point(length-9, 0), point(length-6, -2)),
                     fill="#859aaf", outline=INK)
        draw.line((point(length-6), tip), fill="#d8eaed")
    else:
        long = style in ("staff", "cast_staff")
        butt = point(-10 if long else -3)
        draw.line((butt, tip), fill=INK, width=3)
        draw.line((butt, tip), fill="#825743")
        draw.line((point(2), tip), fill="#bc8e64")
        if style == "mace":
            draw.polygon((point(length-3, -3), point(length+2, -2), point(length+3, 1),
                          point(length, 4), point(length-4, 2)), fill="#8996ad", outline=INK)
            draw.line((point(length-2,-2), point(length+1,-1)), fill="#dbdbdc")
        elif style in CAST_STYLES:
            draw.polygon((point(length-3,-2), point(length-1,-3), point(length+2),
                          point(length-1,2)), fill="#67a4ce", outline=INK)
            draw.point(tip, fill="#dbf2f7")
        else:
            draw.line((point(length-2,-1), point(length-1,1)), fill="#d7a562")
    return tip


def glimmer(draw, spot, size):
    x, y = spot
    draw.line(((x-size, y), (x+size, y)), fill="#77cddb")
    draw.line(((x, y-size), (x, y+size)), fill="#adf5ec")
    draw.point((x, y), fill="#fcfff1")
    if size >= 3:
        draw.point((x-5, y-3), fill="#a9e8f1")
        draw.point((x+4, y+3), fill="#537da5")


def actor_frame(source, head, character, job, pose, style, vector, column=0, spark=0):
    image = Image.new("RGBA", (CELL_W, CELL_H))
    draw = ImageDraw.Draw(image)
    palette, skin = COSTUMES[(character, job)], SKIN[character]

    def pad(point):
        return point[0] + PAD_X, point[1]

    pose = replace(pose, shoulder=pad(pose.shoulder), waist=pad(pose.waist),
                   lead_arm=tuple(map(pad, pose.lead_arm)), back_arm=tuple(map(pad, pose.back_arm)),
                   lead_leg=tuple(map(pad, pose.lead_leg)), back_leg=tuple(map(pad, pose.back_leg)))
    if style in TWO_HANDS:
        hx, hy = pose.lead_arm[-1]
        dx, dy = vector
        ratio = TWO_HANDS[style] / hypot(dx, dy)
        back_hand = (round(hx - dx*ratio), round(hy - dy*ratio))
        pose = replace(pose, back_arm=(pose.back_arm[0], back_hand))
    wx, wy = pose.waist
    for side, (knee, foot) in ((1, pose.back_leg), (-1, pose.lead_leg)):
        line(draw, ((wx+side*2, wy+1), knee, foot), palette[:3], 3)
        fx, fy = foot
        draw.rectangle((fx-3, fy-1, fx+1, fy), fill=INK)
        draw.line(((fx-2, fy-1), (fx, fy-1)), fill=BOOTS[0])
        draw.point((fx-2, fy-1), fill=BOOTS[1])
    back = limb(draw, pose.shoulder, pose.back_arm, palette, front=False)
    grip(draw, back, skin)
    armor(draw, source, pose, palette, job)
    hx, hy = pose.head
    image.alpha_composite(head, (8+PAD_X+hx, 4+hy))
    hand = limb(draw, pose.shoulder, pose.lead_arm, palette, front=True)
    tip = hand
    if style == "bow":
        bow(draw, hand, back, column == 1)
    else:
        tip = weapon(draw, hand, vector, style)
    if style in TWO_HANDS or (style == "bow" and column == 1):
        grip(draw, back, skin)
    grip(draw, hand, skin, open_hand=style == "cast_hand" or (style == "throw" and vector is None))
    if spark:
        glimmer(draw, tip if style != "cast_hand" else (hand[0]-3, hand[1]-1), spark)
    draw.rectangle((0, 32, CELL_W-1, CELL_H-1), fill=(0, 0, 0, 0))
    return image


def make_battle_sheets(jobs=None):
    battle = ROOT / "battle"
    output = battle / "player-motion"
    output.mkdir(exist_ok=True)
    for character, job in COSTUMES:
        if jobs is not None and job not in jobs:
            continue
        path = (battle / f"{character}-v2.png" if job == "unbound"
                else battle / "classes" / f"{character}-{job}.png")
        source = Image.open(path).convert("RGBA")
        head = source.crop((0, 0, 32, 14 if character == "temur" else 13))
        cut = ImageDraw.Draw(head)
        if character == "temur":
            cut.rectangle((16, 13, 31, 13), fill=(0, 0, 0, 0))
        else:
            cut.rectangle((17, 12, 31, 12), fill=(0, 0, 0, 0))
        atlas = Image.new("RGBA", (5*CELL_W, len(STYLES)*CELL_H))
        for row, style in enumerate(STYLES):
            if style == "critical":
                poses = ((KNEEL, None),)
            elif style in CAST_STYLES:
                aim = {"cast_hand": None, "cast_wand": (-8,-3), "cast_staff": (-3,-12),
                       "cast_orb": None}[style]
                poses = tuple((p, aim) for p in (CAST, CAST_HOLD, CAST_RELEASE, CAST_HOLD, CAST))
            else:
                poses = SWINGS[style]
            for col, (pose, vector) in enumerate(poses):
                spark = (1, 3, 2, 0, 0)[col] if style in CAST_STYLES else 0
                frame = actor_frame(source, head, character, job, pose, style, vector, col, spark)
                assert frame.getbbox()[0] > 0 and frame.getbbox()[2] < CELL_W, (character, style, col)
                atlas.alpha_composite(frame, (col*CELL_W, row*CELL_H))
        atlas.save(output / f"{character}-{job}.png")


def make_temur_walk():
    names = ("temur-world-v4.png", "mine-polish/temur-left.png",
             "mine-polish/temur-right.png", "mine-polish/temur-up.png")
    atlas = Image.new("RGBA", (48, 64))
    for row, name in enumerate(names):
        source = Image.open(ROOT / name).convert("RGBA")
        idle = Image.new("RGBA", (16, 16))
        idle.alpha_composite(source, (0, 15-source.getbbox()[3]))
        atlas.alpha_composite(idle, (16, row*16))
        for col, x0 in ((0, 0), (2, 8)):
            # Alternate the lifted boot while keeping its top row joined to
            # the original knee. Side views extend the planted toe one pixel.
            step = idle.copy()
            lifted = idle.crop((x0, 13, x0+8, 15))
            ImageDraw.Draw(step).rectangle((x0, 13, x0+7, 14), fill=(0, 0, 0, 0))
            step.alpha_composite(lifted, (x0, 12))
            if row in (1, 2):
                other = idle.crop((8-x0, 13, 16-x0, 15))
                step.alpha_composite(other, (8-x0 + (-1 if row == 1 else 1), 13))
            atlas.alpha_composite(step, (col*16, row*16))
    atlas.save(ROOT / "temur-overworld.png")


if __name__ == "__main__":
    make_battle_sheets()
    make_temur_walk()
