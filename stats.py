"""Starting statistics for the first party and cavern creatures."""

RETRI = {"max_hp": 520, "max_mp": 12, "strength": 15, "defense": 5,
         "magic": 5, "magic_defense": 5, "agility": 10, "luck": 18,
         "evasion": 10, "accuracy": 10}
TEMUR = {"max_hp": 1030, "max_mp": 33, "strength": 20, "defense": 15,
         "magic": 5, "magic_defense": 5, "agility": 5, "luck": 17,
         "evasion": 5, "accuracy": 3}


def member(name, base):
    result = {"name": name, **base}
    result.update(hp=base["max_hp"], mp=base["max_mp"])
    return result
