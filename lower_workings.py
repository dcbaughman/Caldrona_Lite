"""Larvel's sidequest: the Old Workings below the side-drift stair.

Larvel's crew ran deeper when the floor started knocking, and a Selvar door shut behind them.
Hesk, the crew's tally-keeper, pinned ledger pages at each turn. Their fronts give the way and
their backs hold the old ledger. Selvar rubbings teach Retri enough glyphs to read the door.

The workings sit in an unused band of the cavern map (rows 45-75), apart from every other floor,
the same way the Depths do. Nothing here is visible or walkable unless Retri is standing in it.
"""
import time
import tkinter as tk

from cave_story import ENTRY
from dialogue import DialogueLine
from research import SELVAR_ANALECT
from side_drift import STAIRWELL_TILES

TILE = 16


def _rect(left, top, right, bottom):
    """Tiles of a room, with exclusive right and bottom edges like CavernInstance._room."""
    return {(x, y) for y in range(top, bottom) for x in range(left, right)}


def _hall(start, end, width):
    """The same L-shaped carve as CavernInstance._hall."""
    tiles = set()
    (x, y), (ex, ey) = start, end
    radius = width // 2
    while True:
        tiles.update((x + dx, y + dy) for dy in range(-radius, radius + 1) for dx in range(-radius, radius + 1))
        if (x, y) == (ex, ey):
            return tiles
        if x != ex:
            x += 1 if ex > x else -1
        else:
            y += 1 if ey > y else -1


ROOMS = (
    ("Stair Foot", (6, 46, 12, 51)),
    ("Timber Gallery", (18, 45, 26, 52)),
    ("Bad-Air Drift", (32, 45, 37, 50)),
    ("Flooded Cut", (14, 56, 30, 61)),
    ("Sump", (35, 55, 41, 61)),
    ("High Cut", (4, 56, 9, 67)),
    ("Foreman's Cache", (14, 64, 20, 68)),
    ("Knocking Gallery", (4, 70, 23, 76)),
    ("Seal Hall", (28, 68, 37, 76)),
    ("Crew Refuge", (28, 63, 37, 66)),
)
ROOM_TILES = tuple((name, frozenset(_rect(*box))) for name, box in ROOMS)
HALLS = (
    ((12, 48), (17, 48), 1),  # the crawl Larvel can't fit through
    ((26, 47), (31, 47), 1),
    ((21, 52), (21, 55), 3),
    ((30, 59), (34, 59), 1),
    ((13, 58), (9, 58), 1),
    ((9, 65), (13, 65), 1),
    ((6, 67), (6, 69), 3),
    ((23, 72), (27, 72), 3),
)

# The Selvar door fills the two-row wall between the Seal Hall and the Crew Refuge.
DOOR = (31, 66)
DOOR_TILES = frozenset((DOOR[0] + dx, DOOR[1] + dy) for dx in (0, 1) for dy in (0, 1))
_BASE = set().union(*(tiles for _, tiles in ROOM_TILES), *(_hall(*hall) for hall in HALLS))
OPEN_FLOOR = frozenset(_BASE | DOOR_TILES)
CLOSED_FLOOR = frozenset(_BASE)
WORKINGS_FLOOR = OPEN_FLOOR
WORKINGS_HEIGHT = max(y for _, y in OPEN_FLOOR) + 3

STAIR_UP = (8, 46)
STAIR_UP_TILES = frozenset((STAIR_UP[0] + dx, STAIR_UP[1] + dy) for dx in (0, 1) for dy in (0, 1))
ARRIVAL = (8, 48)
CHARCOAL = (10, 49)
DRIFT_RETURN = (16, 17)  # just south of the stairwell in the side drift
ENTRANCE_LANDING = (ENTRY[0], ENTRY[1] + 1)
SHORTCUT = (35, 63)
SHORTCUT_LANDING = (35, 64)

CRACK = (15, 72)
CRACK_TILES = frozenset((CRACK[0] + dx, CRACK[1] + dy) for dx in (0, 1) for dy in (0, 1))
KNOCKER_TRIGGER_X = 12  # crossing this column in the Knocking Gallery wakes it
KNOCKER_RETREAT = (8, 72)
CACHE = (14, 67)
CACHE_LOOT = (("Ether", 1), ("Remedy", 2))
CINDER_COATS = 2
HESK_REFUGE = (32, 64)
REFUGE_CREW = ((29, 64), (31, 64), (34, 64))
LARVEL_DRIFT = (19, 16)
HESK_DRIFT = (19, 17)

# Ledger pages, in trail order. Main pages lead to the crew; side pages are extra history.
PAGES = {
    "p1": ((19, 46), True, (
        "Front: \"Bad air down the east drift. We went south. Hesk.\"",
        "Back: \"Shift tally. Eleven carts of shale. One cart of blue, sent up sealed. "
        "Foreman says no names on the blue cart.\"",
    )),
    "o1": ((36, 46), False, (
        "Front: \"Dead end. The air's sour. Don't linger.\"",
        "Back, an old survey note, crossed out: \"Blue vein runs under the Selvar markers. Do not cut.\"",
        "Under it, in another hand: \"Paid in full. Cut it.\"",
    )),
    "p2": ((16, 56), True, (
        "Front: \"Water's over the cart rail. Taking the high cut west.\"",
        "Back: \"Foreman's pay, three weeks early. Sunrest silver, from a buyer who signs with a slashed mark.\"",
    )),
    "o2": ((40, 56), False, (
        "Front: \"Sump's flooding. Nothing back here but the old pump.\"",
        "Back: \"Night shift. The pump keeps tapping from below. It isn't the pump. Something knocks back.\"",
    )),
    "p3": ((4, 57), True, (
        "Front: \"Knocking under the floor ahead. Keep to the walls and run for the far side.\"",
        "Someone has left Cinder Coats in the foreman's cache. Wear one down there; the stone is hot enough to blister.",
        "Back: \"Lower gallery timbers cracked from beneath. The floor pushed up. It didn't fall in.\"",
    )),
    "o3": ((19, 64), False, (
        "Front: \"Foreman's cache. There are two heat-lined coats. He won't miss them.\"",
        "Back, the foreman's own note: \"The buyer wants every Selvar stone in the seam cut through.\"",
        "\"Says the old prayers keep something asleep down here. Says that's the point.\"",
    )),
    "p4": ((29, 68), True, (
        "Front: \"The door shut behind us on its own. I copied the marks. Can't read them. If you can, let us out.\"",
        "Back: three Selvar glyphs, traced in charcoal.",
    )),
}
MAIN_PAGES = tuple(key for key, (_, main, _) in PAGES.items() if main)

# Selvar steles. The three main ones hold the words the door needs.
RUBBINGS = {
    "r1": ((6, 46), True, "keep"),
    "r4": ((34, 45), False, "below"),
    "r2": ((27, 56), True, "sleeping"),
    "r5": ((37, 55), False, "name"),
    "r6": ((16, 64), False, "mountain"),
    "r3": ((35, 68), True, "open"),
}
MAIN_RUBBINGS = tuple(key for key, (_, main, _) in RUBBINGS.items() if main)
# The Fjalora word cut down each stone in Selvar (see the Fjalora codex). Words the lexicon
# doesn't have yet use the nearest root: arva (earth) for below, ripo (rest) for sleeping,
# wurd (spoken word) for name, shala (shale) for mountain.
RUBBING_FJALORA = {"r1": "vela", "r4": "arva", "r2": "ripo", "r5": "wurd", "r6": "shala", "r3": "apri"}
PIT_LANTERN = "pit_lantern"

STAGES = ("unstarted", "started", "rescued", "complete")


def fresh_workings():
    # The original boss-clear key stays valid in saves made before the Wyvern.
    return {"stage": "unstarted", "pages": [], "rubbings": [], "charcoal": False, "knocker": False,
            "cache": False, "cinder_coats": False}


def workings_location(tile):
    return next((f"Lower Workings · {name}" for name, tiles in ROOM_TILES if tile in tiles), "Lower Workings")


class LowerWorkings:
    def __init__(self, app, assets, scale):
        self.app, self.scale = app, scale
        art = assets / "mine-polish" / "workings"
        self.images = {name: tk.PhotoImage(master=app.root, file=str(art / f"{name}.png")).zoom(scale)
                       for name in ("stair-up", "ledger-post", "ledger-post-bare",
                                    "selvar-door", "floor-crack", "knocker-burrow", "charcoal", "shortcut",
                                    *(f"stele-{key}{tail}" for key in RUBBINGS for tail in ("", "-rubbed")))}
        c = app.canvas
        self.stair_item = c.create_image(0, 0, image=self.images["stair-up"], anchor="nw", tags=("workings",))
        self.door_item = c.create_image(0, 0, image=self.images["selvar-door"], anchor="nw", tags=("workings",))
        self.crack_item = c.create_image(0, 0, image=self.images["floor-crack"], anchor="nw", tags=("workings",))
        self.cache_item = c.create_image(0, 0, image=app.chest_images[0], tags=("workings",))
        self.charcoal_item = c.create_image(0, 0, image=self.images["charcoal"], tags=("workings",))
        self.shortcut_item = c.create_image(0, 0, image=self.images["shortcut"], anchor="s", tags=("workings",))
        self.page_items = {key: c.create_image(0, 0, anchor="sw", tags=("workings",)) for key in PAGES}
        self.stele_items = {key: c.create_image(0, 0, anchor="s", tags=("workings",)) for key in RUBBINGS}
        larvel = app._load_player("Larvel")
        hesk = app._load_player("Hesk")
        self.larvel_faces = {direction: frames[1] for direction, frames in larvel.items()}
        self.hesk_faces = {direction: frames[1] for direction, frames in hesk.items()}
        self.larvel_item = c.create_image(0, 0, image=self.larvel_faces["left"], tags=("workings", "world_party"))
        self.hesk_item = c.create_image(0, 0, image=self.hesk_faces["down"], tags=("workings", "world_party"))
        self.crew_images = tuple(tk.PhotoImage(master=app.root, file=str(art / f"crew-{i}.png")).zoom(scale)
                                 for i in range(len(REFUGE_CREW)))
        self.crew_items = tuple(c.create_image(0, 0, image=image, tags=("workings", "world_party"))
                                for image in self.crew_images)
        for item in (self.stair_item, self.door_item, self.crack_item, self.cache_item, self.charcoal_item, self.shortcut_item,
                     *self.page_items.values(), *self.stele_items.values(), self.larvel_item, self.hesk_item, *self.crew_items):
            c.tag_lower(item, "player")
        self.boss_pending = False
        self.rescue_scene = False
        self.knocker_noise = assets / "audio" / "shalehorn-scrape.wav"

    # --- state -----------------------------------------------------------------
    @property
    def state(self):
        story = self.app.cave_story
        if not isinstance(story.get("workings"), dict):
            story["workings"] = fresh_workings()
        progress = story["workings"]
        progress.setdefault("charcoal", bool(progress["rubbings"]))
        return progress

    @property
    def stage(self):
        return self.state["stage"]

    def door_open(self):
        return self.stage in ("rescued", "complete")

    def floor(self):
        return OPEN_FLOOR if self.door_open() else CLOSED_FLOOR

    def here(self):
        a = self.app
        return not a.outdoors and a._world_tile() in WORKINGS_FLOOR

    def _in_cavern(self):
        a = self.app
        return not (a.outdoors or a.in_chamber or a._in_den() or self.here())

    def larvel_at_drift(self):
        return self.stage != "complete" and not self.app.opening_intro_active

    def hesk_at_drift(self):
        return self.stage == "rescued"

    def hesk_in_refuge(self):
        return self.rescue_scene or self.stage in ("unstarted", "started")

    def blocked(self, tile):
        """Tiles a prop or a person stands on, inside the workings."""
        s = self.state
        if tile in STAIR_UP_TILES or tile == CACHE:
            return True
        if tile == SHORTCUT or (tile == CHARCOAL and not s["charcoal"]):
            return True
        if any(tile == spot for spot, _, _ in PAGES.values()) or any(tile == spot for spot, _, _ in RUBBINGS.values()):
            return True
        if tile in DOOR_TILES and not self.door_open():
            return True
        if tile in CRACK_TILES and s["knocker"]:
            return True
        return (tile == HESK_REFUGE or tile in REFUGE_CREW) and self.hesk_in_refuge()

    def walkable(self, tile):
        return self.here() and tile in self.floor() and not self.blocked(tile)

    def blocks_cavern(self, tile):
        """Larvel and Hesk stand in the side drift."""
        return ((tile == LARVEL_DRIFT and self.larvel_at_drift())
                or (tile == HESK_DRIFT and self.hesk_at_drift())
                or (tile == ENTRY and self.stage == "complete"))

    # --- the map -----------------------------------------------------------------
    def location(self):
        return workings_location(self.app._world_tile())

    def objective(self):
        if self.stage == "started":
            return "Find Larvel's crew"
        if self.stage == "rescued":
            return "Return to Larvel"
        return ""

    def hint(self, tile):
        if self.here():
            if tile == SHORTCUT and self.stage == "complete":
                return "SHORTCUT"
            if tile == CHARCOAL and not self.state["charcoal"]:
                return "TAKE"
            if tile in STAIR_UP_TILES:
                return "CLIMB"
            if tile in DOOR_TILES and not self.door_open():
                return "INSPECT"
            if tile == CACHE:
                return "OPEN"
            for key, (spot, _, _) in PAGES.items():
                if tile == spot:
                    return "READ" if key not in self.state["pages"] else "INSPECT"
            for key, (spot, _, _) in RUBBINGS.items():
                if tile == spot:
                    return "RUB" if key not in self.state["rubbings"] else "INSPECT"
            return None
        if self._in_cavern() and tile == ENTRY and self.stage == "complete":
            return "SHORTCUT"
        if self._in_cavern() and self.blocks_cavern(tile):
            return "TALK"
        if self._in_cavern() and tile in STAIRWELL_TILES and self.stage != "unstarted":
            return "DESCEND"
        return None

    # --- interaction -------------------------------------------------------------
    def interact(self):
        a = self.app
        tile = a._facing_tile()
        if self._in_cavern():
            if tile == ENTRY and self.stage == "complete":
                self._move_to(SHORTCUT_LANDING, "down")
                return True
            if tile == LARVEL_DRIFT and self.larvel_at_drift():
                self._talk_to_larvel()
                return True
            if tile == HESK_DRIFT and self.hesk_at_drift():
                self._talk_to_larvel()
                return True
            if tile in STAIRWELL_TILES:
                if self.stage != "unstarted":
                    a.dialogue.show([DialogueLine("Retri", "Down the stair, then through the crawl.", thought=True)],
                                    on_complete=lambda: self._move_to(ARRIVAL, "down"))
                    return True
                if self.stage == "unstarted" and self.larvel_at_drift():
                    a.dialogue.show([DialogueLine(
                        "Retri", "Someone's lantern is burning far below. The miner by the stair might know whose.",
                        thought=True)])
                    return True
            return False
        if not self.here():
            return False
        s = self.state
        if tile == SHORTCUT and self.stage == "complete":
            self._move_to(ENTRANCE_LANDING, "down")
            return True
        if tile == CHARCOAL and not s["charcoal"]:
            s["charcoal"] = True
            a._update_world()
            a.dialogue.show([DialogueLine("Retri", "Temur's charcoal. He left a scrap of folded paper with it.", thought=True),
                             DialogueLine("", "Picked up Temur's charcoal.")])
            return True
        if tile in STAIR_UP_TILES:
            self._move_to(DRIFT_RETURN, "down")
            return True
        if tile == CACHE:
            self._open_cache()
            return True
        for key, (spot, _, text) in PAGES.items():
            if tile == spot:
                self._read_page(key, text)
                return True
        for key, (spot, _, word) in RUBBINGS.items():
            if tile == spot:
                self._take_rubbing(key, word)
                return True
        if tile in DOOR_TILES and not self.door_open():
            self._read_door()
            return True
        return False

    def _open_cache(self):
        a, state = self.app, self.state
        lines = []
        if not state["cache"]:
            state["cache"] = True
            for item, count in CACHE_LOOT:
                a._receive_loot(item, count)
            lines.append(DialogueLine("", "Ether ×1  ·  Remedy ×2"))
            a.canvas.itemconfigure(self.cache_item, image=a.chest_images[1])
        if not state.get("cinder_coats", False):
            state["cinder_coats"] = True
            a._receive_loot("cinder_coat", CINDER_COATS)
            lines.append(DialogueLine("", "Cinder Coat ×2. Equip these coats to halve fire damage."))
        a.dialogue.show(lines or [DialogueLine("", "The cache is empty.")])

    def _talk_to_larvel(self):
        a, s = self.app, self.state
        if s["stage"] == "unstarted":
            s["stage"] = "started"
            a.dialogue.show([
                DialogueLine("Larvel", "That lamp down there is ours. My crew ran when the floor started knocking."),
                DialogueLine("Larvel", "The stair collapsed past the first landing. There's a crawlway left, but I can't fit with this rig on."),
                DialogueLine("Retri", "I can. Getting into places like that is what a skirter's for."),
                DialogueLine("Larvel", "Hesk keeps our ledger. Hesk will have pinned pages at the turns. Follow them."),
                DialogueLine("Larvel", "I'll hold the signal rope up here. Bring them back to me."),
            ])
            a._update_world()
        elif s["stage"] == "started":
            a.dialogue.show([DialogueLine("Larvel", "Follow Hesk's pages. I've got the rope.")])
        elif s["stage"] == "rescued":
            lines = [
                DialogueLine("Hesk", "Told you the pages would work."),
                DialogueLine("Larvel", "You brought every one of them back. I won't forget it, skirter."),
                DialogueLine("Larvel", "Take my pit lantern. Its flame holds, even in the worst dark."),
                DialogueLine("", "Received the Pit Lantern."),
            ]
            if len(s["pages"]) == len(PAGES):
                lines += [
                    DialogueLine("Retri", "Hesk's ledger says someone paid your foreman to cut through the Selvar stones."),
                    DialogueLine("Larvel", "A buyer who signs with a slashed mark... Those same slashes are cut across the old seal."),
                    DialogueLine("Retri", "Then someone wanted that thing awake."),
                ]
            lines += [
                DialogueLine("Larvel", "We dug through to the old cave mouth. You can cut straight between the refuge and the entrance now."),
                DialogueLine("Larvel", "I'm taking the crew home to Sunrest. My brother Rando will want to hear all of it."),
                DialogueLine("Larvel", "Find us there. Rando won't believe you got through that crawl."),
            ]
            a.dialogue.show(lines, on_complete=self._crew_leaves)

    def _crew_leaves(self):
        a = self.app
        self.state["stage"] = "complete"
        a._receive_loot(PIT_LANTERN, 1)
        a.cave_story["entrance_collapsed"] = False
        a._update_world(force=True)

    def _read_page(self, key, text):
        a, s = self.app, self.state
        first = key not in s["pages"]
        if first:
            s["pages"].append(key)
        lines = [DialogueLine("Retri", line, thought=True) for line in text]
        if first:
            lines.append(DialogueLine("", f"Ledger page {len(s['pages'])} of {len(PAGES)}"))
        a.dialogue.show(lines)
        self.render(a.world_camera)

    def _take_rubbing(self, key, word):
        a, s = self.app, self.state
        if key in s["rubbings"]:
            a.dialogue.show([DialogueLine("Retri", f"I've already rubbed this one. The glyph means \"{word}\".",
                                          thought=True)])
            return
        if not s["charcoal"]:
            a.dialogue.show([DialogueLine("Retri", "These letters would take a rubbing. There was a stick of charcoal by the stairs.", thought=True)])
            return
        s["rubbings"].append(key)
        lines = [
            DialogueLine("Retri", "A Selvar stone. Temur's charcoal takes a clean rubbing.", thought=True),
            DialogueLine("Retri", f"Next to the others it reads plainly. This glyph means \"{word}\".", thought=True),
            DialogueLine("", f"Selvar rubbing {len(s['rubbings'])} of {len(RUBBINGS)}"),
        ]
        if len(s["rubbings"]) == len(RUBBINGS):
            a._receive_loot(SELVAR_ANALECT, 1)
            lines += [
                DialogueLine("Retri", "That's all of them. Together they read like a whole Selvar prayer.", thought=True),
                DialogueLine("", "The rubbings bind into a Selvar Analect. Open the Tome to study it."),
            ]
        a.dialogue.show(lines)
        self.render(a.world_camera)

    def _read_door(self):
        a, s = self.app, self.state
        if not s["knocker"]:
            a.dialogue.show([DialogueLine("Retri", "The floor is still shaking. I can't get the crew out past that thing.", thought=True)])
            return
        if "p4" not in s["pages"]:
            a.dialogue.show([
                DialogueLine("Retri", "A Selvar door, shut tight. I can hear voices behind it.", thought=True),
                DialogueLine("Retri", "There's a ledger page pinned up near the door.", thought=True),
            ])
            return
        missing = [key for key in MAIN_RUBBINGS if key not in s["rubbings"]]
        if missing:
            known = len(MAIN_RUBBINGS) - len(missing)
            a.dialogue.show([
                DialogueLine("Retri", f"Hesk copied three glyphs. I can read {known} of them.", thought=True),
                DialogueLine("Retri", "I need more Selvar rubbings from stones along the way.", thought=True),
            ])
            return
        s["stage"] = "rescued"
        self.rescue_scene = True
        a.chunk_cache.clear()
        a._update_world(force=True)
        a.dialogue.show([
            DialogueLine("Retri", "\"Open, for those who keep it sleeping.\""),
            DialogueLine("", "The slab grinds aside."),
            DialogueLine("Hesk", "Light! Hesk, tally-keeper. Four of us in here, all breathing."),
            DialogueLine("Hesk", "You followed my pages? Then you've read more of that ledger than the foreman ever wanted read."),
            DialogueLine("Hesk", "I saw Temur take a rubbing upstairs. The Veskar cuts were already there when he came."),
            DialogueLine("Retri", "Larvel's waiting at the top of the stair. Go on up. I'll be right behind you."),
        ], on_complete=self._release_crew)

    def _release_crew(self):
        self.rescue_scene = False
        self.app._update_world()

    def _move_to(self, tile, direction):
        a = self.app
        a.x, a.y = (tile[0] + .5) * TILE, (tile[1] + .5) * TILE
        a.direction, a.walk_frame = direction, 1
        a.keys.clear()
        a.held_direction = None
        a.encounters.reset()
        a.chunk_cache.clear()
        a._update_world(force=True)

    # --- the Ember Wyvern ----------------------------------------------------------
    def on_step(self, tile, now):
        """Wake the Ember Wyvern when Retri crosses the gallery."""
        a, s = self.app, self.state
        if s["knocker"] or self.boss_pending or not self.here():
            return False
        if tile not in dict(ROOM_TILES)["Knocking Gallery"] or tile[0] < KNOCKER_TRIGGER_X:
            return False
        self.boss_pending = True
        a.shalehorn_shake_started = now
        a._update_shalehorn_shake(now)
        a._play_sfx(self.knocker_noise, volume=.58)
        a.dialogue.show([
            DialogueLine("Retri", "Sa dorma. 'May it sleep.' The old binding says the mountain spirit put it down here.", thought=True),
            DialogueLine("", "The last Selvar stroke splits. The buried beast stirs, and orange light spills through the timbers."),
        ], on_complete=lambda: a._begin_battle(time.monotonic()))
        return True

    def boss_battle(self, battle_args):
        from battle import EmberWyvernBattle
        self.boss_pending = False
        return EmberWyvernBattle(**battle_args)

    def finish_battle(self, model, outcome):
        from battle import EmberWyvernBattle
        if not isinstance(model, EmberWyvernBattle):
            return
        a = self.app
        if outcome == "victory":
            self.state["knocker"] = True
        elif outcome == "fled":
            a.x, a.y = ((value + .5) * TILE for value in KNOCKER_RETREAT)
        a.chunk_cache.clear()

    # --- drawing -------------------------------------------------------------------
    def render(self, camera):
        a, c = self.app, self.app.canvas
        cx, cy = camera
        here, cavern = self.here(), self._in_cavern()
        s = self.state

        def place(item, x, y, visible):
            c.coords(item, (x - cx) * self.scale, (y - cy) * self.scale)
            c.itemconfigure(item, state="normal" if visible else "hidden")

        place(self.stair_item, STAIR_UP[0] * TILE, STAIR_UP[1] * TILE, here)
        place(self.charcoal_item, (CHARCOAL[0] + .5) * TILE, (CHARCOAL[1] + .5) * TILE, here and not s["charcoal"])
        place(self.shortcut_item, (SHORTCUT[0] + .5) * TILE, (SHORTCUT[1] + 1) * TILE, here and self.stage == "complete")
        place(self.door_item, DOOR[0] * TILE, DOOR[1] * TILE, here and not self.door_open())
        c.itemconfigure(self.crack_item, image=self.images["knocker-burrow" if s["knocker"] else "floor-crack"])
        place(self.crack_item, CRACK[0] * TILE, CRACK[1] * TILE, here)
        c.itemconfigure(self.cache_item, image=a.chest_images[int(s["cache"])])
        place(self.cache_item, (CACHE[0] + .5) * TILE, (CACHE[1] + .5) * TILE, here)
        for key, ((x, y), _, _) in PAGES.items():
            c.itemconfigure(self.page_items[key],
                            image=self.images["ledger-post-bare" if key in s["pages"] else "ledger-post"])
            place(self.page_items[key], x * TILE, (y + 1) * TILE, here)
        for key, ((x, y), _, _) in RUBBINGS.items():
            c.itemconfigure(self.stele_items[key],
                            image=self.images[f"stele-{key}-rubbed" if key in s["rubbings"] else f"stele-{key}"])
            place(self.stele_items[key], (x + .5) * TILE, (y + 1) * TILE, here)
        if here:
            place(self.hesk_item, (HESK_REFUGE[0] + .5) * TILE, (HESK_REFUGE[1] + .5) * TILE, self.hesk_in_refuge())
            c.itemconfigure(self.hesk_item, image=self.hesk_faces["down"])
        else:
            place(self.hesk_item, (HESK_DRIFT[0] + .5) * TILE, (HESK_DRIFT[1] + .5) * TILE,
                  cavern and self.hesk_at_drift())
            c.itemconfigure(self.hesk_item, image=self.hesk_faces["left"])
        place(self.larvel_item, (LARVEL_DRIFT[0] + .5) * TILE, (LARVEL_DRIFT[1] + .5) * TILE,
              cavern and self.larvel_at_drift())
        for tile, item in zip(REFUGE_CREW, self.crew_items):
            place(item, (tile[0] + .5) * TILE, (tile[1] + .5) * TILE, here and self.hesk_in_refuge())

