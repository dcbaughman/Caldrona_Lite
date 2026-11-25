"""Equipment-based actor poses shared by battle and the player-move lab."""

from dataclasses import dataclass
from pathlib import Path
import tkinter as tk

from arrow_fx import FLIGHT_MS, IMPACT_MS
from classes import current_job
from equipment import item_for, worn_id


CELL_W, CELL_H = 80, 40
PAD_X = (CELL_W - 48) // 2
STYLES = (
    "sword", "greatsword", "pike", "halberd", "bow", "whip",
    "dagger", "mace", "staff", "rod", "throw", "fists",
    "cast_hand", "cast_wand", "cast_staff", "cast_orb", "critical",
)
CAST_STYLES = frozenset(key for key in STYLES if key.startswith("cast_"))
PROJECTILE_OFFSETS = {
    "throw": (-24, -2), "cast_hand": (-30, -8), "cast_wand": (-40, -12),
    "cast_staff": (-30, -30), "cast_orb": (-32, -14),
}


@dataclass(frozen=True)
class Motion:
    style: str
    windup_ms: int
    travel_ms: int = 0
    impact_hold_ms: int = 0

    FOLLOW_THROUGH_MS = 255

    @property
    def release_duration_ms(self):
        return max(self.FOLLOW_THROUGH_MS, self.travel_ms + self.impact_hold_ms)

    def timing(self, impact_ms):
        """Return the effect start and the moment the actor extends the arm."""
        if self.travel_ms or self.style in CAST_STYLES or self.style == "throw":
            return self.windup_ms, self.windup_ms
        release_ms = max(self.windup_ms, impact_ms)
        return release_ms - impact_ms, release_ms

    def column(self, elapsed_ms, release_ms):
        if elapsed_ms < release_ms:
            return 0 if elapsed_ms < release_ms * .32 else 1
        release = elapsed_ms - release_ms
        if release < 83:
            return 2
        if release < 175:
            return 3
        if release < self.FOLLOW_THROUGH_MS:
            return 4
        return None


MOTIONS = {style: Motion(style, windup) for style, windup in (
    ("sword", 180), ("dagger", 145), ("mace", 205), ("staff", 190),
    ("rod", 160), ("throw", 165), ("fists", 145),
    ("cast_hand", 195), ("cast_wand", 195), ("cast_staff", 195), ("cast_orb", 195),
    ("greatsword", 265), ("pike", 205), ("halberd", 235), ("whip", 215),
)}
MOTIONS["bow"] = Motion("bow", 255, FLIGHT_MS, IMPACT_MS)


def _cast_style(item):
    kind = item.weapon_type if item else ""
    if kind == "staff":
        return "cast_staff"
    if kind in ("wand", "rod"):
        return "cast_wand"
    if kind.startswith("focus") or kind == "scepter":
        return "cast_orb"
    return "cast_hand"


def action_motion(member, tag="attack"):
    """A lesson can request a weapon, magic, throwing, or bare-handed pose."""
    item = item_for(worn_id(member, "weapon"))
    if tag == "magic" or (tag == "attack" and item and item.basic_attack_fx in ("wand_bolt", "focus_pulse")):
        return MOTIONS[_cast_style(item)]
    if tag in ("throw", "fists"):
        return MOTIONS[tag]
    if tag not in ("attack", "weapon"):
        return None
    if item is None:
        return MOTIONS["fists"]
    kind = item.weapon_type.strip().lower()
    if kind in ("sword", "greatsword", "staff", "pike", "halberd", "bow", "whip"):
        return MOTIONS[kind]
    if kind == "great sword":
        return MOTIONS["greatsword"]
    if kind in ("longbow", "shortbow"):
        return MOTIONS["bow"]
    if kind in ("dagger", "knife"):
        return MOTIONS["dagger"]
    if kind == "thrown knife":
        return MOTIONS["throw"]
    if kind in ("mace", "club", "cosh"):
        return MOTIONS["mace"]
    if kind in ("wand", "rod", "scepter"):
        return MOTIONS["rod"]
    return MOTIONS["fists"]


class PlayerMotionArt:
    """Load a costume's authored frames only as they are used."""

    def __init__(self, canvas, assets: Path):
        self.canvas = canvas
        self.assets = assets / "battle" / "player-motion"
        self.atlases = {}
        self.frames = {}

    def frame(self, member, style, column=0):
        name = member["name"].lower()
        job = (current_job(member) or "unbound").lower()
        costume = name, job
        if costume not in self.atlases:
            path = self.assets / f"{name}-{job}.png"
            if not path.is_file():
                path = self.assets / f"{name}-unbound.png"
            self.atlases[costume] = (tk.PhotoImage(master=self.canvas, file=str(path))
                                     if path.is_file() else None)
        atlas = self.atlases[costume]
        if atlas is None:
            return None
        key = costume, style, column
        if key not in self.frames:
            row = STYLES.index(style)
            frame = tk.PhotoImage(master=self.canvas, width=CELL_W, height=CELL_H)
            frame.tk.call(frame, "copy", atlas, "-from", column*CELL_W, row*CELL_H,
                          (column+1)*CELL_W, (row+1)*CELL_H)
            self.frames[key] = frame.zoom(2)
        return self.frames[key]
