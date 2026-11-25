"""Persistent ice overlay: impact pop, held crystal, and a short thaw burst."""
import math
from pathlib import Path
import tkinter as tk

class FrozenOverlay:
    TAG='frozen_shell'
    def __init__(self,canvas,assets):
        self.canvas=canvas
        self.assets=Path(assets)/'battle'/'fx'/'frozen-shell'
        self.states={}
        self.images={}

    def clear(self):
        self.canvas.delete(self.TAG)
        self.states.clear()

    def _contact_time(self,scene,key,now):
        if scene.phase=='ability_fx' and (scene.fx_variant is not None or scene.player_motion is not None):
            target=('enemy',scene.model.target) if scene.fx_on_enemy else ('party',scene.fx_ally)
            if key==target:
                return max(now,scene.phase_at+scene.ability_contact_ms/1000)
        elif scene.phase=='hero_action' and scene.model.effect=='Attack' and key==('enemy',scene.model.target):
            return max(now,scene.phase_at+scene.attack_contact_ms/1000)
        elif scene.phase=='enemy_action' and key==('party',scene.model.defender):
            variant=getattr(scene,'_enemy_variant',None)
            return max(now,scene.phase_at+(variant.contact_ms/1000 if variant else 0))
        return now

    def draw(self,scene,now):
        m=scene.model;c=self.canvas
        active={key for key,state in m.statuses.active.items() if state.get('frozen',0)>0 and m._ctb_alive(key)}
        for key in active:
            if key not in self.states or self.states[key]['thaw_at'] is not None:
                if key in self.states:c.delete(self.states[key]['item'])
                self.states[key]={'started':self._contact_time(scene,key,now),'thaw_at':None,'frame':None,
                    'item':c.create_image(0,0,anchor='s',state='hidden',tags=(scene.TAG,'battle_ailment_fx',self.TAG))}
        for key,state in list(self.states.items()):
            if not m._ctb_alive(key):
                c.delete(state['item']);del self.states[key];continue
            if key not in active and state['thaw_at'] is None:
                state['thaw_at']=self._contact_time(scene,key,now)
            if state['thaw_at'] is not None and now>=state['thaw_at']:
                elapsed=now-state['thaw_at']
                if elapsed>=.28:
                    c.delete(state['item']);del self.states[key];continue
                frame=6+min(1,int((elapsed+1e-7)/.14))
            else:
                elapsed=now-state['started']
                if elapsed<0:continue
                frame=min(3,int((elapsed+1e-7)/.08)) if elapsed<.32 else (3,4,5,4)[int((elapsed-.32)/.28)%4]
            side,i=key
            x,y=scene._party_position(i) if side=='party' else scene.enemy_positions[i]
            sprite=scene.party_sprites[i] if side=='party' else scene.enemies[m.enemies[i].sprite]
            width,height=(sprite.width(),sprite.height()) if sprite is not None else (48,48)
            scale=max(2,math.ceil(max(width,height)/40))
            cache=(frame,scale)
            if cache not in self.images:
                self.images[cache]=tk.PhotoImage(master=c,file=str(self.assets/f'{frame}.png')).zoom(scale)
            if state['frame']!=cache:
                c.itemconfigure(state['item'],image=self.images[cache],state='normal')
                state['frame']=cache
            dx,dy=getattr(scene,'_camera_offset',(0,0))
            c.coords(state['item'],x+dx,y+dy+height/2+8)
        c.tag_raise(self.TAG)
        c.tag_raise('battle_ui')
