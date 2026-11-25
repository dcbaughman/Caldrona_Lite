"""Mining remnants, a trapped entrance, and the warning before Shalehorn."""
import math
import random
import time
import tkinter as tk
from dialogue import DialogueLine
from stats import TEMUR, member

ENTRY = (8, 3)
TILE = 16
TEMUR_APPROACH = (10, 13)
TEMUR_STOP = (9, 7)
RECRUIT_OPTIONS = ("Travel with Temur", "Continue alone")
ENTRY_SHOULDERS = ((7, 3), (9, 3))
MINER=(48,7)
MINER_NAME = "Theo"
SIGNS={
 'dropped_tools':((7,5),'tools',"A pick and a snapped brace. Whoever left these was in a hurry."),
 'abandoned_cart':((9,28),'cart',"The cart is still loaded. Deep gouges score the wood, far wider than a pick."),
 'last_lantern':((35,24),'lantern',"A lantern still burns beside an abandoned shift ledger. The last entry reads: 'Blue seam. Keep clear.'"),
 'blue_ore_cart':((25,5),'cart',"Only ordinary ore remains. Every note about the blue stone has been crossed out."),
 'broken_support':((44,7),'tools',"This support was smashed from below. Something heavy has been digging under the workings."),
}

def fresh_story():
 return {'entrance_collapsed':False,'miner_warned':False,'inspected':[],
         'den_unsealed':False,'den_cleared':False,'black_stone_attuned':False,
         'white_stone_seen':False,'depths_chests':[]}

def old_story():
 return dict(fresh_story(), entrance_collapsed=True)

class CaveStory:
 def __init__(self,app,assets,scale):
  self.app = app
  self.scale = scale
  self.shift = 0
  self.started = 0
  self.walk = None
  self.choice = 0
  art = assets / "mine-polish"
  self.images = {
   name: tk.PhotoImage(master=app.root, file=str(art / f"{name}.png")).zoom(scale)
   for name in ("cart", "tools", "lantern", "entrance-open", "entrance-blocked")
  }
  self.images["miner-down"] = app._load_world_actor(art / "miner-down.png")
  detail = assets / "entrance-detail"
  self.stone = [
   tk.PhotoImage(master=app.root, file=str(detail / f"stone-{side}.png")).zoom(scale)
   for side in ("left", "right")
  ]
  self.shards = [
   tk.PhotoImage(master=app.root, file=str(art / f"shard-{i}.png")).zoom(scale)
   for i in range(3)
  ]
  rng = random.Random(14)
  self.debris = [
   (rng.uniform(.02, .42), rng.uniform(-16, 16), rng.uniform(12, 22), rng.randrange(3))
   for _ in range(13)
  ]
  self.dust = [
   (rng.uniform(.15, .48), rng.uniform(-10, 10), rng.uniform(-25, 25), rng.uniform(2, 6))
   for _ in range(20)
  ]
  c = app.canvas
  self.stone_items = [
   c.create_image(0, 0, image=image, anchor="s", tags="cave_story_prop")
   for image in self.stone
  ]
  self.items = {}
  props = [("entry", self.images["entrance-open"]), ("miner", self.images["miner-down"])]
  props.extend((key, self.images[art]) for key, (_, art, _) in SIGNS.items())
  for name, image in props:
   self.items[name] = c.create_image(0, 0, image=image, anchor="s", tags="cave_story_prop")

 def blocked(self,tile):return tile==MINER or tile in {value[0] for value in SIGNS.values()}

 def render(self):
  a=self.app;c=a.canvas;cx,cy=a._camera();s=self.scale
  if a.cave_story['entrance_collapsed']:a.cavern_map.blocked.add(ENTRY)
  else:a.cavern_map.blocked.discard(ENTRY)
  entrance = 'entrance-blocked' if a.cave_story['entrance_collapsed'] else 'entrance-open'
  c.itemconfigure(self.items['entry'], image=self.images[entrance])
  for item, offset in zip(self.stone_items, (-23, 23)):
   c.coords(item, ((ENTRY[0] + .5) * TILE + offset - cx) * s,
            (ENTRY[1] * TILE + 10 - cy) * s)
   c.itemconfigure(item, state="hidden" if a.outdoors else "normal")
  for key,tile in [('entry',ENTRY),('miner',MINER)]+[(key,value[0]) for key,value in SIGNS.items()]:
   baseline = tile[1] * 16 + (12 if key == "entry" else 16)
   c.coords(self.items[key], ((tile[0] + .5) * 16 - cx) * s, (baseline - cy) * s)
   c.itemconfigure(self.items[key],state='hidden' if a.outdoors else 'normal')
  c.tag_raise('cave_story_prop');c.tag_raise('world_party');c.tag_raise('hud');c.tag_raise('dialogue')

 def warning(self):
  a=self.app;a.cave_story['miner_warned']=True;a.keys.clear();a.held_direction=None
  if a.boss_cleared:
   lines=[DialogueLine(MINER_NAME,"The shaking has stopped. You drove it off! There's an old survey opening beyond the blue seam. It should lead outside.")]
  else:
   lines=[DialogueLine(MINER_NAME,"Don't go through that door unprepared. We uncovered a blue rock, and Shalehorn came straight for it."),
          DialogueLine(MINER_NAME,"It guards that stone. Anyone who gets near it is attacked. Its digging and charges are tearing the cave apart."),
          DialogueLine('Retri',"The entrance collapsed behind me. Is there another way out?"),
          DialogueLine(MINER_NAME,"An old survey opening lies beyond its chamber. We couldn't get past Shalehorn to reach it. Use the shrine to save and prepare." )]
  a.dialogue.show(lines)

 def maybe_warn(self):
  a=self.app
  if not a.outdoors and not a.in_chamber and not a.cave_story['miner_warned'] and a.x/16>=45 and a.y/16<=10:
   self.warning();return True
  return False

 def interact(self):
  a=self.app
  if a.outdoors:return False
  dx,dy={'up':(0,-1),'down':(0,1),'left':(-1,0),'right':(1,0)}[a.direction]
  tile=(int(a.x//16)+dx,int(a.y//16)+dy)
  if tile==MINER:self.warning();return True
  if tile==ENTRY:
   a.dialogue.show([DialogueLine('Retri',"The entrance is buried. I can't shift these rocks alone. There has to be another way out.")]);return True
  for key,(point,_,text) in SIGNS.items():
   if tile==point:
    if key not in a.cave_story['inspected']:a.cave_story['inspected'].append(key)
    a.dialogue.show([DialogueLine('Retri',text,thought=True)])
    return True
  return False

 def open_at_entrance(self):
  a = self.app
  a.dialogue.show([
   DialogueLine("Retri", "The calls came from inside. I'll see if anyone's still here.", thought=True),
  ], on_complete=self.walk_inside)

 def walk_inside(self):
  self._start_walk(
   "retri", (ENTRY[0], ENTRY[1] + 1),
   (
    ((8, 5), "down", .27),
    ((8, 6), "down", .27),
    ((8, 6), "left", .40),
    ((8, 6), "right", .40),
    ((8, 7), "down", .30),
   ),
   self.start_collapse,
  )

 def _start_walk(self, actor, start, beats, complete, now=None):
  a = self.app
  a.screen = "cave_walk"
  a.held_direction = None
  self.started = time.monotonic() if now is None else now
  self.walk = (actor, start, beats, complete)
  self.update_walk(self.started)

 def update_walk(self, now):
  actor, start, beats, complete = self.walk
  elapsed = max(0, now - self.started)
  for target, direction, duration in beats:
   if elapsed < duration:
    progress = elapsed / duration
    x = start[0] + (target[0] - start[0]) * progress
    y = start[1] + (target[1] - start[1]) * progress
    stride = 0
    if target != start:
     distance = math.dist(start, target)
     stride = 1 + int(progress * distance * 4)
    self._place_walker(actor, x, y, direction, stride)
    return
   elapsed -= duration
   start = target
  self._place_walker(actor, *target, direction, 0)
  self.walk = None
  complete(now)

 def _place_walker(self, actor, tile_x, tile_y, direction, stride):
  a = self.app
  x, y = (tile_x + .5) * TILE, (tile_y + .5) * TILE
  if actor == "retri":
   a.x, a.y = x, y
   a.direction = direction
   a.walk_frame = (2 if stride % 2 else 0) if stride else 1
   a._update_world()
   return
  cx, cy = a._camera()
  item, _, faces = a.dialogue_actors["temur"]
  a.canvas.coords(item, (x - cx) * self.scale, (y - cy - stride % 2) * self.scale)
  a.canvas.itemconfigure(item, image=faces[direction], state="normal")

 def start_collapse(self, now=None):
  a = self.app
  a.screen = "entrance_collapse"
  a.held_direction = None
  a.direction = "up"
  self.started = time.monotonic() if now is None else now
  self.shift = 0
  a._play_sfx(a.collapse_sound_path)

 def temur_approaches(self, now):
  self._start_walk(
   "temur", TEMUR_APPROACH,
   (((10, 7), "up", 1.12), (TEMUR_STOP, "left", .24)),
   self._temur_arrives, now,
  )

 def _temur_arrives(self, now):
  a = self.app
  a.temur_tile = TEMUR_STOP
  item, _, faces = a.dialogue_actors["temur"]
  a.dialogue_actors["temur"] = (item, TEMUR_STOP, faces)
  a.direction = "right"
  self.offer_temur(after_collapse=True)

 def offer_temur(self, after_collapse=False):
  a = self.app
  a.screen = "game"
  a.temur_story = "offering"
  a._update_world()
  if after_collapse:
   lines = [
    DialogueLine("Temur", "Are you hurt? I heard the roof come down."),
    DialogueLine("Retri", "I'm fine. The way back is buried. Did you call for help?"),
    DialogueLine("Temur", "No. I was looking for the miners too. There may be another way out past the workings."),
   ]
  elif a.boss_cleared:
   lines = [
    DialogueLine("Temur", "The miner says you drove Shalehorn off. Mind if I come with you?"),
   ]
  else:
   lines = [
    DialogueLine("Temur", "I felt the cave-in. Are you looking for the miners too?"),
    DialogueLine("Retri", "Yes. And another way outside."),
   ]
  lines.append(DialogueLine("Temur", "I'm Temur. Want to travel together?"))
  a.dialogue.show(lines, on_complete=self.open_choice)

 def open_choice(self):
  self.app.screen = "temur_choice"
  self.choice = 0
  self.draw_choice()

 def draw_choice(self):
  self.app.dialogue.draw_choice(RECRUIT_OPTIONS, self.choice)

 def navigate_choice(self, direction):
  if direction in ("up", "down"):
   choice = 0 if direction == "up" else 1
   if choice != self.choice:
    self.choice = choice
    self.draw_choice()

 def click_choice(self, x, y):
  if 300 <= x <= 660 and 411 <= y < 495:
   self.choice = min(1, int((y - 411) // 42))
   self.confirm_choice()

 def confirm_choice(self):
  a = self.app
  a.dialogue.clear()
  a.screen = "game"
  if self.choice == 0:
   a.temur_story = "joined"
   a._recruit(member("Temur", TEMUR))
   a._update_world()
   a.dialogue.show([
    DialogueLine("Retri", "I'm Retri. Let's find a way out."),
    DialogueLine("", "Temur joined the party!"),
   ], on_complete=self._finish_opening)
  else:
   a.dialogue.show([
    DialogueLine("Retri", "Thanks, but I'll go on alone."),
    DialogueLine("Temur", "Fair enough. If you make it to Sunrest, look for me there."),
   ], on_complete=self.temur_departs)

 def temur_departs(self):
  a = self.app
  a.temur_story = "departing"
  beats = []
  if a.temur_tile != (10, 7):
   beats.append(((10, 7), "right", .24))
  # Continue down the corridor until the sprite is outside the current frame.
  _, cy = a._camera()
  exit_y = max(13, math.ceil((cy + 180 + TILE / 2) / TILE))
  beats.append(((10, exit_y), "down", (exit_y - 7) * .20))
  self._start_walk("temur", a.temur_tile, tuple(beats), self._temur_leaves)

 def _temur_leaves(self, now):
  a = self.app
  a.temur_story = "declined"
  a.canvas.itemconfigure(a.temur_item, state="hidden")
  self._finish_opening()

 def _finish_opening(self):
  a = self.app
  a.screen = "game"
  a.opening_intro_active = False
  a.held_direction = None
  a.next_step_at = time.monotonic() + .15

 def update(self,now):
  a=self.app;c=a.canvas;s=self.scale;t=max(0,now-self.started)
  c.delete('entrance_debris')
  impact = max(0, t - .14)
  strength = max(0, 1 - impact / 1.15)
  shake = round(math.sin(impact * 86) * 6 * strength) if impact else 0
  for tag in ("world", "cave_story_prop", "temur", "chest"):
   c.move(tag, shake - self.shift, 0)
  self.shift = shake
  a._place_player(a._camera())
  jump = min(1, max(0, (t - .23) / .5))
  c.move("player", shake, -math.sin(jump * math.pi) * 11 * s)
  cx, cy = a._camera()
  x = ((ENTRY[0] + .5) * 16 - cx) * s + shake
  ground = ((ENTRY[1] + .75) * 16 - cy) * s
  for start, offset, drift, radius in self.dust:
   age = (t - start) / 1.25
   if 0 <= age < 1:
    px = x + (offset + drift * age) * s
    py = ground - (2 + 9 * age) * s
    spread = radius * (1 + age) * s
    c.create_oval(px-spread, py-spread*.45, px+spread, py+spread*.45,
                  fill="#746a81" if age < .55 else "#544c64", outline="",
                  stipple="gray25" if age < .5 else "gray12", tags="entrance_debris")
  for start, offset, height, variant in self.debris:
   flight = (t - start) / .42
   if 0 <= flight <= 1:
    px = x + offset * s
    py = ground - (height + 7) * (1 - flight * flight) * s
    c.create_image(px, py, image=self.shards[variant], tags="entrance_debris")
  c.tag_raise("player")
  if t>=.7 and not a.cave_story['entrance_collapsed']:
   a.cave_story['entrance_collapsed']=True;a.cavern_map.blocked.add(ENTRY)
   c.itemconfigure(self.items['entry'],image=self.images['entrance-blocked'])
  if t >= 1.7:
   c.delete("entrance_debris")
   self.shift = 0
   a._update_world(force=True)
   self.temur_approaches(now)
