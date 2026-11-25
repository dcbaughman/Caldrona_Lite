"""Shalehorn's body animation and effects on the battle floor."""
import math
import tkinter as tk

from quarry_floor import QuarryFloor
from shalehorn_attack import CHARGE_DURATION, CONTACT, HEADBUTT_DURATION, ShalehornAttack


class ShalehornEffects:
    FX = "shalehorn_motion"
    HOLE = "shalehorn_hole"
    DURATIONS = {"charge": CHARGE_DURATION, "headbutt": HEADBUTT_DURATION,
                 "tremor": .95, "burrow": 1.05, "eruption": 1.05}

    def __init__(self, canvas, *, legacy_floor=False):
        self.canvas = canvas
        self.legacy_floor = legacy_floor
        self.floor = None
        self.floor_image = None
        self.attack = ShalehornAttack(canvas)
        self.crops = {}
        self.clear()

    def clear(self):
        self.canvas.delete(self.FX)
        self.canvas.delete(self.HOLE)
        self.active = None
        self.hole = False
        self.charge_focus = False
        self.floor_pose = None
        self.rendered_floor = None

    def start(self, scene, now, move):
        self.active, self.started = move, now
        if move == "eruption":
            self._open_hole(scene)

    @property
    def duration(self):
        return self.DURATIONS.get(self.active, .65)

    @property
    def hit_delay(self):
        return CONTACT if self.active == "charge" and not self.legacy_floor else 0

    def _source(self, scene):
        source = scene.enemies[scene.model.enemies[0].sprite]
        if scene.model.statuses.has(("enemy", 0), "darkness"):
            return scene.darkness_silence_fx._black(source)
        return source

    def _crop(self, source, step):
        key = (str(source), step)
        if key not in self.crops:
            w, h = source.width(), source.height()
            image = tk.PhotoImage(master=self.canvas, width=w, height=h)
            visible = max(1, round(h * (8 - step) / 8))
            image.tk.call(image, "copy", source, "-from", 0, 0, w, visible, "-to", 0, 0)
            self.crops[key] = image
        return self.crops[key]

    def update_backdrop(self, scene):
        """Keep the glow cycle and the pixel effect on the same canvas item."""
        backdrop = scene.glow_frames[scene.glow_index]
        if self.charge_focus:
            self.canvas.itemconfigure(scene.backdrop_item, image=self.attack.muted_room(scene.glow_frames[0]))
            return
        if self.floor_pose is None:
            self.canvas.itemconfigure(scene.backdrop_item, image=backdrop)
            self.rendered_floor = None
            return
        key = (str(backdrop), self.floor_pose)
        if key == self.rendered_floor:
            return
        if self.floor is None:
            x, y = scene.enemy_positions[0]
            ground = int(y + self._source(scene).height() // 2 - 5)
            self.floor = QuarryFloor(backdrop, (int(x), ground))
            self.floor_image = tk.PhotoImage(master=self.canvas, width=self.floor.width, height=self.floor.height)
        self.floor.select_backdrop(backdrop)
        self.floor.paint(self.floor_image, *self.floor_pose)
        refresh = getattr(self.canvas, "refresh_image", None)
        if refresh is not None:
            refresh(self.floor_image)
        self.canvas.itemconfigure(scene.backdrop_item, image=self.floor_image)
        self.rendered_floor = key

    def _open_hole(self, scene):
        if self.legacy_floor:
            self._original_hole(scene)
        else:
            self.hole = True
            self.floor_pose = ("burrow", QuarryFloor.SETTLED)
            self.update_backdrop(scene)

    def _original_hole(self, scene):
        if self.hole:
            return
        c = self.canvas
        x, y = scene.enemy_positions[0]
        ground = y + self._source(scene).height() / 2 - 5
        tags = (scene.TAG, self.HOLE)
        c.create_oval(x-72, ground-12, x+72, ground+12, fill="#5f574c", outline="#8c7c61", width=2, tags=tags)
        c.create_oval(x-62, ground-8, x+62, ground+7, fill="#080c13", outline="#353732", tags=tags)
        for j in range(9):
            dx, dy = -68 + j * 17, (j % 3) * 3
            c.create_rectangle(x+dx-3, ground+dy-3, x+dx+4, ground+dy+2,
                               fill=("#7a7163", "#484943", "#a28b6c")[j % 3], outline="", tags=tags)
        c.tag_lower(self.HOLE, scene.enemy_items[0])
        self.hole = True

    def _original_tremor(self, scene, x, ground, t):
        if t < .28:
            return 0
        tags = (scene.TAG, self.FX)
        for j, color in enumerate(("#ad9871", "#736d60", "#4b4b48")):
            radius = max(0, (t - .28 - j * .09) * 360)
            if radius > 0:
                self.canvas.create_oval(x-radius, ground-radius*.13, x+radius, ground+radius*.13,
                                        outline=color, width=2, tags=tags)
        for j in range(7):
            px = x - 50 + j * 75
            self.canvas.create_line(px, ground, px+12, ground-8, px+22, ground+2, px+39, ground-9,
                                    fill="#b1a084", width=2, tags=tags)
        decay = max(0, 1 - (t - .28) / .67)
        return round(math.sin(t * 100) * 7 * decay)

    def draw(self, scene, now):
        move = self.active
        if move is None:
            return
        c = self.canvas
        t = max(0, now - self.started)
        c.delete(self.FX)
        item = scene.enemy_items[0]
        x, y = scene.enemy_positions[0]
        source = self._source(scene)
        h = source.height()
        ground = y + h / 2 - 5
        shake = 0
        if move == "headbutt" or (move == "charge" and not self.legacy_floor):
            focus = move == "charge" and .10 <= t < 1.14
            if focus != self.charge_focus:
                self.charge_focus = focus
                self.update_backdrop(scene)
            self.attack.draw(scene, source, t, move == "charge", (scene.TAG, self.FX))
        elif move == "charge":
            progress = min(1, t / .9)
            lunge = math.sin(math.pi * progress) * 150
            c.coords(item, x+lunge, y-abs(math.sin(progress * math.pi * 3)) * 6)
            c.itemconfigure(item, image=source, state="normal")
        elif move == "tremor":
            hop = -math.sin(t / .3 * math.pi) * 22 if t < .3 else 0
            c.coords(item, x, y+hop)
            c.itemconfigure(item, image=source, state="normal")
            if self.legacy_floor:
                shake = self._original_tremor(scene, x, ground, t)
            elif .29 < t < self.duration:
                self.floor_pose = (move, int(t * QuarryFloor.FPS))
                self.update_backdrop(scene)
        elif move == "burrow":
            if self.legacy_floor:
                self._original_hole(scene)
            elif t > .17:
                self.hole = True
                self.floor_pose = (move, min(QuarryFloor.SETTLED, int(t * QuarryFloor.FPS)))
                self.update_backdrop(scene)
            step = min(8, int(max(0, (t - .24) / .72) * 8))
            c.coords(item, x+math.sin(t * 45) * 3, y+h*step/8)
            c.itemconfigure(item, image=self._crop(source, step), state="hidden" if step >= 8 else "normal")
        else:
            emerged = max(0, min(1, (t - .12) / .55))
            step = max(0, 8 - int(emerged * 8))
            c.coords(item, x, y+h*step/8)
            c.itemconfigure(item, image=self._crop(source, step), state="hidden" if step >= 8 else "normal")
            if .4 < t < .95:
                shake = round(math.sin(t * 90) * 6 * (1 - t))

        if move == "eruption" or (self.legacy_floor and (move == "burrow" or (move == "charge" and t < .9))):
            for j in range(12):
                flight = (t * 2 + j * .071) % 1
                direction = -1 if j % 2 else 1
                px = x + direction * (15 + flight * 70)
                py = ground - math.sin(flight * math.pi) * (18 + j % 4 * 6)
                c.create_rectangle(px-3, py-3, px+3, py+3, fill=("#a18e73", "#71685d", "#42474a")[j % 3],
                                   outline="", tags=(scene.TAG, self.FX))

        c.coords(scene.backdrop_item, shake, 0)
        for i, member_item in enumerate(scene.party_items):
            px, py = scene._party_position(i)
            if shake:
                py += 2 if i % 2 else -2
            elif move == "tremor" and not self.legacy_floor and self.floor_pose is not None:
                sprite = scene.party_sprites[i]
                feet = py + (sprite.height() // 2 if sprite is not None else 0)
                py += self.floor.actor_shift(px, feet, self.floor_pose[1] / QuarryFloor.FPS)
            c.coords(member_item, px+shake, py)
        scene._camera_offset = (shake, 0)
        c.tag_raise("battle_ui")

    def finish(self, scene):
        c = self.canvas
        c.delete(self.FX)
        self.charge_focus = False
        if self.active == "eruption":
            c.delete(self.HOLE)
            self.hole = False
        if not self.legacy_floor:
            if self.active == "burrow":
                self._open_hole(scene)
            else:
                self.floor_pose = None
                self.update_backdrop(scene)
        for i, item in enumerate(scene.party_items):
            c.coords(item, *scene._party_position(i))
        c.coords(scene.backdrop_item, 0, 0)
        scene._camera_offset = (0, 0)
        c.itemconfigure(scene.enemy_items[0], image=self._source(scene),
                        state="hidden" if scene.model.buried else "normal")
        self.active = None
