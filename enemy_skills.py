"""Enemy signature skills, alternating with basic attacks and using finite MP."""
from dataclasses import dataclass


@dataclass(frozen=True)
class EnemySkill:
    name: str
    animation: str
    status: str | None = None
    chance: float = 0
    mp: int = 2
    magic: bool = False
    rank: int = 4
    palette: str = ""
    element: str = ""


SKILLS = {
    "Ivory Spider": (EnemySkill("Venom Bite", "sollers_venom_edge", "poison", .65),),
    "Echo Bat": (EnemySkill("Echo Screech", "seer_mind_flare", magic=True),),
    "Rock Crawler": (EnemySkill("Dust Ram", "unbound_quarry_echo"),),
    "Cinder Hornet": (EnemySkill("Ember Sting", "sollers_venom_edge", "poison", .30),),
    "Ashmane Wolf": (EnemySkill("Raking Lunge", "unbound_hard_edge", rank=3),),
    "Torshield Ram": (EnemySkill("Stone-Crown Charge", "unbound_quarry_echo", rank=5),),
    "Hollow Weaver": (EnemySkill("Silk Snare", "seer_mist_ray", "webbed", .45),),
    "Emberwraith": (EnemySkill("Broodfire", "unbound_ember_arc", magic=True, palette="ember", element="fire"),),
    "Silk Sarcophagus": (EnemySkill("Spiral Seal", "seer_farseal", "webbed", .30, magic=True),),
    "Brood Stalker": (EnemySkill("Blackfang", "sollers_venom_edge", "poison", .55),),
    "Den Mother": (
        EnemySkill("Venom Fang", "sollers_venom_edge", "poison", .70),
        EnemySkill("Rime Howl", "seer_mist_ray", "frozen", .60, magic=True),
    ),
}
