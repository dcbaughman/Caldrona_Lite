"""Build native-pixel class costumes from the approved character poses."""

from pathlib import Path

from PIL import Image, ImageColor

from classes import OUTFIT_JOBS


ASSETS = Path(__file__).resolve().parent / "assets"
CLASS_ART = ASSETS / "battle" / "classes"
# Shadow, cloth, lit fold, and hardware/thread.
NEW_COSTUMES = {
    "weaver": ("#241b36", "#594171", "#9b79b7", "#dccfe6"),
    "riqizaurkeis": ("#24222c", "#45404d", "#817886", "#cb9768"),
    "tidecaller": ("#112e39", "#26717b", "#62aeb0", "#bce0ce"),
}
FIELD_COSTUMES = {
    "seer": ("#21153f", "#494ca0", "#827bc6", "#68dcf0"),
    "sollers": ("#211e2a", "#3e3949", "#716073", "#b39069"),
    "saint": ("#453739", "#a6907c", "#ead9bc", "#e4aa53"),
    **NEW_COSTUMES,
}
POSES = {
    # Minimum clothing row (minimum column for a prone figure), centre of chest,
    # and shoulder panel on each approved pose. The head pixels stay intact.
    "retri": {"": (13, 0, (16, 16), (19, 15)), "guard": (14, 0, (17, 18), (19, 16)),
              "fainted": (17, 16, (19, 20), (21, 18))},
    "temur": {"": (14, 0, (16, 18), (19, 15)), "guard": (14, 0, (16, 19), (19, 17)),
              "fainted": (16, 13, (16, 19), (21, 18))},
}


def insignia(job, x, y):
    """Tiny stitch patterns shared by idle, walking, and wielding poses."""
    if job == "weaver":
        return ((x-1, y+1), (x, y), (x+1, y-1))
    if job == "riqizaurkeis":
        return ((x, y-1), (x-1, y), (x+1, y), (x, y+1))
    if job == "tidecaller":
        return ((x-1, y), (x, y+1), (x+1, y+1))
    return ((x, y),)


def shade(palette, low, high, amount):
    return tuple(round(a + (b-a) * amount) for a, b in zip(palette[low], palette[high]))


def dyed_fabric(pixel, palette):
    r, g, b, alpha = pixel
    level = max(r, g, b)
    if level < 32:
        return pixel
    if level < 105:
        rgb = shade(palette, 0, 1, (level-32) / 73)
    elif level < 190:
        rgb = shade(palette, 1, 2, (level-105) / 85)
    else:
        rgb = shade(palette, 2, 3, min(.67, (level-190) / 97))
    return (*rgb, alpha)


def draw_battle_costume(source, name, job, pose):
    palette = tuple(ImageColor.getrgb(hex_code) for hex_code in NEW_COSTUMES[job])
    top, left, chest, shoulder = POSES[name][pose]
    result = source.copy()

    for y in range(top, 25 if pose != "fainted" else 24):
        for x in range(left, 32):
            pixel = source.getpixel((x, y))
            r, g, b, alpha = pixel
            if not alpha or (pose != "fainted" and y < 19 and x < 13):
                continue
            color = dyed_fabric(pixel, palette)
            # Retain the brown edge of the belt, and keep the new mantle
            # fitted to the existing silhouette rather than enlarging it.
            if y in (18, 19) and r > g * 1.27 and g > b and x < 14:
                continue
            result.putpixel((x, y), color)

    x, y = shoulder
    panels = {
        "weaver": ((x-1, y), (x, y), (x+1, y+1), (x+2, y+2)),
        "riqizaurkeis": ((x-1, y), (x, y-1), (x+1, y-1), (x+2, y), (x, y+1), (x+1, y+1)),
        "tidecaller": ((x-1, y), (x, y), (x+1, y), (x+2, y+1), (x+1, y+2)),
    }
    for points, ink in ((panels[job], palette[2]), (insignia(job, *chest), palette[3])):
        for point in points:
            if point[1] >= top and source.getpixel(point)[3] > 127:
                result.putpixel(point, (*ink, 255))
    return result


def draw_field_costume(atlas, name, job):
    palette = tuple(ImageColor.getrgb(hex_code) for hex_code in FIELD_COSTUMES[job])
    cell = atlas.width // 3
    step = cell // 16
    result = Image.new("RGBA", (48, 64))
    for row in range(4):
        for frame in range(3):
            tile = Image.new("RGBA", (16, 16))
            thread_row = 10 if name == "Temur" else 9
            seam = 9 if row == 1 else 7
            stitches = set(insignia(job, seam, thread_row))
            for y in range(16):
                for x in range(16):
                    pixel = atlas.getpixel((frame*cell + x*step, row*cell + y*step))
                    if pixel[3] and thread_row-1 <= y <= 12:
                        if (x, y) in stitches:
                            pixel = (*palette[3], 255)
                        elif y >= thread_row or 6 <= x <= 9:
                            pixel = dyed_fabric(pixel, palette)
                    tile.putpixel((x, y), pixel)
            result.paste(tile, (frame*16, row*16))
    return result


def prepare():
    for name in ("Retri", "Temur"):
        character = name.lower()
        pose_files = {"": f"{character}-v2.png", "guard": f"{character}-guard.png",
                      "fainted": "retri-fainted-v2.png" if name == "Retri" else "temur-fainted-v1.png"}
        for pose, filename in pose_files.items():
            source = Image.open(ASSETS / "battle" / filename).convert("RGBA")
            for job in NEW_COSTUMES:
                suffix = f"-{pose}" if pose else ""
                costume = draw_battle_costume(source, character, job, pose)
                assert costume.getchannel("A").getbbox() == source.getchannel("A").getbbox()
                costume.save(CLASS_ART / f"{character}-{job}{suffix}.png")
        field = Image.open(ASSETS / f"{character}-overworld.png").convert("RGBA")
        for job in OUTFIT_JOBS:
            draw_field_costume(field, name, job.lower()).save(CLASS_ART / f"{character}-{job.lower()}-overworld.png")


if __name__ == "__main__":
    prepare()
