"""Stage and play the same Crescendo cues in battle and in the title lab."""

from math import cos, sin

from battle_lighting import muted_battlefield
from crescendo_art import Art, CUES, clamp, ease, offset


class CrescendoFX:
    TAG = "crescendo_fx"

    def __init__(self, canvas):
        self.canvas = canvas
        self.move = None
        self.cue = None
        self.gray_frames = {}
        self.backdrop = None

    @property
    def duration_ms(self):
        return self.cue.duration_ms if self.cue else 0

    def cast(self, scene, move):
        model = scene.model
        hp = tuple(member["hp"] for member in model.party)
        mp = tuple(member.get("mp", 0) for member in model.party)
        enemies = tuple(model.health)
        active_enemies = tuple(i for i, health in enumerate(enemies) if health > 0)
        if not model.command("Crescendo", ability_id=move.id):
            return False
        self.move, self.cue = move, CUES[move.id]
        self.starting_hp = hp
        self.starting_mp = mp
        self.starting_enemy_hp = enemies
        self.starting_enemies = active_enemies
        self.impact_shown = False
        self.mp_gains = {i: member.get("mp", 0) - mp[i] for i, member in enumerate(model.party)
                         if member.get("mp", 0) > mp[i]}
        if move.target == "single enemy":
            self.targets = (model.target,)
        elif move.target == "all enemies":
            self.targets = active_enemies
        elif move.effect == "revive":
            self.targets = tuple(model.healed)
        elif move.effect == "self_restore":
            self.targets = (model.actor,)
        else:
            self.targets = tuple(i for i, health in enumerate(hp) if health > 0)
        return True

    def clear(self, scene):
        self.canvas.delete(self.TAG)
        if self.cue and self.backdrop is not None:
            self.canvas.itemconfigure(scene.backdrop_item, image=scene.glow_frames[scene.glow_index])
        self.backdrop = None
        self.move = self.cue = None

    def draw(self, scene, elapsed_ms):
        c, cue = self.canvas, self.cue
        c.delete(self.TAG)
        tags = (scene.TAG, self.TAG)
        windup = clamp(elapsed_ms / cue.contact_ms)
        hit_ms = elapsed_ms - cue.contact_ms
        release = clamp(hit_ms / (cue.duration_ms - cue.contact_ms))
        landed = hit_ms >= 0

        normal = scene.glow_frames[scene.glow_index]
        remaining = cue.duration_ms - elapsed_ms
        gray = elapsed_ms >= 160 and remaining > 170
        backdrop = muted_battlefield(c, scene.glow_frames[0], self.gray_frames) if gray else normal
        if backdrop is not self.backdrop:
            c.itemconfigure(scene.backdrop_item, image=backdrop)
            self.backdrop = backdrop

        recoil = cue.shake * (1-clamp(hit_ms/315)) if landed else 0
        dx = round(sin(hit_ms*.081)*recoil)
        dy = round(cos(hit_ms*.099)*recoil*.48)
        scene._sync_party_sprites(self.starting_hp if not landed else None)
        scene._position_battlefield(dx, dy)
        for i in self.starting_enemies:
            visible = hit_ms < 390 or scene.model.health[i] > 0
            c.itemconfigure(scene.enemy_items[i], state="normal" if visible else "hidden")

        actor = scene.model.actor
        step = cue.lunge * (ease((windup-.68)/.32) * (1-ease(release*2.1)))
        caster = offset(scene._party_position(actor), dx-step, dy)
        if cue.lunge:
            c.coords(scene.party_items[actor], *caster)
        points = scene.enemy_positions if self.move.target != "party" else [
            scene._party_position(i) for i in range(len(scene.model.party))
        ]
        targets = [offset(points[i], dx, dy) for i in self.targets]

        curtain = min(ease(elapsed_ms/175), ease(remaining/235))
        border = round(13 * curtain)
        if border:
            c.create_rectangle(0, 0, 960, border, fill="#0e0e18", outline="", tags=tags)
            c.create_rectangle(0, 321-border, 960, 321, fill="#0e0e18", outline="", tags=tags)
        if 0 <= hit_ms < 70:
            c.create_rectangle(0, border, 960, 321-border, fill=cue.palette[2],
                               outline="", stipple="gray25", tags=tags)

        if release < .91:
            art = Art(c, tags, cue.palette, caster, targets, windup, release, landed)
            cue.draw(art)
        if 105 <= elapsed_ms and release < .62:
            self._title(scene, tags)
        if landed:
            scene._draw_healing(hit_ms / 1000)
            self._impact_numbers(scene, hit_ms, tags)
        else:
            c.delete("battle_healing")
        c.tag_raise("battle_ui")

    def _title(self, scene, tags):
        c = self.canvas
        color, highlight = self.cue.palette[1:3]
        width = max(116, len(self.move.name) * 8)
        left, right = 480-width, 480+width
        c.create_rectangle(left, 20, right, 47, fill="#151420", outline=color, tags=tags)
        c.create_line(left+18, 47, right-18, 47, fill=highlight, tags=tags)
        for x in (left+10, right-10):
            c.create_polygon(x-3, 34, x, 30, x+3, 34, x, 38, fill=highlight, tags=tags)
        c.create_text(480, 33, text=self.move.name.upper(), fill=self.cue.palette[3],
                      font=scene.font(18, True), tags=tags)

    def _impact_numbers(self, scene, hit_ms, tags):
        if hit_ms >= 700:
            return
        dx, dy = scene._camera_offset
        lift = int(hit_ms * .027)
        for i, amount in scene.model.crescendo_hits.items():
            x, y = scene.enemy_positions[i]
            self.canvas.create_text(x+dx, y+dy-64-lift, text=str(amount), fill="#ffe78b",
                                    font=scene.font(28, True), tags=tags)
        for i, gain in self.mp_gains.items():
            x, y = scene._party_position(i)
            self.canvas.create_text(x+dx, y+dy-74-lift, text=f"+{gain} MP", fill="#91e6ff",
                                    font=scene.font(21, True), tags=tags)
