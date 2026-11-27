"""Windehus in the field.

The town's flat layer (grass, paving, walls, stairs and shade) comes baked into one image by
prepare_town_tiles.py, and the world chunks are cut from it. Every house, tree, fence and prop is its own canvas
image, stacked back to front, and the party is slotted in among them by the row it stands on,
so it walks behind a house or in front of it. The mill's sails turn and the sheep-birds in the
hay pen breathe.
"""
from bisect import bisect_right
import json
import tkinter as tk

import windehus

TILE = windehus.TILE
TAG = "windehus_town"
GROUND = "windehus-ground.png"
SAIL_SECONDS = .3              # each frame is a sixteenth turn of the sails
BIRD_MS = (650, 250, 150)      # the sheep-bird idle cycle, as the mount manifest times it
BIRD_PHASE_MS = 370            # so the birds don't breathe together


class TownMap:
    """The town floor in the shape the field code expects of an area."""
    width, height = windehus.WIDTH, windehus.HEIGHT
    spawn = ((windehus.ARRIVAL[0] + .5) * TILE, (windehus.ARRIVAL[1] + .5) * TILE)

    def __init__(self, floor):
        self.floor = floor

    def walkable(self, px, py):
        return (int(px // TILE), int(py // TILE)) in self.floor


class WindehusTown:
    def __init__(self, app, assets, scale):
        self.app, self.scale = app, scale
        self.art = assets / "town"
        self.spots = json.loads((self.art / "tileset.json").read_text(encoding="utf-8"))
        self.sizes = {name: (w, h) for name, (x, y, w, h) in self.spots.items()}
        self.map = TownMap(windehus.floor(self.sizes))
        self.atlas = self.ground = None
        self.sprites = {}
        self.layers = []           # (foot y, lowest canvas item) back to front
        self.keys = []
        self.sails = None
        self.sail_frame = 0
        self.birds = []            # [item, facing, phase ms, frame]
        self.drawn_camera = (0.0, 0.0)

    def here(self):
        return self.app.in_town

    # --- art ---------------------------------------------------------------------------

    def _load(self):
        if self.ground is not None:
            return
        root = self.app.root
        self.atlas = tk.PhotoImage(master=root, file=str(self.art / "tileset.png"))
        self.ground = tk.PhotoImage(master=root, file=str(self.art / GROUND))

    def sprite(self, name):
        if name not in self.sprites:
            x, y, w, h = self.spots[name]
            s = self.scale
            image = tk.PhotoImage(master=self.app.root, width=w * s, height=h * s)
            image.tk.call(image, "copy", self.atlas, "-from", x, y, x + w, y + h, "-zoom", s)
            self.sprites[name] = image
        return self.sprites[name]

    def chunk(self, key, tiles):
        """One world chunk of the flat layer, at screen scale."""
        size, s = tiles * TILE, self.scale
        photo = tk.PhotoImage(master=self.app.root, width=size * s, height=size * s)
        x0, y0 = key[0] * size, key[1] * size
        x1, y1 = min(x0 + size, self.ground.width()), min(y0 + size, self.ground.height())
        if x1 > x0 and y1 > y0:
            photo.tk.call(photo, "copy", self.ground, "-from", x0, y0, x1, y1, "-zoom", s)
        return photo

    def _place_things(self):
        c, s = self.app.canvas, self.scale
        c.delete(TAG)
        self.layers.clear()
        self.birds.clear()
        self.sails = None
        for index, (key, _, steps) in enumerate(windehus.things(self.sizes)):
            first = None
            for name, px, py in steps:
                item = c.create_image(px * s, py * s, image=self.sprite(name), anchor="nw", tags=(TAG,))
                first = first or item
                if name == windehus.MILL_SAILS:
                    self.sails = item
                elif name.startswith("sheepbird-"):
                    facing = name.split("-")[1]
                    for frame in range(len(BIRD_MS)):
                        self.sprite(f"sheepbird-{facing}-{frame}")
                    self.birds.append([item, facing, len(self.birds) * BIRD_PHASE_MS, int(name[-1])])
            self.layers.append((key, first))
        self.keys = [key for key, _ in self.layers]
        self.last_item = c.find_withtag(TAG)[-1]
        # The town stands below the party and everything drawn over the field.
        c.tag_lower(TAG, self.app.player_item)
        self.drawn_camera = (0.0, 0.0)

    # --- coming and going --------------------------------------------------------------

    def enter(self):
        """Arrive on the road from Sunrest."""
        a = self.app
        self._load()
        a.in_town = True
        a.outdoors, a.in_chamber = True, False
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
        a.canvas.delete(TAG)
        self.layers.clear()
        self.birds.clear()
        self.sails = None
        a.cave = a.grassland_map
        a.x, a.y = (tile[0] + .5) * TILE, (tile[1] + .5) * TILE
        a.direction = "down"
        self._arrive()
        a._update_world(force=True)
        a._start_area_music()

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
        cycle = sum(BIRD_MS)
        for bird in self.birds:
            item, facing, phase, shown = bird
            t, frame = (now * 1000 + phase) % cycle, 0
            while t >= BIRD_MS[frame]:
                t -= BIRD_MS[frame]
                frame += 1
            if frame != shown:
                bird[3] = frame
                c.itemconfigure(item, image=self.sprite(f"sheepbird-{facing}-{frame}"))
