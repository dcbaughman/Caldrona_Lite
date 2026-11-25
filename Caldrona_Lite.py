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

from animation_lab import AnimationLab, CrescendoLab, EnemyMoveLab, PlayerMoveLab
from cave_story import CaveStory, fresh_story, old_story, ENTRY, ENTRY_SHOULDERS, MINER, MINER_NAME
from classes import BLUE_STONE, NOKTAKORO, OUTFIT_JOBS, RIQIZAURKEIS, SENBRANKA, current_job
from den_art import black_stone, egg_sacs, white_stone
from depths import (BROOD_CHAMBER, DEN_CHESTS, DEN_DOOR, DEN_APPROACH, DEN_ENTRY, DEN_FLOOR, DEN_HEIGHT, DEN_HEART_GATE,
                    DEN_NEST, DEN_NEST_FOOTPRINT, DEN_SHRINE, DEN_STONE, DEN_STONE_TILES, EGG_SACS,
                    WEB_PANELS, boss_footprint, den_danger, den_location)
from grassland import Cordon, GrasslandInstance, ENTRANCE as GRASS_ENTRY, FENCE, GATE, KORWARD, RIDGE, ROAD, SENBRANKA_TILE
from save_menu import SaveMenu
from save_game import FIELDS as SAVE_FIELDS, SaveError, validate as validate_save
from abilities import attune, remember
from research import ANALECTS, initialize_research, rename_researched
from loot import BAZAAR, BAZAAR_MATERIALS, loot_name
from tome import TomeScene
from web_art import floor_web_tiles, gate_web
from dialogue import DialogueBox, DialogueLine
from astral_scene import AstralScene
from display_settings import (DisplayConfig, ScaledCanvas, available_sizes,
                              load_display, pixel_scale, save_display)
from game_menu import GameMenu
from party_walk import DIRECTIONS, PartyTrail, facing, field_order
from stats import RETRI, member, grow, restore_party
from consumables import RARE_SUPPLIES, SUPPLIES, apply_supply, item_gain_text
from equipment import STARTING_GEAR, item_for, stat_value
from battle import (BattleModel, BattleScene, BattleTransition, EncounterMeter,
                    DenMotherBattle, MAX_HP, MAX_POTIONS, gain_xp, SHALEHORN, ShalehornBattle,
                    cave_encounter, depths_encounter, grassland_encounter)

TILE = 16
VIEW_W, VIEW_H = 320, 180
SCALE = 3
FRAME_MS = 16
STEP_INTERVAL = 0.135
SHALEHORN_SHAKE_SECONDS = .42
DEN_INTRO_SECONDS = 1.12
CHUNK_TILES = 8
CHUNK_PIXELS = TILE * CHUNK_TILES
CHUNK_SCREEN = CHUNK_PIXELS * SCALE

ROOT = Path(__file__).resolve().parent
DISPLAY_FILE = ROOT / "display_settings.json"
SAVE_DIRECTORY = ROOT / "saves"
ASSETS = ROOT / "assets"
CAVERN_MUSIC = ASSETS / "audio" / "cavern-travel.mp3"
DEN_MUSIC = ASSETS / "audio" / "the-depths.mp3"
GRASSLAND_MUSIC = ASSETS / "audio" / "grasslands-travel.mp3"
GOLDENLANDS_MUSIC = ASSETS / "audio" / "goldenlands-theme.mp3"
COLLAPSE_SOUND = ASSETS / "audio" / "entrance-collapse.mp3"
BATTLE_MUSIC = ASSETS / "audio" / "cavern-battle.mp3"
VICTORY_MUSIC = ASSETS / "audio" / "caldrona-level-up.mp3"
GAME_OVER_MUSIC = ASSETS / "audio" / "caldrona-game-over.mp3"
# Title theme from the main game's assets/music/gold.wav, encoded at 128 kbps.
TITLE_MUSIC = ASSETS / "audio" / "gold.mp3"
TITLE_FADE_IN_MS = 1500
TITLE_FADE_OUT_MS = 700
MUSIC_VOLUME = 0.65
RETRI_PORTRAIT = ASSETS / "portraits" / "retri-v2.png"
RETRI_PORTRAIT_REGION = None
TEMUR_PORTRAIT = ASSETS / "portraits" / "temur.png"
MERREN_PORTRAIT = ASSETS / "portraits" / "merren.png"
KORWARD_PORTRAIT = ASSETS / "portraits" / "korward.png"
THEO_PORTRAIT = ASSETS / "portraits" / "theo-v4.png"
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
        rooms=((3,3,14,13),(22,2,36,15),(42,5,53,18),(5,21,23,32),(29,21,48,32),(64,9,77,21))
        old_halls=(((13,8),(25,8)),((34,9),(45,11)),((10,12),(11,25)),((20,26),(33,26)),((40,16),(39,25)))
        self.floor=set()
        for room in rooms:self._room(*room)
        for start,end in old_halls:self._hall(start,end,3)
        self.legacy_floor=set(self.floor)
        self.floor=set()
        for room in rooms:self._room(*room)
        # A single backbone: entry -> lower workings -> upper seam -> boss forecourt.
        for start,end in (((10,12),(11,25)),((20,26),(33,26)),((34,22),(29,14)),((34,9),(45,11))):
            self._hall(start,end,3)
        self._hall((47, 28), (55, 28), 3)
        self.floor.discard((56, 27))
        self.floor.difference_update(ENTRY_SHOULDERS)
        self.public_floor = self.floor.copy()
        self.floor.update(DEN_FLOOR)
        self.blocked=set()
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
        return (int(px // TILE), int(py // TILE)) in self.floor and (int(px // TILE), int(py // TILE)) not in self.blocked


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
        self.dialogue.on_speaker = self._face_dialogue_speaker
        self.dialogue.register_portrait("Retri", RETRI_PORTRAIT, RETRI_PORTRAIT_REGION)
        self.dialogue.register_portrait("Temur", TEMUR_PORTRAIT)
        self.dialogue.register_portrait("Merren", MERREN_PORTRAIT)
        self.dialogue.register_portrait("Korward", KORWARD_PORTRAIT)
        self.dialogue.register_portrait(MINER_NAME, THEO_PORTRAIT)
        self.game_menu = GameMenu(
            self.canvas, self._font,
            lambda: self.dialogue.portrait(RETRI_PORTRAIT, RETRI_PORTRAIT_REGION),
        )
        self.game_menu.roster = lambda: self.party
        self.game_menu.field_leader = lambda: self._field_party()[0]["name"]
        self.game_menu.set_field_leader = self._set_field_leader
        self.game_menu.formation_changed = lambda: self._place_player(self.world_camera)
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
        self.game_menu.party_sprite = lambda name, job: self.battle.class_sprites.get(
            (name, job), {"Retri": self.battle.hero, "Temur": self.battle.temur}.get(name))

        self.screen = "menu"
        self.selection = 0
        self.notice = ""
        self.notice_message = ""
        self.menu_items = ("PLAY", "LOAD GAME", "SETTINGS")
        self.lab_compare = False
        self.animation_lab = None
        self.enemy_move_lab = None
        self.crescendo_lab = None
        self.player_move_lab = None
        self.title_art = TitleBackdrop(self.root, ASSETS / "title")
        self.menu_anim_at = 0.0
        self._pending_music: tuple[Path, int, int, float] | None = None
        self._music_track: Path | None = None
        self._music_start = 0.0
        self._music_lengths: dict[Path, float] = {}
        self._field_music_bookmark: tuple[Path, float] | None = None
        self._music_gain = 0.0
        self._music_ramp: tuple[float, float, float, float] | None = None
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
                ("outfit", self.pygame.CONTROLLER_BUTTON_Y),
                ("menu", self.pygame.CONTROLLER_BUTTON_START),
                ("member_previous", self.pygame.CONTROLLER_BUTTON_LEFTSHOULDER),
                ("member_next", self.pygame.CONTROLLER_BUTTON_RIGHTSHOULDER),
            ) if self.pad.get_button(button)}
        if self.joystick is not None and self.joystick.get_init():
            count = self.joystick.get_numbuttons()
            # Common DS4 DirectInput order: Cross/Circle/Triangle 1/2/3, L1/R1 4/5.
            return {name for index, name in ((1, "confirm"), (2, "back"),
                                              (3, "outfit"),
                                              (4, "member_previous"), (5, "member_next"), (9, "menu"))
                    if count > index and self.joystick.get_button(index)}
        return set()

    def _key_down(self, event: tk.Event) -> None:
        key = str(event.keysym).lower()
        if key == "m" and self.screen in ("game", "route_map"):
            if key not in self.keys:
                if self.screen == "route_map":
                    self.cordon.close_map()
                elif self.route_map and not self.dialogue.active and not self.game_menu.active:
                    self.cordon.show_map()
                self.keys.add(key)
            return
        if self.screen == "sprite_lab":
            if key in self.keys:
                return
            self.keys.add(key)
            if key == "escape":
                self._draw_menu()
            elif key in ("q", "e"):
                self._change_lab_tab(-1 if key == "q" else 1)
            elif key == "return":
                self._activate()
            elif key in ("left", "a", "right", "d", "up", "down"):
                self._navigate_lab({"a": "left", "d": "right"}.get(key, key))
            elif key == "c":
                if self.lab_tab == 1 and self.animation_lab.has_preview:
                    lab = self.animation_lab
                    lab.original = not lab.original
                    self._draw_animation_lab(frame=lab.rendered, paused=lab.paused)
                elif self.lab_tab == 0:
                    self.lab_compare = not self.lab_compare
                    self._draw_sprite_lab()
                elif self.lab_tab == 3:
                    self._change_player_move_outfit()
            elif key == "r":
                self._activate()
                if self.lab_tab == 0:
                    self._load_lab_sprites()
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
                # A menu opened by Enter may clear movement keys during activation.
                self.keys.add(key)
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
        self.lab_tab = self.lab_index = 0
        self.lab_pad_direction = None
        self._load_lab_sprites()
        self._draw_sprite_lab()

    def _load_lab_sprites(self) -> None:
        # The title screen is available before the cavern creates BattleScene.
        # Load only the preview images here, without starting or changing a game.
        root = ASSETS / "battle"
        self.lab_sprites = []
        for name in ("Retri", "Temur"):
            variants = [("Unbound", root / f"{name.lower()}-v2.png")]
            for job in OUTFIT_JOBS:
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

    def _draw_lab_tabs(self) -> None:
        tabs = ("CHARACTER SKINS", "TEST ANIMATION", "CRESCENDOS", "PLAYER MOVES", "ENEMY MOVES")
        for i, label in enumerate(tabs):
            x = 128 + 176 * i
            active = i == self.lab_tab
            self.canvas.create_text(x, 67, text=label, fill=GOLD if active else MUTED,
                                    font=self._font(22, active))
            if active:
                self.canvas.create_line(x-78, 85, x+78, 85, fill=GOLD, width=2)

    def _change_lab_tab(self, step) -> None:
        self.lab_tab = (self.lab_tab + step) % 5
        self._draw_lab_page()

    def _draw_lab_page(self) -> None:
        (self._draw_sprite_lab, self._draw_animation_lab,
         self._draw_crescendo_lab, self._draw_player_move_lab, self._draw_enemy_move_lab)[self.lab_tab]()

    def _active_animation_lab(self):
        return (None, self.animation_lab, self.crescendo_lab, self.player_move_lab, self.enemy_move_lab)[self.lab_tab]

    def _navigate_lab(self, direction) -> None:
        lab = self._active_animation_lab()
        if direction in ("left", "right"):
            step = -1 if direction == "left" else 1
            if lab is not None:
                lab.index = (lab.index + step) % len(lab.MOVES)
            else:
                self.lab_index = (self.lab_index + step) % len(self.lab_sprites)
            self._draw_lab_page()
        elif lab is not None:
            lab.step(-1 if direction == "up" else 1)

    def _draw_animation_lab(self, frame=0, paused=False) -> None:
        if self.animation_lab is None:
            self.animation_lab = AnimationLab(self.canvas, ASSETS / "battle")
        self._draw_frame(show_title=False)
        self._draw_lab_tabs()
        lab = self.animation_lab
        lab.mount(time.monotonic(), self._font, CREAM, MUTED, frame=frame, paused=paused)
        compare = "   C: COMPARE" if lab.has_preview else ""
        self._draw_animation_controls(compare)

    def _draw_crescendo_lab(self) -> None:
        if self.crescendo_lab is None:
            self.crescendo_lab = CrescendoLab(self.canvas, self._font, ASSETS)
        self._draw_frame(show_title=False)
        self._draw_lab_tabs()
        self.crescendo_lab.mount(time.monotonic(), self._font, CREAM, MUTED)
        self._draw_animation_controls()

    def _draw_player_move_lab(self):
        if self.player_move_lab is None:
            self.player_move_lab = PlayerMoveLab(self.canvas, ASSETS)
        self._draw_frame(show_title=False)
        self._draw_lab_tabs()
        self.player_move_lab.mount(time.monotonic(), self._font, CREAM, MUTED)
        self._draw_animation_controls("   C / TRIANGLE: OUTFIT")

    def _change_player_move_outfit(self):
        lab = self.player_move_lab
        lab.outfit = (lab.outfit + 1) % len(lab.OUTFITS)
        self._draw_player_move_lab()

    def _draw_enemy_move_lab(self):
        if self.enemy_move_lab is None:
            self.enemy_move_lab = EnemyMoveLab(self.canvas, ASSETS)
        self._draw_frame(show_title=False)
        self._draw_lab_tabs()
        self.enemy_move_lab.mount(time.monotonic(), self._font, CREAM, MUTED)
        self._draw_animation_controls()

    def _draw_animation_controls(self, compare="") -> None:
        self.canvas.create_text(480, 486, text=f"LEFT / RIGHT: MOVE   UP / DOWN: STEP FRAME   ENTER / CROSS: REPLAY{compare}",
                                fill=MUTED, font=self._font(17))
        self.canvas.create_text(480, 505, text="L1 / R1 OR Q / E: TABS   ESC / CIRCLE: TITLE",
                                fill=CREAM, font=self._font(16))

    def _draw_sprite_lab(self) -> None:
        self.screen = "sprite_lab"
        self._draw_frame(show_title=False)
        name, sprite = self.lab_sprites[self.lab_index]
        self._draw_lab_tabs()
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
        self.canvas.create_text(480, 426, text=f"{self.lab_index + 1} / {len(self.lab_sprites)}", fill=GOLD, font=self._font(20))
        self.canvas.create_text(480, 457, text="LEFT / RIGHT: SPRITE   C: COMPARE   R: RELOAD", fill=MUTED, font=self._font(19))
        self.canvas.create_text(480, 485, text="L1 / R1 OR Q / E: TABS   ESC / CIRCLE: TITLE", fill=CREAM, font=self._font(17))

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
        if self.screen == "cordon_choice":
            self.cordon.choose()
            return
        if self.screen == "route_map":
            self.cordon.close_map()
            return
        if self.screen == "sprite_lab":
            lab = self._active_animation_lab()
            if lab is not None:
                lab.replay(time.monotonic())
            return
        if self.screen == "temur_choice":
            self.mine_story.confirm_choice()
            return
        if self.screen == "save_slots":
            self.save_scene.activate()
            return
        if self.screen == "tome":
            self.tome.confirm()
            return
        if self.screen == "shop":
            self._buy_supply()
            return
        if self.screen in ("faint", "cave_walk", "entrance_collapse"):
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
                if self.screen != "game":
                    return
                if not self.dialogue.active and self.merren_shop_pending:
                    self.merren_shop_pending = False
                    self._open_merren_shop()
                    return
                if not self.dialogue.active and self.grass_intro_active:
                    self.grass_intro_active = False
                    self.grass_camera = None
                    self.canvas.itemconfigure(self.grass_temur_item, state="hidden")
                    self._update_world()
                if not self.dialogue.active and self.boss_intro:
                    self.boss_intro = False
                    self._begin_battle(time.monotonic())
            elif self.game_menu.active:
                action = self.game_menu.activate()
                if action == "title":
                    self._leave_cavern()
                elif action == "sync":
                    self._open_astral(reveal=False)
                elif action == "tome":
                    self._open_tome()
            elif not self.game_menu.active:
                self.canvas.itemconfigure(self.interaction_hint, state="hidden")
                if not (self.mine_story.interact() or self._interact_save_sphere() or self._interact_merren()
                        or self._interact_korward()
                        or self._interact_white_stone() or self._interact_quarry()
                        or self._interact_den() or self._interact_temur()):
                    self._interact_chest()
            return
        if self.screen == "menu":
            if self.selection == 0:
                self._start_cavern(opening=True)
            elif self.selection == 1:
                self._open_save_slots("load")
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
        if self.screen == "route_map":
            self.cordon.close_map()
            return
        if self.screen == "cordon_choice":
            self.cordon.select(1)
            self.cordon.choose()
            return
        if self.screen == "save_slots":
            self.save_scene.back()
            return
        if self.screen == "tome":
            if self.tome.back():
                self.screen = "game"
                self.game_menu.held_direction = None
            return
        if self.screen == "shop":
            self.canvas.delete("merren_shop")
            self.screen = "game"
            self.held_direction = None
            self.next_step_at = time.monotonic() + STEP_INTERVAL
            return
        if self.screen in ("faint", "game_over", "cave_walk", "entrance_collapse", "temur_choice"):
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
                elif self.grass_intro_active or self.boss_intro or getattr(self,"opening_intro_active",False) or self.temur_story == "offering":
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
        self._start_title_music()
        self.keys.clear()
        self.pad_keys.clear()
        self._draw_menu()

    def _area_music(self) -> Path:
        if not getattr(self, "outdoors", False):
            return DEN_MUSIC if hasattr(self, "cave") and self._in_den() else CAVERN_MUSIC
        tile = (int(self.x // TILE), int(self.y // TILE))
        if tile == GATE or self.grassland_map.sheltered(tile):
            return GRASSLAND_MUSIC
        return GOLDENLANDS_MUSIC

    def _start_area_music(self) -> None:
        self._play_music(self._area_music())

    def _bookmark_area_music(self) -> None:
        self._field_music_bookmark = None
        path = self._area_music()
        if path != self._music_track or not self._music_busy():
            return
        played_ms = self.pygame.mixer.music.get_pos()
        if played_ms < 0:
            return
        if path not in self._music_lengths:
            try:
                self._music_lengths[path] = self.pygame.mixer.Sound(str(path)).get_length()
            except (self.pygame.error, OSError):
                return
        length = self._music_lengths[path]
        if length > 0:
            position = (self._music_start + played_ms / 1000) % length
            self._field_music_bookmark = (path, position)

    def _resume_area_music(self) -> None:
        bookmark, self._field_music_bookmark = self._field_music_bookmark, None
        path = self._area_music()
        if bookmark and bookmark[0] == path and bookmark[1] > 0:
            self._play_music(path, start=bookmark[1])
        else:
            self._play_music(path)

    def _start_title_music(self) -> None:
        self._field_music_bookmark = None
        self._play_music(TITLE_MUSIC, fade_ms=TITLE_FADE_IN_MS)

    def _music_busy(self) -> bool:
        return (self.pygame is not None and self.pygame.mixer.get_init()
                and self.pygame.mixer.music.get_busy())

    def _begin_gameplay_music(self) -> None:
        if self._music_track == TITLE_MUSIC:
            self._play_music(self._area_music(), out_ms=TITLE_FADE_OUT_MS)
        else:
            self._start_area_music()

    def _set_music_gain(self, gain: float) -> None:
        self._music_gain = gain
        if self.pygame is not None and self.pygame.mixer.get_init():
            self.pygame.mixer.music.set_volume(gain)

    def _flush_pending_music(self, now: float) -> None:
        if self._music_ramp is not None:
            start, seconds, source, target = self._music_ramp
            progress = min(1.0, max(0.0, (now - start) / seconds))
            ease = progress * progress * (3 - 2 * progress)
            self._set_music_gain(source + (target - source) * ease)
            if progress == 1.0:
                self._music_ramp = None
        if self._pending_music is not None and self._music_ramp is None:
            path, loops, fade_ms, position = self._pending_music
            self._pending_music = None
            self._load_music(path, loops, fade_ms, now, position)

    def _play_music(self, path: Path, loops: int = -1, fade_ms: int = 700, *,
                    out_ms: int = 400, start: float = 0.0, restart: bool = False) -> None:
        if self.pygame is None or not path.is_file():
            return
        now = time.monotonic()
        busy = self._music_busy()
        if busy and path == self._music_track and not (restart or start):
            if (self._pending_music is not None or
                    self._music_ramp is None and self._music_gain < MUSIC_VOLUME):
                self._pending_music = None
                self._music_ramp = (now, .25, self._music_gain, MUSIC_VOLUME)
            return
        if busy and self._music_gain > 0 and out_ms:
            if self._pending_music is None:
                seconds = (min(out_ms, 180) if loops == 0 else out_ms) / 1000
                self._music_ramp = (now, seconds, self._music_gain, 0.0)
            self._pending_music = (path, loops, fade_ms, start)
            return
        self._pending_music = None
        self._load_music(path, loops, fade_ms, now, start)

    def _load_music(self, path: Path, loops: int, fade_ms: int, now: float, start: float) -> None:
        self._music_ramp = None
        try:
            if not self.pygame.mixer.get_init():
                self.pygame.mixer.init()
            self.pygame.mixer.music.load(str(path))
            self._set_music_gain(0.0 if fade_ms else MUSIC_VOLUME)
            if start:
                try:
                    self.pygame.mixer.music.play(loops, start=start)
                except (self.pygame.error, NotImplementedError):
                    start = 0.0
                    self.pygame.mixer.music.play(loops)
            else:
                self.pygame.mixer.music.play(loops)
            self._music_track = path
            self._music_start = start
            if fade_ms:
                self._music_ramp = (now, fade_ms / 1000, 0.0, MUSIC_VOLUME)
        except (self.pygame.error, OSError):
            self._music_track = None
            self.notice = f"Music could not start: {path.name}"

    def _play_sfx(self,path,volume=.75):
        if self.pygame is None:return
        try:
            if not self.pygame.mixer.get_init():self.pygame.mixer.init()
            sound=self.pygame.mixer.Sound(str(path));sound.set_volume(volume)
            self._last_sfx=sound
            sound.play()
        except (self.pygame.error,OSError):
            pass

    def _stop_cavern_music(self) -> None:
        if self.pygame is not None and self.pygame.mixer.get_init():
            self.pygame.mixer.music.fadeout(350)

    def _click(self, event: tk.Event) -> None:
        x, y = self.canvas.logical_x(event.x), self.canvas.logical_y(event.y)
        if self.screen == "route_map":
            self.cordon.close_map()
            return
        if self.screen == "cordon_choice":
            if 288 <= x <= 672 and 410 <= y < 495:
                self.cordon.select(min(1, int((y-410)//42)))
                self.cordon.choose()
            return
        if self.screen == "temur_choice":
            self.mine_story.click_choice(x, y)
            return
        if self.screen == "save_slots":
            self.save_scene.click(x, y)
            return
        if self.screen == "tome":
            self.tome.click(int(x), int(y))
            return
        if self.screen == "shop":
            if 155 <= x < 805 and 149 <= y <= 176:
                self._change_shop_tab(int((x - 155) // 217) - self.shop_tab)
                return
            stock = self._shop_stock()
            spacing = self._shop_row_spacing(stock)
            for index in range(len(stock)):
                if 159 <= x <= 801 and abs(y - (214 + index * spacing)) < spacing / 2:
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
            elif action == "tome":
                self._open_tome()
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

    def _start_cavern(self, *, opening: bool = False) -> None:
        self.screen = "game"
        self.root.title("Caldrona Lite · Cavern")
        self.canvas.configure(background=INK)
        self.canvas.delete("all")
        self.cave = CavernInstance()
        self.cavern_map = self.cave
        self.grassland_map = GrasslandInstance()
        self.outdoors = False
        self.cave_story = fresh_story()
        self.opening_intro_active = opening
        self.collapse_sound_path = COLLAPSE_SOUND
        self._area_step_latch = False
        self.grass_intro_seen = self.grass_intro_active = False
        self.route_map = self.cordon_open = False
        self.grass_camera = None
        self.merren_shop_pending = False
        self.merren_hint_seen = False
        self.merren_tile = (35, 5)
        self.x, self.y = self.cave.spawn
        if opening:
            self.x, self.y = (ENTRY[0] + .5) * TILE, (ENTRY[1] + 1.5) * TILE
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
        self.merren_image = self._load_world_actor(ASSETS / "grassland" / "merren.png")
        entrance = tk.PhotoImage(master=self.root, file=str(grass_art / "cliff0.png"))
        entrance.put("#20252b", to=(3, 5, 13, 16))
        entrance.put("#20252b", to=(5, 3, 11, 5))
        self.entrance_tile = entrance.zoom(SCALE)
        self.player_frames = self._load_player()
        self.world_frames = {"Retri": self.player_frames, "Temur": self._load_player("Temur")}
        self.world_outfits = {}
        self.party_trail = PartyTrail(TILE)
        self.field_leader = "Retri"
        self.encounters = EncounterMeter()
        self.hp, self.potions, self.gold = MAX_HP, MAX_POTIONS, 0
        self.supplies = {"Remedy": 2}
        self.level, self.xp = 1, 0
        self.party = [member("Retri", RETRI)]
        initialize_research(self.party[0])
        self.analects = {}
        self.materials = {}
        self.materials_sold = {}
        self.bazaar_bought = set()
        self.gear_inventory = dict(STARTING_GEAR)
        self.temur_story = "opening" if opening else "waiting"
        self.temur_tile = (10, 7)
        self.temur_image = self._load_world_actor(ASSETS / "temur-world-v4.png")
        self.in_chamber = self.boss_intro = self.boss_cleared = self.astral_sync = False
        self.den_boss_pending = False
        self.den_intro_camera = self.shalehorn_shake_started = None
        self.shalehorn_shake = (0, 0)
        self.stone_reveal = False
        self.outer_door, self.inner_door, self.stone_tile = (49, 4), (70, 21), (70, 14)
        self.shalehorn_footprint = boss_footprint(self.stone_tile)
        self.quarry_objects = []
        for tile, filename in (
            (self.outer_door, "quarry-door.png"),
            (self.inner_door, "quarry-door.png"),
            (self.stone_tile, "astral-stone-outlined.png"),
        ):
            image = tk.PhotoImage(master=self.root, file=str(ASSETS / filename)).zoom(SCALE)
            item = self.canvas.create_image(0, 0, image=image)
            self.quarry_objects.append((tile, image, item))
        boss_art = ASSETS / "overworld-bosses"
        self.shalehorn_world_image = tk.PhotoImage(master=self.root, file=str(boss_art / "shalehorn.png")).zoom(SCALE)
        self.shalehorn_world_item = self.canvas.create_image(
            0, 0, image=self.shalehorn_world_image, anchor="s", state="hidden"
        )
        self.den_door_item = self.canvas.create_image(0, 0, image=self.quarry_objects[0][1])
        self.den_gate_web = gate_web(self.root, SCALE)
        self.den_floor_webs = floor_web_tiles(self.root, WEB_PANELS, SCALE, TILE)
        self.den_egg_art = egg_sacs(self.root, SCALE)
        self.den_egg_items = {
            tile: self.canvas.create_image(0, 0, image=self.den_egg_art[pattern], anchor="s", state="hidden")
            for tile, pattern in EGG_SACS.items()
        }
        self.den_stone_art = black_stone(self.root, SCALE)
        self.den_stone_item = self.canvas.create_image(0, 0, image=self.den_stone_art, anchor="s", state="hidden")
        self.white_stone_art = white_stone(self.root, SCALE)
        self.white_stone_item = self.canvas.create_image(0, 0, image=self.white_stone_art, anchor="s", state="hidden")
        den_atlas = tk.PhotoImage(master=self.root, file=str(boss_art / "den-mother.png"))
        self.den_gaze_frames = []
        for frame in range(3):
            size = 2 * TILE
            image = tk.PhotoImage(master=self.root, width=size, height=size)
            image.tk.call(image, "copy", den_atlas, "-from", frame * size, 0, (frame + 1) * size, size)
            self.den_gaze_frames.append(image.zoom(SCALE))
        self.den_spider_item = self.canvas.create_image(
            0, 0, image=self.den_gaze_frames[0], anchor="s", state="hidden"
        )
        self.save_sphere_tile = (47, 6)
        self.save_sphere_frames = [tk.PhotoImage(master=self.root, file=str(ASSETS / "save-shrine-v2" / f"{i}.png")).zoom(SCALE) for i in range(4)]
        self.save_sphere_item = self.canvas.create_image(0, 0, image=self.save_sphere_frames[0], tags="save_sphere")
        self.den_shrine_item = self.canvas.create_image(0, 0, image=self.save_sphere_frames[0],
                                                        state="hidden", tags="save_sphere")
        self.quarry_objects.append((self.save_sphere_tile, self.save_sphere_frames[0], self.save_sphere_item))
        self.interaction_hint = self.canvas.create_text(
            0, 0, fill="#a2c4cb", font=self._font(14), state="hidden", tags="world_interaction"
        )
        self.chest_tile = (12, 5)
        self.chest_open = False
        self.chest_images = [tk.PhotoImage(master=self.root, file=str(ASSETS / "entrance-detail" / name)).zoom(SCALE)
                             for name in ("lockbox-closed.png", "lockbox-open.png")]
        self.den_chest_items = {tile: self.canvas.create_image(0, 0, state="hidden") for tile in DEN_CHESTS}
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
        self.player_item = self.canvas.create_image(0, 0, anchor="center", tags=("player", "world_party"))
        self.follower_items = []
        self.field_followers = {}
        self.temur_item = self.canvas.create_image(0, 0, image=self.temur_image, tags=("temur",))
        self.chest_item = self.canvas.create_image(0, 0, image=self.chest_images[0], tags=("chest",))
        self.merren_item = self.canvas.create_image(0, 0, image=self.merren_image, state="hidden")
        self.merren_stall_image = tk.PhotoImage(master=self.root, file=str(ASSETS / "chest-closed.png")).zoom(SCALE)
        self.merren_stall = self.canvas.create_image(0, 0, image=self.merren_stall_image, state="hidden")
        self.grass_temur_item = self.canvas.create_image(0, 0, image=self.temur_image, state="hidden")
        self.drawn_player_frame = None
        self.held_direction: str | None = None
        self.next_step_at = 0.0
        self.location_label = self.canvas.create_text(18, VIEW_H*SCALE-18, anchor="sw", fill="#e1e2d6",
                                font=self._font(16), text="Sunrest Excavation",
                                tags=("hud",))
        self.mine_story = CaveStory(self, ASSETS, SCALE)
        # A visible speaker turns when its first dialogue page appears.
        self.dialogue_actors = {
            MINER_NAME.casefold(): (self.mine_story.items["miner"], MINER,
                                    self._npc_faces("miner", self.mine_story.images["miner-down"])),
            "merren": (self.merren_item, self.merren_tile, self._npc_faces("merren", self.merren_image)),
        }
        temur_faces = self._npc_faces("temur", self.temur_image)
        self.dialogue_actors["temur"] = (self.temur_item, self.temur_tile, temur_faces)
        self.korward_faces = {direction: poses[1] for direction, poses in self._load_player("Korward").items()}
        self.cordon_art = {name: grass_image(f"cordon-{name}") for name in ("rail", "side", "gate")}
        self.cordon = Cordon(self, self.cordon_art, SCALE, self.korward_faces)
        self.dialogue_actors["korward"] = (self.cordon.guard, KORWARD, self.korward_faces)
        self.grass_temur_actor = (self.grass_temur_item, (33, 4), temur_faces)
        self._update_world(force=True)
        self._begin_gameplay_music()
        if opening:
            self.mine_story.open_at_entrance()

    @property
    def save_directory(self):
        return SAVE_DIRECTORY

    def _open_save_slots(self, mode):
        self.save_scene = SaveMenu(self, mode)

    def _facing_tile(self) -> tuple[int, int]:
        dx, dy = DIRECTIONS[self.direction]
        x, y = self._world_tile()
        return x + dx, y + dy

    def _world_tile(self) -> tuple[int, int]:
        return int(self.x // TILE), int(self.y // TILE)

    def _interact_save_sphere(self):
        shrine = DEN_SHRINE if self._in_den() else self.save_sphere_tile
        if self.outdoors or self.in_chamber or self._facing_tile() != shrine:
            return False
        self._open_save_slots("save")
        return True

    def _load_journey(self, state):
        validate_save(state)
        area = GrasslandInstance() if state["outdoors"] else CavernInstance()
        story=state.get("cave_story",old_story())
        saved_tile = (int(state["x"] // TILE), int(state["y"] // TILE))
        if not state["outdoors"] and saved_tile in DEN_FLOOR and (state["in_chamber"] or not story.get("den_unsealed")):
            raise SaveError("This save has an invalid den location.")
        if not state["outdoors"] and story["entrance_collapsed"]:area.blocked.add(ENTRY)
        if state["outdoors"] and (saved_tile in FENCE or saved_tile in RIDGE or saved_tile in (KORWARD, SENBRANKA_TILE)
                                  or saved_tile == GATE and not state.get("cordon_open", False)):
            target = min(area.floor - {GATE}, key=lambda p: (abs(p[0]-saved_tile[0])+abs(p[1]-saved_tile[1]), p))
            state = dict(state, x=(target[0]+.5)*TILE, y=(target[1]+.5)*TILE)
        if not area.walkable(state["x"],state["y"]):
            tile=(int(state["x"]//TILE),int(state["y"]//TILE))
            if state["outdoors"] or tile not in area.legacy_floor:
                raise SaveError("This save has an invalid location.")
            target=min(area.floor-area.blocked,key=lambda p:(abs(p[0]-tile[0])+abs(p[1]-tile[1]),p[1],p[0]))
            state=dict(state,x=(target[0]+.5)*TILE,y=(target[1]+.5)*TILE)
        self._start_cavern()
        self.dialogue.clear()
        self.opening_intro_active=False
        self.cave_story=dict(fresh_story(), **story)
        self.cave_story["black_stone_attuned"] = story.get(
            "black_stone_attuned", story.get("black_stone_claimed", False)
        )
        self.cave_story.pop("black_stone_claimed", None)
        self.cave_story["depths_chests"] = list(self.cave_story["depths_chests"])
        self.cave_story["inspected"] = list(story["inspected"])
        for key in SAVE_FIELDS:
            setattr(self, key, state[key])
        self.field_leader = state.get("field_leader", "Retri")
        self.route_map = state.get("route_map", False)
        self.cordon_open = state.get("cordon_open", False)
        for person in self.party:
            if current_job(person) == RIQIZAURKEIS:
                person["job"] = RIQIZAURKEIS
            rename_researched(person)
            if person["hp"] <= 0:
                person.pop("ailments", None)
                person.pop("crescendo_charge", None)
        self.bazaar_bought = set(state["bazaar_bought"])
        self.encounters.steps_left = state["encounter_steps"]
        self.cave = self.grassland_map if self.outdoors else self.cavern_map
        self.hp = self.party[0]["hp"]
        self.level, self.xp = self.party[0]["level"], self.party[0]["xp"]
        self.canvas.itemconfigure(self.chest_item, image=self.chest_images[int(self.chest_open)])
        self.chunk_cache.clear()
        self.keys.clear(); self.pad_keys.clear()
        self.held_direction = None
        self.next_step_at = time.monotonic() + .25
        self._update_world(force=True)
        if self.outdoors or self._in_den():
            self._start_area_music()

    def _supply_inventory(self):
        return {name: self.potions if name == "Potion" else self.supplies.get(name, 0)
                for name in (*SUPPLIES, *RARE_SUPPLIES)}

    def _use_menu_item(self, name, member):
        if not self._supply_inventory().get(name):
            return f"No {name} left."
        used, message = apply_supply(name, member, member.get("ailments"))
        if used and not member.get("ailments"):member.pop("ailments",None)
        if used:
            if name == "Potion":
                self.potions -= 1
            else:
                self.supplies[name] -= 1
            if member["name"] == "Retri":
                self.hp = member["hp"]
            self._place_player(self.world_camera)
        return message

    def _gear_changed(self, member):
        if member["name"] == "Retri":
            self.hp = member["hp"]

    def _recruit(self, member):
        if not any(p["name"] == member["name"] for p in self.party):
            member.setdefault("level", 1)
            member.setdefault("xp", 0)
            initialize_research(member)
            member["active"] = sum(p.get("active", True) for p in self.party) < 3
            self.party.append(member)

    def _field_party(self):
        if self.grass_intro_active:
            return self.party[:1]
        return field_order(self.party, self.field_leader)

    def _set_field_leader(self, name):
        self.field_leader = name
        self._place_player(self.world_camera)

    def _open_tome(self):
        self.tome = TomeScene(self.canvas, self._font, self.game_menu.party_portrait)
        self.screen = "tome"
        self.tome.start(self.party, self.analects)

    def _open_astral(self, reveal=False, *, stone=BLUE_STONE):
        if not hasattr(self, "astral_scene"):
            self.astral_scene = AstralScene(self.canvas, self._font, ASSETS)
        if self.game_menu.active:
            self.game_menu.close()
        self.keys.clear()
        self.held_direction = None
        self._astral_direction_armed = False
        self.screen = "astral"
        self.astral_scene.start(self.party, time.monotonic(), reveal=reveal, stone=stone)

    def _interact_white_stone(self):
        if not self.outdoors or self._facing_tile() != SENBRANKA_TILE:
            return False
        first_contact = not self.cave_story["white_stone_seen"]
        self.cave_story["white_stone_seen"] = True
        self._open_astral(reveal=first_contact, stone=SENBRANKA)
        return True

    def _finish_astral(self, result):
        if result == "close":
            self.screen = "game"
            self.keys.clear()
            self.held_direction = None
            self.next_step_at = time.monotonic() + 0.25

    def _interact_quarry(self):
        if self.outdoors or self._in_den():
            return False
        tile = self._facing_tile()
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
        elif tile == self.stone_tile or (not self.boss_cleared and tile in self.shalehorn_footprint):
            if not self.boss_cleared:
                self._meet_shalehorn()
            else:
                first_contact = not self.astral_sync
                self.astral_sync = True
                # Attunement travels with each member in the saved party.
                for person in self.party:
                    if person.get("attuned_stone") not in (NOKTAKORO, SENBRANKA):
                        attune(person, BLUE_STONE)
                self._open_astral(reveal=first_contact)
        else:
            return False
        return True

    def _in_den(self):
        return not self.outdoors and self._world_tile() in DEN_FLOOR

    def _start_den_intro(self, tile, now):
        if self.outdoors or tile not in BROOD_CHAMBER or self.cave_story["den_cleared"]:
            return False
        self.screen = "den_intro"
        self.den_intro_started = now
        self.den_intro_origin = self.den_intro_camera = self.world_camera
        x, y = DEN_NEST
        self.den_intro_goal = self._center_camera((x + 1) * TILE, y * TILE)
        self.den_intro_gaze = 0
        self.direction = facing((self.x, self.y), ((x + 1) * TILE, y * TILE), self.direction)
        self.walk_frame = 1
        self.keys.clear()
        self.held_direction = None
        self._update_world()
        return True

    def _update_den_intro(self, now):
        elapsed = now - self.den_intro_started
        progress = min(1, max(0, elapsed / .58))
        ease = progress * progress * (3 - 2 * progress)
        camera = tuple(round((start + (end - start) * ease) * SCALE) / SCALE
                       for start, end in zip(self.den_intro_origin, self.den_intro_goal))
        if camera != self.den_intro_camera:
            self.den_intro_camera = camera
            self._update_world()
        gaze = 2 if elapsed >= .76 else 1 if elapsed >= .52 else 0
        if gaze != self.den_intro_gaze:
            self.den_intro_gaze = gaze
            self.canvas.itemconfigure(self.den_spider_item, image=self.den_gaze_frames[gaze])
        if elapsed >= DEN_INTRO_SECONDS:
            self._begin_battle(now, den_boss=True)

    def _interact_den(self):
        if self.outdoors:
            return False
        current = self._world_tile()
        target = self._facing_tile()
        if target == DEN_DOOR and current in (DEN_ENTRY, DEN_APPROACH):
            if not self.cave_story["den_unsealed"]:
                if self.supplies.get("Pitch Torch", 0) > 0:
                    self.supplies["Pitch Torch"] -= 1
                    self.cave_story["den_unsealed"] = True
                    self._update_world(force=True)
                    self.dialogue.show([DialogueLine(
                        "Retri", "The torch takes. Silk burns away from the rock.")])
                    return True
                self.dialogue.show([
                    DialogueLine("Retri", "Silk binds the gate to the rock. It won't budge."),
                    DialogueLine("Retri", "Maybe fire would loosen it."),
                ])
                return True
            entering = current == DEN_APPROACH
            x, y = DEN_ENTRY if entering else DEN_APPROACH
            self.x, self.y = (x + .5) * TILE, (y + .5) * TILE
            self.encounters.reset()
            self.chunk_cache.clear()
            self._update_world(force=True)
            self._start_area_music()
        elif not self._in_den():
            return False
        elif target == DEN_HEART_GATE and not self.cave_story["den_cleared"]:
            self.dialogue.show([DialogueLine("Retri", "The silk pulls tight each time she moves.")])
        elif target in DEN_STONE_TILES and self.cave_story["den_cleared"]:
            first_contact = not self.cave_story["black_stone_attuned"]
            if first_contact:
                self.cave_story["black_stone_attuned"] = True
                for person in self.party:
                    initialize_research(person)
                    person["rp"] += 4
            self._open_astral(reveal=first_contact, stone=NOKTAKORO)
        elif target in DEN_CHESTS:
            key, rewards = DEN_CHESTS[target]
            opened = self.cave_story["depths_chests"]
            if key in opened:
                message = "The chest is empty."
            else:
                for item, count in rewards:
                    self._receive_loot(item, count)
                opened.append(key)
                self.canvas.itemconfigure(self.den_chest_items[target], image=self.chest_images[1])
                message = "  ·  ".join(item_gain_text(loot_name(item), count) for item, count in rewards)
            self.dialogue.show([DialogueLine("", message)])
        elif target in EGG_SACS:
            self.dialogue.show([DialogueLine("Retri", "The silk is warm. Something's moving inside.")])
        else:
            return False
        return True

    def _align_world_sprite(self, sprite):
        """Line up visible feet on row 14 of a native 16-pixel actor tile."""
        bottom = next(
            (y for y in range(sprite.height() - 1, -1, -1)
             if any(not sprite.transparency_get(x, y) for x in range(sprite.width()))),
            14,
        )
        offset = 14 - bottom
        if offset == 0:
            return sprite.zoom(SCALE)
        aligned = tk.PhotoImage(master=self.root, width=TILE, height=TILE)
        source_top = max(0, -offset)
        source_bottom = min(sprite.height(), TILE - offset)
        aligned.tk.call(aligned, "copy", sprite, "-from", 0, source_top,
                        sprite.width(), source_bottom, "-to", 0, source_top + offset)
        return aligned.zoom(SCALE)

    def _load_world_actor(self, path):
        return self._align_world_sprite(tk.PhotoImage(master=self.root, file=str(path)))

    def _npc_faces(self, name, front):
        faces = {"down": front}
        for direction in ("left", "right", "up"):
            faces[direction] = self._load_world_actor(
                ASSETS / "mine-polish" / f"{name}-{direction}.png"
            )
        return faces

    def _face_dialogue_speaker(self, speaker):
        if not hasattr(self, "dialogue_actors"):
            return
        key = speaker.casefold()
        follower = self.field_followers.get(key)
        if follower is not None:
            item, member, (x, y, direction) = follower
            turn = facing((x, y), (self.x, self.y), direction)
            self.canvas.itemconfigure(item, image=self._field_costume(member)[turn][1])
            return
        actor = self.grass_temur_actor if key == "temur" and self.outdoors else self.dialogue_actors.get(key)
        if actor is None:
            return
        item, tile, frames = actor
        if self.canvas.itemcget(item, "state") == "hidden":
            return
        dx = self.x / TILE - (tile[0] + .5)
        dy = self.y / TILE - (tile[1] + .5)
        if abs(dx) > abs(dy):
            direction = "right" if dx > 0 else "left"
        else:
            direction = "down" if dy >= 0 else "up"
        self.canvas.itemconfigure(item, image=frames[direction])

    def _interact_merren(self):
        if not self.outdoors:
            return False
        if self._facing_tile() != self.merren_tile:
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

    def _interact_korward(self):
        if not self.outdoors:
            return False
        target = self._facing_tile()
        if target != KORWARD and (target != GATE or self.cordon_open):
            return False
        self.keys.clear()
        self.held_direction = None
        self.cordon.talk()
        return True

    def _open_merren_shop(self):
        self.screen = "shop"
        self.shop_tab = 0
        self.shop_selection = 0
        self.shop_feedback = ""
        self.shop_direction = None
        self.shop_repeat_at = 0.0
        self._draw_merren_shop()

    def _shop_stock(self):
        if self.shop_tab == 1:
            return BAZAAR_MATERIALS
        if self.shop_tab == 2:
            return BAZAAR
        return SUPPLIES

    @staticmethod
    def _shop_row_spacing(stock):
        return 32 if len(stock) > 4 else 39

    def _change_shop_tab(self, step):
        self.shop_tab = (self.shop_tab + step) % 3
        self.shop_selection = 0
        self.shop_feedback = ""
        self._draw_merren_shop()

    def _bazaar_unlocked(self, key):
        if (key == "pickpocket_dirk" and self.materials_sold.get("Brood Silk", 0) >= 1
                and self.materials_sold.get("Spider Silk", 0) >= 4):
            return True
        return all(self.materials_sold.get(material, 0) >= count
                   for material, count in BAZAAR[key][1].items())

    def _receive_loot(self, key, count):
        if key == "Potion":
            self.potions += count
            return
        if key in ANALECTS:
            inventory = self.analects
        elif key in BAZAAR_MATERIALS:
            inventory = self.materials
        elif key in SUPPLIES or key in RARE_SUPPLIES:
            inventory = self.supplies
        elif item_for(key) is not None:
            inventory = self.gear_inventory
        else:
            raise ValueError(f"Unknown loot item: {key}")
        inventory[key] = inventory.get(key, 0) + count

    def _draw_merren_shop(self):
        c, tag = self.canvas, "merren_shop"
        c.delete(tag)
        c.create_rectangle(132, 90, 828, 467, fill="#101625", outline=GOLD, width=3, tags=tag)
        c.create_text(159, 117, text="MERREN'S WARES", anchor="w", fill=GOLD,
                      font=self._font(25, True), tags=tag)
        c.create_text(801, 117, text=f"{self.gold} GOLD", anchor="e", fill=GOLD,
                      font=self._font(22), tags=tag)
        for i, label in enumerate(("SUPPLIES", "SELL LOOT", "BAZAAR")):
            x = 155 + 217*i
            active = i == self.shop_tab
            c.create_rectangle(x, 149, x+214, 176, fill="#242181" if active else "#192137",
                               outline="#63829a", tags=tag)
            c.create_text(x+107, 162, text=label, fill=GOLD if active else CREAM,
                          font=self._font(16), tags=tag)
        for x, title in ((689, "PRICE"), (796, "OWNED")):
            c.create_text(x, 187, text=title, anchor="e", fill=MUTED, font=self._font(14), tags=tag)
        stock = self._shop_stock()
        spacing = self._shop_row_spacing(stock)
        for i, (key, offer) in enumerate(stock.items()):
            y = 214 + i * spacing
            selected = self.shop_selection == i
            if selected:
                c.create_rectangle(155, y-spacing//2+1, 805, y+spacing//2-1,
                                   fill="#242181", outline="#83b7d5", tags=tag)
                c.create_text(175, y, text="▶", fill=CREAM, font=self._font(18), tags=tag)
            c.create_text(198, y, text=loot_name(key), anchor="w", fill=GOLD if selected else CREAM,
                          font=self._font(22), tags=tag)
            if self.shop_tab == 1:
                price, owned = str(offer), self.materials.get(key, 0)
            elif self.shop_tab == 2:
                price = "SOLD" if key in self.bazaar_bought else str(offer[0]) if self._bazaar_unlocked(key) else "LOCKED"
                owned = self.gear_inventory.get(key, 0)
            else:
                price, owned = str(offer[0]), self._supply_inventory()[key]
            c.create_text(689, y, text=price, anchor="e", fill=CREAM,
                          font=self._font(20), tags=tag)
            c.create_text(796, y, text=str(owned), anchor="e", fill=CREAM,
                          font=self._font(20), tags=tag)
        key = tuple(stock)[self.shop_selection]
        if self.shop_tab == 1:
            detail = f"Sold to Merren: {self.materials_sold.get(key, 0)}. Material sales unlock Bazaar gear."
        elif self.shop_tab == 2 and not self._bazaar_unlocked(key):
            required = BAZAAR[key][1]
            progress = ", ".join(f"{self.materials_sold.get(name, 0)}/{count} {name}"
                                 for name, count in required.items())
            detail = f"Sell to Merren: {progress}."
        elif self.shop_tab == 2:
            detail = item_for(key).description
        else:
            detail = SUPPLIES[key][1]
        c.create_text(159, 367, text=detail, anchor="w", width=625, fill=CREAM,
                      font=self._font(17), tags=tag)
        c.create_text(159, 398, text=self.shop_feedback, anchor="w", fill=GOLD,
                      font=self._font(18), tags=tag)
        c.create_text(159, 435, text="LEFT / RIGHT TAB   UP / DOWN MOVE   ENTER / CROSS TRADE   ESC / CIRCLE BACK",
                      anchor="w", fill=MUTED, font=self._font(13), tags=tag)

    def _buy_supply(self):
        stock = self._shop_stock()
        key = tuple(stock)[self.shop_selection]
        if self.shop_tab == 1:
            if self.materials.get(key, 0):
                self.materials[key] -= 1
                self.materials_sold[key] = self.materials_sold.get(key, 0) + 1
                self.gold += stock[key]
                self.shop_feedback = f"Sold {key}. +{stock[key]} Gold"
            else:
                self.shop_feedback = f"No {key} to sell."
            self._draw_merren_shop()
            return
        if self.shop_tab == 2 and (key in self.bazaar_bought or not self._bazaar_unlocked(key)):
            self.shop_feedback = "Already purchased." if key in self.bazaar_bought else "Sell the listed materials first."
            self._draw_merren_shop()
            return
        price = stock[key][0]
        if self.gold < price:
            self.shop_feedback = "You don't have enough gold."
        else:
            self.gold -= price
            self._receive_loot(key, 1)
            if self.shop_tab == 2:
                self.bazaar_bought.add(key)
            self.shop_feedback = item_gain_text(loot_name(key))
        self._draw_merren_shop()

    def _grassland_intro(self):
        self.grass_intro_seen = self.grass_intro_active = True
        self.grass_camera = self._camera()
        self._place_player(self.grass_camera)
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
                     DialogueLine("", item_gain_text("Potion")),
                     DialogueLine("Retri", "You help every stranger who comes out of a quarry?"),
                     DialogueLine("Merren", "Only the ones that still look useful."),
                     DialogueLine("Temur", "Is there a road around the mountain?"),
                     DialogueLine("Merren", "Ask Korward at the south gate. I'll be here if you need supplies.")]
        else:
            lines = [DialogueLine("Merren", "By the stones! You're alive?"),
                     DialogueLine("Merren", "I saw a silhouette near that cave. Didn't expect anyone to come back out."),
                     DialogueLine("Merren", "You look half-buried. Here, take this potion. First one's charity, second one's business."),
                     DialogueLine("", item_gain_text("Potion")),
                     DialogueLine("Retri", "You stay out here alone?"),
                     DialogueLine("Merren", "Alone enough. Caves spit out customers when they don't swallow them."),
                     DialogueLine("Merren", "Korward's at the south gate. He knows the road around the mountain."),
                     DialogueLine("Merren", "I'm Merren. I'll be here if you need supplies.")]
        self.dialogue.show(lines)

    def _meet_shalehorn(self):
        self.boss_intro = True
        self.shalehorn_shake_started = time.monotonic()
        self._update_shalehorn_shake(self.shalehorn_shake_started)
        lines = [DialogueLine("Retri", "That scraping sound... Look under its tusks. Something blue is pulsing.")]
        if any(p["name"] == "Temur" for p in self.party):
            lines.append(DialogueLine("Temur", "Shalehorn. See how it leans into the light? Brace when it lowers its head."))
        lines.append(DialogueLine("", "A hoof strikes the shale. The beast turns toward the footsteps."))
        self.dialogue.show(lines)

    def _update_shalehorn_shake(self, now):
        if self.shalehorn_shake_started is None:
            return
        elapsed = max(0, now - self.shalehorn_shake_started)
        strength = max(0, 1 - elapsed / SHALEHORN_SHAKE_SECONDS)
        if not strength:
            self.shalehorn_shake_started = None
        offset = (round(3 * strength * math.cos(elapsed * 72)),
                  round(2 * strength * math.sin(elapsed * 91)))
        if offset != self.shalehorn_shake:
            self.shalehorn_shake = offset
            self._update_world()

    def _interact_temur(self) -> bool:
        if self.outdoors:
            return False
        if self.temur_story != "waiting" or self._facing_tile() != self.temur_tile:
            return False
        self.mine_story.offer_temur()
        return True

    def _interact_chest(self) -> None:
        if self.outdoors:
            return
        if self._facing_tile() != self.chest_tile:
            return
        if not self.chest_open:
            self.chest_open = True
            self.potions += 1
            self.canvas.itemconfigure(self.chest_item, image=self.chest_images[1])
            message = item_gain_text("Potion")
        else:
            message = "The chest is empty."
        self.dialogue.show([DialogueLine("", message)])

    def _begin_battle(self, now: float, *, den_boss=False) -> None:
        self.den_boss_pending = den_boss
        self.shalehorn_shake_started = None
        if self.shalehorn_shake != (0, 0):
            self.shalehorn_shake = (0, 0)
            self._update_world()
        self.screen = "battle_in"
        self.keys.clear()
        self.held_direction = None
        self._start_battle_wipe(now)

    def _start_battle_wipe(self, now: float) -> None:
        self._pending_music = self._music_ramp = None
        self._wipe_music_gain = self._music_gain
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
        if isinstance(model, DenMotherBattle):
            self.canvas.itemconfigure(self.den_spider_item, image=self.den_gaze_frames[0])
        self.supplies = model.supplies.copy()
        if outcome == "victory":
            self.gold += model.gold_reward
            for member in model.party:
                old_level = member.get("level", 1)
                level, xp = gain_xp(old_level, member.get("xp", 0), model.xp_reward)
                grow(member, old_level, level)
                member["level"], member["xp"] = level, xp
                initialize_research(member)
                member["rp"] += model.research_reward
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
            elif isinstance(model, DenMotherBattle):
                self.cave_story["den_cleared"] = True
            self.potions = model.potions + model.potion_reward
        elif outcome == "defeat":
            if self._in_den():
                self.chunk_cache.clear()
            self.in_chamber = False
            self.x, self.y = self.cave.spawn
            restore_party(self.party, clear_ailments=True)
            self.hp, self.potions = self.party[0]["hp"], MAX_POTIONS
        else:
            self.hp = next((p["hp"] for p in model.party if p["name"] == "Retri"), self.hp)
            self.potions = model.potions
            if isinstance(model, DenMotherBattle):
                self.x, self.y = ((tile + .5) * TILE for tile in DEN_APPROACH)
                self.chunk_cache.clear()
        if outcome in ("victory", "fled"):
            model.collect_kill_drops()
            for spoils in (model.drops, model.stolen):
                for key, count in spoils.items():
                    self._receive_loot(key, count)
        self.encounters.reset()
        self.screen = "battle_out"
        self.keys.clear()
        self._start_battle_wipe(time.monotonic())

    def _update_battle_transition(self, now: float) -> None:
        progress = self.battle_transition.update(now)
        self._set_music_gain(self._wipe_music_gain * (1 - progress))
        if progress < 1:
            return
        if self.screen == "battle_in":
            self._bookmark_area_music()
            self.party[0]["hp"] = self.hp
            active = [p for p in self.party if p.get("active", True)][:3]
            battle_args = dict(hp=active[0]["hp"], potions=self.potions, level=self.level,
                               xp=self.xp, party=active, supplies=self.supplies)
            in_depths = self._in_den()
            if self.outdoors:
                model = BattleModel(grassland_encounter(self.encounters.rng, len(active)), **battle_args)
            elif self.den_boss_pending:
                model = DenMotherBattle(**battle_args)
            elif in_depths:
                model = BattleModel(depths_encounter(self.encounters.rng, den_danger(self._world_tile()), len(active)),
                                    **battle_args)
            elif self.in_chamber:
                model = ShalehornBattle(SHALEHORN, **battle_args)
            else:
                model = BattleModel(cave_encounter(self.encounters.rng), **battle_args)
            self.den_boss_pending = False
            self.battle.start(model, now, outdoors=self.outdoors, in_depths=in_depths)
            self.screen = "battle"
            self._play_music(ASSETS / "audio" / "first-boss.mp3"
                             if isinstance(model, (DenMotherBattle, ShalehornBattle)) else BATTLE_MUSIC,
                             restart=True)
        else:
            self.battle.close()
            self.screen = "game"
            self.den_intro_camera = None
            self.direction, self.walk_frame = "down", 1
            self._update_world(force=True)
            self.held_direction = None
            self.next_step_at = now + STEP_INTERVAL
            self._resume_area_music()
            if self.stone_reveal:
                self.stone_reveal = False
                self.dialogue.show([DialogueLine("Retri", "It was guarding that blue stone. I can reach it now.")])
        self.battle_transition.close()

    def _load_player(self, name="Retri", job=None) -> dict[str, list[tk.PhotoImage]]:
        cell = 32 if name == "Retri" and job is None else TILE
        file = (ASSETS / f"{name.lower()}-overworld.png" if job is None else
                ASSETS / "battle" / "classes" / f"{name.lower()}-{job.lower()}-overworld.png")
        atlas = tk.PhotoImage(master=self.root, file=str(file))
        frames: dict[str, list[tk.PhotoImage]] = {}
        for row, direction in enumerate(("down", "left", "right", "up")):
            frames[direction] = []
            for col in range(3):
                small = tk.PhotoImage(master=self.root, width=16, height=16)
                small.tk.call(small, "copy", atlas, "-from", col*cell, row*cell,
                              (col+1)*cell, (row+1)*cell, "-subsample", cell//TILE, cell//TILE)
                frames[direction].append(self._align_world_sprite(small))
        return frames

    def _field_costume(self, member):
        name, job = member["name"], current_job(member)
        if name in self.world_frames and job in OUTFIT_JOBS:
            key = name, job
            if key not in self.world_outfits:
                self.world_outfits[key] = self._load_player(name, job)
            return self.world_outfits[key]
        return self.world_frames.get(name)

    def _world_height(self):
        return DEN_HEIGHT if self._in_den() else self.cave.height

    def _center_camera(self, x, y) -> tuple[float, float]:
        max_x = max(0, self.cave.width * TILE - VIEW_W)
        max_y = max(0, self._world_height() * TILE - VIEW_H)
        return min(max(x - VIEW_W / 2, 0), max_x), min(max(y - VIEW_H / 2, 0), max_y)

    def _camera(self) -> tuple[float, float]:
        if self.grass_camera is not None:
            return self.grass_camera
        if self.den_intro_camera is not None:
            return self.den_intro_camera
        cx, cy = self._center_camera(self.x, self.y)
        if not self.outdoors and not self.in_chamber:
            # Frame the whole north wall in the entry room, then blend back to follow.
            edge_distance = max(abs(self.x / TILE - (ENTRY[0] + .5)) - 3, (self.y - self.cavern_map.spawn[1]) / TILE, 0)
            weight = max(0, 1 - edge_distance / 3)
            cy -= max(0, cy - TILE) * weight
        dx, dy = self.shalehorn_shake
        return cx + dx, cy + dy

    def _build_chunk(self, key: tuple[int, int]) -> tk.PhotoImage:
        photo = tk.PhotoImage(master=self.root, width=CHUNK_SCREEN, height=CHUNK_SCREEN)
        gx, gy = key
        in_den = self._in_den()
        floor = self.cave.floor if self.outdoors else DEN_FLOOR if in_den else self.cavern_map.public_floor
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
                if self.boss_cleared and not in_den and (tx, ty) == (70, 8):
                    photo.tk.call(photo, "copy", self.entrance_tile, "-to", *dest)
                    continue
                if (tx, ty) in floor:
                    roll = variation % 100
                    index = 0 if roll < 70 else 2 if roll < 85 else 1 if roll < 97 else 3
                    photo.tk.call(photo, "copy", self.floor_tiles[index], "-to", *dest)
                    if in_den:
                        for web in self.den_floor_webs.get((tx, ty), ()):
                            photo.tk.call(photo, "copy", web, "-to", *dest, "-compositingrule", "overlay")
                elif any((tx+dx, ty+dy) in floor
                         for dx, dy in ((0,1),(0,-1),(1,0),(-1,0))):
                    roll = variation % 100
                    index = 0 if roll < 55 else 1 if roll < 92 else 2 if roll < 97 else 3
                    side = ((tx-1, ty) in floor or (tx+1, ty) in floor) and (tx, ty+1) not in floor
                    wall = self.side_wall_tiles[0 if (tx+1, ty) in floor else 1][variation % 2] if side else self.wall_tiles[index]
                    photo.tk.call(photo, "copy", wall, "-to", *dest)
                    if (tx, ty+1) in floor and variation % 13 == 0:
                        crystal = self.crystal_tiles[(variation // 13) % 4]
                        photo.tk.call(photo, "copy", crystal, "-to", *dest, "-compositingrule", "overlay")
                else:
                    photo.tk.call(photo, "copy", self.solid_rock_tiles[variation % 3], "-to", *dest)
        self.chunk_cache[key] = photo
        return photo

    def _grassland_tile(self, tx, ty, variation):
        tile = tx, ty
        if tile == GRASS_ENTRY:
            return self.entrance_tile
        roll = (variation ^ (variation >> 13) ^ (variation >> 23)) & 255
        if ty < 3 or tile in RIDGE:
            return self.mountain_tiles[int(roll >= 176)]
        road_variant = int(roll >= 128)
        if tile in ROAD:
            return self.path_tiles[road_variant]
        for side in (-1, 1):
            if (tx-side, ty) in ROAD:
                return self.path_edges[side, 0, road_variant]
        # Large warm patches with a few scattered clumps give the field a readable shape.
        warm_patch = math.sin(tx * 0.43 + ty * 0.24) + math.cos(ty * 0.48 - tx * 0.21)
        if warm_patch > 0.8:
            return self.grass_tiles[3 if roll < 100 else 4 if roll < 205 else 5]
        return self.grass_tiles[0 if roll < 110 else 1 if roll < 195 else 2 if roll < 225 else 5]

    def _update_world(self, force: bool = False) -> None:
        camera = self._camera()
        cx, cy = camera
        in_den = self._in_den()
        left, top = int(cx // CHUNK_PIXELS), int(cy // CHUNK_PIXELS)
        right = min((self.cave.width*TILE-1)//CHUNK_PIXELS,
                    int((cx+VIEW_W-1)//CHUNK_PIXELS))
        bottom = min((self._world_height()*TILE-1)//CHUNK_PIXELS,
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
        for tile, image, item in self.quarry_objects:
            self.canvas.coords(item, ((tile[0]+0.5)*TILE-cx)*SCALE, ((tile[1]+0.5)*TILE-cy)*SCALE)
            hidden = self.outdoors or in_den
            self.canvas.itemconfigure(item, state="hidden" if hidden else "normal")
        self._position_overworld_boss(self.shalehorn_world_item, self.stone_tile, camera)
        shalehorn_visible = self.in_chamber and not self.outdoors and not self.boss_cleared
        self.canvas.itemconfigure(self.shalehorn_world_item, state="normal" if shalehorn_visible else "hidden")
        self.canvas.itemconfigure(self.chest_item, state="hidden" if self.outdoors else "normal")
        self.canvas.itemconfigure(self.temur_item, state="normal" if not self.outdoors and self.temur_story in ("waiting", "offering") else "hidden")
        self.canvas.coords(self.merren_item, ((self.merren_tile[0]+0.5)*TILE-cx)*SCALE, ((self.merren_tile[1]+0.5)*TILE-cy)*SCALE)
        self.canvas.coords(self.merren_stall, ((self.merren_tile[0]+1.5)*TILE-cx)*SCALE, ((self.merren_tile[1]+0.5)*TILE-cy)*SCALE)
        for item in (self.merren_item, self.merren_stall):
            self.canvas.itemconfigure(item, state="normal" if self.outdoors else "hidden")
        wx, wy = SENBRANKA_TILE
        self.canvas.coords(self.white_stone_item, ((wx + .5) * TILE - cx) * SCALE,
                           ((wy + 1) * TILE - cy) * SCALE)
        self.canvas.itemconfigure(self.white_stone_item, state="normal" if self.outdoors else "hidden")
        location = ("Sunrest Grasslands" if self.outdoors else den_location(self._world_tile()) if in_den
                    else "Astral Hollow" if self.in_chamber else "Sunrest Excavation")
        self.canvas.itemconfigure(self.location_label, text=location)
        self._draw_den(camera)
        self.cordon.render(camera)
        self._place_player(camera)
        self.mine_story.render()

    def _position_overworld_boss(self, item, base, camera):
        x, y = base
        cx, cy = camera
        self.canvas.coords(item, ((x + 1) * TILE - cx) * SCALE, ((y + 1) * TILE - cy) * SCALE)

    def _draw_den(self, camera):
        c = self.canvas
        c.delete("den_decor")
        c.itemconfigure(self.den_door_item, state="hidden" if self.outdoors else "normal")
        inside = self._in_den()
        cleared = self.cave_story["den_cleared"]
        c.itemconfigure(self.den_spider_item, state="normal" if inside and not cleared else "hidden")
        props = (*self.den_egg_items.items(), (DEN_STONE, self.den_stone_item), (DEN_SHRINE, self.den_shrine_item))
        for _, item in props:
            c.itemconfigure(item, state="normal" if inside else "hidden")
        for item in self.den_chest_items.values():
            c.itemconfigure(item, state="normal" if inside else "hidden")
        if self.outdoors:
            return
        cx, cy = camera

        def center(tile):
            return (((tile[0] + .5) * TILE - cx) * SCALE, ((tile[1] + .5) * TILE - cy) * SCALE)

        x, y = center(DEN_DOOR)
        c.coords(self.den_door_item, x, y)
        if not self.cave_story["den_unsealed"]:
            c.create_image(x, y-3, image=self.den_gate_web, tags="den_decor")
        if inside:
            self._position_overworld_boss(self.den_spider_item, DEN_NEST, camera)
            for tile, item in props:
                x, y = center(tile)
                c.coords(item, x, y if item == self.den_shrine_item else y + TILE * SCALE // 2)
            opened = self.cave_story["depths_chests"]
            for tile, item in self.den_chest_items.items():
                c.coords(item, *center(tile))
                c.itemconfigure(item, image=self.chest_images[int(DEN_CHESTS[tile][0] in opened)])
            if not cleared:
                x, y = center(DEN_HEART_GATE)
                c.create_image(x, y, image=self.den_gate_web, tags="den_decor")
        c.tag_lower("den_decor", "world_party")

    def _change_area(self, outdoors):
        self.outdoors = outdoors
        self.cave = self.grassland_map if outdoors else self.cavern_map
        self.in_chamber = not outdoors
        self.x, self.y = ((32.5*TILE, 3.5*TILE) if outdoors else (70.5*TILE, 9.5*TILE))
        self.direction = "down"
        self._area_step_latch = True
        self.encounters.reset()
        self.chunk_cache.clear()
        self._update_world(force=True)
        self._start_area_music()
        if outdoors and not self.grass_intro_seen:
            self._grassland_intro()

    def _place_player(self, camera: tuple[float, float]) -> None:
        cx, cy = camera
        party = self._field_party()
        screen_x, screen_y = (self.x-cx)*SCALE, (self.y-cy)*SCALE
        frames = self._field_costume(party[0]) or self.player_frames
        frame = frames[self.direction][self.walk_frame]
        if frame is not self.drawn_player_frame:
            self.canvas.itemconfigure(self.player_item, image=frame)
            self.drawn_player_frame = frame
        self.canvas.coords(self.player_item, screen_x, screen_y)

        inside_den = self._in_den()
        area = (self.cave, self.in_chamber, inside_den)
        trail = self.party_trail.sample((self.x, self.y), self.direction, len(party), area,
                                        self._follower_floor)
        while len(self.follower_items) < len(trail):
            self.follower_items.append(self.canvas.create_image(
                0, 0, tags=("world_party", "party_follower"), state="hidden"))
        self.field_followers.clear()
        for item, member, pos in zip(self.follower_items, party[1:], trail):
            x, y, direction = pos
            name = member["name"]
            frames = self._field_costume(member)
            if frames is None or (x, y) == (self.x, self.y):
                self.canvas.itemconfigure(item, state="hidden")
                continue
            self.canvas.coords(item, (x-cx)*SCALE, (y-cy)*SCALE)
            self.canvas.itemconfigure(item, image=frames[direction][self.walk_frame], state="normal")
            if y > self.y:
                self.canvas.tag_raise(item, self.player_item)
            else:
                self.canvas.tag_lower(item, self.player_item)
            self.field_followers[name.casefold()] = item, member, pos
        for item in self.follower_items[len(trail):]:
            self.canvas.itemconfigure(item, state="hidden")

    def _follower_floor(self, x, y):
        tile = int(x // TILE), int(y // TILE)
        return self._can_walk_world(x, y) and (self.outdoors or (tile in DEN_FLOOR) == self._in_den())

    def _can_walk_world(self, x, y):
        if not self.cave.walkable(x, y):
            return False
        tile = int(x // TILE), int(y // TILE)
        if self.outdoors:
            return ((self.cordon_open or tile != GATE)
                    and tile not in (self.merren_tile, (self.merren_tile[0]+1, self.merren_tile[1])))
        if tile in DEN_FLOOR:
            if not self._in_den() or tile in DEN_STONE_TILES or tile in EGG_SACS or tile in DEN_CHESTS or tile == DEN_SHRINE:
                return False
            return self.cave_story["den_cleared"] or (tile not in DEN_NEST_FOOTPRINT and tile != DEN_HEART_GATE)
        if self._in_den():
            return False
        if self.in_chamber and not self.boss_cleared and tile in self.shalehorn_footprint:
            return False
        stationary_objects = (self.chest_tile, self.stone_tile, self.save_sphere_tile,
                              self.outer_door, self.inner_door, DEN_DOOR)
        return (tile not in stationary_objects and not self.mine_story.blocked(tile)
                and (self.temur_story != "waiting" or tile != self.temur_tile))

    def _update_interaction_hint(self):
        label = None
        if not self.dialogue.active and not self.game_menu.active:
            tile = self._facing_tile()
            if self.outdoors:
                if tile == KORWARD or (tile == GATE and not self.cordon_open):
                    label = "TALK"
                elif tile == SENBRANKA_TILE:
                    label = "ATTUNE"
            elif tile == self.save_sphere_tile and not self.in_chamber:
                label = "SAVE"
            elif tile == DEN_SHRINE and self._in_den():
                label = "SAVE"
            elif tile in DEN_STONE_TILES and self._in_den() and self.cave_story["den_cleared"]:
                label = "ATTUNE"
            elif tile == self.stone_tile and self.boss_cleared:
                label = "ATTUNE"
            elif tile == DEN_DOOR or (not self._in_den() and tile in (self.outer_door, self.inner_door)):
                label = "INSPECT"
        if label is None:
            self.canvas.itemconfigure(self.interaction_hint, state="hidden")
            return
        cx, cy = self.world_camera
        x, y = tile
        self.canvas.coords(self.interaction_hint, ((x + .5) * TILE - cx) * SCALE,
                           ((y + .5) * TILE - cy) * SCALE - 44)
        self.canvas.itemconfigure(self.interaction_hint, text=f"{label} · ENTER / CROSS", state="normal")

    def _roll_field_encounter(self, tile):
        if self.outdoors:
            return (self.cordon_open and tile != GATE and not self.grassland_map.sheltered(tile)
                    and self.encounters.step())
        if self._in_den():
            return den_danger(tile) > 0 and self.encounters.step(chance=.16)
        return not self.in_chamber and self.encounters.step()

    def _tick(self) -> None:
        now = time.monotonic()
        self._flush_pending_music(now)
        self._scan_controller(now)
        self.pad_keys = self._dpad()
        buttons = self._controller_buttons()
        tapped = buttons - self.pad_buttons
        self.pad_buttons = buttons
        shoulder_step = int("member_next" in tapped) - int("member_previous" in tapped)
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
        elif self.screen == "save_slots":
            self.save_scene.navigate(direction, now)
        elif self.screen == "settings":
            self._navigate_settings(direction, now)
        elif self.screen == "sprite_lab":
            if shoulder_step:
                self._change_lab_tab(shoulder_step)
            elif self.lab_tab == 3 and "outfit" in tapped:
                self._change_player_move_outfit()
            lab_direction = next((key for key in ("up", "down", "left", "right") if key in self.pad_keys), None)
            if lab_direction and lab_direction != self.lab_pad_direction and not shoulder_step:
                self._navigate_lab(lab_direction)
            self.lab_pad_direction = lab_direction
            lab = self._active_animation_lab()
            if lab is not None:
                lab.update(now)
        elif self.screen == "tome":
            if shoulder_step:
                self.tome.change_category(shoulder_step)
            self.tome.navigate(direction, now)
        elif self.screen == "shop":
            if direction is None:
                self.shop_direction = None
            elif direction != self.shop_direction or now >= self.shop_repeat_at:
                self.shop_direction, self.shop_repeat_at = direction, now + 0.22
                step = -1 if direction in ("up", "left") else 1
                if direction in ("left", "right"):
                    self._change_shop_tab(step)
                else:
                    self.shop_selection = (self.shop_selection + step) % len(self._shop_stock())
                    self.shop_feedback = ""
                    self._draw_merren_shop()
        elif self.screen == "cave_walk":
            self.mine_story.update_walk(now)
        elif self.screen == "entrance_collapse":
            self.mine_story.update(now)
        elif self.screen == "temur_choice":
            self.mine_story.navigate_choice(direction)
        elif self.screen == "cordon_choice":
            if direction in ("up", "down"):
                choice = int(direction == "down")
                if choice != self.cordon.choice:
                    self.cordon.select(choice)
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
        elif self.screen == "den_intro":
            self._update_den_intro(now)
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
            if shoulder_step:
                self.astral_scene.change_member(shoulder_step)
            if direction is None:
                self._astral_direction_armed = True
            self.astral_scene.navigate(direction if self._astral_direction_armed else None, now)
            self.astral_scene.update(now)
        elif self.screen == "game" and self.game_menu.active:
            # Equipment, Crescendo, and Status use the shoulder buttons.
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
                    dx, dy = DIRECTIONS[active]
                    old_direction, old_frame = self.direction, self.walk_frame
                    self.direction = active
                    nx, ny = self.x + dx * TILE, self.y + dy * TILE
                    next_tile = (int(nx // TILE), int(ny // TILE))
                    if self.outdoors and next_tile == GRASS_ENTRY:
                        if not self._area_step_latch:
                            self._change_area(False)
                    elif not self.outdoors and self.in_chamber and self.boss_cleared and next_tile == (70, 8):
                        if not self._area_step_latch:
                            self._change_area(True)
                    elif self._can_walk_world(nx, ny):
                        previous_music = self._area_music() if self.outdoors else None
                        self.x, self.y = nx, ny
                        if self.outdoors and self._area_music() != previous_music:
                            self._start_area_music()
                        self._area_step_latch = False
                        self.walk_frame = 0 if self.walk_frame == 2 else 2
                        self._update_world()
                        if (not self._start_den_intro(next_tile, now) and not self.mine_story.maybe_warn()
                                and self._roll_field_encounter(next_tile)):
                            self._begin_battle(now)
                    else:
                        self.walk_frame = 1
                        if (self.direction, self.walk_frame) != (old_direction, old_frame):
                            self._update_world()
                    self.next_step_at = now + STEP_INTERVAL
            else:
                self.held_direction = None
                self._area_step_latch = False
                if self.walk_frame != 1:
                    self.walk_frame = 1
                    self._update_world()
        if self.screen == "game" and hasattr(self, "save_sphere_frames"):
            self._update_shalehorn_shake(now)
            self.canvas.itemconfigure("save_sphere", image=self.save_sphere_frames[int(now*2)%4])
            self._update_interaction_hint()
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
