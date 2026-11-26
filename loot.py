"""Sunrest's four independent kill slots and three steal slots per foe."""
from collections import Counter
from dataclasses import dataclass

from equipment import item_for
from research import ECHO_ANALECT, QUARRY_ANALECT

BAZAAR_MATERIALS = {"Spider Silk": 4, "Echo Wing": 3, "Shale Chip": 5, "Brood Silk": 12}
# Gear, price, and cumulative materials sold to Merren.
BAZAAR = {
    "field_guard": (24, {"Spider Silk": 3, "Shale Chip": 2}),
    "quarry_mantle": (50, {"Echo Wing": 3, "Shale Chip": 4}),
    "pickpocket_dirk": (65, {"Spider Silk": 4, "Echo Wing": 3}),
    "silkweave_coat": (46, {"Spider Silk": 3, "Echo Wing": 2}),
    "embersteel_blade": (54, {"Shale Chip": 3, "Echo Wing": 2}),
}
STEAL_ODDS = (0.55, 0.10, 0.03)
EQUIPPED_STEAL_ODDS = (0.80, 0.30, 0.06)


@dataclass(frozen=True)
class LootProfile:
    rank: str
    rp: int
    drops: tuple[tuple[str, float], ...]
    steal: tuple[str, str, str]
    fixed: tuple[str, ...] = ()


PROFILES = {
    "Ivory Spider": LootProfile("Regular", 1,
        (("Spider Silk", 0.38), ("Potion", 0.12), ("leather_vest", 0.025), (QUARRY_ANALECT, 0.008)),
        ("Spider Silk", "Potion", QUARRY_ANALECT)),
    "Echo Bat": LootProfile("Regular", 1,
        (("Echo Wing", 0.36), ("Ether", 0.09), ("lucky_charm", 0.02), (ECHO_ANALECT, 0.008)),
        ("Echo Wing", "Potion", ECHO_ANALECT)),
    "Rock Crawler": LootProfile("Regular", 1,
        (("Shale Chip", 0.42), ("Potion", 0.10), ("field_guard", 0.025), (QUARRY_ANALECT, 0.008)),
        ("Shale Chip", "Ether", QUARRY_ANALECT)),
    "Cinder Hornet": LootProfile("Regular", 2,
        (("Remedy", .28), ("Potion", .14), ("Ether", .06), ("lucky_charm", .02)),
        ("Remedy", "Potion", "Ether")),
    "Ashmane Wolf": LootProfile("Regular", 2,
        (("Potion", .32), ("Ether", .10), ("Remedy", .08), ("quarry_coat", .025)),
        ("Potion", "Ether", "Remedy")),
    "Torshield Ram": LootProfile("Regular", 2,
        (("Shale Chip", .30), ("Potion", .22), ("Ether", .08), ("field_guard", .02)),
        ("Potion", "Shale Chip", "Ether")),
    "Hollow Weaver": LootProfile("Regular", 2,
        (("Spider Silk", .72), ("Remedy", .28), ("Brood Silk", .24), ("silkweave_coat", .045)),
        ("Spider Silk", "Remedy", "silkweave_coat")),
    "Emberwraith": LootProfile("Regular", 2,
        (("Ether", .31), ("Remedy", .18), ("Ember Feather", .12), ("embersteel_blade", .04)),
        ("Ether", "Ember Feather", "embersteel_blade")),
    "Silk Sarcophagus": LootProfile("Regular", 3,
        (("Brood Silk", .48), ("Remedy", .32), ("silkweave_coat", .07), ("Ember Talisman", .025)),
        ("Brood Silk", "Remedy", "Ember Talisman")),
    "Brood Stalker": LootProfile("Elite", 3,
        (("Brood Silk", .66), ("Remedy", .40), ("silkweave_coat", .08), ("embersteel_blade", .05)),
        ("Brood Silk", "Remedy", "silkweave_coat")),
    "Den Mother": LootProfile("Boss", 8,
        (("Brood Silk", 0.75), ("Ember Feather", 0.24), ("quarry_mantle", 0.20), ("pickpocket_dirk", 0.045)),
        ("Brood Silk", "Ember Feather", "pickpocket_dirk"), ("broodguard_seal", "silkweave_coat")),
    "Shalehorn": LootProfile("Boss", 5,
        (("Shale Chip", 0.75), ("Ether", 0.25), ("Ember Feather", 0.12), ("Ember Talisman", 0.035)),
        ("Shale Chip", "Ether", "Ember Talisman"), ("shalehorn_crook",)),
    "Ember Wyvern": LootProfile("Boss", 4,
        (("Shale Chip", 0.75), ("Ether", 0.30), ("Remedy", 0.20), ("quarry_coat", 0.06)),
        ("Shale Chip", "Ether", "Remedy")),
}


def roll_kill(profile, rng):
    drops = Counter(profile.fixed)
    for item, odds in profile.drops:
        if rng.random() < odds:
            drops[item] += 1
    return drops


def roll_steal(profile, rng, enhanced=False):
    odds = EQUIPPED_STEAL_ODDS if enhanced else STEAL_ODDS
    return Counter(item for item, chance in zip(profile.steal, odds) if rng.random() < chance)


def loot_name(key):
    gear = item_for(key)
    return gear.name if gear else key
