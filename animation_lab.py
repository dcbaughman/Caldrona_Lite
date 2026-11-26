"""Title-screen previews for battle animations."""
from dataclasses import replace
from math import ceil, pi, sin
from pathlib import Path
import tkinter as tk
from types import SimpleNamespace

from arrow_fx import TAG as BOW_SHOT_TAG, draw_shot
from battle import (BattleModel, BattleScene, DEN_MOTHER, EMBER_WYVERN, EMBERWRAITH, ENEMIES, ENEMY_ROSTER,
                    SILK_SARCOPHAGUS, SPIDERLING, _center_y_on_ground)
from brood_fx import BROOD_DURATION, BroodSilk, brood_shade
from classes import OUTFIT_JOBS
from crescendo import LOADOUTS, MAX_CHARGE, UNLOCKS
from ember_wyvern_fx import PHASE_NAMES as WYVERN_PHASE_NAMES, TRANSITION_SECONDS, EmberWyvernArt
from enemy_motion import (MOTIONS as ENEMY_MOTIONS, enemy_pose_frame, idle_duration, idle_offset,
                          load_brood_shades, load_enemy_frames)
from quarry_floor import QuarryFloor
from player_motion import MOTIONS, PlayerMotionArt, STYLES
from shalehorn_fx import ShalehornEffects
from stats import RETRI, TEMUR, member
from statuses import StatusBook


class QuarryPreview:
    """Build preview frames from the unmodified battle backdrop and sprites."""

    BOSS = (270, 190)
    PARTY = ((738, 255), (774, 189))
    FPS = QuarryFloor.FPS

    def __init__(self, master, assets: Path):
        self.master = master
        self.backdrop = tk.PhotoImage(master=master, file=str(assets / "crystal-glow-0.png"))
        self.boss = tk.PhotoImage(master=master, file=str(assets / "shalehorn.png")).zoom(2)
        self.party = tuple(tk.PhotoImage(master=master, file=str(assets / f"{name}-v2.png")).zoom(2)
                           for name in ("retri", "temur"))
        ground = self.BOSS[1] + self.boss.height() // 2 - 5
        self.floor = QuarryFloor(self.backdrop, (self.BOSS[0], ground))
        self.frames = {}

    @staticmethod
    def _copy(target, art, x, y, visible=None):
        target.tk.call(target, "copy", art, "-from", 0, 0, art.width(),
                       art.height() if visible is None else visible, "-to",
                       round(x - art.width() / 2), round(y - art.height() / 2))

    def frame(self, move, index):
        key = (move, index)
        if key in self.frames:
            return self.frames[key]
        t = index / self.FPS
        image = tk.PhotoImage(master=self.master, width=self.floor.width, height=self.floor.height)
        x, y = self.BOSS
        if move == "burrow":
            step = min(8, int(max(0, (t - .24) / .72) * 8))
            x += sin(t * 45) * 3
            y += self.boss.height() * step / 8
        else:
            step = 0
            if t < .3:
                y -= sin(t / .3 * pi) * 22
        self.floor.paint(image, move, index)
        if step < 8:
            self._copy(image, self.boss, x, y, round(self.boss.height() * (8 - step) / 8))
        for (px, py), art in zip(self.PARTY, self.party):
            y_shift = self.floor.actor_shift(px, py + art.height() // 2, t) if move == "tremor" else 0
            self._copy(image, art, px, py + y_shift)
        self.frames[key] = image
        return image



class FramePlayer:
    FPS = 30
    LOOP_HOLD = 24

    def _begin_playback(self, now, frame=0, paused=False):
        self.started = now - frame / self.FPS
        self.paused = paused
        self.rendered = None
        self._draw(frame)

    def replay(self, now):
        self._begin_playback(now)

    def step(self, amount):
        self.paused = True
        self._draw(max(0, min(self.last_frame, self.rendered + amount)))

    def update(self, now):
        if not self.paused:
            time_frame = int(max(0, now - self.started) * self.FPS)
            self._draw(min(self.last_frame, time_frame % (self.last_frame + self.LOOP_HOLD)))


class EnemyMoveLab(FramePlayer):
    MOVES = (EMBERWRAITH, SILK_SARCOPHAGUS,
             *(foe for foe in ENEMY_ROSTER if foe not in (EMBERWRAITH, SILK_SARCOPHAGUS)))
    LOOP_HOLD = 1
    TAG = "enemy_move_lab"
    GROUND = 381
    BROOD_PREVIEW_AT = 1.2
    WYVERN_RISE_AT = 1.55
    WYVERN_HEAT_AT = 4.10
    WYVERN_DURATION = 7.20

    def __init__(self, canvas, assets):
        self.canvas = canvas
        self.assets = assets / "battle"
        self.index = 0
        self.images = {}
        self.brood_shades = None
        self.brood_silk = BroodSilk(canvas)
        self.wyvern_art = None

    @property
    def foe(self):
        return self.MOVES[self.index]

    @property
    def last_frame(self):
        if self.foe is DEN_MOTHER:
            return ceil((self.BROOD_PREVIEW_AT + BROOD_DURATION + .65) * self.FPS) - 1
        if self.foe is EMBER_WYVERN:
            return ceil(self.WYVERN_DURATION * self.FPS) - 1
        return ceil(idle_duration(self.foe) * self.FPS) - 1

    def mount(self, now, font, ink, muted):
        c, foe = self.canvas, self.foe
        c.delete(self.TAG)
        self.brood_silk.clear()
        c.create_text(480, 114, text=foe.name.upper(), fill=ink, font=font(28, True), tags=self.TAG)
        c.create_rectangle(222, 148, 738, 406, fill="#202b3c", outline="#65748b", width=2, tags=self.TAG)
        if foe is EMBER_WYVERN:
            self.wyvern_floor = c.create_rectangle(223, self.GROUND, 737, 405, fill="#3c2529",
                                                   outline="", state="hidden", tags=self.TAG)
        c.create_line(270, self.GROUND, 690, self.GROUND, fill="#526177", width=2, tags=self.TAG)
        if foe.sprite not in self.images:
            preview_foe = replace(foe, sprite_scale=(3, 2)) if foe is EMBER_WYVERN else foe
            frames = load_enemy_frames(c, self.assets, preview_foe)
            sprite = frames[0]
            zoom = max(1, min(3, 190 // sprite.height(), 310 // sprite.width()))
            self.images[foe.sprite] = tuple(frame.zoom(zoom) for frame in frames) if zoom > 1 else frames, zoom
        self.frames, self.zoom = self.images[foe.sprite]
        sprite = self.frames[0]
        if foe is EMBER_WYVERN:
            if self.wyvern_art is None:
                self.wyvern_art = EmberWyvernArt(c, self.assets, sprite, scale=(3, 2))
            sprite = self.wyvern_art.pose(1)
        self.base_y = _center_y_on_ground(sprite, self.GROUND - foe.sprite_lift * self.zoom)
        self.sprite_item = c.create_image(480, self.base_y, image=sprite, tags=self.TAG)
        if foe is DEN_MOTHER:
            if self.brood_shades is None:
                self.brood_shades = load_brood_shades(c, self.assets, foe)
                self.spiderling = load_enemy_frames(c, self.assets, SPIDERLING)[0]
            self.broodlings = [(c.create_image(*point, image=self.spiderling, tags=self.TAG), self.spiderling, point)
                               for point in ((339, 350), (630, 350))]
        self.frame_item = c.create_text(480, 448, fill=muted, font=font(17), tags=self.TAG)
        self.move_label = c.create_text(480, 425, text=f"{ENEMY_MOTIONS[foe.sprite].label}  ·  {self.index+1}/{len(self.MOVES)}",
                                        fill=ink, font=font(19), tags=self.TAG)
        self._begin_playback(now)

    def _draw(self, frame):
        if frame == self.rendered:
            return
        elapsed = frame / self.FPS
        dx, dy = idle_offset(self.foe, elapsed)
        self.canvas.itemconfigure(self.frame_item, text=f"Frame {frame+1:02d} / {self.last_frame+1:02d}")
        self.rendered = frame
        if self.foe is EMBER_WYVERN:
            self._draw_wyvern(elapsed, dx * self.zoom, dy * self.zoom)
            return
        x, y = 480 + dx * self.zoom, self.base_y + dy * self.zoom
        self.canvas.coords(self.sprite_item, x, y)
        index = enemy_pose_frame(self.foe, elapsed)
        sprite = self.frames[index]
        if self.foe is DEN_MOTHER:
            age = elapsed - self.BROOD_PREVIEW_AT
            shade = brood_shade(age)
            if shade:
                sprite = self.brood_shades[shade - 1][index]
            mouth = (x + sprite.width() * .06, y + sprite.height() * .18)
            self.brood_silk.draw(age, self.sprite_item, mouth, self.broodlings)
        self.canvas.itemconfigure(self.sprite_item, image=sprite)

    def _draw_wyvern(self, elapsed, dx, dy):
        if elapsed >= self.WYVERN_HEAT_AT:
            stage, age = 3, elapsed - self.WYVERN_HEAT_AT
        elif elapsed >= self.WYVERN_RISE_AT:
            stage, age = 2, elapsed - self.WYVERN_RISE_AT
        else:
            stage, age = 1, 0
        c = self.canvas
        tag = self.TAG, "lab_wyvern_fx"
        c.delete("lab_wyvern_fx")
        c.itemconfigure(self.wyvern_floor, state="normal" if stage == 3 and age >= .36 else "hidden")
        sprite = self.wyvern_art.pose(stage, age)
        x = 480 + dx
        c.itemconfigure(self.sprite_item, image=sprite)
        c.coords(self.sprite_item, x, self.GROUND - sprite.height() // 2 + dy)
        if stage == 1 or (stage == 2 and age < .24):
            self.wyvern_art.rubble(480, self.GROUND, tag)
        if stage > 1 and age < TRANSITION_SECONDS[stage]:
            self.wyvern_art.transition_effect(stage, age, x, self.GROUND, tag)
        c.itemconfigure(self.move_label, text=f"{WYVERN_PHASE_NAMES[stage-1]}  ·  {self.index+1}/{len(self.MOVES)}")


class AnimationLab(FramePlayer):
    """Replay the current animation and its optional floor preview in the same viewport."""

    MOVES = ("burrow", "tremor", "headbutt", "charge", "eruption")
    TAG = "animation_lab"
    ORIGINAL = "animation_lab_original"
    TOP = 130
    FPS = QuarryPreview.FPS
    LOOP_HOLD = 20

    def __init__(self, canvas, assets):
        self.canvas = canvas
        self.preview = QuarryPreview(canvas, assets)
        self.legacy = ShalehornEffects(canvas, legacy_floor=True)
        self.live = ShalehornEffects(canvas)
        self.index = 0
        self.original = False

    @property
    def move(self):
        return self.MOVES[self.index]

    @property
    def has_preview(self):
        return self.move in ("burrow", "tremor", "charge")

    @property
    def last_frame(self):
        return ceil(self.legacy.DURATIONS[self.move] * self.preview.FPS)

    def mount(self, now, font, ink, muted, frame=0, paused=False):
        c, art = self.canvas, self.preview
        c.delete(self.TAG)
        self.legacy.clear()
        self.live.clear()
        tag = (self.TAG, self.ORIGINAL)
        backdrop = c.create_image(0, 0, image=art.backdrop, anchor="nw", tags=tag)
        boss = c.create_image(*art.BOSS, image=art.boss, tags=tag)
        party = [c.create_image(*point, image=image, tags=tag) for point, image in zip(art.PARTY, art.party)]
        self.scene = SimpleNamespace(
            TAG=self.ORIGINAL, model=SimpleNamespace(enemies=(SimpleNamespace(sprite="shalehorn"),),
                                                     statuses=StatusBook(), buried=self.move == "burrow",
                                                     defender=0),
            enemies={"shalehorn": art.boss}, enemy_items=[boss], backdrop_item=backdrop,
            enemy_positions=(art.BOSS,), party_items=party, _party_position=art.PARTY.__getitem__,
            glow_frames=(art.backdrop,), glow_index=0, party_sprites=art.party,
        )
        self.field = c.create_image(0, self.TOP, anchor="nw", tags=self.TAG)
        self.title = c.create_text(480, 109, fill=ink, font=font(22, True), tags=self.TAG)
        self.counter = c.create_text(480, 467, fill=muted, font=font(17), tags=self.TAG)
        self._begin_playback(now, frame, paused)

    def _draw(self, frame):
        if frame == self.rendered:
            return
        c = self.canvas
        use_preview = self.move in ("burrow", "tremor") and not self.original
        play_attack = self.move == "headbutt" or (self.move == "charge" and not self.original)
        effects = self.live if play_attack else self.legacy
        label = "Floor effect" if use_preview else "New motion" if play_attack else "Original"
        c.itemconfigure(self.title, text=f"Shalehorn · {self.move.title()} · {label}")
        c.itemconfigure(self.counter, text=f"Frame {frame + 1:02} / {self.last_frame + 1:02}")
        if use_preview:
            c.itemconfigure(self.ORIGINAL, state="hidden")
            c.itemconfigure(self.field, state="normal", image=self.preview.frame(self.move, frame))
        else:
            c.itemconfigure(self.field, state="hidden")
            c.itemconfigure(self.ORIGINAL, state="normal")
            if self.rendered is None or frame < self.rendered:
                effects.clear()
                for item, point in zip((self.scene.backdrop_item, *self.scene.enemy_items, *self.scene.party_items),
                                       ((0, 0), self.preview.BOSS, *self.preview.PARTY)):
                    c.coords(item, *point)
                effects.start(self.scene, 0, self.move)
            else:
                c.move(self.ORIGINAL, 0, -self.TOP)
            effects.draw(self.scene, frame / self.preview.FPS)
            if frame == self.last_frame:
                effects.finish(self.scene)
            c.move(self.ORIGINAL, 0, self.TOP)
            c.tag_lower(self.ORIGINAL, self.field)
        self.rendered = frame


class CrescendoLab(FramePlayer):
    """Play the battle effects on a disposable party and encounter."""

    MOVES = tuple((job, move) for job, moves in LOADOUTS.items() for move in moves)
    TOP = AnimationLab.TOP

    def __init__(self, canvas, font, assets):
        self.canvas = canvas
        self.scene = BattleScene(canvas, font, assets)
        self.index = 0

    @property
    def last_frame(self):
        return ceil(self.scene.ability_duration_ms * self.FPS / 1000)

    def mount(self, now, font, ink, muted):
        job, move = self.MOVES[self.index]
        c = self.canvas
        self.title = c.create_text(480, 109, text=f"{job} · {move.name}   {self.index + 1}/{len(self.MOVES)}",
                                   fill=ink, font=font(22, True))
        self.counter = c.create_text(480, 467, fill=muted, font=font(17))

        hero, ally = member("Retri", RETRI), member("Temur", TEMUR)
        hero.update(job=job, crescendo_charge=MAX_CHARGE, crescendo_choice=move.id, hp=24, mp=0)
        # The lab previews every Crescendo, so it opens all four unlock tiers.
        hero.update(crescendo_progress=10**6, researched=[UNLOCKS[job][2]] if job in UNLOCKS else [])
        ally.update(hp=0 if move.effect == "revive" else 26, mp=0)
        targets = ENEMIES[:2] if move.target == "all enemies" else ENEMIES[:1]
        model = BattleModel([replace(enemy, hp=100) for enemy in targets], party=[hero, ally])

        scene = self.scene
        scene.crescendo_fx.clear(scene)
        scene.model = model
        scene._camera_offset = (0, 0)
        scene._draw_battlefield(now)
        if not scene._cast_ability(move, 0):
            raise RuntimeError(f"Could not preview {move.name}: {model.message}")
        c.move(scene.TAG, 0, self.TOP)
        self.replay(now)

    def _draw(self, frame):
        if frame == self.rendered:
            return
        c, scene = self.canvas, self.scene
        c.move(scene.TAG, 0, -self.TOP)
        scene._draw_ability_frame(frame * 1000 / self.FPS)
        c.move(scene.TAG, 0, self.TOP)
        c.tag_lower(scene.TAG, self.title)
        c.itemconfigure(self.counter, text=f"Frame {frame + 1:02} / {self.last_frame + 1:02}")
        self.rendered = frame


class PlayerMoveLab(FramePlayer):
    """Show both fighters' key poses at the same scale and on the same baseline."""

    MOVES = STYLES
    OUTFITS = ("Unbound", *OUTFIT_JOBS)
    LABELS = {"sword": "Standard Sword", "greatsword": "Greatsword",
              "pike": "Pike", "halberd": "Halberd", "bow": "Bow", "whip": "Whip",
              "dagger": "Dagger", "mace": "Blunt Weapon",
              "staff": "Staff Swing", "rod": "Rod Strike", "throw": "Thrown Knife",
              "fists": "Bare Fists", "cast_hand": "Free-Hand Cast", "cast_wand": "Wand Cast",
              "cast_staff": "Staff Cast", "cast_orb": "Focus Cast", "critical": "Critical HP"}
    BOW_TARGETS = ((204, 246), (551, 204))

    def __init__(self, canvas, assets):
        self.canvas = canvas
        self.assets = assets / "battle"
        self.art = PlayerMotionArt(canvas, assets)
        self.index = self.outfit = 0
        self.images = {}

    @property
    def last_frame(self):
        move = MOTIONS.get(self.MOVES[self.index])
        return ceil((move.windup_ms + move.release_duration_ms) * self.FPS / 1000) if move else 0

    def mount(self, now, font, ink, muted):
        self.job = self.OUTFITS[self.outfit]
        self.style = self.MOVES[self.index]
        c = self.canvas
        c.create_text(480, 109, text=f"{self.LABELS[self.style]} · {self.job}",
                      fill=ink, font=font(24, True))
        c.create_rectangle(126, 143, 834, 411, fill="#202839", outline="#55627a", width=2)
        c.create_line(185, 334, 775, 334, fill="#526478", width=2)
        if self.style == "bow":
            xs = (387, 742)
        else:
            xs = (362, 625) if self.style in ("pike", "whip") else (335, 625)
        self.centers = [(x, 262) for x in xs]
        if self.style == "bow":
            for target in self.BOW_TARGETS:
                self._bow_target(*target)
        self.actors = [(name, c.create_image(*center))
                       for name, center in zip(("Retri", "Temur"), self.centers)]
        for (name, _), x in zip(self.actors, xs):
            c.create_text(x, 374, text=name.upper(), fill=ink, font=font(20, True))
        self.counter = c.create_text(480, 446, fill=muted, font=font(17))
        self.replay(now)

    def _bow_target(self, x, y):
        c = self.canvas
        c.create_polygon(x-3, y+13, x+3, y+13, x+3, 329, x+15, 329,
                         x+15, 334, x-15, 334, x-15, 329, x-3, 329,
                         fill="#55473e", outline="#1b1d2b", width=2)
        for size, shade in ((19, "#594b43"), (14, "#b58d65"), (9, "#625960"), (4, "#eac985")):
            corner = round(size * .59)
            c.create_polygon(x-corner, y-size, x+corner, y-size, x+size, y-corner,
                             x+size, y+corner, x+corner, y+size, x-corner, y+size,
                             x-size, y+corner, x-size, y-corner, fill=shade, outline="#232837")

    def _draw(self, frame):
        if frame == self.rendered:
            return
        move = MOTIONS.get(self.style)
        elapsed_ms = frame * 1000 / self.FPS
        column = move.column(elapsed_ms, move.windup_ms) if move else 0
        for name, item in self.actors:
            key = name, self.job, self.style if column is not None else "standing", column
            if key not in self.images:
                if column is not None:
                    source = self.art.frame({"name": name, "job": self.job}, self.style, column)
                    image = source.zoom(3)
                else:
                    path = (self.assets / f"{name.lower()}-v2.png" if self.job == "Unbound" else
                            self.assets / "classes" / f"{name.lower()}-{self.job.lower()}.png")
                    image = tk.PhotoImage(master=self.canvas, file=str(path)).zoom(6)
                self.images[key] = image
            self.canvas.itemconfigure(item, image=self.images[key])
        if self.style == "bow":
            self.canvas.delete(BOW_SHOT_TAG)
            for center, target in zip(self.centers, self.BOW_TARGETS):
                draw_shot(self.canvas, center, target, elapsed_ms - move.windup_ms, scale=6, tags=())
        label = f"Frame {frame + 1:02} / {self.last_frame + 1:02}" if move else "25% HP OR LOWER"
        self.canvas.itemconfigure(self.counter, text=label)
        self.rendered = frame
