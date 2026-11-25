"""Darkness body tint and a small stitched-lip hex, independent of other overlays."""
import tkinter as tk

class DarknessSilenceFX:
    TAG='silence_seal'
    def __init__(self,canvas):
        self.canvas=canvas;self.images={};self.darkened=set();self.seals={}

    def _base(self,scene,key):
        side,i=key
        if side=='enemy':return scene.enemy_items[i],scene.enemy_image(i)
        return scene.party_items[i],scene.party_image(i)

    def _black(self,source):
        key=str(source)
        if key not in self.images:
            image=tk.PhotoImage(master=self.canvas,width=source.width(),height=source.height())
            # Write opaque horizontal runs; transparent silhouette pixels stay empty.
            for y in range(source.height()):
                start=None;colors=[]
                for x in range(source.width()+1):
                    opaque=x<source.width() and not source.transparency_get(x,y)
                    if opaque:
                        if start is None:start=x
                        r,g,b=source.get(x,y);v=12+(r*3+g*6+b)//100
                        colors.append('#%02x%02x%02x'%(v,v,v+3))
                    elif start is not None:
                        image.put('{'+' '.join(colors)+'}',to=(start,y));start=None;colors=[]
            self.images[key]=image
        return self.images[key]

    def _restore(self,scene,key):
        item,source=self._base(scene,key)
        if source is not None:self.canvas.itemconfigure(item,image=source)
        else:self.canvas.itemconfigure(item,fill='#e99898' if scene.model.party[key[1]]['hp']<=0 else '#ffffff')

    def clear(self,scene):
        for key in self.darkened:self._restore(scene,key)
        self.darkened.clear();self.canvas.delete(self.TAG);self.seals.clear()

    def draw(self,scene,now):
        m=scene.model;c=self.canvas
        dark={key for key in m.statuses.active if m.statuses.has(key,'darkness') and m._ctb_alive(key)}
        for key in self.darkened-dark:self._restore(scene,key)
        for key in dark:
            item,source=self._base(scene,key)
            if source is not None:c.itemconfigure(item,image=self._black(source))
            else:c.itemconfigure(item,fill='#24242b')
        self.darkened=dark
        silent={key for key in m.statuses.active if m.statuses.has(key,'silence') and m._ctb_alive(key)}
        for key in set(self.seals)-silent:
            for item in self.seals.pop(key)['items']:c.delete(item)
        for key in silent:
            side,i=key;actor_item,source=self._base(scene,key)
            width,height=(source.width(),source.height()) if source is not None else (48,48)
            position=c.coords(actor_item)
            x=c.logical_x(position[0]) if hasattr(c,'logical_x') else position[0]
            y=c.logical_y(position[1]) if hasattr(c,'logical_y') else position[1]
            x+=(-1 if side=='party' else 1)*min(14,width*.16)
            y-=height*.23
            if side=='party' and scene.party_pose[i]=='critical' and (i!=m.actor or scene._actor_frame is None):
                y+=15
            if key not in self.seals:
                tags=(scene.TAG,'battle_ailment_fx',self.TAG)
                items=[c.create_polygon(0,0,0,0,0,0,fill='#251e2c',outline='#b49ac5',width=1,tags=tags),
                       c.create_line(0,0,0,0,fill='#ca9eae',width=2,tags=tags)]
                for _ in range(6):items.append(c.create_line(0,0,0,0,fill='#e4d2de',width=1,tags=tags))
                self.seals[key]={'items':items,'point':None,'visibility':None}
            state=self.seals[key]
            visibility='hidden' if c.itemcget(actor_item,'state')=='hidden' else 'normal'
            if state['visibility']!=visibility:
                for item in state['items']:c.itemconfigure(item,state=visibility)
                state['visibility']=visibility
            if state['point']!=(x,y):
                items=state['items']
                c.coords(items[0],x-9,y,x-5,y-6,x+5,y-6,x+9,y,x+5,y+6,x-5,y+6)
                c.coords(items[1],x-5,y,x+5,y)
                for j,offset in enumerate((-3,0,3)):
                    c.coords(items[2+j*2],x+offset-1,y-2,x+offset+1,y+2)
                    c.coords(items[3+j*2],x+offset+1,y-2,x+offset-1,y+2)
                state['point']=(x,y)
        c.tag_raise(self.TAG);c.tag_raise('battle_ui')
