"""Four-slot save/load panel, shared by the sphere and title Continue menu."""
from datetime import datetime
import time
from depths import DEN_FLOOR, den_location
from save_game import SaveError, capture, read_slot, write_slot, slot_path
from stats import restore_party

class SaveMenu:
    TAG='save_slots_ui'
    def __init__(self,app,mode):
        self.app,self.mode=app,mode
        self.selection=0;self.held=None;self.repeat_at=0
        self.confirming=False;self.overwrite=False;self.feedback=''
        if mode=='load':app._draw_title_scene(show_title=False)
        app.screen='save_slots';app.keys.clear();app.pad_keys.clear()
        app.held_direction=None
        self.refresh();self.draw()

    def refresh(self):
        self.slots=[]
        for slot in range(1,5):
            try:self.slots.append(read_slot(self.app.save_directory,slot))
            except SaveError:self.slots.append('unreadable')

    def draw(self):
        c=self.app.canvas;c.delete(self.TAG)
        tag=self.TAG
        c.create_rectangle(115,66,845,508,fill='#101b31',outline='#c3a567',width=3,tags=tag)
        c.create_rectangle(122,73,838,501,outline='#536880',tags=tag)
        def text(x,y,value,size=20,color='#eee9d6',**kw):
            c.create_text(x,y,text=value,font=self.app._font(size),fill=color,tags=tag,**kw)
        text(480,99,'SAVE SPHERE' if self.mode=='save' else 'CONTINUE JOURNEY',28,'#f0d28c')
        for index,data in enumerate(self.slots):
            y=155+index*72;selected=index==self.selection
            c.create_rectangle(140,y-26,820,y+36,fill='#263c55' if selected else '#17243b',outline='#a9e5d7' if selected else '#3e536c',tags=tag)
            text(156,y,'▶' if selected else '',18,'#b1f0dd',anchor='w')
            text(183,y,f'FILE {index+1}',20,'#f0d28c',anchor='w')
            if isinstance(data,dict):
                state=data['state'];party=' / '.join(p['name'] for p in state['party'])
                place='Sunrest Grasslands' if state['outdoors'] else 'Astral Hollow' if state['in_chamber'] else 'Sunrest Excavation'
                tile = (int(state['x'] // 16), int(state['y'] // 16))
                if not state['outdoors'] and tile in DEN_FLOOR:
                    place = den_location(tile)
                text(292,y,f'{party}  ·  Lv {state["party"][0]["level"]}  ·  {state["gold"]} gold',20,anchor='w')
                try:date=datetime.fromisoformat(data['saved_at']).strftime('%b %d, %Y  %I:%M %p')
                except ValueError:date='Saved journey'
                text(292,y+22,f'{place}  ·  {date}',16,'#a9bacb',anchor='w')
            else:
                text(292,y,'EMPTY SLOT' if data is None else 'UNREADABLE SAVE',20,'#91a5ba',anchor='w')
                if data:text(292,y+22,'Choose another file, or replace at a save sphere.',15,'#a9bacb',anchor='w')
        if self.confirming:
            text(480,438,f'Overwrite FILE {self.selection+1}?',21,'#f0d28c')
            text(360,476,('▶ ' if not self.overwrite else '')+'GO BACK',20,'#b1f0dd' if not self.overwrite else '#a9bacb')
            text(626,476,('▶ ' if self.overwrite else '')+'OVERWRITE',20,'#b1f0dd' if self.overwrite else '#a9bacb')
        else:
            text(480,443,self.feedback or ('Choose a file to save your journey.' if self.mode=='save' else 'Choose a saved journey.'),18,'#b1f0dd',width=650)
            text(480,480,'UP / DOWN SELECT  ·  ENTER / CROSS CONFIRM  ·  ESC / CIRCLE BACK',16,'#a9bacb')

    def navigate(self,direction,now):
        if direction not in ('up','down','left','right'):
            self.held=None;return
        if direction==self.held and now<self.repeat_at:return
        self.held=direction;self.repeat_at=now+.22
        if self.confirming:self.overwrite=not self.overwrite
        else:self.selection=(self.selection+(-1 if direction in ('up','left') else 1))%4;self.feedback=''
        self.draw()

    def activate(self):
        slot=self.selection+1
        if self.mode=='load':
            try:
                data=read_slot(self.app.save_directory,slot)
                if data is None:self.feedback='This file is empty.'
                else:self.app._load_journey(data['state']);return
            except (SaveError,OSError) as exc:self.feedback=str(exc)
        else:
            if not self.confirming and slot_path(self.app.save_directory,slot).exists():
                self.confirming=True;self.overwrite=False;self.draw();return
            if self.confirming and not self.overwrite:
                self.confirming=False;self.draw();return
            state = capture(self.app)
            restore_party(state['party'])
            state['hp'] = state['party'][0]['hp']
            try:
                write_slot(self.app.save_directory, slot, state)
            except (OSError, SaveError):
                self.feedback = 'Could not save. Your previous file has been kept.'
            else:
                restore_party(self.app.party)
                self.app.hp = state['hp']
                self.feedback = f'Journey saved to FILE {slot}. Party restored.'
                self.refresh()
            self.confirming=False
        self.draw()

    def back(self):
        if self.confirming:
            self.confirming=False;self.draw();return
        self.app.canvas.delete(self.TAG)
        self.app.keys.clear();self.app.pad_keys.clear()
        if self.mode=='save':
            self.app.screen='game';self.app.held_direction=None
            self.app.next_step_at=time.monotonic()+.25
        else:self.app._draw_menu()

    def click(self,x,y):
        if self.confirming:
            if 452<=y<=494:
                self.overwrite=x>=480;self.activate()
            return
        for i in range(4):
            if 140<=x<=820 and 129+i*72<=y<=191+i*72:
                if self.selection==i:self.activate()
                else:self.selection=i;self.feedback='';self.draw()
                return
