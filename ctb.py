"""Deterministic conditional turn queue; ticks advance only after resolved actions."""
from math import ceil

# Inclusive upper bounds from the supplied Agility breakpoints.
BREAKPOINTS=((0,28),(1,26),(2,24),(3,22),(4,20),(6,16),(9,15),(11,14),
             (14,13),(16,12),(18,11),(22,10),(28,9),(34,8),(43,7),(61,6),
             (97,5),(169,4),(255,3))

def tick_speed(agility):
    value=max(0,min(255,int(agility)))
    return next(speed for upper,speed in BREAKPOINTS if value<=upper)

def recovery(agility,rank=3,status=None):
    if rank<=0:raise ValueError('Action rank must be positive.')
    return ceil(tick_speed(agility)*rank*({'haste':.5,'slow':2}.get(status,1)))

class CTBQueue:
    def __init__(self,agility,is_alive=lambda key:True):
        self.agility=dict(agility)
        self.order={key:i for i,key in enumerate(self.agility)}
        self.alive=is_alive;self.status={};self.tick=0;self.completed=0
        # Separate deterministic opening: rank-3 wait, stable party-first ties.
        # No random opening formula was supplied, so opening order is reproducible.
        self.ready={key:tick_speed(value)*3 for key,value in self.agility.items()}
        self.current=self._select()

    def _select(self):
        living=[key for key in self.ready if self.alive(key)]
        if not living:return None
        key=min(living,key=lambda k:(self.ready[k],self.order[k]))
        self.tick=max(self.tick,self.ready[key])
        return key

    def advance(self,rank=3):
        if self.current is None:return None
        key=self.current
        self.ready[key]=self.tick+recovery(self.agility[key],rank,self.status.get(key))
        self.completed+=1;self.current=self._select()
        return self.current

    def set_status(self,key,status):
        if key not in self.ready:raise KeyError(key)
        if status not in (None,'haste','slow'):raise ValueError('Unknown CTB status.')
        if status==self.status.get(key):return
        wait=max(0,self.ready[key]-self.tick)
        if status=='haste':self.ready[key]=self.tick+wait//2
        elif status=='slow':self.ready[key]=self.tick+wait*2
        # Dispel changes later recovery without readjusting an existing wait.
        self.status[key]=status

    def preview(self,count=6,rank=3):
        if self.current is None:return []
        ready={k:v for k,v in self.ready.items() if self.alive(k)}
        if not ready:return []
        current=self.current if self.current in ready else min(ready,key=lambda k:(ready[k],self.order[k]))
        clock=self.tick;result=[]
        for i in range(count):
            result.append(current)
            ready[current]=clock+recovery(self.agility[current],rank if i==0 else 3,self.status.get(current))
            current=min(ready,key=lambda k:(ready[k],self.order[k]));clock=max(clock,ready[current])
        return result
