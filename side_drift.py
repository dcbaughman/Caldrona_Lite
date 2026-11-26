"""Larvel's side drift: a short tunnel off the entry shaft, with a stairwell down into the old mines.

The stairwell is where a sidequest will begin. For now, inspecting it only sets up the hook.
"""
import tkinter as tk

from dialogue import DialogueLine

TILE = 16
# The drift branches east off the shaft between the entry room and the lower workings,
# the same shaft Larvel walks down after the collapse.
DRIFT_HALL = ((12, 16), (14, 16))  # one tile wide
DRIFT_ROOM = (15, 14, 20, 19)  # left, top, right, bottom (exclusive), like CavernInstance rooms
STAIRWELL = (16, 15)  # top-left tile of the 2 x 2 stairwell
STAIRWELL_TILES = frozenset((STAIRWELL[0] + dx, STAIRWELL[1] + dy) for dx in (0, 1) for dy in (0, 1))


class SideDrift:
    def __init__(self, app, assets, scale):
        self.app, self.scale = app, scale
        self.image = tk.PhotoImage(
            master=app.root, file=str(assets / "mine-polish" / "drift-stairwell.png")
        ).zoom(scale)
        self.item = app.canvas.create_image(0, 0, image=self.image, anchor="nw", tags=("drift_stairwell",))
        app.canvas.tag_lower(self.item, "player")

    def _here(self):
        a = self.app
        return not (a.outdoors or a.in_chamber or a._in_den())

    def is_stairwell(self, tile):
        return self._here() and tile in STAIRWELL_TILES

    def blocked(self, tile):
        return tile in STAIRWELL_TILES

    def render(self, camera):
        cx, cy = camera
        canvas = self.app.canvas
        canvas.coords(self.item, (STAIRWELL[0] * TILE - cx) * self.scale, (STAIRWELL[1] * TILE - cy) * self.scale)
        canvas.itemconfigure(self.item, state="normal" if self._here() else "hidden")

    def interact(self):
        a = self.app
        if not self.is_stairwell(a._facing_tile()):
            return False
        lines = [DialogueLine("Retri", "Stairs, cut down through the drift floor. Someone's lantern is burning far below.",
                              thought=True)]
        if a.cave_story.get("trail_search"):
            lines.append(DialogueLine("Retri", "Larvel said his crew was down this side drift.", thought=True))
        a.dialogue.show(lines)
        return True
