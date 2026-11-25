"""Damage and critical-hit math on Caldrona's stat scale."""


def physical_damage(strength, armor, variance, power=0):
    # Six starting damage and a tempered cubic keep low-level hits near their
    # existing values. Convert local armor to the defense curve's 0–255 scale.
    base = 240 * (6 + power) + strength ** 3
    defense = min(255, armor * 6)
    mitigation = 80_300 - (561 - defense) * defense
    divisor = 240 * 80_300 * 256
    return max(1, (base * mitigation * variance + divisor // 2) // divisor)


def critical_chance(attacker_luck, target_luck, equipment_bonus=0):
    return max(0, min(100, attacker_luck - target_luck + equipment_bonus))
