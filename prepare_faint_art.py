"""Fit Temur's fainted art to the battle cell at native pixel scale."""
from pathlib import Path
import pygame

ROOT = Path(__file__).resolve().parent / "assets" / "battle"


def prepare():
    reference = pygame.image.load(str(ROOT / "retri-fainted-v2.png"))
    bounds = reference.get_bounding_rect(min_alpha=128)
    source = pygame.image.load(str(ROOT / "temur-fainted-v3-source.png"))
    crop = source.subsurface(source.get_bounding_rect(min_alpha=128))
    # The character's head and body need the same visual mass as his standing
    # pose; fit in a 31x15 area while keeping the 32x32 frame and baseline.
    scale = min(31 / crop.get_width(), 15 / crop.get_height())
    size = (max(1, round(crop.get_width() * scale)),
            max(1, round(crop.get_height() * scale)))
    pose = pygame.transform.scale(crop, size)
    for y in range(pose.get_height()):
        for x in range(pose.get_width()):
            color = pose.get_at((x, y))
            pose.set_at((x, y), (color.r, color.g, color.b, 255 if color.a >= 128 else 0))
    result = pygame.Surface(reference.get_size(), pygame.SRCALPHA)
    result.blit(pose, ((result.get_width() - size[0]) // 2, bounds.bottom - size[1]))
    pygame.image.save(result, str(ROOT / "temur-fainted-v1.png"))


if __name__ == "__main__":
    prepare()
