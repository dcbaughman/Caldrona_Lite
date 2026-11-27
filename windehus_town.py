"""Windehus in the field, and the rooms behind its doors.

The town's flat layer (grass, paving, walls, stairs and shade) comes baked into one image by
prepare_town_tiles.py, and the world chunks are cut from it. Every house, tree, fence and prop is
its own canvas image, stacked back to front, and the party is slotted in among them by the row it
stands on, so it walks behind a house or in front of it. The mill's sails turn, the sheep-birds in
the hay pen breathe and the square's lamps flicker.

Walking into the door of the inn, a shop or the mill goes inside (windehus_rooms.py). A room works
the same way: its floor and walls come baked by prepare_town_rooms.py, and its furniture stands
in sorted order round the party. Hearth fires and the forge flicker and the mill's spur wheel
turns. Stepping out through the doorway goes back to the street, in front of the door.
"""
from bisect import bisect_right
import json
import tkinter as tk

from grassland import FROM_TOWN
import windehus
import windehus_rooms

TILE = windehus.TILE
TAG = "windehus_town"
GROUND = "windehus-ground.png"
SAIL_SECONDS = .3              # each frame is a sixteenth turn of the sails
BIRD_MS = (650, 250, 150)      # the sheep-bird idle cycle, as the mount manifest times it
BIRD_PHASE_MS = 370            # so the birds don't breathe together
# The lamp flame's loop, timed like the trail lanterns: rest, left, peak, right, dip, ember.
# Each lamp runs three frames behind the one before, so they never flicker together.
LAMP_MS = (110, 100, 90, 110, 120, 130)
LAMP_PHASE_MS = sum(LAMP_MS[:3])
# Indoors: {sprite prefix: frame times in ms}. The spur wheel turns a quarter cog a frame, in
# step with the sails outside, and wall lanterns flicker like the lamps in the square.
ROOM_MOTION = {"hearth-": (140, 120, 160), "forge-": (190, 170, 210),
               "spurwheel-": (round(SAIL_SECONDS * 1000),) * 4, "lantern-": LAMP_MS}


class TownMap:
    """A floor in the shape the field code expects of an area: the town, or a room."""

    def __init__(self, floor, width=windehus.WIDTH, height=windehus.HEIGHT, spawn=windehus.ARRIVAL):
        self.floor = floor
        self.width, self.height = width, height
        self.spawn = ((spawn[0] + .5) * TILE, (spawn[1] + .5) * TILE)

    def walkable(self, px, py):
        return (int(px // TILE), int(py // TILE)) in self.floor


class WindehusTown:
    def __init__(self, app, assets, scale):
        self.app, self.scale = app, scale
        self.art = assets / "town"
        self.spots = json.loads((self.art / "tileset.json").read_text(encoding="utf-8"))
        self.sizes = {name: (w, h) for name, (x, y, w, h) in self.spots.items()}
        self.map = TownMap(windehus.floor(self.sizes))
        self.room_art = self.art / "rooms"
        self.room_spots = json.loads((self.room_art / "furniture.json").read_text(encoding="utf-8"))
        self.room_sizes = {name: (w, h) for name, (x, y, w, h) in self.room_spots.items()}
        self.room_maps = {
            name: TownMap(windehus_rooms.floor(room, self.room_sizes), room.width, room.height,
                          windehus_rooms.arrival(room))
            for name, room in windehus_rooms.ROOMS.items()}
        self.entrances = windehus_rooms.entrances(self.sizes)
        self.room = None               # the Room the party is in, or None on the street
        self.door = None               # the town door it came in by
        self.atlas = self.ground = self.furniture = None
        self.room_grounds = {}
        self.sprites = {}
        self.room_sprites = {}
        self.layers = []           # (foot y, lowest canvas item) back to front
        self.keys = []
        self.sails = None
        self.sail_frame = 0
        self.birds = []            # [item, facing, phase ms, frame]
        self.lamps = []            # [item, phase ms, frame]
        self.motions = []          # indoors: [item, prefix, frame times, phase ms, frame]
        self.drawn_camera = (0.0, 0.0)

    def here(self):
        return self.app.in_town

    def location(self):
        return self.room.title if self.room else "Windehus"

    # --- art ---------------------------------------------------------------------------

    def _load(self):
        if self.ground is not None:
            return
        root = self.app.root
        self.atlas = tk.PhotoImage(master=root, file=str(self.art / "tileset.png"))
        self.ground = tk.PhotoImage(master=root, file=str(self.art / GROUND))

    def _load_room(self, room):
        if self.furniture is None:
            self.furniture = tk.PhotoImage(master=self.app.root, file=str(self.room_art / "furniture.png"))
        if room.name not in self.room_grounds:
            self.room_grounds[room.name] = tk.PhotoImage(
                master=self.app.root, file=str(self.room_art / f"{room.name}-ground.png"))

    def _crop(self, atlas, spots, cache, name):
        if name not in cache:
            x, y, w, h = spots[name]
            s = self.scale
            image = tk.PhotoImage(master=self.app.root, width=w * s, height=h * s)
            image.tk.call(image, "copy", atlas, "-from", x, y, x + w, y + h, "-zoom", s)
            cache[name] = image
        return cache[name]

    def sprite(self, name):
        """A town sprite, or a piece of furniture while indoors."""
        if self.room is not None:
            return self._crop(self.furniture, self.room_spots, self.room_sprites, name)
        return self._crop(self.atlas, self.spots, self.sprites, name)

    def chunk(self, key, tiles):
        """One world chunk of the flat layer, at screen scale. Past the edge of a room it is
        left clear, so the dark of the canvas shows."""
        size, s = tiles * TILE, self.scale
        ground = self.room_grounds[self.room.name] if self.room else self.ground
        photo = tk.PhotoImage(master=self.app.root, width=size * s, height=size * s)
        x0, y0 = key[0] * size, key[1] * size
        cx0, cy0 = max(0, x0), max(0, y0)
        x1, y1 = min(x0 + size, ground.width()), min(y0 + size, ground.height())
        if x1 > cx0 and y1 > cy0:
            photo.tk.call(photo, "copy", ground, "-from", cx0, cy0, x1, y1, "-zoom", s,
                          "-to", (cx0 - x0) * s, (cy0 - y0) * s)
        return photo

    def _things(self):
        if self.room is not None:
            return windehus_rooms.things(self.room, self.room_sizes)
        return windehus.things(self.sizes)

    def _place_things(self):
        c, s = self.app.canvas, self.scale
        c.delete(TAG)
        self.layers.clear()
        self.birds.clear()
        self.lamps.clear()
        self.motions.clear()
        self.sails = None
        for index, (key, _, steps) in enumerate(self._things()):
            first = None
            for name, px, py in steps:
                item = c.create_image(px * s, py * s, image=self.sprite(name), anchor="nw", tags=(TAG,))
                first = first or item
                prefix = name.rsplit("-", 1)[0] + "-"
                if self.room is not None:
                    if prefix in ROOM_MOTION:
                        times = ROOM_MOTION[prefix]
                        for frame in range(len(times)):
                            self.sprite(f"{prefix}{frame}")
                        phase = len(self.motions) * (LAMP_PHASE_MS if prefix == "lantern-" else 230)
                        self.motions.append([item, prefix, times, phase, 0])
                elif name == windehus.MILL_SAILS:
                    self.sails = item
                elif name.startswith("sheepbird-"):
                    facing = name.split("-")[1]
                    for frame in range(len(BIRD_MS)):
                        self.sprite(f"sheepbird-{facing}-{frame}")
                    self.birds.append([item, facing, len(self.birds) * BIRD_PHASE_MS, int(name[-1])])
                elif name.startswith("lamp-"):
                    for frame in range(len(LAMP_MS)):
                        self.sprite(f"lamp-{frame}")
                    self.lamps.append([item, len(self.lamps) * LAMP_PHASE_MS, int(name[-1])])
            self.layers.append((key, first))
        self.keys = [key for key, _ in self.layers]
        found = c.find_withtag(TAG)
        self.last_item = found[-1] if found else None
        # The town stands below the party and everything drawn over the field.
        if found:
            c.tag_lower(TAG, self.app.player_item)
        self.drawn_camera = (0.0, 0.0)

    # --- coming and going --------------------------------------------------------------

    def enter(self):
        """Arrive on the road from Sunrest."""
        a = self.app
        self._load()
        a.in_town = True
        a.outdoors, a.in_chamber = True, False
        self.room = self.door = None
        a.cave = self.map
        a.x, a.y = self.map.spawn
        a.direction = "up"
        self._arrive()
        self._place_things()
        a._update_world(force=True)
        a._start_area_music()

    def leave(self, tile):
        """Walk back down the road to the grasslands, at the north end of the west road."""
        a = self.app
        a.in_town = False
        self.room = self.door = None
        a.canvas.delete(TAG)
        self.layers.clear()
        self.birds.clear()
        self.lamps.clear()
        self.motions.clear()
        self.sails = None
        a.cave = a.grassland_map
        a.x, a.y = (tile[0] + .5) * TILE, (tile[1] + .5) * TILE
        a.direction = "down"
        self._arrive()
        a._update_world(force=True)
        a._start_area_music()

    def passage(self, tile):
        """True if stepping onto this tile takes the party somewhere else: out of town down
        the road, in at a door, or out through a room's doorway."""
        if self.room is not None:
            return windehus_rooms.leaves_room(self.room, tile)
        return windehus.leaves_town(tile) or tile in self.entrances

    def go(self, tile):
        """Take the passage onto this tile (see passage)."""
        if self.room is not None:
            self.exit_room()
        elif windehus.leaves_town(tile):
            self.leave(FROM_TOWN)
        else:
            self.enter_room(self.entrances[tile], tile)

    def enter_room(self, name, door):
        """Step in at a door: arrive just inside the room's doorway, facing in."""
        a = self.app
        self.room, self.door = windehus_rooms.ROOMS[name], door
        self._load_room(self.room)
        a.cave = self.room_maps[name]
        a.x, a.y = a.cave.spawn
        a.direction = "up"
        self._arrive()
        self._place_things()
        a._update_world(force=True)

    def exit_room(self):
        """Step out through the doorway, onto the street in front of the door."""
        a = self.app
        x, y = self.door
        self.room = self.door = None
        a.cave = self.map
        a.x, a.y = (x + .5) * TILE, (y + 1.5) * TILE
        a.direction = "down"
        self._arrive()
        self._place_things()
        a._update_world(force=True)

    def _arrive(self):
        a = self.app
        a._area_step_latch = True
        a.encounters.reset()
        a.chunk_cache.clear()

    # --- every frame -------------------------------------------------------------------

    def render(self, camera):
        if not self.here() or not self.layers:
            return
        c, s = self.app.canvas, self.scale
        (ox, oy), (cx, cy) = self.drawn_camera, camera
        if (ox, oy) != (cx, cy):
            c.move(TAG, (ox - cx) * s, (oy - cy) * s)
            self.drawn_camera = camera
        self._stack_party()
        c.tag_raise(self.app.interaction_hint)

    def _stack_party(self):
        """Slot each walker just below the first thing standing in front of it, back to front,
        so a follower beside the leader keeps the order the field code gave it."""
        a, c = self.app, self.app.canvas
        walkers = [(pos[1], item) for item, _, pos in a.field_followers.values()] + [(a.y, a.player_item)]
        for y, item in sorted(walkers, key=lambda walker: walker[0]):
            index = bisect_right(self.keys, y + TILE / 2)
            if index < len(self.layers):
                c.tag_lower(item, self.layers[index][1])
            else:
                c.tag_raise(item, self.last_item)

    def animate(self, now):
        if not self.here() or not self.layers:
            return
        c = self.app.canvas
        frame = int(now / SAIL_SECONDS) % 4
        if self.sails is not None and frame != self.sail_frame:
            self.sail_frame = frame
            c.itemconfigure(self.sails, image=self.sprite(f"windmill-sails-{frame}"))
        for bird in self.birds:
            item, facing, phase, shown = bird
            frame = _frame_at((now * 1000 + phase) % sum(BIRD_MS), BIRD_MS)
            if frame != shown:
                bird[3] = frame
                c.itemconfigure(item, image=self.sprite(f"sheepbird-{facing}-{frame}"))
        for lamp in self.lamps:
            item, phase, shown = lamp
            frame = _frame_at((now * 1000 + phase) % sum(LAMP_MS), LAMP_MS)
            if frame != shown:
                lamp[2] = frame
                c.itemconfigure(item, image=self.sprite(f"lamp-{frame}"))
        for motion in self.motions:
            item, prefix, times, phase, shown = motion
            frame = _frame_at((now * 1000 + phase) % sum(times), times)
            if frame != shown:
                motion[4] = frame
                c.itemconfigure(item, image=self.sprite(f"{prefix}{frame}"))


def _frame_at(t, durations):
    """Which frame of a loop with these durations (ms) is showing t ms into it."""
    frame = 0
    while t >= durations[frame]:
        t -= durations[frame]
        frame += 1
    return frame
