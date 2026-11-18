"""Build native grass and road transitions from the original Sunrest tiles."""
from pathlib import Path

import pygame

ART = Path(__file__).resolve().parent / "assets" / "grassland"
SIZE = 16


def load(name):
    return pygame.image.load(ART / f"{name}.png")


def save(surface, name):
    pygame.image.save(surface, ART / f"{name}.png")


def stable(x, y):
    value = (x * 0x45d9f3b + y * 0x119de1f3) & 0xffffffff
    value = ((value ^ (value >> 16)) * 0x45d9f3b) & 0xffffffff
    return (value ^ (value >> 16)) & 255


def soften(tiles):
    base = [pygame.Color(*(sum(tile.get_at((x, y))[channel] for tile in tiles) // len(tiles)
                           for channel in range(3)))
            for y in range(SIZE) for x in range(SIZE)]
    results = []
    for tile in tiles:
        result = tile.copy()
        for y in range(SIZE):
            for x in range(SIZE):
                distance = min(x, y, SIZE - 1 - x, SIZE - 1 - y)
                texture = tile.get_at((x, y))
                background = base[y * SIZE + x]
                # A shared muted border blends tiles while leaving their centers distinct.
                result.set_at((x, y), background.lerp(texture, min(1, (distance + 1) / 6)))
        results.append(result)
    return results


def prepare():
    grass = [load(f"grass{i}") for i in range(4)]
    grass += [grass[0].copy(), pygame.transform.flip(grass[1], True, False)]
    grass[4].fill((16, 11, 0), special_flags=pygame.BLEND_RGB_ADD)
    grass = soften(grass)
    path = soften([load(f"path{i}") for i in range(2)])
    for i, tile in enumerate(grass):
        save(tile, f"meadow{i}")
    for i, tile in enumerate(path):
        save(tile, f"road{i}")
        for direction in (-1, 1):
            for shift in range(4):
                edge = tile.copy()
                for y in range(SIZE):
                    boundary = 4 + shift + stable(y, i) % 4
                    for x in range(SIZE):
                        distance = x if direction == -1 else SIZE - 1 - x
                        amount = max(0, min(1, (distance - boundary + 2) / 5))
                        field = grass[i].get_at((x, y))
                        edge.set_at((x, y), field.lerp(tile.get_at((x, y)), amount))
                save(edge, f"road-edge-{direction}-{shift}-{i}")


if __name__ == "__main__":
    prepare()
