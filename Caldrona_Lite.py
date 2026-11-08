from __future__ import annotations

import ctypes
import math
import os
import time
import tkinter as tk
import tkinter.font as tkfont
from pathlib import Path

TILE = 16
VIEW_W, VIEW_H = 320, 180
SCALE = 3
FRAME_MS = 16
MOVE_SPEED = 68.0
CHUNK_TILES = 8
CHUNK_PIXELS = TILE * CHUNK_TILES
CHUNK_SCREEN = CHUNK_PIXELS * SCALE

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "assets"
CAVERN_MUSIC = ASSETS / "audio" / "cavern-travel.mp3"
INK = "#101722"
PANEL = "#202b3c"
GOLD = "#f0d28c"
MUTED = "#a7b2c2"
CREAM = "#fff1cf"


class CavernInstance:
    """A fixed first-floor cave, built once and kept as a light tile map."""

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
        self.floor.update((x, y) for y in range(top, bottom) for x in range(left, right))

    def _hall(self, start: tuple[int, int], end: tuple[int, int], width: int) -> None:
        x, y = start
        ex, ey = end
        radius = width // 2
        while True:
            self.floor.update((x + dx, y + dy)
                              for dy in range(-radius, radius + 1)
                              for dx in range(-radius, radius + 1))
            if (x, y) == (ex, ey):
                return
            if x != ex:
                x += 1 if ex > x else -1
            elif y != ey:
                y += 1 if ey > y else -1

    def walkable(self, px: float, py: float) -> bool:
        return (int(px // TILE), int(py // TILE)) in self.floor


class CaldronaLite:
    """A low-cost retro menu and single-character cavern exploration slice."""

    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("Caldrona Lite")
        self.root.resizable(False, False)
        self.canvas = tk.Canvas(
            self.root, width=VIEW_W * SCALE, height=VIEW_H * SCALE,
            background="#09090c", highlightthickness=0,
        )
        self.canvas.pack()
        self._font_handles: list[str] = []
        self._load_font()
        self._init_controller()

        self.screen = "menu"
        self.selection = 0
        self.notice = ""
        self.menu_items = ("PLAY", "LOAD GAME", "SETTINGS")
        self.keys: set[str] = set()
        self.pad_keys: set[str] = set()
        self.pad_buttons: set[str] = set()
        self.menu_nav_after = 0.0
        self.last_tick = time.monotonic()
        self.scan_controller_at = 0.0
        self.pad = None
        self.joystick = None
        self.controller_status = "NO D-PAD FOUND"

        for key in ("Up", "Down", "Left", "Right", "w", "a", "s", "d", "Return", "Escape"):
            self.root.bind(f"<KeyPress-{key}>", self._key_down)
            self.root.bind(f"<KeyRelease-{key}>", self._key_up)
        self.root.bind("<Button-1>", self._click)
        self.root.protocol("WM_DELETE_WINDOW", self._close)
        self._draw_menu()
        self.root.after(FRAME_MS, self._tick)
        self.root.mainloop()

    def _load_font(self) -> None:
        if not hasattr(ctypes, "windll"):
            return
        add_font = ctypes.windll.gdi32.AddFontResourceExW
        add_font.argtypes = (ctypes.c_wchar_p, ctypes.c_uint, ctypes.c_void_p)
        add_font.restype = ctypes.c_int
        for filename in ("VT323-Regular.ttf", "PressStart2P-Regular.ttf"):
            path = ROOT / "fonts" / filename
            if path.exists() and add_font(str(path), 0x10, None):
                self._font_handles.append(str(path))

    def _font(self, size: int, bold: bool = False) -> tuple[str, int, str]:
        family = "VT323" if "VT323" in tkfont.families(self.root) else "Consolas"
        return family, size, "bold" if bold else "normal"

    def _init_controller(self) -> None:
        self.pygame = None
        self.controller_api = None
        os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
        try:
            import pygame
            from pygame._sdl2 import controller as controller_api

            pygame.display.init()
            pygame.joystick.init()
            controller_api.init()
            self.pygame = pygame
            self.controller_api = controller_api
        except Exception:
            self.pygame = None
            self.controller_api = None
            self.controller_status = "INSTALL pygame FOR PS4 D-PAD"

    def _scan_controller(self, now: float) -> None:
        if self.pygame is None or now < self.scan_controller_at:
            return
        self.scan_controller_at = now + 0.5
        if self.pad is not None and self.pad.attached():
            return
        self.pad = self.joystick = None
        pygame, api = self.pygame, self.controller_api
        try:
            for index in range(pygame.joystick.get_count()):
                if api.is_controller(index):
                    self.pad = api.Controller(index)
                    self.controller_status = self.pad.as_joystick().get_name()
                    return
                joy = pygame.joystick.Joystick(index)
                joy.init()
                if joy.get_numhats():
                    self.joystick = joy
                    self.controller_status = joy.get_name()
                    return
            self.controller_status = "NO D-PAD FOUND"
        except (pygame.error, RuntimeError):
            self.controller_status = "CONTROLLER DISCONNECTED"

    def _dpad(self) -> set[str]:
        if self.pygame is None:
            return set()
        try:
            self.pygame.event.pump()
            if self.pad is not None and self.pad.attached():
                api = self.controller_api
                return {
                    direction for direction, button in (
                        ("up", self.pygame.CONTROLLER_BUTTON_DPAD_UP),
                        ("down", self.pygame.CONTROLLER_BUTTON_DPAD_DOWN),
                        ("left", self.pygame.CONTROLLER_BUTTON_DPAD_LEFT),
                        ("right", self.pygame.CONTROLLER_BUTTON_DPAD_RIGHT),
                    ) if self.pad.get_button(button)
                }
            if self.joystick is not None and self.joystick.get_init():
                x, y = self.joystick.get_hat(0)
                return ({-1: {"left"}, 1: {"right"}}.get(x, set())
                        | {-1: {"down"}, 1: {"up"}}.get(y, set()))
        except (self.pygame.error, RuntimeError):
            self.pad = self.joystick = None
            self.controller_status = "CONTROLLER DISCONNECTED"
        return set()

    def _controller_buttons(self) -> set[str]:
        if self.pad is not None and self.pad.attached():
            return {name for name, button in (
                ("confirm", self.pygame.CONTROLLER_BUTTON_A),
                ("back", self.pygame.CONTROLLER_BUTTON_B),
            ) if self.pad.get_button(button)}
        if self.joystick is not None and self.joystick.get_init():
            count = self.joystick.get_numbuttons()
            # Common DS4 DirectInput order: Cross is button 1, Circle is button 2.
            return {name for index, name in ((1, "confirm"), (2, "back"))
                    if count > index and self.joystick.get_button(index)}
        return set()

    def _key_down(self, event: tk.Event) -> None:
        key = str(event.keysym).lower()
        if key in ("return", "escape"):
            if key in self.keys:
                return
            self.keys.add(key)
            if key == "return":
                self._activate()
            else:
                self._back()
        else:
            self.keys.add(key)

    def _key_up(self, event: tk.Event) -> None:
        self.keys.discard(str(event.keysym).lower())

    def _menu_direction(self) -> str | None:
        pressed = self._directions()
        # Deliberately resolve to one cardinal direction, even when two are held.
        for direction in ("up", "down", "left", "right"):
            if direction in pressed:
                return direction
        return None

    def _directions(self) -> set[str]:
        pressed = set(self.pad_keys)
        for key, direction in (
            ("up", "up"), ("w", "up"), ("down", "down"), ("s", "down"),
            ("left", "left"), ("a", "left"), ("right", "right"), ("d", "right"),
        ):
            if key in self.keys:
                pressed.add(direction)
        pressed |= self.pad_keys
        return pressed

    def _draw_frame(self) -> None:
        self.canvas.delete("all")
        self.canvas.configure(background=INK)
        self.canvas.create_rectangle(18, 18, 942, 522, outline="#586982", width=3)
        self.canvas.create_rectangle(27, 27, 933, 513, outline="#b79559", width=3)
        for x in (54, 906):
            for y in (54, 486):
                self.canvas.create_rectangle(x-4, y-4, x+4, y+4, fill=GOLD, outline="")
        self.canvas.create_text(480, 145, text="CALDRONA", fill=GOLD,
                               font=("Press Start 2P", 36, "bold"))
        self.canvas.create_text(480, 190, text="A JOURNEY BEGINS", fill=MUTED,
                               font=self._font(30))
        self.canvas.create_rectangle(258, 202, 702, 207, fill="#65748b", outline="")

    def _draw_menu(self) -> None:
        self.screen = "menu"
        self.root.title("Caldrona Lite")
        self._draw_frame()
        for index, label in enumerate(self.menu_items):
            y = 260 + index * 64
            active = index == self.selection
            self.canvas.create_rectangle(
                297, y-23, 663, y+25,
                fill="#33435a" if active else PANEL,
                outline="#edc873" if active else "#364357",
                width=4,
            )
            if active:
                self.canvas.create_text(328, y, text="▶", fill=GOLD,
                                        font=self._font(34, True))
            self.canvas.create_text(480, y, text=label,
                                    fill=CREAM if active else MUTED,
                                    font=self._font(36, True))
        self.canvas.create_text(480, 464, text="D-PAD / ARROWS · CROSS / ENTER SELECT",
                                fill=MUTED, font=self._font(25))
        self.canvas.create_text(480, 488, text="ESC / CIRCLE BACK",
                                fill=MUTED, font=self._font(22))

    def _draw_settings(self) -> None:
        self.screen = "settings"
        self._draw_frame()
        self.canvas.create_text(480, 264, text="SETTINGS", fill=GOLD,
                                font=self._font(38, True))
        self.canvas.create_text(480, 322, text="MOVE: D-PAD OR ARROWS", fill=CREAM,
                                font=self._font(30))
        self.canvas.create_text(480, 360, text="CARDINAL MOVEMENT ONLY", fill=CREAM,
                                font=self._font(30))
        self.canvas.create_text(480, 412, text=f"CONTROLLER: {self.controller_status}",
                                fill=MUTED, font=self._font(24))
        self.canvas.create_text(480, 472, text="ESC / CIRCLE TO RETURN",
                                fill=MUTED, font=self._font(24))

    def _draw_notice(self, message: str) -> None:
        self.screen = "notice"
        self._draw_frame()
        self.canvas.create_text(480, 300, text=message, fill=CREAM,
                                font=self._font(30), width=740)
        self.canvas.create_text(480, 388, text="ENTER / CROSS TO CONTINUE",
                                fill=GOLD, font=self._font(26))

    def _activate(self) -> None:
        if self.screen == "menu":
            if self.selection == 0:
                self._start_cavern()
            elif self.selection == 1:
                self._draw_notice("NO SAVED CAVERN JOURNEY YET.")
            else:
                self._draw_settings()
        elif self.screen == "game":
            self._leave_cavern()
        else:
            self._draw_menu()

    def _back(self) -> None:
        if self.screen == "game":
            self._leave_cavern()
        elif self.screen != "menu":
            self._draw_menu()

    def _leave_cavern(self) -> None:
        self._stop_cavern_music()
        self.keys.clear()
        self.pad_keys.clear()
        self._draw_menu()

    def _start_cavern_music(self) -> None:
        if self.pygame is None or not CAVERN_MUSIC.is_file():
            return
        try:
            if not self.pygame.mixer.get_init():
                self.pygame.mixer.init()
            self.pygame.mixer.music.load(str(CAVERN_MUSIC))
            self.pygame.mixer.music.set_volume(0.65)
            self.pygame.mixer.music.play(-1, fade_ms=700)
        except (self.pygame.error, OSError):
            self.notice = "Cavern music could not start."

    def _stop_cavern_music(self) -> None:
        if self.pygame is not None and self.pygame.mixer.get_init():
            self.pygame.mixer.music.fadeout(350)

    def _click(self, event: tk.Event) -> None:
        if self.screen != "menu":
            return
        x, y = event.x / SCALE, event.y / SCALE
        index = int((y - 260) // 64)
        if 0 <= index < len(self.menu_items) and 99 <= x <= 221:
            self.selection = index
            self._activate()

    def _start_cavern(self) -> None:
        self.screen = "game"
        self.root.title("Caldrona Lite · Cavern")
        self.canvas.delete("all")
        self.cave = CavernInstance()
        self.x, self.y = self.cave.spawn
        self.direction = "down"
        self.walk_frame = 1
        self.floor_tile = tk.PhotoImage(master=self.root, file=str(ASSETS / "cobble_floor.png")).subsample(2, 2).zoom(SCALE, SCALE)
        self.wall_tile = tk.PhotoImage(master=self.root, file=str(ASSETS / "wall_brick.png")).subsample(2, 2).zoom(SCALE, SCALE)
        self.player_frames = self._load_player()
        self.chunk_cache: dict[tuple[int, int], tk.PhotoImage] = {}
        self.chunk_items: dict[tuple[int, int], int] = {}
        self.world_camera = (0.0, 0.0)
        self.player_item = self.canvas.create_image(0, 0, anchor="center", tags=("player",))
        self.drawn_player_frame = None
        self.was_moving = False
        self.canvas.create_rectangle(18, VIEW_H*SCALE-68, 570, VIEW_H*SCALE-24,
                                     fill="#101625", outline="#ad8c54", width=3, tags=("hud",))
        self.canvas.create_text(36, VIEW_H*SCALE-52, anchor="w", fill=GOLD,
                                font=self._font(25, True), text="SUNREST EXCAVATION · FLOOR 1",
                                tags=("hud",))
        self.canvas.create_text(36, VIEW_H*SCALE-31, anchor="w", fill="#d1d5dc",
                                font=self._font(19), text="D-PAD / WASD TO WALK · ESC TO MENU",
                                tags=("hud",))
        self.last_tick = time.monotonic()
        self._update_world(force=True)
        self._start_cavern_music()

    def _load_player(self) -> dict[str, list[tk.PhotoImage]]:
        atlas = tk.PhotoImage(master=self.root, file=str(ASSETS / "retri-overworld.png"))
        frames: dict[str, list[tk.PhotoImage]] = {}
        for row, direction in enumerate(("down", "left", "right", "up")):
            frames[direction] = []
            for col in range(3):
                small = tk.PhotoImage(master=self.root, width=16, height=16)
                small.tk.call(small, "copy", atlas, "-from", col*32, row*32,
                              (col+1)*32, (row+1)*32, "-subsample", 2, 2)
                frames[direction].append(small.zoom(SCALE, SCALE))
        return frames

    def _camera(self) -> tuple[float, float]:
        max_x = max(0, self.cave.width * TILE - VIEW_W)
        max_y = max(0, self.cave.height * TILE - VIEW_H)
        return (min(max(self.x - VIEW_W/2, 0), max_x),
                min(max(self.y - VIEW_H/2, 0), max_y))

    def _build_chunk(self, key: tuple[int, int]) -> tk.PhotoImage:
        photo = tk.PhotoImage(master=self.root, width=CHUNK_SCREEN, height=CHUNK_SCREEN)
        gx, gy = key
        for oy in range(CHUNK_TILES):
            for ox in range(CHUNK_TILES):
                tx, ty = gx*CHUNK_TILES + ox, gy*CHUNK_TILES + oy
                dest = (ox*TILE*SCALE, oy*TILE*SCALE)
                if (tx, ty) in self.cave.floor:
                    photo.tk.call(photo, "copy", self.floor_tile, "-to", *dest)
                elif any((tx+dx, ty+dy) in self.cave.floor
                         for dx, dy in ((0,1),(0,-1),(1,0),(-1,0))):
                    photo.tk.call(photo, "copy", self.wall_tile, "-to", *dest)
        self.chunk_cache[key] = photo
        return photo

    def _update_world(self, force: bool = False) -> None:
        camera = self._camera()
        cx, cy = camera
        left, top = int(cx // CHUNK_PIXELS), int(cy // CHUNK_PIXELS)
        right = min((self.cave.width*TILE-1)//CHUNK_PIXELS,
                    int((cx+VIEW_W-1)//CHUNK_PIXELS))
        bottom = min((self.cave.height*TILE-1)//CHUNK_PIXELS,
                     int((cy+VIEW_H-1)//CHUNK_PIXELS))
        visible = {(x, y) for y in range(top, bottom+1)
                   for x in range(left, right+1)}
        old_x, old_y = self.world_camera
        if force or visible != set(self.chunk_items):
            self.canvas.delete("world")
            self.chunk_items.clear()
            for key in sorted(visible, key=lambda point: (point[1], point[0])):
                photo = self.chunk_cache.get(key) or self._build_chunk(key)
                gx, gy = key
                item = self.canvas.create_image(
                    gx*CHUNK_SCREEN-cx*SCALE, gy*CHUNK_SCREEN-cy*SCALE,
                    image=photo, anchor="nw", tags=("world",),
                )
                self.chunk_items[key] = item
            self.canvas.tag_lower("world")
        else:
            shift_x, shift_y = (old_x-cx)*SCALE, (old_y-cy)*SCALE
            if shift_x or shift_y:
                self.canvas.move("world", shift_x, shift_y)
        self.world_camera = camera
        self._place_player(camera)

    def _place_player(self, camera: tuple[float, float]) -> None:
        cx, cy = camera
        screen_x, screen_y = (self.x-cx)*SCALE, (self.y-cy)*SCALE
        pressed = self._directions()
        direction = next((name for name in ("up","down","left","right") if name in pressed), None)
        if direction:
            self.direction = direction
            self.walk_frame = 0 if int(time.monotonic()*8)%2 else 2
        else:
            self.walk_frame = 1
        frame = self.player_frames[self.direction][self.walk_frame]
        if frame is not self.drawn_player_frame:
            self.canvas.itemconfigure(self.player_item, image=frame)
            self.drawn_player_frame = frame
        self.canvas.coords(self.player_item, screen_x, screen_y)

    def _tick(self) -> None:
        now = time.monotonic()
        dt = min(0.05, now-self.last_tick)
        self.last_tick = now
        self._scan_controller(now)
        self.pad_keys = self._dpad()
        buttons = self._controller_buttons()
        tapped = buttons - self.pad_buttons
        self.pad_buttons = buttons
        if "confirm" in tapped:
            self._activate()
        if "back" in tapped:
            self._back()
        direction = self._menu_direction()
        if self.screen == "menu" and direction in ("up", "down") and now >= self.menu_nav_after:
            new_selection = (self.selection + (-1 if direction == "up" else 1)) % len(self.menu_items)
            if new_selection != self.selection:
                self.selection = new_selection
                self._draw_menu()
            self.menu_nav_after = now + 0.18
        elif self.screen == "game":
            # D-pad input resolves to one axis; diagonals are discarded by priority.
            active = direction
            moved = False
            if active:
                dx, dy = {"up":(0,-1), "down":(0,1), "left":(-1,0), "right":(1,0)}[active]
                distance = MOVE_SPEED*dt
                old_x, old_y = self.x, self.y
                nx, ny = self.x+dx*distance, self.y+dy*distance
                if self.cave.walkable(nx, self.y):
                    self.x = nx
                if self.cave.walkable(self.x, ny):
                    self.y = ny
                moved = self.x != old_x or self.y != old_y
                self.was_moving = moved
            elif self.was_moving:
                self.was_moving = False
                moved = True
            if moved:
                self._update_world()
        self.root.after(FRAME_MS, self._tick)

    def _close(self) -> None:
        if self.pygame is not None:
            try:
                self._stop_cavern_music()
                self.pygame.quit()
            except self.pygame.error:
                pass
        if hasattr(ctypes, "windll"):
            remove_font = ctypes.windll.gdi32.RemoveFontResourceExW
            remove_font.argtypes = (ctypes.c_wchar_p, ctypes.c_uint, ctypes.c_void_p)
            remove_font.restype = ctypes.c_bool
            for path in self._font_handles:
                remove_font(path, 0x10, None)
        self.root.destroy()


if __name__ == "__main__":
    CaldronaLite()
