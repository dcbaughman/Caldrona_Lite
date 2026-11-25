"""The playable trail errand before Retri enters the excavation."""
import math
import time
import tkinter as tk

from consumables import item_gain_text
from dialogue import DialogueLine
from grassland import ENTRANCE, ROAD, GrasslandInstance
from party_walk import DIRECTIONS, facing
from trail_lantern import frame_paths, load_manifest, timeline_for


class OpeningTrail:
    LAMPS = ((33, 9), (33, 3))
    BRANTO = (31, 11)
    TEMUR = (32, 6)
    TILE = 48
    STEP = .14
    LAMP_ZOOM = 2         # 16x16 lantern art shown at 32px, nearest-neighbor
    LAMP_FOOT = 21        # canvas pixels below the lamp point where the old post ended

    def __init__(self, app, assets, music, rumble):
        self.app, self.assets, self.music, self.rumble = app, assets, music, rumble
        self.canvas = c = app.canvas
        app.screen = "opening_trail"
        app.root.title("Caldrona Lite · Mountain Trail")
        app.keys.clear()
        c.delete("all")
        self.map = GrasslandInstance()
        self.position, self.direction = (32, 11), "left"
        self.next_step = 0
        self.step = 0
        self.lit = set()
        self.branto_near = True
        self.branto_gifted = False
        self.turnback_held = False
        app.supplies = {}
        self.temur = self.TEMUR
        self.met = False
        self.depart_at = None
        self.rumble_at = None
        self.finished = False
        self.music_gain = 0.0
        self.rubble = []
        self.shake = 0

        def tile(name):
            return tk.PhotoImage(master=c, file=str(assets / "grassland" / f"{name}.png")).zoom(3)

        grass = [tile(f"meadow{i}") for i in range(6)]
        road = [tile(f"road{i}") for i in range(2)]
        cliff = tile("cliff0")
        self.images = [*grass, *road, cliff]
        for y in range(2, 13):
            for x in range(22, 42):
                variant = x * 19 + y * 13
                image = cliff if y == 2 else road[variant % 2] if (x, y) in ROAD else grass[variant % 6]
                c.create_image(*self.point((x, y)), image=image)
        cave_x, cave_y = self.point(ENTRANCE)
        self.mouth = c.create_polygon(cave_x-21,cave_y+22,cave_x-20,cave_y-4,cave_x-12,cave_y-16,
                                      cave_x+11,cave_y-16,cave_x+19,cave_y-7,cave_x+21,cave_y+22,
                                      fill="#141321", outline="#524755", width=2)

        self.load_lanterns(assets / "trail-lanterns")
        self.lamp_glow = {}
        for point in self.LAMPS:
            x, y = self.point(point)
            z = self.LAMP_ZOOM
            self.lamp_glow[point] = c.create_image(x-16*z, y+self.LAMP_FOOT-16*z-8*z, anchor="nw", state="hidden")

        self.hero_frames = app._load_player()
        self.temur_frames = app._load_player("Temur")
        self.branto_frames = app._load_player("Branto")
        app.dialogue.register_portrait("Branto", assets / "portraits" / "branto-v2.png")
        self.branto_item = c.create_image(*self.point(self.BRANTO), image=self.branto_frames["right"][1])
        self.temur_item = c.create_image(*self.point(self.temur), image=self.temur_frames["down"][1])
        self.hero_item = c.create_image(*self.point(self.position), image=self.hero_frames["left"][1])
        self.lamp_item, self.lamp_shown, self.lamp_lit_at = {}, {}, {}
        for point in self.LAMPS:
            x, y = self.point(point)
            self.lamp_item[point] = c.create_image(x, y+self.LAMP_FOOT, anchor="s", image=self.lamp_unlit)
        c.create_rectangle(14,12,405,48,fill="#201a25",outline="#78624b")
        self.objective = c.create_text(25,30,anchor="w",text="Light the trail lamps  0/2",
                                       fill="#f3d994",font=app._font(18,True))
        self.prompt = c.create_text(26,516,anchor="w",fill="#fff0d6",font=app._font(16))
        self.startle = c.create_text(0,0,text="!",fill="#fff1ad",font=app._font(23,True),state="hidden")
        app._play_music(music)
        self.dialogue([
            DialogueLine("Branto", "Retri. Here, take the lamp oil. Ena's still up on the ridge."),
            DialogueLine("Branto", "Light the cave lamp last. Once it's dark, that's how she finds the trail home."),
            DialogueLine("Retri", "I'll see to it. You get some rest."),
        ])

    def load_lanterns(self, folder):
        """Load Decorum's lantern frames; the zoom is nearest-neighbor so pixels stay crisp."""
        manifest = load_manifest(folder)
        unlit, light_sprites, light_glows, loop_sprites, loop_glows = frame_paths(manifest)
        load = lambda path: tk.PhotoImage(master=self.canvas, file=str(folder / path)).zoom(self.LAMP_ZOOM)
        self.lamp_unlit = load(unlit)
        self.lamp_frames = {
            "light": [(load(s), load(g)) for s, g in zip(light_sprites, light_glows)],
            "lit": [(load(s), load(g)) for s, g in zip(loop_sprites, loop_glows)]}
        self.lamp_timelines = [timeline_for(manifest, i) for i in range(len(self.LAMPS))]

    def animate_lamps(self, now):
        """Show each lamp's current frame; only touches the canvas when the frame changes."""
        c = self.canvas
        for index, point in enumerate(self.LAMPS):
            lit_at = self.lamp_lit_at.get(point)
            key = ("unlit", 0) if lit_at is None else \
                self.lamp_timelines[index].frame((now-lit_at)*1000)
            if self.lamp_shown.get(point) == key:
                continue
            self.lamp_shown[point] = key
            if key[0] == "unlit":
                continue
            sprite, glow = self.lamp_frames[key[0]][key[1]]
            c.itemconfigure(self.lamp_item[point], image=sprite)
            c.itemconfigure(self.lamp_glow[point], image=glow, state="normal")

    def point(self, position):
        x, y = position
        return (x-22)*self.TILE+24,(y-2)*self.TILE+24

    def dialogue(self, lines, complete=None):
        self.app.keys.clear()
        self.app.dialogue.show(lines,on_complete=complete)

    def interact(self, now):
        if self.app.dialogue.active:
            self.app.dialogue.advance()
            return
        if self.rumble_at is not None or self.depart_at is not None:
            return
        dx,dy = DIRECTIONS[self.direction]
        target = (self.position[0]+dx,self.position[1]+dy)
        if self.finished and target == ENTRANCE:
            self.app._start_cavern(from_trail=True)
            return
        if target == self.BRANTO:
            self.talk_to_branto()
            return
        if target not in self.LAMPS or target in self.lit:
            return
        if target == self.LAMPS[-1] and (self.LAMPS[0] not in self.lit or self.temur is not None):
            return
        self.lit.add(target)
        self.lamp_lit_at[target] = now
        self.animate_lamps(now)
        self.canvas.itemconfigure(self.objective,text=f"Light the trail lamps  {len(self.lit)}/2")
        self.app._play_sfx(self.assets / "audio" / "trail-lamp.wav", volume=.42)
        if target == self.LAMPS[-1]:
            self.rumble_at = now
            self.app._pending_music = self.app._music_ramp = None
            self.music_gain = self.app._music_gain

    def update(self, direction, now):
        self.animate_lamps(now)
        if direction != "down":
            self.turnback_held = False
        if self.app.dialogue.active:
            return
        c = self.canvas
        if self.rumble_at is not None:
            self.update_rumble(now-self.rumble_at)
            return
        if self.depart_at is not None:
            elapsed = now-self.depart_at
            if elapsed >= .88:
                c.itemconfigure(self.temur_item,state="hidden")
                self.temur = self.depart_at = None
            else:
                x,y = self.point(self.TEMUR)
                c.coords(self.temur_item,x,y-elapsed*218)
                c.itemconfigure(self.temur_item,image=self.temur_frames["up"][int(elapsed*11)%3])
            return
        if direction not in DIRECTIONS or now < self.next_step:
            return
        dx,dy = DIRECTIONS[direction]
        x,y = self.position[0]+dx,self.position[1]+dy
        self.next_step = now+self.STEP
        self.direction = direction
        can_walk = (23 <= x <= 41 and 3 <= y <= 12 and (x,y) in self.map.floor
                    and (x,y) not in (*self.LAMPS,self.BRANTO,self.temur))
        if can_walk and (y >= 6 or self.temur is None):
            self.position = (x,y)
            self.step = (self.step+1)%3
        c.coords(self.hero_item,*self.point(self.position))
        c.itemconfigure(self.hero_item,image=self.hero_frames[direction][self.step])
        if self.LAMPS[0] in self.lit and not self.met and self.position[1] <= 7:
            self.meet_temur()
            return
        if y == 13 and abs(x-self.BRANTO[0]) <= 2 and not self.turnback_held:
            self.turnback_held = True
            self.face_branto()
            line = ("Temur went into the cave. I'll stay here in case Ena comes down."
                    if self.finished else
                    "Hold on, Retri. Ena's still up there. She'll be looking for those lamps when the light goes.")
            self.dialogue([DialogueLine("Branto", line)])
            return
        near = sum(abs(a-b) for a,b in zip(self.position,self.BRANTO)) == 1
        approached = near and not self.branto_near
        self.branto_near = near
        if approached and not self.branto_gifted:
            self.talk_to_branto()
            return
        target = (self.position[0]+dx,self.position[1]+dy)
        if target == ENTRANCE and self.finished:
            hint = "Enter cave · Enter / Cross"
        elif target == self.BRANTO:
            hint = "Talk to Branto · Enter / Cross"
        elif target in self.LAMPS and target not in self.lit:
            hint = "Light lamp · Enter / Cross"
        else:
            hint = ""
        c.itemconfigure(self.prompt,text=hint)

    def face_branto(self):
        turn = facing(self.BRANTO,self.position,"right")
        self.canvas.itemconfigure(self.branto_item,image=self.branto_frames[turn][1])

    def talk_to_branto(self):
        self.face_branto()
        if self.branto_gifted:
            line = ("Mind the loose shale by the cave mouth."
                    if self.finished else "Take your time on the ridge. The shale's loose underfoot.")
            self.dialogue([DialogueLine("Branto", line)])
            return
        self.branto_gifted = True
        self.app.supplies["Remedy"] = self.app.supplies.get("Remedy", 0) + 1
        self.dialogue([
            DialogueLine("Branto", "Take care up there, lad. Here, take my spare Remedy. I always carry one on shift."),
            DialogueLine("", item_gain_text("Remedy")),
        ])

    def meet_temur(self):
        self.met = True
        direction = facing(self.TEMUR,self.position,"down")
        self.canvas.itemconfigure(self.temur_item,image=self.temur_frames[direction][1])
        self.dialogue([
            DialogueLine("Retri", "Temur? Since when do you take paper and charcoal up the mountain?"),
            DialogueLine("Temur", "Since you started asking so many questions. I'll be quick."),
            DialogueLine("Retri", "I'll light the last lamp. You'll see it on your way out."),
        ], lambda: setattr(self,"depart_at",time.monotonic()))

    def update_rumble(self, elapsed):
        a,c = self.app,self.canvas
        if elapsed >= .25 and not self.rubble:
            a._play_sfx(self.rumble,volume=.58)
            self.rubble = [c.create_rectangle(0,0,0,0,fill=color,outline="")
                           for color in ("#7e7488","#625963","#827283","#48414c","#998582")]
        c.itemconfigure(self.prompt,text="")
        gain = .37 + .63*max(0,1-elapsed/.25, min(1,(elapsed-1.25)/.55))
        a._set_music_gain(self.music_gain*gain)
        x,y = self.point(ENTRANCE)
        px,py = self.point(self.position)
        c.coords(self.startle,px,py-34)
        c.itemconfigure(self.startle,state="normal" if .25 <= elapsed < .68 else "hidden")
        shake = round(math.sin(elapsed*51)*2) if .46 <= elapsed < 1.6 else 0
        c.move(self.mouth,shake-self.shake,0)
        self.shake = shake
        for i,item in enumerate(self.rubble):
            age = max(0,elapsed-.54-i*.075)
            dy = min(37+i%2*4, age**2*150)
            px = x-17+i*8 + min(8,age*4)*(i-2)
            c.coords(item,px,y-16+dy,px+5,y-11+dy)
            c.itemconfigure(item,state="normal" if age else "hidden")
        if elapsed >= 1.82:
            c.move(self.mouth,-self.shake,0)
            self.rumble_at=None
            self.finished=True
            self.dialogue([DialogueLine("Retri", "Temur! Can you hear me?"),
                           DialogueLine("Retri", "No answer. The entrance is still shedding rock.",thought=True)],
                          lambda: c.itemconfigure(self.objective,text="Find Temur at the cave entrance"))
