from __future__ import annotations

import math
import ctypes
import time
import tkinter as tk
import tkinter.font as tkfont
from pathlib import Path

TILE = 16
VIEW_W, VIEW_H = 320, 180
SCALE = 3
FPS_MS = 16
MOVE_SPEED = 72.0

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "assets"


class CavernInstance:
    """A small, self-contained first-floor cave with connected chambers."""

    width, height = 56, 36

    def __init__(self) -> None:
        self.floor: set[tuple[int, int]] = set()
        self._room(3, 3, 14, 13)
        self._room(22, 2, 36, 15)
        self._room(42, 5, 53, 18)
        self._room(5, 21, 23, 32)
        self._room(29, 21, 48, 32)
        self._hall((13, 8), (25, 8), 3)
        self._hall((34, 9), (45, 11), 3)
        self._hall((10, 12), (11, 25), 3)
        self._hall((20, 26), (33, 26), 3)
        self._hall((40, 16), (39, 25), 3)
        self.spawn = (8 * TILE + TILE / 2, 8 * TILE + TILE / 2)

    def _room(self, left: int, top: int, right: int, bottom: int) -> None:
        for y in range(top, bottom):
            for x in range(left, right):
                self.floor.add((x, y))

    def _hall(self, start: tuple[int, int], end: tuple[int, int], width: int) -> None:
        x, y = start
        ex, ey = end
        radius = width // 2
        while True:
            for dy in range(-radius, radius + 1):
                for dx in range(-radius, radius + 1):
                    self.floor.add((x + dx, y + dy))
            if (x, y) == (ex, ey):
                break
            if x != ex:
                x += 1 if ex > x else -1
            elif y != ey:
                y += 1 if ey > y else -1

    def walkable(self, px: float, py: float) -> bool:
        x, y = int(px // TILE), int(py // TILE)
        return (x, y) in self.floor


class CaldronaLite:
    """Low-resolution, single-character exploration prototype."""

    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("Caldrona Lite · Cavern")
        self.root.resizable(False, False)
        self.canvas = tk.Canvas(
            self.root, width=VIEW_W * SCALE, height=VIEW_H * SCALE,
            background="#09090c", highlightthickness=0,
        )
        self.canvas.pack()

        self.cave = CavernInstance()
        self.x, self.y = self.cave.spawn
        self.direction = "down"
        self.walk_frame = 1
        self.keys: set[str] = set()
        self.last_tick = 0.0
        self.last_camera: tuple[int, int] | None = None

        self._font_handles: list[str] = []
        self._load_fonts()
        self.floor_tile = tk.PhotoImage(master=self.root, file=str(ASSETS / "cobble_floor.png")).subsample(2, 2).zoom(3, 3)
        self.wall_tile = tk.PhotoImage(master=self.root, file=str(ASSETS / "wall_brick.png")).subsample(2, 2).zoom(3, 3)
        self.player_frames = self._load_player()

        for key in ("Up", "Down", "Left", "Right", "w", "a", "s", "d"):
            self.root.bind(f"<KeyPress-{key}>", self._key_down)
            self.root.bind(f"<KeyRelease-{key}>", self._key_up)
        self.root.bind("<Escape>", lambda _event: self._close())
        self.root.protocol("WM_DELETE_WINDOW", self._close)

        self.player_item = self.canvas.create_image(0, 0, anchor="center", tags=("player",))
        self.hud_panel = self.canvas.create_rectangle(
            12, VIEW_H * SCALE - 62, 356, VIEW_H * SCALE - 12,
            fill="#101625", outline="#ad8c54", width=3, tags=("hud",),
        )
        self.hud_title = self.canvas.create_text(
            26, VIEW_H * SCALE - 49, anchor="w", fill="#f0d28c",
            font=self._ui_font(19, True), text="SUNREST EXCAVATION  ·  FLOOR 1", tags=("hud",),
        )
        self.hud_hint = self.canvas.create_text(
            26, VIEW_H * SCALE - 25, anchor="w", fill="#c4cbd4",
            font=self._ui_font(17), text="WASD / ARROWS TO WALK     ESC TO QUIT", tags=("hud",),
        )
        self._refresh_world(force=True)
        self.root.after(FPS_MS, self._tick)
        self.root.mainloop()

    def _load_player(self) -> dict[str, list[tk.PhotoImage]]:
        atlas = tk.PhotoImage(master=self.root, file=str(ASSETS / "retri-overworld.png"))
        frames: dict[str, list[tk.PhotoImage]] = {}
        for row, direction in enumerate(("down", "left", "right", "up")):
            frames[direction] = []
            for col in range(3):
                frame = tk.PhotoImage(master=self.root, width=16, height=16)
                frame.tk.call(frame, "copy", atlas, "-from", col * 32, row * 32,
                              (col + 1) * 32, (row + 1) * 32,
                              "-subsample", 2, 2)
                frames[direction].append(frame.zoom(3, 3))
        return frames

    def _load_fonts(self) -> None:
        if not hasattr(ctypes, "windll"):
            return
        add_font = ctypes.windll.gdi32.AddFontResourceExW
        add_font.argtypes = (ctypes.c_wchar_p, ctypes.c_uint, ctypes.c_void_p)
        add_font.restype = ctypes.c_int
        path = ROOT / "fonts" / "VT323-Regular.ttf"
        if path.exists() and add_font(str(path), 0x10, None):
            self._font_handles.append(str(path))

    def _ui_font(self, size: int, bold: bool = False) -> tuple[str, int, str]:
        family = "VT323" if "VT323" in tkfont.families(self.root) else "Consolas"
        return family, size, "bold" if bold else "normal"

    def _key_down(self, event: tk.Event) -> None:
        self.keys.add(str(event.keysym).lower())

    def _key_up(self, event: tk.Event) -> None:
        self.keys.discard(str(event.keysym).lower())

    def _camera(self) -> tuple[int, int]:
        max_x = max(0, self.cave.width * TILE - VIEW_W)
        max_y = max(0, self.cave.height * TILE - VIEW_H)
        cx = min(max(0, int(self.x - VIEW_W / 2)), max_x)
        cy = min(max(0, int(self.y - VIEW_H / 2)), max_y)
        # Snap the static view to tiles; the player glides smoothly on top.
        return (cx // TILE) * TILE, (cy // TILE) * TILE

    def _refresh_world(self, force: bool = False) -> None:
        camera = self._camera()
        if not force and camera == self.last_camera:
            return
        self.last_camera = camera
        cx, cy = camera
        c = self.canvas
        c.delete("world")

        min_x = max(-1, cx // TILE - 1)
        min_y = max(-1, cy // TILE - 1)
        max_x = min(self.cave.width, (cx + VIEW_W) // TILE + 2)
        max_y = min(self.cave.height, (cy + VIEW_H) // TILE + 2)

        for ty in range(min_y, max_y):
            for tx in range(min_x, max_x):
                sx, sy = tx * TILE - cx, ty * TILE - cy
                if (tx, ty) in self.cave.floor:
                    c.create_image(sx * SCALE, sy * SCALE, anchor="nw",
                                   image=self.floor_tile, tags=("world",))
                else:
                    near_floor = any((tx + dx, ty + dy) in self.cave.floor
                                     for dx, dy in ((0, 1), (0, -1), (1, 0), (-1, 0)))
                    if near_floor:
                        c.create_image(sx * SCALE, sy * SCALE, anchor="nw",
                                       image=self.wall_tile, tags=("world",))
        c.tag_lower("world")
        self._place_player(camera)

    def _place_player(self, camera: tuple[int, int]) -> None:
        cx, cy = camera
        sx, sy = (self.x - cx) * SCALE, (self.y - cy) * SCALE
        moving = any(key in self.keys for key in ("up", "down", "left", "right", "w", "a", "s", "d"))
        column = self.walk_frame if moving else 1
        self.canvas.itemconfigure(self.player_item, image=self.player_frames[self.direction][column])
        self.canvas.coords(self.player_item, sx, sy)
        self.canvas.tag_raise("player")
        self.canvas.tag_raise("hud")

    def _tick(self) -> None:
        now = time.monotonic()
        if not self.last_tick:
            self.last_tick = now
        dt = min(0.05, now - self.last_tick)
        self.last_tick = now

        dx = float(("right" in self.keys or "d" in self.keys) -
                   ("left" in self.keys or "a" in self.keys))
        dy = float(("down" in self.keys or "s" in self.keys) -
                   ("up" in self.keys or "w" in self.keys))
        if dx or dy:
            length = math.hypot(dx, dy)
            dx, dy = dx / length, dy / length
            if abs(dx) > abs(dy):
                self.direction = "right" if dx > 0 else "left"
            else:
                self.direction = "down" if dy > 0 else "up"
            distance = MOVE_SPEED * dt
            nx, ny = self.x + dx * distance, self.y + dy * distance
            # Axis-separated checks let the character slide along rock edges.
            if self.cave.walkable(nx, self.y):
                self.x = nx
            if self.cave.walkable(self.x, ny):
                self.y = ny
            self.walk_frame = 0 if int(now * 8) % 2 else 2

        self._refresh_world()
        self._place_player(self._camera())
        self.root.after(FPS_MS, self._tick)

    def _close(self) -> None:
        if hasattr(ctypes, "windll"):
            remove_font = ctypes.windll.gdi32.RemoveFontResourceExW
            remove_font.argtypes = (ctypes.c_wchar_p, ctypes.c_uint, ctypes.c_void_p)
            remove_font.restype = ctypes.c_bool
            for path in self._font_handles:
                remove_font(path, 0x10, None)
        self.root.destroy()


if __name__ == "__main__":
    CaldronaLite()
