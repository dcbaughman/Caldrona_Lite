"""Persistent and timed curable battle ailments."""
from dataclasses import dataclass

@dataclass(frozen=True)
class Ailment:
    label: str
    short: str
    color: str
    duration: int

AILMENTS={
    'poison':Ailment('Poison','PSN','#89d67b',-1),
    'frozen':Ailment('Frozen','FRZ','#9ddff2',1),
    'darkness':Ailment('Darkness','DRK','#b0a2cd',-1),
    'silence':Ailment('Silence','SIL','#e3b3d3',-1),
    'webbed':Ailment('Webbed','WEB','#c9c7df',3),
    # Moveset statuses (movesets.md). Timed, so saves never persist them.
    'slow':Ailment('Slow','SLW','#8fb6e8',3),
    'bogged':Ailment('Bogged','BOG','#a08a5c',2),
    'sinking':Ailment('Sinking','SNK','#7d6a45',3),
}
# Bleed and Curse are not implemented in Lite; cure lists name them and filter here.
def curable(statuses):
    return tuple(status for status in statuses if status in AILMENTS)
# Adds ailments to existing lessons without expanding established class pools.
PLAYER_AILMENTS={
    'unbound_spark':('silence',.40),
    'unbound_flint_burst':('darkness',.50),
    'seer_mind_flare':('silence',.75),
    'seer_mist_ray':('frozen',.65),
    'sollers_venom_edge':('poison',.85),
    'sollers_smoke_spark':('darkness',.75),
}

class StatusBook:
    def __init__(self):
        self.active={}
        self.freeze_guard={}
        self.owners={}

    def bind(self,key,member):
        self.owners[key]=member
        if member.get('hp', 1) <= 0:
            self.clear_ko(key)
            return
        self.active[key]={status:(-1 if AILMENTS[status].duration==-1 else turns)
                          for status,turns in member.get('ailments',{}).items() if status in AILMENTS}

    def sync(self,key):
        if key not in self.owners:return
        lasting={status:-1 for status in self.for_actor(key) if AILMENTS[status].duration==-1}
        if lasting:self.owners[key]['ailments']=lasting
        else:self.owners[key].pop('ailments',None)

    def for_actor(self,key):
        return self.active.setdefault(key,{})

    def has(self,key,status):
        return self.for_actor(key).get(status,0)!=0

    def apply(self,key,status,turns=None):
        if status not in AILMENTS:raise ValueError('Unknown ailment.')
        if status=='frozen' and (self.has(key,status) or self.freeze_guard.get(key,0)>0):return False
        state=self.for_actor(key)
        duration=AILMENTS[status].duration if turns is None else turns
        state[status]=-1 if AILMENTS[status].duration==-1 else max(state.get(status,0),duration)
        self.sync(key)
        return True

    def remove(self,key,status):
        if self.for_actor(key).pop(status,None) is not None and status=='frozen':
            self.freeze_guard[key]=2
        self.sync(key)

    def cure(self,key):
        removed=list(self.for_actor(key))
        for status in removed:self.remove(key,status)
        return removed

    def clear_ko(self,key):
        self.for_actor(key).clear()
        self.freeze_guard.pop(key,None)
        self.sync(key)

    def end_turn(self,key):
        if self.freeze_guard.get(key,0)>0:self.freeze_guard[key]-=1
        for status in list(self.for_actor(key)):
            if self.active[key][status]==-1:continue
            self.active[key][status]-=1
            if self.active[key][status]<=0:self.remove(key,status)

    def label(self,key):
        return ' | '.join(AILMENTS[s].short if n==-1 else f'{AILMENTS[s].short} {n}' for s,n in self.for_actor(key).items())
