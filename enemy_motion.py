"""Native-pixel enemy motion shared by combat and the title-screen preview."""

from dataclasses import dataclass
from math import pi, sin
import tkinter as tk


TICKS_PER_SECOND = 12
OUTLINE = "#08070b"
BROOD_SHADE_STEPS = 10


@dataclass(frozen=True)
class EnemyMotion:
    label: str
    rest_ticks: int
    offsets: tuple[tuple[int, int], ...]
    atlas: str | None = None
    poses: tuple[int, ...] = ()
    pose_fps: int | None = None
    ticks_per_second: int = TICKS_PER_SECOND


MOTIONS = {
    "spider.png": EnemyMotion(
        "Alternating leg twitch", 19, ((0, 0), (1, 0), (2, -1), (1, 0), (-1, 0)),
        "spider-stride.png", (0, 1, 2, 3, 0),
    ),
    "hollow-weaver.png": EnemyMotion(
        "Measured leg taps", 25, ((0, 0), (1, -1), (1, -2), (0, -1), (-1, 0)),
        "hollow-weaver-stride.png", (0, 1, 1, 2, 3),
    ),
    "brood-stalker.png": EnemyMotion(
        "Braced lunge", 23, ((0, 0), (-1, 1), (-2, 2), (3, -1), (1, 0)),
        "brood-stalker-stride.png", (0, 1, 2, 3, 0), ticks_per_second=10,
    ),
    "spiderling.png": EnemyMotion(
        "Quick scuttle", 15, ((0, 0), (1, 0), (2, -1), (-1, 0), (0, 0)),
        "spiderling-stride.png", (0, 1, 2, 3, 0), ticks_per_second=16,
    ),
    "bat.png": EnemyMotion(
        "Wing flutter", 12, ((0, 0), (0, -3), (1, -6), (1, -4), (0, -1), (-1, -3)),
        "bat-wings.png", (0, 1, 0, 2, 3, 2), pose_fps=12,
    ),
    "crawler.png": EnemyMotion(
        "Scuttle and horn dip", 24, ((0, 0), (-1, 0), (2, -1), (2, 0), (1, 0)),
        "crawler-stride.png", (0, 1, 2, 3, 0),
    ),
    "cinder-hornet.png": EnemyMotion(
        "Wing buzz", 9, ((0, 0), (2, -2), (-2, -3), (2, -4), (-1, -2), (1, -1)),
        "cinder-hornet-wings.png", (0, 1, 0, 2, 3, 2), pose_fps=24,
    ),
    "ashmane-wolf.png": EnemyMotion(
        "Prowling feint", 19, ((0, 0), (-2, 1), (-2, 2), (3, -1), (2, 0), (1, 0)),
        "ashmane-wolf-prowl.png", (0, 1, 2, 3, 2, 0),
    ),
    "torshield-ram.png": EnemyMotion(
        "Hoof stamp", 22, ((0, 0), (-1, -1), (-1, -3), (2, 1), (1, 0)),
        "torshield-ram-stride.png", (0, 1, 2, 3, 0), ticks_per_second=8,
    ),
    "emberwraith.png": EnemyMotion(
        "Ground-level ooze", 6, ((0, 0), (-1, 0), (2, 0), (4, 0), (3, 0), (1, 0), (0, 0)),
        "emberwraith-ooze.png", (0, 1, 2, 3, 4, 5, 0), ticks_per_second=9,
    ),
    "silk-sarcophagus.png": EnemyMotion("Silk drift", 0, ()),
    "den-mother.png": EnemyMotion(
        "Leg twitch and Last Brood", 22, ((0, 0), (-1, 0), (-2, -1), (-2, -2), (1, 0), (1, 1)),
        "den-mother-stride.png", (0, 1, 2, 3, 2, 0), ticks_per_second=10,
    ),
    "shalehorn.png": EnemyMotion("Shale shudder", 29, ((0, 0), (-2, 0), (2, -1), (-1, 0), (1, 1))),
    "ember-wyvern.png": EnemyMotion("Coil shift", 21, ((0, 0), (-1, 0), (-3, 0), (3, 0), (1, 0))),
}


def idle_duration(foe):
    if foe.sprite_bob:
        return 2 * pi / 1.5
    motion = MOTIONS[foe.sprite]
    return (len(motion.offsets) + motion.rest_ticks) / motion.ticks_per_second


def idle_offset(foe, elapsed):
    if foe.sprite_bob:
        return round(sin(elapsed * 1.5)), round(foe.sprite_bob * sin(elapsed * 3))
    motion = MOTIONS[foe.sprite]
    tick = int(elapsed * motion.ticks_per_second) % (len(motion.offsets) + motion.rest_ticks)
    return motion.offsets[tick] if tick < len(motion.offsets) else (0, 0)


def load_enemy_sprite(master, folder, foe):
    sprite = tk.PhotoImage(master=master, file=str(folder / foe.sprite))
    return _finish_enemy_sprite(master, sprite, foe)


def load_enemy_frames(master, folder, foe):
    base = load_enemy_sprite(master, folder, foe)
    motion = MOTIONS[foe.sprite]
    if motion.atlas is None:
        return (base,)
    atlas = tk.PhotoImage(master=master, file=str(folder / motion.atlas))
    count = max(motion.poses)
    return (base, *_read_atlas_row(master, atlas, foe, count, 0, atlas.height()))


def _read_atlas_row(master, atlas, foe, count, top, height):
    width = atlas.width() // count
    frames = []
    for i in range(count):
        sprite = tk.PhotoImage(master=master, width=width, height=height)
        sprite.tk.call(sprite, "copy", atlas, "-from", i * width, top, (i + 1) * width, top + height)
        frames.append(_finish_enemy_sprite(master, sprite, foe))
    return tuple(frames)


def load_brood_shades(master, folder, foe):
    atlas = tk.PhotoImage(master=master, file=str(folder / "den-mother-brood.png"))
    height = atlas.height() // BROOD_SHADE_STEPS
    count = max(MOTIONS[foe.sprite].poses) + 1
    return tuple(_read_atlas_row(master, atlas, foe, count, row * height, height)
                 for row in range(BROOD_SHADE_STEPS))


def enemy_pose_frame(foe, elapsed, *, action_elapsed=None):
    motion = MOTIONS[foe.sprite]
    if not motion.poses:
        return 0
    if motion.pose_fps is not None:
        return motion.poses[int(max(0, elapsed) * motion.pose_fps) % len(motion.poses)]
    # Grounded poses share the idle timing, but restart when the enemy lunges.
    elapsed = action_elapsed if action_elapsed is not None else elapsed
    tick = int(max(0, elapsed) * motion.ticks_per_second) % (len(motion.offsets) + motion.rest_ticks)
    return motion.poses[tick] if tick < len(motion.poses) else 0


def _finish_enemy_sprite(master, sprite, foe):
    if foe.ink_outline:
        width, height = sprite.width(), sprite.height()
        inked = tk.PhotoImage(master=master, width=width, height=height)
        opaque = {(x, y) for y in range(height) for x in range(width) if not sprite.transparency_get(x, y)}
        contour = {(x + dx, y + dy) for x, y in opaque for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1))
                   if 0 <= x + dx < width and 0 <= y + dy < height} - opaque
        for x, y in contour:
            inked.put(OUTLINE, (x, y))
        inked.tk.call(inked, "copy", sprite, "-compositingrule", "overlay")
        sprite = inked
    zoom, sample = foe.sprite_scale
    enlarged = sprite.zoom(zoom)
    return enlarged.subsample(sample) if sample != 1 else enlarged
