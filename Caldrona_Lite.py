from __future__ import annotations

import ctypes
import math
import os
import subprocess
import sys
import time
import tkinter as tk
import tkinter.font as tkfont
from collections import OrderedDict
from pathlib import Path

from abilities import attune, remember
from dialogue import DialogueBox, DialogueLine
from astral_scene import AstralScene
from display_settings import (DisplayConfig, ScaledCanvas, available_sizes,
                              load_display, pixel_scale, save_display)
from game_menu import GameMenu
from stats import RETRI, TEMUR, member, grow
from consumables import SUPPLIES, apply_supply
from equipment import STARTING_GEAR, stat_value
from battle import (BattleModel, BattleScene, BattleTransition, EncounterMeter,
                    ENEMIES, MAX_HP, MAX_POTIONS, gain_xp, SHALEHORN, ShalehornBattle, cave_encounter)

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
# Title theme from the main game's assets/music/gold.wav, encoded at 128 kbps.
TITLE_MUSIC = ASSETS / "audio" / "gold.mp3"
TITLE_FADE_IN_MS = 1500
TITLE_FADE_OUT_MS = 700
RETRI_PORTRAIT = ASSETS / "portraits" / "retri-v2.png"
RETRI_PORTRAIT_REGION = None
TEMUR_PORTRAIT = ASSETS / "portraits" / "temur.png"
MERREN_PORTRAIT = ASSETS / "portraits" / "merren.png"
INK = "#101722"
GOLD = "#f0d28c"
MUTED = "#a7b2c2"
CREAM = "#fff1cf"
# Home-menu palette from the main game's MainMenu.
MENU_INK = "#f6edcf"
MENU_GOLD = "#d9b873"
MENU_MUTED = "#96a1bd"
MENU_W, MENU_H = 960, 540
# Same panel metrics as the main home menu, shortened for Lite's three rows.
MENU_PANEL_TOP = 216
MENU_ROW_OFFSET = 38
MENU_ROW_STRIDE = 40
SETTINGS_PANEL_TOP = 148
SETTINGS_ROW_OFFSET = 68
SETTINGS_ROW_STRIDE = 40


# Shown labels only. menu_items stays PLAY, LOAD GAME, SETTINGS in that order.
MENU_LABELS = {
    "PLAY": "NEW JOURNEY",
    "LOAD GAME": "CONTINUE",
    "SETTINGS": "SETTINGS",
}


def _register_bundled_fonts() -> list[str]:
    """Make the bundled pixel fonts visible before Tk starts."""
    handles: list[str] = []
    fonts = ROOT / "fonts"
    files = ("VT323-Regular.ttf", "PressStart2P-Regular.ttf")
    if sys.platform == "win32" and hasattr(ctypes, "windll"):
        add_font = ctypes.windll.gdi32.AddFontResourceExW
        add_font.argtypes = (ctypes.c_wchar_p, ctypes.c_uint, ctypes.c_void_p)
        add_font.restype = ctypes.c_int
        for filename in files:
            path = fonts / filename
            if path.exists() and add_font(str(path), 0x10, None):
                handles.append(str(path))
        return handles
    dest = Path.home() / ".local" / "share" / "fonts" / "caldrona-lite"
    try:
        dest.mkdir(parents=True, exist_ok=True)
        changed = False
        for filename in files:
            source = fonts / filename
            if not source.exists():
                continue
            target = dest / filename
            data = source.read_bytes()
            if not target.exists() or target.read_bytes() != data:
                target.write_bytes(data)
                changed = True
        if changed:
            subprocess.run(["fc-cache", "-f", str(dest)], check=False,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        pass
    return handles


def _menu_row_y(index: int) -> int:
    return MENU_PANEL_TOP + MENU_ROW_OFFSET + index * MENU_ROW_STRIDE


def _settings_row_y(index: int) -> int:
    return SETTINGS_PANEL_TOP + SETTINGS_ROW_OFFSET + index * SETTINGS_ROW_STRIDE


class TitleBackdrop:
    """Animated Caldrona title landscape, ported from the main game's TitleScreen.

    Artwork stays on the 960×540 logical canvas. Background frames are 384 wide,
    so they are enlarged with Tk's integer nearest-neighbor zoom (ceil(960/384) = 3).
    """

    DURATION = 12.0
    SIZES = (256, 384, 576, 768, 960)
    WATER = ((181, 155), (191, 159), (194, 166), (199, 174), (209, 183), (217, 193), (220, 200))
    STARS = ((47, 32), (118, 21), (156, 47), (242, 25), (303, 44))

    def __init__(self, root: tk.Misc, art: Path) -> None:
        self.root = root
        self.art = art
        self.menu_age = 0.0
        self.last_tick = time.monotonic()
        self.scaled: OrderedDict[tuple[str, int], tk.PhotoImage] = OrderedDict()
        self.logos: OrderedDict[tuple[int, int], tk.PhotoImage] = OrderedDict()
        self.scale: int | None = None

    def advance(self, now: float) -> None:
        dt = max(0.0, min(0.25, now - self.last_tick))
        self.last_tick = now
        self.menu_age += dt

    def sky(self) -> tuple[str, int]:
        # Home menu: hold each sky, then blend toward the next over the last 1.5s.
        stage = (3 + int(self.menu_age / 10)) % 4
        blend = round(max(0.0, (self.menu_age % 10 - 8.5) / 1.5) * 15)
        return f"sky-{stage}-{min(15, blend)}", stage

    def image(self, name: str, scale: int) -> tk.PhotoImage | None:
        if self.scale != scale:
            self.scaled.clear()
            self.scale = scale
        key = (name, scale)
        if key not in self.scaled:
            path = self.art / f"{name}.png"
            if not path.is_file():
                return None
            source = tk.PhotoImage(master=self.root, file=str(path))
            self.scaled[key] = source.zoom(scale, scale) if scale > 1 else source
            if len(self.scaled) > 24:
                self.scaled.popitem(last=False)
        self.scaled.move_to_end(key)
        return self.scaled[key]

    def logo(self, width: int, alpha: int) -> tk.PhotoImage | None:
        key = (width, alpha)
        if key not in self.logos:
            path = self.art / f"logo-{width}-{alpha}.png"
            if not path.is_file():
                return None
            self.logos[key] = tk.PhotoImage(master=self.root, file=str(path))
            if len(self.logos) > 24:
                self.logos.popitem(last=False)
        self.logos.move_to_end(key)
        return self.logos[key]

    def draw(self, canvas: tk.Canvas, full_logo: bool = True) -> None:
        w, h = MENU_W, MENU_H
        canvas.create_rectangle(0, 0, w, h, fill="#060b19", outline="")
        scale = max(1, math.ceil(w / 384))
        name, stage = self.sky()
        image = self.image(name, scale)
        age = self.DURATION + self.menu_age
        left, top = 0, 0
        if image is not None:
            margin = max(0, (image.width() - w) / 2)
            left = round(-margin + math.sin(age * 0.14) * min(margin, 8 * scale))
            top = (h - image.height()) // 2
            canvas.create_image(left, top, image=image, anchor="nw", tags="title_sky")
            water_color = "#f6bd75" if stage == 3 else "#c0daf4"
            for n, (x, y) in enumerate(self.WATER):
                drift = math.sin(age * 1.3 + n) * 1.2
                if math.sin(age * 2 + n) > 0.15:
                    canvas.create_line(
                        left + (x + drift) * scale, top + y * scale,
                        left + (x + drift + 3) * scale, top + y * scale,
                        fill=water_color, width=max(1, scale), tags="title_water",
                    )
            if stage >= 2:
                for n, (x, y) in enumerate(self.STARS):
                    light = (math.sin(age * 1.5 + n) + 1) / 2
                    if light > 0.55:
                        color = "#ffe0a8" if stage == 3 else "#d8e9ff"
                        canvas.create_rectangle(
                            left + x * scale, top + y * scale,
                            left + (x + 1) * scale, top + (y + 1) * scale,
                            fill=color, outline="", tags="title_star",
                        )
        if not full_logo:
            return
        cap = min(w - 52, h * 0.93)
        width = max(n for n in self.SIZES if n <= cap)
        # Settled home-menu wordmark (the main game uses alpha step 15 after the reveal).
        logo = self.logo(width, 15)
        y = h * 0.21
        if logo is None:
            canvas.create_text(w / 2, y, text="CALDRONA", fill=MENU_GOLD,
                               font=("Press Start 2P", -16), tags="title_logo")
            return
        canvas.create_image(w / 2, y, image=logo, anchor="center", tags="title_logo")
        for n, dx in enumerate((-0.29, -0.12, 0.08, 0.29)):
            twinkle = max(0.0, math.sin(age * 2 + n * 1.7))
            if twinkle > 0.8:
                x = w / 2 + width * dx
                sy = y + logo.height() * 0.36
                r = 2 + twinkle * 2
                canvas.create_line(x - r, sy, x + r, sy, fill="#fff2ba", width=1, tags="title_glint")
                canvas.create_line(x, sy - r, x, sy + r, fill="#fff2ba", width=1, tags="title_glint")


class CavernInstance:
    """A fixed first-floor cave, built once and kept as a light tile map."""

    width, height = 84, 36

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
        self._room(64, 9, 77, 21)
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


class GrasslandInstance:
    """An open field with a mountain face and an entrance back to the cave."""
    width, height = 64, 40

    def __init__(self):
        self.floor = {(x, y) for y in range(3, self.height - 1)
                      for x in range(1, self.width - 1)}

    def walkable(self, px, py):
        return (int(px // TILE), int(py // TILE)) in self.floor


class CaldronaLite:
    """A low-cost retro menu and single-character cavern exploration slice."""

    def __init__(self) -> None:
        self._font_handles = _register_bundled_fonts()
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
        self._init_controller()
        self.dialogue = DialogueBox(self.canvas, self.root, self._font)
        self.dialogue.register_portrait("Retri", RETRI_PORTRAIT, RETRI_PORTRAIT_REGION)
        self.dialogue.register_portrait("Temur", TEMUR_PORTRAIT)
        self.dialogue.register_portrait("Merren", MERREN_PORTRAIT)
        self.game_menu = GameMenu(
            self.canvas, self._font,
            lambda: self.dialogue.portrait(RETRI_PORTRAIT, RETRI_PORTRAIT_REGION),
        )
        self.game_menu.roster = lambda: self.party
        self.game_menu.inventory = self._supply_inventory
        self.game_menu.use_item = self._use_menu_item
        self.game_menu.gear_inventory = lambda: self.gear_inventory
        self.game_menu.gear_changed = self._gear_changed
        self.game_menu.progress = lambda: (self.level, self.xp, 30*self.level)
        self.game_menu.sync_unlocked = lambda: self.astral_sync
        self.game_menu.party_names = lambda: [member["name"] for member in getattr(self, "party", [{"name": "Retri"}]) if member.get("active", True)]
        self.game_menu.party_portrait = lambda name: self.dialogue.portrait(
            TEMUR_PORTRAIT if name == "Temur" else RETRI_PORTRAIT,
            None if name == "Temur" else RETRI_PORTRAIT_REGION,
        ) if name in ("Retri", "Temur") else None

        self.screen = "menu"
        self.selection = 0
        self.notice = ""
        self.notice_message = ""
        self.menu_items = ("PLAY", "LOAD GAME", "SETTINGS")
        self.lab_compare = False
        self.title_art = TitleBackdrop(self.root, ASSETS / "title")
        self.menu_anim_at = 0.0
        self._pending_music: tuple[Path, int, int, float] | None = None
        self._music_bed: str | None = None
        self._menu_font_family: str | None = None
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

        for key in ("Up", "Down", "Left", "Right", "w", "a", "s", "d", "Return", "Escape", "t", "T", "r", "R", "c", "C"):
            self.root.bind(f"<KeyPress-{key}>", self._key_down)
            self.root.bind(f"<KeyRelease-{key}>", self._key_up)
        self.root.bind("<Button-1>", self._click)
        self.root.protocol("WM_DELETE_WINDOW", self._close)
        self._draw_menu()
        self._start_title_music()
        self.tick_after = self.root.after(FRAME_MS, self._tick)
        self.root.mainloop()

    def _font(self, size: int, bold: bool = False) -> tuple[str, int, str]:
        family = "VT323" if "VT323" in tkfont.families(self.root) else "Consolas"
        return family, size, "bold" if bold else "normal"

    def _pixel_font(self, pixels: int, family: str = "Press Start 2P") -> tuple[str, int]:
        """Pixel size, not points, so Press Start 2P and VT323 stay on the grid."""
        if self._menu_font_family is None:
            self._menu_font_family = ""
            self._font_families = set(tkfont.families(self.root))
        if family not in self._font_families:
            family = "VT323" if "VT323" in self._font_families else "Courier New"
        return family, -abs(pixels)

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
                ("member_previous", self.pygame.CONTROLLER_BUTTON_LEFTSHOULDER),
                ("member_next", self.pygame.CONTROLLER_BUTTON_RIGHTSHOULDER),
            ) if self.pad.get_button(button)}
        if self.joystick is not None and self.joystick.get_init():
            count = self.joystick.get_numbuttons()
            # Common DS4 DirectInput order: Cross/Circle 1/2, L1/R1 4/5.
            return {name for index, name in ((1, "confirm"), (2, "back"),
                                              (4, "member_previous"), (5, "member_next"), (9, "menu"))
                    if count > index and self.joystick.get_button(index)}
        return set()

    def _key_down(self, event: tk.Event) -> None:
        key = str(event.keysym).lower()
        if self.screen == "sprite_lab":
            if key in self.keys:
                return
            self.keys.add(key)
            if key == "escape":
                self._draw_menu()
            elif key == "c":
                self.lab_compare = not self.lab_compare
                self._draw_sprite_lab()
            elif key == "r":
                selected = self.lab_index
                self._open_sprite_lab()
                self.lab_index = selected
                self._draw_sprite_lab()
            elif key in ("left", "a", "right", "d"):
                self.lab_index = (self.lab_index + (-1 if key in ("left", "a") else 1)) % len(self.lab_sprites)
                self._draw_sprite_lab()
            return
        if self.screen == "menu" and key == "t":
            if key not in self.keys:
                self.keys.add(key)
                self._open_sprite_lab()
            return
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

    def _draw_title_scene(self, show_title: bool = True) -> None:
        self.canvas.delete("all")
        self.canvas.configure(background="#060b19")
        self.title_art.draw(self.canvas, full_logo=show_title)
        if not show_title:
            self.canvas.create_text(MENU_W / 2, 34, text="CALDRONA", fill=MENU_GOLD,
                                   font=self._pixel_font(16))

    def _menu_panel(self, x1: float, y1: float, x2: float, y2: float) -> None:
        c = self.canvas
        c.create_rectangle(x1 + 5, y1 + 6, x2 + 5, y2 + 6, fill="#080c1c", outline="")
        c.create_rectangle(x1, y1, x2, y2, fill="#17203d", outline=MENU_GOLD, width=2)
        c.create_rectangle(x1 + 5, y1 + 5, x2 - 5, y2 - 5, outline="#586080")
        for x in (x1, x2):
            for y in (y1, y2):
                c.create_rectangle(x - 2, y - 2, x + 2, y + 2, fill=MENU_GOLD, outline="")

    def _menu_footer(self, hint: str, status: str = "", *, alert: bool = False) -> None:
        c = self.canvas
        c.create_rectangle(0, MENU_H - 72, MENU_W, MENU_H, fill="#060b19", outline="", tags="menu_footer")
        c.create_text(MENU_W / 2, MENU_H - 46, text=hint, fill="#c7ccdc", font=self._pixel_font(8))
        c.create_text(28, MENU_H - 22, text=status or "© CALDRONA", anchor="w",
                      fill=MENU_GOLD if alert else MENU_MUTED, font=self._pixel_font(8))

    def _draw_menu(self) -> None:
        self.screen = "menu"
        self.root.title("Caldrona Lite")
        self._draw_title_scene()
        top = MENU_PANEL_TOP
        bottom = top + MENU_ROW_OFFSET + (len(self.menu_items) - 1) * MENU_ROW_STRIDE + 36
        self._menu_panel(MENU_W / 2 - 182, top, MENU_W / 2 + 182, bottom)
        for index, label in enumerate(self.menu_items):
            y = _menu_row_y(index)
            active = index == self.selection
            self.canvas.create_rectangle(
                MENU_W / 2 - 159, y - 19, MENU_W / 2 + 159, y + 19,
                fill="#263153" if active else "#17203d", outline="",
            )
            if active:
                self.canvas.create_text(MENU_W / 2 - 148, y, text=">", fill=MENU_GOLD,
                                        font=self._pixel_font(8))
            self.canvas.create_text(
                MENU_W / 2, y, text=MENU_LABELS[label],
                fill=MENU_GOLD if active else MENU_INK, font=self._pixel_font(16),
            )
        status = "RESTART TO APPLY DISPLAY CHANGE" if self.saved_display != self.active_display else ""
        self._menu_footer(
            "ARROWS MOVE    PUSH ENTER    ESC BACK",
            status, alert=bool(status),
        )

    def _open_sprite_lab(self) -> None:
        # The title screen is available before the cavern creates BattleScene.
        # Load only the preview images here, without starting or changing a game.
        root = ASSETS / "battle"
        self.lab_sprites = []
        for name in ("Retri", "Temur"):
            variants = [("Unbound", root / f"{name.lower()}-v2.png")]
            for job in ("Sollers", "Saint", "Seer"):
                variants.append((job, root / "classes" / f"{name.lower()}-{job.lower()}.png"))
                variants.extend((f"{job} · {pose.title()}", root / "classes" /
                                 f"{name.lower()}-{job.lower()}-{pose}.png")
                                for pose in ("guard", "fainted"))
            variants.append(("Guard", root / f"{name.lower()}-guard.png"))
            faint = "retri-fainted-v2.png" if name == "Retri" else "temur-fainted-v1.png"
            variants.append(("Fainted", root / faint))
            for label, path in variants:
                image = tk.PhotoImage(master=self.root, file=str(path)).zoom(2)
                self.lab_sprites.append((f"{name} · {label}", image))
        self.lab_index = 0
        self._draw_sprite_lab()

    def _draw_sprite_lab(self) -> None:
        self.screen = "sprite_lab"
        self._draw_frame(show_title=False)
        name, sprite = self.lab_sprites[self.lab_index]
        self.canvas.create_text(480, 75, text="SPRITE TEST", fill=GOLD, font=self._font(36, True))
        self.canvas.create_text(480, 135, text=name.upper(), fill=CREAM, font=self._font(28, True))
        self.canvas.create_rectangle(300, 175, 660, 405, fill="#202b3c", outline="#65748b", width=3)
        # Fainted art uses the same offset as battle, aligning both feet
        # to the same ground when comparing standing and fallen poses.
        pose_y = 298 if name.endswith("Fainted") else 290
        if self.lab_compare:
            parts = name.split(" · ")
            job = parts[1] if parts[1] in ("Sollers", "Saint", "Seer") else "Unbound"
            standing = next(image for label, image in self.lab_sprites
                            if label == f"{parts[0]} · {job}")
            self.canvas.create_text(390, 208, text="STANDING", fill=MUTED, font=self._font(18))
            self.canvas.create_text(570, 208, text="SELECTED", fill=MUTED, font=self._font(18))
            self.canvas.create_line(330, 314, 630, 314, fill="#65748b")
            self.canvas.create_image(390, 290, image=standing)
            self.canvas.create_image(570, pose_y, image=sprite)
        else:
            self.canvas.create_image(480, pose_y, image=sprite)
        self.canvas.create_text(480, 449, text="LEFT / RIGHT: SPRITE   C: COMPARE   R: RELOAD   ESC: TITLE", fill=MUTED, font=self._font(19))
        self.canvas.create_text(480, 486, text=f"{self.lab_index + 1} / {len(self.lab_sprites)}", fill=GOLD, font=self._font(20))

    def _open_settings(self) -> None:
        self.pending_display = self.saved_display
        self.settings_selection = 0
        self.settings_notice = ""
        self.settings_direction = None
        self._draw_settings()

    def _draw_settings(self) -> None:
        self.screen = "settings"
        self._draw_title_scene(show_title=False)
        rows = (
            ("MODE", self.pending_display.mode.upper()),
            ("WINDOW SIZE", f"{self.pending_display.width} x {self.pending_display.height}"
             if self.pending_display.mode == "windowed" else "DESKTOP"),
            ("APPLY", "PENDING" if self.pending_display != self.saved_display
             else "RESTART REQUIRED" if self.saved_display != self.active_display
             else "NO CHANGE"),
        )
        top = SETTINGS_PANEL_TOP
        bottom = top + SETTINGS_ROW_OFFSET + (len(rows) - 1) * SETTINGS_ROW_STRIDE + 36
        self._menu_panel(MENU_W / 2 - 182, top, MENU_W / 2 + 182, bottom)
        self.canvas.create_text(MENU_W / 2, top + 28, text="DISPLAY SETTINGS", fill=MENU_GOLD,
                                font=self._pixel_font(8))
        for index, (label, value) in enumerate(rows):
            y = _settings_row_y(index)
            active = index == self.settings_selection
            self.canvas.create_rectangle(
                MENU_W / 2 - 159, y - 16, MENU_W / 2 + 159, y + 16,
                fill="#263153" if active else "#17203d", outline="",
            )
            if active:
                self.canvas.create_text(MENU_W / 2 - 148, y, text=">", fill=MENU_GOLD,
                                        font=self._pixel_font(8))
            self.canvas.create_text(MENU_W / 2 - 132, y, text=label, anchor="w",
                                    fill=MENU_GOLD if active else MENU_INK,
                                    font=self._pixel_font(20, "VT323"))
            self.canvas.create_text(MENU_W / 2 + 143, y, text=value, anchor="e",
                                    fill=MENU_GOLD if active else MENU_INK,
                                    font=self._pixel_font(20, "VT323"))
        self._menu_footer(
            "ARROWS MOVE    LEFT RIGHT    PUSH ENTER",
            self.settings_notice or "4:3 WINDOW    ESC BACK",
            alert=bool(self.settings_notice),
        )

    def _draw_notice(self, message: str) -> None:
        self.screen = "notice"
        self.notice_message = message
        self._draw_title_scene()
        self._menu_panel(MENU_W / 2 - 220, 220, MENU_W / 2 + 220, 400)
        self.canvas.create_text(MENU_W / 2, 286, text=message, fill=MENU_INK,
                                font=self._pixel_font(22, "VT323"), width=400)
        self.canvas.create_text(MENU_W / 2, 352, text="PUSH ENTER",
                                fill=MENU_GOLD, font=self._pixel_font(8))
        self._menu_footer("ESC BACK")

    def _activate(self) -> None:
        if self.screen == "shop":
            self._buy_supply()
            return
        if self.screen in ("faint", "cave_shake"):
            return
        if self.screen == "astral":
            self._finish_astral(self.astral_scene.confirm())
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
                if not self.dialogue.active and self.merren_shop_pending:
                    self.merren_shop_pending = False
                    self._open_merren_shop()
                    return
                if not self.dialogue.active and self.grass_intro_active:
                    self.grass_intro_active = False
                    self.grass_camera = None
                    self.canvas.itemconfigure(self.grass_temur_item, state="hidden")
                if not self.dialogue.active and self.boss_intro:
                    self.boss_intro = False
                    self._begin_battle(time.monotonic())
                elif not self.dialogue.active and getattr(self, "temur_story", "") == "intro":
                    self.temur_story, self.screen = "shaking", "cave_shake"
                    self.shake_started = time.monotonic()
                elif not self.dialogue.active and getattr(self, "temur_story", "") == "joining":
                    self.temur_story = "joined"
                    self._recruit(member("Temur", TEMUR))
                    self.canvas.itemconfigure(self.temur_item, state="hidden")
            elif self.game_menu.active:
                action = self.game_menu.activate()
                if action == "title":
                    self._leave_cavern()
                elif action == "sync":
                    self._open_astral(reveal=False)
            elif not self.game_menu.active:
                if not self._interact_merren() and not self._interact_quarry() and not self._interact_temur():
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
        if self.screen == "shop":
            self.canvas.delete("merren_shop")
            self.screen = "game"
            self.held_direction = None
            self.next_step_at = time.monotonic() + STEP_INTERVAL
            return
        if self.screen in ("faint", "game_over", "cave_shake"):
            return
        if self.screen == "astral":
            self._finish_astral(self.astral_scene.back())
            return
        if self.screen == "battle":
            self.battle.back()
            return
        if self.screen in ("battle_in", "battle_out"):
            return
        if self.screen == "game":
            if self.dialogue.active:
                if self.merren_shop_pending:
                    self.merren_shop_pending = False
                    self.dialogue.clear()
                elif self.grass_intro_active or self.boss_intro or getattr(self, "temur_story", "") in ("intro", "joining"):
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
        self._queue_title_music()
        self.keys.clear()
        self.pad_keys.clear()
        self._draw_menu()

    def _start_cavern_music(self) -> None:
        self._music_bed = "cavern"
        self._play_music(CAVERN_MUSIC)

    def _start_title_music(self) -> None:
        self._music_bed = "title"
        self._play_music(TITLE_MUSIC, fade_ms=TITLE_FADE_IN_MS)

    def _music_busy(self) -> bool:
        return (self.pygame is not None and self.pygame.mixer.get_init()
                and self.pygame.mixer.music.get_busy())

    def _queue_title_music(self) -> None:
        """Let the cavern theme finish fading, then fade Gold back in."""
        if self._music_busy():
            self.pygame.mixer.music.fadeout(350)
            self._pending_music = (TITLE_MUSIC, -1, TITLE_FADE_IN_MS, time.monotonic() + 0.35)
            self._music_bed = "pending"
            return
        self._start_title_music()

    def _begin_gameplay_music(self) -> None:
        """Fade Gold out, then start the cavern theme with its existing fade-in."""
        if self._music_bed == "title" and self._music_busy():
            self.pygame.mixer.music.fadeout(TITLE_FADE_OUT_MS)
            self._pending_music = (CAVERN_MUSIC, -1, 700, time.monotonic() + TITLE_FADE_OUT_MS / 1000)
            self._music_bed = "pending"
            return
        self._start_cavern_music()

    def _flush_pending_music(self, now: float) -> None:
        pending = self._pending_music
        if pending is None or now < pending[3]:
            return
        path, loops, fade_ms, _when = pending
        self._pending_music = None
        self._music_bed = "title" if path == TITLE_MUSIC else "cavern"
        self._play_music(path, loops=loops, fade_ms=fade_ms)

    def _play_music(self, path: Path, loops: int = -1, fade_ms: int = 700) -> None:
        self._pending_music = None
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
        if self.screen == "shop":
            for index in range(len(SUPPLIES)):
                if 159 <= x <= 801 and abs(y - (196 + index * 51)) <= 22:
                    if self.shop_selection == index:
                        self._buy_supply()
                    else:
                        self.shop_selection = index
                        self._draw_merren_shop()
                    break
            return
        if self.screen == "astral":
            self._finish_astral(self.astral_scene.click(x, y))
            return
        if self.screen == "battle":
            outcome = self.battle.click(x, y, time.monotonic())
            if outcome:
                self._finish_battle(outcome)
            return
        if self.screen == "game" and self.dialogue.active:
            self._activate()
            return
        if self.screen == "game" and self.game_menu.active:
            action = self.game_menu.click(int(x), int(y))
            if action == "title":
                self._leave_cavern()
            elif action == "sync":
                self._open_astral(reveal=False)
            return
        if self.screen == "settings":
            for index in range(3):
                row = _settings_row_y(index)
                if MENU_W / 2 - 159 <= x <= MENU_W / 2 + 159 and abs(y - row) <= 16:
                    self.settings_selection = index
                    self._activate()
                    return
        if self.screen != "menu":
            return
        for index in range(len(self.menu_items)):
            row = _menu_row_y(index)
            if MENU_W / 2 - 159 <= x <= MENU_W / 2 + 159 and abs(y - row) <= 19:
                self.selection = index
                self._activate()
                return

    def _start_cavern(self) -> None:
        self.screen = "game"
        self.root.title("Caldrona Lite · Cavern")
        self.canvas.configure(background=INK)
        self.canvas.delete("all")
        self.cave = CavernInstance()
        self.cavern_map = self.cave
        self.grassland_map = GrasslandInstance()
        self.outdoors = False
        self._area_step_latch = False
        self.grass_intro_seen = self.grass_intro_active = False
        self.grass_camera = None
        self.merren_shop_pending = False
        self.merren_hint_seen = False
        self.merren_tile = (35, 5)
        self.x, self.y = self.cave.spawn
        self.direction = "down"
        self.walk_frame = 1
        cavern_art = ASSETS / "crystal_cavern"
        self.floor_tiles = [tk.PhotoImage(master=self.root, file=str(cavern_art / f"floor_{i}.png")).zoom(SCALE) for i in range(4)]
        source_walls = [tk.PhotoImage(master=self.root, file=str(cavern_art / f"wall_{i}.png")) for i in range(4)]
        self.wall_tiles = [tile.zoom(SCALE) for tile in source_walls]
        self.solid_rock_tiles = [tk.PhotoImage(master=self.root, file=str(cavern_art / f"side_wall_{i}.png")).zoom(SCALE) for i in range(3)]
        def side_wall(source, clockwise):
            # Rotate the actual horizontal wall pixels so color and texture match.
            size = source.width()
            rotated = tk.PhotoImage(master=self.root, width=size, height=size)
            for y in range(size):
                row = []
                for x in range(size):
                    sx, sy = (y, size-1-x) if clockwise else (size-1-y, x)
                    row.append("#%02x%02x%02x" % source.get(sx, sy))
                rotated.put("{" + " ".join(row) + "}", to=(0, y))
            return rotated.zoom(SCALE)
        self.side_wall_tiles = [[side_wall(tile, clockwise) for tile in source_walls[:2]]
                                for clockwise in (False, True)]
        self.crystal_tiles = [tk.PhotoImage(master=self.root, file=str(cavern_art / f"crystal_lit_{i}.png")).zoom(SCALE) for i in range(4)]
        grass_art = ASSETS / "grassland"
        def grass_image(name):
            return tk.PhotoImage(master=self.root, file=str(grass_art / f"{name}.png")).zoom(SCALE)
        self.grass_tiles = [grass_image(f"meadow{i}") for i in range(6)]
        self.path_tiles = [grass_image(f"road{i}") for i in range(2)]
        self.mountain_tiles = [grass_image(f"cliff{i}") for i in range(2)]
        self.path_edges = {(side, shift, i): grass_image(f"road-edge-{side}-{shift}-{i}")
                           for side in (-1, 1) for shift in range(4) for i in range(2)}
        self.merren_image = grass_image("merren")
        entrance = tk.PhotoImage(master=self.root, file=str(grass_art / "cliff0.png"))
        entrance.put("#20252b", to=(3, 5, 13, 16))
        entrance.put("#20252b", to=(5, 3, 11, 5))
        self.entrance_tile = entrance.zoom(SCALE)
        self.player_frames = self._load_player()
        self.encounters = EncounterMeter()
        self.hp, self.potions, self.gold = MAX_HP, MAX_POTIONS, 0
        self.supplies = {}
        self.level, self.xp = 1, 0
        self.party = [member("Retri", RETRI)]
        self.gear_inventory = dict(STARTING_GEAR)
        self.temur_story = "waiting"
        self.temur_tile = (10, 7)
        self.temur_image = tk.PhotoImage(master=self.root, file=str(ASSETS / "temur-world-v4.png")).zoom(SCALE)
        self.in_chamber = self.boss_intro = self.boss_cleared = self.astral_sync = False
        self._stone_step_latch = False
        self.stone_reveal = False
        self.outer_door, self.inner_door, self.stone_tile = (49, 4), (70, 21), (70, 14)
        self.quarry_objects = []
        for tile, filename, scale, lift in (
            (self.outer_door, "quarry-door.png", SCALE, 0),
            (self.inner_door, "quarry-door.png", SCALE, 0),
            (self.stone_tile, "astral-stone.png", SCALE, 0),
            (self.stone_tile, "battle/shalehorn.png", 2, 48),
        ):
            image = tk.PhotoImage(master=self.root, file=str(ASSETS / filename)).zoom(scale)
            item = self.canvas.create_image(0, 0, image=image)
            self.quarry_objects.append((tile, image, item, lift))
        self.chest_tile = (12, 5)
        self.chest_open = False
        self.chest_images = [tk.PhotoImage(master=self.root, file=str(ASSETS / name)).zoom(SCALE)
                             for name in ("chest-closed.png", "chest-open.png")]
        if not hasattr(self, "battle"):
            self.battle = BattleScene(self.canvas, self._font, ASSETS,
                                      lambda: self.dialogue.portrait(RETRI_PORTRAIT, RETRI_PORTRAIT_REGION))
            self.battle.member_portrait = self.game_menu.party_portrait
            self.battle.level_roster = lambda: self.party
            self.battle_transition = BattleTransition(self.canvas)
            self.feather_image = tk.PhotoImage(master=self.root, file=str(ASSETS / "battle" / "feather-v2.png")).zoom(3)
        self.chunk_cache: dict[tuple[int, int], tk.PhotoImage] = {}
        self.chunk_items: dict[tuple[int, int], int] = {}
        self.world_camera = (0.0, 0.0)
        self.player_item = self.canvas.create_image(0, 0, anchor="center", tags=("player",))
        self.temur_item = self.canvas.create_image(0, 0, image=self.temur_image, tags=("temur",))
        self.chest_item = self.canvas.create_image(0, 0, image=self.chest_images[0], tags=("chest",))
        self.merren_item = self.canvas.create_image(0, 0, image=self.merren_image, state="hidden")
        self.merren_stall = self.canvas.create_image(0, 0, image=self.chest_images[0], state="hidden")
        self.grass_temur_item = self.canvas.create_image(0, 0, image=self.temur_image, state="hidden")
        self.drawn_player_frame = None
        self.held_direction: str | None = None
        self.next_step_at = 0.0
        self.canvas.create_rectangle(18, VIEW_H*SCALE-98, 570, VIEW_H*SCALE-18,
                                     fill="#101625", outline="#ad8c54", width=3, tags=("hud",))
        self.location_label = self.canvas.create_text(36, VIEW_H*SCALE-76, anchor="w", fill=GOLD,
                                font=self._font(22, True), text="SUNREST EXCAVATION · FLOOR 1",
                                tags=("hud",))
        self.canvas.create_text(36, VIEW_H*SCALE-39, anchor="w", fill="#d1d5dc",
                                font=self._font(17), text="D-PAD / WASD TO WALK · ESC / OPTIONS FOR MENU",
                                tags=("hud",))
        self._update_world(force=True)
        self._begin_gameplay_music()
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

    def _supply_inventory(self):
        rows = {name: self.potions if name == "Potion" else self.supplies.get(name, 0)
                for name in SUPPLIES}
        carried = self.supplies.get("Ember Talisman", 0)
        if carried:
            rows["Ember Talisman"] = carried
        return rows

    def _use_menu_item(self, name, member):
        if not self._supply_inventory().get(name):
            return f"No {name} left."
        used, message = apply_supply(name, member)
        if used:
            if name == "Potion":
                self.potions -= 1
            else:
                self.supplies[name] -= 1
            if member["name"] == "Retri":
                self.hp = member["hp"]
        return message

    def _gear_changed(self, member):
        if member["name"] == "Retri":
            self.hp = member["hp"]

    def _recruit(self, member):
        if not any(p["name"] == member["name"] for p in self.party):
            member.setdefault("level", 1)
            member.setdefault("xp", 0)
            member["active"] = sum(p.get("active", True) for p in self.party) < 3
            self.party.append(member)

    def _open_astral(self, reveal=False):
        if not hasattr(self, "astral_scene"):
            self.astral_scene = AstralScene(self.canvas, self._font, ASSETS)
        if self.game_menu.active:
            self.game_menu.close()
        self.keys.clear()
        self.held_direction = None
        self._astral_direction_armed = False
        self.screen = "astral"
        self.astral_scene.start(self.party, time.monotonic(), reveal=reveal)

    def _finish_astral(self, result):
        if result == "close":
            self.screen = "game"
            self.keys.clear()
            self.held_direction = None
            self.next_step_at = time.monotonic() + 0.25

    def _interact_quarry(self):
        if self.outdoors:
            return False
        dx, dy = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}[self.direction]
        tile = (int(self.x // TILE) + dx, int(self.y // TILE) + dy)
        if tile == self.outer_door:
            self.in_chamber = True
            self.x, self.y = 70.5*TILE, 17.5*TILE
            self.direction = "up"
            self._update_world(force=True)
            if not self.boss_cleared:
                self._meet_shalehorn()
        elif tile == self.inner_door:
            self.in_chamber = False
            self.x, self.y = 49.5*TILE, 5.5*TILE
            self.direction = "down"
            self._update_world(force=True)
        elif tile == self.stone_tile:
            if not self.boss_cleared:
                self._meet_shalehorn()
            else:
                first_contact = not self.astral_sync
                self.astral_sync = True
                # The astral stone is the first stone. There is no journey save yet,
                # so this flag lives on the member and will travel with the party.
                for person in self.party:
                    attune(person, "first_stone")
                self._stone_step_latch = True
                self._open_astral(reveal=first_contact)
        else:
            return False
        return True

    def _interact_merren(self):
        if not self.outdoors:
            return False
        dx, dy = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}[self.direction]
        if (int(self.x // TILE)+dx, int(self.y // TILE)+dy) != self.merren_tile:
            return False
        self.merren_shop_pending = True
        if not self.merren_hint_seen:
            self.merren_hint_seen = True
            text = ("Your companion doesn't talk much. Usually means he knows more than he says."
                    if any(p['name'] == 'Temur' for p in self.party) else
                    "Been hearing sounds from that cave for days. Now I'm not so sure it's shifting stone.")
        else:
            text = "Good to see you again. Need anything for the road?"
        self.dialogue.show([DialogueLine("Merren", text)])
        return True

    def _open_merren_shop(self):
        self.screen = "shop"
        self.shop_selection = 0
        self.shop_feedback = ""
        self.shop_direction = None
        self.shop_repeat_at = 0.0
        self._draw_merren_shop()

    def _draw_merren_shop(self):
        c, tag = self.canvas, "merren_shop"
        c.delete(tag)
        c.create_rectangle(132, 97, 828, 449, fill="#101625", outline=GOLD, width=3, tags=tag)
        c.create_text(159, 127, text="MERREN'S WARES", anchor="w", fill=GOLD,
                      font=self._font(25, True), tags=tag)
        c.create_text(801, 127, text=f"{self.gold} GOLD", anchor="e", fill=GOLD,
                      font=self._font(22), tags=tag)
        for x, title in ((689, "PRICE"), (796, "OWNED")):
            c.create_text(x, 163, text=title, anchor="e", fill=MUTED, font=self._font(16), tags=tag)
        inventory = self._supply_inventory()
        for i, (name, (price, _)) in enumerate(SUPPLIES.items()):
            y = 196 + i * 51
            selected = self.shop_selection == i
            if selected:
                c.create_rectangle(155, y-21, 805, y+21, fill="#242181", outline="#83b7d5", tags=tag)
                c.create_text(175, y, text="▶", fill=CREAM, font=self._font(18), tags=tag)
            c.create_text(198, y, text=name, anchor="w", fill=GOLD if selected else CREAM,
                          font=self._font(22), tags=tag)
            c.create_text(689, y, text=str(price), anchor="e", fill=CREAM if self.gold >= price else "#f3a8a8",
                          font=self._font(20), tags=tag)
            c.create_text(796, y, text=str(inventory[name]), anchor="e", fill=CREAM,
                          font=self._font(20), tags=tag)
        name = tuple(SUPPLIES)[self.shop_selection]
        c.create_text(159, 353, text=SUPPLIES[name][1], anchor="w", fill=CREAM,
                      font=self._font(19), tags=tag)
        c.create_text(159, 383, text=self.shop_feedback, anchor="w", fill=GOLD,
                      font=self._font(18), tags=tag)
        c.create_text(159, 419, text="UP / DOWN MOVE   ENTER / CROSS BUY   ESC / CIRCLE BACK",
                      anchor="w", fill=MUTED, font=self._font(16), tags=tag)

    def _buy_supply(self):
        name = tuple(SUPPLIES)[self.shop_selection]
        price, _ = SUPPLIES[name]
        if self.gold < price:
            self.shop_feedback = "You don't have enough gold."
        else:
            self.gold -= price
            if name == "Potion":
                self.potions += 1
            else:
                self.supplies[name] = self.supplies.get(name, 0) + 1
            self.shop_feedback = f"Bought 1 {name}."
        self._draw_merren_shop()

    def _grassland_intro(self):
        self.grass_intro_seen = self.grass_intro_active = True
        self.grass_camera = self._camera()
        if any(p['name'] == 'Temur' for p in self.party):
            cx, cy = self.grass_camera
            self.canvas.coords(self.grass_temur_item, (33.5*TILE-cx)*SCALE, (4.5*TILE-cy)*SCALE)
            self.canvas.itemconfigure(self.grass_temur_item, state="normal")
        self.potions += 1
        if any(p['name'] == 'Temur' for p in self.party):
            lines = [DialogueLine("Merren", "Wait -- you weren't alone? So I did see someone go in!"),
                     DialogueLine("Merren", "Mountain dust. Not from around Sunrest, are you?"),
                     DialogueLine("Temur", "No."),
                     DialogueLine("Merren", "Fair enough. You both look like you fought the cave itself."),
                     DialogueLine("Merren", "Here, a potion on the house. Payment for proving I wasn't imagining things."),
                     DialogueLine("Retri", "You help every stranger who comes out of a quarry?"),
                     DialogueLine("Merren", "Only the ones that still look useful."),
                     DialogueLine("Temur", "This road leads to Sunrest?"),
                     DialogueLine("Merren", "Aye. Follow the worn grass west. I'll be here if you need supplies.")]
        else:
            lines = [DialogueLine("Merren", "By the stones! You're alive?"),
                     DialogueLine("Merren", "I saw a silhouette near that cave. Didn't expect anyone to come back out."),
                     DialogueLine("Merren", "You look half-buried. Here, take this potion. First one's charity, second one's business."),
                     DialogueLine("Retri", "You stay out here alone?"),
                     DialogueLine("Merren", "Alone enough. Caves spit out customers when they don't swallow them."),
                     DialogueLine("Merren", "Follow the lower path west to Sunrest. Fewer cliffs, though there may be wolves."),
                     DialogueLine("Merren", "I'm Merren. I'll be here if you need supplies.")]
        self.dialogue.show(lines)

    def _meet_shalehorn(self):
        self.boss_intro = True
        lines = [DialogueLine("Retri", "That scraping sound... Look under its tusks. Something blue is pulsing.")]
        if any(p["name"] == "Temur" for p in self.party):
            lines.append(DialogueLine("Temur", "Shalehorn. See how it leans into the light? Brace when it lowers its head."))
        lines.append(DialogueLine("", "A hoof strikes the shale. The beast turns toward the footsteps."))
        self.dialogue.show(lines)

    def _interact_temur(self) -> bool:
        if self.outdoors:
            return False
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
        if self.outdoors:
            return
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
        self.supplies = model.supplies.copy()
        if outcome == "victory":
            self.gold += model.gold_reward
            for member in model.party:
                old_level = member.get("level", 1)
                level, xp = gain_xp(old_level, member.get("xp", 0), model.xp_reward)
                grow(member, old_level, level)
                member["level"], member["xp"] = level, xp
                remember(member)
            retri = next((p for p in self.party if p["name"] == "Retri"), self.party[0])
            self.level, self.xp = retri.get("level", 1), retri.get("xp", 0)
            for member in model.party:
                if member["hp"] > 0:
                    member["hp"] = min(stat_value(member, "max_hp"), member["hp"] + 8)
            self.hp = next((p["hp"] for p in model.party if p["name"] == "Retri"), self.party[0]["hp"])
            if isinstance(model, ShalehornBattle):
                self.boss_cleared = self.stone_reveal = True
                self.chunk_cache.clear()
            self.potions = max(model.potions, min(MAX_POTIONS, model.potions + 1))
        elif outcome == "defeat":
            self.in_chamber = False
            self.x, self.y = self.cave.spawn
            self.hp, self.potions = stat_value(self.party[0], "max_hp"), MAX_POTIONS
            for member in self.party:
                member["hp"] = stat_value(member, "max_hp")
                if "max_mp" in member:
                    member["mp"] = stat_value(member, "max_mp")
        else:
            self.hp = next((p["hp"] for p in model.party if p["name"] == "Retri"), self.hp)
            self.potions = model.potions
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
            enemy = cave_encounter(self.encounters.rng) if not self.in_chamber else None
            self.party[0]["hp"] = self.hp
            active = [p for p in self.party if p.get("active", True)][:3]
            model_type = ShalehornBattle if self.in_chamber else BattleModel
            opponents = SHALEHORN if self.in_chamber else enemy
            self.battle.start(model_type(opponents, active[0]["hp"], self.potions,
                                        level=self.level, xp=self.xp, party=active,
                                        supplies=self.supplies), now)
            self.screen = "battle"
            self._play_music(ASSETS / "audio" / "first-boss.mp3" if self.in_chamber else BATTLE_MUSIC)
        else:
            self.battle.close()
            self.screen = "game"
            self.direction, self.walk_frame = "down", 1
            self._update_world(force=True)
            self.held_direction = None
            self.next_step_at = now + STEP_INTERVAL
            self._start_cavern_music()
            if self.stone_reveal:
                self.stone_reveal = False
                self.dialogue.show([DialogueLine("Retri", "It was guarding that blue stone. I can reach it now.")])
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
        if self.grass_camera is not None:
            return self.grass_camera
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
                # Stable variation keeps cached chunks identical when revisited.
                variation = ((tx * 73856093) ^ (ty * 19349663)) & 0xffffffff
                if self.outdoors:
                    tile = self._grassland_tile(tx, ty, variation)
                    photo.tk.call(photo, "copy", tile, "-to", *dest)
                    continue
                if self.boss_cleared and (tx, ty) == (70, 8):
                    photo.tk.call(photo, "copy", self.entrance_tile, "-to", *dest)
                    continue
                if (tx, ty) in self.cave.floor:
                    roll = variation % 100
                    index = 0 if roll < 70 else 2 if roll < 85 else 1 if roll < 97 else 3
                    photo.tk.call(photo, "copy", self.floor_tiles[index], "-to", *dest)
                elif any((tx+dx, ty+dy) in self.cave.floor
                         for dx, dy in ((0,1),(0,-1),(1,0),(-1,0))):
                    roll = variation % 100
                    index = 0 if roll < 55 else 1 if roll < 92 else 2 if roll < 97 else 3
                    side = ((tx-1, ty) in self.cave.floor or (tx+1, ty) in self.cave.floor) and (tx, ty+1) not in self.cave.floor
                    wall = self.side_wall_tiles[0 if (tx+1, ty) in self.cave.floor else 1][variation % 2] if side else self.wall_tiles[index]
                    photo.tk.call(photo, "copy", wall, "-to", *dest)
                    if (tx, ty+1) in self.cave.floor and variation % 13 == 0:
                        crystal = self.crystal_tiles[(variation // 13) % 4]
                        photo.tk.call(photo, "copy", crystal, "-to", *dest, "-compositingrule", "overlay")
                else:
                    photo.tk.call(photo, "copy", self.solid_rock_tiles[variation % 3], "-to", *dest)
        self.chunk_cache[key] = photo
        return photo

    def _grassland_tile(self, tx, ty, variation):
        if (tx, ty) == (32, 2):
            return self.entrance_tile
        roll = (variation ^ (variation >> 13) ^ (variation >> 23)) & 255
        if ty < 3:
            return self.mountain_tiles[int(roll >= 176)]
        bend = max(0, ty - 6)
        offset = tx - (32 - bend // 5)
        road_variant = int(roll >= 128)
        if offset == 0:
            return self.path_tiles[road_variant]
        if abs(offset) == 1:
            sweep = min(3, bend % 5)
            shift = 3 - sweep if offset < 0 else sweep
            return self.path_edges[offset, shift, road_variant]
        # Large warm patches with a few scattered clumps give the field a readable shape.
        warm_patch = math.sin(tx * 0.43 + ty * 0.24) + math.cos(ty * 0.48 - tx * 0.21)
        if warm_patch > 0.8:
            return self.grass_tiles[3 if roll < 100 else 4 if roll < 205 else 5]
        return self.grass_tiles[0 if roll < 110 else 1 if roll < 195 else 2 if roll < 225 else 5]

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
        for tile, image, item, lift in self.quarry_objects:
            self.canvas.coords(item, ((tile[0]+0.5)*TILE-cx)*SCALE, ((tile[1]+0.5)*TILE-cy)*SCALE-lift)
            self.canvas.itemconfigure(item, state="hidden" if self.outdoors or (lift and self.boss_cleared) else "normal")
        self.canvas.itemconfigure(self.chest_item, state="hidden" if self.outdoors else "normal")
        self.canvas.itemconfigure(self.temur_item, state="normal" if not self.outdoors and self.temur_story == "waiting" else "hidden")
        self.canvas.coords(self.merren_item, ((self.merren_tile[0]+0.5)*TILE-cx)*SCALE, ((self.merren_tile[1]+0.5)*TILE-cy)*SCALE)
        self.canvas.coords(self.merren_stall, ((self.merren_tile[0]+1.5)*TILE-cx)*SCALE, ((self.merren_tile[1]+0.5)*TILE-cy)*SCALE)
        for item in (self.merren_item, self.merren_stall):
            self.canvas.itemconfigure(item, state="normal" if self.outdoors else "hidden")
        self.canvas.itemconfigure(self.location_label, text="SUNREST GRASSLANDS" if self.outdoors else "ASTRAL HOLLOW" if self.in_chamber else "SUNREST EXCAVATION · FLOOR 1")
        self._place_player(camera)

    def _change_area(self, outdoors):
        self.outdoors = outdoors
        self.cave = self.grassland_map if outdoors else self.cavern_map
        self.in_chamber = not outdoors
        self.x, self.y = ((32.5*TILE, 3.5*TILE) if outdoors else (70.5*TILE, 9.5*TILE))
        self.direction = "down"
        self._stone_step_latch = False
        self._area_step_latch = True
        self.encounters.reset()
        self.chunk_cache.clear()
        self._update_world(force=True)
        if outdoors and not self.grass_intro_seen:
            self._grassland_intro()

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
        self._flush_pending_music(now)
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
        elif self.screen == "shop":
            if direction not in ("up", "down"):
                self.shop_direction = None
            elif direction != self.shop_direction or now >= self.shop_repeat_at:
                self.shop_direction, self.shop_repeat_at = direction, now + 0.22
                step = -1 if direction == "up" else 1
                self.shop_selection = (self.shop_selection + step) % len(SUPPLIES)
                self.shop_feedback = ""
                self._draw_merren_shop()
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
        elif self.screen == "astral":
            if direction is None:
                self._astral_direction_armed = True
            self.astral_scene.navigate(direction if self._astral_direction_armed else None, now)
            self.astral_scene.update(now)
        elif self.screen == "game" and self.game_menu.active:
            # Shoulder buttons switch equipment members once per press. The
            # menu itself ignores this outside the equipment screen.
            shoulder_step = int("member_next" in tapped) - int("member_previous" in tapped)
            if shoulder_step:
                self.game_menu.change_equipment_member(shoulder_step)
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
                    next_tile = (int(nx // TILE), int(ny // TILE))
                    if self.outdoors and next_tile == (32, 2):
                        if not self._area_step_latch:
                            self._change_area(False)
                    elif not self.outdoors and self.in_chamber and self.boss_cleared and next_tile == (70, 8):
                        if not self._area_step_latch:
                            self._change_area(True)
                    elif not self.outdoors and next_tile in (self.outer_door, self.inner_door):
                        self._interact_quarry()
                    elif not self.outdoors and next_tile == self.stone_tile and self.boss_cleared:
                        if not self._stone_step_latch:
                            self._interact_quarry()
                    elif self.cave.walkable(nx, ny) and ((self.outdoors and next_tile not in (self.merren_tile, (self.merren_tile[0]+1, self.merren_tile[1]))) or (not self.outdoors and next_tile not in (self.chest_tile, self.stone_tile) and (self.temur_story == "joined" or next_tile != self.temur_tile))):
                        self.x, self.y = nx, ny
                        self._area_step_latch = False
                        self._stone_step_latch = False
                        self.walk_frame = 0 if self.walk_frame == 2 else 2
                        self._update_world()
                        if not self.outdoors and not self.in_chamber and self.encounters.step():
                            self._begin_battle(now)
                    else:
                        self.walk_frame = 1
                        if (self.direction, self.walk_frame) != (old_direction, old_frame):
                            self._update_world()
                    self.next_step_at = now + STEP_INTERVAL
            else:
                self.held_direction = None
                self._area_step_latch = False
                self._stone_step_latch = False
                if self.walk_frame != 1:
                    self.walk_frame = 1
                    self._update_world()
        if self.screen in ("menu", "settings", "notice"):
            self.title_art.advance(now)
            if now >= self.menu_anim_at:
                self.menu_anim_at = now + 0.04
                if self.screen == "menu":
                    self._draw_menu()
                elif self.screen == "settings":
                    self._draw_settings()
                else:
                    self._draw_notice(self.notice_message)
        self.tick_after = self.root.after(FRAME_MS, self._tick)

    def _close(self) -> None:
        if getattr(self, "game_menu", None) is not None:
            self.game_menu.close()
        if getattr(self, "battle", None) is not None:
            self.battle.close()
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
