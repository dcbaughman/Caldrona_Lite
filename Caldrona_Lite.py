from __future__ import annotations

import ctypes
import math
import os
import time
import tkinter as tk
import tkinter.font as tkfont
from pathlib import Path

from dialogue import DialogueBox, DialogueLine
from display_settings import (DisplayConfig, ScaledCanvas, available_sizes,
                              load_display, pixel_scale, save_display)
from game_menu import GameMenu
from battle import (BattleModel, BattleScene, BattleTransition, EncounterMeter,
                    ENEMIES, MAX_HP, MAX_POTIONS, gain_xp)

TILE = 16
VIEW_W, VIEW_H = 320, 180
SCALE = 3
FRAME_MS = 16
STEP_INTERVAL = 0.135
CHUNK_TILES = 8
CHUNK_PIXELS = TILE * CHUNK_TILES
CHUNK_SCREEN = CHUNK_PIXELS * SCALE

ROOT = Path(__file__).resolve().parent
DISPLAY_FILE = ROOT / "display_settings.json"
ASSETS = ROOT / "assets"
CAVERN_MUSIC = ASSETS / "audio" / "cavern-travel.mp3"
BATTLE_MUSIC = ASSETS / "audio" / "cavern-battle.mp3"
VICTORY_MUSIC = ASSETS / "audio" / "caldrona-level-up.mp3"
GAME_OVER_MUSIC = ASSETS / "audio" / "caldrona-game-over.mp3"
RETRI_PORTRAIT = ASSETS / "portraits" / "allsprites.png"
RETRI_PORTRAIT_REGION = (110, 24, 238, 152)
TEMUR_PORTRAIT = ASSETS / "portraits" / "temur.png"
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
        self.root.configure(background="#08090c")
        self.available_window_sizes = available_sizes(
            self.root.winfo_screenwidth(), self.root.winfo_screenheight(),
        )
        self.active_display = load_display(DISPLAY_FILE, self.available_window_sizes)
        self.saved_display = self.active_display
        self.pending_display = self.saved_display
        outer_width, outer_height = (
            (self.root.winfo_screenwidth(), self.root.winfo_screenheight())
            if self.active_display.mode == "fullscreen"
            else (self.active_display.width, self.active_display.height)
        )
        self.root.geometry(f"{outer_width}x{outer_height}")
        if self.active_display.mode == "fullscreen":
            self.root.attributes("-fullscreen", True)
        self.canvas = ScaledCanvas(
            self.root, pixel_scale(outer_width, outer_height),
            background="#09090c", highlightthickness=0, borderwidth=0,
        )
        self.canvas.pack(expand=True)
        self._font_handles: list[str] = []
        self._load_font()
        self._init_controller()
        self.dialogue = DialogueBox(self.canvas, self.root, self._font)
        self.dialogue.register_portrait("Retri", RETRI_PORTRAIT, RETRI_PORTRAIT_REGION)
        self.dialogue.register_portrait("Temur", TEMUR_PORTRAIT)
        self.game_menu = GameMenu(
            self.canvas, self._font,
            lambda: self.dialogue.portrait(RETRI_PORTRAIT, RETRI_PORTRAIT_REGION),
        )
        self.game_menu.party_names = lambda: [member["name"] for member in getattr(self, "party", [{"name": "Retri"}])]
        self.game_menu.party_portrait = lambda name: self.dialogue.portrait(
            TEMUR_PORTRAIT if name == "Temur" else RETRI_PORTRAIT,
            None if name == "Temur" else RETRI_PORTRAIT_REGION,
        )

        self.screen = "menu"
        self.selection = 0
        self.notice = ""
        self.menu_items = ("PLAY", "LOAD GAME", "SETTINGS")
        self.keys: set[str] = set()
        self.pad_keys: set[str] = set()
        self.pad_buttons: set[str] = set()
        self.menu_nav_after = 0.0
        self.settings_selection = 0
        self.settings_notice = ""
        self.settings_direction: str | None = None
        self.settings_repeat_at = 0.0
        self.settings_repeating = False
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
        self.tick_after = self.root.after(FRAME_MS, self._tick)
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
                ("menu", self.pygame.CONTROLLER_BUTTON_START),
            ) if self.pad.get_button(button)}
        if self.joystick is not None and self.joystick.get_init():
            count = self.joystick.get_numbuttons()
            # Common DS4 DirectInput order: Cross is button 1, Circle is button 2.
            return {name for index, name in ((1, "confirm"), (2, "back"), (9, "menu"))
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

    def _draw_frame(self, show_title: bool = True) -> None:
        self.canvas.delete("all")
        self.canvas.configure(background=INK)
        self.canvas.create_rectangle(18, 18, 942, 522, outline="#586982", width=3)
        self.canvas.create_rectangle(27, 27, 933, 513, outline="#b79559", width=3)
        for x in (54, 906):
            for y in (54, 486):
                self.canvas.create_rectangle(x-4, y-4, x+4, y+4, fill=GOLD, outline="")
        if show_title:
            self.canvas.create_text(480, 145, text="CALDRONA", fill=GOLD,
                                   font=("Press Start 2P", 36, "bold"))
            self.canvas.create_text(480, 190, text="A JOURNEY BEGINS", fill=MUTED,
                                   font=self._font(30))
            self.canvas.create_rectangle(258, 202, 702, 207,
                                         fill="#65748b", outline="")

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
        if self.saved_display != self.active_display:
            self.canvas.create_text(480, 224, text="RESTART TO APPLY DISPLAY CHANGE",
                                    fill=GOLD, font=self._font(21))

    def _open_settings(self) -> None:
        self.pending_display = self.saved_display
        self.settings_selection = 0
        self.settings_notice = ""
        self.settings_direction = None
        self._draw_settings()

    def _draw_settings(self) -> None:
        self.screen = "settings"
        self._draw_frame(show_title=False)
        self.canvas.create_text(480, 150, text="DISPLAY SETTINGS", fill=GOLD,
                                font=self._font(38, True))
        self.canvas.create_rectangle(258, 195, 702, 200, fill="#65748b", outline="")
        rows = (
            ("MODE", self.pending_display.mode.upper()),
            ("WINDOW SIZE", f"{self.pending_display.width} x {self.pending_display.height}"
             if self.pending_display.mode == "windowed" else "DESKTOP"),
            ("APPLY", "PENDING" if self.pending_display != self.saved_display
             else "RESTART REQUIRED" if self.saved_display != self.active_display
             else "NO CHANGE"),
        )
        for index, (label, value) in enumerate(rows):
            y = 273 + index * 64
            active = index == self.settings_selection
            self.canvas.create_rectangle(178, y - 25, 782, y + 25,
                                         fill="#33435a" if active else PANEL,
                                         outline="#edc873" if active else "#364357",
                                         width=3)
            if active:
                self.canvas.create_text(204, y, text="▶", anchor="w", fill=GOLD,
                                        font=self._font(27, True))
            self.canvas.create_text(250, y, text=label, anchor="w", fill=CREAM,
                                    font=self._font(27, active))
            self.canvas.create_text(746, y, text=value, anchor="e",
                                    fill=GOLD if active else MUTED,
                                    font=self._font(27, active))
        self.canvas.create_text(480, 451,
                                text="UP / DOWN SELECT · LEFT / RIGHT CHANGE · ENTER APPLY",
                                fill=MUTED, font=self._font(21))
        self.canvas.create_text(480, 490,
                                text=self.settings_notice or "WINDOWED SIZES ARE 4:3 · ESC TO RETURN",
                                fill=GOLD if self.settings_notice else MUTED,
                                font=self._font(21))

    def _draw_notice(self, message: str) -> None:
        self.screen = "notice"
        self._draw_frame()
        self.canvas.create_text(480, 300, text=message, fill=CREAM,
                                font=self._font(30), width=740)
        self.canvas.create_text(480, 388, text="ENTER / CROSS TO CONTINUE",
                                fill=GOLD, font=self._font(26))

    def _activate(self) -> None:
        if self.screen in ("faint", "cave_shake"):
            return
        if self.screen == "game_over":
            self.canvas.delete("game_over")
            if self.game_over_selection == 0:
                self._finish_battle("defeat")
            else:
                self.battle.close()
                self._leave_cavern()
            return
        if self.screen == "battle":
            outcome = self.battle.confirm(time.monotonic())
            if outcome:
                self._finish_battle(outcome)
            return
        if self.screen in ("battle_in", "battle_out"):
            return
        if self.screen == "game":
            if self.dialogue.active:
                self.dialogue.advance()
                if not self.dialogue.active and getattr(self, "temur_story", "") == "intro":
                    self.temur_story, self.screen = "shaking", "cave_shake"
                    self.shake_started = time.monotonic()
                elif not self.dialogue.active and getattr(self, "temur_story", "") == "joining":
                    self.temur_story = "joined"
                    self.party.append({"name": "Temur", "hp": 70, "max_hp": 70})
                    self.canvas.itemconfigure(self.temur_item, state="hidden")
            elif self.game_menu.active and self.game_menu.activate() == "title":
                self._leave_cavern()
            elif not self.game_menu.active:
                if not self._interact_temur():
                    self._interact_chest()
            return
        if self.screen == "menu":
            if self.selection == 0:
                self._start_cavern()
            elif self.selection == 1:
                self._draw_notice("NO SAVED CAVERN JOURNEY YET.")
            else:
                self._open_settings()
        elif self.screen == "settings":
            if self.settings_selection == 0:
                mode = "fullscreen" if self.pending_display.mode == "windowed" else "windowed"
                self.pending_display = DisplayConfig(
                    mode, self.pending_display.width, self.pending_display.height,
                )
                self.settings_notice = ""
            elif self.settings_selection == 1:
                self._cycle_window_size(1)
            else:
                try:
                    save_display(DISPLAY_FILE, self.pending_display)
                    self.saved_display = self.pending_display
                    self.settings_notice = (
                        "SAVED · RESTART GAME TO APPLY"
                        if self.saved_display != self.active_display else "DISPLAY SETTINGS SAVED"
                    )
                except OSError:
                    self.settings_notice = "COULD NOT SAVE DISPLAY SETTINGS"
            self._draw_settings()
        else:
            self._draw_menu()

    def _cycle_window_size(self, step: int) -> None:
        if self.pending_display.mode != "windowed":
            return
        sizes = self.available_window_sizes
        current = (self.pending_display.width, self.pending_display.height)
        index = (sizes.index(current) + step) % len(sizes)
        self.pending_display = DisplayConfig("windowed", *sizes[index])
        self.settings_notice = ""

    def _navigate_settings(self, direction: str | None, now: float) -> None:
        if direction not in ("up", "down", "left", "right"):
            self.settings_direction = None
            self.settings_repeating = False
            return
        if direction != self.settings_direction:
            self.settings_direction = direction
            self.settings_repeat_at = now
            self.settings_repeating = False
        if now < self.settings_repeat_at:
            return
        if (direction in ("left", "right") and self.settings_selection == 0
                and self.settings_repeating):
            return
        if direction in ("up", "down"):
            step = -1 if direction == "up" else 1
            self.settings_selection = (self.settings_selection + step) % 3
        elif self.settings_selection == 0:
            self.pending_display = DisplayConfig(
                "fullscreen" if self.pending_display.mode == "windowed" else "windowed",
                self.pending_display.width, self.pending_display.height,
            )
        elif self.settings_selection == 1:
            self._cycle_window_size(-1 if direction == "left" else 1)
        self.settings_notice = ""
        self._draw_settings()
        self.settings_repeat_at = now + (0.09 if self.settings_repeating else 0.24)
        self.settings_repeating = True

    def _back(self) -> None:
        if self.screen in ("faint", "game_over", "cave_shake"):
            return
        if self.screen == "battle":
            self.battle.back()
            return
        if self.screen in ("battle_in", "battle_out"):
            return
        if self.screen == "game":
            if self.dialogue.active:
                if getattr(self, "temur_story", "") in ("intro", "joining"):
                    self._activate()
                else:
                    self.dialogue.clear()
            elif self.game_menu.active:
                self.game_menu.back()
            else:
                self.game_menu.open()
        elif self.screen != "menu":
            self._draw_menu()

    def _toggle_game_menu(self) -> None:
        if self.screen != "game" or self.dialogue.active:
            return
        if self.game_menu.active:
            self.game_menu.close()
        else:
            self.game_menu.open()

    def _leave_cavern(self) -> None:
        self.dialogue.clear()
        self.game_menu.close()
        self._stop_cavern_music()
        self.keys.clear()
        self.pad_keys.clear()
        self._draw_menu()

    def _start_cavern_music(self) -> None:
        self._play_music(CAVERN_MUSIC)

    def _play_music(self, path: Path, loops: int = -1, fade_ms: int = 700) -> None:
        if self.pygame is None or not path.is_file():
            return
        try:
            if not self.pygame.mixer.get_init():
                self.pygame.mixer.init()
            self.pygame.mixer.music.load(str(path))
            self.pygame.mixer.music.set_volume(0.65)
            self.pygame.mixer.music.play(loops, fade_ms=fade_ms)
        except (self.pygame.error, OSError):
            self.notice = f"Music could not start: {path.name}"

    def _stop_cavern_music(self) -> None:
        if self.pygame is not None and self.pygame.mixer.get_init():
            self.pygame.mixer.music.fadeout(350)

    def _click(self, event: tk.Event) -> None:
        x, y = self.canvas.logical_x(event.x), self.canvas.logical_y(event.y)
        if self.screen == "battle":
            outcome = self.battle.click(x, y, time.monotonic())
            if outcome:
                self._finish_battle(outcome)
            return
        if self.screen == "game" and self.dialogue.active:
            self._activate()
            return
        if self.screen == "game" and self.game_menu.active:
            if self.game_menu.click(int(x), int(y)) == "title":
                self._leave_cavern()
            return
        if self.screen == "settings":
            for index in range(3):
                if 178 <= x <= 782 and abs(y - (273 + index * 64)) <= 25:
                    self.settings_selection = index
                    self._activate()
                    return
        if self.screen != "menu":
            return
        index = round((y - 260) / 64)
        if (0 <= index < len(self.menu_items) and 297 <= x <= 663
                and abs(y - (260 + index * 64)) <= 25):
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
        self.encounters = EncounterMeter()
        self.hp, self.potions, self.gold = MAX_HP, MAX_POTIONS, 0
        self.level, self.xp = 1, 0
        self.party = [{"name": "Retri", "hp": MAX_HP, "max_hp": MAX_HP}]
        self.temur_story = "waiting"
        self.temur_tile = (10, 7)
        self.temur_image = tk.PhotoImage(master=self.root, file=str(ASSETS / "temur-world-v2.png")).subsample(2).zoom(SCALE)
        self.chest_tile = (12, 5)
        self.chest_open = False
        self.chest_images = [tk.PhotoImage(master=self.root, file=str(ASSETS / name)).zoom(SCALE)
                             for name in ("chest-closed.png", "chest-open.png")]
        if not hasattr(self, "battle"):
            self.battle = BattleScene(self.canvas, self._font, ASSETS,
                                      lambda: self.dialogue.portrait(RETRI_PORTRAIT, RETRI_PORTRAIT_REGION))
            self.battle_transition = BattleTransition(self.canvas)
            self.feather_image = tk.PhotoImage(master=self.root, file=str(ASSETS / "battle" / "feather-v2.png")).zoom(3)
        self.chunk_cache: dict[tuple[int, int], tk.PhotoImage] = {}
        self.chunk_items: dict[tuple[int, int], int] = {}
        self.world_camera = (0.0, 0.0)
        self.player_item = self.canvas.create_image(0, 0, anchor="center", tags=("player",))
        self.temur_item = self.canvas.create_image(0, 0, image=self.temur_image, tags=("temur",))
        self.chest_item = self.canvas.create_image(0, 0, image=self.chest_images[0], tags=("chest",))
        self.drawn_player_frame = None
        self.held_direction: str | None = None
        self.next_step_at = 0.0
        self.canvas.create_rectangle(18, VIEW_H*SCALE-98, 570, VIEW_H*SCALE-18,
                                     fill="#101625", outline="#ad8c54", width=3, tags=("hud",))
        self.canvas.create_text(36, VIEW_H*SCALE-76, anchor="w", fill=GOLD,
                                font=self._font(22, True), text="SUNREST EXCAVATION · FLOOR 1",
                                tags=("hud",))
        self.canvas.create_text(36, VIEW_H*SCALE-39, anchor="w", fill="#d1d5dc",
                                font=self._font(17), text="D-PAD / WASD TO WALK · ESC / OPTIONS FOR MENU",
                                tags=("hud",))
        self._update_world(force=True)
        self._start_cavern_music()
        self.dialogue.show([
            DialogueLine("Retri", "That sound again. It came from inside this cave.",
                         RETRI_PORTRAIT, thought=True,
                         portrait_region=RETRI_PORTRAIT_REGION),
            DialogueLine("Retri", "I'm a skirter. I can go where the village guards won't.",
                         RETRI_PORTRAIT, thought=True,
                         portrait_region=RETRI_PORTRAIT_REGION),
            DialogueLine("Retri", "I'll find its source. Carefully.", RETRI_PORTRAIT,
                         portrait_region=RETRI_PORTRAIT_REGION),
        ])

    def _interact_temur(self) -> bool:
        dx, dy = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}[self.direction]
        if self.temur_story != "waiting" or (int(self.x // TILE) + dx, int(self.y // TILE) + dy) != self.temur_tile:
            return False
        self.temur_story = "intro"
        self.dialogue.show([
            DialogueLine("Temur", "What brings you into a place like this?"),
            DialogueLine("Retri", "I heard a strange noise outside the cave and followed it in.", RETRI_PORTRAIT, portrait_region=RETRI_PORTRAIT_REGION),
            DialogueLine("Temur", "A sound? I heard it too. Stay close."),
        ])
        return True

    def _interact_chest(self) -> None:
        dx, dy = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}[self.direction]
        tile = (int(self.x // TILE) + dx, int(self.y // TILE) + dy)
        if tile != self.chest_tile:
            return
        if not self.chest_open:
            self.chest_open = True
            self.potions += 1
            self.canvas.itemconfigure(self.chest_item, image=self.chest_images[1])
            message = "Found a Potion!"
        else:
            message = "The chest is empty."
        self.dialogue.show([DialogueLine("", message)])

    def _begin_battle(self, now: float) -> None:
        self.screen = "battle_in"
        self.keys.clear()
        self.held_direction = None
        self.battle_transition.start(now)

    def _show_game_over(self, now: float) -> None:
        self.screen = "game_over"
        self.game_over_selection = 0
        self.game_over_started = now
        self.menu_nav_after = now + 0.2
        c = self.canvas
        c.create_rectangle(0, 0, 960, 540, fill="#10101b", outline="", tags="game_over")
        c.create_text(480, 145, text="GAME OVER", fill=GOLD, font=self._font(50, True), tags="game_over")
        self.feather_item = c.create_image(480, 180, image=self.feather_image, tags="game_over")
        self.game_over_options = [c.create_text(480, 360 + i*55, text=label, fill=CREAM,
                                  font=self._font(30, True), tags="game_over")
                                  for i, label in enumerate(("▶  CONTINUE", "TITLE SCREEN"))]
        c.create_text(480, 493, text="D-PAD / ARROWS · ENTER / CROSS", fill=MUTED,
                      font=self._font(21), tags="game_over")

    def _finish_battle(self, outcome: str) -> None:
        model = self.battle.model
        if outcome == "victory":
            self.gold += model.gold_reward
            self.level, self.xp = gain_xp(self.level, self.xp, model.xp_reward)
            self.hp = min(MAX_HP + (self.level - 1) * 5, model.hp + 8 + (self.level - model.level) * 5)
            self.potions = max(model.potions, min(MAX_POTIONS, model.potions + 1))
        elif outcome == "defeat":
            self.x, self.y = self.cave.spawn
            self.hp, self.potions = MAX_HP + (self.level - 1) * 5, MAX_POTIONS
            for member in self.party:
                member["hp"] = member["max_hp"]
        else:
            self.hp, self.potions = model.hp, model.potions
        self.encounters.reset()
        self.screen = "battle_out"
        self.keys.clear()
        self.battle_transition.start(time.monotonic())

    def _update_battle_transition(self, now: float) -> None:
        progress = self.battle_transition.update(now)
        if self.pygame is not None and self.pygame.mixer.get_init():
            self.pygame.mixer.music.set_volume(0.65 * (1 - progress))
        if progress < 1:
            return
        if self.screen == "battle_in":
            enemy = [self.encounters.rng.choice(ENEMIES) for _ in range(self.encounters.rng.randint(1, 3))]
            self.party[0]["hp"] = self.hp
            self.party[0]["max_hp"] = MAX_HP + (self.level-1)*5
            self.battle.start(BattleModel(enemy, self.hp, self.potions, level=self.level, xp=self.xp, party=self.party), now)
            self.screen = "battle"
            self._play_music(BATTLE_MUSIC)
        else:
            self.battle.close()
            self.screen = "game"
            self.direction, self.walk_frame = "down", 1
            self._update_world(force=True)
            self.held_direction = None
            self.next_step_at = now + STEP_INTERVAL
            self._start_cavern_music()
        self.battle_transition.close()

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
        self.canvas.coords(self.chest_item, (self.chest_tile[0]*TILE + TILE/2-cx)*SCALE,
                           (self.chest_tile[1]*TILE + TILE/2-cy)*SCALE)
        self.canvas.coords(self.temur_item, (self.temur_tile[0]*TILE + TILE/2-cx)*SCALE,
                           (self.temur_tile[1]*TILE + TILE/2-cy)*SCALE)
        self._place_player(camera)

    def _place_player(self, camera: tuple[float, float]) -> None:
        cx, cy = camera
        screen_x, screen_y = (self.x-cx)*SCALE, (self.y-cy)*SCALE
        frame = self.player_frames[self.direction][self.walk_frame]
        if frame is not self.drawn_player_frame:
            self.canvas.itemconfigure(self.player_item, image=frame)
            self.drawn_player_frame = frame
        self.canvas.coords(self.player_item, screen_x, screen_y)

    def _tick(self) -> None:
        now = time.monotonic()
        self._scan_controller(now)
        self.pad_keys = self._dpad()
        buttons = self._controller_buttons()
        tapped = buttons - self.pad_buttons
        self.pad_buttons = buttons
        if "confirm" in tapped:
            self._activate()
        if "back" in tapped:
            self._back()
        if "menu" in tapped:
            self._toggle_game_menu()
        direction = self._menu_direction()
        if self.screen == "menu" and direction in ("up", "down") and now >= self.menu_nav_after:
            new_selection = (self.selection + (-1 if direction == "up" else 1)) % len(self.menu_items)
            if new_selection != self.selection:
                self.selection = new_selection
                self._draw_menu()
            self.menu_nav_after = now + 0.18
        elif self.screen == "settings":
            self._navigate_settings(direction, now)
        elif self.screen == "cave_shake":
            elapsed = now - self.shake_started
            shift = (3 if int(elapsed*20)%2 else -3) if elapsed < 1.0 else 0
            self.canvas.move("world", shift - getattr(self, "shake_shift", 0), 0)
            self.canvas.move("player", shift - getattr(self, "shake_shift", 0), 0)
            self.canvas.move("temur", shift - getattr(self, "shake_shift", 0), 0)
            self.canvas.move("chest", shift - getattr(self, "shake_shift", 0), 0)
            self.shake_shift = shift
            if elapsed >= 1.0:
                self.screen, self.temur_story = "game", "joining"
                self.dialogue.show([
                    DialogueLine("Retri", "The whole cave is shaking!"),
                    DialogueLine("Temur", "The mountain is restless. We should travel together."),
                    DialogueLine("Retri", "I'm Retri. Glad to have you with me."),
                    DialogueLine("", "Temur joined the party!"),
                ])
        elif self.screen == "faint":
            if now - self.faint_started >= 1.5:
                self._show_game_over(now)
        elif self.screen == "game_over":
            elapsed = now - self.game_over_started
            self.canvas.coords(self.feather_item, 480 + math.sin(elapsed * 1.8)*45, 180 + min(130, elapsed*25))
            if direction in ("up", "down") and now >= self.menu_nav_after:
                self.game_over_selection = 1 - self.game_over_selection
                self.menu_nav_after = now + 0.2
                for i, label in enumerate(("CONTINUE", "TITLE SCREEN")):
                    self.canvas.itemconfigure(self.game_over_options[i], text=("▶  " if i == self.game_over_selection else "") + label,
                                              fill=GOLD if i == self.game_over_selection else CREAM)
        elif self.screen in ("battle_in", "battle_out"):
            self._update_battle_transition(now)
        elif self.screen == "battle":
            self.battle.navigate(direction, now)
            previous_phase = self.battle.phase
            self.battle.update(now)
            if previous_phase != "result" and self.battle.phase == "result" and self.battle.model.outcome == "victory":
                self._play_music(VICTORY_MUSIC, loops=0, fade_ms=100)
            elif previous_phase != "result" and self.battle.phase == "result" and self.battle.model.outcome == "defeat":
                self.screen, self.faint_started = "faint", now
                self._play_music(GAME_OVER_MUSIC, loops=0, fade_ms=200)
        elif self.screen == "game" and self.game_menu.active:
            self.game_menu.navigate(direction, now)
        elif self.screen == "game" and not self.dialogue.active:
            # One input step is one complete tile. Retri never rests across a
            # floor/wall edge, even when a direction is held.
            active = direction
            if active:
                if active != self.held_direction:
                    self.held_direction = active
                    self.next_step_at = now
                if now >= self.next_step_at:
                    dx, dy = {"up": (0, -1), "down": (0, 1),
                              "left": (-1, 0), "right": (1, 0)}[active]
                    old_direction, old_frame = self.direction, self.walk_frame
                    self.direction = active
                    nx, ny = self.x + dx * TILE, self.y + dy * TILE
                    if self.cave.walkable(nx, ny) and (int(nx // TILE), int(ny // TILE)) != self.chest_tile and (self.temur_story == "joined" or (int(nx // TILE), int(ny // TILE)) != self.temur_tile):
                        self.x, self.y = nx, ny
                        self.walk_frame = 0 if self.walk_frame == 2 else 2
                        self._update_world()
                        if self.encounters.step():
                            self._begin_battle(now)
                    else:
                        self.walk_frame = 1
                        if (self.direction, self.walk_frame) != (old_direction, old_frame):
                            self._update_world()
                    self.next_step_at = now + STEP_INTERVAL
            else:
                self.held_direction = None
                if self.walk_frame != 1:
                    self.walk_frame = 1
                    self._update_world()
        self.tick_after = self.root.after(FRAME_MS, self._tick)

    def _close(self) -> None:
        if hasattr(self, "tick_after"):
            self.root.after_cancel(self.tick_after)
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
