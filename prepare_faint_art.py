"""Fit Temur's generated faint pose to Retri's existing battle cell."""
from pathlib import Path
import pygame

ROOT = Path(__file__).resolve().parent / "assets" / "battle"


def prepare():
    reference = pygame.image.load(str(ROOT / "retri-fainted-v2.png"))
    bounds = reference.get_bounding_rect(min_alpha=128)
    source = pygame.image.load(str(ROOT / "temur-fainted-source.png"))
    source = source.subsurface(source.get_bounding_rect(min_alpha=128))
    pose = pygame.transform.scale(source, bounds.size)
    for y in range(pose.get_height()):
        for x in range(pose.get_width()):
            color = pose.get_at((x, y))
            pose.set_at((x, y), (color.r, color.g, color.b, 255 if color.a >= 128 else 0))
    result = pygame.Surface(reference.get_size(), pygame.SRCALPHA)
    result.blit(pose, bounds.topleft)
    pygame.image.save(result, str(ROOT / "temur-fainted-v1.png"))


if __name__ == "__main__":
    prepare()
