"""Poison fumes and bubbles persist until the actual ailment is cured."""
import math
import tkinter as tk
from frozen_fx import FrozenOverlay

class PoisonOverlay(FrozenOverlay):
 TAG='poison_aura'
 def __init__(self,canvas,assets):
  super().__init__(canvas,assets)
  self.assets=self.assets.parent/'poison-aura'
  self.carry_in=set()

 def begin(self,model):
  self.clear()
  self.carry_in={key for key in model.statuses.active if model.statuses.has(key,'poison')}

 def draw(self,scene,now):
  m=scene.model;c=self.canvas
  active={key for key in m.statuses.active if m.statuses.has(key,'poison') and m._ctb_alive(key)}
  for key in active:
   if key not in self.states:
    started=now-.4 if key in self.carry_in else self._contact_time(scene,key,now)
    self.carry_in.discard(key)
    self.states[key]={'started':started,'frame':None,'item':c.create_image(0,0,anchor='s',state='hidden',tags=(scene.TAG,'battle_ailment_fx',self.TAG))}
  for key,state in list(self.states.items()):
   if key not in active:
    c.delete(state['item']);del self.states[key];continue
   elapsed=now-state['started']
   if elapsed<0:continue
   frame=min(3,int((elapsed+1e-7)/.1)) if elapsed<.4 else 4+int((elapsed-.4)/.18)%4
   side,i=key;x,y=scene._party_position(i) if side=='party' else scene.enemy_positions[i]
   sprite=scene.party_sprites[i] if side=='party' else scene.enemies[m.enemies[i].sprite]
   width,height=(sprite.width(),sprite.height()) if sprite is not None else (48,48)
   scale=max(2,math.ceil(max(width,height)/40));cache=(frame,scale)
   if cache not in self.images:self.images[cache]=tk.PhotoImage(master=c,file=str(self.assets/f'{frame}.png')).zoom(scale)
   if state['frame']!=cache:
    c.itemconfigure(state['item'],image=self.images[cache],state='normal');state['frame']=cache
   dx,dy=getattr(scene,'_camera_offset',(0,0));c.coords(state['item'],x+dx,y+dy+height/2+8)
  c.tag_raise(self.TAG);c.tag_raise('battle_ui')
